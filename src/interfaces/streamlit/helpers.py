"""Helper utilities shared by Streamlit components for state and exports."""

from __future__ import annotations

import io
import json
from collections.abc import Mapping, MutableMapping, Sequence
from dataclasses import dataclass

import pandas as pd

from src.application.scenario_planner import ScenarioResult


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
            frame.to_excel(writer, index=False, sheet_name="Idiot Index")
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

    benchmark = {
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
    if industry_code and industry_code in set(df["industry_code"]):
        row = df[df["industry_code"] == industry_code].iloc[0]
        benchmark.update(
            {
                "idiot_index_delta": row["idiot_index"] - benchmark["idiot_index_avg"],
                "value_added_pct_delta": row["value_added_pct"] - benchmark["value_added_pct_avg"],
                "materials_share_pct_delta": row["materials_share_pct"]
                - benchmark["materials_share_pct_avg"],
                "resilience_score_delta": row.get("resilience_score")
                - benchmark["resilience_score_avg"],
                "materials_dependency_ratio_delta": row.get("materials_dependency_ratio")
                - benchmark["materials_dependency_ratio_avg"],
                "shock_sensitivity_index_delta": row.get("shock_sensitivity_index")
                - benchmark["shock_sensitivity_index_avg"],
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


def prepare_trend_data(
    df: pd.DataFrame,
    selected_codes: Sequence[str],
) -> pd.DataFrame:
    """Return time-series data for the provided industry codes."""

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
    }
    return summary


def build_scenario_comparison_table(
    result: ScenarioResult,
    *,
    focus_codes: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Return baseline vs scenario metrics with delta columns."""

    baseline = result.baseline
    scenario = result.scenario

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
        data = {
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
