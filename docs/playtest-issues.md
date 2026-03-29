# Playtest Issues

Issues surfaced during exploratory playtesting with live LLM generation (2026-03-28).
Model used: `unsloth/qwen3.5-35b-a3b` via LM Studio at `http://192.168.3.181:1234`.

---

## P1 — Breaks the experience

### ~~NPC conversation is stateless across turns~~ ✅ Fixed
`npc_response` generation payload now includes `conversation_history` from the last 6 `memory_log` entries that contain both `input_text` and `npc_response`. Engine saves each LLM response into `memory_log`. Verified with 3-turn conversation where Ila referenced her own prior words.

---

### ~~Windows stdout encoding breaks Unicode output~~ ✅ Fixed
`cli.main` now calls `sys.stdout.reconfigure(encoding='utf-8', errors='replace')` and `sys.stderr.reconfigure` before any output.

---

## P2 — Degrades the experience significantly

### Character limits on generated fields too restrictive for quality models
Several Pydantic validators set limits that were appropriate for small/stub models but reject well-formed responses from larger models, silently falling back to template text.

| Field | Original | Current | Notes |
|---|---|---|---|
| `npc_line` | 280 | 640 | 35B responses exceeded 480 in follow-up session |
| `summary_text` | 160 | 320 | Richer summaries exceeded 160 |

**Status:** Both raised in this session. May need further tuning as more content is generated.

**Location:** `generation/npc_response.py:NPCResponseCacheableText`, `NPCResponseGenerationResult`

---

### ~~NPC emotional state not reflected in generated responses~~ ✅ Fixed
Added `emotional_register` computed field to the NPC generation payload — a plain-English translation of trust/fear/suspicion into behavioral guidance (e.g. "afraid — hedges every statement, avoids specific details"). Generation prompt now explicitly instructs the model to use `emotional_register` to shape HOW the NPC speaks. Verified: Sered deflects institutionally, Brin hedges and probes back, Ila redirects cautiously.

---

### ~~Sered Marr is mechanically inert~~ ✅ Fixed
`talk_to_npc` now calls `_npc_clue(npc)` instead of `_primary_clue()`. `_npc_clue` walks the NPC's `known_clue_ids` and returns the first non-solid clue, falling back to the primary clue only if none are found. Each NPC now advances their own evidence. Sered advances `clue_missing_maintenance_line`, Brin the same (she also knows it), Ila advances `clue_outage_predates_disappearance`.

---

### ~~District summary text is raw template output~~ ✅ Fixed
`engine._generate_district_entry_prose` uses `generate_json` with a `{"prose": "..."}` schema. Bypasses Qwen3 thinking leakage. LLM fallback stays if generation fails.

---

### ~~LLM config must be re-passed on every CLI invocation~~ ✅ Fixed
`cli` saves `llm_url`/`llm_model` to `<db-stem>.json` on first use with `--llm-url`/`--llm-model`, then auto-loads it on subsequent commands.

---

## P3 — Quality and design gaps

### No friction in case resolution
The case resolves immediately once the clue is solid and Ila's memory log is non-empty. The player can go `start → enter → talk → case` and win in four commands.

**Note:** This is intentional for the MVP vertical slice — the scenario was kept short to enable functional testing. This becomes a real issue only when the scenario is expanded beyond the initial test case.

**Location:** `app.py:advance_case`

---

### Small models degrade badly with the full JSON schema
The 4B model (Nemotron Nano) required a sanitize fix for invalid field prefixes and still generated ellipsis-only responses that degraded on follow-up. The 20B model (gpt-oss-20b-sombliterated) generated `<|channel|>` tokens and stub placeholders. The schema is too complex for models under ~30B.

**Impact:** The game is not usable below ~30B without significant prompt simplification or a two-pass approach (generate prose, then extract structured effects separately).

**Location:** `generation/npc_response.py:NPCResponseGenerator._build_messages`

---

### Model quality check missing from new game setup
When a local model is configured, there is no validation that the model is capable of producing schema-compliant, non-degenerate NPC responses. Poor models silently fall back to template text, which is not obvious to the player.

**Impact:** A player using a 4B or 7B model gets a degraded experience with no warning. Model problems are only discovered through play.

**Fix direction:** During `start` (new game setup), run a lightweight probe generation — a minimal NPC response task with a known fixture — and report the result to the player. Flag models that fail schema compliance, produce degenerate output (ellipsis chains, empty fields), or exceed a latency threshold.

---

### NPC exit lines repeat verbatim across turns
When an NPC signals conversation closure, the same exit phrase repeats word-for-word on subsequent turns. The design intent — using repetition as a social signal that the thread is exhausted — is correct. The polish gap is that the exact same sentence is used rather than varied language that conveys the same closure.

**Note:** This is a quality issue, not a design flaw. The behavior is correct; the prose execution is mechanical.

**Fix direction:** The generation prompt should instruct the model to vary its closing language across turns rather than reuse the prior exit line verbatim. The conversation history in the payload makes this possible — the model can see what it already said.

---

### ~~Location inspection has no narrative or object-level interaction~~ ✅ Fixed
`LocationInspectionGenerator` wired in for both whole-scene and object-level inspection. Each `LocationState` now has `scene_objects: list[str]`. Whole-scene inspect shows the object list; `inspect <location_id> <object>` focuses the generation on that object with a narrowed prompt and stays on the physical detail. CLI: `inspect location_ledger_room "maintenance log shelf"`.

---

### ~~No ellipsis/placeholder guard in `npc_line` validation~~ ✅ Fixed
`_require_single_turn_text` now rejects strings where fewer than 25% of non-whitespace characters are alphabetic. Catches pure ellipsis, punctuation-only, and stub placeholders.

---
