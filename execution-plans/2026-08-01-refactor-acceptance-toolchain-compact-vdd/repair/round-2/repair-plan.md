# Repair Round 2 - Self-hosted Locator Candidate Bound

## Finding

A self-hosted Acceptance candidate changes several governance sources returned
by broad Locator queries. The Acceptance adapter did not expose the canonical
Locator's supported candidate limit, so rejected candidate read sets could
make every context stale even when the accepted source was unchanged.

Severity: P1. Failure family: `self-hosted-knowledge-read-set-collision`.

## Repair

Expose `--max-candidates` with a closed range of 1 through 12, bind the value in
the Locator request, and pass it to the canonical Locator CLI. This permits an
exact, relevant query to freeze only its highest-ranked source while retaining
request/result hashes and normal source verification.

## Validation

- The adapter test binds `max_candidates=1` in both request and CLI arguments.
- Invalid zero or excessive limits fail before Locator execution.
- The complete Acceptance and compact-VDD terminal suites must pass again.

This repair carries `authorizes=[]` and does not bypass Locator publication,
catalog, snapshot, decision, or source-hash validation.
