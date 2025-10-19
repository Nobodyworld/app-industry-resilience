import os
import tempfile

import pandas as pd

from src.security import FilePolicy, SecurityUtils


def test_validate_file_upload_with_real_path() -> None:
    policy = FilePolicy(max_size_mb=1)
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as handle:
        handle.write(b"industry_code,industry_name,year\n311,Food,2021\n")
        temp_path = handle.name

    try:
        result = SecurityUtils.validate_file_upload(temp_path, policy=policy)
        assert result.ok is True
        assert result.value is not None
    finally:
        os.unlink(temp_path)


def test_validate_file_upload_metadata() -> None:
    policy = FilePolicy(max_size_mb=1)
    result = SecurityUtils.validate_file_upload(
        "uploaded.csv", policy=policy, file_size_bytes=256
    )
    assert result.ok is True


def test_validate_file_upload_rejects_large_file() -> None:
    policy = FilePolicy(max_size_mb=1)
    result = SecurityUtils.validate_file_upload(
        "oversized.csv", policy=policy, file_size_bytes=2 * 1024 * 1024
    )
    assert result.ok is False
    assert "exceeds" in result.message


def test_sanitize_filename_removes_dangerous_sequences() -> None:
    assert SecurityUtils.sanitize_filename("../etc/passwd") != "../etc/passwd"
    assert ".." not in SecurityUtils.sanitize_filename("../etc/passwd")
    assert SecurityUtils.sanitize_filename("bad<script>.csv").endswith(".csv")


def test_validate_csv_content_checks_limits() -> None:
    df = pd.DataFrame({
        "industry_code": ["311"],
        "industry_name": ["Food"],
        "year": [2021],
        "gross_output": [1000],
    })
    result = SecurityUtils.validate_csv_content(df)
    assert result.ok is True


def test_validate_csv_content_detects_dangerous_value() -> None:
    df = pd.DataFrame({
        "industry_code": ["311"],
        "industry_name": ["<script>alert('xss')</script>"],
        "year": [2021],
    })
    result = SecurityUtils.validate_csv_content(df)
    assert result.ok is False
    assert "dangerous" in result.message.lower()


def test_validate_api_key_success_and_failure() -> None:
    success = SecurityUtils.validate_api_key("good_api_key_12345", "Test")
    assert success.ok is True
    assert success.value == "good_api_key_12345"

    failure = SecurityUtils.validate_api_key("short", "Test")
    assert failure.ok is False


def test_validate_year_bounds() -> None:
    valid = SecurityUtils.validate_year(2024)
    assert valid.ok and valid.value == 2024

    out_of_range = SecurityUtils.validate_year(1800)
    assert out_of_range.ok is False
    assert "between" in out_of_range.message


def test_sanitize_string_input_strips_and_escapes() -> None:
    sanitized = SecurityUtils.sanitize_string_input("  <script>alert('x')</script>  ")
    assert "<" not in sanitized
    assert "script" not in sanitized.lower()
    assert "alert" not in sanitized.lower()


def test_rate_limit_check_validation() -> None:
    assert SecurityUtils.rate_limit_check("id", 1, 60).ok is True
    assert SecurityUtils.rate_limit_check("id", 0, 60).ok is False
