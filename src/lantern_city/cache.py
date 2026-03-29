from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lantern_city.models import RuntimeModel
from lantern_city.store import SQLiteStore

type JSONDict = dict[str, Any]


@dataclass(frozen=True, slots=True)
class CacheDependency:
    object_type: str
    object_id: str
    version: int

    @classmethod
    def from_model(cls, model: RuntimeModel) -> CacheDependency:
        return cls(object_type=model.type, object_id=model.id, version=model.version)

    def to_payload(self) -> JSONDict:
        return {
            "object_type": self.object_type,
            "object_id": self.object_id,
            "version": self.version,
        }


class StoreBackedCache:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def set(
        self,
        *,
        key: str,
        payload: JSONDict,
        owner: RuntimeModel | CacheDependency,
        dependencies: list[RuntimeModel | CacheDependency],
    ) -> None:
        owner_ref = _as_dependency(owner)
        dependency_refs = [_as_dependency(dependency) for dependency in dependencies]
        stored_payload = {
            "value": payload,
            "dependencies": [dependency.to_payload() for dependency in dependency_refs],
        }
        self.store.save_cache(
            key,
            stored_payload,
            version=owner_ref.version,
            object_type=owner_ref.object_type,
            object_id=owner_ref.object_id,
        )

    def get(self, key: str) -> JSONDict | None:
        entry = self.store.load_cache(key)
        if entry is None:
            return None

        dependencies = [
            CacheDependency(
                object_type=str(item["object_type"]),
                object_id=str(item["object_id"]),
                version=int(item["version"]),
            )
            for item in entry["payload"].get("dependencies", [])
        ]
        if not self._dependencies_match(dependencies):
            self.store.invalidate_cache_by_key_prefix(key)
            return None
        value = entry["payload"].get("value")
        if not isinstance(value, dict):
            return None
        return value

    def _dependencies_match(self, dependencies: list[CacheDependency]) -> bool:
        for dependency in dependencies:
            current_object = self.store.load_object(dependency.object_type, dependency.object_id)
            if current_object is None:
                return False
            if current_object.version != dependency.version:
                return False
        return True


def build_cache_key(namespace: str, object_type: str, object_id: str, artifact_name: str) -> str:
    return ":".join([namespace, object_type, object_id, artifact_name])


def _as_dependency(value: RuntimeModel | CacheDependency) -> CacheDependency:
    if isinstance(value, CacheDependency):
        return value
    return CacheDependency.from_model(value)


__all__ = ["CacheDependency", "StoreBackedCache", "build_cache_key"]
