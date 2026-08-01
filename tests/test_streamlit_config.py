from __future__ import annotations

import tomllib
from pathlib import Path


def test_streamlit_usage_telemetry_is_disabled_in_local_and_docker_runs() -> None:
    config_path = Path(".streamlit/config.toml")
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))

    assert config["browser"]["gatherUsageStats"] is False

    dockerignore_rules = {
        line.strip()
        for line in Path(".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert ".streamlit/*" in dockerignore_rules
    assert "!.streamlit/config.toml" in dockerignore_rules
