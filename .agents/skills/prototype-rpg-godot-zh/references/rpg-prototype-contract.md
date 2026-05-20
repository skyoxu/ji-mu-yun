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
