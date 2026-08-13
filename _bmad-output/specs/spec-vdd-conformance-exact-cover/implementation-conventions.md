# Implementation Conventions

## Capability Surface

- Capability 名称为 `vdd-conformance-exact-cover`。
- Target 参数接受任意 `execution-plans/<target>`，不得包含 BROH 专用分支。
- Exact-cover 读取有效 VDD source-freeze manifest；unknown legacy manifest/schema fail closed，不迁移或改写 legacy plan。
- LLM obligation extraction 必须使用仓库 shared LLM backend 与 UTF-8 stdin。
- 每次 requirement coverage 不得触发一次 LLM pass；正常成本应主要来自 parsing、set operations 与 hashing。

## Planned Skill Layout

```text
vdd-conformance-exact-cover/
├── SKILL.md
├── agents/openai.yaml
├── scripts/validate_conformance.py
├── scripts/build_obligation_inventory.py
└── references/
    ├── schemas/
    │   ├── run-manifest.v1.schema.json
    │   ├── obligation-inventory.v1.schema.json
    │   ├── shard-result.v1.schema.json
    │   ├── conformance-matrix.v1.schema.json
    │   ├── conformance-result.v1.schema.json
    │   ├── conformant-receipt.v1.schema.json
    │   └── vdd-repair-input.v1.schema.json
    ├── workflow.md
    └── fixtures.md
```

`SKILL.md` 只包含 trigger、input/output contract、execution order 与 failure routing。Schemas、fixtures 与重复 checks 放在 `references/`/`scripts/`。脚本必须可独立执行并只返回小型 JSON summary。

VDD producer schema 由 `.agents/skills/vdd-execution-plan/references/schemas/vdd-source-freeze-manifest.v1.schema.json` 独占拥有。Exact-cover 不复制或发布该 schema；它只把 VDD schema 的 repository-relative path、精确 byte SHA-256 与 declared version 绑定到 validator identity，并在缺失、漂移或 unknown version 时 fail closed。

## Ownership Limits

- 不复制 Bootstrap runner、reviewer layers、risk policy、lifecycle 或 VDD repair implementation。
- VDD adapter 只拥有 source freeze、create/repair、`draft` 与 `plan-ready`。Mandatory receipt preflight 与 `implementation-authorized` publication 位于独立 maintainer authorization adapter。
- Shared canonical-contract core owns package/manifests/envelopes schemas, canonical JSON/domain hashing, path containment/order, and cross-adapter golden vectors; VDD and exact-cover adapters may not fork these rules.
- 不引入 Chapter 5 Taskmaster triplet、`tasks_back`/`tasks_gameplay`、game taxonomy、script names、PowerShell/local-path assumptions、multi-stage `extract → align → coverage → semantic_gate → refs` reviewer chain、majority-vote correctness、第二套 source discovery、automatic semantic baseline promotion 或 automatic Bootstrap invocation。
- Chapter 5 只是 execution-governance inspiration，不是 runtime dependency。
