"""Composable UI components and adaptive helpers for the Idiot Index Streamlit app."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import TypeAlias, cast

import pandas as pd

import streamlit as st
from src.core import HealthSummary
from streamlit.runtime.uploaded_file_manager import UploadedFile

from .helpers import (
    DownloadArtifact,
    extract_health_badge,
    snapshot_history_table,
    snapshot_timeline_frame,
)


@dataclass
class SidebarState:
    """Captures sidebar selections and validation outcomes."""

    data_mode: str
    year_input: int
    year_clean: int | None
    bea_key: str
    census_key: str
    uploaded_file: UploadedFile | None
    errors: list[str]
    halt: bool


@dataclass
class ScenarioControlState:
    """Reflect user selections from the Scenario Lab panel."""

    target_codes: list[str]
    gross_output_delta_pct: float
    materials_cost_delta_pct: float
    value_added_delta_pct: float
    intermediate_inputs_delta_pct: float


def load_custom_styles() -> None:
    """Inject global CSS to create a calm, timeless visual system."""

    st.markdown(
        """
        <style>
            :root {
                --ink-900: #0b1f33;
                --ink-600: #33536f;
                --ink-300: #8ca1b4;
                --ink-200: #c8d2dc;
                --glow-500: #3cd0c9;
                --glow-300: #8ee4df;
                --accent-soft: rgba(60, 208, 201, 0.12);
                --surface: #f7f9fb;
                --surface-strong: #ecf1f5;
            }

            .stApp {
                background: var(--surface);
            }

            .page-hero {
                padding: 2.5rem 2rem 1.5rem 2rem;
                border-radius: 24px;
                background: linear-gradient(135deg, rgba(11, 31, 51, 0.92), rgba(51, 83, 111, 0.85));
                color: white;
                margin-bottom: 1.5rem;
                box-shadow: 0 24px 48px rgba(11, 31, 51, 0.18);
            }

            .page-hero h1 {
                font-size: 2.6rem;
                margin-bottom: 0.35rem;
            }

            .page-hero p {
                font-size: 1.12rem;
                opacity: 0.85;
                max-width: 720px;
            }

            .page-hero__meta {
                display: flex;
                flex-wrap: wrap;
                gap: 0.6rem;
                margin-top: 1.25rem;
            }

            .meta-chip {
                padding: 0.35rem 0.8rem;
                border-radius: 999px;
                background: rgba(255, 255, 255, 0.15);
                font-size: 0.85rem;
                letter-spacing: 0.01em;
            }

            .signal-card {
                background: white;
                padding: 1rem 1.2rem;
                border-radius: 18px;
                border: 1px solid var(--surface-strong);
                box-shadow: 0 12px 32px rgba(11, 31, 51, 0.06);
                height: 100%;
            }

            .signal-card__label {
                font-size: 0.75rem;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                color: var(--ink-600);
                margin-bottom: 0.35rem;
            }

            .signal-card__value {
                font-size: 1.8rem;
                font-weight: 600;
                color: var(--ink-900);
            }

            .signal-card__hint {
                font-size: 0.85rem;
                color: var(--ink-300);
            }

            .state-banner {
                border-radius: 18px;
                padding: 1rem 1.2rem;
                background: var(--accent-soft);
                border: 1px solid rgba(60, 208, 201, 0.4);
                color: var(--ink-900);
                margin-bottom: 1.25rem;
            }

            .deep-dive {
                padding: 1.5rem;
                border-radius: 24px;
                background: white;
                border: 1px solid var(--surface-strong);
                box-shadow: 0 18px 42px rgba(11, 31, 51, 0.08);
            }

            .deep-dive__heading {
                font-size: 1.4rem;
                font-weight: 600;
                color: var(--ink-900);
            }

            .deep-dive__story {
                margin-top: 0.75rem;
                font-size: 1rem;
                color: var(--ink-600);
                line-height: 1.6;
            }

            .download-panel {
                margin-top: 1.5rem;
                padding: 1.2rem 1.5rem;
                border-radius: 18px;
                background: white;
                border: 1px dashed var(--surface-strong);
            }

            .sidebar-guidance {
                font-size: 0.85rem;
                color: var(--ink-300);
                margin-top: 0.75rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_page_header(
    title: str,
    subtitle: str,
    meta: dict[str, str],
    focus_mode: bool,
) -> bool:
    """Render the hero header and return the current focus mode toggle state."""

    with st.container():
        st.markdown(
            f"""
            <div class="page-hero">
                <div class="page-hero__primary">
                    <h1>{title}</h1>
                    <p>{subtitle}</p>
                </div>
                <div class="page-hero__meta">
                    {''.join(f'<span class="meta-chip">{label}: {value}</span>' for label, value in meta.items())}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    control_col_left, control_col_right = st.columns([5, 1])
    with control_col_right:
        return st.toggle(
            "Focus mode",
            value=focus_mode,
            help="Focus mode minimizes distractions and spotlights the deep dive panel.",
        )


def render_sidebar(
    *,
    default_year: int,
    year_bounds: tuple[int, int],
    bea_key: str,
    census_key: str,
    security_utils,
) -> SidebarState:
    """Render sidebar inputs and validations, returning state for the caller."""

    st.sidebar.header("Data Studio")
    st.sidebar.write("Choose how the Idiot Index should listen to your data today.")

    options = ["Sample (offline)", "Upload CSV", "Census ASM (Manufacturing)", "BEA (Economy-wide)"]
    data_mode = st.sidebar.selectbox("Source", options)

    min_year, max_year = year_bounds
    year_input = int(
        st.sidebar.number_input(
            "Reference year",
            min_value=min_year,
            max_value=max_year,
            value=default_year,
            step=1,
        )
    )

    errors: list[str] = []
    year_result = security_utils.validate_year(year_input)
    if not year_result.ok or year_result.value is None:
        st.sidebar.error(year_result.message)
        errors.append(year_result.message)
        year_clean = None
    else:
        year_clean = year_result.value

    bea_val = st.sidebar.text_input("BEA API Key", value=bea_key, type="password")
    census_val = st.sidebar.text_input("Census API Key", value=census_key, type="password")

    uploaded_file = None
    if data_mode == "Upload CSV":
        uploaded_file = st.sidebar.file_uploader("Upload CSV", type=["csv"])
        if uploaded_file is None:
            st.sidebar.info("Drop a CSV to activate the canvas.")
    elif data_mode == "Census ASM (Manufacturing)":
        key_result = security_utils.validate_api_key(census_val, "Census")
        if not key_result.ok:
            st.sidebar.error(key_result.message)
            errors.append(key_result.message)
    elif data_mode == "BEA (Economy-wide)":
        key_result = security_utils.validate_api_key(bea_val, "BEA")
        if not key_result.ok:
            st.sidebar.error(key_result.message)
            errors.append(key_result.message)

    guidance = {
        "Sample (offline)": "Explore the experience instantly with curated demo data.",
        "Upload CSV": "Bring your own dataset. Required columns: industry_code, industry_name, year.",
        "Census ASM (Manufacturing)": "Connect to the U.S. Census Annual Survey of Manufactures.",
        "BEA (Economy-wide)": "Access the Bureau of Economic Analysis industry accounts.",
    }
    st.sidebar.markdown(
        f"<div class='sidebar-guidance'>{guidance[data_mode]}</div>",
        unsafe_allow_html=True,
    )

    halt = bool(errors)
    if data_mode == "Upload CSV" and uploaded_file is None:
        halt = True

    return SidebarState(
        data_mode=data_mode,
        year_input=year_input,
        year_clean=year_clean,
        bea_key=bea_val,
        census_key=census_val,
        uploaded_file=uploaded_file,
        errors=errors,
        halt=halt,
    )


def render_signal_bar(df: pd.DataFrame, *, health_summary: HealthSummary | None = None) -> None:
    """Show high-level dataset signals."""

    total_rows = len(df)
    distinct_industries = df["industry_code"].nunique()
    dominant_year = (
        int(df["year"].mode().iloc[0])
        if "year" in df.columns and not df["year"].isna().all()
        else "—"
    )
    avg_idiot_index = df["idiot_index"].mean() if "idiot_index" in df.columns else None

    cards: list[dict[str, str]] = [
        {
            "label": "Rows",
            "value": f"{total_rows:,}",
            "hint": "records currently in view",
        },
        {
            "label": "Distinct industries",
            "value": f"{distinct_industries:,}",
            "hint": "unique NAICS-style codes",
        },
        {
            "label": "Modal year",
            "value": str(dominant_year),
            "hint": "most common reporting year",
        },
        {
            "label": "Mean Idiot Index",
            "value": f"{avg_idiot_index:.2f}" if avg_idiot_index is not None else "—",
            "hint": "gross output ÷ materials cost",
        },
    ]

    badge = extract_health_badge(health_summary)
    if badge["score"] is not None:
        cards.append(
            {
                "label": "Avg health score",
                "value": str(badge["score"]),
                "hint": f"risk band: {badge['band']}" if badge["band"] else "composite resilience",
            }
        )

    cols = st.columns(len(cards))
    for col, card in zip(cols, cards, strict=False):
        with col:
            st.markdown(
                f"""
                <div class="signal-card">
                    <div class="signal-card__label">{card['label']}</div>
                    <div class="signal-card__value">{card['value']}</div>
                    <div class="signal-card__hint">{card['hint']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_state_banner(message: str) -> None:
    """Display an adaptive banner summarizing the current context."""

    st.markdown(
        f"<div class='state-banner'>{message}</div>",
        unsafe_allow_html=True,
    )


def render_insight_tabs(labels: Iterable[str]) -> list[st.delta_generator.DeltaGenerator]:
    """Create the primary insight tabs and return them."""

    return list(st.tabs(list(labels)))


def render_deep_dive(
    *,
    row: pd.Series,
    story: str,
    focus_mode: bool,
) -> None:
    """Present a deep dive narrative for the selected industry."""

    container = st.container()
    with container:
        st.markdown("<div class='deep-dive'>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='deep-dive__heading'>{row['industry_name']}</div>",
            unsafe_allow_html=True,
        )
        st.caption(
            f"Code: {row['industry_code']} · Year: {int(row['year']) if pd.notna(row['year']) else 'N/A'}"
        )

        metric_cols = container.columns(4 if not focus_mode else 2)
        key_metrics = [
            ("Idiot Index", row.get("idiot_index")),
            ("Value-Added %", row.get("value_added_pct")),
            ("Materials Share %", row.get("materials_share_pct")),
            ("Value Added", row.get("value_added")),
        ]

        for idx, (label, value) in enumerate(key_metrics):
            if idx >= len(metric_cols):
                break
            with metric_cols[idx]:
                if value is None or pd.isna(value):
                    st.metric(label, "N/A")
                elif "%" in label:
                    st.metric(label, f"{value:.1f}%")
                elif label == "Idiot Index":
                    st.metric(label, f"{value:.2f}")
                else:
                    st.metric(label, f"{value:,.0f}")

        raw_cols = container.columns(4)
        for col, (label, key) in zip(
            raw_cols,
            [
                ("Gross Output", "gross_output"),
                ("Materials Cost", "materials_cost"),
                ("Intermediate Inputs", "intermediate_inputs"),
                ("Source", "source"),
            ],
            strict=False,
        ):
            with col:
                value = row.get(key)
                if key == "source":
                    st.metric(label, value if pd.notna(value) else "Unknown")
                else:
                    st.metric(label, f"{value:,.0f}" if pd.notna(value) else "—")

        st.markdown("""<div class='deep-dive__story'>""", unsafe_allow_html=True)
        st.markdown(story)
        st.markdown("""</div>""", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)


def render_scenario_controls(
    *,
    available_codes: Sequence[str],
    code_formatter: Callable[[str], str],
    default_selection: Sequence[str] | None = None,
    default_gross_delta: float = 0.0,
    default_materials_delta: float = 0.0,
    default_value_delta: float = 0.0,
    default_intermediate_delta: float = 0.0,
) -> ScenarioControlState:
    """Render Scenario Lab controls and return selected deltas."""

    st.markdown(
        "The Scenario Lab applies percentage shocks to industries so you can probe resilience and dependency instantly."
    )
    selection = st.multiselect(
        "Target industries",
        options=list(available_codes),
        default=list(default_selection or []),
        format_func=code_formatter,
        help="Leave empty to stress test the entire dataset.",
    )

    with st.expander("Adjust cost structure", expanded=True):
        gross_delta = st.slider(
            "Gross output change (%)",
            min_value=-50.0,
            max_value=50.0,
            value=default_gross_delta,
            step=1.0,
        )
        materials_delta = st.slider(
            "Materials cost change (%)",
            min_value=-50.0,
            max_value=50.0,
            value=default_materials_delta,
            step=1.0,
        )
        value_delta = st.slider(
            "Value added change (%)",
            min_value=-25.0,
            max_value=25.0,
            value=default_value_delta,
            step=1.0,
        )
        intermediate_delta = st.slider(
            "Intermediate inputs change (%)",
            min_value=-50.0,
            max_value=50.0,
            value=default_intermediate_delta,
            step=1.0,
            help="Applies when intermediate inputs are available separately from materials cost.",
        )

    return ScenarioControlState(
        target_codes=list(selection),
        gross_output_delta_pct=gross_delta,
        materials_cost_delta_pct=materials_delta,
        value_added_delta_pct=value_delta,
        intermediate_inputs_delta_pct=intermediate_delta,
    )


def render_scenario_results(
    *,
    summary: Mapping[str, object],
    comparison_table: pd.DataFrame,
    top_deltas: pd.DataFrame,
    figure: object | None = None,
) -> None:
    """Display scenario summaries, tables, and optional chart."""

    baseline_summary = summary["baseline"]
    delta_summary = cast(Mapping[str, float | None], summary["delta"])

    metric_cols_primary = st.columns(3)

    def _metric(
        column, label: str, baseline_value: float | None, delta_value: float | None
    ) -> None:
        baseline_display = f"{baseline_value:,.2f}" if baseline_value is not None else "—"
        delta_display = f"{delta_value:+,.2f}" if delta_value is not None else None
        column.metric(label, baseline_display, delta_display)

    _metric(
        metric_cols_primary[0],
        "Gross output total",
        getattr(baseline_summary, "gross_output_total", None),
        delta_summary.get("gross_output_total"),
    )
    _metric(
        metric_cols_primary[1],
        "Value added total",
        getattr(baseline_summary, "value_added_total", None),
        delta_summary.get("value_added_total"),
    )
    _metric(
        metric_cols_primary[2],
        "Average resilience score",
        getattr(baseline_summary, "resilience_score_avg", None),
        delta_summary.get("resilience_score_avg"),
    )

    metric_cols_secondary = st.columns(4)
    _metric(
        metric_cols_secondary[0],
        "Average Idiot Index",
        getattr(baseline_summary, "idiot_index_avg", None),
        delta_summary.get("idiot_index_avg"),
    )
    _metric(
        metric_cols_secondary[1],
        "Materials dependency ratio",
        getattr(baseline_summary, "materials_dependency_ratio_avg", None),
        delta_summary.get("materials_dependency_ratio_avg"),
    )
    _metric(
        metric_cols_secondary[2],
        "Shock sensitivity index",
        getattr(baseline_summary, "shock_sensitivity_index_avg", None),
        delta_summary.get("shock_sensitivity_index_avg"),
    )
    _metric(
        metric_cols_secondary[3],
        "Average health score",
        getattr(baseline_summary, "health_score_avg", None),
        delta_summary.get("health_score_avg"),
    )

    health_meta = cast(dict[str, HealthSummary | None], summary.get("health", {}))
    baseline_health = health_meta.get("baseline")
    scenario_health = health_meta.get("scenario")
    if baseline_health and scenario_health:
        st.caption(
            "Risk band shift: "
            f"{baseline_health.overall.risk_band or '—'} → {scenario_health.overall.risk_band or '—'}"
        )

    st.markdown("### Scenario comparison table")
    st.dataframe(comparison_table, use_container_width=True)

    if figure is not None:
        st.plotly_chart(figure, use_container_width=True)

    st.markdown("### Leading changes")
    st.dataframe(top_deltas, use_container_width=True)


def render_download_panel(artifacts: Sequence[DownloadArtifact]) -> None:
    """Display a styled download area with multiple export options."""

    if not artifacts:
        return

    with st.container():
        st.markdown("<div class='download-panel'>", unsafe_allow_html=True)
        st.write("Carry the Idiot Index narrative with you.")
        for artifact in artifacts:
            st.download_button(
                artifact.label,
                data=artifact.data,
                file_name=artifact.file_name,
                mime=artifact.mime,
                use_container_width=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)


def render_observability_snapshots(
    history: Sequence[Mapping[str, object]], *, empty_message: str | None = None
) -> None:
    """Render snapshot history and trend visualisations."""

    st.subheader("Observability snapshots")
    if not history:
        st.info(
            empty_message
            or "No snapshots recorded yet. Run `make observability-snapshot` after key deployments to capture state."
        )
        return

    latest: Mapping[str, object] = history[0]
    events_raw = latest.get("events", {})
    latest_events: Mapping[str, object]
    if isinstance(events_raw, Mapping):
        latest_events = events_raw
    else:
        latest_events = {}
    cols = st.columns(3)
    captured_at = latest.get("captured_at")
    captured_label = (
        captured_at.strftime("%Y-%m-%d %H:%M:%SZ")
        if hasattr(captured_at, "strftime")
        else str(captured_at)
    )
    with cols[0]:
        st.metric("Most recent", captured_label)
        metadata_raw = latest.get("metadata", {})
        label = metadata_raw.get("label") if isinstance(metadata_raw, Mapping) else None
        if label:
            st.caption(f"Labelled: {label}")
    with cols[1]:
        events_captured = latest.get("event_total", 0)
        st.metric("Events captured", cast(MetricValue, events_captured))
    with cols[2]:
        errors_observed = latest_events.get("error", 0)
        st.metric("Errors observed", cast(MetricValue, errors_observed))

    replication = latest.get("replication")
    if isinstance(replication, Mapping):
        status_raw = replication.get("status")
        backend_raw = replication.get("backend")
        destination = replication.get("path")
        error_message = replication.get("error")
        status = str(status_raw).strip().lower() if status_raw else ""
        backend = str(backend_raw).strip() if backend_raw else "unspecified backend"
        message = f"Latest replication {status or 'status unknown'} via **{backend}**."
        if destination:
            message += f" Destination: `{destination}`."
        if error_message:
            message += f" Error: {error_message}."
        if status == "success":
            st.success(message)
        elif status == "error":
            st.error(message)
        else:
            st.info(message)
    else:
        st.caption("Remote replication disabled or no replication telemetry captured yet.")

    timeline = snapshot_timeline_frame(history)
    if not timeline.empty:
        timeline_chart = timeline.set_index("captured_at")[["event_total", "errors", "success"]]
        st.line_chart(timeline_chart)

    table = snapshot_history_table(history)
    if not table.empty:
        st.dataframe(table, use_container_width=True, hide_index=True)

    last_error = latest.get("last_error")
    if last_error:
        st.markdown("#### Most recent error event")
        st.json(last_error)


def build_data_story(
    *,
    row: pd.Series,
    filtered_size: int,
    total_size: int,
    filter_query: str,
    data_mode: str,
) -> str:
    """Craft an adaptive paragraph describing the current insight."""

    name = row.get("industry_name", "This industry")
    index_val = row.get("idiot_index")
    story_parts = []

    if pd.notna(index_val):
        story_parts.append(
            f"**{name}** carries an Idiot Index of **{index_val:.2f}**, highlighting the balance between gross output and materials cost."
        )
    else:
        story_parts.append(
            f"**{name}** lacks a recent Idiot Index reading, suggesting the source data may need review."
        )

    if filter_query:
        story_parts.append(
            f"You narrowed the field with the search `{filter_query}`, leaving {filtered_size:,} of {total_size:,} industries in focus."
        )
    else:
        story_parts.append(
            f"All {total_size:,} industries remain in view, giving you a full-spectrum comparison."
        )

    story_parts.append(
        f"The dataset is streaming from **{data_mode}**, keeping the analysis grounded in the latest available structures."
    )

    materials_share = row.get("materials_share_pct")
    if pd.notna(materials_share):
        if materials_share > 60:
            story_parts.append(
                "Materials dominate costs here, suggesting tighter margins and a closer watch on supplier dynamics."
            )
        elif materials_share < 40:
            story_parts.append(
                "Materials are a lighter share of costs, signaling room to leverage process or talent advantages."
            )
        else:
            story_parts.append("A balanced materials share hints at a stable operational rhythm.")

    return " ".join(story_parts)


MetricValue: TypeAlias = int | float | str | None
