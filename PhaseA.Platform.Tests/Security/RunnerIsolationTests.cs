using FluentAssertions;
using PhaseA.Platform.Workspaces;
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
}
