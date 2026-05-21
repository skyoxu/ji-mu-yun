# RPG Prototype Contract

## Intent

This contract defines the default implementation expectations for a short playable Godot RPG prototype routed through the repo-local `prototype-rpg-godot-zh` skill.

## Path Rules

- Never assume the repository root name.
- Never assume the Godot project is directly under the repo root.
- Never hardcode absolute asset paths.
- Store and exchange repo-relative paths only.

## Required Systems

### Map Scene

- A bounded playable map scene suitable for a short prototype loop.
- Movement and encounter entry logic.
- Reward chest/object placement support.
- Obstacle/path validation for generated or randomized layouts when needed.
- Scene switching that does not visually stack map and battle content.

### Battle Scene

- Separate battle presentation from map presentation.
- Visible player and enemy state.
- Time-based or turn-based resolution appropriate to the prototype record.
- Battle log remains visible through the result state unless the design explicitly changes it.
- Clean return path to map or prototype end state.

### Reward Flow

- Three-choice reward selection.
- Reward application to attributes, equipment, or passive skills according to the prototype record.
- Return to the correct scene after resolution.


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
- A prototype that navigates to the RPG shell but shows a blank screen after `Start Adventure` is not accepted.

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
