from __future__ import annotations

from types import SimpleNamespace

import streamlit as st

from src.interfaces.streamlit.components import (
    build_data_story,
    render_download_panel,
    render_insight_tabs,
    render_page_header,
)


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
    assert "lacks a recent Idiot Index" in story
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
    dummy_col_right.toggle = lambda label, value, help=None: True

    monkeypatch.setattr(st, "container", lambda: DummyCol())
    monkeypatch.setattr(st, "markdown", lambda *a, **k: None)
    monkeypatch.setattr(st, "columns", lambda *a, **k: (None, dummy_col_right))
    monkeypatch.setattr(st, "toggle", lambda label, value, help=None: True)
    focus = render_page_header("Title", "Subtitle", {"Environment": "dev"}, focus_mode=False)
    assert focus is True


def test_render_download_panel_empty(monkeypatch) -> None:
    # When no artifacts, the function should return without exception
    render_download_panel([])
