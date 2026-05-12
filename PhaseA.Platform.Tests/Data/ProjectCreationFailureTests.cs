using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Tests.Data;
using Xunit;

namespace PhaseA.Platform.Tests.Data;

public sealed class ProjectCreationFailureTests
{
    [Fact]
    public async Task RecordProjectCreationFailureAsync_PreservesLatestFailure()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var options = Options(workspaceRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();

        await store.RecordProjectCreationFailureAsync(new ProjectCreationFailureCommand(
            accountId,
            "project-one",
            "Project One",
            "Game One",
            "manual",
            "godot-prototype-default",
            Path.Combine(workspaceRoot.Path, accountId, "project-one"),
            "first failure"));
        await store.RecordProjectCreationFailureAsync(new ProjectCreationFailureCommand(
            accountId,
            "project-two",
            "Project Two",
            "Game Two",
            "manual",
            "godot-prototype-default",
            Path.Combine(workspaceRoot.Path, accountId, "project-two"),
            "second failure"));

        var latest = await store.GetLatestProjectCreationFailureAsync(accountId);

        latest.Should().NotBeNull();
        latest!.ProjectId.Should().Be("project-two");
        latest.FailureError.Should().Be("second failure");
    }

    private static PhaseAPlatformOptions Options(string workspaceRoot)
    {
        return PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspaceRoot, "metadata.sqlite3")
        });
    }

    private sealed class TempDirectory : IDisposable
    {
        private TempDirectory(string path)
        {
            Path = path;
        }

        public string Path { get; }

        public static TempDirectory Create(string prefix)
        {
            var path = System.IO.Path.Combine(System.IO.Path.GetTempPath(), $"{prefix}-{Guid.NewGuid():N}");
            Directory.CreateDirectory(path);
            return new TempDirectory(path);
        }

        public void Dispose()
        {
            if (Directory.Exists(Path))
            {
                Directory.Delete(Path, recursive: true);
            }
        }
    }
}
