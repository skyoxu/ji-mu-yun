# Repair Round 4 Findings

Source: `docs/know22.txt`. This is a narrow execution-proof repair. Authority,
requirements, and slice design remain unchanged.

| ID | Disposition | Repair |
| --- | --- | --- |
| P0-1 | fixed | Implementation commands execute a declared validator and revalidate its hash-bound receipt and artifact hashes. |
| P0-2 | fixed | Terminal derives the complete RED/GREEN command universe from `implementation-contract.v1.json`. |
| P0-3 | fixed | Repair knowledge composition is separated from S5 exact-cover dogfood. |
| P1-1 | fixed | Repair composition invokes the real `vdd_knowledge_preflight.py` CLI with the current skill-input receipt. |
| P1-2 | fixed | Repair composition receipt is append-only under its run and closure binds the fixed receipt hash. |
