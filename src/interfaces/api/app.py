"""FastAPI application exposing the Idiot Index services."""

# ruff: noqa: B008

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from typing import Any, cast

import pandas as pd

from fastapi_compat import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi_compat.middleware.cors import CORSMiddleware
from src.application import DataSource, IdiotIndexService, ScenarioPlanner
from src.core import LineageStep, attach_lineage, build_lineage, summarise_health
from src.extensions.manager import get_extension_manager
from src.infrastructure.observability import (
    bootstrap_observability,
    build_default_probe,
)
from src.interfaces.api.dependencies import (
    get_idiot_index_service,
    get_scenario_planner,
    get_snapshot_storage,
    metric_config_from_flag,
)
from src.interfaces.api.schemas import (
    EvaluateFilters,
    EvaluateRequest,
    EvaluateResponse,
    HealthAnalyticsEnvelope,
    HealthAnalyticsRequest,
    HealthAnalyticsResponse,
    HealthResponse,
    MetaConnectorsResponse,
    MetaSourcesResponse,
    ObservabilityDigestResponse,
    ObservabilityEventsResponse,
    ObservabilityEventsSummaryModel,
    ObservabilityMetricsModel,
    ObservabilitySnapshotMeta,
    ObservabilitySnapshotResponse,
    ObservabilityStatusResponse,
    ObservationEventModel,
    ScenarioRequest,
    ScenarioResponse,
    adjustments_to_domain,
    health_summary_to_model,
    lineage_model_from_dataframe,
    metadata_from_summary,
    records_to_dataframe,
    scenario_to_response,
    snapshot_meta_to_payload,
    snapshot_response_to_payload,
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
                error=error,
            )
        return response


_extension_manager = get_extension_manager()
_observability_registry = bootstrap_observability()
_extension_manager.apply_instrumentation_extensions(_observability_registry)

app = InstrumentedFastAPI(
    title="Idiot Index API",
    version=__version__,
    telemetry=ApiTelemetry(observability=_observability_registry),
)
_health_probe = build_default_probe(
    telemetry_snapshot=lambda: app.telemetry.health_snapshot(),
    extension_manager_provider=lambda: _extension_manager,
)
_observability_registry.bind_probe(_health_probe)


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


@app.get(
    "/observability/status",
    response_model=ObservabilityStatusResponse,
    tags=["system"],
)
def observability_status() -> ObservabilityStatusResponse:
    """Return a snapshot of metrics, traces, and recent observation events."""

    digest = _observability_registry.digest()
    events = digest["events"]
    return ObservabilityStatusResponse(
        metrics=ObservabilityMetricsModel(**digest["metrics"]),
        traces=digest["traces"],
        recent_events=[ObservationEventModel(**event) for event in events["recent"]],
        health_checks=digest["health_checks"],
        event_counters=events["counts"],
        last_error=(
            ObservationEventModel(**events["last_error"]) if events.get("last_error") else None
        ),
    )


@app.get(
    "/observability/digest",
    response_model=ObservabilityDigestResponse,
    tags=["system"],
)
def observability_digest() -> ObservabilityDigestResponse:
    """Return an enriched observability digest for automation and dashboards."""

    digest = _observability_registry.digest()
    events = digest["events"]
    last_error = events.get("last_error")
    event_payload = ObservabilityEventsSummaryModel(
        counts=events["counts"],
        total=events["total"],
        recent=[ObservationEventModel(**event) for event in events["recent"]],
        last_error=ObservationEventModel(**last_error) if last_error else None,
    )
    return ObservabilityDigestResponse(
        metrics=ObservabilityMetricsModel(**digest["metrics"]),
        traces=digest["traces"],
        health_checks=digest["health_checks"],
        events=event_payload,
        subscriptions=digest["subscriptions"],
    )


@app.get(
    "/observability/events",
    response_model=ObservabilityEventsResponse,
    tags=["system"],
)
def observability_events(
    limit: int | None = Query(25, ge=1, le=100),
    status: str | None = Query(
        None,
        description="Optional status filter (success, error, warn).",
        min_length=1,
    ),
) -> ObservabilityEventsResponse:
    """Expose recent observation events for debugging and automation."""

    normalised_status = status.lower() if status else None
    filtered = _observability_registry.events(status=normalised_status)
    if limit is not None:
        limited = filtered[:limit]
    else:
        limited = filtered
    events = [ObservationEventModel(**event) for event in limited]
    return ObservabilityEventsResponse(
        events=events,
        total_available=len(filtered),
        applied_limit=limit,
        applied_status=normalised_status,
    )


@app.get(
    "/observability/snapshots",
    response_model=list[ObservabilitySnapshotMeta],
    tags=["system"],
)
def observability_snapshots(
    storage=Depends(get_snapshot_storage),
) -> list[dict[str, Any]]:
    """List stored observability snapshots."""

    snapshots = storage.list()
    return [snapshot_meta_to_payload(snapshot) for snapshot in snapshots]


