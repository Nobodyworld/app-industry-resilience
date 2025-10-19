"""Centralised logging utilities with structured output and redaction."""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, MutableMapping, Optional

from .config import AppConfig

_SENSITIVE_TOKENS = ("key", "token", "secret", "password", "credential")


@dataclass(frozen=True)
class RemoteLoggingConfig:
    """Configuration for remote log shipping."""

    host: str
    port: int
    protocol: str = "udp"  # or "tcp"


class RedactingJSONFormatter(logging.Formatter):
    """Formatter emitting JSON with sensitive field redaction."""

    def __init__(self, *, redact_fields: Iterable[str] = _SENSITIVE_TOKENS) -> None:
        super().__init__()
        self._redact_fields = tuple(redact_fields)

    def format(self, record: logging.LogRecord) -> str:  # pragma: no cover - exercised via tests
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        extra_payload = getattr(record, "payload", None)
        if isinstance(extra_payload, Mapping):
            payload.update(_redact_mapping(extra_payload, self._redact_fields))
        return json.dumps(payload, ensure_ascii=False)


class RedactingTextFormatter(logging.Formatter):
    """Formatter that redacts sensitive substrings in plain text output."""

    def __init__(self, fmt: str, *, redact_fields: Iterable[str] = _SENSITIVE_TOKENS) -> None:
        super().__init__(fmt)
        self._redact_fields = tuple(redact_fields)

    def format(self, record: logging.LogRecord) -> str:  # pragma: no cover - exercised via tests
        rendered = super().format(record)
        extra_payload = getattr(record, "payload", None)
        if isinstance(extra_payload, Mapping):
            sanitized = _redact_mapping(extra_payload, self._redact_fields)
            rendered = f"{rendered} | {json.dumps(sanitized, ensure_ascii=False)}"
        for token in self._redact_fields:
            rendered = rendered.replace(token, f"{token[0]}***")
        return rendered


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = "logs/app.log",
    *,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    structured: bool | None = None,
    redact_fields: Iterable[str] = _SENSITIVE_TOKENS,
    remote: RemoteLoggingConfig | None = None,
) -> logging.Logger:
    """Set up logging with optional structured output and remote shipping."""

    structured = _resolve_structured(structured)
    logger = logging.getLogger()
    logger.setLevel(_safe_level(level))

    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    formatter: logging.Formatter
    if structured:
        formatter = RedactingJSONFormatter(redact_fields=redact_fields)
    else:
        formatter = RedactingTextFormatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
            redact_fields=redact_fields,
        )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    if remote:
        handler: logging.Handler
        if remote.protocol.lower() == "tcp":
            handler = logging.handlers.SocketHandler(remote.host, remote.port)
        else:
            handler = logging.handlers.DatagramHandler(remote.host, remote.port)
        handler.setLevel(logging.INFO)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    app_logger = logging.getLogger("idiot_index")
    app_logger.setLevel(_safe_level(level))

    return app_logger


def configure_logging_from_config(
    config: AppConfig,
    *,
    structured: bool | None = None,
    remote: RemoteLoggingConfig | None = None,
) -> logging.Logger:
    """Configure logging using an :class:`AppConfig` instance."""

    structured = _resolve_structured(structured)
    remote = remote or _remote_from_env()
    return setup_logging(
        level=config.log_level,
        log_file="logs/app.log" if config.is_production else None,
        structured=structured,
        remote=remote,
    )


def refresh_log_level(level: str) -> None:
    """Dynamically adjust log levels at runtime."""

    logging.getLogger().setLevel(_safe_level(level))
    logging.getLogger("idiot_index").setLevel(_safe_level(level))


def log_api_call(
    service: str,
    endpoint: str,
    params: Optional[Mapping[str, object]] = None,
    *,
    success: bool = True,
    error: Optional[str] = None,
) -> None:
    payload = {"service": service, "endpoint": endpoint}
    if params:
        payload["params"] = _redact_mapping(params, _SENSITIVE_TOKENS)
    if success:
        logger.info("API call successful", extra={"payload": payload})
    else:
        logger.error(
            "API call failed",
            extra={"payload": {**payload, "error": error or "unknown"}},
        )


def log_performance(operation: str, duration: float, *, success: bool = True) -> None:
    message = "Operation completed" if success else "Operation failed"
    logger.info(
        message,
        extra={"payload": {"operation": operation, "duration": duration}},
    )


def log_cache_hit(cache_key: str, cache_type: str = "api") -> None:
    logger.debug(
        "Cache hit",
        extra={"payload": {"cache_type": cache_type, "cache_key": cache_key}},
    )


def log_cache_miss(cache_key: str, cache_type: str = "api") -> None:
    logger.debug(
        "Cache miss",
        extra={"payload": {"cache_type": cache_type, "cache_key": cache_key}},
    )


def log_data_processing(operation: str, records_processed: int, *, success: bool = True) -> None:
    message = "Data processing completed" if success else "Data processing failed"
    logger.log(
        logging.INFO if success else logging.ERROR,
        message,
        extra={
            "payload": {
                "operation": operation,
                "records_processed": records_processed,
            }
        },
    )


def _resolve_structured(explicit: bool | None) -> bool:
    if explicit is not None:
        return explicit
    env_value = os.getenv("LOG_STRUCTURED", "false").lower()
    return env_value in {"1", "true", "yes", "on"}


def _remote_from_env() -> RemoteLoggingConfig | None:
    host = os.getenv("LOG_SHIP_HOST")
    port_raw = os.getenv("LOG_SHIP_PORT")
    if not host or not port_raw:
        return None
    try:
        port = int(port_raw)
    except ValueError:
        raise ValueError("LOG_SHIP_PORT must be an integer if provided.") from None
    protocol = os.getenv("LOG_SHIP_PROTOCOL", "udp")
    return RemoteLoggingConfig(host=host, port=port, protocol=protocol)


def _safe_level(level: str) -> int:
    return getattr(logging, level.upper(), logging.INFO)


def _redact_mapping(
    mapping: Mapping[str, object],
    sensitive_tokens: Iterable[str],
) -> MutableMapping[str, object]:
    redacted: MutableMapping[str, object] = {}
    lower_tokens = tuple(token.lower() for token in sensitive_tokens)
    for key, value in mapping.items():
        if any(token in key.lower() for token in lower_tokens):
            redacted[key] = "***redacted***"
        else:
            redacted[key] = value
    return redacted


logger = setup_logging()


__all__ = [
    "RemoteLoggingConfig",
    "configure_logging_from_config",
    "log_api_call",
    "log_cache_hit",
    "log_cache_miss",
    "log_data_processing",
    "log_performance",
    "logger",
    "refresh_log_level",
    "setup_logging",
]
