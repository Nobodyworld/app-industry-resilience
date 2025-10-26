"""Instrumentation extension capturing dataset and scenario quality telemetry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.extensions.contracts import InstrumentationExtension
from src.extensions.manager import ExtensionManager
from src.infrastructure.observability.health import HealthComponent, HealthStatus
from src.infrastructure.observability.instrumentation import ObservabilityRegistry, ObservationEvent


@dataclass
class _DataQualityInstrumentation(InstrumentationExtension):
    """Track dataset row counts, missing ratios, and expose health signals."""

    name: str = "data_quality"
    _latest_dataset: dict[str, Any] | None = field(default=None, init=False, repr=False)
    _latest_scenario: dict[str, Any] | None = field(default=None, init=False, repr=False)

    def register(self, registry: ObservabilityRegistry) -> None:
        dataset_rows = registry.gauge(
            "idiot_index_dataset_rows",
            "Row counts for dataset and scenario frames",
            label_names=("context", "frame", "source"),
        )
        missing_ratio = registry.gauge(
            "idiot_index_dataset_missing_ratio",
            "Share of missing values for dataset and scenario frames",
            label_names=("context", "frame", "source"),
        )

        def _record_dataset(event: ObservationEvent) -> None:
            attributes = dict(event.attributes)
            source = str(attributes.get("source", "unknown"))
            context_labels = {"context": "dataset", "source": source}
            dataset_rows.set(
                float(attributes.get("full_rows", 0)),
                labels={**context_labels, "frame": "full"},
            )
            dataset_rows.set(
                float(attributes.get("filtered_rows", 0)),
                labels={**context_labels, "frame": "filtered"},
            )
            missing_ratio.set(
                float(attributes.get("full_missing_ratio", 0.0)),
                labels={**context_labels, "frame": "full"},
            )
            missing_ratio.set(
                float(attributes.get("filtered_missing_ratio", 0.0)),
                labels={**context_labels, "frame": "filtered"},
            )
            payload = event.as_dict()
            self._latest_dataset = {
                "timestamp": payload["timestamp"],
                "status": payload["status"],
                "attributes": attributes,
            }

        def _record_scenario(event: ObservationEvent) -> None:
            attributes = dict(event.attributes)
            source = str(attributes.get("source", "scenario"))
            context_labels = {"context": "scenario", "source": source}
            dataset_rows.set(
                float(attributes.get("baseline_rows", 0)),
                labels={**context_labels, "frame": "baseline"},
            )
            dataset_rows.set(
                float(attributes.get("scenario_rows", 0)),
                labels={**context_labels, "frame": "scenario"},
            )
            dataset_rows.set(
                float(attributes.get("delta_rows", 0)),
                labels={**context_labels, "frame": "delta"},
            )
            missing_ratio.set(
                float(attributes.get("baseline_missing_ratio", 0.0)),
                labels={**context_labels, "frame": "baseline"},
            )
            missing_ratio.set(
                float(attributes.get("scenario_missing_ratio", 0.0)),
                labels={**context_labels, "frame": "scenario"},
            )
            payload = event.as_dict()
            self._latest_scenario = {
                "timestamp": payload["timestamp"],
                "status": payload["status"],
                "attributes": attributes,
            }

        registry.subscribe("service.dataset.profile", _record_dataset)
        registry.subscribe("service.scenario.profile", _record_scenario)

        def _health() -> HealthComponent:
            status: HealthStatus = "pass"
            summary = "Data quality telemetry captured"
            details: dict[str, Any] = {
                "latest_dataset": self._latest_dataset,
                "latest_scenario": self._latest_scenario,
            }
            dataset_attrs = (self._latest_dataset or {}).get("attributes", {})
            filtered_rows = int(dataset_attrs.get("filtered_rows", 0) or 0)
            filtered_ratio = float(dataset_attrs.get("filtered_missing_ratio", 0.0) or 0.0)
            if self._latest_dataset is None:
                status = "warn"
                summary = "No dataset profile events recorded"
            elif filtered_rows == 0:
                status = "warn"
                summary = "Latest dataset profile contained zero filtered rows"
            elif filtered_ratio >= 0.25:
                status = "warn"
                summary = "Filtered dataset has high missing value ratio"

            scenario_attrs = (self._latest_scenario or {}).get("attributes", {})
            scenario_ratio = float(scenario_attrs.get("scenario_missing_ratio", 0.0) or 0.0)
            if scenario_ratio >= 0.25:
                status = "warn"
                summary = "Scenario data exhibits high missing value ratio"

            return HealthComponent(
                name="data_quality",
                status=status,
                summary=summary,
                details=details,
            )

        registry.register_health_check("data_quality", _health)


def register(manager: ExtensionManager) -> None:
    manager.register_instrumentation_extension(_DataQualityInstrumentation())


__all__ = ["register"]
