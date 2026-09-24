using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Readback;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S52BoundaryTests
{
    private readonly ITestOutputHelper _output;

    public S52BoundaryTests(ITestOutputHelper output) => _output = output;

    [Fact]
    public void O_EE142D9EE309()
    {
        using var fixture = S52Fixture.Create();
        var oldTicket = fixture.PreviewTickets.CreateTicket(
            fixture.AccountId,
            fixture.ProjectId,
            fixture.ResourcePath);

        var restore = fixture.Restore();
        var oldTicketIsAuthorized = fixture.PreviewTickets.IsValid(
            oldTicket,
            fixture.AccountId,
            fixture.ProjectId,
            fixture.ResourcePath);
        var oldTicketGrantsRestoredResource = oldTicketIsAuthorized && File.Exists(fixture.RestoredResourcePath);

        Require(
            restore.Status == RestoreAttemptStatus.Published &&
            !oldTicketIsAuthorized &&
            !oldTicketGrantsRestoredResource,
            "FAILURE-O-EE142D9EE309",
            "A pre-restore preview ticket remained valid or authorized the restored resource.");
        _output.WriteLine("S52-OBSERVATION O-EE142D9EE309 old-preview-ticket-denied-after-restore");
    }

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
        {
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
        }
    }

    private sealed class S52Fixture : IDisposable
    {
        private S52Fixture(
            string root,
            string connectionString,
            SnapshotManifest manifest,
            RequestContext context,
            RunnerLease lease,
            ProjectAssetPreviewTicketService previewTickets)
        {
            Root = root;
            ConnectionString = connectionString;
            Manifest = manifest;
            Context = context;
            Lease = lease;
            PreviewTickets = previewTickets;
            SourceRoot = Directory.CreateDirectory(Path.Combine(root, "source")).FullName;
            DestinationRoot = Directory.CreateDirectory(Path.Combine(root, "destination")).FullName;
        }

        public string Root { get; }
        public string ConnectionString { get; }
        public string AccountId => "s52-account";
        public string ProjectId => "s52-project";
        public string WorkspaceId => "s52-workspace";
        public string ResourcePath => "private-preview.png";
        public string RestoredResourcePath => Path.Combine(DestinationRoot, ".restore-current", ResourcePath);
        public SnapshotManifest Manifest { get; }
        public RequestContext Context { get; }
        public RunnerLease Lease { get; }
        public ProjectAssetPreviewTicketService PreviewTickets { get; }
        public string SourceRoot { get; }
        public string DestinationRoot { get; }

        public static S52Fixture Create()
        {
            var root = Directory.CreateTempSubdirectory("s52-boundary-").FullName;
            var connectionString = new SqliteConnectionStringBuilder
            {
                DataSource = Path.Combine(root, "metadata.sqlite3"),
                Pooling = false
            }.ToString();
            SqliteMetadataSchema.InitializeAsync(connectionString).GetAwaiter().GetResult();
            _ = new RestoreService(connectionString);

            var content = "s52-preview-content"u8.ToArray();
            var manifest = SnapshotManifest.Create(
                "s52-snapshot",
                "s52-workspace",
                "s52-account",
                "s52-project",
                "s52-policy",
                [("private-preview.png", content)]);
            manifest = manifest with
            {
                ProtectedContent = SnapshotManifest.ProtectContent(
                    [("private-preview.png", content)],
                    manifest.KeyReference)
            };

            var context = RequestContext.FromIdentity(
                new AccountIdentity("s52-account", "owner", PhaseAAuth.UserRole),
                "s52-requester",
                "s52-credential",
                "s52-correlation");
            var lease = new RunnerLease("s52-lease", "s52-account", "s52-project", 1);
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

            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
            {
                ["PHASEA_TICKET_SIGNING_SECRET"] = "s52-ticket-signing-secret"
            });
            return new S52Fixture(
                root,
                connectionString,
                manifest,
                context,
                lease,
                new ProjectAssetPreviewTicketService(options));
        }

        public RestoreAttempt Restore() => new RestoreService(ConnectionString).Restore(
            Context,
            Manifest,
            SourceRoot,
            DestinationRoot,
            Lease,
            "s52-restore");

        public void Dispose()
        {
            SqliteConnection.ClearAllPools();
            try { Directory.Delete(Root, recursive: true); }
            catch (IOException) { }
        }
    }
}
