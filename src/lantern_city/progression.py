from __future__ import annotations

from dataclasses import dataclass

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


def _clamp(score: int) -> int:
    return max(0, min(score, 100))
