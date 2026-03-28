from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from lantern_city.models import RuntimeModel
from lantern_city.serialization import deserialize_model, to_json_string

type CachePayload = dict[str, Any]
type CacheEntry = dict[str, Any]
LEGACY_CACHE_OBJECT_TYPE = "Unknown"


class SQLiteStore:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def save_object(self, obj: RuntimeModel) -> None:
        with self._connect() as connection:
            stored_created_at = self._load_object_created_at(connection, obj.type, obj.id)
            object_to_store = obj.model_copy(
                update={"created_at": stored_created_at or obj.created_at}
            )
            payload = to_json_string(object_to_store)
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
                ON CONFLICT(type, id) DO UPDATE SET
                    version = excluded.version,
                    created_at = world_objects.created_at,
                    updated_at = excluded.updated_at,
                    payload = excluded.payload
                """,
                (
                    object_to_store.id,
                    object_to_store.type,
                    object_to_store.version,
                    object_to_store.created_at,
                    object_to_store.updated_at,
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
        timestamp = self._current_timestamp()
        stored_created_at = created_at or updated_at or timestamp
        stored_updated_at = updated_at or created_at or timestamp

        with self._connect() as connection:
            persisted_created_at = self._load_cache_created_at(connection, cache_key)
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
                    created_at = cache_entries.created_at,
                    updated_at = excluded.updated_at,
                    payload = excluded.payload,
                    ttl_seconds = excluded.ttl_seconds
                """,
                (
                    cache_key,
                    object_type,
                    object_id,
                    version,
                    persisted_created_at or stored_created_at,
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

    def invalidate_cache_by_key_prefix(self, cache_key_prefix: str) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM cache_entries WHERE substr(cache_key, 1, length(?)) = ?",
                (cache_key_prefix, cache_key_prefix),
            )
        return cursor.rowcount

    def invalidate_cache_by_object(self, object_type: str, object_id: str) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM cache_entries WHERE object_type = ? AND object_id = ?",
                (object_type, object_id),
            )
        return cursor.rowcount

    def _initialize(self) -> None:
        with self._connect() as connection:
            self._migrate_world_objects_schema(connection)
            self._migrate_cache_entries_schema(connection)
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS world_objects (
                    id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY (type, id)
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
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_cache_entries_object_identity
                ON cache_entries(object_type, object_id)
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _load_object_created_at(
        self, connection: sqlite3.Connection, object_type: str, object_id: str
    ) -> str | None:
        row = connection.execute(
            "SELECT created_at FROM world_objects WHERE type = ? AND id = ?",
            (object_type, object_id),
        ).fetchone()
        return None if row is None else str(row["created_at"])

    def _load_cache_created_at(self, connection: sqlite3.Connection, cache_key: str) -> str | None:
        row = connection.execute(
            "SELECT created_at FROM cache_entries WHERE cache_key = ?",
            (cache_key,),
        ).fetchone()
        return None if row is None else str(row["created_at"])

    def _current_timestamp(self) -> str:
        return datetime.now(UTC).isoformat()

    def _migrate_world_objects_schema(self, connection: sqlite3.Connection) -> None:
        table_info = connection.execute("PRAGMA table_info(world_objects)").fetchall()
        if not table_info:
            return

        has_composite_primary_key = any(
            row["name"] == "type" and row["pk"] == 1 for row in table_info
        ) and any(row["name"] == "id" and row["pk"] == 2 for row in table_info)
        if has_composite_primary_key:
            return

        connection.execute("ALTER TABLE world_objects RENAME TO world_objects_legacy")
        connection.execute(
            """
            CREATE TABLE world_objects (
                id TEXT NOT NULL,
                type TEXT NOT NULL,
                version INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                payload TEXT NOT NULL,
                PRIMARY KEY (type, id)
            )
            """
        )
        connection.execute(
            """
            INSERT INTO world_objects (id, type, version, created_at, updated_at, payload)
            SELECT id, type, version, created_at, updated_at, payload
            FROM world_objects_legacy
            """
        )
        connection.execute("DROP TABLE world_objects_legacy")

    def _migrate_cache_entries_schema(self, connection: sqlite3.Connection) -> None:
        table_info = connection.execute("PRAGMA table_info(cache_entries)").fetchall()
        if not table_info:
            return

        has_object_type = any(row["name"] == "object_type" for row in table_info)
        object_type_not_null = any(
            row["name"] == "object_type" and row["notnull"] == 1 for row in table_info
        )
        if has_object_type and object_type_not_null:
            return

        connection.execute("ALTER TABLE cache_entries RENAME TO cache_entries_legacy")
        connection.execute(
            """
            CREATE TABLE cache_entries (
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

        if has_object_type:
            object_type_expression = f"COALESCE(object_type, '{LEGACY_CACHE_OBJECT_TYPE}')"
        else:
            object_type_expression = f"'{LEGACY_CACHE_OBJECT_TYPE}'"

        connection.execute(
            f"""
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
            SELECT
                cache_key,
                {object_type_expression},
                object_id,
                version,
                created_at,
                updated_at,
                payload,
                ttl_seconds
            FROM cache_entries_legacy
            """
        )
        connection.execute("DROP TABLE cache_entries_legacy")


__all__ = ["SQLiteStore"]
