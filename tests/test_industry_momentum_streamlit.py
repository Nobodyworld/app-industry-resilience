"""Streamlit AppTest coverage for multi-source Industry Momentum states."""

from __future__ import annotations

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
    assert len(app.get("plotly_chart")) == 5
    assert len(app.dataframe) >= 7
    assert len(app.download_button) == 3
    assert any("Accessible monthly data table" in item.value for item in app.markdown)


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
