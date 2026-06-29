from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

try:  # pragma: no cover - optional dependency handling
    from botocore.session import get_session as _botocore_get_session
    from botocore.stub import ANY, Stubber
except Exception:  # pragma: no cover - exercised when botocore unavailable
    _botocore_get_session = None
    ANY = Stubber = None

from src.core import SnapshotRemoteStorageConfig
from src.extensions.manager import ExtensionManager, load_extensions
from src.infrastructure.observability.instrumentation import ObservabilityRegistry
from src.infrastructure.observability.replication import (
    NullSnapshotReplicator,
    SnapshotReplicationError,
    build_snapshot_replicator,
)
from src.infrastructure.observability.storage import ObservabilitySnapshot


class _DummySession:
    def __init__(self, client) -> None:
        self._client = client

    def create_client(self, service_name: str, **_: object):
        assert service_name == "s3"
        return self._client


def _make_snapshot(snapshot_id: str) -> ObservabilitySnapshot:
    return ObservabilitySnapshot(
        snapshot_id=snapshot_id,
        captured_at=datetime.now(UTC),
        payload={"events": {"total": 1}},
        metadata={"reason": "unit-test"},
    )


def _write_snapshot(path: Path, snapshot: ObservabilitySnapshot) -> None:
    payload = snapshot.to_dict()
    metadata = payload.get("metadata", {})
    if isinstance(metadata, dict):
        normalised = {
            key: sorted(value, key=str) if isinstance(value, set) else value
            for key, value in metadata.items()
        }
        payload["metadata"] = normalised
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_build_snapshot_replicator_returns_null_for_disabled() -> None:
    replicator = build_snapshot_replicator(None)
    assert isinstance(replicator, NullSnapshotReplicator)


@pytest.mark.skipif(
    _botocore_get_session is None or Stubber is None,
    reason="botocore not available",
)
def test_s3_replicator_uploads_snapshot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    assert _botocore_get_session is not None  # for mypy
    assert Stubber is not None
    session = _botocore_get_session()
    client = session.create_client(
        "s3", region_name="us-east-1", endpoint_url="https://example.com"
    )
    stubber = Stubber(client)
    stubber.add_response(
        "put_object",
        {},
        {
            "Bucket": "idiot-index-snapshots",
            "Key": "nightly/test-snap.json",
            "Body": ANY,
            "ContentType": "application/json",
            "Metadata": ANY,
        },
    )
    stubber.activate()
    monkeypatch.setattr(
        "src.infrastructure.observability.replication.get_session",
        lambda: _DummySession(client),
    )

    config = SnapshotRemoteStorageConfig(
        enabled=True,
        backend="s3",
        bucket="idiot-index-snapshots",
        prefix="nightly/",
        region="us-east-1",
        endpoint_url="https://example.com",
        access_key=None,
        secret_key=None,
        session_token=None,
        use_ssl=True,
        force_path_style=False,
        max_retries=2,
    )

    replicator = build_snapshot_replicator(config)

    snapshot = _make_snapshot("test-snap")
    snapshot_path = tmp_path / "test-snap.json"
    _write_snapshot(snapshot_path, snapshot)

    replicator.replicate(snapshot, snapshot_path)
    replicator.close()

    stubber.assert_no_pending_responses()


@pytest.mark.skipif(
    _botocore_get_session is None or Stubber is None,
    reason="botocore not available",
)
def test_s3_replicator_serialises_metadata(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    assert _botocore_get_session is not None
    assert Stubber is not None
    session = _botocore_get_session()
    client = session.create_client(
        "s3", region_name="us-east-1", endpoint_url="https://example.com"
    )
    stubber = Stubber(client)
    monkeypatch.setattr(
        "src.infrastructure.observability.replication.get_session",
        lambda: _DummySession(client),
    )

    snapshot = ObservabilitySnapshot(
        snapshot_id="meta-snap",
        captured_at=datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC),
        payload={"events": {"total": 1}},
        metadata={
            "Reason": "unit-test",
            "Complex Data": {"nested": True},
            "List": [1, 2],
            "Boolean": False,
            "Set": {"beta", "alpha"},
        },
    )

    expected_metadata = {
        "snapshot-id": snapshot.snapshot_id,
        "captured-at": snapshot.captured_at.isoformat(),
        "reason": "unit-test",
        "complex-data": json.dumps({"nested": True}),
        "list": json.dumps([1, 2]),
        "boolean": "False",
        "set": json.dumps(["alpha", "beta"]),
    }

    stubber.add_response(
        "put_object",
        {},
        {
            "Bucket": "idiot-index-snapshots",
            "Key": "meta/meta-snap.json",
            "Body": ANY,
            "ContentType": "application/json",
            "Metadata": expected_metadata,
        },
    )
    stubber.activate()

    config = SnapshotRemoteStorageConfig(
        enabled=True,
        backend="s3",
        bucket="idiot-index-snapshots",
        prefix="meta/",
        region="us-east-1",
        endpoint_url="https://example.com",
        access_key=None,
        secret_key=None,
        session_token=None,
        use_ssl=True,
        force_path_style=False,
        max_retries=2,
    )

    replicator = build_snapshot_replicator(config)

    snapshot_path = tmp_path / "meta-snap.json"
    _write_snapshot(snapshot_path, snapshot)

    replicator.replicate(snapshot, snapshot_path)

    stubber.assert_no_pending_responses()


