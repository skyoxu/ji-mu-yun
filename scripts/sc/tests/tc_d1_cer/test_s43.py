import hashlib
import json
# Accepted ADR-0041: lifecycle acceptance belongs to its current owner.
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
PREFLIGHT = ROOT / ".agents/skills/authorization/scripts/conformance_preflight.py"
SCHEMA = ROOT / "scripts/sc/schemas/toolchain-evaluation-seed-manifest.v1.schema.json"
KINDS = ("Replay", "seed", "matrix", "review", "Quick Dev")

def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()

def _fixture(tmp: Path):
    manifest = tmp / "manifest.json"
    mapping = tmp / "mapping.json"
    validator = tmp / "validator.py"
    manifest.write_text('{"canonical_hash":"fixture"}\n', encoding="utf-8")
    entries = []
    for index, kind in enumerate(KINDS):
        path = tmp / f"artifact-{index}.json"
        path.write_text(json.dumps({"artifact_type": kind, "authorizes": []}), encoding="utf-8")
        entries.append({"artifact_type": kind, "path": str(path)})
    mapping.write_text(json.dumps({"required_artifact_types": list(KINDS), "artifacts": entries}), encoding="utf-8")
    validator.write_text("# bounded fixture\n", encoding="utf-8")
    return manifest, mapping, validator

def _run(tmp: Path, authorizes: list[str], manifest: Path, mapping: Path, validator: Path):
    receipt = tmp / "receipt.json"
    source_hash = _digest(manifest) if manifest.exists() else "sha256:missing"
    receipt.write_text(json.dumps({"schema_version":"vdd-conformance-result.v1","status":"conformant","errors":[],"authorizes":authorizes,"source_manifest_hash":source_hash,"source_manifest_canonical_hash":"fixture","requirements_manifest_hash":_digest(mapping),"validator_identity":_digest(validator)}), encoding="utf-8")
    return subprocess.run([sys.executable, str(PREFLIGHT), "--receipt", str(receipt), "--manifest", str(manifest), "--mapping", str(mapping), "--validator", str(validator)], cwd=tmp, capture_output=True, text=True, encoding="utf-8", check=False, timeout=30)

def _check(ok: bool, failure_id: str, detail: object) -> None:
    if not ok:
        print(f"FAILURE_ID:{failure_id}")
    assert ok, detail

@pytest.mark.cer_assertion("A-E27D4A209E25-1")
def test_only_acceptance_owner_publication_authorizes_empty_set() -> None:
    sys.path.insert(0, str(ROOT / ".agents/skills/run-refactor-implementation-acceptance/scripts"))
    from semantic_import import finalize_acceptance

    identities = {key: "sha256:" + chr(97 + index) * 64 for index, key in enumerate((
        "baselineIdentityHash", "candidateIdentityHash", "consumerClosureHash",
        "requiredChecksHash", "policyHash", "specSelectionHash",
    ))}
    result = finalize_acceptance({
        "acceptanceMode": "unattended", "route": "deterministic_only", "triggerIds": [],
        "identities": identities, "supervisedDecision": None, "bootstrapImport": None,
    })
    assert result["lifecycleTransition"] == "acceptance-passed"
    assert result["authorizes"] == ["acceptance-passed"]

@pytest.mark.cer_assertion("A-FE5BCD96B20D-1")
def test_non_empty_authorization_set_is_rejected() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw); manifest, mapping, validator = _fixture(tmp)
        result = _run(tmp, [], manifest, mapping, validator); report = json.loads(result.stdout)
        assert result.returncode == 0, result.stderr
        rows = report.get("artifacts", [])
        expected = json.loads(mapping.read_text(encoding="utf-8"))["artifacts"]
        _check(len(rows) == len(KINDS) and {row.get("artifact_type") for row in rows} == set(KINDS) and {row.get("path") for row in rows} == {row["path"] for row in expected} and all(set(row) == {"artifact_type", "path", "authorizes"} and row.get("authorizes") == [] for row in rows) and report.get("non_empty_count") == 0, "FI-FE5BCD96B20D-1", report)

@pytest.mark.cer_assertion("A-FE5BCD96B20D-2")
@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("fixture_case", ["missing", "malformed", "omitted", "unreadable", "missing-metadata"])
def test_missing_or_malformed_artifact_fails_closed(fixture_case: str, kind: str) -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw); manifest, mapping, validator = _fixture(tmp)
        document = json.loads(mapping.read_text(encoding="utf-8"))
        entry = next(item for item in document["artifacts"] if item["artifact_type"] == kind)
        path = Path(entry["path"])
        if fixture_case == "missing": path.unlink()
        elif fixture_case == "malformed": path.write_text("{malformed", encoding="utf-8")
        elif fixture_case == "unreadable":
            path.unlink()
            path.mkdir()
        elif fixture_case == "omitted":
            document["artifacts"].remove(entry)
            mapping.write_text(json.dumps(document), encoding="utf-8")
        else: path.write_text(json.dumps({"artifact_type": kind}), encoding="utf-8")
        result = _run(tmp, [], manifest, mapping, validator); report = json.loads(result.stdout)
        diagnostic = json.dumps(report)
        marker = kind if fixture_case == "omitted" else Path(entry["path"]).name
        _check(result.returncode == 2 and report.get("status") == "blocked" and report.get("authorizes") == [] and marker in diagnostic, "FI-FE5BCD96B20D-2", report)

@pytest.mark.cer_assertion("A-FE5BCD96B20D-1")
@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("invalid_value", [["unexpected"], ["acceptance-passed"], None, "unexpected", {}, 0, False])
def test_named_non_empty_authorization_set_is_rejected(kind: str, invalid_value: object) -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        manifest, mapping, validator = _fixture(tmp)
        entries = json.loads(mapping.read_text(encoding="utf-8"))["artifacts"]
        entry = next(item for item in entries if item["artifact_type"] == kind)
        Path(entry["path"]).write_text(json.dumps({"artifact_type": kind, "authorizes": invalid_value}), encoding="utf-8")
        result = _run(tmp, [], manifest, mapping, validator)
        report = json.loads(result.stdout)
        _check(result.returncode == 2 and report.get("status") == "blocked" and report.get("authorizes") == [] and Path(entry["path"]).name in json.dumps(report), "FI-FE5BCD96B20D-1", report)

def test_negative_fixture_checks_real_preflight() -> None:
    result = subprocess.run([sys.executable, str(ROOT / ".agents/skills/authorization/tests/validators/preflight_negative.py")], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False, timeout=30)
    assert result.returncode == 1, (result.stdout, result.stderr)
    report = json.loads(result.stdout)
    assert report["status"] == "blocked"
    assert report["authorizes"] == []
