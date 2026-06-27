"""Snapshot replication helpers for shipping observability archives to remote stores."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Protocol, runtime_checkable

from src.core import SnapshotRemoteStorageConfig

from .storage import ObservabilitySnapshot

LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from src.extensions.manager import ExtensionManager

try:  # pragma: no cover - import fallback exercised in tests
    from botocore.config import Config as BotoConfig
    from botocore.exceptions import BotoCoreError, ClientError
    from botocore.session import get_session

    _HAS_BOTOCORE = True
except Exception:  # pragma: no cover - botocore optional at runtime
    BotoConfig = None
    ClientError = BotoCoreError = Exception

    def get_session() -> Any:
        raise ImportError("botocore is required for S3 snapshot replication")

    _HAS_BOTOCORE = False


GoogleAPIError: type[BaseException]

try:  # pragma: no cover - optional dependency
    from google.api_core.exceptions import GoogleAPIError as GoogleAPIErrorType
    from google.cloud import storage as gcs_storage

    _HAS_GCS = True
    GoogleAPIError = GoogleAPIErrorType
except Exception:  # pragma: no cover - gcs optional
    GoogleAPIError = Exception
    gcs_storage = None
    _HAS_GCS = False


try:  # pragma: no cover - optional dependency
    from azure.core.exceptions import AzureError
    from azure.storage.blob import BlobServiceClient

    _HAS_AZURE = True
except Exception:  # pragma: no cover - azure optional
    AzureError = Exception
    BlobServiceClient = None
    _HAS_AZURE = False


class SnapshotReplicationError(RuntimeError):
    """Raised when a snapshot fails to replicate to remote storage."""


@runtime_checkable
class SnapshotReplicator(Protocol):
    """Protocol describing snapshot replication behaviour."""

    def replicate(self, snapshot: ObservabilitySnapshot, path: Path) -> None:
        """Ship ``snapshot`` stored at ``path`` to a remote backend."""

    def close(self) -> None:
        """Release any resources held by the replicator."""


@dataclass(slots=True)
class NullSnapshotReplicator:
    """No-op replicator used when remote shipping is disabled."""

    def replicate(self, snapshot: ObservabilitySnapshot, path: Path) -> None:  # noqa: D401
        return None

    def close(self) -> None:  # noqa: D401 - interface requirement
        return None


@dataclass(slots=True)
class S3SnapshotReplicator:
    """Replicate snapshots to an S3-compatible object store."""

    uri_scheme: ClassVar[str] = "s3"
    bucket: str
    prefix: str
    client: Any
    max_attempts: int

    def replicate(self, snapshot: ObservabilitySnapshot, path: Path) -> None:
        key = self._object_key(snapshot.snapshot_id)
        metadata = _serialise_metadata(snapshot.metadata)
        metadata["snapshot-id"] = snapshot.snapshot_id
        metadata["captured-at"] = snapshot.captured_at.isoformat()
        try:
            body = path.read_bytes()
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=body,
                ContentType="application/json",
                Metadata=metadata,
            )
            LOGGER.debug(
                "Replicated observability snapshot to remote storage",
                extra={
                    "bucket": self.bucket,
                    "key": key,
                    "size_bytes": len(body),
                },
            )
        except (BotoCoreError, ClientError, OSError) as exc:  # pragma: no cover - error path
            LOGGER.warning(
                "Failed to replicate snapshot to remote storage",
                extra={"bucket": self.bucket, "key": key},
                exc_info=exc,
            )
            raise SnapshotReplicationError(str(exc)) from exc

    def close(self) -> None:
        close = getattr(self.client, "close", None)
        if callable(close):
            close()

    def _object_key(self, snapshot_id: str) -> str:
        if self.prefix:
            return f"{self.prefix}{snapshot_id}.json"
        return f"{snapshot_id}.json"


@dataclass(slots=True)
class GCSnapshotReplicator:
    """Replicate snapshots to a Google Cloud Storage bucket."""

    uri_scheme: ClassVar[str] = "gs"
    bucket: str
    prefix: str
    client: Any
    max_attempts: int
    location: str | None = None
    timeout_seconds: float | None = None

    def replicate(self, snapshot: ObservabilitySnapshot, path: Path) -> None:
        key = self._object_key(snapshot.snapshot_id)
        metadata = _serialise_metadata(snapshot.metadata)
        metadata["snapshot-id"] = snapshot.snapshot_id
        metadata["captured-at"] = snapshot.captured_at.isoformat()
        attempts = max(1, self.max_attempts)
        last_error: BaseException | None = None
        for attempt in range(1, attempts + 1):
            try:
                bucket = self.client.bucket(self.bucket)
                blob = bucket.blob(key)
                blob.metadata = metadata
                blob.upload_from_filename(
                    str(path),
                    content_type="application/json",
                    timeout=self.timeout_seconds,
                )
            except (GoogleAPIError, OSError, AttributeError) as exc:
                last_error = exc
                log_extra = {
                    "bucket": self.bucket,
                    "key": key,
                    "attempt": attempt,
                }
                if attempt == attempts:
                    LOGGER.warning(
                        "Failed to replicate snapshot to GCS", extra=log_extra, exc_info=exc
                    )
                else:
                    LOGGER.debug("Retrying GCS snapshot replication", extra=log_extra, exc_info=exc)
            else:
                LOGGER.debug(
                    "Replicated observability snapshot to GCS",
                    extra={
                        "bucket": self.bucket,
                        "key": key,
                        "size_bytes": path.stat().st_size,
                    },
                )
                return
        if last_error is not None:
            raise SnapshotReplicationError(str(last_error)) from last_error

    def close(self) -> None:
        close = getattr(self.client, "close", None)
        if callable(close):
            close()

    def _object_key(self, snapshot_id: str) -> str:
        if self.prefix:
            return f"{self.prefix}{snapshot_id}.json"
        return f"{snapshot_id}.json"


@dataclass(slots=True)
class AzureBlobSnapshotReplicator:
    """Replicate snapshots to Azure Blob Storage."""

    uri_scheme: ClassVar[str] = "azure"
    container: str
    prefix: str
    client: Any
    max_attempts: int
    timeout_seconds: float | None = None

    def replicate(self, snapshot: ObservabilitySnapshot, path: Path) -> None:
        blob_name = self._blob_name(snapshot.snapshot_id)
        metadata = _serialise_metadata(snapshot.metadata)
        metadata["snapshot-id"] = snapshot.snapshot_id
        metadata["captured-at"] = snapshot.captured_at.isoformat()
        body = path.read_bytes()
        attempts = max(1, self.max_attempts)
        last_error: BaseException | None = None
        for attempt in range(1, attempts + 1):
            try:
                blob_client = self.client.get_blob_client(container=self.container, blob=blob_name)
                blob_client.upload_blob(
                    body,
                    overwrite=True,
                    metadata=metadata,
                    content_type="application/json",
                    timeout=self.timeout_seconds,
                )
            except (AzureError, OSError, AttributeError) as exc:
                last_error = exc
                log_extra = {
                    "container": self.container,
                    "blob": blob_name,
                    "attempt": attempt,
                }
                if attempt == attempts:
                    LOGGER.warning(
                        "Failed to replicate snapshot to Azure Blob",
                        extra=log_extra,
                        exc_info=exc,
                    )
                else:
                    LOGGER.debug(
                        "Retrying Azure Blob snapshot replication",
                        extra=log_extra,
                        exc_info=exc,
                    )
            else:
                LOGGER.debug(
                    "Replicated observability snapshot to Azure Blob",
                    extra={
                        "container": self.container,
                        "blob": blob_name,
                        "size_bytes": len(body),
                    },
                )
                return
        if last_error is not None:
            raise SnapshotReplicationError(str(last_error)) from last_error

    def close(self) -> None:
        close = getattr(self.client, "close", None)
        if callable(close):
            close()

    def _blob_name(self, snapshot_id: str) -> str:
        if self.prefix:
            return f"{self.prefix}{snapshot_id}.json"
        return f"{snapshot_id}.json"


def build_snapshot_replicator(
    config: SnapshotRemoteStorageConfig | None,
    *,
    manager: ExtensionManager | None = None,
) -> SnapshotReplicator:
    """Construct a replicator based on remote configuration."""

    if not config or not config.enabled:
        return NullSnapshotReplicator()

    resolved_manager = manager
    if resolved_manager is None:
        try:  # pragma: no cover - defensive lazy import
            from src.extensions.manager import get_extension_manager
        except Exception:  # pragma: no cover - extension bootstrap issues
            resolved_manager = None
        else:
            try:
                resolved_manager = get_extension_manager()
            except Exception:  # pragma: no cover - defensive
                resolved_manager = None

    if resolved_manager is not None:
        replicator = resolved_manager.build_replication_backend(config)
        if replicator is not None:
            return replicator

    backend = (config.backend or "").lower()
    if backend == "s3":
        return create_s3_snapshot_replicator(config)

    if backend == "gcs":
        return create_gcs_snapshot_replicator(config)

    if backend in {"azure", "azure-blob", "azure_blob"}:
        return create_azure_snapshot_replicator(config)

    if backend.startswith("plugin:"):
        LOGGER.warning(
            "No replication extension matched plugin backend; falling back to local persistence.",
            extra={"backend": config.backend},
        )
        return NullSnapshotReplicator()

    LOGGER.warning(
        "Unsupported snapshot replication backend requested",
        extra={"backend": config.backend},
    )
    return NullSnapshotReplicator()


def create_s3_snapshot_replicator(
    config: SnapshotRemoteStorageConfig,
) -> SnapshotReplicator:
    """Return an S3-backed replicator or a null fallback when misconfigured."""

    if not _HAS_BOTOCORE:
        LOGGER.warning(
            "Remote snapshot backend requires botocore; falling back to local-only persistence."
        )
        return NullSnapshotReplicator()

    if not config.bucket:
        LOGGER.error("Remote snapshot shipping enabled without bucket; disabling replicator.")
        return NullSnapshotReplicator()

    session = get_session()
    retries = max(1, config.max_retries)
    boto_config = None
    if BotoConfig is not None:
        boto_config = BotoConfig(retries={"max_attempts": retries, "mode": "standard"})
        if config.force_path_style:
            boto_config = boto_config.merge(BotoConfig(s3={"addressing_style": "path"}))
    client_kwargs: dict[str, Any] = {
        "region_name": config.region,
        "use_ssl": config.use_ssl,
        "endpoint_url": config.endpoint_url,
        "config": boto_config,
    }
    if config.access_key and config.secret_key:
        client_kwargs["aws_access_key_id"] = config.access_key
        client_kwargs["aws_secret_access_key"] = config.secret_key
    if config.session_token:
        client_kwargs["aws_session_token"] = config.session_token

    client: Any = session.create_client(
        "s3", **{k: v for k, v in client_kwargs.items() if v is not None}
    )
    prefix = _normalise_prefix(config.prefix)
    return S3SnapshotReplicator(
        bucket=config.bucket,
        prefix=prefix,
        client=client,
        max_attempts=retries,
    )


def create_gcs_snapshot_replicator(
    config: SnapshotRemoteStorageConfig,
) -> SnapshotReplicator:
    """Return a GCS-backed replicator or a null fallback when unavailable."""

    if not _HAS_GCS or gcs_storage is None:
        LOGGER.warning(
            "Remote snapshot backend 'gcs' requested but google-cloud-storage is unavailable; falling back to local persistence."
        )
        return NullSnapshotReplicator()

    if not config.bucket:
        LOGGER.error(
            "GCS replication enabled without OBSERVABILITY_SNAPSHOT_GCS_BUCKET; disabling replicator."
        )
        return NullSnapshotReplicator()

    client = _build_gcs_client(config)
    if client is None:
        return NullSnapshotReplicator()

    attempts = max(1, config.max_retries)
    prefix = _normalise_prefix(config.prefix)
    location = None
    options = config.options or {}
    if options.get("location"):
        location = str(options.get("location"))
    timeout_seconds = _coerce_timeout(options.get("timeout_seconds"), backend="gcs")
    return GCSnapshotReplicator(
        bucket=config.bucket,
        prefix=prefix,
        client=client,
        max_attempts=attempts,
        location=location,
        timeout_seconds=timeout_seconds,
    )


def create_azure_snapshot_replicator(
    config: SnapshotRemoteStorageConfig,
) -> SnapshotReplicator:
    """Return an Azure Blob replicator or a null fallback when unavailable."""

    if not _HAS_AZURE or BlobServiceClient is None:
        LOGGER.warning(
            "Remote snapshot backend 'azure-blob' requested but azure-storage-blob is unavailable; falling back to local persistence."
        )
        return NullSnapshotReplicator()

    container = config.bucket
    if not container:
        LOGGER.error(
            "Azure Blob replication enabled without OBSERVABILITY_SNAPSHOT_AZURE_CONTAINER; disabling replicator."
        )
        return NullSnapshotReplicator()

    options = config.options or {}
    connection_string = options.get("connection_string")
    account_url = options.get("account_url")
    credential = options.get("credential") or options.get("sas_token")
    timeout_seconds = _coerce_timeout(options.get("timeout_seconds"), backend="azure-blob")

    try:
        if connection_string:
            client = BlobServiceClient.from_connection_string(str(connection_string))
        elif account_url:
            client = BlobServiceClient(account_url=str(account_url), credential=credential)
        else:
            LOGGER.warning(
                "Azure Blob replication configured without connection string or account URL; falling back to local persistence."
            )
            return NullSnapshotReplicator()
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning(
            "Failed to initialise Azure Blob client; falling back to local persistence.",
            exc_info=exc,
        )
        return NullSnapshotReplicator()

    attempts = max(1, config.max_retries)
    prefix = _normalise_prefix(config.prefix)
    return AzureBlobSnapshotReplicator(
        container=container,
        prefix=prefix,
        client=client,
        max_attempts=attempts,
        timeout_seconds=timeout_seconds,
    )


def _build_gcs_client(config: SnapshotRemoteStorageConfig) -> Any | None:
    """Initialise a GCS client using configuration options."""

    storage = gcs_storage
    if storage is None:
        return None

    options = config.options or {}
    project = options.get("project")
    credentials_file = options.get("credentials_file")
    credentials_json = options.get("credentials_json")

    try:
        if credentials_file:
            return storage.Client.from_service_account_json(str(credentials_file), project=project)
        if credentials_json:
            try:
                payload = json.loads(str(credentials_json))
            except json.JSONDecodeError as exc:  # pragma: no cover - defensive
                LOGGER.error(
                    "OBSERVABILITY_SNAPSHOT_GCS_CREDENTIALS_JSON is invalid JSON; disabling GCS replication.",
                    exc_info=exc,
                )
                return None
            return storage.Client.from_service_account_info(payload, project=project)
        return storage.Client(project=project)
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning(
            "Failed to initialise GCS client; falling back to local persistence.",
            exc_info=exc,
        )
        return None


def _serialise_metadata(metadata: Mapping[str, Any]) -> dict[str, str]:
    serialised: dict[str, str] = {}
    for key, value in metadata.items():
        safe_key = str(key).strip().lower().replace(" ", "-")
        if not safe_key:
            continue
        try:
            if isinstance(value, Mapping):
                serialised[safe_key[:128]] = json.dumps(value)
            elif isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
                serialised[safe_key[:128]] = json.dumps(list(value))
            elif isinstance(value, Set):
                serialised[safe_key[:128]] = json.dumps(sorted(value, key=lambda item: str(item)))
            else:
                serialised[safe_key[:128]] = str(value)
        except (TypeError, ValueError):
            serialised[safe_key[:128]] = str(value)
    return serialised


def _normalise_prefix(prefix: str | None) -> str:
    if not prefix:
        return ""
    value = prefix.strip().strip("/")
    if not value:
        return ""
    return f"{value}/"


def _coerce_timeout(value: Any, *, backend: str) -> float | None:
    """Normalise timeout values from configuration payloads."""

    if value is None:
        return None
    try:
        candidate = float(value)
    except (TypeError, ValueError):
        LOGGER.warning(
            "Ignoring invalid timeout configuration for snapshot replication backend",
            extra={"backend": backend, "timeout": value},
        )
        return None
    if candidate <= 0:
        LOGGER.warning(
            "Ignoring non-positive timeout for snapshot replication backend",
            extra={"backend": backend, "timeout": candidate},
        )
        return None
    return candidate


__all__ = [
    "NullSnapshotReplicator",
    "S3SnapshotReplicator",
    "GCSnapshotReplicator",
    "AzureBlobSnapshotReplicator",
    "SnapshotReplicationError",
    "SnapshotReplicator",
    "build_snapshot_replicator",
    "create_s3_snapshot_replicator",
    "create_gcs_snapshot_replicator",
    "create_azure_snapshot_replicator",
]
