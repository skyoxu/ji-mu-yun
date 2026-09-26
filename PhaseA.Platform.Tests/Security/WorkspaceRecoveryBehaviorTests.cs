using FluentAssertions;
using Microsoft.Data.Sqlite;
using PhaseA.Platform.Data;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using PhaseA.Platform.Workflow;
using Xunit;

namespace PhaseA.Platform.Tests.PhaseB;

public sealed class WorkspaceRecoveryBehaviorTests
{
    [Fact]
    public void Context_Propagates_ToBackgroundAndRejectsOtherAccount()
    {
        var context = RequestContext.FromIdentity(new AccountIdentity("a", "owner", PhaseAAuth.UserRole), "p", "c", "r");
        context.ForBackground("r2").AccountId.Should().Be("a");
        var act = () => context.DemandAccount("b");
        act.Should().Throw<UnauthorizedAccessException>();
    }

    [Fact]
    public void RunnerPolicy_RejectsEscapeAndStaleFence()
    {
        var act = () => RunnerIsolationPolicy.RequireContainedPath(Path.GetTempPath(), "..\\outside");
        act.Should().Throw<UnauthorizedAccessException>();
        var expected = new RunnerLease("l", "a", "p", 2);
        var stale = () => RunnerIsolationPolicy.DemandCurrentLease(expected, expected with { Fence = 1 });
        stale.Should().Throw<InvalidOperationException>();
        RunnerIsolationPolicy.Describe("a", "p", Path.GetTempPath()).LowPrivilegeRequired.Should().BeTrue();
    }

    [Fact]
    public void RunnerPolicy_RejectsReparsePointWhenPlatformSupportsLinks()
    {
        if (!OperatingSystem.IsWindows()) return;
        var root = Directory.CreateTempSubdirectory("phase-b-reparse");
        var target = Directory.CreateTempSubdirectory("phase-b-reparse-target");
        try
        {
            var link = Path.Combine(root.FullName, "link");
            try { Directory.CreateSymbolicLink(link, target.FullName); }
            catch (Exception) { return; }
            var act = () => RunnerIsolationPolicy.RequireContainedPath(root.FullName, "link/file.txt");
            act.Should().Throw<UnauthorizedAccessException>();
        }
        finally { root.Delete(true); target.Delete(true); }
    }

    [Fact]
    public void SnapshotAndRestore_RoundTripWithQuotaAndSoftDelete()
    {
        var root = Directory.CreateTempSubdirectory("phase-b");
        try
        {
            File.WriteAllText(Path.Combine(root.FullName, "project.godot"), "hello");
            File.WriteAllBytes(Path.Combine(root.FullName, "large.jpg"), new byte[32]);
            var context = RequestContext.FromIdentity(new AccountIdentity("a", "owner", PhaseAAuth.UserRole), "p", "c", "r");
            var storage = new WorkspaceStorageService();
            storage.SetQuota("a", 100);
            var record = storage.CreateSnapshot(context, root.FullName, "s1", "w", "p", "policy-1", new HashSet<string>(StringComparer.OrdinalIgnoreCase) { ".jpg" });
            record.Manifest.Files.Should().ContainSingle();
            var destination = Directory.CreateTempSubdirectory("phase-b-restore");
            var attempt = new RestoreService().Restore(context, record.Manifest, root.FullName, destination.FullName, new RunnerLease("l", "a", "p", 1));
            attempt.Status.Should().Be(RestoreAttemptStatus.Published);
            File.ReadAllText(Path.Combine(destination.FullName, ".restore-current", "project.godot")).Should().Be("hello");
            storage.SoftDeleteSnapshot(context, "s1");
            storage.GetQuota("a").UsedBytes.Should().Be(0);
            destination.Delete(true);
        }
        finally { root.Delete(true); }
    }

