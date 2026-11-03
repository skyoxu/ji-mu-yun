using Microsoft.Data.Sqlite;

namespace PhaseA.Platform.Data;

public sealed partial class PhaseAMetadataStore
{
    // ADR-0061: a revoked producer cannot execute, but its previously admitted,
    // exact operation must still record failure and release its own commitment.
    // The callback accepts no identity, status, output, run or project arguments.
    internal async Task<Func<Task>> CapturePackageRestoreCleanupAsync(string runId, CancellationToken token)
    {
        var projectId = ResolveNodeReference("run", runId);
        DemandCurrentNodeOperation(projectId: projectId, write: true);
        var project = await GetProjectSnapshotAsync(projectId, token)
            ?? throw new UnauthorizedAccessException("project_not_found");
        var run = await GetRunSnapshotAsync(runId, token)
            ?? throw new UnauthorizedAccessException("run_not_found");
        if (!run.RunType.StartsWith("project-package-restore:", StringComparison.Ordinal) ||
            run.Status != "queued" || await GetRunnerLockOwnerAsync(projectId, token) != runId)
            throw new UnauthorizedAccessException("owned_package_restore_cleanup_required");
        return () => FinalizeOwnedPackageRestoreAsync(project.AccountId, projectId, runId, run.RunType);
    }

    private async Task FinalizeOwnedPackageRestoreAsync(string accountId, string projectId, string runId, string runType)
    {
        DemandPersistedNodeBinding();
        await using var connection = await OpenConnectionAsync(CancellationToken.None);
        using var transaction = connection.BeginTransaction();
        using var command = connection.CreateCommand();
        command.Transaction = transaction;
        command.CommandText = """
            SELECT count(*) FROM runs r JOIN projects p ON p.id=r.project_id
            JOIN accounts a ON a.id=p.account_id JOIN node_binding n ON n.singleton_key=1
            WHERE r.id=$run AND r.project_id=$project AND r.run_type=$type
              AND p.account_id=$account AND p.node_id=$node AND a.home_node_id=$node AND n.node_id=$node;
            """;
        command.Parameters.AddWithValue("$run", runId);
        command.Parameters.AddWithValue("$project", projectId);
        command.Parameters.AddWithValue("$account", accountId);
        command.Parameters.AddWithValue("$node", _options.NodeId!);
        command.Parameters.AddWithValue("$type", runType);
        if (Convert.ToInt64(await command.ExecuteScalarAsync()) != 1)
            throw new UnauthorizedAccessException("owned_package_restore_cleanup_changed");
        var now = DateTimeOffset.UtcNow.ToString("O");
        command.CommandText = """
            UPDATE runs SET status='failed', finished_utc=$now, exit_code=500,
              stdout_text='', stderr_text='Admitted package restore did not complete.',
              evidence_json='{"code":"package_restore_failed"}'
            WHERE id=$run AND project_id=$project AND run_type=$type AND status IN ('queued','running')
              AND EXISTS(SELECT 1 FROM runner_locks WHERE project_id=$project AND run_id=$run);
            """;
        command.Parameters.AddWithValue("$now", now);
        if (await command.ExecuteNonQueryAsync() == 1)
        {
            await UpsertRunDurationMetricAsync(connection, transaction, runId, now, CancellationToken.None);
            await PruneRunDurationMetricsAsync(connection, transaction, CancellationToken.None);
        }
        // This exact lock cannot be the successor operation's commitment.
        command.CommandText = """
            DELETE FROM runner_locks WHERE project_id=$project AND run_id=$run
              AND EXISTS(SELECT 1 FROM runs WHERE id=$run AND project_id=$project AND run_type=$type
                AND status IN ('failed','cancel','succeeded','blocked'));
            """;
        await command.ExecuteNonQueryAsync();
        transaction.Commit();
    }
}
