# CH456 V3 worker hang evidence

Candidate: `dc3a92347e46acfd1431a84823b067e1635e6b02`.

The complete CH456 regression passed (`196 passed`). The single real-semantic
run used a 3600-second compile watchdog and a 900-second repair timeout. V0,
V0A, all five V1 workers, and V4 atomic recall completed. V3 initial worker
`codex exec` was started with a 180-second timeout but never emitted a
`worker-returned` checkpoint; the process tree remained alive for about 28
minutes and was terminated manually. No live blind or final acceptance was
started. The copied run retains the exact progress file, caches, worker output,
receipts and schemas.
