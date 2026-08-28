"""Run detect-secrets without rewriting the reviewed baseline."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--exclude-lines", action="append", default=[])
    parser.add_argument("filenames", nargs="*")
    return parser.parse_args()


def _tracked_files(baseline: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    baseline_name = baseline.as_posix()
    return [
        filename
        for filename in completed.stdout.decode("utf-8").split("\0")
        if filename and filename != baseline_name and Path(filename).is_file()
    ]


def main() -> int:
    args = _parse_args()
    baseline = Path(args.baseline)
    filenames = [filename.replace("\\", "/") for filename in args.filenames]
    if not filenames:
        filenames = _tracked_files(baseline)

    temporary_name = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".secrets.baseline", delete=False) as temporary:
            temporary.write(baseline.read_bytes())
            temporary_name = temporary.name

        command = [
            sys.executable,
            "-m",
            "detect_secrets.pre_commit_hook",
            "--baseline",
            temporary_name,
        ]
        for pattern in args.exclude_lines:
            command.extend(["--exclude-lines", pattern])
        command.extend(filenames)

        completed = subprocess.run(command, capture_output=True, text=True)
        if completed.returncode == 3:
            return 0
        if completed.stdout:
            print(completed.stdout, end="")
        if completed.stderr:
            print(completed.stderr, end="", file=sys.stderr)
        return completed.returncode
    finally:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
