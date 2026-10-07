# Local prerequisite failure and interrupted verification

Candidate: `de6e6a4b0427bc53a8dd9d03b528be075ce0e3d5`.
Accepted ADR-0058 governs direct verification; C3 stays OPEN and authorizes=[].

This attempt was interrupted with session exit 130 after discovering missing
jsonschema and unhydrated historical blobs in the partial clone. The native
Git read timeout and failed pytest phase records are retained. This is not a
passed test result. No terminal pytest result or JUnit is invented.

The historical blobs were fetched by immutable object ID and jsonschema 4.26.0
was installed before a new, separate full-scope verification. The original
Windows evidence and all prior Q7/Q8 remain unchanged.
