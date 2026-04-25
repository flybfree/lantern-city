# Playtest Issues

Issues surfaced during exploratory playtesting with live LLM generation (2026-03-28).
Model used: `unsloth/qwen3.5-35b-a3b` via LM Studio at `http://192.168.3.181:1234`.

---

## 2026-04-24 live playtest addendum

Model used during current `dist` playtest: `google/gemma-4-e4b` via LM Studio.
Primary session reviewed: `dist/city-20260424-2051.log` and `dist/city-20260424-2051.log.json`.

### P1 — GM intent routing still breaks player agency
The GM layer still misroutes natural-language requests often enough to make the investigation feel arbitrary:
- asking about a specific NPC can become a different question entirely
- theory/recovery requests can be routed into `talk` instead of `board` or `leads`
- location/object examination can degrade into invalid commands or district-only `look` failures

**Concrete examples from the session:**
- `tell me about senator reed` became a question about Mr. Li
- `what is my case theory` got routed into `talk npc_elara_vance ...`
- `look around` in a location became `look location_succession_gallery`
- `examine holographic screens` produced an explicitly invalid command string

**Impact:** The player feels motion without control. Atmosphere remains strong, but trust in the action loop drops because the game is no longer reliably doing what the player asked.

**Fix direction:** Add hard normalization overrides ahead of generic GM output:
- theory/recovery requests should prefer `board`, `leads`, or `matters`
- `look around` in a location should prefer `inspect <current_location>`
- visible object references should prefer `inspect <current_location> <object_name>`

**Status:** In progress. First routing overrides added in `game_master.py`, plus object-aware `inspect` command parsing in `app.py`.

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

**Architecture note:** This should now be treated as an explicit MVP baseline shortcut, not as the default rule for the evolved simulation. Future case-depth work should preserve this path intentionally for onboarding/regression purposes while allowing broader systems to require more friction.

---

### MVP vertical slice assumptions and evolved runtime rules are still easy to mix up
The repo now contains both:
- a short authored MVP proof-of-loop path
- a deeper simulation direction with latent cases, pressure, and stronger state evolution

Those are both valid, but they serve different purposes. Problems arise when:
- the vertical-slice shortcut silently becomes the default rule for all cases
- or newer simulation logic accidentally breaks the baseline authored loop that tests and onboarding still rely on

**Impact:** This creates recurring regressions and design confusion. A change can be locally reasonable but still be wrong because it applies the assumptions of one layer to the other.

**Fix direction:** Keep the distinction explicit in docs, tests, and shared logic:
- MVP baseline behavior should remain a controlled, intentional shortcut
- deeper runtime behavior should be the default direction for post-MVP systems
- shared logic should not blend the two accidentally

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

### Clue signaling needs a deeper UX/readability pass
Pre-case clue signaling is now functionally in place: the engine, app output, and GM narration all mark certain clues as significant before the related case is formally understood. That fixes the immediate contextless-clue problem, but the broader investigation readability layer is still shallow.

**Current limitation:** The system mostly uses a generic "this matters" signal. It does not yet distinguish clearly between:
- a clue that is merely interesting
- a clue that likely belongs to a hidden case
- a clue that changes the current theory
- a clue that raises urgency or danger

Related review surfaces like `clues`, `board`, `leads`, `journal`, and the TUI side panels also need a stronger pass so the player can track not just that a clue matters, but why it matters and what it suggests doing next.

**Impact:** The player is less likely to miss important evidence than before, but the game still does not fully support the intended investigation readability. This is now a game-improvement task rather than a blocking bug.

**Fix direction:** Revisit clue signaling as part of interaction-model strengthening. Add richer clue categories/signals, clearer follow-up guidance, and stronger review/board/TUI presentation for newly surfaced leads and clue reinterpretation.

---

### The world still reacts too little to delay and social history
The repo now has partial ingredients for a living simulation:
- NPC memory logs
- relationship snapshots
- offscreen NPC updates
- case pressure
- city time index

But those systems are still too loosely connected to produce the intended feeling that people remember, institutions move, and time costs something.

**Current limitation:** The player can still treat most of the world as paused between direct interactions. NPCs and factions do not yet feel active enough offscreen, and delay does not yet produce a broad enough set of visible consequences.

**Impact:** The city risks feeling like a responsive mystery shell rather than a live social machine. Cases can have pressure, but the wider world still does not consistently communicate that time passed, relationships shifted, or opportunities narrowed because of it.

**Fix direction:** Implement the post-MVP world-turn and social-simulation phase:
- discrete world turns
- bounded idle-delay catch-up
- stronger NPC social memory and relationship persistence
- faction operations and pressure
- case evolution tied to elapsed turns and actor behavior
- explicit player-facing reporting of offscreen change

**Execution note:** This should primarily strengthen the evolved/generated runtime. The authored MVP baseline loop can keep lighter or partially bypassed simulation behavior if needed for onboarding and regression stability.

---

### ~~Location inspection has no narrative or object-level interaction~~ ✅ Fixed
`LocationInspectionGenerator` wired in for both whole-scene and object-level inspection. Each `LocationState` now has `scene_objects: list[str]`. Whole-scene inspect shows the object list; `inspect <location_id> <object>` focuses the generation on that object with a narrowed prompt and stays on the physical detail. CLI: `inspect location_ledger_room "maintenance log shelf"`.

---

### ~~No ellipsis/placeholder guard in `npc_line` validation~~ ✅ Fixed
`_require_single_turn_text` now rejects strings where fewer than 25% of non-whitespace characters are alphabetic. Catches pure ellipsis, punctuation-only, and stub placeholders.

---
