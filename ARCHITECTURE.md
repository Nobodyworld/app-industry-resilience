# Architecture Overview

The Idiot Index application is organised into clear layers to separate domain logic from interfaces and infrastructure concerns.

## Layers

### Core (`src/core/`)
Holds pure domain logic and reusable utilities:
- `config`, `cache`, `metrics`, `normalize`, `security`, `types`, and `utils` encapsulate configuration parsing, caching, metric computation, column normalisation, validation, typed results, and HTTP helpers.
- Exposed collectively through `src/core/__init__.py` for convenient imports and backward compatibility via legacy shims in `src/`.

### Adapters (`src/adapters/`)
External data connectors for BEA and Census ASM APIs. They depend on core services for caching, security, and normalisation. Legacy imports under `src/sources/` re-export the new modules to avoid breaking existing integrations.

### Infrastructure (`src/infrastructure/`)
Cross-cutting concerns such as logging configuration and rate limiting. These modules wrap the Python `logging` ecosystem with redaction and rotation plus thread-safe token buckets.

### Interfaces (`src/interfaces/`)
UI presentation components. The Streamlit implementation lives in `src/interfaces/streamlit/`, exposing sidebar orchestration, layout helpers, and download preparation. Compatibility wrappers continue to exist under `src/ui/`.

### Agents (`agents/`)
Agent-ready surfaces defined with dataclasses and lightweight schema metadata in `agents/idiot_index.py`. Tools are registered via `agents/toolkit.py` and documented for automated clients.

### Entry Point (`app.py`)
The Streamlit application composes the layers: it reads configuration from core, retrieves data via adapters, leverages core normalisation/metric utilities, renders UI components, and provides downloads.

## Testing
`tests/` maps to the layered structure, exercising config validation, caching, metrics, security utilities, logging behaviour, UI helpers, and the agent tool registry. pytest fixtures wire up backwards-compatible import paths.

## Backward Compatibility
To avoid breaking existing imports, thin shims remain under `src/` (e.g., `src/config.py`, `src/sources/`, `src/ui/`). They forward to the reorganised modules while external consumers migrate.
