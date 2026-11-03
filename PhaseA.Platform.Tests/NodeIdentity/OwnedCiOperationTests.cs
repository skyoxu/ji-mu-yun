using PhaseA.Platform.Runs;
using PhaseA.Platform.Workspaces;
using Xunit;

namespace PhaseA.Platform.Tests.NodeIdentity;

// ADR-0061: supplemental fixtures authenticate; they never replace dispatch denial.
public sealed class OwnedCiOperationTests
{
    [Fact]
    public async Task FixtureAuthorityAllowsItsProjectAndRejectsRevokedDispatch()
    {
        var root = S206TestSupport.CreateOwnedFixtureRoot("ci-operation-pair-");
        var options = S206TestSupport.OwnedNodeOptions(new()
        {
            ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(root, "workspaces"),
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(root, "declared.sqlite3")
        });
        var layout = WorkspaceLayoutBuilder.Build(options.HostedWorkspaceRoot, "ci-owner", "ci-project");
        var owned = await OwnedCiOperation.CreateAsync(options, layout.RootPath, layout.RepoPath, "ci-owner", "ci-project");
        var project = (await owned.Store.GetProjectSnapshotAsync("ci-project"))!;
        using var registration = S206TestSupport.RegisterOwnedProjectBoundary(project, options);
        using var current = S206TestSupport.EnterCurrentContext(owned.Context);
        var runner = new HostedProcessRunner(authority: owned.Store);
        var file = OperatingSystem.IsWindows() ? "cmd.exe" : "/bin/sh";
        string[] arguments = OperatingSystem.IsWindows() ? ["/d", "/c", "echo CI_AUTHORIZED"] : ["-c", "echo CI_AUTHORIZED"];
        var command = new HostedProcessCommand(file, arguments, project.RepoPath, new Dictionary<string, string>(),
            RequireIsolation: true, TotalTimeout: TimeSpan.FromSeconds(10));
        PhaseA.Platform.Data.NodeProjectMetadata metadata = owned.Store;
        Assert.Equal("ci-project", (await metadata.GetProjectSnapshotAsync("ci-project"))!.ProjectId);
        // The portable positive proves real metadata authorization. The native
        // process positive additionally runs on Windows; Linux is not ACL proof.
        if (OperatingSystem.IsWindows())
        {
            var positive = await runner.RunAsync(command);
            Assert.Equal(0, positive.ExitCode);
            Assert.Contains("CI_AUTHORIZED", positive.Stdout);
        }
        await owned.Store.RotateUserTokenAsync("ci-owner");
        var denied = await runner.RunAsync(command);
        Assert.Equal(403, denied.ExitCode);
        Assert.DoesNotContain("CI_AUTHORIZED", denied.Stdout);
    }
}
