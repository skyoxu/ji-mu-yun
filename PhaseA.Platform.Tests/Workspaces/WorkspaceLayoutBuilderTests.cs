using FluentAssertions;
using PhaseA.Platform.Workspaces;
using Xunit;

namespace PhaseA.Platform.Tests.Workspaces;

public sealed class WorkspaceLayoutBuilderTests
{
    [Fact]
    public void Build_CreatesRepoRuntimeAndMetaPathsUnderRoot()
    {
        var layout = WorkspaceLayoutBuilder.Build(@"C:\workspaces", "account1", "project1");

        layout.RootPath.Should().Be(Path.GetFullPath(@"C:\workspaces\account1\project1"));
        layout.RepoPath.Should().Be(Path.GetFullPath(@"C:\workspaces\account1\project1\repo"));
        layout.RuntimePath.Should().Be(Path.GetFullPath(@"C:\workspaces\account1\project1\runtime"));
        layout.MetaPath.Should().Be(Path.GetFullPath(@"C:\workspaces\account1\project1\meta"));
    }

    [Theory]
    [InlineData("..")]
    [InlineData("bad:name")]
    public void Build_RejectsUnsafePathSegments(string segment)
    {
        var act = () => WorkspaceLayoutBuilder.Build(@"C:\workspaces", "account1", segment);

        act.Should().Throw<ArgumentException>();
    }
}
