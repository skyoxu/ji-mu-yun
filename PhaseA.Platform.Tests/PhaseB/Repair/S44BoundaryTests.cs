using System.Text;
using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S44BoundaryTests
{
    private readonly ITestOutputHelper _output;

    public S44BoundaryTests(ITestOutputHelper output) => _output = output;

    [Fact]
    public async Task O_6C4973EE3FE2()
    {
        var observations = new List<TopologyObservation>();
        var sequence = 0;
        foreach (var category in PlacementCategories)
        {
            foreach (var condition in PlacementConditions)
            {
                using var fixture = await TopologySeedFixture.CreateAsync(++sequence);
                var placementReference = PlacementReference.For(category, condition);
                var attempt = fixture.Restore(category, condition);
                var persisted = fixture.ReadPersistedAttempt(category, condition);
                var restoredContent = fixture.ReadRestoredContent();

                observations.Add(new TopologyObservation(
                    category,
                    condition,
                    placementReference.Value,
                    persisted is not null &&
                    persisted.AccountId == fixture.AccountId &&
                    persisted.ProjectId == fixture.ProjectId &&
                    persisted.SnapshotId == fixture.Manifest.SnapshotId &&
                    attempt.Status == RestoreAttemptStatus.Published,
                    restoredContent == TopologySeedFixture.Content,
                    persisted?.Status.ToString() ?? "missing",
                    restoredContent == TopologySeedFixture.Content));
            }
        }

        foreach (var observation in observations)
        {
            _output.WriteLine(
                $"S44-CASE category={observation.Category} condition={observation.Condition} " +
                $"placement_reference={observation.PlacementReference ?? "null"} " +
                $"authority={(observation.ServerOwned ? "server-records" : "invalid")} " +
                $"restore={(observation.ContentValid ? "content" : "invalid")} " +
                $"attempt={observation.AttemptStatus} content={observation.ContentObserved}");
        }

        Require(
            observations.Count == PlacementCategories.Length * PlacementConditions.Length &&
            observations.All(observation => observation.ServerOwned && observation.ContentValid) &&
            PlacementCategories.All(category => PlacementConditions.All(condition =>
                observations.Any(observation => observation.Category == category && observation.Condition == condition))),
            "FAILURE-O-6C4973EE3FE2",
            "The single-node topology seed did not cover every optional placement reference while deriving ownership and restore validity from server records and content.");
        _output.WriteLine("S44-OBSERVATION O-6C4973EE3FE2 single-node-topology-reference-matrix-covered-with-server-record-ownership-and-content-restore");
    }

    private static readonly string[] PlacementCategories = ["node", "runner", "sandbox", "attempt", "snapshot"];
    private static readonly string[] PlacementConditions = ["null", "default", "changed"];

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
        {
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
        }
    }

    private sealed record PlacementReference(string? Value)
    {
        public static PlacementReference For(string category, string condition) => condition switch
        {
            "null" => new PlacementReference((string?)null),
            "default" => new PlacementReference($"{category}-default"),
            "changed" => new PlacementReference($"{category}-changed"),
            _ => throw new ArgumentOutOfRangeException(nameof(condition))
        };
    }

    private sealed record TopologyObservation(
        string Category,
        string Condition,
        string? PlacementReference,
        bool ServerOwned,
        bool ContentValid,
        string AttemptStatus,
        bool ContentObserved);

    private sealed record PersistedAttempt(string AccountId, string ProjectId, string SnapshotId, RestoreAttemptStatus Status);

    private sealed class TopologySeedFixture : IDisposable
    {
        public const string Content = "s44-server-derived-content";

        private TopologySeedFixture(
            string root,
            string connectionString,
            PhaseAMetadataStore store,
            string accountId,
            string projectId,
            SnapshotManifest manifest,
            RequestContext context,
            RunnerLease lease,
            string sourceRoot,
            string destinationRoot)
        {
            Root = root;
            ConnectionString = connectionString;
            Store = store;
            AccountId = accountId;
            ProjectId = projectId;
            Manifest = manifest;
            Context = context;
            Lease = lease;
            SourceRoot = sourceRoot;
            DestinationRoot = destinationRoot;
        }

        public string Root { get; }
        public string ConnectionString { get; }
        public PhaseAMetadataStore Store { get; }
        public string AccountId { get; }
        public string ProjectId { get; }
        public SnapshotManifest Manifest { get; }
        public RequestContext Context { get; }
        public RunnerLease Lease { get; }
        public string SourceRoot { get; }
        public string DestinationRoot { get; }

        public static async Task<TopologySeedFixture> CreateAsync(int sequence)
        {
            var root = Directory.CreateTempSubdirectory("s44-boundary-").FullName;
            var connectionString = new SqliteConnectionStringBuilder
            {
                DataSource = Path.Combine(root, "metadata.sqlite3"),
                Pooling = false
            }.ToString();
            await SqliteMetadataSchema.InitializeAsync(connectionString);
            var store = new PhaseAMetadataStore(
                connectionString,
                PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>()));
            _ = new RestoreService(connectionString);
            var account = await store.CreateUserAccountAsync($"s44-user-{sequence}-{Guid.NewGuid():N}", 1);
            var projectId = $"s44-project-{sequence}-{Guid.NewGuid():N}";
            var workspace = Directory.CreateDirectory(Path.Combine(root, "workspace"));
            await store.CreateProjectAsync(new ProjectCreationCommand(
                projectId,
                account.AccountId,
                "S44 topology seed",
                "S44 topology seed",
                "manual",
                "default",
                false,
                [],
                workspace.FullName,
                Path.Combine(workspace.FullName, "repo"),
                Path.Combine(workspace.FullName, "runtime"),
                Path.Combine(workspace.FullName, "meta")));
            RouteAuthorityFixture.Seed(connectionString, account.AccountId, projectId, workspace.FullName);

            var sourceRoot = Directory.CreateDirectory(Path.Combine(root, "source")).FullName;
            var destinationRoot = Directory.CreateDirectory(Path.Combine(root, "destination")).FullName;
            var content = Encoding.UTF8.GetBytes(Content);
            File.WriteAllBytes(Path.Combine(sourceRoot, "project.godot"), content);
            var manifest = SnapshotManifest.Create(
                $"s44-snapshot-{sequence}",
                $"s44-workspace-{sequence}",
                account.AccountId,
                projectId,
                "s44-policy",
                [("project.godot", content)]);
            manifest = manifest with
            {
                ProtectedContent = SnapshotManifest.ProtectContent([("project.godot", content)], manifest.KeyReference)
            };
            var context = RequestContext.FromIdentity(
                new AccountIdentity(account.AccountId, "s44-owner", PhaseAAuth.UserRole),
                $"s44-principal-{sequence}",
                $"s44-credential-{sequence}",
                $"s44-correlation-{sequence}");
            var lease = new RunnerLease($"s44-lease-{sequence}", account.AccountId, projectId, 1);
            using (var connection = new SqliteConnection(connectionString))
            {
                connection.Open();
                using var command = connection.CreateCommand();
                command.CommandText = "INSERT INTO runner_leases(lease_id,account_id,project_id,fence) VALUES($lease,$account,$project,$fence)";
                command.Parameters.AddWithValue("$lease", lease.LeaseId);
                command.Parameters.AddWithValue("$account", lease.AccountId);
                command.Parameters.AddWithValue("$project", lease.ProjectId);
                command.Parameters.AddWithValue("$fence", lease.Fence);
                command.ExecuteNonQuery();
            }
            return new TopologySeedFixture(root, connectionString, store, account.AccountId, projectId, manifest, context, lease, sourceRoot, destinationRoot);
        }

        public RestoreAttempt Restore(string category, string condition) =>
            new RestoreService(ConnectionString, new RouteRecoveryAuthorityResolver(ConnectionString)).RestorePrepared(
                Context,
                Manifest,
                condition switch
                {
                    "null" => null!,
                    "default" => string.Empty,
                    "changed" => Path.Combine(Root, $"{category}-placement-reference"),
                    _ => throw new ArgumentOutOfRangeException(nameof(condition))
                },
                DestinationRoot,
                Lease,
                $"s44-{category}-{condition}");

        public PersistedAttempt? ReadPersistedAttempt(string category, string condition)
        {
            using var connection = new SqliteConnection(ConnectionString);
            connection.Open();
            using var command = connection.CreateCommand();
            command.CommandText = "SELECT account_id,project_id,snapshot_id,status FROM restore_attempts WHERE idempotency_key=$key";
            command.Parameters.AddWithValue("$key", $"s44-{category}-{condition}");
            using var reader = command.ExecuteReader();
            return reader.Read() ? new PersistedAttempt(reader.GetString(0), reader.GetString(1), reader.GetString(2), Enum.Parse<RestoreAttemptStatus>(reader.GetString(3))) : null;
        }

        public string? ReadRestoredContent()
        {
            var path = Path.Combine(DestinationRoot, ".restore-current", "project.godot");
            return File.Exists(path) ? File.ReadAllText(path, Encoding.UTF8) : null;
        }

        public void Dispose()
        {
            SqliteConnection.ClearAllPools();
            if (Directory.Exists(Root)) Directory.Delete(Root, recursive: true);
        }
    }
}
