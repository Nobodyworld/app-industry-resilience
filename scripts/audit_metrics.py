"""Compute stewardship metrics for the Idiot Index repository."""

from __future__ import annotations

try:
    from scripts import _bootstrap  # type: ignore  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - direct execution fallback
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts import _bootstrap  # type: ignore  # noqa: F401

import argparse
import json
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import ast
import statistics

from src.application import DataSource, IdiotIndexService

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_PATH = REPO_ROOT / "build" / "reports" / "audit-metrics.json"
CORE_MODULE_ROOT = REPO_ROOT / "src" / "core"


@dataclass(frozen=True)
class ComplexityReport:
    """Cyclomatic complexity summary for a module."""

    module: str
    complexity: float


@dataclass(frozen=True)
class DependencyReport:
    """Graph characteristics for internal module imports."""

    depth: int
    cohesion_ratio: float
    internal_edges: int
    external_edges: int


def _python_files(base: Path) -> list[Path]:
    return sorted(path for path in base.rglob("*.py") if path.is_file())


def _module_name(path: Path) -> str:
    relative = path.relative_to(REPO_ROOT).with_suffix("")
    return ".".join(relative.parts)


def _decision_points(node: ast.AST) -> int:
    if isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.IfExp)):
        return 1
    if isinstance(node, ast.Try):
        return 1 + len(node.handlers)
    if isinstance(node, ast.BoolOp):
        return max(0, len(node.values) - 1)
    return 0


def compute_module_complexity(path: Path) -> ComplexityReport:
    """Approximate cyclomatic complexity for a Python module."""

    tree = ast.parse(path.read_text(encoding="utf-8"))
    complexity = 1  # baseline path
    for node in ast.walk(tree):
        complexity += _decision_points(node)
    return ComplexityReport(module=_module_name(path), complexity=float(complexity))


def summarise_core_complexity() -> tuple[list[ComplexityReport], float]:
    """Return per-module complexity and overall average for core modules."""

    modules = [compute_module_complexity(path) for path in _python_files(CORE_MODULE_ROOT)]
    average = statistics.mean(report.complexity for report in modules) if modules else 0.0
    return modules, float(average)


def _resolve_import(module: str, node: ast.ImportFrom) -> str | None:
    package = module.split(".")
    if node.level:
        package = package[:-node.level]
    if node.module:
        package += node.module.split(".")
    if not package:
        return None
    return ".".join(part for part in package if part)


def _gather_imports(path: Path) -> tuple[str, set[str], int, int]:
    module = _module_name(path)
    internal: set[str] = set()
    internal_edges = 0
    external_edges = 0
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                target = alias.name
                if target.startswith("src."):
                    internal.add(target)
                    internal_edges += 1
                else:
                    external_edges += 1
        elif isinstance(node, ast.ImportFrom):
            target = _resolve_import(module, node)
            if not target:
                continue
            qualified = f"{target}" if target.startswith("src") else target
            if qualified.startswith("src."):
                internal.add(qualified)
                internal_edges += 1
            else:
                external_edges += 1
    return module, internal, internal_edges, external_edges


def _longest_depth(graph: Mapping[str, set[str]]) -> int:
    memo: dict[str, int] = {}

    def visit(node: str, stack: tuple[str, ...]) -> int:
        if node in memo:
            return memo[node]
        if node in stack:
            return 1
        neighbours = graph.get(node, set())
        if not neighbours:
            memo[node] = 1
            return 1
        depth = 1
        for neighbour in neighbours:
            depth = max(depth, 1 + visit(neighbour, stack + (node,)))
        memo[node] = depth
        return depth

    return max((visit(node, tuple()) for node in graph), default=0)


def summarise_dependencies() -> DependencyReport:
    """Analyse internal import graph characteristics."""

    graph: dict[str, set[str]] = {}
    internal_edges = 0
    external_edges = 0
    for path in _python_files(REPO_ROOT / "src"):
        module, internal, internal_count, external_count = _gather_imports(path)
        if internal:
            graph[module] = internal
        internal_edges += internal_count
        external_edges += external_count
    total_edges = internal_edges + external_edges
    cohesion = (internal_edges / total_edges) if total_edges else 0.0
    depth = _longest_depth(graph)
    return DependencyReport(
        depth=depth,
        cohesion_ratio=float(round(cohesion, 4)),
        internal_edges=internal_edges,
        external_edges=external_edges,
    )


def load_coverage(report_path: Path) -> float:
    """Load overall coverage percentage, falling back to coverage XML when needed."""

    if report_path.exists():
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        return float(payload.get("overall", 0.0))

    xml_report = REPO_ROOT / "coverage.xml"
    if xml_report.exists():
        root = ET.parse(xml_report).getroot()
        rate = root.get("line-rate")
        if rate is not None:
            return float(rate) * 100.0

    raise FileNotFoundError(
        "Coverage report missing: expected trace JSON or coverage.xml. Run "
        "scripts/run_tests_with_trace.py or pytest with --cov to generate reports."
    )


def measure_service_latency(runs: int = 5) -> float:
    """Measure IdiotIndexService evaluation latency using the sample dataset."""

    service = IdiotIndexService()
    durations: list[float] = []
    for _ in range(runs):
        start = time.perf_counter()
        service.evaluate(year=2021, source=DataSource.SAMPLE, top_n=5)
        durations.append(time.perf_counter() - start)
    return float(sum(durations) / len(durations))


def code_size_megabytes() -> float:
    """Return the total Python source footprint in megabytes."""

    total_bytes = sum(path.stat().st_size for path in _python_files(REPO_ROOT / "src"))
    return float(total_bytes / (1024 * 1024))


def generate_report(*, runs: int) -> dict[str, object]:
    coverage = load_coverage(REPO_ROOT / "build" / "reports" / "coverage-trace.json")
    complexity_entries, complexity_average = summarise_core_complexity()
    dependency_report = summarise_dependencies()
    latency = measure_service_latency(runs=runs)
    return {
        "coverage_percent": round(coverage, 2),
        "complexity_average": round(complexity_average, 2),
        "complexity_top": [
            {
                "module": entry.module,
                "complexity": round(entry.complexity, 2),
            }
            for entry in sorted(
                complexity_entries, key=lambda item: item.complexity, reverse=True
            )[:5]
        ],
        "dependency_depth": dependency_report.depth,
        "cohesion_ratio": dependency_report.cohesion_ratio,
        "internal_edges": dependency_report.internal_edges,
        "external_edges": dependency_report.external_edges,
        "code_size_mb": round(code_size_megabytes(), 3),
        "idiot_index_latency_s": round(latency, 4),
    }


def write_report(payload: Mapping[str, object], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


# agent-entrypoint: exposes stewardship metrics for automation pipelines.
__all__ = [
    "ComplexityReport",
    "DependencyReport",
    "compute_module_complexity",
    "summarise_core_complexity",
    "summarise_dependencies",
    "load_coverage",
    "measure_service_latency",
    "code_size_megabytes",
    "generate_report",
    "write_report",
    "main",
]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=5, help="Number of latency measurements to perform")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Path to write the audit report JSON",
    )
    args = parser.parse_args(argv)

    payload = generate_report(runs=max(1, args.runs))
    write_report(payload, args.output)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
