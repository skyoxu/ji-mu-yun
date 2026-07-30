# Repair Review Handoff

After a P0/P1 repair reaches its plan-local terminal predicate, build one
append-only `acceptance-repair-completeness-request.v1` with
`tools/build_repair_review_handoff.py`. Supply the original execution-plan
acceptance target, its stable Bootstrap lineage family, consumed semantic
round count, current predecessor run, hash-bound baseline and complete candidate
content manifests, changed files, direct consumers, targeted tests, validation
references, generated sibling-callsite inventories, and registered
producer/consumer composition receipts.

Immediately pass that request to the Acceptance-owned deterministic audit:

```text
py -3 .agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py audit-repair-completeness --request <handoff.json> --out <repair-completeness.json>
```

The audit must discover every matching sibling callsite from declared search
roots and require each one to be changed or explicitly excluded. Every
declared changed path must exactly equal the complete candidate manifest's
derived change set; Quick Dev's list is not authority. Every composition
receipt must come from a successful registered controlled command invoked with
one `--input-path` for each producer and consumer. The audit binds every
present changed path to its content hash and every deleted changed path to its
baseline hash before routing can continue.
Each composition check must cover a changed path, list its consumer in
`directConsumers`, and list its receipt in `validationRefs`.
Preserve both artifacts under the original target plan. They authorize
nothing; `run-refactor-implementation-acceptance` owns the subsequent route.

Do not create a review successor, change `lineageFamilyId`, reset consumed
rounds, invoke Bootstrap, or infer `deterministic_only`,
`focused_repair_review`, `full_implementation_conformance`, or `manual_pause`
inside Quick Dev.
