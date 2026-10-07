# Missing historical input and interrupted verification

Candidate: `de6e6a4b0427bc53a8dd9d03b528be075ce0e3d5`.
Accepted ADR-0058 governs this direct verification; C3 remains OPEN.

jsonschema and historical source objects were available, but the sparse
checkout lacked the 08-01 validator and receipt input. Actual fresh replay
rejected that absence. This attempt was interrupted with session exit 130.
Events and the native diagnostic replay are retained; no complete pytest
result or JUnit is invented. A complete source checkout and immutable
historical receipt blobs were materialized before starting a separate run.
