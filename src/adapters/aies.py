"""Keyless loader for the latest Census Annual Integrated Economic Survey release."""

from __future__ import annotations

import io
import zipfile
from collections.abc import Callable
from datetime import UTC, datetime

import pandas as pd
import requests

from ..core import LineageStep, attach_lineage, build_lineage

AIES_SURVEY_YEAR = 2023
AIES_RELEASE_DATE = "2026-02-26"
AIES_BASIC_URL = "https://www2.census.gov/programs-surveys/aies/data/2023/AIES00BASIC.zip"
AIES_EXPENSE_URL = "https://www2.census.gov/programs-surveys/aies/data/2023/AIES00EXP01.zip"

Download = Callable[[str], bytes]


class AIESDataError(RuntimeError):
    """Raised when the official AIES snapshot cannot be downloaded or parsed."""


def fetch_latest_aies_snapshot(*, download: Download | None = None) -> pd.DataFrame:
    """Return the latest national AIES industry snapshot without requiring an API key."""

    downloader = download or _download
    basic = _read_zip_table(downloader(AIES_BASIC_URL), "AIES00BASIC.dat")
    expenses = _read_zip_table(downloader(AIES_EXPENSE_URL), "AIES00EXP01.dat")
    return build_aies_snapshot(basic, expenses)


def build_aies_snapshot(basic: pd.DataFrame, expenses: pd.DataFrame) -> pd.DataFrame:
    """Merge AIES revenue and operating-expense tables into the application schema."""

    key_columns = ["NAICS", "NAICS_LABEL", "YEAR"]
    basic_required = {*key_columns, "GEOTYPE", "TYPOP", "TAXSTAT", "RCPT_TOT_VAL"}
    expense_required = {*key_columns, "GEOTYPE", "TYPOP", "TAXSTAT", "EXPS_TOT_DVAL"}
    _require_columns(basic, basic_required, "AIES basic")
    _require_columns(expenses, expense_required, "AIES operating expenses")

    basic_national = _national_industries(basic).loc[:, [*key_columns, "RCPT_TOT_VAL"]]
    expense_national = _national_industries(expenses).loc[:, [*key_columns, "EXPS_TOT_DVAL"]]
    merged = basic_national.merge(
        expense_national,
        on=key_columns,
        how="inner",
        validate="one_to_one",
    )

    output = pd.DataFrame(
        {
            "industry_code": merged["NAICS"].astype("string"),
            "industry_name": merged["NAICS_LABEL"].astype("string"),
            "year": pd.to_numeric(merged["YEAR"], errors="coerce").astype("Int64"),
            # Census publishes both measures in thousands of dollars.
            "gross_output": pd.to_numeric(merged["RCPT_TOT_VAL"], errors="coerce") * 1_000,
            "materials_cost": pd.NA,
            "intermediate_inputs": (
                pd.to_numeric(merged["EXPS_TOT_DVAL"], errors="coerce") * 1_000
            ),
            "source": "Census AIES (operating-expense proxy)",
            "survey": "Annual Integrated Economic Survey",
            "release_date": AIES_RELEASE_DATE,
            "denominator_definition": "Total operating expenses",
        }
    )
    output["value_added"] = output["gross_output"] - output["intermediate_inputs"]
    output.dropna(subset=["gross_output", "intermediate_inputs"], inplace=True)
    output.sort_values(["year", "industry_code"], inplace=True)
    output.reset_index(drop=True, inplace=True)
    output.attrs["source_metadata"] = {
        "agency": "U.S. Census Bureau",
        "survey": "Annual Integrated Economic Survey",
        "survey_year": AIES_SURVEY_YEAR,
        "release_date": AIES_RELEASE_DATE,
        "basic_url": AIES_BASIC_URL,
        "expense_url": AIES_EXPENSE_URL,
        "denominator": "Total operating expenses (proxy for intermediate inputs)",
        "notes": [
            "AIES replaced the Annual Survey of Manufactures beginning with survey year 2023.",
            "This view is a cost-efficiency proxy, not the strict BEA gross-output/intermediate-inputs ratio.",
        ],
    }
    return attach_aies_snapshot_lineage(output)


def attach_aies_snapshot_lineage(frame: pd.DataFrame) -> pd.DataFrame:
    """Attach the public official-snapshot envelope to an AIES dataframe."""

    return attach_lineage(
        frame,
        build_lineage(
            source="census",
            source_kind="official_snapshot",
            dataset_id="aies",
            provider="U.S. Census Bureau",
            observation_period=AIES_SURVEY_YEAR,
            snapshot_at=datetime.fromisoformat(AIES_RELEASE_DATE).replace(tzinfo=UTC),
            retrieval_mode="snapshot",
            is_sample=False,
            is_official=True,
            transformations=(
                LineageStep(name="source_load", details={"record_count": len(frame)}),
            ),
        ),
    )


def _download(url: str) -> bytes:
    try:
        response = requests.get(
            url,
            timeout=60,
            headers={"User-Agent": "idiot-index/0.1 (+official-data-refresh)"},
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise AIESDataError(f"Unable to download official AIES data from {url}: {exc}") from exc
    return response.content


def _read_zip_table(payload: bytes, member: str) -> pd.DataFrame:
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            with archive.open(member) as stream:
                frame = pd.read_csv(stream, sep="|", dtype="string")
    except (KeyError, OSError, ValueError, zipfile.BadZipFile) as exc:
        raise AIESDataError(f"Invalid AIES archive; expected {member}.") from exc
    frame.rename(columns=lambda name: str(name).removeprefix("#"), inplace=True)
    return frame


def _national_industries(frame: pd.DataFrame) -> pd.DataFrame:
    filtered = frame[
        (frame["GEOTYPE"] == "01")
        & (frame["TYPOP"] == "00")
        & (frame["TAXSTAT"] == "00")
        # Keep comparable sector and subsector rows. Mixing deeper industry
        # groups into the same ranking would double count their parent totals.
        & frame["NAICS"].str.fullmatch(r"\d{2,3}", na=False)
    ].copy()
    filtered.drop_duplicates(subset=["NAICS", "NAICS_LABEL", "YEAR"], inplace=True)
    return filtered


def _require_columns(frame: pd.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise AIESDataError(f"{label} data is missing required columns: {', '.join(missing)}")


__all__ = [
    "AIES_BASIC_URL",
    "AIESDataError",
    "AIES_EXPENSE_URL",
    "AIES_RELEASE_DATE",
    "AIES_SURVEY_YEAR",
    "attach_aies_snapshot_lineage",
    "build_aies_snapshot",
    "fetch_latest_aies_snapshot",
]
