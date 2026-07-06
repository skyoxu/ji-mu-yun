## Sports Game Specific Elements

### Sport-Specific Rules

{{sport_rules}}

**Rule implementation:**

- Core sport rules (scoring, fouls, violations)
- Match/game structure (quarters, periods, innings, etc.)
- Referee/umpire system
- Rule variations (if applicable)
- Simulation vs. arcade rule adherence

### Team and Player Systems

{{team_player}}

**Roster design:**

- Player attributes (speed, strength, skill, etc.)
- Position-specific stats
- Team composition
- Substitution mechanics
- Stamina/fatigue system
- Injury system (if applicable)

### Match Structure

{{match_structure}}

**Game flow:**

- Pre-match setup (lineups, strategies)
- In-match actions (plays, tactics, timeouts)
- Half-time/intermission
- Overtime/extra time rules
- Post-match results and stats

### Physics and Realism

{{physics_realism}}

**Simulation balance:**

- Physics accuracy (ball/puck physics, player movement)
- Realism vs. fun tradeoffs
- Animation systems
- Collision detection
- Weather/field condition effects

### Career and Season Modes

{{career_season}}

**Long-term modes:**

- Career mode structure
- Season/tournament progression
- Transfer/draft systems
- Team management
- Contract negotiations
- Sponsor/financial systems

### Multiplayer Modes

{{multiplayer}}

**Competitive play:**

- Local multiplayer (couch co-op)
- Online multiplayer
- Ranked/casual modes
- Ultimate team/card collection (if applicable)
- Co-op vs. AI

## Default Prototype Contract

This contract is workflow-consumed default guidance. Unless the user-confirmed GDD explicitly conflicts with it, `Always` scenes and modules must be included in the GDD outline, scene route, prototype plan, and repair/iteration planning. If the GDD overrides an `Always` item, record the override reason explicitly.

### Default Scenes

| scene_id | scene_name | purpose | required | entry_from | exits_to | minimum_playable_content |
| --- | --- | --- | --- | --- | --- | --- |
| match_field | Match field / court | Represent the sport space, player control, ball/object, and score. | Always | start | match_result | Playable possession/action loop with rules and score feedback. |
| team_setup | Team, player, or mode setup | Sports games often require side/team/player selection. | Conditional | start | match_field | Team/player selection exists when more than one side or athlete matters. |
| match_result | Match result | Matches need win/loss/time/score closure. | Always | match_field | match_field,team_setup | Score or timer creates an end state and restart/rematch path. |

### Required Modules

| module_id | module_name | required_by_default | purpose | minimum_acceptance |
| --- | --- | --- | --- | --- |
| sport_rules | Core sport rule and scoring model | Always | The prototype must encode the sport objective. | Legal scoring condition updates score and can end play. |
| player_control_physics | Player and object control/physics | Always | Sports feel requires embodied control. | Player and ball/puck/object movement collide and respond plausibly. |
| opponent_or_team_ai | Opponent, teammate, or second-player control | Always | Sports need contesting agents. | AI or second player can contest possession/position. |
| match_clock_hud | Clock, score, possession, or status HUD | Always | Players need match readability. | HUD updates score/time/status during play. |

## Module Matrix

This matrix is a first-loop planning convention for GDD creation and later module scoping. It does not override a project-specific brief, GDD, prototype type kit, or executable route contract.

Use only these default values: `Always`, `Conditional`, `Optional`, and `Out of Scope`.

| No | id | Module | Default | Purpose | Acceptance |
| --- | --- | --- | --- | --- | --- |
| 1 | `first_loop_context` | First-loop context and objective | Always | Establish the player role, starting state, and near-term objective for the first Sports loop. | GDD or route plan identifies the player role, first playable state, short-term goal, and success or failure condition. |
| 2 | `sport_specific_rules` | Sport-Specific Rules | Conditional | Plan the first-loop sport-specific rules needed for this game type. | If included, the GDD or route plan defines the sport-specific rules behavior, player-facing feedback, and how it changes the first-loop state. |
| 3 | `team_and_player_systems` | Team and Player Systems | Conditional | Plan the first-loop team and player systems needed for this game type. | If included, the GDD or route plan defines the team and player systems behavior, player-facing feedback, and how it changes the first-loop state. |
| 4 | `match_structure` | Match Structure | Conditional | Plan the first-loop match structure needed for this game type. | If included, the GDD or route plan defines the match structure behavior, player-facing feedback, and how it changes the first-loop state. |
| 5 | `physics_and_realism` | Physics and Realism | Conditional | Plan the first-loop physics and realism needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the physics and realism behavior, player-facing feedback, and how it changes the first-loop state. |
| 6 | `career_and_season_modes` | Career and Season Modes | Conditional | Plan the first-loop career and season modes needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the career and season modes behavior, player-facing feedback, and how it changes the first-loop state. |
| 7 | `multiplayer_modes` | Multiplayer Modes | Conditional | Plan the first-loop multiplayer modes needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the multiplayer modes behavior, player-facing feedback, and how it changes the first-loop state. |
| 8 | `final_sports_loop_acceptance` | Final Sports first-loop acceptance | Always | Validate that the selected Sports modules form one coherent playable first loop. | GDD or route plan links entry, core action, feedback, result, and next state; excluded conditional or optional modules have clear reasons. |