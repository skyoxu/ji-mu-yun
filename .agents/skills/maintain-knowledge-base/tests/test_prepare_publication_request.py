from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prepare_publication_request.py"


def _load():
    spec = importlib.util.spec_from_file_location("prepare_publication_request", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PublicationRequestTests(unittest.TestCase):
    def test_requires_ack_and_writes_append_only_main_bound_request(self) -> None:
        module = _load()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = Path("logs/knowledge-context/publication-requests/request.json")
            route_payload = {
                "schema_version": "jimuyun.acceptance-knowledge-maintenance-route.v1",
                "status": "blocked", "failure_code": "catalog_stale",
                "next_action": "knowledge-maintenance-required", "target_plan": "execution-plans/plan",
                "snapshot": {"ref": "refs/heads/main", "commit": "a" * 40},
                "request_sha256": "sha256:" + "b" * 64, "result_sha256": "sha256:" + "c" * 64,
                "automatic_publication_allowed": False,
                "requires_explicit_maintainer_confirmation": True, "authorizes": [],
            }
            route_seed = module._canonical_hash(route_payload).removeprefix("sha256:")
            route = root / f"execution-plans/plan/knowledge-context-routes/{route_seed}.json"
            route.parent.mkdir(parents=True)
            route_payload["route_output"] = route.relative_to(root).as_posix()
            route_payload["route_sha256"] = module._canonical_hash(route_payload)
            route.write_text(json.dumps(route_payload), encoding="utf-8")
            base = [
                "prepare", "--repository-root", str(root), "--request-id", "request-1",
                "--trigger", "catalog-stale-maintenance", "--target-plan", "execution-plans/plan",
                "--output", str(output).replace("\\", "/"),
                "--source-route", str(route.relative_to(root)).replace("\\", "/"),
            ]
            with mock.patch.object(sys, "argv", base):
                with self.assertRaisesRegex(SystemExit, "explicit maintainer confirmation"):
                    module.main()
            with mock.patch.object(sys, "argv", [*base, "--ack-maintainer"]), \
                 mock.patch.object(module, "_main_commit", return_value="a" * 40), \
                 mock.patch.object(module, "_target_exists_at_main", return_value=True):
                self.assertEqual(0, module.main())
                with self.assertRaisesRegex(SystemExit, "append-only"):
                    module.main()
            request = json.loads((root / output).read_text(encoding="utf-8"))
            self.assertEqual("maintain-knowledge-base", request["caller"])
            self.assertEqual("a" * 40, request["main_commit"])
            self.assertFalse(request["automatic"])
            self.assertTrue(request["maintainer_confirmation"])
            self.assertEqual(route_payload["route_sha256"], request["source_route"]["sha256"])


if __name__ == "__main__":
    unittest.main()
