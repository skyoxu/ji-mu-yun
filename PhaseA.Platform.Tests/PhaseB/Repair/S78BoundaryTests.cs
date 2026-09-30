using System.Security.Cryptography;
using System.Text.Json;
using Microsoft.Data.Sqlite;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S78BoundaryTests
{
    private readonly ITestOutputHelper _output;

    public S78BoundaryTests(ITestOutputHelper output) => _output = output;

    [Fact]
    public void O_005AF027AF20() => Verify("O_005AF027AF20", "FAILURE-O-005AF027AF20", observation =>
        observation.HasField("PlatformCompatibilityVersion", "platformCompatibilityVersion")
        && observation.HasField("StorageCompatibilityVersion", "storageCompatibilityVersion"),
        "Published manifest did not declare platform and storage compatibility versions.");

    [Fact]
    public void O_0B827B3F1DF8() => Verify("O_0B827B3F1DF8", "FAILURE-O-0B827B3F1DF8", observation =>
        observation.HasField("KeyReference", "keyReference") && observation.HasNoPlaintextKey,
        "Published manifest did not retain a key reference without plaintext key material.");

    [Fact]
    public void O_1A6001B8457D() => Verify("O_1A6001B8457D", "FAILURE-O-1A6001B8457D", observation =>
        observation.FieldEquals("ProjectId", "projectId", SnapshotProbe.ProjectId),
        "Published manifest did not retain the authoritative Project ID.");

    [Fact]
    public void O_39F52FDEF1AA()
    {
        using var probe = SnapshotProbe.Create();
        Require(probe.HasCompleteMixedInventory, "FAILURE-O-39F52FDEF1AA", "Mixed fixture did not contain every required category.");
        Observe("O_39F52FDEF1AA");
    }

    [Fact]
    public void O_48F7894B3810() => Verify("O_48F7894B3810", "FAILURE-O-48F7894B3810", observation =>
        observation.HasOpaqueKeyReference
        && observation.HasNoPlaintextKey,
        "Published manifest did not prove the accepted key-reference boundary.");

    [Fact]
    public void O_4B55B33561ED() => Verify("O_4B55B33561ED", "FAILURE-O-4B55B33561ED", observation => observation.HasNoPlaintextKey,
        "Published Snapshot artifact disclosed the fixture plaintext key.");

    [Fact]
    public void O_637B22FBD097() => Verify("O_637B22FBD097", "FAILURE-O-637B22FBD097", observation =>
        observation.HasField("RecoveryRebuildInstructions", "recoveryRebuildInstructions"),
        "Published manifest did not declare recovery rebuild instructions.");

    [Fact]
    public void O_71211D09ED69() => Verify("O_71211D09ED69", "FAILURE-O-71211D09ED69", observation => observation.HasContentHashes,
        "Published manifest did not bind its content inventory with hashes.");

    [Fact]
    public void O_77C69533E116() => Verify("O_77C69533E116", "FAILURE-O-77C69533E116", observation =>
        observation.FieldEquals("SnapshotId", "snapshotId", SnapshotProbe.SnapshotId),
        "Published manifest did not retain a stable Snapshot ID.");

    [Fact]
    public void O_9F0B8CFD82B0() => Verify("O_9F0B8CFD82B0", "FAILURE-O-9F0B8CFD82B0", observation =>
        !observation.ManifestText.Contains(SnapshotProbe.AbsolutePathValue, StringComparison.Ordinal)
        && !observation.HasFile(SnapshotProbe.AbsolutePathFixture),
        "Published Snapshot contained the absolute-path fixture value.");

    [Fact]
    public void O_A0B263A78B53() => Verify("O_A0B263A78B53", "FAILURE-O-A0B263A78B53", observation =>
        observation.HasExactFile(SnapshotProbe.SourceFixture),
        "Published Snapshot omitted supported persistent source data.");

    [Fact]
    public void O_A1E96696878A() => Verify("O_A1E96696878A", "FAILURE-O-A1E96696878A", observation =>
        observation.HasField("ContentExclusions", "contentExclusions"),
        "Published manifest did not declare content exclusions.");

    [Fact]
    public void O_BD6AC3F538D6() => Verify("O_BD6AC3F538D6", "FAILURE-O-BD6AC3F538D6", observation =>
        observation.HasField("Creator", "creator", "CreatedBy", "createdBy"),
        "Published manifest did not record creator provenance.");

    [Fact]
    public void O_C099736647B3() => Verify("O_C099736647B3", "FAILURE-O-C099736647B3", observation =>
        observation.HasField("Retention", "retention", "RetentionState", "retentionState"),
        "Published manifest did not record retention information.");

    [Fact]
    public void O_CA969AA27571() => Verify("O_CA969AA27571", "FAILURE-O-CA969AA27571", observation =>
        observation.HasField("CreationAction", "creationAction"),
        "Published manifest did not record creation-action provenance.");

    [Fact]
    public void O_CC8E549073FD() => Verify("O_CC8E549073FD", "FAILURE-O-CC8E549073FD", observation =>
        observation.HasField("ContentInventory", "contentInventory", "Files", "files"),
        "Published manifest did not record a normalized content inventory.");

    [Fact]
    public void O_CF08C5874978() => Verify("O_CF08C5874978", "FAILURE-O-CF08C5874978", observation =>
        observation.HasField("CreatedAt", "createdAt", "CreationTime", "creationTime"),
        "Published manifest did not record creation-time provenance.");

    [Fact]
    public void O_CF9A089A1346() => Verify("O_CF9A089A1346", "FAILURE-O-CF9A089A1346", observation =>
        observation.FieldEquals("AccountId", "accountId", SnapshotProbe.AccountId),
        "Published manifest did not retain the authoritative Account ID.");

    [Fact]
    public void O_D61408107A00() => Verify("O_D61408107A00", "FAILURE-O-D61408107A00", observation =>
        observation.HasExactFile(SnapshotProbe.TestFixture),
        "Published Snapshot omitted supported persistent test data.");

    [Fact]
    public void O_DAF232D67D56() => Verify("O_DAF232D67D56", "FAILURE-O-DAF232D67D56", observation =>
        observation.HasField("RecoveryConditions", "recoveryConditions")
        && observation.HasField("RecoveryPrerequisites", "recoveryPrerequisites"),
        "Published manifest did not declare recovery conditions and prerequisites.");

    [Fact]
    public void O_DB654A6BD822() => Verify("O_DB654A6BD822", "FAILURE-O-DB654A6BD822", observation =>
        observation.FieldEquals("WorkspaceId", "workspaceId", SnapshotProbe.WorkspaceId),
        "Published manifest did not retain a stable Workspace ID.");

    [Fact]
    public void O_DEFE8E5A41DF() => Verify("O_DEFE8E5A41DF", "FAILURE-O-DEFE8E5A41DF", observation =>
        !observation.HasFile(SnapshotProbe.LinkFixture),
        "Published Snapshot followed or recorded the fixture link.");

    [Fact]
    public void O_EBA99C7FA89E() => Verify("O_EBA99C7FA89E", "FAILURE-O-EBA99C7FA89E", observation => observation.HasNoPlaintextKey,
        "Published manifest disclosed the fixture plaintext key.");

    [Fact]
    public void O_ED827B133807() => Verify("O_ED827B133807", "FAILURE-O-ED827B133807", observation =>
        observation.HasField("ContentSize", "contentSize", "ContentSizeBytes", "contentSizeBytes"),
        "Published manifest did not record aggregate content size information.");

    [Fact]
    public void O_EF1F883CB07E() => Verify("O_EF1F883CB07E", "FAILURE-O-EF1F883CB07E", observation =>
        observation.HasField("OwnershipPolicyReference", "ownershipPolicyReference")
        && observation.HasField("AclPolicyReference", "aclPolicyReference"),
        "Published manifest did not reference ownership and ACL policy.");

    [Fact]
    public void O_EF2EB8ED143C() => Verify("O_EF2EB8ED143C", "FAILURE-O-EF2EB8ED143C", observation =>
        observation.HasField("SchemaVersion", "schemaVersion"),
        "Published manifest did not declare its schema version.");

    [Fact]
    public void O_824_SNAPSHOT_PLAN_CONTENT() => Verify("O_824_SNAPSHOT_PLAN_CONTENT", "FAILURE-O-824-SNAPSHOT-PLAN-CONTENT", observation =>
        observation.HasExactFile(SnapshotProbe.PlanFixture),
        "Published Snapshot did not retain the exact supported plan/project-work bytes.");

    [Fact]
    public void O_824_SNAPSHOT_APPROVED_ASSETS() => Verify("O_824_SNAPSHOT_APPROVED_ASSETS", "FAILURE-O-824-SNAPSHOT-APPROVED-ASSETS", observation =>
        observation.HasExactFile(SnapshotProbe.ApprovedAssetFixture) && !observation.HasFile(SnapshotProbe.UnsafeAssetFixture),
        "Published Snapshot did not retain the approved asset while excluding blacklisted content.");

    private void Verify(string caseName, string failureId, Func<SnapshotObservation, bool> predicate, string message)
    {
        using var probe = SnapshotProbe.Create();
        var observation = probe.Publish();
        Require(predicate(observation), failureId, message);
        Observe(caseName);
    }

    private void Observe(string caseName) => _output.WriteLine($"S78-OBSERVATION {caseName} snapshot-boundary-verified");

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
    }

    private sealed class SnapshotProbe : IDisposable
    {
        public const string AccountId = "account-s78";
        public const string ProjectId = "project-s78";
        public const string WorkspaceId = "workspace-s78";
        public const string SnapshotId = "snapshot-s78";
        public const string PlaintextKey = "fixture-plaintext-key-not-for-production";
        public const string AbsolutePathValue = "C:\\snapshot-fixture\\outside-root";
        public const string SourceFixture = "src/main.cs";
        public const string TestFixture = "tests/main_tests.cs";
        public const string PlanFixture = "project-work/recovery-plan.md";
        public const string ApprovedAssetFixture = "assets/approved.png";
        public const string UnsafeAssetFixture = "assets/unsafe.exe";
        public const string AbsolutePathFixture = "metadata/absolute-path.absolute";
        public const string LinkFixture = "links/fixture-link";

        private readonly DirectoryInfo _root;
        private readonly string _databasePath;
        private readonly Dictionary<string, byte[]> _expectedFiles;

        private SnapshotProbe(DirectoryInfo root, string databasePath, Dictionary<string, byte[]> expectedFiles)
        {
            _root = root;
            _databasePath = databasePath;
            _expectedFiles = expectedFiles;
        }

        public bool HasCompleteMixedInventory => new[]
        {
            "gdd/game-design.md", "modules/player.module", SourceFixture, TestFixture, "artifacts/build-report.asset",
            "cache/local.cache", "build/output.bin", "temporary/scratch.tmp", "secrets/credential.secret",
            "tickets/incident.ticket", AbsolutePathFixture, LinkFixture
        }.All(path => File.Exists(Path.Combine(_root.FullName, path)))
        && (File.GetAttributes(Path.Combine(_root.FullName, LinkFixture)) & FileAttributes.ReparsePoint) != 0;

        public static SnapshotProbe Create()
        {
            var root = Directory.CreateTempSubdirectory("s78-boundary-");
            var databasePath = Path.Combine(Path.GetTempPath(), $"s78-{Guid.NewGuid():N}.db");
            var expectedFiles = new Dictionary<string, byte[]>(StringComparer.Ordinal);
            var probe = new SnapshotProbe(root, databasePath, expectedFiles);
            probe.Write("gdd/game-design.md", "gdd-content");
            probe.Write("modules/player.module", "module-content");
            probe.Write(SourceFixture, "source-content");
            probe.Write(TestFixture, "test-content");
            probe.Write("artifacts/build-report.asset", "artifact-content");
            probe.Write(PlanFixture, "plan-content-exact");
            probe.Write(ApprovedAssetFixture, "approved-asset-bytes");
            probe.Write(UnsafeAssetFixture, "unsafe-asset-bytes");
            probe.Write("cache/local.cache", "cache-content");
            probe.Write("build/output.bin", "build-content");
            probe.Write("temporary/scratch.tmp", "temporary-content");
            probe.Write("secrets/credential.secret", PlaintextKey);
            probe.Write("tickets/incident.ticket", "ticket-content");
            probe.Write(AbsolutePathFixture, AbsolutePathValue);
            var linkPath = Path.Combine(root.FullName, LinkFixture);
            Directory.CreateDirectory(Path.GetDirectoryName(linkPath)!);
            File.CreateSymbolicLink(linkPath, Path.Combine(root.FullName, SourceFixture));
            probe.CreateProjectDatabase();
            return probe;
        }

        public SnapshotObservation Publish()
        {
            var context = RequestContext.FromIdentity(
                new AccountIdentity(AccountId, "owner", PhaseAAuth.UserRole),
                "principal-s78",
                "credential-s78",
                "correlation-s78");
            var storage = new WorkspaceStorageService($"Data Source={_databasePath}");
            var blacklist = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
            {
                ".cache", ".bin", ".tmp", ".secret", ".ticket", ".absolute", ".exe"
            };
            var record = storage.CreateSnapshot(context, _root.FullName, SnapshotId, WorkspaceId, ProjectId, "policy-s78", blacklist);
            return new SnapshotObservation(record, File.ReadAllText(record.ManifestPath), _expectedFiles);
        }

        public void Dispose()
        {
            SqliteConnection.ClearAllPools();
            if (_root.Exists)
                _root.Delete(true);
            if (File.Exists(_databasePath))
                File.Delete(_databasePath);
        }

        private void Write(string relativePath, string content)
        {
            var bytes = System.Text.Encoding.UTF8.GetBytes(content);
            var path = Path.Combine(_root.FullName, relativePath);
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            File.WriteAllBytes(path, bytes);
            _expectedFiles.Add(relativePath, bytes);
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

    private sealed class SnapshotObservation
    {
        private readonly WorkspaceSnapshotRecord _record;
        private readonly JsonDocument _document;
        private readonly IReadOnlyDictionary<string, byte[]> _expectedFiles;

        public SnapshotObservation(WorkspaceSnapshotRecord record, string manifestText, IReadOnlyDictionary<string, byte[]> expectedFiles)
        {
            _record = record;
            ManifestText = manifestText;
            _document = JsonDocument.Parse(manifestText);
            _expectedFiles = expectedFiles;
        }

        public string ManifestText { get; }

        public bool HasNoPlaintextKey => !ManifestText.Contains(SnapshotProbe.PlaintextKey, StringComparison.Ordinal);
        public bool HasOpaqueKeyReference =>
            _record.Manifest.KeyReference.StartsWith("keyref-", StringComparison.Ordinal) &&
            _record.Manifest.KeyReference.Length > "keyref-".Length;

        public bool HasContentHashes => _record.Manifest.Files.Length > 0
            && _record.Manifest.Files.All(file => file.Sha256.Length == 64 && file.Sha256.All(Uri.IsHexDigit));

        public bool HasFile(string relativePath) => _record.Manifest.Files.Any(file =>
            StringComparer.Ordinal.Equals(file.RelativePath, relativePath));

        public bool HasExactFile(string relativePath) => _expectedFiles.TryGetValue(relativePath, out var expected)
            && _record.Manifest.Files.Any(file => StringComparer.Ordinal.Equals(file.RelativePath, relativePath)
                && StringComparer.Ordinal.Equals(file.Sha256, Convert.ToHexString(SHA256.HashData(expected)).ToLowerInvariant())
                && file.Length == expected.LongLength);

        public bool HasField(params string[] names) => names.Any(name =>
            _document.RootElement.TryGetProperty(name, out var value) && HasValue(value));

        public bool FieldEquals(string firstName, string secondName, string expected) =>
            TryGetString(firstName, out var first) && StringComparer.Ordinal.Equals(first, expected)
            || TryGetString(secondName, out var second) && StringComparer.Ordinal.Equals(second, expected);

        private bool TryGetString(string name, out string? value)
        {
            value = null;
            if (!_document.RootElement.TryGetProperty(name, out var element) || element.ValueKind != JsonValueKind.String)
                return false;
            value = element.GetString();
            return !string.IsNullOrWhiteSpace(value);
        }

        private static bool HasValue(JsonElement value) => value.ValueKind switch
        {
            JsonValueKind.String => !string.IsNullOrWhiteSpace(value.GetString()),
            JsonValueKind.Array => value.GetArrayLength() > 0,
            JsonValueKind.Object => value.EnumerateObject().Any(),
            JsonValueKind.Number => true,
            JsonValueKind.True => true,
            _ => false
        };
    }
}
