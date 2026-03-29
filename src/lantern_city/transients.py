"""Transient NPC encounters — ephemeral background figures who appear on district entry.

Transients are not persisted, carry no clue knowledge, and do not advance cases.
They add texture and can produce small player progress effects.
Encounter probability per district entry: ~30%.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class TransientEncounter:
    archetype: str
    narrative: str
    effect_track: str | None  # None = flavor only
    effect_amount: int        # 0 = no mechanical effect
    effect_reason: str


# Each entry: (archetype_label, [narrative variants], effect_track, effect_amount)
# effect_track=None means flavor-only; amount=0 means no change even if track is set.
_DISTRICT_POOL: dict[str, list[tuple[str, list[str], str | None, int]]] = {
    "district_old_quarter": [
        (
            "archive petitioner",
            [
                "A petitioner waiting on a records dispute watches you pass with tired eyes. "
                "She says nothing. The case she is holding is thick.",
                "A man in clerk's dress is comparing two ledger pages near the archive door. "
                "He glances up, then back down. Whatever he is checking, he does not find it.",
            ],
            None,
            0,
        ),
        (
            "maintenance runner",
            [
                "A maintenance runner crosses your path without acknowledgment, then slows "
                "slightly after passing — checking your reflection in a window.",
                "A young runner with a service key rack pauses at a corner, looks toward "
                "the archive, and takes a different route when he notices you.",
            ],
            "reputation",
            -1,
        ),
        (
            "records copyist",
            [
                "A copyist leaving the archive nods in passing — the brief, neutral "
                "acknowledgment of someone who has seen many people come through.",
                "A woman with ink on her sleeve holds the archive door open for you, "
                "then moves off without comment.",
            ],
            "reputation",
            1,
        ),
        (
            "district resident",
            [
                "An older man sits on a low step, reading something. He does not look up. "
                "The notice board behind him has a new sheet over an older one.",
                "A resident pauses at a posted notice, reads it carefully, and walks away "
                "faster than she arrived.",
            ],
            None,
            0,
        ),
    ],
    "district_lantern_ward": [
        (
            "compliance observer",
            [
                "A compliance officer with a certification ledger makes a note as you enter "
                "the district. She does not approach, but the note exists.",
                "A watch aide near the Ceremonial Walk holds eye contact for a moment too long. "
                "He writes something when you look away.",
            ],
            "reputation",
            -2,
        ),
        (
            "permit applicant",
            [
                "A permit applicant waiting outside the regulation office greets you with "
                "careful civility — the tone of someone practising neutral behavior.",
                "A junior administrator holds a door for you and offers a brief, "
                "procedurally correct nod.",
            ],
            "reputation",
            1,
        ),
        (
            "ceremonial attendant",
            [
                "A ceremonial attendant is adjusting a lantern post arrangement. "
                "He does not acknowledge you, but the work is very deliberate.",
                "Two attendants in civic dress pass without speaking. "
                "One of them glances at your hands.",
            ],
            None,
            0,
        ),
        (
            "lamp inspector",
            [
                "A lamp inspector is working her way down the Ceremonial Walk with "
                "a measuring rod and a maintenance form. She notes your presence "
                "as a matter of professional habit.",
                "An inspector with a lantern check kit pauses near you, compares "
                "something on a clipboard to a fixture above, and moves on.",
            ],
            "reputation",
            -1,
        ),
    ],
    "district_the_docks": [
        (
            "cargo hauler",
            [
                "A hauler with a load balanced on his shoulder steps around you without "
                "breaking stride. He does not ask why you are here.",
                "A cargo hauler setting down a crate looks up briefly, makes a judgment, "
                "and goes back to work.",
            ],
            None,
            0,
        ),
        (
            "route runner",
            [
                "A route runner offers you a shortcut to the pier landing with practiced "
                "casualness, then watches to confirm you take it.",
                "A runner passes you, then slows at the next corner to observe "
                "where you are heading. Route knowledge moves quickly here.",
            ],
            "reputation",
            -1,
        ),
        (
            "manifest checker",
            [
                "A dock clerk with a cargo manifest does not look up as you pass. "
                "The manifest is longer than it needs to be for what is on the pier.",
                "A checker comparing crate marks against a register glances at you "
                "once with the expression of someone counting things.",
            ],
            None,
            0,
        ),
        (
            "off-duty dockworker",
            [
                "An off-duty worker leaning against a bollard nods at you — "
                "the neutral acknowledgment of someone who recognizes an outsider and "
                "has decided to let it pass.",
                "A dockworker eating a late meal on a cargo step watches you with "
                "the kind of attention that costs nothing and remembers everything.",
            ],
            "reputation",
            1,
        ),
    ],
    "district_market_spires": [
        (
            "guild compliance observer",
            [
                "A guild compliance officer with a certification seal and a small ledger "
                "logs your presence in the district. It is a standard procedure.",
                "A compliance aide near the guild hall entrance notes you with the "
                "practiced efficiency of someone tracking foot traffic.",
            ],
            "reputation",
            -2,
        ),
        (
            "commercial trader",
            [
                "A trader reviewing a price board glances at you with brief professional "
                "assessment — categorizing you by what you might need.",
                "A merchant packing up a stall pauses to see if you are a buyer. "
                "When it becomes clear you are not, she returns to her work without comment.",
            ],
            None,
            0,
        ),
        (
            "records certification clerk",
            [
                "A certification clerk passing between offices nods with the minimal "
                "courtesy of someone who is on a deadline.",
                "A clerk in trade district dress holds a stack of certified documents "
                "and moves around you with practiced efficiency.",
            ],
            "reputation",
            1,
        ),
        (
            "information broker",
            [
                "A figure near the records office makes eye contact and then "
                "deliberately looks elsewhere — the signal of someone deciding "
                "whether you are worth approaching.",
                "A quiet man near the trade floor perimeter has been in the same "
                "position long enough to have seen everyone who entered today.",
            ],
            "reputation",
            -1,
        ),
    ],
    "district_salt_barrens": [
        (
            "scavenger",
            [
                "A scavenger working the edge of the abandoned works watches you "
                "from a distance and does not approach.",
                "A figure with a salvage sack stops moving when you enter view, "
                "waits, then resumes working at a greater distance.",
            ],
            None,
            0,
        ),
        (
            "material broker",
            [
                "A material broker with a route ledger makes a note as you pass — "
                "not hostile, just recording. Movement through the Barrens gets tracked "
                "by people the city does not employ.",
                "A broker comparing scrap grades pauses to assess you with the same "
                "practiced eye she uses on the material.",
            ],
            "reputation",
            -1,
        ),
        (
            "departing worker",
            [
                "Someone was clearly leaving before you arrived. "
                "They finish leaving faster.",
                "A worker collecting tools stops, looks at you, and decides "
                "to collect them somewhere else.",
            ],
            None,
            0,
        ),
        (
            "long-term resident",
            [
                "A figure sitting against a stripped lantern mount does not react to "
                "your arrival. They have seen enough arrivals to distinguish the kinds.",
                "An older woman sorting salvage near the yard boundary acknowledges "
                "you with a nod that means: I see you, you are not a threat yet, "
                "that is the limit of my interest.",
            ],
            "reputation",
            1,
        ),
    ],
    "district_underways": [
        (
            "maintenance crew rotation",
            [
                "A two-person maintenance rotation passes through the junction. "
                "One of them takes note of your presence. Route wardens talk.",
                "A maintenance crew with contracted tools moves through without "
                "stopping. One worker marks something on the route board as they leave.",
            ],
            "reputation",
            -2,
        ),
        (
            "shrine technical worker",
            [
                "A Shrine technical corps worker pauses at a conduit junction, "
                "assesses you with the careful attention of someone who knows "
                "this space well and knows you are new to it.",
                "A technical worker with a shrine maintenance kit stops her work "
                "to establish who you are before resuming.",
            ],
            "reputation",
            -1,
        ),
        (
            "contracted route worker",
            [
                "A contracted worker on a permit rotation moves through without "
                "acknowledgment — you are either authorized to be here or you will "
                "become someone else's problem.",
                "A route worker consulting a junction map glances up, confirms you "
                "are not on the maintenance schedule, and keeps working.",
            ],
            None,
            0,
        ),
    ],
}

_ENCOUNTER_CHANCE = 0.30


def roll_encounter(
    district_id: str,
    *,
    rng: random.Random | None = None,
) -> TransientEncounter | None:
    """Return a transient encounter for the given district, or None.

    Uses *rng* if provided (useful for deterministic tests).
    """
    r = rng or random.Random()
    if r.random() > _ENCOUNTER_CHANCE:
        return None
    pool = _DISTRICT_POOL.get(district_id)
    if not pool:
        return None
    archetype, narratives, track, amount = r.choice(pool)
    narrative = r.choice(narratives)
    return TransientEncounter(
        archetype=archetype,
        narrative=narrative,
        effect_track=track,
        effect_amount=amount,
        effect_reason=f"Transient encounter: {archetype} in {district_id}.",
    )


__all__ = ["TransientEncounter", "roll_encounter"]
