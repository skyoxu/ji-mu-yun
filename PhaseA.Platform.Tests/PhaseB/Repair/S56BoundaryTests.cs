using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Workspaces;
using Xunit;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S56BoundaryTests
{
    [Fact]
    public async Task O_CEEBD932678A()
    {
        var root = Directory.CreateTempSubdirectory("s56-run-completion-");
        try
        {
            var databasePath = Path.Combine(root.FullName, "metadata.sqlite3");
            var connectionString = new SqliteConnectionStringBuilder { DataSource = databasePath }.ToString();
            await SqliteMetadataSchema.InitializeAsync(connectionString);

            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
            {
                ["HOSTED_WORKSPACE_ROOT"] = root.FullName,
            });
            var store = new PhaseAMetadataStore(connectionString, options);
            var account = await store.CreateUserAccountAsync($"s56-user-{Guid.NewGuid():N}", 1);
            var projectId = $"s56-project-{Guid.NewGuid():N}";
            var workspaceRoot = Directory.CreateDirectory(Path.Combine(root.FullName, "workspace"));
            var project = await store.CreateProjectAsync(new ProjectCreationCommand(
                projectId,
                account.AccountId,
                "S56 boundary",
                "S56 boundary",
                "manual",
                "default",
                false,
                [],
                workspaceRoot.FullName,
                Path.Combine(workspaceRoot.FullName, "repo"),
                Path.Combine(workspaceRoot.FullName, "runtime"),
                Path.Combine(workspaceRoot.FullName, "meta")));
            if (!project.Succeeded || string.IsNullOrWhiteSpace(project.WorkspaceId))
            {
                throw new InvalidOperationException("S56 fixture could not create its disposable Project.");
            }

            var snapshots = new WorkspaceStorageService(connectionString);
            var before = snapshots.ListSnapshots(account.AccountId, projectId, includeDeleted: true);
            var runId = await store.CreateRunAsync(projectId, project.WorkspaceId, "s56-run-completion");
            var started = await store.TryMarkRunStartedAsync(runId, null);
            await store.CompleteRunAsync(runId, "succeeded", 0, "completed", "", "{}");
            var completed = await store.GetRunSnapshotAsync(runId);
            var after = snapshots.ListSnapshots(account.AccountId, projectId, includeDeleted: true);

            Require(
                started &&
                completed is
                {
                    ProjectId: var completedProjectId,
                    WorkspaceId: var completedWorkspaceId,
                    RunType: "s56-run-completion",
                    Status: "succeeded",
                    ExitCode: 0,
                    StartedUtc: not null,
                    FinishedUtc: not null
                } &&
                completedProjectId == projectId &&
                completedWorkspaceId == project.WorkspaceId &&
                before.Count == 0 &&
                after.Count == before.Count,
                "FAILURE-O-CEEBD932678A",
                "Run completion created a Snapshot without an explicit Snapshot request or did not retain its completed operation record.");
        }
        finally
        {
            SqliteConnection.ClearAllPools();
            root.Delete(recursive: true);
        }
    }

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
        {
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
        }
    }
}
