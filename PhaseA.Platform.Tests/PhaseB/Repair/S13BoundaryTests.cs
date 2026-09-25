using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S13BoundaryTests
{
    private readonly ITestOutputHelper _output;

    public S13BoundaryTests(ITestOutputHelper output)
    {
        _output = output;
    }

    [Fact]
    public void O_14E737AA22E2()
    {
        var source = Directory.CreateTempSubdirectory("s13-secret-source");
        var destination = Directory.CreateTempSubdirectory("s13-secret-destination");
        var databasePath = Path.Combine(Path.GetTempPath(), $"s13-secret-{Guid.NewGuid():N}.db");
        try
        {
            File.WriteAllText(Path.Combine(source.FullName, "project.godot"), "restored");
            var connectionString = $"Data Source={databasePath}";
            var accountId = CreateRestoreAccountAndProject(connectionString, source.FullName, "project-secret");
            var manifest = SnapshotManifest.Create(
                "snapshot-secret",
                "workspace-secret",
                accountId,
                "project-secret",
                "policy-restore",
                [("project.godot", "restored"u8.ToArray())]);
            manifest = manifest with
            {
                ProtectedContent = SnapshotManifest.ProtectContent(
                    [("project.godot", "restored"u8.ToArray())], manifest.KeyReference)
            };
            var oldSecret = RequestContext.FromIdentity(
                new AccountIdentity(accountId, "owner", PhaseAAuth.UserRole),
                "principal-old",
                "pre-restore-secret",
                "correlation-old");
            var currentSecret = RequestContext.FromIdentity(
                new AccountIdentity(accountId, "owner", PhaseAAuth.UserRole),
                "principal-current",
                "post-restore-secret",
                "correlation-current");
            var lease = new RunnerLease("lease-secret", accountId, "project-secret", 1);

            using (var connection = new SqliteConnection(connectionString))
            {
                connection.Open();
                using var command = connection.CreateCommand();
                command.CommandText = "INSERT INTO runner_leases(lease_id,account_id,project_id,fence) VALUES ($lease,$account,$project,$fence);";
                command.Parameters.AddWithValue("$lease", lease.LeaseId);
                command.Parameters.AddWithValue("$account", accountId);
                command.Parameters.AddWithValue("$project", lease.ProjectId);
                command.Parameters.AddWithValue("$fence", lease.Fence);
                command.ExecuteNonQuery();
            }
            var service = new RestoreService(connectionString);
            var currentAttempt = service.Restore(
                currentSecret,
                manifest,
                source.FullName,
                destination.FullName,
                lease,
                "current-secret");
            var oldRejected = false;
            try
            {
                service.Restore(oldSecret, manifest, source.FullName, destination.FullName, lease, "old-secret");
            }
            catch (UnauthorizedAccessException)
            {
                oldRejected = true;
            }
            var currentEnabled = currentAttempt.Status == RestoreAttemptStatus.Published &&
                File.ReadAllText(Path.Combine(destination.FullName, ".restore-current", "project.godot")) == "restored";
            if (oldRejected)
                _output.WriteLine("S13-OBSERVATION O-14E737AA22E2 pre-restore-secret-rejected");
            Require(currentEnabled, "FAILURE-O-14E737AA22E2", "Current restore credential did not enable the restored runtime.");
            Require(oldRejected, "FAILURE-O-14E737AA22E2", "Pre-restore credential remained authoritative after restore.");
        }
        finally
        {
            SqliteConnection.ClearAllPools();
            source.Delete(true);
            destination.Delete(true);
            if (File.Exists(databasePath)) File.Delete(databasePath);
        }
    }

    [Fact]
    public void O_6D37E601F3EB_DriftBlocked()
    {
        RunDriftScenario("O-6D37E601F3EB", "move-policy", requireRepairedPublication: false);
    }

    [Fact]
    public void O_6D37E601F3EB_RepairedPublished()
    {
        RunDriftScenario("O-6D37E601F3EB", "move-policy", requireRepairedPublication: true);
    }

    [Fact]
    public void O_8736D23A1BAF_DriftBlocked()
    {
        RunDriftScenario("O-8736D23A1BAF", "upgrade-policy", requireRepairedPublication: false);
    }

    [Fact]
    public void O_8736D23A1BAF_RepairedPublished()
    {
        RunDriftScenario("O-8736D23A1BAF", "upgrade-policy", requireRepairedPublication: true);
    }

    [Fact]
    public void O_F17C15697A79()
    {
        var databasePath = Path.Combine(Path.GetTempPath(), $"s13-lease-{Guid.NewGuid():N}.db");
        var source = Directory.CreateTempSubdirectory("s13-lease-source");
        var destination = Directory.CreateTempSubdirectory("s13-lease-destination");
        try
        {
            var connectionString = $"Data Source={databasePath}";
            var accountId = CreateRestoreAccountAndProject(connectionString, source.FullName, "project-lease");
            using (var connection = new SqliteConnection(connectionString))
            {
                connection.Open();
                using var command = connection.CreateCommand();
                command.CommandText = "INSERT INTO runner_leases(lease_id,account_id,project_id,fence) VALUES ('lease-stale',$account,'project-lease',1);";
                command.Parameters.AddWithValue("$account", accountId);
                command.ExecuteNonQuery();
            }

            File.WriteAllText(Path.Combine(source.FullName, "project.godot"), "before");
            var manifest = SnapshotManifest.Create(
                "snapshot-lease",
                "workspace-lease",
                accountId,
                "project-lease",
                "policy-lease",
                [("project.godot", "before"u8.ToArray())]);
            manifest = manifest with
            {
                ProtectedContent = SnapshotManifest.ProtectContent(
                    [("project.godot", "before"u8.ToArray())], manifest.KeyReference)
            };
            var context = RequestContext.FromIdentity(
                new AccountIdentity(accountId, "owner", PhaseAAuth.UserRole),
                "principal-lease",
                "secret-lease",
                "correlation-lease");
            var staleLease = new RunnerLease("lease-stale", accountId, "project-lease", 1);
            var service = new RestoreService(connectionString);
            var first = service.Restore(context, manifest, source.FullName, destination.FullName, staleLease, "lease-first");
            Require(first.Status == RestoreAttemptStatus.Published, "FAILURE-O-F17C15697A79", "Initial restore did not publish its staged result.");

            using (var connection = new SqliteConnection(connectionString))
            {
                connection.Open();
                using var command = connection.CreateCommand();
                command.CommandText = "UPDATE runner_leases SET fence = 2 WHERE lease_id = 'lease-stale';";
                command.ExecuteNonQuery();
            }

            var staleRejected = false;
            try
            {
                service.Restore(context, manifest, source.FullName, destination.FullName, staleLease, "lease-stale-retry");
            }
            catch (InvalidOperationException error) when (error.Message.Contains("not authoritative", StringComparison.Ordinal))
            {
                staleRejected = true;
            }

            var publishedContent = File.ReadAllText(Path.Combine(destination.FullName, ".restore-current", "project.godot"));
            if (staleRejected && publishedContent == "before")
                _output.WriteLine("S13-OBSERVATION O-F17C15697A79 stale-lease-publication-denied");
            Require(staleRejected, "FAILURE-O-F17C15697A79", "A superseded lease reached the publication boundary.");
            Require(publishedContent == "before", "FAILURE-O-F17C15697A79", "Stale restore content replaced the current publication.");
        }
        finally
        {
            SqliteConnection.ClearAllPools();
            source.Delete(true);
            destination.Delete(true);
            if (File.Exists(databasePath)) File.Delete(databasePath);
        }
    }

    private void RunDriftScenario(string observationId, string policyVersion, bool requireRepairedPublication)
    {
        var databasePath = Path.Combine(Path.GetTempPath(), $"s13-drift-{Guid.NewGuid():N}.db");
        var root = Directory.CreateTempSubdirectory("s13-drift-root");
        try
        {
            var connectionString = $"Data Source={databasePath}";
            using (var connection = new SqliteConnection(connectionString))
            {
                connection.Open();
                using var command = connection.CreateCommand();
                command.CommandText = "CREATE TABLE projects (id TEXT PRIMARY KEY, account_id TEXT NOT NULL); INSERT INTO projects VALUES ('project-drift', 'account-drift'); CREATE TABLE workspace_repair_audit (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, action TEXT NOT NULL);";
                command.ExecuteNonQuery();
            }

            File.WriteAllText(Path.Combine(root.FullName, "project.godot"), policyVersion);
            var context = RequestContext.FromIdentity(
                new AccountIdentity("account-drift", "owner", PhaseAAuth.UserRole),
                "principal-drift",
                "secret-drift",
                "correlation-drift");
            var storage = new WorkspaceStorageService(connectionString);
            storage.SetQuota("account-drift", 1_000_000);

            SetProjectOwner(connectionString, "drifted-owner");
            var driftRejected = !TryCreateSnapshot(storage, context, root.FullName, "drift-first", policyVersion);
            var retryRejected = !TryCreateSnapshot(storage, context, root.FullName, "drift-retry", policyVersion);

            SetProjectOwner(connectionString, "account-drift");
            var unrepairedRejected = !TryCreateSnapshot(storage, context, root.FullName, "before-audit-repair", policyVersion);
            InsertRepairAudit(connectionString, observationId);
            var repairedPublished = TryCreateSnapshot(storage, context, root.FullName, "after-audit-repair", policyVersion);
            var auditRecorded = HasRepairAudit(connectionString, observationId);

            if (driftRejected)
                _output.WriteLine($"S13-OBSERVATION {observationId} drift-blocked");
            if (driftRejected && retryRejected && unrepairedRejected && repairedPublished && auditRecorded)
                _output.WriteLine($"S13-OBSERVATION {observationId} repaired-published");
            Require(driftRejected, $"FAILURE-{observationId}", "Permission drift was publishable.");
            if (requireRepairedPublication)
            {
                Require(retryRejected, $"FAILURE-{observationId}", "A retry bypassed the drift block.");
                Require(unrepairedRejected, $"FAILURE-{observationId}", "Owner restoration without an audited repair released publication.");
                Require(repairedPublished && auditRecorded, $"FAILURE-{observationId}", "Audited repair did not release publication.");
            }
        }
        finally
        {
            SqliteConnection.ClearAllPools();
            root.Delete(true);
            if (File.Exists(databasePath)) File.Delete(databasePath);
        }
    }

    private static bool TryCreateSnapshot(WorkspaceStorageService storage, RequestContext context, string root, string snapshotId, string policyVersion)
    {
        try
        {
            storage.CreateSnapshot(context, root, snapshotId, "workspace-drift", "project-drift", policyVersion, new HashSet<string>(StringComparer.OrdinalIgnoreCase));
            return true;
        }
        catch (UnauthorizedAccessException)
        {
            return false;
        }
    }

    private static string CreateRestoreAccountAndProject(string connectionString, string sourceRoot, string projectId)
    {
        // ADR-0061: restore probes require production-created account and project metadata.
        SqliteMetadataSchema.InitializeAsync(connectionString).GetAwaiter().GetResult();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = sourceRoot,
        });
        var store = new PhaseAMetadataStore(connectionString, options);
        var account = store.CreateUserAccountAsync($"s13-user-{Guid.NewGuid():N}", 1).GetAwaiter().GetResult();
        var projectRoot = Directory.CreateDirectory(Path.Combine(sourceRoot, "metadata-project"));
        _ = store.CreateProjectAsync(new ProjectCreationCommand(
            projectId, account.AccountId, "S13 boundary", "S13 boundary", "manual", "default", false, [],
            projectRoot.FullName, Path.Combine(projectRoot.FullName, "repo"),
            Path.Combine(projectRoot.FullName, "runtime"), Path.Combine(projectRoot.FullName, "meta"))).GetAwaiter().GetResult();
        _ = new RestoreService(connectionString);
        return account.AccountId;
    }

    private static void SetProjectOwner(string connectionString, string accountId)
    {
        using var connection = new SqliteConnection(connectionString);
        connection.Open();
        using var command = connection.CreateCommand();
        command.CommandText = "UPDATE projects SET account_id = $account WHERE id = 'project-drift';";
        command.Parameters.AddWithValue("$account", accountId);
        command.ExecuteNonQuery();
    }

    private static void InsertRepairAudit(string connectionString, string observationId)
    {
        using var connection = new SqliteConnection(connectionString);
        connection.Open();
        using var command = connection.CreateCommand();
        command.CommandText = "INSERT INTO workspace_repair_audit VALUES ($id, 'project-drift', 'protected-owner-repair');";
        command.Parameters.AddWithValue("$id", observationId);
        command.ExecuteNonQuery();
    }

    private static bool HasRepairAudit(string connectionString, string observationId)
    {
        using var connection = new SqliteConnection(connectionString);
        connection.Open();
        using var command = connection.CreateCommand();
        command.CommandText = "SELECT COUNT(*) FROM workspace_repair_audit WHERE id = $id AND action = 'protected-owner-repair';";
        command.Parameters.AddWithValue("$id", observationId);
        return Convert.ToInt32(command.ExecuteScalar()) == 1;
    }

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
    }
}
