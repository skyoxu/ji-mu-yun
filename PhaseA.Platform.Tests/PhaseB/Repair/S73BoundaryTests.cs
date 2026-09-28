using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S73BoundaryTests
{
    private const string ProjectId = "s73-project";
    private readonly ITestOutputHelper _output;

    public S73BoundaryTests(ITestOutputHelper output)
    {
        _output = output;
    }

    [Fact]
    public async Task O_E443F1B126A1()
    {
        var root = Directory.CreateTempSubdirectory("s73-restart-");
        var databasePath = Path.Combine(root.FullName, "metadata.sqlite3");
        try
        {
            var connectionString = new SqliteConnectionStringBuilder { DataSource = databasePath }.ToString();
            await SqliteMetadataSchema.InitializeAsync(connectionString);
            await new SqliteMigrationService().MigrateAsync(connectionString, "s73-account", ProjectId, "s73-restart-migration");

            var store = CreateStore(connectionString, root.FullName);
        var accountId = await CreateProjectAsync(store, connectionString, root.FullName);
            var leaseId = await store.CreateRunAsync(ProjectId, null, "s73-restart");
            var acquired = await store.TryAcquireRunnerLockAsync(ProjectId, leaseId);
            var restartedStore = CreateStore(connectionString, root.FullName);
            var restartedProject = await restartedStore.GetProjectSnapshotAsync(ProjectId);
            var lease = await ReadLeaseAsync(connectionString, leaseId);

            Require(
                acquired && restartedProject is not null && lease is not null && lease.AccountId == accountId,
                "FAILURE-O-E443F1B126A1",
                "A Project lease acquired through the metadata store was not readable from SQLite after restart.");

            var source = Directory.CreateDirectory(Path.Combine(root.FullName, "source"));
            var destination = Directory.CreateDirectory(Path.Combine(root.FullName, "destination"));
            File.WriteAllText(Path.Combine(source.FullName, "project.godot"), "s73 durable publication");
            var context = RequestContext.FromIdentity(
                new AccountIdentity(lease!.AccountId, "owner", PhaseAAuth.UserRole),
                "s73-principal",
                "s73-runtime-credential",
                "s73-correlation");
            var storage = new WorkspaceStorageService();
            storage.SetQuota(lease.AccountId, 1024 * 1024);
            var manifest = storage.CreateSnapshot(
                context,
                source.FullName,
                "s73-snapshot",
                "s73-workspace",
                ProjectId,
                "s73-policy",
                new HashSet<string>()).Manifest;
            var published = new RestoreService(connectionString, new RouteRecoveryAuthorityResolver(connectionString)).RestorePrepared(
                context,
                manifest,
                source.FullName,
                destination.FullName,
                lease);

            Require(
                published.Status == RestoreAttemptStatus.Published &&
                File.ReadAllText(Path.Combine(destination.FullName, ".restore-current", "project.godot")) == "s73 durable publication",
                "FAILURE-O-E443F1B126A1",
                "The restarted SQLite lease could not fence publication through the production restore boundary.");
            _output.WriteLine("S73-OBSERVATION O-E443F1B126A1 durable-lease-read-after-restart-fenced-publication");
        }
        finally
        {
            SqliteConnection.ClearAllPools();
            root.Delete(recursive: true);
        }
    }

    [Fact]
    public async Task O_1E153CD67F3B()
    {
        var root = Directory.CreateTempSubdirectory("s73-supersession-");
        var databasePath = Path.Combine(root.FullName, "metadata.sqlite3");
        try
        {
            var connectionString = new SqliteConnectionStringBuilder { DataSource = databasePath }.ToString();
            await SqliteMetadataSchema.InitializeAsync(connectionString);
            await new SqliteMigrationService().MigrateAsync(connectionString, "s73-account", ProjectId, "s73-supersession-migration");
            var store = CreateStore(connectionString, root.FullName);
            await CreateProjectAsync(store, connectionString, root.FullName);
            var firstLeaseId = await store.CreateRunAsync(ProjectId, null, "s73-first");
            var supersedingLeaseId = await store.CreateRunAsync(ProjectId, null, "s73-second");

            var firstAcquired = await store.TryAcquireRunnerLockAsync(ProjectId, firstLeaseId);
            await store.ReleaseRunnerLockAsync(ProjectId, firstLeaseId);
            var supersedingAcquired = await store.TryAcquireRunnerLockAsync(ProjectId, supersedingLeaseId);
            var firstLease = await ReadLeaseAsync(connectionString, firstLeaseId);
            var supersedingLease = await ReadLeaseAsync(connectionString, supersedingLeaseId);

            Require(
                firstAcquired && supersedingAcquired &&
                firstLease is not null && supersedingLease is not null &&
                supersedingLease.Fence > firstLease.Fence,
                "FAILURE-O-1E153CD67F3B",
                "A superseding Project lease did not persist a strictly greater SQLite fencing value.");
            _output.WriteLine("S73-OBSERVATION O-1E153CD67F3B superseding-lease-has-greater-durable-fence");
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

    private static async Task<string> CreateProjectAsync(PhaseAMetadataStore store, string connectionString, string root)
    {
        var account = await store.CreateUserAccountAsync($"s73-user-{Guid.NewGuid():N}", 1);
        var projectRoot = Directory.CreateDirectory(Path.Combine(root, "project"));
        var project = await store.CreateProjectAsync(new ProjectCreationCommand(
            ProjectId,
            account.AccountId,
            "S73 boundary",
            "S73 boundary",
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
            throw new InvalidOperationException("The disposable S73 project could not be created.");
        }
        RouteAuthorityFixture.Seed(connectionString, account.AccountId, ProjectId, projectRoot.FullName);
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
