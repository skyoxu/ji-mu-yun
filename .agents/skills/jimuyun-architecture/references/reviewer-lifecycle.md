# Reviewer lifecycle

These caller constraints apply before native activation and to every reviewer
spawned by the native gate. They adapt tool use, not the architecture method.

1. Freeze the spine revision before dispatch. Dispatch the entire native rubric
   and configured reviewer set once, through collaboration/agent lifecycle APIs.
   Give each reviewer the frozen spine, its lens and an isolated review output
   path. Return only verdict, top findings and path to the parent.
2. Monitor only with wait_agent, list_agents or the actual provider's equivalent
   agent-status API. A process/exec wait requires the identifier returned by its
   matching execution call and never waits for a reviewer agent. FastCtx, Git,
   filesystem polling, shell commands, empty calls and text placeholders are not
   dispatch, waiting or progress probes.
3. On the first unknown-agent, cell-not-found or route mismatch, stop that route.
   Inspect lifecycle state once through the correct agent API. Never invent,
   guess, substitute or recycle a process/cell/agent identifier. Resume only a
   known live agent through its matching lifecycle API; otherwise report that
   reviewer unavailable and block finalization until it is resolved.
4. On an agent wait timeout, inspect agent state once, then wait through that
   lifecycle API again or report the unavailable reviewer. No command-poll loop.
5. While any reviewer is running, do not edit the frozen spine or run lint,
   repository validation, complete rereads or Git status probes. Native initial
   lint occurs before dispatch. After the entire reviewer set is terminal,
   consolidate findings, apply fixes once, rerun lint and rerun the complete set
   on the new revision if fixes are material. Never cherry-pick reviewer lenses.
6. When subagents genuinely are unavailable, report the limitation and follow
   the native documented sequential fallback: write each complete review before
   dropping it from context. Do not present this as independent-agent evidence.

The caller's real agent tools enforce dispatch and report observed status.
This reference is not a scheduler, simulated tool result, Acceptance authority
or a replacement for the native reviewer gate.
