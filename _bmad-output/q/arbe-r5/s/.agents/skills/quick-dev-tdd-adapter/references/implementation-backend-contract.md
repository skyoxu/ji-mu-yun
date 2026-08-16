# Implementation Backend Contract

The implementation backend receives one immutable Slice Capsule containing only the slice intent, requirement and acceptance IDs, authority references, allowed and forbidden paths, current RED evidence, and the targeted GREEN command.

The backend may propose or perform only declared allowed writes. It must report changed paths, commands attempted, blockers, and a non-authoritative candidate status. It must not select a plan, schedule a provider, create hidden state, commit, mark work done, perform semantic review, authorize acceptance, handoff, or release.

Backend output is an observation. The plan-local validator independently verifies the resulting evidence and state transition.
