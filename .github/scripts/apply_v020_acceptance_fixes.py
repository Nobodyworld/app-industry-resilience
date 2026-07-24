from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one source match, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


health_route = '\n\n@app.get("/health", response_model=HealthResponse, tags=["system"])\n'
openapi_route = '''

@app.get("/openapi.json", tags=["system"])
def openapi_document() -> Response:
    """Expose the generated OpenAPI contract through the live application."""

    return Response(
        status_code=status.HTTP_200_OK,
        data=app.openapi(),
        media_type="application/json",
    )


@app.get("/health", response_model=HealthResponse, tags=["system"])
'''
replace_once("src/interfaces/api/app.py", health_route, openapi_route)

api_test_marker = "\n\ndef test_health_endpoint_reports_ok() -> None:\n"
api_test = '''

def test_openapi_endpoint_exposes_live_contract() -> None:
    response = client.get("/openapi.json")
    payload = response.json()

    assert response.status_code == 200
    assert response.media_type == "application/json"
    assert payload["openapi"] == "3.1.0"
    assert payload["info"]["title"] == "Idiot Index API"
    assert payload["info"]["version"] == app.version
    assert "/openapi.json" in payload["paths"]
    assert "/v1/meta/public-data" in payload["paths"]


def test_health_endpoint_reports_ok() -> None:
'''
replace_once("tests/test_api.py", api_test_marker, api_test)

replace_once(
    "src/interfaces/streamlit/components.py",
    '''
            .stApp {
                background: var(--surface);
            }

''',
    "",
)
replace_once(
    "src/interfaces/streamlit/components.py",
    '''                background: var(--accent-soft);
                border: 1px solid rgba(60, 208, 201, 0.4);''',
    '''                background: #d9f7f4;
                border: 1px solid #3aa8a2;''',
)
replace_once(
    "src/interfaces/streamlit/components.py",
    "                color: var(--ink-300);\n                margin-top: 0.75rem;",
    "                color: inherit;\n                margin-top: 0.75rem;",
)

replace_once(
    "tests/test_streamlit_components.py",
    "    build_data_story,\n    render_data_provenance,\n",
    "    build_data_story,\n    load_custom_styles,\n    render_data_provenance,\n",
)
provenance_test_marker = (
    "\n\ndef test_render_data_provenance_uses_typed_lineage_only(monkeypatch) -> None:\n"
)
style_test = '''

def test_custom_styles_preserve_native_theme_contrast(monkeypatch) -> None:
    rendered: list[str] = []
    monkeypatch.setattr(
        st,
        "markdown",
        lambda body, **_kwargs: rendered.append(body),
    )

    load_custom_styles()

    css = rendered[0]
    assert ".stApp {" not in css
    assert "background: #d9f7f4;" in css
    assert ".sidebar-guidance" in css and "color: inherit;" in css


def test_render_data_provenance_uses_typed_lineage_only(monkeypatch) -> None:
'''
replace_once(
    "tests/test_streamlit_components.py",
    provenance_test_marker,
    style_test,
)
