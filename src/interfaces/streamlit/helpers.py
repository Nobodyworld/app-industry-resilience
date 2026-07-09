"""Helper utilities shared by Streamlit components for state and exports."""

from __future__ import annotations

import io
import json
import logging
from collections.abc import Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pandas as pd

from src.application.scenario_planner import ScenarioResult
from src.core import HealthSummary
from src.core.metrics import MetricConfig, compute_metrics
from src.infrastructure.observability.storage import (
    ObservabilitySnapshot,
    SnapshotStorage,
)


@dataclass(frozen=True)
class DownloadArtifact:
    """Materialised file ready to be served via a Streamlit download button."""

    label: str
    file_name: str
    mime: str
    data: bytes


def prepare_download_artifacts(
    df_full: pd.DataFrame,
    df_filtered: pd.DataFrame,
    *,
    base_name: str,
) -> list[DownloadArtifact]:
    """Return download payloads for the full and filtered datasets.

    The helper eagerly renders CSV, JSON, and optional Excel artefacts so the
    Streamlit layer simply iterates over the resulting dataclasses when
    building download buttons.
    """

    artifacts: list[DownloadArtifact] = []

    def _csv_bytes(frame: pd.DataFrame) -> bytes:
        buffer = io.StringIO()
        frame.to_csv(buffer, index=False)
        return buffer.getvalue().encode()

    def _json_bytes(frame: pd.DataFrame) -> bytes:
        return json.dumps(frame.to_dict(orient="records"), ensure_ascii=False).encode()

    def _excel_bytes(frame: pd.DataFrame) -> bytes | None:
        try:
            import xlsxwriter  # noqa: F401
        except ModuleNotFoundError:
            return None
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            frame.to_excel(writer, index=False, sheet_name="Cost Structure")
        return buffer.getvalue()

    options = {
        "full": df_full,
        "filtered": df_filtered,
    }
    for suffix, frame in options.items():
        label_hint = "All rows" if suffix == "full" else "Current view"
        safe_base = base_name.replace(".csv", "")
        artifacts.extend(
            [
                DownloadArtifact(
                    label=f"{label_hint} – CSV",
                    file_name=f"{safe_base}_{suffix}.csv",
                    mime="text/csv",
                    data=_csv_bytes(frame),
                ),
                DownloadArtifact(
                    label=f"{label_hint} – JSON",
                    file_name=f"{safe_base}_{suffix}.json",
                    mime="application/json",
                    data=_json_bytes(frame),
                ),
            ]
        )
        excel_payload = _excel_bytes(frame)
        if excel_payload is not None:
            artifacts.append(
                DownloadArtifact(
                    label=f"{label_hint} – Excel",
                    file_name=f"{safe_base}_{suffix}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    data=excel_payload,
                )
            )
    return artifacts


def build_comparison_table(
    df: pd.DataFrame,
    selected_codes: Sequence[str],
) -> pd.DataFrame:
    """Return metrics for ``selected_codes`` suitable for side-by-side display."""

    # Ensure dataframe contains derived metrics required by the UI helpers.
    df = _ensure_metrics(df)

    if not selected_codes:
        return pd.DataFrame(
            columns=[
                "industry_code",
                "industry_name",
                "idiot_index",
                "value_added_pct",
                "materials_share_pct",
                "resilience_score",
                "materials_dependency_ratio",
                "shock_sensitivity_index",
            ]
        )

    comparison = df[df["industry_code"].isin(selected_codes)].copy()
    comparison = comparison[
        [
            "industry_code",
            "industry_name",
            "idiot_index",
            "value_added_pct",
            "materials_share_pct",
            "gross_output",
            "value_added",
            "resilience_score",
            "materials_dependency_ratio",
            "shock_sensitivity_index",
        ]
    ]
    return comparison.sort_values("idiot_index", ascending=False)


