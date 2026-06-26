## Party Game Specific Elements

### Minigame Variety

{{minigame_variety}}

**Minigame design:**

- Minigame count (launch + DLC)
- Genre variety (racing, puzzle, reflex, trivia, etc.)
- Minigame length (15-60 seconds typical)
- Skill vs. luck balance
- Team vs. FFA minigames
- Accessibility across skill levels

### Turn Structure

{{turn_structure}}

**Game flow:**

- Board game structure (if applicable)
- Turn order (fixed, random, earned)
- Turn actions (roll dice, move, minigame, etc.)
- Event spaces
- Special mechanics (warp, steal, bonus)
- Match length (rounds, turns, time)

### Player Elimination vs. Points

{{scoring_elimination}}

**Competition design:**

- Points-based (everyone plays to the end)
- Elimination (last player standing)
- Hybrid systems
- Comeback mechanics
- Handicap systems
- Victory conditions

### Local Multiplayer UX

{{local_multiplayer}}

**Couch co-op design:**

- Controller sharing vs. individual controllers
- Screen layout (split-screen, shared screen)
- Turn clarity (whose turn indicators)
- Spectator experience (watching others play)
- Player join/drop mechanics
- Tutorial integration for new players

### Accessibility and Skill Range

{{accessibility}}

**Inclusive design:**

- Skill floor (easy to understand)
- Skill ceiling (depth for experienced players)
- Luck elements to balance skill gaps
- Assist modes or handicaps
- Child-friendly content
- Colorblind modes and accessibility

### Session Length

{{session_length}}

**Time management:**

- Quick play (5-10 minutes)
- Standard match (15-30 minutes)
- Extended match (30+ minutes)
- Drop-in/drop-out support
- Pause and resume
- Party management (hosting, invites)

### Module Matrix

This matrix is a first-loop planning convention for GDD creation and later module scoping. It does not override a project-specific brief, GDD, prototype type kit, or executable route contract.

Use only these default values: `Always`, `Conditional`, `Optional`, and `Out of Scope`.

| No | id | Module | Default | Purpose | Acceptance |
| --- | --- | --- | --- | --- | --- |
| 1 | `first_loop_context` | First-loop context and objective | Always | Establish the player role, starting state, and near-term objective for the first Party Game loop. | GDD or route plan identifies the player role, first playable state, short-term goal, and success or failure condition. |
| 2 | `minigame_variety` | Minigame Variety | Conditional | Plan the first-loop minigame variety needed for this game type. | If included, the GDD or route plan defines the minigame variety behavior, player-facing feedback, and how it changes the first-loop state. |
| 3 | `turn_structure` | Turn Structure | Conditional | Plan the first-loop turn structure needed for this game type. | If included, the GDD or route plan defines the turn structure behavior, player-facing feedback, and how it changes the first-loop state. |
| 4 | `player_elimination_vs_points` | Player Elimination vs. Points | Conditional | Plan the first-loop player elimination vs. points needed for this game type. | If included, the GDD or route plan defines the player elimination vs. points behavior, player-facing feedback, and how it changes the first-loop state. |
| 5 | `local_multiplayer_ux` | Local Multiplayer UX | Conditional | Plan the first-loop local multiplayer ux needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the local multiplayer ux behavior, player-facing feedback, and how it changes the first-loop state. |
| 6 | `accessibility_and_skill_range` | Accessibility and Skill Range | Conditional | Plan the first-loop accessibility and skill range needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the accessibility and skill range behavior, player-facing feedback, and how it changes the first-loop state. |
| 7 | `session_length` | Session Length | Conditional | Plan the first-loop session length needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the session length behavior, player-facing feedback, and how it changes the first-loop state. |
| 8 | `final_party_game_loop_acceptance` | Final Party Game first-loop acceptance | Always | Validate that the selected Party Game modules form one coherent playable first loop. | GDD or route plan links entry, core action, feedback, result, and next state; excluded conditional or optional modules have clear reasons. |