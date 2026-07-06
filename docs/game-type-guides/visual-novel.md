## Visual Novel Specific Elements

<narrative-workflow-critical>
This game type is **narrative-critical**. You MUST run the Narrative Design workflow after completing the GDD to create:
- Complete story structure and script
- All character profiles and development arcs
- Branching story flowcharts
- Scene-by-scene breakdown
- Dialogue drafts
- Multiple route planning
</narrative-workflow-critical>

### Branching Story Structure

{{branching_structure}}

**Narrative design:**

- Story route types (character routes, plot branches)
- Branch points (choices, stats, flags)
- Convergence points
- Route length and pacing
- True/golden ending requirements
- Branch complexity (simple, moderate, complex)

### Choice Impact System

{{choice_impact}}

**Decision mechanics:**

- Choice types (immediate, delayed, hidden)
- Choice visualization (explicit, subtle, invisible)
- Point systems (affection, alignment, stats)
- Flag tracking
- Choice consequences
- Meaningful vs. cosmetic choices

### Route Design

{{route_design}}

**Route structure:**

- Common route (shared beginning)
- Individual routes (character-specific paths)
- Route unlock conditions
- Route length balance
- Route independence vs. interconnection
- Recommended play order

### Character Relationship Systems

{{relationship_systems}}

**Character mechanics:**

- Affection/friendship points
- Relationship milestones
- Character-specific scenes
- Dialogue variations based on relationship
- Multiple romance options (if applicable)
- Platonic vs. romantic paths

### Save/Load and Flowchart

{{save_flowchart}}

**Player navigation:**

- Save point frequency
- Quick save/load
- Scene skip functionality
- Flowchart/scene select (after completion)
- Branch tracking visualization
- Completion percentage

### Art Asset Requirements

{{art_assets}}

**Visual content:**

- Character sprites (poses, expressions)
- Background art (locations, times of day)
- CG artwork (key moments, endings)
- UI elements
- Special effects
- Asset quantity estimates

## Default Prototype Contract

This contract is workflow-consumed default guidance. Unless the user-confirmed GDD explicitly conflicts with it, `Always` scenes and modules must be included in the GDD outline, scene route, prototype plan, and repair/iteration planning. If the GDD overrides an `Always` item, record the override reason explicitly.

### Default Scenes

| scene_id | scene_name | purpose | required | entry_from | exits_to | minimum_playable_content |
| --- | --- | --- | --- | --- | --- | --- |
| dialogue_scene | Dialogue scene | Present speaker, portrait/background, text, and progression. | Always | start | choice_branch | Player advances dialogue with stable speaker/text presentation. |
| choice_branch | Choice branch | Offer meaningful options that set flags or branch content. | Always | dialogue_scene | dialogue_scene,branch_result | Choice changes state, route, relationship, or next scene. |
| branch_result | Branch result / ending preview | Branching needs consequence feedback. | Conditional | choice_branch | dialogue_scene | Different choice produces different visible result when branching is in scope. |

### Required Modules

| module_id | module_name | required_by_default | purpose | minimum_acceptance |
| --- | --- | --- | --- | --- |
| dialogue_renderer | Dialogue text, speaker, and visual presentation | Always | Visual novels rely on readable authored text flow. | Text advances, speaker identity displays, and layout is stable. |
| choice_system | Choice and branching system | Always | Player agency is usually expressed through choices. | Choices set flags and affect subsequent dialogue or scene. |
| state_flags | Flags, relationship, or route state | Always | Branching requires persistent state. | Choice/state persists and can be read by later content. |
| asset_slots | Background, portrait, and audio slots | Conditional | VN presentation depends on reusable media slots. | Placeholder assets exist unless the GDD explicitly text-only. |

## Module Matrix

This matrix is a first-loop planning convention for GDD creation and later module scoping. It does not override a project-specific brief, GDD, prototype type kit, or executable route contract.

Use only these default values: `Always`, `Conditional`, `Optional`, and `Out of Scope`.

| No | id | Module | Default | Purpose | Acceptance |
| --- | --- | --- | --- | --- | --- |
| 1 | `first_loop_context` | First-loop context and objective | Always | Establish the player role, starting state, and near-term objective for the first Visual Novel loop. | GDD or route plan identifies the player role, first playable state, short-term goal, and success or failure condition. |
| 2 | `branching_story_structure` | Branching Story Structure | Conditional | Plan the first-loop branching story structure needed for this game type. | If included, the GDD or route plan defines the branching story structure behavior, player-facing feedback, and how it changes the first-loop state. |
| 3 | `choice_impact_system` | Choice Impact System | Conditional | Plan the first-loop choice impact system needed for this game type. | If included, the GDD or route plan defines the choice impact system behavior, player-facing feedback, and how it changes the first-loop state. |
| 4 | `route_design` | Route Design | Conditional | Plan the first-loop route design needed for this game type. | If included, the GDD or route plan defines the route design behavior, player-facing feedback, and how it changes the first-loop state. |
| 5 | `character_relationship_systems` | Character Relationship Systems | Conditional | Plan the first-loop character relationship systems needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the character relationship systems behavior, player-facing feedback, and how it changes the first-loop state. |
| 6 | `save_load_and_flowchart` | Save/Load and Flowchart | Conditional | Plan the first-loop save/load and flowchart needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the save/load and flowchart behavior, player-facing feedback, and how it changes the first-loop state. |
| 7 | `art_asset_requirements` | Art Asset Requirements | Conditional | Plan the first-loop art asset requirements needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the art asset requirements behavior, player-facing feedback, and how it changes the first-loop state. |
| 8 | `final_visual_novel_loop_acceptance` | Final Visual Novel first-loop acceptance | Always | Validate that the selected Visual Novel modules form one coherent playable first loop. | GDD or route plan links entry, core action, feedback, result, and next state; excluded conditional or optional modules have clear reasons. |