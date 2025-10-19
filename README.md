# Idiot Index – U.S. Industry Dashboard

A pragmatic Streamlit app to estimate and visualize the so‑called **“Idiot Index”** across industries:

> **Idiot Index = Gross Output ÷ Cost of Materials (or Intermediate Inputs)**

This isn’t an academic metric; it’s a blunt heuristic popularized in engineering circles to spot bloated cost structures. Use it as a red‑flag indicator, then dig deeper.

---

## What this app does

- Pulls industry data from **BEA** (Gross Output, Intermediate Inputs, Value Added) and **Census ASM** (Shipments, Cost of Materials, Value Added) when API keys are provided.
- Computes:
  - Idiot Index (Output ÷ Materials / Intermediate Inputs)
  - Value‑Added %
  - Gross‑margin analogs
- Lets you:
  - Compare sectors via sortable tables
  - Drill down by NAICS code with robust error handling
  - Upload your own CSVs with automatic schema validation
  - Export results (CSV)
  - Explore data with interactive Plotly charts
- Works **offline** out of the box via a bundled sample dataset.
- **Robust error handling** with graceful degradation and clear user feedback
- **Input validation** for all user inputs and data sources

> **Blunt reality:** Official APIs evolve. The BEA and ASM endpoints/variables change over time.
> This app isolates API calls so you can fix one file when the feds reshuffle schemas.

---

## Quick start (no keys, offline demo)

```bash
# 1) Create and activate a virtual environment (optional but recommended)
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# 2) Install deps
pip install -r requirements.txt

# 3) Run
streamlit run app.py
```

