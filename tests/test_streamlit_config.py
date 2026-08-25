from __future__ import annotations

import tomllib
from pathlib import Path


def _relative_luminance(hex_color: str) -> float:
    channels = [int(hex_color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


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


def test_light_theme_primary_color_has_normal_text_contrast() -> None:
    config = tomllib.loads(Path(".streamlit/config.toml").read_text(encoding="utf-8"))
    primary = config["theme"]["light"]["primaryColor"]
    contrast = (1.0 + 0.05) / (_relative_luminance(primary) + 0.05)

    assert contrast >= 4.5
