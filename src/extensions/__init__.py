"""Extension utilities for the Idiot Index platform."""

from .contracts import (
    ConnectorExtension,
    ExtensionContributions,
    InstrumentationExtension,
    ReplicationExtension,
    ScenarioExtension,
    SummaryExtension,
)
from .manager import (
    ExtensionManager,
    discover_extension_modules,
    get_extension_manager,
    load_extensions,
)

__all__ = [
    "ExtensionContributions",
    "ConnectorExtension",
    "InstrumentationExtension",
    "ReplicationExtension",
    "ScenarioExtension",
    "SummaryExtension",
    "ExtensionManager",
    "discover_extension_modules",
    "get_extension_manager",
    "load_extensions",
]
