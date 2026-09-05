# CH456 regression failure evidence

Candidate: `8572c4c4383900271c6cf90bc403bda907397380`

The complete CH456 regression selector exited `1`: `1 failed, 182 passed`.
The failed lifecycle test raised `ValueError: slice semantic bindings incomplete`
from `stage_pipeline.py:46`.

The configured 900-second live semantic repair setting was not invoked. Per the
single-run, first-failure stop rule, real semantic, formal live blind, and final
acceptance were not run.
