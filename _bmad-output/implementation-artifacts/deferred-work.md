- source_spec: `_bmad-output/implementation-artifacts/spec-7-25-round1-p1-closure.md`
  summary: Focused Acceptance import appears to route authentic focused runs through the generic three-layer finalized-run validator.
  evidence: Independent review identified unconditional generic replay in `.agents/skills/run-refactor-implementation-acceptance/scripts/bootstrap_integration.py`; this control-plane path predates and is outside the Hosted Context and knowledge-output repair scope.
- source_spec: `_bmad-output/implementation-artifacts/spec-7-25-round1-p1-closure.md`
  summary: P2 v2 validation receipts may accept caller-authored passed payloads without a trusted producer or command receipt binding.
  evidence: Independent review identified permissive receipt acceptance in `.agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py`; this P2 closure protocol is outside the current two-P1 repair scope.
- source_spec: `_bmad-output/implementation-artifacts/spec-7-25-round1-p1-closure.md`
  summary: Compact VDD routing may rely on shallow completion metadata without replaying the plan validators.
  evidence: Independent edge-case review identified the classification path in `.agents/skills/bmad-quick-dev/scripts/quick_dev_input_router.py`; this input-routing behavior is unrelated to the Hosted Context and knowledge-output findings.
- source_spec: `_bmad-output/implementation-artifacts/spec-fix-model-visible-tool-round-contract-hardening.md`
  summary: Trusted preflight, background, and provider adapters need a non-workspace control-plane attestation mechanism before any registry can be enabled.
  evidence: Review confirmed that an adapter ID in a workspace-authored sidecar is not independently unforgeable; the current registries intentionally remain empty and adding a signing or control-plane trust root requires a separate accepted decision.
- source_spec: `_bmad-output/implementation-artifacts/spec-fix-model-visible-tool-round-contract-hardening.md`
  summary: Observed round, token, and per-operation visible-byte claims need capture-time telemetry provenance rather than caller-authored local JSON.
  evidence: The current measurement sidecar cross-checks internal consistency but cannot prove that ledger byte counts or round events came from the external provider; closing this requires a trusted telemetry adapter and result-capture contract.
- source_spec: `_bmad-output/implementation-artifacts/spec-fix-model-visible-tool-round-contract-hardening.md`
  summary: The model-visible tool-round contract is not yet wired into the real FastCtx, Codex, MCP, browser, image, or functions.exec runtime paths.
  evidence: Repository search found only the proposed contract, schemas, producer, validator, examples, and tests; the document correctly remains Proposed and external enforcement needs a separately authorized integration change.
