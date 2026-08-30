import os
from pathlib import Path
import sys
import unittest
from unittest import mock

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from governance_policy import resolve_governance_policy


class GovernancePolicyTests(unittest.TestCase):
    def test_default_is_development_with_governance_disabled(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            policy = resolve_governance_policy()

        self.assertEqual("development", policy["phase_service_state"])
        self.assertEqual("auto", policy["mode"])
        self.assertFalse(policy["enabled"])
        self.assertEqual("phase-service-state", policy["source"])

    def test_auto_enables_governance_for_test_and_production(self) -> None:
        for state in ("test", "production"):
            with self.subTest(state=state):
                policy = resolve_governance_policy(
                    environment={"PHASEA_SERVICE_STATE": state}
                )
                self.assertTrue(policy["enabled"])

    def test_parameter_overrides_phase_service_state(self) -> None:
        enabled = resolve_governance_policy(
            "on", environment={"PHASEA_SERVICE_STATE": "development"}
        )
        disabled = resolve_governance_policy(
            "off", environment={"PHASEA_SERVICE_STATE": "production"}
        )

        self.assertTrue(enabled["enabled"])
        self.assertFalse(disabled["enabled"])
        self.assertEqual("parameter", enabled["source"])
        self.assertEqual("parameter", disabled["source"])

    def test_environment_mode_overrides_phase_service_state(self) -> None:
        policy = resolve_governance_policy(
            environment={
                "PHASEA_SERVICE_STATE": "development",
                "JIMUYUN_GOVERNANCE_MODE": "on",
            }
        )

        self.assertTrue(policy["enabled"])
        self.assertEqual("environment", policy["source"])

    def test_invalid_values_fail_closed(self) -> None:
        with self.assertRaises(ValueError):
            resolve_governance_policy(environment={"PHASEA_SERVICE_STATE": "staging"})
        with self.assertRaises(ValueError):
            resolve_governance_policy("sometimes")


if __name__ == "__main__":
    unittest.main()
