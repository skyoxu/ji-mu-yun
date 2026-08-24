using FluentAssertions;
using Microsoft.Data.Sqlite;
using PhaseA.Platform.Data;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
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
}
