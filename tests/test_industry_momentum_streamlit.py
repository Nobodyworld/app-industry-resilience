"""Streamlit AppTest coverage for multi-source Industry Momentum states."""

from __future__ import annotations

from datetime import date

from streamlit.testing.v1 import AppTest


def _component(body: str) -> AppTest:
    app = AppTest.from_string(body)
    app.run(timeout=60)
    assert not app.exception
    return app


def test_exact_and_broader_state_has_sections_charts_tables_and_exports() -> None:
    app = _component("""
from datetime import date
from src.application import IndustryMomentumService
from src.interfaces.streamlit.industry_momentum import render_industry_momentum
render_industry_momentum(
    selected_industry_code="325211",
    comparison_codes=["325211", "999999"],
    service=IndustryMomentumService(as_of=date(2026, 8, 10)),
)
""")
    assert [tab.label for tab in app.tabs] == [
        "Prices",
        "Employment",
        "Production & Capacity",
    ]
    assert any("Verified exact and broader-published" in item.value for item in app.success)
    assert any("Broader published mapping" in item.value for item in app.warning)
    assert any("Comparison mapping availability" in item.value for item in app.markdown)
    comparison = next(
        item.value for item in app.dataframe if "Mapping availability" in item.value.columns
    )
    assert comparison[["Annual industry code", "Mapping availability"]].to_dict(
        orient="records"
    ) == [
        {"Annual industry code": "325211", "Mapping availability": "Available"},
        {"Annual industry code": "999999", "Mapping availability": "Unmapped"},
    ]
    assert len(app.get("plotly_chart")) == 5
    assert len(app.dataframe) >= 7
    assert len(app.download_button) == 3
    assert any("Accessible monthly data table" in item.value for item in app.markdown)
    history_control = next(
        item
        for item in app.checkbox
        if item.label == "Use a custom Industry Momentum history window"
    )
    assert history_control.value is False
    assert not app.date_input


def test_user_reachable_future_window_renders_empty_range_without_claims() -> None:
    app = _component("""
from datetime import date
from src.application import IndustryMomentumService
from src.interfaces.streamlit.industry_momentum import render_industry_momentum
render_industry_momentum(
    selected_industry_code="325211",
    comparison_codes=[],
    service=IndustryMomentumService(as_of=date(2026, 8, 10)),
)
""")
    next(
        item
        for item in app.checkbox
        if item.label == "Use a custom Industry Momentum history window"
    ).check().run(timeout=60)
    next(item for item in app.date_input if item.label == "History start month").set_value(
        date(2030, 1, 17)
    ).run(timeout=60)
    next(item for item in app.date_input if item.label == "History end month").set_value(
        date(2030, 12, 28)
    ).run(timeout=60)

    assert not app.exception
    assert any("Overall state: **empty_range**" in item.value for item in app.markdown)
    assert any("requested date range is empty" in item.value for item in app.info)
    assert any("requested snapshot range has no observations" in item.value for item in app.info)
    assert not any(item.label == "Latest value" for item in app.metric)
    assert not app.get("plotly_chart")


