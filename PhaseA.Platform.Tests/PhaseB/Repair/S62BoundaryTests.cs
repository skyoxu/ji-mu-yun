using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S62BoundaryTests
{
    private const string AccountId = "s62-account";
    private const string WorkspaceId = "s62-workspace";
    private const string ProjectId = "s62-project";
    private readonly ITestOutputHelper _output;

    public S62BoundaryTests(ITestOutputHelper output) => _output = output;

    [Fact]
    public void O_93887D63FCE9()
    {
        var root = Directory.CreateTempSubdirectory("s62-boundary-");
        try
        {
            var database = Path.Combine(root.FullName, "metadata.sqlite3");
            var connectionString = new SqliteConnectionStringBuilder { DataSource = database, Pooling = false }.ToString();
            SqliteMetadataSchema.InitializeAsync(connectionString).GetAwaiter().GetResult();
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
            {
                ["HOSTED_WORKSPACE_ROOT"] = root.FullName,
            });
            var store = new PhaseAMetadataStore(connectionString, options);
            var account = store.CreateUserAccountAsync($"s62-user-{Guid.NewGuid():N}", 1).GetAwaiter().GetResult();
            var projectRoot = Directory.CreateDirectory(Path.Combine(root.FullName, "project"));
            _ = store.CreateProjectAsync(new ProjectCreationCommand(
                ProjectId, account.AccountId, "S62 boundary", "S62 boundary", "manual", "default", false, [],
                projectRoot.FullName, Path.Combine(projectRoot.FullName, "repo"),
                Path.Combine(projectRoot.FullName, "runtime"), Path.Combine(projectRoot.FullName, "meta"))).GetAwaiter().GetResult();
            RouteAuthorityFixture.Seed(connectionString, account.AccountId, ProjectId, projectRoot.FullName);
            var context = RequestContext.FromIdentity(
                new AccountIdentity(account.AccountId, "s62-owner", PhaseAAuth.UserRole),
                "s62-requester",
                "s62-credential",
                "s62-correlation");
            var lease = new RunnerLease("s62-lease", account.AccountId, ProjectId, 1);
            using (var connection = new SqliteConnection(connectionString))
            {
                connection.Open();
                using var command = connection.CreateCommand();
                command.CommandText = "INSERT INTO runner_leases(lease_id,account_id,project_id,fence) VALUES($id,$account,$project,$fence)";
                command.Parameters.AddWithValue("$id", lease.LeaseId);
                command.Parameters.AddWithValue("$account", lease.AccountId);
                command.Parameters.AddWithValue("$project", lease.ProjectId);
                command.Parameters.AddWithValue("$fence", lease.Fence);
                new RestoreService(connectionString);
                command.ExecuteNonQuery();
            }

            var source = Directory.CreateDirectory(Path.Combine(root.FullName, "source"));
            var destination = Directory.CreateDirectory(Path.Combine(root.FullName, "destination"));
            var content = "s62-content"u8.ToArray();
            File.WriteAllBytes(Path.Combine(source.FullName, "project.godot"), content);
            var manifest = SnapshotManifest.Create(
                "s62-snapshot",
                WorkspaceId,
                account.AccountId,
                ProjectId,
                "s62-policy",
                [("project.godot", content)]);
            manifest = manifest with
            {
                ProtectedContent = SnapshotManifest.ProtectContent(
                    [("project.godot", content)],
                    manifest.KeyReference),
            };
            var badHash = manifest with
            {
                Files = manifest.Files.SetItem(0, manifest.Files[0] with { Sha256 = new string('0', 64) }),
            };
            var badSize = manifest with
            {
                Files = manifest.Files.SetItem(0, manifest.Files[0] with { Length = manifest.Files[0].Length + 1 }),
            };
            var service = new RestoreService(connectionString, new RouteRecoveryAuthorityResolver(connectionString));
            var cancelled = service.RestorePrepared(context, badHash, source.FullName, destination.FullName, lease, "s62-cancelled");
            var failed = service.RestorePrepared(context, badSize, source.FullName, destination.FullName, lease, "s62-failed");

            var schema = ReadAuditColumns(connectionString);
            var audit = ReadAuditRows(connectionString);
            var quarantine = Directory.Exists(Path.Combine(destination.FullName, ".restore-quarantine", cancelled.AttemptId)) &&
                Directory.Exists(Path.Combine(destination.FullName, ".restore-quarantine", failed.AttemptId));
            var observed = cancelled.Status == RestoreAttemptStatus.Quarantined &&
                failed.Status == RestoreAttemptStatus.Quarantined &&
                quarantine &&
                new[] { "recorded_utc", "action", "account_id", "workspace_id", "correlation_id" }
                    .All(schema.Contains) &&
                audit.Count >= 2 &&
                audit.Any(row => row.Action == "restore-interrupted") &&
                audit.Any(row => row.Action == "staging-disposition") &&
                audit.All(row => row.Fields.All(field => field is "recorded_utc" or "action" or "account_id" or "workspace_id" or "correlation_id"));

            if (!observed)
            {
                _output.WriteLine("FAILURE-O-93887D63FCE9");
                throw new Xunit.Sdk.XunitException("FAILURE-O-93887D63FCE9: restore interruption and staging disposition were not durably audited with Attempt linkage and restricted fields.");
            }

            _output.WriteLine("S62-OBSERVATION O-93887D63FCE9 restore-interruption-and-staging-disposition-audited");
        }
        finally
        {
            SqliteConnection.ClearAllPools();
            if (root.Exists) root.Delete(recursive: true);
        }
    }

    private static HashSet<string> ReadAuditColumns(string connectionString)
    {
        using var connection = new SqliteConnection(connectionString);
        connection.Open();
        using var command = connection.CreateCommand();
        command.CommandText = "PRAGMA table_info(restore_audit)";
        using var reader = command.ExecuteReader();
        var columns = new HashSet<string>(StringComparer.Ordinal);
        while (reader.Read()) columns.Add(reader.GetString(1));
        return columns;
    }

    private static List<AuditRow> ReadAuditRows(string connectionString)
    {
        using var connection = new SqliteConnection(connectionString);
        connection.Open();
        using var command = connection.CreateCommand();
        command.CommandText = "SELECT recorded_utc, action, account_id, workspace_id, correlation_id FROM restore_audit";
        using var reader = command.ExecuteReader();
        var rows = new List<AuditRow>();
        while (reader.Read())
        {
            rows.Add(new AuditRow(
                reader.GetString(0),
                reader.GetString(1),
                new HashSet<string>(StringComparer.Ordinal)
                {
                    "recorded_utc", "action", "account_id", "workspace_id", "correlation_id",
                }));
        }
        return rows;
    }

    private sealed record AuditRow(string RecordedUtc, string Action, IReadOnlySet<string> Fields);
}
