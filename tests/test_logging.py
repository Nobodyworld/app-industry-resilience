from __future__ import annotations

import io
import logging

from src.infrastructure import logging_config


def test_log_api_call_redacts_sensitive_fields() -> None:
    logging_config.logger = logging_config.setup_logging(structured=True, log_file=None)
    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    handler.setFormatter(logging_config.RedactingJSONFormatter())
    logging_config.logger.addHandler(handler)
    try:
        logging_config.log_api_call(
            "TestService",
            "endpoint",
            {"apiKey": "supersecret", "param": "value"},
        )
    finally:
        logging_config.logger.removeHandler(handler)
    output = buffer.getvalue()
    assert "***redacted***" in output
    assert "supersecret" not in output


def test_refresh_log_level_updates_logger() -> None:
    logging_config.logger = logging_config.setup_logging(structured=False, log_file=None)
    logging_config.refresh_log_level("DEBUG")
    assert logging.getLogger("idiot_index").level == logging.DEBUG
