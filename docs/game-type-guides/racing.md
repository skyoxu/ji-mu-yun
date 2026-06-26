## Racing Game Specific Elements

### Vehicle Handling and Physics

{{vehicle_physics}}

**Handling systems:**

- Physics model (arcade vs. simulation vs. hybrid)
- Vehicle stats (speed, acceleration, handling, braking, weight)
- Drift mechanics
- Collision physics
- Vehicle damage system (if applicable)

### Vehicle Roster

{{vehicle_roster}}

**Vehicle design:**

- Vehicle types (cars, bikes, boats, etc.)
- Vehicle classes (lightweight, balanced, heavyweight)
- Unlock progression
- Customization options (visual, performance)
- Balance considerations

### Track Design

{{track_design}}

**Course design:**

- Track variety (circuits, point-to-point, open world)
- Track length and lap counts
- Hazards and obstacles
- Shortcuts and alternate paths
- Track-specific mechanics
- Environmental themes

### Race Mechanics

{{race_mechanics}}

**Core racing:**

- Starting mechanics (countdown, reaction time)
- Checkpoint system
- Lap tracking and position
- Slipstreaming/drafting
- Pit stops (if applicable)
- Weather and time-of-day effects

### Powerups and Boost

{{powerups_boost}}

**Enhancement systems (if arcade-style):**

- Powerup types (offensive, defensive, utility)
- Boost mechanics (drift boost, nitro, slipstream)
- Item balance
- Counterplay mechanics
- Powerup placement on track

### Game Modes

{{game_modes}}

**Mode variety:**

- Standard race
- Time trial
- Elimination/knockout
- Battle/arena modes
- Career/campaign mode
- Online multiplayer modes

### Progression and Unlocks

{{progression}}

**Player advancement:**

- Career structure
- Unlockable vehicles and tracks
- Currency/rewards system
- Achievements and challenges
- Skill-based unlocks vs. time-based

### Module Matrix

This matrix is a first-loop planning convention for GDD creation and later module scoping. It does not override a project-specific brief, GDD, prototype type kit, or executable route contract.

Use only these default values: `Always`, `Conditional`, `Optional`, and `Out of Scope`.

| No | id | Module | Default | Purpose | Acceptance |
| --- | --- | --- | --- | --- | --- |
| 1 | `first_loop_context` | First-loop context and objective | Always | Establish the player role, starting state, and near-term objective for the first Racing loop. | GDD or route plan identifies the player role, first playable state, short-term goal, and success or failure condition. |
| 2 | `vehicle_handling_and_physics` | Vehicle Handling and Physics | Conditional | Plan the first-loop vehicle handling and physics needed for this game type. | If included, the GDD or route plan defines the vehicle handling and physics behavior, player-facing feedback, and how it changes the first-loop state. |
| 3 | `vehicle_roster` | Vehicle Roster | Conditional | Plan the first-loop vehicle roster needed for this game type. | If included, the GDD or route plan defines the vehicle roster behavior, player-facing feedback, and how it changes the first-loop state. |
| 4 | `track_design` | Track Design | Conditional | Plan the first-loop track design needed for this game type. | If included, the GDD or route plan defines the track design behavior, player-facing feedback, and how it changes the first-loop state. |
| 5 | `race_mechanics` | Race Mechanics | Conditional | Plan the first-loop race mechanics needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the race mechanics behavior, player-facing feedback, and how it changes the first-loop state. |
| 6 | `powerups_and_boost` | Powerups and Boost | Conditional | Plan the first-loop powerups and boost needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the powerups and boost behavior, player-facing feedback, and how it changes the first-loop state. |
| 7 | `game_modes` | Game Modes | Conditional | Plan the first-loop game modes needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the game modes behavior, player-facing feedback, and how it changes the first-loop state. |
| 8 | `progression_and_unlocks` | Progression and Unlocks | Conditional | Plan the first-loop progression and unlocks needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the progression and unlocks behavior, player-facing feedback, and how it changes the first-loop state. |
| 9 | `final_racing_loop_acceptance` | Final Racing first-loop acceptance | Always | Validate that the selected Racing modules form one coherent playable first loop. | GDD or route plan links entry, core action, feedback, result, and next state; excluded conditional or optional modules have clear reasons. |