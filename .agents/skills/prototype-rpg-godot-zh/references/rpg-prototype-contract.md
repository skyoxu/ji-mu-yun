# RPG Prototype Contract

## Intent

This contract defines the default implementation expectations for a short playable Godot RPG prototype routed through the repo-local `prototype-rpg-godot-zh` skill.

## Path Rules

- Never assume the repository root name.
- Never assume the Godot project is directly under the repo root.
- Never hardcode absolute asset paths.
- Store and exchange repo-relative paths only.

## Required Systems

### User Input Traceability

- The project prototype contract is the first source of truth for RPG runtime behavior.
- `form_fields` and `input_traceability` from the project contract override this RPG contract whenever the user supplied a concrete value.
- RPG defaults, template scenes, default assets, and example balance values are fallback aids only. They must not replace concrete user values from the project contract.
- Encounter probability, movement rules, enemy stats, reward rules, map objectives, victory conditions, failure conditions, player fantasy, and the minimum playable loop must be derived from the user fields when those fields are non-empty.
- If the user says each movement increases encounter chance by a concrete value, that value must appear in runtime logic, visible feedback, tests, or an explicit needs-fix blocker.
- If the user gives enemy health, attack, reward, or win/fail rules, those concrete values must appear in battle logic, UI/state text, tests, or an explicit needs-fix blocker.
- A final RPG acceptance pass must fail when a concrete non-empty user field exists only in markdown or metadata and is not represented in scene flow, runtime behavior, UI feedback, test coverage, or a recorded needs-fix reason.


### JRPG First-Loop Capability Profile

This RPG route uses a JRPG first-loop capability profile. The profile does not require every RPG project to follow a DQ-like seven-step map-battle-reward script. It requires the implementation and iteration routes to select the capabilities that the project contract actually implies.

Capability vocabulary:

- Opening context and player objective.
- Field, town, or map navigation with stable control.
- Interaction/discovery beat such as NPC dialogue, chest, investigation, or objective discovery.
- Conflict entry when the project asks for encounter, battle, enemy, boss, or challenge.
- Battle or challenge resolution when a conflict exists.
- Party or character state readability when HP, stats, equipment, party, or status matter.
- Growth, reward, or consequence feedback when reward, item, level, choice, experience, or story consequence matters.
- Return-or-continue loop to the next playable state when the first loop continues.
- Quest or story progress when narrative or town events are central.
- Final first-loop acceptance across the selected capabilities.

DQ-like is one possible capability selection. Town-quest, story-event, exploration, or interaction-first JRPG prototypes may omit BattleScene or reward-choice requirements unless the project contract asks for them.

### Map Scene

- A bounded playable map scene suitable for a short prototype loop.
- Movement and encounter entry logic.
- A single shared coordinate parent for the visible map art, movement grid, and token overlay. The map art, grid, player token, enemy token, and objective tokens must not drift apart under layout resizing.
- If the prototype uses a 600x600 map and 10x10 grid, movement tokens must be positioned inside that same 600x600 layer.
- Reward chest/object placement support.
- Obstacle/path validation for generated or randomized layouts when needed.
- Scene switching that does not visually stack map and battle content.

### Battle Scene

- Separate battle presentation from map presentation.
- Visible player and enemy state.
- Time-based or turn-based resolution appropriate to the prototype record.
- `Attack` must not blindly resolve the entire battle and immediately leave the scene unless the prototype record explicitly calls for one-click full battle settlement.
- If a normal battle win produces reward options, the main prototype route must show the reward selection instead of returning directly to the map.
- The final-run victory flag is only for full prototype completion, not for deciding whether a normal battle reward panel should appear.
- Battle log remains visible through the result state unless the design explicitly changes it.
- Clean return path to map or prototype end state.

### Reward Flow

- Three-choice reward selection.
- Reward application to attributes, equipment, or passive skills according to the prototype record.
- Return to the correct scene after resolution, with the map scene visible, the player token visible, and movement input still active.


### Core Resource Routes

Keep the smallest possible set of explicit core resource paths for RPG prototypes:

- Map assets: `Game.Godot/Prototypes/DefaultRpgTemplate/Assets/Map/`
- Player assets: `Game.Godot/Prototypes/DefaultRpgTemplate/Assets/Player/`
- Enemy assets: `Game.Godot/Prototypes/DefaultRpgTemplate/Assets/Enemy/`

Scene ownership must remain separate:

- `MapScene` consumes map assets and player assets.
- `BattleScene` consumes player assets, enemy assets, and battle UI assets.
- The main prototype scene owns routing, not combat rules.


### Runtime Asset Instance Contract

- Active RPG prototype scenes must not rely on assets that are only present in a template folder if the current project slug owns the playable slice.
- Copy the required map, player, and enemy visual assets into the current prototype slug, for example `Game.Godot/Prototypes/dq-rpg/Assets/`.
- Do not keep `Game.Godot/.gdignore` in active RPG prototype projects because it blocks Godot resource import for runtime assets under `Game.Godot`.
- Each current prototype scene must use exact, category-safe node names for the three foundation assets:
  - `RpgMapAsset` uses a map/background/tile asset.
  - `RpgPlayerAsset` uses a player/hero/protagonist asset.
  - `RpgEnemyAsset` uses an enemy/monster/boss asset.
- Asset references must resolve to real `res://` files, and Godot import metadata must be generated before acceptance smoke.

### Start Adventure Visibility Contract

- `StartButton.Pressed` must switch from the menu to a visible map scene.
- `MapScene` must be under `CanvasLayer/UI` or an equivalent UI layout parent with non-zero viewport-sized layout.
- The map scene must remain visible after the click and contain visible map markers, a grid, status text, the player asset, and the enemy asset.
- The visible RPG map contract must always include `Grid`, plus one accepted marker set: legacy `Title` + `StatusLabel` under `MapScene`, or current HUD `HeaderLabel` + `StatsLabel` + `ObjectiveLabel` on the prototype shell. Near-equivalent third naming schemes such as `MapTitle` or `PositionLabel` are contract drift and must fail final acceptance.
- A prototype that navigates to the RPG shell but shows a blank screen after `Start Adventure` is not accepted.

### Main Scene Default Visibility Contract

- `Game.Godot/Scenes/Main.tscn` is the shared entry shell and must not show template/debug UI over prototype routes by default.
- The root-level `VBox`, `Overlays`, and `ScreenRoot` nodes must exist and must default to `visible = false`.
- Prototype creation, execute-next-goal, needs-fix, and final acceptance must preserve this default-hidden state.
- Showing these nodes later is allowed only through explicit runtime navigation or settings logic, not as the scene default.

### Assets And UI

- Support repo-local generated or hand-authored assets.
- Keep asset references configurable or discoverable, not hardcoded.
- UI must remain readable around generated backgrounds and scene art.
- Default RPG template assets live under `Game.Godot/Prototypes/DefaultRpgTemplate/Assets/`.
- Default RPG scene templates live under `Game.Godot/Prototypes/DefaultRpgTemplate/`.
- New RPG prototypes may reuse these assets directly for the first playable pass, but should keep the prototype slug and record paths repo-relative.

## Delivery Boundary

This contract is for prototype parity and TDD guidance only. It does not require:

- full progression systems
- long-term save data
- full narrative scripting
- formal production architecture
