from __future__ import annotations

from dataclasses import dataclass

from lantern_city.active_slice import (
    ActiveSlice,
    RequestIntent,
    build_active_slice,
    classify_request_intent,
)
from lantern_city.models import PlayerRequest
from lantern_city.store import SQLiteStore


@dataclass(frozen=True, slots=True)
class OrchestratedRequest:
    request: PlayerRequest
    intent: RequestIntent
    active_slice: ActiveSlice


def orchestrate_request(
    store: SQLiteStore,
    *,
    city_id: str,
    request: PlayerRequest,
) -> OrchestratedRequest:
    intent = classify_request_intent(request)
    active_slice = build_active_slice(store, city_id=city_id, request=request, intent=intent)
    return OrchestratedRequest(request=request, intent=intent, active_slice=active_slice)


__all__ = ["OrchestratedRequest", "RequestIntent", "classify_request_intent", "orchestrate_request"]
