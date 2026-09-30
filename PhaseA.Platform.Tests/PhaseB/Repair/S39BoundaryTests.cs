using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using Xunit;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S39BoundaryTests
{
    [Fact]
    public async Task O_26EB3FEDC908()
    {
        await using var fixture = await BoundaryFixture.CreateAsync();
        var requester = await fixture.CreateAccountAsync("s39-requester");
        var conflictingOwner = await fixture.CreateAccountAsync("s39-conflicting-owner");
        var project = await fixture.CreateProjectAsync(conflictingOwner.AccountId, "conflicting-owner");

        if (!project.Succeeded || project.ProjectId is null)
            throw new InvalidOperationException("S39 conflicting-owner fixture project was not created.");
        var observation = await fixture.ReadForRequesterAsync(requester.AccountId, project.ProjectId);

        Require(
            !string.Equals(observation.PersistedOwner, requester.AccountId, StringComparison.Ordinal) &&
            !observation.RequesterOwnsProject &&
            observation.RequesterProjects.All(candidate => !string.Equals(candidate.ProjectId, project.ProjectId, StringComparison.Ordinal)),
            "FAILURE-O-26EB3FEDC908",
            "The conflicting project was assigned or adopted by the authenticated requester.");
    }

    [Fact]
    public async Task O_9CC6D75341B4()
    {
        await using var fixture = await BoundaryFixture.CreateAsync();
        var requester = await fixture.CreateAccountAsync("s39-requester");
        var alternateOwner = await fixture.CreateAccountAsync("s39-alternate-owner");
        var ambiguousOwner = $"{requester.AccountId}|{alternateOwner.AccountId}";
        var projectId = await fixture.CreateLegacyProjectAsync(ambiguousOwner, "ambiguous-owner");

        var observation = await fixture.ReadForRequesterAsync(requester.AccountId, projectId);

        Require(
            string.Equals(observation.PersistedBootstrapStatus, "quarantined", StringComparison.Ordinal) &&
            !string.Equals(observation.PersistedOwner, requester.AccountId, StringComparison.Ordinal) &&
            !observation.RequesterOwnsProject &&
            observation.RequesterProjects.All(candidate => !string.Equals(candidate.ProjectId, projectId, StringComparison.Ordinal)),
            "FAILURE-O-9CC6D75341B4",
            "The ambiguous ownership record was not persisted as quarantined and excluded from normal requester ownership.");
    }

    [Fact]
    public async Task O_C0DC8313E8FC()
    {
        await using var fixture = await BoundaryFixture.CreateAsync();
        var requester = await fixture.CreateAccountAsync("s39-requester");
        var orphanOwner = $"orphan-{Guid.NewGuid():N}";
        var projectId = await fixture.CreateLegacyProjectAsync(orphanOwner, "orphan-owner");

        var observation = await fixture.ReadForRequesterAsync(requester.AccountId, projectId);

        Require(
            !string.Equals(observation.PersistedOwner, requester.AccountId, StringComparison.Ordinal) &&
            !observation.RequesterOwnsProject &&
            observation.RequesterProjects.All(candidate => !string.Equals(candidate.ProjectId, projectId, StringComparison.Ordinal)),
            "FAILURE-O-C0DC8313E8FC",
            "The orphan project was assigned or adopted by the authenticated requester.");
    }

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
        {
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
        }
    }

    private sealed class BoundaryFixture : IAsyncDisposable
    {
        private readonly string _databasePath;
        private readonly string _workspaceRoot;
        private readonly PhaseAMetadataStore _store;

        private BoundaryFixture(string databasePath, string workspaceRoot, PhaseAMetadataStore store)
        {
            _databasePath = databasePath;
            _workspaceRoot = workspaceRoot;
            _store = store;
        }

        public static async Task<BoundaryFixture> CreateAsync()
        {
            var databasePath = Path.Combine(Path.GetTempPath(), $"s39-{Guid.NewGuid():N}.sqlite3");
            var connectionString = new SqliteConnectionStringBuilder { DataSource = databasePath, Pooling = false }.ToString();
            await SqliteMetadataSchema.InitializeAsync(connectionString);
            var workspaceRoot = Path.Combine(Path.GetDirectoryName(databasePath)!, "workspaces");
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
            {
                ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot
            });
            return new BoundaryFixture(databasePath, workspaceRoot, new PhaseAMetadataStore(connectionString, options));
        }

        public Task<AdminCreateUserResult> CreateAccountAsync(string username)
        {
            return _store.CreateUserAccountAsync(username, 4);
        }

        public Task<ProjectCreationResult> CreateProjectAsync(string ownerAccountId, string name)
        {
            var projectRoot = Path.Combine(_workspaceRoot, $"s39-project-{Guid.NewGuid():N}");
            return _store.CreateProjectAsync(new ProjectCreationCommand(
                $"project-{Guid.NewGuid():N}",
                ownerAccountId,
                name,
                name,
                "manual",
                "default",
                false,
                [],
                projectRoot,
                Path.Combine(projectRoot, "repo"),
                Path.Combine(projectRoot, "runtime"),
                Path.Combine(projectRoot, "meta")));
        }

        public async Task<string> CreateLegacyProjectAsync(string ownerAccountId, string name)
        {
            var projectId = $"legacy-{Guid.NewGuid():N}";
            await using var connection = new SqliteConnection(
                new SqliteConnectionStringBuilder { DataSource = _databasePath, Pooling = false }.ToString());
            await connection.OpenAsync();

            await using (var foreignKeys = connection.CreateCommand())
            {
                foreignKeys.CommandText = "PRAGMA foreign_keys = OFF;";
                await foreignKeys.ExecuteNonQueryAsync();
            }

            await using var command = connection.CreateCommand();
            command.CommandText =
                """
                INSERT INTO projects (
                    id, account_id, name, game_name, game_type_source, template_rule_id, created_utc)
                VALUES ($id, $account_id, $name, $game_name, 'legacy', 'legacy', $created_utc);
                """;
            command.Parameters.AddWithValue("$id", projectId);
            command.Parameters.AddWithValue("$account_id", ownerAccountId);
            command.Parameters.AddWithValue("$name", name);
            command.Parameters.AddWithValue("$game_name", name);
            command.Parameters.AddWithValue("$created_utc", DateTimeOffset.UtcNow.ToString("O"));
            await command.ExecuteNonQueryAsync();
            return projectId;
        }

        public async Task<RequesterProjectObservation> ReadForRequesterAsync(string requesterAccountId, string projectId)
        {
            var requesterOwnsProject = await _store.ProjectBelongsToAccountAsync(requesterAccountId, projectId);
            var requesterProjects = await _store.ListProjectsAsync(requesterAccountId);
            var project = await _store.GetProjectSnapshotAsync(projectId);
            await using var connection = new SqliteConnection(
                new SqliteConnectionStringBuilder { DataSource = _databasePath, Pooling = false }.ToString());
            await connection.OpenAsync();
            await using var command = connection.CreateCommand();
            command.CommandText = "SELECT account_id, bootstrap_status FROM projects WHERE id = $project_id";
            command.Parameters.AddWithValue("$project_id", projectId);
            await using var reader = await command.ExecuteReaderAsync();
            if (!await reader.ReadAsync())
                throw new InvalidOperationException("S39 fixture project is absent from authoritative storage.");
            return new RequesterProjectObservation(requesterOwnsProject, requesterProjects, project,
                reader.GetString(0), reader.GetString(1));
        }

        public ValueTask DisposeAsync()
        {
            SqliteConnection.ClearAllPools();
            if (File.Exists(_databasePath))
            {
                File.Delete(_databasePath);
            }

            return ValueTask.CompletedTask;
        }
    }

    private sealed record RequesterProjectObservation(
        bool RequesterOwnsProject,
        IReadOnlyList<ProjectListItem> RequesterProjects,
        ProjectSnapshot? Project,
        string PersistedOwner,
        string PersistedBootstrapStatus);
}
