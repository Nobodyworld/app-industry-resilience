from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_APP_PATH = str(_REPOSITORY_ROOT / "app.py")


@pytest.fixture(autouse=True)
def _run_from_repository_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(_REPOSITORY_ROOT)


def _load_app() -> AppTest:
    app = AppTest.from_file(_APP_PATH)
    app.run(timeout=30)
    assert not app.exception
    return app


def test_startup_renders_primary_navigation() -> None:
    app = _load_app()

    tabs = [tab.label for tab in app.tabs]
    assert "Overview" in tabs
    assert "Explore" in tabs
    assert "Compare" in tabs
    assert "Scenario Lab" in tabs
    assert "Industry Momentum" in tabs
    assert "Observability" not in tabs

    text_blob = " ".join(markdown.value for markdown in app.markdown)
    assert "Start here" in text_blob
    assert "Output-to-cost ratio" in text_blob


def test_first_run_defaults_to_sample_and_hides_api_key_inputs() -> None:
    app = _load_app()

    sidebar_labels = [text.value for text in app.sidebar.markdown] + [
        text.value for text in app.sidebar.text
    ]
    sidebar_text = " ".join(sidebar_labels)

    assert "bundled offline sample data" in sidebar_text.lower()
    assert "BEA API Key" not in sidebar_text
    assert "Census API Key" not in sidebar_text
    assert app.sidebar.selectbox[0].label == "Data source"
    assert app.sidebar.selectbox[0].value == "Sample (offline)"


def test_first_run_guide_can_be_dismissed_and_reopened() -> None:
    app = _load_app()
    assert any(header.value == "First-run guide" for header in app.subheader)
    dismiss = next(button for button in app.button if button.label == "Dismiss first-run guide")
    dismiss.click().run(timeout=30)
    assert not any(header.value == "First-run guide" for header in app.subheader)
    reopen = next(button for button in app.sidebar.button if button.label == "Show first-run guide")
    reopen.click().run(timeout=30)
    assert any(header.value == "First-run guide" for header in app.subheader)


def test_explicit_source_query_and_session_selection_are_preserved() -> None:
    app = AppTest.from_file(_APP_PATH)
    app.query_params["mode"] = "official-snapshot-(aies-2023)"
    app.run(timeout=30)
    assert not app.exception
    assert app.sidebar.selectbox[0].value == "Official snapshot (AIES 2023)"

    app.sidebar.selectbox[0].set_value("Sample (offline)").run(timeout=30)
    assert app.sidebar.selectbox[0].value == "Sample (offline)"


def test_unresolved_source_query_defaults_to_sample() -> None:
    app = AppTest.from_file(_APP_PATH)
    app.query_params["mode"] = "retired-source"
    app.run(timeout=30)
    assert not app.exception
    assert app.sidebar.selectbox[0].label == "Data source"
    assert app.sidebar.selectbox[0].value == "Sample (offline)"


def test_scenario_idle_and_validation_message() -> None:
    app = _load_app()

    initial_infos = [info.value for info in app.info]
    assert any("Idle scenario state" in message for message in initial_infos)

    run_buttons = [button for button in app.button if button.label == "Run scenario"]
    assert run_buttons
    run_buttons[0].click().run(timeout=30)

    warnings = [warning.value for warning in app.warning]
    assert any("Set at least one non-zero adjustment" in message for message in warnings)


def test_scenario_run_and_reset_cycle() -> None:
    app = _load_app()

    gross_slider = next(
        slider for slider in app.slider if slider.label == "Gross output change (%)"
    )
    gross_slider.set_value(10.0).run(timeout=30)

    run_button = next(button for button in app.button if button.label == "Run scenario")
    run_button.click().run(timeout=30)

    captions = [caption.value for caption in app.caption]
    assert any("Baseline values are current-state estimates" in value for value in captions)

    reset_button = next(button for button in app.button if button.label == "Reset scenario")
    reset_button.click().run(timeout=30)

    infos = [info.value for info in app.info]
    assert any("Idle scenario state" in message for message in infos)


def test_momentum_manual_browse_and_history_window_do_not_mutate_annual_state() -> None:
    app = _load_app()
    annual_before = app.session_state["industry_selection_code"]
    annual_select = next(item for item in app.selectbox if item.label == "Select an industry")
    annual_select_value = annual_select.value

    momentum_browse = next(
        item for item in app.selectbox if item.label == "Browse verified Industry Momentum mappings"
    )
    momentum_browse.set_value("325211").run(timeout=60)
    assert app.session_state["industry_selection_code"] == annual_before
    assert (
        next(item for item in app.selectbox if item.label == "Select an industry").value
        == annual_select_value
    )

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
    assert app.session_state["industry_selection_code"] == annual_before
    assert (
        next(item for item in app.selectbox if item.label == "Select an industry").value
        == annual_select_value
    )


