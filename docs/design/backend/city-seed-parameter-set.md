# Lantern City — City Seed Parameter Set

## Purpose

This document defines the parameters used to generate a new Lantern City instance at the start of a run.

The seed should be flexible enough to produce replayability, but structured enough to keep each city coherent.

## Core Principle

The city seed is where replayability is expressed.
The runtime engine stays stable; the seed determines the city’s shape, mood, tension, and hidden structure.

## Parameter Groups

### 1. City Identity
These define the broad flavor of the city.

This group should shape the overall feel of the run without forcing specific plot events.
It is the city’s “first impression” and should stay stable across the run.

Required fields:
- `city_name`
- `dominant_mood`
- `weather_pattern`
- `architectural_style`
- `economic_character`
- `social_texture`
- `ritual_texture`
- `baseline_noise_level`

#### city_name
- The city’s stable identity anchor.
- Can be a fixed canonical name or a generated one.
- Should feel memorable and distinct.

#### dominant_mood
- A short list of 2–4 tone words.
- Use broad emotional/weather descriptors, not plot descriptors.
- Example values: `noir`, `damp`, `uneasy`, `intimate`, `tense`, `wary`

#### weather_pattern
- The city’s recurring atmospheric condition.
- Should support the setting’s tone and visual identity.
- Example values: persistent rain, coastal fog, salt wind, overcast drizzle, humid nights

#### architectural_style
- The dominant built-environment character.
- Should describe what the player sees when they move through the city.
- Example values: old stone and brass, stacked harbor terraces, narrow alleys, elevated walkways, soot-dark industry

#### economic_character
- The city’s main survival engine.
- This should tell us what the city does to keep itself alive.
- Example values: port trade, archive administration, manufacturing, debt finance, ritual commerce, shipping and repair

#### social_texture
- How ordinary people behave and relate to each other.
- Should describe the baseline social pressure in the city.
- Example values: guarded, practical, rumor-driven, hierarchy-conscious, cooperative under pressure, formal in public

#### ritual_texture
- The city’s relationship to symbols, civic rites, and memory systems.
- Should say whether ritual is formal, improvised, hidden, politicized, or rare.
- Example values: formal lantern ceremonies, shrine-maintained routes, memory registries, public observance with hidden practice

#### baseline_noise_level
- How much weirdness the city tolerates before it feels abnormal.
- Suggested values: `low`, `medium`, `high`
- Low means strange events feel shocking.
- High means the city already contains a lot of ambiguity and unresolved irregularity.

Examples:
- rain-soaked port metropolis
- tidal trade city
- archive-heavy inland capital
- lantern-lit industrial harbor
- fog-bound administrative city with ceremonial lantern law

### 2. District Configuration
These define how many districts exist and what roles they play.

Districts are the main playable regions of the city.
They should be distinct enough to feel like different social ecosystems, but still part of one coherent city.

Required fields:
- `district_count`
- `district_names`
- `district_roles`
- `district_stability_baseline`
- `district_lantern_states`
- `district_access_patterns`
- `district_hidden_location_density`

#### district_count
- The number of districts generated for this run.
- Recommended MVP range: 2–5.
- Higher counts should increase replay variety but not overwhelm the player.

#### district_names
- Unique district names matching the city theme.
- Names should hint at function or mood.
- Example values: Old Quarter, Lantern Ward, Docks, Salt Barrens, Market Spires

#### district_roles
- The social and mechanical role of each district.
- Each district should have a clear purpose in the city’s ecosystem.
- Example roles:
  - administrative center
  - trade center
  - memory/archive district
  - industrial district
  - fringe/superstitious district
  - understructure district
  - ceremonial district

#### district_stability_baseline
- Starting coherence and safety of each district.
- Suggested range: 0.0 to 1.0
- Lower values mean more uncertainty, tension, and lantern sensitivity.

#### district_lantern_states
- Initial lantern condition for each district.
- Use the standard lantern states: bright, dim, flickering, extinguished, altered.
- This should shape clue reliability, NPC behavior, and access.

#### district_access_patterns
- How easy it is to move into or through each district.
- Can encode gated access, public access, nighttime restrictions, faction-controlled entry, or hidden routes.

#### district_hidden_location_density
- How many hidden or unlockable locations each district tends to contain.
- Suggested values: low, medium, high or a normalized numeric value.
- Higher density means more discovery and investigation depth.

