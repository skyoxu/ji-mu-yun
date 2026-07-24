# Skill Compliance Protocol

Package tests prove the deterministic package contract, not model behavior in a fresh conversation. Validate all three profiles, lifecycle ownership, optional-review policy, conditional 95 behavior, dependency-scoped freshness, and no-live-plan hardcoding.

Run:

```text
py -3 scripts/validate_skill_contract.py --skill-root <skill-root>
py -3 -m unittest discover -s scripts/tests -p "test_*.py" -v
```

When practical, separately observe a clear standard request, a resumable interrupted request, and a self-hosted competing-pressure request in fresh contexts. Report that observation separately from package tests.
