import unittest

from scripts.toolchain.canonical_evidence import canonical_bytes, domain_hash, normalize_repository_path, parse_json_strict, validate_content_identity


class CanonicalEvidenceTests(unittest.TestCase):
    def test_golden_identity_is_domain_separated(self):
        payload = {"b": [1, True], "a": "x"}
        self.assertEqual(b'{"a":"x","b":[1,true]}', canonical_bytes(payload))
        self.assertNotEqual(domain_hash("artifact.v1", payload), domain_hash("other.v1", payload))
        self.assertTrue(validate_content_identity("artifact.v1", payload, domain_hash("artifact.v1", payload)))

    def test_paths_are_lexically_normalized(self):
        self.assertEqual("a/c", normalize_repository_path("repo", "a\\b/../c"))

    def test_reject_invalid_canonical_inputs(self):
        for raw in (b'\xef\xbb\xbf{}', '{"x":1,"x":2}', '{"x":1.0}', '{"x":-0}'):
            with self.assertRaises(ValueError): parse_json_strict(raw)
        for path in ("../x", "C:/x", "/x"):
            with self.assertRaises(ValueError): normalize_repository_path("repo", path)


if __name__ == "__main__":
    unittest.main()
