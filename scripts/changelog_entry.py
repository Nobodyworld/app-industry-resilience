"""Append a structured entry to the project changelog."""

from __future__ import annotations

import argparse
import datetime as _dt
import json
from pathlib import Path
from typing import Sequence


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", required=True, help="Feature or change title.")
    parser.add_argument(
        "--lines",
        nargs="+",
        required=True,
        help="Bullet lines describing the change.",
    )
    parser.add_argument(
        "--date",
        default=_dt.date.today().isoformat(),
        help="Entry date in ISO format (defaults to today).",
    )
    parser.add_argument(
        "--file",
        default="CHANGELOG.md",
        help="Path to the changelog file (default: CHANGELOG.md).",
    )
    parser.add_argument(
        "--metadata",
        help="Optional JSON metadata appended as an indented block.",
    )
    return parser.parse_args(argv)


def _format_entry(date: str, title: str, lines: Sequence[str], metadata: str | None) -> str:
    header = f"# {date} – {title}\n"
    body = "\n".join(f"- {line}" for line in lines)
    extras = ""
    if metadata:
        try:
            parsed = json.loads(metadata)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid metadata JSON: {exc}") from exc
        formatted = json.dumps(parsed, indent=2, sort_keys=True)
        extras = "\n" + "    " + formatted.replace("\n", "\n    ")
    return f"{header}{body}{extras}\n\n"


def append_entry(path: Path, entry: str) -> None:
    if not path.exists():
        raise SystemExit(f"Changelog file not found: {path}")
    content = path.read_text(encoding="utf-8")
    marker = "# Changelog\n"
    if not content.startswith(marker):
        raise SystemExit("Changelog must start with '# Changelog'.")
    insertion_index = content.find("\n\n")
    if insertion_index == -1:
        insertion_index = len(content)
        prefix = content
        suffix = ""
    else:
        insertion_index += 2
        prefix = content[:insertion_index]
        suffix = content[insertion_index:]
    updated = prefix + entry + suffix
    path.write_text(updated, encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    entry = _format_entry(args.date, args.title, args.lines, args.metadata)
    append_entry(Path(args.file), entry)
    print(f"[idiot-index] Changelog updated with '{args.title}'.")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
