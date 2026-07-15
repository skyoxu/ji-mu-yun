#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import msvcrt
import os
import re
import sys
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "vdd.clarification-state.v1"
HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
QUESTION_ID_PATTERN = re.compile(r"^CQ-[0-9]{3,}$")
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SENSITIVE_KEY_PATTERN = re.compile(
    r"(^|_)(api_?key|authorization|credential|password|secret|token|access_token|refresh_token|"
    r"raw_user_(?:text|input)|raw_conversation|conversation_transcript|personal_data|pii|"
    r"email_address|phone_number)($|_)",
    re.IGNORECASE,
)
SENSITIVE_VALUE_PATTERNS = (
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)
SENSITIVE_VALUE_FAMILIES = (
    "bearer",
    "openai",
    "github-classic",
    "github-fine-grained",
    "aws-access-key",
    "google-api-key",
    "slack-token",
    "private-key",
)
ALLOWED_MODES = {"create", "repair"}
ALLOWED_STATUSES = {"active", "closed", "invalidated", "superseded"}
INVALIDATION_SOURCE_STATUSES = {"active", "closed"}
SUPERSEDE_SOURCE_STATUSES = {"active", "closed", "invalidated"}
EVIDENCE_TARGET_OVERLAP_POLICY = "disjoint"
MAXIMUM_ACTIVE_RUNS_PER_TARGET = 1
TARGET_IDENTITY_CASE_POLICY = "windows-case-insensitive"
STATE_MUTATION_LOCK_POLICY = "repository-canonical-target-scoped-cross-process"
TARGET_REGISTRY_POLICY = "repository-canonical-independent-of-evidence-root"
TRANSITION_COMMIT_POLICY = "recoverable-pending-idempotent-event"
COMMAND_RULE_IDS = (
    "VDD-CLARIFICATION-ACTIVE-RUN",
    "VDD-CLARIFICATION-EVIDENCE-OVERLAP",
    "VDD-CLARIFICATION-QUESTION-TRANSITION",
    "VDD-CLARIFICATION-STATE-TRANSITION",
)
ALLOWED_INTERACTION_MODES = {"interactive", "headless"}
ALLOWED_QUESTION_STATUSES = {"open", "answered", "deferred", "superseded", "reopened"}
ALLOWED_QUESTION_BASES = {"gap", "conflict", "change", "reopened", "confirmed_authority"}
QUESTION_STATUS_TRANSITIONS = {
    "open": {"open", "answered", "deferred", "superseded"},
    "answered": {"answered", "superseded"},
    "deferred": {"deferred", "answered", "superseded"},
    "reopened": {"reopened", "answered", "deferred", "superseded"},
    "superseded": {"superseded"},
}
MINIMUM_QUESTIONS_PER_ROUND = 5
DIMENSION_KEYS = (
    "goal_scope_non_goals",
    "authority_current_state",
    "constraints_compatibility",
    "acceptance_evidence",
    "dependencies_risks_recovery",
)
REQUIRED_STATE_FIELDS = (
    "schema_version",
    "run_id",
    "mode",
    "target",
    "target_slug",
    "status",
    "interaction_mode",
    "authority_hash",
    "current_authority_hash",
    "target_hash",
    "current_target_hash",
    "confirmed_boundaries",
    "non_goals",
    "conflicts",
    "open_items",
    "open_blocker_count",
    "questions",
    "rounds",
    "exit_attestation",
    "write_disposition",
    "updated_at",
)
REQUIRED_ROUND_FIELDS = (
    "round_id",
    "question_ids",
    "same_level_exhausted",
    "same_level_exhausted_reason",
    "confidence",
    "blocker_count",
    "dimension_scores",
    "dimension_evidence",
    "recommend_exit",
    "analysis",
    "user_turn_id",
)
REQUIRED_QUESTION_FIELDS = ("id", "status", "blocking", "summary", "recommendation", "basis")
ALLOWED_QUESTION_FIELDS = frozenset((*REQUIRED_QUESTION_FIELDS, "owner", "recheck_condition"))
REOPENABLE_QUESTION_STATUSES = {"answered", "deferred"}
OPEN_BLOCKER_STATUSES = {"open", "reopened", "deferred"}
REGISTRY_SCHEMA_VERSION = "vdd.clarification-target-registry.v1"
PENDING_TRANSITION_SCHEMA_VERSION = "vdd.clarification-pending-transition.v1"
REQUIRED_EXIT_FIELDS = (
    "actor",
    "explicit_no_more_clarification",
    "explicit_write_permission",
    "user_response_hash",
    "user_turn_id",
    "summary",
    "confidence",
    "authority_hash",
    "target_hash",
    "draft_only",
    "closed_at",
)


class ClarificationCommandError(ValueError):
    def __init__(self, rule_id: str, message: str) -> None:
        super().__init__(message)
        self.rule_id = rule_id


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def finding(rule_id: str, target: str, message: str) -> dict[str, str]:
    return {"rule_id": rule_id, "target": target, "message": message}


def is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def is_timezone_datetime(value: Any) -> bool:
    if not is_non_empty_string(value):
        return False
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is not None
    except ValueError:
        return False


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant is not allowed: {value}")


