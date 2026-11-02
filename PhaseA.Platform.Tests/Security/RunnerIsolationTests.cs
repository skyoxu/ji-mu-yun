using FluentAssertions;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using PhaseA.Platform.Tests.PhaseB.Repair;
using Xunit;

namespace PhaseA.Platform.Tests.PhaseB;

public sealed class RunnerIsolationTests
{
    [Fact]
    public void RootPath_FilesystemRootAndNestedDirectoryAreValid()
    {
        // ADR-0061: retain the native filesystem root, including a Windows drive root.
        // Running on Linux exercises / only, not Windows drive/ACL behavior.
        var directory = Directory.CreateTempSubdirectory("s206-native-root-");
        var filesystemRoot = Path.GetPathRoot(directory.FullName)!;
        var child = Directory.CreateDirectory(Path.Combine(directory.FullName, "nested"));
        Action fromRoot = () => RunnerIsolationPolicy.RequireNoReparsePoint(filesystemRoot, child.FullName);
        Action fromDirectory = () => RunnerIsolationPolicy.RequireNoReparsePoint(directory.FullName, child.FullName);
        fromRoot.Should().NotThrow();
        fromDirectory.Should().NotThrow();
        RunnerIsolationPolicy.RequireContainedPath(directory.FullName, "nested/item.txt")
            .Should().Be(Path.Combine(child.FullName, "item.txt"));
    }

    [Fact]
    public void RootPath_ContainmentAndRealReparseDenialsRemainEnforced()
    {
        var root = Directory.CreateTempSubdirectory("s206-root-denials-");
        var outside = Directory.CreateTempSubdirectory("s206-root-outside-");
        var file = Path.Combine(outside.FullName, "retained.txt");
        File.WriteAllText(file, "unchanged external fixture");
        var directoryLink = Path.Combine(root.FullName, "directory-link");
        var fileLink = Path.Combine(root.FullName, "file-link.txt");
        Directory.CreateSymbolicLink(directoryLink, outside.FullName);
        File.CreateSymbolicLink(fileLink, file);
        Action traversal = () => RunnerIsolationPolicy.RequireContainedPath(root.FullName, "../escape.txt");
        Action absolute = () => RunnerIsolationPolicy.RequireContainedPath(root.FullName, file);
        Action directoryReparse = () => RunnerIsolationPolicy.RequireContainedPath(root.FullName, "directory-link/retained.txt");
        Action fileReparse = () => RunnerIsolationPolicy.RequireContainedPath(root.FullName, "file-link.txt");
        traversal.Should().Throw<UnauthorizedAccessException>();
        absolute.Should().Throw<UnauthorizedAccessException>();
        directoryReparse.Should().Throw<UnauthorizedAccessException>();
        fileReparse.Should().Throw<UnauthorizedAccessException>();
        File.ReadAllText(file).Should().Be("unchanged external fixture");
    }

    [Fact]
    public void WorkspaceLayout_StaysUnderAccountProjectRoot()
    {
        var layout = WorkspaceLayoutBuilder.Build(@"C:\phase-workspaces", "account-a", "project-a");

        layout.RootPath.Should().StartWith(@"C:\phase-workspaces\account-a\project-a");
        WorkspacePathPolicy.IsUnderRoot(@"C:\phase-workspaces", layout.RootPath).Should().BeTrue();
    }

    [Fact]
    public void PrepareWorkspace_PublishesEnforcedIsolationBoundary()
    {
        // ADR-0061: this disposable fixture must not overwrite another fixture's credential target.
        var accountId = $"account-a-{Guid.NewGuid():N}";
        var projectId = $"project-a-{Guid.NewGuid():N}";
        var root = Directory.CreateTempSubdirectory("phase-runner-isolation");
        try
        {
            using var credentials = OperatingSystem.IsWindows()
                ? TestRunnerCredentialScope.Create(accountId, projectId)
                : null;
            var descriptor = credentials?.Describe(accountId, projectId, root.FullName)
                ?? RunnerIsolationPolicy.Describe(accountId, projectId, root.FullName);
            using var handle = RunnerIsolationPolicy.PrepareWorkspace(descriptor);
            File.Exists(handle.MarkerPath).Should().BeTrue();
            File.ReadAllText(handle.MarkerPath).Should().Contain(accountId).And.Contain(projectId);
        }
        finally { root.Delete(true); }
    }
}
