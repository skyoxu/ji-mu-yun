using System.Security.Cryptography;
using System.Text;
using Microsoft.Data.Sqlite;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S21BoundaryTests
{
    private readonly ITestOutputHelper _output;

    public S21BoundaryTests(ITestOutputHelper output) => _output = output;

    [Fact]
    public void O_0DA4D1A674FC() => Verify("O_0DA4D1A674FC", "FAILURE-O-0DA4D1A674FC", SnapshotBoundaryProbe.Capture, item => item.SecretExcluded, "Snapshot content or its manifest published the secret fixture value.");

    [Fact]
    public void O_254A534B34DC() => Verify("O_254A534B34DC", "FAILURE-O-254A534B34DC", SnapshotBoundaryProbe.Capture, item => item.TicketExcluded, "Snapshot content or its manifest published the temporary ticket fixture value.");

    [Fact]
    public void O_256764D63B41() => Verify("O_256764D63B41", "FAILURE-O-256764D63B41", SnapshotBoundaryProbe.Capture, item => item.GddIncluded, "Snapshot omitted the supported persistent GDD fixture bytes.");

    [Fact]
    public void O_333BFBBDD4E6() => Verify("O_333BFBBDD4E6", "FAILURE-O-333BFBBDD4E6", SnapshotBoundaryProbe.Capture, item => item.ModuleIncluded, "Snapshot omitted the supported persistent module fixture bytes.");

    [Fact]
    public void O_428F1AED1718() => Verify("O_428F1AED1718", "FAILURE-O-428F1AED1718", SnapshotBoundaryProbe.Capture, item => item.LinkTargetUntouched, "Snapshot traversal read or published the fixture link target.");

    [Fact]
    public void O_6927E3DB2340() => Verify("O_6927E3DB2340", "FAILURE-O-6927E3DB2340", SnapshotBoundaryProbe.Capture, item => item.CacheExcluded, "Snapshot content or its manifest published cache fixture bytes.");

    [Fact]
    public void O_7A7ADBD789E8() => Verify("O_7A7ADBD789E8", "FAILURE-O-7A7ADBD789E8", SnapshotBoundaryProbe.Capture, item => item.BuildExcluded, "Snapshot content or its manifest published build fixture bytes.");

    [Fact]
    public void O_54456853027B() => Verify("O_54456853027B", "FAILURE-O-54456853027B", QuotaProbe.Capture, item => item.UserQuotaRejected && item.OnlyInitialSnapshotExists, "Snapshot admission did not reject an account-scoped over-limit request before persistence.");

    [Fact]
    public void O_90F61CB8C839() => Verify("O_90F61CB8C839", "FAILURE-O-90F61CB8C839", VersionProbe.Capture, item => item.FirstManifestBytesUnchanged, "The first Snapshot manifest bytes changed after another version and an existing-ID request.");

    [Fact]
    public void O_CC9B0A135A23() => Verify("O_CC9B0A135A23", "FAILURE-O-CC9B0A135A23", VersionProbe.Capture, item => item.IndependentVersions && item.ExistingIdRejected && item.FirstManifestBytesUnchanged, "Snapshot history was not append-only and immutable across an existing-ID request.");

    [Fact]
    public void O_DAE26C389431() => Verify("O_DAE26C389431", "FAILURE-O-DAE26C389431", VersionProbe.Capture, item => item.FirstPayloadBytesUnchanged, "The first Snapshot protected content bytes changed after version creation, restart, or ID reuse.");

    [Fact]
    public void O_5743EDD3B96D() => Verify("O_5743EDD3B96D", "FAILURE-O-5743EDD3B96D", VersionProbe.Capture, item => item.FirstPolicyBytesUnchanged && item.NewSnapshotUsesNewPolicy, "Historical policy binding changed after restart or the new policy did not bind only the later Snapshot.");

    [Fact]
    public void O_6F2FD7753C43() => Verify("O_6F2FD7753C43", "FAILURE-O-6F2FD7753C43", VersionProbe.Capture, item => item.FirstPolicyBindingPresent && item.FirstPolicyBytesUnchanged, "Snapshot did not retain the active policy version as an immutable binding.");

    [Fact]
    public void O_ABFD538C2712() => Verify("O_ABFD538C2712", "FAILURE-O-ABFD538C2712", RetentionProbe.Capture, item => item.RetentionProfileIsThirtyDays, "The exercised retention boundary did not record the required 30-day profile.");

    [Fact]
    public void O_A59BCC9699EA() => Verify("O_A59BCC9699EA", "FAILURE-O-A59BCC9699EA", RetentionProbe.Capture, item => item.RestoreInputsRemainReadable, "Retention handling removed an input retained for restore readback.");

    [Fact]
    public void O_866209DC052D() => Verify("O_866209DC052D", "FAILURE-O-866209DC052D", RetentionProbe.Capture, item => item.ExpiryAuditRecorded, "The exercised retention boundary did not retain an expiry audit record.");

    [Fact]
    public void O_9E1B4D8DE8E7() => Verify("O_9E1B4D8DE8E7", "FAILURE-O-9E1B4D8DE8E7", RetentionProbe.Capture, item => item.CleanupAuditRecorded, "The exercised retention boundary did not retain a cleanup audit record.");

    private void Verify<T>(string caseName, string failureId, Func<T> capture, Func<T, bool> predicate, string message)
        where T : IS21Observation
    {
        using var observation = capture();
        var satisfied = predicate(observation);
        _output.WriteLine($"S21_OBSERVATION:{caseName}:{satisfied.ToString().ToLowerInvariant()}");
        Require(satisfied, failureId, message);
    }

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
    }

    private interface IS21Observation : IDisposable { }

    private sealed record class SnapshotBoundaryProbe : IS21Observation
    {
        private const string AccountId = "account-s21-boundary";
        private const string ProjectId = "project-s21-boundary";
        private const string SnapshotId = "snapshot-s21-boundary";
        private const string Secret = "s21-secret-fixture-value";
        private const string Ticket = "s21-temporary-ticket-value";
        private const string Cache = "s21-cache-fixture-value";
        private const string Build = "s21-build-fixture-value";
        private const string Gdd = "s21-supported-gdd-value";
        private const string Module = "s21-supported-module-value";
        private const string LinkTarget = "s21-outside-link-target-value";
        private readonly DirectoryInfo _root;
        private readonly DirectoryInfo _outside;
        private readonly string _databasePath;

        private SnapshotBoundaryProbe(DirectoryInfo root, DirectoryInfo outside, string databasePath)
        {
            _root = root;
            _outside = outside;
            _databasePath = databasePath;
        }

        public bool SecretExcluded { get; private init; }
        public bool TicketExcluded { get; private init; }
        public bool CacheExcluded { get; private init; }
        public bool BuildExcluded { get; private init; }
        public bool GddIncluded { get; private init; }
        public bool ModuleIncluded { get; private init; }
        public bool LinkTargetUntouched { get; private init; }

        public static SnapshotBoundaryProbe Capture()
        {
            var root = Directory.CreateTempSubdirectory("s21-boundary-");
            var outside = Directory.CreateTempSubdirectory("s21-outside-");
            var databasePath = Path.Combine(Path.GetTempPath(), $"s21-boundary-{Guid.NewGuid():N}.db");
            var probe = new SnapshotBoundaryProbe(root, outside, databasePath);
            try
            {
                probe.Write("gdd/game-design.md", Gdd);
                probe.Write("modules/player.module", Module);
                probe.Write("cache/local.cache", Cache);
                probe.Write("build/output.bin", Build);
                probe.Write("secrets/token.secret", Secret);
                probe.Write("tickets/capability.ticket", Ticket);
                var target = Path.Combine(outside.FullName, "outside.txt");
                File.WriteAllText(target, LinkTarget);
                var link = Path.Combine(root.FullName, "links", "outside-link");
                Directory.CreateDirectory(Path.GetDirectoryName(link)!);
                File.CreateSymbolicLink(link, target);
                probe.CreateProjectDatabase();

                var record = probe.CreateStorage().CreateSnapshot(probe.Context(), root.FullName, SnapshotId, "workspace-s21-boundary", ProjectId, "policy-s21-boundary", probe.Blacklist());
                var manifest = File.ReadAllText(record.ManifestPath);
                var payload = record.Manifest.ReadProtectedContent().SelectMany(item => item.Value).ToArray();
                var has = (string path, string value) => record.Manifest.Files.Any(file => file.RelativePath == path) && Contains(payload, value);
                var excludes = (string path, string value) => !record.Manifest.Files.Any(file => file.RelativePath == path) && !manifest.Contains(value, StringComparison.Ordinal) && !Contains(payload, value);
                return probe with
                {
                    GddIncluded = has("gdd/game-design.md", Gdd),
                    ModuleIncluded = has("modules/player.module", Module),
                    CacheExcluded = excludes("cache/local.cache", Cache),
                    BuildExcluded = excludes("build/output.bin", Build),
                    SecretExcluded = excludes("secrets/token.secret", Secret),
                    TicketExcluded = excludes("tickets/capability.ticket", Ticket),
                    LinkTargetUntouched = !record.Manifest.Files.Any(file => file.RelativePath == "links/outside-link") && !Contains(payload, LinkTarget) && !manifest.Contains(LinkTarget, StringComparison.Ordinal)
                };
            }
            catch
            {
                probe.Dispose();
                throw;
            }
        }

        public void Dispose()
        {
            SqliteConnection.ClearAllPools();
            if (_root.Exists) _root.Delete(true);
            if (_outside.Exists) _outside.Delete(true);
            if (File.Exists(_databasePath)) File.Delete(_databasePath);
        }

        private static bool Contains(byte[] payload, string value) => payload.AsSpan().IndexOf(Encoding.UTF8.GetBytes(value)) >= 0;

        private WorkspaceStorageService CreateStorage() => new($"Data Source={_databasePath}");
        private RequestContext Context() => RequestContext.FromIdentity(new AccountIdentity(AccountId, "s21", PhaseAAuth.UserRole), "principal-s21", "credential-s21", "correlation-s21");
        private HashSet<string> Blacklist() => new(StringComparer.OrdinalIgnoreCase) { ".cache", ".bin", ".secret", ".ticket" };

        private void Write(string relativePath, string value)
        {
            var path = Path.Combine(_root.FullName, relativePath);
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            File.WriteAllText(path, value);
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

    private sealed record class VersionProbe : IS21Observation
    {
        private const string AccountId = "account-s21-version";
        private const string ProjectId = "project-s21-version";
        private readonly DirectoryInfo _root;
        private readonly string _databasePath;

        private VersionProbe(DirectoryInfo root, string databasePath) { _root = root; _databasePath = databasePath; }

        public bool FirstManifestBytesUnchanged { get; private init; }
        public bool FirstPayloadBytesUnchanged { get; private init; }
        public bool IndependentVersions { get; private init; }
        public bool ExistingIdRejected { get; private init; }
        public bool FirstPolicyBindingPresent { get; private init; }
        public bool FirstPolicyBytesUnchanged { get; private init; }
        public bool NewSnapshotUsesNewPolicy { get; private init; }

        public static VersionProbe Capture()
        {
            var root = Directory.CreateTempSubdirectory("s21-version-");
            var databasePath = Path.Combine(Path.GetTempPath(), $"s21-version-{Guid.NewGuid():N}.db");
            var probe = new VersionProbe(root, databasePath);
            try
            {
                probe.Write("gdd/first.md", "s21-first-version-content");
                probe.CreateProjectDatabase();
                var storage = probe.CreateStorage();
                var first = storage.CreateSnapshot(probe.Context(), root.FullName, "snapshot-s21-first", "workspace-s21-version", ProjectId, "policy-s21-v1", probe.Blacklist());
                var firstManifest = File.ReadAllBytes(first.ManifestPath);
                var firstPayloadPath = Path.Combine(root.FullName, ".snapshots-snapshot-s21-first.protected");
                var firstPayload = File.ReadAllBytes(firstPayloadPath);
                var firstPolicy = Encoding.UTF8.GetBytes(first.Manifest.PolicyVersion);

                probe.Write("modules/second.module", "s21-second-version-content");
                storage.CreateSnapshot(probe.Context(), root.FullName, "snapshot-s21-second", "workspace-s21-version", ProjectId, "policy-s21-v1", probe.Blacklist());
                var rejected = false;
                try { storage.CreateSnapshot(probe.Context(), root.FullName, "snapshot-s21-first", "workspace-s21-version", ProjectId, "policy-s21-v1", probe.Blacklist()); }
                catch (InvalidOperationException) { rejected = true; }

                var restarted = probe.CreateStorage();
                restarted.CreateSnapshot(probe.Context(), root.FullName, "snapshot-s21-third", "workspace-s21-version", ProjectId, "policy-s21-v2", probe.Blacklist());
                var firstAfter = restarted.ListSnapshots(AccountId, ProjectId, includeDeleted: true).Single(record => record.Manifest.SnapshotId == "snapshot-s21-first");
                var thirdAfter = restarted.ListSnapshots(AccountId, ProjectId, includeDeleted: true).Single(record => record.Manifest.SnapshotId == "snapshot-s21-third");
                return probe with
                {
                    FirstManifestBytesUnchanged = firstManifest.AsSpan().SequenceEqual(File.ReadAllBytes(first.ManifestPath)),
                    FirstPayloadBytesUnchanged = firstPayload.AsSpan().SequenceEqual(File.ReadAllBytes(firstPayloadPath)),
                    IndependentVersions = restarted.ListSnapshots(AccountId, ProjectId, includeDeleted: true).Count == 3,
                    ExistingIdRejected = rejected,
                    FirstPolicyBindingPresent = firstAfter.Manifest.PolicyVersion == "policy-s21-v1",
                    FirstPolicyBytesUnchanged = firstPolicy.AsSpan().SequenceEqual(Encoding.UTF8.GetBytes(firstAfter.Manifest.PolicyVersion)),
                    NewSnapshotUsesNewPolicy = thirdAfter.Manifest.PolicyVersion == "policy-s21-v2"
                };
            }
            catch
            {
                probe.Dispose();
                throw;
            }
        }

        public void Dispose()
        {
            SqliteConnection.ClearAllPools();
            if (_root.Exists) _root.Delete(true);
            if (File.Exists(_databasePath)) File.Delete(_databasePath);
        }

        private WorkspaceStorageService CreateStorage() => new($"Data Source={_databasePath}");
        private RequestContext Context() => RequestContext.FromIdentity(new AccountIdentity(AccountId, "s21", PhaseAAuth.UserRole), "principal-s21", "credential-s21", "correlation-s21");
        private HashSet<string> Blacklist() => new(StringComparer.OrdinalIgnoreCase) { ".protected" };

        private void Write(string relativePath, string content)
        {
            var path = Path.Combine(_root.FullName, relativePath);
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            File.WriteAllText(path, content);
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

    private sealed record class QuotaProbe : IS21Observation
    {
        private const string AccountId = "account-s21-quota";
        private const string ProjectId = "project-s21-quota";
        private readonly DirectoryInfo _root;
        private readonly string _databasePath;

        private QuotaProbe(DirectoryInfo root, string databasePath) { _root = root; _databasePath = databasePath; }

        public bool UserQuotaRejected { get; private init; }
        public bool OnlyInitialSnapshotExists { get; private init; }

        public static QuotaProbe Capture()
        {
            var root = Directory.CreateTempSubdirectory("s21-quota-");
            var databasePath = Path.Combine(Path.GetTempPath(), $"s21-quota-{Guid.NewGuid():N}.db");
            var probe = new QuotaProbe(root, databasePath);
            try
            {
                probe.Write("project.godot", "s21-quota-bytes");
                probe.CreateProjectDatabase();
                var storage = probe.CreateStorage();
                storage.SetQuota(AccountId, Encoding.UTF8.GetByteCount("s21-quota-bytes"));
                storage.CreateSnapshot(probe.Context(), root.FullName, "snapshot-s21-quota-initial", "workspace-s21-quota", ProjectId, "policy-s21-quota", new HashSet<string>(StringComparer.OrdinalIgnoreCase));
                var rejected = false;
                try { storage.CreateSnapshot(probe.Context(), root.FullName, "snapshot-s21-quota-over-limit", "workspace-s21-quota", ProjectId, "policy-s21-quota", new HashSet<string>(StringComparer.OrdinalIgnoreCase)); }
                catch (IOException) { rejected = true; }
                return probe with
                {
                    UserQuotaRejected = rejected,
                    OnlyInitialSnapshotExists = storage.ListSnapshots(AccountId, ProjectId).Count == 1
                };
            }
            catch
            {
                probe.Dispose();
                throw;
            }
        }

        public void Dispose()
        {
            SqliteConnection.ClearAllPools();
            if (_root.Exists) _root.Delete(true);
            if (File.Exists(_databasePath)) File.Delete(_databasePath);
        }

        private WorkspaceStorageService CreateStorage() => new($"Data Source={_databasePath}");
        private RequestContext Context() => RequestContext.FromIdentity(new AccountIdentity(AccountId, "s21", PhaseAAuth.UserRole), "principal-s21", "credential-s21", "correlation-s21");
        private void Write(string relativePath, string content) => File.WriteAllText(Path.Combine(_root.FullName, relativePath), content);

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

    private sealed record class RetentionProbe : IS21Observation
    {
        private const string AccountId = "account-s21-retention";
        private const string ProjectId = "project-s21-retention";
        private readonly DirectoryInfo _root;
        private readonly string _databasePath;

        private RetentionProbe(DirectoryInfo root, string databasePath) { _root = root; _databasePath = databasePath; }

        public bool RetentionProfileIsThirtyDays { get; private init; }
        public bool RestoreInputsRemainReadable { get; private init; }
        public bool ExpiryAuditRecorded { get; private init; }
        public bool CleanupAuditRecorded { get; private init; }

        public static RetentionProbe Capture()
        {
            var root = Directory.CreateTempSubdirectory("s21-retention-");
            var databasePath = Path.Combine(Path.GetTempPath(), $"s21-retention-{Guid.NewGuid():N}.db");
            var probe = new RetentionProbe(root, databasePath);
            try
            {
                probe.Write("gdd/restore-input.md", "s21-retention-restore-input");
                probe.CreateProjectDatabase();
                var storage = probe.CreateStorage();
                var record = storage.CreateSnapshot(probe.Context(), root.FullName, "snapshot-s21-retention", "workspace-s21-retention", ProjectId, "policy-s21-retention", new HashSet<string>(StringComparer.OrdinalIgnoreCase));
                storage.SoftDeleteSnapshot(probe.Context(), record.Manifest.SnapshotId);
                var retained = storage.ListSnapshots(AccountId, ProjectId, includeDeleted: true).Single();
                return probe with
                {
                    RetentionProfileIsThirtyDays = retained.Manifest.Retention == "30-day",
                    RestoreInputsRemainReadable = retained.Deleted && retained.Manifest.Files.Any(file => file.RelativePath == "gdd/restore-input.md") && File.Exists(record.ManifestPath),
                    ExpiryAuditRecorded = probe.HasRetentionAudit("expiry"),
                    CleanupAuditRecorded = probe.HasRetentionAudit("cleanup")
                };
            }
            catch
            {
                probe.Dispose();
                throw;
            }
        }

        public void Dispose()
        {
            SqliteConnection.ClearAllPools();
            if (_root.Exists) _root.Delete(true);
            if (File.Exists(_databasePath)) File.Delete(_databasePath);
        }

        private bool HasRetentionAudit(string action)
        {
            using var connection = new SqliteConnection($"Data Source={_databasePath}");
            connection.Open();
            using var tables = connection.CreateCommand();
            tables.CommandText = "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='snapshot_retention_audit';";
            if (Convert.ToInt32(tables.ExecuteScalar()) != 1) return false;
            using var audit = connection.CreateCommand();
            audit.CommandText = "SELECT COUNT(*) FROM snapshot_retention_audit WHERE action=$action;";
            audit.Parameters.AddWithValue("$action", action);
            return Convert.ToInt32(audit.ExecuteScalar()) > 0;
        }

        private WorkspaceStorageService CreateStorage() => new($"Data Source={_databasePath}");
        private RequestContext Context() => RequestContext.FromIdentity(new AccountIdentity(AccountId, "s21", PhaseAAuth.UserRole), "principal-s21", "credential-s21", "correlation-s21");

        private void Write(string relativePath, string content)
        {
            var path = Path.Combine(_root.FullName, relativePath);
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            File.WriteAllText(path, content);
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
