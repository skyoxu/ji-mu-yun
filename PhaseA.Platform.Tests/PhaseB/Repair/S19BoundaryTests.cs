using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S19BoundaryTests
{
    private readonly ITestOutputHelper _output;

    public S19BoundaryTests(ITestOutputHelper output) => _output = output;

    [Fact]
    public void O_192BAC5BF05E()
    {
        var results = new List<RestoreValidityResult>();
        foreach (var variant in new[] { PlacementVariant.Null, PlacementVariant.Default, PlacementVariant.Changed })
        {
            using var fixture = RestoreValidityFixture.Create();
            results.Add(fixture.Evaluate(variant));
        }

        var expectedStatus = RestoreAttemptStatus.Published;
        var validAcrossPlacementReferences = results.Count == 3 &&
            results.All(result =>
                result.Status == expectedStatus &&
                result.AuthoritativeRecord == result.ExpectedRecord &&
                result.VerifiedContent == RestoreValidityFixture.Content) &&
            results.Select(result => result.Status).Distinct().Count() == 1;

        Require(
            validAcrossPlacementReferences,
            "FAILURE-O-192BAC5BF05E",
            "Restore validity changed when only the null, default, or changed placement reference varied.");
        _output.WriteLine(
            "S19-OBSERVATION O-192BAC5BF05E " +
            "server-record-and-verified-content-validity-is-identical-across-null-default-and-changed-placement-references");
    }

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
        {
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
        }
    }

    private enum PlacementVariant
    {
        Null,
        Default,
        Changed
    }

    private sealed class RestoreValidityFixture : IDisposable
    {
        public const string Content = "s19-verified-content";

        private RestoreValidityFixture(
            string root,
            string connectionString,
            SnapshotManifest manifest,
            RequestContext context,
            RunnerLease lease,
            string destinationRoot)
        {
            Root = root;
            ConnectionString = connectionString;
            Manifest = manifest;
            Context = context;
            Lease = lease;
            DestinationRoot = destinationRoot;
        }

        public string Root { get; }
        public string ConnectionString { get; }
        public SnapshotManifest Manifest { get; }
        public RequestContext Context { get; }
        public RunnerLease Lease { get; }
        public string DestinationRoot { get; }

        public static RestoreValidityFixture Create()
        {
            var root = Directory.CreateTempSubdirectory("s19-restore-validity-").FullName;
            var connectionString = new SqliteConnectionStringBuilder
            {
                DataSource = Path.Combine(root, "metadata.sqlite3"),
                Pooling = false
            }.ToString();
            SqliteMetadataSchema.InitializeAsync(connectionString).GetAwaiter().GetResult();
            _ = new RestoreService(connectionString);
            // ADR-0061: exercise restore validity with a real enabled account and project.
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
            {
                ["HOSTED_WORKSPACE_ROOT"] = root,
            });
            var store = new PhaseAMetadataStore(connectionString, options);
            var account = store.CreateUserAccountAsync($"s19-user-{Guid.NewGuid():N}", 1).GetAwaiter().GetResult();
            var projectRoot = Directory.CreateDirectory(Path.Combine(root, "project"));
            _ = store.CreateProjectAsync(new ProjectCreationCommand(
                "s19-project",
                account.AccountId,
                "S19 boundary",
                "S19 boundary",
                "manual",
                "default",
                false,
                [],
                projectRoot.FullName,
                Path.Combine(projectRoot.FullName, "repo"),
                Path.Combine(projectRoot.FullName, "runtime"),
                Path.Combine(projectRoot.FullName, "meta"))).GetAwaiter().GetResult();
            RouteAuthorityFixture.Seed(connectionString, account.AccountId, "s19-project", projectRoot.FullName);

            var manifest = SnapshotManifest.Create(
                "s19-snapshot",
                "s19-workspace",
                account.AccountId,
                "s19-project",
                "s19-policy",
                [("project.godot", "s19-verified-content"u8.ToArray())]);
            manifest = manifest with
            {
                ProtectedContent = SnapshotManifest.ProtectContent(
                    [("project.godot", "s19-verified-content"u8.ToArray())],
                    manifest.KeyReference)
            };
            var context = RequestContext.FromIdentity(
                new AccountIdentity(account.AccountId, "owner", PhaseAAuth.UserRole),
                "s19-requester",
                "s19-credential",
                "s19-correlation");
            var lease = new RunnerLease("s19-lease", account.AccountId, "s19-project", 1);
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

            return new RestoreValidityFixture(
                root,
                connectionString,
                manifest,
                context,
                lease,
                Directory.CreateDirectory(Path.Combine(root, "destination")).FullName);
        }

        public RestoreValidityResult Evaluate(PlacementVariant variant)
        {
            string? placementReference = variant switch
            {
                PlacementVariant.Null => null,
                PlacementVariant.Default => string.Empty,
                PlacementVariant.Changed => Path.Combine(Root, "moved-placement-reference"),
                _ => throw new ArgumentOutOfRangeException(nameof(variant))
            };
            var idempotencyKey = $"s19-{variant.ToString().ToLowerInvariant()}";
            var attempt = new RestoreService(ConnectionString, new RouteRecoveryAuthorityResolver(ConnectionString)).Restore(
                Context,
                Manifest,
                placementReference!,
                DestinationRoot,
                Lease,
                idempotencyKey);
            var authoritativeRecord = ReadAuthoritativeRecord(idempotencyKey);
            var verifiedContent = File.ReadAllText(Path.Combine(DestinationRoot, ".restore-current", "project.godot"));
            return new RestoreValidityResult(
                attempt.Status,
                authoritativeRecord,
                new RestoreRecord(Manifest.SnapshotId, Manifest.WorkspaceId, Manifest.AccountId, Manifest.ProjectId),
                verifiedContent);
        }

        private RestoreRecord? ReadAuthoritativeRecord(string idempotencyKey)
        {
            using var connection = new SqliteConnection(ConnectionString);
            connection.Open();
            using var command = connection.CreateCommand();
            command.CommandText = "SELECT snapshot_id,workspace_id,account_id,project_id FROM restore_attempts WHERE idempotency_key=$key";
            command.Parameters.AddWithValue("$key", idempotencyKey);
            using var reader = command.ExecuteReader();
            return reader.Read()
                ? new RestoreRecord(reader.GetString(0), reader.GetString(1), reader.GetString(2), reader.GetString(3))
                : null;
        }

        public void Dispose()
        {
            SqliteConnection.ClearAllPools();
            try { Directory.Delete(Root, true); } catch (IOException) { }
        }
    }

    private sealed record RestoreValidityResult(
        RestoreAttemptStatus Status,
        RestoreRecord? AuthoritativeRecord,
        RestoreRecord ExpectedRecord,
        string VerifiedContent);

    private sealed record RestoreRecord(string SnapshotId, string WorkspaceId, string AccountId, string ProjectId);
}
