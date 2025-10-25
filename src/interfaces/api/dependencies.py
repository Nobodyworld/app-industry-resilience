"""Dependency wiring for the headless FastAPI service."""

from __future__ import annotations

from functools import lru_cache

from src.application import IdiotIndexService, ScenarioPlanner
from src.core import MetricConfig
from src.extensions.manager import get_extension_manager


@lru_cache(maxsize=1)
def _service_singleton() -> IdiotIndexService:
    return IdiotIndexService(extension_manager=get_extension_manager())


@lru_cache(maxsize=1)
def _planner_singleton() -> ScenarioPlanner:
    return ScenarioPlanner(
        metric_config=MetricConfig(use_cache=False), extension_manager=get_extension_manager()
    )


def get_idiot_index_service() -> IdiotIndexService:
    """Return a shared IdiotIndexService instance."""

    return _service_singleton()


def get_scenario_planner() -> ScenarioPlanner:
    """Return a shared ScenarioPlanner instance."""

    return _planner_singleton()


def metric_config_from_flag(flag: bool | None) -> MetricConfig | None:
    """Build a MetricConfig override based on the provided flag."""

    if flag is None:
        return None
    return MetricConfig(use_cache=flag)
