using Microsoft.Data.Sqlite;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S61BoundaryTests
{
    private readonly ITestOutputHelper _output;

    public S61BoundaryTests(ITestOutputHelper output) => _output = output;

    [Fact]
    public void O_27A650DB20C0()
    {
        using var fixture = SnapshotPolicyFixture.Create();
        fixture.WriteSourceFile("retained.txt", "before-policy");
        fixture.WriteSourceFile("excluded.old", "excluded-before-policy");
        var historical = fixture.CreateSnapshot("s61-historical", "policy-s61-v1", [".old"]);
        var manifestBeforeActivation = File.ReadAllBytes(historical.ManifestPath);
        var contentBeforeActivation = historical.Manifest.ReadProtectedContent();

        fixture.WriteSourceFile("excluded.new", "excluded-after-policy");
        _ = fixture.CreateSnapshot("s61-current", "policy-s61-v2", [".new"]);

        var reloadedHistorical = fixture.Reload("s61-historical");
        var historicalUnchanged = manifestBeforeActivation.SequenceEqual(File.ReadAllBytes(reloadedHistorical.ManifestPath))
            && historical.Manifest.PolicyVersion == reloadedHistorical.Manifest.PolicyVersion
            && historical.Manifest.ContentExclusions.SequenceEqual(reloadedHistorical.Manifest.ContentExclusions)
            && historical.Manifest.Files.SequenceEqual(reloadedHistorical.Manifest.Files)
            && ContentEquals(contentBeforeActivation, reloadedHistorical.Manifest.ReadProtectedContent());

        Require(
            historicalUnchanged && reloadedHistorical.Manifest.PolicyVersion == "policy-s61-v1",
            "FAILURE-O-27A650DB20C0",
            "A historical Snapshot changed after a later extension policy version was used for Snapshot creation.");
        Observe("O-27A650DB20C0 historical-snapshot-manifest-content-hashes-exclusions-and-policy-binding-unchanged");
    }

    [Fact]
    public void O_3584E0AB2B63()
    {
        using var fixture = SnapshotPolicyFixture.Create();
        fixture.WriteSourceFile("allowed.txt", "allowed-content");
        fixture.WriteSourceFile("prohibited.blocked", "prohibited-content");
        var snapshot = fixture.CreateSnapshot("s61-filtered", "policy-s61-v2", [".blocked"]);
        var retained = snapshot.Manifest.ReadProtectedContent();

        var prohibitedRetained = snapshot.Manifest.Files.Any(file => file.RelativePath.EndsWith(".blocked", StringComparison.OrdinalIgnoreCase))
            || retained.Keys.Any(path => path.EndsWith(".blocked", StringComparison.OrdinalIgnoreCase));
        Require(
            snapshot.Manifest.PolicyVersion == "policy-s61-v2"
            && snapshot.Manifest.ContentExclusions.SequenceEqual([".blocked"])
            && !prohibitedRetained
            && retained.ContainsKey("allowed.txt"),
            "FAILURE-O-3584E0AB2B63",
            "A Snapshot retained a file prohibited by its bound extension policy or did not record that exclusion.");
        Observe("O-3584E0AB2B63 bound-policy-excludes-prohibited-content-from-manifest-and-retained-payload");
    }

    [Fact]
    public void O_4B79BCC985BE()
    {
        using var fixture = SnapshotPolicyFixture.Create();
        fixture.WriteSourceFile("before.txt", "before-content");
        fixture.WriteSourceFile("before.legacy", "legacy-content");
        var before = fixture.CreateSnapshot("s61-before", "policy-s61-v1", [".legacy"]);
        var beforeManifestBytes = File.ReadAllBytes(before.ManifestPath);

        fixture.WriteSourceFile("after.blocked", "blocked-after-change");
        var after = fixture.CreateSnapshot("s61-after", "policy-s61-v2", [".blocked"]);
        var reloaded = fixture.ReloadAll();
        var persistedBefore = reloaded.Single(snapshot => snapshot.Manifest.SnapshotId == "s61-before");
        var persistedAfter = reloaded.Single(snapshot => snapshot.Manifest.SnapshotId == "s61-after");

        var comparisonProvesScope = before.Manifest.PolicyVersion == "policy-s61-v1"
            && after.Manifest.PolicyVersion == "policy-s61-v2"
            && !before.Manifest.PolicyVersion.Equals(after.Manifest.PolicyVersion, StringComparison.Ordinal)
            && beforeManifestBytes.SequenceEqual(File.ReadAllBytes(persistedBefore.ManifestPath))
            && persistedBefore.Manifest.Files.SequenceEqual(before.Manifest.Files)
            && persistedBefore.Manifest.ContentExclusions.SequenceEqual(before.Manifest.ContentExclusions)
            && persistedAfter.Manifest.ContentExclusions.SequenceEqual([".blocked"])
            && persistedAfter.Manifest.Files.All(file => !file.RelativePath.EndsWith(".blocked", StringComparison.OrdinalIgnoreCase));

        Require(
            comparisonProvesScope,
            "FAILURE-O-4B79BCC985BE",
            "The persisted before-and-after Snapshot comparison did not prove policy scope without historical mutation.");
        Observe("O-4B79BCC985BE persisted-before-after-snapshot-comparison-proves-only-new-manifest-uses-new-policy");
    }

    [Fact]
    public void O_537551CF10EA()
    {
        using var fixture = SnapshotPolicyFixture.Create();
        fixture.WriteSourceFile("baseline.txt", "baseline-content");
        var prior = fixture.CreateSnapshot("s61-policy-v1", "policy-s61-v1", [".old"]);
        fixture.WriteSourceFile("new-policy.blocked", "new-policy-content");
        var active = fixture.CreateSnapshot("s61-policy-v2", "policy-s61-v2", [".blocked"]);
        var persisted = fixture.ReloadAll();
        var priorBinding = persisted.Single(snapshot => snapshot.Manifest.SnapshotId == prior.Manifest.SnapshotId).Manifest;
        var activeBinding = persisted.Single(snapshot => snapshot.Manifest.SnapshotId == active.Manifest.SnapshotId).Manifest;

        Require(
            priorBinding.PolicyVersion == "policy-s61-v1"
            && activeBinding.PolicyVersion == "policy-s61-v2"
            && !string.Equals(priorBinding.PolicyVersion, activeBinding.PolicyVersion, StringComparison.Ordinal)
            && activeBinding.ContentExclusions.SequenceEqual([".blocked"])
            && activeBinding.Files.All(file => !file.RelativePath.EndsWith(".blocked", StringComparison.OrdinalIgnoreCase)),
            "FAILURE-O-537551CF10EA",
            "The storage boundary did not retain distinct immutable policy-version bindings for prior and subsequent Snapshots.");
        Observe("O-537551CF10EA distinct-policy-version-bindings-retained-for-prior-and-subsequent-snapshots");
    }

    [Fact]
    public async Task O_B44C311965F3()
    {
        using var fixture = SnapshotPolicyFixture.Create();
        var inventoryBeforeTimer = fixture.ReloadAll().Count;
        var fired = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        using var timer = new Timer(_ => fired.TrySetResult(), null, TimeSpan.FromMilliseconds(25), Timeout.InfiniteTimeSpan);
        await fired.Task.WaitAsync(TimeSpan.FromSeconds(5));
        var inventoryAfterTimer = fixture.ReloadAll().Count;

        Require(
            inventoryBeforeTimer == 0 && inventoryAfterTimer == 0,
            "FAILURE-O-B44C311965F3",
            "Timer activity created a Snapshot without an explicit Snapshot creation request.");
        Observe("O-B44C311965F3 timer-activity-did-not-create-a-snapshot");
    }

    private void Observe(string observation) => _output.WriteLine($"S61-OBSERVATION {observation}");

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
        {
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
        }
    }

    private static bool ContentEquals(IReadOnlyDictionary<string, byte[]> expected, IReadOnlyDictionary<string, byte[]> actual) =>
        expected.Count == actual.Count
        && expected.All(entry => actual.TryGetValue(entry.Key, out var value) && entry.Value.SequenceEqual(value));

    private sealed class SnapshotPolicyFixture : IDisposable
    {
        private const string AccountId = "account-s61";
        private const string ProjectId = "project-s61";
        private const string WorkspaceId = "workspace-s61";
        private readonly DirectoryInfo _root;
        private readonly string _databasePath;

        private SnapshotPolicyFixture(DirectoryInfo root, string databasePath)
        {
            _root = root;
            _databasePath = databasePath;
        }

        public static SnapshotPolicyFixture Create()
        {
            var root = Directory.CreateTempSubdirectory("s61-boundary-");
            var databasePath = Path.Combine(Path.GetTempPath(), $"s61-{Guid.NewGuid():N}.db");
            var fixture = new SnapshotPolicyFixture(root, databasePath);
            fixture.CreateProjectDatabase();
            return fixture;
        }

        public void WriteSourceFile(string relativePath, string content)
        {
            var path = Path.Combine(_root.FullName, relativePath);
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            File.WriteAllText(path, content);
        }

        public WorkspaceSnapshotRecord CreateSnapshot(string snapshotId, string policyVersion, string[] blacklist)
        {
            var context = RequestContext.FromIdentity(
                new AccountIdentity(AccountId, "owner", PhaseAAuth.UserRole),
                "principal-s61",
                "credential-s61",
                "correlation-s61");
            return new WorkspaceStorageService($"Data Source={_databasePath}").CreateSnapshot(
                context,
                _root.FullName,
                snapshotId,
                WorkspaceId,
                ProjectId,
                policyVersion,
                new HashSet<string>(blacklist, StringComparer.OrdinalIgnoreCase));
        }

        public WorkspaceSnapshotRecord Reload(string snapshotId) =>
            ReloadAll().Single(snapshot => snapshot.Manifest.SnapshotId == snapshotId);

        public IReadOnlyList<WorkspaceSnapshotRecord> ReloadAll() =>
            new WorkspaceStorageService($"Data Source={_databasePath}").ListSnapshots(AccountId, ProjectId);

        public void Dispose()
        {
            SqliteConnection.ClearAllPools();
            if (_root.Exists)
            {
                _root.Delete(true);
            }

            if (File.Exists(_databasePath))
            {
                File.Delete(_databasePath);
            }
        }

        private void CreateProjectDatabase()
        {
            using var connection = new SqliteConnection($"Data Source={_databasePath}");
            connection.Open();
            using var command = connection.CreateCommand();
            command.CommandText = "CREATE TABLE projects (id TEXT PRIMARY KEY, account_id TEXT NOT NULL); INSERT INTO projects(id, account_id) VALUES ($project, $account);";
            command.Parameters.AddWithValue("$project", ProjectId);
            command.Parameters.AddWithValue("$account", AccountId);
            command.ExecuteNonQuery();
        }
    }
}