def calculate_benchmark(df: pd.DataFrame, industry_code: str | None) -> Mapping[str, float | None]:
    """Compute dataset benchmark values and optional industry deltas."""

    df = _ensure_metrics(df)

    benchmark: dict[str, float | None] = {
        "idiot_index_avg": df["idiot_index"].mean(skipna=True),
        "value_added_pct_avg": df["value_added_pct"].mean(skipna=True),
        "materials_share_pct_avg": df["materials_share_pct"].mean(skipna=True),
        "resilience_score_avg": df.get("resilience_score", pd.Series(dtype="float64")).mean(
            skipna=True
        ),
        "materials_dependency_ratio_avg": df.get(
            "materials_dependency_ratio", pd.Series(dtype="float64")
        ).mean(skipna=True),
        "shock_sensitivity_index_avg": df.get(
            "shock_sensitivity_index", pd.Series(dtype="float64")
        ).mean(skipna=True),
    }

    def _optional_number(value: Any) -> float | None:
        if value is None or pd.isna(value):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _delta(left: Any, right: Any) -> float | None:
        left_num = _optional_number(left)
        right_num = _optional_number(right)
        if left_num is None or right_num is None:
            return None
        return left_num - right_num

    if industry_code and industry_code in set(df["industry_code"]):
        row = df[df["industry_code"] == industry_code].iloc[0]
        benchmark.update(
            {
                "idiot_index_delta": _delta(row.get("idiot_index"), benchmark["idiot_index_avg"]),
                "value_added_pct_delta": _delta(
                    row.get("value_added_pct"), benchmark["value_added_pct_avg"]
                ),
                "materials_share_pct_delta": _delta(
                    row.get("materials_share_pct"), benchmark["materials_share_pct_avg"]
                ),
                "resilience_score_delta": _delta(
                    row.get("resilience_score"), benchmark["resilience_score_avg"]
                ),
                "materials_dependency_ratio_delta": _delta(
                    row.get("materials_dependency_ratio"),
                    benchmark["materials_dependency_ratio_avg"],
                ),
                "shock_sensitivity_index_delta": _delta(
                    row.get("shock_sensitivity_index"),
                    benchmark["shock_sensitivity_index_avg"],
                ),
            }
        )
    else:
        benchmark.update(
            {
                "idiot_index_delta": None,
                "value_added_pct_delta": None,
                "materials_share_pct_delta": None,
                "resilience_score_delta": None,
                "materials_dependency_ratio_delta": None,
                "shock_sensitivity_index_delta": None,
            }
        )
    return benchmark


def build_health_sector_table(summary: HealthSummary | None) -> pd.DataFrame:
    """Return a tidy dataframe describing health scores per cohort."""

    if summary is None:
        return pd.DataFrame(
            columns=[
                "cohort",
                "industries",
                "average_health_score",
                "risk_band",
                "average_idiot_index",
            ]
        )

    rows = [
        {
            "cohort": "Overall",
            "industries": summary.overall.industries,
            "average_health_score": summary.overall.average_health_score,
            "risk_band": summary.overall.risk_band,
            "average_idiot_index": summary.overall.average_idiot_index,
        }
    ]
    for aggregate in summary.sectors:
        rows.append(
            {
                "cohort": f"Sector {aggregate.label}",
                "industries": aggregate.industries,
                "average_health_score": aggregate.average_health_score,
                "risk_band": aggregate.risk_band,
                "average_idiot_index": aggregate.average_idiot_index,
            }
        )
    table = pd.DataFrame(rows)
    return table.sort_values("average_health_score", ascending=False, na_position="last")


def build_health_band_distribution(summary: HealthSummary | None) -> pd.DataFrame:
    """Return risk band counts for charting or tables."""

    if summary is None:
        return pd.DataFrame(columns=["band", "industries", "percentage"])
    return pd.DataFrame([band.__dict__ for band in summary.band_breakdown])


def build_health_risk_table(summary: HealthSummary | None, *, limit: int = 5) -> pd.DataFrame:
    """Return highest-risk industries based on health score."""

    if summary is None or not summary.top_risks:
        return pd.DataFrame(columns=["industry_code", "industry_name", "health_score", "band"])
    rows = [risk.__dict__ for risk in summary.top_risks[:limit]]
    table = pd.DataFrame(rows)
    return table.sort_values("health_score", ascending=True, na_position="last")


