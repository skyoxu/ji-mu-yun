#!/usr/bin/env python3
from __future__ import annotations

import unittest

from scripts.python.tests.prototype_workflow_router_test_support import load_module

class PrototypeWorkflowRouterDevCliEntrypointTests(unittest.TestCase):
    def test_dev_cli_should_expose_prototype_workflow_entry(self) -> None:
        builders = load_module("dev_cli_builders_module_for_proto_workflow", "scripts/python/dev_cli_builders.py")
        dev_cli = load_module("dev_cli_module_for_proto_workflow", "scripts/python/dev_cli.py")
        parser = dev_cli.build_parser()
        args = parser.parse_args(["run-prototype-workflow", "--prototype-file", "docs/prototypes/sample.md"])
        cmd = builders.build_run_prototype_workflow_cmd(args)

        self.assertEqual("run-prototype-workflow", args.cmd)
        self.assertIn("scripts/python/run_prototype_workflow.py", cmd)
        self.assertIn("docs/prototypes/sample.md", cmd)

    def test_dev_cli_should_expose_phase_a_prototype_real_e2e_entry(self) -> None:
        builders = load_module("dev_cli_builders_module_for_phase_a_prototype_real_e2e", "scripts/python/dev_cli_builders.py")
        dev_cli = load_module("dev_cli_module_for_phase_a_prototype_real_e2e", "scripts/python/dev_cli.py")
        parser = dev_cli.build_parser()
        args = parser.parse_args(
            [
                "phase-a-prototype-real-e2e",
                "--repository-root",
                "C:/jimuyun",
                "--timeout-seconds",
                "1800",
                "--stop-after-day",
                "7",
            ]
        )
        cmd = builders.build_phase_a_prototype_real_e2e_cmd(args)

        self.assertEqual("phase-a-prototype-real-e2e", args.cmd)
        self.assertIn("scripts/python/phase_a_prototype_e2e_real.py", cmd)
        self.assertIn("C:/jimuyun", cmd)
        self.assertIn("1800", cmd)
        self.assertIn("7", cmd)


if __name__ == "__main__":
    unittest.main()
