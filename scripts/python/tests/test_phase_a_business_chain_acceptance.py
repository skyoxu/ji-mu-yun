from __future__ import annotations

import contextlib
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import phase_a_business_chain_acceptance as acceptance


def evidence():
    # ADR-0036/0038: fixture HTTP proves the acceptance consumer, not live model work.
    value = "a" * 64
    workflow = {"projectId": "project-a", "routeStateArtifacts": {"status": "ready", "blockingIssues": [],
        "artifacts": [{"route": route, "status": sorted(statuses)[0], "freshness": "fresh", "blockingIssueIds": []}
                      for route, statuses in acceptance.ROUTES.items()]},
        "steps": [{"id": step, "status": "done", "evidence": "db-bound machine evidence"}
                  for step in acceptance.EXECUTION_STEPS]}
    refs = [{"kind": "sidecar", "path": "meta/routes/current.json"}]
    contract = {"projectId": "project-a", "status": "fresh", "freshness": {"status": "fresh"},
                "blockingIssues": [], "evidenceRefs": refs}
    ui = {"projectId": "project-a", "status": "succeeded", "freshness": "fresh", "finalReadinessEligible": True,
          "blockingIssues": [], "evidenceRefs": refs}
    ui.update({field: value for field in acceptance.HASH_FIELDS})
    contract.update({field: value for field in acceptance.HASH_BINDINGS.values()})
    return workflow, contract, ui


