"""FastAPI application exposing the Idiot Index services."""

# ruff: noqa: B008

from __future__ import annotations

import logging
import os
from typing import Any, cast

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from src.application import DataSource, IdiotIndexService, ScenarioPlanner
from src.extensions.manager import get_extension_manager
from src.infrastructure.observability import build_default_probe
from src.interfaces.api.dependencies import (
    get_idiot_index_service,
    get_scenario_planner,
    metric_config_from_flag,
)
from src.interfaces.api.schemas import (
    EvaluateFilters,
    EvaluateRequest,
    EvaluateResponse,
    HealthResponse,
    MetaSourcesResponse,
    ScenarioRequest,
    ScenarioResponse,
    adjustments_to_domain,
    records_to_dataframe,
    scenario_to_response,
    summary_to_response,
)
from src.interfaces.api.telemetry import DEFAULT_TELEMETRY, ApiTelemetry
from src.version import __version__

logger = logging.getLogger(__name__)


class InstrumentedFastAPI(FastAPI):
    """FastAPI façade with telemetry instrumentation."""

    def __init__(self, *, telemetry: ApiTelemetry | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.telemetry = telemetry or DEFAULT_TELEMETRY

    def handle_request(self, method: str, path: str, payload: Any | None = None) -> Response:
        context = self.telemetry.start_request(method, path)
        error: BaseException | None = None
        try:
            response = super().handle_request(method, path, payload)
        except Exception as exc:  # pragma: no cover - defensive guard
            error = exc
            logger.exception("Unhandled API error", extra={"path": path, "method": method})
            self.telemetry.record_exception(path, kind=exc.__class__.__name__)
            response = Response(status_code=500, data={"detail": "Internal Server Error"})
        finally:
            self.telemetry.finish_request(
                method,
                path,
                response.status_code,
                context,
                trace_id=context.trace_id,
                error=error,
            )
        return response


app = InstrumentedFastAPI(title="Idiot Index API", version=__version__)
_health_probe = build_default_probe(
    telemetry_snapshot=lambda: app.telemetry.health_snapshot(),
    extension_manager_provider=get_extension_manager,
)


def _allowed_origins() -> list[str]:
    raw = os.getenv("API_CORS_ALLOW_ORIGINS", "*")
    if not raw:
        return ["*"]
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def _allow_credentials(origins: list[str]) -> bool:
    flag = os.getenv("API_CORS_ALLOW_CREDENTIALS", "false").lower() in {"1", "true", "yes", "on"}
    if "*" in origins and flag:
        return False
    return flag


_origins = _allowed_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=_allow_credentials(_origins),
)


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    """Return a simple health payload."""

    telemetry = app.telemetry
    report = _health_probe.snapshot()
    metadata = dict(report.metadata)
    metadata.setdefault("telemetry", telemetry.health_snapshot())
    trace_id = telemetry.correlation_id()
    return HealthResponse(
        status=report.status,
        service="idiot-index-api",
        version=__version__,
        checked_at=report.checked_at,
        trace_id=trace_id,
        components=[component.as_dict() for component in report.components],
        metadata=metadata,
        telemetry=metadata.get("telemetry", {}),
    )


@app.get("/healthz", response_model=HealthResponse, tags=["system"])
def healthz() -> HealthResponse:
    """Kubernetes-style health endpoint mirroring `/health`."""

    response = cast(HealthResponse, health())
    return response


@app.get("/metrics", tags=["system"])
def metrics() -> Response:
    """Expose Prometheus metrics."""

    payload = app.telemetry.metrics_response()
    return Response(
        status_code=status.HTTP_200_OK, data=payload, media_type="text/plain; version=0.0.4"
    )


@app.get("/meta/sources", response_model=MetaSourcesResponse, tags=["meta"])
def list_sources() -> MetaSourcesResponse:
    """List supported data sources."""

    return MetaSourcesResponse(sources=[source.value for source in DataSource])


@app.post(
    "/evaluate", response_model=EvaluateResponse, tags=["evaluate"], status_code=status.HTTP_200_OK
)
def evaluate(
    request: EvaluateRequest,
    service: Any = Depends(get_idiot_index_service),  # noqa: B008
) -> EvaluateResponse:
    telemetry = app.telemetry
    service = cast(IdiotIndexService, service)
    with telemetry.tracer.start_span(
        "service.evaluate_idiot_index",
        attributes={"source": request.source, "year": request.year},
    ):
        dataframe = None
        if request.records:
            try:
                dataframe = records_to_dataframe(request.records)
            except ValueError as exc:  # pragma: no cover - validated by Pydantic but defensive
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
                ) from exc
            dataframe.attrs.setdefault("source", "api-inline")
            dataframe.attrs.setdefault("source_origin", "api")

        try:
            summary = service.evaluate(
                year=request.year,
                source=request.source,
                search=request.search,
                top_n=request.top_n,
                dataframe=dataframe,
                metric_config=metric_config_from_flag(request.use_cache),
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    filters = EvaluateFilters(search=request.search, top_n=request.top_n)
    response = summary_to_response(
        summary, source=request.source, year=request.year, filters=filters
    )
    trace_id = telemetry.correlation_id()
    if trace_id:
        response.metadata.setdefault("telemetry", {})["trace_id"] = trace_id
    return response


@app.post(
    "/scenario", response_model=ScenarioResponse, tags=["scenario"], status_code=status.HTTP_200_OK
)
def run_scenario(
    request: ScenarioRequest,
    planner: Any = Depends(get_scenario_planner),  # noqa: B008
) -> ScenarioResponse:
    telemetry = app.telemetry
    planner = cast(ScenarioPlanner, planner)
    with telemetry.tracer.start_span(
        "service.scenario_plan",
        attributes={"adjustments": len(request.adjustments)},
    ):
        try:
            base_df = records_to_dataframe(request.base_records)
        except ValueError as exc:  # pragma: no cover - request validation should prevent
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        base_df.attrs.setdefault("source", "api-scenario")

        adjustments = adjustments_to_domain(request.adjustments)

        active_planner = planner
        if request.use_cache is not None and request.use_cache != planner.metric_config.use_cache:
            active_planner = ScenarioPlanner(
                metric_config=metric_config_from_flag(request.use_cache) or planner.metric_config
            )

        try:
            result = active_planner.plan(base_df, adjustments)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    response = scenario_to_response(result)
    trace_id = telemetry.correlation_id()
    if trace_id:
        response.metadata.setdefault("telemetry", {})["trace_id"] = trace_id
    return response


__all__ = ["app"]
