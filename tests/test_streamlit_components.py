from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import streamlit as st

from src.interfaces.streamlit.components import (
    ONBOARDING_DISMISSED_SESSION_KEY,
    SOURCE_SESSION_KEY,
    build_data_story,
    render_data_provenance,
    render_download_panel,
    render_first_run_onboarding,
    render_insight_tabs,
    render_observability_snapshots,
    render_page_header,
    render_scenario_controls,
    render_scenario_results,
    render_sidebar,
    render_signal_bar,
    render_state_banner,
    render_trend_data_table,
)
from src.interfaces.streamlit.provenance import attach_uploaded_file_lineage


def test_build_data_story_with_materials_share() -> None:
    row = SimpleNamespace(
        industry_name="Widgets",
        industry_code="999",
        year=2021,
        idiot_index=2.5,
        materials_share_pct=65.0,
    )
    story = build_data_story(
        row=row.__dict__,
        filtered_size=1,
        total_size=10,
        filter_query="",
        data_mode="Sample (offline)",
    )
    assert "Widgets" in story
    assert "Materials dominate costs" in story


def test_build_data_story_with_no_materials_share() -> None:
    row = SimpleNamespace(
        industry_name="Gadgets",
        industry_code="888",
        year=2021,
        idiot_index=None,
        materials_share_pct=None,
    )
    story = build_data_story(
        row=row.__dict__,
        filtered_size=2,
        total_size=20,
        filter_query="search",
        data_mode="Upload CSV",
    )
    assert "lacks a recent output-to-cost ratio" in story
    assert "narrowed the field" in story
    assert "`search`" in story


def test_render_insight_tabs_returns_generated(monkeypatch) -> None:
    created = [SimpleNamespace(name="Tab1"), SimpleNamespace(name="Tab2")]
    monkeypatch.setattr(st, "tabs", lambda labels: created)
    tabs = render_insight_tabs(["Tab1", "Tab2"])
    assert tabs == created


def test_render_page_header_toggle(monkeypatch) -> None:
    # Monkeypatch Streamlit primitives used by the header
    class DummyCol:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    dummy_col_right = DummyCol()

    monkeypatch.setattr(st, "container", lambda: DummyCol())
    monkeypatch.setattr(st, "markdown", lambda *a, **k: None)
    monkeypatch.setattr(st, "columns", lambda *a, **k: (None, dummy_col_right))
    monkeypatch.setattr(st, "toggle", lambda label, value, help=None: True)
    focus = render_page_header("Title", "Subtitle", {"Environment": "dev"}, focus_mode=False)
    assert focus is True


def test_render_data_provenance_uses_typed_lineage_only(monkeypatch) -> None:
    captured: list[pd.DataFrame] = []
    captions: list[str] = []

    class ExpanderCtx:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    frame = pd.DataFrame(
        {
            "industry_code": ["311"],
            "industry_name": ["Food"],
            "year": [2023],
        }
    )
    frame.attrs.update(
        {
            "uploaded_filename": "private-client-data.csv",
            "api_key": "sentinel-secret",
        }
    )
    attach_uploaded_file_lineage(frame)

    monkeypatch.setattr(st, "expander", lambda *_args, **_kwargs: ExpanderCtx())
    monkeypatch.setattr(st, "caption", lambda value: captions.append(value))
    monkeypatch.setattr(st, "markdown", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        st,
        "dataframe",
        lambda frame, **_kwargs: captured.append(frame.copy()),
    )

    render_data_provenance(frame)

    assert len(captured) == 2
    rendered = " ".join(table.to_string() for table in captured)
    assert "user-upload" in rendered
    assert "uploaded_file" in rendered
    assert "private-client-data.csv" not in rendered
    assert "sentinel-secret" not in rendered
    assert any("typed lineage contract" in caption for caption in captions)


def test_render_download_panel_empty(monkeypatch) -> None:
    # When no artifacts, the function should return without exception
    render_download_panel([])


