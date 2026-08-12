from __future__ import annotations

# Contract and evidence authority: Accepted ADR-0038.

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import validate_model_visible_tool_round_summary as validator_module
from build_model_visible_tool_round_summary import build
from validate_model_visible_tool_round_summary import (
    ToolRoundSummaryValidationError,
    _load_json,
    operation_manifest_hash,
    validate_payload,
)


REPO_ROOT = Path(__file__).resolve().parents[3]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


class ModelVisibleToolRoundSummaryValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "AGENTS.md").write_text("# Repository contract\n", encoding="utf-8", newline="\n")
        self.measurement_adapter_patch = patch.object(
            validator_module, "REGISTERED_MEASUREMENT_ADAPTERS", {"test-measurement-adapter": lambda context: True}
        )
        self.measurement_adapter_patch.start()
        self.addCleanup(self.measurement_adapter_patch.stop)

    def _evidence(self, ref_id: str, relative: str, kind: str = "sidecar") -> dict[str, object]:
        path = self.root / relative
        return {
            "ref_id": ref_id,
            "kind": kind,
            "path": relative.replace("\\", "/"),
            "sha256": _sha256(path),
            "hash_status": "verified",
            "run_id": "round-001",
            "turn_id": "turn-001",
            "scope_kind": "repository",
            "scope_ref": "repo",
            "owner": "toolchain",
        }

    def valid_payload(self) -> dict[str, object]:
        scope = {"scope_kind": "repository", "scope_ref": "repo"}
        operation_ids = ["read-a", "read-b"]
        operations = [
            {
                "operation_id": "read-a",
                "tool_call_id": "call:read-a",
                "parent_tool_call_id": None,
                "round_id": "round-001",
                "scope": scope,
                "tool_family": "fastctx",
                "access_mode": "read-only",
                "execution_mode": "sequential",
                "status": "complete",
                "attempts": 1,
                "group_id": None,
                "visible_result_bytes": 600,
                "persisted_output_bytes": 0,
                "evidence_ref": None,
                "background_lifecycle": None,
            },
            {
                "operation_id": "read-b",
                "tool_call_id": "call:read-b",
                "parent_tool_call_id": "call:read-a",
                "round_id": "round-001",
                "scope": scope,
                "tool_family": "codex-shell",
                "access_mode": "read-only",
                "execution_mode": "sequential",
                "status": "complete",
                "attempts": 1,
                "group_id": None,
                "visible_result_bytes": 600,
                "persisted_output_bytes": 0,
                "evidence_ref": None,
                "background_lifecycle": None,
            },
        ]
        preflight = {
            "schema_version": "model-visible-tool-preflight.v1",
            "run_id": "round-001",
            "turn_id": "turn-001",
            "scope": scope,
            "operation_ids": operation_ids,
            "operation_manifest_sha256": operation_manifest_hash(operations),
            "checks": {
                "same_scope_verified": True,
                "authorization_verified": True,
                "secret_redaction_verified": True,
                "read_only_verified": True,
            },
            "authority": {
                "kind": "repository-agent-contract",
                "source_path": "AGENTS.md",
                "sha256": _sha256(self.root / "AGENTS.md"),
                "adapter_id": "test-preflight-adapter",
            },
            "generated_at": "2026-08-11T00:00:00Z",
        }
        _write_json(self.root / "logs/preflight.json", preflight)
        _write_json(
            self.root / "logs/measurement.json",
            {
                "schema_version": "model-visible-tool-measurement.v1",
                "run_id": "round-001",
                "turn_id": "turn-001",
                "scope": scope,
                "round_measurement": {"mode": "observed", "model_visible_rounds": 1},
                "round_events": [
                    {"round_id": "round-001", "turn_id": "turn-001", "result_blocks": 1, "observed": True}
                ],
                "visible_result_bytes": 1200,
                "token_measurement": {
                    "mode": "estimated",
                    "visible_result_tokens": 300,
                    "method": "utf8-bytes-ceil-div-4",
                },
                "capture_adapter": "test-measurement-adapter",
                "recorded_at": "2026-08-11T00:00:00Z",
            },
        )
        evidence_refs = sorted(
            [
                self._evidence("ev-preflight", "logs/preflight.json"),
                self._evidence("ev-measurement", "logs/measurement.json"),
            ],
            key=lambda item: str(item["ref_id"]),
        )
        return {
            "schema_version": "model-visible-tool-round-summary.v1",
            "status": "complete",
            "run_id": "round-001",
            "turn_id": "turn-001",
            "parent_turn_id": None,
            "scope": scope,
            "timing": {"started_at": "2026-08-11T00:00:00Z", "finished_at": "2026-08-11T00:00:01Z"},
            "measurement": {
                "rounds": "observed",
                "tokens": "estimated",
                "rounds_evidence_ref": "ev-measurement",
                "tokens_evidence_ref": "ev-measurement",
            },
            "metrics": {
                "model_visible_rounds": 1,
                "underlying_tool_calls": 2,
                "parallel_groups": 0,
                "sequential_calls": 2,
                "background_calls": 0,
                "retries": 0,
                "visible_result_bytes": 1200,
                "visible_result_tokens": 300,
                "persisted_output_bytes": 0,
                "partial_results": 0,
                "failed_calls": 0,
                "interrupted_calls": 0,
                "blocked_calls": 0,
            },
            "preflight": {
                "same_scope_verified": False,
                "authorization_verified": False,
                "secret_redaction_verified": False,
                "parallelization_allowed": False,
                "block_reason": None,
                "evidence_ref": None,
            },
            "round_events": [
                {"round_id": "round-001", "turn_id": "turn-001", "result_blocks": 1, "observed": True}
            ],
            "operations": operations,
            "continuation": {"has_more": False, "offsets": []},
            "evidence_refs": evidence_refs,
            "external_boundaries": [],
            "errors": [],
        }

    def _ledger(self, payload: dict[str, object]) -> dict[str, object]:
        return {key: copy.deepcopy(value) for key, value in payload.items() if key not in {"schema_version", "status", "metrics"}}

    @staticmethod
    def _ref(payload: dict[str, object], ref_id: str) -> dict[str, object]:
        return next(item for item in payload["evidence_refs"] if item["ref_id"] == ref_id)

    def _parallel_payload(self) -> dict[str, object]:
        payload = self.valid_payload()
        for operation in payload["operations"]:
            operation["execution_mode"] = "parallel"
            operation["group_id"] = "group-1"
        payload["metrics"]["parallel_groups"] = 1
        payload["metrics"]["sequential_calls"] = 0
        payload["preflight"] = {
            "same_scope_verified": True,
            "authorization_verified": True,
            "secret_redaction_verified": True,
            "parallelization_allowed": True,
            "block_reason": None,
            "evidence_ref": "ev-preflight",
        }
        sidecar_path = self.root / "logs/preflight.json"
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        sidecar["operation_manifest_sha256"] = operation_manifest_hash(payload["operations"])
        _write_json(sidecar_path, sidecar)
        self._ref(payload, "ev-preflight")["sha256"] = _sha256(sidecar_path)
        return payload

    def _background_payload(self) -> dict[str, object]:
        payload = self.valid_payload()
        log_path = self.root / "logs/background.log"
        log_path.write_text("background complete\n", encoding="utf-8", newline="\n")
        log_size = log_path.stat().st_size
        payload["evidence_refs"].append(self._evidence("ev-background-log", "logs/background.log", kind="log"))
        payload["evidence_refs"].sort(key=lambda item: str(item["ref_id"]))
        operation = payload["operations"][1]
        operation["tool_family"] = "fastctx"
        operation["execution_mode"] = "background"
        operation["evidence_ref"] = "ev-background-log"
        operation["persisted_output_bytes"] = log_size
        operation["background_lifecycle"] = {
            "adapter": "fastctx",
            "job_id": "job:background-001",
            "terminal_state": "complete",
            "exit_code": 0,
            "log_evidence_ref": "ev-background-log",
            "log_unit": "byte",
            "log_start": 0,
            "log_end": log_size,
            "poll_count": 1,
            "stop_reason": "terminal",
        }
        payload["metrics"]["sequential_calls"] = 1
        payload["metrics"]["background_calls"] = 1
        payload["metrics"]["persisted_output_bytes"] = log_size
        return payload

    def test_valid_summary(self) -> None:
        validate_payload(self.valid_payload(), root=self.root)

    def test_complete_measurement_requires_registered_capture_adapter(self) -> None:
        with patch.object(validator_module, "REGISTERED_MEASUREMENT_ADAPTERS", {}):
            with self.assertRaises(ToolRoundSummaryValidationError):
                validate_payload(self.valid_payload(), root=self.root)

    def test_partial_observed_measurement_also_requires_trusted_capture_verifier(self) -> None:
        payload = self.valid_payload()
        payload["status"] = "partial"
        payload["operations"][0]["status"] = "partial"
        payload["metrics"]["partial_results"] = 1
        with patch.object(validator_module, "REGISTERED_MEASUREMENT_ADAPTERS", {}):
            with self.assertRaises(ToolRoundSummaryValidationError):
                validate_payload(payload, root=self.root)

    def test_adapter_name_without_callable_verifier_is_not_trusted(self) -> None:
        with patch.object(
            validator_module, "REGISTERED_MEASUREMENT_ADAPTERS", {"test-measurement-adapter": "registered"}
        ):
            with self.assertRaises(ToolRoundSummaryValidationError):
                validate_payload(self.valid_payload(), root=self.root)

    def test_parallel_requires_authoritative_preflight(self) -> None:
        payload = self._parallel_payload()
        payload["preflight"] = {**payload["preflight"], "evidence_ref": None}
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_parallel_preflight_boolean_must_match_sidecar(self) -> None:
        payload = self._parallel_payload()
        payload["preflight"] = {**payload["preflight"], "authorization_verified": False}
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_sequential_operations_cannot_self_attest_preflight_flags(self) -> None:
        payload = self.valid_payload()
        payload["preflight"]["same_scope_verified"] = True
        payload["preflight"]["authorization_verified"] = True
        payload["preflight"]["secret_redaction_verified"] = True
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_blocked_parallel_operations_cannot_self_attest_preflight_flags(self) -> None:
        payload = self._parallel_payload()
        for operation in payload["operations"]:
            operation["status"] = "blocked"
            operation["attempts"] = 0
            operation["round_id"] = None
            operation["visible_result_bytes"] = 0
            operation["persisted_output_bytes"] = 0
            operation["evidence_ref"] = None
            operation["background_lifecycle"] = None
        payload["status"] = "blocked"
        payload["measurement"] = {
            "rounds": "unknown",
            "tokens": "unknown",
            "rounds_evidence_ref": None,
            "tokens_evidence_ref": None,
        }
        payload["metrics"] = {
            "model_visible_rounds": 0,
            "underlying_tool_calls": 0,
            "parallel_groups": 1,
            "sequential_calls": 0,
            "background_calls": 0,
            "retries": 0,
            "visible_result_bytes": 0,
            "visible_result_tokens": 0,
            "persisted_output_bytes": 0,
            "partial_results": 0,
            "failed_calls": 0,
            "interrupted_calls": 0,
            "blocked_calls": 2,
        }
        payload["preflight"] = {
            "same_scope_verified": True,
            "authorization_verified": True,
            "secret_redaction_verified": True,
            "parallelization_allowed": False,
            "block_reason": "preflight not proven",
            "evidence_ref": None,
        }
        payload["round_events"] = []
        payload["external_boundaries"] = [
            {"boundary": "functions.exec", "observed": False, "reason": "outer continuation telemetry is unavailable"},
            {"boundary": "token-accounting", "observed": False, "reason": "service token accounting is unavailable"},
        ]
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_preflight_binds_operation_set(self) -> None:
        payload = self._parallel_payload()
        sidecar_path = self.root / "logs/preflight.json"
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        sidecar["operation_ids"] = ["read-a"]
        _write_json(sidecar_path, sidecar)
        self._ref(payload, "ev-preflight")["sha256"] = _sha256(sidecar_path)
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_preflight_manifest_binds_tool_call_lineage(self) -> None:
        payload = self._parallel_payload()
        payload["operations"][0]["tool_call_id"] = "call:changed"
        payload["operations"][1]["parent_tool_call_id"] = "call:changed"
        with patch.object(validator_module, "REGISTERED_PREFLIGHT_ADAPTERS", {"test-preflight-adapter": lambda context: True}):
            with self.assertRaises(ToolRoundSummaryValidationError):
                validate_payload(payload, root=self.root)

    def test_preflight_binds_current_agents_hash(self) -> None:
        payload = self._parallel_payload()
        (self.root / "AGENTS.md").write_text("# Changed contract\n", encoding="utf-8", newline="\n")
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_preflight_authority_symlink_is_rejected_before_hashing(self) -> None:
        payload = self._parallel_payload()
        external_authority = self.root.parent / f"{self.root.name}-outside-agents.md"
        external_authority.write_text("# Outside contract\n", encoding="utf-8", newline="\n")
        self.addCleanup(external_authority.unlink, missing_ok=True)
        authority_path = self.root / "AGENTS.md"
        authority_path.unlink()
        try:
            authority_path.symlink_to(external_authority)
        except OSError as exc:
            self.skipTest(f"file symlink unavailable: {type(exc).__name__}")
        sidecar_path = self.root / "logs/preflight.json"
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        sidecar["authority"]["sha256"] = _sha256(external_authority)
        _write_json(sidecar_path, sidecar)
        self._ref(payload, "ev-preflight")["sha256"] = _sha256(sidecar_path)
        with patch.object(validator_module, "REGISTERED_PREFLIGHT_ADAPTERS", {"test-preflight-adapter": lambda context: True}):
            with self.assertRaises(ToolRoundSummaryValidationError):
                validate_payload(payload, root=self.root)

    def test_preflight_sidecar_schema_is_checked_without_jsonschema_dependency(self) -> None:
        payload = self._parallel_payload()
        sidecar_path = self.root / "logs/preflight.json"
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        sidecar["checks"]["read_only_verified"] = False
        _write_json(sidecar_path, sidecar)
        self._ref(payload, "ev-preflight")["sha256"] = _sha256(sidecar_path)
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_preflight_sidecar_rejects_invalid_timestamp_and_scope_in_fallback(self) -> None:
        payload = self._parallel_payload()
        sidecar_path = self.root / "logs/preflight.json"
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        sidecar["generated_at"] = "not-a-time"
        sidecar["scope"]["scope_ref"] = "/outside"
        _write_json(sidecar_path, sidecar)
        self._ref(payload, "ev-preflight")["sha256"] = _sha256(sidecar_path)
        with patch.object(validator_module, "REGISTERED_PREFLIGHT_ADAPTERS", {"test-preflight-adapter": lambda context: True}):
            with self.assertRaises(ToolRoundSummaryValidationError):
                validate_payload(payload, root=self.root)

    def test_workspace_authored_preflight_is_rejected_without_registered_adapter(self) -> None:
        payload = self._parallel_payload()
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_registered_preflight_adapter_validates_bound_parallel_payload(self) -> None:
        payload = self._parallel_payload()
        with patch.object(validator_module, "REGISTERED_PREFLIGHT_ADAPTERS", {"test-preflight-adapter": lambda context: True}):
            validate_payload(payload, root=self.root)

    def test_project_scope_parallelization_is_blocked_in_v1(self) -> None:
        payload = self._parallel_payload()
        project_scope = {"scope_kind": "project", "scope_ref": "projects/p1"}
        payload["scope"] = project_scope
        for operation in payload["operations"]:
            operation["scope"] = project_scope
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_project_scope_parallelization_can_record_never_started_blocked_calls(self) -> None:
        payload = self._parallel_payload()
        project_scope = {"scope_kind": "project", "scope_ref": "projects/p1"}
        payload["scope"] = project_scope
        for operation in payload["operations"]:
            operation["scope"] = project_scope
            operation["status"] = "blocked"
            operation["attempts"] = 0
            operation["round_id"] = None
            operation["visible_result_bytes"] = 0
            operation["persisted_output_bytes"] = 0
            operation["evidence_ref"] = None
            operation["background_lifecycle"] = None
        for evidence in payload["evidence_refs"]:
            evidence["scope_kind"] = "project"
            evidence["scope_ref"] = "projects/p1"
        payload["status"] = "blocked"
        payload["measurement"] = {
            "rounds": "unknown",
            "tokens": "unknown",
            "rounds_evidence_ref": None,
            "tokens_evidence_ref": None,
        }
        payload["round_events"] = []
        payload["metrics"] = {
            "model_visible_rounds": 0,
            "underlying_tool_calls": 0,
            "parallel_groups": 1,
            "sequential_calls": 0,
            "background_calls": 0,
            "retries": 0,
            "visible_result_bytes": 0,
            "visible_result_tokens": 0,
            "persisted_output_bytes": 0,
            "partial_results": 0,
            "failed_calls": 0,
            "interrupted_calls": 0,
            "blocked_calls": 2,
        }
        payload["preflight"] = {
            "same_scope_verified": False,
            "authorization_verified": False,
            "secret_redaction_verified": False,
            "parallelization_allowed": False,
            "block_reason": "project scope is not enabled in v1",
            "evidence_ref": None,
        }
        payload["external_boundaries"] = [
            {"boundary": "functions.exec", "observed": False, "reason": "outer continuation telemetry is unavailable"},
            {"boundary": "token-accounting", "observed": False, "reason": "service token accounting is unavailable"},
        ]
        validate_payload(payload, root=self.root)

    def test_side_effecting_operation_cannot_run_in_parallel(self) -> None:
        payload = self._parallel_payload()
        payload["operations"][0]["access_mode"] = "side-effecting"
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_external_tool_cannot_self_attest_an_unregistered_adapter(self) -> None:
        payload = self._parallel_payload()
        payload["operations"][1]["tool_family"] = "mcp"
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)
        payload["external_boundaries"] = [
            {"boundary": "mcp-provider", "observed": True, "reason": "provider adapter emitted bound telemetry"}
        ]
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_external_tool_requires_its_boundary_record(self) -> None:
        payload = self.valid_payload()
        payload["operations"][0]["tool_family"] = "functions-exec"
        payload["operations"][0]["status"] = "partial"
        payload["metrics"]["partial_results"] = 1
        payload["status"] = "partial"
        payload["external_boundaries"] = []
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_unknown_rounds_require_the_matching_external_boundary(self) -> None:
        payload = self.valid_payload()
        payload["operations"][0]["tool_family"] = "mcp"
        payload["measurement"] = {
            "rounds": "unknown",
            "tokens": "unknown",
            "rounds_evidence_ref": None,
            "tokens_evidence_ref": None,
        }
        payload["round_events"] = []
        payload["metrics"]["model_visible_rounds"] = 0
        payload["metrics"]["visible_result_tokens"] = 0
        for operation in payload["operations"]:
            operation["round_id"] = None
        payload["external_boundaries"] = [
            {"boundary": "browser-provider", "observed": False, "reason": "browser telemetry unavailable"},
            {"boundary": "token-accounting", "observed": False, "reason": "service token accounting is unavailable"},
        ]
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_registered_observed_provider_boundary_can_complete(self) -> None:
        payload = self.valid_payload()
        payload["operations"][0]["tool_family"] = "functions-exec"
        payload["external_boundaries"] = [
            {"boundary": "functions.exec", "observed": True, "reason": "trusted provider telemetry is bound"}
        ]
        with patch.object(validator_module, "REGISTERED_OBSERVED_BOUNDARIES", {"functions.exec": lambda context: True}):
            validate_payload(payload, root=self.root)

    def test_complete_summary_cannot_have_continuation(self) -> None:
        payload = self.valid_payload()
        payload["continuation"] = {
            "has_more": True,
            "offsets": [{"operation_id": "read-a", "unit": "line", "next": 10}],
        }
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_path_traversal_is_rejected(self) -> None:
        payload = self.valid_payload()
        self._ref(payload, "ev-measurement")["path"] = "../outside.json"
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_windows_alternate_data_stream_evidence_path_is_rejected(self) -> None:
        payload = self.valid_payload()
        self._ref(payload, "ev-measurement")["path"] = "logs/measurement.json:hidden"
        with patch.object(validator_module, "jsonschema", None):
            with self.assertRaises(ToolRoundSummaryValidationError):
                validate_payload(payload, root=self.root)
        ledger = self._ledger(self.valid_payload())
        self._ref(ledger, "ev-measurement")["path"] = "logs/measurement.json:hidden"
        with self.assertRaises(ToolRoundSummaryValidationError):
            build(ledger, self.root)

    def test_reparse_workspace_root_is_rejected(self) -> None:
        payload = self.valid_payload()
        link = self.root.parent / f"{self.root.name}-root-link"
        try:
            link.symlink_to(self.root, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"directory symlink unavailable: {type(exc).__name__}")
        self.addCleanup(link.unlink, missing_ok=True)
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=link)

    def test_reparse_evidence_component_is_rejected(self) -> None:
        payload = self.valid_payload()
        link = self.root / "logs-link"
        try:
            link.symlink_to(self.root / "logs", target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"directory symlink unavailable: {type(exc).__name__}")
        self.addCleanup(link.unlink, missing_ok=True)
        measurement_ref = self._ref(payload, "ev-measurement")
        measurement_ref["path"] = "logs-link/measurement.json"
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_unredacted_secret_is_rejected(self) -> None:
        payload = self.valid_payload()
        payload["operations"][0]["status"] = "failed"
        payload["metrics"]["failed_calls"] = 1
        payload["status"] = "failed"
        payload["errors"] = [
            {"code": "tool.failure", "family": "tool", "severity": "error", "message": "authorization=raw-secret-value", "operation_id": "read-a"}
        ]
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_common_github_token_is_rejected_from_summary(self) -> None:
        payload = self.valid_payload()
        payload["status"] = "partial"
        payload["errors"] = [
            {
                "code": "tool.warning",
                "family": "redaction",
                "severity": "warning",
                "message": "credential ghp_1234567890abcdefghijklmnopqrstuv",
                "operation_id": None,
            }
        ]
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_secret_in_local_evidence_is_rejected(self) -> None:
        payload = self.valid_payload()
        evidence_path = self.root / "logs/secret.log"
        evidence_path.write_text("authorization=super-secret-value\n", encoding="utf-8", newline="\n")
        payload["evidence_refs"].append(self._evidence("ev-secret-log", "logs/secret.log", kind="log"))
        payload["evidence_refs"].sort(key=lambda item: str(item["ref_id"]))
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_secret_crossing_scan_chunk_boundary_is_rejected(self) -> None:
        payload = self.valid_payload()
        evidence_path = self.root / "logs/chunk-secret.log"
        evidence_path.write_text(
            "x" * (64 * 1024 - 5) + " github_pat_1234567890abcdefghijklmnopqrstuv\n",
            encoding="utf-8",
            newline="\n",
        )
        payload["evidence_refs"].append(self._evidence("ev-chunk-secret", "logs/chunk-secret.log", kind="log"))
        payload["evidence_refs"].sort(key=lambda item: str(item["ref_id"]))
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_redacted_placeholder_is_accepted(self) -> None:
        payload = self.valid_payload()
        payload["status"] = "partial"
        payload["errors"] = [
            {
                "code": "tool.warning",
                "family": "redaction",
                "severity": "warning",
                "message": "authorization=<redacted>",
                "operation_id": None,
            }
        ]
        validate_payload(payload, root=self.root)

    def test_unknown_redacted_placeholder_cannot_hide_a_credential(self) -> None:
        payload = self.valid_payload()
        payload["status"] = "partial"
        payload["errors"] = [
            {
                "code": "tool.warning",
                "family": "redaction",
                "severity": "warning",
                "message": "authorization=<redacted-token=ghp_1234567890abcdefghijklmnopqrstuv>",
                "operation_id": None,
            }
        ]
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_text_evidence_with_nul_control_bytes_is_rejected(self) -> None:
        payload = self.valid_payload()
        evidence_path = self.root / "logs/utf16.log"
        evidence_path.write_bytes("authorization=super-secret-value\n".encode("utf-16le"))
        payload["evidence_refs"].append(self._evidence("ev-utf16-log", "logs/utf16.log", kind="log"))
        payload["evidence_refs"].sort(key=lambda item: str(item["ref_id"]))
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_free_text_error_is_rejected(self) -> None:
        payload = self.valid_payload()
        payload["errors"] = ["tool failed"]
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_absolute_host_path_in_error_is_rejected(self) -> None:
        payload = self.valid_payload()
        payload["operations"][0]["status"] = "failed"
        payload["metrics"]["failed_calls"] = 1
        payload["status"] = "failed"
        payload["errors"] = [
            {"code": "tool.failure", "family": "tool", "severity": "error", "message": "failed at C:\\Users\\operator\\secret.log", "operation_id": "read-a"}
        ]
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_metrics_must_match_operations_and_round_events(self) -> None:
        payload = self.valid_payload()
        payload["metrics"] = {**payload["metrics"], "model_visible_rounds": 9, "underlying_tool_calls": 1}
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_blocked_zero_attempts_has_zero_retries(self) -> None:
        payload = self.valid_payload()
        blocked_operation = payload["operations"][0]
        blocked_operation["status"] = "blocked"
        blocked_operation["attempts"] = 0
        blocked_operation["round_id"] = None
        blocked_operation["visible_result_bytes"] = 0
        payload["preflight"]["block_reason"] = "preflight not proven"
        payload["status"] = "blocked"
        payload["metrics"]["underlying_tool_calls"] = 1
        payload["metrics"]["retries"] = 0
        payload["metrics"]["visible_result_bytes"] = 600
        payload["metrics"]["visible_result_tokens"] = 150
        payload["metrics"]["blocked_calls"] = 1
        measurement_path = self.root / "logs/measurement.json"
        measurement = json.loads(measurement_path.read_text(encoding="utf-8"))
        measurement["visible_result_bytes"] = 600
        measurement["token_measurement"]["visible_result_tokens"] = 150
        _write_json(measurement_path, measurement)
        self._ref(payload, "ev-measurement")["sha256"] = _sha256(measurement_path)
        validate_payload(payload, root=self.root)
        summary = build(self._ledger(payload), self.root)
        self.assertEqual(0, summary["metrics"]["retries"])

    def test_blocked_zero_attempts_cannot_claim_output_or_round_evidence(self) -> None:
        payload = self.valid_payload()
        payload["operations"][0]["status"] = "blocked"
        payload["operations"][0]["attempts"] = 0
        payload["preflight"]["block_reason"] = "preflight not proven"
        payload["status"] = "blocked"
        payload["metrics"]["underlying_tool_calls"] = 1
        payload["metrics"]["blocked_calls"] = 1
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_non_blocked_zero_attempts_is_rejected_without_jsonschema(self) -> None:
        payload = self.valid_payload()
        payload["operations"][0]["attempts"] = 0
        with patch.object(validator_module, "jsonschema", None):
            with self.assertRaises(ToolRoundSummaryValidationError):
                validate_payload(payload, root=self.root)

    def test_null_tool_call_id_is_rejected_by_dependency_free_fallback(self) -> None:
        payload = self.valid_payload()
        payload["operations"][0]["tool_call_id"] = None
        with patch.object(validator_module, "jsonschema", None):
            with self.assertRaises(ToolRoundSummaryValidationError):
                validate_payload(payload, root=self.root)

    def test_duplicate_tool_call_id_is_rejected(self) -> None:
        payload = self.valid_payload()
        payload["operations"][1]["tool_call_id"] = "call:read-a"
        payload["operations"][1]["parent_tool_call_id"] = None
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_parent_tool_call_cycle_is_rejected(self) -> None:
        payload = self.valid_payload()
        payload["operations"][0]["parent_tool_call_id"] = "call:read-b"
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_operation_scope_must_match_summary_scope(self) -> None:
        payload = self.valid_payload()
        payload["operations"][0]["scope"] = {"scope_kind": "repository", "scope_ref": "other"}
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_round_id_must_reference_round_event(self) -> None:
        payload = self.valid_payload()
        payload["operations"][0]["round_id"] = "round-missing"
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_round_event_must_be_referenced_by_an_operation(self) -> None:
        payload = self.valid_payload()
        orphan_event = {"round_id": "round-999", "turn_id": "turn-001", "result_blocks": 1, "observed": True}
        payload["round_events"].append(orphan_event)
        payload["metrics"]["model_visible_rounds"] = 2
        sidecar_path = self.root / "logs/measurement.json"
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        sidecar["round_events"].append(orphan_event)
        sidecar["round_measurement"]["model_visible_rounds"] = 2
        _write_json(sidecar_path, sidecar)
        self._ref(payload, "ev-measurement")["sha256"] = _sha256(sidecar_path)
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_parallel_group_cannot_span_multiple_round_events(self) -> None:
        payload = self._parallel_payload()
        payload["operations"][1]["round_id"] = "round-002"
        second_event = {"round_id": "round-002", "turn_id": "turn-001", "result_blocks": 1, "observed": True}
        payload["round_events"].append(second_event)
        payload["metrics"]["model_visible_rounds"] = 2
        measurement_path = self.root / "logs/measurement.json"
        measurement = json.loads(measurement_path.read_text(encoding="utf-8"))
        measurement["round_events"].append(second_event)
        measurement["round_measurement"]["model_visible_rounds"] = 2
        _write_json(measurement_path, measurement)
        self._ref(payload, "ev-measurement")["sha256"] = _sha256(measurement_path)
        preflight_path = self.root / "logs/preflight.json"
        preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
        preflight["operation_manifest_sha256"] = operation_manifest_hash(payload["operations"])
        _write_json(preflight_path, preflight)
        self._ref(payload, "ev-preflight")["sha256"] = _sha256(preflight_path)
        with patch.object(validator_module, "REGISTERED_PREFLIGHT_ADAPTERS", {"test-preflight-adapter": lambda context: True}):
            with self.assertRaises(ToolRoundSummaryValidationError):
                validate_payload(payload, root=self.root)

    def test_timing_must_be_ordered_iso8601(self) -> None:
        payload = self.valid_payload()
        payload["timing"] = {"started_at": "not-a-time", "finished_at": "2026-08-10T00:00:00Z"}
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_unknown_measurements_require_zero_values_and_boundaries(self) -> None:
        payload = self.valid_payload()
        payload["measurement"] = {
            "rounds": "unknown",
            "tokens": "unknown",
            "rounds_evidence_ref": None,
            "tokens_evidence_ref": None,
        }
        payload["round_events"] = []
        payload["metrics"]["model_visible_rounds"] = 0
        payload["metrics"]["visible_result_tokens"] = 0
        for operation in payload["operations"]:
            operation["round_id"] = None
        payload["external_boundaries"] = [
            {"boundary": "functions.exec", "observed": False, "reason": "outer continuation telemetry is unavailable"},
            {"boundary": "token-accounting", "observed": False, "reason": "service token accounting is unavailable"},
        ]
        validate_payload(payload, root=self.root)
        payload["external_boundaries"] = []
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_local_evidence_hash_is_verified(self) -> None:
        payload = self.valid_payload()
        self._ref(payload, "ev-measurement")["sha256"] = "sha256:" + "f" * 64
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_local_evidence_owner_cannot_be_unknown(self) -> None:
        payload = self.valid_payload()
        self._ref(payload, "ev-measurement")["owner"] = "unknown"
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_operation_evidence_aliases_cannot_double_count_one_file(self) -> None:
        payload = self.valid_payload()
        output_path = self.root / "logs/output-summary.txt"
        output_path.write_text("bounded result\n", encoding="utf-8", newline="\n")
        output_size = output_path.stat().st_size
        payload["evidence_refs"].extend(
            [
                self._evidence("ev-output-a", "logs/output-summary.txt", kind="summary"),
                self._evidence("ev-output-b", "logs/output-summary.txt", kind="summary"),
            ]
        )
        payload["evidence_refs"].sort(key=lambda item: str(item["ref_id"]))
        payload["operations"][0]["evidence_ref"] = "ev-output-a"
        payload["operations"][0]["persisted_output_bytes"] = output_size
        payload["operations"][1]["evidence_ref"] = "ev-output-b"
        payload["operations"][1]["persisted_output_bytes"] = output_size
        payload["metrics"]["persisted_output_bytes"] = output_size * 2
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_operation_evidence_cannot_reuse_a_measurement_sidecar(self) -> None:
        payload = self.valid_payload()
        measurement_size = (self.root / "logs/measurement.json").stat().st_size
        payload["operations"][0]["evidence_ref"] = "ev-measurement"
        payload["operations"][0]["persisted_output_bytes"] = measurement_size
        payload["metrics"]["persisted_output_bytes"] = measurement_size
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_duplicate_json_object_members_are_rejected(self) -> None:
        duplicate_json = self.root / "duplicate.json"
        duplicate_json.write_text('{"status":"complete","status":"failed"}\n', encoding="utf-8", newline="\n")
        with self.assertRaises(ToolRoundSummaryValidationError):
            _load_json(duplicate_json)

    def test_measurement_refs_must_be_verified_local_evidence(self) -> None:
        payload = self.valid_payload()
        payload["measurement"]["rounds_evidence_ref"] = "ev-missing"
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_measurement_sidecar_content_is_bound_to_summary(self) -> None:
        payload = self.valid_payload()
        sidecar_path = self.root / "logs/measurement.json"
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        sidecar["visible_result_bytes"] = 999
        _write_json(sidecar_path, sidecar)
        self._ref(payload, "ev-measurement")["sha256"] = _sha256(sidecar_path)
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_measurement_sidecar_rejects_invalid_timestamp_in_fallback(self) -> None:
        payload = self.valid_payload()
        sidecar_path = self.root / "logs/measurement.json"
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        sidecar["recorded_at"] = "not-a-time"
        _write_json(sidecar_path, sidecar)
        self._ref(payload, "ev-measurement")["sha256"] = _sha256(sidecar_path)
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_rounds_sidecar_bytes_are_bound_when_tokens_unknown(self) -> None:
        payload = self.valid_payload()
        payload["measurement"] = {
            "rounds": "observed",
            "tokens": "unknown",
            "rounds_evidence_ref": "ev-measurement",
            "tokens_evidence_ref": None,
        }
        payload["metrics"]["visible_result_tokens"] = 0
        payload["external_boundaries"] = [
            {"boundary": "token-accounting", "observed": False, "reason": "token accounting unavailable"}
        ]
        sidecar_path = self.root / "logs/measurement.json"
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        sidecar["visible_result_bytes"] = 999
        _write_json(sidecar_path, sidecar)
        self._ref(payload, "ev-measurement")["sha256"] = _sha256(sidecar_path)
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_unobserved_functions_exec_boundary_cannot_claim_observed_rounds(self) -> None:
        payload = self.valid_payload()
        operation = payload["operations"][0]
        operation["tool_family"] = "functions-exec"
        operation["status"] = "partial"
        payload["status"] = "partial"
        payload["metrics"]["partial_results"] = 1
        payload["external_boundaries"] = [
            {"boundary": "functions.exec", "observed": False, "reason": "outer round telemetry unavailable"}
        ]
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_external_artifact_cannot_form_complete_summary(self) -> None:
        payload = self.valid_payload()
        payload["evidence_refs"].append(
            {
                "ref_id": "ev-z-external",
                "kind": "artifact",
                "artifact_id": "mcp:artifact-001",
                "sha256": "sha256:" + "a" * 64,
                "hash_status": "external-unverified",
                "run_id": "round-001",
                "turn_id": "turn-001",
                "scope_kind": "repository",
                "scope_ref": "repo",
                "owner": "mcp-provider",
            }
        )
        payload["external_boundaries"].append(
            {"boundary": "mcp-provider", "observed": False, "reason": "provider attestation is unavailable"}
        )
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)
        payload["status"] = "partial"
        validate_payload(payload, root=self.root)

    def test_external_artifact_requires_owner_binding(self) -> None:
        payload = self.valid_payload()
        payload["evidence_refs"].append(
            {
                "ref_id": "ev-z-external",
                "kind": "artifact",
                "artifact_id": "mcp:artifact-001",
                "sha256": "sha256:" + "a" * 64,
                "hash_status": "external-unverified",
                "run_id": "round-001",
                "turn_id": "turn-001",
            }
        )
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_external_artifact_scope_binding_is_checked(self) -> None:
        payload = self.valid_payload()
        payload["evidence_refs"].append(
            {
                "ref_id": "ev-z-external",
                "kind": "artifact",
                "artifact_id": "mcp:artifact-001",
                "sha256": "sha256:" + "a" * 64,
                "hash_status": "external-unverified",
                "run_id": "round-001",
                "turn_id": "turn-001",
                "scope_kind": "workspace",
                "scope_ref": "other-workspace",
                "owner": "mcp-provider",
            }
        )
        payload["external_boundaries"].append(
            {"boundary": "mcp-provider", "observed": False, "reason": "provider attestation is unavailable"}
        )
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_external_artifact_requires_matching_provider_boundary(self) -> None:
        payload = self.valid_payload()
        payload["evidence_refs"].append(
            {
                "ref_id": "ev-z-external",
                "kind": "artifact",
                "artifact_id": "mcp:artifact-001",
                "sha256": "sha256:" + "a" * 64,
                "hash_status": "external-unverified",
                "run_id": "round-001",
                "turn_id": "turn-001",
                "scope_kind": "repository",
                "scope_ref": "repo",
                "owner": "mcp-provider",
            }
        )
        payload["evidence_refs"].sort(key=lambda item: str(item["ref_id"]))
        payload["external_boundaries"] = [
            {"boundary": "browser-provider", "observed": False, "reason": "browser telemetry unavailable"}
        ]
        payload["status"] = "partial"
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_external_artifact_owner_must_match_artifact_namespace(self) -> None:
        payload = self.valid_payload()
        payload["evidence_refs"].append(
            {
                "ref_id": "ev-z-external",
                "kind": "artifact",
                "artifact_id": "mcp:artifact-001",
                "sha256": "sha256:" + "a" * 64,
                "hash_status": "external-unverified",
                "run_id": "round-001",
                "turn_id": "turn-001",
                "scope_kind": "repository",
                "scope_ref": "repo",
                "owner": "browser-provider",
            }
        )
        payload["evidence_refs"].sort(key=lambda item: str(item["ref_id"]))
        payload["external_boundaries"] = [
            {"boundary": "mcp-provider", "observed": False, "reason": "MCP telemetry unavailable"}
        ]
        payload["status"] = "partial"
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_interrupted_state_is_consistent(self) -> None:
        payload = self.valid_payload()
        payload["operations"][0]["status"] = "interrupted"
        payload["metrics"]["interrupted_calls"] = 1
        payload["status"] = "interrupted"
        validate_payload(payload, root=self.root)

    def test_warning_error_requires_partial_status(self) -> None:
        payload = self.valid_payload()
        payload["status"] = "partial"
        payload["errors"] = [
            {"code": "tool.warning", "family": "tool", "severity": "warning", "message": "provider returned a warning", "operation_id": None}
        ]
        validate_payload(payload, root=self.root)
        payload["status"] = "complete"
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_producer_derives_metrics_from_operations_and_events(self) -> None:
        ledger = self._ledger(self.valid_payload())
        ledger["model_visible_rounds"] = 99
        summary = build(ledger, self.root)
        self.assertEqual(1, summary["metrics"]["model_visible_rounds"])
        self.assertEqual(2, summary["metrics"]["underlying_tool_calls"])
        self.assertEqual(0, summary["metrics"]["parallel_groups"])
        self.assertEqual(1200, summary["metrics"]["visible_result_bytes"])

    def test_producer_marks_external_artifact_partial(self) -> None:
        ledger = self._ledger(self.valid_payload())
        ledger["evidence_refs"].append(
            {
                "ref_id": "ev-z-external",
                "kind": "artifact",
                "artifact_id": "mcp:artifact-001",
                "sha256": "sha256:" + "a" * 64,
                "owner": "mcp-provider",
            }
        )
        ledger["external_boundaries"].append(
            {"boundary": "mcp-provider", "observed": False, "reason": "provider attestation is unavailable"}
        )
        summary = build(ledger, self.root)
        self.assertEqual("partial", summary["status"])
        self.assertEqual("external-unverified", summary["evidence_refs"][-1]["hash_status"])

    def test_producer_derives_interrupted_count_and_status(self) -> None:
        ledger = self._ledger(self.valid_payload())
        ledger["operations"][0]["status"] = "interrupted"
        summary = build(ledger, self.root)
        self.assertEqual("interrupted", summary["status"])
        self.assertEqual(1, summary["metrics"]["interrupted_calls"])

    def test_producer_accounts_for_background_operations(self) -> None:
        payload = self._background_payload()
        with patch.object(validator_module, "REGISTERED_BACKGROUND_ADAPTERS", {"fastctx": lambda context: True}):
            summary = build(self._ledger(payload), self.root)
        self.assertEqual(1, summary["metrics"]["background_calls"])
        self.assertEqual(1, summary["metrics"]["sequential_calls"])

    def test_background_without_lifecycle_cannot_complete(self) -> None:
        payload = self.valid_payload()
        operation = payload["operations"][1]
        operation["execution_mode"] = "background"
        payload["metrics"]["sequential_calls"] = 1
        payload["metrics"]["background_calls"] = 1
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(payload, root=self.root)

    def test_background_complete_requires_registered_adapter(self) -> None:
        with self.assertRaises(ToolRoundSummaryValidationError):
            validate_payload(self._background_payload(), root=self.root)

    def test_registered_background_lifecycle_can_validate(self) -> None:
        payload = self._background_payload()
        with patch.object(validator_module, "REGISTERED_BACKGROUND_ADAPTERS", {"fastctx": lambda context: True}):
            validate_payload(payload, root=self.root)

    def test_timed_out_running_background_job_is_failed_and_valid(self) -> None:
        payload = self._background_payload()
        operation = payload["operations"][1]
        operation["status"] = "failed"
        payload["status"] = "failed"
        payload["metrics"]["failed_calls"] = 1
        payload["errors"] = [{
            "code": "timeout",
            "family": "timeout",
            "severity": "error",
            "message": "background job exceeded deadline",
            "operation_id": operation["operation_id"],
        }]
        lifecycle = operation["background_lifecycle"]
        lifecycle["terminal_state"] = "running"
        lifecycle["exit_code"] = None
        lifecycle["timed_out"] = True
        with patch.object(validator_module, "REGISTERED_BACKGROUND_ADAPTERS", {"fastctx": lambda context: True}):
            validate_payload(payload, root=self.root)

    def test_timed_out_background_job_requires_running_state(self) -> None:
        payload = self._background_payload()
        lifecycle = payload["operations"][1]["background_lifecycle"]
        lifecycle["timed_out"] = True
        with patch.object(validator_module, "REGISTERED_BACKGROUND_ADAPTERS", {"fastctx": lambda context: True}):
            with self.assertRaises(ToolRoundSummaryValidationError):
                validate_payload(payload, root=self.root)

    def test_background_lifecycle_binds_exit_and_log_range(self) -> None:
        payload = self._background_payload()
        lifecycle = payload["operations"][1]["background_lifecycle"]
        lifecycle["exit_code"] = 1
        with patch.object(validator_module, "REGISTERED_BACKGROUND_ADAPTERS", {"fastctx": lambda context: True}):
            with self.assertRaises(ToolRoundSummaryValidationError):
                validate_payload(payload, root=self.root)
        payload = self._background_payload()
        payload["operations"][1]["background_lifecycle"]["log_end"] += 1
        with patch.object(validator_module, "REGISTERED_BACKGROUND_ADAPTERS", {"fastctx": lambda context: True}):
            with self.assertRaises(ToolRoundSummaryValidationError):
                validate_payload(payload, root=self.root)

    def test_cli_does_not_disclose_absolute_output_path(self) -> None:
        ledger = self._ledger(self.valid_payload())
        ledger["operations"][0]["status"] = "partial"
        ledger["measurement"] = {
            "rounds": "unknown",
            "tokens": "unknown",
            "rounds_evidence_ref": None,
            "tokens_evidence_ref": None,
        }
        ledger["round_events"] = []
        for operation in ledger["operations"]:
            operation["round_id"] = None
        ledger["external_boundaries"] = [
            {"boundary": "codex-service", "observed": False, "reason": "outer round telemetry unavailable"},
            {"boundary": "token-accounting", "observed": False, "reason": "token accounting unavailable"},
        ]
        input_path = self.root / "ledger.json"
        output_path = self.root / "logs/summary.json"
        _write_json(input_path, ledger)
        completed = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/python/build_model_visible_tool_round_summary.py"),
                "--input",
                str(input_path),
                "--output",
                str(output_path),
                "--root",
                str(self.root),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertNotIn(str(self.root), completed.stdout)
        self.assertEqual("logs/summary.json", json.loads(completed.stdout)["output_ref"])
        self.assertTrue(output_path.is_file())

    def test_cli_error_does_not_disclose_absolute_input_path(self) -> None:
        missing_path = self.root / "private/missing-ledger.json"
        completed = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/python/build_model_visible_tool_round_summary.py"),
                "--input",
                str(missing_path),
                "--output",
                str(self.root / "summary.json"),
                "--root",
                str(self.root),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(2, completed.returncode)
        self.assertNotIn(str(self.root), completed.stderr)

    def test_cli_rejects_output_outside_workspace_root(self) -> None:
        ledger = self._ledger(self.valid_payload())
        input_path = self.root / "ledger.json"
        _write_json(input_path, ledger)
        with tempfile.TemporaryDirectory() as outside:
            outside_output = Path(outside) / "outside-summary.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts/python/build_model_visible_tool_round_summary.py"),
                    "--input",
                    str(input_path),
                    "--output",
                    str(outside_output),
                    "--root",
                    str(self.root),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(2, completed.returncode)
            self.assertNotIn(str(self.root), completed.stderr)
            self.assertFalse(outside_output.exists())

    def test_cli_does_not_overwrite_existing_evidence(self) -> None:
        ledger = self._ledger(self.valid_payload())
        input_path = self.root / "ledger.json"
        output_path = self.root / "logs/existing-summary.json"
        original = b'{"status":"failed"}\n'
        _write_json(input_path, ledger)
        output_path.write_bytes(original)
        completed = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/python/build_model_visible_tool_round_summary.py"),
                "--input",
                str(input_path),
                "--output",
                str(output_path),
                "--root",
                str(self.root),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(2, completed.returncode)
        self.assertEqual(original, output_path.read_bytes())
        self.assertNotIn(str(self.root), completed.stderr)


if __name__ == "__main__":
    unittest.main()
