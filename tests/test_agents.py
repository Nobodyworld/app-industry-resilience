from __future__ import annotations

import pytest

from agents import (
    DataSource,
    IdiotIndexRequest,
    IdiotIndexResponse,
    compute_idiot_index_summary,
    get_tool,
    list_tools,
)


@pytest.mark.parametrize("source", [DataSource.SAMPLE])
def test_compute_idiot_index_summary_offline(source: DataSource) -> None:
    request = IdiotIndexRequest(year=2021, source=source, top_n=3)
    response = compute_idiot_index_summary(request)
    assert isinstance(response, IdiotIndexResponse)
    assert response.rows_evaluated > 0
    assert len(response.top_industries) <= 3
    assert all(item.idiot_index > 0 for item in response.top_industries)


def test_agent_tool_registry_contains_schema() -> None:
    tools = list_tools()
    names = {tool.name for tool in tools}
    assert "compute_idiot_index_summary" in names

    metadata = get_tool("compute_idiot_index_summary")
    input_schema = metadata.input_schema
    output_schema = metadata.output_schema

    assert "properties" in input_schema
    assert "top_industries" in output_schema["properties"]
