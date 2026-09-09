"""ADR-0053/0058: real Q8 -> projection -> Coordinator; no live backend."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[4]
SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
QD = ROOT / ".agents/skills/quick-dev-tdd-adapter/tools"
for path in (ROOT, SCRIPTS, QD, QD / "tests", ROOT / "scripts/python", ROOT / "scripts/python/tests"):
    sys.path.insert(0, str(path))

sys.path.insert(0, str(SCRIPTS))
import acceptance_cli as cli
import compact_vdd_projection as projection
import current_quick_dev_handoff as handoff
from test_cer_behavior_routing import fixture, execute, implement
from coverage_predicates import publish_implementation_complete, validate_slice_ready
from runtime_evidence import sha256_value
from skill_input_composition_support import publish_ready_receipt
from knowledge_context import freeze_knowledge_context


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def sha(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def ref(path, root):
    return {"path": path.relative_to(root).as_posix(), "sha256": sha(path)}


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root, text=True, encoding="utf-8").strip()


def knowledge(root, target, commit):
    # A small, hash-bound published catalog, consumed by the real validator.
    digest = hashlib.sha256((root / "rules.md").read_bytes()).hexdigest()
    snapshot = {"ref": "refs/heads/main", "commit": commit, "snapshot_id": "fixture-snapshot",
                "sources": [{"path": "rules.md", "sha256": digest}]}
    module = {"module_id": "rules", "source_path": "rules.md", "source_sha256": digest}
    catalog = {"schema_version": "jimuyun.repository-knowledge-catalog.v2", "authority_ref": "refs/heads/main",
               "source_snapshot": snapshot, "modules": [module]}
    policy = {"policy_revision": "test"}
    projections = {"policy_revision": "test", "policy_sha256": cli.canonical_hash(policy),
                   "catalog_sha256": cli.canonical_hash(catalog), "source_snapshot_id": "fixture-snapshot",
                   "projections": [{"consumer": "refactor-acceptance", "eligible_module_ids": ["rules"]}]}
    documents = {
        "snapshot": ("snapshots/repository-source-snapshot.v1.json", snapshot),
        "catalog_v2": ("catalogs/repository-knowledge-catalog.v2.json", catalog),
        "catalog_v1": ("catalogs/repository-knowledge-catalog.v1.json", {}),
        "policy": ("policies/consumer-policies.v2.json", policy),
        "projections": ("projections/consumer-projections.v1.json", projections),
        "exclusions": ("policies/source-exclusions.v1.json", {}),
        "query_suite": ("evaluation/repository-knowledge-query-suite.v1.json", {}),
    }
    artifacts = {name: {"sha256": sha(write(root / "knowledge" / path, value))}
                 for name, (path, value) in documents.items()}
    gen = root / "knowledge/indexes/generations" / ("a" * 64)
    artifacts["query_report"] = {"bundle_path": "report.json", "sha256": sha(write(gen / "report.json", {"status": "pass"}))}
    manifest = {"schema_version": "jimuyun.knowledge-publication-generation.v1", "generation_id": "a" * 64,
                "source_snapshot_id": "fixture-snapshot", "main_commit": commit, "artifacts": artifacts}
    write(gen / "manifest.json", manifest)
    write(root / "knowledge/indexes/current.json", {"schema_version": "jimuyun.knowledge-index-pointer.v2",
          "generation_id": "a" * 64, "generation_sha256": sha(gen / "manifest.json"),
          "source_snapshot_id": "fixture-snapshot", "main_commit": commit})
    request = {"schema_version": "jimuyun.knowledge-locator-request.v1", "request_id": "test",
               "snapshot": {"ref": "refs/heads/main", "commit": commit}, "consumer": "refactor-acceptance", "policy_revision": "test"}
    selected = {"module_id": "rules", "path": "rules.md", "source_sha256": digest}
    result = {"schema_version": "jimuyun.knowledge-locator-result.v1", "request_id": "test", "snapshot": request["snapshot"],
              "status": "matched", "policy_revision": "test", "source_snapshot_id": "fixture-snapshot", "candidates": [selected]}
    context = {"schema_version": "jimuyun.knowledge-consumer-context.v1", "consumer": "refactor-acceptance",
               "locator_request": request, "locator_result": result, "required_modules": ["rules"],
               "decisions": [{"owner": "adapter", "decision": "accepted", "satisfies": ["rules"], "candidate": selected}],
               "request_sha256": cli.canonical_hash(request), "result_sha256": cli.canonical_hash(result)}
    context["preflight"] = {"status": "ready", "failure_code": None, "context_sha256": cli.canonical_hash(context),
                            "knowledge_freshness": "current", "catalog_failure_code": None}
    write(target / "knowledge.json", context)
    return freeze_knowledge_context(target, "knowledge.json")


def build(root, monkeypatch, present=(True, True), command_exit=0, knowledge_newline=None):
    semantic, roots = fixture(root, present)
    (root / ".gitignore").write_text("*\n!candidate.py\n!.gitignore\n", encoding="utf-8")
    (root / "rules.md").write_text("# Rules\nVerify current candidate behavior.\n", encoding="utf-8", newline=knowledge_newline)
    for relative in ("scripts/python/knowledge_context_validation.py", "scripts/python/_knowledge_locator_core.py",
                     ".agents/skills/quick-dev-tdd-adapter/tools/coverage_predicates.py"):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, path)
    git(root, "init", "-q", "-b", "main")
    # Keep worktree hashes and committed fixture bytes identical on Windows.
    git(root, "config", "core.autocrlf", "false")
    git(root, "config", "user.email", "test@example.invalid")
    git(root, "config", "user.name", "Test")
    git(root, "add", "-f", "candidate.py", ".gitignore", "rules.md", "scripts", ".agents")
    git(root, "commit", "-qm", "baseline")
    baseline = git(root, "rev-parse", "HEAD")
    route = execute(root, semantic, "probe")
    stages = []
    if not all(present):
        assert execute(root, semantic, "red", route)["predicate_result"]
        implement(root, (True, True))
        stages += ["green", "refactor"]
    if any(present):
        stages += ["regression"]
    for stage in stages:
        assert execute(root, semantic, stage, route)["predicate_result"]
    execute(root, semantic, "terminal", route, materialize_only=True)
    run = root / "RUN-1"
    ready = validate_slice_ready(workspace=root, semantic_plan=semantic, run_root=run, slice_id="S1", snapshot_roots=roots,
                                 source_commit=baseline, base_commit=baseline, out=run / "ready.json")
    assert execute(root, semantic, "terminal", route)["predicate_result"]
    predecessor = {"slice_id": "S1", "run_root": "RUN-1", "result_ref": "RUN-1/ready.json", "result_sha256": sha256_value(ready)}
    result = publish_implementation_complete(workspace=root, semantic_plan=semantic, predecessors=[predecessor], snapshot_roots=roots,
                                            source_commit=baseline, base_commit=baseline, out=run / "complete.json")
    current = {"semanticPlan": ref(semantic, root), "receipt": ref(run / "complete.json", root),
               "snapshotRoots": roots, "sourceCommit": baseline, "baseCommit": baseline}
    assert handoff.verify_current_handoff(root, current) == result
    target = root / "execution-plans/target"
    target.mkdir(parents=True)
    (target / "requirements.md").write_text("# Acceptance\nBoth values must return their inputs.\n", encoding="utf-8")
    knowledge(root, target, baseline)
    skill = publish_ready_receipt(root, consumer="run-refactor-implementation-acceptance", operation="acceptance",
                                 target="execution-plans/target", role_paths={"implementation_target": ["candidate.py"],
                                 "acceptance_requirements": ["execution-plans/target/requirements.md"]})
    candidate = git(root, "rev-parse", "HEAD")
    # The present-only fixture uses a declared source baseline predating a comment.
    if all(present):
        old = root / "baseline-candidate.txt"
        old.write_text("def value(kind):\n return {1: 1, 2: 2}[kind]\n# previous implementation\n", encoding="utf-8")
        overlays = {"candidate.py": "baseline-candidate.txt"}
    else:
        overlays = {}
    policy = ROOT / ".agents/skills/run-refactor-implementation-acceptance/policies/toolchain-code-review.v1.json"
    shutil.copyfile(policy, target / "policy.json")
    command = {"id": "acceptance-check", "executable": sys.executable, "argv": ["-c", f"import sys; from candidate import value; assert value(1)==1 and value(2)==2; sys.exit({command_exit})"], "cwd": ".", "timeout_seconds": 10, "shell": False}
    request = {"schemaVersion": "compact-vdd-acceptance-projection-request.v1", "targetPlan": "execution-plans/target",
               "runId": "closeout", "changeId": "test", "baselineRevision": baseline, "candidateRevision": candidate,
               "baselineOverlaySources": overlays, "changedPaths": ["candidate.py"], "affectedConsumerRefs": ["tests/test_one.py"],
               "targetPlanPaths": ["requirements.md"], "knowledgeContextPath": "knowledge.json", "codeReviewDomain": "toolchain",
               "codeReviewPolicyPath": "execution-plans/target/policy.json", "implementationReceiptPath": "RUN-1/complete.json",
               "implementationReceiptHash": sha(run / "complete.json"), "currentQuickDev": current,
               "commands": [command], "actions": [{"actionId": "acceptance-check", "commandId": "acceptance-check", "dependsOn": [], "order": 1, "activation": True}], "authorizes": []}
    request_path = write(root / "projection.json", request)
    monkeypatch.setattr(cli, "REPOSITORY_ROOT", root)
    # Code lives in the fixture repository, like the real installed entrypoint.
    monkeypatch.setattr(handoff, "OWNER", root / ".agents/skills/quick-dev-tdd-adapter/tools")
    projected = projection.project(root, request_path)
    bundle = root / projected["bundle"]
    prepared_path = root / "prepared.json"
    cli.prepare_run(str(root / projected["runRequest"]), str(prepared_path), prerequisite_bundle_path=bundle.relative_to(target).as_posix())
    coord = {"schemaVersion": "jimuyun.acceptance-coordinator-request.v3", "targetPlan": "execution-plans/target",
             "preparedRunInput": ref(prepared_path, root), "skillInputReceipt": ref(skill["receipt"], root),
             "skillInputContract": ref(skill["contract"], root), "authorizes": []}
    return write(root / "coordinator.json", coord), root / "coordinator-result.json", current


@pytest.mark.parametrize("present", [(True, True), (True, False), (False, False)])
def test_current_q8_projection_and_real_coordinator_close_and_replay(tmp_path, monkeypatch, present):
    request, output, _ = build(tmp_path, monkeypatch, present)
    monkeypatch.setattr(sys, "argv", ["acceptance", "run-coordinator", "--request", str(request), "--out", str(output)])
    assert cli.main() == 0
    result = json.loads(output.read_text())
    assert result["status"] == "completed", result
    assert result["finalization"]["authorizes"] == ["acceptance-passed"]
    run = tmp_path / result["runDirectory"]
    events = (run / "acceptance-events.jsonl").read_bytes()
    assert cli.run_coordinator(str(request), str(output)) == result
    assert (run / "acceptance-events.jsonl").read_bytes() == events
    receipt = next(run.glob("actions/*/*/result.json"))
    receipt.write_text(receipt.read_text() + " ", encoding="utf-8")
    with pytest.raises((ValueError, cli.ControlError), match="receipt.*stale"):
        cli.run_coordinator(str(request), str(output))


def test_current_handoff_preserves_crlf_catalog_bytes_with_user_autocrlf(tmp_path, monkeypatch):
    # ADR-0058: byte-bound fixture sources must not inherit Git conversion.
    config = tmp_path / "user.gitconfig"
    config.write_text("[core]\n\tautocrlf = true\n", encoding="utf-8", newline="\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    root = tmp_path / "repo"
    root.mkdir()
    request, output, _ = build(root, monkeypatch, knowledge_newline="\r\n")
    assert b"\r\n" in (root / "rules.md").read_bytes()
    committed = subprocess.check_output(["git", "show", "main:rules.md"], cwd=root)
    assert committed == (root / "rules.md").read_bytes()
    assert cli.run_coordinator(str(request), str(output))["status"] == "completed"


def test_failed_acceptance_action_stops_once_and_cannot_borrow_q8_pass(tmp_path, monkeypatch):
    request, output, _ = build(tmp_path, monkeypatch, (True, False), command_exit=3)
    result = cli.run_coordinator(str(request), str(output))
    assert result["status"] == "waiting" and result["finalization"] is None
    run = tmp_path / result["runDirectory"]
    assert len(list(run.glob("actions/*/*/result.json"))) == 1
    assert cli.run_coordinator(str(request), str(output)) == result
    assert len(list(run.glob("actions/*/*/result.json"))) == 1
    successor_output = output.with_name("coordinator-successor-output.json")
    assert cli.run_coordinator(str(request), str(successor_output))["status"] == "waiting"
    assert len(list(run.glob("actions/*/*/result.json"))) == 1


def test_q8_replay_rejects_source_and_deferred_drift(tmp_path, monkeypatch):
    request, output, binding = build(tmp_path, monkeypatch, (True, False))
    source = tmp_path / "candidate.py"
    original = source.read_bytes()
    source.write_bytes(original + b"# drift\n")
    with pytest.raises(ValueError, match="runtime root stale"):
        handoff.verify_current_handoff(tmp_path, binding)
    source.write_bytes(original)
    plan = tmp_path / binding["semanticPlan"]["path"]
    document = json.loads(plan.read_text())
    document["behavior_routing"]["deferred"] = [{"type": "blocking", "reason": "unresolved", "resolution_owner": "external", "resolution_stage": "acceptance", "affected_obligation_ids": ["O-1"], "blocking": False}]
    write(plan, document)
    binding["semanticPlan"] = ref(plan, tmp_path)
    with pytest.raises(ValueError, match="blocks-current-scope"):
        handoff.verify_current_handoff(tmp_path, binding)


@pytest.mark.parametrize("mutation", ["final", "events", "registry", "prepared", "context"])
def test_coordinator_replay_rejects_changed_owned_evidence(tmp_path, monkeypatch, mutation):
    request, output, _ = build(tmp_path, monkeypatch, (True, False))
    result = cli.run_coordinator(str(request), str(output))
    assert result["status"] == "completed"
    run = tmp_path / result["runDirectory"]
    if mutation == "final":
        path = run / result["finalization"]["final"]["path"]
        value = json.loads(path.read_text()); value["status"] = "forged"
        write(path, value)
    elif mutation == "events":
        path = run / "acceptance-events.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        for row in rows:
            if row.get("eventType") == "action-completed":
                row["inputHashes"]["runInputHash"] = "sha256:" + "0" * 64
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    elif mutation == "registry":
        path = tmp_path / "execution-plans/target/acceptance-inputs/closeout/command-registry.v1.json"
        value = json.loads(path.read_text()); value["commands"][0]["argv"] = ["-c", "pass"]
        write(path, value)
    elif mutation == "prepared":
        path = run / "prepare-run.v1.json"
        value = json.loads(path.read_text()); value["input"]["changed_paths"] = []
        write(path, value)
    else:
        path = tmp_path / ".skill-input-composition/output/skill-input-context.v1.json"
        value = json.loads(path.read_text()); value["sections"] = []
        write(path, value)
    with pytest.raises(ValueError):
        cli.run_coordinator(str(request), str(output))


def test_explicit_review_request_returns_handoff_without_actions_or_bootstrap(tmp_path, monkeypatch):
    request, output, _ = build(tmp_path, monkeypatch, (True, False))
    value = json.loads(request.read_text()); value["maintainerIntent"] = "request"
    write(request, value)
    result = cli.run_coordinator(str(request), str(output))
    assert result["status"] == "semantic_handoff_required"
    assert result["bootstrapInvoked"] is False
    run = tmp_path / result["runDirectory"]
    assert not list(run.glob("actions/*/*/result.json"))
    assert cli.run_coordinator(str(request), str(output)) == result


@pytest.mark.parametrize("path", [".agents/skills/run-phase-bootstrap-review/SKILL.md", "runtime/phase-a/start.ps1", "PhaseA.Platform/Program.cs"])
def test_bootstrap_requires_explicit_intent_even_for_risk_paths(path):
    from review_requirement import decide_review_requirement
    policy = json.loads((SCRIPTS.parent / "policies/semantic-review-trigger-policy.v1.json").read_text())
    inputs = {"candidateIdentity": {"changedPaths": [path]}, "deterministicEvidence": {"status": "passed"}, "policy": policy}
    default = decide_review_requirement(inputs)
    assert default["requirement"] == "not_required" and default["profile"] is None
    explicit = decide_review_requirement({**inputs, "maintainerIntent": "request"})
    assert explicit["requirement"] == "required" and explicit["profile"] is not None
    blocked = decide_review_requirement({**inputs, "deterministicEvidence": {"status": "failed"}})
    assert blocked["decisionStatus"] == "blocked" and blocked["requirement"] is None