def test_render_sidebar_upload_requires_file(monkeypatch) -> None:
    class SidebarStub:
        def __init__(self) -> None:
            self.messages: list[tuple[str, str]] = []

        def header(self, _text: str) -> None:
            return None

        def write(self, _text: str) -> None:
            return None

        def selectbox(self, _label: str, _options: list[str], **_kwargs) -> str:
            return "Upload CSV"

        def number_input(self, *_args, **_kwargs) -> int:
            return 2024

        def error(self, text: str) -> None:
            self.messages.append(("error", text))

        def text_input(self, _label: str, value: str, type: str = "default") -> str:  # noqa: A002
            return value

        def file_uploader(
            self, _label: str, type: list[str] | None = None, **_kwargs
        ):  # noqa: A002
            return None

        def info(self, text: str) -> None:
            self.messages.append(("info", text))

        def markdown(self, _text: str, unsafe_allow_html: bool = False) -> None:
            return None

        def caption(self, _text: str) -> None:
            return None

    sidebar = SidebarStub()
    monkeypatch.setattr(st, "sidebar", sidebar)

    class SecurityStub:
        @staticmethod
        def validate_year(value: int):
            return SimpleNamespace(ok=True, value=value, message="")

        @staticmethod
        def validate_api_key(value: str, provider: str):
            return SimpleNamespace(ok=True, value=value, message=f"{provider} ok")

    state = render_sidebar(
        default_year=2024,
        year_bounds=(2000, 2025),
        bea_key="",
        census_key="",
        security_utils=SecurityStub,
    )

    assert state.data_mode == "Upload CSV"
    assert state.uploaded_file is None
    assert state.halt is True
    assert any(level == "info" for level, _ in sidebar.messages)


def test_render_sidebar_bea_invalid_key(monkeypatch) -> None:
    class SidebarStub:
        def header(self, _text: str) -> None:
            return None

        def write(self, _text: str) -> None:
            return None

        def selectbox(self, _label: str, _options: list[str], **_kwargs) -> str:
            return "BEA (Economy-wide)"

        def number_input(self, *_args, **_kwargs) -> int:
            return 2022

        def error(self, _text: str) -> None:
            return None

        def text_input(
            self, _label: str, value: str, type: str = "default", **_kwargs
        ) -> str:  # noqa: A002
            return "bad-key"

        def file_uploader(
            self, _label: str, type: list[str] | None = None, **_kwargs
        ):  # noqa: A002
            return None

        def info(self, _text: str) -> None:
            return None

        def markdown(self, _text: str, unsafe_allow_html: bool = False) -> None:
            return None

        def caption(self, _text: str) -> None:
            return None

    monkeypatch.setattr(st, "sidebar", SidebarStub())

    class SecurityStub:
        @staticmethod
        def validate_year(value: int):
            return SimpleNamespace(ok=True, value=value, message="")

        @staticmethod
        def validate_api_key(_value: str, provider: str):
            return SimpleNamespace(ok=False, value=None, message=f"{provider} key invalid")

    state = render_sidebar(
        default_year=2024,
        year_bounds=(2000, 2025),
        bea_key="",
        census_key="",
        security_utils=SecurityStub,
    )

    assert state.data_mode == "BEA (Economy-wide)"
    assert state.halt is True
    assert any("invalid" in message for message in state.errors)


def test_render_signal_bar_and_state_banner(monkeypatch) -> None:
    calls: list[str] = []

    class ColumnCtx:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(st, "columns", lambda count: [ColumnCtx() for _ in range(count)])
    monkeypatch.setattr(st, "markdown", lambda *args, **kwargs: calls.append("markdown"))

    df = pd.DataFrame(
        [
            {"industry_code": "311", "year": 2023, "idiot_index": 1.2},
            {"industry_code": "312", "year": 2023, "idiot_index": 2.4},
        ]
    )

    render_signal_bar(df)
    render_state_banner("Current mode: sample")

    assert calls


