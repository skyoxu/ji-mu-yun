---
name: phasea-daily-cleanup
description: Audit and safely clean Phase A local runtime clutter. Use when the user asks to inspect disk usage, clean logs, remove orphan Phase A workspaces, prune local hard-check artifacts, or perform daily/weekly housekeeping for this repository.
---

# Phase A Daily Cleanup

## Quick Start

Always start with a dry run:

```powershell
py -3 .agents/skills/phasea-daily-cleanup/scripts/phasea_daily_cleanup.py --repo-root .
```

Apply only after the user agrees:

```powershell
py -3 .agents/skills/phasea-daily-cleanup/scripts/phasea_daily_cleanup.py --repo-root . --apply --confirm-delete DELETE
```

If the dry-run reports more than 2048 MB reclaimable, the default apply command blocks. Raise the limit only after reviewing the report:

```powershell
py -3 .agents/skills/phasea-daily-cleanup/scripts/phasea_daily_cleanup.py --repo-root . --apply --confirm-delete DELETE --max-delete-mb 8192
```

Do not use `--max-delete-mb 0` during validation. It disables the delete budget and requires an extra confirmation:

```powershell
py -3 .agents/skills/phasea-daily-cleanup/scripts/phasea_daily_cleanup.py --repo-root . --apply --confirm-delete DELETE --max-delete-mb 0 --confirm-unbounded-delete UNBOUNDED
```

The script writes JSON and Markdown reports under `logs/cleanup/`.

When the goal is to understand why disk space was not released, run a read-only workspace audit:

```powershell
py -3 .agents/skills/phasea-daily-cleanup/scripts/phasea_daily_cleanup.py --repo-root . --workspace-audit
```

This mode lists workspace size, project metadata, bootstrap status, live/orphan status, and reparse protection state. It cannot be combined with `--apply`.

For legacy external workspaces under `C:\workspaces`, run a separate read-only audit:

```powershell
py -3 .agents/skills/phasea-daily-cleanup/scripts/phasea_daily_cleanup.py --repo-root . --external-workspace-audit
```

Delete only exact 32-character child ids after reviewing the audit:

```powershell
py -3 .agents/skills/phasea-daily-cleanup/scripts/phasea_daily_cleanup.py --repo-root . --external-workspace-delete <32hex-id>
py -3 .agents/skills/phasea-daily-cleanup/scripts/phasea_daily_cleanup.py --repo-root . --external-workspace-delete <32hex-id> --apply --confirm-delete DELETE --confirm-external-workspaces EXTERNAL-WORKSPACES
```

External workspace cleanup accepts only `C:\workspaces` as its root.

To prepare deletion of large orphan workspaces, first dry-run with the exact `project_dir` ids from the audit:

```powershell
py -3 .agents/skills/phasea-daily-cleanup/scripts/phasea_daily_cleanup.py --repo-root . --workspace-delete <32hex-project-dir>
```

Apply only after reviewing the dry-run report and only for orphan entries:

```powershell
py -3 .agents/skills/phasea-daily-cleanup/scripts/phasea_daily_cleanup.py --repo-root . --workspace-delete <32hex-project-dir> --apply --confirm-delete DELETE --confirm-orphan-workspaces ORPHAN-WORKSPACES
```

`--workspace-delete` refuses live database-backed workspaces and nonstandard paths. It removes reparse/junction entries themselves but does not recurse into their targets.
Dry-run includes a deletion preflight with file count, directory count, reparse entry count, and permission/access errors.
During confirmed `--workspace-delete --apply`, read-only file attributes inside the selected orphan workspace are cleared before deletion. The default daily cleanup path does not modify file attributes.

## Safety Rules

