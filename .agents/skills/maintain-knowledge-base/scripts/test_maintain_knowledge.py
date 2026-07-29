#!/usr/bin/env python3
"""Focused executable tests for maintain_knowledge.py."""
from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).with_name("maintain_knowledge.py")


def run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, encoding="utf-8", capture_output=True, check=False)


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=True, indent=2) + "\n", encoding="utf-8", newline="\n")


def request(commit: str, mode: str = "existing-only", target: dict | None = None) -> dict:
    return {
        "schema_version": "jimuyun.knowledge-maintenance-request.v1",
        "request_id": f"test-{mode}",
        "skill_id": "maintain-knowledge-base",
        "mode": mode,
        "authority": {"authority_ref": "refs/heads/main", "main_commit": commit, "implicit_fetch": False, "dirty_worktree_authority": False},
        "knowledge_snapshot_id": "before",
        "target": target or {"kind": "none", "repo_relative_path": None, "snapshot_kind": "none", "content_sha256": None},
        "discovery_policy": "existing-entries-only" if mode == "existing-only" else "target-scoped",
        "source_write_policy": "forbidden",
        "knowledge_write_classes": ["projection", "index", "maintenance-log"],
        "append_only_log": True,
        "log_root": "logs/knowledge-context",
    }


def execute(repo: Path, request_path: Path, catalog_path: Path, output_path: Path) -> subprocess.CompletedProcess[str]:
    return run("py", "-3", str(SCRIPT), "--request", str(request_path), "--catalog", str(catalog_path), "--output", str(output_path), "--repo-root", str(repo), cwd=repo)


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        repo = Path(raw)
        assert run("git", "init", "-b", "main", cwd=repo).returncode == 0
        assert run("git", "config", "user.email", "test@example.invalid", cwd=repo).returncode == 0
        assert run("git", "config", "user.name", "Test", cwd=repo).returncode == 0
        docs = repo / "docs"
        docs.mkdir()
        fact = docs / "fact.md"
        fact.write_text("main fact\n", encoding="utf-8", newline="\n")
        (docs / "unregistered.md").write_text("must not be discovered\n", encoding="utf-8", newline="\n")
        assert run("git", "add", ".", cwd=repo).returncode == 0
        assert run("git", "commit", "-m", "fixture", cwd=repo).returncode == 0
        commit = run("git", "rev-parse", "refs/heads/main", cwd=repo).stdout.strip()
        catalog = {"entries": [{"entry_id": "fact", "source_path": "docs/fact.md", "source_sha256": "0" * 64}]}
        catalog_path, request_path, output_path = repo / "catalog.json", repo / "request.json", repo / "derived.json"
        write_json(catalog_path, catalog)
        write_json(request_path, request(commit))
        completed = execute(repo, request_path, catalog_path, output_path)
        assert completed.returncode == 0, completed.stderr + completed.stdout
        result = json.loads(output_path.read_text(encoding="utf-8"))
        assert result["status"] == "updated"
        assert result["entries"][0]["after_sha256"] == sha256(b"main fact\n")
        assert [entry["source_path"] for entry in result["entries"]] == ["docs/fact.md"]
        assert result["source_mutation_count"] == 0
        assert fact.read_text(encoding="utf-8") == "main fact\n"
        assert (repo / result["log"]["log_ref"]).exists()

        catalog["entries"][0]["source_sha256"] = sha256(b"main fact\n")
        write_json(catalog_path, catalog)
        incremental = execute(repo, request_path, catalog_path, output_path)
        assert incremental.returncode == 0, incremental.stderr + incremental.stdout
        unchanged = json.loads(output_path.read_text(encoding="utf-8"))
        assert unchanged["status"] == "unchanged"
        assert unchanged["lkg_disposition"] == "preserved"
        assert [entry["source_path"] for entry in unchanged["entries"]] == ["docs/fact.md"]
        retained_logs = list((repo / "logs" / "knowledge-context").rglob("*.v1.json"))
        assert len(retained_logs) >= 2

        write_json(catalog_path, {"schema_version": "legacy-source-snapshot", "files": [{"path": "docs/fact.md", "sha256": sha256(b"main fact\n")} ]})
        legacy = execute(repo, request_path, catalog_path, output_path)
        assert legacy.returncode == 0, legacy.stderr + legacy.stdout
        assert json.loads(output_path.read_text(encoding="utf-8"))["status"] == "unchanged"

        modern_catalog = {
            "source_snapshot": {
                "ref": "refs/heads/main",
                "commit": "0" * 40,
                "sources": [{"path": "docs/fact.md", "sha256": "0" * 64}],
            },
            "entries": [{"entry_id": "fact", "source_path": "docs/fact.md", "source_sha256": sha256(b"main fact\n")}],
        }
        write_json(catalog_path, modern_catalog)
        modern = execute(repo, request_path, catalog_path, output_path)
        assert modern.returncode == 0, modern.stderr + modern.stdout
        modern_result = json.loads(output_path.read_text(encoding="utf-8"))
        assert modern_result["status"] == "updated"
        assert modern_result["catalog_source_snapshot_status"] == "stale"
        assert modern_result["suggested_catalog_source_snapshot"]["commit"] == commit
        assert modern_result["suggested_catalog_source_snapshot"]["sources"] == [{"path": "docs/fact.md", "sha256": sha256(b"main fact\n")}]

        support_digest = sha256(b"must not be discovered\n")
        v2_catalog = {
            "source_snapshot": {
                "ref": "refs/heads/main",
                "commit": commit,
                "sources": [
                    {"path": "docs/fact.md", "sha256": sha256(b"main fact\n"), "source_role": "primary"},
                    {"path": "docs/unregistered.md", "sha256": support_digest, "source_role": "supporting-source"},
                ],
            },
            "modules": [{
                "entry_id": "fact", "source_path": "docs/fact.md", "source_sha256": sha256(b"main fact\n"),
                "resources": [{"role": "supporting-source", "path": "docs/unregistered.md", "source_sha256": support_digest}],
            }],
        }
        write_json(catalog_path, v2_catalog)
        v2 = execute(repo, request_path, catalog_path, output_path)
        assert v2.returncode == 0, v2.stderr + v2.stdout
        v2_result = json.loads(output_path.read_text(encoding="utf-8"))
        assert v2_result["catalog_source_snapshot_status"] == "current"
        assert {item["source_path"] for item in v2_result["entries"]} == {"docs/fact.md", "docs/unregistered.md"}

        write_json(request_path, request("0" * 40))
        rejected = execute(repo, request_path, catalog_path, output_path)
        assert rejected.returncode == 2
        assert json.loads(output_path.read_text(encoding="utf-8"))["log"]["failure_code"] == "main_commit_mismatch"

        provisional = docs / "worktree-only.md"
        provisional.write_text("not committed\n", encoding="utf-8", newline="\n")
        write_json(request_path, request(commit, "targeted", {"kind": "document-directory", "repo_relative_path": "docs/worktree-only.md", "snapshot_kind": "worktree", "content_sha256": sha256(provisional.read_bytes())}))
        targeted = execute(repo, request_path, catalog_path, output_path)
        assert targeted.returncode == 0, targeted.stderr + targeted.stdout
        candidate = json.loads(output_path.read_text(encoding="utf-8"))["entries"]
        assert candidate[0]["authority_status"] == "provisional"
        assert candidate[0]["disposition"] == "candidate"

        write_json(request_path, request(commit, "targeted", {"kind": "document-directory", "repo_relative_path": "docs/migration", "snapshot_kind": "main", "content_sha256": None}))
        excluded = execute(repo, request_path, catalog_path, output_path)
        assert excluded.returncode == 2
        assert json.loads(output_path.read_text(encoding="utf-8"))["log"]["failure_code"] == "source_path_excluded"
    print("MAINTAIN_KNOWLEDGE_TEST PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