class BusinessChainAcceptanceTests(unittest.TestCase):
    def test_current_complete_chain_is_accepted(self):
        self.assertEqual([], acceptance.evaluate("project-a", *evidence()))

    def test_each_missing_route_is_blocked(self):
        for route in acceptance.ROUTES:
            workflow, contract, ui = evidence()
            workflow["routeStateArtifacts"]["artifacts"] = [row for row in workflow["routeStateArtifacts"]["artifacts"] if row["route"] != route]
            self.assertIn(f"route:{route}:missing_or_duplicate", acceptance.evaluate("project-a", workflow, contract, ui))

    def test_stale_source_and_false_green_are_blocked(self):
        workflow, contract, ui = evidence()
        ui["sourceContractHash"] = "b" * 64
        ui["finalReadinessEligible"] = False
        ui["freshness"] = "stale"
        failures = acceptance.evaluate("project-a", workflow, contract, ui)
        self.assertIn("ui:sourceContractHash:source_changed", failures)
        self.assertIn("ui:final_readiness_blocked", failures)

    def test_empty_hashes_and_unbound_project_are_blocked(self):
        workflow, contract, ui = evidence()
        ui["sourceIterationSessionHash"] = ""
        contract["projectId"] = "project-b"
        failures = acceptance.evaluate("project-a", workflow, contract, ui)
        self.assertIn("ui:sourceIterationSessionHash:hash_missing_or_invalid", failures)
        self.assertIn("contract:project_binding_invalid", failures)

    def test_current_failure_overrides_earlier_pass(self):
        workflow, contract, ui = evidence()
        workflow["steps"].append({"id": "needs-fix-or-repair", "status": "fix"})
        workflow["steps"][2]["status"] = "pending"
        failures = acceptance.evaluate("project-a", workflow, contract, ui)
        self.assertIn("execution:repair_not_closed", failures)
        self.assertIn("execution:prototype-acceptance:not_complete", failures)

    def test_machine_evidence_and_duplicate_rows_are_required(self):
        workflow, contract, ui = evidence()
        workflow["routeStateArtifacts"]["artifacts"].append(copy.deepcopy(workflow["routeStateArtifacts"]["artifacts"][0]))
        ui["evidenceRefs"] = []
        failures = acceptance.evaluate("project-a", workflow, contract, ui)
        self.assertIn("route:gdd-question-form:missing_or_duplicate", failures)
        self.assertIn("ui:machine_evidence_missing", failures)

    def test_missing_credential_is_unavailable_and_never_passed(self):
        (Path(__file__).resolve().parents[3] / "logs").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[3] / "logs") as temp:
            output = Path(temp) / "unavailable.json"
            with patch.dict(os.environ, {"ACCEPTANCE_TEST_TOKEN": ""}), contextlib.redirect_stdout(io.StringIO()):
                code = acceptance.main(["--base-url", "https://example.invalid", "--project-id", "project-a",
                                        "--token-env", "ACCEPTANCE_TEST_TOKEN", "--output", str(output)])
            self.assertEqual(2, code)
            self.assertEqual("unavailable", json.loads(output.read_text(encoding="utf-8"))["status"])

    def test_relative_and_absolute_output_preserve_unavailable_exit_contract(self):
        # ADR-0038: a valid evidence path must not change the acceptance result.
        root = Path(__file__).resolve().parents[3]
        (root / "logs").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root / "logs") as temp:
            for relative in (False, True):
                with self.subTest(relative=relative):
                    output = Path(temp) / ("relative.json" if relative else "absolute.json")
                    argument = os.path.relpath(output) if relative else str(output)
                    printed = io.StringIO()
                    with patch.dict(os.environ, {"ACCEPTANCE_TEST_TOKEN": ""}), contextlib.redirect_stdout(printed):
                        code = acceptance.main(["--base-url", "https://example.invalid", "--project-id", "project-a",
                            "--token-env", "ACCEPTANCE_TEST_TOKEN", "--output", argument])
                    self.assertEqual(2, code)
                    self.assertEqual("unavailable", json.loads(output.read_text(encoding="utf-8"))["status"])
                    self.assertEqual(str(output.relative_to(root)), json.loads(printed.getvalue())["evidence"])

    def test_output_outside_logs_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as result:
                acceptance.main(["--base-url", "https://example.invalid", "--project-id", "project-a",
                                 "--output", str(Path(temp) / "outside.json")])
            self.assertEqual(2, result.exception.code)
            self.assertFalse((Path(temp) / "outside.json").exists())

    def test_authenticated_http_readback_is_read_only_and_redacted(self):
        self._http_case("ok", "passed", 0)

    def test_denied_access_is_unavailable(self):
        self._http_case("denied", "unavailable", 2)

    def test_relative_output_preserves_passed_and_blocked_results(self):
        self._http_case("ok", "passed", 0, relative_output=True)
        self._http_case("blocked", "blocked", 2, relative_output=True)

    def test_redirect_does_not_forward_the_credential(self):
        self._http_case("redirect", "unavailable", 2)

    def _http_case(self, mode, expected_status, expected_exit, relative_output=False):
        requests = []
        payloads = dict(zip(("workflow-route", "prototype-contract/status", "ui-wiring-closure/latest"), evidence()))
        if mode == "blocked":
            payloads["ui-wiring-closure/latest"]["finalReadinessEligible"] = False

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append((self.command, self.path, self.headers.get("Authorization")))
                if mode == "denied":
                    self.send_error(403)
                    return
                if mode == "redirect":
                    self.send_response(302)
                    self.send_header("Location", "/credential-trap")
                    self.end_headers()
                    return
                suffix = self.path.removeprefix("/api/projects/project-a/")
                if suffix not in payloads or self.headers.get("Authorization") != "Bearer fixture-secret":
                    self.send_error(403)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(payloads[suffix]).encode("utf-8"))

            def log_message(self, *_):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            root = Path(__file__).resolve().parents[3]
            (root / "logs").mkdir(exist_ok=True)
            with tempfile.TemporaryDirectory(dir=root / "logs") as temp:
                output = Path(temp) / "acceptance.json"
                printed = io.StringIO()
                with patch.dict(os.environ, {"ACCEPTANCE_TEST_TOKEN": "fixture-secret"}), contextlib.redirect_stdout(printed):
                    code = acceptance.main(["--base-url", f"http://127.0.0.1:{server.server_port}", "--allow-http",
                        "--project-id", "project-a", "--token-env", "ACCEPTANCE_TEST_TOKEN", "--output",
                        os.path.relpath(output) if relative_output else str(output)])
                report_text = output.read_text(encoding="utf-8")
                report = json.loads(report_text)
                self.assertEqual(expected_exit, code)
                self.assertEqual(expected_status, report["status"])
                self.assertFalse(report["routes_executed"])
                self.assertFalse(report["live_model_invoked"])
                self.assertNotIn("fixture-secret", report_text + printed.getvalue())
            self.assertEqual(3 if mode in {"ok", "blocked"} else 1, len(requests))
            self.assertTrue(all(method == "GET" and auth == "Bearer fixture-secret" for method, _, auth in requests))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
