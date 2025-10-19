# Stage 2 – Deep Diagnostic

## Code Smells & Anti-Patterns
- **Missing imports causing runtime failures (critical):**
  - `src/security.py` references `re` without importing it, preventing module import.
  - `src/cache.py` lacks imports for `json`, `threading`, and `time`, breaking cache usage.
  - `src/logging_config.py` uses `logging`, `logging.handlers`, and `json` without importing them.
  - `src/sources/bea.py` omits `concurrent.futures` and `time` imports despite heavy use.
  - `src/sources/census_asm.py` constructs DataFrames but never imports `pandas`.
  - `src/utils.py` relies on `random` and `time` in retry logic without importing them.
- **Error handling gaps (moderate):** caching helpers swallow JSON/OS errors without logging; BEA client re-raises generic exceptions without context enrichment; Streamlit upload handler silently stops on fetch failures.
- **Config polish issues (minor):** development requirements file and CI workflow lack trailing newlines, violating formatting conventions; `.env.example` may not document new logging/env knobs introduced by logging module.

## Typing & Validation Weaknesses
- Several functions return `None` on failure without structured error feedback (e.g., file uploads). Consider typed result wrappers or richer messaging.
- API helpers rely on loose `dict[str, Any]` structures; additional TypedDict/Pydantic schemas would strengthen contracts for agent use.

## Security Review
- Security helpers intend to sanitize filenames/strings but `_DANGEROUS_PATTERNS` cannot compile without `re` import.
- No explicit audit of dependency versions against known CVEs; requirements pins may need review.
- Streamlit query parameter encoding lacks checksum/hmac for share URLs (acceptable but note for future hardening).

## TODO / FIXME Inventory
- No inline TODO/FIXME comments in source; legacy `docs/exec-plan.md` references previously resolved TODOs. No action items remain from code comments.

## Triggered Modes
- **Architecture Alignment:** The entrypoint and service modules need import corrections, explicit dependency boundaries, and clearer initialization of caches/logging.
- **Zero-Bloat Refactor:** Remove dead/unused logic, add missing imports, tighten retry/cache behavior, and ensure modules expose minimal, efficient surfaces.
- **Full-System Polish:** Enforce formatting, restore trailing newlines, update docs, add docstrings where absent, and ensure typing hints remain consistent.
- **Test & Verify:** Expand/refresh tests after fixes; ensure pytest covers new pathways and run the full CI-equivalent stack locally.
- **Security & Stability Audit:** Repair security helpers, review dependency versions, and document secure configuration practices.
- **AI-Ready Refactor:** Introduce structured schemas (e.g., Pydantic) for agent interoperability and author `docs/AI_INTERFACE.md` describing callable surfaces.

