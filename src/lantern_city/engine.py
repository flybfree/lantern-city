from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from typing import Any

from lantern_city.active_slice import ActiveSlice, RequestIntent
from lantern_city.generation.writing_guardrails import (
    COMMON_AVOID_RULES,
    DISTRICT_PROSE_RULES,
    TONE_SYSTEM_BLOCK,
)
from lantern_city.generation.location_inspection import (
    LocationInspectionError,
    LocationInspectionGenerator,
    LocationInspectionRequest,
)
from lantern_city.generation.npc_response import (
    NPCResponseGenerationError,
    NPCResponseGenerationResult,
    NPCResponseGenerationRequest,
    NPCResponseGenerator,
)
from lantern_city.llm_client import OpenAICompatibleConfig, OpenAICompatibleLLMClient
from lantern_city.models import (
    ClueState,
    DistrictState,
    FactionState,
    NPCState,
    PlayerProgressState,
    PlayerRequest,
    RuntimeModel,
)
from lantern_city.orchestrator import orchestrate_request
from lantern_city.response import ResponsePayload, compose_response
from lantern_city.social import (
    append_memory_entry,
    apply_player_flag,
    apply_player_social_consequence,
    apply_relationship_shift,
    build_conversation_memory_entry,
    summarize_relationship,
)
from lantern_city.store import SQLiteStore
from lantern_city.log import get_logger

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class EngineOutcome:
    intent: RequestIntent
    active_slice: ActiveSlice
    response: ResponsePayload
    changed_objects: list[str]


@dataclass(frozen=True, slots=True)
class _GeneratedNPCOutcomeRead:
    learned: list[str]
    now_available: list[str]
    next_actions: list[str]
    state_changes: list[str]


@dataclass(slots=True)
class StateUpdateEngine:
    store: SQLiteStore

    def apply_updates(self, *objects: RuntimeModel) -> list[str]:
        if not objects:
            return []
        self.store.save_objects_atomically(objects)
        return [f"{obj.type}:{obj.id}" for obj in objects]


def handle_player_request(
    store: SQLiteStore,
    *,
    city_id: str,
    request: PlayerRequest,
    llm_config: OpenAICompatibleConfig | None = None,
    progress: PlayerProgressState | None = None,
    case_intro_text: str | None = None,
) -> EngineOutcome:
    log.debug("handle_player_request intent=%r target=%r", request.intent, request.target_id)
    orchestrated = orchestrate_request(store, city_id=city_id, request=request)
    log.debug("handle_player_request resolved_intent=%r", orchestrated.intent)
    state_update_engine = StateUpdateEngine(store)

    if orchestrated.intent == "district_entry":
        response, changed_objects = _handle_district_entry(
            state_update_engine,
            orchestrated.active_slice,
            request,
            llm_config=llm_config,
        )
    elif orchestrated.intent == "talk_to_npc":
        response, changed_objects = _handle_npc_conversation(
            state_update_engine,
            orchestrated.active_slice,
            request,
            llm_config=llm_config,
            progress=progress,
            case_intro_text=case_intro_text,
        )
    elif orchestrated.intent == "inspect_location":
        response = _build_inspection_response(
            orchestrated.active_slice, request, llm_config=llm_config, progress=progress
        )
        changed_objects = []
    elif orchestrated.intent == "case_progression":
        response = _build_case_response(orchestrated.active_slice)
        changed_objects = []
    else:
        response = compose_response(
            narrative_text="You pause and take stock of the scene.",
            next_actions=["Review what stands out", "Choose a more specific action"],
        )
        changed_objects = []

    return EngineOutcome(
        intent=orchestrated.intent,
        active_slice=orchestrated.active_slice,
        response=response,
        changed_objects=changed_objects,
    )