### 3. Faction Configuration
These define the city’s power structure.

Factions should feel like living agents with public legitimacy and private agendas.
They are not just labels; they are persistent strategic forces in the city.

Required fields:
- `faction_count`
- `faction_names`
- `faction_roles`
- `public_goals`
- `hidden_goals`
- `faction_influence_map`
- `faction_tension_map`
- `faction_attitudes_toward_player`

#### faction_count
- The number of tracked factions in the run.
- Recommended MVP range: 2–5.
- More factions increase political complexity and replayability.

#### faction_names
- Distinct faction names that fit the city’s identity.
- Names should imply power, culture, or function.
- Example values: Council of Lights, Memory Keepers, Dock Unions, Merchant Houses, Shrine Circles

#### faction_roles
- Each faction’s role in the city’s ecosystem.
- Roles should describe what the faction controls or influences.
- Example roles:
  - civic authority
  - trade power
  - labor organization
  - memory stewardship
  - ritual governance
  - undercity logistics

#### public_goals
- What each faction claims to want.
- These should be plausible and legible to the player.
- Example: maintain order, keep trade flowing, preserve records, protect workers

#### hidden_goals
- What each faction is really trying to do.
- These should create tension, contradiction, and mystery.
- Example: control memory, monopolize routes, erase rivals, conceal anomalies

#### faction_influence_map
- Which districts each faction influences and how strongly.
- Suggested representation: normalized scores per district.
- Higher influence means greater access, leverage, and reach.

#### faction_tension_map
- Conflict pressure between factions.
- Suggested representation: pairwise tension scores.
- Higher tension means more chance of sabotage, rivalry, or opportunistic cooperation.

#### faction_attitudes_toward_player
- The faction’s starting stance toward the player.
- Suggested values: friendly, neutral, wary, hostile, utilitarian, unknown
- This should be shallow at the start and deepen through play.

Examples:
- Council of Lights vs Memory Keepers
- Merchant Houses vs Dock Unions
- Shrine Circles balancing both public ritual and hidden control

### 4. Lantern Configuration
These define the lantern system at startup.

Lanterns are a core city system, not decoration.
They should shape visibility, memory, legitimacy, movement, and hidden control.

Required fields:
- `lantern_system_style`
- `lantern_ownership_structure`
- `lantern_maintenance_structure`
- `lantern_condition_distribution`
- `lantern_reach_profile`
- `lantern_social_effect_profile`
- `lantern_memory_effect_profile`
- `lantern_tampering_probability`

#### lantern_system_style
- The overall shape of the lantern network.
- Example values: civic grid, fragmented district lamps, ceremonial chain, private-owned routes, mixed public/ritual infrastructure

#### lantern_ownership_structure
- Who officially owns or regulates lanterns.
- Example values: central civic authority, district councils, shrine groups, merchant houses, mixed control

#### lantern_maintenance_structure
- Who actually keeps the lanterns functioning.
- This may differ from the official owner.
- Example values: civic engineers, shrine technicians, contractor crews, guild labor, hidden ritual maintainers

#### lantern_condition_distribution
- The starting spread of lantern states across the city.
- Use the standard lantern conditions: bright, dim, flickering, extinguished, altered.
- Represent as proportions or per-district assignments.

#### lantern_reach_profile
- How far lantern influence extends.
- Can be district-wide, street-level, route-based, or irregular depending on the city seed.
- This should support uncertainty about who really controls what.

#### lantern_social_effect_profile
- How lantern state affects behavior and social order.
- Example effects: hesitation, legitimacy, public confidence, reduced crime, surveillance pressure, restricted movement

#### lantern_memory_effect_profile
- How lantern state affects memory, testimony, records, and continuity.
- Example effects: clearer testimony, contradictory accounts, missing entries, unstable recall, selective remembrance

#### lantern_tampering_probability
- The likelihood that lanterns are altered, damaged, or ritually redirected at seed start.
- Suggested range: 0.0 to 1.0
- Higher values increase mystery and instability.

Examples:
- tightly regulated civic grid
- fragmented district-owned lights
- ritual-maintained ceremonial lamps
- mixed civic and private control

### 5. Missingness Configuration
These define how active the central mystery is.

Missingness is the city’s core anomaly.
It should define how reality, memory, records, and presence become unstable.

