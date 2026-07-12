using System.Text;
using FluentAssertions;
using PhaseA.Platform.Data;
using PhaseA.Platform.Runs;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class PrototypeRouteStateWriterTests
{
    [Fact]
    public void ReadLatestIterationPlanState_FallsBackToMirrorWhenPrimaryJsonIsInvalid()
    {
        var root = Path.Combine(Path.GetTempPath(), $"phasea-route-state-{Guid.NewGuid():N}");
        try
        {
            var project = Project(root);
            var writer = new PrototypeRouteStateWriter();
            writer.WriteIterationPlanState(project, new { route = "iteration-plan", status = "ready" });
            var primaryPath = Path.Combine(project.MetaPath, "routes", "iteration-plan", "latest.json");
            File.WriteAllText(primaryPath, "{ invalid", Encoding.UTF8);

            var state = writer.ReadLatestIterationPlanState(project);

            state.Should().Contain("\"status\": \"ready\"");
        }
        finally
        {
            if (Directory.Exists(root))
            {
                Directory.Delete(root, recursive: true);
            }
        }
    }

    [Fact]
    public void WriteIterationPlanState_LeavesNoTemporaryFiles()
    {
        var root = Path.Combine(Path.GetTempPath(), $"phasea-route-state-{Guid.NewGuid():N}");
        try
        {
            var project = Project(root);
            var writer = new PrototypeRouteStateWriter();

            writer.WriteIterationPlanState(project, new { route = "iteration-plan", status = "ready" });
            writer.WriteIterationPlanState(project, new { route = "iteration-plan", status = "confirmed" });

            Directory.EnumerateFiles(root, "*.tmp", SearchOption.AllDirectories).Should().BeEmpty();
            writer.ReadLatestIterationPlanState(project).Should().Contain("\"status\": \"confirmed\"");
        }
        finally
        {
            if (Directory.Exists(root))
            {
                Directory.Delete(root, recursive: true);
            }
        }
    }

    [Theory]
    [InlineData("../../outside.json")]
    [InlineData("C:/outside.json")]
    [InlineData("meta/routes/iteration-plan/latest.json")]
    public void WriteIterationPlanInteractionRegionState_RejectsEscapedOrNonCanonicalPath(string artifactRef)
    {
        var root = Path.Combine(Path.GetTempPath(), $"phasea-route-state-{Guid.NewGuid():N}");
        try
        {
            var project = Project(root);
            var writer = new PrototypeRouteStateWriter();

            var act = () => writer.WriteIterationPlanInteractionRegionState(
                project,
                1,
                new { status = "pending" },
                artifactRef);

            act.Should().Throw<InvalidOperationException>();
        }
        finally
        {
            if (Directory.Exists(root))
            {
                Directory.Delete(root, recursive: true);
            }
        }
    }

    private static ProjectSnapshot Project(string root)
    {
        var repoPath = Path.Combine(root, "repo");
        return new ProjectSnapshot(
            "project-1",
            "account-1",
            "Project",
            "Game",
            "rpg",
            "",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-1",
            root,
            repoPath,
            Path.Combine(repoPath, "runtime"),
            Path.Combine(root, "metadata"));
    }
}