- Do not delete `logs/phase-a-innernet/data/phase-a-platform.sqlite3`.
- Do not delete `logs/phase-a-innernet/data/aicodemirror-codex-homes`.
- Do not delete `logs/phase-a-innernet/runtime`, pid files, or watchdog files.
- Do not delete a workspace directory if it appears in the live SQLite `workspaces.root_path` table.
- Treat `logs/phase-a-innernet/workspaces/<account>/<project>` as safe only when both path segments are 32-character hex ids and the project is orphaned by the metadata database.
- Protect nonstandard workspace paths because they may be shared tool state instead of user project workspaces.
- If the metadata database is missing or unreadable, stop instead of treating workspaces as orphaned.
- Keep recent orphan workspaces for at least 1 day by default so fresh failure evidence can be inspected.
- Clean only dated `logs/ci`, `logs/e2e`, and `logs/unit` children by default; preserve named utility folders such as `logs/ci/project-health`.
- Refuse to delete symlinks, junctions, or other reparse points.
- Refuse to delete a directory tree if any descendant is a symlink, junction, or other reparse point.
- Refuse to run unless `--repo-root` looks like this Phase A repository with `AGENTS.md`, `PhaseA.Platform`, and `logs/phase-a-innernet`.
- Prefer `--dry-run` unless the user explicitly asks to delete.
- Require `--confirm-delete DELETE` together with `--apply`.
- Block apply runs above `--max-delete-mb` unless the operator explicitly raises the limit. Default is 2048 MB.
- Do not delete test result folders unless `--include-test-results` is explicitly passed.
- Do not recursively measure protected directory sizes by default; pass `--measure-protected` only when auditing disk usage.
- Do not delete this tool's own `logs/cleanup/phasea-daily-cleanup-*` reports unless `--include-cleanup-reports` is explicitly passed.
- During apply, deleting cleanup reports additionally requires `--confirm-cleanup-reports CLEANUP-REPORTS`.
- Refuse `--include-cleanup-reports` with retention below 7 days.
- Disabling the delete budget with `--max-delete-mb 0` additionally requires `--confirm-unbounded-delete UNBOUNDED`.
- `--workspace-audit` is read-only and must not be combined with `--apply`.
- `--workspace-delete` requires exact 32-character project_dir ids, refuses live projects, and requires `--confirm-orphan-workspaces ORPHAN-WORKSPACES` with `--apply`.
- Use `--workspace-delete` only from a fresh `--workspace-audit` report.
- `--external-workspace-audit` is read-only and must not be combined with `--apply`.
- `--external-workspace-delete` accepts only exact 32-character child ids under `C:\workspaces` and requires `--confirm-external-workspaces EXTERNAL-WORKSPACES` with `--apply`.

## Cleanup Targets

The default script policy is conservative:

- Orphan project workspaces under `logs/phase-a-innernet/workspaces`.
- Old `logs/phase-a-innernet/tmp` children.
- Old dated `logs/ci`, `logs/e2e`, and `logs/unit` children.
- Test result folders such as `Game.Core.Tests/TestResults`, `PhaseA.Platform.Tests/TestResults`, and `Tests.Godot/reports` only when `--include-test-results` is passed.
- Old cleanup reports under `logs/cleanup/` only when `--include-cleanup-reports` is passed.

Default retention:

- Keep active database-backed project workspaces indefinitely.
- Keep recent dated logs for 3 days.
- Keep temporary directories for 1 day.
- Keep recent orphan workspaces for 1 day.
- Keep test results indefinitely unless `--include-test-results` is passed, then keep recent test results for 1 day.
- Keep cleanup reports indefinitely unless `--include-cleanup-reports` is passed, then keep recent cleanup reports for 14 days.
- Cleanup report retention cannot be set below 7 days.

Default reporting limits:

- Include only the largest 200 old tmp children in a single run; use `--max-tmp-candidates 0` to audit all tmp children.
- Protected directory entries report `size_measured: false` by default to keep dry-run fast; use `--measure-protected` for a slower disk-usage audit.

## Reporting

After running the script, summarize:

- Total reclaimable size.
- Largest orphan workspaces.
- Whether any live project workspaces were protected.
- The report paths.
- Whether the run was dry-run or apply.

For `--workspace-audit`, summarize:

- Total workspace size.
- Plain orphan workspace size.
- Orphan workspace size protected by reparse/junction detection.
- Largest workspaces by size.
- Which entries are live database-backed projects.
- Which entries are orphaned but protected by reparse/junction detection.
- Which entries are orphaned and could be considered for a dedicated deletion workflow.

For `--workspace-delete`, summarize:

- Whether the run was dry-run or apply.
- The exact project_dir ids selected.
- Total selected size.
- Deletion preflight counts and any access errors.
- Read-only entry count; confirmed workspace delete can clear these attributes inside selected orphan workspaces.
- Any refused live/nonstandard/not-found entries.
- Whether any deletion failed due to permissions.

For external workspace audit/delete, summarize:

- Total `C:\workspaces` size and child count.
- Largest child directories.
- Selected exact ids.
- Preflight counts and failures.
- Whether the run was dry-run or apply.

If deletion fails for locked files, report the blocked paths and do not force-kill unrelated processes unless the user specifically asks.