def test_valid_window_filters_displayed_rows_and_signal_exports() -> None:
    app = _component("""
import csv
import io
from datetime import date
import streamlit as st
from src.application import IndustryMomentumService
from src.application.industry_momentum_exports import build_industry_momentum_exports as real_build
from src.interfaces.streamlit import industry_momentum as momentum_ui
captured = []
def capture_exports(result):
    artifacts = real_build(result)
    csv_rows = list(csv.DictReader(io.StringIO(artifacts[0].data.decode("utf-8"))))
    captured.append((result.requested_filters, len(csv_rows)))
    return artifacts
momentum_ui.build_industry_momentum_exports = capture_exports
momentum_ui.render_industry_momentum(
    selected_industry_code="325211",
    comparison_codes=[],
    service=IndustryMomentumService(as_of=date(2026, 8, 10)),
)
if captured:
    st.write(f"Export start: {captured[-1][0]['start']}")
    st.write(f"Export end: {captured[-1][0]['end']}")
    st.write(f"Export rows: {captured[-1][1]}")
""")
    next(
        item
        for item in app.checkbox
        if item.label == "Use a custom Industry Momentum history window"
    ).check().run(timeout=60)
    next(item for item in app.date_input if item.label == "History start month").set_value(
        date(2025, 1, 17)
    ).run(timeout=60)
    next(item for item in app.date_input if item.label == "History end month").set_value(
        date(2025, 2, 28)
    ).run(timeout=60)

    assert not app.exception
    assert any(
        "Custom history window: 2025-01 through 2025-02" in item.value for item in app.caption
    )
    signal_tables = [
        item.value for item in app.dataframe if "Observation month" in item.value.columns
    ]
    assert len(signal_tables) == 5
    assert all(
        table["Observation month"].tolist() == ["2025-01", "2025-02"] for table in signal_tables
    )
    rendered_text = " ".join(item.value for item in app.markdown)
    assert "Export start: 2025-01-01" in rendered_text
    assert "Export end: 2025-02-01" in rendered_text
    assert "Export rows: 10" in rendered_text
    assert len(app.download_button) == 3


def test_reversed_history_window_stops_before_service_call_with_accessible_error() -> None:
    app = _component("""
import streamlit as st
from src.application import IndustryMomentumService
from src.interfaces.streamlit.industry_momentum import render_industry_momentum
class CountingService(IndustryMomentumService):
    def __init__(self):
        super().__init__()
        self.calls = 0
    def for_industry_code(self, code, **kwargs):
        self.calls += 1
        return super().for_industry_code(code, **kwargs)
service = CountingService()
render_industry_momentum(
    selected_industry_code="325211",
    comparison_codes=[],
    service=service,
)
st.write(f"Service calls: {service.calls}")
""")
    next(
        item
        for item in app.checkbox
        if item.label == "Use a custom Industry Momentum history window"
    ).check().run(timeout=60)
    next(item for item in app.date_input if item.label == "History start month").set_value(
        date(2026, 3, 14)
    ).run(timeout=60)
    next(item for item in app.date_input if item.label == "History end month").set_value(
        date(2025, 3, 28)
    ).run(timeout=60)

    assert not app.exception
    assert any(
        item.value == "History start month must be on or before history end month."
        for item in app.error
    )
    assert any("Service calls: 0" in item.value for item in app.markdown)
    assert not app.download_button


def test_unmapped_manual_and_stale_states_are_explicit() -> None:
    app = _component("""
from datetime import date
from src.application import IndustryMomentumService
from src.interfaces.streamlit.industry_momentum import render_industry_momentum
render_industry_momentum(
    selected_industry_code="999999",
    comparison_codes=[],
    service=IndustryMomentumService(as_of=date(2027, 1, 1)),
)
""")
    assert any("No verified Industry Momentum mapping" in item.value for item in app.warning)
    assert any("Manual browse state" in item.value for item in app.info)
    assert any("Freshness: Stale" in item.value for item in app.warning)


def test_partial_family_and_complete_error_states_do_not_leak_paths() -> None:
    partial = _component("""
from pathlib import Path
from src.application import IndustryMomentumService
from src.interfaces.streamlit.industry_momentum import render_industry_momentum
missing = Path("does-not-exist")
render_industry_momentum(
    selected_industry_code="325211",
    comparison_codes=[],
    service=IndustryMomentumService(ces_snapshot_path=missing, ces_metadata_path=missing),
)
""")
    assert any("Partial state" in item.value for item in partial.warning)
    assert any("snapshot is unavailable" in item.value for item in partial.error)
    assert "does-not-exist" not in " ".join(item.value for item in partial.error)

    error = _component("""
from src.interfaces.streamlit.industry_momentum import render_industry_momentum
render_industry_momentum(
    selected_industry_code="325211",
    comparison_codes=[],
    service=None,
    load_error="validation",
)
""")
    assert any("temporarily unavailable" in item.value for item in error.error)
