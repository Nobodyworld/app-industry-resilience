"""Deterministic, signal-only exports for Industry Momentum results."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from typing import Literal

import pandas as pd

from src.core.industry_momentum import IndustryMomentumResult, IndustryMomentumSignalHistory

IndustryMomentumExportFormat = Literal["csv", "json", "xlsx"]


@dataclass(frozen=True)
class IndustryMomentumExportArtifact:
    label: str
    file_name: str
    mime: str
    data: bytes


def build_industry_momentum_exports(
    result: IndustryMomentumResult,
) -> tuple[IndustryMomentumExportArtifact, ...]:
    """Build standalone exports without mixing annual dashboard lineage."""

    stem = f"industry_momentum_{result.industry_code}"
    return (
        IndustryMomentumExportArtifact(
            "Industry Momentum observations – CSV",
            f"{stem}.csv",
            "text/csv",
            _csv_bytes(result),
        ),
        IndustryMomentumExportArtifact(
            "Industry Momentum envelope – JSON",
            f"{stem}.json",
            "application/json",
            _json_bytes(result),
        ),
        IndustryMomentumExportArtifact(
            "Industry Momentum workbook – Excel",
            f"{stem}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            _xlsx_bytes(result),
        ),
    )


def _histories(result: IndustryMomentumResult) -> list[IndustryMomentumSignalHistory]:
    return [history for family in result.families for history in family.histories]


def _observation_rows(result: IndustryMomentumResult) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for history in _histories(result):
        mapping = history.mapping
        provenance = history.provenance
        for observation in history.observations:
            rows.append(
                {
                    **observation.to_dict(),
                    "registry_label": mapping.registry_label,
                    "official_title": mapping.official_title,
                    "mapping_level": mapping.mapping_level,
                    "mapping_basis": mapping.mapping_basis,
                    "change_method": mapping.change_method,
                    "provider": provenance.provider if provenance else "",
                    "source_url": provenance.source_url if provenance else mapping.source_url,
                    "retrieved_at": (provenance.to_dict()["retrieved_at"] if provenance else ""),
                    "retrieval_mode": (provenance.retrieval_mode if provenance else "unavailable"),
                    "manifest_identity": provenance.manifest_identity if provenance else "",
                    "snapshot_sha256": provenance.snapshot_sha256 if provenance else "",
                    "registry_version": provenance.registry_version if provenance else "",
                    "schema_version": provenance.schema_version if provenance else "",
                    "observation_start": (
                        history.observation_start.isoformat() if history.observation_start else ""
                    ),
                    "observation_end": (
                        history.observation_end.isoformat() if history.observation_end else ""
                    ),
                    "transformations": (
                        " | ".join(provenance.transformations) if provenance else ""
                    ),
                    "interpretation_warning": history.limitations[0],
                    "comparison_warning": history.limitations[1],
                }
            )
    return rows


def _csv_bytes(result: IndustryMomentumResult) -> bytes:
    rows = _observation_rows(result)
    fields = [
        "source_family",
        "signal_type",
        "series_id",
        "published_industry_code",
        "target_industry_code",
        "mapping_relationship",
        "mapping_level",
        "registry_label",
        "official_title",
        "observation_date",
        "value",
        "units",
        "seasonal_adjustment",
        "base_period",
        "release_period",
        "source",
        "mapping_basis",
        "change_method",
        "provider",
        "source_url",
        "retrieved_at",
        "retrieval_mode",
        "manifest_identity",
        "snapshot_sha256",
        "registry_version",
        "schema_version",
        "observation_start",
        "observation_end",
        "transformations",
        "interpretation_warning",
        "comparison_warning",
    ]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: _spreadsheet_safe(row.get(field, "")) for field in fields})
    return buffer.getvalue().encode("utf-8")


def _json_bytes(result: IndustryMomentumResult) -> bytes:
    return (
        json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _xlsx_bytes(result: IndustryMomentumResult) -> bytes:
    rows = _observation_rows(result)
    signal_sheets = {
        "Price Signals": {"producer_price_index"},
        "Employment Signals": {
            "employment_count",
            "average_weekly_hours",
            "average_hourly_earnings",
        },
        "Production Signals": {"industrial_production_index"},
        "Capacity Signals": {"capacity_index", "capacity_utilization_rate"},
    }
    metadata_rows: list[dict[str, object]] = []
    for history in _histories(result):
        payload = history.to_dict()
        payload.pop("observations", None)
        metadata_rows.append(
            {
                "source_family": history.mapping.source_family,
                "signal_type": history.mapping.signal_type,
                "series_id": history.mapping.series_id,
                "metadata": json.dumps(payload, ensure_ascii=False, sort_keys=True),
            }
        )
    buffer = io.BytesIO()
    with pd.ExcelWriter(
        buffer,
        engine="xlsxwriter",
        engine_kwargs={"options": {"strings_to_formulas": False, "strings_to_urls": False}},
    ) as writer:
        workbook = writer.book
        retrieved = [
            history.provenance.retrieved_at
            for history in _histories(result)
            if history.provenance is not None
        ]
        workbook.set_properties(
            {
                "title": "Industry Momentum",
                "subject": "Reviewed official monthly context signals",
                "author": "Industry Resilience Dashboard",
                "created": min(retrieved).replace(tzinfo=None) if retrieved else None,
            }
        )
        for sheet_name, signal_types in signal_sheets.items():
            sheet_rows = [row for row in rows if row["signal_type"] in signal_types]
            pd.DataFrame(sheet_rows).map(_spreadsheet_safe).to_excel(
                writer, index=False, sheet_name=sheet_name
            )
        pd.DataFrame(metadata_rows).map(_spreadsheet_safe).to_excel(
            writer, index=False, sheet_name="Signal Metadata"
        )
    return buffer.getvalue()


def _spreadsheet_safe(value: object) -> object:
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


__all__ = [
    "IndustryMomentumExportArtifact",
    "IndustryMomentumExportFormat",
    "build_industry_momentum_exports",
]
