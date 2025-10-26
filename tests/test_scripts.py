from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import audit_metrics as audit_script
from scripts import bump_version as bump_module
from scripts import diagnostics_bundle
from scripts import observability_snapshot as observability_script
from scripts import run_tests_with_trace as trace_script
from scripts import scaffold_extension as scaffold_module
from scripts import scaffold_service as service_scaffold
from scripts.prefetch_data import main as prefetch_main
from scripts.prefetch_data import resolve_sources
from scripts.run_scenario import (
    build_adjustments,
    parse_adjustment_expression,
)
from scripts.run_scenario import (
    main as scenario_main,
)
from src.application import DataSource


def test_compute_module_complexity_counts_branches(monkeypatch, tmp_path) -> None:
    repo_root = tmp_path
    core_root = repo_root / "src" / "core"
    core_root.mkdir(parents=True)
    module_path = core_root / "demo.py"
    module_path.write_text(
        "def feature(flag: bool) -> int:\n    if flag:\n        return 1\n    return 0\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(audit_script, "REPO_ROOT", repo_root)
    monkeypatch.setattr(audit_script, "CORE_MODULE_ROOT", core_root)

    report = audit_script.compute_module_complexity(module_path)

    assert report.module.endswith("demo")
    assert report.complexity >= 2


def test_load_coverage_reads_value(tmp_path) -> None:
    report_path = tmp_path / "coverage.json"
    report_path.write_text(json.dumps({"overall": 93.21}), encoding="utf-8")

    value = audit_script.load_coverage(report_path)

    assert value == 93.21


def test_load_coverage_falls_back_to_xml(monkeypatch, tmp_path) -> None:
    xml_report = tmp_path / "coverage.xml"
    xml_report.write_text('<coverage line-rate="0.8765" />', encoding="utf-8")

    monkeypatch.setattr(audit_script, "REPO_ROOT", tmp_path)

    value = audit_script.load_coverage(tmp_path / "missing.json")

    assert value == pytest.approx(87.65, rel=1e-6)


def test_generate_report_aggregates_helpers(monkeypatch) -> None:
    monkeypatch.setattr(audit_script, "load_coverage", lambda *_: 91.234)
    monkeypatch.setattr(
        audit_script,
        "summarise_core_complexity",
        lambda: ([audit_script.ComplexityReport("demo", 4.2)], 4.2),
    )
    monkeypatch.setattr(
        audit_script,
        "summarise_dependencies",
        lambda: audit_script.DependencyReport(
            depth=5, cohesion_ratio=0.55, internal_edges=10, external_edges=8
        ),
    )
    monkeypatch.setattr(audit_script, "measure_service_latency", lambda **_: 0.01234)
    monkeypatch.setattr(audit_script, "code_size_megabytes", lambda: 1.234)

    payload = audit_script.generate_report(runs=3)

    assert payload["coverage_percent"] == 91.23
    assert payload["complexity_average"] == 4.2
    assert payload["dependency_depth"] == 5
    assert payload["cohesion_ratio"] == 0.55
    assert payload["idiot_index_latency_s"] == 0.0123
    assert payload["code_size_mb"] == 1.234
    assert payload["complexity_top"][0]["module"] == "demo"


def test_audit_main_writes_report(tmp_path, monkeypatch, capsys) -> None:
    output_path = tmp_path / "report.json"
    monkeypatch.setattr(
        audit_script,
        "generate_report",
        lambda **_: {"coverage_percent": 88.8, "dependency_depth": 3},
    )

    exit_code = audit_script.main(["--runs", "2", "--output", str(output_path)])

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["coverage_percent"] == 88.8
    printed = json.loads(capsys.readouterr().out)
    assert printed == payload


def test_diagnostics_bundle_main(tmp_path, monkeypatch) -> None:
    output_path = tmp_path / "diagnostics.json"
    snapshot_dir = tmp_path / "snapshots"
    monkeypatch.setenv("OBSERVABILITY_SNAPSHOT_DIR", str(snapshot_dir))

    exit_code = diagnostics_bundle.main(
        ["--output", str(output_path), "--limit-events", "5", "--pretty"]
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert "health" in payload
    assert payload["observability"]["events"]["applied_limit"] == 5
    assert payload["snapshots"]["directory"].endswith("snapshots")


def test_parse_adjustment_expression() -> None:
    adjustment = parse_adjustment_expression("codes=111|112,gross=5,materials=-3,value=2")
    assert adjustment.industry_codes == ["111", "112"]
    assert adjustment.gross_output_delta_pct == 5.0
    assert adjustment.materials_cost_delta_pct == -3.0
    assert adjustment.value_added_delta_pct == 2.0


def test_build_adjustments_handles_multiple() -> None:
    adjustments = build_adjustments(["gross=1", "codes=22,materials=-2"])
    assert len(adjustments) == 2
    assert adjustments[0].gross_output_delta_pct == 1.0
    assert adjustments[1].industry_codes == ["22"]


def test_scenario_main_generates_output(tmp_path) -> None:
    output_path = tmp_path / "scenario.json"
    exit_code = scenario_main(
        ["--adjust", "codes=22,gross=1", "--output", str(output_path), "--top", "1"]
    )
    assert exit_code == 0
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert "baseline_summary" in data
    assert data["adjustments"][0]["gross_output_delta_pct"] == 1.0


def test_prefetch_main_runs_sample(monkeypatch) -> None:
    # Limit to sample source to avoid network calls
    exit_code = prefetch_main(["--sources", "sample", "--years", "2021"])
    assert exit_code == 0


def test_resolve_sources_maps_enum() -> None:
    sources = resolve_sources(["sample", "census"])
    assert sources == [DataSource.SAMPLE, DataSource.CENSUS]


def test_scaffold_extension_generates_module(monkeypatch, tmp_path) -> None:
    manifest_path = tmp_path / "manifest.json"
    package_path = tmp_path / "community"
    monkeypatch.setattr(scaffold_module, "MANIFEST_PATH", manifest_path)
    monkeypatch.setattr(scaffold_module, "COMMUNITY_PACKAGE", package_path)

    scaffold_module._ensure_package()
    module_path = scaffold_module.scaffold_extension(
        "demo_scaffold",
        include_scenario=True,
        include_instrumentation=True,
        force=False,
    )

    assert module_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "src.extensions.community.demo_scaffold" in manifest["modules"]


def test_collect_executable_lines_skips_docstrings(tmp_path) -> None:
    module_path = tmp_path / "module.py"
    module_path.write_text(
        '"""Module doc."""\n\n\ndef demo() -> int:\n    """Function doc."""\n    return 1\n',
        encoding="utf-8",
    )

    lines = trace_script.collect_executable_lines(module_path)

    assert 1 not in lines
    assert 4 in lines
    assert 6 in lines


def test_compute_coverage_counts_all_files(tmp_path) -> None:
    package_root = tmp_path / "src"
    package_root.mkdir()
    file_path = package_root / "sample.py"
    file_path.write_text("def active() -> int:\n    return 42\n", encoding="utf-8")

    coverage_entries, overall = trace_script.compute_coverage(
        {}, repo_root=tmp_path, targets=[package_root]
    )

    assert overall == 0.0
    assert coverage_entries[0].total >= 2


def test_execute_respects_threshold(tmp_path) -> None:
    repo_root = tmp_path
    src_root = repo_root / "src"
    src_root.mkdir()
    module_path = src_root / "app.py"
    module_path.write_text("def run() -> int:\n    return 1\n", encoding="utf-8")

    def fake_runner(_: list[str]) -> tuple[int, dict[Path, dict[int, int]]]:
        return 0, {module_path.resolve(): {2: 1}}

    json_output = repo_root / "coverage.json"
    summary_output = repo_root / "coverage.txt"

    exit_code = trace_script.execute(
        [],
        threshold=50.0,
        json_output=json_output,
        summary_output=summary_output,
        repo_root=repo_root,
        paths=[module_path],
        runner=fake_runner,
    )

    assert exit_code == 0
    assert json.loads(json_output.read_text(encoding="utf-8"))["overall"] >= 50.0
    assert "Overall" in summary_output.read_text(encoding="utf-8")


def test_execute_fails_when_below_threshold(tmp_path) -> None:
    repo_root = tmp_path
    src_root = repo_root / "src"
    src_root.mkdir()
    module_path = src_root / "app.py"
    module_path.write_text("def run() -> int:\n    return 1\n", encoding="utf-8")

    def fake_runner(_: list[str]) -> tuple[int, dict[Path, dict[int, int]]]:
        return 0, {}

    json_output = repo_root / "coverage.json"
    summary_output = repo_root / "coverage.txt"

    exit_code = trace_script.execute(
        [],
        threshold=80.0,
        json_output=json_output,
        summary_output=summary_output,
        repo_root=repo_root,
        paths=[module_path],
        runner=fake_runner,
    )

    assert exit_code == 1


def test_observability_snapshot_outputs_json(capsys) -> None:
    exit_code = observability_script.main(["--pretty"])
    output = capsys.readouterr().out

    assert exit_code == 0
    payload = json.loads(output)
    assert "metrics" in payload
    assert "traces" in payload


def test_observability_snapshot_store_and_list(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("OBSERVABILITY_SNAPSHOT_DIR", str(tmp_path))

    exit_code = observability_script.main(["--store"])
    captured = capsys.readouterr()

    assert exit_code == 0
    json.loads(captured.out)  # digest payload
    assert "Stored snapshot" in captured.err
    stored_files = list(tmp_path.glob("*.json"))
    assert stored_files, "Expected snapshot file to be created"

    list_exit = observability_script.main(["--list", "--pretty"])
    listed = capsys.readouterr()

    assert list_exit == 0
    listing = json.loads(listed.out)
    assert listing and "snapshot_id" in listing[0]
    assert listing[0]["metadata"]["source"] == "cli"


def test_observability_snapshot_compare(monkeypatch, tmp_path, capsys) -> None:
    storage_dir = tmp_path / "store"
    monkeypatch.setenv("OBSERVABILITY_SNAPSHOT_DIR", str(storage_dir))

    storage_dir.mkdir()
    observability_script.main(["--store"])
    capsys.readouterr()

    output_file = tmp_path / "target.json"
    exit_code = observability_script.main(["--output", str(output_file), "--label", "comparison"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert output_file.exists()
    json.loads(captured.out)

    diff_exit = observability_script.main(["--compare", str(output_file), "--pretty"])
    diff_output = capsys.readouterr().out

    assert diff_exit == 0
    diff_payload = json.loads(diff_output)
    assert "event_counts_delta" in diff_payload
    assert diff_payload["metadata_changes"]["added"].get("label") == "comparison"


def test_scaffold_service_generates_module(monkeypatch, tmp_path) -> None:
    target = tmp_path / "services"
    monkeypatch.setattr(service_scaffold, "SERVICE_PACKAGE", target)
    module_path = service_scaffold.scaffold_service("supply_chain", force=False)

    assert module_path.exists()
    content = module_path.read_text(encoding="utf-8")
    assert "Generated service scaffold" in content


def test_bump_version_logic() -> None:
    assert bump_module.bump_version("1.2.3", "patch") == "1.2.4"
    assert bump_module.bump_version("1.2.3", "minor") == "1.3.0"
    assert bump_module.bump_version("1.2.3", "major") == "2.0.0"


def test_seed_changelog_creates_template(monkeypatch, tmp_path) -> None:
    changelog_path = tmp_path / "CHANGELOG.md"
    changelog_path.write_text("# Changelog\n", encoding="utf-8")
    monkeypatch.setattr(bump_module, "CHANGELOG_PATH", changelog_path)
    bump_module.seed_changelog("9.9.9")
    content = changelog_path.read_text(encoding="utf-8")
    assert "v9.9.9" in content
    assert "### Added" in content


def test_update_pyproject_replaces_versions(monkeypatch, tmp_path) -> None:
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text('version = "0.1.0"\nversion = "0.1.0"\n', encoding="utf-8")
    monkeypatch.setattr(bump_module, "PYPROJECT_PATH", pyproject_path)
    bump_module.update_pyproject("0.1.0", "0.2.0")
    assert pyproject_path.read_text(encoding="utf-8").count('version = "0.2.0"') == 2
