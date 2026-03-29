from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from lantern_city.models import PlayerProgressState, ScoreTier

TRACKS = (
    "lantern_understanding",
    "access",
    "reputation",
    "leverage",
    "city_impact",
    "clue_mastery",
)
LEARNING_TRACKS = {"lantern_understanding", "clue_mastery"}
DEFAULT_STARTING_SCORES = {
    "lantern_understanding": 18,
    "access": 10,
    "reputation": 12,
    "leverage": 5,
    "city_impact": 2,
    "clue_mastery": 20,
}
TIER_LABELS = {
    "lantern_understanding": {
        1: "Untrained",
        2: "Informed",
        3: "Literate",
        4: "Expert",
        5: "Deep Expert",
    },
    "access": {1: "Public", 2: "Restricted", 3: "Trusted", 4: "Cleared", 5: "Secret"},
    "reputation": {1: "Wary", 2: "Known", 3: "Respected", 4: "Trusted", 5: "Established"},
    "leverage": {1: "None", 2: "Limited", 3: "Useful", 4: "Strong", 5: "Dominant"},
    "city_impact": {1: "Minimal", 2: "Local", 3: "District", 4: "Citywide", 5: "Structural"},
    "clue_mastery": {1: "Basic", 2: "Competent", 3: "Sharp", 4: "Insightful", 5: "Forensic"},
}
_UNLOCKS = {
    "lantern_understanding": {
        1: ["Notice obvious light anomalies when scenes surface them."],
        2: [
            "Ask whether an outage began before a disappearance.",
            "Receive clearer clue notes for lantern-linked evidence.",
        ],
        3: [
            "Compare witness reliability by location.",
            "Treat some uncertain clues as likely lantern-distorted.",
        ],
        4: ["Separate neglect, sabotage, and ritual alteration more reliably."],
        5: ["Read deep lantern patterns and identify engineered city-scale distortions."],
    },
    "access": {
        1: ["Use ordinary public routes and services."],
        2: ["Enter some restricted spaces through recognized channels."],
        3: ["Reach trusted spaces where wider decisions are made."],
        4: ["Use cleared institutional routes with less friction."],
        5: ["Reach secret archives and hidden administrative spaces."],
    },
    "reputation": {
        1: ["People are wary and require proof."],
        2: ["Locals recognize your name and some work."],
        3: ["Relevant NPCs offer more direct trust."],
        4: ["Trusted standing softens social barriers."],
        5: ["You are established and city memory carries your reputation."],
    },
    "leverage": {
        1: ["Little usable pressure."],
        2: ["Reopen blocked conversations with favors or debts."],
        3: ["Convert contradiction chains into useful leverage."],
        4: ["Strong leverage changes negotiations materially."],
        5: ["Dominant leverage can force major concessions."],
    },
    "city_impact": {
        1: ["Most actions stay local."],
        2: ["Your choices visibly affect a place or block."],
        3: ["District outcomes become more available."],
        4: ["Citywide consequences enter play."],
        5: ["Structural changes to the city become possible."],
    },
    "clue_mastery": {
        1: ["Read basic clue signals."],
        2: ["Connect contradictions with competent rigor."],
        3: ["Extract sharper conclusions from mixed evidence."],
        4: ["Interpret layered clue webs insightfully."],
        5: ["Operate at near-forensic reliability."],
    },
}
_CLUE_INTERPRETATION_REQUIREMENTS = {
    "credible": 1,
    "solid": 1,
    "uncertain": 3,
    "distorted": 4,
    "unstable": 4,
    "contradicted": 1,
}
_CITY_SCOPE_REQUIREMENTS = {
    "local": {"city_impact": 1, "access": 1},
    "district": {"city_impact": 3, "access": 3},
    "citywide": {"city_impact": 4, "access": 4},
    "structural": {"city_impact": 5, "access": 5},
}
_INFORMAL_ACCESS_REQUIREMENTS = {
    "public": 1,
    "restricted": 2,
    "trusted": 3,
}
_PRESSURE_EVIDENCE_REQUIREMENTS = {
    "rumor": 4,
    "documented": 3,
    "contradiction_chain": 3,
    "hard_proof": 2,
}


@dataclass(frozen=True)
class ProgressChange:
    track: str
    reason: str
    amount: int
    old_score: int
    new_score: int
    old_tier: str
    new_tier: str


def starting_progress_state(
    *,
    progress_id: str,
    created_at: str,
    updated_at: str,
) -> PlayerProgressState:
    payload = {
        track: ScoreTier(score=score, tier=get_tier_label(track, get_tier(score)))
        for track, score in DEFAULT_STARTING_SCORES.items()
    }
    return PlayerProgressState(
        id=progress_id,
        created_at=created_at,
        updated_at=updated_at,
        **payload,
    )


def get_tier(score: int) -> int:
    score = _clamp(score)
    if score <= 19:
        return 1
    if score <= 39:
        return 2
    if score <= 59:
        return 3
    if score <= 79:
        return 4
    return 5


