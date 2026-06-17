---
name: prototype-deckbuilder-godot-zh
description: "Use when the prototype top-level router has identified game_type deckbuilder / roguelike deckbuilder / card-building battler and the repo should implement or refine a short playable Godot deckbuilder prototype with cards, deck flow, resource turns, enemy intent, rewards, deck mutation, and optional route nodes."
---

# Prototype Deckbuilder Godot Route

## Purpose

This skill is the route playbook for short playable Godot deckbuilder prototypes. It keeps prototype creation, iteration planning, execute-next-goal, needs-fix, repair-plan, revalidation, and final acceptance on a card-building first-loop profile instead of the generic prototype route.

## Required Reading

1. `docs/workflows/prototype-lane.md`
2. `docs/workflows/prototype-tdd.md`
3. `docs/workflows/prototype-7day-playable-godot-zh.md`
4. `docs/prototype-type-kits/deckbuilder.md`
5. `references/deckbuilder-prototype-contract.md`

`AGENTS.md` is required only when maintaining the Phase A platform repo, workflow code, docs, or this skill. Hosted deckbuilder project routes must not use `AGENTS.md` as project recovery memory.

## Hosted Route Recovery Protocol

Before any hosted prototype route implements or repairs a game project, restore project memory from project-level route files, not from `AGENTS.md`:

1. Read the resolved game-type route profile and this route skill prompt block.
2. Read `meta/project-execution-guide.md` as the project-level `/new` recovery protocol.
3. Read `meta/routes/prototype-contract/latest.json` as the primary project contract source; concrete user form fields and `input_traceability` override templates.
4. Read only the latest route state relevant to the current route and current step, such as `meta/routes/prototype/latest.json`, `meta/routes/iteration-plan/latest.json`, `meta/routes/execute-next-goal/latest.json`, `meta/routes/prototype-repair/latest.json`, or `meta/routes/repair-plan/latest.json`.
5. For needs-fix, read the current step `meta/routes/needs-fix/step-XX/repair-ledger.json` before changing files and update it with fixed, remaining, and newly found blockers.
6. Treat the latest platform validation blocker as higher priority than older assistant summaries, route state, or repair ledger memory.

If a mandatory recovery source is missing, fail closed or record the missing source explicitly.

## Operating Rules

- Speak to the user in Chinese.
- Keep code, scripts, tests, comments, and logs in English.
- Keep Chinese documentation writes UTF-8.
- Do not hardcode absolute project paths, Godot project paths, or asset paths.
- Resolve all repo paths from the active repository root.
- Prefer repo-relative paths when recording metadata.
- Treat this skill as prototype-lane only, not Chapter 6 formal delivery.
- Player-visible Godot text defaults to Chinese unless the user explicitly asks for another language or the game fiction requires it.

## First-Loop Capability Scope

Deckbuilder routes use a first-loop capability profile:

1. Run context and objective.
2. Starter deck readability.
3. Resource and turn rules.
4. Enemy intent or pressure source.
5. Card play resolution feedback.
6. Deck cycle and hand flow.
7. Combat win/fail resolution.
8. Post-combat card draft or reward.
9. Deck mutation feedback.
10. Map or route choice only when requested.
11. Final deckbuilder first-loop acceptance.

## Planning Rules

- Keep each goal small enough to execute independently.
- Do not collapse deck readability, energy/turn rules, card play, deck cycling, combat result, reward draft, and deck mutation into one broad goal.
- `map_or_route_choice` is conditional. Only include it when the project asks for route map, nodes, events, shops, elites, branches, path choice, or Slay-the-Spire-like structure.
- Project-specific form values override this route contract whenever present.
- Do not build full collection economy, ranked modes, card packs, long-term balance, full card pools, or production-scale content unless explicitly requested.

## Runtime Expectations

- Use a simple playable card battle as the default prototype shape.
- The player should see a run objective, readable cards, visible energy/cost, enemy intent, and immediate card resolution feedback.
- The deck model should show at least one of hand, draw pile, discard pile, deck list, or starter deck summary.
- At least one card must be playable and must affect visible state.
- Cards must move through at least one draw, discard, shuffle, exhaust, or equivalent flow.
- Combat must reach victory or defeat.
- Victory should open reward/card draft choices unless the project contract explicitly replaces reward with another deck mutation.
- Selecting a reward should visibly change deck or run state.
- Optional route maps should feel similar to the `C:\gametype\card` template at a prototype level: map/route choices, combat node, reward, event/shop/rest only when requested. Do not copy that absolute path or make it a hosted dependency.

## Validation And Repair Rules

- Needs-fix runs must repair the current goal only.
- Do not advance to later capabilities while the current capability has failed validation.
- Runtime proof beats code-only markers. If a card effect, reward, or deck mutation exists only in code, record needs-fix.
- Final acceptance is only valid after selected first-loop capabilities work end-to-end and package readiness is proven.

## Repo-Relative References

- Skill file: `.agents/skills/prototype-deckbuilder-godot-zh/SKILL.md`
- Contract file: `.agents/skills/prototype-deckbuilder-godot-zh/references/deckbuilder-prototype-contract.md`