def _handle_district_entry(
    state_update_engine: StateUpdateEngine,
    active_slice: ActiveSlice,
    request: PlayerRequest,
    *,
    llm_config: OpenAICompatibleConfig | None = None,
) -> tuple[ResponsePayload, list[str]]:
    city = active_slice.city
    district = _require_district(active_slice)
    case_title = None if active_slice.case is None else active_slice.case.title

    entry_prose = _generate_district_entry_prose(active_slice, llm_config=llm_config)
    narrative_text = entry_prose or (
        f"You enter {district.name}. The lanterns are {district.lantern_condition}."
    )

    response = compose_response(
        narrative_text=narrative_text,
        state_changes=[f"Presence increased in {district.name}."] if district.name else [],
        learned=[f"The district lanterns are running {district.lantern_condition}."],
        visible_npcs=[npc.name for npc in active_slice.npcs if npc.name][:4],
        notable_objects=_district_notable_objects(active_slice),
        exits=[_display_name(location_id) for location_id in district.visible_locations[:4]],
        case_relevance=_case_relevance(active_slice),
        now_available=_district_now_available(district, active_slice.npcs),
        next_actions=_district_next_actions(district, case_title),
    )

    updated_city = city.model_copy(
        update={
            "player_presence_level": round(min(city.player_presence_level + 0.1, 1.0), 3),
            "version": city.version + 1,
            "updated_at": request.updated_at,
        }
    )
    changed_objects = state_update_engine.apply_updates(updated_city)
    return response, changed_objects


def _handle_npc_conversation(
    state_update_engine: StateUpdateEngine,
    active_slice: ActiveSlice,
    request: PlayerRequest,
    *,
    llm_config: OpenAICompatibleConfig | None = None,
    progress: PlayerProgressState | None = None,
    case_intro_text: str | None = None,
) -> tuple[ResponsePayload, list[str]]:
    npc = _require_npc(active_slice)
    clue = _first_clue(active_slice.clues)
    case_title = None if active_slice.case is None else active_slice.case.title
    loyalty_faction = _load_loyalty_faction(active_slice, npc, state_update_engine.store)

    generation_result = _generate_npc_dialogue(
        state_update_engine.store,
        active_slice,
        request,
        llm_config=llm_config,
        progress=progress,
        case_intro_text=case_intro_text,
    )
    generation_read = _read_generated_npc_outcome(
        generation_result,
        loyalty_faction=loyalty_faction,
    )
    npc_line = None if generation_result is None else generation_result.cacheable_text.npc_line
    if npc_line is None:
        public_identity = f", {npc.public_identity}" if npc.public_identity else ""
        quoted_input = request.input_text or "Ask a careful question."
        narrative_text = (
            f'You ask {npc.name}{public_identity}, "{quoted_input}" '
            "They answer carefully and stay close to what is already known."
        )
    else:
        narrative_text = npc_line

    state_changes = [f"Recorded a new conversation beat with {npc.name}."] if npc.name else []
    updated_npc = npc
    if generation_result is not None:
        shift = generation_result.structured_updates.relationship_shift
        social_result = apply_relationship_shift(
            updated_npc,
            trust_delta=shift.trust_delta,
            suspicion_delta=shift.suspicion_delta,
            fear_delta=shift.fear_delta,
            tag=shift.tag,
            updated_at=request.updated_at,
        )
        updated_npc = social_result.npc
        state_changes.extend(social_result.state_changes)
        player_flag = _infer_player_flag(
            request.input_text,
            generation_result.structured_updates.dialogue_act,
            generation_result.structured_updates.npc_stance,
        )
        if player_flag is not None:
            updated_npc = apply_player_flag(updated_npc, flag=player_flag, updated_at=request.updated_at)
            state_changes.append(f"{npc.name} now remembers: {player_flag}.")
        consequence_result = apply_player_social_consequence(
            updated_npc,
            player_flag=player_flag,
            player_input=request.input_text,
            updated_at=request.updated_at,
        )
        updated_npc = consequence_result.npc
        state_changes.extend(consequence_result.state_changes)
        followthrough_read = _social_followthrough_effects(
            active_slice,
            updated_npc,
            player_flag=player_flag,
        )
        conversation_read = _conversation_outcome_read(
            generation_result.structured_updates.dialogue_act,
            generation_result.structured_updates.npc_stance,
        )
        if conversation_read:
            state_changes.append(f"Conversation read: {conversation_read}.")
        state_changes.append(f"Relationship state: {summarize_relationship(updated_npc)}.")
        state_changes.extend(generation_read.state_changes)
        state_changes.extend(followthrough_read.state_changes)
    else:
        player_flag = None
        followthrough_read = _GeneratedNPCOutcomeRead([], [], [], [])

    response = compose_response(
        narrative_text=narrative_text,
        state_changes=state_changes,
        learned=_merge_unique_lines(
            _merge_unique_lines(_learned_clues(active_slice, clue), generation_read.learned),
            followthrough_read.learned,
        ),
        visible_npcs=[npc.name] if npc.name else [],
        notable_objects=_conversation_notable_objects(active_slice, npc),
        exits=_conversation_exits(active_slice),
        case_relevance=_case_relevance(active_slice, clue=clue),
        now_available=_merge_unique_lines(
            _merge_unique_lines(_conversation_now_available(active_slice, npc), generation_read.now_available),
            followthrough_read.now_available,
        ),
        next_actions=_merge_unique_lines(
            _merge_unique_lines(generation_read.next_actions, followthrough_read.next_actions),
            _conversation_next_actions(case_title),
        ),
    )

    memory_entry = build_conversation_memory_entry(
        request_id=request.id,
        input_text=request.input_text,
        updated_at=request.updated_at,
        npc_response=npc_line,
        npc_exit_line=(
            None
            if generation_result is None
            else generation_result.cacheable_text.exit_line_if_needed
        ),
        dialogue_act=(
            None if generation_result is None else generation_result.structured_updates.dialogue_act
        ),
        npc_stance=(
            None if generation_result is None else generation_result.structured_updates.npc_stance
        ),
        relationship_tag=(
            None
            if generation_result is None
            else generation_result.structured_updates.relationship_shift.tag
        ),
        player_flag=player_flag,
        summary_text=None if generation_result is None else generation_result.summary_text,
        related_case_ids=[] if clue is None else clue.related_case_ids,
        related_clue_ids=[] if clue is None else [clue.id],
    )
    updated_npc = append_memory_entry(
        updated_npc,
        memory_entry=memory_entry,
        updated_at=request.updated_at,
    ).model_copy(
        update={
            "version": updated_npc.version + 1,
            "updated_at": request.updated_at,
        }
    )
    changed_objects = state_update_engine.apply_updates(updated_npc)
    return response, changed_objects


