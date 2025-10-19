import io
from typing import Optional, Tuple

import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit.runtime.uploaded_file_manager import UploadedFile

from src.config import BEA_API_KEY, CENSUS_API_KEY, DEFAULT_YEAR
from src.metrics import compute_metrics, format_for_display
from src.normalize import normalize_columns
from src.security import SecurityUtils
from src.ui.components import (
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

# TODO - Add comprehensive error handling for Streamlit app initialization failures
# TODO - Implement user session management for better state handling across page refreshes
# TODO - Add loading states and progress indicators for long-running operations


@st.cache_data(show_spinner=False)
def load_sample() -> pd.DataFrame:
    return pd.read_csv("data/sample_industries.csv")


def try_fetch_census(year: int, api_key: str) -> pd.DataFrame:
    from src.sources.census_asm import fetch_asm_manufacturing

    return fetch_asm_manufacturing(api_key=api_key, year=year)


def try_fetch_bea(year: int, api_key: str) -> pd.DataFrame:
    from src.sources.bea import fetch_go_ii_by_industry

    return fetch_go_ii_by_industry(api_key=api_key, year=year)


def process_uploaded_file(uploaded_file: UploadedFile) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """Validate and materialize a CSV upload into a dataframe."""

    try:
        file_valid, file_msg = SecurityUtils.validate_file_upload(
            uploaded_file.name, SecurityUtils.MAX_FILE_SIZE_MB
        )
        if not file_valid:
            return None, f"File security check failed: {file_msg}"

        temp_df = pd.read_csv(uploaded_file)

        content_valid, content_msg = SecurityUtils.validate_csv_content(temp_df)
        if not content_valid:
            return None, f"CSV content security check failed: {content_msg}"

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
    except Exception as exc:  # pylint: disable=broad-except
        return None, f"Error reading CSV: {exc}"


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode()


st.set_page_config(page_title="Idiot Index – Industry Dashboard", layout="wide")
load_custom_styles()

if "focus_mode" not in st.session_state:
    st.session_state["focus_mode"] = False
if "search_query" not in st.session_state:
    st.session_state["search_query"] = ""
if "industry_selection" not in st.session_state:
    st.session_state["industry_selection"] = None

sidebar_state = render_sidebar(
    default_year=DEFAULT_YEAR,
    year_bounds=(1997, 2100),
    bea_key=BEA_API_KEY,
    census_key=CENSUS_API_KEY,
    security_utils=SecurityUtils,
)

if sidebar_state.halt or sidebar_state.year_clean is None:
    st.stop()

data_mode = sidebar_state.data_mode
year_clean = sidebar_state.year_clean
bea_key = sidebar_state.bea_key.strip()
census_key = sidebar_state.census_key.strip()
uploaded_file = sidebar_state.uploaded_file

df_raw: Optional[pd.DataFrame] = None
error: Optional[str] = None

if data_mode == "Sample (offline)":
    df_raw = load_sample()
elif data_mode == "Upload CSV":
    if uploaded_file is None:
        st.stop()
    df_raw, error = process_uploaded_file(uploaded_file)
    if error:
        st.sidebar.error(error)
        st.stop()
    st.sidebar.success("CSV loaded and validated.")
elif data_mode == "Census ASM (Manufacturing)":
    try:
        df_raw = try_fetch_census(year=year_clean, api_key=census_key)
        st.sidebar.success(f"ASM fetched for {year_clean}.")
    except Exception as exc:  # pylint: disable=broad-except
        error = str(exc)
        st.sidebar.error(f"ASM fetch failed: {exc}")
elif data_mode == "BEA (Economy-wide)":
    try:
        df_raw = try_fetch_bea(year=year_clean, api_key=bea_key)
        st.sidebar.success(f"BEA fetched for {year_clean}.")
    except Exception as exc:  # pylint: disable=broad-except
        error = str(exc)
        st.sidebar.error(f"BEA fetch failed: {exc}")

if df_raw is None:
    st.stop()

# Normalize, compute
assert df_raw is not None  # Type hint for linter
df_norm = normalize_columns(df_raw)
df = compute_metrics(df_norm)
df = format_for_display(df)

current_query_raw = st.session_state.get("search_query", "")
current_query = SecurityUtils.sanitize_string_input(current_query_raw.strip())

df_filtered = df.copy()
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
        "Visible": f"{len(df_filtered):,} / {len(df):,}",
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
    df_view = df.copy()
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
choices = df_view["industry_name"].tolist()
if not choices:
    st.warning("No industries match the current filters.")
else:
    if (
        st.session_state["industry_selection"] not in choices
        and choices
    ):
        st.session_state["industry_selection"] = choices[0]

    selected = st.selectbox(
        "Select an industry",
        choices,
        index=choices.index(st.session_state["industry_selection"])
        if st.session_state["industry_selection"] in choices
        else 0,
        key="industry_selection",
    )
    row = df_view[df_view["industry_name"] == selected].head(1)
    if row.empty:
        st.error("No data available for the selected industry.")
    else:
        current_row = row.iloc[0]
        story = build_data_story(
            row=current_row,
            filtered_size=len(df_view),
            total_size=len(df),
            filter_query=SecurityUtils.sanitize_string_input(
                st.session_state.get("search_query", "").strip()
            ),
            data_mode=data_mode,
        )
        render_deep_dive(row=current_row, story=story, focus_mode=focus_mode)

render_download_panel(
    file_name="idiot_index_results.csv",
    data=to_csv_bytes(df),
)

# TODO - Add industry comparison functionality to compare multiple industries side-by-side
# TODO - Implement historical trend analysis for selected industries over time
# TODO - Add industry benchmarking against industry averages or percentiles
# TODO - Add multiple export formats (Excel, JSON, PDF reports)
# TODO - Implement filtered data export based on current view
# TODO - Add data sharing functionality with unique URLs or embed codes
