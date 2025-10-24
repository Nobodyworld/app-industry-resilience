from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import pytest

from src.application import DataSource, IdiotIndexSummary, evaluate_idiot_index
from src.application.idiot_index_service import (
    IdiotIndexService,
    LoggerHooks,
    sanitize_search,
)
from src.core import AppConfig, load_config


def _sample_frame() -> pd.DataFrame:
    frame = pd.DataFrame(
        [
            {
                "industry_code": "111",
                "industry_name": "Alpha Manufacturing",
                "year": 2021,
                "gross_output": 1000.0,
                "materials_cost": 400.0,
                "intermediate_inputs": None,
                "value_added": 600.0,
                "source": "Sample",
            },
            {
                "industry_code": "222",
                "industry_name": "Beta Utilities",
                "year": 2021,
                "gross_output": 500.0,
                "materials_cost": 250.0,
                "intermediate_inputs": None,
                "value_added": 250.0,
                "source": "Sample",
            },
        ]
    )
    frame.attrs["bea_metadata"] = {"notes": ["demo note"]}
    return frame


def test_evaluate_sample_uses_loader() -> None:
    summary = evaluate_idiot_index(
        year=2021,
        source=DataSource.SAMPLE,
        sample_loader=_sample_frame,
    )

    assert isinstance(summary, IdiotIndexSummary)
    assert summary.dataframe_full.shape[0] == 2
    assert summary.average_idiot_index is not None
    assert len(summary.leaderboard) == 2
    assert summary.notes == ("demo note",)


def test_evaluate_with_search_filters_results() -> None:
    summary = evaluate_idiot_index(
        year=2021,
        source=DataSource.SAMPLE,
        sample_loader=_sample_frame,
        search="  beta  ",
        top_n=5,
    )

    assert summary.dataframe_filtered.shape[0] == 1
    codes = {entry.industry_code for entry in summary.leaderboard}
    assert codes == {"222"}


def test_bea_requires_api_key() -> None:
    config = load_config({"BEA_API_KEY": ""})

    with pytest.raises(ValueError):
        evaluate_idiot_index(
            year=2021,
            source=DataSource.BEA,
            config=config,
            fetch_bea=lambda api_key, year: _sample_frame(),
        )


def test_logger_hooks_invoked() -> None:
    performance_events: list[tuple[str, float]] = []
    processing_events: list[tuple[str, int]] = []

    def log_performance(name: str, duration: float) -> None:
        performance_events.append((name, duration))

    def log_processing(name: str, count: int) -> None:
        processing_events.append((name, count))

    evaluate_idiot_index(
        year=2021,
        source=DataSource.SAMPLE,
        sample_loader=_sample_frame,
        logger_hooks=LoggerHooks(
            log_performance=log_performance,
            log_data_processing=log_processing,
        ),
    )

    assert performance_events and performance_events[0][0] == "evaluate_idiot_index"
    assert processing_events and processing_events[0][0] == "idiot_index_records"


def test_service_uses_injected_config_loader() -> None:
    calls: list[int] = []

    def custom_loader() -> AppConfig:
        calls.append(1)
        return load_config()

    service = IdiotIndexService(config_loader=custom_loader, default_sample_loader=_sample_frame)

    service.evaluate(year=2021, source=DataSource.SAMPLE)

    assert calls, "Custom config loader should be invoked"


def test_sanitize_search_handles_blank_and_malicious_input() -> None:
    assert sanitize_search("   ") is None
    assert sanitize_search(None) is None
    # Security utils strips script tags and leaves safe residue
    assert sanitize_search("<script>alert('x')</script>") == "'x')"


def test_evaluate_requires_positive_topn() -> None:
    with pytest.raises(ValueError):
        evaluate_idiot_index(year=2021, source=DataSource.SAMPLE, top_n=0, sample_loader=_sample_frame)
