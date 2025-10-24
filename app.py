"""Streamlit dashboard for exploring Idiot Index metrics and narratives.

The app composes application services with Streamlit components to fetch data,
compute metrics, and render an adaptive user interface. The module also
exposes a handful of utility functions that are reused by tests to mock API
calls and CSV uploads.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Mapping, Optional, Sequence, Tuple

import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit.runtime.uploaded_file_manager import UploadedFile
from urllib.parse import urlencode

from src.application import DataSource, evaluate_idiot_index
from src.core import FilePolicy, SecurityUtils, get_config_summary
from src.interfaces.streamlit.bootstrap import (
    BootstrapError,
    get_bootstrap_state,
)
from src.interfaces.streamlit.components import (
    build_data_story,
    load_custom_styles,
    render_deep_dive,
    render_download_panel,
    render_insight_tabs,
    render_page_header,
    render_sidebar,
    render_signal_bar,
    render_state_banner,
)
from src.interfaces.streamlit.helpers import (
    build_comparison_table,
    calculate_benchmark,
    decode_query_params,
    encode_query_params,
    prepare_download_artifacts,
    prepare_trend_data,
)

@st.cache_data(show_spinner=False)
def load_sample() -> pd.DataFrame:
    """Return the bundled sample dataset for offline exploration."""

    return pd.read_csv("data/sample_industries.csv")


def process_uploaded_file(
    uploaded_file: UploadedFile, *, policy: FilePolicy
) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
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


st.set_page_config(page_title="Idiot Index – Industry Dashboard", layout="wide")
load_custom_styles()

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

for warning in bootstrap_state.warnings:
    st.sidebar.warning(warning)

with st.sidebar.expander("Configuration summary", expanded=False):
    st.json(get_config_summary(APP_CONFIG))

query_params_initial = decode_query_params(st.experimental_get_query_params())


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
    "Sample (offline)",
    "Upload CSV",
    "Census ASM (Manufacturing)",
    "BEA (Economy-wide)",
]
mode_raw = _last_value("mode")
if mode_raw:
    slug_lookup = {option.lower().replace(" ", "-"): option for option in sidebar_modes}
    resolved_mode = slug_lookup.get(mode_raw)
    if resolved_mode:
        st.session_state["Source"] = resolved_mode

year_bounds = sidebar_context.year_bounds

sidebar_state = render_sidebar(
    default_year=year_override,
    year_bounds=year_bounds,
    bea_key=APP_CONFIG.bea_api_key or "",
    census_key=APP_CONFIG.census_api_key or "",
    security_utils=SecurityUtils,
)

if sidebar_state.halt or sidebar_state.year_clean is None:
    st.stop()

data_mode = sidebar_state.data_mode
data_mode_slug = data_mode.lower().replace(" ", "-")
year_clean = sidebar_state.year_clean
bea_key = sidebar_state.bea_key.strip()
census_key = sidebar_state.census_key.strip()
uploaded_file = sidebar_state.uploaded_file

mode_to_source = {
    "Sample (offline)": DataSource.SAMPLE,
    "Census ASM (Manufacturing)": DataSource.CENSUS,
    "BEA (Economy-wide)": DataSource.BEA,
}

service_source = mode_to_source.get(data_mode, DataSource.SAMPLE)
dataframe_override: Optional[pd.DataFrame] = None
service_config = APP_CONFIG
error: Optional[str] = None

if data_mode == "Upload CSV":
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
if data_mode == "Upload CSV":
    source_for_service = DataSource.SAMPLE
else:
    source_for_service = service_source

try:
    summary = evaluate_idiot_index(
        year=year_clean,
        source=source_for_service,
        dataframe=dataframe_override,
        config=service_config,
        sample_loader=load_sample,
        top_n=50,
    )
    if data_mode == "Census ASM (Manufacturing)":
        st.sidebar.success(f"ASM fetched for {year_clean}.")
    elif data_mode == "BEA (Economy-wide)":
        st.sidebar.success(f"BEA fetched for {year_clean}.")
except Exception as exc:  # pylint: disable=broad-except
    error = str(exc)
    st.sidebar.error(f"{data_mode.split(' (')[0]} fetch failed: {exc}")
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

focus_mode = render_page_header(
    title="Idiot Index Intelligence Studio",
    subtitle="Sense, compare, and narrate the balance between gross output and materials cost.",
    meta={
        "Source": data_mode,
        "Year": str(year_clean),
        "Visible": f"{len(df_filtered):,} / {len(df_display):,}",
    },
    focus_mode=st.session_state["focus_mode"],
)

st.session_state["focus_mode"] = focus_mode

if focus_mode:
    render_state_banner(
        "Focus mode is active. Peripheral panels stay within reach, but the deep dive takes center stage."
    )
else:
    if data_mode == "Upload CSV":
        render_state_banner(
            "Working from your uploaded dataset. Everything stays local to this session."
        )
    elif error:
        render_state_banner(
            "We hit a retrieval snag earlier. Showing the most recent successful data in the meantime."
        )
    else:
        render_state_banner(
            f"{len(df_filtered):,} industries tuned · adjust the filters to tighten the narrative."
        )

if not focus_mode:
    render_signal_bar(df_filtered)

pulse_tab, industries_tab, signals_tab = render_insight_tabs(
    ["Pulse", "Industries", "Top Signals"]
)

with pulse_tab:
    st.subheader("Pulse overview")
    cols = st.columns(3)
    with cols[0]:
        st.metric("Rows", len(df_filtered))
    with cols[1]:
        st.metric("Distinct industries", df_filtered["industry_code"].nunique())
    with cols[2]:
        dominant_year = (
            int(df_filtered["year"].mode().iloc[0])
            if not df_filtered["year"].isna().all()
            else "N/A"
        )
        st.metric("Modal year", dominant_year)

    st.markdown("---")
    st.write("Top by Idiot Index")
    top5 = (
        df_filtered.sort_values("idiot_index", ascending=False)
        .head(5)
        .loc[:, ["industry_name", "idiot_index", "value_added_pct"]]
    )
    st.dataframe(top5, use_container_width=True)

with industries_tab:
    st.subheader("Industry explorer")
    search_value = st.text_input(
        "Search by name or code",
        value=current_query_raw,
        placeholder="Start typing to focus the table…",
        key="search_query",
    )
    sanitized = SecurityUtils.sanitize_string_input(search_value.strip())
    df_view = df_display.copy()
    if sanitized:
        query_lower = sanitized.lower()
        df_view = df_view[
            df_view["industry_name"].str.lower().str.contains(query_lower)
            | df_view["industry_code"].str.lower().str.contains(query_lower)
        ]
    st.dataframe(
        df_view.sort_values(["year", "idiot_index"], ascending=[False, False]),
        use_container_width=True,
    )

with signals_tab:
    st.subheader("Momentum signals")
    topn = st.slider(
        "How many industries should headline the chart?",
        min_value=5,
        max_value=50,
        value=15,
        step=5,
    )
    chart_df = df_view.sort_values("idiot_index", ascending=False).head(topn)
    fig = px.bar(
        chart_df,
        x="idiot_index",
        y="industry_name",
        orientation="h",
        title=f"Top {topn} Industries by Idiot Index",
        labels={"idiot_index": "Idiot Index", "industry_name": "Industry"},
        color="idiot_index",
        color_continuous_scale="RdYlGn_r",
    )
    fig.update_layout(
        xaxis_title="Idiot Index (Gross Output ÷ Materials Cost)",
        yaxis_title="Industry",
        height=max(400, len(chart_df) * 25),
    )
    st.plotly_chart(fig, use_container_width=True)

st.subheader("Deep dive")
code_lookup = dict(zip(df_filtered["industry_code"], df_filtered["industry_name"]))
choices: Sequence[str] = list(dict.fromkeys(df_filtered["industry_code"]))
selected_code: Optional[str] = None
if not choices:
    st.warning("No industries match the current filters.")
else:
    default_code = st.session_state.get("industry_selection_code")
    if default_code not in choices:
        default_code = choices[0]
        st.session_state["industry_selection_code"] = default_code
    selected_code = st.selectbox(
        "Select an industry",
        choices,
        index=choices.index(default_code) if default_code in choices else 0,
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
        render_deep_dive(row=current_row, story=story, focus_mode=focus_mode)

st.markdown("---")
st.subheader("Comparisons & benchmarking")

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
    st.info("Select one or more industries to compare their Idiot Index and value-added mix.")
else:
    st.dataframe(comparison_table, use_container_width=True)

trend_selection = comparison_selection or ([selected_code] if selected_code else [])
trend_data = prepare_trend_data(df_display, trend_selection)
if trend_data.empty or trend_data["year"].nunique() <= 1:
    st.caption("Add additional years to see historical trendlines for the selected industries.")
else:
    trend_fig = px.line(
        trend_data,
        x="year",
        y="idiot_index",
        color="industry_name",
        title="Historical Idiot Index trend",
    )
    trend_fig.update_layout(xaxis_title="Year", yaxis_title="Idiot Index")
    st.plotly_chart(trend_fig, use_container_width=True)

benchmark_stats = calculate_benchmark(df_display, selected_code)
metric_cols = st.columns(3)

idiot_avg = benchmark_stats.get("idiot_index_avg")
idiot_delta = benchmark_stats.get("idiot_index_delta")
with metric_cols[0]:
    st.metric(
        "Dataset average Idiot Index",
        f"{idiot_avg:.2f}" if idiot_avg is not None and pd.notna(idiot_avg) else "—",
        delta=(
            f"{idiot_delta:+.2f}"
            if idiot_delta is not None and pd.notna(idiot_delta)
            else None
        ),
    )

value_avg = benchmark_stats.get("value_added_pct_avg")
value_delta = benchmark_stats.get("value_added_pct_delta")
with metric_cols[1]:
    st.metric(
        "Dataset average Value-Added %",
        f"{value_avg:.1f}%" if value_avg is not None and pd.notna(value_avg) else "—",
        delta=(
            f"{value_delta:+.1f}%"
            if value_delta is not None and pd.notna(value_delta)
            else None
        ),
    )

materials_avg = benchmark_stats.get("materials_share_pct_avg")
materials_delta = benchmark_stats.get("materials_share_pct_delta")
with metric_cols[2]:
    st.metric(
        "Dataset average Materials Share %",
        f"{materials_avg:.1f}%"
        if materials_avg is not None and pd.notna(materials_avg)
        else "—",
        delta=(
            f"{materials_delta:+.1f}%"
            if materials_delta is not None and pd.notna(materials_delta)
            else None
        ),
    )

download_artifacts = prepare_download_artifacts(
    df_full=df_display,
    df_filtered=df_filtered,
    base_name="idiot_index_results",
)
render_download_panel(download_artifacts)

share_mapping = encode_query_params(
    focus="true" if focus_mode else "false",
    search=current_query_raw or None,
    industry=selected_code if selected_code else None,
    compare=comparison_selection if comparison_selection else None,
    year=str(year_clean) if year_clean is not None else None,
    mode=data_mode_slug,
)

def _normalise(mapping: Mapping[str, list[str]]) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Normalise query mappings for deterministic comparisons."""

    return tuple(sorted((key, tuple(values)) for key, values in mapping.items()))

if _normalise(share_mapping) != _normalise(query_params_initial):
    st.experimental_set_query_params(**share_mapping)

share_url = "?" + urlencode(
    [(key, value) for key, values in share_mapping.items() for value in values]
)
st.text_input(
    "Shareable link",
    value=share_url,
    help="Copy this URL to revisit the dashboard with the same filters and selections.",
)