def test_first_run_onboarding_can_dismiss_and_reopen(monkeypatch) -> None:
    calls: list[str] = []

    class SidebarStub:
        def button(self, _label: str, **_kwargs) -> bool:
            return False

    monkeypatch.setattr(st, "sidebar", SidebarStub())
    monkeypatch.setattr(st, "subheader", lambda value: calls.append(value))
    monkeypatch.setattr(st, "info", lambda value: calls.append(value))
    monkeypatch.setattr(st, "markdown", lambda value: calls.append(value))
    monkeypatch.setattr(st, "caption", lambda value: calls.append(value))
    monkeypatch.setattr(st, "button", lambda _label, **_kwargs: False)
    monkeypatch.setattr(st, "rerun", lambda: None)
    st.session_state.pop(ONBOARDING_DISMISSED_SESSION_KEY, None)
    render_first_run_onboarding()
    assert "First-run guide" in calls
    assert st.session_state[ONBOARDING_DISMISSED_SESSION_KEY] is False

    monkeypatch.setattr(st, "button", lambda _label, **_kwargs: True)
    render_first_run_onboarding()
    assert st.session_state[ONBOARDING_DISMISSED_SESSION_KEY] is True


def test_sidebar_uses_stable_accessible_control_keys(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class SidebarStub:
        def header(self, *_args) -> None:
            pass

        def write(self, *_args) -> None:
            pass

        def selectbox(self, label, _options, **kwargs):
            captured["source_label"] = label
            captured["source_key"] = kwargs["key"]
            captured["source_help"] = kwargs["help"]
            return "Sample (offline)"

        def caption(self, *_args) -> None:
            pass

        def number_input(self, *_args, **kwargs):
            captured["year_help"] = kwargs["help"]
            return 2024

        def markdown(self, *_args, **_kwargs) -> None:
            pass

    monkeypatch.setattr(st, "sidebar", SidebarStub())
    state = render_sidebar(
        default_year=2024,
        year_bounds=(2000, 2025),
        bea_key="",
        census_key="",
        security_utils=SimpleNamespace(
            validate_year=lambda value: SimpleNamespace(ok=True, value=value, message="")
        ),
    )
    assert state.data_mode == "Sample (offline)"
    assert captured["source_label"] == "Data source"
    assert captured["source_key"] == SOURCE_SESSION_KEY
    assert captured["source_help"] and captured["year_help"]


def test_trend_table_uses_readable_columns(monkeypatch) -> None:
    captured: list[pd.DataFrame] = []

    class ExpanderCtx:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(st, "expander", lambda *_args, **_kwargs: ExpanderCtx())
    monkeypatch.setattr(st, "dataframe", lambda frame, **_kwargs: captured.append(frame))
    render_trend_data_table(
        pd.DataFrame(
            [{"year": 2021, "industry_name": "Widgets", "industry_code": "999", "idiot_index": 1.5}]
        )
    )
    assert list(captured[0].columns) == [
        "Year",
        "Industry",
        "Industry code",
        "Output-to-cost ratio",
    ]


def test_custom_style_uses_accessible_muted_text_token(monkeypatch) -> None:
    from src.interfaces.streamlit.components import load_custom_styles

    styles: list[str] = []
    monkeypatch.setattr(st, "markdown", lambda value, **_kwargs: styles.append(value))
    load_custom_styles()
    assert "--ink-300: #5f7488;" in styles[0]


def test_render_scenario_controls_and_results(monkeypatch) -> None:
    class ExpanderCtx:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class MetricCol:
        def __init__(self) -> None:
            self.metrics: list[tuple[str, str, str | None]] = []

        def metric(
            self, label: str, baseline_display: str, delta_display: str | None = None
        ) -> None:
            self.metrics.append((label, baseline_display, delta_display))

    class ButtonCol:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(st, "markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(st, "multiselect", lambda *args, **kwargs: ["311"])
    monkeypatch.setattr(st, "expander", lambda *args, **kwargs: ExpanderCtx())
    slider_values = iter([5.0, -2.0, 1.0, 3.0])
    monkeypatch.setattr(st, "slider", lambda *args, **kwargs: next(slider_values))

    def _columns(count: int):
        if count == 2:
            return [ButtonCol(), ButtonCol()]
        return [MetricCol() for _ in range(count)]

    monkeypatch.setattr(st, "columns", _columns)
    monkeypatch.setattr(st, "button", lambda *args, **kwargs: False)
    monkeypatch.setattr(st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(st, "dataframe", lambda *args, **kwargs: None)
    monkeypatch.setattr(st, "plotly_chart", lambda *args, **kwargs: None)

    controls = render_scenario_controls(
        available_codes=["311", "312"],
        code_formatter=lambda code: code,
    )
    assert controls.target_codes == ["311"]
    assert controls.gross_output_delta_pct == 5.0
    assert controls.materials_cost_delta_pct == -2.0

    baseline = SimpleNamespace(
        gross_output_total=1000.0,
        value_added_total=400.0,
        resilience_score_avg=60.0,
        idiot_index_avg=2.0,
        materials_dependency_ratio_avg=0.5,
        shock_sensitivity_index_avg=0.2,
        health_score_avg=55.0,
    )
    scenario = SimpleNamespace(
        overall=SimpleNamespace(risk_band="medium"),
    )
    health = {
        "baseline": SimpleNamespace(overall=SimpleNamespace(risk_band="low")),
        "scenario": scenario,
    }
    summary = {
        "baseline": baseline,
        "delta": {
            "gross_output_total": 10.0,
            "value_added_total": -5.0,
            "resilience_score_avg": 2.0,
            "idiot_index_avg": 0.1,
            "materials_dependency_ratio_avg": 0.05,
            "shock_sensitivity_index_avg": -0.02,
            "health_score_avg": 1.0,
        },
        "health": health,
    }
    comparison_table = pd.DataFrame([{"industry_code": "311"}])
    top_deltas = pd.DataFrame([{"industry_code": "311", "idiot_index_delta": 0.1}])

    render_scenario_results(
        summary=summary,
        comparison_table=comparison_table,
        top_deltas=top_deltas,
        figure={"chart": "ok"},
    )


def test_render_observability_snapshots_variants(monkeypatch) -> None:
    messages: list[str] = []

    class ColCtx:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def metric(self, *_args, **_kwargs) -> None:
            return None

        def caption(self, *_args, **_kwargs) -> None:
            return None

    monkeypatch.setattr(st, "subheader", lambda *args, **kwargs: None)
    monkeypatch.setattr(st, "info", lambda text: messages.append(f"info:{text}"))
    monkeypatch.setattr(st, "columns", lambda count: [ColCtx() for _ in range(count)])
    monkeypatch.setattr(st, "metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(st, "success", lambda text: messages.append(f"success:{text}"))
    monkeypatch.setattr(st, "error", lambda text: messages.append(f"error:{text}"))
    monkeypatch.setattr(st, "plotly_chart", lambda *args, **kwargs: None)
    monkeypatch.setattr(st, "dataframe", lambda *args, **kwargs: None)
    monkeypatch.setattr(st, "markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(st, "json", lambda *args, **kwargs: None)

    render_observability_snapshots([])
    assert any(item.startswith("info:") for item in messages)

    history = [
        {
            "snapshot_id": "snap-1",
            "captured_at": "2026-01-01T00:00:00Z",
            "event_total": 3,
            "events": {"error": 1, "success": 2},
            "metadata": {"label": "nightly"},
            "replication": {"status": "success", "backend": "s3", "path": "s3://bucket/a"},
            "last_error": {"message": "demo"},
        }
    ]

    render_observability_snapshots(history)
    assert any(item.startswith("success:") for item in messages)
