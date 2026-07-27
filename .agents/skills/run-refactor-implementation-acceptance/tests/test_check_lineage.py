from __future__ import annotations

import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))


class CheckLineageTests(unittest.TestCase):
    def _check(self, module, namespace: str, source_key: str, state: str = "active") -> dict:
        return {"checkId": module.stable_check_id(namespace, "plan.md", source_key, source_key), "sourcePath": "plan.md", "sourceKey": source_key, "semanticKey": source_key, "state": state}

    def test_retired_check_requires_a_tombstone_lineage_event(self) -> None:
        import check_lineage
        from acceptance_core import InputError

        retired = self._check(check_lineage, "CHK", "old", "retired")
        with self.assertRaisesRegex(InputError, "tombstone"):
            check_lineage.validate_check_id_lineage({"schemaVersion": "check-id-lineage.v1", "checks": [retired], "events": [], "authorizes": []})

    def test_split_preserves_retired_predecessor_and_active_successors(self) -> None:
        import check_lineage

        old = self._check(check_lineage, "CHK", "old", "retired")
        left = self._check(check_lineage, "CHK", "left")
        right = self._check(check_lineage, "CHK", "right")
        value = {"schemaVersion": "check-id-lineage.v1", "checks": [old, left, right], "events": [{"eventId": "split-old", "kind": "split", "fromCheckIds": [old["checkId"]], "toCheckIds": [left["checkId"], right["checkId"]], "reason": "atomic split"}], "authorizes": []}
        self.assertEqual({left["checkId"], right["checkId"]}, check_lineage.active_check_ids(value))


if __name__ == "__main__":
    unittest.main()
