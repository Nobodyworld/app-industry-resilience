#!/usr/bin/env python3
"""Fallback quality gate when pre-commit is unavailable."""

from __future__ import annotations

try:
    from src.scripts import _bootstrap  # noqa: F401
except (ModuleNotFoundError, ImportError):  # pragma: no cover - fallback for direct execution
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from src.scripts import _bootstrap  # noqa: F401

import argparse
import shutil
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_PATHS = ["app.py", "src", "tests"]


def run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, cwd=REPO_ROOT)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def git_ls_files(patterns: Iterable[str]) -> list[str]:
    cmd = ["git", "ls-files", "--"] + list(patterns)
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    files = [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip() and not line.strip().startswith(".agent/")
    ]
    return files


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Run a faster local gate (skip text scans and security scans).",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip pytest execution.",
    )
    parser.add_argument(
        "--skip-security",
        action="store_true",
        help="Skip security scans (pip-audit and detect-secrets).",
    )
    parser.add_argument(
        "--python-only",
        action="store_true",
        help="Run only Python formatter/lint/type/tests (skip text-file hygiene checks).",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    text_patterns = [
        "*.py",
        "*.md",
        "*.markdown",
        "*.txt",
        "*.rst",
        "*.yml",
        "*.yaml",
        "*.json",
        "*.toml",
    ]

    text_files = git_ls_files(text_patterns)
    python_files = git_ls_files(["*.py"])

    if text_files and not args.fast and not args.python_only:
        run([sys.executable, "src/scripts/check_trailing_whitespace.py", *text_files])
        run(
            [
                sys.executable,
                "src/scripts/check_trailing_whitespace.py",
                "--check-eof",
                *text_files,
            ]
        )
        run([sys.executable, "src/scripts/codespell.py", *text_files])

    if python_files:
        run([sys.executable, "-m", "black", "--check", *PACKAGE_PATHS])
        run([sys.executable, "-m", "ruff", "check", *PACKAGE_PATHS])
        run([sys.executable, "-m", "mypy", "src"])

    if not args.skip_tests:
        run([sys.executable, "-m", "pytest", "-q"])

    if args.fast or args.skip_security:
        return 0

    if Path("requirements.txt").exists() and Path("requirements-dev.txt").exists():
        if _module_available("pip_audit"):
            report_dir = REPO_ROOT / "build" / "reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            run(
                [
                    sys.executable,
                    "-m",
                    "pip_audit",
                    "-r",
                    "requirements.txt",
                    "-r",
                    "requirements-dev.txt",
                    "--format",
                    "json",
                    "--output",
                    str(report_dir / "pip-audit.json"),
                ]
            )
        if shutil.which("detect-secrets-hook"):
            run(["detect-secrets-hook", "--baseline", "config/.secrets.baseline"])
        elif _module_available("detect_secrets"):
            scan_output = REPO_ROOT / "build" / "reports" / ".detect-secrets.scan.json"
            scan_output.parent.mkdir(parents=True, exist_ok=True)
            with scan_output.open("w", encoding="utf-8", newline="\n") as handle:
                result = subprocess.run(
                    [sys.executable, "-m", "detect_secrets", "scan", "--all-files"],
                    cwd=REPO_ROOT,
                    stdout=handle,
                )
                if result.returncode != 0:
                    raise SystemExit(result.returncode)

    return 0


def _module_available(module: str) -> bool:
    try:
        import importlib.util

        return importlib.util.find_spec(module) is not None
    except (ImportError, AttributeError):
        return False


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
