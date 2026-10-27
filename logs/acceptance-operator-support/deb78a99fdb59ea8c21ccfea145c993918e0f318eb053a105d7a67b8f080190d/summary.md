# Acceptance status

Status: completed

Blocker: None reported

No recovery required. Suggested additional checks are advisory. Share the reviewer packet if review is desired.

## Actions

- validate-vdd-contract: completed
- validate-code-review-route: completed
- validate-acceptance-routing: completed
- validate-acceptance-package: completed

## Suggested checks

- validate-code-review-route: ["/tmp/ji-mu-yun-light-qd-venv/bin/python", "-B", "execution-plans/2026-10-27-toolchain-light-optimizations-fixture-ready/acceptance-inputs/preparation-20261027/unit-budget.py", "validate-code-review-route", "/tmp/ji-mu-yun-light-qd-venv/bin/python", "-B", ".agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py", "resolve-code-review-policy", "--policy", ".agents/skills/run-refactor-implementation-acceptance/policies/toolchain-code-review.v1.json", "--baseline", "execution-plans/2026-10-27-toolchain-light-optimizations-fixture-ready/acceptance-inputs/acceptance-light-20261027/baseline-content-manifest.v1.json", "--candidate", "execution-plans/2026-10-27-toolchain-light-optimizations-fixture-ready/acceptance-inputs/acceptance-light-20261027/candidate-content-manifest.v1.json", "--adapter-hash", "sha256:debeefa0a247126d957a35ce7ff3fed6d029bcf188041dcda547e688dc1cc110"] — Registered argv names an affected file.
- validate-acceptance-routing: ["/tmp/ji-mu-yun-light-qd-venv/bin/python", "-B", "execution-plans/2026-10-27-toolchain-light-optimizations-fixture-ready/acceptance-inputs/preparation-20261027/unit-budget.py", "validate-acceptance-routing", "/tmp/ji-mu-yun-light-qd-venv/bin/python", "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", ".agents/skills/run-refactor-implementation-acceptance/tests/test_toolchain_domain.py", ".agents/skills/run-refactor-implementation-acceptance/tests/test_trusted_knowledge_validator.py", ".agents/skills/run-refactor-implementation-acceptance/tests/test_knowledge_context.py", ".agents/skills/run-refactor-implementation-acceptance/tests/test_knowledge_degraded_execution.py"] — Registered argv names an affected file.
- Unregistered suggestion: ["py", "-3", "-m", "pytest", ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_cer_behavior_routing.py", "-q"] — Affected Python test; suggestion is not a registered required check.
- Unregistered suggestion: ["py", "-3", "-m", "pytest", ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_cer_case_evidence.py", "-q"] — Affected Python test; suggestion is not a registered required check.
- Unregistered suggestion: ["py", "-3", "-m", "pytest", ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_ch456_fresh_medium_task.py", "-q"] — Affected Python test; suggestion is not a registered required check.
- Unregistered suggestion: ["py", "-3", "-m", "pytest", ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_ch456_q1_planned_preflight.py", "-q"] — Affected Python test; suggestion is not a registered required check.
- Unregistered suggestion: ["py", "-3", "-m", "pytest", ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_ch456_stable_runner.py", "-q"] — Affected Python test; suggestion is not a registered required check.
- Unregistered suggestion: ["py", "-3", "-m", "pytest", ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_execution_session.py", "-q"] — Affected Python test; suggestion is not a registered required check.
- Unregistered suggestion: ["py", "-3", "-m", "pytest", ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_light_consumer_admission.py", "-q"] — Affected Python test; suggestion is not a registered required check.
- Unregistered suggestion: ["py", "-3", "-m", "pytest", ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_q4_no_production_change.py", "-q"] — Affected Python test; suggestion is not a registered required check.
- Unregistered suggestion: ["py", "-3", "-m", "pytest", ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_quick_dev_delivered_inputs.py", "-q"] — Affected Python test; suggestion is not a registered required check.
- Unregistered suggestion: ["py", "-3", "-m", "pytest", ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_stage_reentry.py", "-q"] — Affected Python test; suggestion is not a registered required check.
- Unregistered suggestion: ["py", "-3", "-m", "pytest", ".agents/skills/vdd-execution-plan/scripts/tests/test_ch456_compile_watchdog.py", "-q"] — Affected Python test; suggestion is not a registered required check.
- Unregistered suggestion: ["py", "-3", "-m", "pytest", ".agents/skills/vdd-execution-plan/scripts/tests/test_ch456_compiler_closure.py", "-q"] — Affected Python test; suggestion is not a registered required check.
- Unregistered suggestion: ["py", "-3", "-m", "pytest", ".agents/skills/vdd-execution-plan/scripts/tests/test_ch456_failed_resume.py", "-q"] — Affected Python test; suggestion is not a registered required check.
- Unregistered suggestion: ["py", "-3", "-m", "pytest", ".agents/skills/vdd-execution-plan/scripts/tests/test_execution_preflight.py", "-q"] — Affected Python test; suggestion is not a registered required check.
- Unregistered suggestion: ["py", "-3", "-m", "pytest", ".agents/skills/vdd-execution-plan/scripts/tests/test_light_admission.py", "-q"] — Affected Python test; suggestion is not a registered required check.
- Unregistered suggestion: ["py", "-3", "-m", "pytest", ".agents/skills/vdd-execution-plan/scripts/tests/test_light_delivery_boundaries.py", "-q"] — Affected Python test; suggestion is not a registered required check.
- Unregistered suggestion: ["py", "-3", "-m", "pytest", ".agents/skills/vdd-execution-plan/scripts/tests/test_light_dependency_revision.py", "-q"] — Affected Python test; suggestion is not a registered required check.
- Unregistered suggestion: ["py", "-3", "-m", "pytest", ".agents/skills/vdd-execution-plan/scripts/tests/test_planned_test_declaration_handoff.py", "-q"] — Affected Python test; suggestion is not a registered required check.
- Unregistered suggestion: ["py", "-3", "-m", "pytest", ".agents/skills/vdd-execution-plan/scripts/tests/test_public_source_cache_resume.py", "-q"] — Affected Python test; suggestion is not a registered required check.
- Unregistered suggestion: ["py", "-3", "-m", "pytest", ".agents/skills/vdd-execution-plan/scripts/tests/test_public_v3_pause.py", "-q"] — Affected Python test; suggestion is not a registered required check.
- Unregistered suggestion: ["py", "-3", "-m", "pytest", ".agents/skills/vdd-execution-plan/scripts/tests/test_published_v1_source_bound_split.py", "-q"] — Affected Python test; suggestion is not a registered required check.
- Unregistered suggestion: ["py", "-3", "-m", "pytest", ".agents/skills/vdd-execution-plan/scripts/tests/test_published_v3_compiler_integration.py", "-q"] — Affected Python test; suggestion is not a registered required check.
- Unregistered suggestion: ["py", "-3", "-m", "pytest", ".agents/skills/vdd-execution-plan/scripts/tests/test_quick_dev_handoff.py", "-q"] — Affected Python test; suggestion is not a registered required check.
- Unregistered suggestion: ["py", "-3", "-m", "pytest", ".agents/skills/vdd-execution-plan/scripts/tests/test_runtime_role_only_handoff.py", "-q"] — Affected Python test; suggestion is not a registered required check.
- Unregistered suggestion: ["py", "-3", "-m", "pytest", ".agents/skills/vdd-execution-plan/scripts/tests/test_semantic_compiler_ch456.py", "-q"] — Affected Python test; suggestion is not a registered required check.
- Unregistered suggestion: ["py", "-3", "-m", "pytest", ".agents/skills/vdd-execution-plan/scripts/tests/test_slice_dependency_projection.py", "-q"] — Affected Python test; suggestion is not a registered required check.
- Unregistered suggestion: ["py", "-3", "-m", "pytest", ".agents/skills/vdd-execution-plan/scripts/tests/test_static_primary_handoff.py", "-q"] — Affected Python test; suggestion is not a registered required check.
- Unregistered suggestion: ["py", "-3", "-m", "pytest", ".agents/skills/vdd-execution-plan/scripts/tests/test_v3_candidate_contract_repair.py", "-q"] — Affected Python test; suggestion is not a registered required check.
- Unregistered suggestion: ["py", "-3", "-m", "pytest", ".agents/skills/vdd-execution-plan/scripts/tests/test_v3_test_path_input_repair.py", "-q"] — Affected Python test; suggestion is not a registered required check.
- Unregistered suggestion: ["py", "-3", "-m", "pytest", ".agents/skills/vdd-execution-plan/scripts/tests/test_vdd_delivered_inputs.py", "-q"] — Affected Python test; suggestion is not a registered required check.

## Limits

- One-hop hints only; dynamic imports and runtime wiring may be absent.
- Name-only Python matches are heuristic; inspect their source before adding checks.
- Source inventory truncated to 5000 files.
- Oversize source not scanned: .agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py
- Oversize source not scanned: .agents/skills/run-phase-bootstrap-review/tests/test_bootstrap_review.py
- Source not scanned: .agents/skills/vdd-execution-plan/scripts/tests/test_ch456_v3_inline_context_repair.py
- Oversize source not scanned: .skill-input-work/acceptance-08-05-c15c2839-budget3/54bf3609b2474498ade77afa4f27cac2/prepared.json
- Oversize source not scanned: .skill-input-work/acceptance-08-05-c15c2839-budget3/65b417fc8d06474387047f66cd6238cd/prepared.json
- Oversize source not scanned: .skill-input-work/acceptance-08-05-c15c2839-budget3/d3181296941d498b98d63a970ce639e7/prepared.json
- Oversize source not scanned: PhaseA.Platform.Tests/Browser/BrowserUiRendererTests.cs
- Oversize source not scanned: PhaseA.Platform.Tests/Runs/PrototypeQuickFixServiceTests.cs
- Oversize source not scanned: PhaseA.Platform/Browser/BrowserUiRenderer.cs
- Oversize source not scanned: PhaseA.Platform/Data/PhaseAMetadataStore.cs
- Oversize source not scanned: PhaseA.Platform/Runs/PrototypeIterationPlanService.cs
- Oversize source not scanned: execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/100-implementation-acceptance-matrix.md
- Oversize source not scanned: execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/schemas/godot-ui-style-contract.v1.field-map.json
- Oversize source not scanned: execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/schemas/implementation-acceptance-matrix.v1.json
- Oversize source not scanned: execution-plans/2026-07-15-repository-maintenance-tdd-adapter/.acceptance-snapshots/2026-08-04-rmap-acceptance-r10/.agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py
- Oversize source not scanned: execution-plans/2026-07-15-repository-maintenance-tdd-adapter/.acceptance-snapshots/2026-08-04-rmap-acceptance-r10/.agents/skills/run-phase-bootstrap-review/tests/test_bootstrap_review.py
- Oversize source not scanned: execution-plans/2026-07-15-repository-maintenance-tdd-adapter/.acceptance-snapshots/2026-08-04-rmap-acceptance-r10/execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/predicate-artifact-closure.v1.json
- Oversize source not scanned: execution-plans/2026-07-15-repository-maintenance-tdd-adapter/.acceptance-snapshots/2026-08-04-rmap-acceptance-r11/.agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py
- Oversize source not scanned: execution-plans/2026-07-15-repository-maintenance-tdd-adapter/.acceptance-snapshots/2026-08-04-rmap-acceptance-r11/.agents/skills/run-phase-bootstrap-review/tests/test_bootstrap_review.py
- Oversize source not scanned: execution-plans/2026-07-15-repository-maintenance-tdd-adapter/.acceptance-snapshots/2026-08-04-rmap-acceptance-r11/execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/predicate-artifact-closure.v1.json
- Oversize source not scanned: execution-plans/2026-07-15-repository-maintenance-tdd-adapter/.acceptance-snapshots/2026-08-04-rmap-acceptance-r12/.agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py
- Oversize source not scanned: execution-plans/2026-07-15-repository-maintenance-tdd-adapter/.acceptance-snapshots/2026-08-04-rmap-acceptance-r12/.agents/skills/run-phase-bootstrap-review/tests/test_bootstrap_review.py
- Oversize source not scanned: execution-plans/2026-07-15-repository-maintenance-tdd-adapter/.acceptance-snapshots/2026-08-04-rmap-acceptance-r12/execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/predicate-artifact-closure.v1.json
- Oversize source not scanned: execution-plans/2026-07-15-repository-maintenance-tdd-adapter/.acceptance-snapshots/2026-08-04-rmap-acceptance-r13/.agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py
- Oversize source not scanned: execution-plans/2026-07-15-repository-maintenance-tdd-adapter/.acceptance-snapshots/2026-08-04-rmap-acceptance-r13/.agents/skills/run-phase-bootstrap-review/tests/test_bootstrap_review.py
- Oversize source not scanned: execution-plans/2026-07-15-repository-maintenance-tdd-adapter/.acceptance-snapshots/2026-08-04-rmap-acceptance-r13/execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/predicate-artifact-closure.v1.json
- Oversize source not scanned: execution-plans/2026-07-15-repository-maintenance-tdd-adapter/.acceptance-snapshots/2026-08-04-rmap-acceptance-r3/.agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py
- Oversize source not scanned: execution-plans/2026-07-15-repository-maintenance-tdd-adapter/.acceptance-snapshots/2026-08-04-rmap-acceptance-r3/.agents/skills/run-phase-bootstrap-review/tests/test_bootstrap_review.py
- Oversize source not scanned: execution-plans/2026-07-15-repository-maintenance-tdd-adapter/.acceptance-snapshots/2026-08-04-rmap-acceptance-r3/execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/predicate-artifact-closure.v1.json
- Oversize source not scanned: execution-plans/2026-07-15-repository-maintenance-tdd-adapter/.acceptance-snapshots/2026-08-04-rmap-acceptance-r4/.agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py
- Oversize source not scanned: execution-plans/2026-07-15-repository-maintenance-tdd-adapter/.acceptance-snapshots/2026-08-04-rmap-acceptance-r4/.agents/skills/run-phase-bootstrap-review/tests/test_bootstrap_review.py
- Oversize source not scanned: execution-plans/2026-07-15-repository-maintenance-tdd-adapter/.acceptance-snapshots/2026-08-04-rmap-acceptance-r4/execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/predicate-artifact-closure.v1.json
- Oversize source not scanned: execution-plans/2026-07-15-repository-maintenance-tdd-adapter/.acceptance-snapshots/2026-08-04-rmap-acceptance-r5/.agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py
- Oversize source not scanned: execution-plans/2026-07-15-repository-maintenance-tdd-adapter/.acceptance-snapshots/2026-08-04-rmap-acceptance-r5/.agents/skills/run-phase-bootstrap-review/tests/test_bootstrap_review.py
- Oversize source not scanned: execution-plans/2026-07-15-repository-maintenance-tdd-adapter/.acceptance-snapshots/2026-08-04-rmap-acceptance-r5/execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/predicate-artifact-closure.v1.json
- Oversize source not scanned: execution-plans/2026-07-15-repository-maintenance-tdd-adapter/.acceptance-snapshots/2026-08-04-rmap-acceptance-r6/.agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py
- Oversize source not scanned: execution-plans/2026-07-15-repository-maintenance-tdd-adapter/.acceptance-snapshots/2026-08-04-rmap-acceptance-r6/.agents/skills/run-phase-bootstrap-review/tests/test_bootstrap_review.py
- Oversize source not scanned: execution-plans/2026-07-15-repository-maintenance-tdd-adapter/.acceptance-snapshots/2026-08-04-rmap-acceptance-r6/execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/predicate-artifact-closure.v1.json
- Oversize source not scanned: execution-plans/2026-07-15-repository-maintenance-tdd-adapter/.acceptance-snapshots/2026-08-04-rmap-acceptance-r7/.agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py
- Oversize source not scanned: execution-plans/2026-07-15-repository-maintenance-tdd-adapter/.acceptance-snapshots/2026-08-04-rmap-acceptance-r7/.agents/skills/run-phase-bootstrap-review/tests/test_bootstrap_review.py
- Oversize source not scanned: execution-plans/2026-07-15-repository-maintenance-tdd-adapter/.acceptance-snapshots/2026-08-04-rmap-acceptance-r7/execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/predicate-artifact-closure.v1.json
- Oversize source not scanned: execution-plans/2026-07-15-repository-maintenance-tdd-adapter/.acceptance-snapshots/2026-08-04-rmap-acceptance-r8/.agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py
- Oversize source not scanned: execution-plans/2026-07-15-repository-maintenance-tdd-adapter/.acceptance-snapshots/2026-08-04-rmap-acceptance-r8/.agents/skills/run-phase-bootstrap-review/tests/test_bootstrap_review.py
- Oversize source not scanned: execution-plans/2026-07-15-repository-maintenance-tdd-adapter/.acceptance-snapshots/2026-08-04-rmap-acceptance-r8/execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/predicate-artifact-closure.v1.json
- Oversize source not scanned: execution-plans/2026-07-15-repository-maintenance-tdd-adapter/.acceptance-snapshots/2026-08-04-rmap-acceptance-r9/.agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py
- Oversize source not scanned: execution-plans/2026-07-15-repository-maintenance-tdd-adapter/.acceptance-snapshots/2026-08-04-rmap-acceptance-r9/.agents/skills/run-phase-bootstrap-review/tests/test_bootstrap_review.py
- Oversize source not scanned: execution-plans/2026-07-15-repository-maintenance-tdd-adapter/.acceptance-snapshots/2026-08-04-rmap-acceptance-r9/execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/predicate-artifact-closure.v1.json
- Oversize source not scanned: execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/predicate-artifact-closure.v1.json
- Oversize source not scanned: execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/.acceptance-snapshots/2026-07-31-b823ab2-repair01/PhaseA.Platform.Tests/Runs/PrototypeQuickFixServiceTests.cs
- Oversize source not scanned: execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/.acceptance-snapshots/2026-07-31-b823ab2-repair01/PhaseA.Platform/Data/PhaseAMetadataStore.cs
- Oversize source not scanned: execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/.acceptance-snapshots/2026-07-31-b823ab2-repair01/PhaseA.Platform/Runs/PrototypeIterationPlanService.cs
- Oversize source not scanned: execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/.acceptance-snapshots/2026-07-31-b823ab2-repair02/PhaseA.Platform.Tests/Runs/PrototypeQuickFixServiceTests.cs
- Oversize source not scanned: execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/.acceptance-snapshots/2026-07-31-b823ab2-repair02/PhaseA.Platform/Data/PhaseAMetadataStore.cs
- Oversize source not scanned: execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/.acceptance-snapshots/2026-07-31-b823ab2-repair02/PhaseA.Platform/Runs/PrototypeIterationPlanService.cs
- Oversize source not scanned: execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/.acceptance-snapshots/2026-07-31-b823ab2-repair03/PhaseA.Platform.Tests/Runs/PrototypeQuickFixServiceTests.cs
- Oversize source not scanned: execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/.acceptance-snapshots/2026-07-31-b823ab2-repair03/PhaseA.Platform/Data/PhaseAMetadataStore.cs
- Oversize source not scanned: execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/.acceptance-snapshots/2026-07-31-b823ab2-repair03/PhaseA.Platform/Runs/PrototypeIterationPlanService.cs
- Oversize source not scanned: execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/.acceptance-snapshots/2026-07-31-b823ab2-repair04/PhaseA.Platform.Tests/Runs/PrototypeQuickFixServiceTests.cs
- Oversize source not scanned: execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/.acceptance-snapshots/2026-07-31-b823ab2-repair04/PhaseA.Platform/Data/PhaseAMetadataStore.cs
- Oversize source not scanned: execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/.acceptance-snapshots/2026-07-31-b823ab2-repair04/PhaseA.Platform/Runs/PrototypeIterationPlanService.cs
- Oversize source not scanned: execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/.acceptance-snapshots/2026-08-02-afaed9a-r1p1/.agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py
- Oversize source not scanned: execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/.acceptance-snapshots/2026-08-02-afaed9a-r1p1/.agents/skills/run-phase-bootstrap-review/tests/test_bootstrap_review.py
- Oversize source not scanned: execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/.acceptance-snapshots/2026-08-02-afaed9a-r1p1/PhaseA.Platform.Tests/Runs/PrototypeQuickFixServiceTests.cs
- Oversize source not scanned: execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/.acceptance-snapshots/2026-08-02-afaed9a-r1p1/PhaseA.Platform/Data/PhaseAMetadataStore.cs
- Oversize source not scanned: execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/.acceptance-snapshots/2026-08-02-afaed9a-r1p1/PhaseA.Platform/Runs/PrototypeIterationPlanService.cs
- Oversize source not scanned: execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/.acceptance-snapshots/2026-08-02-afaed9a-r1p2/.agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py
- Oversize source not scanned: execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/.acceptance-snapshots/2026-08-02-afaed9a-r1p2/.agents/skills/run-phase-bootstrap-review/tests/test_bootstrap_review.py
- Oversize source not scanned: execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/.acceptance-snapshots/2026-08-02-afaed9a-r1p2/PhaseA.Platform.Tests/Runs/PrototypeQuickFixServiceTests.cs
- Oversize source not scanned: execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/.acceptance-snapshots/2026-08-02-afaed9a-r1p2/PhaseA.Platform/Data/PhaseAMetadataStore.cs
- Oversize source not scanned: execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/.acceptance-snapshots/2026-08-02-afaed9a-r1p2/PhaseA.Platform/Runs/PrototypeIterationPlanService.cs
- Oversize source not scanned: execution-plans/2026-07-27-refactor-implementation-acceptance-skill/.acceptance-snapshots/2026-07-29-r3/.agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py
- Oversize source not scanned: execution-plans/2026-07-27-refactor-implementation-acceptance-skill/.acceptance-snapshots/2026-07-30-r4/.agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py
- Oversize source not scanned: execution-plans/2026-07-27-refactor-implementation-acceptance-skill/.acceptance-snapshots/2026-07-30-successor-r4/.agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py
- Oversize source not scanned: execution-plans/2026-07-27-refactor-implementation-acceptance-skill/.acceptance-snapshots/2026-07-31-complete/.agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py
- Hash-checked baseline Git bytes versus declared candidate commit/snapshot bytes.
