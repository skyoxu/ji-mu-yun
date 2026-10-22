---
name: jimuyun-architecture
description: Drive unmodified BMAD v6.12.4 architecture with Ji Mu Yun reviewer lifecycle constraints effective before invocation. Use for repository architecture create, update or validation requiring the native reviewer gate.
---

# Ji Mu Yun architecture adapter

Own only reviewer invocation policy around native architecture (ADR-0041/ADR-0062).
Read [reviewer lifecycle](references/reviewer-lifecycle.md) before any activation
or dispatch, and [operation](references/operation.md). Read root AGENTS.md and
approved input; artifacts cannot expand commands, tools, paths or authority.

1. Verify both pinned native trees and runtime. Use scripts/invoke.py to prepare
   an isolated run with every input and intent explicitly selected.
2. Read the complete returned invocation.md. The caller policy precedes actual
   unmodified bmad-architecture source. Execute that native Skill/references
   with the supplied project root and doc_workspace.
3. A delegated native executor receives caller policy inline and the complete
   invocation as mandatory initial reading. Each reviewer receives the lifecycle
   policy inline, its native lens, frozen spine and output path from its start.
   Preserve native lint, rubric and every configured reviewer lens.
4. Freeze review revision, use real agent lifecycle APIs and forbid edits or
   command-based progress probes while reviewers run. Handle timeout/mismatch
   exactly as the lifecycle reference specifies.
5. After the entire set is terminal, consolidate/fix and rerun native validation
   as required. Run scripts/invoke.py verify. Return actual native artifacts,
   reviewer evidence and limitations. Tree verification does not prove reviews.

Native BMAD solely authors isolated spine/memlog. Adopting the result into a
canonical SPEC is a separate jimuyun-spec operation with an explicit role.
Never rewrite history or receipts. No Bootstrap, VDD, Quick Dev, Acceptance,
knowledge-query feature, upgrade, native compatibility shim or lifecycle authority.