def get_tier_label(track: str, tier: int) -> str:
    return TIER_LABELS[track][tier]


def apply_progress_change(
    progress: PlayerProgressState,
    *,
    track: str,
    amount: int,
    reason: str,
    updated_at: str,
    allow_learning_loss: bool = False,
) -> tuple[PlayerProgressState, ProgressChange]:
    if track not in TRACKS:
        raise ValueError(f"Unknown progression track: {track}")
    if amount < 0 and track in LEARNING_TRACKS and not allow_learning_loss:
        raise ValueError(
            f"{track} is a stable learning track and does not lose progress by default"
        )

    current = getattr(progress, track)
    new_score = _clamp(current.score + amount)
    new_tier = get_tier_label(track, get_tier(new_score))
    updated = progress.model_copy(
        update={
            track: ScoreTier(score=new_score, tier=new_tier),
            "updated_at": updated_at,
        }
    )
    return updated, ProgressChange(
        track=track,
        reason=reason,
        amount=amount,
        old_score=current.score,
        new_score=new_score,
        old_tier=current.tier,
        new_tier=new_tier,
    )


def current_unlocks(track: str, score: int) -> list[str]:
    tier = get_tier(score)
    unlocks: list[str] = []
    for current_tier in range(1, tier + 1):
        unlocks.extend(_UNLOCKS[track][current_tier])
    return unlocks


def describe_track(progress: PlayerProgressState, track: str) -> str:
    score_tier = getattr(progress, track)
    unlock_preview = current_unlocks(track, score_tier.score)[-1]
    name = track.replace("_", " ").title()
    return f"{name}: {score_tier.score} ({score_tier.tier}) - {unlock_preview}"


def can_interpret_lantern_clue(
    progress: PlayerProgressState,
    *,
    clue_reliability: Literal[
        "solid", "credible", "uncertain", "distorted", "unstable", "contradicted"
    ],
    requires_location_comparison: bool = False,
) -> bool:
    required_tier = _CLUE_INTERPRETATION_REQUIREMENTS[clue_reliability]
    if requires_location_comparison:
        required_tier = max(required_tier, 3)
    return _track_tier(progress, "lantern_understanding") >= required_tier


def can_convert_clues_to_leverage(
    progress: PlayerProgressState,
    *,
    contradiction_count: int,
    target_kind: Literal["person", "institution"] = "person",
) -> bool:
    clue_mastery_tier = _track_tier(progress, "clue_mastery")
    if contradiction_count < 2 or clue_mastery_tier < 2:
        return False
    if target_kind == "institution":
        return _track_tier(progress, "access") >= 3
    return True


def can_pursue_city_impact_opportunity(
    progress: PlayerProgressState,
    *,
    scope: Literal["local", "district", "citywide", "structural"],
) -> bool:
    requirements = _CITY_SCOPE_REQUIREMENTS[scope]
    return (
        _track_tier(progress, "city_impact") >= requirements["city_impact"]
        and _track_tier(progress, "access") >= requirements["access"]
    )


def can_use_informal_access(
    progress: PlayerProgressState,
    *,
    required_access: Literal["public", "restricted", "trusted"],
    district_or_faction_familiar: bool = False,
) -> bool:
    required_tier = _INFORMAL_ACCESS_REQUIREMENTS[required_access]
    access_tier = _track_tier(progress, "access")
    reputation_tier = _track_tier(progress, "reputation")
    if access_tier >= required_tier:
        return True
    if required_access == "restricted":
        if district_or_faction_familiar and reputation_tier >= 1:
            return True
        return reputation_tier >= 3
    if required_access == "trusted":
        return district_or_faction_familiar and reputation_tier >= 4
    return False


def can_pressure_npc(
    progress: PlayerProgressState,
    *,
    evidence_strength: Literal["rumor", "documented", "contradiction_chain", "hard_proof"],
    institutional: bool = False,
) -> bool:
    leverage_tier = _track_tier(progress, "leverage")
    required_tier = _PRESSURE_EVIDENCE_REQUIREMENTS[evidence_strength]
    if leverage_tier < required_tier:
        return False
    if institutional:
        return (
            evidence_strength in {"contradiction_chain", "hard_proof"}
            and _track_tier(progress, "access") >= 3
        )
    return True


def can_reopen_blocked_conversation(
    progress: PlayerProgressState,
    *,
    has_contradiction_chain: bool,
) -> bool:
    reputation_tier = _track_tier(progress, "reputation")
    leverage_tier = _track_tier(progress, "leverage")
    if reputation_tier >= 4:
        return True
    return leverage_tier >= 3 and has_contradiction_chain


def _track_tier(progress: PlayerProgressState, track: str) -> int:
    return get_tier(getattr(progress, track).score)


def _clamp(score: int) -> int:
    return max(0, min(score, 100))
