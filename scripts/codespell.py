#!/usr/bin/env python3
"""Offline-friendly spell checker for common typos."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve()

COMMON_MISSPELLINGS: dict[str, str] = {
    "teh": "the",
    "recieve": "receive",
    "seperate": "separate",
    "occured": "occurred",
    "occurrance": "occurrence",
    "embarass": "embarrass",
    "dependant": "dependent",
    "adress": "address",
    "definately": "definitely",
    "lenght": "length",
}


def find_typos(text: str) -> list[tuple[int, str, str]]:
    issues: list[tuple[int, str, str]] = []
    lines = text.splitlines()
    for line_no, line in enumerate(lines, start=1):
        lower = line.lower()
        for typo, suggestion in COMMON_MISSPELLINGS.items():
            for _ in re.finditer(rf"\b{re.escape(typo)}\b", lower):
                issues.append((line_no, typo, suggestion))
    return issues


def check_file(path: Path) -> list[tuple[int, str, str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    return find_typos(text)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Check files for common typos")
    parser.add_argument("files", nargs="+", help="Files to scan")
    args = parser.parse_args(argv[1:])

    had_error = False
    for file_name in args.files:
        path = Path(file_name).resolve()
        if not path.exists() or not path.is_file():
            continue
        if path == SCRIPT_PATH:
            continue
        for line_no, typo, suggestion in check_file(path):
            print(f"{path}:{line_no}: '{typo}' -> '{suggestion}'", file=sys.stderr)
            had_error = True

    return 1 if had_error else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv))
