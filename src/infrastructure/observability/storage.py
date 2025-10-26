"""File-backed storage for observability registry snapshots."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final
from uuid import uuid4

__all__ = [
    "ObservabilitySnapshot",
    "SnapshotStorage",
    "build_snapshot_id",
    "load_snapshot_from_file",
]

_SNAPSHOT_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9_-]+$")


@dataclass(frozen=True)
class ObservabilitySnapshot:
    """Container representing a captured observability digest."""

    snapshot_id: str
    captured_at: datetime
    payload: Mapping[str, Any]
    metadata: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Return a serialisable payload for persistence."""

        return {
            "snapshot_id": self.snapshot_id,
            "captured_at": self.captured_at.isoformat(),
            "payload": dict(self.payload),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ObservabilitySnapshot:
        """Hydrate a snapshot from a dictionary payload."""

        try:
            captured_at_raw = data["captured_at"]
            snapshot_id = str(data["snapshot_id"])
            payload = data.get("payload", {})
            metadata = data.get("metadata", {})
        except KeyError as exc:  # pragma: no cover - defensive
            raise ValueError(f"Snapshot payload missing key: {exc}") from exc

        captured_at = _parse_datetime(captured_at_raw)
        return cls(
            snapshot_id=snapshot_id,
            captured_at=captured_at,
            payload=dict(payload),
            metadata=dict(metadata),
        )


class SnapshotStorage:
    """Persist :class:`ObservabilitySnapshot` records to a directory."""

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._base_dir.mkdir(parents=True, exist_ok=True)

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    def save(self, snapshot: ObservabilitySnapshot) -> Path:
        """Write a snapshot to disk atomically and return its path."""

        path = self._path_for(snapshot.snapshot_id)
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(snapshot.to_dict(), indent=2), encoding="utf-8")
        os.replace(tmp_path, path)
        return path

    def list(self) -> list[ObservabilitySnapshot]:
        """Return all stored snapshots sorted chronologically."""

        snapshots: list[ObservabilitySnapshot] = []
        for path in sorted(self._base_dir.glob("*.json")):
            loaded = load_snapshot_from_file(path)
            snapshots.append(loaded)
        snapshots.sort(key=lambda snap: snap.captured_at)
        return snapshots

    def get(self, snapshot_id: str) -> ObservabilitySnapshot:
        """Return a stored snapshot matching ``snapshot_id``."""

        path = self._path_for(snapshot_id)
        if not path.exists():
            raise FileNotFoundError(f"Snapshot '{snapshot_id}' not found in {self._base_dir}")
        return load_snapshot_from_file(path)

    def path_for(self, snapshot_id: str) -> Path:
        """Return the canonical path for ``snapshot_id`` without touching disk."""

        return self._path_for(snapshot_id)

    def latest(self) -> ObservabilitySnapshot | None:
        """Return the most recent snapshot if any exist."""

        snapshots = self.list()
        if not snapshots:
            return None
        return snapshots[-1]

    def delete(self, snapshot_id: str) -> None:
        """Remove a stored snapshot if it exists."""

        path = self._path_for(snapshot_id)
        if path.exists():
            path.unlink()

    def _path_for(self, snapshot_id: str) -> Path:
        normalised = _normalise_snapshot_id(snapshot_id)
        return self._base_dir / f"{normalised}.json"


def load_snapshot_from_file(path: Path) -> ObservabilitySnapshot:
    """Load a snapshot from ``path``."""

    data = json.loads(path.read_text(encoding="utf-8"))
    return ObservabilitySnapshot.from_dict(data)


def build_snapshot_id(captured_at: datetime | None = None) -> str:
    """Create a filesystem-safe snapshot identifier."""

    when = captured_at or datetime.now(UTC)
    return f"{when.strftime('%Y%m%dT%H%M%S%fZ')}-{uuid4().hex[:8]}"


def _parse_datetime(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        return raw.astimezone(UTC)
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw).astimezone(UTC)
        except ValueError as exc:  # pragma: no cover - defensive
            raise ValueError(f"Invalid datetime string: {raw}") from exc
    raise TypeError(f"Unsupported datetime payload: {raw!r}")


def _normalise_snapshot_id(snapshot_id: str) -> str:
    value = str(snapshot_id)
    if not value:
        raise ValueError("Snapshot identifier cannot be empty.")
    if not _SNAPSHOT_ID_PATTERN.fullmatch(value):
        raise ValueError(
            "Snapshot identifiers must match ^[A-Za-z0-9_-]+$ to prevent path traversal."
        )
    return value
