from __future__ import annotations

from streamlit.testing.v1 import AppTest


def _load_app() -> AppTest:
    app = AppTest.from_file("app.py")
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
    app = AppTest.from_file("app.py")
    app.query_params["mode"] = "official-snapshot-(aies-2023)"
    app.run(timeout=30)
    assert not app.exception
    assert app.sidebar.selectbox[0].value == "Official snapshot (AIES 2023)"

    app.query_params.clear()
    app.sidebar.selectbox[0].set_value("Sample (offline)").run(timeout=30)
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
