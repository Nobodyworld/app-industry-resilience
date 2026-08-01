"""Streamlit AppTest coverage for Industry Pulse user states."""

from __future__ import annotations

from streamlit.testing.v1 import AppTest


def _component_app(body: str) -> AppTest:
    app = AppTest.from_string(body)
    app.run(timeout=30)
    assert not app.exception
    return app


def test_default_dashboard_has_fifth_pulse_tab_and_manual_browse_state() -> None:
    app = AppTest.from_file("app.py")
    app.run(timeout=30)
    assert not app.exception

    assert [tab.label for tab in app.tabs] == [
        "Overview",
        "Explore",
        "Compare",
        "Scenario Lab",
        "Industry Pulse",
    ]
    assert any(select.label == "Browse verified signals" for select in app.selectbox)
    assert any("No verified exact six-digit" in warning.value for warning in app.warning)
    assert any("Manual browse state" in info.value for info in app.info)
    assert any(metric.label == "Latest PPI value" for metric in app.metric)
    assert len(app.get("plotly_chart")) >= 1
    assert any(
        "Producer Price Index observations show price movement" in warning.value
        for warning in app.warning
    )


def test_exact_mapping_state_is_synchronized_and_has_chart_table_and_exports() -> None:
    app = _component_app("""
from src.application import IndustryPulseService
from src.interfaces.streamlit.industry_pulse import render_industry_pulse
render_industry_pulse(
    selected_industry_code="311111",
    comparison_codes=["311111", "999999"],
    service=IndustryPulseService(),
)
""")
    assert any("Exact verified mapping" in item.value for item in app.success)
    assert not any("Manual browse state" in item.value for item in app.info)
    assert any("Comparison mapping availability" in item.value for item in app.markdown)
    assert len(app.get("plotly_chart")) == 1
    assert len(app.dataframe) >= 2
    assert len(app.download_button) == 3


def test_stale_empty_and_error_states_are_explicit() -> None:
    stale = _component_app("""
from datetime import date
from src.application import IndustryPulseService
from src.interfaces.streamlit.industry_pulse import render_industry_pulse
render_industry_pulse(
    selected_industry_code="311111",
    comparison_codes=[],
    service=IndustryPulseService(as_of=date(2027, 1, 1)),
)
""")
    assert any("Freshness: Stale" in item.value for item in stale.warning)

    empty = _component_app("""
from datetime import date
from src.application import IndustryPulseService
from src.interfaces.streamlit.industry_pulse import render_industry_pulse
class EmptyService:
    def __init__(self):
        self._service = IndustryPulseService()
        self.registry = self._service.registry
    def for_industry_code(self, code, **kwargs):
        return self._service.for_industry_code(
            code, start=date(2030, 1, 1), end=date(2030, 12, 1)
        )
render_industry_pulse(
    selected_industry_code="311111",
    comparison_codes=[],
    service=EmptyService(),
)
""")
    assert any("requested snapshot range" in item.value for item in empty.info)
    assert not empty.get("plotly_chart")

    error = _component_app("""
from src.interfaces.streamlit.industry_pulse import render_industry_pulse
render_industry_pulse(
    selected_industry_code="311111",
    comparison_codes=[],
    service=None,
    load_error="IndustryPulseSnapshotError",
)
""")
    assert any("temporarily unavailable" in item.value for item in error.error)
