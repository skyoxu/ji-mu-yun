using System.Text;
using Microsoft.Data.Sqlite;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

[Collection("PhaseA snapshot environment")]
public sealed class S22BoundaryTests
{
    private readonly ITestOutputHelper _output;

    public S22BoundaryTests(ITestOutputHelper output) => _output = output;

    [Fact]
    public void O_D6DA22255508()
    {
        using var probe = SnapshotProtectionProbe.Create();
        var observation = probe.CreateSnapshot();
        _output.WriteLine($"S22_OBSERVATION:keyReference={observation.KeyReference};mechanism={observation.Mechanism};protectedPayload={observation.HasProtectedPayload.ToString().ToLowerInvariant()};recovered={observation.RecoveredOriginalBytes.ToString().ToLowerInvariant()}");

        Require(
            observation.KeyReference.StartsWith("keyref-", StringComparison.Ordinal)
            && observation.Mechanism == SnapshotProtectionProbe.Mechanism
            && observation.HasProtectedPayload
            && observation.RecoveredOriginalBytes,
            "FAILURE-O-D6DA22255508",
            "Snapshot storage did not retain an AES-256-GCM protected payload recoverable through its selected key-reference profile.");
    }

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
    }

    private sealed class SnapshotProtectionProbe : IDisposable
    {
        public const string Mechanism = "AES-256-GCM";
        private const string SnapshotId = "snapshot-s22";
        private const string WorkspaceId = "workspace-s22";
        private const string AccountId = "account-s22";
        private const string ProjectId = "project-s22";
        private static readonly byte[] Plaintext = Encoding.UTF8.GetBytes("s22 nonempty bounded fixture payload");
        private readonly DirectoryInfo _root;
        private readonly string _databasePath;
        private readonly string? _previousKeyRoot;

        private SnapshotProtectionProbe(DirectoryInfo root, string databasePath, string? previousKeyRoot)
        {
            _root = root;
            _databasePath = databasePath;
            _previousKeyRoot = previousKeyRoot;
        }

        public static SnapshotProtectionProbe Create()
        {
            var root = Directory.CreateTempSubdirectory("s22-boundary-");
            var databasePath = Path.Combine(Path.GetTempPath(), $"s22-{Guid.NewGuid():N}.db");
            var previousKeyRoot = Environment.GetEnvironmentVariable("PHASEA_SNAPSHOT_KEY_ROOT");
            Environment.SetEnvironmentVariable("PHASEA_SNAPSHOT_KEY_ROOT", Path.Combine(root.FullName, "keys"));
            var probe = new SnapshotProtectionProbe(root, databasePath, previousKeyRoot);
            var fixturePath = Path.Combine(root.FullName, "content", "fixture.bin");
            Directory.CreateDirectory(Path.GetDirectoryName(fixturePath)!);
            File.WriteAllBytes(fixturePath, Plaintext);
            probe.CreateProjectDatabase();
            return probe;
        }

        public SnapshotProtectionObservation CreateSnapshot()
        {
            var context = RequestContext.FromIdentity(
                new AccountIdentity(AccountId, "owner", PhaseAAuth.UserRole),
                "principal-s22",
                "credential-s22",
                "correlation-s22");
            var storage = new WorkspaceStorageService($"Data Source={_databasePath}");
            var record = storage.CreateSnapshot(
                context,
                _root.FullName,
                SnapshotId,
                WorkspaceId,
                ProjectId,
                "policy-s22",
                new HashSet<string>(StringComparer.OrdinalIgnoreCase));
            var artifacts = Directory.EnumerateFiles(_root.FullName, $".snapshots-{SnapshotId}.*", SearchOption.TopDirectoryOnly)
                .Where(path => !StringComparer.OrdinalIgnoreCase.Equals(path, record.ManifestPath))
                .ToArray();

            var hasProtectedPayload = artifacts.Length == 1;
            var mechanism = "missing";
            var recoveredOriginalBytes = false;
            if (hasProtectedPayload)
            {
                var payload = File.ReadAllBytes(artifacts[0]);
                mechanism = payload.AsSpan().StartsWith("S22-AES-256-GCM-V1\0"u8) ? Mechanism : "unknown";
                hasProtectedPayload = payload.AsSpan().IndexOf(Plaintext) < 0;
                recoveredOriginalBytes = record.Manifest.ReadProtectedContent().TryGetValue("content/fixture.bin", out var content)
                    && content.AsSpan().SequenceEqual(Plaintext);
            }

            return new SnapshotProtectionObservation(record.Manifest.KeyReference, mechanism, hasProtectedPayload, recoveredOriginalBytes);
        }

        public void Dispose()
        {
            Environment.SetEnvironmentVariable("PHASEA_SNAPSHOT_KEY_ROOT", _previousKeyRoot);
            SqliteConnection.ClearAllPools();
            if (_root.Exists)
                _root.Delete(true);
            if (File.Exists(_databasePath))
                File.Delete(_databasePath);
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

    private sealed record SnapshotProtectionObservation(string KeyReference, string Mechanism, bool HasProtectedPayload, bool RecoveredOriginalBytes);
}
