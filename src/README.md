# Source Code Layout

The `src/` tree follows a layered architecture so application logic, integrations, and user interfaces remain decoupled:

- `application/` – orchestrates domain workflows including Idiot Index evaluation and scenario planning.
- `adapters/` – external data connectors (BEA, Census, local files) plus caching utilities.
- `core/` – shared domain models, analytics helpers, and security utilities.
- `infrastructure/` – observability, persistence, configuration loading, and runtime services.
- `interfaces/` – public-facing entry points (Streamlit UI, CLI facades, FastAPI-compatible surfaces).
- `agents/` – agent-safe wrappers exposing curated tool metadata and dataclass schemas.
- `ui/` – Streamlit component helpers and view logic reused by the main app.
- Root modules (e.g., `config.py`, `metrics.py`) provide lightweight glue used across layers.

Refer to [`docs/handbook/ARCHITECTURE.md`](../docs/handbook/ARCHITECTURE.md) for sequence diagrams and deeper explanations of the boundaries between packages.
