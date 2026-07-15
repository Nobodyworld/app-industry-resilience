"""Streamlit dashboard for exploring Idiot Index metrics and narratives.

The app composes application services with Streamlit components to fetch data,
compute metrics, and render an adaptive user interface. The module also
exposes a handful of utility functions that are reused by tests to mock API
calls and CSV uploads.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any, cast
from urllib.parse import urlencode

import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit.runtime.uploaded_file_manager import UploadedFile

from src.application import (
    DataSource,
    NormalizationOptions,
    ScenarioAdjustment,
    ScenarioPlanner,
    evaluate_idiot_index,
)
from src.core import FilePolicy, SecurityUtils, get_config_summary
from src.interfaces.streamlit.bootstrap import (
    BootstrapError,
    get_bootstrap_state,
)
from src.interfaces.streamlit.components import (
    SOURCE_SESSION_KEY,
    build_data_story,
    load_custom_styles,
    render_deep_dive,
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
from src.interfaces.streamlit.helpers import (
    build_comparison_table,
    build_health_band_distribution,
    build_scenario_comparison_table,
    calculate_benchmark,
    decode_query_params,
    encode_query_params,
    load_snapshot_history,
    prepare_download_artifacts,
    prepare_trend_data,
    summarise_scenario_deltas,
)


def _get_query_params() -> dict[str, list[str]]:
    """Return query params as a mutable mapping of key to list of values."""

    if hasattr(st, "experimental_get_query_params"):
        return dict(decode_query_params(st.experimental_get_query_params()))

    params = st.query_params
    query_params: dict[str, list[str]] = {}
    for key in list(params.keys()):
        values: list[str] = []
        get_all = getattr(params, "get_all", None)
        if callable(get_all):
            raw_values = get_all(key)
            if raw_values:
                values = [str(value) for value in raw_values]
        if not values:
            raw_value = params.get(key)
            if raw_value is None:
                continue
            if isinstance(raw_value, list):
                values = [str(value) for value in raw_value]
            else:
                values = [str(raw_value)]
        if values:
            query_params[key] = values
    return query_params


def _set_query_params(params: Mapping[str, list[str]]) -> None:
    """Set query params using modern Streamlit API with legacy fallback."""

    if hasattr(st, "experimental_set_query_params"):
        st.experimental_set_query_params(**params)
        return

    query_params = st.query_params
    query_params.clear()
    for key, values in params.items():
        if not values:
            continue
        if len(values) == 1:
            query_params[key] = values[0]
        else:
            query_params[key] = values


@st.cache_data(show_spinner=False)
def load_sample() -> pd.DataFrame:
    """Return the bundled sample dataset for offline exploration."""

    return pd.read_csv("data/sample_industries.csv")


@st.cache_data(show_spinner=False)
def load_official_snapshot() -> pd.DataFrame:
    """Return the refreshed, keyless Census AIES snapshot."""

    return pd.read_csv("data/official_industry_snapshot.csv")


def process_uploaded_file(
    uploaded_file: UploadedFile, *, policy: FilePolicy
) -> tuple[pd.DataFrame | None, str | None]:
    """Validate and materialize a CSV upload into a dataframe."""

    try:
        meta_result = SecurityUtils.validate_file_upload(
            uploaded_file.name,
            policy,
            file_size_bytes=getattr(uploaded_file, "size", None),
        )
        if not meta_result.ok:
            return None, f"File security check failed: {meta_result.message}"

        temp_df = pd.read_csv(uploaded_file)

        content_result = SecurityUtils.validate_csv_content(temp_df)
        if not content_result.ok:
            return None, f"CSV content security check failed: {content_result.message}"

        required_cols = ["industry_code", "industry_name", "year"]
        optional_cols = [
            "gross_output",
            "materials_cost",
            "intermediate_inputs",
            "value_added",
            "source",
        ]

        df_columns = [col.lower().strip() for col in temp_df.columns]
        missing_required = [col for col in required_cols if col not in df_columns]

        if missing_required:
            hint = ", ".join(required_cols)
            optional = ", ".join(optional_cols)
            return (
                None,
                "CSV missing required columns: {missing}. Required: {req}. Optional: {opt}.".format(
                    missing=", ".join(missing_required), req=hint, opt=optional
                ),
            )

        return temp_df, None
    except Exception as exc:  # pragma: no cover - Streamlit runtime safeguard
        return None, f"Error reading CSV: {exc}"


st.set_page_config(
    page_title="U.S. Industry Cost Structure and Resilience Dashboard", layout="wide"
)
load_custom_styles()

SCENARIO_PLANNER = ScenarioPlanner()

try:
    bootstrap_state = get_bootstrap_state()
except BootstrapError as exc:
    st.sidebar.error(f"Configuration error: {exc}")
    st.stop()

CONFIG_VALIDATION = bootstrap_state.validation

try:
    APP_CONFIG = bootstrap_state.ensure_ready()
except BootstrapError as exc:
    for err in bootstrap_state.errors:
        st.sidebar.error(err)
    st.sidebar.error(str(exc))
    st.stop()

APP_NORMALIZATION = NormalizationOptions(
    dtype_overrides=dict(APP_CONFIG.normalization_dtype_overrides)
)

OBSERVABILITY_HISTORY = load_snapshot_history(APP_CONFIG.observability_snapshot_dir, limit=12)
bootstrap_warnings = list(bootstrap_state.warnings)
config_summary = cast(dict[str, Any], get_config_summary(APP_CONFIG))
handler_summary = SecurityUtils.rate_limit_handler_summary()
config_summary.setdefault("rate_limit_backend", {})["handler"] = handler_summary

query_params_initial = _get_query_params()


def _last_value(key: str, default: str | None = None) -> str | None:
    """Return the last query parameter value for ``key`` if present."""

    values = query_params_initial.get(key)
    if not values:
        return default
    return values[-1]


if "focus_mode" not in st.session_state:
    focus_raw = (_last_value("focus", "false") or "false").lower()
    st.session_state["focus_mode"] = focus_raw in {"true", "1", "yes"}
if "search_query" not in st.session_state:
    st.session_state["search_query"] = _last_value("search", "") or ""
if "industry_selection_code" not in st.session_state:
    st.session_state["industry_selection_code"] = _last_value("industry")
if "comparison_codes" not in st.session_state:
    st.session_state["comparison_codes"] = query_params_initial.get("compare", [])

sidebar_context = bootstrap_state.sidebar_context

year_override = sidebar_context.default_year
year_override_raw = _last_value("year")
if year_override_raw:
    try:
        year_override = int(year_override_raw)
    except ValueError:
        year_override = sidebar_context.default_year

year_override = sidebar_context.normalise_year(year_override)

sidebar_modes = [
    "Official snapshot (AIES 2023)",
    "Sample (offline)",
    "Upload CSV",
    "Census ASM (legacy)",
    "BEA (Economy-wide)",
]
mode_raw = _last_value("mode")
if mode_raw:
    slug_lookup = {option.lower().replace(" ", "-"): option for option in sidebar_modes}
    resolved_mode = slug_lookup.get(mode_raw)
    if resolved_mode:
        st.session_state[SOURCE_SESSION_KEY] = resolved_mode
elif SOURCE_SESSION_KEY not in st.session_state:
    st.session_state[SOURCE_SESSION_KEY] = "Sample (offline)"

year_bounds = sidebar_context.year_bounds

sidebar_state = render_sidebar(
    default_year=year_override,
    year_bounds=year_bounds,
    bea_key=APP_CONFIG.bea_api_key or "",
    census_key=APP_CONFIG.census_api_key or "",
    security_utils=SecurityUtils,
)

data_mode = sidebar_state.data_mode

with st.sidebar.expander("Technical diagnostics", expanded=False):
    if bootstrap_warnings and data_mode in {"Census ASM (legacy)", "BEA (Economy-wide)"}:
        for warning in bootstrap_warnings:
            st.warning(warning)

    rate_backend = handler_summary.get("backend", "memory")
    if rate_backend == "redis":
        if handler_summary.get("last_error"):
            st.warning(
                "Redis rate limiter is active but reported recent errors; falling back to in-memory tokens."
            )
        else:
            st.success("Redis-backed rate limiting active across instances.")
    else:
        st.info("Rate limiting is running in in-process memory mode.")

    st.json(config_summary)

if sidebar_state.halt or sidebar_state.year_clean is None:
    st.stop()

data_mode_slug = data_mode.lower().replace(" ", "-")
year_clean = sidebar_state.year_clean
if data_mode == "Official snapshot (AIES 2023)":
    year_clean = 2023
bea_key = sidebar_state.bea_key.strip()
census_key = sidebar_state.census_key.strip()
uploaded_file = sidebar_state.uploaded_file

mode_to_source = {
    "Sample (offline)": DataSource.SAMPLE,
    "Census ASM (legacy)": DataSource.CENSUS,
    "BEA (Economy-wide)": DataSource.BEA,
}

service_source = mode_to_source.get(data_mode, DataSource.SAMPLE)
dataframe_override: pd.DataFrame | None = None
service_config = APP_CONFIG
error: str | None = None

if data_mode == "Official snapshot (AIES 2023)":
    dataframe_override = load_official_snapshot()
elif data_mode == "Upload CSV":
    if uploaded_file is None:
        st.stop()
    dataframe_override, error = process_uploaded_file(
        uploaded_file, policy=FilePolicy(max_size_mb=APP_CONFIG.max_csv_size_mb)
    )
    if error:
        st.sidebar.error(error)
        st.stop()
    st.sidebar.success("CSV loaded and validated.")
else:
    if service_source is DataSource.BEA and bea_key:
        service_config = replace(APP_CONFIG, bea_api_key=bea_key)
    elif service_source is DataSource.CENSUS and census_key:
        service_config = replace(APP_CONFIG, census_api_key=census_key)

summary = None
if data_mode in {"Official snapshot (AIES 2023)", "Upload CSV"}:
    source_for_service = DataSource.SAMPLE
else:
    source_for_service = service_source

fetch_status = st.sidebar.empty()
spinner_message = "Computing industry metrics…"
if data_mode == "Official snapshot (AIES 2023)":
    fetch_status.info("Loading: latest official Census AIES snapshot…")
    spinner_message = "Loading Census AIES survey-year 2023 data…"
elif data_mode == "Sample (offline)":
    fetch_status.info("Loading: bundled sample dataset…")
    spinner_message = "Loading sample dataset…"
elif data_mode == "Census ASM (legacy)":
    fetch_status.info(f"Loading: Census ASM data for {year_clean}…")
    spinner_message = f"Fetching Census ASM data for {year_clean}…"
elif data_mode == "BEA (Economy-wide)":
    fetch_status.info(f"Loading: BEA tables for {year_clean}…")
    spinner_message = f"Fetching BEA tables for {year_clean}…"
elif data_mode == "Upload CSV":
    fetch_status.info("Loading: validating uploaded dataset…")
    spinner_message = "Validating uploaded dataset…"

try:
    with st.spinner(spinner_message):
        summary = evaluate_idiot_index(
            year=year_clean,
            source=source_for_service,
            dataframe=dataframe_override,
            config=service_config,
            sample_loader=load_sample,
            top_n=50,
            normalization_options=APP_NORMALIZATION,
        )
    if data_mode == "Official snapshot (AIES 2023)":
        fetch_status.success("Ready: Census AIES 2023 benchmark (released February 26, 2026).")
    elif data_mode == "Census ASM (legacy)":
        fetch_status.success(f"Ready: Census ASM data for {year_clean}.")
    elif data_mode == "BEA (Economy-wide)":
        fetch_status.success(f"Ready: BEA tables for {year_clean}.")
    elif data_mode == "Sample (offline)":
        fetch_status.success("Ready: bundled sample dataset.")
    else:
        fetch_status.success("Ready: industry metrics computed.")
except Exception as exc:  # pylint: disable=broad-except
    error = str(exc)
    fetch_status.error(f"Error: {data_mode.split(' (')[0]} fetch failed: {exc}")
    summary = None

if summary is None:
    st.stop()

df_display = summary.dataframe_full

current_query_raw = st.session_state.get("search_query", "")
current_query = SecurityUtils.sanitize_string_input(current_query_raw.strip())

df_filtered = df_display.copy()
if current_query:
    query_lower = current_query.lower()
    df_filtered = df_filtered[
        df_filtered["industry_name"].str.lower().str.contains(query_lower)
        | df_filtered["industry_code"].str.lower().str.contains(query_lower)
    ]

render_page_header(
    title="U.S. Industry Cost Structure and Resilience Dashboard",
    subtitle="Explore industry cost structures using transparent ratio calculations and scenario sensitivity checks.",
    meta={
        "Source": data_mode,
        "Year": str(year_clean),
        "Visible": f"{len(df_filtered):,} / {len(df_display):,}",
    },
    focus_mode=False,
    show_focus_toggle=False,
)

render_state_banner(
    "Start with source and vintage, then explore an industry, compare peers, and run a scenario before exporting outputs."
)

render_first_run_onboarding()

st.markdown("### Start here")
st.markdown(
    "1. Confirm source and vintage.\n"
    "2. Use the **Output-to-cost ratio** (gross output divided by materials cost or intermediate inputs).\n"
    "3. Explore one industry, compare peers, then run a scenario.\n"
    "4. Export full or filtered results from the export panel."
)
st.caption(
    "This ratio is not a credit model or causal forecast. Census AIES uses a revenue-to-operating-expense proxy. "
    "Composite indicators are experimental and algebraically related, so they do not independently prove industry health or distress."
)
st.caption('Historically described as the informal "Idiot Index" in legacy materials.')

if data_mode == "Official snapshot (AIES 2023)":
    st.info(
        "**Data vintage:** 2023 Annual Integrated Economic Survey, released February 26, 2026. "
        "This dashboard shows a revenue-to-operating-expense proxy for cost structure analysis."
    )
    with st.expander("About this dataset", expanded=False):
        st.markdown("**Official-data availability timeline (as of June 27, 2026)**")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Source": "Census ASM",
                        "Observation period": "2021",
                        "Published": "May 31, 2023",
                        "Status / next milestone": "Discontinued; replaced by AIES",
                    },
                    {
                        "Source": "Census Economic Census",
                        "Observation period": "2022",
                        "Published": "April 10, 2025",
                        "Status / next milestone": "Five-year manufacturing benchmark",
                    },
                    {
                        "Source": "Census AIES",
                        "Observation period": "2023",
                        "Published": "February 26, 2026",
                        "Status / next milestone": "Current annual comprehensive benchmark",
                    },
                    {
                        "Source": "BEA GDP by Industry",
                        "Observation period": "2026 Q1",
                        "Published": "June 25, 2026",
                        "Status / next milestone": "Next industry release: September 30, 2026",
                    },
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

render_signal_bar(df_filtered, health_summary=summary.health_summary_filtered)


def _format_overview_table(frame: pd.DataFrame) -> pd.DataFrame:
    table = frame.loc[
        :,
        [
            "industry_code",
            "industry_name",
            "year",
            "idiot_index",
            "value_added_pct",
            "materials_share_pct",
            "source",
        ],
    ].copy()
    table = table.rename(
        columns={
            "industry_code": "Industry code",
            "industry_name": "Industry",
            "year": "Year",
            "idiot_index": "Output-to-cost ratio",
            "value_added_pct": "Value-added (%)",
            "materials_share_pct": "Cost share (%)",
            "source": "Source",
        }
    )
    for col in ["Output-to-cost ratio", "Value-added (%)", "Cost share (%)"]:
        table[col] = pd.to_numeric(table[col], errors="coerce").round(2)
    return table


tabs = ["Overview", "Explore", "Compare", "Scenario Lab"]
overview_tab, explore_tab, compare_tab, scenario_tab = render_insight_tabs(tabs)

code_lookup = dict(zip(df_filtered["industry_code"], df_filtered["industry_name"], strict=False))
choices: Sequence[str] = list(dict.fromkeys(df_filtered["industry_code"]))
selected_code: str | None = None
if choices:
    default_code = st.session_state.get("industry_selection_code")
    if default_code not in choices:
        default_code = choices[0]
    selected_code = default_code
    st.session_state["industry_selection_code"] = selected_code

with overview_tab:
    st.subheader("Overview")
    st.markdown("**Top industries by output-to-cost ratio**")
    overview_table = _format_overview_table(
        df_filtered.sort_values("idiot_index", ascending=False).head(10)
    )
    st.dataframe(overview_table, use_container_width=True, hide_index=True)

    health_filtered = summary.health_summary_filtered
    distribution_table = build_health_band_distribution(health_filtered)
    if not distribution_table.empty:
        st.markdown("**Indicator-band distribution**")
        st.dataframe(distribution_table, use_container_width=True, hide_index=True)

with explore_tab:
    st.subheader("Explore")
    search_value = st.text_input(
        "Search by name or code",
        value=current_query_raw,
        placeholder="Start typing to focus the table…",
        key="search_query",
    )
    sanitized = SecurityUtils.sanitize_string_input(search_value.strip() if search_value else "")
    df_view = df_display.copy()
    if sanitized:
        query_lower = sanitized.lower()
        df_view = df_view[
            df_view["industry_name"].str.lower().str.contains(query_lower)
            | df_view["industry_code"].str.lower().str.contains(query_lower)
        ]

    st.dataframe(
        _format_overview_table(
            df_view.sort_values(["year", "idiot_index"], ascending=[False, False])
        ),
        use_container_width=True,
        hide_index=True,
    )

    if not choices:
        st.warning("No industries match the current filters.")
    else:
        selected_code = st.selectbox(
            "Select an industry",
            choices,
            index=choices.index(selected_code) if selected_code in choices else 0,
            format_func=lambda code: f"{code_lookup.get(code, code)} ({code})",
        )
        st.session_state["industry_selection_code"] = selected_code
        row = df_filtered[df_filtered["industry_code"] == selected_code].head(1)
        if row.empty:
            st.error("No data available for the selected industry.")
        else:
            current_row = row.iloc[0]
            story = build_data_story(
                row=current_row,
                filtered_size=len(df_filtered),
                total_size=len(df_display),
                filter_query=SecurityUtils.sanitize_string_input(
                    st.session_state.get("search_query", "").strip()
                ),
                data_mode=data_mode,
            )
            render_deep_dive(row=current_row, story=story, focus_mode=False)

    with st.expander("Advanced data view", expanded=False):
        st.dataframe(df_view, use_container_width=True)

comparison_selection: list[str] = []
with compare_tab:
    st.subheader("Compare")
    comparison_options = sorted(code_lookup.keys())
    valid_existing = [
        code for code in st.session_state.get("comparison_codes", []) if code in comparison_options
    ]
    comparison_selection = st.multiselect(
        "Compare industries",
        options=comparison_options,
        default=valid_existing,
        format_func=lambda code: f"{code_lookup.get(code, code)} ({code})",
    )
    st.session_state["comparison_codes"] = comparison_selection

    comparison_table = build_comparison_table(df_display, comparison_selection)
    if comparison_table.empty:
        st.info(
            "Select one or more industries to compare output-to-cost ratio and composition signals."
        )
    else:
        comparison_display = comparison_table.rename(
            columns={
                "industry_code": "Industry code",
                "industry_name": "Industry",
                "idiot_index": "Output-to-cost ratio",
                "value_added_pct": "Value-added (%)",
                "materials_share_pct": "Cost share (%)",
                "gross_output": "Gross output",
                "value_added": "Value added",
                "resilience_score": "Comparative score",
                "materials_dependency_ratio": "Materials dependency ratio",
                "shock_sensitivity_index": "Input sensitivity index",
            }
        )
        st.dataframe(comparison_display.round(3), use_container_width=True, hide_index=True)

    trend_selection = comparison_selection or ([selected_code] if selected_code else [])
    trend_data = prepare_trend_data(df_display, trend_selection)
    if trend_data.empty or trend_data["year"].nunique() <= 1:
        st.caption("Add additional years to see historical trendlines for selected industries.")
    else:
        trend_fig = px.line(
            trend_data,
            x="year",
            y="idiot_index",
            color="industry_name",
            title="Historical output-to-cost ratio trend",
        )
        trend_fig.update_layout(xaxis_title="Year", yaxis_title="Output-to-cost ratio")
        st.plotly_chart(trend_fig, use_container_width=True)
        render_trend_data_table(trend_data)

    benchmark_stats = calculate_benchmark(df_display, selected_code)
    metric_cols = st.columns(3)
    with metric_cols[0]:
        st.metric(
            "Dataset average output-to-cost ratio",
            (
                f"{benchmark_stats.get('idiot_index_avg'):.2f}"
                if benchmark_stats.get("idiot_index_avg") is not None
                and pd.notna(benchmark_stats.get("idiot_index_avg"))
                else "—"
            ),
            delta=(
                f"{benchmark_stats.get('idiot_index_delta'):+.2f}"
                if benchmark_stats.get("idiot_index_delta") is not None
                and pd.notna(benchmark_stats.get("idiot_index_delta"))
                else None
            ),
        )
    with metric_cols[1]:
        st.metric(
            "Dataset average value-added (%)",
            (
                f"{benchmark_stats.get('value_added_pct_avg'):.1f}%"
                if benchmark_stats.get("value_added_pct_avg") is not None
                and pd.notna(benchmark_stats.get("value_added_pct_avg"))
                else "—"
            ),
            delta=(
                f"{benchmark_stats.get('value_added_pct_delta'):+.1f}%"
                if benchmark_stats.get("value_added_pct_delta") is not None
                and pd.notna(benchmark_stats.get("value_added_pct_delta"))
                else None
            ),
        )
    with metric_cols[2]:
        st.metric(
            "Dataset average cost share (%)",
            (
                f"{benchmark_stats.get('materials_share_pct_avg'):.1f}%"
                if benchmark_stats.get("materials_share_pct_avg") is not None
                and pd.notna(benchmark_stats.get("materials_share_pct_avg"))
                else "—"
            ),
            delta=(
                f"{benchmark_stats.get('materials_share_pct_delta'):+.1f}%"
                if benchmark_stats.get("materials_share_pct_delta") is not None
                and pd.notna(benchmark_stats.get("materials_share_pct_delta"))
                else None
            ),
        )


def _last_float_query(key: str, default: float = 0.0) -> float:
    values = query_params_initial.get(key)
    if not values:
        return default
    try:
        return float(values[-1])
    except (TypeError, ValueError):
        return default


scenario_defaults_selection = [
    code for code in query_params_initial.get("scenario_codes", []) if code in code_lookup
]
scenario_default_gross = _last_float_query("scenario_gross")
scenario_default_materials = _last_float_query("scenario_materials")
scenario_default_value = _last_float_query("scenario_value")
scenario_default_intermediate = _last_float_query("scenario_intermediate")

if st.session_state.pop("scenario_reset_pending", False):
    for key in [
        "scenario_target_codes",
        "scenario_gross_delta",
        "scenario_materials_delta",
        "scenario_value_delta",
        "scenario_intermediate_delta",
    ]:
        st.session_state.pop(key, None)

if "scenario_target_codes" not in st.session_state:
    st.session_state["scenario_target_codes"] = (
        scenario_defaults_selection
        or comparison_selection
        or ([selected_code] if selected_code else [])
    )
if "scenario_gross_delta" not in st.session_state:
    st.session_state["scenario_gross_delta"] = scenario_default_gross
if "scenario_materials_delta" not in st.session_state:
    st.session_state["scenario_materials_delta"] = scenario_default_materials
if "scenario_value_delta" not in st.session_state:
    st.session_state["scenario_value_delta"] = scenario_default_value
if "scenario_intermediate_delta" not in st.session_state:
    st.session_state["scenario_intermediate_delta"] = scenario_default_intermediate

with scenario_tab:
    st.subheader("Scenario Lab")

    available_scenario_codes = sorted(code_lookup.keys())
    valid_scenario_targets = [
        code
        for code in cast(list[str], st.session_state.get("scenario_target_codes", []))
        if code in available_scenario_codes
    ]
    st.session_state["scenario_target_codes"] = valid_scenario_targets

    scenario_controls = render_scenario_controls(
        available_codes=available_scenario_codes,
        code_formatter=lambda code: f"{code_lookup.get(code, code)} ({code})",
        default_selection=valid_scenario_targets,
        default_gross_delta=float(st.session_state.get("scenario_gross_delta", 0.0)),
        default_materials_delta=float(st.session_state.get("scenario_materials_delta", 0.0)),
        default_value_delta=float(st.session_state.get("scenario_value_delta", 0.0)),
        default_intermediate_delta=float(st.session_state.get("scenario_intermediate_delta", 0.0)),
    )

    has_non_zero_adjustment = any(
        abs(value) > 0.001
        for value in [
            scenario_controls.gross_output_delta_pct,
            scenario_controls.materials_cost_delta_pct,
            scenario_controls.value_added_delta_pct,
            scenario_controls.intermediate_inputs_delta_pct,
        ]
    )

    scenario_payload = {
        "target_codes": list(scenario_controls.target_codes),
        "gross": float(scenario_controls.gross_output_delta_pct),
        "materials": float(scenario_controls.materials_cost_delta_pct),
        "value": float(scenario_controls.value_added_delta_pct),
        "intermediate": float(scenario_controls.intermediate_inputs_delta_pct),
    }

    if scenario_controls.reset_requested:
        st.session_state["scenario_committed"] = None
        st.session_state["scenario_reset_pending"] = True
        st.rerun()

    if scenario_controls.run_requested:
        if not has_non_zero_adjustment:
            st.warning("Set at least one non-zero adjustment before running a scenario.")
            st.session_state["scenario_committed"] = None
        else:
            st.session_state["scenario_committed"] = scenario_payload

    committed_scenario = st.session_state.get("scenario_committed")
    adjustment_active = committed_scenario is not None

    if adjustment_active and committed_scenario != scenario_payload:
        st.info("Adjustments changed. Click Run scenario to refresh results.")

    if adjustment_active:
        scenario_adjustment = ScenarioAdjustment(
            industry_codes=committed_scenario["target_codes"] or None,
            gross_output_delta_pct=committed_scenario["gross"],
            materials_cost_delta_pct=committed_scenario["materials"],
            value_added_delta_pct=committed_scenario["value"],
            intermediate_inputs_delta_pct=committed_scenario["intermediate"],
        )

        scenario_result = SCENARIO_PLANNER.plan(df_display, [scenario_adjustment])
        scenario_summary = summarise_scenario_deltas(scenario_result, top_n=10)

        focus_codes: Sequence[str] = committed_scenario["target_codes"] or comparison_selection
        if not focus_codes and selected_code:
            focus_codes = [selected_code]

        scenario_table = build_scenario_comparison_table(
            scenario_result, focus_codes=focus_codes or None
        )
        scenario_table_display = scenario_table.rename(
            columns={
                "industry_code": "Industry code",
                "industry_name": "Industry",
                "gross_output_baseline": "Gross output (baseline)",
                "gross_output_scenario": "Gross output (scenario)",
                "gross_output_delta": "Gross output (delta)",
                "materials_cost_baseline": "Materials cost (baseline)",
                "materials_cost_scenario": "Materials cost (scenario)",
                "materials_cost_delta": "Materials cost (delta)",
                "value_added_baseline": "Value added (baseline)",
                "value_added_scenario": "Value added (scenario)",
                "value_added_delta": "Value added (delta)",
                "idiot_index_baseline": "Output-to-cost ratio (baseline)",
                "idiot_index_scenario": "Output-to-cost ratio (scenario)",
                "idiot_index_delta": "Output-to-cost ratio (delta)",
                "resilience_score_baseline": "Comparative score (baseline)",
                "resilience_score_scenario": "Comparative score (scenario)",
                "resilience_score_delta": "Comparative score (delta)",
            }
        ).round(3)

        top_deltas = cast(pd.DataFrame, scenario_summary["top"]).copy()
        top_deltas = top_deltas.rename(
            columns={
                "industry_code": "Industry code",
                "industry_name": "Industry",
                "idiot_index": "Output-to-cost ratio (delta)",
            }
        )

        chart_source = scenario_result.deltas
        if focus_codes:
            chart_source = chart_source[chart_source["industry_code"].isin(focus_codes)]
        chart_slice = chart_source.sort_values("idiot_index", ascending=False).head(10)
        scenario_fig = px.bar(
            chart_slice,
            x="idiot_index",
            y="industry_name",
            orientation="h",
            title="Output-to-cost ratio delta (scenario vs baseline)",
            labels={"idiot_index": "Δ Output-to-cost ratio", "industry_name": "Industry"},
            color="idiot_index",
            color_continuous_scale="Tealrose",
        )
        scenario_fig.update_layout(
            xaxis_title="Δ Output-to-cost ratio",
            yaxis_title="Industry",
        )

        render_scenario_results(
            summary=scenario_summary,
            comparison_table=scenario_table_display,
            top_deltas=top_deltas,
            figure=scenario_fig,
        )
    else:
        st.info(
            "Idle scenario state. Select an industry target if useful, set at least one non-zero adjustment, and click Run scenario."
        )

with st.expander("Technical diagnostics", expanded=False):
    render_observability_snapshots(
        OBSERVABILITY_HISTORY,
        empty_message=(
            "Snapshots are persisted under "
            f"`{APP_CONFIG.observability_snapshot_dir}`. Run `make observability-snapshot` to capture one."
        ),
    )

download_artifacts = prepare_download_artifacts(
    df_full=df_display,
    df_filtered=df_filtered,
    base_name="industry_cost_structure_results",
)
st.caption(
    "Export scope: 'All rows' exports the active dataset for the selected source; "
    "'Current view' exports the currently filtered table state."
)
render_download_panel(download_artifacts)

share_mapping: dict[str, list[str]] = dict(
    encode_query_params(
        focus="false",
        search=st.session_state.get("search_query", "") or None,
        industry=selected_code if selected_code else None,
        compare=comparison_selection if comparison_selection else None,
        year=str(year_clean) if year_clean is not None else None,
        mode=data_mode_slug,
    )
)


def _store_scenario_param(key: str, value: float) -> None:
    if abs(value) > 0.001:
        share_mapping[key] = [f"{value:.1f}"]
    else:
        share_mapping.pop(key, None)


if adjustment_active and committed_scenario:
    if committed_scenario["target_codes"]:
        share_mapping["scenario_codes"] = list(committed_scenario["target_codes"])
    else:
        share_mapping.pop("scenario_codes", None)
    _store_scenario_param("scenario_gross", committed_scenario["gross"])
    _store_scenario_param("scenario_materials", committed_scenario["materials"])
    _store_scenario_param("scenario_value", committed_scenario["value"])
    _store_scenario_param("scenario_intermediate", committed_scenario["intermediate"])
else:
    for key in [
        "scenario_codes",
        "scenario_gross",
        "scenario_materials",
        "scenario_value",
        "scenario_intermediate",
    ]:
        share_mapping.pop(key, None)


def _normalise(mapping: Mapping[str, list[str]]) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Normalise query mappings for deterministic comparisons."""

    return tuple(sorted((key, tuple(values)) for key, values in mapping.items()))


if _normalise(share_mapping) != _normalise(query_params_initial):
    _set_query_params(share_mapping)

share_url = "?" + urlencode(
    [(key, value) for key, values in share_mapping.items() for value in values]
)
st.text_input(
    "Shareable link",
    value=share_url,
    help="Copy this URL to revisit the dashboard with the same filters and selections.",
)