@pytest.mark.parametrize("query", ["[", "(", ".", "*"])
def test_literal_search_punctuation_has_no_regex_matches(query: str) -> None:
    app = _load_app()
    app.text_input(key="search_query").set_value(query).run(timeout=30)
    assert not app.exception
    assert any("No industries match" in warning.value for warning in app.warning)
    assert not any("Avg composite indicator" in text.value for text in app.markdown)
    assert app.query_params["search"] == [query]


def test_sample_year_deep_link_matches_header_and_provenance() -> None:
    app = AppTest.from_file(_APP_PATH)
    app.query_params.update({"mode": "sample-(offline)", "year": "2025"})
    app.run(timeout=30)
    assert not app.exception
    year = app.number_input(key="reference_year")
    assert year.value == 2021
    assert year.disabled
    assert app.query_params["year"] == ["2021"]
    header = next(text.value for text in app.markdown if "Visible" in text.value)
    assert "2021" in header and "2025" not in header
    provenance = next(table.value for table in app.dataframe if "Field" in table.value.columns)
    assert provenance.set_index("Field").loc["Observation period", "Value"] == "2021"


def test_normal_source_cycle_clears_scenario_without_clearing_url() -> None:
    app = _load_app()
    app.slider(key="scenario_gross_delta").set_value(10.0).run(timeout=30)
    next(button for button in app.button if button.label == "Run scenario").click().run(timeout=30)
    assert app.session_state["scenario_committed"]
    for source, slug in [
        ("Official snapshot (AIES 2023)", "official-snapshot-(aies-2023)"),
        ("Sample (offline)", "sample-(offline)"),
    ]:
        app.sidebar.selectbox[0].set_value(source).run(timeout=30)
        assert not app.exception
        assert app.sidebar.selectbox[0].value == source
        assert app.query_params["mode"] == [slug]
        assert not app.session_state.filtered_state.get("scenario_committed")
        assert "scenario_gross" not in app.query_params


def test_entering_upload_clears_committed_scenario_even_before_file_loaded() -> None:
    app = _load_app()
    app.slider(key="scenario_gross_delta").set_value(10.0).run(timeout=30)
    next(button for button in app.button if button.label == "Run scenario").click().run(timeout=30)
    app.sidebar.selectbox[0].set_value("Upload CSV").run(timeout=30)
    assert not app.exception
    assert not app.session_state.filtered_state.get("scenario_committed")
    app.sidebar.selectbox[0].set_value("Sample (offline)").run(timeout=30)
    assert not app.exception
    assert not app.session_state.filtered_state.get("scenario_committed")


def test_scenario_deep_link_initializes_inputs_once() -> None:
    app = AppTest.from_file(_APP_PATH)
    app.query_params.update({"scenario_codes": "311", "scenario_gross": "-10"})
    app.run(timeout=30)
    assert not app.exception
    assert app.slider(key="scenario_gross_delta").value == -10.0
    assert app.multiselect(key="scenario_target_codes").value == ["311"]
    app.slider(key="scenario_gross_delta").set_value(-5.0).run(timeout=30)
    assert app.slider(key="scenario_gross_delta").value == -5.0


@pytest.mark.parametrize("query, count", [("Food", 1), ("no-such-industry", 0), ("", 8)])
def test_current_view_population_is_shared_by_cards_tables_and_exports(
    monkeypatch, query, count
) -> None:
    import io

    import pandas as pd

    from src.interfaces.streamlit import components, helpers

    captured = {}
    original_signal = components.render_signal_bar
    original_exports = helpers.prepare_download_artifacts

    def signal(frame, *, health_summary=None):
        captured["frame"] = frame.copy()
        captured["health"] = health_summary
        return original_signal(frame, health_summary=health_summary)

    def exports(df_full, df_filtered, *, base_name):
        artifacts = original_exports(df_full, df_filtered, base_name=base_name)
        captured["exports"] = artifacts
        return artifacts

    monkeypatch.setattr(components, "render_signal_bar", signal)
    monkeypatch.setattr(helpers, "prepare_download_artifacts", exports)
    app = _load_app()
    app.text_input(key="search_query").set_value(query).run(timeout=30)
    assert not app.exception
    assert len(captured["frame"]) == count
    assert captured["health"].overall.industries == count
    if count:
        assert captured["health"].overall.average_health_score == pytest.approx(
            captured["frame"].health_score.mean()
        )
    csv = next(
        artifact for artifact in captured["exports"] if artifact.file_name.endswith("filtered.csv")
    )
    exported = pd.read_csv(io.BytesIO(csv.data), dtype={"industry_code": str})
    assert exported.industry_code.tolist() == captured["frame"].industry_code.tolist()
    tables = [
        table.value
        for table in app.dataframe
        if "Industry code" in table.value.columns and "Year" in table.value.columns
    ]
    assert any(len(table) == count for table in tables)


