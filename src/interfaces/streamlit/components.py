"""Composable UI components and adaptive helpers for the Idiot Index Streamlit app."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from html import escape
from typing import TypeAlias, cast

import pandas as pd
import plotly.express as px

import streamlit as st
from src.core import HealthSummary
from streamlit.runtime.uploaded_file_manager import UploadedFile

from .helpers import (
    DownloadArtifact,
    extract_health_badge,
    snapshot_history_table,
    snapshot_timeline_frame,
)

SOURCE_SESSION_KEY = "Source"
ONBOARDING_DISMISSED_SESSION_KEY = "first_run_onboarding_dismissed"


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
    run_requested: bool
    reset_requested: bool


def load_custom_styles() -> None:
    """Inject global CSS to create a calm, timeless visual system."""

    st.markdown(
        """
        <style>
            :root {
                --ink-900: #0b1f33;
                --ink-600: #33536f;
                --ink-300: #5f7488;
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
    *,
    show_focus_toggle: bool = True,
) -> bool:
    """Render the hero header and return the current focus mode toggle state."""

    with st.container():
        st.markdown(
            f"""
            <section class="page-hero" aria-label="Dashboard overview">
                <div class="page-hero__primary">
                    <h1>{escape(title)}</h1>
                    <p>{escape(subtitle)}</p>
                </div>
                <div class="page-hero__meta" role="list" aria-label="Dashboard context">
                    {''.join(f'<span class="meta-chip" role="listitem">{escape(label)}: {escape(value)}</span>' for label, value in meta.items())}
                </div>
            </section>
            """,
            unsafe_allow_html=True,
        )

    if not show_focus_toggle:
        return False

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
    st.sidebar.write(
        "Choose the active dataset and continue through explore, compare, and scenario steps."
    )

    options = [
        "Official snapshot (AIES 2023)",
        "Sample (offline)",
        "Upload CSV",
        "Census ASM (legacy)",
        "BEA (Economy-wide)",
    ]
    data_mode = st.sidebar.selectbox(
        "Data source",
        options,
        key=SOURCE_SESSION_KEY,
        help="Choose bundled sample data, an official snapshot, an upload, or a credentialed adapter.",
    )

    source_status = {
        "Official snapshot (AIES 2023)": "Official benchmark",
        "Sample (offline)": "Offline demonstration",
        "Upload CSV": "User-provided data",
        "Census ASM (legacy)": "Legacy adapter",
        "BEA (Economy-wide)": "Experimental adapter",
    }
    st.sidebar.caption(f"Status: {source_status[data_mode]}")

    min_year, max_year = year_bounds
    reference_default = 2023 if data_mode == "Official snapshot (AIES 2023)" else default_year
    year_input = int(
        st.sidebar.number_input(
            "Reference year",
            min_value=min_year,
            max_value=max_year,
            value=reference_default,
            step=1,
            disabled=data_mode == "Official snapshot (AIES 2023)",
            key="reference_year",
            help="Select the reporting year for sources that support multiple years.",
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

    bea_val = bea_key
    census_val = census_key

    uploaded_file = None
    if data_mode == "Upload CSV":
        uploaded_file = st.sidebar.file_uploader(
            "Industry data CSV",
            type=["csv"],
            key="industry_data_csv",
            help="Required columns: industry_code, industry_name, and year.",
        )
        if uploaded_file is None:
            st.sidebar.info("Drop a CSV to activate the canvas.")
    elif data_mode == "Census ASM (legacy)":
        st.sidebar.caption("Advanced adapter: requires a Census API key.")
        census_val = st.sidebar.text_input(
            "Census API Key",
            value=census_key,
            type="password",
            key="census_api_key_input",
            help="Used only for the legacy Census ASM adapter; the key remains masked.",
        )
        key_result = security_utils.validate_api_key(census_val, "Census")
        if not key_result.ok:
            st.sidebar.error(key_result.message)
            errors.append(key_result.message)
    elif data_mode == "BEA (Economy-wide)":
        st.sidebar.caption("Experimental adapter: requires a BEA API key.")
        bea_val = st.sidebar.text_input(
            "BEA API Key",
            value=bea_key,
            type="password",
            key="bea_api_key_input",
            help="Used only for the experimental BEA adapter; the key remains masked.",
        )
        key_result = security_utils.validate_api_key(bea_val, "BEA")
        if not key_result.ok:
            st.sidebar.error(key_result.message)
            errors.append(key_result.message)

    guidance = {
        "Official snapshot (AIES 2023)": (
            "Latest keyless Census benchmark: survey year 2023, released February 26, 2026. "
            "Uses total operating expenses as the denominator."
        ),
        "Sample (offline)": "Explore the dashboard instantly with bundled offline sample data.",
        "Upload CSV": "Bring your own dataset. Required columns: industry_code, industry_name, year.",
        "Census ASM (legacy)": (
            "Legacy manufacturing series through 2021. Not equivalent to the official AIES benchmark path."
        ),
        "BEA (Economy-wide)": (
            "Experimental adapter for BEA industry accounts. Not equivalent to the official AIES benchmark path."
        ),
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


def render_first_run_onboarding() -> None:
    """Render a session-dismissible guide for new dashboard visitors."""

    if ONBOARDING_DISMISSED_SESSION_KEY not in st.session_state:
        st.session_state[ONBOARDING_DISMISSED_SESSION_KEY] = False

    if st.sidebar.button("Show first-run guide", key="show_first_run_guide"):
        st.session_state[ONBOARDING_DISMISSED_SESSION_KEY] = False

    if st.session_state[ONBOARDING_DISMISSED_SESSION_KEY]:
        return

    st.subheader("First-run guide")
    st.info(
        "Start with Sample (offline): bundled data needs no credentials. Choose another source in "
        "the Data source control when you are ready."
    )
    st.markdown(
        "1. **Overview**\n"
        "2. **Explore**\n"
        "3. **Compare**\n"
        "4. **Scenario Lab**\n"
        "5. **Export**"
    )
    st.caption(
        "The output-to-cost ratio is descriptive. Composite indicators are experimental and "
        "algebraically related; outputs are not credit, insolvency, causal, investment, or policy conclusions."
    )
    if st.button("Dismiss first-run guide", key="dismiss_first_run_guide"):
        st.session_state[ONBOARDING_DISMISSED_SESSION_KEY] = True
        st.rerun()


def render_trend_data_table(trend_data: pd.DataFrame) -> None:
    """Render the accessible table alternative for a historical trend chart."""

    with st.expander("View historical trend data table", expanded=False):
        trend_table = trend_data.rename(
            columns={
                "year": "Year",
                "industry_name": "Industry",
                "industry_code": "Industry code",
                "idiot_index": "Output-to-cost ratio",
            }
        )
        st.dataframe(
            trend_table[["Year", "Industry", "Industry code", "Output-to-cost ratio"]],
            use_container_width=True,
            hide_index=True,
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
            "label": "Mean output-to-cost ratio",
            "value": f"{avg_idiot_index:.2f}" if avg_idiot_index is not None else "—",
            "hint": "gross output ÷ available cost input",
        },
    ]

    badge = extract_health_badge(health_summary)
    if badge["score"] is not None:
        cards.append(
            {
                "label": "Avg composite indicator",
                "value": str(badge["score"]),
                "hint": (
                    f"indicator band: {badge['band']}" if badge["band"] else "composite indicator"
                ),
            }
        )

    cols = st.columns(len(cards))
    for col, card in zip(cols, cards, strict=False):
        with col:
            st.markdown(
                f"""
                <section class="signal-card" role="group" aria-label="{escape(card['label'])}">
                    <div class="signal-card__label">{card['label']}</div>
                    <div class="signal-card__value">{card['value']}</div>
                    <div class="signal-card__hint">{card['hint']}</div>
                </section>
                """,
                unsafe_allow_html=True,
            )


def render_state_banner(message: str) -> None:
    """Display an adaptive banner summarizing the current context."""

    st.markdown(
        f"<div class='state-banner' role='status'>{escape(message)}</div>",
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
        st.markdown(
            "<section class='deep-dive' aria-label='Industry deep dive'>", unsafe_allow_html=True
        )
        st.markdown(
            f"<h2 class='deep-dive__heading'>{escape(str(row['industry_name']))}</h2>",
            unsafe_allow_html=True,
        )
        st.caption(
            f"Code: {row['industry_code']} · Year: {int(row['year']) if pd.notna(row['year']) else 'N/A'}"
        )

        metric_cols = container.columns(4 if not focus_mode else 2)
        key_metrics = [
            ("Output-to-cost ratio", row.get("idiot_index")),
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
                elif label == "Output-to-cost ratio":
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
        st.markdown("</section>", unsafe_allow_html=True)


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
        "Scenario output is arithmetic sensitivity analysis, not a forecast. "
        "Run a scenario only after setting at least one non-zero adjustment."
    )
    selection = st.multiselect(
        "Target industries",
        options=list(available_codes),
        default=list(default_selection or []),
        format_func=code_formatter,
        help="Leave empty to stress test the entire dataset.",
        key="scenario_target_codes",
    )

    with st.expander("Adjust cost structure", expanded=True):
        gross_delta = st.slider(
            "Gross output change (%)",
            min_value=-50.0,
            max_value=50.0,
            value=default_gross_delta,
            step=1.0,
            key="scenario_gross_delta",
        )
        materials_delta = st.slider(
            "Materials cost change (%)",
            min_value=-50.0,
            max_value=50.0,
            value=default_materials_delta,
            step=1.0,
            key="scenario_materials_delta",
        )
        value_delta = st.slider(
            "Value added change (%)",
            min_value=-25.0,
            max_value=25.0,
            value=default_value_delta,
            step=1.0,
            key="scenario_value_delta",
        )
        intermediate_delta = st.slider(
            "Intermediate inputs change (%)",
            min_value=-50.0,
            max_value=50.0,
            value=default_intermediate_delta,
            step=1.0,
            help="Applies when intermediate inputs are available separately from materials cost.",
            key="scenario_intermediate_delta",
        )

    action_col, reset_col = st.columns(2)
    with action_col:
        run_requested = st.button("Run scenario", use_container_width=True, key="scenario_run")
    with reset_col:
        reset_requested = st.button(
            "Reset scenario", use_container_width=True, key="scenario_reset"
        )

    return ScenarioControlState(
        target_codes=list(selection),
        gross_output_delta_pct=gross_delta,
        materials_cost_delta_pct=materials_delta,
        value_added_delta_pct=value_delta,
        intermediate_inputs_delta_pct=intermediate_delta,
        run_requested=run_requested,
        reset_requested=reset_requested,
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
    scenario_summary = summary.get("scenario")
    delta_summary = cast(Mapping[str, float | None], summary["delta"])

    st.caption(
        "Baseline values are current-state estimates. Scenario values and deltas are arithmetic sensitivity outputs only."
    )

    metric_cols_primary = st.columns(3)

    def _metric(
        column,
        label: str,
        baseline_value: float | None,
        scenario_value: float | None,
        delta_value: float | None,
    ) -> None:
        if baseline_value is None or scenario_value is None:
            column.metric(label, "—", None)
            return

        delta_display = f"{delta_value:+,.2f}" if delta_value is not None else None
        column.metric(
            label,
            f"Baseline {baseline_value:,.2f}",
            f"Scenario {scenario_value:,.2f} ({delta_display})" if delta_display else None,
        )

    _metric(
        metric_cols_primary[0],
        "Gross output total",
        getattr(baseline_summary, "gross_output_total", None),
        getattr(scenario_summary, "gross_output_total", None),
        delta_summary.get("gross_output_total"),
    )
    _metric(
        metric_cols_primary[1],
        "Value added total",
        getattr(baseline_summary, "value_added_total", None),
        getattr(scenario_summary, "value_added_total", None),
        delta_summary.get("value_added_total"),
    )
    _metric(
        metric_cols_primary[2],
        "Average comparative score",
        getattr(baseline_summary, "resilience_score_avg", None),
        getattr(scenario_summary, "resilience_score_avg", None),
        delta_summary.get("resilience_score_avg"),
    )

    metric_cols_secondary = st.columns(4)
    _metric(
        metric_cols_secondary[0],
        "Average output-to-cost ratio",
        getattr(baseline_summary, "idiot_index_avg", None),
        getattr(scenario_summary, "idiot_index_avg", None),
        delta_summary.get("idiot_index_avg"),
    )
    _metric(
        metric_cols_secondary[1],
        "Materials dependency ratio",
        getattr(baseline_summary, "materials_dependency_ratio_avg", None),
        getattr(scenario_summary, "materials_dependency_ratio_avg", None),
        delta_summary.get("materials_dependency_ratio_avg"),
    )
    _metric(
        metric_cols_secondary[2],
        "Input sensitivity index",
        getattr(baseline_summary, "shock_sensitivity_index_avg", None),
        getattr(scenario_summary, "shock_sensitivity_index_avg", None),
        delta_summary.get("shock_sensitivity_index_avg"),
    )
    _metric(
        metric_cols_secondary[3],
        "Average composite indicator",
        getattr(baseline_summary, "health_score_avg", None),
        getattr(scenario_summary, "health_score_avg", None),
        delta_summary.get("health_score_avg"),
    )

    health_meta = cast(dict[str, HealthSummary | None], summary.get("health", {}))
    baseline_health = health_meta.get("baseline")
    scenario_health = health_meta.get("scenario")
    if baseline_health and scenario_health:
        st.caption(
            "Indicator-band shift: "
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
        st.write("Export the current analysis outputs.")
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
        timeline_chart = px.line(
            timeline,
            x="captured_at",
            y=["event_total", "errors", "success"],
            labels={"captured_at": "Captured at", "value": "Events", "variable": "Series"},
        )
        st.plotly_chart(timeline_chart, use_container_width=True)

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
            f"**{name}** carries an output-to-cost ratio of **{index_val:.2f}**, highlighting the balance between gross output and its available cost input."
        )
    else:
        story_parts.append(
            f"**{name}** lacks a recent output-to-cost ratio reading, suggesting the source data may need review."
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
        if materials_share > 60 and data_mode == "Official snapshot (AIES 2023)":
            story_parts.append(
                "Operating expenses dominate reported revenue here, indicating a narrow "
                "operating spread under the AIES proxy."
            )
        elif materials_share > 60:
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


MetricValue: TypeAlias = (  # noqa: UP040 - Compatible alias for mypy runtime version
    int | float | str | None
)
