from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel

from lantern_city.models import RuntimeModel

RuntimeModelT = TypeVar("RuntimeModelT", bound=RuntimeModel)


MODEL_TYPES: dict[str, type[RuntimeModel]] = {
    model_cls.model_fields["type"].default: model_cls
    for model_cls in RuntimeModel.__subclasses__()
}


def to_json_payload(model: BaseModel) -> dict[str, object]:
    if not isinstance(model, BaseModel):
        msg = "serialize_model expected a Pydantic model"
        raise TypeError(msg)

    return model.model_dump(mode="json")


def to_json_string(model: BaseModel) -> str:
    return json.dumps(to_json_payload(model), sort_keys=True)


def serialize_model(model: BaseModel) -> str:
    return to_json_string(model)


def deserialize_model(
    payload: str | dict[str, object],
    *,
    model_cls: type[RuntimeModelT] | None = None,
) -> RuntimeModel | RuntimeModelT:
    normalized_payload = _normalize_payload(payload)

    if model_cls is None:
        runtime_type = normalized_payload.get("type")
        if not isinstance(runtime_type, str) or runtime_type not in MODEL_TYPES:
            msg = f"Unknown model type: {runtime_type!r}"
            raise ValueError(msg)
        model_cls = MODEL_TYPES[runtime_type]
    else:
        payload_type = normalized_payload.get("type")
        expected_type = model_cls.model_fields["type"].default
        if payload_type != expected_type:
            msg = (
                f"Payload type {payload_type!r} does not match requested model class "
                f"{model_cls.__name__!r}"
            )
            raise ValueError(msg)

    return model_cls.model_validate(normalized_payload)


def _normalize_payload(payload: str | dict[str, object]) -> dict[str, object]:
    if isinstance(payload, str):
        loaded = json.loads(payload)
        if not isinstance(loaded, dict):
            msg = "Serialized payload must decode to a JSON object"
            raise TypeError(msg)
        return loaded

    return payload


__all__ = [
    "deserialize_model",
    "serialize_model",
    "to_json_payload",
    "to_json_string",
]