@pytest.mark.skipif(
    _botocore_get_session is None or Stubber is None,
    reason="botocore not available",
)
def test_s3_replicator_raises_on_client_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assert _botocore_get_session is not None
    assert Stubber is not None
    session = _botocore_get_session()
    client = session.create_client(
        "s3", region_name="us-east-1", endpoint_url="https://example.com"
    )
    stubber = Stubber(client)
    stubber.add_client_error(
        "put_object",
        service_error_code="AccessDenied",
        service_message="denied",
        http_status_code=403,
        expected_params={
            "Bucket": "idiot-index-snapshots",
            "Key": "test-snap.json",
            "Body": ANY,
            "ContentType": "application/json",
            "Metadata": ANY,
        },
    )
    stubber.activate()
    monkeypatch.setattr(
        "src.infrastructure.observability.replication.get_session",
        lambda: _DummySession(client),
    )

    config = SnapshotRemoteStorageConfig(
        enabled=True,
        backend="s3",
        bucket="idiot-index-snapshots",
        prefix="",
        region="us-east-1",
        endpoint_url="https://example.com",
        access_key=None,
        secret_key=None,
        session_token=None,
        use_ssl=True,
        force_path_style=False,
        max_retries=1,
    )

    replicator = build_snapshot_replicator(config)
    snapshot = _make_snapshot("test-snap")
    snapshot_path = tmp_path / "test-snap.json"
    _write_snapshot(snapshot_path, snapshot)

    with pytest.raises(SnapshotReplicationError):
        replicator.replicate(snapshot, snapshot_path)

    stubber.assert_no_pending_responses()


def test_gcs_replicator_uploads_snapshot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from src.infrastructure.observability import replication as module

    class StubBlob:
        def __init__(self) -> None:
            self.metadata: dict[str, Any] = {}
            self.calls: list[tuple[str, str, float | None]] = []

        def upload_from_filename(
            self,
            filename: str,
            *,
            content_type: str,
            timeout: float | None = None,
        ) -> None:
            self.calls.append((filename, content_type, timeout))

    class StubBucket:
        def __init__(self) -> None:
            self.requests: list[str] = []
            self.last_blob: StubBlob | None = None

        def blob(self, key: str) -> StubBlob:
            self.requests.append(key)
            blob = StubBlob()
            self.last_blob = blob
            return blob

    class StubGCSClient:
        def __init__(self, project: str | None = None) -> None:
            self.project = project
            self.bucket_calls: list[str] = []
            self.closed = False
            self.buckets: dict[str, StubBucket] = {}

        @classmethod
        def from_service_account_json(cls, *_: Any, project: str | None = None) -> StubGCSClient:
            return cls(project=project)

        @classmethod
        def from_service_account_info(cls, *_: Any, project: str | None = None) -> StubGCSClient:
            return cls(project=project)

        def bucket(self, name: str) -> StubBucket:
            self.bucket_calls.append(name)
            return self.buckets.setdefault(name, StubBucket())

        def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(module, "_HAS_GCS", True)
    monkeypatch.setattr(module, "gcs_storage", type("Storage", (), {"Client": StubGCSClient}))
    monkeypatch.setattr(module, "GoogleAPIError", RuntimeError)

    config = SnapshotRemoteStorageConfig(
        enabled=True,
        backend="gcs",
        bucket="idiot-index-snapshots",
        prefix="remote/",
        region=None,
        endpoint_url=None,
        access_key=None,
        secret_key=None,
        session_token=None,
        use_ssl=True,
        force_path_style=False,
        max_retries=2,
        options={"project": "test", "timeout_seconds": 15},
    )

    replicator = build_snapshot_replicator(config)
    snapshot = _make_snapshot("gcs-snap")
    snapshot_path = tmp_path / "gcs-snap.json"
    _write_snapshot(snapshot_path, snapshot)

    replicator.replicate(snapshot, snapshot_path)
    replicator.close()

    client = cast(Any, replicator).client
    assert isinstance(client, StubGCSClient)
    assert client.project == "test"
    assert client.bucket_calls == ["idiot-index-snapshots"]
    assert client.closed is True

    bucket = client.buckets["idiot-index-snapshots"]
    assert bucket.requests == ["remote/gcs-snap.json"]
    assert bucket.last_blob is not None
    assert bucket.last_blob.calls[0] == (str(snapshot_path), "application/json", 15.0)