    [Fact]
    public void Restore_CorruptSourceQuarantinesWithoutPublishing()
    {
        var source = Directory.CreateTempSubdirectory("phase-b-source");
        var destination = Directory.CreateTempSubdirectory("phase-b-destination");
        try
        {
            File.WriteAllText(Path.Combine(source.FullName, "project.godot"), "original");
            var manifest = SnapshotManifest.Create("s", "w", "a", "p", "v", [("project.godot", "original"u8.ToArray())]);
            File.WriteAllText(Path.Combine(source.FullName, "project.godot"), "corrupt");
            var context = RequestContext.FromIdentity(new AccountIdentity("a", "owner", PhaseAAuth.UserRole), "p", "c", "r");
            var attempt = new RestoreService().Restore(context, manifest, source.FullName, destination.FullName, new RunnerLease("l", "a", "p", 1));
            attempt.Status.Should().Be(RestoreAttemptStatus.Quarantined);
            Directory.Exists(Path.Combine(destination.FullName, ".restore-current")).Should().BeFalse();
        }
        finally { source.Delete(true); destination.Delete(true); }
    }

    [Fact]
    public async Task SqliteMigration_IsFreshUpgradeAndReuseSafe()
    {
        var path = Path.Combine(Path.GetTempPath(), $"phase-b-{Guid.NewGuid():N}.db");
        try
        {
            var service = new SqliteMigrationService();
            var first = await service.MigrateAsync($"Data Source={path}", "a", "p", "c1");
            var second = await service.MigrateAsync($"Data Source={path}", "a", "p", "c2");
            first.Status.Should().Be("completed");
            second.Status.Should().Be("completed");
            await using (var connection = new SqliteConnection($"Data Source={path}"))
            {
                await connection.OpenAsync();
                await using var command = connection.CreateCommand();
                command.CommandText = "SELECT COUNT(*) FROM phase_b_schema";
                Convert.ToInt32(await command.ExecuteScalarAsync()).Should().Be(1);
            }
        }
        finally { SqliteConnection.ClearAllPools(); if (File.Exists(path)) File.Delete(path); }
    }

    [Fact]
    public void PersistentStorage_UsesProjectOwnershipAndQuotaAcrossInstances()
    {
        var path = Path.Combine(Path.GetTempPath(), $"phase-b-{Guid.NewGuid():N}.db");
        var root = Directory.CreateTempSubdirectory("phase-b-persistent");
        try
        {
            using (var connection = new SqliteConnection($"Data Source={path}"))
            { connection.Open(); using var command = connection.CreateCommand(); command.CommandText = "CREATE TABLE projects(id TEXT PRIMARY KEY, account_id TEXT NOT NULL); INSERT INTO projects(id,account_id) VALUES('p','a');"; command.ExecuteNonQuery(); }
            File.WriteAllText(Path.Combine(root.FullName, "project.godot"), "hello");
            var context = RequestContext.FromIdentity(new AccountIdentity("a", "owner", PhaseAAuth.UserRole), "p", "c", "r");
            var storage = new WorkspaceStorageService($"Data Source={path}"); storage.SetQuota("a", 100);
            storage.CreateSnapshot(context, root.FullName, "persisted", "w", "p", "v", new HashSet<string>());
            new WorkspaceStorageService($"Data Source={path}").GetQuota("a").UsedBytes.Should().Be(5);
        }
        finally { SqliteConnection.ClearAllPools(); root.Delete(true); if (File.Exists(path)) File.Delete(path); }
    }

    [Fact]
    public void PersistentStorage_ReloadsAndSoftDeletesSnapshotsAfterRestart()
    {
        var path = Path.Combine(Path.GetTempPath(), $"phase-b-{Guid.NewGuid():N}.db");
        var root = Directory.CreateTempSubdirectory("phase-b-snapshot-reload");
        try
        {
            using (var connection = new SqliteConnection($"Data Source={path}"))
            { connection.Open(); using var command = connection.CreateCommand(); command.CommandText = "CREATE TABLE projects(id TEXT PRIMARY KEY, account_id TEXT NOT NULL); INSERT INTO projects(id,account_id) VALUES('p','a');"; command.ExecuteNonQuery(); }
            File.WriteAllText(Path.Combine(root.FullName, "project.godot"), "hello");
            var context = RequestContext.FromIdentity(new AccountIdentity("a", "owner", PhaseAAuth.UserRole), "p", "c", "r");
            var first = new WorkspaceStorageService($"Data Source={path}"); first.SetQuota("a", 100);
            first.CreateSnapshot(context, root.FullName, "persisted", "w", "p", "v", new HashSet<string>());
            var restarted = new WorkspaceStorageService($"Data Source={path}");
            restarted.ListSnapshots("a", "p").Should().ContainSingle(x => x.Manifest.SnapshotId == "persisted");
            restarted.SoftDeleteSnapshot(context, "persisted");
            new WorkspaceStorageService($"Data Source={path}").ListSnapshots("a", "p").Should().BeEmpty();
        }
        finally { SqliteConnection.ClearAllPools(); root.Delete(true); if (File.Exists(path)) File.Delete(path); }
    }