@app.get(
    "/observability/snapshots/{snapshot_id}",
    response_model=ObservabilitySnapshotResponse,
    tags=["system"],
)
def observability_snapshot_detail(
    snapshot_id: str,
    storage=Depends(get_snapshot_storage),
) -> dict[str, Any]:
    """Return a stored observability snapshot by identifier."""

    try:
        snapshot = storage.get(snapshot_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return snapshot_response_to_payload(snapshot)


_API_V1_PREFIX = "/v1"
_LEGACY_API_SUNSET = "Fri, 15 Jan 2027 00:00:00 GMT"


def _legacy_api_headers(successor_path: str) -> dict[str, str]:
    """Return the centralized migration headers for one legacy route."""

    return {
        "Deprecation": "true",
        "Sunset": _LEGACY_API_SUNSET,
        "Link": f'<{successor_path}>; rel="successor-version"',
    }


def _legacy_alias_response(payload: Any, successor_path: str) -> Response:
    """Serialize a typed payload and attach legacy-route migration headers."""

    data = payload.model_dump(mode="json") if hasattr(payload, "model_dump") else payload
    return Response(
        status_code=status.HTTP_200_OK,
        data=data,
        headers=_legacy_api_headers(successor_path),
    )


def _list_sources_response() -> MetaSourcesResponse:
    return MetaSourcesResponse(sources=[source.value for source in DataSource])


@app.get("/v1/meta/sources", response_model=MetaSourcesResponse, tags=["meta"])
def list_sources_v1() -> MetaSourcesResponse:
    """List supported data sources through the canonical v1 route."""

    return _list_sources_response()


@app.get(
    "/meta/sources",
    response_model=MetaSourcesResponse,
    tags=["meta"],
    deprecated=True,
)
def list_sources() -> Response:
    """List sources through the deprecated unversioned compatibility alias."""

    return _legacy_alias_response(_list_sources_response(), "/v1/meta/sources")


def _list_connectors_response() -> MetaConnectorsResponse:
    _extension_manager.initialise_connectors()
    summary = _extension_manager.connector_registry.summary(include_health=True)
    return MetaConnectorsResponse.from_summary(summary)


@app.get("/v1/meta/connectors", response_model=MetaConnectorsResponse, tags=["meta"])
def list_connectors_v1() -> MetaConnectorsResponse:
    """List registered connectors through the canonical v1 route."""

    return _list_connectors_response()


@app.get(
    "/meta/connectors",
    response_model=MetaConnectorsResponse,
    tags=["meta"],
    deprecated=True,
)
def list_connectors() -> Response:
    """List connectors through the deprecated unversioned compatibility alias."""

    return _legacy_alias_response(_list_connectors_response(), "/v1/meta/connectors")


def _attach_api_inline_lineage(frame: pd.DataFrame, *, year: int) -> None:
    """Attach redacted source lineage for API-supplied inline records."""

    lineage = build_lineage(
        source="api-inline",
        source_kind="inline_records",
        dataset_id="api-inline",
        observation_period=year,
        acquired_at=datetime.now(UTC),
        retrieval_mode="inline",
        is_sample=False,
        is_official=False,
        transformations=(
            LineageStep(
                name="source_load",
                details={"record_count": len(frame)},
            ),
        ),
    )
    attach_lineage(frame, lineage)


def _evaluate_response(
    request: EvaluateRequest,
    service: IdiotIndexService,
) -> EvaluateResponse:
    telemetry = app.telemetry
    with telemetry.tracer.start_span(
        "service.evaluate_idiot_index",
        attributes={"source": request.source, "year": request.year},
    ):
        dataframe = None
        if request.records:
            try:
                dataframe = records_to_dataframe(request.records)
            except ValueError as exc:  # pragma: no cover - validated but defensive
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(exc),
                ) from exc
            dataframe.attrs.setdefault("source", "api-inline")
            dataframe.attrs.setdefault("source_origin", "api")
            _attach_api_inline_lineage(dataframe, year=request.year)

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
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    filters = EvaluateFilters(search=request.search, top_n=request.top_n)
    response = summary_to_response(
        summary,
        source=request.source,
        year=request.year,
        filters=filters,
    )
    trace_id = telemetry.correlation_id()
    if trace_id:
        response.metadata.setdefault("telemetry", {})["trace_id"] = trace_id
    return response


@app.post(
    "/v1/evaluate",
    response_model=EvaluateResponse,
    tags=["evaluate"],
    status_code=status.HTTP_200_OK,
)
def evaluate_v1(
    request: EvaluateRequest,
    service: Any = Depends(get_idiot_index_service),  # noqa: B008
) -> EvaluateResponse:
    """Evaluate industry metrics through the canonical v1 route."""

    return _evaluate_response(request, cast(IdiotIndexService, service))


