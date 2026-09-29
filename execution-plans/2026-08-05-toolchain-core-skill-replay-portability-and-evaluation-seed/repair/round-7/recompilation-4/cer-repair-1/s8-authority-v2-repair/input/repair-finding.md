# S8 authority refresh finding

The S8 regression selector executes the TC-D1 plan validator. Its authority
manifest binds four current authority sources to obsolete bytes, and its
knowledge preflight passes a legacy Skill-input v1 receipt to a live v2 gate.
Refresh the authority source hashes and bind a new v2 repair input. Preserve
the requirement contract, C3 OPEN, historical evidence, and `authorizes=[]`.
