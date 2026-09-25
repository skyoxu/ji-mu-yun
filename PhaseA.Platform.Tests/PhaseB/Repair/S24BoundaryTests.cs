using System.Security.Cryptography;
using System.Text;
using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S24BoundaryTests
{
    private readonly ITestOutputHelper _output;

    public S24BoundaryTests(ITestOutputHelper output) => _output = output;

    [Fact]
    public void O_43E456451EF0()
    {
        var manifest = S24Fixture.CreateProtectedManifest();
        var plaintextKey = SHA256.HashData(Encoding.UTF8.GetBytes($"s22-static-profile/{manifest.KeyReference}"));
        var readback = manifest.ProtectedContent!;
        var noPlaintextKey = readback.AsSpan().IndexOf(plaintextKey) < 0;

        Require(
            noPlaintextKey,
            "FAILURE-O-43E456451EF0",
            "Snapshot readback exposed the plaintext encryption key.");
        _output.WriteLine($"S24_OBSERVATION:O-43E456451EF0;noPlaintextKey={noPlaintextKey.ToString().ToLowerInvariant()}");
    }

    [Fact]
    public void O_86F8F24B801C()
    {
        using var fixture = S24Fixture.CreateWithUnavailableKey();
        var attempt = fixture.Restore();
        var persistedStatus = fixture.ReadAttemptStatus();
        var published = fixture.IsPublished();
        var blocked = attempt.Status == RestoreAttemptStatus.Quarantined && persistedStatus == nameof(RestoreAttemptStatus.Quarantined) && !published;

        Require(
            blocked,
            "FAILURE-O-86F8F24B801C",
            "Restore published a workspace or did not quarantine the attempt when its required key was unavailable.");
        _output.WriteLine($"S24_OBSERVATION:O-86F8F24B801C;blocked={blocked.ToString().ToLowerInvariant()};published={published.ToString().ToLowerInvariant()};attemptStatus={persistedStatus}");
    }

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
    }

    private sealed class S24Fixture : IDisposable
    {
        private const string AccountId = "s24-account";
        private const string ProjectId = "s24-project";
        private const string WorkspaceId = "s24-workspace";
        private const string IdempotencyKey = "s24-required-key-unavailable";
        private static readonly (string RelativePath, byte[] Content)[] Files = [("project.godot", "s24 protected content"u8.ToArray())];

        private S24Fixture(string root, string connectionString, SnapshotManifest manifest, RequestContext context, RunnerLease lease)
        {
            Root = root;
            ConnectionString = connectionString;
            Manifest = manifest;
            Context = context;
            Lease = lease;
            SourceRoot = Directory.CreateDirectory(Path.Combine(root, "source")).FullName;
            DestinationRoot = Directory.CreateDirectory(Path.Combine(root, "destination")).FullName;
        }

        public string Root { get; }
        public string ConnectionString { get; }
        public SnapshotManifest Manifest { get; }
        public RequestContext Context { get; }
        public RunnerLease Lease { get; }
        public string SourceRoot { get; }
        public string DestinationRoot { get; }

        public static SnapshotManifest CreateProtectedManifest()
        {
            var manifest = SnapshotManifest.Create("s24-snapshot", WorkspaceId, AccountId, ProjectId, "policy-s24", Files);
            return manifest with { ProtectedContent = SnapshotManifest.ProtectContent(Files, manifest.KeyReference) };
        }

        public static S24Fixture CreateWithUnavailableKey()
        {
            var root = Directory.CreateTempSubdirectory("s24-boundary-").FullName;
            var connectionString = new SqliteConnectionStringBuilder { DataSource = Path.Combine(root, "metadata.sqlite3"), Pooling = false }.ToString();
            SqliteMetadataSchema.InitializeAsync(connectionString).GetAwaiter().GetResult();
            _ = new RestoreService(connectionString);
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
            {
                ["HOSTED_WORKSPACE_ROOT"] = root,
            });
            var store = new PhaseAMetadataStore(connectionString, options);
            var account = store.CreateUserAccountAsync($"s24-user-{Guid.NewGuid():N}", 1).GetAwaiter().GetResult();
            var projectRoot = Directory.CreateDirectory(Path.Combine(root, "project"));
            _ = store.CreateProjectAsync(new ProjectCreationCommand(
                ProjectId, account.AccountId, "S24 boundary", "S24 boundary", "manual", "default", false, [],
                projectRoot.FullName, Path.Combine(projectRoot.FullName, "repo"),
                Path.Combine(projectRoot.FullName, "runtime"), Path.Combine(projectRoot.FullName, "meta"))).GetAwaiter().GetResult();
            var protectedManifest = SnapshotManifest.Create("s24-snapshot", WorkspaceId, account.AccountId, ProjectId, "policy-s24", Files) with
            {
                ProtectedContent = SnapshotManifest.ProtectContent(Files, SnapshotManifest.Create("s24-snapshot", WorkspaceId, account.AccountId, ProjectId, "policy-s24", Files).KeyReference)
            };
            var manifest = protectedManifest with { KeyReference = "keyref-s24-unavailable" };
            var context = RequestContext.FromIdentity(
                new AccountIdentity(account.AccountId, "owner", PhaseAAuth.UserRole),
                "s24-requester",
                "s24-credential",
                "s24-correlation");
            var lease = new RunnerLease("s24-lease", account.AccountId, ProjectId, 1);
            using (var connection = new SqliteConnection(connectionString))
            {
                connection.Open();
                using var command = connection.CreateCommand();
                command.CommandText = "INSERT INTO runner_leases(lease_id,account_id,project_id,fence) VALUES($id,$account,$project,$fence)";
                command.Parameters.AddWithValue("$id", lease.LeaseId);
                command.Parameters.AddWithValue("$account", lease.AccountId);
                command.Parameters.AddWithValue("$project", lease.ProjectId);
                command.Parameters.AddWithValue("$fence", lease.Fence);
                command.ExecuteNonQuery();
            }

            return new S24Fixture(root, connectionString, manifest, context, lease);
        }

        public RestoreAttempt Restore() => new RestoreService(ConnectionString).Restore(Context, Manifest, SourceRoot, DestinationRoot, Lease, IdempotencyKey);

        public string? ReadAttemptStatus()
        {
            using var connection = new SqliteConnection(ConnectionString);
            connection.Open();
            using var command = connection.CreateCommand();
            command.CommandText = "SELECT status FROM restore_attempts WHERE idempotency_key=$key";
            command.Parameters.AddWithValue("$key", IdempotencyKey);
            return command.ExecuteScalar()?.ToString();
        }

        public bool IsPublished() => Directory.Exists(Path.Combine(DestinationRoot, ".restore-current"));

        public void Dispose()
        {
            SqliteConnection.ClearAllPools();
            try { Directory.Delete(Root, true); } catch (IOException) { }
        }
    }
}
