from __future__ import annotations

import json

from scripts import bump_version as bump_module
from scripts import scaffold_extension as scaffold_module
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
        "demo_scaffold", include_scenario=True, force=False
    )

    assert module_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "src.extensions.community.demo_scaffold" in manifest["modules"]


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