Required fields:
- `missingness_pressure`
- `missingness_scope`
- `missingness_visibility`
- `missingness_style`
- `missingness_targets`
- `missingness_risk_level`

#### missingness_pressure
- Overall intensity of the anomaly at seed start.
- Suggested range: 0.0 to 1.0
- Higher values mean the city begins closer to instability.

#### missingness_scope
- What kinds of things Missingness affects first.
- Example values: records first, people first, places first, names first, relationships first, mixed

#### missingness_visibility
- How obvious the problem is to ordinary citizens.
- Example values: hidden, rumor-level, known-but-denied, openly feared, institutionally acknowledged

#### missingness_style
- The texture of the anomaly.
- Example values: edited records, vanishing names, contradictory witness accounts, unstable maps, absent buildings, inconsistent family histories

#### missingness_targets
- The starting focus of Missingness.
- Could be specific people, families, districts, archives, routes, or institutions.
- Can be one or more target classes.

#### missingness_risk_level
- How dangerous the anomaly is likely to become.
- Suggested values: low, medium, high
- Higher risk means more escalation potential and stronger consequences.

Examples:
- records vanish before people do
- people disappear from official memory first
- entire households become inconsistent across ledgers
- places shift before witnesses agree

### 6. Case Configuration
These define the starting investigations.

Cases are the initial story hooks that make the city playable.
They should create immediate pressure without solving themselves automatically.

Required fields:
- `starting_case_count`
- `case_types`
- `case_intensity`
- `case_scope`
- `case_involved_districts`
- `case_involved_factions`
- `case_key_npcs`
- `case_failure_modes`

#### starting_case_count
- Number of active cases at game start.
- Recommended MVP range: 1–2.
- More than that may dilute focus in the first run.

#### case_types
- The kinds of problems the city begins with.
- Example values: missing person, lantern outage, record corruption, faction dispute, ritual anomaly, route disappearance

#### case_intensity
- How urgent or disruptive the opening case feels.
- Suggested values: low, medium, high
- Higher intensity should create stronger immediate consequences.

#### case_scope
- How broad the case is at the start.
- Example values: single location, single district, multi-district, city-adjacent

#### case_involved_districts
- Which districts are touched by the opening cases.
- Should be limited enough to keep the MVP focused.

#### case_involved_factions
- Which factions are already entangled in the opening problem.
- Helps seed political pressure immediately.

#### case_key_npcs
- The first important characters tied to the case.
- These should include at least one lead or informant.

#### case_failure_modes
- How the case can fail, stall, or mutate.
- Example values: suspect escapes, evidence is destroyed, district becomes unstable, faction suppresses the truth, Missingness escalates

Examples:
- a missing clerk whose records no longer exist
- a lantern outage hiding a political dispute
- a shrine anomaly causing contradictory testimony
- a trade route vanishing from the public map

### 7. NPC Configuration
These define the tracked cast.

NPCs are the city’s active agents.
They should have memory, goals, and enough structure to make conversations matter.

Required fields:
- `tracked_npc_count`
- `npc_role_distribution`
- `npc_relevance_distribution`
- `npc_memory_depth`
- `npc_relationship_density`
- `npc_secrecy_level`
- `npc_mobility_pattern`

#### tracked_npc_count
- Number of NPCs tracked in detail at the start of the run.
- Recommended MVP range: 3–8.
- More NPCs should increase social complexity, not just noise.

#### npc_role_distribution
- The mix of NPC categories in the initial cast.
- Recommended categories:
  - leads
  - informants
  - gatekeepers
  - world NPCs
  - ambient/promotable NPCs

#### npc_relevance_distribution
- How many NPCs are immediately relevant versus later discoverable.
- This helps avoid overwhelming the player with too many “important” people at once.

#### npc_memory_depth
- How much each NPC remembers at seed start.
- Could be shallow, medium, deep, or a numeric scale.
- Deeper memory should produce stronger continuity and more persistent consequences.

#### npc_relationship_density
- How many meaningful links each NPC has to factions, districts, cases, or other NPCs.
- Higher density increases the city’s social web and investigation potential.

#### npc_secrecy_level
- How likely an NPC is to hide motives or withhold information.
- Example values: low, medium, high
- Higher secrecy should make conversations more investigative.

