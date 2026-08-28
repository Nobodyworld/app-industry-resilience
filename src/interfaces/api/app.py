"""FastAPI application exposing the Idiot Index services."""

# ruff: noqa: B008

from __future__ import annotations

import logging
import os
import re
from datetime import UTC, date, datetime
from typing import Any, cast

import pandas as pd

from fastapi_compat import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi_compat.middleware.cors import CORSMiddleware
from src.application import (
    DataSource,
    IdiotIndexService,
    IndustryMomentumService,
    IndustryPulseService,
    ScenarioPlanner,
)
from src.core import (
    LineageStep,
    attach_lineage,
    build_lineage,
    public_dataset_catalog,
    summarise_health,
)
from src.core.industry_momentum import (
    INDUSTRY_MOMENTUM_COMPARISON_LIMITATION,
    INDUSTRY_MOMENTUM_INTERPRETATION,
    SignalType,
    SourceFamily,
)
from src.core.industry_pulse import IndustryPulseSnapshotError
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
    IndustryMomentumListResponse,
    IndustryMomentumResponse,
    IndustryPulseListResponse,
    IndustryPulseResponse,
    MetaConnectorsResponse,
    MetaPublicDataResponse,
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


_industry_pulse_initialization_error: str | None = None


def _initialize_industry_pulse_service() -> IndustryPulseService | None:
    """Load the optional offline snapshot without preventing API startup."""

    global _industry_pulse_initialization_error
    try:
        service = IndustryPulseService()
    except IndustryPulseSnapshotError:
        _industry_pulse_initialization_error = "snapshot_validation_failure"
        logger.warning(
            "Industry Pulse snapshot is unavailable.",
            extra={"error_classification": _industry_pulse_initialization_error},
        )
        return None
    _industry_pulse_initialization_error = None
    return service


def _require_industry_pulse_service() -> IndustryPulseService:
    if _industry_pulse_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Industry Pulse snapshot is unavailable.",
        )
    return _industry_pulse_service


def _initialize_industry_momentum_service() -> IndustryMomentumService | None:
    """Load independent snapshot families without preventing API startup."""

    try:
        return IndustryMomentumService()
    except (OSError, ValueError):
        logger.warning(
            "Industry Momentum service initialization failed.",
            extra={"error_classification": "momentum_initialization_failure"},
        )
        return None


def _require_industry_momentum_service() -> IndustryMomentumService:
    if _industry_momentum_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Industry Momentum snapshots are unavailable.",
        )
    return _industry_momentum_service


_origins = _allowed_origins()
_industry_pulse_service = _initialize_industry_pulse_service()
_industry_momentum_service = _initialize_industry_momentum_service()

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=_allow_credentials(_origins),
)


@app.get("/openapi.json", tags=["system"])
def openapi_document() -> Response:
    """Expose the generated OpenAPI contract through the live application."""

    return Response(
        status_code=status.HTTP_200_OK,
        data=app.openapi(),
        media_type="application/json",
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


def _list_public_data_response() -> MetaPublicDataResponse:
    return MetaPublicDataResponse.from_definitions(public_dataset_catalog())


@app.get("/v1/meta/public-data", response_model=MetaPublicDataResponse, tags=["meta"])
def list_public_data_v1() -> MetaPublicDataResponse:
    """List the validated no-auth public-data readiness catalog."""

    return _list_public_data_response()


def _parse_signal_date(value: str | None, field_name: str) -> date | None:
    if value is None:
        return None
    if re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", value):
        value = f"{value}-01"
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} must use YYYY-MM or YYYY-MM-DD.",
        ) from exc
    if parsed.day != 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} must identify a calendar month.",
        )
    return parsed


def _validated_signal_filters(
    *,
    start: str | None,
    end: str | None,
    limit: int,
) -> tuple[date | None, date | None, int]:
    start_date = _parse_signal_date(start, "start")
    end_date = _parse_signal_date(end, "end")
    if start_date is not None and end_date is not None and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start date cannot be after end date.",
        )
    if limit < 1 or limit > 120:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="limit must be between 1 and 120.",
        )
    return start_date, end_date, limit


@app.get(
    "/v1/context/momentum",
    response_model=IndustryMomentumListResponse,
    tags=["context"],
)
def list_industry_momentum_v1(
    source_family: SourceFamily | None = Query(None),
    signal_type: SignalType | None = Query(None),
    series_id: str | None = Query(None),
    start: str | None = Query(None),
    end: str | None = Query(None),
    limit: int = Query(1, ge=1, le=120),
) -> IndustryMomentumListResponse:
    """List the verified registry and offline source-family snapshot summaries."""

    _validate_momentum_enum_filters(source_family, signal_type)
    service = _require_industry_momentum_service()
    _validated_signal_filters(start=start, end=end, limit=limit)
    if series_id is not None:
        registered = service.registry.by_series_id(series_id)
        if registered is not None and (
            (source_family is not None and registered.source_family != source_family)
            or (signal_type is not None and registered.signal_type != signal_type)
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=("series_id does not match the requested source_family or signal_type."),
            )
    mappings = service.list_mappings(
        source_family=source_family,
        signal_type=signal_type,
        series_id=series_id,
    )
    metadata = service.metadata["families"]
    summary_fields = (
        "dataset_id",
        "manifest_identity",
        "latest_release_period",
        "observation_range",
        "row_count",
        "series_count",
        "registry_version",
        "schema_version",
    )
    snapshot_summaries = {
        family: {field: payload.get(field) for field in summary_fields if field in payload}
        for family, payload in metadata.items()
        if isinstance(payload, dict) and (source_family is None or family == source_family)
    }
    availability = service.availability_summary()
    if source_family is not None:
        availability = {source_family: availability[source_family]}
    return IndustryMomentumListResponse(
        count=len(mappings),
        registry=[mapping.to_dict() for mapping in mappings],
        source_family_availability=availability,
        latest_snapshot_summaries=snapshot_summaries,
        limitations=[
            INDUSTRY_MOMENTUM_INTERPRETATION,
            INDUSTRY_MOMENTUM_COMPARISON_LIMITATION,
        ],
    )