def _build_inspection_response(
    active_slice: ActiveSlice,
    request: PlayerRequest,
    *,
    llm_config: OpenAICompatibleConfig | None = None,
    progress: PlayerProgressState | None = None,
) -> ResponsePayload:
    location_name = "the area"
    if active_slice.location is not None:
        location_name = active_slice.location.name

    prose = _generate_inspection_prose(active_slice, request, llm_config=llm_config, progress=progress)
    if prose is not None:
        narrative_text, learned, next_actions = prose
    else:
        clue = _first_clue(active_slice.clues)
        narrative_text = f"You inspect {location_name} for anything that stands out."
        learned = _learned_clues(active_slice, clue)
        next_actions = ["Inspect a narrower detail", "Review known clues"]
    clue = _first_clue(active_slice.clues)
    state_changes = []
    inspection_read = _inspection_outcome_read(clue)
    if inspection_read:
        state_changes.append(f"Inspection read: {inspection_read}.")

    return compose_response(
        narrative_text=narrative_text,
        state_changes=state_changes,
        learned=learned,
        visible_npcs=_inspection_visible_npcs(active_slice),
        notable_objects=_inspection_notable_objects(active_slice),
        exits=_inspection_exits(active_slice),
        case_relevance=_case_relevance(active_slice, clue=clue),
        now_available=["Ask about what you found"],
        next_actions=next_actions,
    )


