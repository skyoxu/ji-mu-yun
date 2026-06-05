---
name: prototype-survivorslike-godot-zh
description: Use when the prototype top-level router has identified game_type survivorslike / Vampire Survivors-like and the repo should implement or refine a short playable Godot arena-survival prototype.
---

# Prototype Survivors-like Godot Route

## Purpose

This skill is the route playbook for short playable Vampire Survivors-like Godot prototypes. It keeps prototype creation, iteration planning, execute-next-goal, needs-fix, repair-plan, revalidation, and final acceptance on an arena-survival first-loop profile instead of the generic prototype route.

## Route Recovery Protocol

Before planning, executing, repairing, or validating a hosted project:

1. Read the project execution guide.
2. Read the latest prototype contract.
3. Read the latest prototype state and iteration-plan state.
4. Read the current goal and the needs-fix repair ledger when repairing.
5. Use this skill and `references/survivorslike-prototype-contract.md` as the game-type design route.

Do not use repository-level `AGENTS.md` as hosted project memory.

## Vampire Survivors-like First-Loop Capability Scope

- Run start and survival objective.
- Arena movement and camera readability.
- Enemy spawn pressure curve.
- Auto-attack or core weapon loop.
- Hit, damage, health, and death feedback.
- Pickup and resource collection.
- Level-up choice or power selection.
- Build growth and power fantasy feedback.
- Escalation event or mini-milestone.
- Run end, summary, and restart loop.

## Planning Rules

- The iteration plan should use the capability scope above as the semantic graph.
- Keep each goal small enough to execute independently.
- Do not collapse movement, spawning, weapon, pickup, level-up, escalation, and final summary into one broad step.
- Project-specific form values override this route contract whenever present.
- Do not build long-term meta-progression, save systems, full roguelite economy, or production-scale content unless explicitly requested.

## Execution Rules

- The player fantasy is survival under pressure while becoming stronger.
- Prioritize readable movement, pressure, hit feedback, and pickup/upgrade loops over decorative content.
- A valid first pass may use simple shapes or generated sprites, but runtime assets must resolve through repo-relative `res://` paths.
- Every upgrade must produce visible runtime behavior or a clear needs-fix blocker.

## Validation And Repair Rules

- Needs-fix runs must repair the current goal only.
- Do not advance to later capabilities while the current capability has failed validation.
- Final acceptance is only valid after the selected first-loop capabilities work end-to-end and package readiness is proven.

