import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from validate_fastctx_summary import SummaryValidationError, validate_payload


def complete_summary():
    return {
        "schema_version": "fastctx-summary.v1",
        "status": "complete",
        "source": {"path": "input.jsonl", "kind": "jsonl", "sha256": "sha256:" + "a" * 64},
        "query": {"pattern": "error"},
        "stats": {"records": 1, "bytes": 10, "max_input_tokens": 20},
        "findings": [],
        "offsets": [],
        "truncated": False,
        "omitted_records": 0,
        "generated_at": "2026-08-11T00:00:00Z",
        "errors": [],
    }


class FastCtxSummaryValidationTests(unittest.TestCase):
    def test_complete_summary_is_valid(self):
        validate_payload(complete_summary())

    def test_complete_summary_cannot_claim_truncation(self):
        payload = complete_summary()
        payload["truncated"] = True
        with self.assertRaises(SummaryValidationError):
            validate_payload(payload)

    def test_partial_summary_requires_offset(self):
        payload = complete_summary()
        payload.update({"status": "partial", "truncated": True})
        with self.assertRaises(SummaryValidationError):
            validate_payload(payload)

    def test_failed_summary_requires_error(self):
        payload = complete_summary()
        payload.update({"status": "failed"})
        with self.assertRaises(SummaryValidationError):
            validate_payload(payload)

    def test_unknown_property_is_rejected_without_jsonschema(self):
        payload = complete_summary()
        payload["unexpected"] = True
        with self.assertRaises(SummaryValidationError):
            validate_payload(payload)

    def test_invalid_offset_shape_is_rejected(self):
        payload = complete_summary()
        payload.update({"status": "partial", "truncated": True, "offsets": [{"next": 3}]})
        with self.assertRaises(SummaryValidationError):
            validate_payload(payload)

    def test_findings_unknown_fields_are_rejected(self):
        payload = complete_summary()
        payload["findings"] = [{"line": 1, "kind": "match", "raw": "secret"}]
        with self.assertRaises(SummaryValidationError):
            validate_payload(payload)

    def test_findings_unredacted_credentials_are_rejected(self):
        payload = complete_summary()
        payload["findings"] = [{"line": 1, "kind": "match", "sample": "Bearer abc.def.ghi"}]
        with self.assertRaises(SummaryValidationError):
            validate_payload(payload)

    def test_oversized_serialized_summary_is_rejected(self):
        payload = complete_summary()
        payload["query"] = {"details": "x" * 13000}
        with self.assertRaises(SummaryValidationError):
            validate_payload(payload)

    def test_failed_summary_errors_cannot_contain_credentials(self):
        payload = complete_summary()
        payload.update({"status": "failed", "errors": ["Authorization: Bearer abc.def.ghi"]})
        with self.assertRaises(SummaryValidationError):
            validate_payload(payload)


if __name__ == "__main__":
    unittest.main()
