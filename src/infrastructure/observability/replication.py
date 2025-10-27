"""Snapshot replication helpers for shipping observability archives to remote stores."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

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


__all__ = [
    "NullSnapshotReplicator",
    "S3SnapshotReplicator",
    "SnapshotReplicationError",
    "SnapshotReplicator",
    "build_snapshot_replicator",
    "create_s3_snapshot_replicator",
]
