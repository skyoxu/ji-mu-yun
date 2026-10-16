using Microsoft.Data.Sqlite;
using PhaseA.Platform.Data;
using PhaseA.Platform.Workspaces;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S35BoundaryTests
{
    private readonly ITestOutputHelper _output;

    public S35BoundaryTests(ITestOutputHelper output)
    {
        _output = output;
    }

    [Fact]
    public async Task O_BF44FB067530()
    {
        var root = CreateDisposableRoot();
        try
        {
            var databasePath = Path.Combine(root.FullName, "metadata.sqlite3");
            var connectionString = new SqliteConnectionStringBuilder { DataSource = databasePath }.ToString();

            await SqliteMetadataSchema.InitializeAsync(connectionString);
            var operationRecord = await new SqliteMigrationService().MigrateAsync(
                connectionString,
                "s35-account",
                "s35-project",
                "s35-migration");
            if (operationRecord.Status != "completed" || operationRecord.OperationId.Length == 0)
            {
                throw new InvalidOperationException("The disposable production migration did not complete.");
            }

            var storage = new WorkspaceStorageService(connectionString);
            var snapshots = storage.ListSnapshots("s35-account", "s35-project", includeDeleted: true);

            Require(
                snapshots.Count == 0,
                "FAILURE-O-BF44FB067530",
                "Migration created a Snapshot without an explicit Snapshot request.");

            _output.WriteLine(
                "migration-status={0} operation-id={1} snapshot-inventory-count={2} correlation={3}",
                operationRecord.Status,
                operationRecord.OperationId,
                snapshots.Count,
                operationRecord.CorrelationId);
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

    private static DirectoryInfo CreateDisposableRoot()
    {
        var testRoot = Environment.GetEnvironmentVariable("S35_TEST_ROOT");
        if (string.IsNullOrWhiteSpace(testRoot) || !Directory.Exists(testRoot))
        {
            throw new InvalidOperationException("S35_TEST_ROOT must name an existing disposable test root.");
        }

        return Directory.CreateDirectory(Path.Combine(testRoot, $"s35-migration-{Guid.NewGuid():N}"));
    }
}
