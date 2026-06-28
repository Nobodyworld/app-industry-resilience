"""Execute pytest under the built-in trace module and produce a coverage summary."""

from __future__ import annotations

try:
    from src.scripts import _bootstrap  # noqa: F401
except (ModuleNotFoundError, ImportError):  # pragma: no cover - allow CLI execution
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from src.scripts import _bootstrap  # noqa: F401

import argparse
import ast
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from trace import Trace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_DIR = REPO_ROOT / "build" / "reports"
DEFAULT_JSON_REPORT = DEFAULT_REPORT_DIR / "coverage-trace.json"
DEFAULT_SUMMARY_REPORT = DEFAULT_REPORT_DIR / "coverage-trace.txt"
DEFAULT_PATHS = [
    Path("src/core/analytics.py"),
    Path("src/application/idiot_index_service.py"),
    Path("src/interfaces/api/app.py"),
    Path("src/interfaces/api/schemas.py"),
]


@dataclass(frozen=True)
class FileCoverage:
    """Coverage metrics for an individual source file."""

    path: Path
    executed: int
    total: int

    @property
    def percent(self) -> float:
        if self.total == 0:
            return 100.0
        return (self.executed / self.total) * 100.0


CountsMapping = Mapping[Path, Mapping[int, int]]
Runner = Callable[[Sequence[str]], tuple[int, CountsMapping]]


def collect_executable_lines(path: Path) -> set[int]:
    """Return line numbers considered executable for coverage purposes."""

    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    lines = source.splitlines()

    docstring_lines: set[int] = set()
    nodes: list[ast.AST] = [tree]
    nodes.extend(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    )
    for node in nodes:
        body = getattr(node, "body", [])
        if not body:
            continue
        first = body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            start = first.lineno
            end = getattr(first, "end_lineno", start)
            docstring_lines.update(range(start, end + 1))

    executable: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.stmt):
            executable.add(node.lineno)

    filtered: set[int] = set()
    for lineno in executable:
        if lineno in docstring_lines:
            continue
        if lineno <= 0 or lineno > len(lines):
            continue
        text = lines[lineno - 1].strip()
        if not text or text.startswith("#"):
            continue
        filtered.add(lineno)
    return filtered


def coalesce_counts(raw_counts: Mapping[tuple[str, int], int]) -> dict[Path, dict[int, int]]:
    """Convert trace module results into a per-file mapping."""

    aggregated: dict[Path, dict[int, int]] = {}
    for (filename, lineno), count in raw_counts.items():
        path = Path(filename).resolve()
        file_counts = aggregated.setdefault(path, {})
        file_counts[lineno] = file_counts.get(lineno, 0) + count
    return aggregated


def compute_coverage(
    counts: CountsMapping, *, repo_root: Path, targets: Sequence[Path] | None = None
) -> tuple[list[FileCoverage], float]:
    """Calculate coverage metrics for the specified Python modules."""

    if targets:
        gathered: set[Path] = set()
        for target in targets:
            resolved = target if target.is_absolute() else (repo_root / target)
            if resolved.is_dir():
                gathered.update(path.resolve() for path in resolved.rglob("*.py"))
            elif resolved.suffix == ".py" and resolved.exists():
                gathered.add(resolved.resolve())
        files = sorted(gathered)
    else:
        files = sorted((repo_root / "src").rglob("*.py"))
    coverage_entries: list[FileCoverage] = []
    total_lines = 0
    total_executed = 0

    for file_path in files:
        executable = collect_executable_lines(file_path)
        executed = sum(1 for line in executable if counts.get(file_path, {}).get(line))
        coverage_entries.append(FileCoverage(file_path, executed, len(executable)))
        total_lines += len(executable)
        total_executed += executed

    overall = 100.0 if total_lines == 0 else (total_executed / total_lines) * 100.0
    return coverage_entries, overall


def run_with_trace(pytest_args: Sequence[str]) -> tuple[int, CountsMapping]:
    """Execute pytest and return the exit code alongside trace counts."""

    tracer = Trace(count=True, trace=False, ignoredirs=[sys.prefix, sys.exec_prefix])
    exit_code = tracer.runfunc(pytest.main, list(pytest_args))
    results = tracer.results()
    counts = coalesce_counts(results.counts)
    return int(exit_code or 0), counts


def execute(
    pytest_args: Sequence[str],
    *,
    threshold: float,
    json_output: Path,
    summary_output: Path,
    repo_root: Path,
    paths: Sequence[Path] | None,
    runner: Runner = run_with_trace,
) -> int:
    """Run tests with trace coverage and persist reports."""

    exit_code, counts = runner(pytest_args)
    if exit_code != 0:
        return int(exit_code)

    coverage_entries, overall = compute_coverage(counts, repo_root=repo_root, targets=paths)

    json_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)

    report_payload = {
        "overall": overall,
        "files": [
            {
                "path": str(entry.path.relative_to(repo_root)),
                "executed": entry.executed,
                "total": entry.total,
                "percent": entry.percent,
            }
            for entry in coverage_entries
        ],
    }
    json_output.write_text(json.dumps(report_payload, indent=2), encoding="utf-8")

    summary_lines = ["Coverage summary:", f"  Overall: {overall:.2f}%"]
    for entry in coverage_entries:
        relative = entry.path.relative_to(repo_root)
        summary_lines.append(
            f"  {relative}: {entry.executed}/{entry.total} lines ({entry.percent:.2f}%)"
        )
    summary_output.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    print(f"Trace coverage overall: {overall:.2f}% (reports: {json_output}, {summary_output})")

    if overall < threshold:
        print(
            f"Coverage {overall:.2f}% is below the required threshold of {threshold:.2f}%.",
            file=sys.stderr,
        )
        return 1
    return 0


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "pytest_args", nargs=argparse.REMAINDER, help="Arguments forwarded to pytest."
    )
    parser.add_argument(
        "--threshold", type=float, default=90.0, help="Minimum overall coverage percentage."
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=DEFAULT_JSON_REPORT,
        help="Path to write the JSON coverage report.",
    )
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=DEFAULT_SUMMARY_REPORT,
        help="Path to write the textual coverage summary.",
    )
    parser.add_argument(
        "--paths",
        nargs="*",
        type=Path,
        default=None,
        help="Optional list of files or directories to measure coverage for (relative to repo root).",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    pytest_args = list(args.pytest_args)
    if pytest_args and pytest_args[0] == "--":
        pytest_args = pytest_args[1:]
    json_output = (
        args.json_output if args.json_output.is_absolute() else REPO_ROOT / args.json_output
    )
    summary_output = (
        args.summary_output
        if args.summary_output.is_absolute()
        else REPO_ROOT / args.summary_output
    )
    configured_paths = args.paths or DEFAULT_PATHS
    target_paths = [path if path.is_absolute() else (REPO_ROOT / path) for path in configured_paths]
    return execute(
        pytest_args,
        threshold=args.threshold,
        json_output=json_output,
        summary_output=summary_output,
        repo_root=REPO_ROOT,
        paths=target_paths,
    )


if __name__ == "__main__":
    raise SystemExit(main())
