# Resume the Consumer receipt binding repair

Baseline: `791e8c89bc1273328350deb9e2b0ffa69a9792e3`.
The existing output remains `repair-vdd`; this input is non-authorizing and
does not change C3, implementation status, Acceptance, or archive state.

`O-480CAC26FC28` retains real approved Candidate-Route invocation and current
result capture, and additionally binds each Consumer's actual interface, input,
command, output, result, and dependencies. The S7 real production owner,
selector, write boundary, and forbidden paths remain unchanged.

Use the canonical compiler with the original requirements, existing failed
output directory, `--v1-reuse-from-plan` predecessor, and this file through
`--v3-contract-repair`. Preserve all caches and failed attempts. Do not use a
worker-cache fixture or resume Quick Dev unless the canonical result is
`plan-ready`.
