import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[4]
MODULE_PATH = ROOT / ".agents/skills/run-phase-bootstrap-review/scripts/runtime_policy.py"
SPEC = importlib.util.spec_from_file_location("runtime_policy", MODULE_PATH)
RUNTIME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNTIME)
sys.path.insert(0, str(MODULE_PATH.parent))
import bootstrap_review


IDENTITY = {"candidate": "sha256:candidate", "closure": "sha256:closure", "segment": "sha256:segment", "attempt": "attempt-1"}
POLICY = {"schema_version": "bootstrap-runtime-policy.v1", "liveness_seconds": 10, "effective_progress_seconds": 60, "no_progress_seconds": 60, "launch_grace_seconds": 5, "terminal_grace_seconds": 5, "lease_seconds": 60, "retry_limits": {"transport": 2}, "backoff_seconds": 1, "status_throttle_seconds": 5, "output_max_bytes": 12000, "authorizes": []}


class RuntimePolicyEventsTests(unittest.TestCase):
    def test_reject_heartbeat_stdout_and_poll_as_effective_progress(self):
        for kind in ("heartbeat", "stdout", "poll"):
            with self.assertRaises(ValueError):
                RUNTIME.validate_effective_progress({**IDENTITY, "kind": kind}, IDENTITY)

    def test_accepts_identity_bound_evidence_increment(self):
        event = {**IDENTITY, "kind": "evidence_increment", "evidence_hash": "sha256:new"}
        self.assertTrue(RUNTIME.validate_effective_progress(event, IDENTITY))

    def test_watchdog_stops_after_only_effective_progress_window(self):
        self.assertEqual("active", RUNTIME.watchdog_state(POLICY, 100, 159))
        self.assertEqual("no-progress-stop", RUNTIME.watchdog_state(POLICY, 100, 160))

    def test_lease_requires_live_matching_process_identity(self):
        events = [
            {"kind": "attempt_started", "attempt": "attempt-1", "timestamp": 100, "write_set": ["x"], "process": {"pid": 7, "created": "a"}},
            {"kind": "attempt_terminal", "attempt": "attempt-2", "timestamp": 100, "write_set": ["y"], "process": {"pid": 8, "created": "b"}},
        ]
        live = {7: "a", 8: "reused"}
        lease = RUNTIME.reconcile_leases(events, live, now=105, policy=POLICY)
        self.assertEqual(["x"], lease["occupied_write_set"])
        self.assertEqual(["attempt-2"], lease["stale_attempts"])

    def test_lease_requires_liveness_and_effective_progress_independently(self):
        started = {"kind": "attempt_started", "attempt": "attempt-1", "timestamp": 100, "write_set": ["x"], "process": {"pid": 7, "created": "a"}}
        live = {7: "a"}
        self.assertEqual([], RUNTIME.reconcile_leases([started], live, now=111, policy=POLICY)["occupied_write_set"])
        heartbeat = {"kind": "heartbeat", "attempt": "attempt-1", "timestamp": 155}
        self.assertEqual([], RUNTIME.reconcile_leases([started, heartbeat], live, now=161, policy=POLICY)["occupied_write_set"])
        progress = {"kind": "effective_progress", "attempt": "attempt-1", "timestamp": 155, "identity": IDENTITY, "progress": {**IDENTITY, "kind": "evidence_increment", "evidence_hash": "sha256:new"}}
        self.assertEqual(["x"], RUNTIME.reconcile_leases([started, heartbeat, progress], live, now=161, policy=POLICY)["occupied_write_set"])

    def test_rejects_incomplete_runtime_policy(self):
        with self.assertRaises(ValueError):
            RUNTIME.validate_runtime_policy({"schema_version": "bootstrap-runtime-policy.v1", "authorizes": []})

    def test_bootstrap_event_adapter_expires_liveness_without_expiring_progress(self):
        identity = {**IDENTITY, "attempt": "attempt-1"}
        events = [
            {"eventType": "attempt-started", "attemptId": "attempt-1", "timestamp": _iso(100), "pid": 7, "processIdentity": "a", "writeSet": ["x"]},
            {"eventType": "attempt-heartbeat", "attemptId": "attempt-1", "timestamp": _iso(100)},
            {"eventType": "attempt-effective-progress", "attemptId": "attempt-1", "timestamp": _iso(155), "effectiveProgressIdentity": identity, "effectiveProgress": {**identity, "kind": "evidence_increment", "evidence_hash": "sha256:new"}},
        ]
        lease = bootstrap_review.reconcile_runtime_leases(events, policy=POLICY, now=161, live_processes={7: "a"})
        self.assertEqual([], lease["occupied_write_set"])
        self.assertEqual(["attempt-1"], lease["stale_attempts"])

    def test_bootstrap_event_adapter_expires_progress_without_expiring_liveness(self):
        identity = {**IDENTITY, "attempt": "attempt-1"}
        events = [
            {"eventType": "attempt-started", "attemptId": "attempt-1", "timestamp": _iso(100), "pid": 7, "processIdentity": "a", "writeSet": ["x"]},
            {"eventType": "attempt-effective-progress", "attemptId": "attempt-1", "timestamp": _iso(100), "effectiveProgressIdentity": identity, "effectiveProgress": {**identity, "kind": "evidence_increment", "evidence_hash": "sha256:new"}},
            {"eventType": "attempt-heartbeat", "attemptId": "attempt-1", "timestamp": _iso(155)},
        ]
        lease = bootstrap_review.reconcile_runtime_leases(events, policy=POLICY, now=161, live_processes={7: "a"})
        self.assertEqual([], lease["occupied_write_set"])
        self.assertEqual(["attempt-1"], lease["stale_attempts"])

    def test_retry_is_transport_only_bounded_and_targets_failed_segment(self):
        self.assertEqual("retry", RUNTIME.retry_decision(POLICY, "transport", 1, "segment-2", {"segment-2"}))
        self.assertEqual("blocked", RUNTIME.retry_decision(POLICY, "transport", 2, "segment-2", {"segment-2"}))
        self.assertEqual("blocked", RUNTIME.retry_decision(POLICY, "semantic", 1, "segment-2", {"segment-2"}))
        self.assertEqual("blocked", RUNTIME.retry_decision(POLICY, "transport", 1, "segment-1", {"segment-2"}))


def _iso(seconds: int) -> str:
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat().replace("+00:00", "Z")