def extract_health_badge(summary: HealthSummary | None) -> Mapping[str, str | None]:
    """Return formatted values for badge display."""

    if summary is None:
        return {"score": None, "band": None}
    score = summary.overall.average_health_score
    band = summary.overall.risk_band
    return {
        "score": f"{score:.1f}" if score is not None else None,
        "band": band,
    }


def prepare_trend_data(
    df: pd.DataFrame,
    selected_codes: Sequence[str],
) -> pd.DataFrame:
    """Return time-series data for the provided industry codes."""

    df = _ensure_metrics(df)

    if not selected_codes:
        return pd.DataFrame(columns=["year", "industry_name", "idiot_index"])

    trend = df[df["industry_code"].isin(selected_codes)].copy()
    trend = trend.sort_values(["industry_code", "year"])
    return trend[["year", "industry_name", "industry_code", "idiot_index"]]


def summarise_scenario_deltas(result: ScenarioResult, *, top_n: int = 5) -> Mapping[str, object]:
    """Return aggregate and per-industry deltas for scenario presentation."""

    top = result.deltas.sort_values("idiot_index", ascending=False).head(top_n)
    summary = {
        "baseline": result.baseline_summary,
        "scenario": result.scenario_summary,
        "delta": result.delta_summary,
        "top": top,
        "health": {
            "baseline": result.baseline_health_summary,
            "scenario": result.scenario_health_summary,
        },
    }
    return summary