def _sensitive_paths(value: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}"
            normalized_key = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(key))
            normalized_key = re.sub(r"[^A-Za-z0-9]+", "_", normalized_key).strip("_")
            if SENSITIVE_KEY_PATTERN.search(normalized_key):
                hits.append(child)
            hits.extend(_sensitive_paths(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            hits.extend(_sensitive_paths(item, f"{path}[{index}]"))
    elif isinstance(value, str) and any(pattern.search(value) for pattern in SENSITIVE_VALUE_PATTERNS):
        hits.append(path)
    return hits


def validate_state_data(data: Any, target: str = "state.json") -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if not isinstance(data, dict):
        return [finding("VDD-CLARIFICATION-PARSE", target, "state must be a JSON object")]

    for field_name in REQUIRED_STATE_FIELDS:
        if field_name not in data:
            findings.append(
                finding("VDD-CLARIFICATION-FIELD", target, f"missing required field: {field_name}")
            )

    sensitive = _sensitive_paths(data)
    if sensitive:
        findings.append(
            finding(
                "VDD-CLARIFICATION-SENSITIVE",
                target,
                f"state contains prohibited sensitive fields or values: {sensitive}",
            )
        )

    required_strings = ("run_id", "target", "target_slug")
    if data.get("schema_version") != SCHEMA_VERSION:
        findings.append(
            finding(
                "VDD-CLARIFICATION-SCHEMA",
                target,
                f"unsupported schema_version: {data.get('schema_version')!r}",
            )
        )
    for field_name in required_strings:
        if not is_non_empty_string(data.get(field_name)):
            findings.append(
                finding("VDD-CLARIFICATION-FIELD", target, f"{field_name} is required")
            )
    if data.get("mode") not in ALLOWED_MODES:
        findings.append(
            finding("VDD-CLARIFICATION-FIELD", target, f"invalid mode: {data.get('mode')!r}")
        )
    if data.get("status") not in ALLOWED_STATUSES:
        findings.append(
            finding("VDD-CLARIFICATION-FIELD", target, f"invalid status: {data.get('status')!r}")
        )
    if data.get("interaction_mode") not in ALLOWED_INTERACTION_MODES:
        findings.append(
            finding(
                "VDD-CLARIFICATION-FIELD",
                target,
                f"invalid interaction_mode: {data.get('interaction_mode')!r}",
            )
        )
    for field_name in ("authority_hash", "current_authority_hash", "target_hash", "current_target_hash"):
        if not isinstance(data.get(field_name), str) or not HASH_PATTERN.fullmatch(data[field_name]):
            findings.append(
                finding("VDD-CLARIFICATION-HASH", target, f"invalid {field_name}")
            )
    if not is_timezone_datetime(data.get("updated_at")):
        findings.append(
            finding("VDD-CLARIFICATION-FIELD", target, "updated_at must include a timezone")
        )

    for field_name in ("confirmed_boundaries", "non_goals", "conflicts", "open_items"):
        value = data.get(field_name)
        if not isinstance(value, list) or any(not is_non_empty_string(item) for item in value):
            findings.append(
                finding(
                    "VDD-CLARIFICATION-FIELD",
                    target,
                    f"{field_name} must be a string list",
                )
            )

    blocker_count = data.get("open_blocker_count")
    if not isinstance(blocker_count, int) or isinstance(blocker_count, bool) or blocker_count < 0:
        findings.append(
            finding(
                "VDD-CLARIFICATION-BLOCKER",
                target,
                "open_blocker_count must be a non-negative integer",
            )
        )
        blocker_count = 0

    questions = data.get("questions")
    question_map: dict[str, dict[str, Any]] = {}
    if not isinstance(questions, list):
        findings.append(
            finding("VDD-CLARIFICATION-QUESTION", target, "questions must be a list")
        )
    else:
        for index, question in enumerate(questions):
            question_target = f"{target}#questions[{index}]"
            if not isinstance(question, dict):
                findings.append(
                    finding("VDD-CLARIFICATION-QUESTION", question_target, "question must be an object")
                )
                continue
            for field_name in REQUIRED_QUESTION_FIELDS:
                if field_name not in question:
                    findings.append(
                        finding(
                            "VDD-CLARIFICATION-QUESTION",
                            question_target,
                            f"missing required field: {field_name}",
                        )
                    )
            extra_fields = sorted(set(question) - ALLOWED_QUESTION_FIELDS)
            if extra_fields:
                findings.append(
                    finding(
                        "VDD-CLARIFICATION-QUESTION",
                        question_target,
                        f"unsupported question fields: {extra_fields}",
                    )
                )
            question_id = question.get("id")
            if not isinstance(question_id, str) or not QUESTION_ID_PATTERN.fullmatch(question_id):
                findings.append(
                    finding("VDD-CLARIFICATION-QUESTION", question_target, "invalid stable question id")
                )
            elif question_id in question_map:
                findings.append(
                    finding("VDD-CLARIFICATION-QUESTION", question_target, f"duplicate id: {question_id}")
                )
            else:
                question_map[question_id] = question
            if question.get("status") not in ALLOWED_QUESTION_STATUSES:
                findings.append(
                    finding("VDD-CLARIFICATION-QUESTION", question_target, "invalid question status")
                )
            if question.get("status") == "deferred":
                for field_name in ("owner", "recheck_condition"):
                    if not is_non_empty_string(question.get(field_name)):
                        findings.append(
                            finding(
                                "VDD-CLARIFICATION-DEFERRED",
                                question_target,
                                f"deferred question requires {field_name}",
                            )
                        )
            if not isinstance(question.get("blocking"), bool):
                findings.append(
                    finding("VDD-CLARIFICATION-QUESTION", question_target, "blocking must be boolean")
                )
            for field_name in ("summary", "recommendation"):
                if not is_non_empty_string(question.get(field_name)):
                    findings.append(
                        finding(
                            "VDD-CLARIFICATION-QUESTION",
                            question_target,
                            f"{field_name} is required",
                        )
                    )
            basis = question.get("basis")
            if basis not in ALLOWED_QUESTION_BASES:
                findings.append(
                    finding("VDD-CLARIFICATION-QUESTION", question_target, "invalid question basis")
                )
            if data.get("mode") == "repair" and basis == "confirmed_authority":
                findings.append(
                    finding(
                        "VDD-CLARIFICATION-REASK",
                        question_target,
                        "repair mode must not re-ask confirmed authority",
                    )
                )
        computed_blockers = sum(
            1
            for question in questions
            if isinstance(question, dict)
            and question.get("blocking") is True
            and question.get("status") in OPEN_BLOCKER_STATUSES
        )
        if isinstance(blocker_count, int) and blocker_count != computed_blockers:
            findings.append(
                finding(
                    "VDD-CLARIFICATION-BLOCKER",
                    target,
                    f"open_blocker_count={blocker_count} does not match questions={computed_blockers}",
                )
            )

    rounds = data.get("rounds")
    if not isinstance(rounds, list):
        findings.append(finding("VDD-CLARIFICATION-ROUND", target, "rounds must be a list"))
        rounds = []
    round_ids: set[str] = set()
    for index, round_item in enumerate(rounds):
        round_target = f"{target}#rounds[{index}]"
        if not isinstance(round_item, dict):
            findings.append(
                finding("VDD-CLARIFICATION-ROUND", round_target, "round must be an object")
            )
            continue
        for field_name in REQUIRED_ROUND_FIELDS:
            if field_name not in round_item:
                findings.append(
                    finding(
                        "VDD-CLARIFICATION-ROUND",
                        round_target,
                        f"missing required field: {field_name}",
                    )
                )
        round_id = round_item.get("round_id")
        if not is_non_empty_string(round_id) or round_id in round_ids:
            findings.append(
                finding("VDD-CLARIFICATION-ROUND", round_target, "round_id must be unique")
            )
        else:
            round_ids.add(round_id)
        question_ids = round_item.get("question_ids")
        if not isinstance(question_ids, list) or any(
            not isinstance(item, str) or item not in question_map for item in question_ids
        ):
            findings.append(
                finding(
                    "VDD-CLARIFICATION-ROUND",
                    round_target,
                    "question_ids must reference known questions",
                )
            )
            question_ids = []
        if len(question_ids) != len(set(question_ids)):
            findings.append(
                finding("VDD-CLARIFICATION-ROUND", round_target, "question_ids must be unique")
            )
        exhausted = round_item.get("same_level_exhausted")
        reason = round_item.get("same_level_exhausted_reason")
        if len(question_ids) < MINIMUM_QUESTIONS_PER_ROUND and not (
            exhausted is True and is_non_empty_string(reason)
        ):
            findings.append(
                finding(
                    "VDD-CLARIFICATION-QUESTION-COUNT",
                    round_target,
                    "fewer than five questions requires a same-level exhaustion reason",
                )
            )
        if len(question_ids) >= MINIMUM_QUESTIONS_PER_ROUND and exhausted not in {False, None}:
            findings.append(
                finding(
                    "VDD-CLARIFICATION-QUESTION-COUNT",
                    round_target,
                    "same_level_exhausted must be false when five or more questions are asked",
                )
            )
        confidence = round_item.get("confidence")
        if not isinstance(confidence, int) or isinstance(confidence, bool) or not 0 <= confidence <= 100:
            findings.append(
                finding("VDD-CLARIFICATION-CONFIDENCE", round_target, "confidence must be 0..100")
            )
        dimension_scores = round_item.get("dimension_scores")
        if not isinstance(dimension_scores, dict) or set(dimension_scores) != set(DIMENSION_KEYS):
            findings.append(
                finding(
                    "VDD-CLARIFICATION-CONFIDENCE",
                    round_target,
                    f"dimension_scores must contain exactly {list(DIMENSION_KEYS)}",
                )
            )
        else:
            score_values = list(dimension_scores.values())
            if any(
                not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 20
                for value in score_values
            ):
                findings.append(
                    finding(
                        "VDD-CLARIFICATION-CONFIDENCE",
                        round_target,
                        "dimension scores must be integers from 0 to 20",
                    )
                )
            elif isinstance(confidence, int) and sum(score_values) != confidence:
                findings.append(
                    finding(
                        "VDD-CLARIFICATION-CONFIDENCE",
                        round_target,
                        "confidence must equal the sum of dimension scores",
                    )
                )
        dimension_evidence = round_item.get("dimension_evidence")
        if not isinstance(dimension_evidence, dict) or set(dimension_evidence) != set(DIMENSION_KEYS) or any(
            not is_non_empty_string(value) for value in dimension_evidence.values()
        ):
            findings.append(
                finding(
                    "VDD-CLARIFICATION-CONFIDENCE",
                    round_target,
                    f"dimension_evidence must explain exactly {list(DIMENSION_KEYS)}",
                )
            )
        round_blocker_count = round_item.get("blocker_count")
        if not isinstance(round_blocker_count, int) or isinstance(round_blocker_count, bool) or round_blocker_count < 0:
            findings.append(
                finding(
                    "VDD-CLARIFICATION-BLOCKER",
                    round_target,
                    "round blocker_count must be a non-negative integer",
                )
            )
            round_blocker_count = 0
        if round_blocker_count > 0 and isinstance(confidence, int) and confidence > 89:
            findings.append(
                finding(
                    "VDD-CLARIFICATION-CONFIDENCE",
                    round_target,
                    "open blockers cap confidence at 89",
                )
            )
        recommend_exit = round_item.get("recommend_exit")
        if not isinstance(recommend_exit, bool):
            findings.append(
                finding(
                    "VDD-CLARIFICATION-CONFIDENCE",
                    round_target,
                    "recommend_exit must be boolean",
                )
            )
        elif recommend_exit and (not isinstance(confidence, int) or confidence < 90 or round_blocker_count > 0):
            findings.append(
                finding(
                    "VDD-CLARIFICATION-CONFIDENCE",
                    round_target,
                    "exit may be recommended only at confidence >= 90 with no blockers",
                )
            )
        if not is_non_empty_string(round_item.get("analysis")):
            findings.append(
                finding("VDD-CLARIFICATION-ROUND", round_target, "analysis is required")
            )
        if not is_non_empty_string(round_item.get("user_turn_id")):
            findings.append(
                finding("VDD-CLARIFICATION-ROUND", round_target, "user_turn_id is required")
            )

    status = data.get("status")
    disposition = data.get("write_disposition")
    exit_attestation = data.get("exit_attestation")
    if status == "closed":
        if not rounds:
            findings.append(
                finding("VDD-CLARIFICATION-EXIT", target, "closed state requires at least one round")
            )
        if data.get("interaction_mode") != "interactive":
            findings.append(
                finding("VDD-CLARIFICATION-HEADLESS", target, "headless state cannot close")
            )
        if not isinstance(exit_attestation, dict):
            findings.append(
                finding("VDD-CLARIFICATION-EXIT", target, "closed state requires exit_attestation")
            )
        else:
            for field_name in REQUIRED_EXIT_FIELDS:
                if field_name not in exit_attestation:
                    findings.append(
                        finding(
                            "VDD-CLARIFICATION-EXIT",
                            target,
                            f"missing exit field: {field_name}",
                        )
                    )
            if exit_attestation.get("actor") != "user":
                findings.append(
                    finding("VDD-CLARIFICATION-AUTO-EXIT", target, "exit actor must be user")
                )
            if exit_attestation.get("explicit_no_more_clarification") is not True or exit_attestation.get(
                "explicit_write_permission"
            ) is not True:
                findings.append(
                    finding(
                        "VDD-CLARIFICATION-EXIT",
                        target,
                        "exit must attest both no-more-clarification and write permission",
                    )
                )
            for field_name in ("user_response_hash", "authority_hash", "target_hash"):
                if not isinstance(exit_attestation.get(field_name), str) or not HASH_PATTERN.fullmatch(
                    exit_attestation[field_name]
                ):
                    findings.append(
                        finding("VDD-CLARIFICATION-EXIT", target, f"invalid exit {field_name}")
                    )
            for field_name in ("user_turn_id", "summary"):
                if not is_non_empty_string(exit_attestation.get(field_name)):
                    findings.append(
                        finding("VDD-CLARIFICATION-EXIT", target, f"exit {field_name} is required")
                    )
            if rounds and isinstance(rounds[-1], dict) and exit_attestation.get("user_turn_id") == rounds[-1].get(
                "user_turn_id"
            ):
                findings.append(
                    finding(
                        "VDD-CLARIFICATION-EXIT",
                        target,
                        "exit must come from a distinct post-summary user turn",
                    )
                )
            if not is_timezone_datetime(exit_attestation.get("closed_at")):
                findings.append(
                    finding("VDD-CLARIFICATION-EXIT", target, "closed_at must include a timezone")
                )
            exit_confidence = exit_attestation.get("confidence")
            if not isinstance(exit_confidence, int) or isinstance(exit_confidence, bool) or not 0 <= exit_confidence <= 100:
                findings.append(
                    finding("VDD-CLARIFICATION-CONFIDENCE", target, "exit confidence must be 0..100")
                )
            elif rounds and isinstance(rounds[-1], dict) and exit_confidence != rounds[-1].get("confidence"):
                findings.append(
                    finding(
                        "VDD-CLARIFICATION-CONFIDENCE",
                        target,
                        "exit confidence must match the final clarification round",
                    )
                )
            if exit_attestation.get("authority_hash") != data.get("current_authority_hash") or exit_attestation.get(
                "target_hash"
            ) != data.get("current_target_hash"):
                findings.append(
                    finding("VDD-CLARIFICATION-STALE", target, "exit is bound to stale authority or target")
                )
            draft_only = exit_attestation.get("draft_only")
            if not isinstance(draft_only, bool):
                findings.append(
                    finding("VDD-CLARIFICATION-EXIT", target, "draft_only must be boolean")
                )
            if blocker_count > 0 and (draft_only is not True or disposition != "draft_only"):
                findings.append(
                    finding(
                        "VDD-CLARIFICATION-BLOCKER",
                        target,
                        "closed state with blockers must be draft_only",
                    )
                )
            if blocker_count == 0 and disposition not in {"normal", "draft_only"}:
                findings.append(
                    finding("VDD-CLARIFICATION-EXIT", target, "invalid closed write_disposition")
                )
        if data.get("authority_hash") != data.get("current_authority_hash") or data.get(
            "target_hash"
        ) != data.get("current_target_hash"):
            findings.append(
                finding("VDD-CLARIFICATION-STALE", target, "closed state hashes are stale")
            )
    else:
        if exit_attestation is not None:
            findings.append(
                finding("VDD-CLARIFICATION-EXIT", target, "non-closed state cannot retain exit_attestation")
            )
        if disposition != "blocked":
            findings.append(
                finding(
                    "VDD-CLARIFICATION-WRITE-BOUNDARY",
                    target,
                    "non-closed state must block target writes",
                )
            )

    return sorted(findings, key=lambda item: (item["rule_id"], item["target"], item["message"]))


def validate_state_file(path: Path) -> list[dict[str, str]]:
    try:
        data = load_json(path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return [finding("VDD-CLARIFICATION-PARSE", str(path), str(exc))]
    return validate_state_data(data, str(path))


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _write_state(path: Path, data: dict[str, Any]) -> None:
    _atomic_write(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def _append_event(run_dir: Path, event: dict[str, Any]) -> None:
    path = run_dir / "events.jsonl"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    transition_id = event.get("transition_id")
    if is_non_empty_string(transition_id):
        for line_number, line in enumerate(existing.splitlines(), start=1):
            try:
                prior = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid event JSON at line {line_number}: {exc}") from exc
            if isinstance(prior, dict) and prior.get("transition_id") == transition_id:
                return
    line = json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
    _atomic_write(path, existing + line)


def _pending_transition_path(run_dir: Path) -> Path:
    return run_dir / "pending-transition.json"


def _commit_state_and_event(
    state_path: Path, state: dict[str, Any], event: dict[str, Any]
) -> None:
    transition_id = event.get("transition_id") or f"transition-{uuid.uuid4()}"
    committed_event = {**event, "transition_id": transition_id}
    pending_path = _pending_transition_path(state_path.parent)
    pending = {
        "schema_version": PENDING_TRANSITION_SCHEMA_VERSION,
        "transition_id": transition_id,
        "state": state,
        "event": committed_event,
    }
    _atomic_write(pending_path, json.dumps(pending, ensure_ascii=False, indent=2) + "\n")
    _write_state(state_path, state)
    _append_event(state_path.parent, committed_event)
    pending_path.unlink()


def _recover_pending_transition(state_path: Path) -> None:
    pending_path = _pending_transition_path(state_path.parent)
    if not pending_path.exists():
        return
    payload = load_json(pending_path)
    if not isinstance(payload, dict) or payload.get("schema_version") != PENDING_TRANSITION_SCHEMA_VERSION:
        raise ValueError(f"invalid pending transition: {pending_path}")
    state = payload.get("state")
    event = payload.get("event")
    transition_id = payload.get("transition_id")
    if not isinstance(state, dict) or not isinstance(event, dict) or not is_non_empty_string(transition_id):
        raise ValueError(f"incomplete pending transition: {pending_path}")
    if event.get("transition_id") != transition_id:
        raise ValueError(f"pending transition identity mismatch: {pending_path}")
    findings = validate_state_data(state, str(state_path))
    if findings:
        raise ValueError(json.dumps(findings, ensure_ascii=False))
    _write_state(state_path, state)
    _append_event(state_path.parent, event)
    pending_path.unlink()


@contextmanager
def _target_lock(target_root: Path):
    target_root.mkdir(parents=True, exist_ok=True)
    lock_path = target_root / ".clarification.lock"
    with lock_path.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
            os.fsync(handle.fileno())
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def _canonical_registry_target_root(project_root: Path, target_slug: str) -> Path:
    git_root = project_root / ".git"
    if git_root.is_dir():
        return git_root / "vdd-clarification-registry" / target_slug
    return project_root / ".vdd-clarification-registry" / target_slug


def _repository_root_for_state(state_path: Path, state: dict[str, Any]) -> Path:
    recorded = state.get("repository_root")
    if is_non_empty_string(recorded):
        project_root = Path(recorded).resolve()
        try:
            state_path.resolve().relative_to(project_root)
        except ValueError as exc:
            raise ValueError("state is outside its recorded repository root") from exc
        return project_root
    for ancestor in state_path.resolve().parents:
        if (ancestor / ".git").exists():
            return ancestor
    for ancestor in state_path.resolve().parents:
        if ancestor.name.casefold() == "vdd-clarifications" and ancestor.parent.name.casefold() == "logs":
            return ancestor.parent.parent
    current = Path.cwd().resolve()
    try:
        state_path.resolve().relative_to(current)
    except ValueError as exc:
        raise ValueError("legacy state has no discoverable repository root") from exc
    return current


def _registry_state_paths(project_root: Path, target_slug: str) -> set[Path]:
    registry_path = _canonical_registry_target_root(project_root, target_slug) / "registry.json"
    paths: set[Path] = set()
    registry_exists = registry_path.exists()
    if registry_exists:
        registry = load_json(registry_path)
        if not isinstance(registry, dict) or registry.get("schema_version") != REGISTRY_SCHEMA_VERSION:
            raise ValueError(f"invalid clarification target registry: {registry_path}")
        for relative in registry.get("active_states", []):
            if not is_non_empty_string(relative):
                raise ValueError(f"invalid clarification registry state path: {relative!r}")
            candidate = (project_root / relative).resolve()
            try:
                candidate.relative_to(project_root)
            except ValueError as exc:
                raise ValueError("clarification registry path escapes repository root") from exc
            paths.add(candidate)
    if not registry_exists:
        for state_path in project_root.rglob("state.json"):
            parts = {part.casefold() for part in state_path.parts}
            if "vdd-clarifications" in parts and state_path.parent.parent.name.casefold() == target_slug.casefold():
                paths.add(state_path.resolve())
    return paths


def _write_target_registry(
    project_root: Path, target: str, target_slug: str, active_paths: list[Path]
) -> None:
    registry_path = _canonical_registry_target_root(project_root, target_slug) / "registry.json"
    relative_paths = []
    for path in sorted(active_paths):
        relative_paths.append(path.resolve().relative_to(project_root).as_posix())
    payload = {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "target": target,
        "target_slug": target_slug,
        "active_states": relative_paths,
        "updated_at": now_iso(),
    }
    _atomic_write(registry_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _active_states_for_target(
    project_root: Path,
    target: str,
    target_slug: str,
    exclude: Path | None = None,
) -> list[Path]:
    active: list[Path] = []
    excluded = exclude.resolve() if exclude is not None else None
    for state_path in sorted(_registry_state_paths(project_root, target_slug)):
        if excluded is not None and state_path == excluded:
            continue
        if not state_path.exists() and _pending_transition_path(state_path.parent).exists():
            _recover_pending_transition(state_path)
        if not state_path.exists():
            continue
        try:
            state = _load_state(state_path)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"cannot inspect existing clarification state {state_path}: {exc}") from exc
        if _target_identity(str(state.get("target", ""))) != _target_identity(target):
            raise ValueError(f"clarification target registry identity mismatch: {state_path}")
        if state.get("status") == "active":
            active.append(state_path)
    _write_target_registry(project_root, target, target_slug, active)
    return active


def _locked_state_command(handler):
    @wraps(handler)
    def locked(args: argparse.Namespace) -> dict[str, Any]:
        state_path = _state_path(args.state)
        initial_state = _load_state(state_path)
        project_root = _repository_root_for_state(state_path, initial_state)
        target_slug = initial_state.get("target_slug")
        if not is_non_empty_string(target_slug):
            raise ValueError("state target_slug is required for canonical locking")
        registry_root = _canonical_registry_target_root(project_root, target_slug)
        with _target_lock(registry_root):
            _recover_pending_transition(state_path)
            state = _load_state(state_path)
            result = handler(args, state_path, state)
            _active_states_for_target(project_root, state["target"], target_slug)
            return result

    return locked


def _target_identity(target: str) -> str:
    normalized = target.replace("\\", "/").rstrip("/") or "root"
    return normalized.casefold()


def _slug_for_target(target: str) -> str:
    normalized = _target_identity(target)
    base = re.sub(r"[^a-z0-9]+", "-", Path(normalized).name.lower()).strip("-") or "target"
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:8]
    return f"{base}-{digest}"


def _state_path(value: str) -> Path:
    path = Path(value).resolve()
    path = path / "state.json" if path.is_dir() else path
    if path.name != "state.json" or "vdd-clarifications" not in {
        part.lower() for part in path.parts
    }:
        raise ValueError("state path must be a state.json under vdd-clarifications")
    return path


def _load_state(path: Path) -> dict[str, Any]:
    data = load_json(path)
    if not isinstance(data, dict):
        raise ValueError("state must be a JSON object")
    return data


def _active_state_paths(target_root: Path, exclude: Path | None = None) -> list[Path]:
    active: list[Path] = []
    excluded = exclude.resolve() if exclude is not None else None
    if not target_root.exists():
        return active
    for state_path in target_root.glob("*/state.json"):
        if excluded is not None and state_path.resolve() == excluded:
            continue
        try:
            if _load_state(state_path).get("status") == "active":
                active.append(state_path)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"cannot inspect existing clarification state {state_path}: {exc}") from exc
    return sorted(active)


def _normalize_target(project_root: Path, target: str) -> str:
    candidate = Path(target)
    resolved = candidate.resolve() if candidate.is_absolute() else (project_root / candidate).resolve()
    try:
        relative = resolved.relative_to(project_root)
    except ValueError as exc:
        raise ValueError("clarification target must stay within project root") from exc
    normalized = relative.as_posix()
    if not normalized or normalized == ".":
        raise ValueError("clarification target must not be the project root")
    return normalized


def _merge_question(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    mutable_fields = {"status", "owner", "recheck_condition"}
    for field_name in sorted((set(existing) | set(incoming)) - mutable_fields):
        if existing.get(field_name) != incoming.get(field_name):
            raise ClarificationCommandError(
                "VDD-CLARIFICATION-QUESTION-TRANSITION",
                f"stable question {existing.get('id')} cannot redefine {field_name}",
            )
    current_status = existing.get("status")
    next_status = incoming.get("status")
    if next_status not in QUESTION_STATUS_TRANSITIONS.get(current_status, set()):
        raise ClarificationCommandError(
            "VDD-CLARIFICATION-QUESTION-TRANSITION",
            f"stable question {existing.get('id')} cannot transition {current_status} -> {next_status}",
        )
    merged = dict(existing)
    merged["status"] = next_status
    for field_name in ("owner", "recheck_condition"):
        if next_status == "deferred" and field_name in incoming:
            merged[field_name] = incoming[field_name]
        elif next_status != "deferred":
            merged.pop(field_name, None)
    return merged


def command_init(args: argparse.Namespace) -> dict[str, Any]:
    project_root = Path(args.project_root).resolve()
    if args.evidence_root:
        evidence_input = Path(args.evidence_root)
        evidence_root = (
            evidence_input.resolve()
            if evidence_input.is_absolute()
            else (project_root / evidence_input).resolve()
        )
    else:
        evidence_root = project_root / "logs"
    normalized_target = _normalize_target(project_root, args.target)
    try:
        evidence_root.relative_to(project_root)
    except ValueError as exc:
        raise ValueError("clarification evidence root must stay within project root") from exc
    target_path = (project_root / normalized_target).resolve()
    if (
        evidence_root == target_path
        or evidence_root.is_relative_to(target_path)
        or target_path.is_relative_to(evidence_root)
    ):
        raise ClarificationCommandError(
            "VDD-CLARIFICATION-EVIDENCE-OVERLAP",
            "clarification evidence root and target plan must not overlap",
        )
    target_slug = _slug_for_target(normalized_target)
    run_id = args.run_id or datetime.now(timezone.utc).strftime("clarification-%Y%m%dT%H%M%SZ")
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise ValueError("run_id must contain only letters, digits, dot, underscore, or hyphen")
    target_root = evidence_root / "vdd-clarifications" / target_slug
    registry_root = _canonical_registry_target_root(project_root, target_slug)
    with _target_lock(registry_root):
        active = _active_states_for_target(project_root, normalized_target, target_slug)
        if active:
            return {
                "status": "resume_required",
                "active_states": [str(path) for path in sorted(active)],
            }
        run_dir = target_root / run_id
        state_path = run_dir / "state.json"
        if state_path.exists():
            raise ValueError(f"run already exists: {state_path}")
        timestamp = now_iso()
        state = {
            "schema_version": SCHEMA_VERSION,
            "repository_root": str(project_root),
            "run_id": run_id,
            "mode": args.mode,
            "target": normalized_target,
            "target_slug": target_slug,
            "status": "active",
            "interaction_mode": args.interaction_mode,
            "authority_hash": args.authority_hash,
            "current_authority_hash": args.authority_hash,
            "target_hash": args.target_hash,
            "current_target_hash": args.target_hash,
            "confirmed_boundaries": [],
            "non_goals": [],
            "conflicts": [],
            "open_items": [],
            "open_blocker_count": 0,
            "questions": [],
            "rounds": [],
            "exit_attestation": None,
            "write_disposition": "blocked",
            "updated_at": timestamp,
        }
        findings = validate_state_data(state, str(state_path))
        if findings:
            raise ValueError(json.dumps(findings, ensure_ascii=False))
        _write_target_registry(project_root, normalized_target, target_slug, [state_path])
        _commit_state_and_event(
            state_path,
            state,
            {"event": "initialized", "at": timestamp, "run_id": run_id},
        )
        return {"status": "initialized", "state": str(state_path)}


def _merge_unique(existing: list[str], additions: Any) -> list[str]:
    if additions is None:
        return existing
    if not isinstance(additions, list) or any(not is_non_empty_string(item) for item in additions):
        raise ValueError("boundary updates must be lists of non-empty strings")
    return existing + [item for item in additions if item not in existing]


@_locked_state_command
def command_record_round(
    args: argparse.Namespace, state_path: Path, state: dict[str, Any]
) -> dict[str, Any]:
    if state.get("status") != "active":
        raise ClarificationCommandError(
            "VDD-CLARIFICATION-STATE-TRANSITION",
            "rounds can be recorded only for an active run",
        )
    payload = load_json(Path(args.round_file).resolve())
    if not isinstance(payload, dict):
        raise ValueError("round payload must be a JSON object")
    if _sensitive_paths(payload):
        raise ValueError("round payload contains prohibited sensitive data")
    questions = payload.get("questions")
    if not isinstance(questions, list):
        raise ValueError("round payload questions must be a list")
    question_map = {item["id"]: item for item in state["questions"] if isinstance(item, dict) and "id" in item}
    question_ids: list[str] = []
    for question in questions:
        if not isinstance(question, dict) or not is_non_empty_string(question.get("id")):
            raise ValueError("each round question requires an id")
        extra_fields = sorted(set(question) - ALLOWED_QUESTION_FIELDS)
        if extra_fields:
            raise ClarificationCommandError(
                "VDD-CLARIFICATION-QUESTION-TRANSITION",
                f"question {question.get('id')} contains unsupported fields: {extra_fields}",
            )
        existing = question_map.get(question["id"])
        question_map[question["id"]] = (
            _merge_question(existing, question) if existing is not None else question
        )
        question_ids.append(question["id"])
    state["questions"] = list(question_map.values())
    round_item = {
        "round_id": payload.get("round_id"),
        "question_ids": question_ids,
        "same_level_exhausted": payload.get("same_level_exhausted", False),
        "same_level_exhausted_reason": payload.get("same_level_exhausted_reason"),
        "confidence": payload.get("confidence"),
        "blocker_count": 0,
        "dimension_scores": payload.get("dimension_scores"),
        "dimension_evidence": payload.get("dimension_evidence"),
        "recommend_exit": payload.get("recommend_exit"),
        "analysis": payload.get("analysis"),
        "user_turn_id": payload.get("user_turn_id"),
    }
    for field_name in ("confirmed_boundaries", "non_goals", "conflicts", "open_items"):
        state[field_name] = _merge_unique(state[field_name], payload.get(field_name))
    state["open_blocker_count"] = sum(
        1
        for question in state["questions"]
        if question.get("blocking") is True and question.get("status") in OPEN_BLOCKER_STATUSES
    )
    round_item["blocker_count"] = state["open_blocker_count"]
    state["rounds"].append(round_item)
    state["updated_at"] = now_iso()
    findings = validate_state_data(state, str(state_path))
    if findings:
        raise ValueError(json.dumps(findings, ensure_ascii=False))
    _commit_state_and_event(
        state_path,
        state,
        {
            "event": "round_recorded",
            "at": state["updated_at"],
            "round_id": round_item["round_id"],
            "question_ids": question_ids,
            "confidence": round_item["confidence"],
        },
    )
    return {"status": "round_recorded", "state": str(state_path)}


@_locked_state_command
def command_close(
    args: argparse.Namespace, state_path: Path, state: dict[str, Any]
) -> dict[str, Any]:
    if state.get("status") != "active":
        raise ClarificationCommandError(
            "VDD-CLARIFICATION-STATE-TRANSITION",
            "only an active run can close",
        )
    payload = load_json(Path(args.exit_file).resolve())
    if not isinstance(payload, dict):
        raise ValueError("exit payload must be a JSON object")
    if _sensitive_paths(payload):
        raise ValueError("exit payload contains prohibited sensitive data")
    state["current_authority_hash"] = payload.get("current_authority_hash")
    state["current_target_hash"] = payload.get("current_target_hash")
    draft_only = state.get("open_blocker_count", 0) > 0 or payload.get("draft_only") is True
    state["exit_attestation"] = {
        "actor": payload.get("actor"),
        "explicit_no_more_clarification": payload.get("explicit_no_more_clarification"),
        "explicit_write_permission": payload.get("explicit_write_permission"),
        "user_response_hash": payload.get("user_response_hash"),
        "user_turn_id": payload.get("user_turn_id"),
        "summary": payload.get("summary"),
        "confidence": payload.get("confidence"),
        "authority_hash": payload.get("current_authority_hash"),
        "target_hash": payload.get("current_target_hash"),
        "draft_only": draft_only,
        "closed_at": now_iso(),
    }
    state["status"] = "closed"
    state["write_disposition"] = "draft_only" if draft_only else "normal"
    state["updated_at"] = state["exit_attestation"]["closed_at"]
    findings = validate_state_data(state, str(state_path))
    if findings:
        raise ValueError(json.dumps(findings, ensure_ascii=False))
    _commit_state_and_event(
        state_path,
        state,
        {
            "event": "clarification_exit_attested",
            "at": state["updated_at"],
            "actor": state["exit_attestation"]["actor"],
            "user_response_hash": state["exit_attestation"]["user_response_hash"],
            "draft_only": draft_only,
        },
    )
    return {"status": "closed", "state": str(state_path), "write_disposition": state["write_disposition"]}


@_locked_state_command
def command_invalidate(
    args: argparse.Namespace, state_path: Path, state: dict[str, Any]
) -> dict[str, Any]:
    if state.get("status") not in INVALIDATION_SOURCE_STATUSES:
        allowed = ", ".join(sorted(INVALIDATION_SOURCE_STATUSES))
        raise ClarificationCommandError(
            "VDD-CLARIFICATION-STATE-TRANSITION",
            f"only {allowed} runs can be invalidated",
        )
    if _sensitive_paths({"reason": args.reason}):
        raise ValueError("invalidation reason contains prohibited sensitive data")
    state["status"] = "invalidated"
    state["current_authority_hash"] = args.current_authority_hash
    state["current_target_hash"] = args.current_target_hash
    state["exit_attestation"] = None
    state["write_disposition"] = "blocked"
    state["updated_at"] = now_iso()
    findings = validate_state_data(state, str(state_path))
    if findings:
        raise ValueError(json.dumps(findings, ensure_ascii=False))
    _commit_state_and_event(
        state_path,
        state,
        {"event": "invalidated", "at": state["updated_at"], "reason": args.reason},
    )
    return {"status": "invalidated", "state": str(state_path)}


@_locked_state_command
def command_reopen(
    args: argparse.Namespace, state_path: Path, state: dict[str, Any]
) -> dict[str, Any]:
    if state.get("status") != "invalidated":
        raise ClarificationCommandError(
            "VDD-CLARIFICATION-STATE-TRANSITION",
            "only an invalidated run can reopen",
        )
    project_root = _repository_root_for_state(state_path, state)
    active_siblings = _active_states_for_target(
        project_root,
        state["target"],
        state["target_slug"],
        exclude=state_path,
    )
    if active_siblings:
        raise ClarificationCommandError(
            "VDD-CLARIFICATION-ACTIVE-RUN",
            "cannot reopen while another run is active for the target: "
            + ", ".join(str(path) for path in active_siblings)
        )
    requested = set(args.question_id)
    known = {question.get("id") for question in state.get("questions", []) if isinstance(question, dict)}
    unknown = sorted(requested - known)
    if unknown:
        raise ValueError(f"cannot reopen unknown question ids: {unknown}")
    if not requested:
        raise ValueError("at least one question id is required to reopen")
    if _sensitive_paths({"reason": args.reason}):
        raise ValueError("reopen reason contains prohibited sensitive data")
    non_reopenable = sorted(
        question["id"]
        for question in state["questions"]
        if question.get("id") in requested
        and question.get("status") not in REOPENABLE_QUESTION_STATUSES
    )
    if non_reopenable:
        raise ClarificationCommandError(
            "VDD-CLARIFICATION-QUESTION-TRANSITION",
            "questions are not reopenable from their current status: " + ", ".join(non_reopenable),
        )
    for question in state["questions"]:
        if question.get("id") in requested:
            question["status"] = "reopened"
            question.pop("owner", None)
            question.pop("recheck_condition", None)
    state["open_blocker_count"] = sum(
        1
        for question in state["questions"]
        if question.get("blocking") is True and question.get("status") in OPEN_BLOCKER_STATUSES
    )
    state["authority_hash"] = state["current_authority_hash"]
    state["target_hash"] = state["current_target_hash"]
    state["status"] = "active"
    state["write_disposition"] = "blocked"
    state["updated_at"] = now_iso()
    findings = validate_state_data(state, str(state_path))
    if findings:
        raise ValueError(json.dumps(findings, ensure_ascii=False))
    _commit_state_and_event(
        state_path,
        state,
        {
            "event": "reopened",
            "at": state["updated_at"],
            "question_ids": sorted(requested),
            "reason": args.reason,
        },
    )
    return {"status": "active", "state": str(state_path), "reopened": sorted(requested)}


@_locked_state_command
def command_supersede(
    args: argparse.Namespace, state_path: Path, state: dict[str, Any]
) -> dict[str, Any]:
    if state.get("status") not in SUPERSEDE_SOURCE_STATUSES:
        allowed = ", ".join(sorted(SUPERSEDE_SOURCE_STATUSES))
        raise ClarificationCommandError(
            "VDD-CLARIFICATION-STATE-TRANSITION",
            f"only {allowed} runs can be superseded",
        )
    if args.successor_run_id == state.get("run_id"):
        raise ClarificationCommandError(
            "VDD-CLARIFICATION-STATE-TRANSITION",
            "successor run must differ from the superseded run",
        )
    state["status"] = "superseded"
    state["exit_attestation"] = None
    state["write_disposition"] = "blocked"
    state["updated_at"] = now_iso()
    findings = validate_state_data(state, str(state_path))
    if findings:
        raise ValueError(json.dumps(findings, ensure_ascii=False))
    _commit_state_and_event(
        state_path,
        state,
        {
            "event": "superseded",
            "at": state["updated_at"],
            "successor_run_id": args.successor_run_id,
        },
    )
    return {"status": "superseded", "state": str(state_path)}


def command_validate(args: argparse.Namespace) -> dict[str, Any]:
    state_path = _state_path(args.state)
    findings = validate_state_file(state_path)
    return {"schema_version": "vdd.clarification-validation.v1", "ok": not findings, "findings": findings}


def command_status(args: argparse.Namespace) -> dict[str, Any]:
    state_path = _state_path(args.state)
    state = _load_state(state_path)
    findings = validate_state_data(state, str(state_path))
    if findings:
        return {
            "schema_version": "vdd.clarification-status.v1",
            "ok": False,
            "status": "invalid_state",
            "findings": findings,
        }
    last_round = state["rounds"][-1] if state["rounds"] else None
    pending = [
        {
            "id": question["id"],
            "status": question["status"],
            "blocking": question["blocking"],
            "summary": question["summary"],
            "recommendation": question["recommendation"],
        }
        for question in state["questions"]
        if question["status"] in {"open", "deferred", "reopened"}
    ]
    if state["status"] == "closed":
        status = "clarification_complete"
    else:
        status = "clarification_required"
    return {
        "schema_version": "vdd.clarification-status.v1",
        "ok": True,
        "status": status,
        "run_id": state["run_id"],
        "state": str(state_path),
        "confidence": last_round.get("confidence") if last_round else None,
        "open_blocker_count": state["open_blocker_count"],
        "pending_questions": pending,
        "write_disposition": state["write_disposition"],
    }


def add_hash_argument(parser: argparse.ArgumentParser, name: str) -> None:
    parser.add_argument(name, required=True, type=str)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Maintain resumable VDD clarification state.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init")
    init.add_argument("--project-root", default=".")
    init.add_argument("--evidence-root")
    init.add_argument("--target", required=True)
    init.add_argument("--mode", required=True, choices=sorted(ALLOWED_MODES))
    init.add_argument("--interaction-mode", required=True, choices=sorted(ALLOWED_INTERACTION_MODES))
    init.add_argument("--run-id")
    add_hash_argument(init, "--authority-hash")
    add_hash_argument(init, "--target-hash")
    init.set_defaults(handler=command_init)

    record = subparsers.add_parser("record-round")
    record.add_argument("--state", required=True)
    record.add_argument("--round-file", required=True)
    record.set_defaults(handler=command_record_round)

    close = subparsers.add_parser("close")
    close.add_argument("--state", required=True)
    close.add_argument("--exit-file", required=True)
    close.set_defaults(handler=command_close)

    invalidate = subparsers.add_parser("invalidate")
    invalidate.add_argument("--state", required=True)
    invalidate.add_argument("--reason", required=True)
    add_hash_argument(invalidate, "--current-authority-hash")
    add_hash_argument(invalidate, "--current-target-hash")
    invalidate.set_defaults(handler=command_invalidate)

    reopen = subparsers.add_parser("reopen")
    reopen.add_argument("--state", required=True)
    reopen.add_argument("--question-id", action="append", default=[])
    reopen.add_argument("--reason", required=True)
    reopen.set_defaults(handler=command_reopen)

    supersede = subparsers.add_parser("supersede")
    supersede.add_argument("--state", required=True)
    supersede.add_argument("--successor-run-id", required=True)
    supersede.set_defaults(handler=command_supersede)

    validate = subparsers.add_parser("validate")
    validate.add_argument("--state", required=True)
    validate.set_defaults(handler=command_validate)

    status = subparsers.add_parser("status")
    status.add_argument("--state", required=True)
    status.set_defaults(handler=command_status)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = args.handler(args)
    except ClarificationCommandError as exc:
        payload = {
            "schema_version": "vdd.clarification-command.v1",
            "ok": False,
            "rule_id": exc.rule_id,
            "error": str(exc),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        payload = {
            "schema_version": "vdd.clarification-command.v1",
            "ok": False,
            "error": str(exc),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1
    if "ok" not in payload:
        payload = {"schema_version": "vdd.clarification-command.v1", "ok": True, **payload}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("ok", True) else 1


if __name__ == "__main__":
    sys.exit(main())
