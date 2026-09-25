using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S48BoundaryTests
{
    private const string ProjectId = "s48-project";
    private readonly ITestOutputHelper _output;

    public S48BoundaryTests(ITestOutputHelper output)
    {
        _output = output;
    }

    [Fact]
    public async Task O_92963141AC9F()
    {
        var root = Directory.CreateTempSubdirectory("s48-fenced-publication-");
        try
        {
            var connectionString = new SqliteConnectionStringBuilder
            {
                DataSource = Path.Combine(root.FullName, "metadata.sqlite3"),
            }.ToString();
            await SqliteMetadataSchema.InitializeAsync(connectionString);
            await new SqliteMigrationService().MigrateAsync(connectionString, "s48-account", ProjectId, "s48-migration");

            var store = CreateStore(connectionString, root.FullName);
            var accountId = await CreateProjectAsync(store, root.FullName);
            var staleRunId = await store.CreateRunAsync(ProjectId, null, "s48-stale");
            var currentRunId = await store.CreateRunAsync(ProjectId, null, "s48-current");
            var staleAcquired = await store.TryAcquireRunnerLockAsync(ProjectId, staleRunId);
            await store.ReleaseRunnerLockAsync(ProjectId, staleRunId);
            var currentAcquired = await store.TryAcquireRunnerLockAsync(ProjectId, currentRunId);
            var staleLease = await ReadLeaseAsync(connectionString, staleRunId);
            var currentLease = await ReadLeaseAsync(connectionString, currentRunId);

            var currentSource = Directory.CreateDirectory(Path.Combine(root.FullName, "current-source"));
            var staleSource = Directory.CreateDirectory(Path.Combine(root.FullName, "stale-source"));
            var destination = Directory.CreateDirectory(Path.Combine(root.FullName, "destination"));
            File.WriteAllText(Path.Combine(currentSource.FullName, "project.godot"), "current fenced publication");
            File.WriteAllText(Path.Combine(staleSource.FullName, "project.godot"), "stale fenced publication");

            var context = RequestContext.FromIdentity(
                new AccountIdentity(accountId, "owner", PhaseAAuth.UserRole),
                "s48-principal",
                "s48-runtime-credential",
                "s48-correlation");
            var storage = new WorkspaceStorageService();
            storage.SetQuota(accountId, 1024 * 1024);
            var currentManifest = storage.CreateSnapshot(
                context,
                currentSource.FullName,
                "s48-current-snapshot",
                "s48-workspace",
                ProjectId,
                "s48-policy",
                new HashSet<string>()).Manifest;
            var staleManifest = storage.CreateSnapshot(
                context,
                staleSource.FullName,
                "s48-stale-snapshot",
                "s48-workspace",
                ProjectId,
                "s48-policy",
                new HashSet<string>()).Manifest;

            var restore = new RestoreService(connectionString);
            var currentPublication = currentLease is null
                ? null
                : restore.Restore(context, currentManifest, currentSource.FullName, destination.FullName, currentLease);
            var staleRejected = false;
            if (staleLease is not null)
            {
                try
                {
                    restore.Restore(context, staleManifest, staleSource.FullName, destination.FullName, staleLease);
                }
                catch (InvalidOperationException error) when (error.Message == "runner lease is not authoritative")
                {
                    staleRejected = true;
                }
            }

            var currentPublishedPath = Path.Combine(destination.FullName, ".restore-current", "project.godot");
            var authoritativePublicationRemains = File.Exists(currentPublishedPath)
                && File.ReadAllText(currentPublishedPath) == "current fenced publication";
            Require(
                staleAcquired && currentAcquired &&
                staleLease is not null && currentLease is not null && currentLease.Fence > staleLease.Fence &&
                currentPublication?.Status == RestoreAttemptStatus.Published &&
                staleRejected && authoritativePublicationRemains,
                "FAILURE-O-92963141AC9F",
                "A stale Run published across the fenced restore boundary or replaced the current publication.");
            _output.WriteLine("S48-OBSERVATION O-92963141AC9F stale-publication-rejected-current-fenced-publication-remains-authoritative");
        }
        finally
        {
            SqliteConnection.ClearAllPools();
            root.Delete(recursive: true);
        }
    }

    private static PhaseAMetadataStore CreateStore(string connectionString, string workspaceRoot)
    {
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot,
        });
        return new PhaseAMetadataStore(connectionString, options);
    }

    private static async Task<string> CreateProjectAsync(PhaseAMetadataStore store, string root)
    {
        var account = await store.CreateUserAccountAsync($"s48-user-{Guid.NewGuid():N}", 1);
        var projectRoot = Directory.CreateDirectory(Path.Combine(root, "project"));
        var project = await store.CreateProjectAsync(new ProjectCreationCommand(
            ProjectId,
            account.AccountId,
            "S48 boundary",
            "S48 boundary",
            "manual",
            "default",
            false,
            [],
            projectRoot.FullName,
            Path.Combine(projectRoot.FullName, "repo"),
            Path.Combine(projectRoot.FullName, "runtime"),
            Path.Combine(projectRoot.FullName, "meta")));
        if (project.ProjectId != ProjectId)
        {
            throw new InvalidOperationException("The disposable S48 project could not be created.");
        }

        return account.AccountId;
    }

    private static async Task<RunnerLease?> ReadLeaseAsync(string connectionString, string leaseId)
    {
        await using var connection = new SqliteConnection(connectionString);
        await connection.OpenAsync();
        await using var command = connection.CreateCommand();
        command.CommandText =
            "SELECT lease_id, account_id, project_id, fence FROM runner_leases WHERE lease_id = $lease_id;";
        command.Parameters.AddWithValue("$lease_id", leaseId);
        await using var reader = await command.ExecuteReaderAsync();
        return await reader.ReadAsync()
            ? new RunnerLease(reader.GetString(0), reader.GetString(1), reader.GetString(2), reader.GetInt64(3))
            : null;
    }

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
        {
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
        }
    }
}
