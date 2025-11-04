"""Tests for extension system including summary, scenario, and instrumentation extensions."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.application.idiot_index_service import IdiotIndexSummary, IndustryMetrics
from src.application.scenario_planner import ScenarioResult, ScenarioSummary
from src.extensions.manager import ExtensionManager, load_extensions
from src.infrastructure.observability.instrumentation import ObservabilityRegistry


@pytest.fixture()
def sample_summary() -> IdiotIndexSummary:
    dataframe = pd.DataFrame(
        [
            {
                "industry_code": "1111",
                "industry_name": "Sample Industry",
                "materials_share_pct": 42.0,
                "idiot_index": 1.2,
                "value_added_pct": 55.0,
                "resilience_score": 1.5,
                "materials_dependency_ratio": 0.4,
                "shock_sensitivity_index": 0.5,
                "health_score": 72.0,
                "health_band": "healthy",
            },
            {
                "industry_code": "2222",
                "industry_name": "Runner Up",
                "materials_share_pct": 21.0,
                "idiot_index": 0.9,
                "value_added_pct": 48.0,
                "resilience_score": 1.3,
                "materials_dependency_ratio": 0.5,
                "shock_sensitivity_index": 0.6,
                "health_score": 61.0,
                "health_band": "watch",
            },
        ]
    )
    dataframe.attrs["source"] = "test"
    return IdiotIndexSummary(
        dataframe_full=dataframe.copy(),
        dataframe_filtered=dataframe,
        leaderboard=(
            IndustryMetrics(
                industry_code="1111",
                industry_name="Sample Industry",
                idiot_index=1.2,
                value_added_pct=None,
                materials_share_pct=42.0,
                gross_output=None,
                value_added=None,
            ),
        ),
        average_idiot_index=1.05,
        notes=tuple(),
        health_summary_full=None,
        health_summary_filtered=None,
    )


def test_builtin_extensions_register_and_contribute(sample_summary: IdiotIndexSummary) -> None:
    manager = load_extensions(
        ExtensionManager(), ["src.extensions.builtins.manufacturing_cost_driver"]
    )
    contributions = manager.apply_summary_extensions(sample_summary)

    assert any("manufacturing_cost_driver" in note for note in contributions.notes)
    assert "manufacturing_cost_driver" in contributions.metadata


def test_extension_failures_are_logged_and_ignored(sample_summary: IdiotIndexSummary) -> None:
    class BrokenExtension:
        name = "broken"

        def contribute(self, summary):  # type: ignore[override]
            raise RuntimeError("boom")

    manager = load_extensions(
        ExtensionManager(), ["src.extensions.builtins.manufacturing_cost_driver"]
    )
    manager.register_summary_extension(BrokenExtension())

    contributions = manager.apply_summary_extensions(sample_summary)

    assert "manufacturing_cost_driver" in contributions.metadata
    assert all("broken" not in note for note in contributions.notes)


def test_scenario_extension_enriches_metadata() -> None:
    manager = load_extensions(
        ExtensionManager(), ["src.extensions.builtins.manufacturing_cost_driver"]
    )
    baseline = pd.DataFrame(
        [
            {"materials_share_pct": 10.0},
            {"materials_share_pct": 20.0},
        ]
    )
    scenario = pd.DataFrame(
        [
            {"materials_share_pct": 12.0},
            {"materials_share_pct": 25.0},
        ]
    )
    deltas = pd.DataFrame([{"materials_share_pct": 2.0}])
    summary = ScenarioSummary(
        gross_output_total=1.0,
        materials_cost_total=1.0,
        value_added_total=1.0,
        idiot_index_avg=1.0,
        resilience_score_avg=1.0,
        materials_dependency_ratio_avg=1.0,
        shock_sensitivity_index_avg=1.0,
        health_score_avg=1.0,
    )
    result = ScenarioResult(
        baseline=baseline,
        scenario=scenario,
        deltas=deltas,
        baseline_summary=summary,
        scenario_summary=summary,
        delta_summary={"materials_dependency_ratio_avg": 0.0},
    )

    contributions = manager.apply_scenario_extensions(result)

    assert "manufacturing_cost_driver" in contributions.metadata
    assert any("manufacturing_cost_driver" in note for note in contributions.notes)


def test_extension_catalog_includes_data_quality() -> None:
    manager = load_extensions(ExtensionManager())
    catalog = manager.catalog()
    names = {entry.name for entry in catalog}
    assert {
        "data_quality",
        "snapshot_persistence",
        "snapshot_replication_s3",
        "snapshot_replication_debug",
    }.issubset(names)
    instrumentation_entries = [entry for entry in catalog if entry.kind == "instrumentation"]
    instrumentation_modules = {entry.module for entry in instrumentation_entries}
    assert "src.extensions.builtins.data_quality" in instrumentation_modules
    assert "src.extensions.builtins.snapshot_persistence" in instrumentation_modules
    assert "src.extensions.builtins.snapshot_replication" in instrumentation_modules
    replication_entries = [entry for entry in catalog if entry.kind == "replication"]
    replication_modules = {entry.module for entry in replication_entries}
    assert "src.extensions.builtins.snapshot_replication" in replication_modules


def test_extensions_catalog_cli_json(capsys) -> None:
    from scripts import extensions_catalog

    exit_code = extensions_catalog.main(["--json", "--kind", "instrumentation"])
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert exit_code == 0
    assert any(entry["name"] == "data_quality" for entry in payload)
    assert any(entry["name"] == "snapshot_persistence" for entry in payload)


def test_connector_catalog_includes_builtins() -> None:
    manager = load_extensions(ExtensionManager())
    manager.initialise_connectors()
    summary = manager.connector_registry.summary(include_health=True)

    assert summary["count"] >= 3
    identifiers = {item["identifier"] for item in summary["items"]}
    assert {"sample_offline", "bea", "census_asm"}.issubset(identifiers)
    sample = next(item for item in summary["items"] if item["identifier"] == "sample_offline")
    assert sample["health"]["status"] in {"pass", "warn", "fail"}


def test_snapshot_persistence_extension_persists_and_prunes(tmp_path, monkeypatch) -> None:
    from types import SimpleNamespace

    from src.extensions.builtins import snapshot_persistence

    config_stub = SimpleNamespace(
        observability_snapshot_dir=tmp_path,
        observability_snapshot_retention_count=1,
        observability_snapshot_retention_days=0,
        observability_snapshot_min_interval_seconds=0.0,
        observability_snapshot_remote=None,
    )

    monkeypatch.setattr(snapshot_persistence, "load_config", lambda: config_stub)

    class StubReplicator:
        def __init__(self) -> None:
            self.calls: list[Path] = []
            self.closed = False

        def replicate(self, snapshot, path) -> None:  # type: ignore[no-untyped-def]
            self.calls.append(path)

        def close(self) -> None:  # type: ignore[no-untyped-def]
            self.closed = True

    stub_replicator = StubReplicator()
    monkeypatch.setattr(
        snapshot_persistence,
        "build_snapshot_replicator",
        lambda _cfg: stub_replicator,
    )

    registry = ObservabilityRegistry()
    extension = snapshot_persistence._SnapshotPersistenceExtension()
    extension.register(registry)

    startup_files = sorted(tmp_path.glob("*.json"))
    assert len(startup_files) == 1

    registry.record_event(
        "service.demo",
        status="error",
        duration=0.05,
        attributes={"source": "test"},
        error="boom",
    )

    remaining_files = sorted(tmp_path.glob("*.json"))
    assert len(remaining_files) == 1
    payload = json.loads(remaining_files[0].read_text())
    assert payload["metadata"]["reason"] in {"event", "shutdown"}
    assert stub_replicator.calls
