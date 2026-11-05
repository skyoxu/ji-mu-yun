"""ADR-0044/0048/0050/0057: an access refusal never authorizes recovery I/O.

Every filesystem/process boundary below is mocked; these tests neither publish
nor access a real temporary directory, lock, generation or formal layer.
"""
from contextlib import nullcontext
import io
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import publish_knowledge_catalog as publisher


class Writer(io.StringIO):
    def fileno(self):
        return 123456


class PermissionStopTests(unittest.TestCase):
    def test_wrapped_and_grouped_refusals_remain_visible(self):
        original = PermissionError("denied synthetic target")
        wrapped = RuntimeError("wrapper")
        wrapped.__cause__ = original
        self.assertTrue(publisher._access_refused(wrapped))
        self.assertTrue(publisher._access_refused(ExceptionGroup("group", [ValueError("ordinary"), original])))
        wrapped.__context__ = wrapped
        self.assertTrue(publisher._access_refused(wrapped))
        self.assertFalse(publisher._access_refused(ValueError("ordinary semantic failure")))

    def test_run_does_not_write_failure_evidence_after_access_refusal(self):
        with patch.object(publisher, "_single_writer", return_value=nullcontext()), patch.object(publisher, "_main_commit", side_effect=PermissionError("denied synthetic target")), patch.object(publisher, "_write_failure") as failure:
            result = publisher.run(Path("C:/synthetic-only"), publish=False, repeat=1)
        self.assertEqual("blocked", result["status"])
        failure.assert_not_called()

    def test_single_writer_does_not_reopen_or_remove_lock_after_refusal(self):
        with patch.object(Path, "mkdir"), patch.object(publisher, "_acquisition_guard", return_value=nullcontext()), patch.object(publisher.os, "open", return_value=123456), patch.object(publisher.os, "fdopen", return_value=Writer()), patch.object(publisher.os, "fsync"), patch.object(publisher, "_process_identity", return_value={}), patch.object(Path, "read_text", return_value='{"token":"not-owned"}') as read, patch.object(Path, "unlink") as remove:
            with self.assertRaises(PermissionError):
                with publisher._single_writer(Path("C:/synthetic-only")):
                    raise PermissionError("denied synthetic target")
        read.assert_not_called()
        remove.assert_not_called()

    def test_generation_write_refusal_retains_temporary_without_querying_it(self):
        with patch.object(Path, "exists", return_value=False) as exists, patch.object(Path, "mkdir"), patch.object(publisher.tempfile, "mkdtemp", return_value="C:/synthetic-only/stage"), patch.object(Path, "write_bytes", side_effect=PermissionError("denied synthetic target")), patch.object(publisher.shutil, "rmtree") as remove:
            with self.assertRaises(PermissionError):
                publisher._publish_bundle(Path("C:/synthetic-only"), main_commit="0" * 40,
                    layer_bytes={}, input_bytes={}, report_bytes=b"{}", report={"snapshot": {"snapshot_id": "dummy"}, "policy_revision": "dummy", "summary": {}}, publication_authorization=publisher._PublicationAuthorization({}))
        self.assertEqual(1, exists.call_count)  # Existing-generation check only.
        remove.assert_not_called()

    def test_rollback_access_refusal_stops_before_other_targets_or_verification(self):
        with patch.object(publisher, "_restore_bytes", side_effect=PermissionError("denied synthetic target")) as restore, patch.object(Path, "is_file") as stat:
            with self.assertRaises(RuntimeError):
                publisher._rollback_and_verify({Path("one"): b"a", Path("two"): b"b"})
        self.assertEqual(1, restore.call_count)
        stat.assert_not_called()

    def test_stale_lock_read_refusal_does_not_stat_or_retry(self):
        with patch.object(Path, "read_bytes", side_effect=PermissionError("denied synthetic target")) as read, patch.object(Path, "stat", return_value=SimpleNamespace(st_mtime=publisher.time.time())) as stat:
            with self.assertRaises(PermissionError):
                publisher._recover_stale_lock(Path("C:/synthetic-only"), Path("C:/synthetic-only/lock"))
        self.assertEqual(1, read.call_count)
        stat.assert_not_called()

    def test_nonpermission_semantic_failure_keeps_existing_failure_evidence(self):
        with patch.object(publisher, "_single_writer", return_value=nullcontext()), patch.object(publisher, "_main_commit", side_effect=ValueError("semantic mismatch")), patch.object(publisher, "_write_failure", return_value=Path("synthetic-evidence.json")) as failure:
            result = publisher.run(Path("C:/synthetic-only"), publish=False, repeat=1)
        self.assertEqual("synthetic-evidence.json", result["evidence"])
        failure.assert_called_once()

    def test_nonpermission_rollback_still_restores_and_verifies_every_target(self):
        with patch.object(publisher, "_restore_bytes") as restore, patch.object(Path, "is_file", return_value=False) as stat:
            publisher._rollback_and_verify({Path("one"): None, Path("two"): None})
        self.assertEqual(2, restore.call_count)
        self.assertEqual(2, stat.call_count)

    def test_restore_access_refusal_does_not_write_failure_evidence(self):
        with patch.object(publisher, "_single_writer", return_value=nullcontext()), patch.object(publisher, "_main_commit", side_effect=PermissionError("denied synthetic target")), patch.object(publisher, "_write_failure") as failure:
            result = publisher.restore_last_known_good(Path("C:/synthetic-only"), repeat=1)
        failure.assert_not_called()
        self.assertTrue(result["access_refused"])
        self.assertTrue(result["retained_state_unverified"])
        self.assertIsNone(result["evidence"])

    def test_lkg_activation_refusal_does_not_begin_rollback(self):
        with patch.object(Path, "is_file", return_value=False), patch.object(publisher, "_main_commit", return_value="0" * 40), patch.object(publisher, "_atomic_bytes", side_effect=PermissionError("denied synthetic target")), patch.object(publisher, "_rollback_and_verify") as rollback:
            with self.assertRaises(PermissionError):
                publisher._activate_lkg(Path("C:/synthetic-only"), pointer={}, pointer_bytes=b"{}", manifest={}, payloads={k: b"{}" for k in publisher.LAYER_PATHS}, layers={}, inputs={}, repeat=1, expected_main="0" * 40)
        rollback.assert_not_called()

    def test_publish_activation_refusal_does_not_begin_rollback(self):
        with patch.object(Path, "exists", return_value=False), patch.object(Path, "is_file", return_value=False), patch.object(Path, "mkdir"), patch.object(Path, "write_bytes"), patch.object(publisher.tempfile, "mkdtemp", return_value="C:/synthetic-only/stage"), patch.object(publisher.os, "replace"), patch.object(publisher, "_main_commit", return_value="0" * 40), patch.object(publisher, "_atomic_bytes", side_effect=PermissionError("denied synthetic target")), patch.object(publisher, "_rollback_and_verify") as rollback:
            with self.assertRaises(PermissionError):
                publisher._publish_bundle(Path("C:/synthetic-only"), main_commit="0" * 40,
                    layer_bytes={k: b"{}" for k in publisher.LAYER_PATHS}, input_bytes={}, report_bytes=b"{}", report={"snapshot": {"snapshot_id": "dummy"}, "policy_revision": "dummy", "summary": {}}, publication_authorization=publisher._PublicationAuthorization({}))
        rollback.assert_not_called()

    def test_staging_cleanup_failure_preserves_both_causes_without_retry(self):
        with patch.object(publisher.tempfile, "mkdtemp", return_value="C:/synthetic-only/stage"), patch.object(Path, "exists", return_value=True) as exists, patch.object(publisher.shutil, "rmtree", side_effect=PermissionError("cleanup denied")) as remove:
            with self.assertRaises(RuntimeError) as caught:
                with publisher._private_staging(Path("C:/synthetic-only"), "stage-"):
                    raise ValueError("original semantic failure")
        self.assertIn("original semantic failure", str(caught.exception))
        self.assertIn("cleanup denied", str(caught.exception))
        self.assertTrue(publisher._access_refused(caught.exception))
        self.assertEqual(1, exists.call_count)
        remove.assert_called_once()

    def test_normal_private_staging_cleanup_remains_enabled(self):
        with patch.object(publisher.tempfile, "mkdtemp", return_value="C:/synthetic-only/stage"), patch.object(Path, "exists", return_value=True), patch.object(publisher.shutil, "rmtree") as remove:
            with publisher._private_staging(Path("C:/synthetic-only"), "stage-"):
                pass
        remove.assert_called_once()

    def test_lock_cleanup_refusal_preserves_an_existing_body_failure(self):
        with patch.object(Path, "mkdir"), patch.object(publisher, "_acquisition_guard", return_value=nullcontext()), patch.object(publisher.os, "open", return_value=123456), patch.object(publisher.os, "fdopen", return_value=Writer()), patch.object(publisher.os, "fsync"), patch.object(publisher, "_process_identity", return_value={}), patch.object(Path, "read_text", side_effect=PermissionError("cleanup denied")) as read, patch.object(Path, "unlink") as remove:
            with self.assertRaises(RuntimeError) as caught:
                with publisher._single_writer(Path("C:/synthetic-only")):
                    raise ValueError("original semantic failure")
        self.assertIn("original semantic failure", str(caught.exception))
        self.assertIn("cleanup denied", str(caught.exception))
        self.assertTrue(publisher._access_refused(caught.exception))
        read.assert_called_once()
        remove.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
