import io
import pandas as pd
import streamlit as st
import plotly.express as px
from src.config import BEA_API_KEY, CENSUS_API_KEY, DEFAULT_YEAR
from src.normalize import normalize_columns
from src.metrics import compute_metrics, format_for_display
from src.security import SecurityUtils

# TODO - Add comprehensive error handling for Streamlit app initialization failures
# TODO - Implement user session management for better state handling across page refreshes
# TODO - Add loading states and progress indicators for long-running operations

st.set_page_config(page_title="Idiot Index – Industry Dashboard", layout="wide")

st.title("Idiot Index – Industry Dashboard")
st.caption("Idiot Index = Gross Output ÷ Cost of Materials (or Intermediate Inputs). Use as a red flag, not a religion.")

# Sidebar – data source and keys
st.sidebar.header("Data")
data_mode = st.sidebar.selectbox("Choose data source",
                                 ["Sample (offline)", "Upload CSV", "Census ASM (Manufacturing)", "BEA (Economy-wide)"])

year = st.sidebar.number_input("Year", min_value=1997, max_value=2100, value=DEFAULT_YEAR, step=1)
bea_key = st.sidebar.text_input("BEA API Key", value=BEA_API_KEY, type="password")
census_key = st.sidebar.text_input("Census API Key", value=CENSUS_API_KEY, type="password")

# Validate inputs with security checks
year_valid, year_clean, year_msg = SecurityUtils.validate_year(year)
if not year_valid:
    st.sidebar.error(year_msg)
    st.stop()

if data_mode in ["Census ASM (Manufacturing)", "BEA (Economy-wide)"]:
    if data_mode == "Census ASM (Manufacturing)":
        key_valid, key_msg = SecurityUtils.validate_api_key(census_key, "Census")
        if not key_valid:
            st.sidebar.error(key_msg)
            st.stop()
    elif data_mode == "BEA (Economy-wide)":
        key_valid, key_msg = SecurityUtils.validate_api_key(bea_key, "BEA")
        if not key_valid:
            st.sidebar.error(key_msg)
            st.stop()

# TODO - Add input validation for data_mode selection to prevent invalid states
# TODO - Implement API key rotation and refresh mechanisms for long-running sessions
# TODO - Add data source health checks to warn users about API availability issues

@st.cache_data(show_spinner=False)
def load_sample():
    return pd.read_csv("data/sample_industries.csv")

def try_fetch_census(year:int, api_key:str) -> pd.DataFrame:
    from src.sources.census_asm import fetch_asm_manufacturing
    return fetch_asm_manufacturing(api_key=api_key, year=year)

def try_fetch_bea(year:int, api_key:str) -> pd.DataFrame:
    from src.sources.bea import fetch_go_ii_by_industry
    return fetch_go_ii_by_industry(api_key=api_key, year=year)

df_raw = None
error = None

# TODO - Implement retry logic with exponential backoff for API failures
# TODO - Add data quality validation after loading to ensure data integrity
# TODO - Implement data source fallback mechanisms when primary sources fail

if data_mode == "Sample (offline)":
    df_raw = load_sample()
elif data_mode == "Upload CSV":
    up = st.sidebar.file_uploader("Upload CSV", type=["csv"])
    if up:
        try:
            # Security validation for uploaded file
            file_valid, file_msg = SecurityUtils.validate_file_upload(up.name, SecurityUtils.MAX_FILE_SIZE_MB)
            if not file_valid:
                st.sidebar.error(f"File security check failed: {file_msg}")
                df_raw = None
            else:
                temp_df = pd.read_csv(up)

                # Validate CSV content for security
                content_valid, content_msg = SecurityUtils.validate_csv_content(temp_df)
                if not content_valid:
                    st.sidebar.error(f"CSV content security check failed: {content_msg}")
                    df_raw = None
                else:
                    # Validate CSV schema
                    required_cols = ['industry_code', 'industry_name', 'year']
                    optional_cols = ['gross_output', 'materials_cost', 'intermediate_inputs', 'value_added', 'source']

                    df_columns = [col.lower().strip() for col in temp_df.columns]
                    missing_required = [col for col in required_cols if col not in df_columns]

                    if missing_required:
                        st.sidebar.error(f"CSV missing required columns: {', '.join(missing_required)}")
                        st.sidebar.info("Required columns: industry_code, industry_name, year")
                        st.sidebar.info("Optional columns: gross_output, materials_cost, intermediate_inputs, value_added, source")
                        df_raw = None
                    else:
                        df_raw = temp_df
                        st.sidebar.success("CSV loaded and validated.")
        except Exception as e:
            st.sidebar.error(f"Error reading CSV: {e}")
            df_raw = None
    else:
        st.sidebar.info("Upload a CSV to proceed.")
        df_raw = None

# TODO - Add support for Excel file uploads (.xlsx, .xls) with proper validation
# TODO - Implement CSV preview functionality before full processing
# TODO - Add data type inference and validation for uploaded columns
elif data_mode == "Census ASM (Manufacturing)":
    try:
        df_raw = try_fetch_census(year=year_clean, api_key=census_key.strip())
        st.sidebar.success(f"ASM fetched for {year_clean}.")
    except Exception as e:
        error = str(e)
        st.sidebar.error(f"ASM fetch failed: {e}")
elif data_mode == "BEA (Economy-wide)":
    try:
        df_raw = try_fetch_bea(year=year_clean, api_key=bea_key.strip())
        st.sidebar.success(f"BEA fetched for {year_clean}.")
    except Exception as e:
        error = str(e)
        st.sidebar.error(f"BEA fetch failed: {e}")

