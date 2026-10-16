using FluentAssertions;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using PhaseA.Platform.Tests.PhaseB.Repair;
using Xunit;

namespace PhaseA.Platform.Tests.PhaseB;

public sealed class RunnerIsolationTests
{
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
