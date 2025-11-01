# Agent Interface

The Idiot Index app ships with a lightweight agent toolkit under `src/agents/`. Tools are registered via `src.agents.toolkit.tool` which records dataclass-based request/response schemas for automation platforms.

## Available Tools

### `compute_idiot_index_summary`
- **Purpose:** Load Idiot Index data from the sample dataset, BEA, or Census ASM, then compute key metrics and a leaderboard.
- **Module:** `src.agents.idiot_index`
- **Request model:** `IdiotIndexRequest`
- **Response model:** `IdiotIndexResponse`

#### Request Fields
| Field | Type | Description |
| --- | --- | --- |
| `year` | integer | Calendar year between 1997 and 2100. |
| `source` | enum (`sample`, `bea`, `census`) | Data source to query. BEA and Census require API keys configured via environment variables. |
| `search` | string (optional) | Case-insensitive filter applied to industry name or code. Sanitised automatically. |
| `top_n` | integer | Number of industries to include in the leaderboard (1–25). |

#### Response Fields
| Field | Type | Description |
| --- | --- | --- |
| `rows_evaluated` | integer | Number of rows considered after filtering. |
| `idiot_index_average` | number | Mean Idiot Index across the filtered dataset (if available). |
| `top_industries` | array of objects | Each entry contains `code`, `name`, `idiot_index`, and optional `value_added_pct`. |
| `notes` | array of strings | Metadata returned by upstream services (e.g., BEA notes). |
| `health_score_average` | number | Composite health score (0–100) for the filtered dataset. |
| `health_risk_band` | string | Risk band label (`excellent`, `healthy`, `watch`, or `critical`). |

The JSON schemas for the request and response models are accessible at runtime via `src.agents.get_tool("compute_idiot_index_summary").input_schema` and `.output_schema`.

## Example Usage

```python
from src.agents import IdiotIndexRequest, compute_idiot_index_summary

request = IdiotIndexRequest(year=2021, source="sample", top_n=5)
response = compute_idiot_index_summary(request)

for industry in response.top_industries:
    print(industry.code, industry.name, industry.idiot_index)
```

### Inspecting JSON Schema programmatically

```python
from src.agents import get_tool

tool = get_tool("compute_idiot_index_summary")
print(tool.input_schema)
print(tool.output_schema)
```

Both schemas follow JSON Schema Draft 7 conventions. Optional fields surface under the `required` key.

### Running from the command line

The repo ships with a helper script that mirrors the agent call:

```bash
python - <<'PY'
from src.agents import IdiotIndexRequest, compute_idiot_index_summary

payload = IdiotIndexRequest(year=2020, source="sample", top_n=3)
summary = compute_idiot_index_summary(payload)

print(f"Rows evaluated: {summary.rows_evaluated}")
for row in summary.top_industries:
    print(f"{row.code}: {row.name} ({row.idiot_index:.2f})")
PY
```

## Validation Behaviour
- Invalid years or leaderboard sizes raise `ValueError` before any network calls occur.
- Search strings are sanitised using `SecurityUtils.sanitize_string_input` to strip dangerous patterns.
- When live data sources are requested without API keys, a `ValueError` is raised immediately.

## Error handling

- `ValueError` – user misconfiguration (year out of range, missing API keys, invalid `top_n`).
- `RuntimeError` – propagated from adapters when upstream services are unavailable even after retries.
- Network exceptions are converted to domain-specific errors within adapters and logged via `src.infrastructure.log_performance`.

Applications embedding the toolkit should catch `ValueError` for actionable user feedback and re-raise or log other exceptions.

## Extending the Toolkit
1. Create a dataclass for the request and response payloads.
2. Decorate the callable with `@tool(name="...", description="...")`.
3. The decorator automatically registers the tool and captures JSON schemas for integration.

### Integration checklist

- [ ] Import request/response dataclasses from `src.agents` to keep type hints stable.
- [ ] Validate API keys are present before invoking live sources (BEA or Census).
- [ ] Handle pagination in long-running conversations by storing `IdiotIndexRequest` copies if you expect to reuse them.
- [ ] Leverage the JSON schema metadata to configure third-party agent platforms.
