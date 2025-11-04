"""Tests for Streamlit bootstrap utilities and configuration loading."""

import pytest

import src.interfaces.streamlit.bootstrap as bootstrap_module
from src.interfaces.streamlit import get_bootstrap_state, reset_bootstrap_state
from src.interfaces.streamlit.bootstrap import BootstrapError


@pytest.fixture(autouse=True)
def clear_bootstrap_cache() -> None:
    reset_bootstrap_state()
    yield
    reset_bootstrap_state()


def test_bootstrap_state_uses_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    call_count = 0
    original_load_config = bootstrap_module.load_config

    def tracking_load(env: dict[str, str] | None = None):
        nonlocal call_count
        call_count += 1
        return original_load_config(env)

    monkeypatch.setattr(bootstrap_module, "load_config", tracking_load)

    first = get_bootstrap_state()
    second = get_bootstrap_state()

    assert first is second
    assert call_count == 1


def test_bootstrap_state_respects_env_override() -> None:
    state = get_bootstrap_state({"DEFAULT_YEAR": "2018"})
    assert state.config.default_year == 2018
    assert state.validation.errors == ()


def test_reset_bootstrap_state_forces_reload() -> None:
    earlier = get_bootstrap_state({"DEFAULT_YEAR": "2019"})
    reset_bootstrap_state()
    later = get_bootstrap_state({"DEFAULT_YEAR": "2020"})
    assert later is not earlier
    assert later.config.default_year == 2020


def test_bootstrap_state_wraps_config_errors() -> None:
    with pytest.raises(BootstrapError):
        get_bootstrap_state({"ENVIRONMENT": "invalid"})


def test_bootstrap_state_flags_warnings() -> None:
    state = get_bootstrap_state(
        {
            "ENVIRONMENT": "development",
            "DEFAULT_YEAR": "2020",
            "BEA_API_KEY": "",
            "CENSUS_API_KEY": "",
        }
    )
    assert state.has_warnings is True
    assert state.warnings
    assert state.errors == ()


def test_bootstrap_state_year_bounds_union() -> None:
    state = get_bootstrap_state(
        {
            "ENVIRONMENT": "development",
            "DEFAULT_YEAR": "2000",
            "SUPPORTED_YEARS_BEA": "2000-2020",
            "SUPPORTED_YEARS_CENSUS": "1995-2018",
        }
    )
    assert state.supported_year_bounds == (1995, 2020)


def test_bootstrap_state_case_insensitive_env_keys() -> None:
    first = get_bootstrap_state({"default_year": "2017"})
    second = get_bootstrap_state({"DEFAULT_YEAR": "2017"})
    assert first is second


def test_bootstrap_state_ensure_ready_raises() -> None:
    state = get_bootstrap_state({"DEFAULT_YEAR": "1900"})
    assert state.validation.errors
    with pytest.raises(BootstrapError) as excinfo:
        state.ensure_ready()
    for message in state.errors:
        assert message in str(excinfo.value)


def test_bootstrap_state_ensure_ready_returns_config() -> None:
    state = get_bootstrap_state()
    assert state.ensure_ready() is state.config


def test_normalised_env_converts_non_string_values() -> None:
    state = get_bootstrap_state({"DEFAULT_YEAR": 2016})
    assert state.config.default_year == 2016


def test_sidebar_context_clamps_years() -> None:
    state = get_bootstrap_state(
        {
            "SUPPORTED_YEARS_BEA": "2000-2005",
            "SUPPORTED_YEARS_CENSUS": "1995-2003",
            "DEFAULT_YEAR": "2003",
        }
    )
    sidebar = state.sidebar_context
    assert sidebar.year_bounds == (1995, 2005)
    assert sidebar.normalise_year(1990) == 1995
    assert sidebar.normalise_year(2050) == 2005
    assert sidebar.normalise_year(None) == 2003


def test_env_normalisation_ignores_none_values() -> None:
    state_with_none = get_bootstrap_state({"DEFAULT_YEAR": None})
    baseline = get_bootstrap_state()
    assert state_with_none is baseline
