"""Centralised logging utilities with structured output and redaction."""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import re
import sys
from collections.abc import Iterable, Mapping, Sequence, Set
from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any, cast

from ..core import AppConfig
from .observability import current_trace_id

_SENSITIVE_TOKENS = ("key", "token", "secret", "password", "credential")
DEFAULT_REDACTION_SENTINEL = "***redacted***"
RECURSIVE_REFERENCE_PLACEHOLDER = "<recursive reference>"


@dataclass(frozen=True, slots=True)
class PayloadRedactor:
    """Redact mapping-like payloads while guarding against cycles and custom objects."""

    sensitive_tokens: tuple[str, ...]
    sentinel: str = DEFAULT_REDACTION_SENTINEL
    _tokens_casefold: tuple[str, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "_tokens_casefold",
            tuple(token.casefold() for token in self.sensitive_tokens),
        )

    @property
    def tokens_casefold(self) -> tuple[str, ...]:
        return self._tokens_casefold

    def redact_mapping(self, mapping: Mapping[Any, Any]) -> dict[Any, Any]:
        memo: dict[int, Any] = {}
        return self._redact_mapping(mapping, memo)

    def _redact_mapping(self, mapping: Mapping[Any, Any], memo: dict[int, Any]) -> dict[Any, Any]:
        mapping_id = id(mapping)
        existing = memo.get(mapping_id)
        if existing is not None:
            if existing is _IN_PROGRESS_MARKER:
                return RECURSIVE_REFERENCE_PLACEHOLDER  # type: ignore[return-value]
            return cast(dict[Any, Any], existing)

        memo[mapping_id] = _IN_PROGRESS_MARKER
        redacted: dict[Any, Any] = {}
        for key, value in mapping.items():
            if self._key_contains_token(key):
                redacted[key] = self.sentinel
                continue
            redacted[key] = self._redact_value(value, memo)
        memo[mapping_id] = redacted
        return redacted

    def _redact_value(self, value: Any, memo: dict[int, Any]) -> Any:
        if isinstance(value, Mapping):
            return self._redact_mapping(value, memo)
        if self._is_namedtuple(value):
            return self._redact_mapping(value._asdict(), memo)
        if is_dataclass(value) and not isinstance(value, type):
            return self._redact_dataclass(value, memo)
        if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
            return self._redact_sequence(value, memo)
        if isinstance(value, Set):
            return self._redact_set(value, memo)
        if hasattr(value, "__dict__") and not isinstance(value, type):
            return self._redact_object(value, memo)
        return value

    def _redact_sequence(self, sequence: Sequence, memo: dict[int, Any]) -> Any:
        sequence_id = id(sequence)
        existing = memo.get(sequence_id)
        if existing is not None:
            if existing is _IN_PROGRESS_MARKER:
                return RECURSIVE_REFERENCE_PLACEHOLDER
            return existing

        memo[sequence_id] = _IN_PROGRESS_MARKER
        redacted_items = [self._redact_value(item, memo) for item in sequence]

        if isinstance(sequence, tuple):
            result: Any = tuple(redacted_items)
        elif isinstance(sequence, list):
            result = redacted_items
        else:
            result = list(redacted_items)
        memo[sequence_id] = result
        return result

    def _redact_dataclass(self, instance: Any, memo: dict[int, Any]) -> dict[str, Any]:
        instance_id = id(instance)
        existing = memo.get(instance_id)
        if existing is not None:
            if existing is _IN_PROGRESS_MARKER:
                return RECURSIVE_REFERENCE_PLACEHOLDER  # type: ignore[return-value]
            return cast(dict[str, Any], existing)

        memo[instance_id] = _IN_PROGRESS_MARKER
        redacted: dict[str, Any] = {}
        for data_field in fields(instance):
            field_name = data_field.name
            if self._key_contains_token(field_name):
                redacted[field_name] = self.sentinel
                continue
            redacted[field_name] = self._redact_value(getattr(instance, field_name), memo)
        memo[instance_id] = redacted
        return redacted

    def _redact_set(self, values: Set, memo: dict[int, Any]) -> list[Any]:
        set_id = id(values)
        existing = memo.get(set_id)
        if existing is not None:
            if existing is _IN_PROGRESS_MARKER:
                return RECURSIVE_REFERENCE_PLACEHOLDER  # type: ignore[return-value]
            return cast(list[Any], existing)

        memo[set_id] = _IN_PROGRESS_MARKER
        redacted_items = [self._redact_value(item, memo) for item in values]
        result: list[Any] = list(redacted_items)
        memo[set_id] = result
        return result

    def _redact_object(self, obj: Any, memo: dict[int, Any]) -> dict[str, Any]:
        obj_id = id(obj)
        existing = memo.get(obj_id)
        if existing is not None:
            if existing is _IN_PROGRESS_MARKER:
                return RECURSIVE_REFERENCE_PLACEHOLDER  # type: ignore[return-value]
            return cast(dict[str, Any], existing)

        memo[obj_id] = _IN_PROGRESS_MARKER
        attribute_map = {key: value for key, value in vars(obj).items() if not key.startswith("_")}
        redacted = self._redact_mapping(attribute_map, memo)
        memo[obj_id] = redacted
        return redacted

    def _key_contains_token(self, key: Any) -> bool:
        if not isinstance(key, str):
            return False
        key_casefold = key.casefold()
        tokens = self.tokens_casefold
        return any(token in key_casefold for token in tokens)

    @staticmethod
    def _is_namedtuple(value: Any) -> bool:
        return hasattr(value, "_asdict") and hasattr(value, "_fields")


