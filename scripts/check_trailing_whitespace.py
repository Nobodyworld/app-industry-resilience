#!/usr/bin/env python3
"""Utility script to enforce trailing whitespace and EOF newline rules."""
from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path


def _read_lines(path: Path) -> Iterable[str]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            yield from handle
    except UnicodeDecodeError:
        return


def check_trailing(path: Path) -> list[tuple[int, str]]:
    violations: list[tuple[int, str]] = []
    for line_no, line in enumerate(_read_lines(path), start=1):
        stripped = line.rstrip("\n\r")
        if stripped.rstrip(" \t") != stripped:
            violations.append((line_no, "trailing whitespace"))
    return violations


def check_eof_newline(path: Path) -> bool:
    try:
        data = path.read_bytes()
    except UnicodeDecodeError:
        return True
    if not data:
        return True
    return data.endswith(b"\n")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Check files for whitespace issues")
    parser.add_argument("files", nargs="+", help="Files to inspect")
    parser.add_argument(
        "--check-eof",
        action="store_true",
        help="Only verify that the file ends with a newline",
    )
    args = parser.parse_args(argv[1:])

    had_error = False

    for file_name in args.files:
        path = Path(file_name)
        if not path.exists() or not path.is_file():
            continue

        if args.check_eof:
            if not check_eof_newline(path):
                print(f"{file_name}: missing trailing newline", file=sys.stderr)
                had_error = True
        else:
            for line_no, reason in check_trailing(path):
                print(f"{file_name}:{line_no}: {reason}", file=sys.stderr)
                had_error = True

    return 1 if had_error else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv))
