from __future__ import annotations

import pytest

from src.scripts.benchmark_metrics import (
    REQUIRED_DERIVED_COLUMNS,
    benchmark_metrics,
    build_benchmark_frame,
    main,
)


@pytest.mark.parametrize("rows", [100, 10_000, 100_000])
def test_benchmark_frame_has_requested_rows_and_base_columns(rows: int) -> None:
    frame = build_benchmark_frame(rows)
    assert len(frame) == rows
    assert {
        "industry_code",
        "industry_name",
        "year",
        "gross_output",
        "materials_cost",
        "value_added",
    } <= set(frame.columns)


def test_benchmark_result_includes_status_and_threshold() -> None:
    result = benchmark_metrics(100, runs=3, threshold_seconds=60.0)
    assert result.rows == 100
    assert result.duration_seconds >= 0
    assert result.threshold_seconds == 60.0
    assert result.passed


def test_benchmark_check_mode_fails_for_impossible_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.argv", ["benchmark_metrics.py", "--check", "--threshold-seconds", "0"])
    with pytest.raises(SystemExit, match="1"):
        main()


def test_benchmark_harness_requires_no_network_or_filesystem(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import builtins
    import socket

    monkeypatch.setattr(socket, "create_connection", lambda *args, **kwargs: pytest.fail("network"))
    monkeypatch.setattr(builtins, "open", lambda *args, **kwargs: pytest.fail("filesystem"))
    result = benchmark_metrics(100, runs=3, threshold_seconds=60.0)
    assert result.passed
    assert REQUIRED_DERIVED_COLUMNS
