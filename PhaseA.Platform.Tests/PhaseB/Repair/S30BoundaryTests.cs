using Microsoft.Data.Sqlite;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using System.Text;
using System.Text.Json;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S30BoundaryTests
{
    private const string PolicyVersion = "policy-s30-extension-policy-v1";
    private readonly ITestOutputHelper _output;

    public S30BoundaryTests(ITestOutputHelper output)
    {
        _output = output;
    }

    [Fact]
    public void O_13F33C30B03B()
    {
        using var fixture = SnapshotBoundaryFixture.Create();
        fixture.WriteSourceFile("assets/allowed.txt", "allowed snapshot content");
        fixture.WriteSourceFile("assets/prohibited.blocked", "prohibited snapshot content");
        fixture.WriteSourceFile(
            "policy/exclusion-notes.md",
            "Files ending in .blocked are excluded by policy-s30-extension-policy-v1.");

        var snapshot = fixture.CreateSnapshot();
        var retainedPayload = snapshot.Manifest.ReadProtectedContent();
        using var exportedManifest = JsonDocument.Parse(File.ReadAllText(snapshot.ManifestPath));
        var exportedFilePaths = exportedManifest.RootElement
            .GetProperty("Files")
            .EnumerateArray()
            .Select(file => file.GetProperty("RelativePath").GetString()!)
            .ToArray();
        var exportedExclusions = exportedManifest.RootElement
            .GetProperty("ContentExclusions")
            .EnumerateArray()
            .Select(extension => extension.GetString())
            .ToArray();

        var prohibitedContentRetained = snapshot.Manifest.Files
            .Select(file => file.RelativePath)
            .Concat(retainedPayload.Keys)
            .Concat(exportedFilePaths)
            .Any(path => path.EndsWith(".blocked", StringComparison.OrdinalIgnoreCase));
        var descriptorRetained = retainedPayload.TryGetValue("policy/exclusion-notes.md", out var descriptor)
            && Encoding.UTF8.GetString(descriptor).Contains(".blocked", StringComparison.Ordinal);
        var actualBehavior = snapshot.Manifest.PolicyVersion == PolicyVersion
            && exportedManifest.RootElement.GetProperty("PolicyVersion").GetString() == PolicyVersion
            && snapshot.Manifest.ContentExclusions.SequenceEqual([".blocked"])
            && exportedExclusions.SequenceEqual([".blocked"])
            && !prohibitedContentRetained
            && retainedPayload.ContainsKey("assets/allowed.txt")
            && descriptorRetained;

        if (actualBehavior)
        {
            _output.WriteLine(
                "S30-OBSERVATION O-13F33C30B03B prohibited-extension-absent-from-manifest-export-and-retained-payload-while-policy-metadata-and-description-remain");
        }

        Require(
            actualBehavior,
            "FAILURE-O-13F33C30B03B",
            "The Snapshot retained prohibited extension content or rejected valid exclusion metadata and policy description.");
    }

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
        {
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
        }
    }

    private sealed class SnapshotBoundaryFixture : IDisposable
    {
        private const string AccountId = "account-s30";
        private const string ProjectId = "project-s30";
        private const string WorkspaceId = "workspace-s30";
        private readonly DirectoryInfo _root;
        private readonly string _databasePath;

        private SnapshotBoundaryFixture(DirectoryInfo root, string databasePath)
        {
            _root = root;
            _databasePath = databasePath;
        }

        public static SnapshotBoundaryFixture Create()
        {
            var root = Directory.CreateTempSubdirectory("s30-snapshot-boundary-");
            var databasePath = Path.Combine(Path.GetTempPath(), $"s30-{Guid.NewGuid():N}.db");
            var fixture = new SnapshotBoundaryFixture(root, databasePath);
            fixture.CreateProjectDatabase();
            return fixture;
        }

        public void WriteSourceFile(string relativePath, string content)
        {
            var path = Path.Combine(_root.FullName, relativePath);
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            File.WriteAllText(path, content);
        }

        public WorkspaceSnapshotRecord CreateSnapshot()
        {
            var context = RequestContext.FromIdentity(
                new AccountIdentity(AccountId, "owner", PhaseAAuth.UserRole),
                "principal-s30",
                "credential-s30",
                "correlation-s30");
            return new WorkspaceStorageService($"Data Source={_databasePath}").CreateSnapshot(
                context,
                _root.FullName,
                "snapshot-s30",
                WorkspaceId,
                ProjectId,
                PolicyVersion,
                new HashSet<string>([".blocked"], StringComparer.OrdinalIgnoreCase));
        }

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
