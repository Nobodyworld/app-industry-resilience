"""Helper script to execute the pytest suite under Python's trace module."""

from __future__ import annotations

import os
import sys


def main() -> int:
    import pytest  # Imported lazily so environments without pytest can skip this helper.

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(repo_root)
    return pytest.main()


if __name__ == "__main__":  # pragma: no cover - script entry point
    raise SystemExit(main())