#### npc_mobility_pattern
- How often the NPC moves, relocates, or changes availability.
- Example values: static, district-bound, routine-mobility, unpredictable, case-driven

Suggested role distribution:
- leads
- informants
- gatekeepers
- world NPCs
- ambient/promotable NPCs

### 8. Progression Start State
These define the player’s initial knowledge and access.

The starting progression state should establish the player as capable but not yet powerful.
They should have enough grounding to investigate, but still need to learn the city.

Required fields:
- `starting_lantern_understanding`
- `starting_access`
- `starting_reputation`
- `starting_leverage`
- `starting_city_impact`
- `starting_clue_mastery`

#### starting_lantern_understanding
- The player’s initial knowledge of lantern behavior.
- Suggested value: low to moderate.

#### starting_access
- The player’s initial ability to enter places or speak to certain groups.
- Suggested value: low.

#### starting_reputation
- The player’s initial standing with the city.
- Suggested value: low or neutral depending on the run’s premise.

#### starting_leverage
- The player’s initial pressure points and secrets.
- Suggested value: low, but not always zero.

#### starting_city_impact
- How much the city already reacts to the player at game start.
- Suggested value: very low.

#### starting_clue_mastery
- The player’s initial ability to read and connect clues.
- Suggested value: low to moderate.

These should usually start low but not zero, so the player has something to work with.

Suggested starting tier profile:
- Lantern Understanding: Novice or Informed
- Access: Public or Limited
- Reputation: Neutral or Wary
- Leverage: None or Limited
- City Impact: Local minimum
- Clue Mastery: Novice or Competent

### 9. Tone and Difficulty
These define the pacing and challenge of the run.

This group controls how dense, hostile, and strange the city feels during play.
It should influence how quickly the player gets useful information and how hard it is to reshape the city.

Required fields:
- `story_density`
- `mystery_complexity`
- `social_resistance`
- `investigation_pace`
- `consequence_severity`
- `revelation_delay`
- `narrative_strangeness`

#### story_density
- How much meaningful content the city produces per area or session.
- Suggested values: low, medium, high

#### mystery_complexity
- How layered and interdependent the opening mysteries are.
- Suggested values: low, medium, high

#### social_resistance
- How hard it is to persuade, access, or influence people.
- Suggested values: low, medium, high

#### investigation_pace
- How quickly clues and scene changes should emerge.
- Suggested values: slow, moderate, fast

#### consequence_severity
- How hard the city pushes back when the player changes state.
- Suggested values: low, medium, high

#### revelation_delay
- How long it should take before the player gets a major truth.
- Suggested values: short, medium, long

#### narrative_strangeness
- How unusual or uncanny the run should feel.
- Suggested values: low, medium, high

## Tuning Guidance

- High story density + high mystery complexity creates a rich but demanding run.
- High social resistance makes NPC interaction more cautious and investigative.
- Fast investigation pace should be used when you want a more action-oriented mystery.
- Long revelation delay is useful when the city should feel opaque and layered.
- High narrative strangeness should be reserved for runs where the uncanny is central rather than occasional.

## Suggested Default Profile

For the first MVP-style run:
- story_density: medium
- mystery_complexity: medium
- social_resistance: medium
- investigation_pace: moderate
- consequence_severity: medium
- revelation_delay: medium
- narrative_strangeness: medium

## Recommended Seed Output Structure

The city seed generator should output:
- city identity
- district list and roles
- faction list and roles
- lantern profile
- missingness profile
- starting cases
- tracked NPC anchors
- starting progression state
- summary of the city’s central conflict

## Example Seed Shape

```json
{
  "city_name": "Lantern City",
  "dominant_mood": ["noir", "wet", "uncertain"],
  "district_count": 5,
  "faction_count": 4,
  "lantern_system_style": "civic grid with ritual overlays",
  "missingness_pressure": 0.42,
  "starting_case_count": 1,
  "tracked_npc_count": 6,
  "story_density": "medium",
  "mystery_complexity": "medium"
}
```

## Scaling Rule

For larger cities, increase:
- district count
- NPC count
- case count
- hidden location density
- faction tension
- lantern complexity

For smaller or faster runs, decrease those values while keeping the same underlying engine.

## Design Rule

The city seed should be the only place where the game decides how large and complex a run begins.
The runtime should not care whether the seed created a small city or a large one.
