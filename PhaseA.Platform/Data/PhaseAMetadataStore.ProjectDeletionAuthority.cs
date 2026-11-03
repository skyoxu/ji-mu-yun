using Microsoft.Data.Sqlite;
using PhaseA.Platform.Projects;

namespace PhaseA.Platform.Data;

public sealed partial class PhaseAMetadataStore
{
    // ADR-0061: this exact deletion operation never widens ordinary project read authority.
    internal async Task<ProjectDeletionResult> DeleteProjectForCurrentActorAsync(
        string actorAccountId, bool administratorRequested, string projectId, CancellationToken cancellationToken)
    {
        void AuthorizeActor()
        {
            DemandCurrentNodeOperation(accountId: actorAccountId, write: true);
            if (administratorRequested) DemandCurrentNodeAdminOperation();
        }
        AuthorizeActor();
        var project = await GetProjectSnapshotAsync(projectId, cancellationToken);
        string? owner = project?.AccountId;
        if (owner is null)
        {
            await using var connection = await OpenConnectionAsync(cancellationToken);
            await using var command = connection.CreateCommand();
            command.CommandText = "SELECT account_id FROM project_delete_tombstones WHERE project_id=$project;";
            command.Parameters.AddWithValue("$project", projectId);
            owner = await command.ExecuteScalarAsync(cancellationToken) as string;
        }
        if (owner is null || (!administratorRequested && owner != actorAccountId))
            return ProjectDeletionResult.Failure("project_not_found");

        void AuthorizeTarget()
        {
            AuthorizeActor();
            using var connection = new SqliteConnection(_connectionString);
            connection.Open();
            using var command = connection.CreateCommand();
            // An administrator may target another local owner, never a foreign node.
            // Tombstone lookup remains exact; regular callers cannot enumerate other owners.
            command.CommandText = """
                SELECT count(*) FROM accounts a JOIN node_binding n ON n.singleton_key=1
                WHERE a.id=$owner AND a.home_node_id=n.node_id AND n.node_id=$node
                  AND (EXISTS(SELECT 1 FROM projects p WHERE p.id=$project AND p.account_id=a.id AND p.node_id=n.node_id)
                    OR (NOT EXISTS(SELECT 1 FROM projects p WHERE p.id=$project)
                      AND EXISTS(SELECT 1 FROM project_delete_tombstones t WHERE t.project_id=$project AND t.account_id=a.id)))
                  AND NOT EXISTS(SELECT 1 FROM projects p WHERE p.id=$project AND (p.account_id<>a.id OR p.node_id IS NULL OR p.node_id<>n.node_id));
                """;
            command.Parameters.AddWithValue("$owner", owner);
            command.Parameters.AddWithValue("$project", projectId);
            command.Parameters.AddWithValue("$node", _options.NodeId!);
            if (Convert.ToInt64(command.ExecuteScalar()) != 1)
                throw new UnauthorizedAccessException("current_node_authority_required");
        }
        AuthorizeTarget();
        if (project is not null && (project.BootstrapStatus == "running" ||
            await HasActiveRunAsync(projectId, cancellationToken) || await HasRunnerLockAsync(projectId, cancellationToken)))
            return ProjectDeletionResult.Failure("project_busy");
        await SoftDeleteProjectAsync(projectId, cancellationToken, AuthorizeTarget);
        return ProjectDeletionResult.Deleted(projectId);
    }
}
