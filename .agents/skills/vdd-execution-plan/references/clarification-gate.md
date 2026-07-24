# Material Clarification Gate

Read authority and current state before asking questions. Ask only about a decision that materially changes scope, compatibility, destructive behavior, protected-path approval, or acceptance. Do not ask filler questions, enforce a question count, or gate writing on a numeric confidence score.

When the request and repository resolve those boundaries, ask zero questions and proceed. Explicit write authorization in the initial user request permits writing when no material blocker is discovered. If a material blocker remains, ask a focused question and keep the plan `draft` until it is resolved or explicitly recorded as a bounded draft assumption.

Persist only a minimized summary of unresolved decisions when it must survive a session boundary. A normal `standard` plan has no clarification file, registry, lock, reviewer identity record, or distributed coordination. Current persisted decisions use `fact_gap`, `user_decision`, or `authority_conflict` plus acyclic `depends_on` references; they impose no question count or confidence score.

Hash drift reports `stale` without changing bytes. Only an explicit invalidate followed by reopen may replace hashes and clear stale decisions. Legacy v1/v2 bytes have a digest-bound inspection path and no mutation or migration path. Sensitive current input produces a sanitized terminal quarantine; sensitive legacy input fails with digest-only diagnostics and remains byte-preserving.

Before writing, recheck authority relevant to the selected scope. Unrelated working-tree changes do not reopen clarification.
