## Rhythm Game Specific Elements

### Music Synchronization

{{music_sync}}

**Core mechanics:**

- Beat/rhythm detection
- Note types (tap, hold, slide, etc.)
- Synchronization accuracy
- Audio-visual feedback
- Lane systems (4-key, 6-key, circular, etc.)
- Offset calibration

### Note Charts and Patterns

{{note_charts}}

**Chart design:**

- Charting philosophy (fun, challenge, accuracy to song)
- Pattern vocabulary (streams, jumps, chords, etc.)
- Difficulty representation
- Special patterns (gimmicks, memes)
- Chart preview
- Custom chart support (if applicable)

### Timing Windows

{{timing_windows}}

**Judgment system:**

- Judgment tiers (perfect, great, good, bad, miss)
- Timing windows (frame-perfect vs. lenient)
- Visual feedback for timing
- Audio feedback
- Combo system
- Health/life system (if applicable)

### Scoring System

{{scoring}}

**Score design:**

- Base score calculation
- Combo multipliers
- Accuracy weighting
- Max score calculation
- Grade/rank system (S, A, B, C)
- Leaderboards and competition

### Difficulty Tiers

{{difficulty_tiers}}

**Progression:**

- Difficulty levels (easy, normal, hard, expert, etc.)
- Difficulty representation (stars, numbers)
- Unlock conditions
- Difficulty curve
- Accessibility options
- Expert+ content

### Song Selection

{{song_selection}}

**Music library:**

- Song count (launch + planned DLC)
- Genre diversity
- Licensing vs. original music
- Song length targets
- Song unlock progression
- Favorites and playlists

## Default Prototype Contract

This contract is workflow-consumed default guidance. Unless the user-confirmed GDD explicitly conflicts with it, `Always` scenes and modules must be included in the GDD outline, scene route, prototype plan, and repair/iteration planning. If the GDD overrides an `Always` item, record the override reason explicitly.

### Default Scenes

| scene_id | scene_name | purpose | required | entry_from | exits_to | minimum_playable_content |
| --- | --- | --- | --- | --- | --- | --- |
| song_select | Song or chart select | Let the player start a track and understand difficulty/tempo. | Conditional | start | rhythm_play | A chart/song can be selected when multiple tracks exist. |
| rhythm_play | Rhythm gameplay lane | Synchronize prompts/notes with music or beat timing. | Always | song_select,start | results | Player hits timed inputs and receives accuracy feedback. |
| results | Results | Show score, combo, accuracy, and retry/continue. | Always | rhythm_play | song_select,rhythm_play | Performance summary is shown after chart ends or fails. |

### Required Modules

| module_id | module_name | required_by_default | purpose | minimum_acceptance |
| --- | --- | --- | --- | --- |
| beat_timing | Beat timing and chart scheduler | Always | Rhythm games depend on precise timing windows. | Notes/prompts spawn or activate according to chart time. |
| input_judgement | Input judgement windows | Always | The loop needs hit/miss/accuracy feedback. | Inputs are judged as hit/miss/grade based on timing. |
| score_combo | Score, combo, and accuracy model | Always | Players need performance feedback. | Score/combo/accuracy update during play and summarize after. |
| audio_sync | Audio and visual synchronization | Always | Desync breaks rhythm gameplay. | Visual prompts align with music/beat within declared tolerance. |

## Module Matrix

This matrix is a first-loop planning convention for GDD creation and later module scoping. It does not override a project-specific brief, GDD, prototype type kit, or executable route contract.

Use only these default values: `Always`, `Conditional`, `Optional`, and `Out of Scope`.

| No | id | Module | Default | Purpose | Acceptance |
| --- | --- | --- | --- | --- | --- |
| 1 | `performance_context_objective` | Performance context and objective | Always | Clarify song, stage, role, and performance goal. | Song or level name, target, performer context, and success condition are defined. |
| 2 | `beat_grid_audio_sync` | Beat grid and audio sync | Always | Anchor timing gameplay in stable music and beat data. | Music playback, BPM or beat timing, measure progression, and input timing relationship are defined. |
| 3 | `cue_readability` | Cue readability | Always | Let players see or hear when to act before the timing window. | Notes, beat lines, pulses, enemy tells, lanes, or visual cues are readable and do not hide core action. |
| 4 | `timed_input_action` | Timed input action | Always | Define the core action performed on beat. | Tap, hold, slide, aim, dodge, attack, lane switch, or gesture input is scoped with early, accurate, and late outcomes. |
| 5 | `timing_feedback_scoring` | Timing feedback and scoring | Always | Show immediately whether the player was accurate. | Perfect, good, miss, score, accuracy, health, meter, or grade feedback is defined. |
| 6 | `song_section_progression` | Song section progression | Always | Prove more than a single note interaction. | At least two song sections or difficulty beats are planned with cue and pacing changes. |
| 7 | `result_restart_loop` | Result and restart loop | Always | Close the song or stage experience. | Completion, failure, summary, retry, or next-song flow is defined. |
| 8 | `combo_meter_reward_feedback` | Combo, meter, or reward feedback | Conditional | Give players a sustained performance target. | If included, combo, multiplier, crowd, heat, health, or reward meter changes with performance. |
| 9 | `expressive_pitch_or_gesture_control` | Expressive pitch or gesture control | Optional | Support musical expression beyond binary timing. | If included, pitch, slide, intensity, aim direction, or gesture quality affects score, tone, or combat. |
| 10 | `movement_or_rail_sync` | Movement or rail sync | Optional | Support music-driven movement, lane shifts, dodges, or collection. | If included, player motion, obstacles, or collectibles are synchronized to song sections. |
| 11 | `combat_or_target_resolution` | Combat or target resolution | Optional | Support on-beat shooting, attacks, kills, or executions. | If included, rhythmic attacks produce clearer benefits and enemy feedback remains synchronized. |
| 12 | `latency_calibration_accessibility` | Latency calibration and accessibility | Conditional | Reduce device-latency frustration. | Calibration, loose timing mode, visual beat assist, audio mix controls, or remapping is scoped when relevant. |
| 13 | `final_rhythm_loop_acceptance` | Final rhythm loop acceptance | Always | Validate music, cue, input, scoring, and restart. | GDD or route plan links song start, beat sync, cues, input, score feedback, result, and retry; excluded modules have reasons. |