if df_raw is None:
    st.stop()

# Normalize, compute
assert df_raw is not None  # Type hint for linter
df_norm = normalize_columns(df_raw)
df = compute_metrics(df_norm)
df = format_for_display(df)

# TODO - Add data quality metrics and validation after processing
# TODO - Implement data export functionality for processed datasets
# TODO - Add data versioning and change tracking for user uploads

# Filters
left, right = st.columns([2,1])
with left:
    st.subheader("Industry Table")
    q = st.text_input("Filter by name or code", "")
    # Sanitize user input
    q_sanitized = SecurityUtils.sanitize_string_input(q.strip())
    df_view = df.copy()
    if q_sanitized:
        ql = q_sanitized.lower()
        df_view = df_view[df_view['industry_name'].str.lower().str.contains(ql) |
                          df_view['industry_code'].str.lower().str.contains(ql)]
    st.dataframe(df_view.sort_values(["year","idiot_index"], ascending=[False, False]), use_container_width=True)

# TODO - Add advanced filtering options (date ranges, value ranges, industry categories)
# TODO - Implement pagination for large datasets to improve performance
# TODO - Add column sorting and visibility controls for the data table

with right:
    st.subheader("Summary")
    st.metric("Rows", len(df))
    st.metric("Distinct industries", df["industry_code"].nunique())
    st.metric("Year (mode)", int(df["year"].mode().iloc[0]) if not df["year"].isna().all() else 0)
    st.write("Top by Idiot Index")
    top5 = df.sort_values("idiot_index", ascending=False).head(5)[["industry_name","idiot_index","value_added_pct"]]
    st.dataframe(top5, use_container_width=True)

# Chart – simple bar of idiot index (top N)
st.subheader("Top Industries by Idiot Index")
topn = st.slider("How many to show", min_value=5, max_value=50, value=15, step=5)
chart_df = df.sort_values("idiot_index", ascending=False).head(topn)
fig = px.bar(
    chart_df,
    x="idiot_index",
    y="industry_name",
    orientation='h',
    title=f"Top {topn} Industries by Idiot Index",
    labels={"idiot_index": "Idiot Index", "industry_name": "Industry"},
    color="idiot_index",
    color_continuous_scale="RdYlGn_r"  # Red for high values, green for low
)
fig.update_layout(
    xaxis_title="Idiot Index (Gross Output ÷ Materials Cost)",
    yaxis_title="Industry",
    height=max(400, len(chart_df) * 25)  # Dynamic height based on number of bars
)
st.plotly_chart(fig, use_container_width=True)

# TODO - Add interactive chart features (zoom, pan, selection)
# TODO - Implement multiple chart types (scatter plots, heatmaps, trend lines)
# TODO - Add chart export functionality (PNG, SVG, PDF)

# Deep dive select
st.subheader("Deep Dive")
choices = df["industry_name"].tolist()
sel = st.selectbox("Select an industry", choices)
row = df[df["industry_name"] == sel].head(1)
if not row.empty:
    r = row.iloc[0]
    year_display = int(r['year']) if pd.notna(r['year']) else 'N/A'
    st.write(f"**{r['industry_name']}** — Code: `{r['industry_code']}` — Year: {year_display}")
    c1, c2, c3 = st.columns(3)

    # Safely display metrics with fallbacks
    idiot_index = r['idiot_index'] if pd.notna(r['idiot_index']) else None
    c1.metric("Idiot Index", f"{idiot_index:.2f}" if idiot_index is not None else "N/A")

    value_added_pct = r['value_added_pct'] if pd.notna(r['value_added_pct']) else None
    c2.metric("Value-Added %", f"{value_added_pct:.1f}%" if value_added_pct is not None else "N/A")

    materials_share_pct = r['materials_share_pct'] if pd.notna(r['materials_share_pct']) else None
    c3.metric("Materials Share %", f"{materials_share_pct:.1f}%" if materials_share_pct is not None else "N/A")

    st.write("**Raw figures (thousand $ assumed for demo):**")
    cols = st.columns(4)

    gross_output = r['gross_output'] if pd.notna(r['gross_output']) else None
    cols[0].metric("Gross Output", f"{gross_output:,.0f}" if gross_output is not None else "—")

    materials_cost = r['materials_cost'] if pd.notna(r['materials_cost']) else None
    cols[1].metric("Materials Cost", f"{materials_cost:,.0f}" if materials_cost is not None else "—")

    intermediate_inputs = r['intermediate_inputs'] if pd.notna(r['intermediate_inputs']) else None
    cols[2].metric("Intermediate Inputs", f"{intermediate_inputs:,.0f}" if intermediate_inputs is not None else "—")

    value_added = r['value_added'] if pd.notna(r['value_added']) else None
    cols[3].metric("Value Added", f"{value_added:,.0f}" if value_added is not None else "—")

    source_display = r['source'] if pd.notna(r['source']) else 'Unknown'
    st.caption(f"Source: {source_display}")
else:
    st.error("No data available for selected industry")

# TODO - Add industry comparison functionality to compare multiple industries side-by-side
# TODO - Implement historical trend analysis for selected industries over time
# TODO - Add industry benchmarking against industry averages or percentiles

# Download
def to_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode()

st.download_button("Download Results (CSV)", data=to_csv_bytes(df), file_name="idiot_index_results.csv", mime="text/csv")

# TODO - Add multiple export formats (Excel, JSON, PDF reports)
# TODO - Implement filtered data export based on current view
# TODO - Add data sharing functionality with unique URLs or embed codes
