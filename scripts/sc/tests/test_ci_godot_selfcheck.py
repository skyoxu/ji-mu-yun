"""ADR-0005 runtime gate must reject missing critical autoloads."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'python'))
import godot_selfcheck


class GodotSelfcheckTests(unittest.TestCase):
    def healthy(self):
        return {'ports': {name: True for name in godot_selfcheck.CRITICAL_PORTS}}

    def test_all_required_ports_ready_passes(self):
        result = godot_selfcheck.validate_selfcheck_result(self.healthy(), 0)
        self.assertEqual('ok', result['status'])
        self.assertEqual(6, result['ports_ok'])

    def test_zero_ready_ports_cannot_pass_as_observed_in_run_36864053647(self):
        data = {'ports': {name: False for name in godot_selfcheck.CRITICAL_PORTS}}
        result = godot_selfcheck.validate_selfcheck_result(data, 0)
        self.assertEqual('fail', result['status'])
        self.assertEqual(0, result['ports_ok'])

    def test_each_missing_or_false_required_port_fails(self):
        for name in godot_selfcheck.CRITICAL_PORTS:
            for value in (False, None, 'true', 1):
                with self.subTest(name=name, value=value):
                    data = self.healthy()
                    data['ports'][name] = value
                    self.assertEqual('fail', godot_selfcheck.validate_selfcheck_result(data, 0)['status'])
            data = self.healthy()
            del data['ports'][name]
            self.assertEqual('fail', godot_selfcheck.validate_selfcheck_result(data, 0)['status'])

    def test_missing_or_malformed_port_map_fails(self):
        for data in (None, [], {}, {'ports': []}):
            with self.subTest(data=data):
                self.assertEqual('fail', godot_selfcheck.validate_selfcheck_result(data, 0)['status'])

    def test_nonzero_exit_or_reported_error_fails_despite_ready_ports(self):
        self.assertEqual('fail', godot_selfcheck.validate_selfcheck_result(self.healthy(), 124)['status'])
        data = self.healthy()
        data['error'] = 'CompositionRoot not found (autoload not configured)'
        self.assertEqual('fail', godot_selfcheck.validate_selfcheck_result(data, 0)['status'])

    def test_best_effort_ui_probe_does_not_change_critical_port_gate(self):
        data = self.healthy()
        data['ui'] = {'main': False, 'error': 'best effort'}
        self.assertEqual('ok', godot_selfcheck.validate_selfcheck_result(data, 0)['status'])


if __name__ == '__main__':
    unittest.main()