@app.get(
    "/v1/context/momentum/{industry_code}",
    response_model=IndustryMomentumResponse,
    tags=["context"],
)
def get_industry_momentum_v1(
    industry_code: str,
    source_family: SourceFamily | None = Query(None),
    signal_type: SignalType | None = Query(None),
    series_id: str | None = Query(None),
    start: str | None = Query(None),
    end: str | None = Query(None),
    limit: int = Query(120, ge=1, le=120),
) -> IndustryMomentumResponse:
    """Return bounded multi-source context for one exact selected industry code."""

    _validate_momentum_enum_filters(source_family, signal_type)
    service = _require_industry_momentum_service()
    if re.fullmatch(r"[0-9]{6}", industry_code) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="industry_code must be an exact six-digit NAICS code.",
        )
    start_date, end_date, bounded_limit = _validated_signal_filters(
        start=start, end=end, limit=limit
    )
    if series_id is not None:
        registered = service.registry.by_series_id(series_id)
        if registered is not None and (
            registered.target_industry_code != industry_code
            or (source_family is not None and registered.source_family != source_family)
            or (signal_type is not None and registered.signal_type != signal_type)
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="series_id does not match the requested industry or family filters.",
            )
    result = service.for_industry_code(
        industry_code,
        source_family=source_family,
        signal_type=signal_type,
        series_id=series_id,
        start=start_date,
        end=end_date,
        limit=bounded_limit,
    )
    if result.availability == "unavailable":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Requested Industry Momentum snapshots are unavailable.",
        )
    return IndustryMomentumResponse.from_result(result)


def _validate_momentum_enum_filters(
    source_family: SourceFamily | None, signal_type: SignalType | None
) -> None:
    allowed_families = {"bls_ppi", "bls_ces", "fed_g17"}
    allowed_signals = {
        "producer_price_index",
        "employment_count",
        "average_weekly_hours",
        "average_hourly_earnings",
        "industrial_production_index",
        "capacity_index",
        "capacity_utilization_rate",
    }
    if source_family is not None and source_family not in allowed_families:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="source_family is unsupported.",
        )
    if signal_type is not None and signal_type not in allowed_signals:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="signal_type is unsupported.",
        )


@app.get(
    "/v1/context/signals",
    response_model=IndustryPulseListResponse,
    tags=["context"],
)
def list_industry_pulse_signals_v1(
    series_id: str | None = Query(None),
    start: str | None = Query(None),
    end: str | None = Query(None),
    limit: int = Query(1, ge=1, le=120),
) -> IndustryPulseListResponse:
    """List verified mappings with bounded snapshot-backed summaries."""

    service = _require_industry_pulse_service()
    start_date, end_date, bounded_limit = _validated_signal_filters(
        start=start, end=end, limit=limit
    )
    histories = [
        service.for_industry_code(
            mapping.industry_code,
            start=start_date,
            end=end_date,
            limit=bounded_limit,
        )
        for mapping in service.list_mappings(series_id=series_id)
    ]
    signals = [IndustryPulseResponse.from_history(history) for history in histories]
    return IndustryPulseListResponse(count=len(signals), signals=signals)


@app.get(
    "/v1/context/signals/{industry_code}",
    response_model=IndustryPulseResponse,
    tags=["context"],
)
def get_industry_pulse_signal_v1(
    industry_code: str,
    series_id: str | None = Query(None),
    start: str | None = Query(None),
    end: str | None = Query(None),
    limit: int = Query(120, ge=1, le=120),
) -> IndustryPulseResponse:
    """Return one exact six-digit Industry Pulse mapping and filtered history."""

    service = _require_industry_pulse_service()
    if re.fullmatch(r"[0-9]{6}", industry_code) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="industry_code must be an exact six-digit NAICS code.",
        )
    start_date, end_date, bounded_limit = _validated_signal_filters(
        start=start, end=end, limit=limit
    )
    mapping = service.registry.by_industry_code(industry_code)
    if series_id is not None and (mapping is None or mapping.series_id != series_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="series_id does not match the requested verified industry mapping.",
        )
    history = service.for_industry_code(
        industry_code,
        start=start_date,
        end=end_date,
        limit=bounded_limit,
    )
    return IndustryPulseResponse.from_history(history)


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
