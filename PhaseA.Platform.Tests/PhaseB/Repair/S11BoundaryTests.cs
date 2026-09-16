using Microsoft.Data.Sqlite;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S11BoundaryTests
{
    private readonly ITestOutputHelper _output;

    public S11BoundaryTests(ITestOutputHelper output)
    {
        _output = output;
    }

    [Fact]
    public void O_1869C360A137()
    {
        var databasePath = CreateProjectDatabase("account-read", "project-read");
        var root = Directory.CreateTempSubdirectory("s11-read-root");
        try
        {
            File.WriteAllText(Path.Combine(root.FullName, "project.godot"), "read-content");
            var context = CreateContext("account-read");
            var connectionString = $"Data Source={databasePath}";
            var storage = new WorkspaceStorageService(connectionString);
            storage.CreateSnapshot(
                context,
                root.FullName,
                "snapshot-read",
                "workspace-read",
                "project-read",
                "policy-read",
                new HashSet<string>(StringComparer.OrdinalIgnoreCase));

            var restarted = new WorkspaceStorageService(connectionString);
            var records = restarted.ListSnapshots("account-read", "project-read");
            var record = records.SingleOrDefault();
            var valid = record is not null
                && record.Manifest.SnapshotId == "snapshot-read"
                && record.Manifest.WorkspaceId == "workspace-read"
                && record.Manifest.AccountId == "account-read"
                && record.Manifest.ProjectId == "project-read"
                && record.Manifest.Files.Length == 1
                && record.Manifest.Files[0].RelativePath == "project.godot";
            Require(valid, "FAILURE-O-1869C360A137", "Logical-ID read did not return the persisted snapshot data.");
            _output.WriteLine("S11-OBSERVATION O-1869C360A137 logical-id-read-through-storage-contract");
        }
        finally
        {
            SqliteConnection.ClearAllPools();
            root.Delete(true);
            DeleteDatabase(databasePath);
        }
    }

    [Fact]
    public void O_1FA17D58FC4E()
    {
        var databasePath = CreateProjectDatabase("account-lifecycle", "project-lifecycle");
        var root = Directory.CreateTempSubdirectory("s11-lifecycle-root");
        try
        {
            File.WriteAllText(Path.Combine(root.FullName, "project.godot"), "lifecycle-content");
            var context = CreateContext("account-lifecycle");
            var storage = new WorkspaceStorageService($"Data Source={databasePath}");
            storage.CreateSnapshot(
                context,
                root.FullName,
                "snapshot-lifecycle",
                "workspace-lifecycle",
                "project-lifecycle",
                "policy-lifecycle",
                new HashSet<string>(StringComparer.OrdinalIgnoreCase));

            storage.SoftDeleteSnapshot(context, "snapshot-lifecycle");
            var active = storage.ListSnapshots("account-lifecycle", "project-lifecycle");
            var all = storage.ListSnapshots("account-lifecycle", "project-lifecycle", includeDeleted: true);
            var deleted = all.SingleOrDefault();
            var valid = active.Count == 0
                && deleted is not null
                && deleted.Deleted
                && deleted.Manifest.SnapshotId == "snapshot-lifecycle"
                && deleted.Manifest.AccountId == "account-lifecycle"
                && deleted.Manifest.ProjectId == "project-lifecycle";
            Require(valid, "FAILURE-O-1FA17D58FC4E", "Logical-ID lifecycle validation did not report the deleted state.");
            _output.WriteLine("S11-OBSERVATION O-1FA17D58FC4E logical-id-lifecycle-state-validated");
        }
        finally
        {
            SqliteConnection.ClearAllPools();
            root.Delete(true);
            DeleteDatabase(databasePath);
        }
    }

    [Fact]
    public void O_D7C47A840DC6()
    {
        var databasePath = CreateProjectDatabase("account-drill", "project-drill");
        var root = Directory.CreateTempSubdirectory("s11-drill-root");
        var destination = Directory.CreateTempSubdirectory("s11-drill-destination");
        try
        {
            File.WriteAllText(Path.Combine(root.FullName, "project.godot"), "representative-content");
            var context = CreateContext("account-drill");
            var storage = new WorkspaceStorageService($"Data Source={databasePath}");
            var snapshot = storage.CreateSnapshot(
                context,
                root.FullName,
                "snapshot-drill",
                "workspace-drill",
                "project-drill",
                "policy-drill",
                new HashSet<string>(StringComparer.OrdinalIgnoreCase));
            var attempt = new RestoreService().Restore(
                context,
                snapshot.Manifest,
                root.FullName,
                destination.FullName,
                new RunnerLease("lease-drill", "account-drill", "project-drill", 1));
            var restoredPath = Path.Combine(destination.FullName, ".restore-current", "project.godot");
            var valid = snapshot.Manifest.Files.Length >= 1
                && attempt.Status == RestoreAttemptStatus.Published
                && File.Exists(restoredPath)
                && File.ReadAllText(restoredPath) == "representative-content";
            Require(valid, "FAILURE-O-D7C47A840DC6", "The substitute-root drill did not use and restore nonempty fixture content.");
            _output.WriteLine("S11-OBSERVATION O-D7C47A840DC6 nonempty-representative-fixture-restored");
        }
        finally
        {
            SqliteConnection.ClearAllPools();
            root.Delete(true);
            destination.Delete(true);
            DeleteDatabase(databasePath);
        }
    }

    [Fact]
    public void O_E48E57DFA6A1()
    {
        var databasePath = CreateProjectDatabase("account-count", "project-count");
        var root = Directory.CreateTempSubdirectory("s11-count-root");
        try
        {
            File.WriteAllText(Path.Combine(root.FullName, "project.godot"), "bounded-content");
            var context = CreateContext("account-count");
            var storage = new WorkspaceStorageService($"Data Source={databasePath}");
            var snapshot = storage.CreateSnapshot(
                context,
                root.FullName,
                "snapshot-count",
                "workspace-count",
                "project-count",
                "policy-count",
                new HashSet<string>(StringComparer.OrdinalIgnoreCase));
            var fixtureFileCount = snapshot.Manifest.Files.Length;
            var valid = fixtureFileCount >= 1 && fixtureFileCount <= 10_000;
            Require(valid, "FAILURE-O-E48E57DFA6A1", "The representative fixture exceeded the 10,000-file bound.");
            _output.WriteLine("S11-OBSERVATION O-E48E57DFA6A1 representative-fixture-within-file-bound");
        }
        finally
        {
            SqliteConnection.ClearAllPools();
            root.Delete(true);
            DeleteDatabase(databasePath);
        }
    }

    private static RequestContext CreateContext(string accountId)
    {
        return RequestContext.FromIdentity(
            new AccountIdentity(accountId, "owner", PhaseAAuth.UserRole),
            $"principal-{accountId}",
            $"credential-{accountId}",
            $"correlation-{accountId}");
    }

    private static string CreateProjectDatabase(string accountId, string projectId)
    {
        var path = Path.Combine(Path.GetTempPath(), $"s11-{Guid.NewGuid():N}.db");
        using var connection = new SqliteConnection($"Data Source={path}");
        connection.Open();
        using var command = connection.CreateCommand();
        command.CommandText = "CREATE TABLE projects (id TEXT PRIMARY KEY, account_id TEXT NOT NULL); INSERT INTO projects(id, account_id) VALUES ($project, $account);";
        command.Parameters.AddWithValue("$project", projectId);
        command.Parameters.AddWithValue("$account", accountId);
        command.ExecuteNonQuery();
        return path;
    }

    private static void DeleteDatabase(string path)
    {
        if (File.Exists(path))
            File.Delete(path);
    }

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
    }
}