def build_scenario_comparison_table(
    result: ScenarioResult,
    *,
    focus_codes: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Return baseline vs scenario metrics with delta columns."""

    baseline = _ensure_metrics(result.baseline)
    scenario = _ensure_metrics(result.scenario)

    if focus_codes:
        baseline = baseline[baseline["industry_code"].isin(focus_codes)]
        scenario = scenario[scenario["industry_code"].isin(focus_codes)]

    merged = baseline.merge(
        scenario,
        on=["industry_code", "industry_name", "year"],
        suffixes=("_baseline", "_scenario"),
    )

    metrics = [
        "gross_output",
        "materials_cost",
        "value_added",
        "idiot_index",
        "resilience_score",
        "materials_dependency_ratio",
        "shock_sensitivity_index",
    ]

    rows = []
    for row in merged.itertuples():
        data: dict[str, Any] = {
            "industry_code": row.industry_code,
            "industry_name": row.industry_name,
        }
        for metric in metrics:
            baseline_value = getattr(row, f"{metric}_baseline", None)
            scenario_value = getattr(row, f"{metric}_scenario", None)
            data[f"{metric}_baseline"] = baseline_value
            data[f"{metric}_scenario"] = scenario_value
            if baseline_value is not None and scenario_value is not None:
                data[f"{metric}_delta"] = scenario_value - baseline_value
            else:
                data[f"{metric}_delta"] = None
        rows.append(data)

    return pd.DataFrame(rows)


def _ensure_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure the DataFrame has computed derived metrics.

    If derived metric columns are missing, compute them using compute_metrics
    with caching disabled to avoid external side effects.
    """
    required = {
        "idiot_index",
        "value_added_pct",
        "materials_share_pct",
        "resilience_score",
        "materials_dependency_ratio",
        "shock_sensitivity_index",
    }
    if not required.intersection(set(df.columns)):
        # If df already has some derived columns we still prefer to compute
        # only when none are present; compute_metrics will preserve base data.
        logging.getLogger("idiot_index.helpers").info(
            "Auto-computing derived metrics for DataFrame passed into UI helper"
        )
        return compute_metrics(df.copy(), config=MetricConfig(use_cache=False))
    return df


def summarise_observability_snapshot(snapshot: ObservabilitySnapshot) -> dict[str, Any]:
    """Return structured summary data for a stored observability snapshot."""

    events = snapshot.payload.get("events", {})
    counts = events.get("counts", {})
    metrics = snapshot.payload.get("metrics", {})
    numeric_metrics = {
        key: int(value) for key, value in metrics.items() if isinstance(value, int | float)
    }
    replication_summary: dict[str, Any] | None = None
    recent_events = events.get("recent")
    if isinstance(recent_events, Sequence):
        for event in recent_events:
            if not isinstance(event, Mapping):
                continue
            if event.get("name") != "observability.snapshot.replication":
                continue
            attributes = (
                event.get("attributes") if isinstance(event.get("attributes"), Mapping) else {}
            )
            attributes = cast(Mapping[str, Any], attributes)
            replication_summary = {
                "status": event.get("status"),
                "backend": attributes.get("backend"),
                "replicator": attributes.get("replicator"),
                "path": attributes.get("path"),
                "reason": attributes.get("reason"),
                "label": attributes.get("label"),
                "trace_id": event.get("trace_id"),
                "error": event.get("error"),
                "timestamp": event.get("timestamp"),
            }
            break
    return {
        "snapshot_id": snapshot.snapshot_id,
        "captured_at": snapshot.captured_at,
        "event_total": int(events.get("total") or 0),
        "events": {key: int(counts.get(key, 0) or 0) for key in counts},
        "metadata": dict(snapshot.metadata),
        "metrics": numeric_metrics,
        "last_error": events.get("last_error"),
        "replication": replication_summary,
    }


def load_snapshot_history(base_dir: Path, limit: int = 10) -> list[dict[str, Any]]:
    """Load at most ``limit`` snapshot summaries from the given directory."""

    storage = SnapshotStorage(base_dir)
    snapshots = storage.list()
    if not snapshots:
        return []
    selected = snapshots[-limit:]
    selected.reverse()
    return [summarise_observability_snapshot(snapshot) for snapshot in selected]


def snapshot_history_table(summaries: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    """Transform snapshot summaries into a tabular dataframe for Streamlit."""

    rows: list[dict[str, Any]] = []
    for summary in summaries:
        events = summary.get("events", {})
        metadata = summary.get("metadata", {})
        replication = summary.get("replication")
        replication_label: str | None = None
        if isinstance(replication, Mapping):
            status = replication.get("status")
            backend = replication.get("backend")
            parts: list[str] = []
            if isinstance(status, str) and status.strip():
                parts.append(status.strip().capitalize())
            if isinstance(backend, str) and backend.strip():
                label = backend.strip()
                if parts:
                    parts[-1] = f"{parts[-1]} ({label})"
                else:
                    parts.append(label)
            if parts:
                replication_label = " ".join(parts)
        if not replication_label:
            replication_label = "Local only"
        rows.append(
            {
                "Snapshot": summary.get("snapshot_id"),
                "Captured": (
                    pd.to_datetime(cast(Any, summary.get("captured_at")))
                    if summary.get("captured_at") is not None
                    else pd.NaT
                ),
                "Events": summary.get("event_total", 0),
                "Errors": events.get("error", 0),
                "Success": events.get("success", 0),
                "Label": metadata.get("label"),
                "Replication": replication_label,
            }
        )
    return pd.DataFrame(rows)


def snapshot_timeline_frame(summaries: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    """Return a tidy dataframe charting event totals and error counts over time."""

    timeline: list[dict[str, Any]] = []
    for summary in summaries:
        captured_at = (
            pd.to_datetime(cast(Any, summary.get("captured_at")))
            if summary.get("captured_at") is not None
            else pd.NaT
        )
        events = summary.get("events", {})
        timeline.append(
            {
                "captured_at": captured_at,
                "event_total": summary.get("event_total", 0),
                "errors": events.get("error", 0),
                "success": events.get("success", 0),
                "snapshot_id": summary.get("snapshot_id"),
            }
        )
    return pd.DataFrame(timeline)


def decode_query_params(params: Mapping[str, list[str]]) -> MutableMapping[str, list[str]]:
    """Convert Streamlit query params into a mutable mapping preserving multiples."""

    decoded: MutableMapping[str, list[str]] = {}
    for key, values in params.items():
        if values:
            decoded[key] = list(values)
    return decoded


def encode_query_params(**state: str | Sequence[str] | None) -> Mapping[str, list[str]]:
    """Create a query param mapping suitable for Streamlit."""

    encoded: dict[str, list[str]] = {}
    for key, value in state.items():
        if value is None:
            continue
        if isinstance(value, str):
            encoded[key] = [value]
        else:
            encoded[key] = [str(item) for item in value]
    return encoded
