using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S59BoundaryTests
{
    private const string ProjectId = "s59-project";
    private readonly ITestOutputHelper _output;

    public S59BoundaryTests(ITestOutputHelper output)
    {
        _output = output;
    }

    [Fact]
    public async Task O_C865A3100948()
    {
        var root = Directory.CreateTempSubdirectory("s59-content-");
        try
        {
            var connectionString = await CreateDatabaseAsync(root.FullName, "s59-content");
            var (context, accountId, lease) = await CreateRestoreContextAsync(connectionString, root.FullName, "s59-content");
            var source = Directory.CreateDirectory(Path.Combine(root.FullName, "source"));
            var destination = Directory.CreateDirectory(Path.Combine(root.FullName, "fresh-destination"));
            var originalBytes = new byte[] { 0x00, 0x10, 0x80, 0xFF, 0x41, 0x0A };
            var sourceFile = Path.Combine(source.FullName, "project.godot");
            File.WriteAllBytes(sourceFile, originalBytes);

            var storage = new WorkspaceStorageService(connectionString);
            storage.SetQuota(accountId, 1024 * 1024);
            var snapshot = storage.CreateSnapshot(
                context,
                source.FullName,
                "s59-content-a",
                "s59-content-workspace",
                ProjectId,
                "s59-policy",
                new HashSet<string>(StringComparer.OrdinalIgnoreCase));

            File.Delete(sourceFile);
            var restored = new RestoreService(connectionString, new RouteRecoveryAuthorityResolver(connectionString)).RestorePrepared(
                context,
                snapshot.Manifest,
                source.FullName,
                destination.FullName,
                lease,
                "s59-content-restore-a");
            var recoveredFile = Path.Combine(destination.FullName, ".restore-current", "project.godot");
            var exactOriginalBytes = restored.Status == RestoreAttemptStatus.Published &&
                File.Exists(recoveredFile) &&
                originalBytes.SequenceEqual(File.ReadAllBytes(recoveredFile));

            Require(
                exactOriginalBytes,
                "FAILURE-O-C865A3100948",
                "A Snapshot did not restore its captured bytes to a fresh root after the source file was deleted.");
            _output.WriteLine("S59-OBSERVATION O-C865A3100948 snapshot-content-survives-source-loss");
        }
        finally
        {
            SqliteConnection.ClearAllPools();
            root.Delete(recursive: true);
        }
    }

    [Fact]
    public async Task O_824_LAST_PUBLISHED_RPO()
    {
        var root = Directory.CreateTempSubdirectory("s59-rpo-");
        try
        {
            var connectionString = await CreateDatabaseAsync(root.FullName, "s59-rpo");
            var (context, accountId, lease) = await CreateRestoreContextAsync(connectionString, root.FullName, "s59-rpo");
            var source = Directory.CreateDirectory(Path.Combine(root.FullName, "source"));
            var publishedDestination = Directory.CreateDirectory(Path.Combine(root.FullName, "published-a"));
            var destination = Directory.CreateDirectory(Path.Combine(root.FullName, "fresh-destination"));
            var publishedA = new byte[] { 0x41, 0x2D, 0x76, 0x31, 0x00, 0xFF };
            var unpublishedB = new byte[] { 0x42, 0x2D, 0x76, 0x32, 0x00, 0xFF };
            var sourceFile = Path.Combine(source.FullName, "project.godot");
            File.WriteAllBytes(sourceFile, publishedA);

            var storage = new WorkspaceStorageService(connectionString);
            storage.SetQuota(accountId, 1024 * 1024);
            var snapshotA = storage.CreateSnapshot(
                context,
                source.FullName,
                "s59-rpo-a",
                "s59-rpo-workspace",
                ProjectId,
                "s59-policy",
                new HashSet<string>(StringComparer.OrdinalIgnoreCase));

            var published = new RestoreService(connectionString, new RouteRecoveryAuthorityResolver(connectionString)).RestorePrepared(
                context,
                snapshotA.Manifest,
                source.FullName,
                publishedDestination.FullName,
                lease,
                "s59-rpo-publish-a");
            var publishedFile = Path.Combine(publishedDestination.FullName, ".restore-current", "project.godot");
            var aWasPublished = published.Status == RestoreAttemptStatus.Published &&
                File.Exists(publishedFile) &&
                publishedA.SequenceEqual(File.ReadAllBytes(publishedFile));

            storage.SetQuota(accountId, snapshotA.Manifest.ContentSize);
            File.WriteAllBytes(sourceFile, unpublishedB);
            var firstBPublicationInterrupted = SnapshotPublicationIsInterrupted(
                storage,
                context,
                source.FullName,
                "s59-rpo-b",
                "s59-rpo-workspace");
            var retryBPublicationRemainedIsolated = SnapshotPublicationIsInterrupted(
                storage,
                context,
                source.FullName,
                "s59-rpo-b-retry",
                "s59-rpo-workspace");

            storage.SetQuota(accountId, 1024 * 1024);
            File.Delete(sourceFile);
            var recoveryStore = CreateStore(connectionString, root.FullName);
            await recoveryStore.ReleaseRunnerLockAsync(ProjectId, lease.LeaseId);
            var recoveryRunId = await recoveryStore.CreateRunAsync(ProjectId, null, "s59-rpo-recovery-run");
            if (!await recoveryStore.TryAcquireRunnerLockAsync(ProjectId, recoveryRunId))
                throw new InvalidOperationException("The disposable S59 recovery runner lease could not be acquired.");
            var recoveryLease = await ReadLeaseAsync(connectionString, recoveryRunId)
                ?? throw new InvalidOperationException("The disposable S59 recovery runner lease could not be read.");
            var restored = new RestoreService(connectionString, new RouteRecoveryAuthorityResolver(connectionString)).RestorePrepared(
                context,
                snapshotA.Manifest,
                source.FullName,
                destination.FullName,
                recoveryLease,
                "s59-rpo-restore-a");
            var recoveredFile = Path.Combine(destination.FullName, ".restore-current", "project.godot");
            var recoveredPublishedA = restored.Status == RestoreAttemptStatus.Published &&
                File.Exists(recoveredFile) &&
                publishedA.SequenceEqual(File.ReadAllBytes(recoveredFile));

            Require(
                aWasPublished && firstBPublicationInterrupted && retryBPublicationRemainedIsolated && recoveredPublishedA,
                "FAILURE-O-824-LAST-PUBLISHED-RPO",
                "The last published Snapshot A was not recoverable after interrupted Snapshot B attempts and source loss.");
            _output.WriteLine("S59-OBSERVATION O-824-LAST-PUBLISHED-RPO last-published-a-survives-interrupted-b");
        }
        finally
        {
            SqliteConnection.ClearAllPools();
            root.Delete(recursive: true);
        }
    }

    private static bool SnapshotPublicationIsInterrupted(
        WorkspaceStorageService storage,
        RequestContext context,
        string sourceRoot,
        string snapshotId,
        string workspaceId)
    {
        try
        {
            storage.CreateSnapshot(
                context,
                sourceRoot,
                snapshotId,
                workspaceId,
                ProjectId,
                "s59-policy",
                new HashSet<string>(StringComparer.OrdinalIgnoreCase));
            return false;
        }
        catch (IOException)
        {
            return true;
        }
    }

    private static async Task<string> CreateDatabaseAsync(string root, string prefix)
    {
        var databasePath = Path.Combine(root, "metadata.sqlite3");
        var connectionString = new SqliteConnectionStringBuilder { DataSource = databasePath }.ToString();
        await SqliteMetadataSchema.InitializeAsync(connectionString);
        await new SqliteMigrationService().MigrateAsync(connectionString, $"{prefix}-account", ProjectId, $"{prefix}-migration");
        return connectionString;
    }

    private static async Task<(RequestContext Context, string AccountId, RunnerLease Lease)> CreateRestoreContextAsync(
        string connectionString,
        string root,
        string prefix)
    {
        var store = CreateStore(connectionString, root);
        var accountId = await CreateProjectAsync(store, connectionString, root, prefix);
        var leaseId = await store.CreateRunAsync(ProjectId, null, $"{prefix}-run");
        if (!await store.TryAcquireRunnerLockAsync(ProjectId, leaseId))
        {
            throw new InvalidOperationException("The disposable S59 runner lease could not be acquired.");
        }

        var lease = await ReadLeaseAsync(connectionString, leaseId)
            ?? throw new InvalidOperationException("The disposable S59 runner lease could not be read.");
        var context = RequestContext.FromIdentity(
            new AccountIdentity(accountId, "owner", PhaseAAuth.UserRole),
            $"{prefix}-principal",
            $"{prefix}-runtime-credential",
            $"{prefix}-correlation");
        return (context, accountId, lease);
    }

    private static PhaseAMetadataStore CreateStore(string connectionString, string workspaceRoot)
    {
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot,
        });
        return new PhaseAMetadataStore(connectionString, options);
    }

    private static async Task<string> CreateProjectAsync(PhaseAMetadataStore store, string connectionString, string root, string prefix)
    {
        var account = await store.CreateUserAccountAsync($"{prefix}-user-{Guid.NewGuid():N}", 1);
        var projectRoot = Directory.CreateDirectory(Path.Combine(root, "project"));
        var project = await store.CreateProjectAsync(new ProjectCreationCommand(
            ProjectId,
            account.AccountId,
            "S59 boundary",
            "S59 boundary",
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
            throw new InvalidOperationException("The disposable S59 project could not be created.");
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
