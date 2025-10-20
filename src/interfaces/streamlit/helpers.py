from __future__ import annotations

import io
import json
from dataclasses import dataclass
from typing import Iterable, Mapping, MutableMapping, Sequence

import pandas as pd


@dataclass(frozen=True)
class DownloadArtifact:
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
    """Return download payloads for the full and filtered datasets."""

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
    """Return metrics for the selected industries for side-by-side comparison."""

    if not selected_codes:
        return pd.DataFrame(columns=[
            "industry_code",
            "industry_name",
            "idiot_index",
            "value_added_pct",
            "materials_share_pct",
        ])

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
        ]
    ]
    return comparison.sort_values("idiot_index", ascending=False)


def calculate_benchmark(df: pd.DataFrame, industry_code: str | None) -> Mapping[str, float | None]:
    """Compute dataset benchmark values and optional industry deltas."""

    benchmark = {
        "idiot_index_avg": df["idiot_index"].mean(skipna=True),
        "value_added_pct_avg": df["value_added_pct"].mean(skipna=True),
        "materials_share_pct_avg": df["materials_share_pct"].mean(skipna=True),
    }
    if industry_code and industry_code in set(df["industry_code"]):
        row = df[df["industry_code"] == industry_code].iloc[0]
        benchmark.update(
            {
                "idiot_index_delta": row["idiot_index"] - benchmark["idiot_index_avg"],
                "value_added_pct_delta": row["value_added_pct"]
                - benchmark["value_added_pct_avg"],
                "materials_share_pct_delta": row["materials_share_pct"]
                - benchmark["materials_share_pct_avg"],
            }
        )
    else:
        benchmark.update(
            {
                "idiot_index_delta": None,
                "value_added_pct_delta": None,
                "materials_share_pct_delta": None,
            }
        )
    return benchmark


def prepare_trend_data(
    df: pd.DataFrame,
    selected_codes: Sequence[str],
) -> pd.DataFrame:
    """Return time-series data for selected industries."""

    if not selected_codes:
        return pd.DataFrame(columns=["year", "industry_name", "idiot_index"])

    trend = df[df["industry_code"].isin(selected_codes)].copy()
    trend = trend.sort_values(["industry_code", "year"])
    return trend[["year", "industry_name", "industry_code", "idiot_index"]]


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
