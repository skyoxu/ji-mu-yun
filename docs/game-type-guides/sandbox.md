## Sandbox Game Specific Elements

### Creation Tools

{{creation_tools}}

**Building mechanics:**

- Tool types (place, delete, modify, paint)
- Object library (blocks, props, entities)
- Precision controls (snap, free, grid)
- Copy/paste and templates
- Undo/redo system
- Import/export functionality

### Physics and Building Systems

{{physics_building}}

**System simulation:**

- Physics engine (rigid body, soft body, fluids)
- Structural integrity (if applicable)
- Destruction mechanics
- Material properties
- Constraint systems (joints, hinges, motors)
- Interactive simulations

### Sharing and Community

{{sharing_community}}

**Social features:**

- Creation sharing (workshop, gallery)
- Discoverability (search, trending, featured)
- Rating and feedback systems
- Collaboration tools
- Modding support
- User-generated content moderation

### Constraints and Rules

{{constraints_rules}}

**Game design:**

- Creative mode (unlimited resources, no objectives)
- Challenge mode (limited resources, objectives)
- Budget/point systems (if competitive)
- Build limits (size, complexity)
- Rulesets and game modes
- Victory conditions (if applicable)

### Tools and Editing

{{tools_editing}}

**Advanced features:**

- Logic gates/scripting (if applicable)
- Animation tools
- Terrain editing
- Weather/environment controls
- Lighting and effects
- Testing/preview modes

### Emergent Gameplay

{{emergent_gameplay}}

**Player creativity:**

- Unintended creations (embracing exploits)
- Community-defined challenges
- Speedrunning player creations
- Cross-creation interaction
- Viral moments and showcases
- Evolution of the meta

### Module Matrix

This matrix is a first-loop planning convention for GDD creation and later module scoping. It does not override a project-specific brief, GDD, prototype type kit, or executable route contract.

Use only these default values: `Always`, `Conditional`, `Optional`, and `Out of Scope`.

| No | id | Module | Default | Purpose | Acceptance |
| --- | --- | --- | --- | --- | --- |
| 1 | `first_loop_context` | First-loop context and objective | Always | Establish the player role, starting state, and near-term objective for the first Sandbox loop. | GDD or route plan identifies the player role, first playable state, short-term goal, and success or failure condition. |
| 2 | `creation_tools` | Creation Tools | Conditional | Plan the first-loop creation tools needed for this game type. | If included, the GDD or route plan defines the creation tools behavior, player-facing feedback, and how it changes the first-loop state. |
| 3 | `physics_and_building_systems` | Physics and Building Systems | Conditional | Plan the first-loop physics and building systems needed for this game type. | If included, the GDD or route plan defines the physics and building systems behavior, player-facing feedback, and how it changes the first-loop state. |
| 4 | `sharing_and_community` | Sharing and Community | Conditional | Plan the first-loop sharing and community needed for this game type. | If included, the GDD or route plan defines the sharing and community behavior, player-facing feedback, and how it changes the first-loop state. |
| 5 | `constraints_and_rules` | Constraints and Rules | Conditional | Plan the first-loop constraints and rules needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the constraints and rules behavior, player-facing feedback, and how it changes the first-loop state. |
| 6 | `tools_and_editing` | Tools and Editing | Conditional | Plan the first-loop tools and editing needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the tools and editing behavior, player-facing feedback, and how it changes the first-loop state. |
| 7 | `emergent_gameplay` | Emergent Gameplay | Conditional | Plan the first-loop emergent gameplay needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the emergent gameplay behavior, player-facing feedback, and how it changes the first-loop state. |
| 8 | `final_sandbox_loop_acceptance` | Final Sandbox first-loop acceptance | Always | Validate that the selected Sandbox modules form one coherent playable first loop. | GDD or route plan links entry, core action, feedback, result, and next state; excluded conditional or optional modules have clear reasons. |