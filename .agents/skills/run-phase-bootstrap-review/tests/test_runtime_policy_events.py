import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[4]
MODULE_PATH = ROOT / ".agents/skills/run-phase-bootstrap-review/scripts/runtime_policy.py"
SPEC = importlib.util.spec_from_file_location("runtime_policy", MODULE_PATH)
RUNTIME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNTIME)


IDENTITY = {"candidate": "sha256:candidate", "closure": "sha256:closure", "segment": "sha256:segment", "attempt": "attempt-1"}
POLICY = {"schema_version": "bootstrap-runtime-policy.v1", "no_progress_seconds": 60, "retry_limits": {"transport": 2}, "authorizes": []}


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
            {"kind": "attempt_started", "attempt": "attempt-1", "write_set": ["x"], "process": {"pid": 7, "created": "a"}},
            {"kind": "attempt_terminal", "attempt": "attempt-2", "write_set": ["y"], "process": {"pid": 8, "created": "b"}},
        ]
        live = {7: "a", 8: "reused"}
        lease = RUNTIME.reconcile_leases(events, live)
        self.assertEqual(["x"], lease["occupied_write_set"])
        self.assertEqual(["attempt-2"], lease["stale_attempts"])

    def test_retry_is_transport_only_bounded_and_targets_failed_segment(self):
        self.assertEqual("retry", RUNTIME.retry_decision(POLICY, "transport", 1, "segment-2", {"segment-2"}))
        self.assertEqual("blocked", RUNTIME.retry_decision(POLICY, "transport", 2, "segment-2", {"segment-2"}))
        self.assertEqual("blocked", RUNTIME.retry_decision(POLICY, "semantic", 1, "segment-2", {"segment-2"}))
        self.assertEqual("blocked", RUNTIME.retry_decision(POLICY, "transport", 1, "segment-1", {"segment-2"}))
