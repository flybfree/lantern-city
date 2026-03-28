from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from lantern_city.models import RuntimeModel
from lantern_city.serialization import deserialize_model, to_json_string

type CachePayload = dict[str, Any]
type CacheEntry = dict[str, Any]


class SQLiteStore:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def save_object(self, obj: RuntimeModel) -> None:
        payload = to_json_string(obj)

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO world_objects (
                    id,
                    type,
                    version,
                    created_at,
                    updated_at,
                    payload
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    type = excluded.type,
                    version = excluded.version,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    payload = excluded.payload
                """,
                (
                    obj.id,
                    obj.type,
                    obj.version,
                    obj.created_at,
                    obj.updated_at,
                    payload,
                ),
            )

    def load_object(self, object_type: str, object_id: str) -> RuntimeModel | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM world_objects WHERE type = ? AND id = ?",
                (object_type, object_id),
            ).fetchone()

        if row is None:
            return None

        model = deserialize_model(row["payload"])
        if not isinstance(model, RuntimeModel):
            msg = f"Stored payload for {object_type}:{object_id} is not a runtime model"
            raise TypeError(msg)
        return model

    def list_objects(self, object_type: str) -> list[RuntimeModel]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM world_objects WHERE type = ? ORDER BY id",
                (object_type,),
            ).fetchall()

        objects: list[RuntimeModel] = []
        for row in rows:
            model = deserialize_model(row["payload"])
            if not isinstance(model, RuntimeModel):
                msg = f"Stored payload for type {object_type} is not a runtime model"
                raise TypeError(msg)
            objects.append(model)
        return objects

    def delete_object(self, object_type: str, object_id: str) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM world_objects WHERE type = ? AND id = ?",
                (object_type, object_id),
            )
        return cursor.rowcount

    def save_cache(
        self,
        cache_key: str,
        payload: CachePayload,
        *,
        version: int,
        object_type: str,
        object_id: str | None = None,
        ttl_seconds: int | None = None,
        created_at: str | None = None,
        updated_at: str | None = None,
    ) -> None:
        stored_created_at = created_at or updated_at or "now"
        stored_updated_at = updated_at or created_at or "now"

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO cache_entries (
                    cache_key,
                    object_type,
                    object_id,
                    version,
                    created_at,
                    updated_at,
                    payload,
                    ttl_seconds
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    object_type = excluded.object_type,
                    object_id = excluded.object_id,
                    version = excluded.version,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    payload = excluded.payload,
                    ttl_seconds = excluded.ttl_seconds
                """,
                (
                    cache_key,
                    object_type,
                    object_id,
                    version,
                    stored_created_at,
                    stored_updated_at,
                    json.dumps(payload, sort_keys=True),
                    ttl_seconds,
                ),
            )

    def load_cache(self, cache_key: str) -> CacheEntry | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    cache_key,
                    object_type,
                    object_id,
                    version,
                    created_at,
                    updated_at,
                    payload,
                    ttl_seconds
                FROM cache_entries
                WHERE cache_key = ?
                """,
                (cache_key,),
            ).fetchone()

        if row is None:
            return None

        return {
            "cache_key": row["cache_key"],
            "object_type": row["object_type"],
            "object_id": row["object_id"],
            "version": row["version"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "payload": json.loads(row["payload"]),
            "ttl_seconds": row["ttl_seconds"],
        }

    def invalidate_cache(self, prefix_or_id: str) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM cache_entries WHERE cache_key LIKE ? OR object_id = ?",
                (f"{prefix_or_id}%", prefix_or_id),
            )
        return cursor.rowcount

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS world_objects (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_world_objects_type ON world_objects(type)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    cache_key TEXT PRIMARY KEY,
                    object_type TEXT NOT NULL,
                    object_id TEXT,
                    version INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    ttl_seconds INTEGER
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_cache_entries_object_id ON cache_entries(object_id)"
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection


__all__ = ["SQLiteStore"]
