from __future__ import annotations

import io
import json
import logging
from collections import namedtuple
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from src.infrastructure import logging_config


def _configure_json_logger(**formatter_kwargs: object) -> tuple[io.StringIO, logging.Handler]:
    logging_config.logger = logging_config.setup_logging(structured=True, log_file=None)
    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    handler.setFormatter(logging_config.RedactingJSONFormatter(**formatter_kwargs))
    logging_config.logger.addHandler(handler)
    return buffer, handler


def _configure_text_logger(**formatter_kwargs: object) -> tuple[io.StringIO, logging.Handler]:
    logging_config.logger = logging_config.setup_logging(structured=False, log_file=None)
    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    handler.setFormatter(
        logging_config.RedactingTextFormatter("%(levelname)s:%(message)s", **formatter_kwargs)
    )
    logging_config.logger.addHandler(handler)
    return buffer, handler


TokenRecord = namedtuple("TokenRecord", ["token", "description"])


@dataclass
class CredentialEnvelope:
    api_key: str
    nested: object


def test_log_api_call_redacts_sensitive_fields() -> None:
    buffer, handler = _configure_json_logger()
    try:
        logging_config.log_api_call(
            "TestService",
            "endpoint",
            {"apiKey": "supersecret", "param": "value"},
        )
    finally:
        logging_config.logger.removeHandler(handler)
    output = buffer.getvalue()
    assert logging_config.DEFAULT_REDACTION_SENTINEL in output
    assert "supersecret" not in output


def test_log_api_call_redacts_nested_sensitive_fields() -> None:
    buffer, handler = _configure_json_logger()
    payload = {
        "metadata": {
            "clientSecret": "topsecret",
            "items": [
                {"token": "abc123"},
                {"value": "safe"},
            ],
        },
        "nonSensitiveList": ["safe", {"apiKey": "hidden"}],
        "listSecrets": ["safe", "value"],
    }
    try:
        logging_config.log_api_call("TestService", "endpoint", payload)
    finally:
        logging_config.logger.removeHandler(handler)

    output = json.loads(buffer.getvalue())
    metadata = output["params"]["metadata"]
    assert metadata["clientSecret"] == logging_config.DEFAULT_REDACTION_SENTINEL
    assert metadata["items"][0]["token"] == logging_config.DEFAULT_REDACTION_SENTINEL
    assert (
        output["params"]["nonSensitiveList"][1]["apiKey"]
        == logging_config.DEFAULT_REDACTION_SENTINEL
    )
    assert output["params"]["listSecrets"] == logging_config.DEFAULT_REDACTION_SENTINEL


def test_redactor_handles_dataclasses_and_namespaces() -> None:
    buffer, handler = _configure_json_logger()
    payload = {
        "profile": CredentialEnvelope(
            api_key="abc123",
            nested={"clientSecret": "hidden", "note": "visible"},
        ),
        "namespace": SimpleNamespace(secret_token="value", visible="ok"),
    }
    try:
        logging_config.log_api_call("TestService", "endpoint", payload)
    finally:
        logging_config.logger.removeHandler(handler)

    output = json.loads(buffer.getvalue())
    credentials = output["params"]["profile"]
    assert credentials["api_key"] == logging_config.DEFAULT_REDACTION_SENTINEL
    assert credentials["nested"]["clientSecret"] == logging_config.DEFAULT_REDACTION_SENTINEL
    assert credentials["nested"]["note"] == "visible"

    namespace = output["params"]["namespace"]
    assert namespace["secret_token"] == logging_config.DEFAULT_REDACTION_SENTINEL
    assert namespace["visible"] == "ok"


def test_redactor_handles_recursive_structures() -> None:
    buffer, handler = _configure_json_logger()
    payload: dict[str, object] = {"level": "root"}
    payload["self"] = payload
    try:
        logging_config.log_api_call("TestService", "endpoint", payload)
    finally:
        logging_config.logger.removeHandler(handler)

    output = json.loads(buffer.getvalue())
    assert output["params"]["self"] == logging_config.RECURSIVE_REFERENCE_PLACEHOLDER


