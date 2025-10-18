import re
import os
from typing import Any, Union
from pathlib import Path
import pandas as pd

class SecurityUtils:
    """Security utilities for input validation and sanitization."""

    # File upload security
    MAX_FILE_SIZE_MB = 50
    ALLOWED_EXTENSIONS = {'.csv', '.xlsx', '.xls'}
    DANGEROUS_PATTERNS = [
        r'<script', r'javascript:', r'on\w+\s*=', r'eval\s*\(',
        r'document\.', r'window\.', r'alert\s*\(', r'prompt\s*\('
    ]

    # TODO - Implement configurable security policies via environment variables
    # TODO - Add support for custom dangerous pattern definitions
    # TODO - Implement security event logging and monitoring

    @staticmethod
    def validate_file_upload(file_path: Union[str, Path], max_size_mb: int = MAX_FILE_SIZE_MB) -> tuple[bool, str]:
        """Validate uploaded file for security and size constraints."""
        try:
            path = Path(file_path)

            # Check if file exists
            if not path.exists():
                return False, "File does not exist"

            # Check file extension
            if path.suffix.lower() not in SecurityUtils.ALLOWED_EXTENSIONS:
                return False, f"File type not allowed. Allowed: {', '.join(SecurityUtils.ALLOWED_EXTENSIONS)}"

            # Check file size
            file_size_mb = path.stat().st_size / (1024 * 1024)
            if file_size_mb > max_size_mb:
                return False, f"File too large. Maximum size: {max_size_mb}MB"

            # Check for dangerous content in filename
            filename = path.name
            if SecurityUtils._contains_dangerous_patterns(filename):
                return False, "Filename contains potentially dangerous characters"

            return True, "File validation passed"

        except Exception as e:
            return False, f"File validation error: {str(e)}"

    # TODO - Add file content type validation beyond extension checking
    # TODO - Implement virus scanning integration for uploaded files
    # TODO - Add file integrity checking with checksums

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename to prevent path traversal and other attacks."""
        if not filename:
            return "uploaded_file.csv"

        # Remove path separators and dangerous sequences
        filename = re.sub(r'[\/\\]', '', filename)
        filename = re.sub(r'\.\.', '', filename)  # Remove ..

        # Remove dangerous characters
        filename = re.sub(r'[<>:"|?*]', '', filename)

        # Limit length
        if len(filename) > 255:
            name, ext = os.path.splitext(filename)
            filename = name[:255-len(ext)] + ext

        # Ensure it's not empty and has extension
        if not filename.strip():
            filename = "uploaded_file.csv"
        elif not os.path.splitext(filename)[1]:
            filename += ".csv"

        return filename

    @staticmethod
    def validate_csv_content(df: pd.DataFrame) -> tuple[bool, str]:
        """Validate CSV content for security issues."""
        try:
            # Check for reasonable number of columns
            if len(df.columns) > 100:
                return False, "Too many columns in CSV"

            # Check for reasonable number of rows
            if len(df) > 100000:
                return False, "Too many rows in CSV"

            # Check column names for dangerous patterns
            for col in df.columns:
                if SecurityUtils._contains_dangerous_patterns(str(col)):
                    return False, f"Column name contains dangerous pattern: {col}"

            # Check a sample of cell values
            sample_size = min(100, len(df))
            for i in range(sample_size):
                for col in df.columns:
                    value = str(df.iloc[i][col])
                    if len(value) > 10000:  # Reasonable cell content limit
                        return False, f"Cell content too large in row {i}, column {col}"
                    if SecurityUtils._contains_dangerous_patterns(value):
                        return False, f"Cell content contains dangerous pattern in row {i}, column {col}"

            return True, "CSV content validation passed"

        except Exception as e:
            return False, f"CSV validation error: {str(e)}"

    # TODO - Implement more sophisticated content analysis (SQL injection patterns, etc.)
    # TODO - Add data type validation and schema enforcement
    # TODO - Implement configurable content size limits based on data type

    @staticmethod
    def validate_api_key(api_key: str, service_name: str) -> tuple[bool, str]:
        """Validate API key format and security."""
        if not api_key or not api_key.strip():
            return False, f"{service_name} API key is required"

        key = api_key.strip()

        # Check length (reasonable bounds)
        if len(key) < 10:
            return False, f"{service_name} API key too short"
        if len(key) > 200:
            return False, f"{service_name} API key too long"

        # Check for potentially dangerous characters
        if re.search(r'[<>]', key):
            return False, f"{service_name} API key contains invalid characters"

        return True, "API key validation passed"

    @staticmethod
    def validate_year(year: Any) -> tuple[bool, int, str]:
        """Validate and sanitize year input."""
        try:
            # Convert to int
            year_int = int(float(year))

            # Check reasonable range
            if year_int < 1900 or year_int > 2100:
                return False, 0, "Year must be between 1900 and 2100"

            return True, year_int, "Year validation passed"

        except (ValueError, TypeError):
            return False, 0, "Invalid year format"

    @staticmethod
    def sanitize_string_input(input_str: str, max_length: int = 1000) -> str:
        """Sanitize string input for display."""
        if not input_str:
            return ""

        # Limit length
        if len(input_str) > max_length:
            input_str = input_str[:max_length] + "..."

        # Remove potentially dangerous HTML/script content
        for pattern in SecurityUtils.DANGEROUS_PATTERNS:
            input_str = re.sub(pattern, '', input_str, flags=re.IGNORECASE)

        return input_str.strip()

    @staticmethod
    def _contains_dangerous_patterns(text: str) -> bool:
        """Check if text contains dangerous patterns."""
        text_lower = text.lower()
        for pattern in SecurityUtils.DANGEROUS_PATTERNS:
            if re.search(pattern, text_lower):
                return True
        return False

    @staticmethod
    def rate_limit_check(identifier: str, max_requests: int, window_seconds: int) -> tuple[bool, str]:
        """Check if request should be rate limited (simplified version)."""
        # This is a simplified version - in production you'd use Redis or similar
        # For now, we'll just return True (allow) since we have the rate limiter module
        return True, "Rate limit check passed"

# TODO - Implement proper rate limiting with Redis or in-memory storage
# TODO - Add rate limit bypass mechanisms for trusted clients
# TODO - Implement adaptive rate limiting based on system load