"""Compact tone and style guardrails from the Lantern City Writing Bible.

These strings are injected into LLM generation prompts to enforce consistent
voice and prevent drift toward generic fantasy, purple prose, or melodrama.
"""
from __future__ import annotations

# ── Core tone block ──────────────────────────────────────────────────────────
# Appended to system prompts for all generators.

TONE_SYSTEM_BLOCK = (
    "Writing style: atmospheric but not indulgent. "
    "Poetic phrasing is allowed; hidden meaning is not. "
    "Quietly eerie, not spectacular. "
    "Civic and institutional detail over mythic grandeur. "
    "Emotion through behavior and implication, not declaration. "
    "The setting is a rain-soaked port city of offices, shrines, routes, and records."
)

# ── Common avoidance rules ───────────────────────────────────────────────────
# Appended to user prompts across all generators.

COMMON_AVOID_RULES = """\
- avoid purple prose and abstract noun piles
- avoid generic fantasy diction: ancient evil, arcane power, destiny, chosen one, spectral, cosmic terror
- avoid clichés: "shadows danced", "hauntingly beautiful", "a chill ran down the spine", \
"the truth was darker than expected", "soul" used generically, "whispers in the dark" without a material cause
- do not invent metaphysical explanations beyond the provided context
- do not let mood obscure what the player can observe or do next"""

# ── NPC dialogue rules ───────────────────────────────────────────────────────
# Added to NPC response prompts.

NPC_DIALOGUE_RULES = """\
- 1 to 4 sentences per turn; no monologues unless a major reveal or confrontation justifies it
- reveal through framing, omission, emphasis, and deflection — not through exposition
- clerks and officials: procedural diction, certainty-words even under uncertainty, \
no emotional overstatement ("The record is inconsistent, not absent.")
- shrine workers: practical with occasional symbolic framing, notice condition and pattern \
("The light was wrong before the complaint reached the desk.")
- workers and locals: plain speech, describe what they saw or heard or carried, \
resist official-sounding statements if afraid ("I took the key where I was told. That\'s all.")
- do not make every NPC equally literary, equally cryptic, or equally noir-hardboiled"""

# ── Scene narration rules ────────────────────────────────────────────────────
# Added to location inspection prompts.

SCENE_NARRATION_RULES = """\
- place the player somewhere specific, surface what is unusual, leave visible hooks for action
- 1 to 2 strong sensory anchors drawn from: stone, brass, ink, rain, soot, oil, damp, glass, rope, ash
- evidence-first on clue-adjacent details: state what is observable before suggesting implication
- do not open with long backstory, weather chains, or proper noun introductions without anchor"""

# ── District prose rules ─────────────────────────────────────────────────────
# Added to district entry prose prompts.

DISTRICT_PROSE_RULES = """\
- 2 to 3 short sentences; communicate the district's social logic through atmosphere
- Old Quarter: damp, careful, documentary, memory-heavy, quietly compromised — \
stone, paper, ink, ledgers, shrines, latches, narrow courtyards
- Lantern Ward: bright, ordered, administratively calm, curated, watchful — \
polished surfaces, counters, approved routes, ceremonial lighting
- no backstory dumps; no new proper nouns without immediate anchor; \
no long atmospheric chain that ends with no actionable hook"""


__all__ = [
    "TONE_SYSTEM_BLOCK",
    "COMMON_AVOID_RULES",
    "NPC_DIALOGUE_RULES",
    "SCENE_NARRATION_RULES",
    "DISTRICT_PROSE_RULES",
]
