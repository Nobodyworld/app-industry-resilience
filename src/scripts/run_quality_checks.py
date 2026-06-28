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

import shutil
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYTHON_TARGETS = [Path("scripts")]


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


def main(argv: list[str]) -> int:
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
    lint_targets = [str(target) for target in PYTHON_TARGETS if target.exists()]

    if text_files:
        run([sys.executable, "scripts/check_trailing_whitespace.py", *text_files])
        run([sys.executable, "scripts/check_trailing_whitespace.py", "--check-eof", *text_files])
        run([sys.executable, "scripts/codespell.py", *text_files])

    if python_files and lint_targets:
        run([sys.executable, "-m", "black", "--check", *lint_targets])
        run([sys.executable, "-m", "ruff", "check", *lint_targets])
        run([sys.executable, "-m", "mypy", "scripts"])

    if Path("requirements.txt").exists() and Path("requirements-dev.txt").exists():
        if _module_available("pip_audit"):
            run(
                [
                    sys.executable,
                    "-m",
                    "pip_audit",
                    "-r",
                    "requirements.txt",
                    "-r",
                    "requirements-dev.txt",
                ]
            )
        if shutil.which("detect-secrets-hook"):
            run(["detect-secrets-hook", "--baseline", ".secrets.baseline"])
        elif _module_available("detect_secrets"):
            scan_output = REPO_ROOT / "build" / "reports" / ".detect-secrets.scan.json"
            scan_output.parent.mkdir(parents=True, exist_ok=True)
            run(
                [
                    sys.executable,
                    "-m",
                    "detect_secrets",
                    "scan",
                    "--all-files",
                    "--json",
                    "--output",
                    str(scan_output),
                ]
            )

    return 0


def _module_available(module: str) -> bool:
    try:
        import importlib.util

        return importlib.util.find_spec(module) is not None
    except (ImportError, AttributeError):
        return False


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv))
