from __future__ import annotations

from lantern_city.models import ClueState

CLUE_RELIABILITY_STATES = (
    "solid",
    "credible",
    "uncertain",
    "distorted",
    "contradicted",
    "unstable",
)
CLUE_STATUS_STATES = ("new", "confirmed", "contradicted", "obsolete")

_SOURCE_BASELINE_RELIABILITY = {
    "physical": "credible",
    "document": "credible",
    "testimony": "uncertain",
    "composite": "solid",
}
_CLARIFICATION_UPGRADES = {
    "unstable": "uncertain",
    "distorted": "uncertain",
    "uncertain": "credible",
    "credible": "solid",
    "solid": "solid",
    "contradicted": "contradicted",
}


def create_clue(
    *,
    clue_id: str,
    source_type: str,
    source_id: str,
    clue_text: str,
    created_at: str,
    reliability: str | None = None,
    tags: list[str] | None = None,
    related_npc_ids: list[str] | None = None,
    related_case_ids: list[str] | None = None,
    related_district_ids: list[str] | None = None,
) -> ClueState:
    selected_reliability = reliability or _SOURCE_BASELINE_RELIABILITY.get(source_type, "uncertain")
    _validate_reliability(selected_reliability)
    return ClueState(
        id=clue_id,
        created_at=created_at,
        updated_at=created_at,
        source_type=source_type,
        source_id=source_id,
        clue_text=clue_text,
        reliability=selected_reliability,
        tags=list(tags or []),
        related_npc_ids=list(related_npc_ids or []),
        related_case_ids=list(related_case_ids or []),
        related_district_ids=list(related_district_ids or []),
        status="new",
    )


def clarify_clue(clue: ClueState, *, clarification_text: str, updated_at: str) -> ClueState:
    next_reliability = _CLARIFICATION_UPGRADES[clue.reliability]
    next_status = clue.status
    if next_reliability in {"credible", "solid"} and clue.status != "contradicted":
        next_status = "confirmed"
    return clue.model_copy(
        update={
            "clue_text": f"{clue.clue_text}\nClarification: {clarification_text}",
            "reliability": next_reliability,
            "status": next_status,
            "updated_at": updated_at,
        }
    )


def contradict_clue(clue: ClueState, *, contradiction_text: str, updated_at: str) -> ClueState:
    tags = list(clue.tags)
    if "contradicted" not in tags:
        tags.append("contradicted")
    return clue.model_copy(
        update={
            "clue_text": f"{clue.clue_text}\nContradiction: {contradiction_text}",
            "reliability": "contradicted",
            "status": "contradicted",
            "tags": tags,
            "updated_at": updated_at,
        }
    )


def set_clue_status(clue: ClueState, status: str, *, updated_at: str) -> ClueState:
    if status not in CLUE_STATUS_STATES:
        raise ValueError(f"Invalid clue status: {status}")
    return clue.model_copy(update={"status": status, "updated_at": updated_at})


def _validate_reliability(reliability: str) -> None:
    if reliability not in CLUE_RELIABILITY_STATES:
        raise ValueError(f"Invalid clue reliability: {reliability}")