def _generate_inspection_prose(
    active_slice: ActiveSlice,
    request: PlayerRequest,
    *,
    llm_config: OpenAICompatibleConfig | None,
    progress: PlayerProgressState | None = None,
) -> tuple[str, list[str], list[str]] | None:
    if llm_config is None:
        return None
    try:
        llm_client = OpenAICompatibleLLMClient(llm_config)
        gen_request = LocationInspectionRequest(
            request_id=request.id,
            active_slice=active_slice,
            player_request=request,
            progress=progress,
        )
        result = LocationInspectionGenerator(llm_client).generate(gen_request)
        llm_client.close()

        def _ensure_period(s: str) -> str:
            s = s.strip()
            return s if s.endswith((".", "!", "?")) else s + "."

        parts = [_ensure_period(result.scene_text)]
        if result.lantern_effect:
            parts.append(_ensure_period(result.lantern_effect))
        if result.clue_connection:
            parts.append(_ensure_period(result.clue_connection))
        narrative_text = " ".join(parts)

        learned = result.notable_details
        next_actions = ["Ask an NPC about what you found", "Inspect a narrower detail"]
        return narrative_text, learned, next_actions
    except (LocationInspectionError, Exception) as exc:
        print(f"[LLM] inspection generation failed: {exc}", file=sys.stderr)
        return None


