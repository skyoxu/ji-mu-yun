"""Canonical Q8 runtime closure predicate."""
from __future__ import annotations
from typing import Any, Iterable, Mapping, Sequence
from runtime_evidence import HASH_RE, STAGES


def validate_runtime_closure(tuples: Sequence[Mapping[str, Any]], expected_keys: Iterable[str], snapshot_sha: str) -> tuple[bool, list[str]]:
    findings: list[str] = []
    expected = set(expected_keys)
    actual: list[str] = []
    nonterminal_selector: dict[tuple[str, str], str] = {}
    for index, item in enumerate(tuples):
        key = item.get("tuple_key")
        canonical = f"{item.get('slice_id')}|{item.get('acceptance_id')}|{item.get('stage')}"
        if key != canonical: findings.append(f"tuple[{index}]:tuple-key-mismatch")
        stage = item.get("stage")
        if stage not in (*STAGES, "regression"): findings.append(f"tuple[{index}]:stage-invalid")
        if not HASH_RE.fullmatch(str(item.get("runtime_edge_sha256", ""))): findings.append(f"tuple[{index}]:edge-hash")
        if item.get("current_snapshot_sha256") != snapshot_sha: findings.append(f"tuple[{index}]:snapshot")
        selector = item.get("selector_identity")
        if not isinstance(selector, str) or not selector: findings.append(f"tuple[{index}]:selector")
        elif stage != "terminal":
            pair = (str(item.get("slice_id")), str(item.get("acceptance_id")))
            if pair in nonterminal_selector and nonterminal_selector[pair] != selector: findings.append(f"tuple[{index}]:selector-drift")
            else: nonterminal_selector[pair] = selector
        if isinstance(key, str): actual.append(key)
    if len(actual) != len(set(actual)): findings.append("tuple-key-duplicate")
    if set(actual) != expected: findings.append("tuple-key-set-mismatch")
    if len(actual) != len(expected): findings.append("tuple-cardinality-mismatch")
    return not findings, findings
