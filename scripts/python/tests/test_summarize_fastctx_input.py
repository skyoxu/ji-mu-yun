import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from summarize_fastctx_input import summarize
from validate_fastctx_summary import validate_payload


class FastCtxInputSummaryTests(unittest.TestCase):
    def test_complete_jsonl_summary_is_bounded_and_valid(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "input.jsonl"
            source.write_text('{"status":"ok"}\n{"status":"error","token":"secret-value"}\n', encoding="utf-8")
            payload = summarize(source, kind="jsonl", pattern="error", max_findings=10, max_summary_bytes=12000)
            validate_payload(payload)
            self.assertEqual("complete", payload["status"])
            self.assertIn("<redacted>", payload["findings"][0]["sample"])

    def test_summary_overflow_is_partial_with_offset(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "events.log"
            source.write_text("".join("error " + ("x" * 200) + "\n" for _ in range(100)), encoding="utf-8")
            payload = summarize(source, kind="log", pattern="error", max_findings=100, max_summary_bytes=1000)
            validate_payload(payload)
            self.assertEqual("partial", payload["status"])
            self.assertTrue(payload["offsets"])
            self.assertGreater(payload["omitted_records"], 0)
            serialized = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            self.assertLessEqual(len(serialized), 1000)

    def test_partial_offset_is_first_omitted_line(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "events.log"
            source.write_text("".join(f"error line-{index} " + ("x" * 200) + "\n" for index in range(1, 30)), encoding="utf-8")
            payload = summarize(source, kind="log", pattern="error", max_findings=200, max_summary_bytes=1000)
            self.assertEqual(2, payload["offsets"][0]["next"])
            self.assertEqual(28, payload["omitted_records"])

    def test_bearer_token_is_not_left_in_sample(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "events.log"
            bearer = "eyJhbGciOiJIUzI1NiJ9.secret.payload"
            source.write_text(f"Authorization: Bearer {bearer}\n", encoding="utf-8")
            payload = summarize(source, kind="log", pattern="Authorization", max_findings=10, max_summary_bytes=12000)
            self.assertNotIn(bearer, payload["findings"][0]["sample"])
            self.assertIn("<redacted>", payload["findings"][0]["sample"])

    def test_multiword_secret_is_redacted_as_one_value(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "events.log"
            source.write_text('password: "correct horse battery staple"\n', encoding="utf-8")
            payload = summarize(source, kind="log", pattern="password", max_findings=10, max_summary_bytes=12000)
            sample = payload["findings"][0]["sample"]
            self.assertEqual("password=<redacted>", sample)

    def test_invalid_utf8_fails_without_raw_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "broken.log"
            source.write_bytes(b"ok\n\xff\n")
            payload = summarize(source, kind="log", pattern="error", max_findings=10, max_summary_bytes=12000)
            validate_payload(payload)
            self.assertEqual("failed", payload["status"])
            self.assertTrue(payload["errors"])


if __name__ == "__main__":
    unittest.main()