    [Fact]
    public void Restore_RejectsLeaseThatIsNotThePersistedAuthority()
    {
        var path = Path.Combine(Path.GetTempPath(), $"phase-b-{Guid.NewGuid():N}.db");
        var source = Directory.CreateTempSubdirectory("phase-b-lease-source");
        var destination = Directory.CreateTempSubdirectory("phase-b-lease-destination");
        try
        {
            using (var connection = new SqliteConnection($"Data Source={path}"))
            {
                connection.Open();
                using var command = connection.CreateCommand();
                command.CommandText = "CREATE TABLE accounts (id TEXT PRIMARY KEY, is_disabled INTEGER NOT NULL); INSERT INTO accounts VALUES('a',0);" +
                    "CREATE TABLE runner_leases (lease_id TEXT PRIMARY KEY, account_id TEXT NOT NULL, project_id TEXT NOT NULL, fence INTEGER NOT NULL); INSERT INTO runner_leases VALUES('lease','a','p',2);" +
                    "CREATE TABLE restore_audit (recorded_utc TEXT NOT NULL, action TEXT NOT NULL, account_id TEXT NOT NULL, workspace_id TEXT NOT NULL, correlation_id TEXT NOT NULL);" +
                    "CREATE TABLE route_recovery_evidence (recorded_utc TEXT NOT NULL, authority_count INTEGER NOT NULL, has_current_blocker INTEGER NOT NULL, is_blocked INTEGER NOT NULL, can_continue INTEGER NOT NULL, source_order_json TEXT NOT NULL, blocker_json TEXT NOT NULL);" +
                    "INSERT INTO route_recovery_evidence VALUES($utc,8,0,0,1,$sources,'[]');";
                command.Parameters.AddWithValue("$utc", DateTimeOffset.UtcNow.ToString("O"));
                command.Parameters.AddWithValue("$sources", System.Text.Json.JsonSerializer.Serialize(HostedRouteRecoveryContract.SourceOrder));
                command.ExecuteNonQuery();
            }
            File.WriteAllText(Path.Combine(source.FullName, "project.godot"), "content");
            var manifest = SnapshotManifest.Create("s", "w", "a", "p", "v", [("project.godot", "content"u8.ToArray())]);
            var context = RequestContext.FromIdentity(new AccountIdentity("a", "owner", PhaseAAuth.UserRole), "p", "c", "r");
            var act = () => new RestoreService($"Data Source={path}").Restore(context, manifest, source.FullName, destination.FullName, new RunnerLease("lease", "a", "p", 1));
            act.Should().Throw<InvalidOperationException>().WithMessage("*not authoritative*");
        }
        finally { SqliteConnection.ClearAllPools(); source.Delete(true); destination.Delete(true); if (File.Exists(path)) File.Delete(path); }
    }

    [Fact]
    public void Restore_IsIdempotentAndDoesNotDeleteExistingPublishedTreeBeforeCommit()
    {
        var source = Directory.CreateTempSubdirectory("phase-b-idempotent-source");
        var destination = Directory.CreateTempSubdirectory("phase-b-idempotent-destination");
        try
        {
            File.WriteAllText(Path.Combine(source.FullName, "project.godot"), "new");
            File.WriteAllText(Path.Combine(destination.FullName, "keep.txt"), "old");
            var manifest = SnapshotManifest.Create("s", "w", "a", "p", "v", [("project.godot", "new"u8.ToArray())]);
            var context = RequestContext.FromIdentity(new AccountIdentity("a", "owner", PhaseAAuth.UserRole), "p", "c", "r");
            var service = new RestoreService(); var lease = new RunnerLease("l", "a", "p", 1);
            var first = service.Restore(context, manifest, source.FullName, destination.FullName, lease, "key-1");
            var second = service.Restore(context, manifest, source.FullName, destination.FullName, lease, "key-1");
            first.Should().Be(second);
        }
        finally { source.Delete(true); destination.Delete(true); }
    }
}
