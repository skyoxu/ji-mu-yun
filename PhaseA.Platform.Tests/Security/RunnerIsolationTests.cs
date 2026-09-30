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
        var root = Directory.CreateTempSubdirectory("phase-runner-isolation");
        try
        {
            using var credentials = OperatingSystem.IsWindows()
                ? TestRunnerCredentialScope.Create("account-a", "project-a")
                : null;
            var descriptor = credentials?.Describe("account-a", "project-a", root.FullName)
                ?? RunnerIsolationPolicy.Describe("account-a", "project-a", root.FullName);
            using var handle = RunnerIsolationPolicy.PrepareWorkspace(descriptor);
            File.Exists(handle.MarkerPath).Should().BeTrue();
            File.ReadAllText(handle.MarkerPath).Should().Contain("account-a").And.Contain("project-a");
        }
        finally { root.Delete(true); }
    }
}