def _strip_thinking(text: str) -> str:
    """Remove <think>...</think> blocks and leading reasoning headers from model output."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    lines = text.splitlines()
    prose_lines = []
    skip = False
    for line in lines:
        stripped = line.strip()
        if re.match(r"^(thinking|reasoning|thought process|step \d)", stripped, re.IGNORECASE):
            skip = True
            continue
        if skip and re.match(r"^\d+\.", stripped):
            continue
        if skip and stripped and not re.match(r"^\d+\.", stripped):
            skip = False
        if not skip:
            prose_lines.append(line)
    return "\n".join(prose_lines).strip()


def _generate_district_entry_prose(
    active_slice: ActiveSlice,
    *,
    llm_config: OpenAICompatibleConfig | None,
) -> str | None:
    if llm_config is None or active_slice.district is None:
        return None
    try:
        district = active_slice.district
        city = active_slice.city
        case_title = None if active_slice.case is None else active_slice.case.title
        npc_names = [npc.name for npc in active_slice.npcs if npc.name]

        npc_hint = f" {npc_names[0]} can be found here." if npc_names else ""
        case_hint = f" An active case draws you here: {case_title}." if case_title else ""

        prompt = (
            f"Write 2-3 sentences of atmospheric entry prose for a player arriving in "
            f"{district.name}, a {district.tone} district. "
            f"The lanterns are {district.lantern_condition}. "
            f"Access is {district.current_access_level}."
            f"{case_hint}{npc_hint}\n\n"
            f"Rules:\n{DISTRICT_PROSE_RULES}\n{COMMON_AVOID_RULES}"
        )
        schema = {
            "type": "object",
            "properties": {"prose": {"type": "string"}},
            "required": ["prose"],
        }
        llm_client = OpenAICompatibleLLMClient(llm_config)
        result = llm_client.generate_json(
            messages=[
                {"role": "system", "content": f"You write terse atmospheric prose for a text RPG. Return valid JSON only. {TONE_SYSTEM_BLOCK}"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=1000,
            schema=schema,
        )
        llm_client.close()
        prose = (result.get("prose") or "").strip().strip('"')
        return prose if prose else None
    except Exception as exc:
        print(f"[LLM] district entry generation failed: {exc}", file=sys.stderr)
        return None


def _build_case_response(active_slice: ActiveSlice) -> ResponsePayload:
    if active_slice.case is None:
        return compose_response(
            narrative_text="You review your current leads, but no active case is focused here.",
            case_relevance=["No active case is anchored to this scene yet."],
            next_actions=["Choose a district lead", "Speak to a local contact"],
        )
    return compose_response(
        narrative_text=f"You review {active_slice.case.title}.",
        learned=list(active_slice.case.open_questions),
        visible_npcs=[npc.name for npc in active_slice.npcs if npc.name][:4],
        notable_objects=_district_notable_objects(active_slice),
        exits=_inspection_exits(active_slice),
        case_relevance=_case_relevance(active_slice),
        now_available=["Follow a case lead"],
        next_actions=["Inspect related evidence", "Speak to an involved NPC"],
    )


def _generate_npc_dialogue(
    store: SQLiteStore,
    active_slice: ActiveSlice,
    request: PlayerRequest,
    *,
    llm_config: OpenAICompatibleConfig | None,
    progress: PlayerProgressState | None = None,
    case_intro_text: str | None = None,
) -> NPCResponseGenerationResult | None:
    if llm_config is None or not active_slice.npcs:
        return None
    try:
        llm_client = OpenAICompatibleLLMClient(llm_config)
        target_npc = active_slice.npcs[0]
        gen_request = NPCResponseGenerationRequest(
            request_id=request.id,
            active_slice=active_slice,
            player_request=request,
            npc_id=request.target_id,
            progress=progress,
            case_intro_text=case_intro_text,
            loyalty_faction=_load_loyalty_faction(active_slice, target_npc, store),
        )
        result = NPCResponseGenerator(llm_client).generate(gen_request, max_tokens=2000)
        llm_client.close()
        return result
    except (NPCResponseGenerationError, Exception) as exc:
        print(f"[LLM] generation failed: {exc}", file=sys.stderr)
        return None


def _read_generated_npc_outcome(
    generation_result: NPCResponseGenerationResult | None,
    *,
    loyalty_faction: FactionState | None,
) -> _GeneratedNPCOutcomeRead:
    if generation_result is None:
        return _GeneratedNPCOutcomeRead([], [], [], [])

    style = _faction_style(loyalty_faction)
    updates = generation_result.structured_updates
    learned = [effect.note for effect in updates.clue_effects if effect.note]
    now_available: list[str] = []
    next_actions: list[str] = []
    state_changes: list[str] = []

    for redirect in updates.redirect_targets:
        target_label = _display_name(redirect.target_id)
        if style == "records":
            now_available.append(f"Follow the redirected paper trail to {target_label}")
        elif style == "civic":
            now_available.append(f"Accept the official reroute to {target_label}")
        else:
            now_available.append(f"Follow the lead to {target_label}")
        next_actions.append(f"Go to {target_label}")

    for access in updates.access_effects:
        target_label = _display_name(access.target_id) if access.target_id else "the indicated office"
        if style == "civic":
            now_available.append(f"Request official access to {target_label}")
            state_changes.append(f"Institutional pressure: civic routing now points through {target_label}.")
        elif style == "records":
            now_available.append(f"Check the record trail at {target_label}")
            state_changes.append(f"Institutional pressure: the conversation was redirected into records and intermediaries.")
        else:
            now_available.append(f"Use the opening at {target_label}")
        if access.note:
            learned.append(access.note)

    for suggestion in generation_result.cacheable_text.follow_up_suggestions:
        if style == "civic" and _looks_like_question(suggestion):
            next_actions.append(f"Make a formal request: {suggestion}")
        else:
            next_actions.append(suggestion)

    dialogue_act = updates.dialogue_act.lower()
    npc_stance = updates.npc_stance.lower()
    if style == "civic" and any(token in dialogue_act or token in npc_stance for token in ("refus", "official", "guard", "procedur")):
        state_changes.append("Institutional pressure: the reply stayed procedural and access-minded.")
    if style == "records" and any(token in dialogue_act or token in npc_stance for token in ("redirect", "deflect", "guard", "careful")):
        state_changes.append("Institutional pressure: the reply favored omission, deflection, and paper trails.")

    return _GeneratedNPCOutcomeRead(
        learned=_dedupe_preserve_order(learned),
        now_available=_dedupe_preserve_order(now_available),
        next_actions=_dedupe_preserve_order(next_actions),
        state_changes=_dedupe_preserve_order(state_changes),
    )


def _load_loyalty_faction(
    active_slice: ActiveSlice,
    npc: NPCState,
    store: SQLiteStore,
) -> FactionState | None:
    if not npc.loyalty:
        return None
    loyalty = store.load_object("FactionState", npc.loyalty)
    if isinstance(loyalty, FactionState):
        return loyalty
    for faction_id in active_slice.city.faction_ids:
        candidate = store.load_object("FactionState", faction_id)
        if isinstance(candidate, FactionState) and candidate.name == npc.loyalty:
            return candidate
    return None


def _conversation_outcome_read(dialogue_act: str, npc_stance: str) -> str:
    text = f"{dialogue_act} {npc_stance}".lower()
    if any(token in text for token in ("refus", "procedur", "official")):
        return "procedural block or formal refusal"
    if any(token in text for token in ("warn", "caution", "risk", "afraid", "fear")):
        return "warning delivered under pressure"
    if any(token in text for token in ("redirect", "deflect", "dodge", "avoid")):
        return "careful deflection with a redirect"
    if any(token in text for token in ("confirm", "answer", "reveal", "explain", "hint")):
        return "direct answer with usable detail"
    if any(token in text for token in ("guard", "careful", "hesitant", "wary")):
        return "guarded answer with limited detail"
    return ""


def _inspection_outcome_read(clue: ClueState | None) -> str:
    if clue is None:
        return "atmosphere and scene texture, but no solid lead yet"
    if clue.reliability == "contradicted":
        return "a contradiction in the scene that needs explanation"
    if clue.reliability in {"credible", "solid"}:
        if clue.source_type == "document":
            return "a concrete paper-trail sign worth following quickly"
        if clue.source_type == "physical":
            return "a concrete physical sign worth following"
        if clue.source_type == "testimony":
            return "a credible witness lead anchored in the scene"
        return "a credible lead anchored in the scene"
    if clue.source_type == "document":
        return "a weak paper trail that still needs corroboration"
    if clue.source_type == "physical":
        return "a suspicious physical detail that still needs confirmation"
    if clue.source_type == "testimony":
        return "a tentative witness lead rather than a conclusion"
    return "a live lead, but not proof yet"


def _faction_style(faction: FactionState | None) -> str:
    if faction is None:
        return "general"
    text = " ".join(
        [
            faction.name,
            faction.public_goal,
            faction.hidden_goal,
            *faction.known_assets,
            *faction.active_plans,
        ]
    ).lower()
    if any(token in text for token in ("records", "memory", "archive", "certification", "continuity")):
        return "records"
    if any(token in text for token in ("order", "compliance", "permit", "civic", "lantern", "public confidence")):
        return "civic"
    return "general"


def _merge_unique_lines(left: list[str], right: list[str]) -> list[str]:
    return _dedupe_preserve_order([*left, *right])


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _looks_like_question(text: str) -> bool:
    normalized = text.strip().lower()
    return normalized.startswith(("ask ", "request ", "find out ", "go to ")) or normalized.endswith("?")


def _infer_player_flag(
    player_input: str,
    dialogue_act: str,
    npc_stance: str,
) -> str | None:
    normalized = f"{player_input} {dialogue_act} {npc_stance}".lower()
    if any(
        token in normalized
        for token in (
            "kept my word",
            "kept your word",
            "as promised",
            "i brought it",
            "here it is",
            "i followed through",
        )
    ):
        return "promise_honored"
    if any(
        token in normalized
        for token in (
            "can't do it",
            "cannot do it",
            "won't do it",
            "couldn't get it",
            "i failed",
            "broke my word",
            "can't keep that promise",
        )
    ):
        return "promise_broken"
    if any(token in normalized for token in ("promise", "swear", "i will", "you have my word")):
        return "promise_made"
    if any(token in normalized for token in ("sorry", "apolog", "forgive me")):
        return "apology_offered"
    if any(token in normalized for token in ("or else", "regret it", "i'll make you")):
        return "threat_made"
    if any(token in normalized for token in ("i owe you", "in your debt", "owe you one", "return the favor")):
        return "debt_acknowledged"
    if any(token in normalized for token in ("favor", "help me", "do this for me", "i need your help")):
        return "favor_requested"
    if any(token in normalized for token in ("threat", "pressure", "intimidat", "coerce")):
        return "pressure_applied"
    if any(token in normalized for token in ("help", "protect", "safe", "rescue")):
        return "protective"
    if any(token in normalized for token in ("lie", "deceiv", "mislead")):
        return "deceptive"
    return None


def _district_now_available(district: DistrictState, npcs: list[NPCState]) -> list[str]:
    available: list[str] = []
    if district.visible_locations:
        available.append(f"Travel to {_display_name(district.visible_locations[0])}")
    if npcs:
        available.append(f"Speak to {npcs[0].name}")
    return available


def _district_next_actions(district: DistrictState, case_title: str | None) -> list[str]:
    next_actions: list[str] = []
    if district.visible_locations:
        next_actions.append(f"Inspect {_display_name(district.visible_locations[0])}")
    if case_title is not None:
        next_actions.append(f"Review {case_title}")
    return next_actions


def _conversation_now_available(active_slice: ActiveSlice, npc: NPCState) -> list[str]:
    available: list[str] = []
    if active_slice.location is not None:
        available.append(f"Inspect {active_slice.location.name}")
    elif npc.location_id is not None:
        available.append(f"Inspect {_display_name(npc.location_id)}")
    available.append(f"Press {npc.name} for specifics")
    return available


def _conversation_next_actions(case_title: str | None) -> list[str]:
    next_actions = ["Ask a narrower question"]
    if case_title is not None:
        next_actions.append(f"Review {case_title}")
    return next_actions


def _social_followthrough_effects(
    active_slice: ActiveSlice,
    npc: NPCState,
    *,
    player_flag: str | None,
) -> _GeneratedNPCOutcomeRead:
    target_label = _promise_route_target(active_slice, npc)
    if player_flag == "promise_honored":
        payoff_kind = _promise_payoff_kind(npc)
        if payoff_kind == "access":
            now_available = [f"Ask {npc.name} to open the formal route into {target_label}."]
            now_available.append(f"Use the access opening around {target_label}.")
            return _GeneratedNPCOutcomeRead(
                learned=[f"{npc.name} is now willing to bend procedure or access around {target_label} on your behalf."],
                now_available=now_available,
                next_actions=[
                    f"Ask which door, desk, or permit gets you into {target_label}.",
                    "Push the access advantage before the opening closes.",
                ],
                state_changes=["Access shift: keeping your word opened an institutional route through this NPC."],
            )
        if payoff_kind == "document":
            now_available = [f"Ask {npc.name} for the document trail they were holding back around {target_label}."]
            now_available.append(f"Follow the records opening around {target_label}.")
            return _GeneratedNPCOutcomeRead(
                learned=[f"{npc.name} is ready to expose part of the paper trail around {target_label}."],
                now_available=now_available,
                next_actions=[
                    f"Ask for the copy, ledger, or certification tied to {target_label}.",
                    "Compare the new paperwork quickly before it gets corrected away.",
                ],
                state_changes=["Access shift: keeping your word opened a document path through this NPC."],
            )
        now_available = [f"Ask {npc.name} what they will risk telling you about {target_label} now."]
        now_available.append(f"Use the opening around {target_label}.")
        return _GeneratedNPCOutcomeRead(
            learned=[f"{npc.name} treats the favor-based opening around {target_label} as real now."],
            now_available=now_available,
            next_actions=[
                f"Ask for the detail they were holding back about {target_label}.",
                "Press the strongest follow-up while the goodwill is fresh.",
            ],
            state_changes=["Access shift: keeping your word opened a more direct line with this NPC."],
        )
    if player_flag == "promise_broken":
        payoff_kind = _promise_payoff_kind(npc)
        if payoff_kind == "access":
            learned = [f"{npc.name} closes the access route you were relying on."]
            next_actions = [
                "Find another route or sponsor instead of expecting procedural help here.",
                "Rebuild trust before asking this NPC for permits or access again.",
            ]
            state_change = "Access shift: breaking your word closed an institutional route through this NPC."
        elif payoff_kind == "document":
            learned = [f"{npc.name} closes the document trail they might have exposed for you."]
            next_actions = [
                "Find corroborating paperwork elsewhere instead of expecting this record source to help.",
                "Rebuild trust before asking this NPC for protected records again.",
            ]
            state_change = "Access shift: breaking your word closed a document route through this NPC."
        else:
            learned = [f"{npc.name} closes the favor-based path you were relying on."]
            next_actions = [
                "Rebuild trust before asking this NPC for protected details again.",
                "Find corroboration elsewhere instead of expecting the promised help.",
            ]
            state_change = "Access shift: breaking your word closed an easier route through this NPC."
        return _GeneratedNPCOutcomeRead(
            learned=learned,
            now_available=[f"Look for another contact instead of leaning on {npc.name} right now."],
            next_actions=next_actions,
            state_changes=[state_change],
        )
    return _GeneratedNPCOutcomeRead([], [], [], [])


def _promise_payoff_kind(npc: NPCState) -> str:
    role = npc.role_category.lower()
    identity = f"{npc.public_identity} {npc.current_objective} {npc.hidden_objective}".lower()
    if role in {"authority", "gatekeeper"}:
        return "access"
    if any(token in identity for token in ("record", "ledger", "archive", "registr", "certification", "copy sheet")):
        return "document"
    return "testimony"


def _promise_route_target(active_slice: ActiveSlice, npc: NPCState) -> str:
    if active_slice.location is not None:
        return active_slice.location.name
    if npc.location_id is not None:
        return _display_name(npc.location_id)
    if active_slice.district is not None:
        return active_slice.district.name
    return npc.name


def _district_notable_objects(active_slice: ActiveSlice) -> list[str]:
    if active_slice.district is None:
        return []
    # District-entry slices do not carry a list of LocationState objects, only IDs.
    # Surface those locations as the notable scene targets instead of crashing on
    # a non-existent ActiveSlice.locations field.
    return [_display_name(location_id) for location_id in active_slice.district.visible_locations[:4]]


def _conversation_notable_objects(active_slice: ActiveSlice, npc: NPCState) -> list[str]:
    if active_slice.location is not None and active_slice.location.scene_objects:
        return active_slice.location.scene_objects[:4]
    if npc.location_id:
        return [_display_name(npc.location_id)]
    return []


def _conversation_exits(active_slice: ActiveSlice) -> list[str]:
    if active_slice.location is not None:
        return [active_slice.location.name]
    if active_slice.district is not None:
        return [_display_name(location_id) for location_id in active_slice.district.visible_locations[:3]]
    return []


def _inspection_visible_npcs(active_slice: ActiveSlice) -> list[str]:
    return [npc.name for npc in active_slice.npcs if npc.name][:4]


def _inspection_notable_objects(active_slice: ActiveSlice) -> list[str]:
    if active_slice.location is None:
        return []
    return active_slice.location.scene_objects[:4]


def _inspection_exits(active_slice: ActiveSlice) -> list[str]:
    if active_slice.district is None:
        return []
    return [_display_name(location_id) for location_id in active_slice.district.visible_locations[:4]]


def _case_relevance(active_slice: ActiveSlice, clue: ClueState | None = None) -> list[str]:
    relevance: list[str] = []
    if active_slice.case is not None:
        relevance.append(f"Active case: {active_slice.case.title} [{active_slice.case.status}]")
        if active_slice.case.open_questions:
            relevance.append(active_slice.case.open_questions[0])
    relevance.extend(_pre_case_clue_signals(active_slice, clue))
    if clue is not None:
        relevance.append(f"Clue reliability: {clue.reliability}")
    if active_slice.district is not None:
        relevance.append(f"Lantern condition: {active_slice.district.lantern_condition}")
    return relevance[:4]


def _learned_clues(active_slice: ActiveSlice, clue: ClueState | None) -> list[str]:
    if clue is None:
        return []
    if _is_pre_case_significant_clue(active_slice, clue):
        return [f"Notable clue: {clue.clue_text}"]
    return [clue.clue_text]


def _pre_case_clue_signals(active_slice: ActiveSlice, clue: ClueState | None) -> list[str]:
    if not _is_pre_case_significant_clue(active_slice, clue):
        return []
    return [
        "New lead: This clue feels significant, even though you do not yet know what case it belongs to."
    ]


def _is_pre_case_significant_clue(active_slice: ActiveSlice, clue: ClueState | None) -> bool:
    if clue is None or active_slice.case is not None:
        return False
    return bool(clue.related_case_ids)


def _require_district(active_slice: ActiveSlice) -> DistrictState:
    if active_slice.district is None:
        raise LookupError("District request requires an active district slice")
    return active_slice.district


def _require_npc(active_slice: ActiveSlice) -> NPCState:
    if not active_slice.npcs:
        raise LookupError("Conversation request requires an active NPC slice")
    return active_slice.npcs[0]


def _first_clue(clues: list[ClueState]) -> ClueState | None:
    if not clues:
        return None
    return clues[0]


def _display_name(identifier: str) -> str:
    if identifier.startswith(("location_", "district_", "case_", "npc_")):
        return identifier.split("_", 1)[1].replace("_", " ").title()
    return identifier


__all__ = ["EngineOutcome", "StateUpdateEngine", "handle_player_request"]
