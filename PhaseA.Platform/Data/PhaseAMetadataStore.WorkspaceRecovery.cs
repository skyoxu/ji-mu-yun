using System.Text.Json;
using PhaseA.Platform.Workspaces;

namespace PhaseA.Platform.Data;

public sealed partial class PhaseAMetadataStore
{
    public async Task<string?> GetRunnerLockOwnerAsync(string projectId, CancellationToken token = default)
    {
        await using var connection = await OpenConnectionAsync(token);
        using var command = connection.CreateCommand();
        command.CommandText = "SELECT run_id FROM runner_locks WHERE project_id=$project LIMIT 1";
        command.Parameters.AddWithValue("$project", projectId);
        return await command.ExecuteScalarAsync(token) as string;
    }

    // ADR-0033/0061: publish the three active paths and activation receipt together.
    // Old generations and run history remain available; no live database repair.
    public async Task ActivateWorkspaceGenerationAsync(ProjectSnapshot project, string runId,
        string snapshotId, string attemptId, string generationRoot, string credentialHash, CancellationToken token = default)
    {
        if (!WorkspacePathPolicy.IsUnderRoot(WorkspaceGenerationPaths.StorageRoot(project), generationRoot))
            throw new UnauthorizedAccessException("Workspace generation escaped the project root.");
        var now = DateTimeOffset.UtcNow.ToString("O");
        await using var connection = await OpenConnectionAsync(token);
        using var transaction = connection.BeginTransaction();
        using var command = connection.CreateCommand();
        command.Transaction = transaction;
        command.CommandText = """
            UPDATE workspaces SET root_path=$generation, repo_path=$repo, runtime_path=$runtime, meta_path=$meta
            WHERE id=$workspace AND project_id=$project AND repo_path=$previous
              AND EXISTS (SELECT 1 FROM projects WHERE id=$project AND account_id=$account)
              AND EXISTS (SELECT 1 FROM accounts WHERE id=$account AND token_hash=$credential AND is_disabled=0
                AND (valid_until_utc IS NULL OR valid_until_utc>$now))
              AND EXISTS (SELECT 1 FROM runner_locks WHERE project_id=$project AND run_id=$run)
              AND EXISTS (SELECT 1 FROM runs WHERE id=$run AND status='running');
            """;
        command.Parameters.AddWithValue("$repo", Path.Combine(generationRoot, "repo"));
        command.Parameters.AddWithValue("$generation", generationRoot);
        command.Parameters.AddWithValue("$runtime", Path.Combine(generationRoot, "runtime"));
        command.Parameters.AddWithValue("$meta", Path.Combine(generationRoot, "meta"));
        command.Parameters.AddWithValue("$workspace", project.WorkspaceId);
        command.Parameters.AddWithValue("$project", project.ProjectId);
        command.Parameters.AddWithValue("$account", project.AccountId);
        command.Parameters.AddWithValue("$run", runId);
        command.Parameters.AddWithValue("$previous", project.RepoPath);
        command.Parameters.AddWithValue("$credential", credentialHash);
        command.Parameters.AddWithValue("$now", now);
        if (await command.ExecuteNonQueryAsync(token) != 1)
            throw new InvalidOperationException("Workspace activation no longer owns the project.");
        command.CommandText = """
            INSERT INTO project_workspace_activations
              (run_id, account_id, project_id, snapshot_id, attempt_id, generation_root, activated_utc)
            VALUES ($run, $account, $project, $snapshot, $attempt, $generation, $now);
            UPDATE project_ui_states SET state_json='{}', updated_utc=$now
              WHERE project_id=$project AND account_id=$account;
            UPDATE project_iteration_sessions SET status='paused_for_review', updated_utc=$now
              WHERE id=(SELECT id FROM project_iteration_sessions WHERE project_id=$project
                AND account_id=$account ORDER BY created_utc DESC LIMIT 1);
            UPDATE runs SET status='succeeded', finished_utc=$now, exit_code=0,
              stdout_text='Project version restored and activated.', stderr_text='', evidence_json=$evidence
              WHERE id=$run AND status='running';
            """;
        command.Parameters.AddWithValue("$snapshot", snapshotId);
        command.Parameters.AddWithValue("$attempt", attemptId);
        command.Parameters.AddWithValue("$evidence", JsonSerializer.Serialize(new
        {
            snapshotId, attemptId, activated = true, revalidationRequired = true,
            producerRunId = runId, activatedUtc = now
        }));
        await command.ExecuteNonQueryAsync(token);
        await UpsertRunDurationMetricAsync(connection, transaction, runId, now, token);
        await PruneRunDurationMetricsAsync(connection, transaction, token);
        await ReleaseRunnerLockForRunAsync(connection, transaction, project.ProjectId, runId, token);
        transaction.Commit();
    }

    public async Task<DateTimeOffset?> GetLastWorkspaceActivationUtcAsync(string accountId,
        string projectId, CancellationToken token = default)
    {
        await using var connection = await OpenConnectionAsync(token);
        using var command = connection.CreateCommand();
        command.CommandText = """
            SELECT activated_utc FROM project_workspace_activations
            WHERE project_id=$project AND account_id=$account ORDER BY activated_utc DESC LIMIT 1;
            """;
        command.Parameters.AddWithValue("$project", projectId);
        command.Parameters.AddWithValue("$account", accountId);
        var value = await command.ExecuteScalarAsync(token);
        return value is string text && DateTimeOffset.TryParse(text, out var parsed) ? parsed : null;
    }

    public async Task<bool> RequiresRestoreValidationAsync(string accountId, string projectId,
        CancellationToken token = default)
    {
        var activation = await GetLastWorkspaceActivationUtcAsync(accountId, projectId, token);
        if (activation is null) return false;
        var runs = await ListRunsForProjectAsync(projectId, token);
        foreach (var run in runs.Where(run => run.RunType == "prototype-7day-playable"))
        {
            if (!DateTimeOffset.TryParse(run.CreatedUtc, out var created) || created <= activation) continue;
            try
            {
                using var doc = JsonDocument.Parse(run.EvidenceJson ?? "{}");
                if (!doc.RootElement.TryGetProperty("validation_only", out var validation) || validation.ValueKind != JsonValueKind.True)
                    continue;
                if (doc.RootElement.TryGetProperty("skeleton_validation_only", out var skeleton) && skeleton.ValueKind == JsonValueKind.True)
                    continue;
                return run.Status != "succeeded";
            }
            catch (JsonException) { }
        }
        return true;
    }
}
