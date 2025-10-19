# Idiot Index Dashboard - Copilot Instructions

## Architecture Overview

This is a **production-ready Streamlit app** that computes the "Idiot Index" (Gross Output ÷ Materials Cost) for U.S. industries using government data sources. The app follows a clean **pipeline pattern** with comprehensive error handling and validation:

1. **Data Sources** (`src/sources/`) - API clients for BEA and Census ASM with retry logic
2. **Normalization** (`src/normalize.py`) - Column mapping, type coercion, and schema validation
3. **Metrics** (`src/metrics.py`) - Core business logic for ratio calculations with defensive programming
4. **Presentation** (`app.py`) - Streamlit UI with caching, validation, and interactive Plotly charts

## Key Patterns & Conventions

### Data Flow Pattern
```python
df_raw → validate_schema() → normalize_columns() → compute_metrics() → format_for_display() → Streamlit UI
```

### Column Schema (Normalized)
All data sources must map to: `industry_code`, `industry_name`, `year`, `gross_output`, `materials_cost`, `intermediate_inputs`, `value_added`, `source`

### API Client Design
- Each data source in `src/sources/` is **isolated** - when APIs change, fix one file
- Use `safe_get_json()` from `utils.py` for consistent error handling with retry logic
- Always include clear error messages about API endpoint changes (see BEA example)
- Census ASM uses different variable names (RCPTOT→gross_output, CSTMTOT→materials_cost)

### Streamlit Caching Strategy
- `@st.cache_data` on sample data loading only - API calls are NOT cached to allow fresh data
- Use `show_spinner=False` for sample data to avoid UI clutter

### Error Handling Philosophy
- **Graceful degradation** - show error in sidebar but don't crash
- **Offline-first** - sample data always works without APIs
- **Comprehensive validation** at all pipeline stages
- API failures store error message but continue with sidebar feedback

## Development Workflows

### Running the App
```bash
streamlit run app.py
# Alternative port: streamlit run app.py --server.port 8502
```

### Adding New Data Sources
1. Create new module in `src/sources/` (follow `census_asm.py` pattern)
2. Map API response to normalized column schema in `normalize.py`
3. Add source option to `data_mode` selectbox in `app.py`
4. Include error handling and clear API documentation comments

### Environment Configuration
- Uses `.env` file loaded via `python-dotenv` in `src/config.py`
- API keys also configurable at runtime via Streamlit sidebar
- `DEFAULT_YEAR = 2021` in config - adjust for different data availability
- Configuration validation with environment-aware warnings

### Dependencies & Data Files
- **Core**: streamlit, pandas, requests, python-dotenv, plotly
- **Sample data**: `data/sample_industries.csv` - mix of BEA/ASM demo data
- **NAICS mapping**: `assets/naics_map.csv` - industry code to friendly name mapping

## Critical Implementation Details

### Metric Calculations (`src/metrics.py`)
- **Idiot Index**: `gross_output / materials_cost` (falls back to `intermediate_inputs`)
- **Value Added**: Uses provided value OR computes as `gross_output - intermediate_inputs`
- **Defensive programming**: Replace inf/-inf with `pd.NA` to prevent UI crashes
- **Validation**: Ensures gross_output exists before calculations

### Data Normalization (`src/normalize.py`)
- **Case insensitive** column mapping via `.lower()`
- **Type coercion**: Custom `coerce_numeric()` handles dirty API data
- **Required vs Optional**: Ensures all expected columns exist (adds `None` if missing)
- **Schema validation**: Checks for required columns before processing

### API Integration Notes
- **BEA**: Complete implementation using GDPbyIndustry Tables 1 & 2
- **Census ASM**: Working implementation but endpoints evolve (check api.census.gov)
- **Corporate networks**: Upload CSV bypass for proxy/firewall issues
- **HTTP resilience**: Retry logic with exponential backoff and error differentiation

## File Upload Schema
When adding CSV upload support, expect:
```csv
industry_code,industry_name,year,gross_output,materials_cost,intermediate_inputs,value_added,source
```
Minimum required: `industry_code`, `industry_name`, `year`, `gross_output` + (`materials_cost` OR `intermediate_inputs`)

## ExecPlans Integration
For complex features, follow `.agent/AGENTS.md` guidance - use ExecPlans for multi-file changes affecting the data pipeline or adding new data sources.
