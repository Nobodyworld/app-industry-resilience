"""Deterministic Industry Pulse exports with separate signal provenance."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from typing import Literal

import pandas as pd

from src.core.industry_pulse import IndustryPulseSeriesHistory

IndustryPulseExportFormat = Literal["csv", "json", "xlsx"]


@dataclass(frozen=True)
class IndustryPulseExportArtifact:
    label: str
    file_name: str
    mime: str
    data: bytes


def build_industry_pulse_exports(
    history: IndustryPulseSeriesHistory,
) -> tuple[IndustryPulseExportArtifact, ...]:
    """Build signal-only exports without reading or mutating annual data lineage."""

    code = history.mapping.industry_code if history.mapping else "unmapped"
    stem = f"industry_pulse_{code}"
    return (
        IndustryPulseExportArtifact(
            label="Industry Pulse observations – CSV",
            file_name=f"{stem}.csv",
            mime="text/csv",
            data=_csv_bytes(history),
        ),
        IndustryPulseExportArtifact(
            label="Industry Pulse envelope – JSON",
            file_name=f"{stem}.json",
            mime="application/json",
            data=_json_bytes(history),
        ),
        IndustryPulseExportArtifact(
            label="Industry Pulse workbook – Excel",
            file_name=f"{stem}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            data=_xlsx_bytes(history),
        ),
    )


def _csv_bytes(history: IndustryPulseSeriesHistory) -> bytes:
    fields = [
        "series_id",
        "industry_code",
        "industry_name",
        "observation_date",
        "value",
        "units",
        "seasonal_adjustment",
        "base_date",
        "release_period",
        "source",
        "retrieval_mode",
        "snapshot_sha256",
        "transformations",
        "interpretation_warning",
    ]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for observation in history.observations:
        writer.writerow(
            {
                **observation.to_dict(),
                "retrieval_mode": history.provenance.retrieval_mode,
                "snapshot_sha256": history.provenance.snapshot_sha256,
                "transformations": " | ".join(history.provenance.transformations),
                "interpretation_warning": history.limitations[0],
            }
        )
    return buffer.getvalue().encode("utf-8")


def _json_bytes(history: IndustryPulseSeriesHistory) -> bytes:
    payload = history.to_dict()
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _xlsx_bytes(history: IndustryPulseSeriesHistory) -> bytes:
    buffer = io.BytesIO()
    observation_rows = [item.to_dict() for item in history.observations]
    mapping = history.mapping.to_dict() if history.mapping else {}
    metadata = {
        "availability": history.availability,
        **mapping,
        "release_period": history.release_period,
        "observation_start": (
            history.observation_start.isoformat() if history.observation_start else None
        ),
        "observation_end": (
            history.observation_end.isoformat() if history.observation_end else None
        ),
        **history.provenance.to_dict(),
        "transformations": " | ".join(history.provenance.transformations),
        "interpretation_warning": history.limitations[0],
        "level_comparison_warning": history.limitations[1],
    }
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        workbook = writer.book
        workbook.set_properties(
            {
                "title": "Industry Pulse",
                "subject": "Reviewed offline BLS PPI context signal",
                "author": "Industry Resilience Dashboard",
                "created": history.provenance.retrieved_at.replace(tzinfo=None),
            }
        )
        pd.DataFrame(observation_rows).to_excel(writer, index=False, sheet_name="Industry Pulse")
        pd.DataFrame(
            [{"field": key, "value": _metadata_value(value)} for key, value in metadata.items()]
        ).to_excel(writer, index=False, sheet_name="Signal Metadata")
    return buffer.getvalue()


def _metadata_value(value: object) -> object:
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


__all__ = [
    "IndustryPulseExportArtifact",
    "IndustryPulseExportFormat",
    "build_industry_pulse_exports",
]
