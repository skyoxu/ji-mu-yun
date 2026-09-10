# Historical And Skill-input Routes

Read this guide only for the operation selected in SKILL.md. Commands run from the repository root unless stated otherwise; inline paths retain their original repository/Skill-root meaning.

## Skill-input Adopting Routes

For routes that explicitly adopt Skill-input, including `adapter.py`
`prepare_with_skill_input`, bind `plan_directory` and `target_files` for
`execute`. The current staged runtime's separate governance policy is unchanged;
this does not inject governance artifacts into its default runtime snapshot.
Use the v2 request and commands in `docs/workflows/skill-input-v2.md`
(ADR-0060). Bind the real consumer contract, explicit required-input roots,
registry, authority envelope with `skill_input_baseline`, and Knowledge freeze.
The adapter derives candidate changes from Git; never supply an empty changed
set to conceal Knowledge changes. Run `skill_input_v2.py prepare`, consume all
pages, then `finish`. Pass only `<storage>/current.v1.json` as
`--skill-input-receipt`, with the bound `--skill-input-contract`.
The live gate revalidates inputs/candidate and automatically persists a
non-authorizing consumer-use reference before handing off context. V1 CLI
replay requires `--historical-v1`; its output cannot enter a live consumer.
Transport coverage is not semantic approval and does not replace downstream
Knowledge, review, lifecycle, or authorization requirements.

## Legacy Compatibility

Historical v1 plans are read-only compatibility inputs. `tools/legacy_compat.py` may report reusable identities or required current projection, but legacy combined receipt/observation fields, aggregate execution counters and plan-local terminal status cannot directly become current v2 evidence or completion authority. `scripts/quick_dev/replay_legacy_tdd.py` is a regression harness only: it may prove a historical RED baseline and current GREEN with the same declared selector/failure identities, but it never authorizes current evidence.

Legacy compatibility tests may load their explicitly named historical fixtures, Bootstrap helpers, or Acceptance helpers. Those dependencies remain test/replay inputs only; their existence never promotes a legacy loop, governance receipt, historical success, or acceptance route into current runtime authority.