@app.post(
    "/evaluate",
    response_model=EvaluateResponse,
    tags=["evaluate"],
    status_code=status.HTTP_200_OK,
    deprecated=True,
)
def evaluate(
    request: EvaluateRequest,
    service: Any = Depends(get_idiot_index_service),  # noqa: B008
) -> Response:
    """Evaluate through the deprecated unversioned compatibility alias."""

    payload = _evaluate_response(request, cast(IdiotIndexService, service))
    return _legacy_alias_response(payload, "/v1/evaluate")


def _scenario_response(
    request: ScenarioRequest,
    planner: ScenarioPlanner,
) -> ScenarioResponse:
    telemetry = app.telemetry
    with telemetry.tracer.start_span(
        "service.scenario_plan",
        attributes={"adjustments": len(request.adjustments)},
    ):
        try:
            base_df = records_to_dataframe(request.base_records)
        except ValueError as exc:  # pragma: no cover - validated but defensive
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

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
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    response = scenario_to_response(result)
    trace_id = telemetry.correlation_id()
    if trace_id:
        response.metadata.setdefault("telemetry", {})["trace_id"] = trace_id
    return response


@app.post(
    "/v1/scenario",
    response_model=ScenarioResponse,
    tags=["scenario"],
    status_code=status.HTTP_200_OK,
)
def run_scenario_v1(
    request: ScenarioRequest,
    planner: Any = Depends(get_scenario_planner),  # noqa: B008
) -> ScenarioResponse:
    """Run scenario planning through the canonical v1 route."""

    return _scenario_response(request, cast(ScenarioPlanner, planner))


@app.post(
    "/scenario",
    response_model=ScenarioResponse,
    tags=["scenario"],
    status_code=status.HTTP_200_OK,
    deprecated=True,
)
def run_scenario(
    request: ScenarioRequest,
    planner: Any = Depends(get_scenario_planner),  # noqa: B008
) -> Response:
    """Run scenarios through the deprecated unversioned compatibility alias."""

    payload = _scenario_response(request, cast(ScenarioPlanner, planner))
    return _legacy_alias_response(payload, "/v1/scenario")


def _analytics_health_response(
    request: HealthAnalyticsRequest,
    service: IdiotIndexService,
) -> HealthAnalyticsResponse:
    telemetry = app.telemetry
    filters = EvaluateFilters(search=request.search, top_n=5)

    dataframe = None
    if request.records:
        try:
            dataframe = records_to_dataframe(request.records)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        dataframe.attrs.setdefault("source", "api-inline")
        dataframe.attrs.setdefault("source_origin", "api-health")
        _attach_api_inline_lineage(dataframe, year=request.year)

    with telemetry.tracer.start_span(
        "service.analytics_health",
        attributes={"source": request.source, "year": request.year},
    ):
        try:
            summary = service.evaluate(
                year=request.year,
                source=request.source,
                search=request.search,
                top_n=filters.top_n,
                dataframe=dataframe,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    full_summary = summarise_health(
        summary.dataframe_full,
        group_by=request.group_by,
        top_risk_limit=request.top_risks,
    )
    filtered_summary = summarise_health(
        summary.dataframe_filtered,
        group_by=request.group_by,
        top_risk_limit=request.top_risks,
    )
    envelope = HealthAnalyticsEnvelope(
        full=health_summary_to_model(full_summary),
        filtered=health_summary_to_model(filtered_summary),
    )
    response = HealthAnalyticsResponse(
        source=request.source,
        year=request.year,
        filters=filters,
        health=envelope,
        metadata=metadata_from_summary(summary),
        lineage=lineage_model_from_dataframe(summary.dataframe_full),
    )
    trace_id = telemetry.correlation_id()
    if trace_id:
        response.metadata.setdefault("telemetry", {})["trace_id"] = trace_id
    return response


@app.post(
    "/v1/analytics/health",
    response_model=HealthAnalyticsResponse,
    tags=["analytics"],
    status_code=status.HTTP_200_OK,
)
def analytics_health_v1(
    request: HealthAnalyticsRequest,
    service: Any = Depends(get_idiot_index_service),  # noqa: B008
) -> HealthAnalyticsResponse:
    """Return health analytics through the canonical v1 route."""

    return _analytics_health_response(request, cast(IdiotIndexService, service))


@app.post(
    "/analytics/health",
    response_model=HealthAnalyticsResponse,
    tags=["analytics"],
    status_code=status.HTTP_200_OK,
    deprecated=True,
)
def analytics_health(
    request: HealthAnalyticsRequest,
    service: Any = Depends(get_idiot_index_service),  # noqa: B008
) -> Response:
    """Return health analytics through the deprecated unversioned alias."""

    payload = _analytics_health_response(request, cast(IdiotIndexService, service))
    return _legacy_alias_response(payload, "/v1/analytics/health")


__all__ = ["app"]