Open the local URL it prints (usually http://localhost:8501). The app will load the **sample dataset** so you can click around immediately.

## Docker Deployment

For easy deployment and development:

```bash
# Build the Docker image
docker build -t idiot-index-app .

# Run the container
docker run -p 8501:8501 idiot-index-app
```

## Development

Install development dependencies:

```bash
pip install -r requirements-dev.txt
```

Run code quality checks:

```bash
# Unit tests
pytest

# Linting
flake8 src/

# Type checking
mypy src/
```

## API Keys

To access live government data, create a `.env` file:

```bash
BEA_API_KEY=your_bea_api_key_here
CENSUS_API_KEY=your_census_api_key_here
```

Get API keys from:
- [BEA API](https://apps.bea.gov/API/signup/)
- [Census API](https://www.census.gov/data/developers/data-sets.html)

### Configuration reference

The app validates configuration at startup before rendering the UI. Key environment variables:

- `ENVIRONMENT`: `development` (default), `testing`, or `production`.
- `DEFAULT_YEAR`: Initial year selection when the sidebar loads.
- `CACHE_ENABLED`: Enable/disable filesystem caches (`true`/`false`).
- `CACHE_DIR`: Base directory for cache files (defaults to `.cache`).
- `BEA_API_KEY`, `CENSUS_API_KEY`: Required when `ENVIRONMENT=production`.

Launch the app and open the “Configuration summary” expander in the sidebar to review resolved values and warnings.

---

## Using real data (recommended)

1. Get keys:
   - **BEA API Key**: https://apps.bea.gov/API/signup/index.cfm
   - **Census API Key** (ASM): https://api.census.gov/data/key_signup.html
2. Put them in a `.env` file (see `.env.example`) or paste them into the sidebar at runtime.
3. In the app sidebar, choose **Data → “BEA”** for economy‑wide aggregates or **“Census ASM”** for detailed manufacturing NAICS. Fetch, compute, explore.

### Notes on data mappings
- **BEA** exposes **GDP by Industry** and **Input‑Output** datasets. We request **Gross Output** and **Intermediate Inputs** at annual cadence. BEA industry codes are close to NAICS groupings; we ship a simple `assets/naics_map.csv` for friendly names and a lightweight mapping.
- **Census ASM** provides **Value of Shipments (RCPTOT)**, **Cost of Materials (CSTMTOT)**, **Value Added (VALADD)** for manufacturing (NAICS 31‑33). Data are annual and sometimes suppressed at very fine granularity.

If an API call fails or a series isn’t available, the app will surface a terse error and gracefully fall back.

---

## Bring your own data

Want to avoid APIs entirely or use proprietary data? Go to **Data → “Upload CSV”** and drop in a file with columns:

```
industry_code,industry_name,year,gross_output,materials_cost,intermediate_inputs,value_added,source
```
At minimum, provide: `industry_code`, `industry_name`, `year`, and either:
- `gross_output` + `materials_cost`, **or**
- `gross_output` + `intermediate_inputs` (used as materials proxy).

---

## Export

Use the "Download Results (CSV)" button to export all computed metrics.

---

## Recent Improvements

This application has been significantly enhanced with production-ready features:

### **Robustness & Error Handling**
- **Comprehensive input validation** for all user inputs and data sources
- **Graceful error handling** with clear user feedback instead of crashes
- **API resilience** with retry logic and detailed error differentiation
- **Data validation** at multiple pipeline stages to prevent invalid computations

### **Enhanced User Experience**
- **Interactive Plotly charts** replacing basic visualizations
- **CSV upload validation** with clear schema requirements and error messages
- **Improved deep-dive views** with safe handling of missing data
- **Better sidebar feedback** for data loading and error states

### **Code Quality & Security**
- **Typed configuration loader** with validation and sidebar warnings
- **Deterministic caching** with TTL management and per-test isolation
- **Hardened security utilities** covering uploads, strings, and API keys
- **Retriable HTTP client** with typed errors and exponential backoff
- **Expanded automated tests** spanning config, metrics, normalization, and API clients

### **API Integration**
- **Complete BEA API implementation** (previously stubbed)
- **Enhanced Census ASM client** with better error handling
- **HTTP client improvements** with retry logic and timeout handling

---

## Limitations (don't kid yourself)

- This is a **ratio**, not gospel. High values can reflect IP, safety, regulation, or capital intensity—not “idiocy.”
- Different sources define outputs/inputs differently; read their docs. We annotate the source on each row.
- Retail and services accounting can be weird in national accounts (e.g., margins vs merchandise). Interpret with care.

---

## Project layout

```
.
├── app.py
├── requirements.txt
├── .env.example
├── LICENSE
├── README.md
├── assets/
│   └── naics_map.csv
├── data/
│   └── sample_industries.csv
├── src/
│   ├── __init__.py
│   ├── cache.py
│   ├── config.py
│   ├── metrics.py
│   ├── normalize.py
│   ├── rate_limiter.py
│   ├── security.py
│   ├── types.py
│   ├── utils.py
│   └── sources/
│       ├── bea.py
│       └── census_asm.py
└── tests/
    ├── test_config.py
    ├── test_core.py
    └── test_security.py
```

---

## License

MIT. See `LICENSE`.

---

## Enterprise Features

This application implements production-grade features for reliability, performance, and maintainability:

### 🚀 Performance & Caching

- **File-based caches** for API responses and metric computations with configurable TTLs
- **Atomic writes** to prevent partial cache files and reduce corruption risk
- **Cache statistics helper** for inspecting cache size and entry counts during diagnostics

### 🔒 Security & Rate Limiting

- **API rate limiting** via configurable token buckets per provider
- **Environment-aware defaults** for stricter production limits
- **Upload hygiene** with filename sanitization, file-size enforcement, and CSV content scans
- **API key validation** with length checks and character whitelists
- **String sanitization** to strip dangerous HTML/script patterns
- **Year and numeric validation** before expensive computations

### 📊 Observability

- **Rotating file and console logs** via `src/logging_config.py`
- **API call logging hooks** to trace outbound requests and timings

### ⚙️ Configuration Management

- **Environment Detection**: Automatic production/development/test environment handling
- **Dynamic Settings**: Configurable cache TTL, logging levels, and API limits via environment variables
- **Validation on Startup**: Comprehensive configuration validation with helpful error messages
- **Security-Conscious**: No sensitive data exposure in logs or configuration summaries

### 🏗️ Infrastructure & DevOps

- **Dockerfile** for reproducible local or cloud deployments
- **Development tooling** pinned in `requirements-dev.txt` (black, flake8, mypy, pytest-cov)
- **Type hints** and linting integrated into the codebase

### 🧪 Quality Assurance

- **Pytest suite** covering configuration, normalization, metrics, security, and API clients
- **Mock-based integration tests** for BEA and Census API adapters
- **Type hints** throughout core modules for editor and static analysis support

---

## Architecture Overview

```text
idiot-index-app/
├── app.py                 # Streamlit UI with validation and caching
├── src/
│   ├── cache.py          # Intelligent file-based caching system
│   ├── config.py         # Environment-aware configuration management
│   ├── logging_config.py # Structured logging with performance tracking
│   ├── metrics.py        # Business logic with defensive programming
│   ├── normalize.py      # Data validation and schema normalization
│   ├── rate_limiter.py   # Token bucket rate limiting
│   ├── sources/          # Isolated API client modules
│   │   ├── bea.py       # BEA GDPbyIndustry API client
│   │   └── census_asm.py # Census ASM API client
│   └── utils.py          # HTTP client with retry logic
├── tests/                # Comprehensive test suite
├── Dockerfile           # Containerization with health checks
├── .dockerignore       # Docker build optimization
├── .github/workflows/  # CI/CD pipeline
├── requirements.txt    # Production dependencies
└── requirements-dev.txt # Development tooling
```

### Data Flow Pipeline

```text
User Input → Validation → Caching Check → API Call (Rate Limited) →
Data Processing → Metrics Computation → Caching Storage →
UI Rendering → Logging & Monitoring
```

---

## Configuration Options

Configure the application via environment variables:

```bash
# Environment
ENVIRONMENT=production  # development | production | testing

# API Keys
BEA_API_KEY=your_key
CENSUS_API_KEY=your_key

# Performance
CACHE_ENABLED=true
CACHE_TTL_API=3600      # API cache TTL in seconds
CACHE_TTL_COMPUTATION=1800  # Computation cache TTL

# Rate Limiting (requests per minute)
BEA_RATE_LIMIT=10       # Production: 10, Development: 30
CENSUS_RATE_LIMIT=20    # Production: 20, Development: 50

# Logging
LOG_LEVEL=INFO          # DEBUG | INFO | WARNING | ERROR | CRITICAL

# Data Validation
MAX_CSV_SIZE_MB=50
DEFAULT_YEAR=2021
```

---

## API Integration Details

### BEA (Bureau of Economic Analysis)

- **Dataset**: GDPbyIndustry
- **Tables**: Gross Output (Table 1), Intermediate Inputs (Table 2)
- **Rate Limit**: 10 requests/minute (production), 30/minute (development)
- **Cache TTL**: 1 hour
- **Data Range**: 1997-2024

### Census ASM (Annual Survey of Manufactures)

- **Dataset**: Manufacturing statistics
- **Variables**: RCPTOT (shipments), CSTMTOT (materials), VALADD (value added)
- **Rate Limit**: 20 requests/minute (production), 50/minute (development)
- **Cache TTL**: 1 hour
- **Data Range**: 1997-2023

---

## Monitoring & Logs

The application generates structured logs for monitoring:

```text
logs/app.log  # Rotating file logs (DEBUG level)
console       # Console logs (INFO level)
```

Log entries include:

- API call success/failure with timing
- Cache hits/misses
- Performance metrics
- Error details with context
- Configuration validation results

---

## Troubleshooting

- **Port in use**: `streamlit run app.py --server.port 8502`
- **SSL issues** behind proxies: set `REQUESTS_CA_BUNDLE` or disable SSL verification in a pinch (not recommended).
- **Corporate networks** blocking APIs: use the **Upload CSV** path.

---

## Why this exists

You asked for a no‑nonsense tool to interrogate cost structure by industry. This gives you the lever:
pull fresh official stats, compute the ratio, and then challenge the assumptions.

