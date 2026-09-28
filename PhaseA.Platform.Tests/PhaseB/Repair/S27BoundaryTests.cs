using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S27BoundaryTests
{
    private const string ProjectId = "s27-project";
    private readonly ITestOutputHelper _output;

    public S27BoundaryTests(ITestOutputHelper output) => _output = output;

    [Fact]
    public async Task O_EF3B026F4525()
    {
        var root = Directory.CreateTempSubdirectory("s27-publication-boundary-");
        try
        {
            var connectionString = new SqliteConnectionStringBuilder
            {
                DataSource = Path.Combine(root.FullName, "metadata.sqlite3"),
                Pooling = false,
            }.ToString();
            await SqliteMetadataSchema.InitializeAsync(connectionString);
            await new SqliteMigrationService().MigrateAsync(connectionString, "s27-migration-account", ProjectId, "s27-migration");

            var store = CreateStore(connectionString, root.FullName);
            var account = await store.CreateUserAccountAsync($"s27-user-{Guid.NewGuid():N}", 1);
            var projectRoot = Directory.CreateDirectory(Path.Combine(root.FullName, "project"));
            var project = await store.CreateProjectAsync(new ProjectCreationCommand(
                ProjectId,
                account.AccountId,
                "S27 boundary",
                "S27 boundary",
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
                throw new InvalidOperationException("The disposable S27 project could not be created.");
            }

            var context = RequestContext.FromIdentity(
                new AccountIdentity(account.AccountId, "s27-owner", PhaseAAuth.UserRole),
                "s27-principal",
                "s27-runtime-credential",
                "s27-correlation");
            var source = Directory.CreateDirectory(Path.Combine(root.FullName, "source"));
            File.WriteAllText(Path.Combine(source.FullName, "project.godot"), "s27 unpublished result");
            var storage = new WorkspaceStorageService(connectionString);
            storage.SetQuota(account.AccountId, 4 * 1024 * 1024);
            var snapshot = storage.CreateSnapshot(
                context,
                source.FullName,
                "s27-snapshot",
                "s27-workspace",
                ProjectId,
                "s27-policy",
                new HashSet<string>(StringComparer.OrdinalIgnoreCase));

            var runId = await store.CreateRunAsync(ProjectId, null, "s27-run");
            if (!await store.TryAcquireRunnerLockAsync(ProjectId, runId))
            {
                throw new InvalidOperationException("The disposable S27 runner lease could not be acquired.");
            }

            var lease = await ReadLeaseAsync(connectionString, runId)
                ?? throw new InvalidOperationException("The disposable S27 runner lease could not be read.");
            var leaseCountBeforeBoundary = CountLeases(connectionString, ProjectId);
            var destination = Directory.CreateDirectory(Path.Combine(root.FullName, "destination"));

            var queue = new HeavyRunnerQueueService(TimeSpan.Zero, maxConcurrentRuns: 1);
            var blockerStarted = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
            var releaseBlocker = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
            var blocker = queue.ExecuteAsync(
                "s27-blocker",
                account.AccountId,
                ProjectId,
                "s27-blocker",
                async cancellationToken =>
                {
                    blockerStarted.TrySetResult(true);
                    await releaseBlocker.Task.WaitAsync(cancellationToken);
                    return true;
                });
            await blockerStarted.Task.WaitAsync(TimeSpan.FromSeconds(10));

            var publication = queue.ExecuteAsync(
                "s27-publication",
                account.AccountId,
                ProjectId,
                "workspace-restore",
                _ =>
                {
                    try
                    {
                        var attempt = new RestoreService(connectionString).RestorePrepared(
                            context,
                            snapshot.Manifest,
                            source.FullName,
                            destination.FullName,
                            lease,
                            "s27-disabled-at-publication");
                        return Task.FromResult<RestoreAttempt?>(attempt);
                    }
                    catch (UnauthorizedAccessException)
                    {
                        return Task.FromResult<RestoreAttempt?>(null);
                    }
                });

            if (!await store.SetUserDisabledAsync(account.AccountId, true))
            {
                throw new InvalidOperationException("The disposable S27 account could not be disabled.");
            }

            releaseBlocker.TrySetResult(true);
            await blocker;
            var attemptResult = await publication;
            var publishedPath = Path.Combine(destination.FullName, ".restore-current", "project.godot");
            var deniedAtBoundary = attemptResult is null;
            var noPublishedResult = !File.Exists(publishedPath);
            var noNewLease = CountLeases(connectionString, ProjectId) == leaseCountBeforeBoundary;

            Require(
                deniedAtBoundary && noPublishedResult && noNewLease,
                "FAILURE-O-EF3B026F4525",
                "The disabled Account operation published a result or gained publication authority after the atomic boundary.");
            _output.WriteLine("S27-OBSERVATION O-EF3B026F4525 publication-denied-after-account-disablement-no-result-or-lease");
        }
        finally
        {
            SqliteConnection.ClearAllPools();
            if (root.Exists)
            {
                root.Delete(recursive: true);
            }
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

    private static async Task<RunnerLease?> ReadLeaseAsync(string connectionString, string leaseId)
    {
        await using var connection = new SqliteConnection(connectionString);
        await connection.OpenAsync();
        await using var command = connection.CreateCommand();
        command.CommandText = "SELECT lease_id, account_id, project_id, fence FROM runner_leases WHERE lease_id=$lease";
        command.Parameters.AddWithValue("$lease", leaseId);
        await using var reader = await command.ExecuteReaderAsync();
        return await reader.ReadAsync()
            ? new RunnerLease(reader.GetString(0), reader.GetString(1), reader.GetString(2), reader.GetInt64(3))
            : null;
    }

    private static int CountLeases(string connectionString, string projectId)
    {
        using var connection = new SqliteConnection(connectionString);
        connection.Open();
        using var command = connection.CreateCommand();
        command.CommandText = "SELECT COUNT(*) FROM runner_leases WHERE project_id=$project";
        command.Parameters.AddWithValue("$project", projectId);
        return Convert.ToInt32(command.ExecuteScalar());
    }

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
        {
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
        }
    }
}
