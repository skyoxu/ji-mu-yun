using System.Diagnostics;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using Xunit;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

// ADR-0061: exercise raw Restore; do not use the prepared-fixture extension here.
public sealed class RestoreTreeSecurityRegressionTests
{
    [Fact]
    public void MissingDescriptor_QuarantinesInsteadOfPublishing()
    {
        var root = Directory.CreateTempSubdirectory("restore-missing-acl-").FullName;
        try
        {
            var manifest = Manifest();
            var context = new RequestContext("owner", "account", new HashSet<string> { "member" }, "credential", "correlation");
            var result = new RestoreService().Restore(context, manifest, root, root, new RunnerLease("lease", "account", "project", 1));
            Assert.Equal(RestoreAttemptStatus.Quarantined, result.Status);
            Assert.Equal("acl_invalid", result.FailureCategory);
            Assert.False(Directory.Exists(Path.Combine(root, ".restore-current")));
        }
        finally { Directory.Delete(root, true); }
    }

    [Fact]
    public void ChildAclDrift_IsDetectedWhileWorkspaceRootIsUnchanged()
    {
        if (!OperatingSystem.IsWindows()) throw new PlatformNotSupportedException("NTFS ACL evidence requires Windows.");
        var root = Directory.CreateTempSubdirectory("restore-child-acl-").FullName;
        try
        {
            using var isolation = RunnerIsolationPolicy.PrepareWorkspace(new RunnerIsolationDescriptor("account", "project", "phase-r-a-p", root, true, true, true));
            var tree = Directory.CreateDirectory(Path.Combine(root, "staging")).FullName;
            var child = Path.Combine(tree, "content.txt"); File.WriteAllText(child, "content");
            RunnerIsolationPolicy.PrepareRestoreTree(isolation.Descriptor, tree);
            Assert.True(RunnerIsolationPolicy.HasExpectedRestoreTreeSecurity(isolation.Descriptor, tree));
            using var process = Process.Start(new ProcessStartInfo("icacls.exe", $"\"{child}\" /grant \"*S-1-1-0:F\"") { UseShellExecute = false, CreateNoWindow = true });
            Assert.NotNull(process); process!.WaitForExit(); Assert.Equal(0, process.ExitCode);
            Assert.True(RunnerIsolationPolicy.HasExpectedWorkspaceSecurity(isolation.Descriptor));
            Assert.False(RunnerIsolationPolicy.HasExpectedRestoreTreeSecurity(isolation.Descriptor, tree));
        }
        finally { Directory.Delete(root, true); }
    }

    private static SnapshotManifest Manifest()
    {
        var files = new[] { (RelativePath: "content.txt", Content: "content"u8.ToArray()) };
        var manifest = SnapshotManifest.Create("snapshot", "workspace", "account", "project", "policy", files);
        return manifest with { ProtectedContent = SnapshotManifest.ProtectContent(files, manifest.KeyReference) };
    }
}