@pytest.mark.parametrize(
    "runtime_url, label",
    [(None, "Share/query parameters"), ("https://example.com/app/", "Shareable link")],
)
def test_share_control_label_matches_runtime_value(monkeypatch, runtime_url, label) -> None:
    from types import SimpleNamespace

    import streamlit as st

    monkeypatch.setattr(st, "context", SimpleNamespace(url=runtime_url))
    app = _load_app()
    control = next(item for item in app.text_input if item.label == label)
    assert control.value.startswith("https://example.com/app/?" if runtime_url else "?")


def test_changed_upload_bytes_clear_scenario_with_same_source_and_filename(monkeypatch) -> None:
    import io
    from dataclasses import replace

    from src.interfaces.streamlit import components

    class Upload(io.BytesIO):
        name = "industries.csv"

        @property
        def size(self):
            return len(self.getvalue())

    uploaded = {"bytes": (_REPOSITORY_ROOT / "data/sample_industries.csv").read_bytes()}
    original = components.render_sidebar

    def sidebar(**kwargs):
        state = original(**kwargs)
        if state.data_mode == "Upload CSV":
            return replace(state, uploaded_file=Upload(uploaded["bytes"]), halt=False)
        return state

    monkeypatch.setattr(components, "render_sidebar", sidebar)
    app = _load_app()
    app.sidebar.selectbox[0].set_value("Upload CSV").run(timeout=30)
    assert not app.exception
    app.slider(key="scenario_gross_delta").set_value(10.0).run(timeout=30)
    next(button for button in app.button if button.label == "Run scenario").click().run(timeout=30)
    assert app.session_state["scenario_committed"]
    app.text_input(key="search_query").set_value("Food").run(timeout=30)
    assert app.session_state["scenario_committed"]
    uploaded["bytes"] = uploaded["bytes"].replace(b"904100", b"904101")
    app.run(timeout=30)
    assert not app.exception
    assert not app.session_state.filtered_state.get("scenario_committed")
    assert any("Baseline changed" in item.value for item in app.info)


def test_requested_year_change_clears_scenario_and_preserves_initial_deep_link(monkeypatch) -> None:
    from dataclasses import replace

    import pandas as pd

    import src.application as application
    from src.interfaces.streamlit import components

    original_sidebar = components.render_sidebar
    original_evaluate = application.evaluate_idiot_index

    def sidebar(**kwargs):
        state = original_sidebar(**kwargs)
        return replace(state, halt=False)

    def evaluate(**kwargs):
        # Exercise a year-selectable adapter without network or API credentials.
        frame = pd.read_csv(_REPOSITORY_ROOT / "data/sample_industries.csv")
        frame["year"] = kwargs["year"]
        kwargs.update(source=application.DataSource.SAMPLE, dataframe=frame)
        return original_evaluate(**kwargs)

    monkeypatch.setattr(components, "render_sidebar", sidebar)
    monkeypatch.setattr(application, "evaluate_idiot_index", evaluate)
    app = AppTest.from_file(_APP_PATH)
    app.query_params.update({"mode": "census-asm-(legacy)", "year": "2020"})
    app.run(timeout=30)
    assert not app.exception
    assert app.number_input(key="reference_year").value == 2020
    app.slider(key="scenario_gross_delta").set_value(10.0).run(timeout=30)
    assert app.number_input(key="reference_year").value == 2020
    next(button for button in app.button if button.label == "Run scenario").click().run(timeout=30)
    assert app.session_state["scenario_committed"]
    app.number_input(key="reference_year").set_value(2021).run(timeout=30)
    assert not app.exception
    assert not app.session_state.filtered_state.get("scenario_committed")
    assert app.query_params["year"] == ["2021"]
