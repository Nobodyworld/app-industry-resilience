#!/usr/bin/env python
"""Bump the project version and seed a changelog entry."""

from __future__ import annotations

try:
    from src.scripts import _bootstrap  # noqa: F401
except (ModuleNotFoundError, ImportError):  # pragma: no cover - direct execution compatibility
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from src.scripts import _bootstrap  # noqa: F401

import argparse
import datetime as dt
import re
from pathlib import Path

PYPROJECT_PATH = Path("pyproject.toml")
CHANGELOG_PATH = Path("CHANGELOG.md")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--part",
        choices=["major", "minor", "patch"],
        default="patch",
        help="Semantic version part to increment (default: patch).",
    )
    parser.add_argument("--version", help="Override with an explicit version (e.g., 1.2.3).")
    return parser.parse_args()


def load_current_version() -> str:
    match = re.search(
        r'version\s*=\s*"(\d+\.\d+\.\d+)"', PYPROJECT_PATH.read_text(encoding="utf-8")
    )
    if not match:
        raise RuntimeError("Unable to locate version in pyproject.toml")
    return match.group(1)


def bump_version(version: str, part: str) -> str:
    major, minor, patch = (int(piece) for piece in version.split("."))
    if part == "major":
        major += 1
        minor = 0
        patch = 0
    elif part == "minor":
        minor += 1
        patch = 0
    else:
        patch += 1
    return f"{major}.{minor}.{patch}"


def update_pyproject(old: str, new: str) -> None:
    content = PYPROJECT_PATH.read_text(encoding="utf-8")
    content = content.replace(f'version = "{old}"', f'version = "{new}"', 1)
    content = content.replace(f'version = "{old}"', f'version = "{new}"', 1)
    PYPROJECT_PATH.write_text(content, encoding="utf-8")


def seed_changelog(version: str) -> None:
    today = dt.date.today().isoformat()
    header = f"## {today} (v{version})"
    changelog = CHANGELOG_PATH.read_text(encoding="utf-8")
    if header in changelog:
        return
    sections = "\n".join(
        [
            "### Added",
            "- _TBD_",
            "### Changed",
            "- _TBD_",
            "### Fixed",
            "- _TBD_",
            "### Removed",
            "- _TBD_",
        ]
    )
    updated = changelog.replace("# Changelog", f"# Changelog\n\n{header}\n{sections}\n\n")
    CHANGELOG_PATH.write_text(updated, encoding="utf-8")


def main() -> int:
    args = parse_args()
    current = load_current_version()
    new_version = args.version or bump_version(current, args.part)
    update_pyproject(current, new_version)
    seed_changelog(new_version)
    print(f"Bumped version: {current} -> {new_version}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
