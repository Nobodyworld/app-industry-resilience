"""Instrumentation extension wiring rate limiting telemetry and health."""

from __future__ import annotations

from dataclasses import dataclass

from src.core import RetryEvent, SecurityUtils, register_retry_observer
from src.extensions.contracts import InstrumentationExtension
from src.extensions.manager import ExtensionManager
from src.infrastructure.observability.health import HealthComponent, HealthStatus
from src.infrastructure.observability.instrumentation import ObservabilityRegistry
from src.infrastructure.rate_limiter import configure_metrics, get_api_limiter


@dataclass
class _RateLimitingInstrumentation(InstrumentationExtension):
    name: str = "rate_limiting"

    def register(self, registry: ObservabilityRegistry) -> None:
        counter = registry.counter(
            "rate_limit_requests_total",
            "Total rate limit enforcement decisions",
            label_names=("scope", "backend", "outcome"),
        )
        wait_histogram = registry.histogram(
            "rate_limit_wait_seconds",
            "Seconds spent waiting for rate limit tokens",
            label_names=("scope", "backend"),
        )
        configure_metrics(counter, wait_histogram)

        retry_counter = registry.counter(
            "http_retries_total",
            "HTTP retry attempts observed",
            label_names=("status",),
        )
        retry_delay = registry.histogram(
            "http_retry_delay_seconds",
            "Delay before HTTP retry attempts",
            label_names=("status",),
        )

        def _retry_observer(event: RetryEvent) -> None:
            retry_counter.increment(labels={"status": event.status})
            if event.delay_seconds > 0:
                retry_delay.observe(event.delay_seconds, labels={"status": event.status})

        register_retry_observer(_retry_observer)

        def _health() -> HealthComponent:
            limiter = get_api_limiter()
            limiter_status = limiter.status()
            security_summary = SecurityUtils.rate_limit_handler_summary()
            mode = str(limiter_status.get("mode", "memory"))
            status: HealthStatus = "pass"
            summary = f"Rate limiting backend: {mode}"
            if mode.endswith("-fallback") or limiter_status.get("last_error"):
                status = "warn"
                summary = "Redis rate limiter experiencing errors"

            details = {
                "limiter": limiter_status,
                "security_handler": security_summary,
            }
            return HealthComponent(
                name="rate_limiting", status=status, summary=summary, details=details
            )

        registry.register_health_check("rate_limiting", _health)


def register(manager: ExtensionManager) -> None:
    manager.register_instrumentation_extension(_RateLimitingInstrumentation())


__all__ = ["register"]
