"""ADR-0041: test plan repair/projection integrity, not product completion."""
import copy
import json
import unittest

import repair_plan as repair


class ReviewRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = json.loads((repair.HERE / "before/semantic-plan-bundle.v1.json").read_text(encoding="utf-8"))
        cls.repaired = repair.repaired_bundle(cls.original)

    def test_unreviewed_baseline_is_rejected(self):
        changed = copy.deepcopy(self.original)
        changed["plan_id"] = "unreviewed"
        with self.assertRaisesRegex(ValueError, "not the reviewed"):
            repair.repaired_bundle(changed)

    def test_only_two_obligations_and_slices_change(self):
        for field, key, allowed in (("obligations", "obligation_id", {repair.AUTH, repair.REPLAY}), ("slices", "slice_id", {"S14", "S19"})):
            before = {v[key]: v for v in self.original[field]}
            after = {v[key]: v for v in self.repaired[field]}
            self.assertEqual(set(before), set(after))
            self.assertEqual({k for k in before if before[k] != after[k]}, allowed)
        self.assertEqual(self.original["slices"][24], self.repaired["slices"][24])

    def test_graph_and_routing_reject_projection_loss(self):
        repair.validate(self.repaired)
        broken = copy.deepcopy(self.repaired)
        broken["final_plan_coverage"].pop()
        with self.assertRaises(ValueError):
            repair.validate(broken)
        broken = copy.deepcopy(self.repaired)
        broken["behavior_routing"]["intents"].pop()
        with self.assertRaises(ValueError):
            repair.validate(broken)

    def test_old_acceptance_and_failure_ids_cannot_survive(self):
        changed_aids = {a["acceptance_id"] for a in self.original["acceptances"] if set(a["obligation_ids"]) & {repair.AUTH, repair.REPLAY}}
        changed_fids = {f["failure_intent_id"] for f in self.original["failure_intents"] if set(f["acceptance_ids"]) & changed_aids}
        text = json.dumps(self.repaired)
        for old in changed_aids | changed_fids:
            self.assertNotIn(old, text)
        for a in self.repaired["acceptances"]:
            if set(a["obligation_ids"]) & {repair.AUTH, repair.REPLAY}:
                self.assertEqual(a["acceptance_id"], repair.stable_id("A-", a, ("obligation_ids", "given", "when", "then", "oracle", "assertion_ids")))

    def test_new_acceptances_have_independent_positive_and_negative_assertions(self):
        by_oid = {o: a for a in self.repaired["acceptances"] for o in a["obligation_ids"]}
        self.assertTrue({"AO-17a-empty-array-control", "AO-17a-any-nonempty-rejected", "AO-17a-missing-malformed-rejected"} <= set(by_oid[repair.AUTH]["assertion_ids"]))
        self.assertTrue({"AO-09e-original-bytes-reconstructed", "AO-09e-same-identity-real-replay", "AO-09e-mismatch-missing-no-launch", "AO-09e-no-output-reuse"} <= set(by_oid[repair.REPLAY]["assertion_ids"]))
        self.assertNotEqual(repair.digest(self.original), repair.digest(self.repaired))

    def test_protected_paths_are_not_added_and_generation_is_deterministic(self):
        for s in self.repaired["slices"]:
            for path in s["production_owners"] + s["allowed_write_paths"]:
                self.assertFalse(path.startswith(("PhaseA.Platform", "runtime/phase-a", "_bmad/", ".agents/skills/bmad-", ".agents/skills/gds-")))
        self.assertEqual(self.repaired, repair.repaired_bundle(self.original))
        state = json.loads((repair.PLAN / "compiler-state.v1.json").read_text(encoding="utf-8"))
        self.assertEqual(state["state"], "repair-vdd")
        self.assertEqual(state["authorizes"], [])
        self.assertEqual(state["semantic_plan_sha256"], repair.digest(self.repaired))


if __name__ == "__main__":
    unittest.main()
