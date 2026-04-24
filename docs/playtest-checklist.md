# Lantern City Playtest Checklist

Use this checklist when validating a build through actual play rather than unit tests.

The current game has two meaningful runtime layers:

- `generated_runtime`
  This is the player-facing default when a healthy LLM is available.
- `mvp_baseline`
  This is the controlled authored fallback/tutorial path.

Run both when you are validating a release candidate, a major UX change, or anything that touches clue flow, case progression, startup behavior, or GM narration.

---

## Before You Start

- Record the date, commit, and branch.
- Record the database used for the run.
- Record the startup mode used:
  - `generated_runtime`
  - `mvp_baseline`
- If using an LLM, record:
  - model name
  - endpoint
  - whether startup reported `Model check: pass` or `Model check: warning`
- Start a fresh notes file for observations, regressions, and command transcripts worth keeping.

---

## Pass 1: Startup And Orientation

Goal: confirm the game starts cleanly and tells the player where they are.

- Start a new game.
- Confirm startup output includes:
  - `Lantern City ready:`
  - `Startup mode: ...`
- If using `generated_runtime`, confirm startup also reports model check status.
- Confirm the initial scene is understandable without guessing hidden state.
- Confirm the TUI side panel or command output gives a usable first action.

Log if:

- startup mode is unclear
- model quality status is missing or misleading
- the opening scene feels empty, confusing, or directionless

---

## Pass 2: Baseline Loop

Goal: confirm the authored fallback path still works as a short, reliable loop.

- Start in `mvp_baseline`.
- Move through the Missing Clerk flow.
- Confirm the player can:
  - orient to the scene
  - inspect something useful
  - talk to at least one NPC
  - acquire and understand at least one meaningful clue
  - review the case with `board`, `leads`, or `journal`
  - resolve the case through the intended short path
- Confirm startup, recovery, and clue wording do not assume generated content.

Log if:

- the baseline loop breaks
- the baseline loop now depends on generated-runtime assumptions
- a quick onboarding run feels longer, more opaque, or more fragile than intended

---

## Pass 3: Generated Runtime Loop

Goal: confirm the player-facing default produces a coherent investigation loop.

- Start in `generated_runtime`.
- Confirm a generated city/case boots successfully.
- Enter a district, inspect a location, and talk to at least one NPC.
- Confirm generated case content feels coherent enough to follow.
- Activate a case if it is not active at the start.
- Advance the case through at least one meaningful clue update.
- Resolve or materially progress the generated case.
- Save and reload if that is part of the flow you are exercising.

Log if:

- generation produces unusable or contradictory setup text
- the case lacks a usable thread to follow
- reload loses state, startup mode, or case progress

---

## Pass 4: Clue Signaling

Goal: confirm the player can tell when something matters before fully understanding it.

- Find at least one clue before the related case is fully understood.
- Confirm the response makes it clear that the clue is significant.
- Confirm the player is not forced to guess whether the result mattered.
- Confirm the clue is later understandable in hindsight once the case context exists.

Check these specific questions:

- Does the game clearly say this is a new lead or something worth remembering?
- Does it avoid over-explaining the hidden case too early?
- When the clue becomes contextualized later, does it feel legible rather than arbitrary?

Log if:

- early clues still feel contextless
- significance is too generic to be useful
- hindsight does not clarify why the clue mattered

---

## Pass 5: Clue Readability

Goal: confirm clue review surfaces explain what the evidence is doing.

Review:

- `clues`
- `board`
- `leads`
- `journal`
- `status`
- `compare`
- `matters`

For at least three clues, check whether the game communicates:

- what role the clue is playing
- why it matters
- what the player should do next

Look specifically for these distinctions:

- supports current case
- contradiction to explain
- paper trail or lead to verify
- interesting but still weak evidence

Log if:

- clue language feels flat or repetitive
- the same clue reads differently across surfaces in a confusing way
- the game marks a clue as important without saying why

---

## Pass 6: Recovery UX

Goal: confirm a stuck player can recover without external help.

While intentionally losing the thread, try:

- `board`
- `leads`
- `journal`
- `matters`
- `compare`
- a vague GM prompt such as:
  - `what should I do next?`
  - `what matters here?`
  - `I'm stuck`

Confirm the game gives:

- a readable summary of the current situation
- concrete next actions
- commands or follow-up directions that match the actual state

Log if:

- recovery guidance is too generic
- recovery surfaces disagree with each other
- the GM advice does not match the command-layer guidance

---

## Pass 7: GM Narration

Goal: confirm the GM preserves investigation clarity rather than obscuring it.

During normal play and recovery prompts, check whether the GM:

- preserves clue-role distinctions
- makes significant findings feel significant
- avoids collapsing every clue into generic ominous prose
- points the player toward useful follow-up actions

Log if:

- GM narration hides practical meaning behind style
- recap prose loses clue role distinctions
- GM-mode recovery becomes vague or ornamental

---

## Pass 8: TUI Readability

Goal: confirm the side panel keeps the player oriented between commands.

Check whether the TUI:

- shows startup mode and model-check status clearly
- shows useful recovery hints
- reflects clue-reading summaries, not just clue counts
- keeps active case and pressure legible
- updates cleanly as clues and cases change

Log if:

- the side panel is stale
- the panel suggests commands that do not fit the current state
- clue-reading summaries are misleading or too compressed

---

## Pass 9: Persistence

Goal: confirm important progress survives reloads.

- Acquire clues.
- Advance or resolve a case.
- Restart or reload the game.
- Confirm the following survive correctly:
  - startup mode
  - known clues
  - active or solved cases
  - generated case identity and title
  - journal/board readability after reload

Log if:

- state is missing after reload
- a recovered session becomes harder to read than the original session

---

## Pass 10: Friction And Pacing

Goal: judge whether the game feels appropriately paced for the runtime mode being tested.

For `mvp_baseline`, ask:

- is the loop short and clear enough for onboarding?
- does it still prove the game works end to end?

For `generated_runtime`, ask:

- does the case offer enough resistance to feel investigative?
- is there enough guidance to prevent drift or dead air?
- does progress feel earned without becoming obscure?

Log if:

- baseline is too long or too opaque
- generated runtime is too easy, too abrupt, or too directionless

---

## Issue Logging Template

Use one entry per issue:

```text
Title:
Date:
Build/commit:
Startup mode:
Model:
Area:
Severity:

What I did:

What I expected:

What happened:

Why it matters:

Suggested fix direction:
```

---

## Exit Criteria

A build is in reasonable shape for the next step when:

- both startup modes still work for their intended purpose
- generated runtime is playable as the default experience
- clue significance is legible before and after case discovery
- recovery surfaces help a stuck player re-enter the loop
- GM narration supports clarity instead of undermining it
- persistence does not erase orientation

If those are true, the next issues should come from play quality, pacing, and content depth rather than architecture drift.
