"""Windows transport/identity fault tests (Accepted ADR-0058)."""
from __future__ import annotations

import tempfile
import unittest
import copy
import ctypes
from pathlib import Path, PureWindowsPath
from unittest import mock

import test_skill_replay_review_regressions as support

replay = support.replay


class WindowsJobContractTests(unittest.TestCase):
    def test_win32_kernel_handle_signatures_preserve_pointer_width(self):
        from scripts.sc import skill_replay_windows_job as jobs
        api = mock.MagicMock()
        with mock.patch.object(ctypes, "WinDLL", return_value=api, create=True):
            self.assertIs(api, jobs.kernel_api())
        self.assertIs(ctypes.c_void_p, api.CreateJobObjectW.restype)
        self.assertIs(ctypes.c_void_p, api.CreateToolhelp32Snapshot.restype)
        self.assertIs(ctypes.c_void_p, api.OpenThread.restype)
        self.assertEqual([ctypes.c_void_p, ctypes.c_void_p], api.AssignProcessToJobObject.argtypes)
        self.assertEqual(28, ctypes.sizeof(jobs.ThreadEntry))
        self.assertEqual(48, ctypes.sizeof(jobs.Accounting))
        if ctypes.sizeof(ctypes.c_void_p) == 8:
            self.assertEqual(144, ctypes.sizeof(jobs.ExtendedLimits))

    def test_failed_job_assignment_never_resumes_uncontained_code(self):
        from scripts.sc import skill_replay_windows_job as jobs
        api = mock.MagicMock()
        handle = 0x100000001
        api.CreateJobObjectW.return_value = handle
        api.SetInformationJobObject.return_value = 1
        api.AssignProcessToJobObject.return_value = 0
        with mock.patch.object(ctypes, "get_last_error", return_value=5, create=True), \
             mock.patch.object(ctypes, "WinError", side_effect=lambda code: OSError(code, "job denied"), create=True):
            job = jobs.WindowsJob(api)
            try:
                with self.assertRaisesRegex(OSError, "job denied"):
                    job.assign_and_resume(mock.Mock(pid=123, _handle=handle + 1))
            finally:
                job.close()
        api.OpenThread.assert_not_called()
        api.ResumeThread.assert_not_called()
        api.AssignProcessToJobObject.assert_called_once_with(handle, handle + 1)
        api.CloseHandle.assert_called_once_with(handle)


class WindowsBindingTests(unittest.TestCase):
    def setUp(self):
        self.fixture = support.NativeRuntimeTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)

    def freeze(self):
        self.fixture.git("add", ".")
        self.fixture.git("commit", "-qm", "Freeze Windows binding fault input")
        commit = self.fixture.git("rev-parse", "HEAD").strip()
        self.fixture.pin_fixture_authority(commit)
        return commit

    def mixed_case_resources(self):
        for name in ("Z-policy.json", "a-policy.json", "SKILL.md"):
            self.fixture.write("validator/" + name, "{}\n")
        return self.freeze()

    def windows_order(self):
        return mock.patch.object(type(self.fixture.root), "__lt__", lambda left, right:
                                 PureWindowsPath(str(left)) < PureWindowsPath(str(right)))

    def test_windows_path_order_cannot_create_false_trust_membership_drift(self):
        self.mixed_case_resources()
        with self.windows_order():
            receipt = replay.validate_package("candidate", "capability.json")
        self.assertEqual("pass", receipt["status"])

    def test_package_and_dependency_identities_are_platform_order_independent(self):
        self.mixed_case_resources()
        root = self.fixture.root
        expected_manifest = replay.manifest(root / "candidate")
        expected_closure = replay.runtime.dependency_closure(root, ("candidate", "validator"))
        with self.windows_order():
            self.assertEqual(expected_manifest, replay.manifest(root / "candidate"))
            self.assertEqual(expected_closure, replay.runtime.dependency_closure(root, ("candidate", "validator")))

    def test_non_ascii_git_owner_names_are_not_misread_as_quoted_paths(self):
        self.fixture.write("validator/\u5b57\u6bb5-policy.json", "{}\n")
        self.freeze()
        self.assertEqual("pass", replay.validate_package("candidate", "capability.json")["status"])

    def test_case_only_owner_rename_still_requires_trust_approval(self):
        self.fixture.write("validator/CasePolicy.json", "{}\n")
        self.freeze()
        original = self.fixture.root / "validator/CasePolicy.json"
        intermediate = original.with_name("rename-in-progress.json")
        original.rename(intermediate)
        intermediate.rename(original.with_name("casepolicy.json"))
        with self.assertRaisesRegex(ValueError, "membership drift.*Trust Approval"):
            replay.validate_package("candidate", "capability.json")

    def test_materialization_reads_raw_git_bytes_without_eol_conversion(self):
        self.fixture.write(".gitattributes", "candidate/SKILL.md text eol=crlf\n")
        commit = self.freeze()
        expected = replay.runtime.git_bytes(self.fixture.root, commit, "candidate/SKILL.md")
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "prior"
            replay.runtime.materialize_git(self.fixture.root, commit, destination, ("candidate",))
            self.assertEqual(expected, (destination / "candidate/SKILL.md").read_bytes())

    def test_fresh_replay_reproduces_identity_when_clone_uses_windows_eol_default(self):
        original_git = replay.runtime.git

        def clone_with_windows_default(root, *arguments):
            output = original_git(root, *arguments)
            if arguments and arguments[0] == "clone":
                original_git(Path(arguments[-1]), "config", "core.autocrlf", "true")
            return output

        with mock.patch.object(replay.runtime, "git", side_effect=clone_with_windows_default):
            result, code = replay.replay_package("candidate", "capability.json", "fresh")
        self.assertEqual(0, code)
        current = result["current_wrapper_replay"]
        self.assertEqual(current["pinned_semantic_verdict"], current["fresh_semantic_verdict"])
        import shutil
        shutil.rmtree(Path(current["checkout_path"]).parent)

    def test_duplicate_raw_matrix_inputs_name_both_cases_before_execution(self):
        self.fixture.write("candidate/feature.py", "def result():\n    return 2\n")
        matrix = replay.runtime.prepare_matrix(self.fixture.root, "candidate", "capability.json",
                                               self.fixture.commit, "logs/duplicates/matrix.json")
        duplicate = copy.deepcopy(matrix)
        first, second = duplicate["cases"][:2]
        raw = (self.fixture.root / first["fixture"]["path"]).read_bytes()
        path = self.fixture.root / "logs/duplicates/copied-input.json"
        path.write_bytes(raw)
        second["fixture"] = {"path": path.relative_to(self.fixture.root).as_posix(),
                             "sha256": replay.runtime.sha(raw)}
        result, code = replay.runtime.replay_matrix(self.fixture.root, duplicate)
        self.assertNotEqual(0, code)
        reason = " ".join(result["invalid_reasons"])
        self.assertIn("duplicate", reason)
        self.assertIn(first["case_id"], reason)
        self.assertIn(second["case_id"], reason)
        self.assertTrue(all(not row["executed"] for row in result["case_results"]))


if __name__ == "__main__":
    unittest.main()
