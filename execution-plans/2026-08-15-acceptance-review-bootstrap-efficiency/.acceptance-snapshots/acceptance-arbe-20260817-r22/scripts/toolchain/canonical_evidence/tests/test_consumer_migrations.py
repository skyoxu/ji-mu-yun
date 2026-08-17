import importlib.util
from pathlib import Path
import unittest

from scripts.toolchain.canonical_evidence import canonical_bytes, domain_hash


ROOT = Path(__file__).resolve().parents[4]


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CoreConsumerMigrationTests(unittest.TestCase):
    def test_bmad_spec_uses_the_shared_canonical_primitive(self):
        module = load("canonical_package", ".agents/skills/bmad-spec/scripts/canonical_package.py")
        self.assertIs(canonical_bytes, module.canonical_bytes)
        self.assertEqual(
            domain_hash("jimuyun.canonical-spec-package.descriptor.v1", {"id": "x"}),
            module.domain_hash("jimuyun.canonical-spec-package.descriptor.v1", {"id": "x"}),
        )

    def test_vdd_source_freeze_uses_the_shared_canonical_primitive(self):
        module = load("source_freeze", ".agents/skills/vdd-execution-plan/scripts/source_freeze.py")
        self.assertIs(canonical_bytes, module.canonical_bytes)
        self.assertEqual(domain_hash(module.HASH_DOMAIN, {"id": "x"}), module.domain_hash({"id": "x"}))

    def test_exact_cover_uses_the_shared_canonical_primitive(self):
        module = load("conformance", ".agents/skills/vdd-conformance-exact-cover/scripts/conformance.py")
        self.assertIs(canonical_bytes, module.canonical_bytes)
        self.assertEqual(
            domain_hash("jimuyun.vdd-exact-cover.run_aggregate_fingerprint.v1", {"id": "x"}),
            module.domain_hash("run_aggregate_fingerprint", {"id": "x"}),
        )

    def test_acceptance_and_bootstrap_use_the_shared_canonical_bytes(self):
        acceptance = load("acceptance_core", ".agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_core.py")
        bootstrap = load("bootstrap_review", ".agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py")
        self.assertIs(canonical_bytes, acceptance.canonical_bytes)
        self.assertIs(canonical_bytes, bootstrap.canonical_bytes)

    def test_quick_dev_production_composer_no_longer_imports_a_plan_directory(self):
        source = (ROOT / ".agents/skills/quick-dev-tdd-adapter/tools/stage_artifact_composer.py").read_text(encoding="utf-8")
        self.assertNotIn("execution-plans/2026-07-15-repository-maintenance-tdd-adapter", source)


if __name__ == "__main__":
    unittest.main()
