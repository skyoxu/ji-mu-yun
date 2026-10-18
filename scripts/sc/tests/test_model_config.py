from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

SC_ROOT = Path(__file__).resolve().parents[1]
if str(SC_ROOT) not in sys.path:
    sys.path.insert(0, str(SC_ROOT))

import model_config


class ModelConfigTests(unittest.TestCase):
    def test_adjacent_model_file_takes_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "model-routing.toml").write_text('model = "o4-mini"\n', encoding="utf-8")
            (root / "config.toml").write_text('model = "fallback-model"\n', encoding="utf-8")
            self.assertEqual("o4-mini", model_config.load_model(codex_dir=root))

    def test_non_gpt_model_id_is_valid(self) -> None:
        self.assertTrue(model_config.is_valid_model_id("o4-mini"))

    def test_missing_adjacent_model_file_falls_back_to_config_toml(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "config.toml").write_text('model = "gpt-6.1-sol"\n', encoding="utf-8")
            self.assertEqual("gpt-6.1-sol", model_config.load_model(codex_dir=root))


if __name__ == "__main__":
    unittest.main()