_IN_PROGRESS_MARKER = object()
_DEFAULT_REDACTOR = PayloadRedactor(_SENSITIVE_TOKENS)


@dataclass(frozen=True)
class RemoteLoggingConfig:
    """Configuration for remote log shipping."""

    host: str
    port: int
    protocol: str = "udp"  # or "tcp"


class RedactingJSONFormatter(logging.Formatter):
    """Formatter emitting JSON with sensitive field redaction."""

    def __init__(
        self,
        *,
        redact_fields: Iterable[str] = _SENSITIVE_TOKENS,
        sentinel: str = DEFAULT_REDACTION_SENTINEL,
    ) -> None:
        super().__init__()
        self._redact_fields = tuple(redact_fields)
        self._sentinel = sentinel
        self._redactor = _build_redactor(self._redact_fields, sentinel)

    def format(self, record: logging.LogRecord) -> str:  # pragma: no cover - exercised via tests
        payload: dict[str, object] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
        }
        trace_id = getattr(record, "trace_id", None)
        if trace_id:
            payload["trace_id"] = trace_id
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        extra_payload = getattr(record, "payload", None)
        if isinstance(extra_payload, Mapping):
            payload.update(self._redactor.redact_mapping(extra_payload))
        return json.dumps(payload, ensure_ascii=False)


class RedactingTextFormatter(logging.Formatter):
    """Formatter that redacts sensitive substrings in plain text output."""

    def __init__(
        self,
        fmt: str,
        *,
        redact_fields: Iterable[str] = _SENSITIVE_TOKENS,
        sentinel: str = DEFAULT_REDACTION_SENTINEL,
    ) -> None:
        super().__init__(fmt)
        self._redact_fields = tuple(redact_fields)
        self._sentinel = sentinel
        self._redactor = _build_redactor(self._redact_fields, sentinel)
        self._token_pattern = _compile_token_pattern(self._redact_fields)

    def format(self, record: logging.LogRecord) -> str:  # pragma: no cover - exercised via tests
        rendered = super().format(record)
        extra_payload = getattr(record, "payload", None)
        if isinstance(extra_payload, Mapping):
            sanitized = self._redactor.redact_mapping(extra_payload)
            rendered = f"{rendered} | {json.dumps(sanitized, ensure_ascii=False)}"
        rendered = _mask_text(
            rendered,
            self._redact_fields,
            self._sentinel,
            pattern=self._token_pattern,
        )
        return rendered


class TraceIdFilter(logging.Filter):
    """Attach the current trace identifier to log records."""

    def filter(self, record: logging.LogRecord) -> bool:  # pragma: no cover - minimal logic
        trace_id = current_trace_id()
        record.trace_id = trace_id or "-"
        return True


