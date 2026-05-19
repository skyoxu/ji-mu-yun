using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Runs;
using System.Text.Json;
using SQLitePCL;

namespace PhaseA.Platform.Data;

public sealed class PhaseAMetadataStore
{
    private readonly string _connectionString;
    private readonly PhaseAPlatformOptions _options;

    public PhaseAMetadataStore(string connectionString, PhaseAPlatformOptions options)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(connectionString);
        ArgumentNullException.ThrowIfNull(options);

        _connectionString = connectionString;
        _options = options;
        Batteries_V2.Init();
    }

    public async Task<string> EnsureSingleAdminAsync(CancellationToken cancellationToken = default)
    {
        await using var connection = await OpenConnectionAsync(cancellationToken);
        var now = DateTimeOffset.UtcNow.ToString("O");

        await using var transaction = (SqliteTransaction)await connection.BeginTransactionAsync(cancellationToken);

        var existingId = await ExecuteScalarStringAsync(
            connection,
            "SELECT id FROM accounts WHERE is_admin = 1 ORDER BY created_utc LIMIT 1;",
            cancellationToken);

        if (!string.IsNullOrWhiteSpace(existingId))
        {
            await transaction.CommitAsync(cancellationToken);
            return existingId;
        }

        var accountId = NewId();
        await using (var command = connection.CreateCommand())
        {
            command.CommandText =
                """
                INSERT INTO accounts (id, username, password_hash, token_hash, is_admin, created_utc)
                VALUES ($id, $username, $password_hash, $token_hash, 1, $created_utc);
                """;
            command.Parameters.AddWithValue("$id", accountId);
            command.Parameters.AddWithValue("$username", _options.AdminUsername);
            command.Parameters.AddWithValue("$password_hash", (object?)_options.AdminPasswordHash ?? DBNull.Value);
            command.Parameters.AddWithValue("$token_hash", (object?)_options.AdminTokenHash ?? DBNull.Value);
            command.Parameters.AddWithValue("$created_utc", now);
            await command.ExecuteNonQueryAsync(cancellationToken);
        }

        await UpsertProjectLimitAsync(connection, accountId, _options.HostedProjectLimit, now, cancellationToken);

        await transaction.CommitAsync(cancellationToken);
        return accountId;
    }

    public async Task ReconcileProjectBootstrapStatusAsync(CancellationToken cancellationToken = default)
    {
        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            UPDATE projects
            SET bootstrap_status = CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM runs
                        WHERE runs.project_id = projects.id
                          AND runs.run_type = 'chapter2-bootstrap'
                          AND runs.status = 'succeeded'
                    ) THEN 'succeeded'
                    WHEN EXISTS (
                        SELECT 1
                        FROM runs
                        WHERE runs.project_id = projects.id
                          AND runs.run_type = 'chapter2-bootstrap'
                          AND runs.status = 'failed'
                    ) THEN 'failed'
                    ELSE bootstrap_status
                END,
                bootstrap_error = CASE
                    WHEN bootstrap_status = 'initial' AND EXISTS (
                        SELECT 1
                        FROM runs
                        WHERE runs.project_id = projects.id
                          AND runs.run_type = 'chapter2-bootstrap'
                          AND runs.status = 'failed'
                    ) THEN 'Chapter 2 initialization failed.'
                    ELSE bootstrap_error
                END
            WHERE bootstrap_status = 'initial';
            """;
        await command.ExecuteNonQueryAsync(cancellationToken);
    }

    public async Task<IReadOnlyList<StaleProjectInitializationSnapshot>> ListStaleProjectInitializationsAsync(
        TimeSpan maxAge,
        CancellationToken cancellationToken = default)
    {
        var thresholdUtc = DateTimeOffset.UtcNow.Subtract(maxAge).ToString("O");
        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT
                p.id,
                p.account_id,
                p.name,
                p.game_name,
                p.game_type_source,
                p.template_rule_id,
                w.root_path,
                r.id,
                r.status,
                r.created_utc,
                r.started_utc
            FROM projects p
            INNER JOIN workspaces w ON w.project_id = p.id
            INNER JOIN runs r ON r.project_id = p.id
            WHERE p.bootstrap_status = 'running'
              AND r.run_type = 'chapter2-bootstrap'
              AND r.status IN ('queued', 'running')
              AND COALESCE(r.started_utc, r.created_utc) < $threshold_utc
            ORDER BY r.created_utc ASC;
            """;
        command.Parameters.AddWithValue("$threshold_utc", thresholdUtc);

        var stale = new List<StaleProjectInitializationSnapshot>();
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            stale.Add(new StaleProjectInitializationSnapshot(
                reader.GetString(0),
                reader.GetString(1),
                reader.GetString(2),
                reader.GetString(3),
                reader.GetString(4),
                reader.GetString(5),
                reader.GetString(6),
                reader.GetString(7),
                reader.GetString(8),
                reader.GetString(9),
                reader.IsDBNull(10) ? null : reader.GetString(10)));
        }

        return stale;
    }

    public async Task<IReadOnlyList<InterruptedRunSnapshot>> ListInterruptedRunsAsync(CancellationToken cancellationToken = default)
    {
        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT id, project_id, run_type, status, created_utc, started_utc, progress_updated_utc
            FROM runs
            WHERE status IN ('queued', 'running')
            ORDER BY created_utc ASC, id ASC;
            """;

        var runs = new List<InterruptedRunSnapshot>();
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            runs.Add(new InterruptedRunSnapshot(
                reader.GetString(0),
                reader.GetString(1),
                reader.GetString(2),
                reader.GetString(3),
                reader.GetString(4),
                reader.IsDBNull(5) ? null : reader.GetString(5),
                reader.IsDBNull(6) ? null : reader.GetString(6)));
        }

        return runs;
    }

    public async Task<int> ReconcileInterruptedRunsAsync(
        string failureMessage,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(failureMessage);

        var interruptedRuns = await ListInterruptedRunsAsync(cancellationToken);
        if (interruptedRuns.Count == 0)
        {
            return 0;
        }

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var transaction = (SqliteTransaction)await connection.BeginTransactionAsync(cancellationToken);
        var finishedUtc = DateTimeOffset.UtcNow.ToString("O");
        var evidenceJson = JsonSerializer.Serialize(new
        {
            failure_code = "interrupted_by_service_restart",
            reason = "service_restart_recovery"
        });

        foreach (var run in interruptedRuns)
        {
            await using (var command = connection.CreateCommand())
            {
                command.Transaction = transaction;
                command.CommandText =
                    """
                    UPDATE runs
                    SET status = 'failed',
                        finished_utc = $finished_utc,
                        exit_code = COALESCE(exit_code, 500),
                        stderr_text = CASE
                            WHEN stderr_text IS NULL OR stderr_text = '' THEN $stderr_text
                            ELSE stderr_text || char(10) || $stderr_text
                        END,
                        evidence_json = CASE
                            WHEN evidence_json IS NULL OR evidence_json = '' THEN $evidence_json
                            ELSE evidence_json
                        END
                    WHERE id = $id
                      AND status IN ('queued', 'running');
                    """;
                command.Parameters.AddWithValue("$id", run.RunId);
                command.Parameters.AddWithValue("$finished_utc", finishedUtc);
                command.Parameters.AddWithValue("$stderr_text", failureMessage);
                command.Parameters.AddWithValue("$evidence_json", evidenceJson);
                await command.ExecuteNonQueryAsync(cancellationToken);
            }

            await using (var lockCommand = connection.CreateCommand())
            {
                lockCommand.Transaction = transaction;
                lockCommand.CommandText =
                    """
                    DELETE FROM runner_locks
                    WHERE project_id = $project_id
                       OR run_id = $run_id;
                    """;
                lockCommand.Parameters.AddWithValue("$project_id", run.ProjectId);
                lockCommand.Parameters.AddWithValue("$run_id", run.RunId);
                await lockCommand.ExecuteNonQueryAsync(cancellationToken);
            }
        }

        await transaction.CommitAsync(cancellationToken);
        return interruptedRuns.Count;
    }

    public async Task<int> ReconcileAbandonedRunsAsync(
        Func<InterruptedRunSnapshot, TimeSpan?> maxAgeSelector,
        Func<InterruptedRunSnapshot, string> failureMessageSelector,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(maxAgeSelector);
        ArgumentNullException.ThrowIfNull(failureMessageSelector);

        var now = DateTimeOffset.UtcNow;
        var interruptedRuns = await ListInterruptedRunsAsync(cancellationToken);
        var abandonedRuns = interruptedRuns
            .Where(run =>
            {
                var maxAge = maxAgeSelector(run);
                if (maxAge is null)
                {
                    return false;
                }

                var heartbeatUtc = ParseRunHeartbeatUtc(run);
                return heartbeatUtc <= now.Subtract(maxAge.Value);
            })
            .ToList();

        if (abandonedRuns.Count == 0)
        {
            return 0;
        }

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var transaction = (SqliteTransaction)await connection.BeginTransactionAsync(cancellationToken);
        var finishedUtc = now.ToString("O");

        foreach (var run in abandonedRuns)
        {
            var failureMessage = failureMessageSelector(run);
            var evidenceJson = JsonSerializer.Serialize(new
            {
                failure_code = "abandoned_run_recovered",
                reason = "heartbeat_timeout_recovery"
            });

            await using (var command = connection.CreateCommand())
            {
                command.Transaction = transaction;
                command.CommandText =
                    """
                    UPDATE runs
                    SET status = 'failed',
                        finished_utc = $finished_utc,
                        exit_code = COALESCE(exit_code, 500),
                        stderr_text = CASE
                            WHEN stderr_text IS NULL OR stderr_text = '' THEN $stderr_text
                            ELSE stderr_text || char(10) || $stderr_text
                        END,
                        evidence_json = CASE
                            WHEN evidence_json IS NULL OR evidence_json = '' THEN $evidence_json
                            ELSE evidence_json
                        END
                    WHERE id = $id
                      AND status IN ('queued', 'running');
                    """;
                command.Parameters.AddWithValue("$id", run.RunId);
                command.Parameters.AddWithValue("$finished_utc", finishedUtc);
                command.Parameters.AddWithValue("$stderr_text", failureMessage);
                command.Parameters.AddWithValue("$evidence_json", evidenceJson);
                await command.ExecuteNonQueryAsync(cancellationToken);
            }

            await using (var lockCommand = connection.CreateCommand())
            {
                lockCommand.Transaction = transaction;
                lockCommand.CommandText =
                    """
                    DELETE FROM runner_locks
                    WHERE project_id = $project_id
                       OR run_id = $run_id;
                    """;
                lockCommand.Parameters.AddWithValue("$project_id", run.ProjectId);
                lockCommand.Parameters.AddWithValue("$run_id", run.RunId);
                await lockCommand.ExecuteNonQueryAsync(cancellationToken);
            }
        }

        await transaction.CommitAsync(cancellationToken);
        return abandonedRuns.Count;
    }

    public async Task UpsertLlmBindingAsync(LlmBindingCommand create, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(create);
        ArgumentException.ThrowIfNullOrWhiteSpace(create.AccountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(create.GatewayProvider);
        ArgumentException.ThrowIfNullOrWhiteSpace(create.GatewayBaseUrl);
        ArgumentException.ThrowIfNullOrWhiteSpace(create.ExternalAccountRef);
        ArgumentException.ThrowIfNullOrWhiteSpace(create.TokenRef);

        var now = DateTimeOffset.UtcNow.ToString("O");
        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            INSERT INTO account_llm_bindings (
                account_id,
                gateway_provider,
                gateway_base_url,
                external_account_ref,
                token_ref,
                created_utc,
                updated_utc)
            VALUES (
                $account_id,
                $gateway_provider,
                $gateway_base_url,
                $external_account_ref,
                $token_ref,
                $created_utc,
                $updated_utc)
            ON CONFLICT(account_id) DO UPDATE SET
                gateway_provider = excluded.gateway_provider,
                gateway_base_url = excluded.gateway_base_url,
                external_account_ref = excluded.external_account_ref,
                token_ref = excluded.token_ref,
                updated_utc = excluded.updated_utc;
            """;
        command.Parameters.AddWithValue("$account_id", create.AccountId);
        command.Parameters.AddWithValue("$gateway_provider", create.GatewayProvider);
        command.Parameters.AddWithValue("$gateway_base_url", create.GatewayBaseUrl);
        command.Parameters.AddWithValue("$external_account_ref", create.ExternalAccountRef);
        command.Parameters.AddWithValue("$token_ref", create.TokenRef);
        command.Parameters.AddWithValue("$created_utc", now);
        command.Parameters.AddWithValue("$updated_utc", now);
        await command.ExecuteNonQueryAsync(cancellationToken);
    }

    public async Task<LlmBindingSnapshot?> GetLlmBindingAsync(string accountId, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT account_id, gateway_provider, gateway_base_url, external_account_ref, token_ref
            FROM account_llm_bindings
            WHERE account_id = $account_id;
            """;
        command.Parameters.AddWithValue("$account_id", accountId);

        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        if (!await reader.ReadAsync(cancellationToken))
        {
            return null;
        }

        return new LlmBindingSnapshot(
            reader.GetString(0),
            reader.GetString(1),
            reader.GetString(2),
            reader.GetString(3),
            reader.GetString(4));
    }

    public async Task<int> GetProjectLimitAsync(string accountId, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        var value = await ExecuteScalarLongAsync(
            connection,
            "SELECT project_limit FROM project_limits WHERE account_id = $account_id;",
            cancellationToken,
            ("$account_id", accountId));

        return value is null ? _options.HostedProjectLimit : checked((int)value.Value);
    }

    public async Task<ProjectCreationResult> CreateProjectAsync(
        ProjectCreationCommand create,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(create);
        ArgumentException.ThrowIfNullOrWhiteSpace(create.ProjectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(create.AccountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(create.ProjectName);
        ArgumentException.ThrowIfNullOrWhiteSpace(create.GameName);
        ArgumentException.ThrowIfNullOrWhiteSpace(create.GameTypeSource);
        ArgumentException.ThrowIfNullOrWhiteSpace(create.TemplateRuleId);
        ArgumentException.ThrowIfNullOrWhiteSpace(create.WorkspaceRootPath);
        ArgumentException.ThrowIfNullOrWhiteSpace(create.RepoPath);
        ArgumentException.ThrowIfNullOrWhiteSpace(create.RuntimePath);
        ArgumentException.ThrowIfNullOrWhiteSpace(create.MetaPath);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var transaction = await connection.BeginTransactionAsync(cancellationToken);

        var limit = await GetProjectLimitInsideTransactionAsync(connection, create.AccountId, cancellationToken);
        var initializingCount = await ExecuteScalarLongAsync(
            connection,
            "SELECT COUNT(*) FROM projects WHERE account_id = $account_id AND bootstrap_status = 'running';",
            cancellationToken,
            ("$account_id", create.AccountId)) ?? 0;

        if (initializingCount > 0)
        {
            await transaction.RollbackAsync(cancellationToken);
            return ProjectCreationResult.Failure("project_initialization_in_progress");
        }

        var count = await ExecuteScalarLongAsync(
            connection,
            "SELECT COUNT(*) FROM projects WHERE account_id = $account_id;",
            cancellationToken,
            ("$account_id", create.AccountId)) ?? 0;

        if (count >= limit)
        {
            await transaction.RollbackAsync(cancellationToken);
            return ProjectCreationResult.QuotaExceeded(limit);
        }

        var workspaceId = NewId();
        var allowedWorkflowsJson = JsonSerializer.Serialize(create.AllowedWorkflows);
        await using (var command = connection.CreateCommand())
        {
            command.CommandText =
                """
                INSERT INTO projects (
                    id,
                    account_id,
                    name,
                    game_name,
                    game_type_source,
                    template_rule_id,
                    llm_binding_required,
                    allowed_workflows_json,
                    bootstrap_status,
                    bootstrap_error,
                    created_utc)
                VALUES (
                    $id,
                    $account_id,
                    $name,
                    $game_name,
                    $game_type_source,
                    $template_rule_id,
                    $llm_binding_required,
                    $allowed_workflows_json,
                    'running',
                    NULL,
                    $created_utc);
                """;
            command.Parameters.AddWithValue("$id", create.ProjectId);
            command.Parameters.AddWithValue("$account_id", create.AccountId);
            command.Parameters.AddWithValue("$name", create.ProjectName);
            command.Parameters.AddWithValue("$game_name", create.GameName);
            command.Parameters.AddWithValue("$game_type_source", create.GameTypeSource);
            command.Parameters.AddWithValue("$template_rule_id", create.TemplateRuleId);
            command.Parameters.AddWithValue("$llm_binding_required", create.LlmBindingRequired ? 1 : 0);
            command.Parameters.AddWithValue("$allowed_workflows_json", allowedWorkflowsJson);
            command.Parameters.AddWithValue("$created_utc", DateTimeOffset.UtcNow.ToString("O"));
            await command.ExecuteNonQueryAsync(cancellationToken);
        }

        await using (var command = connection.CreateCommand())
        {
            command.CommandText =
                """
                INSERT INTO workspaces (id, project_id, root_path, repo_path, runtime_path, meta_path, created_utc)
                VALUES ($id, $project_id, $root_path, $repo_path, $runtime_path, $meta_path, $created_utc);
                """;
            command.Parameters.AddWithValue("$id", workspaceId);
            command.Parameters.AddWithValue("$project_id", create.ProjectId);
            command.Parameters.AddWithValue("$root_path", create.WorkspaceRootPath);
            command.Parameters.AddWithValue("$repo_path", create.RepoPath);
            command.Parameters.AddWithValue("$runtime_path", create.RuntimePath);
            command.Parameters.AddWithValue("$meta_path", create.MetaPath);
            command.Parameters.AddWithValue("$created_utc", DateTimeOffset.UtcNow.ToString("O"));
            await command.ExecuteNonQueryAsync(cancellationToken);
        }

        await transaction.CommitAsync(cancellationToken);
        return ProjectCreationResult.Created(
            create.ProjectId,
            workspaceId,
            create.WorkspaceRootPath,
            create.TemplateRuleId,
            create.LlmBindingRequired,
            create.AllowedWorkflows);
    }

    public async Task<ProjectSnapshot?> GetProjectSnapshotAsync(string projectId, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT
                p.id,
                p.account_id,
                p.name,
                p.game_name,
                p.game_type_source,
                p.template_rule_id,
                p.llm_binding_required,
                p.allowed_workflows_json,
                p.bootstrap_status,
                p.bootstrap_error,
                w.id,
                w.root_path,
                w.repo_path,
                w.runtime_path,
                w.meta_path
            FROM projects p
            INNER JOIN workspaces w ON w.project_id = p.id
            WHERE p.id = $project_id;
            """;
        command.Parameters.AddWithValue("$project_id", projectId);

        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        if (!await reader.ReadAsync(cancellationToken))
        {
            return null;
        }

        return new ProjectSnapshot(
            reader.GetString(0),
            reader.GetString(1),
            reader.GetString(2),
            reader.GetString(3),
            reader.GetString(4),
            reader.GetString(5),
            reader.GetInt64(6) == 1,
            reader.GetString(7),
            reader.GetString(8),
            reader.IsDBNull(9) ? null : reader.GetString(9),
            reader.GetString(10),
            reader.GetString(11),
            reader.GetString(12),
            reader.GetString(13),
            reader.GetString(14));
    }

    public async Task<IReadOnlyList<ProjectListItem>> ListProjectsAsync(string accountId, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT p.id, p.account_id, p.name, p.game_name, p.game_type_source, p.template_rule_id, p.bootstrap_status, p.bootstrap_error, w.root_path
            FROM projects p
            INNER JOIN workspaces w ON w.project_id = p.id
            WHERE p.account_id = $account_id
            ORDER BY p.created_utc, p.id;
            """;
        command.Parameters.AddWithValue("$account_id", accountId);

        var projects = new List<ProjectListItem>();
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            projects.Add(new ProjectListItem(
                reader.GetString(0),
                reader.GetString(1),
                reader.GetString(2),
                reader.GetString(3),
                reader.GetString(4),
                reader.GetString(5),
                reader.GetString(6),
                reader.IsDBNull(7) ? null : reader.GetString(7),
                reader.GetString(8)));
        }

        return projects;
    }

    public async Task<IReadOnlyList<ProjectSnapshot>> ListProjectSnapshotsAsync(CancellationToken cancellationToken = default)
    {
        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT
                p.id,
                p.account_id,
                p.name,
                p.game_name,
                p.game_type_source,
                p.template_rule_id,
                p.llm_binding_required,
                p.allowed_workflows_json,
                p.bootstrap_status,
                p.bootstrap_error,
                w.id,
                w.root_path,
                w.repo_path,
                w.runtime_path,
                w.meta_path
            FROM projects p
            INNER JOIN workspaces w ON w.project_id = p.id
            ORDER BY p.created_utc, p.id;
            """;

        var projects = new List<ProjectSnapshot>();
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            projects.Add(new ProjectSnapshot(
                reader.GetString(0),
                reader.GetString(1),
                reader.GetString(2),
                reader.GetString(3),
                reader.GetString(4),
                reader.GetString(5),
                reader.GetInt64(6) == 1,
                reader.GetString(7),
                reader.GetString(8),
                reader.IsDBNull(9) ? null : reader.GetString(9),
                reader.GetString(10),
                reader.GetString(11),
                reader.GetString(12),
                reader.GetString(13),
                reader.GetString(14)));
        }

        return projects;
    }

    public async Task SetProjectBootstrapStatusAsync(
        string projectId,
        string status,
        string? error,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(status);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            UPDATE projects
            SET bootstrap_status = $status,
                bootstrap_error = $error
            WHERE id = $project_id;
            """;
        command.Parameters.AddWithValue("$project_id", projectId);
        command.Parameters.AddWithValue("$status", status);
        command.Parameters.AddWithValue("$error", (object?)error ?? DBNull.Value);
        await command.ExecuteNonQueryAsync(cancellationToken);
    }

    public async Task<bool> HasRunnerLockAsync(string projectId, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        var count = await ExecuteScalarLongAsync(
            connection,
            "SELECT COUNT(*) FROM runner_locks WHERE project_id = $project_id;",
            cancellationToken,
            ("$project_id", projectId)) ?? 0;
        return count > 0;
    }

    public async Task<bool> HasActiveRunAsync(string projectId, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        var count = await ExecuteScalarLongAsync(
            connection,
            "SELECT COUNT(*) FROM runs WHERE project_id = $project_id AND status IN ('queued', 'running');",
            cancellationToken,
            ("$project_id", projectId)) ?? 0;
        return count > 0;
    }

    public async Task DeleteProjectAsync(string projectId, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText = "DELETE FROM projects WHERE id = $project_id;";
        command.Parameters.AddWithValue("$project_id", projectId);
        await command.ExecuteNonQueryAsync(cancellationToken);
    }

    public async Task RecordProjectCreationFailureAsync(
        ProjectCreationFailureCommand failure,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(failure);
        ArgumentException.ThrowIfNullOrWhiteSpace(failure.AccountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(failure.ProjectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(failure.ProjectName);
        ArgumentException.ThrowIfNullOrWhiteSpace(failure.GameName);
        ArgumentException.ThrowIfNullOrWhiteSpace(failure.GameTypeSource);
        ArgumentException.ThrowIfNullOrWhiteSpace(failure.TemplateRuleId);
        ArgumentException.ThrowIfNullOrWhiteSpace(failure.WorkspaceRootPath);
        ArgumentException.ThrowIfNullOrWhiteSpace(failure.FailureError);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            INSERT INTO project_creation_failures (
                id,
                account_id,
                project_id,
                project_name,
                game_name,
                game_type_source,
                template_rule_id,
                workspace_root_path,
                failure_error,
                created_utc)
            VALUES (
                $id,
                $account_id,
                $project_id,
                $project_name,
                $game_name,
                $game_type_source,
                $template_rule_id,
                $workspace_root_path,
                $failure_error,
                $created_utc);
            """;
        command.Parameters.AddWithValue("$id", NewId());
        command.Parameters.AddWithValue("$account_id", failure.AccountId);
        command.Parameters.AddWithValue("$project_id", failure.ProjectId);
        command.Parameters.AddWithValue("$project_name", failure.ProjectName);
        command.Parameters.AddWithValue("$game_name", failure.GameName);
        command.Parameters.AddWithValue("$game_type_source", failure.GameTypeSource);
        command.Parameters.AddWithValue("$template_rule_id", failure.TemplateRuleId);
        command.Parameters.AddWithValue("$workspace_root_path", failure.WorkspaceRootPath);
        command.Parameters.AddWithValue("$failure_error", failure.FailureError);
        command.Parameters.AddWithValue("$created_utc", DateTimeOffset.UtcNow.ToString("O"));
        await command.ExecuteNonQueryAsync(cancellationToken);
    }

    public async Task<ProjectCreationFailureSnapshot?> GetLatestProjectCreationFailureAsync(
        string accountId,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT
                id,
                account_id,
                project_id,
                project_name,
                game_name,
                game_type_source,
                template_rule_id,
                workspace_root_path,
                failure_error,
                created_utc
            FROM project_creation_failures
            WHERE account_id = $account_id
            ORDER BY created_utc DESC, rowid DESC
            LIMIT 1;
            """;
        command.Parameters.AddWithValue("$account_id", accountId);

        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        if (!await reader.ReadAsync(cancellationToken))
        {
            return null;
        }

        return new ProjectCreationFailureSnapshot(
            reader.GetString(0),
            reader.GetString(1),
            reader.GetString(2),
            reader.GetString(3),
            reader.GetString(4),
            reader.GetString(5),
            reader.GetString(6),
            reader.GetString(7),
            reader.GetString(8),
            reader.GetString(9));
    }

    public async Task<string> CreateRunAsync(
        string projectId,
        string? workspaceId,
        string runType,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(runType);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        var runId = NewId();
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            INSERT INTO runs (id, project_id, workspace_id, run_type, status, created_utc)
            VALUES ($id, $project_id, $workspace_id, $run_type, 'queued', $created_utc);
            """;
        command.Parameters.AddWithValue("$id", runId);
        command.Parameters.AddWithValue("$project_id", projectId);
        command.Parameters.AddWithValue("$workspace_id", (object?)workspaceId ?? DBNull.Value);
        command.Parameters.AddWithValue("$run_type", runType);
        command.Parameters.AddWithValue("$created_utc", DateTimeOffset.UtcNow.ToString("O"));
        await command.ExecuteNonQueryAsync(cancellationToken);
        return runId;
    }

    public async Task MarkRunStartedAsync(string runId, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(runId);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            UPDATE runs
            SET status = 'running',
                started_utc = $started_utc
            WHERE id = $id;
            """;
        command.Parameters.AddWithValue("$id", runId);
        command.Parameters.AddWithValue("$started_utc", DateTimeOffset.UtcNow.ToString("O"));
        await command.ExecuteNonQueryAsync(cancellationToken);
    }

    public async Task UpdateRunProgressAsync(
        string runId,
        string step,
        string substep,
        string label,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(runId);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            UPDATE runs
            SET progress_step = $progress_step,
                progress_substep = $progress_substep,
                progress_label = $progress_label,
                progress_updated_utc = $progress_updated_utc
            WHERE id = $id;
            """;
        command.Parameters.AddWithValue("$id", runId);
        command.Parameters.AddWithValue("$progress_step", step);
        command.Parameters.AddWithValue("$progress_substep", substep);
        command.Parameters.AddWithValue("$progress_label", label);
        command.Parameters.AddWithValue("$progress_updated_utc", DateTimeOffset.UtcNow.ToString("O"));
        await command.ExecuteNonQueryAsync(cancellationToken);
    }

    public async Task CompleteRunAsync(
        string runId,
        string status,
        int exitCode,
        string stdoutText,
        string stderrText,
        string evidenceJson,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(runId);
        ArgumentException.ThrowIfNullOrWhiteSpace(status);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            UPDATE runs
            SET status = $status,
                finished_utc = $finished_utc,
                exit_code = $exit_code,
                stdout_text = $stdout_text,
                stderr_text = $stderr_text,
                evidence_json = $evidence_json
            WHERE id = $id;
            """;
        command.Parameters.AddWithValue("$id", runId);
        command.Parameters.AddWithValue("$status", status);
        command.Parameters.AddWithValue("$finished_utc", DateTimeOffset.UtcNow.ToString("O"));
        command.Parameters.AddWithValue("$exit_code", exitCode);
        command.Parameters.AddWithValue("$stdout_text", stdoutText);
        command.Parameters.AddWithValue("$stderr_text", stderrText);
        command.Parameters.AddWithValue("$evidence_json", evidenceJson);
        await command.ExecuteNonQueryAsync(cancellationToken);
    }

    public async Task AddArtifactAsync(ArtifactCreationCommand create, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(create);
        ArgumentException.ThrowIfNullOrWhiteSpace(create.RunId);
        ArgumentException.ThrowIfNullOrWhiteSpace(create.ProjectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(create.ArtifactType);
        ArgumentException.ThrowIfNullOrWhiteSpace(create.RelativePath);
        ArgumentException.ThrowIfNullOrWhiteSpace(create.Summary);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            INSERT INTO artifacts (id, run_id, project_id, artifact_type, relative_path, summary, created_utc)
            VALUES ($id, $run_id, $project_id, $artifact_type, $relative_path, $summary, $created_utc);
            """;
        command.Parameters.AddWithValue("$id", NewId());
        command.Parameters.AddWithValue("$run_id", create.RunId);
        command.Parameters.AddWithValue("$project_id", create.ProjectId);
        command.Parameters.AddWithValue("$artifact_type", create.ArtifactType);
        command.Parameters.AddWithValue("$relative_path", create.RelativePath);
        command.Parameters.AddWithValue("$summary", create.Summary);
        command.Parameters.AddWithValue("$created_utc", DateTimeOffset.UtcNow.ToString("O"));
        await command.ExecuteNonQueryAsync(cancellationToken);
    }

    public async Task<RunSnapshot?> GetRunSnapshotAsync(string runId, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(runId);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT
                id,
                project_id,
                workspace_id,
                run_type,
                status,
                exit_code,
                stdout_text,
                stderr_text,
                evidence_json,
                progress_step,
                progress_substep,
                progress_label,
                progress_updated_utc,
                llm_gateway,
                llm_request_id,
                llm_model,
                llm_cost_json
            FROM runs
            WHERE id = $id;
            """;
        command.Parameters.AddWithValue("$id", runId);

        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        if (!await reader.ReadAsync(cancellationToken))
        {
            return null;
        }

        return new RunSnapshot(
            reader.GetString(0),
            reader.GetString(1),
            reader.IsDBNull(2) ? null : reader.GetString(2),
            reader.GetString(3),
            reader.GetString(4),
            reader.IsDBNull(5) ? null : reader.GetInt32(5),
            reader.IsDBNull(6) ? null : reader.GetString(6),
            reader.IsDBNull(7) ? null : reader.GetString(7),
            reader.IsDBNull(8) ? null : reader.GetString(8),
            reader.GetString(9),
            reader.GetString(10),
            reader.GetString(11),
            reader.IsDBNull(12) ? null : reader.GetString(12),
            reader.IsDBNull(13) ? null : reader.GetString(13),
            reader.IsDBNull(14) ? null : reader.GetString(14),
            reader.IsDBNull(15) ? null : reader.GetString(15),
            reader.IsDBNull(16) ? null : reader.GetString(16));
    }

    public async Task<IReadOnlyList<RunSnapshot>> ListRunsForProjectAsync(string projectId, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT
                id,
                project_id,
                workspace_id,
                run_type,
                status,
                exit_code,
                stdout_text,
                stderr_text,
                evidence_json,
                progress_step,
                progress_substep,
                progress_label,
                progress_updated_utc,
                llm_gateway,
                llm_request_id,
                llm_model,
                llm_cost_json
            FROM runs
            WHERE project_id = $project_id
            ORDER BY created_utc DESC, id DESC;
            """;
        command.Parameters.AddWithValue("$project_id", projectId);

        var runs = new List<RunSnapshot>();
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            runs.Add(new RunSnapshot(
                reader.GetString(0),
                reader.GetString(1),
                reader.IsDBNull(2) ? null : reader.GetString(2),
                reader.GetString(3),
                reader.GetString(4),
                reader.IsDBNull(5) ? null : reader.GetInt32(5),
                reader.IsDBNull(6) ? null : reader.GetString(6),
                reader.IsDBNull(7) ? null : reader.GetString(7),
                reader.IsDBNull(8) ? null : reader.GetString(8),
                reader.GetString(9),
                reader.GetString(10),
                reader.GetString(11),
                reader.IsDBNull(12) ? null : reader.GetString(12),
                reader.IsDBNull(13) ? null : reader.GetString(13),
                reader.IsDBNull(14) ? null : reader.GetString(14),
                reader.IsDBNull(15) ? null : reader.GetString(15),
                reader.IsDBNull(16) ? null : reader.GetString(16)));
        }

        return runs;
    }

    public async Task<RunSnapshot?> GetActiveRunForAccountAsync(string accountId, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT
                r.id,
                r.project_id,
                r.workspace_id,
                r.run_type,
                r.status,
                r.exit_code,
                r.stdout_text,
                r.stderr_text,
                r.evidence_json,
                r.progress_step,
                r.progress_substep,
                r.progress_label,
                r.progress_updated_utc,
                r.llm_gateway,
                r.llm_request_id,
                r.llm_model,
                r.llm_cost_json
            FROM runs r
            INNER JOIN projects p ON p.id = r.project_id
            WHERE p.account_id = $account_id
              AND r.status IN ('queued', 'running')
            ORDER BY r.created_utc DESC, r.id DESC
            LIMIT 1;
            """;
        command.Parameters.AddWithValue("$account_id", accountId);

        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        if (!await reader.ReadAsync(cancellationToken))
        {
            return null;
        }

        return new RunSnapshot(
            reader.GetString(0),
            reader.GetString(1),
            reader.IsDBNull(2) ? null : reader.GetString(2),
            reader.GetString(3),
            reader.GetString(4),
            reader.IsDBNull(5) ? null : reader.GetInt32(5),
            reader.IsDBNull(6) ? null : reader.GetString(6),
            reader.IsDBNull(7) ? null : reader.GetString(7),
            reader.IsDBNull(8) ? null : reader.GetString(8),
            reader.GetString(9),
            reader.GetString(10),
            reader.GetString(11),
            reader.IsDBNull(12) ? null : reader.GetString(12),
            reader.IsDBNull(13) ? null : reader.GetString(13),
            reader.IsDBNull(14) ? null : reader.GetString(14),
            reader.IsDBNull(15) ? null : reader.GetString(15),
            reader.IsDBNull(16) ? null : reader.GetString(16));
    }

    public async Task RecordRunLlmAuditAsync(
        string runId,
        string llmGateway,
        string? llmRequestId,
        string? llmModel,
        string llmCostJson,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(runId);
        ArgumentException.ThrowIfNullOrWhiteSpace(llmGateway);
        ArgumentException.ThrowIfNullOrWhiteSpace(llmCostJson);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            UPDATE runs
            SET llm_gateway = $llm_gateway,
                llm_request_id = $llm_request_id,
                llm_model = $llm_model,
                llm_cost_json = $llm_cost_json
            WHERE id = $id;
            """;
        command.Parameters.AddWithValue("$id", runId);
        command.Parameters.AddWithValue("$llm_gateway", llmGateway);
        command.Parameters.AddWithValue("$llm_request_id", (object?)llmRequestId ?? DBNull.Value);
        command.Parameters.AddWithValue("$llm_model", (object?)llmModel ?? DBNull.Value);
        command.Parameters.AddWithValue("$llm_cost_json", llmCostJson);
        await command.ExecuteNonQueryAsync(cancellationToken);
    }

    public async Task<IReadOnlyList<string>> ListAccountLlmCostJsonForUtcDayAsync(
        string accountId,
        DateOnly utcDay,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);

        var from = utcDay.ToDateTime(TimeOnly.MinValue, DateTimeKind.Utc).ToString("O");
        var to = utcDay.AddDays(1).ToDateTime(TimeOnly.MinValue, DateTimeKind.Utc).ToString("O");
        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT r.llm_cost_json
            FROM runs r
            INNER JOIN projects p ON p.id = r.project_id
            WHERE p.account_id = $account_id
              AND r.created_utc >= $from_utc
              AND r.created_utc < $to_utc
              AND r.llm_cost_json IS NOT NULL;
            """;
        command.Parameters.AddWithValue("$account_id", accountId);
        command.Parameters.AddWithValue("$from_utc", from);
        command.Parameters.AddWithValue("$to_utc", to);

        var costs = new List<string>();
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            costs.Add(reader.GetString(0));
        }

        return costs;
    }

    public async Task<IReadOnlyList<ArtifactSnapshot>> ListArtifactsForRunAsync(string runId, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(runId);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT id, run_id, project_id, artifact_type, relative_path, summary
            FROM artifacts
            WHERE run_id = $run_id
            ORDER BY created_utc, id;
            """;
        command.Parameters.AddWithValue("$run_id", runId);

        var artifacts = new List<ArtifactSnapshot>();
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            artifacts.Add(new ArtifactSnapshot(
                reader.GetString(0),
                reader.IsDBNull(1) ? null : reader.GetString(1),
                reader.GetString(2),
                reader.GetString(3),
                reader.GetString(4),
                reader.GetString(5)));
        }

        return artifacts;
    }

    public async Task<ArtifactSnapshot?> GetArtifactAsync(string artifactId, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(artifactId);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT id, run_id, project_id, artifact_type, relative_path, summary
            FROM artifacts
            WHERE id = $artifact_id;
            """;
        command.Parameters.AddWithValue("$artifact_id", artifactId);

        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        if (!await reader.ReadAsync(cancellationToken))
        {
            return null;
        }

        return new ArtifactSnapshot(
            reader.GetString(0),
            reader.IsDBNull(1) ? null : reader.GetString(1),
            reader.GetString(2),
            reader.GetString(3),
            reader.GetString(4),
            reader.GetString(5));
    }

    public async Task<bool> TryAcquireRunnerLockAsync(
        string projectId,
        string runId,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(runId);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            INSERT OR IGNORE INTO runner_locks (project_id, run_id, acquired_utc)
            VALUES ($project_id, $run_id, $acquired_utc);
            """;
        command.Parameters.AddWithValue("$project_id", projectId);
        command.Parameters.AddWithValue("$run_id", runId);
        command.Parameters.AddWithValue("$acquired_utc", DateTimeOffset.UtcNow.ToString("O"));
        var inserted = await command.ExecuteNonQueryAsync(cancellationToken);
        return inserted == 1;
    }

    public async Task ReleaseRunnerLockAsync(string projectId, string runId, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(runId);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            DELETE FROM runner_locks
            WHERE project_id = $project_id
              AND run_id = $run_id;
            """;
        command.Parameters.AddWithValue("$project_id", projectId);
        command.Parameters.AddWithValue("$run_id", runId);
        await command.ExecuteNonQueryAsync(cancellationToken);
    }

    private static DateTimeOffset ParseRunHeartbeatUtc(InterruptedRunSnapshot run)
    {
        var candidates = new[]
        {
            run.ProgressUpdatedUtc,
            run.StartedUtc,
            run.CreatedUtc
        };

        foreach (var candidate in candidates)
        {
            if (!string.IsNullOrWhiteSpace(candidate) &&
                DateTimeOffset.TryParse(candidate, out var parsed))
            {
                return parsed;
            }
        }

        return DateTimeOffset.MinValue;
    }

    public async Task<IReadOnlyList<ProjectChatMessageSnapshot>> ListProjectChatMessagesAsync(
        string accountId,
        string projectId,
        int limit = 50,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        limit = Math.Clamp(limit, 1, 100);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT id, account_id, project_id, role, content, kind, created_utc
            FROM (
                SELECT id, account_id, project_id, role, content, kind, created_utc
                FROM project_chat_messages
                WHERE account_id = $account_id
                  AND project_id = $project_id
                ORDER BY created_utc DESC
                LIMIT $limit
            )
            ORDER BY created_utc ASC;
            """;
        command.Parameters.AddWithValue("$account_id", accountId);
        command.Parameters.AddWithValue("$project_id", projectId);
        command.Parameters.AddWithValue("$limit", limit);

        var messages = new List<ProjectChatMessageSnapshot>();
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            messages.Add(new ProjectChatMessageSnapshot(
                reader.GetString(0),
                reader.GetString(1),
                reader.GetString(2),
                reader.GetString(3),
                reader.GetString(4),
                reader.IsDBNull(5) ? null : reader.GetString(5),
                reader.GetString(6)));
        }

        return messages;
    }

    public async Task AddProjectChatMessageAsync(
        string accountId,
        string projectId,
        string role,
        string content,
        string? kind = null,
        int retainLatest = 50,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(role);
        ArgumentException.ThrowIfNullOrWhiteSpace(content);
        retainLatest = Math.Clamp(retainLatest, 1, 100);

        if (role is not ("user" or "assistant"))
        {
            throw new ArgumentOutOfRangeException(nameof(role), "Chat role must be user or assistant.");
        }

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var transaction = await connection.BeginTransactionAsync(cancellationToken);
        await using (var command = connection.CreateCommand())
        {
            command.Transaction = (SqliteTransaction)transaction;
            command.CommandText =
                """
                INSERT INTO project_chat_messages (id, account_id, project_id, role, content, kind, created_utc)
                VALUES ($id, $account_id, $project_id, $role, $content, $kind, $created_utc);
                """;
            command.Parameters.AddWithValue("$id", NewId());
            command.Parameters.AddWithValue("$account_id", accountId);
            command.Parameters.AddWithValue("$project_id", projectId);
            command.Parameters.AddWithValue("$role", role);
            command.Parameters.AddWithValue("$content", content);
            command.Parameters.AddWithValue("$kind", (object?)kind ?? DBNull.Value);
            command.Parameters.AddWithValue("$created_utc", DateTimeOffset.UtcNow.ToString("O"));
            await command.ExecuteNonQueryAsync(cancellationToken);
        }

        await using (var command = connection.CreateCommand())
        {
            command.Transaction = (SqliteTransaction)transaction;
            command.CommandText =
                """
                DELETE FROM project_chat_messages
                WHERE account_id = $account_id
                  AND project_id = $project_id
                  AND id NOT IN (
                    SELECT id
                    FROM project_chat_messages
                    WHERE account_id = $account_id
                      AND project_id = $project_id
                    ORDER BY created_utc DESC
                    LIMIT $retain_latest
                  );
                """;
            command.Parameters.AddWithValue("$account_id", accountId);
            command.Parameters.AddWithValue("$project_id", projectId);
            command.Parameters.AddWithValue("$retain_latest", retainLatest);
            await command.ExecuteNonQueryAsync(cancellationToken);
        }

        await transaction.CommitAsync(cancellationToken);
    }

    public async Task<ProjectIterationSessionSnapshot> CreateProjectIterationSessionAsync(
        string accountId,
        string projectId,
        string sourceKind,
        string sourceMessage,
        string overallGoal,
        IReadOnlyList<ProjectIterationGoalCreateCommand> goals,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(sourceKind);
        ArgumentException.ThrowIfNullOrWhiteSpace(sourceMessage);
        ArgumentException.ThrowIfNullOrWhiteSpace(overallGoal);
        ArgumentNullException.ThrowIfNull(goals);

        var sessionId = NewId();
        var now = DateTimeOffset.UtcNow.ToString("O");

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var transaction = await connection.BeginTransactionAsync(cancellationToken);
        await using (var command = connection.CreateCommand())
        {
            command.Transaction = (SqliteTransaction)transaction;
            command.CommandText =
                """
                INSERT INTO project_iteration_sessions (
                    id,
                    project_id,
                    account_id,
                    source_kind,
                    source_message,
                    overall_goal,
                    status,
                    current_goal_index,
                    latest_summary,
                    latest_evaluation_json,
                    created_utc,
                    updated_utc,
                    completed_utc)
                VALUES (
                    $id,
                    $project_id,
                    $account_id,
                    $source_kind,
                    $source_message,
                    $overall_goal,
                    'planning',
                    0,
                    NULL,
                    NULL,
                    $created_utc,
                    $updated_utc,
                    NULL);
                """;
            command.Parameters.AddWithValue("$id", sessionId);
            command.Parameters.AddWithValue("$project_id", projectId);
            command.Parameters.AddWithValue("$account_id", accountId);
            command.Parameters.AddWithValue("$source_kind", sourceKind);
            command.Parameters.AddWithValue("$source_message", sourceMessage);
            command.Parameters.AddWithValue("$overall_goal", overallGoal);
            command.Parameters.AddWithValue("$created_utc", now);
            command.Parameters.AddWithValue("$updated_utc", now);
            await command.ExecuteNonQueryAsync(cancellationToken);
        }

        foreach (var goal in goals.OrderBy(goal => goal.GoalIndex))
        {
            await using var command = connection.CreateCommand();
            command.Transaction = (SqliteTransaction)transaction;
            command.CommandText =
                """
                INSERT INTO project_iteration_goals (
                    id,
                    session_id,
                    goal_index,
                    title,
                    description,
                    acceptance_hint,
                    status,
                    result_summary,
                    created_utc,
                    updated_utc,
                    completed_utc)
                VALUES (
                    $id,
                    $session_id,
                    $goal_index,
                    $title,
                    $description,
                    $acceptance_hint,
                    'pending',
                    NULL,
                    $created_utc,
                    $updated_utc,
                    NULL);
                """;
            command.Parameters.AddWithValue("$id", NewId());
            command.Parameters.AddWithValue("$session_id", sessionId);
            command.Parameters.AddWithValue("$goal_index", goal.GoalIndex);
            command.Parameters.AddWithValue("$title", goal.Title);
            command.Parameters.AddWithValue("$description", goal.Description);
            command.Parameters.AddWithValue("$acceptance_hint", (object?)goal.AcceptanceHint ?? DBNull.Value);
            command.Parameters.AddWithValue("$created_utc", now);
            command.Parameters.AddWithValue("$updated_utc", now);
            await command.ExecuteNonQueryAsync(cancellationToken);
        }

        await transaction.CommitAsync(cancellationToken);
        return new ProjectIterationSessionSnapshot(
            sessionId,
            projectId,
            accountId,
            sourceKind,
            sourceMessage,
            overallGoal,
            "planning",
            0,
            null,
            null,
            now,
            now,
            null);
    }

    public async Task UpdateProjectIterationSessionStatusAsync(
        string sessionId,
        string status,
        int currentGoalIndex,
        string? latestSummary,
        string? latestEvaluationJson = null,
        string? completedUtc = null,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(sessionId);
        ArgumentException.ThrowIfNullOrWhiteSpace(status);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            UPDATE project_iteration_sessions
            SET status = $status,
                current_goal_index = $current_goal_index,
                latest_summary = $latest_summary,
                latest_evaluation_json = $latest_evaluation_json,
                updated_utc = $updated_utc,
                completed_utc = $completed_utc
            WHERE id = $id;
            """;
        command.Parameters.AddWithValue("$id", sessionId);
        command.Parameters.AddWithValue("$status", status);
        command.Parameters.AddWithValue("$current_goal_index", currentGoalIndex);
        command.Parameters.AddWithValue("$latest_summary", (object?)latestSummary ?? DBNull.Value);
        command.Parameters.AddWithValue("$latest_evaluation_json", (object?)latestEvaluationJson ?? DBNull.Value);
        command.Parameters.AddWithValue("$updated_utc", DateTimeOffset.UtcNow.ToString("O"));
        command.Parameters.AddWithValue("$completed_utc", (object?)completedUtc ?? DBNull.Value);
        await command.ExecuteNonQueryAsync(cancellationToken);
    }

    public async Task<ProjectIterationSessionDetails?> GetLatestProjectIterationSessionAsync(
        string projectId,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        ProjectIterationSessionSnapshot? session = null;
        await using (var command = connection.CreateCommand())
        {
            command.CommandText =
                """
                SELECT id, project_id, account_id, source_kind, source_message, overall_goal, status,
                       current_goal_index, latest_summary, latest_evaluation_json, created_utc, updated_utc, completed_utc
                FROM project_iteration_sessions
                WHERE project_id = $project_id
                ORDER BY created_utc DESC
                LIMIT 1;
                """;
            command.Parameters.AddWithValue("$project_id", projectId);
            await using var reader = await command.ExecuteReaderAsync(cancellationToken);
            if (await reader.ReadAsync(cancellationToken))
            {
                session = new ProjectIterationSessionSnapshot(
                    reader.GetString(0),
                    reader.GetString(1),
                    reader.GetString(2),
                    reader.GetString(3),
                    reader.GetString(4),
                    reader.GetString(5),
                    reader.GetString(6),
                    reader.GetInt32(7),
                    reader.IsDBNull(8) ? null : reader.GetString(8),
                    reader.IsDBNull(9) ? null : reader.GetString(9),
                    reader.GetString(10),
                    reader.GetString(11),
                    reader.IsDBNull(12) ? null : reader.GetString(12));
            }
        }

        if (session is null)
        {
            return null;
        }

        var goals = new List<ProjectIterationGoalSnapshot>();
        await using (var command = connection.CreateCommand())
        {
            command.CommandText =
                """
                SELECT id, session_id, goal_index, title, description, acceptance_hint, status, result_summary,
                       created_utc, updated_utc, completed_utc
                FROM project_iteration_goals
                WHERE session_id = $session_id
                ORDER BY goal_index ASC;
                """;
            command.Parameters.AddWithValue("$session_id", session.SessionId);
            await using var reader = await command.ExecuteReaderAsync(cancellationToken);
            while (await reader.ReadAsync(cancellationToken))
            {
                goals.Add(new ProjectIterationGoalSnapshot(
                    reader.GetString(0),
                    reader.GetString(1),
                    reader.GetInt32(2),
                    reader.GetString(3),
                    reader.GetString(4),
                    reader.IsDBNull(5) ? null : reader.GetString(5),
                    reader.GetString(6),
                    reader.IsDBNull(7) ? null : reader.GetString(7),
                    reader.GetString(8),
                    reader.GetString(9),
                    reader.IsDBNull(10) ? null : reader.GetString(10)));
            }
        }

        var goalRuns = new List<ProjectIterationGoalRunSnapshot>();
        await using (var command = connection.CreateCommand())
        {
            command.CommandText =
                """
                SELECT id, session_id, goal_id, run_id, run_type, created_utc
                FROM project_iteration_goal_runs
                WHERE session_id = $session_id
                ORDER BY created_utc ASC, id ASC;
                """;
            command.Parameters.AddWithValue("$session_id", session.SessionId);
            await using var reader = await command.ExecuteReaderAsync(cancellationToken);
            while (await reader.ReadAsync(cancellationToken))
            {
                goalRuns.Add(new ProjectIterationGoalRunSnapshot(
                    reader.GetString(0),
                    reader.GetString(1),
                    reader.GetString(2),
                    reader.GetString(3),
                    reader.GetString(4),
                    reader.GetString(5)));
            }
        }

        PrototypeIterationPlanEvaluationResult? latestEvaluation = null;
        if (!string.IsNullOrWhiteSpace(session.LatestEvaluationJson))
        {
            try
            {
                latestEvaluation = JsonSerializer.Deserialize<PrototypeIterationPlanEvaluationResult>(session.LatestEvaluationJson!);
            }
            catch (JsonException)
            {
                latestEvaluation = null;
            }
        }

        return new ProjectIterationSessionDetails(session, goals, goalRuns, latestEvaluation);
    }

    public async Task UpdateProjectIterationGoalStatusAsync(
        string goalId,
        string status,
        string? resultSummary,
        string? completedUtc,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(goalId);
        ArgumentException.ThrowIfNullOrWhiteSpace(status);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            UPDATE project_iteration_goals
            SET status = $status,
                result_summary = $result_summary,
                updated_utc = $updated_utc,
                completed_utc = $completed_utc
            WHERE id = $id;
            """;
        command.Parameters.AddWithValue("$id", goalId);
        command.Parameters.AddWithValue("$status", status);
        command.Parameters.AddWithValue("$result_summary", (object?)resultSummary ?? DBNull.Value);
        command.Parameters.AddWithValue("$updated_utc", DateTimeOffset.UtcNow.ToString("O"));
        command.Parameters.AddWithValue("$completed_utc", (object?)completedUtc ?? DBNull.Value);
        await command.ExecuteNonQueryAsync(cancellationToken);
    }

    public async Task UpsertProjectRunMemoryAsync(
        string projectId,
        string scope,
        string status,
        string currentObjective,
        string completedItemsJson,
        string currentBlockersJson,
        string nextRecommendedAction,
        string allowedScopeJson,
        string? lastVerifiedResult,
        string? lastRunOutcome,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(scope);
        ArgumentException.ThrowIfNullOrWhiteSpace(status);
        ArgumentException.ThrowIfNullOrWhiteSpace(currentObjective);
        ArgumentException.ThrowIfNullOrWhiteSpace(completedItemsJson);
        ArgumentException.ThrowIfNullOrWhiteSpace(currentBlockersJson);
        ArgumentException.ThrowIfNullOrWhiteSpace(nextRecommendedAction);
        ArgumentException.ThrowIfNullOrWhiteSpace(allowedScopeJson);

        var now = DateTimeOffset.UtcNow.ToString("O");
        await using var connection = await OpenConnectionAsync(cancellationToken);
        var existingId = await ExecuteScalarStringAsync(
            connection,
            "SELECT id FROM project_run_memories WHERE project_id = $project_id AND scope = $scope;",
            cancellationToken,
            ("$project_id", projectId),
            ("$scope", scope));

        if (string.IsNullOrWhiteSpace(existingId))
        {
            await using var insert = connection.CreateCommand();
            insert.CommandText =
                """
                INSERT INTO project_run_memories (
                    id, project_id, scope, status, current_objective, completed_items_json,
                    current_blockers_json, next_recommended_action, allowed_scope_json,
                    last_verified_result, last_run_outcome, updated_utc)
                VALUES (
                    $id, $project_id, $scope, $status, $current_objective, $completed_items_json,
                    $current_blockers_json, $next_recommended_action, $allowed_scope_json,
                    $last_verified_result, $last_run_outcome, $updated_utc);
                """;
            insert.Parameters.AddWithValue("$id", NewId());
            insert.Parameters.AddWithValue("$project_id", projectId);
            insert.Parameters.AddWithValue("$scope", scope);
            insert.Parameters.AddWithValue("$status", status);
            insert.Parameters.AddWithValue("$current_objective", currentObjective);
            insert.Parameters.AddWithValue("$completed_items_json", completedItemsJson);
            insert.Parameters.AddWithValue("$current_blockers_json", currentBlockersJson);
            insert.Parameters.AddWithValue("$next_recommended_action", nextRecommendedAction);
            insert.Parameters.AddWithValue("$allowed_scope_json", allowedScopeJson);
            insert.Parameters.AddWithValue("$last_verified_result", (object?)lastVerifiedResult ?? DBNull.Value);
            insert.Parameters.AddWithValue("$last_run_outcome", (object?)lastRunOutcome ?? DBNull.Value);
            insert.Parameters.AddWithValue("$updated_utc", now);
            await insert.ExecuteNonQueryAsync(cancellationToken);
            return;
        }

        await using var update = connection.CreateCommand();
        update.CommandText =
            """
            UPDATE project_run_memories
            SET status = $status,
                current_objective = $current_objective,
                completed_items_json = $completed_items_json,
                current_blockers_json = $current_blockers_json,
                next_recommended_action = $next_recommended_action,
                allowed_scope_json = $allowed_scope_json,
                last_verified_result = $last_verified_result,
                last_run_outcome = $last_run_outcome,
                updated_utc = $updated_utc
            WHERE id = $id;
            """;
        update.Parameters.AddWithValue("$id", existingId);
        update.Parameters.AddWithValue("$status", status);
        update.Parameters.AddWithValue("$current_objective", currentObjective);
        update.Parameters.AddWithValue("$completed_items_json", completedItemsJson);
        update.Parameters.AddWithValue("$current_blockers_json", currentBlockersJson);
        update.Parameters.AddWithValue("$next_recommended_action", nextRecommendedAction);
        update.Parameters.AddWithValue("$allowed_scope_json", allowedScopeJson);
        update.Parameters.AddWithValue("$last_verified_result", (object?)lastVerifiedResult ?? DBNull.Value);
        update.Parameters.AddWithValue("$last_run_outcome", (object?)lastRunOutcome ?? DBNull.Value);
        update.Parameters.AddWithValue("$updated_utc", now);
        await update.ExecuteNonQueryAsync(cancellationToken);
    }

    public async Task<ProjectRunMemorySnapshot?> GetProjectRunMemoryAsync(
        string projectId,
        string scope,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(scope);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT id, project_id, scope, status, current_objective, completed_items_json,
                   current_blockers_json, next_recommended_action, allowed_scope_json,
                   last_verified_result, last_run_outcome, updated_utc
            FROM project_run_memories
            WHERE project_id = $project_id AND scope = $scope
            LIMIT 1;
            """;
        command.Parameters.AddWithValue("$project_id", projectId);
        command.Parameters.AddWithValue("$scope", scope);
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        if (!await reader.ReadAsync(cancellationToken))
        {
            return null;
        }

        return new ProjectRunMemorySnapshot(
            reader.GetString(0),
            reader.GetString(1),
            reader.GetString(2),
            reader.GetString(3),
            reader.GetString(4),
            reader.GetString(5),
            reader.GetString(6),
            reader.GetString(7),
            reader.GetString(8),
            reader.IsDBNull(9) ? null : reader.GetString(9),
            reader.IsDBNull(10) ? null : reader.GetString(10),
            reader.GetString(11));
    }

    public async Task LinkProjectIterationGoalRunAsync(
        string sessionId,
        string goalId,
        string runId,
        string runType,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(sessionId);
        ArgumentException.ThrowIfNullOrWhiteSpace(goalId);
        ArgumentException.ThrowIfNullOrWhiteSpace(runId);
        ArgumentException.ThrowIfNullOrWhiteSpace(runType);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            INSERT INTO project_iteration_goal_runs (id, session_id, goal_id, run_id, run_type, created_utc)
            VALUES ($id, $session_id, $goal_id, $run_id, $run_type, $created_utc);
            """;
        command.Parameters.AddWithValue("$id", NewId());
        command.Parameters.AddWithValue("$session_id", sessionId);
        command.Parameters.AddWithValue("$goal_id", goalId);
        command.Parameters.AddWithValue("$run_id", runId);
        command.Parameters.AddWithValue("$run_type", runType);
        command.Parameters.AddWithValue("$created_utc", DateTimeOffset.UtcNow.ToString("O"));
        await command.ExecuteNonQueryAsync(cancellationToken);
    }

    public async Task<ProjectPrototypeDraftSnapshot?> GetProjectPrototypeDraftAsync(
        string projectId,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT
                project_id,
                status,
                run_id,
                file_name,
                prototype_slug,
                hypothesis,
                core_player_fantasy,
                minimum_playable_loop,
                success_criteria_json,
                game_feature,
                core_gameplay_loop,
                win_fail_conditions,
                matched_fields_json,
                warnings_json,
                failure_code,
                line_count,
                byte_count,
                updated_utc
            FROM project_prototype_drafts
            WHERE project_id = $project_id;
            """;
        command.Parameters.AddWithValue("$project_id", projectId);

        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        if (!await reader.ReadAsync(cancellationToken))
        {
            return null;
        }

        return new ProjectPrototypeDraftSnapshot(
            reader.GetString(0),
            reader.GetString(1),
            reader.IsDBNull(2) ? null : reader.GetString(2),
            reader.IsDBNull(3) ? null : reader.GetString(3),
            reader.IsDBNull(4) ? null : reader.GetString(4),
            reader.IsDBNull(5) ? null : reader.GetString(5),
            reader.IsDBNull(6) ? null : reader.GetString(6),
            reader.IsDBNull(7) ? null : reader.GetString(7),
            reader.GetString(8),
            reader.IsDBNull(9) ? null : reader.GetString(9),
            reader.IsDBNull(10) ? null : reader.GetString(10),
            reader.IsDBNull(11) ? null : reader.GetString(11),
            reader.GetString(12),
            reader.GetString(13),
            reader.IsDBNull(14) ? null : reader.GetString(14),
            reader.GetInt32(15),
            reader.GetInt32(16),
            reader.GetString(17));
    }

    public async Task UpsertProjectPrototypeDraftAsync(
        string projectId,
        string status,
        string? runId,
        string? fileName,
        string? prototypeSlug,
        string? hypothesis,
        string? corePlayerFantasy,
        string? minimumPlayableLoop,
        string successCriteriaJson,
        string? gameFeature,
        string? coreGameplayLoop,
        string? winFailConditions,
        string matchedFieldsJson,
        string warningsJson,
        string? failureCode,
        int lineCount,
        int byteCount,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(status);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            INSERT INTO project_prototype_drafts (
                project_id,
                status,
                run_id,
                file_name,
                prototype_slug,
                hypothesis,
                core_player_fantasy,
                minimum_playable_loop,
                success_criteria_json,
                game_feature,
                core_gameplay_loop,
                win_fail_conditions,
                matched_fields_json,
                warnings_json,
                failure_code,
                line_count,
                byte_count,
                updated_utc)
            VALUES (
                $project_id,
                $status,
                $run_id,
                $file_name,
                $prototype_slug,
                $hypothesis,
                $core_player_fantasy,
                $minimum_playable_loop,
                $success_criteria_json,
                $game_feature,
                $core_gameplay_loop,
                $win_fail_conditions,
                $matched_fields_json,
                $warnings_json,
                $failure_code,
                $line_count,
                $byte_count,
                $updated_utc)
            ON CONFLICT(project_id) DO UPDATE SET
                status = excluded.status,
                run_id = excluded.run_id,
                file_name = excluded.file_name,
                prototype_slug = excluded.prototype_slug,
                hypothesis = excluded.hypothesis,
                core_player_fantasy = excluded.core_player_fantasy,
                minimum_playable_loop = excluded.minimum_playable_loop,
                success_criteria_json = excluded.success_criteria_json,
                game_feature = excluded.game_feature,
                core_gameplay_loop = excluded.core_gameplay_loop,
                win_fail_conditions = excluded.win_fail_conditions,
                matched_fields_json = excluded.matched_fields_json,
                warnings_json = excluded.warnings_json,
                failure_code = excluded.failure_code,
                line_count = excluded.line_count,
                byte_count = excluded.byte_count,
                updated_utc = excluded.updated_utc;
            """;
        command.Parameters.AddWithValue("$project_id", projectId);
        command.Parameters.AddWithValue("$status", status);
        command.Parameters.AddWithValue("$run_id", (object?)runId ?? DBNull.Value);
        command.Parameters.AddWithValue("$file_name", (object?)fileName ?? DBNull.Value);
        command.Parameters.AddWithValue("$prototype_slug", (object?)prototypeSlug ?? DBNull.Value);
        command.Parameters.AddWithValue("$hypothesis", (object?)hypothesis ?? DBNull.Value);
        command.Parameters.AddWithValue("$core_player_fantasy", (object?)corePlayerFantasy ?? DBNull.Value);
        command.Parameters.AddWithValue("$minimum_playable_loop", (object?)minimumPlayableLoop ?? DBNull.Value);
        command.Parameters.AddWithValue("$success_criteria_json", successCriteriaJson);
        command.Parameters.AddWithValue("$game_feature", (object?)gameFeature ?? DBNull.Value);
        command.Parameters.AddWithValue("$core_gameplay_loop", (object?)coreGameplayLoop ?? DBNull.Value);
        command.Parameters.AddWithValue("$win_fail_conditions", (object?)winFailConditions ?? DBNull.Value);
        command.Parameters.AddWithValue("$matched_fields_json", matchedFieldsJson);
        command.Parameters.AddWithValue("$warnings_json", warningsJson);
        command.Parameters.AddWithValue("$failure_code", (object?)failureCode ?? DBNull.Value);
        command.Parameters.AddWithValue("$line_count", lineCount);
        command.Parameters.AddWithValue("$byte_count", byteCount);
        command.Parameters.AddWithValue("$updated_utc", DateTimeOffset.UtcNow.ToString("O"));
        await command.ExecuteNonQueryAsync(cancellationToken);
    }

    private async Task<int> GetProjectLimitInsideTransactionAsync(SqliteConnection connection, string accountId, CancellationToken cancellationToken)
    {
        var value = await ExecuteScalarLongAsync(
            connection,
            "SELECT project_limit FROM project_limits WHERE account_id = $account_id;",
            cancellationToken,
            ("$account_id", accountId));

        return value is null ? _options.HostedProjectLimit : checked((int)value.Value);
    }

    private async Task<SqliteConnection> OpenConnectionAsync(CancellationToken cancellationToken)
    {
        var connection = new SqliteConnection(_connectionString);
        await connection.OpenAsync(cancellationToken);

        await using var command = connection.CreateCommand();
        command.CommandText = "PRAGMA foreign_keys = ON;";
        await command.ExecuteNonQueryAsync(cancellationToken);

        return connection;
    }

    private static async Task UpsertProjectLimitAsync(SqliteConnection connection, string accountId, int projectLimit, string now, CancellationToken cancellationToken)
    {
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            INSERT INTO project_limits (account_id, project_limit, created_utc, updated_utc)
            VALUES ($account_id, $project_limit, $created_utc, $updated_utc)
            ON CONFLICT(account_id) DO UPDATE SET
                project_limit = excluded.project_limit,
                updated_utc = excluded.updated_utc;
            """;
        command.Parameters.AddWithValue("$account_id", accountId);
        command.Parameters.AddWithValue("$project_limit", projectLimit);
        command.Parameters.AddWithValue("$created_utc", now);
        command.Parameters.AddWithValue("$updated_utc", now);
        await command.ExecuteNonQueryAsync(cancellationToken);
    }

    private static async Task<string?> ExecuteScalarStringAsync(
        SqliteConnection connection,
        string sql,
        CancellationToken cancellationToken,
        params (string Name, object Value)[] parameters)
    {
        await using var command = connection.CreateCommand();
        command.CommandText = sql;
        foreach (var parameter in parameters)
        {
            command.Parameters.AddWithValue(parameter.Name, parameter.Value);
        }

        var result = await command.ExecuteScalarAsync(cancellationToken);
        return result as string;
    }

    private static async Task<long?> ExecuteScalarLongAsync(
        SqliteConnection connection,
        string sql,
        CancellationToken cancellationToken,
        params (string Name, object Value)[] parameters)
    {
        await using var command = connection.CreateCommand();
        command.CommandText = sql;
        foreach (var parameter in parameters)
        {
            command.Parameters.AddWithValue(parameter.Name, parameter.Value);
        }

        var result = await command.ExecuteScalarAsync(cancellationToken);
        return result is null or DBNull ? null : Convert.ToInt64(result);
    }

    private static string NewId()
    {
        return Guid.NewGuid().ToString("N");
    }
}
