using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
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

        await using var transaction = await connection.BeginTransactionAsync(cancellationToken);

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
