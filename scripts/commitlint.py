#!/usr/bin/env python3
"""Lightweight Conventional Commit linter.

This script emulates the subset of commitlint rules we enforce locally without
requiring Node.js. It validates the commit summary for format, type, and
subject casing/length constraints.
"""
from __future__ import annotations

try:
    from scripts import _bootstrap  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - direct execution support
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts import _bootstrap  # noqa: F401

import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

ALLOWED_TYPES = {
    "build",
    "chore",
    "ci",
    "docs",
    "feat",
    "fix",
    "perf",
    "refactor",
    "revert",
    "style",
    "test",
}
SUMMARY_PATTERN = re.compile(r"^(?P<type>[a-z]+)(\((?P<scope>[^)]+)\))?: (?P<subject>.+)$")
SUMMARY_MAX_LENGTH = 72
IGNORED_PREFIXES = ("fixup!", "squash!")


@dataclass
class LintError:
    message: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message


def _first_meaningful_line(lines: Iterable[str]) -> str:
    for line in lines:
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _validate_summary(summary: str) -> list[LintError]:
    errors: list[LintError] = []

    for prefix in IGNORED_PREFIXES:
        if summary.startswith(prefix):
            return errors

    match = SUMMARY_PATTERN.match(summary)
    if not match:
        errors.append(
            LintError(
                "Commit message must follow '<type>(<scope>): <subject>' Conventional Commit format."
            )
        )
        return errors

    commit_type = match.group("type")
    subject = match.group("subject")

    if commit_type not in ALLOWED_TYPES:
        allowed = ", ".join(sorted(ALLOWED_TYPES))
        errors.append(LintError(f"Type '{commit_type}' is not allowed. Use one of: {allowed}."))

    if len(subject) > SUMMARY_MAX_LENGTH:
        errors.append(
            LintError(
                f"Subject is too long ({len(subject)} > {SUMMARY_MAX_LENGTH} characters). Shorten it."
            )
        )

    if subject.endswith("."):
        errors.append(LintError("Subject must not end with a period."))

    if subject and subject[0].isupper():
        errors.append(LintError("Subject should start with a lowercase letter."))

    return errors


def lint_commit_message(path: Path) -> int:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        print(f"commitlint: commit message file not found: {path}", file=sys.stderr)
        return 1

    summary = _first_meaningful_line(lines)
    if not summary:
        print("commitlint: commit message is empty.", file=sys.stderr)
        return 1

    errors = _validate_summary(summary)

    if errors:
        print("commitlint: Conventional Commit validation failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: commitlint.py <commit-message-file>", file=sys.stderr)
        return 1

    path = Path(argv[1])
    return lint_commit_message(path)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv))

