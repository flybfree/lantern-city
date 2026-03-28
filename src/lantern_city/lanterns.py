from __future__ import annotations

from lantern_city.models import ClueState, LanternCityModel

_WITNESS_STEPS = ("unusable", "unstable", "uncertain", "credible", "strong")
_CLUE_DEGRADATION = {
    "solid": "credible",
    "credible": "uncertain",
    "uncertain": "unstable",
    "distorted": "unstable",
    "unstable": "unstable",
    "contradicted": "contradicted",
}
_SOURCE_DOMAIN_MAP = {
    "physical": "physical",
    "document": "records",
    "testimony": "testimony",
    "composite": "composite",
}


class LanternRuleProfile(LanternCityModel):
    state: str
    missingness: str = "none"
    altered_target_domain: str | None = None
    altered_effect_mode: str | None = None
    altered_scope: str | None = None
    altered_owner_or_suspected_controller: str | None = None


def assess_witness_confidence(
    profile: LanternRuleProfile,
    *,
    domain: str = "testimony",
    direct_experience: bool = False,
    outside_zone: bool = False,
    corroborated: bool = False,
    lantern_understanding_tier: int = 1,
    motive_to_conceal: bool = False,
) -> str:
    step = _base_witness_step(profile, domain=domain)
    if direct_experience:
        step += 1
    if outside_zone:
        step += 1
    if corroborated:
        step += 1
    if lantern_understanding_tier >= 2:
        step += 1
    if motive_to_conceal:
        step -= 1
    if profile.missingness == "high":
        step -= 1
    elif profile.missingness == "medium":
        step -= 0
    return _WITNESS_STEPS[_clamp(step, 0, len(_WITNESS_STEPS) - 1)]


def assess_memory(profile: LanternRuleProfile) -> str:
    if profile.state == "bright" and profile.missingness in {"none", "low"}:
        return "anchored"
    if profile.state == "altered":
        return "selectively distorted"
    if profile.state == "extinguished" or profile.missingness == "high":
        return "fragmented"
    if profile.state == "flickering" or profile.missingness == "medium":
        return "drifting"
    return "strained"


def assess_access(
    profile: LanternRuleProfile,
    *,
    required_access: str,
    formal: bool,
    leverage_tier: int = 1,
    reputation_tier: int = 1,
) -> str:
    if profile.state == "bright":
        return "open"
    if profile.state == "dim":
        if formal:
            return "open" if required_access == "public" else "contested"
        return "open" if leverage_tier >= 2 or reputation_tier >= 2 else "contested"
    if profile.state == "flickering":
        if formal:
            return "contested" if required_access == "public" else "blocked"
        return "contested" if leverage_tier >= 2 else "blocked"
    if profile.state == "extinguished":
        if formal:
            return "blocked"
        return "contested" if leverage_tier >= 2 else "blocked"
    if profile.state == "altered":
        if profile.altered_target_domain == "access":
            return "blocked" if formal else "contested"
        return "contested"
    raise ValueError(f"Unsupported lantern state: {profile.state}")


def apply_lantern_to_clue(
    clue: ClueState,
    profile: LanternRuleProfile,
    *,
    updated_at: str,
) -> ClueState:
    if clue.reliability == "contradicted":
        return clue.model_copy(update={"updated_at": updated_at})

    domain = _SOURCE_DOMAIN_MAP.get(clue.source_type, clue.source_type)
    reliability = clue.reliability

    if profile.state == "dim" and clue.source_type == "testimony":
        reliability = _degrade(reliability, 1)
    elif profile.state == "flickering":
        reliability = _degrade(reliability, 2 if clue.source_type == "testimony" else 1)
    elif profile.state == "extinguished":
        if clue.source_type == "testimony":
            reliability = "unstable"
        elif clue.source_type == "document":
            reliability = "distorted"
        else:
            reliability = _degrade(reliability, 1)
    elif profile.state == "altered" and profile.altered_target_domain == domain:
        reliability = "distorted"

    if profile.missingness == "high" and profile.state in {"flickering", "extinguished"}:
        if clue.source_type == "testimony":
            reliability = "unstable"
        elif clue.source_type != "physical":
            reliability = _degrade(reliability, 1)
    elif (
        profile.missingness == "medium"
        and reliability == "uncertain"
        and clue.source_type == "document"
    ):
        if profile.state == "altered" and profile.altered_target_domain == domain:
            reliability = "distorted"

    return clue.model_copy(update={"reliability": reliability, "updated_at": updated_at})


def _base_witness_step(profile: LanternRuleProfile, *, domain: str) -> int:
    if profile.state == "bright":
        return 3
    if profile.state == "dim":
        return 2
    if profile.state == "flickering":
        return 1
    if profile.state == "extinguished":
        return 0
    if profile.state == "altered":
        return 1 if profile.altered_target_domain == domain else 3
    raise ValueError(f"Unsupported lantern state: {profile.state}")


def _degrade(reliability: str, steps: int) -> str:
    current = reliability
    for _ in range(steps):
        current = _CLUE_DEGRADATION[current]
    return current


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(value, maximum))