def test_build_snapshot_replicator_handles_missing_botocore(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = SnapshotRemoteStorageConfig(
        enabled=True,
        backend="s3",
        bucket="idiot-index-snapshots",
        prefix="",
        region=None,
        endpoint_url=None,
        access_key=None,
        secret_key=None,
        session_token=None,
        use_ssl=True,
        force_path_style=False,
        max_retries=1,
    )

    monkeypatch.setattr("src.infrastructure.observability.replication._HAS_BOTOCORE", False)
    replicator = build_snapshot_replicator(config)
    assert isinstance(replicator, NullSnapshotReplicator)


def test_azure_replicator_uploads_snapshot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from src.infrastructure.observability import replication as module

    class StubBlobClient:
        def __init__(self) -> None:
            self.uploads: list[tuple[bytes, bool, dict[str, Any], str, float | None]] = []

        def upload_blob(
            self,
            data: bytes,
            *,
            overwrite: bool,
            metadata: Mapping[str, Any],
            content_type: str,
            timeout: float | None = None,
        ) -> None:
            self.uploads.append((data, overwrite, dict(metadata), content_type, timeout))

    class StubAzureClient:
        def __init__(
            self,
            *,
            connection_string: str | None = None,
            account_url: str | None = None,
            credential: Any | None = None,
        ) -> None:
            self.connection_string = connection_string
            self.account_url = account_url
            self.credential = credential
            self.closed = False
            self._blob_client = StubBlobClient()
            self.last_request: tuple[str, str] | None = None

        @classmethod
        def from_connection_string(cls, connection_string: str) -> StubAzureClient:
            return cls(connection_string=connection_string)

        def get_blob_client(self, *, container: str, blob: str) -> StubBlobClient:
            self.last_request = (container, blob)
            return self._blob_client

        def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(module, "_HAS_AZURE", True)

    def _factory(**kwargs: Any) -> StubAzureClient:
        return StubAzureClient(**kwargs)

    monkeypatch.setattr(
        module,
        "BlobServiceClient",
        type(
            "BlobServiceClient",
            (),
            {
                "from_connection_string": staticmethod(
                    lambda conn: StubAzureClient(connection_string=conn)
                ),
                "__call__": staticmethod(_factory),
            },
        ),
    )

    config = SnapshotRemoteStorageConfig(
        enabled=True,
        backend="azure-blob",
        bucket="snapshots",
        prefix="nightly/",
        region=None,
        endpoint_url=None,
        access_key=None,
        secret_key=None,
        session_token=None,
        use_ssl=True,
        force_path_style=False,
        max_retries=1,
        options={
            "connection_string": "UseDevelopmentStorage=true",
            "timeout_seconds": 12,
        },
    )

    replicator = build_snapshot_replicator(config)
    snapshot = _make_snapshot("azure-snap")
    snapshot_path = tmp_path / "azure-snap.json"
    _write_snapshot(snapshot_path, snapshot)

    replicator.replicate(snapshot, snapshot_path)
    replicator.close()

    client = cast(Any, replicator).client
    assert isinstance(client, StubAzureClient)
    assert client.connection_string == "UseDevelopmentStorage=true"
    assert client.last_request == ("snapshots", "nightly/azure-snap.json")
    assert client.closed is True

    uploads = client._blob_client.uploads
    assert uploads[0][1] is True
    assert uploads[0][3] == "application/json"
    assert uploads[0][4] == 12.0
    assert uploads[0][2]["snapshot-id"] == "azure-snap"


def test_debug_plugin_replicator_writes_local(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OBSERVABILITY_SNAPSHOT_DIR", str(tmp_path))
    config = SnapshotRemoteStorageConfig(
        enabled=True,
        backend="plugin:debug",
        bucket=None,
        prefix="",
        region=None,
        endpoint_url=None,
        access_key=None,
        secret_key=None,
        session_token=None,
        use_ssl=True,
        force_path_style=False,
        max_retries=0,
        options={"path": str(tmp_path / "remote-debug")},
    )

    replicator = build_snapshot_replicator(config)
    snapshot = _make_snapshot("debug")
    snapshot_path = tmp_path / "debug.json"
    _write_snapshot(snapshot_path, snapshot)

    replicator.replicate(snapshot, snapshot_path)

    replicated = tmp_path / "remote-debug" / "debug.json"
    assert replicated.exists()


def test_snapshot_replication_instrumentation_records_events() -> None:
    registry = ObservabilityRegistry()
    manager = load_extensions(ExtensionManager(), ["src.extensions.builtins.snapshot_replication"])
    manager.apply_instrumentation_extensions(registry)

    registry.record_event(
        "observability.snapshot.replication",
        attributes={"backend": "plugin:debug"},
        status="success",
        duration=0.2,
    )

    counter = registry.metrics.counters["idiot_index_snapshot_replications_total"]
    samples = dict(counter.samples())
    assert samples[("success", "plugin:debug")] == 1.0

    gauge = registry.metrics.gauges["idiot_index_snapshot_replication_age_seconds"]
    gauge_samples = dict(gauge.samples())
    assert gauge_samples[()] == 0.0

    health = registry._health_checks["snapshot_replication"]()
    assert health.status == "pass"
    assert "plugin:debug" in health.details.get("backend", "")


def test_null_replicator_is_noop(tmp_path: Path) -> None:
    replicator = NullSnapshotReplicator()
    snapshot = _make_snapshot("noop")
    snapshot_path = tmp_path / "noop.json"
    _write_snapshot(snapshot_path, snapshot)

    replicator.replicate(snapshot, snapshot_path)
    replicator.close()


def test_replicator_close_without_client_close_method() -> None:
    class NoCloseClient:
        pass

    from src.infrastructure.observability.replication import (
        AzureBlobSnapshotReplicator,
        GCSnapshotReplicator,
        S3SnapshotReplicator,
    )

    S3SnapshotReplicator(bucket="b", prefix="", client=NoCloseClient(), max_attempts=1).close()
    GCSnapshotReplicator(bucket="b", prefix="", client=NoCloseClient(), max_attempts=1).close()
    AzureBlobSnapshotReplicator(
        container="c", prefix="", client=NoCloseClient(), max_attempts=1
    ).close()


def test_gcs_replicator_raises_after_retries(tmp_path: Path) -> None:
    from src.infrastructure.observability.replication import GCSnapshotReplicator

    class FailingBlob:
        metadata: dict[str, Any] = {}

        def upload_from_filename(self, *_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError("upload failed")

    class FailingBucket:
        def blob(self, _key: str) -> FailingBlob:
            return FailingBlob()

    class FailingClient:
        def bucket(self, _name: str) -> FailingBucket:
            return FailingBucket()

    replicator = GCSnapshotReplicator(
        bucket="bucket",
        prefix="",
        client=FailingClient(),
        max_attempts=2,
    )

    snapshot = _make_snapshot("gcs-fail")
    snapshot_path = tmp_path / "gcs-fail.json"
    _write_snapshot(snapshot_path, snapshot)

    with pytest.raises(SnapshotReplicationError):
        replicator.replicate(snapshot, snapshot_path)


def test_azure_replicator_raises_after_retries(tmp_path: Path) -> None:
    from src.infrastructure.observability.replication import AzureBlobSnapshotReplicator

    class FailingBlobClient:
        def upload_blob(self, *_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError("azure upload failed")

    class FailingAzureClient:
        def get_blob_client(self, *, container: str, blob: str) -> FailingBlobClient:
            return FailingBlobClient()

    replicator = AzureBlobSnapshotReplicator(
        container="snapshots",
        prefix="",
        client=FailingAzureClient(),
        max_attempts=2,
    )

    snapshot = _make_snapshot("azure-fail")
    snapshot_path = tmp_path / "azure-fail.json"
    _write_snapshot(snapshot_path, snapshot)

    with pytest.raises(SnapshotReplicationError):
        replicator.replicate(snapshot, snapshot_path)


def test_create_azure_replicator_falls_back_without_connection_settings(monkeypatch) -> None:
    from src.infrastructure.observability import replication as module

    monkeypatch.setattr(module, "_HAS_AZURE", True)
    monkeypatch.setattr(module, "BlobServiceClient", object())

    config = SnapshotRemoteStorageConfig(
        enabled=True,
        backend="azure-blob",
        bucket="snapshots",
        prefix="",
        region=None,
        endpoint_url=None,
        access_key=None,
        secret_key=None,
        session_token=None,
        use_ssl=True,
        force_path_style=False,
        max_retries=1,
        options={},
    )

    replicator = module.create_azure_snapshot_replicator(config)
    assert isinstance(replicator, NullSnapshotReplicator)


def test_build_gcs_client_invalid_json_and_constructor_failure(monkeypatch) -> None:
    from src.infrastructure.observability import replication as module

    class RaisingClient:
        def __init__(self, **_kwargs: Any) -> None:
            raise RuntimeError("boom")

        @classmethod
        def from_service_account_json(cls, *_args: Any, **_kwargs: Any):
            raise RuntimeError("boom")

        @classmethod
        def from_service_account_info(cls, *_args: Any, **_kwargs: Any):
            raise RuntimeError("boom")

    monkeypatch.setattr(module, "gcs_storage", type("Storage", (), {"Client": RaisingClient}))

    invalid_json_cfg = SnapshotRemoteStorageConfig(
        enabled=True,
        backend="gcs",
        bucket="bucket",
        prefix="",
        region=None,
        endpoint_url=None,
        access_key=None,
        secret_key=None,
        session_token=None,
        use_ssl=True,
        force_path_style=False,
        max_retries=1,
        options={"credentials_json": "{invalid"},
    )
    assert module._build_gcs_client(invalid_json_cfg) is None

    ctor_failure_cfg = replace(invalid_json_cfg, options={"project": "x"})
    assert module._build_gcs_client(ctor_failure_cfg) is None


def test_replication_helper_serialisation_and_timeout_normalisation() -> None:
    from src.infrastructure.observability import replication as module

    serialised = module._serialise_metadata(
        {
            "": "skip",
            "Set Value": {"b", "a"},
            "Map": {"bad": object()},
            "Seq": [1, 2],
        }
    )
    assert "" not in serialised
    assert "set-value" in serialised
    assert serialised["seq"] == "[1, 2]"
    assert "map" in serialised

    assert module._normalise_prefix(None) == ""
    assert module._normalise_prefix(" /nightly// ") == "nightly/"
    assert module._coerce_timeout(None, backend="gcs") is None
    assert module._coerce_timeout("bad", backend="gcs") is None
    assert module._coerce_timeout(0, backend="gcs") is None
    assert module._coerce_timeout("1.5", backend="gcs") == 1.5


def test_build_snapshot_replicator_with_custom_manager() -> None:
    class CustomReplicator:
        def replicate(self, snapshot: ObservabilitySnapshot, path: Path) -> None:
            return None

        def close(self) -> None:
            return None

    class ManagerStub:
        def __init__(self, result: object | None) -> None:
            self.result = result

        def build_replication_backend(self, config: SnapshotRemoteStorageConfig):
            return self.result

    config = SnapshotRemoteStorageConfig(
        enabled=True,
        backend="plugin:custom",
        bucket=None,
        prefix="",
        region=None,
        endpoint_url=None,
        access_key=None,
        secret_key=None,
        session_token=None,
        use_ssl=True,
        force_path_style=False,
        max_retries=1,
    )

    custom = CustomReplicator()
    resolved = build_snapshot_replicator(config, manager=cast(Any, ManagerStub(custom)))
    assert resolved is custom

    fallback = build_snapshot_replicator(config, manager=cast(Any, ManagerStub(None)))
    assert isinstance(fallback, NullSnapshotReplicator)