def setup_logging(
    level: str = "INFO",
    log_file: str | None = "logs/app.log",
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

    for existing_handler in logger.handlers[:]:
        logger.removeHandler(existing_handler)

    formatter: logging.Formatter
    if structured:
        formatter = RedactingJSONFormatter(redact_fields=redact_fields)
    else:
        formatter = RedactingTextFormatter(
            "%(asctime)s - %(name)s - %(levelname)s - trace=%(trace_id)s - %(funcName)s:%(lineno)d - %(message)s",
            redact_fields=redact_fields,
        )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    trace_filter = TraceIdFilter()
    console_handler.addFilter(trace_filter)
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
        file_handler.addFilter(trace_filter)
        logger.addHandler(file_handler)

    if remote:
        protocol = _normalise_protocol(remote.protocol)
        remote_handler: logging.Handler
        if protocol == "tcp":
            remote_handler = logging.handlers.SocketHandler(remote.host, remote.port)
        else:
            remote_handler = logging.handlers.DatagramHandler(remote.host, remote.port)
        remote_handler.setLevel(logging.INFO)
        remote_handler.setFormatter(formatter)
        remote_handler.addFilter(trace_filter)
        logger.addHandler(remote_handler)

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
    params: Mapping[str, object] | None = None,
    *,
    success: bool = True,
    error: str | None = None,
) -> None:
    payload: dict[str, object] = {"service": service, "endpoint": endpoint}
    if params:
        payload["params"] = _redact_mapping(params, _SENSITIVE_TOKENS)
    if success:
        logger.info("API call successful", extra={"payload": payload})
    else:
        failure_payload = dict(payload)
        failure_payload["error"] = error or "unknown"
        logger.error("API call failed", extra={"payload": failure_payload})


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
    protocol = _normalise_protocol(os.getenv("LOG_SHIP_PROTOCOL", "udp"))
    return RemoteLoggingConfig(host=host, port=port, protocol=protocol)


def _safe_level(level: str) -> int:
    return getattr(logging, level.upper(), logging.INFO)


def _redact_mapping(
    mapping: Mapping[Any, object],
    sensitive_tokens: Iterable[str] = _SENSITIVE_TOKENS,
    *,
    sentinel: str = DEFAULT_REDACTION_SENTINEL,
) -> dict[Any, object]:
    tokens_tuple = tuple(sensitive_tokens)
    redactor = _build_redactor(tokens_tuple, sentinel)
    return redactor.redact_mapping(mapping)


def _build_redactor(tokens: Iterable[str], sentinel: str) -> PayloadRedactor:
    tokens_tuple = tuple(tokens)
    if (
        sentinel == _DEFAULT_REDACTOR.sentinel
        and tuple(token.casefold() for token in tokens_tuple) == _DEFAULT_REDACTOR.tokens_casefold
    ):
        return _DEFAULT_REDACTOR
    return PayloadRedactor(tokens_tuple, sentinel=sentinel)


def _mask_text(
    text: str,
    tokens: Iterable[str],
    sentinel: str,
    *,
    pattern: re.Pattern[str] | None = None,
) -> str:
    pattern_obj = pattern or _compile_token_pattern(tokens)
    if pattern_obj is None:
        return text

    def _replace(match: re.Match[str]) -> str:
        matched = match.group(0)
        if matched == sentinel:
            return matched
        if len(matched) <= 1:
            return sentinel
        return f"{matched[0]}***"

    return pattern_obj.sub(_replace, text)


def _compile_token_pattern(tokens: Iterable[str]) -> re.Pattern[str] | None:
    token_list = [token for token in tokens if token]
    if not token_list:
        return None
    return re.compile("|".join(re.escape(token) for token in token_list), re.IGNORECASE)


def _normalise_protocol(candidate: str) -> str:
    protocol = candidate.lower()
    if protocol not in {"tcp", "udp"}:
        raise ValueError("Remote logging protocol must be 'tcp' or 'udp'.")
    return protocol


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
