"""Built-in connector catalog describing bundled integrations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.core.config import get_config_summary, load_config
from src.extensions.connectors import ConnectorRegistration, ConnectorRegistry
from src.extensions.contracts import ConnectorExtension
from src.extensions.manager import ExtensionManager
from src.infrastructure.observability.health import HealthComponent, HealthStatus

SAMPLE_DATA_PATH = Path("data/sample_industries.csv")


def _sample_dataset_health() -> HealthComponent:
    exists = SAMPLE_DATA_PATH.exists()
    status: HealthStatus = "pass" if exists else "fail"
    summary = "Bundled sample dataset available" if exists else "Sample dataset not found"
    details = {"path": str(SAMPLE_DATA_PATH), "expected": True}
    if not exists:
        details["remediation"] = "Run `make prefetch-cache` to restore the bundled sample CSV."
    return HealthComponent(
        name="connector:sample_offline", status=status, summary=summary, details=details
    )


def _bea_health() -> HealthComponent:
    config = load_config()
    summary = get_config_summary(config)
    api_key_present = bool(summary.get("bea_key_set"))
    status: HealthStatus = "pass" if api_key_present else "warn"
    message = "BEA API ready" if api_key_present else "BEA API key not configured"
    details = {
        "api_key_present": api_key_present,
        "supported_years": summary.get("supported_years_bea"),
        "base_urls": summary.get("bea_api_base_urls"),
    }
    return HealthComponent(name="connector:bea", status=status, summary=message, details=details)


def _census_health() -> HealthComponent:
    config = load_config()
    summary = get_config_summary(config)
    api_key_present = bool(summary.get("census_key_set"))
    status: HealthStatus = "pass" if api_key_present else "warn"
    message = (
        "Census ASM connector configured" if api_key_present else "Census API key not configured"
    )
    details = {
        "api_key_present": api_key_present,
        "supported_years": summary.get("supported_years_census"),
        "cache_dir": summary.get("cache_dir"),
    }
    return HealthComponent(
        name="connector:census_asm", status=status, summary=message, details=details
    )


@dataclass
class _ConnectorCatalogExtension(ConnectorExtension):
    name: str = "connector_catalog"

    def register(self, registry: ConnectorRegistry) -> None:
        registry.register(
            ConnectorRegistration(
                identifier="sample_offline",
                name="Sample Dataset",
                kind="data_source",
                version="1.0",
                description="Bundled offline CSV used for demos, tests, and air-gapped exploration.",
                owner="Idiot Index",
                tags=("offline", "demo"),
                capabilities=("read", "analytics"),
                metadata={"path": str(SAMPLE_DATA_PATH)},
                health_check=_sample_dataset_health,
            )
        )
        registry.register(
            ConnectorRegistration(
                identifier="bea",
                name="BEA Industry Accounts API",
                kind="data_source",
                version="v2",
                description="Pulls Bureau of Economic Analysis industry metrics for Idiot Index evaluation.",
                owner="U.S. Bureau of Economic Analysis",
                tags=("api", "industry", "official"),
                capabilities=("read", "normalize", "metrics"),
                metadata={"documentation": "https://apps.bea.gov/API/api.svc"},
                health_check=_bea_health,
            )
        )
        registry.register(
            ConnectorRegistration(
                identifier="census_asm",
                name="Census Annual Survey of Manufactures",
                kind="data_source",
                version="annual",
                description="Imports ASM manufacturing data for material dependency analysis.",
                owner="U.S. Census Bureau",
                tags=("api", "manufacturing"),
                capabilities=("read", "normalize"),
                metadata={
                    "documentation": "https://www.census.gov/data/developers/data-sets/asm.html"
                },
                health_check=_census_health,
            )
        )


def register(manager: ExtensionManager) -> None:
    manager.register_connector_extension(_ConnectorCatalogExtension())


__all__ = ["register"]
