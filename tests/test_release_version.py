from __future__ import annotations

import ast
import tomllib
from pathlib import Path
from typing import Any

from src.scripts import (
    generate_industry_momentum_ces_snapshot,
    generate_industry_momentum_g17_snapshot,
    generate_industry_pulse_snapshot,
)

EXPECTED_VERSION = "0.4.0"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _fallback_version() -> str:
    version_path = PROJECT_ROOT / "src" / "version.py"
    tree = ast.parse(version_path.read_text(encoding="utf-8"), filename=str(version_path))
    fallback_values = [
        node.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets
        )
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    ]
    assert len(fallback_values) == 1
    return fallback_values[0]


def test_authoritative_release_versions_are_aligned() -> None:
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project_version = pyproject["project"]["version"]
    commitizen_version = pyproject["tool"]["commitizen"]["version"]
    fallback_version = _fallback_version()

    assert project_version == EXPECTED_VERSION
    assert commitizen_version == EXPECTED_VERSION
    assert fallback_version == EXPECTED_VERSION
    assert len({project_version, commitizen_version, fallback_version}) == 1


def test_industry_pulse_snapshot_user_agent_uses_the_canonical_version(monkeypatch) -> None:
    request: dict[str, Any] = {}

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"status": "REQUEST_SUCCEEDED"}

    def fake_post(url: str, **kwargs: Any) -> Response:
        request["url"] = url
        request.update(kwargs)
        return Response()

    monkeypatch.setattr(generate_industry_pulse_snapshot, "__version__", EXPECTED_VERSION)
    monkeypatch.setattr(generate_industry_pulse_snapshot.requests, "post", fake_post)

    generate_industry_pulse_snapshot._request_bls(2024, 2026)

    assert request["headers"] == {
        "User-Agent": f"industry-resilience-dashboard/{EXPECTED_VERSION} (+offline-snapshot)"
    }


def test_ces_snapshot_user_agent_uses_the_canonical_version(monkeypatch) -> None:
    request: dict[str, Any] = {}

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"status": "REQUEST_SUCCEEDED"}

    def fake_post(url: str, **kwargs: Any) -> Response:
        request["url"] = url
        request.update(kwargs)
        return Response()

    monkeypatch.setattr(
        generate_industry_momentum_ces_snapshot,
        "__version__",
        EXPECTED_VERSION,
    )
    monkeypatch.setattr(
        generate_industry_momentum_ces_snapshot.requests,
        "post",
        fake_post,
    )

    generate_industry_momentum_ces_snapshot.fetch_payload(start_year=2024, end_year=2026)

    assert request["headers"] == {
        "User-Agent": f"industry-resilience-dashboard/{EXPECTED_VERSION}"
    }


def test_g17_snapshot_user_agent_uses_the_canonical_version(monkeypatch) -> None:
    requests_made: list[tuple[str, dict[str, Any]]] = []

    class Response:
        text = ""

        def raise_for_status(self) -> None:
            return None

    def fake_get(url: str, **kwargs: Any) -> Response:
        requests_made.append((url, kwargs))
        return Response()

    monkeypatch.setattr(
        generate_industry_momentum_g17_snapshot,
        "__version__",
        EXPECTED_VERSION,
    )
    monkeypatch.setattr(
        generate_industry_momentum_g17_snapshot.requests,
        "get",
        fake_get,
    )

    payloads = generate_industry_momentum_g17_snapshot.fetch_files()

    expected_files = generate_industry_momentum_g17_snapshot.G17_FILES
    assert set(payloads) == set(expected_files)
    assert len(requests_made) == len(expected_files)
    assert all(
        request["headers"]
        == {"User-Agent": f"industry-resilience-dashboard/{EXPECTED_VERSION}"}
        for _, request in requests_made
    )