def test_redactor_converts_sets_and_namedtuples() -> None:
    buffer, handler = _configure_json_logger()
    token_record = TokenRecord(token="value", description="ok")
    payload = {
        "records": {token_record},
        "tupleWrapper": ("safe", {"password": "unsafe"}),
    }
    try:
        logging_config.log_api_call("TestService", "endpoint", payload)
    finally:
        logging_config.logger.removeHandler(handler)

    output = json.loads(buffer.getvalue())
    records = output["params"]["records"]
    assert isinstance(records, list)
    assert any(record["token"] == logging_config.DEFAULT_REDACTION_SENTINEL for record in records)
    tuple_wrapper = output["params"]["tupleWrapper"]
    assert tuple_wrapper[0] == "safe"
    assert tuple_wrapper[1]["password"] == logging_config.DEFAULT_REDACTION_SENTINEL


def test_redactor_handles_non_string_keys() -> None:
    buffer, handler = _configure_json_logger()
    payload = {
        1: {"apiKey": "value"},
        "details": {"password": "unsafe"},
    }
    try:
        logging_config.log_api_call("TestService", "endpoint", payload)
    finally:
        logging_config.logger.removeHandler(handler)

    output = json.loads(buffer.getvalue())
    params = output["params"]
    assert params["1"]["apiKey"] == logging_config.DEFAULT_REDACTION_SENTINEL
    assert params["details"]["password"] == logging_config.DEFAULT_REDACTION_SENTINEL


def test_json_formatter_respects_custom_sentinel() -> None:
    custom_sentinel = "<<hidden>>"
    buffer, handler = _configure_json_logger(sentinel=custom_sentinel, redact_fields=("secret",))
    try:
        logging_config.log_api_call(
            "TestService",
            "endpoint",
            {"secretValue": "disclose", "nested": {"param": "ok"}},
        )
    finally:
        logging_config.logger.removeHandler(handler)

    output = json.loads(buffer.getvalue())
    assert output["params"]["secretValue"] == custom_sentinel
    assert output["params"]["nested"] == {"param": "ok"}


def test_text_formatter_masks_tokens_case_insensitively() -> None:
    buffer, handler = _configure_text_logger()
    try:
        logging_config.logger.info(
            "APIKEY exposed",
            extra={"payload": {"apiKey": "value", "note": "safe"}},
        )
    finally:
        logging_config.logger.removeHandler(handler)

    output = buffer.getvalue()
    assert "APIK*** exposed" in output
    assert logging_config.DEFAULT_REDACTION_SENTINEL in output
    assert "APIKEY" not in output


def test_mask_text_uses_precompiled_pattern() -> None:
    pattern = logging_config._compile_token_pattern(["secret"])
    assert pattern is not None
    masked = logging_config._mask_text(
        "secret exposed",
        ("secret",),
        logging_config.DEFAULT_REDACTION_SENTINEL,
        pattern=pattern,
    )
    recomputed = logging_config._mask_text(
        "secret exposed",
        ("secret",),
        logging_config.DEFAULT_REDACTION_SENTINEL,
    )
    assert masked == recomputed


def test_refresh_log_level_updates_logger() -> None:
    logging_config.logger = logging_config.setup_logging(structured=False, log_file=None)
    logging_config.refresh_log_level("DEBUG")
    assert logging.getLogger("idiot_index").level == logging.DEBUG


def test_remote_from_env_validates_protocol(monkeypatch) -> None:
    monkeypatch.setenv("LOG_SHIP_HOST", "logs.example.com")
    monkeypatch.setenv("LOG_SHIP_PORT", "9000")
    monkeypatch.setenv("LOG_SHIP_PROTOCOL", "smtp")

    with pytest.raises(ValueError):
        logging_config._remote_from_env()

    monkeypatch.delenv("LOG_SHIP_HOST", raising=False)
    monkeypatch.delenv("LOG_SHIP_PORT", raising=False)
    monkeypatch.delenv("LOG_SHIP_PROTOCOL", raising=False)


def test_setup_logging_rejects_invalid_remote_protocol() -> None:
    remote = logging_config.RemoteLoggingConfig(host="logs.example.com", port=9000, protocol="smtp")

    with pytest.raises(ValueError):
        logging_config.setup_logging(log_file=None, remote=remote)
