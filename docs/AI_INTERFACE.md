# Agent Interface

The Idiot Index app ships with a lightweight agent toolkit under `agents/`. Tools are registered via `agents.toolkit.tool` which records dataclass-based request/response schemas for automation platforms.

## Available Tools

### `compute_idiot_index_summary`
- **Purpose:** Load Idiot Index data from the sample dataset, BEA, or Census ASM, then compute key metrics and a leaderboard.
- **Module:** `agents.idiot_index`
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

The JSON schemas for the request and response models are accessible at runtime via `agents.get_tool("compute_idiot_index_summary").input_schema` and `.output_schema`.

## Example Usage

```python
from agents import IdiotIndexRequest, compute_idiot_index_summary

request = IdiotIndexRequest(year=2021, source="sample", top_n=5)
response = compute_idiot_index_summary(request)

for industry in response.top_industries:
    print(industry.code, industry.name, industry.idiot_index)
```

## Validation Behaviour
- Invalid years or leaderboard sizes raise `ValueError` before any network calls occur.
- Search strings are sanitised using `SecurityUtils.sanitize_string_input` to strip dangerous patterns.
- When live data sources are requested without API keys, a `ValueError` is raised immediately.

## Extending the Toolkit
1. Create a dataclass for the request and response payloads.
2. Decorate the callable with `@tool(name="...", description="...")`.
3. The decorator automatically registers the tool and captures JSON schemas for integration.
