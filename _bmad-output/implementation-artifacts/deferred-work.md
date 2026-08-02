- source_spec: `_bmad-output/implementation-artifacts/spec-7-25-round1-p1-closure.md`
  summary: Focused Acceptance import appears to route authentic focused runs through the generic three-layer finalized-run validator.
  evidence: Independent review identified unconditional generic replay in `.agents/skills/run-refactor-implementation-acceptance/scripts/bootstrap_integration.py`; this control-plane path predates and is outside the Hosted Context and knowledge-output repair scope.
- source_spec: `_bmad-output/implementation-artifacts/spec-7-25-round1-p1-closure.md`
  summary: P2 v2 validation receipts may accept caller-authored passed payloads without a trusted producer or command receipt binding.
  evidence: Independent review identified permissive receipt acceptance in `.agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py`; this P2 closure protocol is outside the current two-P1 repair scope.
- source_spec: `_bmad-output/implementation-artifacts/spec-7-25-round1-p1-closure.md`
  summary: Compact VDD routing may rely on shallow completion metadata without replaying the plan validators.
  evidence: Independent edge-case review identified the classification path in `.agents/skills/bmad-quick-dev/scripts/quick_dev_input_router.py`; this input-routing behavior is unrelated to the Hosted Context and knowledge-output findings.
