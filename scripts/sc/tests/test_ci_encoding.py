"""Tracked-source and immutable capture regressions (ADR-0005)."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "python"))
import check_encoding


class CiEncodingTests(unittest.TestCase):
    def make_capture(self, root):
        source = root / "execution-plans/sample/capture.raw.txt"
        source.parent.mkdir(parents=True)
        source.write_bytes("fixture output \u4e2d\u6587\r\n".encode("utf-16"))
        normalized = root / "logs/evidence/capture.utf8.txt"
        normalized.parent.mkdir(parents=True)
        normalized.write_bytes(source.read_bytes().decode("utf-16").replace("\r\n", "\n").encode("utf-8"))
        row = {
            "source_path": source.relative_to(root).as_posix(),
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "source_encoding": "utf-16",
            "normalized_path": normalized.relative_to(root).as_posix(),
        }
        manifest = root / "manifest.json"
        manifest.write_text(
            json.dumps({"schema": "encoding-raw-evidence.v1", "entries": [row]}),
            encoding="utf-8",
        )
        return source, normalized, manifest, row

    def test_binary_probe_is_not_misclassified_as_small_text(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stdout.bin"
            path.write_bytes(b"\xff\x00\x01")
            self.assertFalse(check_encoding.is_text_file(str(path)))

    def test_active_utf16_text_remains_a_utf8_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "active.md"
            path.write_bytes("active source".encode("utf-16"))
            self.assertTrue(check_encoding.is_text_file(str(path)))
            self.assertFalse(check_encoding.check_utf8(str(path))["utf8_ok"])

    def test_raw_capture_is_classified_only_with_an_exact_utf8_sidecar(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, _, manifest, row = self.make_capture(root)
            before = source.read_bytes()
            captures, errors = check_encoding.validate_raw_evidence(root, manifest)
            self.assertEqual([], errors)
            self.assertEqual(row, captures[str(source.resolve())])
            self.assertEqual(before, source.read_bytes())
            self.assertFalse(check_encoding.check_utf8(str(source))["utf8_ok"])

    def test_changed_raw_hash_cannot_keep_an_exemption(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, _, manifest, _ = self.make_capture(root)
            source.write_bytes("modified capture".encode("utf-16"))
            captures, errors = check_encoding.validate_raw_evidence(root, manifest)
            self.assertEqual({}, captures)
            self.assertIn("hash changed", errors[0]["error"])

    def test_stale_or_modified_sidecar_fails_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, normalized, manifest, _ = self.make_capture(root)
            normalized.write_text("unrelated success", encoding="utf-8")
            captures, errors = check_encoding.validate_raw_evidence(root, manifest)
            self.assertEqual({}, captures)
            self.assertIn("does not match", errors[0]["error"])

    def test_active_source_cannot_be_declared_as_historical_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, _, manifest, row = self.make_capture(root)
            active = root / "active.md"
            source.rename(active)
            row["source_path"] = "active.md"
            manifest.write_text(
                json.dumps({"schema": "encoding-raw-evidence.v1", "entries": [row]}),
                encoding="utf-8",
            )
            captures, errors = check_encoding.validate_raw_evidence(root, manifest)
            self.assertEqual({}, captures)
            self.assertIn("Only historical terminal captures", errors[0]["error"])

    def test_older_commit_date_does_not_produce_an_empty_source_scan(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.cs"
            source.write_text("class Source {}\n", encoding="utf-8")
            subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(root), "add", "source.cs"], check=True)
            environment = dict(
                os.environ, GIT_AUTHOR_DATE="2000-01-01T00:00:00+00:00",
                GIT_COMMITTER_DATE="2000-01-01T00:00:00+00:00",
            )
            subprocess.run(
                ["git", "-C", str(root), "-c", "user.name=fixture",
                 "-c", "user.email=fixture@example.invalid", "commit", "-m", "old fixture"],
                env=environment, check=True, capture_output=True,
            )
            self.assertEqual([str(source)], check_encoding.git_tracked_files(root))


if __name__ == "__main__":
    unittest.main()
