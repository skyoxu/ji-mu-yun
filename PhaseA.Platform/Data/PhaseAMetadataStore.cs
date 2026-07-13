using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workflow;
using System.Collections.Concurrent;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using SQLitePCL;

namespace PhaseA.Platform.Data;

public sealed class PhaseAMetadataStore
{
    private static readonly ConcurrentDictionary<string, SemaphoreSlim> AdminReviewSidecarLocks = new(StringComparer.Ordinal);
    private static readonly ConcurrentDictionary<string, SemaphoreSlim> AdminReviewUpsertLocks = new(StringComparer.Ordinal);
    private static readonly IReadOnlySet<string> AdminReviewSeverities = new HashSet<string>(
        ["P0", "P1", "P2"],
        StringComparer.Ordinal);
    private static readonly IReadOnlySet<string> AdminReviewEvidenceKinds = new HashSet<string>(
        ["log", "artifact", "sidecar", "screenshot", "db_row", "smoke", "validator"],
        StringComparer.Ordinal);
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
            await SyncAdminSecretsAsync(connection, existingId, cancellationToken);
            await UpsertProjectLimitAsync(connection, existingId, _options.HostedProjectLimit, now, cancellationToken);
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

    public async Task<AccountSnapshot?> ResolveAccountByTokenHashAsync(string tokenHash, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(tokenHash);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT id, username, is_admin, is_disabled
            FROM accounts
            WHERE token_hash = $token_hash
              AND is_disabled = 0
              AND (valid_until_utc IS NULL OR valid_until_utc > $now_utc)
            LIMIT 1;
            """;
        command.Parameters.AddWithValue("$token_hash", tokenHash);
        command.Parameters.AddWithValue("$now_utc", DateTimeOffset.UtcNow.ToString("O"));

        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        if (!await reader.ReadAsync(cancellationToken))
        {
            return null;
        }

        return new AccountSnapshot(
            reader.GetString(0),
            reader.GetString(1),
            reader.GetInt64(2) == 1,
            reader.GetInt64(3) == 1);
    }

    public async Task<AdminCreateUserResult> CreateUserAccountAsync(
        string username,
        int projectLimit,
        int? validDays = null,
        decimal? spendLimitCny = null,
        bool requireAiCodeMirrorKey = false,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(username);
        if (projectLimit < 1)
        {
            throw new ArgumentOutOfRangeException(nameof(projectLimit), "Project limit must be greater than zero.");
        }

        var normalizedUsername = username.Trim();
        var token = GenerateAccountToken();
        var tokenHash = PhaseAAuth.HashTokenForStorage(token);
        var now = DateTimeOffset.UtcNow.ToString("O");
        var validUntilUtc = validDays is > 0
            ? DateTimeOffset.UtcNow.AddDays(validDays.Value).ToString("O")
            : null;
        var accountId = NewId();

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var transaction = (SqliteTransaction)await connection.BeginTransactionAsync(cancellationToken);
        await using (var command = connection.CreateCommand())
        {
            command.Transaction = transaction;
            command.CommandText =
                """
                INSERT INTO accounts (id, username, password_hash, token_hash, is_admin, valid_until_utc, spend_limit_cny, created_utc)
                VALUES ($id, $username, NULL, $token_hash, 0, $valid_until_utc, $spend_limit_cny, $created_utc);
                """;
            command.Parameters.AddWithValue("$id", accountId);
            command.Parameters.AddWithValue("$username", normalizedUsername);
            command.Parameters.AddWithValue("$token_hash", tokenHash);
            command.Parameters.AddWithValue("$valid_until_utc", (object?)validUntilUtc ?? DBNull.Value);
            command.Parameters.AddWithValue("$spend_limit_cny", spendLimitCny is null ? DBNull.Value : spendLimitCny.Value.ToString(System.Globalization.CultureInfo.InvariantCulture));
            command.Parameters.AddWithValue("$created_utc", now);
            await command.ExecuteNonQueryAsync(cancellationToken);
        }

        await UpsertProjectLimitAsync(connection, accountId, projectLimit, now, cancellationToken);
        var assignedKeyName = requireAiCodeMirrorKey
            ? await AssignNextAvailableAiCodeMirrorKeyInsideTransactionAsync(connection, transaction, accountId, now, cancellationToken)
            : null;
        if (requireAiCodeMirrorKey && string.IsNullOrWhiteSpace(assignedKeyName))
        {
            await transaction.RollbackAsync(cancellationToken);
            throw new InvalidOperationException("aicodemirror_key_pool_exhausted");
        }

        await transaction.CommitAsync(cancellationToken);

        return new AdminCreateUserResult(accountId, normalizedUsername, token, projectLimit, validUntilUtc, spendLimitCny, assignedKeyName);
    }

    public Task<AdminCreateUserResult> CreateUserAccountAsync(
        string username,
        int projectLimit,
        CancellationToken cancellationToken)
    {
        return CreateUserAccountAsync(username, projectLimit, null, null, false, cancellationToken);
    }

    public async Task<IReadOnlyList<AdminUserListItem>> ListAccountsAsync(CancellationToken cancellationToken = default)
    {
        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT
                a.id,
                a.username,
                a.is_admin,
                a.is_disabled,
                COALESCE(pl.project_limit, $default_project_limit),
                COUNT(p.id),
                a.created_utc,
                a.valid_until_utc,
                a.spend_limit_cny,
                ak.key_name
            FROM accounts a
            LEFT JOIN project_limits pl ON pl.account_id = a.id
            LEFT JOIN projects p ON p.account_id = a.id
            LEFT JOIN aicodemirror_key_pool ak ON ak.account_id = a.id
            GROUP BY a.id, a.username, a.is_admin, a.is_disabled, pl.project_limit, a.created_utc, a.valid_until_utc, a.spend_limit_cny, ak.key_name
            ORDER BY a.is_admin DESC, a.created_utc ASC, a.username ASC;
            """;
        command.Parameters.AddWithValue("$default_project_limit", _options.HostedProjectLimit);

        var accounts = new List<AdminUserListItem>();
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            accounts.Add(new AdminUserListItem(
                reader.GetString(0),
                reader.GetString(1),
                reader.GetInt64(2) == 1,
                reader.GetInt64(3) == 1,
                checked((int)reader.GetInt64(4)),
                checked((int)reader.GetInt64(5)),
                reader.GetString(6),
                reader.IsDBNull(7) ? null : reader.GetString(7),
                reader.IsDBNull(8) ? null : decimal.Parse(reader.GetString(8), System.Globalization.CultureInfo.InvariantCulture),
                reader.IsDBNull(9) ? null : reader.GetString(9)));
        }

        return accounts;
    }

    public async Task<bool> UpdateUserLimitsAsync(
        string accountId,
        int? validDays,
        decimal? spendLimitCny,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        if (validDays is < 0)
        {
            throw new ArgumentOutOfRangeException(nameof(validDays), "Valid days must be null or non-negative.");
        }

        var validUntilUtc = validDays is > 0
            ? DateTimeOffset.UtcNow.AddDays(validDays.Value).ToString("O")
            : null;
        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            UPDATE accounts
            SET valid_until_utc = $valid_until_utc,
                spend_limit_cny = $spend_limit_cny
            WHERE id = $account_id
              AND is_admin = 0;
            """;
        command.Parameters.AddWithValue("$account_id", accountId);
        command.Parameters.AddWithValue("$valid_until_utc", (object?)validUntilUtc ?? DBNull.Value);
        command.Parameters.AddWithValue("$spend_limit_cny", spendLimitCny is null ? DBNull.Value : spendLimitCny.Value.ToString(System.Globalization.CultureInfo.InvariantCulture));
        return await command.ExecuteNonQueryAsync(cancellationToken) > 0;
    }

    public async Task<bool> SetUserDisabledAsync(
        string accountId,
        bool disabled,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            UPDATE accounts
            SET is_disabled = $is_disabled
            WHERE id = $account_id
              AND is_admin = 0;
            """;
        command.Parameters.AddWithValue("$account_id", accountId);
        command.Parameters.AddWithValue("$is_disabled", disabled ? 1 : 0);
        return await command.ExecuteNonQueryAsync(cancellationToken) > 0;
    }

    public async Task<AdminRotateUserTokenResult?> RotateUserTokenAsync(
        string accountId,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);

        var token = GenerateAccountToken();
        var tokenHash = PhaseAAuth.HashTokenForStorage(token);
        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var transaction = (SqliteTransaction)await connection.BeginTransactionAsync(cancellationToken);

        string? username;
        await using (var lookup = connection.CreateCommand())
        {
            lookup.Transaction = transaction;
            lookup.CommandText =
                """
                SELECT username
                FROM accounts
                WHERE id = $account_id
                  AND is_admin = 0;
                """;
            lookup.Parameters.AddWithValue("$account_id", accountId);
            username = await lookup.ExecuteScalarAsync(cancellationToken) as string;
        }

        if (string.IsNullOrWhiteSpace(username))
        {
            await transaction.RollbackAsync(cancellationToken);
            return null;
        }

        await using (var update = connection.CreateCommand())
        {
            update.Transaction = transaction;
            update.CommandText =
                """
                UPDATE accounts
                SET token_hash = $token_hash,
                    is_disabled = 0
                WHERE id = $account_id
                  AND is_admin = 0;
                """;
            update.Parameters.AddWithValue("$account_id", accountId);
            update.Parameters.AddWithValue("$token_hash", tokenHash);
            await update.ExecuteNonQueryAsync(cancellationToken);
        }

        await transaction.CommitAsync(cancellationToken);
        return new AdminRotateUserTokenResult(accountId, username, token);
    }

    public async Task RecordAdminAccountAuditEventAsync(
        string actorAccountId,
        string action,
        string? targetAccountId,
        object metadata,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(actorAccountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(action);
        ArgumentNullException.ThrowIfNull(metadata);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            INSERT INTO admin_account_audit_events (
                id,
                actor_account_id,
                action,
                target_account_id,
                metadata_json,
                created_utc)
            VALUES (
                $id,
                $actor_account_id,
                $action,
                $target_account_id,
                $metadata_json,
                $created_utc);
            """;
        command.Parameters.AddWithValue("$id", NewId());
        command.Parameters.AddWithValue("$actor_account_id", actorAccountId);
        command.Parameters.AddWithValue("$action", action.Trim());
        command.Parameters.AddWithValue("$target_account_id", (object?)targetAccountId ?? DBNull.Value);
        command.Parameters.AddWithValue("$metadata_json", SecretRedactionPolicy.RedactForPersistence(JsonSerializer.Serialize(metadata)));
        command.Parameters.AddWithValue("$created_utc", DateTimeOffset.UtcNow.ToString("O"));
        await command.ExecuteNonQueryAsync(cancellationToken);
    }

    public Task<IReadOnlyList<AdminAccountAuditEvent>> ListAdminAccountAuditEventsAsync(
        int limit = 100,
        CancellationToken cancellationToken = default)
    {
        return ListAdminAccountAuditEventsAsync(
            new AdminAccountAuditQuery(limit, 0, null, null),
            cancellationToken);
    }

    public async Task<IReadOnlyList<AdminAccountAuditEvent>> ListAdminAccountAuditEventsAsync(
        AdminAccountAuditQuery query,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(query);
        var limit = Math.Clamp(query.Limit, 1, 500);
        var offset = Math.Max(0, query.Offset);
        if (limit < 1)
        {
            throw new ArgumentOutOfRangeException(nameof(limit), "Limit must be greater than zero.");
        }

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT id, actor_account_id, action, target_account_id, metadata_json, created_utc
            FROM admin_account_audit_events
            WHERE ($action IS NULL OR action = $action)
              AND ($target_account_id IS NULL OR target_account_id = $target_account_id)
            ORDER BY created_utc DESC, id DESC
            LIMIT $limit OFFSET $offset;
            """;
        command.Parameters.AddWithValue("$action", string.IsNullOrWhiteSpace(query.Action) ? DBNull.Value : query.Action.Trim());
        command.Parameters.AddWithValue("$target_account_id", string.IsNullOrWhiteSpace(query.TargetAccountId) ? DBNull.Value : query.TargetAccountId.Trim());
        command.Parameters.AddWithValue("$limit", limit);
        command.Parameters.AddWithValue("$offset", offset);

        var events = new List<AdminAccountAuditEvent>();
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            events.Add(new AdminAccountAuditEvent(
                reader.GetString(0),
                reader.GetString(1),
                reader.GetString(2),
                reader.IsDBNull(3) ? null : reader.GetString(3),
                reader.GetString(4),
                reader.GetString(5)));
        }

        return events;
    }

    public async Task<bool> ProjectBelongsToAccountAsync(
        string accountId,
        string projectId,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        var count = await ExecuteScalarLongAsync(
            connection,
            "SELECT COUNT(*) FROM projects WHERE id = $project_id AND account_id = $account_id;",
            cancellationToken,
            ("$project_id", projectId),
            ("$account_id", accountId)) ?? 0;
        return count > 0;
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
                    WHEN bootstrap_status = 'running'
                     AND NOT EXISTS (
                        SELECT 1
                        FROM runs
                        WHERE runs.project_id = projects.id
                          AND runs.run_type = 'chapter2-bootstrap'
                          AND runs.status IN ('queued', 'running')
                    ) THEN 'failed'
                    ELSE bootstrap_status
                END,
                bootstrap_error = CASE
                    WHEN bootstrap_status IN ('initial', 'running') AND EXISTS (
                        SELECT 1
                        FROM runs
                        WHERE runs.project_id = projects.id
                          AND runs.run_type = 'chapter2-bootstrap'
                          AND runs.status = 'failed'
                    ) THEN 'Chapter 2 initialization failed.'
                    WHEN bootstrap_status = 'running'
                     AND NOT EXISTS (
                        SELECT 1
                        FROM runs
                        WHERE runs.project_id = projects.id
                          AND runs.run_type = 'chapter2-bootstrap'
                          AND runs.status IN ('queued', 'running')
                    )
                     AND NOT EXISTS (
                        SELECT 1
                        FROM runs
                        WHERE runs.project_id = projects.id
                          AND runs.run_type = 'chapter2-bootstrap'
                          AND runs.status IN ('succeeded', 'failed')
                    ) THEN 'Project initialization was left in running state without an active Chapter 2 bootstrap run.'
                    ELSE bootstrap_error
                END
            WHERE bootstrap_status IN ('initial', 'running');
            """;
        await command.ExecuteNonQueryAsync(cancellationToken);
    }

    public async Task<IReadOnlyList<StaleProjectInitializationSnapshot>> ListOrphanedProjectInitializationsAsync(
        CancellationToken cancellationToken = default)
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
                w.root_path,
                '',
                'missing',
                p.created_utc,
                NULL
            FROM projects p
            INNER JOIN workspaces w ON w.project_id = p.id
            WHERE p.bootstrap_status = 'running'
              AND NOT EXISTS (
                  SELECT 1
                  FROM runs r
                  WHERE r.project_id = p.id
                    AND r.run_type = 'chapter2-bootstrap'
              )
            ORDER BY p.created_utc ASC;
            """;

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

            if (string.Equals(run.RunType, "prototype-iteration-goal", StringComparison.Ordinal))
            {
                const string goalSummary = "本轮目标执行因服务重启中断，已恢复为可重新执行状态。";
                await using (var goalCommand = connection.CreateCommand())
                {
                    goalCommand.Transaction = transaction;
                    goalCommand.CommandText =
                        """
                        UPDATE project_iteration_goals
                        SET status = 'pending',
                            result_summary = CASE
                                WHEN result_summary IS NULL OR result_summary = '' THEN $goal_summary
                                ELSE result_summary
                            END,
                            updated_utc = $finished_utc,
                            completed_utc = NULL
                        WHERE status = 'running'
                          AND session_id IN (
                              SELECT id
                              FROM project_iteration_sessions
                              WHERE project_id = $project_id
                                AND status = 'running'
                          )
                          AND (
                              id IN (
                                  SELECT goal_id
                                  FROM project_iteration_goal_runs
                                  WHERE run_id = $run_id
                                    AND run_type = 'prototype-iteration-goal'
                              )
                              OR NOT EXISTS (
                                  SELECT 1
                                  FROM project_iteration_goal_runs
                                  WHERE run_id = $run_id
                                    AND run_type = 'prototype-iteration-goal'
                              )
                          );
                        """;
                    goalCommand.Parameters.AddWithValue("$project_id", run.ProjectId);
                    goalCommand.Parameters.AddWithValue("$run_id", run.RunId);
                    goalCommand.Parameters.AddWithValue("$goal_summary", goalSummary);
                    goalCommand.Parameters.AddWithValue("$finished_utc", finishedUtc);
                    await goalCommand.ExecuteNonQueryAsync(cancellationToken);
                }

                await using (var sessionCommand = connection.CreateCommand())
                {
                    sessionCommand.Transaction = transaction;
                    sessionCommand.CommandText =
                        """
                        UPDATE project_iteration_sessions
                        SET status = 'paused_for_review',
                            current_goal_index = COALESCE(
                                (
                                    SELECT g.goal_index
                                    FROM project_iteration_goals g
                                    INNER JOIN project_iteration_goal_runs gr ON gr.goal_id = g.id
                                    WHERE gr.run_id = $run_id
                                      AND gr.run_type = 'prototype-iteration-goal'
                                    ORDER BY g.goal_index ASC
                                    LIMIT 1
                                ),
                                (
                                    SELECT g.goal_index
                                    FROM project_iteration_goals g
                                    WHERE g.session_id = project_iteration_sessions.id
                                      AND g.status = 'pending'
                                    ORDER BY g.goal_index ASC
                                    LIMIT 1
                                ),
                                current_goal_index),
                            latest_summary = $goal_summary,
                            updated_utc = $finished_utc,
                            completed_utc = NULL
                        WHERE project_id = $project_id
                          AND status = 'running'
                          AND (
                              id IN (
                                  SELECT session_id
                                  FROM project_iteration_goal_runs
                                  WHERE run_id = $run_id
                                    AND run_type = 'prototype-iteration-goal'
                              )
                              OR NOT EXISTS (
                                  SELECT 1
                                  FROM project_iteration_goal_runs
                                  WHERE run_id = $run_id
                                    AND run_type = 'prototype-iteration-goal'
                              )
                          );
                        """;
                    sessionCommand.Parameters.AddWithValue("$project_id", run.ProjectId);
                    sessionCommand.Parameters.AddWithValue("$run_id", run.RunId);
                    sessionCommand.Parameters.AddWithValue("$goal_summary", goalSummary);
                    sessionCommand.Parameters.AddWithValue("$finished_utc", finishedUtc);
                    await sessionCommand.ExecuteNonQueryAsync(cancellationToken);
                }
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

    public async Task<AiCodeMirrorKeyPoolEntry> UpsertAiCodeMirrorKeyAsync(
        AiCodeMirrorKeyImportCommand create,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(create);
        ArgumentException.ThrowIfNullOrWhiteSpace(create.KeyName);

        var keyName = create.KeyName.Trim();
        var now = DateTimeOffset.UtcNow.ToString("O");
        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            INSERT INTO aicodemirror_key_pool (
                id,
                key_name,
                status,
                notes,
                valid_days,
                expires_utc,
                credential_imported,
                imported_utc,
                updated_utc)
            VALUES (
                $id,
                $key_name,
                'available',
                $notes,
                $valid_days,
                $expires_utc,
                $credential_imported,
                $imported_utc,
                $updated_utc)
            ON CONFLICT(key_name) DO UPDATE SET
                notes = excluded.notes,
                valid_days = excluded.valid_days,
                expires_utc = excluded.expires_utc,
                credential_imported = CASE
                    WHEN excluded.credential_imported = 1 THEN 1
                    ELSE aicodemirror_key_pool.credential_imported
                END,
                updated_utc = excluded.updated_utc;
            """;
        var expiresUtc = create.ValidDays is > 0
            ? DateTimeOffset.UtcNow.AddDays(create.ValidDays.Value).ToString("O")
            : null;
        command.Parameters.AddWithValue("$id", NewId());
        command.Parameters.AddWithValue("$key_name", keyName);
        command.Parameters.AddWithValue("$notes", (object?)create.Notes ?? DBNull.Value);
        command.Parameters.AddWithValue("$valid_days", (object?)create.ValidDays ?? DBNull.Value);
        command.Parameters.AddWithValue("$expires_utc", (object?)expiresUtc ?? DBNull.Value);
        command.Parameters.AddWithValue("$credential_imported", create.CredentialImported ? 1 : 0);
        command.Parameters.AddWithValue("$imported_utc", now);
        command.Parameters.AddWithValue("$updated_utc", now);
        await command.ExecuteNonQueryAsync(cancellationToken);

        return (await GetAiCodeMirrorKeyByNameAsync(keyName, cancellationToken))!;
    }

    public async Task<AiCodeMirrorKeyAssignmentResult> AssignAiCodeMirrorKeyToAccountAsync(
        string keyName,
        string accountId,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(keyName);
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);

        var now = DateTimeOffset.UtcNow.ToString("O");
        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var transaction = (SqliteTransaction)await connection.BeginTransactionAsync(cancellationToken);

        var accountExists = await ExecuteScalarLongAsync(
            connection,
            "SELECT COUNT(1) FROM accounts WHERE id = $account_id;",
            cancellationToken,
            ("$account_id", accountId));
        if (accountExists is not > 0)
        {
            await transaction.RollbackAsync(cancellationToken);
            return AiCodeMirrorKeyAssignmentResult.Failure("account_not_found");
        }

        var key = await ReadAiCodeMirrorKeyByNameAsync(connection, keyName.Trim(), transaction, cancellationToken);
        if (key is null)
        {
            await transaction.RollbackAsync(cancellationToken);
            return AiCodeMirrorKeyAssignmentResult.Failure("aicodemirror_key_not_found");
        }

        if (string.Equals(key.Status, "closed", StringComparison.OrdinalIgnoreCase))
        {
            await transaction.RollbackAsync(cancellationToken);
            return AiCodeMirrorKeyAssignmentResult.Failure("aicodemirror_key_closed");
        }

        if (!string.IsNullOrWhiteSpace(key.ExpiresUtc) &&
            string.CompareOrdinal(key.ExpiresUtc, now) <= 0)
        {
            await transaction.RollbackAsync(cancellationToken);
            return AiCodeMirrorKeyAssignmentResult.Failure("aicodemirror_key_expired");
        }

        if (!key.CredentialImported)
        {
            await transaction.RollbackAsync(cancellationToken);
            return AiCodeMirrorKeyAssignmentResult.Failure("aicodemirror_key_credential_not_imported");
        }

        if (!string.IsNullOrWhiteSpace(key.AccountId) &&
            !string.Equals(key.AccountId, accountId, StringComparison.Ordinal))
        {
            await transaction.RollbackAsync(cancellationToken);
            return AiCodeMirrorKeyAssignmentResult.Failure("aicodemirror_key_already_assigned");
        }

        await using var clearCommand = connection.CreateCommand();
        clearCommand.Transaction = transaction;
        clearCommand.CommandText =
            """
            UPDATE aicodemirror_key_pool
            SET account_id = NULL,
                status = 'available',
                assigned_utc = NULL,
                updated_utc = $updated_utc
            WHERE account_id = $account_id
              AND key_name <> $key_name;
            """;
        clearCommand.Parameters.AddWithValue("$account_id", accountId);
        clearCommand.Parameters.AddWithValue("$key_name", keyName.Trim());
        clearCommand.Parameters.AddWithValue("$updated_utc", now);
        await clearCommand.ExecuteNonQueryAsync(cancellationToken);

        await using var assignCommand = connection.CreateCommand();
        assignCommand.Transaction = transaction;
        assignCommand.CommandText =
            """
            UPDATE aicodemirror_key_pool
            SET account_id = $account_id,
                status = 'assigned',
                assigned_utc = COALESCE(assigned_utc, $assigned_utc),
                updated_utc = $updated_utc
            WHERE key_name = $key_name;
            """;
        assignCommand.Parameters.AddWithValue("$account_id", accountId);
        assignCommand.Parameters.AddWithValue("$key_name", keyName.Trim());
        assignCommand.Parameters.AddWithValue("$assigned_utc", now);
        assignCommand.Parameters.AddWithValue("$updated_utc", now);
        await assignCommand.ExecuteNonQueryAsync(cancellationToken);

        await transaction.CommitAsync(cancellationToken);
        var assigned = await GetAiCodeMirrorKeyForAccountAsync(accountId, cancellationToken);
        return assigned is null
            ? AiCodeMirrorKeyAssignmentResult.Failure("aicodemirror_key_assignment_failed")
            : AiCodeMirrorKeyAssignmentResult.Ok(assigned);
    }

    public async Task<AiCodeMirrorKeyPoolEntry?> GetAiCodeMirrorKeyForAccountAsync(
        string accountId,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT id, key_name, account_id, status, notes, valid_days, expires_utc, credential_imported, imported_utc, assigned_utc, updated_utc
            FROM aicodemirror_key_pool
            WHERE account_id = $account_id
            ORDER BY assigned_utc DESC, updated_utc DESC
            LIMIT 1;
            """;
        command.Parameters.AddWithValue("$account_id", accountId);
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        return await reader.ReadAsync(cancellationToken) ? ReadAiCodeMirrorKey(reader) : null;
    }

    public async Task<IReadOnlyList<AiCodeMirrorKeyPoolEntry>> ListAiCodeMirrorKeysAsync(CancellationToken cancellationToken = default)
    {
        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT id, key_name, account_id, status, notes, valid_days, expires_utc, credential_imported, imported_utc, assigned_utc, updated_utc
            FROM aicodemirror_key_pool
            ORDER BY imported_utc DESC, key_name;
            """;
        var items = new List<AiCodeMirrorKeyPoolEntry>();
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            items.Add(ReadAiCodeMirrorKey(reader));
        }

        return items;
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
        ArgumentException.ThrowIfNullOrWhiteSpace(create.GameTypeMatchJson);
        ArgumentException.ThrowIfNullOrWhiteSpace(create.TemplateRuleId);
        ArgumentException.ThrowIfNullOrWhiteSpace(create.WorkspaceRootPath);
        ArgumentException.ThrowIfNullOrWhiteSpace(create.RepoPath);
        ArgumentException.ThrowIfNullOrWhiteSpace(create.RuntimePath);
        ArgumentException.ThrowIfNullOrWhiteSpace(create.MetaPath);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var transaction = await connection.BeginTransactionAsync(cancellationToken);

        var limit = await GetProjectLimitInsideTransactionAsync(connection, create.AccountId, cancellationToken);
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
        var createdUtc = DateTimeOffset.UtcNow.ToString("O");
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
                    game_type_match_json,
                    created_utc,
                    last_activity_utc)
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
                    $game_type_match_json,
                    $created_utc,
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
            command.Parameters.AddWithValue("$game_type_match_json", create.GameTypeMatchJson);
            command.Parameters.AddWithValue("$created_utc", createdUtc);
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
            command.Parameters.AddWithValue("$created_utc", createdUtc);
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
                p.game_type_match_json,
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
            reader.GetString(11),
            reader.GetString(12),
            reader.GetString(13),
            reader.GetString(14),
            reader.GetString(15),
            reader.GetString(10));
    }

    public async Task<IReadOnlyList<ProjectListItem>> ListProjectsAsync(string accountId, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);

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
                p.bootstrap_status,
                p.bootstrap_error,
                w.root_path,
                p.created_utc,
                COALESCE(p.last_activity_utc, p.created_utc) AS last_activity_utc,
                p.game_type_match_json
            FROM projects p
            INNER JOIN workspaces w ON w.project_id = p.id
            WHERE p.account_id = $account_id
            ORDER BY COALESCE(p.last_activity_utc, p.created_utc), p.created_utc, p.id;
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
                reader.GetString(8),
                reader.GetString(9),
                reader.GetString(10),
                reader.GetString(11)));
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
                p.game_type_match_json,
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
                reader.GetString(11),
                reader.GetString(12),
                reader.GetString(13),
                reader.GetString(14),
                reader.GetString(15),
                reader.GetString(10)));
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
            """
            SELECT COUNT(*)
            FROM runner_locks rl
            LEFT JOIN runs r ON r.id = rl.run_id
            WHERE rl.project_id = $project_id
              AND (
                  rl.run_id IS NULL
                  OR r.status IN ('queued', 'running')
              );
            """,
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
            "SELECT COUNT(*) FROM runs WHERE project_id = $project_id AND status IN ('queued', 'running') AND run_type <> 'prototype-chat';",
            cancellationToken,
            ("$project_id", projectId)) ?? 0;
        return count > 0;
    }

    public async Task DeleteProjectAsync(string projectId, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var transaction = (SqliteTransaction)await connection.BeginTransactionAsync(cancellationToken);
        await RecordProjectDeleteTombstoneInsideTransactionAsync(connection, transaction, projectId, cancellationToken);
        await using var command = connection.CreateCommand();
        command.Transaction = transaction;
        command.CommandText = "DELETE FROM projects WHERE id = $project_id;";
        command.Parameters.AddWithValue("$project_id", projectId);
        await command.ExecuteNonQueryAsync(cancellationToken);
        await transaction.CommitAsync(cancellationToken);
    }

    public async Task<ProjectAdminReviewQueueEntry> UpsertProjectAdminReviewQueueEntryAsync(
        ProjectAdminReviewQueueCommand entry,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(entry.AccountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(entry.ProjectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(entry.RouteId);
        ArgumentException.ThrowIfNullOrWhiteSpace(entry.Severity);
        ArgumentException.ThrowIfNullOrWhiteSpace(entry.BlockingReason);
        ArgumentException.ThrowIfNullOrWhiteSpace(entry.SourceArtifactPath);
        if (!ProjectAdminReviewQueuePolicy.InputStatuses.Contains(entry.Status))
        {
            throw new ArgumentOutOfRangeException(nameof(entry), entry.Status, "admin_review_queue_status_invalid");
        }
        if (!AdminReviewSeverities.Contains(entry.Severity))
        {
            throw new ArgumentOutOfRangeException(nameof(entry), entry.Severity, "admin_review_queue_severity_invalid");
        }

        var id = NewId();
        var now = DateTimeOffset.UtcNow.ToString("O");
        var safeBlockingReason = SecretRedactionPolicy.RedactForPersistence(entry.BlockingReason);
        var safeSourceArtifactPath = SecretRedactionPolicy.RedactForPersistence(entry.SourceArtifactPath);
        var safeEvidenceRefsJson = NormalizeAdminReviewEvidenceRefsJson(entry.EvidenceRefsJson);
        var upsertLockKey = string.Join("\u001f", entry.ProjectId, entry.RouteId, entry.RequirementId);
        var upsertGate = AdminReviewUpsertLocks.GetOrAdd(upsertLockKey, _ => new SemaphoreSlim(1, 1));
        await upsertGate.WaitAsync(cancellationToken);
        try
        {
        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var transaction = (SqliteTransaction)await connection.BeginTransactionAsync(cancellationToken);
        var current = await GetProjectAdminReviewQueueEntryByKeyAsync(
            connection,
            transaction,
            entry.ProjectId,
            entry.RouteId,
            entry.RequirementId,
            cancellationToken);
        if (current is not null &&
            string.Equals(current.AccountId, entry.AccountId, StringComparison.Ordinal) &&
            string.Equals(current.Severity, entry.Severity, StringComparison.Ordinal) &&
            string.Equals(current.BlockingReason, safeBlockingReason, StringComparison.Ordinal) &&
            string.Equals(current.SourceArtifactPath, safeSourceArtifactPath, StringComparison.Ordinal) &&
            string.Equals(current.EvidenceRefsJson, safeEvidenceRefsJson, StringComparison.Ordinal))
        {
            await transaction.CommitAsync(cancellationToken);
            await RefreshAdminReviewQueueSidecarAsync(current.ProjectId, cancellationToken);
            return current;
        }

        if (current is not null)
        {
            await using var supersede = connection.CreateCommand();
            supersede.Transaction = transaction;
            supersede.CommandText =
                """
                UPDATE project_admin_review_queue
                SET status = 'superseded',
                    superseded_by_entry_id = $superseded_by_entry_id,
                    updated_utc = $updated_utc
                WHERE id = $id;
                """;
            supersede.Parameters.AddWithValue("$id", current.Id);
            supersede.Parameters.AddWithValue("$superseded_by_entry_id", id);
            supersede.Parameters.AddWithValue("$updated_utc", now);
            await supersede.ExecuteNonQueryAsync(cancellationToken);
        }

        await using (var command = connection.CreateCommand())
        {
            command.Transaction = transaction;
            command.CommandText =
                """
                INSERT INTO project_admin_review_queue (
                    id, account_id, project_id, route_id, requirement_id, severity, blocking_reason,
                    source_artifact_path, evidence_refs_json, status, decision_status, created_utc, updated_utc,
                    supersedes_entry_id)
                VALUES (
                    $id, $account_id, $project_id, $route_id, $requirement_id, $severity, $blocking_reason,
                    $source_artifact_path, $evidence_refs_json, $status, 'pending', $created_utc, $updated_utc,
                    $supersedes_entry_id);
                """;
            command.Parameters.AddWithValue("$id", id);
            command.Parameters.AddWithValue("$account_id", entry.AccountId);
            command.Parameters.AddWithValue("$project_id", entry.ProjectId);
            command.Parameters.AddWithValue("$route_id", entry.RouteId);
            command.Parameters.AddWithValue("$requirement_id", entry.RequirementId);
            command.Parameters.AddWithValue("$severity", entry.Severity);
            command.Parameters.AddWithValue("$blocking_reason", safeBlockingReason);
            command.Parameters.AddWithValue("$source_artifact_path", safeSourceArtifactPath);
            command.Parameters.AddWithValue("$evidence_refs_json", safeEvidenceRefsJson);
            command.Parameters.AddWithValue("$status", entry.Status);
            command.Parameters.AddWithValue("$created_utc", now);
            command.Parameters.AddWithValue("$updated_utc", now);
            command.Parameters.AddWithValue("$supersedes_entry_id", (object?)current?.Id ?? DBNull.Value);
            await command.ExecuteNonQueryAsync(cancellationToken);
        }
        await transaction.CommitAsync(cancellationToken);

        var created = await GetProjectAdminReviewQueueEntryByIdAsync(id, cancellationToken) ??
            throw new InvalidOperationException("admin_review_queue_upsert_failed");
        await RefreshAdminReviewQueueSidecarAsync(created.ProjectId, cancellationToken);
        return created;
        }
        finally
        {
            upsertGate.Release();
        }
    }

    public async Task ReconcileProjectAdminReviewQueueAsync(
        string accountId,
        string projectId,
        string routeId,
        IReadOnlySet<string> activeRequirementIds,
        string sourceArtifactPath,
        string evidenceRefsJson,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(routeId);
        ArgumentNullException.ThrowIfNull(activeRequirementIds);
        var safeSourceArtifactPath = SecretRedactionPolicy.RedactForPersistence(sourceArtifactPath);
        var safeEvidenceRefsJson = NormalizeAdminReviewEvidenceRefsJson(evidenceRefsJson);
        var now = DateTimeOffset.UtcNow.ToString("O");

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var transaction = (SqliteTransaction)await connection.BeginTransactionAsync(cancellationToken);
        var currentEntries = new List<ProjectAdminReviewQueueEntry>();
        await using (var select = connection.CreateCommand())
        {
            select.Transaction = transaction;
            select.CommandText =
                """
                SELECT id, account_id, project_id, route_id, requirement_id, severity, blocking_reason,
                       source_artifact_path, evidence_refs_json, status, decision_status, decision_actor_account_id,
                       decision_reason, decision_metadata_json, decision_version, created_utc, updated_utc, decided_utc, project_deleted_utc,
                       supersedes_entry_id, superseded_by_entry_id
                FROM project_admin_review_queue
                WHERE account_id = $account_id
                  AND project_id = $project_id
                  AND route_id = $route_id
                  AND status <> 'superseded';
                """;
            select.Parameters.AddWithValue("$account_id", accountId);
            select.Parameters.AddWithValue("$project_id", projectId);
            select.Parameters.AddWithValue("$route_id", routeId);
            await using var reader = await select.ExecuteReaderAsync(cancellationToken);
            while (await reader.ReadAsync(cancellationToken))
            {
                currentEntries.Add(ReadAdminReviewQueueEntry(reader));
            }
        }

        foreach (var current in currentEntries.Where(entry =>
                     !activeRequirementIds.Contains(entry.RequirementId) &&
                     entry.Status != "resolved"))
        {
            var replacementId = NewId();
            await using (var supersede = connection.CreateCommand())
            {
                supersede.Transaction = transaction;
                supersede.CommandText =
                    """
                    UPDATE project_admin_review_queue
                    SET status = 'superseded',
                        superseded_by_entry_id = $replacement_id,
                        updated_utc = $updated_utc
                    WHERE id = $id;
                    """;
                supersede.Parameters.AddWithValue("$replacement_id", replacementId);
                supersede.Parameters.AddWithValue("$updated_utc", now);
                supersede.Parameters.AddWithValue("$id", current.Id);
                await supersede.ExecuteNonQueryAsync(cancellationToken);
            }

            await using var insert = connection.CreateCommand();
            insert.Transaction = transaction;
            insert.CommandText =
                """
                INSERT INTO project_admin_review_queue (
                    id, account_id, project_id, route_id, requirement_id, severity, blocking_reason,
                    source_artifact_path, evidence_refs_json, status, decision_status, decision_actor_account_id, decision_reason,
                    decision_metadata_json, decision_version, created_utc, updated_utc, decided_utc, supersedes_entry_id)
                VALUES (
                    $id, $account_id, $project_id, $route_id, $requirement_id, $severity, $blocking_reason,
                    $source_artifact_path, $evidence_refs_json, 'resolved', 'resolved', 'system', $decision_reason,
                    $decision_metadata_json, 1, $created_utc, $updated_utc, $decided_utc, $supersedes_entry_id);
                """;
            insert.Parameters.AddWithValue("$id", replacementId);
            insert.Parameters.AddWithValue("$account_id", current.AccountId);
            insert.Parameters.AddWithValue("$project_id", current.ProjectId);
            insert.Parameters.AddWithValue("$route_id", current.RouteId);
            insert.Parameters.AddWithValue("$requirement_id", current.RequirementId);
            insert.Parameters.AddWithValue("$severity", current.Severity);
            insert.Parameters.AddWithValue("$blocking_reason", current.BlockingReason);
            insert.Parameters.AddWithValue("$source_artifact_path", safeSourceArtifactPath);
            insert.Parameters.AddWithValue("$evidence_refs_json", safeEvidenceRefsJson);
            insert.Parameters.AddWithValue("$decision_reason", "Source blocker removed during route reconciliation.");
            insert.Parameters.AddWithValue("$decision_metadata_json", JsonSerializer.Serialize(new
            {
                decision_by = "system",
                decision_role = "system_reconciliation",
                decision_reason = "Source blocker removed during route reconciliation.",
                decision_utc = now,
                resolution = "source_blocker_removed",
                evidence_refs = JsonSerializer.Deserialize<JsonElement>(safeEvidenceRefsJson)
            }));
            insert.Parameters.AddWithValue("$created_utc", now);
            insert.Parameters.AddWithValue("$updated_utc", now);
            insert.Parameters.AddWithValue("$decided_utc", now);
            insert.Parameters.AddWithValue("$supersedes_entry_id", current.Id);
            await insert.ExecuteNonQueryAsync(cancellationToken);

            await using var history = connection.CreateCommand();
            history.Transaction = transaction;
            history.CommandText =
                """
                INSERT INTO project_admin_review_decisions (
                    id, entry_id, decision_version, decision_status, decision_actor_account_id,
                    decision_reason, decision_metadata_json, created_utc)
                SELECT $history_id, id, 1, decision_status, decision_actor_account_id,
                       decision_reason, decision_metadata_json, $created_utc
                FROM project_admin_review_queue
                WHERE id = $entry_id;
                """;
            history.Parameters.AddWithValue("$history_id", NewId());
            history.Parameters.AddWithValue("$entry_id", replacementId);
            history.Parameters.AddWithValue("$created_utc", now);
            await history.ExecuteNonQueryAsync(cancellationToken);
        }

        await transaction.CommitAsync(cancellationToken);
        await RefreshAdminReviewQueueSidecarAsync(projectId, cancellationToken);
    }

    public async Task<IReadOnlyList<ProjectAdminReviewQueueEntry>> ListProjectAdminReviewQueueForAdminAsync(
        string status = "open",
        int limit = 100,
        CancellationToken cancellationToken = default)
    {
        return await ListProjectAdminReviewQueueForAdminAsync(
            new ProjectAdminReviewQueueQuery(status, Limit: limit),
            cancellationToken);
    }

    public async Task<IReadOnlyList<ProjectAdminReviewQueueEntry>> ListProjectAdminReviewQueueForAdminAsync(
        ProjectAdminReviewQueueQuery query,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(query);
        var cutoffUtc = query.MinimumAgeMinutes is > 0
            ? DateTimeOffset.UtcNow.AddMinutes(-query.MinimumAgeMinutes.Value).ToString("O")
            : "";
        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT id, account_id, project_id, route_id, requirement_id, severity, blocking_reason,
                   source_artifact_path, evidence_refs_json, status, decision_status, decision_actor_account_id,
                   decision_reason, decision_metadata_json, decision_version, created_utc, updated_utc, decided_utc, project_deleted_utc,
                   supersedes_entry_id, superseded_by_entry_id
            FROM project_admin_review_queue
            WHERE ($status = '' OR status = $status)
              AND ($project_id = '' OR project_id = $project_id)
              AND ($route_id = '' OR route_id = $route_id)
              AND ($severity = '' OR severity = $severity)
              AND ($cutoff_utc = '' OR created_utc <= $cutoff_utc)
            ORDER BY created_utc DESC, id DESC
            LIMIT $limit;
            """;
        command.Parameters.AddWithValue("$status", query.Status ?? "");
        command.Parameters.AddWithValue("$project_id", query.ProjectId ?? "");
        command.Parameters.AddWithValue("$route_id", query.RouteId ?? "");
        command.Parameters.AddWithValue("$severity", query.Severity ?? "");
        command.Parameters.AddWithValue("$cutoff_utc", cutoffUtc);
        command.Parameters.AddWithValue("$limit", Math.Clamp(query.Limit, 1, 500));
        var entries = new List<ProjectAdminReviewQueueEntry>();
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            entries.Add(ReadAdminReviewQueueEntry(reader));
        }

        return entries;
    }

    public async Task<IReadOnlyList<ProjectAdminReviewQueueEntry>> ListProjectAdminReviewQueueForProjectAsync(
        string accountId,
        string projectId,
        string status = "open",
        int limit = 100,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT id, account_id, project_id, route_id, requirement_id, severity, blocking_reason,
                   source_artifact_path, evidence_refs_json, status, decision_status, decision_actor_account_id,
                   decision_reason, decision_metadata_json, decision_version, created_utc, updated_utc, decided_utc, project_deleted_utc,
                   supersedes_entry_id, superseded_by_entry_id
            FROM project_admin_review_queue
            WHERE account_id = $account_id
              AND project_id = $project_id
              AND ($status = '' OR status = $status)
            ORDER BY created_utc DESC, id DESC
            LIMIT $limit;
            """;
        command.Parameters.AddWithValue("$account_id", accountId);
        command.Parameters.AddWithValue("$project_id", projectId);
        command.Parameters.AddWithValue("$status", status);
        command.Parameters.AddWithValue("$limit", limit <= 0 ? -1 : Math.Clamp(limit, 1, 500));
        var entries = new List<ProjectAdminReviewQueueEntry>();
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            entries.Add(ReadAdminReviewQueueEntry(reader));
        }

        return entries;
    }

    public async Task<ProjectAdminReviewDecisionResult> DecideProjectAdminReviewQueueEntryAsync(
        string entryId,
        string actorAccountId,
        ProjectAdminReviewDecisionRequest request,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(entryId);
        ArgumentException.ThrowIfNullOrWhiteSpace(actorAccountId);
        ArgumentNullException.ThrowIfNull(request);
        var decisionStatus = request.DecisionStatus?.Trim() ?? "";
        var decisionReason = request.DecisionReason?.Trim() ?? "";
        var safeDecisionReason = SecretRedactionPolicy.RedactForPersistence(decisionReason);
        if (decisionReason.Length == 0)
        {
            return new ProjectAdminReviewDecisionResult("rejected", "admin_review_decision_reason_missing", null);
        }
        if (!ProjectAdminReviewQueuePolicy.DecisionStatuses.Contains(decisionStatus))
        {
            return new ProjectAdminReviewDecisionResult("rejected", "admin_review_decision_invalid", null);
        }
        if (request.ExpectedDecisionVersion < 0)
        {
            return new ProjectAdminReviewDecisionResult("rejected", "admin_review_decision_version_invalid", null);
        }
        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var transaction = (SqliteTransaction)await connection.BeginTransactionAsync(cancellationToken);
        var existing = await GetProjectAdminReviewQueueEntryByIdAsync(connection, entryId, cancellationToken, transaction);
        if (existing is null)
        {
            return new ProjectAdminReviewDecisionResult("not_found", "admin_review_entry_not_found", null);
        }
        if (existing.Status == "superseded")
        {
            return new ProjectAdminReviewDecisionResult("conflict", "admin_review_entry_superseded", existing);
        }

        JsonArray normalizedDecisionEvidenceRefs;
        try
        {
            normalizedDecisionEvidenceRefs = NormalizeAdminReviewDecisionEvidenceRefs(request.DecisionEvidenceRefs);
        }
        catch (ArgumentException exception)
        {
            return new ProjectAdminReviewDecisionResult("rejected", exception.Message, existing);
        }

        var nowValue = DateTimeOffset.UtcNow;
        var now = nowValue.ToString("O");
        if (existing.DecisionVersion != request.ExpectedDecisionVersion)
        {
            var retryMetadataJson = BuildAdminReviewDecisionMetadata(
                request,
                actorAccountId,
                safeDecisionReason,
                existing.DecidedUtc ?? now,
                normalizedDecisionEvidenceRefs);
            if (existing.DecisionStatus == decisionStatus &&
                existing.DecisionActorAccountId == actorAccountId &&
                existing.DecisionReason == safeDecisionReason &&
                existing.DecisionMetadataJson == retryMetadataJson)
            {
                await transaction.RollbackAsync(cancellationToken);
                await RefreshAdminReviewQueueSidecarAsync(existing.ProjectId, cancellationToken);
                return new ProjectAdminReviewDecisionResult("returned_existing", null, existing);
            }

            return new ProjectAdminReviewDecisionResult("conflict", "decision_version_conflict", existing);
        }

        if (decisionStatus == "deferred" && !HasValidDeferredDecisionMetadata(request, existing.RouteId, nowValue))
        {
            return new ProjectAdminReviewDecisionResult("rejected", "admin_review_deferred_metadata_invalid", existing);
        }
        if (normalizedDecisionEvidenceRefs.Count == 0)
        {
            return new ProjectAdminReviewDecisionResult("rejected", "admin_review_decision_evidence_required", existing);
        }

        if (!await AdminReviewDecisionEvidenceRefsExistAsync(
                connection,
                transaction,
                existing.ProjectId,
                normalizedDecisionEvidenceRefs,
                cancellationToken))
        {
            return new ProjectAdminReviewDecisionResult("rejected", "admin_review_decision_evidence_ref_not_found", existing);
        }

        var decisionMetadataJson = BuildAdminReviewDecisionMetadata(
            request,
            actorAccountId,
            safeDecisionReason,
            now,
            normalizedDecisionEvidenceRefs);
        await using (var command = connection.CreateCommand())
        {
            command.Transaction = transaction;
            command.CommandText =
                """
                UPDATE project_admin_review_queue
                SET status = $decision_status,
                    decision_status = $decision_status,
                    decision_actor_account_id = $actor_account_id,
                    decision_reason = $decision_reason,
                    decision_metadata_json = $decision_metadata_json,
                    decision_version = decision_version + 1,
                    updated_utc = $updated_utc,
                    decided_utc = $decided_utc
                WHERE id = $id
                  AND decision_version = $expected_decision_version;
                """;
            command.Parameters.AddWithValue("$id", entryId);
            command.Parameters.AddWithValue("$actor_account_id", actorAccountId);
            command.Parameters.AddWithValue("$decision_status", decisionStatus);
            command.Parameters.AddWithValue("$decision_reason", safeDecisionReason);
            command.Parameters.AddWithValue("$decision_metadata_json", decisionMetadataJson);
            command.Parameters.AddWithValue("$expected_decision_version", request.ExpectedDecisionVersion);
            command.Parameters.AddWithValue("$updated_utc", now);
            command.Parameters.AddWithValue("$decided_utc", now);
            var rows = await command.ExecuteNonQueryAsync(cancellationToken);
            if (rows == 0)
            {
                var current = await GetProjectAdminReviewQueueEntryByIdAsync(connection, entryId, cancellationToken, transaction);
                return new ProjectAdminReviewDecisionResult("conflict", "decision_version_conflict", current);
            }
        }

        await using (var history = connection.CreateCommand())
        {
            history.Transaction = transaction;
            history.CommandText =
                """
                INSERT INTO project_admin_review_decisions (
                    id, entry_id, decision_version, decision_status, decision_actor_account_id,
                    decision_reason, decision_metadata_json, created_utc)
                VALUES (
                    $id, $entry_id, $decision_version, $decision_status, $decision_actor_account_id,
                    $decision_reason, $decision_metadata_json, $created_utc);
                """;
            history.Parameters.AddWithValue("$id", NewId());
            history.Parameters.AddWithValue("$entry_id", entryId);
            history.Parameters.AddWithValue("$decision_version", existing.DecisionVersion + 1);
            history.Parameters.AddWithValue("$decision_status", decisionStatus);
            history.Parameters.AddWithValue("$decision_actor_account_id", actorAccountId);
            history.Parameters.AddWithValue("$decision_reason", safeDecisionReason);
            history.Parameters.AddWithValue("$decision_metadata_json", decisionMetadataJson);
            history.Parameters.AddWithValue("$created_utc", now);
            await history.ExecuteNonQueryAsync(cancellationToken);
        }
        await transaction.CommitAsync(cancellationToken);

        var updated = await GetProjectAdminReviewQueueEntryByIdAsync(connection, entryId, cancellationToken);
        if (updated is not null)
        {
            await RefreshAdminReviewQueueSidecarAsync(updated.ProjectId, cancellationToken);
        }
        return new ProjectAdminReviewDecisionResult("updated", null, updated);
    }

    public async Task<ProjectDiagnosticSpoolEntry> RecordProjectDiagnosticSpoolEntryAsync(
        ProjectDiagnosticSpoolCommand entry,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(entry.AccountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(entry.ProjectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(entry.RouteId);
        ArgumentException.ThrowIfNullOrWhiteSpace(entry.FailureFamily);
        ArgumentException.ThrowIfNullOrWhiteSpace(entry.Severity);
        ArgumentException.ThrowIfNullOrWhiteSpace(entry.SafeSummary);

        var id = NewId();
        var diagnosticId = id;
        var now = DateTimeOffset.UtcNow.ToString("O");
        var retentionClass = string.IsNullOrWhiteSpace(entry.RetentionClass)
            ? DefaultDiagnosticRetentionClass(entry.TriageStatus, entry.Severity)
            : entry.RetentionClass.Trim();
        var userSafeSummary = RedactDiagnosticText(entry.SafeSummary);
        var adminSummary = string.IsNullOrWhiteSpace(entry.AdminSummary)
            ? userSafeSummary
            : RedactDiagnosticText(entry.AdminSummary);
        var normalizedEntry = entry with
        {
            SafeSummary = userSafeSummary,
            AdminSummary = adminSummary,
            RetentionClass = retentionClass,
            SourceRefsJson = SecretRedactionPolicy.RedactForPersistence(entry.SourceRefsJson),
            EvidenceRefsJson = SecretRedactionPolicy.RedactForPersistence(entry.EvidenceRefsJson),
            SourceArtifactPath = SecretRedactionPolicy.RedactForPersistence(entry.SourceArtifactPath),
            ReplacementEvidenceRefsJson = SecretRedactionPolicy.RedactForPersistence(entry.ReplacementEvidenceRefsJson)
        };
        var spoolRef = "";
        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var transaction = await connection.BeginTransactionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.Transaction = (SqliteTransaction)transaction;
        command.CommandText =
            """
            INSERT OR IGNORE INTO project_diagnostic_spool (
                id, diagnostic_id, account_id, project_id, project_name_snapshot, run_id, route_id, failure_family, severity, triage_status,
                retention_class, redaction_status, spool_ref, safe_summary, user_safe_summary, source_refs_json,
                evidence_refs_json, source_artifact_path, cleanup_status, replacement_evidence_refs_json, admin_summary, remediation_hint_id,
                dedupe_scope_key, created_utc, updated_utc)
            VALUES (
                $id, $diagnostic_id, $account_id, $project_id, $project_name_snapshot, $run_id, $route_id, $failure_family, $severity, $triage_status,
                $retention_class, $redaction_status, $spool_ref, $safe_summary, $user_safe_summary, $source_refs_json,
                $evidence_refs_json, $source_artifact_path, $cleanup_status, $replacement_evidence_refs_json, $admin_summary, $remediation_hint_id,
                $dedupe_scope_key, $created_utc, $updated_utc);
            """;
        command.Parameters.AddWithValue("$id", id);
        command.Parameters.AddWithValue("$diagnostic_id", diagnosticId);
        command.Parameters.AddWithValue("$account_id", entry.AccountId);
        command.Parameters.AddWithValue("$project_id", entry.ProjectId);
        command.Parameters.AddWithValue("$project_name_snapshot", entry.ProjectNameSnapshot);
        command.Parameters.AddWithValue("$run_id", entry.RunId);
        command.Parameters.AddWithValue("$route_id", entry.RouteId);
        command.Parameters.AddWithValue("$failure_family", entry.FailureFamily);
        command.Parameters.AddWithValue("$severity", entry.Severity);
        command.Parameters.AddWithValue("$triage_status", entry.TriageStatus);
        command.Parameters.AddWithValue("$retention_class", retentionClass);
        command.Parameters.AddWithValue("$redaction_status", entry.RedactionStatus);
        command.Parameters.AddWithValue("$spool_ref", spoolRef);
        command.Parameters.AddWithValue("$safe_summary", userSafeSummary);
        command.Parameters.AddWithValue("$user_safe_summary", userSafeSummary);
        command.Parameters.AddWithValue("$source_refs_json", normalizedEntry.SourceRefsJson);
        command.Parameters.AddWithValue("$evidence_refs_json", normalizedEntry.EvidenceRefsJson);
        command.Parameters.AddWithValue("$source_artifact_path", normalizedEntry.SourceArtifactPath);
        command.Parameters.AddWithValue("$cleanup_status", entry.CleanupStatus);
        command.Parameters.AddWithValue("$replacement_evidence_refs_json", normalizedEntry.ReplacementEvidenceRefsJson);
        command.Parameters.AddWithValue("$admin_summary", adminSummary);
        command.Parameters.AddWithValue("$remediation_hint_id", entry.RemediationHintId);
        command.Parameters.AddWithValue("$dedupe_scope_key", entry.DedupeScopeKey);
        command.Parameters.AddWithValue("$created_utc", now);
        command.Parameters.AddWithValue("$updated_utc", now);
        var inserted = await command.ExecuteNonQueryAsync(cancellationToken);

        if (inserted == 0 && !string.IsNullOrWhiteSpace(entry.DedupeScopeKey))
        {
            await using var existingCommand = connection.CreateCommand();
            existingCommand.Transaction = (SqliteTransaction)transaction;
            existingCommand.CommandText =
                """
                SELECT id
                FROM project_diagnostic_spool
                WHERE account_id = $account_id
                  AND project_id = $project_id
                  AND route_id = $route_id
                  AND failure_family = $failure_family
                  AND severity = $severity
                  AND triage_status = 'unresolved'
                  AND dedupe_scope_key = $dedupe_scope_key
                ORDER BY created_utc DESC, id DESC
                LIMIT 1;
                """;
            existingCommand.Parameters.AddWithValue("$account_id", entry.AccountId);
            existingCommand.Parameters.AddWithValue("$project_id", entry.ProjectId);
            existingCommand.Parameters.AddWithValue("$route_id", entry.RouteId);
            existingCommand.Parameters.AddWithValue("$failure_family", entry.FailureFamily);
            existingCommand.Parameters.AddWithValue("$severity", entry.Severity);
            existingCommand.Parameters.AddWithValue("$dedupe_scope_key", entry.DedupeScopeKey);
            var existingId = await existingCommand.ExecuteScalarAsync(cancellationToken) as string;
            if (!string.IsNullOrWhiteSpace(existingId))
            {
                await transaction.CommitAsync(cancellationToken);
                var existing = (await GetProjectDiagnosticSpoolEntryByIdAsync(existingId, cancellationToken))!;
                return await EnsureDiagnosticSpoolEvidenceAsync(existing, cancellationToken);
            }
        }

        try
        {
            spoolRef = await WriteDiagnosticSpoolFileAsync(
                diagnosticId,
                normalizedEntry,
                now,
                cancellationToken);
            await using var updateSpoolRef = connection.CreateCommand();
            updateSpoolRef.Transaction = (SqliteTransaction)transaction;
            updateSpoolRef.CommandText =
                "UPDATE project_diagnostic_spool SET spool_ref = $spool_ref WHERE id = $id;";
            updateSpoolRef.Parameters.AddWithValue("$spool_ref", spoolRef);
            updateSpoolRef.Parameters.AddWithValue("$id", id);
            await updateSpoolRef.ExecuteNonQueryAsync(cancellationToken);
            await transaction.CommitAsync(cancellationToken);
        }
        catch
        {
            await transaction.RollbackAsync(CancellationToken.None);
            if (!string.IsNullOrWhiteSpace(spoolRef))
            {
                DeleteDiagnosticSpoolFile(spoolRef, normalizedEntry);
            }
            throw;
        }

        return (await GetProjectDiagnosticSpoolEntryByIdAsync(id, cancellationToken))!;
    }

    private async Task<ProjectDiagnosticSpoolEntry> EnsureDiagnosticSpoolEvidenceAsync(
        ProjectDiagnosticSpoolEntry existing,
        CancellationToken cancellationToken)
    {
        var entry = new ProjectDiagnosticSpoolCommand(
            existing.AccountId,
            existing.ProjectId,
            existing.RouteId,
            existing.FailureFamily,
            existing.Severity,
            existing.SafeSummary,
            existing.EvidenceRefsJson,
            existing.SourceArtifactPath,
            existing.TriageStatus,
            existing.ProjectNameSnapshot,
            existing.RunId,
            existing.SourceRefsJson,
            existing.RedactionStatus,
            existing.RetentionClass,
            existing.CleanupStatus,
            existing.ReplacementEvidenceRefsJson,
            existing.AdminSummary,
            existing.RemediationHintId);
        if (!string.IsNullOrWhiteSpace(existing.SpoolRef) && DiagnosticSpoolFileExists(existing.SpoolRef, entry))
        {
            return existing;
        }

        var spoolRef = await WriteDiagnosticSpoolFileAsync(
            existing.DiagnosticId,
            entry,
            existing.CreatedUtc,
            cancellationToken);
        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var update = connection.CreateCommand();
        update.CommandText = "UPDATE project_diagnostic_spool SET spool_ref = $spool_ref WHERE id = $id;";
        update.Parameters.AddWithValue("$spool_ref", spoolRef);
        update.Parameters.AddWithValue("$id", existing.Id);
        await update.ExecuteNonQueryAsync(cancellationToken);
        return (await GetProjectDiagnosticSpoolEntryByIdAsync(existing.Id, cancellationToken))!;
    }

    public async Task<IReadOnlyList<ProjectDiagnosticSpoolEntry>> ListProjectDiagnosticSpoolForAdminAsync(
        string triageStatus = "unresolved",
        int limit = 100,
        CancellationToken cancellationToken = default)
    {
        return await ListProjectDiagnosticSpoolForAdminAsync(
            new ProjectDiagnosticSpoolQuery(triageStatus, Limit: limit),
            cancellationToken);
    }

    public async Task<IReadOnlyList<ProjectDiagnosticSpoolEntry>> ListProjectDiagnosticSpoolForAdminAsync(
        ProjectDiagnosticSpoolQuery query,
        CancellationToken cancellationToken = default)
    {
        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT id, diagnostic_id, account_id, project_id, project_name_snapshot, run_id, route_id, failure_family, severity, triage_status,
                   retention_class, redaction_status, spool_ref, safe_summary, user_safe_summary, source_refs_json,
                   evidence_refs_json, source_artifact_path, cleanup_status, replacement_evidence_refs_json, admin_summary, remediation_hint_id,
                   created_utc, updated_utc, resolved_utc, project_deleted_utc, triage_decision_by, triage_decision_reason,
                   deletion_event_id, project_tombstone_id
            FROM project_diagnostic_spool
            WHERE ($triage_status = '' OR triage_status = $triage_status)
              AND ($account_id IS NULL OR account_id = $account_id)
              AND ($project_id IS NULL OR project_id = $project_id)
              AND ($route_id IS NULL OR route_id = $route_id)
              AND ($failure_family IS NULL OR failure_family = $failure_family)
              AND ($severity IS NULL OR severity = $severity)
            ORDER BY updated_utc DESC, id DESC
            LIMIT $limit;
            """;
        command.Parameters.AddWithValue("$triage_status", query.TriageStatus);
        command.Parameters.AddWithValue("$account_id", string.IsNullOrWhiteSpace(query.AccountId) ? DBNull.Value : query.AccountId);
        command.Parameters.AddWithValue("$project_id", string.IsNullOrWhiteSpace(query.ProjectId) ? DBNull.Value : query.ProjectId);
        command.Parameters.AddWithValue("$route_id", string.IsNullOrWhiteSpace(query.RouteId) ? DBNull.Value : query.RouteId);
        command.Parameters.AddWithValue("$failure_family", string.IsNullOrWhiteSpace(query.FailureFamily) ? DBNull.Value : query.FailureFamily);
        command.Parameters.AddWithValue("$severity", string.IsNullOrWhiteSpace(query.Severity) ? DBNull.Value : query.Severity);
        command.Parameters.AddWithValue("$limit", Math.Clamp(query.Limit, 1, 500));
        var entries = new List<ProjectDiagnosticSpoolEntry>();
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            entries.Add(ReadDiagnosticSpoolEntry(reader));
        }

        return entries;
    }

    public async Task<IReadOnlyList<ProjectDiagnosticSpoolEntry>> ListProjectDiagnosticSpoolForAccountAsync(
        string accountId,
        string projectId,
        string triageStatus = "unresolved",
        int limit = 100,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        return await ListProjectDiagnosticSpoolForAdminAsync(
            new ProjectDiagnosticSpoolQuery(triageStatus, accountId, projectId, Limit: limit),
            cancellationToken);
    }

    public async Task<ProjectDiagnosticTriageDecisionResult> DecideProjectDiagnosticSpoolEntryAsync(
        string diagnosticId,
        string actorAccountId,
        string triageStatus,
        string triageDecisionReason,
        string replacementEvidenceRefsJson,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(diagnosticId);
        ArgumentException.ThrowIfNullOrWhiteSpace(actorAccountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(triageStatus);
        ArgumentException.ThrowIfNullOrWhiteSpace(triageDecisionReason);

        var allowed = new HashSet<string>(StringComparer.Ordinal)
        {
            "unresolved",
            "resolved",
            "ignored",
            "backlog"
        };
        if (!allowed.Contains(triageStatus))
        {
            return new ProjectDiagnosticTriageDecisionResult("invalid", "diagnostic_triage_status_invalid", null);
        }

        var existing = await GetProjectDiagnosticSpoolEntryByIdAsync(diagnosticId, cancellationToken);
        if (existing is null)
        {
            return new ProjectDiagnosticTriageDecisionResult("not_found", "diagnostic_not_found", null);
        }

        var now = DateTimeOffset.UtcNow.ToString("O");
        var retentionClass = triageStatus switch
        {
            "resolved" => "resolved_audit",
            "ignored" => "ignored_audit",
            "backlog" => "backlog_audit",
            _ => DefaultDiagnosticRetentionClass(triageStatus, existing.Severity)
        };
        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            UPDATE project_diagnostic_spool
            SET triage_status = $triage_status,
                retention_class = $retention_class,
                updated_utc = $updated_utc,
                resolved_utc = CASE WHEN $triage_status IN ('resolved', 'ignored') THEN $updated_utc ELSE resolved_utc END,
                triage_decision_by = $triage_decision_by,
                triage_decision_reason = $triage_decision_reason,
                replacement_evidence_refs_json = $replacement_evidence_refs_json
            WHERE diagnostic_id = $diagnostic_id;
            """;
        command.Parameters.AddWithValue("$diagnostic_id", diagnosticId);
        command.Parameters.AddWithValue("$triage_status", triageStatus);
        command.Parameters.AddWithValue("$retention_class", retentionClass);
        command.Parameters.AddWithValue("$updated_utc", now);
        command.Parameters.AddWithValue("$triage_decision_by", actorAccountId);
        command.Parameters.AddWithValue("$triage_decision_reason", RedactDiagnosticText(triageDecisionReason));
        command.Parameters.AddWithValue("$replacement_evidence_refs_json", replacementEvidenceRefsJson);
        await command.ExecuteNonQueryAsync(cancellationToken);

        return new ProjectDiagnosticTriageDecisionResult(
            "updated",
            null,
            await GetProjectDiagnosticSpoolEntryByIdAsync(diagnosticId, cancellationToken));
    }

    public async Task<int> CountUnresolvedBlockingDiagnosticsAsync(
        string accountId,
        string projectId,
        CancellationToken cancellationToken = default)
    {
        await using var connection = await OpenConnectionAsync(cancellationToken);
        var count = await ExecuteScalarLongAsync(
            connection,
            """
            SELECT COUNT(*)
            FROM project_diagnostic_spool
            WHERE account_id = $account_id
              AND project_id = $project_id
              AND triage_status IN ('unresolved', 'backlog')
              AND severity IN ('P0', 'P1', 'P2');
            """,
            cancellationToken,
            ("$account_id", accountId),
            ("$project_id", projectId)) ?? 0;
        return checked((int)count);
    }

    public async Task<IReadOnlyList<ProjectDeleteTombstone>> ListProjectDeleteTombstonesForAdminAsync(
        int limit = 100,
        CancellationToken cancellationToken = default)
    {
        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT project_tombstone_id, deletion_event_id, project_id, account_id, project_name, deleted_utc, unresolved_admin_review_count, unresolved_diagnostic_count, evidence_refs_json
            FROM project_delete_tombstones
            ORDER BY deleted_utc DESC, project_id DESC
            LIMIT $limit;
            """;
        command.Parameters.AddWithValue("$limit", Math.Clamp(limit, 1, 500));
        var tombstones = new List<ProjectDeleteTombstone>();
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            tombstones.Add(new ProjectDeleteTombstone(
                reader.GetString(0),
                reader.GetString(1),
                reader.GetString(2),
                reader.GetString(3),
                reader.GetString(4),
                reader.GetString(5),
                checked((int)reader.GetInt64(6)),
                checked((int)reader.GetInt64(7)),
                reader.GetString(8)));
        }

        return tombstones;
    }

    public async Task UpdateProjectGameTypeMatchAsync(
        string projectId,
        string gameTypeMatchJson,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(gameTypeMatchJson);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            UPDATE projects
            SET game_type_match_json = $game_type_match_json,
                last_activity_utc = $updated_utc
            WHERE id = $project_id;
            """;
        command.Parameters.AddWithValue("$project_id", projectId);
        command.Parameters.AddWithValue("$game_type_match_json", gameTypeMatchJson);
        command.Parameters.AddWithValue("$updated_utc", DateTimeOffset.UtcNow.ToString("O"));
        await command.ExecuteNonQueryAsync(cancellationToken);
    }

    public async Task<ProjectUiStateSnapshot?> GetProjectUiStateAsync(
        string accountId,
        string projectId,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT account_id, project_id, state_json, updated_utc
            FROM project_ui_states
            WHERE account_id = $account_id
              AND project_id = $project_id
            LIMIT 1;
            """;
        command.Parameters.AddWithValue("$account_id", accountId);
        command.Parameters.AddWithValue("$project_id", projectId);

        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        if (!await reader.ReadAsync(cancellationToken))
        {
            return null;
        }

        return new ProjectUiStateSnapshot(
            reader.GetString(0),
            reader.GetString(1),
            reader.GetString(2),
            reader.GetString(3));
    }

    public async Task UpsertProjectUiStateAsync(
        string accountId,
        string projectId,
        string stateJson,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        stateJson = string.IsNullOrWhiteSpace(stateJson) ? "{}" : stateJson.Trim();

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            INSERT INTO project_ui_states (
                account_id,
                project_id,
                state_json,
                updated_utc)
            VALUES (
                $account_id,
                $project_id,
                $state_json,
                $updated_utc)
            ON CONFLICT(account_id, project_id) DO UPDATE SET
                state_json = excluded.state_json,
                updated_utc = excluded.updated_utc;
            """;
        command.Parameters.AddWithValue("$account_id", accountId);
        command.Parameters.AddWithValue("$project_id", projectId);
        command.Parameters.AddWithValue("$state_json", stateJson);
        command.Parameters.AddWithValue("$updated_utc", DateTimeOffset.UtcNow.ToString("O"));
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

    public async Task RecordProjectGameTypeMatchFailureAsync(
        ProjectGameTypeMatchFailureCommand failure,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(failure);
        ArgumentException.ThrowIfNullOrWhiteSpace(failure.AccountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(failure.ProjectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(failure.ProjectName);
        ArgumentException.ThrowIfNullOrWhiteSpace(failure.GameName);
        ArgumentException.ThrowIfNullOrWhiteSpace(failure.MatchStatus);
        ArgumentException.ThrowIfNullOrWhiteSpace(failure.StatusReason);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            INSERT INTO project_game_type_match_failures (
                id,
                account_id,
                project_id,
                project_name,
                game_name,
                game_type_source,
                match_status,
                status_reason,
                reference_query,
                normalized_genre_tags_json,
                candidate_scores_json,
                missing_guide_path,
                matched_game_type_id,
                matched_guide_path,
                steam_app_id,
                steam_name,
                steam_resolved_query,
                steam_attempted_queries_json,
                created_utc)
            VALUES (
                $id,
                $account_id,
                $project_id,
                $project_name,
                $game_name,
                $game_type_source,
                $match_status,
                $status_reason,
                $reference_query,
                $normalized_genre_tags_json,
                $candidate_scores_json,
                $missing_guide_path,
                $matched_game_type_id,
                $matched_guide_path,
                $steam_app_id,
                $steam_name,
                $steam_resolved_query,
                $steam_attempted_queries_json,
                $created_utc);
            """;
        command.Parameters.AddWithValue("$id", NewId());
        command.Parameters.AddWithValue("$account_id", failure.AccountId);
        command.Parameters.AddWithValue("$project_id", failure.ProjectId);
        command.Parameters.AddWithValue("$project_name", failure.ProjectName);
        command.Parameters.AddWithValue("$game_name", failure.GameName);
        command.Parameters.AddWithValue("$game_type_source", failure.GameTypeSource);
        command.Parameters.AddWithValue("$match_status", failure.MatchStatus);
        command.Parameters.AddWithValue("$status_reason", failure.StatusReason);
        command.Parameters.AddWithValue("$reference_query", failure.ReferenceQuery);
        command.Parameters.AddWithValue("$normalized_genre_tags_json", failure.NormalizedGenreTagsJson);
        command.Parameters.AddWithValue("$candidate_scores_json", failure.CandidateScoresJson);
        command.Parameters.AddWithValue("$missing_guide_path", failure.MissingGuidePath);
        command.Parameters.AddWithValue("$matched_game_type_id", failure.MatchedGameTypeId);
        command.Parameters.AddWithValue("$matched_guide_path", failure.MatchedGuidePath);
        command.Parameters.AddWithValue("$steam_app_id", failure.SteamAppId);
        command.Parameters.AddWithValue("$steam_name", failure.SteamName);
        command.Parameters.AddWithValue("$steam_resolved_query", failure.SteamResolvedQuery);
        command.Parameters.AddWithValue("$steam_attempted_queries_json", failure.SteamAttemptedQueriesJson);
        command.Parameters.AddWithValue("$created_utc", DateTimeOffset.UtcNow.ToString("O"));
        await command.ExecuteNonQueryAsync(cancellationToken);
    }

    public async Task<IReadOnlyList<ProjectGameTypeMatchFailureSnapshot>> ListProjectGameTypeMatchFailuresForAdminAsync(
        int limit,
        CancellationToken cancellationToken = default)
    {
        return await ListProjectGameTypeMatchRecordsForAdminAsync(limit, includeMatched: false, cancellationToken);
    }

    public async Task<IReadOnlyList<ProjectGameTypeMatchFailureSnapshot>> ListProjectGameTypeMatchRecordsForAdminAsync(
        int limit,
        CancellationToken cancellationToken = default)
    {
        return await ListProjectGameTypeMatchRecordsForAdminAsync(limit, includeMatched: true, cancellationToken);
    }

    private async Task<IReadOnlyList<ProjectGameTypeMatchFailureSnapshot>> ListProjectGameTypeMatchRecordsForAdminAsync(
        int limit,
        bool includeMatched,
        CancellationToken cancellationToken)
    {
        var boundedLimit = Math.Clamp(limit, 1, 500);
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
                match_status,
                status_reason,
                reference_query,
                normalized_genre_tags_json,
                candidate_scores_json,
                missing_guide_path,
                matched_game_type_id,
                matched_guide_path,
                steam_app_id,
                steam_name,
                steam_resolved_query,
                steam_attempted_queries_json,
                created_utc
            FROM project_game_type_match_failures
            WHERE $include_matched = 1 OR match_status <> 'matched'
            ORDER BY created_utc DESC, rowid DESC
            LIMIT $limit;
            """;
        command.Parameters.AddWithValue("$limit", boundedLimit);
        command.Parameters.AddWithValue("$include_matched", includeMatched ? 1 : 0);

        var records = new List<ProjectGameTypeMatchFailureSnapshot>();
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            records.Add(new ProjectGameTypeMatchFailureSnapshot(
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
                reader.GetString(10),
                reader.GetString(11),
                reader.GetString(12),
                reader.GetString(13),
                reader.GetString(14),
                reader.GetString(15),
                reader.GetString(16),
                reader.GetString(17),
                reader.GetString(18)));
        }

        return records;
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
        await MarkRunStartedAsync(runId, null, cancellationToken);
    }

    public async Task MarkRunStartedAsync(string runId, int? queuePositionAtStart, CancellationToken cancellationToken = default)
    {
        await TryMarkRunStartedAsync(runId, queuePositionAtStart, cancellationToken);
    }

    public async Task<bool> TryMarkRunStartedAsync(string runId, int? queuePositionAtStart, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(runId);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            UPDATE runs
            SET status = 'running',
                started_utc = $started_utc,
                queue_position_at_start = $queue_position_at_start
            WHERE id = $id
              AND status = 'queued';
            """;
        command.Parameters.AddWithValue("$id", runId);
        command.Parameters.AddWithValue("$started_utc", DateTimeOffset.UtcNow.ToString("O"));
        command.Parameters.AddWithValue("$queue_position_at_start", (object?)queuePositionAtStart ?? DBNull.Value);
        var updated = await command.ExecuteNonQueryAsync(cancellationToken);
        if (updated > 0)
        {
            return true;
        }

        var status = await GetRunStatusAsync(connection, runId, cancellationToken);
        if (string.Equals(status, "cancel", StringComparison.Ordinal))
        {
            var projectId = await GetRunProjectIdAsync(connection, runId, cancellationToken);
            if (!string.IsNullOrWhiteSpace(projectId))
            {
                await ReleaseRunnerLockForRunAsync(connection, projectId, runId, cancellationToken);
            }

            throw new OperationCanceledException($"Run {runId} was cancelled before it started.");
        }

        return false;
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
            WHERE id = $id
              AND status <> 'cancel';
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
        var finishedUtc = DateTimeOffset.UtcNow.ToString("O");
        await using var transaction = (SqliteTransaction)await connection.BeginTransactionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.Transaction = transaction;
        command.CommandText =
            """
            UPDATE runs
            SET status = $status,
                finished_utc = $finished_utc,
                exit_code = $exit_code,
                stdout_text = $stdout_text,
                stderr_text = $stderr_text,
                evidence_json = $evidence_json
            WHERE id = $id
              AND status <> 'cancel';
            """;
        command.Parameters.AddWithValue("$id", runId);
        command.Parameters.AddWithValue("$status", status);
        command.Parameters.AddWithValue("$finished_utc", finishedUtc);
        command.Parameters.AddWithValue("$exit_code", exitCode);
        command.Parameters.AddWithValue("$stdout_text", stdoutText);
        command.Parameters.AddWithValue("$stderr_text", stderrText);
        command.Parameters.AddWithValue("$evidence_json", evidenceJson);
        var updated = await command.ExecuteNonQueryAsync(cancellationToken);

        if (updated > 0)
        {
            await UpsertRunDurationMetricAsync(connection, transaction, runId, finishedUtc, cancellationToken);
            await PruneRunDurationMetricsAsync(connection, transaction, cancellationToken);
            var projectId = await GetRunProjectIdAsync(connection, runId, cancellationToken);
            if (!string.IsNullOrWhiteSpace(projectId))
            {
                await ReleaseRunnerLockForRunAsync(connection, transaction, projectId, runId, cancellationToken);
            }
        }

        await transaction.CommitAsync(cancellationToken);
    }

    public async Task<RunCancelResult> CancelRunAsync(
        string accountId,
        string runId,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(runId);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        var existing = await GetRunForAccountAsync(connection, accountId, runId, cancellationToken);
        if (existing is null)
        {
            return RunCancelResult.NotFound;
        }

        if (!string.Equals(existing.Status, "queued", StringComparison.Ordinal) &&
            !string.Equals(existing.Status, "running", StringComparison.Ordinal))
        {
            return RunCancelResult.NotActive;
        }

        var finishedUtc = DateTimeOffset.UtcNow.ToString("O");
        await using var transaction = (SqliteTransaction)await connection.BeginTransactionAsync(cancellationToken);
        var evidenceJson = JsonSerializer.Serialize(new
        {
            cancelled_by_user = true,
            cancelled_utc = finishedUtc
        });
        var updated = await TryCancelRunWithStatusAsync(connection, transaction, runId, "queued", finishedUtc, evidenceJson, cancellationToken);
        var releaseQueuedLock = updated > 0;
        if (updated == 0)
        {
            updated = await TryCancelRunWithStatusAsync(connection, transaction, runId, "running", finishedUtc, evidenceJson, cancellationToken);
        }

        if (updated == 0)
        {
            await transaction.RollbackAsync(cancellationToken);
            return RunCancelResult.NotActive;
        }

        await using var lockCommand = connection.CreateCommand();
        lockCommand.Transaction = transaction;
        lockCommand.CommandText =
            """
            DELETE FROM runner_locks
            WHERE project_id = $project_id
              AND run_id = $run_id;
            """;
        lockCommand.Parameters.AddWithValue("$project_id", existing.ProjectId);
        lockCommand.Parameters.AddWithValue("$run_id", runId);
        await lockCommand.ExecuteNonQueryAsync(cancellationToken);

        await UpsertRunDurationMetricAsync(connection, transaction, runId, finishedUtc, cancellationToken);
        await PruneRunDurationMetricsAsync(connection, transaction, cancellationToken);
        await transaction.CommitAsync(cancellationToken);
        return RunCancelResult.Cancelled;
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
                created_utc,
                started_utc,
                finished_utc,
                queue_position_at_start,
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

        return ReadRunSnapshot(reader);
    }

    private static async Task<RunSnapshot?> GetRunForAccountAsync(
        SqliteConnection connection,
        string accountId,
        string runId,
        CancellationToken cancellationToken)
    {
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT
                r.id,
                r.project_id,
                r.workspace_id,
                r.run_type,
                r.status,
                r.created_utc,
                r.started_utc,
                r.finished_utc,
                r.queue_position_at_start,
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
            WHERE r.id = $run_id
              AND p.account_id = $account_id;
            """;
        command.Parameters.AddWithValue("$run_id", runId);
        command.Parameters.AddWithValue("$account_id", accountId);

        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        return await reader.ReadAsync(cancellationToken) ? ReadRunSnapshot(reader) : null;
    }

    private static async Task<string?> GetRunStatusAsync(
        SqliteConnection connection,
        string runId,
        CancellationToken cancellationToken)
    {
        await using var command = connection.CreateCommand();
        command.CommandText = "SELECT status FROM runs WHERE id = $id;";
        command.Parameters.AddWithValue("$id", runId);
        var value = await command.ExecuteScalarAsync(cancellationToken);
        return value as string;
    }

    private static async Task<string?> GetRunProjectIdAsync(
        SqliteConnection connection,
        string runId,
        CancellationToken cancellationToken)
    {
        await using var command = connection.CreateCommand();
        command.CommandText = "SELECT project_id FROM runs WHERE id = $id;";
        command.Parameters.AddWithValue("$id", runId);
        var value = await command.ExecuteScalarAsync(cancellationToken);
        return value as string;
    }

    private static async Task ReleaseRunnerLockForRunAsync(
        SqliteConnection connection,
        string projectId,
        string runId,
        CancellationToken cancellationToken)
    {
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

    private static async Task ReleaseRunnerLockForRunAsync(
        SqliteConnection connection,
        SqliteTransaction transaction,
        string projectId,
        string runId,
        CancellationToken cancellationToken)
    {
        await using var command = connection.CreateCommand();
        command.Transaction = transaction;
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

    private static async Task<int> TryCancelRunWithStatusAsync(
        SqliteConnection connection,
        SqliteTransaction transaction,
        string runId,
        string expectedStatus,
        string finishedUtc,
        string evidenceJson,
        CancellationToken cancellationToken)
    {
        await using var command = connection.CreateCommand();
        command.Transaction = transaction;
        command.CommandText =
            """
            UPDATE runs
            SET status = 'cancel',
                finished_utc = $finished_utc,
                exit_code = 499,
                stdout_text = COALESCE(stdout_text, ''),
                stderr_text = CASE
                    WHEN stderr_text IS NULL OR stderr_text = '' THEN 'Cancelled by user.'
                    ELSE stderr_text || CHAR(10) || 'Cancelled by user.'
                END,
                evidence_json = $evidence_json,
                progress_step = 'cancel',
                progress_substep = 'user_cancelled',
                progress_label = '用户已取消当前 run。',
                progress_updated_utc = $finished_utc
            WHERE id = $id
              AND status = $expected_status;
            """;
        command.Parameters.AddWithValue("$id", runId);
        command.Parameters.AddWithValue("$expected_status", expectedStatus);
        command.Parameters.AddWithValue("$finished_utc", finishedUtc);
        command.Parameters.AddWithValue("$evidence_json", evidenceJson);
        return await command.ExecuteNonQueryAsync(cancellationToken);
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
                created_utc,
                started_utc,
                finished_utc,
                queue_position_at_start,
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
            runs.Add(ReadRunSnapshot(reader));
        }

        return runs;
    }

    public async Task<IReadOnlyList<RunSnapshot>> ListLlmRunsForAccountAsync(
        string accountId,
        int limit = 20,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        if (limit < 1)
        {
            throw new ArgumentOutOfRangeException(nameof(limit), "Limit must be greater than zero.");
        }

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
                r.created_utc,
                r.started_utc,
                r.finished_utc,
                r.queue_position_at_start,
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
              AND r.llm_cost_json IS NOT NULL
            ORDER BY r.created_utc DESC, r.id DESC
            LIMIT $limit;
            """;
        command.Parameters.AddWithValue("$account_id", accountId);
        command.Parameters.AddWithValue("$limit", limit);

        var runs = new List<RunSnapshot>();
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            runs.Add(ReadRunSnapshot(reader));
        }

        return runs;
    }

    public async Task<IReadOnlyList<(AdminUserListItem Account, RunSnapshot Run)>> ListLlmRunsForAdminAsync(
        int limit = 100,
        CancellationToken cancellationToken = default)
    {
        if (limit < 1)
        {
            throw new ArgumentOutOfRangeException(nameof(limit), "Limit must be greater than zero.");
        }

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT
                a.id,
                a.username,
                a.is_admin,
                a.is_disabled,
                COALESCE(pl.project_limit, $default_project_limit),
                (
                    SELECT COUNT(*)
                    FROM projects count_projects
                    WHERE count_projects.account_id = a.id
                ) AS project_count,
                a.created_utc,
                r.id,
                r.project_id,
                r.workspace_id,
                r.run_type,
                r.status,
                r.created_utc,
                r.started_utc,
                r.finished_utc,
                r.queue_position_at_start,
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
            INNER JOIN accounts a ON a.id = p.account_id
            LEFT JOIN project_limits pl ON pl.account_id = a.id
            WHERE r.llm_cost_json IS NOT NULL
            ORDER BY r.created_utc DESC, r.id DESC
            LIMIT $limit;
            """;
        command.Parameters.AddWithValue("$default_project_limit", _options.HostedProjectLimit);
        command.Parameters.AddWithValue("$limit", limit);

        var rows = new List<(AdminUserListItem Account, RunSnapshot Run)>();
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            var account = new AdminUserListItem(
                reader.GetString(0),
                reader.GetString(1),
                reader.GetInt64(2) == 1,
                reader.GetInt64(3) == 1,
                checked((int)reader.GetInt64(4)),
                checked((int)reader.GetInt64(5)),
                reader.GetString(6));
            var run = ReadRunSnapshot(reader, offset: 7);
            rows.Add((account, run));
        }

        return rows;
    }

    public async Task<IReadOnlyList<LlmUsageRunRow>> ListLlmUsageRowsForAdminAsync(
        string fromUtc,
        string toUtc,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(fromUtc);
        ArgumentException.ThrowIfNullOrWhiteSpace(toUtc);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT
                a.id,
                a.username,
                a.is_admin,
                a.is_disabled,
                p.id,
                p.name,
                p.game_name,
                r.id,
                r.run_type,
                r.status,
                r.created_utc,
                r.llm_model,
                r.llm_cost_json
            FROM runs r
            INNER JOIN projects p ON p.id = r.project_id
            INNER JOIN accounts a ON a.id = p.account_id
            WHERE r.llm_cost_json IS NOT NULL
              AND r.created_utc >= $from_utc
              AND r.created_utc < $to_utc
            ORDER BY r.created_utc ASC, r.id ASC;
            """;
        command.Parameters.AddWithValue("$from_utc", fromUtc);
        command.Parameters.AddWithValue("$to_utc", toUtc);

        var rows = new List<LlmUsageRunRow>();
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            rows.Add(new LlmUsageRunRow(
                reader.GetString(0),
                reader.GetString(1),
                reader.GetInt64(2) == 1,
                reader.GetInt64(3) == 1,
                reader.GetString(4),
                reader.GetString(5),
                reader.GetString(6),
                reader.GetString(7),
                reader.GetString(8),
                reader.GetString(9),
                reader.GetString(10),
                reader.IsDBNull(11) ? null : reader.GetString(11),
                reader.GetString(12)));
        }

        return rows;
    }

    public async Task<IReadOnlyList<AdminRunMetricsRow>> ListRunMetricsForAdminAsync(
        string? accountId,
        string? runType,
        int limit = 500,
        CancellationToken cancellationToken = default)
    {
        if (limit < 1)
        {
            throw new ArgumentOutOfRangeException(nameof(limit), "Limit must be greater than zero.");
        }

        var boundedLimit = Math.Clamp(limit, 1, 500);
        var normalizedAccountId = string.IsNullOrWhiteSpace(accountId) ? null : accountId.Trim();
        var normalizedRunType = string.IsNullOrWhiteSpace(runType) ? null : runType.Trim();

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT account_id,
                   username,
                   project_id,
                   project_name,
                   game_name,
                   run_id,
                   run_type,
                   status,
                   created_utc,
                   started_utc,
                   finished_utc,
                   queue_position_at_start,
                   queue_seconds,
                   runtime_seconds,
                   exit_code
            FROM (
                SELECT
                    account_id,
                    username,
                    project_id,
                    project_name,
                    game_name,
                    run_id,
                    run_type,
                    status,
                    created_utc,
                    started_utc,
                    finished_utc,
                    queue_position_at_start,
                    queue_seconds,
                    runtime_seconds,
                    exit_code,
                    ROW_NUMBER() OVER (
                        PARTITION BY account_id
                        ORDER BY created_utc DESC, run_id DESC
                    ) AS rn
                FROM run_duration_metrics
                WHERE bucket = 'workflow'
                  AND ($account_id IS NULL OR account_id = $account_id)
                  AND ($run_type IS NULL OR run_type = $run_type)
            )
            WHERE rn <= $limit
            ORDER BY created_utc DESC, run_id DESC
            """;
        command.Parameters.AddWithValue("$account_id", (object?)normalizedAccountId ?? DBNull.Value);
        command.Parameters.AddWithValue("$run_type", (object?)normalizedRunType ?? DBNull.Value);
        command.Parameters.AddWithValue("$limit", boundedLimit);

        var rows = new List<AdminRunMetricsRow>();
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            rows.Add(new AdminRunMetricsRow(
                ReadRunDurationMetricSnapshot(reader)));
        }

        return rows;
    }

    public async Task<IReadOnlyList<AdminChatRunMetricSnapshotRow>> ListChatRunMetricSnapshotsForAdminAsync(
        string? accountId,
        int limit = 500,
        CancellationToken cancellationToken = default)
    {
        var boundedLimit = Math.Clamp(limit, 1, 500);
        var normalizedAccountId = string.IsNullOrWhiteSpace(accountId) ? null : accountId.Trim();

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT
                account_id,
                username,
                project_id,
                project_name,
                game_name,
                run_id,
                run_type,
                status,
                created_utc,
                started_utc,
                finished_utc,
                queue_position_at_start,
                queue_seconds,
                runtime_seconds,
                exit_code
            FROM run_duration_metrics
            WHERE bucket = 'chat'
              AND ($account_id IS NULL OR account_id = $account_id)
            ORDER BY created_utc DESC, run_id DESC
            LIMIT $limit;
            """;
        command.Parameters.AddWithValue("$account_id", (object?)normalizedAccountId ?? DBNull.Value);
        command.Parameters.AddWithValue("$limit", boundedLimit);

        var rows = new List<AdminChatRunMetricSnapshotRow>();
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            rows.Add(new AdminChatRunMetricSnapshotRow(ReadRunDurationMetricSnapshot(reader)));
        }

        return rows;
    }

    public async Task<IReadOnlyList<AdminAssetRunMetricsRow>> ListAssetRunMetricsForAdminAsync(
        string? accountId,
        string? runType,
        int limit = 500,
        CancellationToken cancellationToken = default)
    {
        var boundedLimit = Math.Clamp(limit, 1, 500);
        var normalizedAccountId = string.IsNullOrWhiteSpace(accountId) ? null : accountId.Trim();
        var normalizedRunType = string.IsNullOrWhiteSpace(runType) ? null : runType.Trim();

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT
                account_id,
                username,
                project_id,
                project_name,
                game_name,
                run_id,
                run_type,
                status,
                created_utc,
                started_utc,
                finished_utc,
                queue_position_at_start,
                queue_seconds,
                runtime_seconds,
                exit_code
            FROM run_duration_metrics
            WHERE bucket = 'asset'
              AND ($account_id IS NULL OR account_id = $account_id)
              AND ($run_type IS NULL OR run_type = $run_type)
            ORDER BY created_utc DESC, run_id DESC
            LIMIT $limit;
            """;
        command.Parameters.AddWithValue("$account_id", (object?)normalizedAccountId ?? DBNull.Value);
        command.Parameters.AddWithValue("$run_type", (object?)normalizedRunType ?? DBNull.Value);
        command.Parameters.AddWithValue("$limit", boundedLimit);

        var rows = new List<AdminAssetRunMetricsRow>();
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            rows.Add(new AdminAssetRunMetricsRow(ReadRunDurationMetricSnapshot(reader)));
        }

        return rows;
    }

    public async Task<IReadOnlyList<AdminChatRunMetricsRow>> ListChatRunMetricsForAdminAsync(
        string? accountId,
        CancellationToken cancellationToken = default)
    {
        var normalizedAccountId = string.IsNullOrWhiteSpace(accountId) ? null : accountId.Trim();

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT
                account_id,
                username,
                COUNT(*) AS run_count,
                ROUND(AVG(queue_seconds), 3) AS average_queue_seconds,
                ROUND(AVG(runtime_seconds), 3) AS average_runtime_seconds
            FROM run_duration_metrics
            WHERE bucket = 'chat'
              AND ($account_id IS NULL OR account_id = $account_id)
            GROUP BY account_id, username
            ORDER BY username ASC, account_id ASC;
            """;
        command.Parameters.AddWithValue("$account_id", (object?)normalizedAccountId ?? DBNull.Value);

        var rows = new List<AdminChatRunMetricsRow>();
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            rows.Add(new AdminChatRunMetricsRow(
                reader.GetString(0),
                reader.GetString(1),
                checked((int)reader.GetInt64(2)),
                reader.IsDBNull(3) ? null : reader.GetDouble(3),
                reader.IsDBNull(4) ? null : reader.GetDouble(4)));
        }

        return rows;
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
                r.created_utc,
                r.started_utc,
                r.finished_utc,
                r.queue_position_at_start,
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
              AND r.run_type <> 'prototype-chat'
            ORDER BY r.created_utc DESC, r.id DESC
            LIMIT 1;
            """;
        command.Parameters.AddWithValue("$account_id", accountId);

        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        if (!await reader.ReadAsync(cancellationToken))
        {
            return null;
        }

        return ReadRunSnapshot(reader);
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
        var mergedCostJson = await MergeRunLlmCostJsonAsync(connection, runId, llmCostJson, cancellationToken);
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
        command.Parameters.AddWithValue("$llm_cost_json", mergedCostJson);
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

    public async Task<IReadOnlyList<ArtifactSnapshot>> ListArtifactsForProjectAsync(
        string projectId,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT id, run_id, project_id, artifact_type, relative_path, summary
            FROM artifacts
            WHERE project_id = $project_id
            ORDER BY created_utc, id;
            """;
        command.Parameters.AddWithValue("$project_id", projectId);

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

    public async Task UpsertProjectRoutePromptEvidenceBindingAsync(
        ProjectRoutePromptEvidenceBindingCommand binding,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(binding);
        ArgumentException.ThrowIfNullOrWhiteSpace(binding.ProjectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(binding.RouteId);
        ArgumentException.ThrowIfNullOrWhiteSpace(binding.ExecutionPromptHash);
        ArgumentException.ThrowIfNullOrWhiteSpace(binding.PersistedPromptHash);
        ArgumentException.ThrowIfNullOrWhiteSpace(binding.PromptArtifactRef);
        ArgumentException.ThrowIfNullOrWhiteSpace(binding.PromptEvidenceRef);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            INSERT INTO project_route_prompt_evidence_bindings (
                project_id,
                route_id,
                execution_prompt_hash,
                persisted_prompt_hash,
                prompt_artifact_ref,
                prompt_evidence_ref,
                updated_utc
            ) VALUES (
                $project_id,
                $route_id,
                $execution_prompt_hash,
                $persisted_prompt_hash,
                $prompt_artifact_ref,
                $prompt_evidence_ref,
                $updated_utc
            )
            ON CONFLICT(project_id, route_id) DO UPDATE SET
                execution_prompt_hash = excluded.execution_prompt_hash,
                persisted_prompt_hash = excluded.persisted_prompt_hash,
                prompt_artifact_ref = excluded.prompt_artifact_ref,
                prompt_evidence_ref = excluded.prompt_evidence_ref,
                updated_utc = excluded.updated_utc;
            """;
        command.Parameters.AddWithValue("$project_id", binding.ProjectId);
        command.Parameters.AddWithValue("$route_id", binding.RouteId);
        command.Parameters.AddWithValue("$execution_prompt_hash", binding.ExecutionPromptHash);
        command.Parameters.AddWithValue("$persisted_prompt_hash", binding.PersistedPromptHash);
        command.Parameters.AddWithValue("$prompt_artifact_ref", binding.PromptArtifactRef);
        command.Parameters.AddWithValue("$prompt_evidence_ref", binding.PromptEvidenceRef);
        command.Parameters.AddWithValue("$updated_utc", DateTimeOffset.UtcNow.ToString("O"));
        await command.ExecuteNonQueryAsync(cancellationToken);
    }

    public async Task<IReadOnlyList<ProjectRoutePromptEvidenceBinding>> ListProjectRoutePromptEvidenceBindingsAsync(
        string projectId,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT project_id, route_id, execution_prompt_hash, persisted_prompt_hash,
                   prompt_artifact_ref, prompt_evidence_ref, updated_utc
            FROM project_route_prompt_evidence_bindings
            WHERE project_id = $project_id
            ORDER BY route_id;
            """;
        command.Parameters.AddWithValue("$project_id", projectId);

        var bindings = new List<ProjectRoutePromptEvidenceBinding>();
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            bindings.Add(new ProjectRoutePromptEvidenceBinding(
                reader.GetString(0),
                reader.GetString(1),
                reader.GetString(2),
                reader.GetString(3),
                reader.GetString(4),
                reader.GetString(5),
                reader.GetString(6)));
        }

        return bindings;
    }

    public async Task<IReadOnlyList<ArtifactSnapshot>> ListArtifactsForRunsAsync(
        IReadOnlyCollection<string> runIds,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(runIds);

        var normalizedRunIds = runIds
            .Where(runId => !string.IsNullOrWhiteSpace(runId))
            .Distinct(StringComparer.Ordinal)
            .ToArray();
        if (normalizedRunIds.Length == 0)
        {
            return [];
        }

        var artifacts = new List<ArtifactSnapshot>();
        await using var connection = await OpenConnectionAsync(cancellationToken);

        const int chunkSize = 500;
        foreach (var runIdChunk in normalizedRunIds.Chunk(chunkSize))
        {
            await using var command = connection.CreateCommand();
            var parameterNames = new List<string>(runIdChunk.Length);
            for (var i = 0; i < runIdChunk.Length; i++)
            {
                var parameterName = $"$run_id_{i}";
                parameterNames.Add(parameterName);
                command.Parameters.AddWithValue(parameterName, runIdChunk[i]);
            }

            command.CommandText =
                $"""
                SELECT id, run_id, project_id, artifact_type, relative_path, summary
                FROM artifacts
                WHERE run_id IN ({string.Join(", ", parameterNames)})
                ORDER BY created_utc, id;
                """;

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

    public async Task<ProjectChatMemorySnapshot?> GetProjectChatMemoryAsync(
        string accountId,
        string projectId,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT account_id, project_id, memory_summary, provider_session_ref, updated_utc
            FROM project_chat_memories
            WHERE account_id = $account_id
              AND project_id = $project_id;
            """;
        command.Parameters.AddWithValue("$account_id", accountId);
        command.Parameters.AddWithValue("$project_id", projectId);

        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        if (!await reader.ReadAsync(cancellationToken))
        {
            return null;
        }

        return new ProjectChatMemorySnapshot(
            reader.GetString(0),
            reader.GetString(1),
            reader.GetString(2),
            reader.IsDBNull(3) ? null : reader.GetString(3),
            reader.GetString(4));
    }

    public async Task UpsertProjectChatMemoryAsync(
        string accountId,
        string projectId,
        string memorySummary,
        string? providerSessionRef,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        memorySummary = memorySummary.Trim();

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            INSERT INTO project_chat_memories (
                account_id,
                project_id,
                memory_summary,
                provider_session_ref,
                updated_utc)
            VALUES (
                $account_id,
                $project_id,
                $memory_summary,
                $provider_session_ref,
                $updated_utc)
            ON CONFLICT(account_id, project_id) DO UPDATE SET
                memory_summary = excluded.memory_summary,
                provider_session_ref = excluded.provider_session_ref,
                updated_utc = excluded.updated_utc;
            """;
        command.Parameters.AddWithValue("$account_id", accountId);
        command.Parameters.AddWithValue("$project_id", projectId);
        command.Parameters.AddWithValue("$memory_summary", memorySummary);
        command.Parameters.AddWithValue("$provider_session_ref", (object?)providerSessionRef ?? DBNull.Value);
        command.Parameters.AddWithValue("$updated_utc", DateTimeOffset.UtcNow.ToString("O"));
        await command.ExecuteNonQueryAsync(cancellationToken);
    }

    public async Task<ProjectIterationSessionSnapshot> CreateProjectIterationSessionAsync(
        string accountId,
        string projectId,
        string sourceKind,
        string sourceMessage,
        string overallGoal,
        IReadOnlyList<ProjectIterationGoalCreateCommand> goals,
        CancellationToken cancellationToken = default,
        string? sessionId = null,
        string? requestIdentityHash = null,
        string? routeStateJson = null,
        string initialStatus = "planning",
        string? initialSummary = null)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(sourceKind);
        ArgumentException.ThrowIfNullOrWhiteSpace(sourceMessage);
        ArgumentException.ThrowIfNullOrWhiteSpace(overallGoal);
        ArgumentException.ThrowIfNullOrWhiteSpace(initialStatus);
        ArgumentNullException.ThrowIfNull(goals);

        sessionId = string.IsNullOrWhiteSpace(sessionId) ? NewId() : sessionId.Trim();
        var now = DateTimeOffset.UtcNow.ToString("O");

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var transaction = await connection.BeginTransactionAsync(cancellationToken);
        await using (var command = connection.CreateCommand())
        {
            command.Transaction = (SqliteTransaction)transaction;
            command.CommandText =
                """
                INSERT OR IGNORE INTO project_iteration_sessions (
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
                    request_identity_hash,
                    route_state_json,
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
                    $status,
                    0,
                    $latest_summary,
                    NULL,
                    $request_identity_hash,
                    $route_state_json,
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
            command.Parameters.AddWithValue("$status", initialStatus);
            command.Parameters.AddWithValue("$latest_summary", (object?)initialSummary ?? DBNull.Value);
            command.Parameters.AddWithValue("$request_identity_hash", (object?)requestIdentityHash ?? DBNull.Value);
            command.Parameters.AddWithValue("$route_state_json", (object?)routeStateJson ?? DBNull.Value);
            command.Parameters.AddWithValue("$created_utc", now);
            command.Parameters.AddWithValue("$updated_utc", now);
            if (await command.ExecuteNonQueryAsync(cancellationToken) != 1)
            {
                await transaction.RollbackAsync(cancellationToken);
                throw new ProjectIterationRequestIdentityConflictException();
            }
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
            initialStatus,
            0,
            initialSummary,
            null,
            now,
            now,
            null,
            null,
            requestIdentityHash,
            routeStateJson);
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
        CancellationToken cancellationToken)
    {
        return await GetLatestProjectIterationSessionAsync(projectId, null, cancellationToken);
    }

    public async Task SetProjectIterationTraceabilityAnchorAsync(
        string sessionId,
        string traceabilityAnchorJson,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(sessionId);
        ArgumentException.ThrowIfNullOrWhiteSpace(traceabilityAnchorJson);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            UPDATE project_iteration_sessions
            SET traceability_anchor_json = $traceability_anchor_json,
                updated_utc = $updated_utc
            WHERE id = $id;
            """;
        command.Parameters.AddWithValue("$id", sessionId);
        command.Parameters.AddWithValue("$traceability_anchor_json", traceabilityAnchorJson);
        command.Parameters.AddWithValue("$updated_utc", DateTimeOffset.UtcNow.ToString("O"));
        if (await command.ExecuteNonQueryAsync(cancellationToken) != 1)
        {
            throw new InvalidOperationException("Iteration session not found.");
        }
    }

    public async Task<ProjectIterationSessionDetails?> GetLatestProjectIterationSessionAsync(
        string projectId,
        string? sourceKind = null,
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
                       current_goal_index, latest_summary, latest_evaluation_json, traceability_anchor_json, created_utc, updated_utc, completed_utc,
                       request_identity_hash, route_state_json
                FROM project_iteration_sessions
                WHERE project_id = $project_id
                  AND (
                      ($source_kind IS NOT NULL AND source_kind = $source_kind)
                      OR ($source_kind IS NULL AND source_kind <> 'repair_plan')
                  )
                ORDER BY created_utc DESC
                LIMIT 1;
                """;
            command.Parameters.AddWithValue("$project_id", projectId);
            command.Parameters.AddWithValue("$source_kind", (object?)sourceKind ?? DBNull.Value);
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
                    reader.GetString(11),
                    reader.GetString(12),
                    reader.IsDBNull(13) ? null : reader.GetString(13),
                    reader.IsDBNull(10) ? null : reader.GetString(10),
                    reader.IsDBNull(14) ? null : reader.GetString(14),
                    reader.IsDBNull(15) ? null : reader.GetString(15));
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

    public async Task<IReadOnlyList<ProjectIterationSessionDetails>> ListProjectIterationSessionsAsync(
        string projectId,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        var sessions = new List<ProjectIterationSessionSnapshot>();
        await using (var command = connection.CreateCommand())
        {
            command.CommandText =
                """
                SELECT id, project_id, account_id, source_kind, source_message, overall_goal, status,
                       current_goal_index, latest_summary, latest_evaluation_json, traceability_anchor_json, created_utc, updated_utc, completed_utc,
                       request_identity_hash, route_state_json
                FROM project_iteration_sessions
                WHERE project_id = $project_id
                  AND source_kind <> 'repair_plan'
                ORDER BY created_utc ASC, id ASC;
                """;
            command.Parameters.AddWithValue("$project_id", projectId);
            await using var reader = await command.ExecuteReaderAsync(cancellationToken);
            while (await reader.ReadAsync(cancellationToken))
            {
                sessions.Add(new ProjectIterationSessionSnapshot(
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
                    reader.GetString(11),
                    reader.GetString(12),
                    reader.IsDBNull(13) ? null : reader.GetString(13),
                    reader.IsDBNull(10) ? null : reader.GetString(10),
                    reader.IsDBNull(14) ? null : reader.GetString(14),
                    reader.IsDBNull(15) ? null : reader.GetString(15)));
            }
        }

        var result = new List<ProjectIterationSessionDetails>();
        foreach (var session in sessions)
        {
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

            result.Add(new ProjectIterationSessionDetails(session, goals, goalRuns, latestEvaluation));
        }

        return result;
    }

    public async Task<ProjectIterationSessionDetails?> GetProjectIterationSessionAsync(
        string projectId,
        string sessionId,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(sessionId);

        var sessions = await ListProjectIterationSessionsAsync(projectId, cancellationToken);
        return sessions.FirstOrDefault(session => string.Equals(session.Session.SessionId, sessionId, StringComparison.Ordinal));
    }

    public async Task<ProjectIterationSessionDetails?> GetProjectIterationSessionByRequestIdentityAsync(
        string accountId,
        string projectId,
        string requestIdentityHash,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(requestIdentityHash);

        string? sessionId = null;
        await using (var connection = await OpenConnectionAsync(cancellationToken))
        await using (var command = connection.CreateCommand())
        {
            command.CommandText =
                """
                SELECT id
                FROM project_iteration_sessions
                WHERE account_id = $account_id
                  AND project_id = $project_id
                  AND request_identity_hash = $request_identity_hash
                ORDER BY created_utc DESC, id DESC
                LIMIT 1;
                """;
            command.Parameters.AddWithValue("$account_id", accountId);
            command.Parameters.AddWithValue("$project_id", projectId);
            command.Parameters.AddWithValue("$request_identity_hash", requestIdentityHash);
            sessionId = await command.ExecuteScalarAsync(cancellationToken) as string;
        }

        return string.IsNullOrWhiteSpace(sessionId)
            ? null
            : await GetProjectIterationSessionAsync(projectId, sessionId, cancellationToken);
    }

    public async Task<int> DeleteProjectIterationSessionsAsync(
        string projectId,
        string accountId,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            DELETE FROM project_iteration_sessions
            WHERE project_id = $project_id
              AND account_id = $account_id
              AND source_kind <> 'repair_plan';
            """;
        command.Parameters.AddWithValue("$project_id", projectId);
        command.Parameters.AddWithValue("$account_id", accountId);
        return await command.ExecuteNonQueryAsync(cancellationToken);
    }

    public async Task<int> DeleteProjectIterationSessionAsync(
        string projectId,
        string accountId,
        string sessionId,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(sessionId);

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            DELETE FROM project_iteration_sessions
            WHERE id = $session_id
              AND project_id = $project_id
              AND account_id = $account_id
              AND source_kind <> 'repair_plan';
            """;
        command.Parameters.AddWithValue("$session_id", sessionId);
        command.Parameters.AddWithValue("$project_id", projectId);
        command.Parameters.AddWithValue("$account_id", accountId);
        return await command.ExecuteNonQueryAsync(cancellationToken);
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
                draft_text,
                coverage_percent,
                coverage_summary,
                coverage_missing_topics_json,
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
            reader.IsDBNull(16) ? null : reader.GetString(16),
            reader.GetString(17),
            reader.IsDBNull(18) ? null : reader.GetString(18),
            reader.GetInt32(19),
            reader.GetInt32(20),
            reader.GetString(21));
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
        string? draftText,
        int coveragePercent,
        string? coverageSummary,
        string coverageMissingTopicsJson,
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
                draft_text,
                coverage_percent,
                coverage_summary,
                coverage_missing_topics_json,
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
                $draft_text,
                $coverage_percent,
                $coverage_summary,
                $coverage_missing_topics_json,
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
                draft_text = excluded.draft_text,
                coverage_percent = excluded.coverage_percent,
                coverage_summary = excluded.coverage_summary,
                coverage_missing_topics_json = excluded.coverage_missing_topics_json,
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
        command.Parameters.AddWithValue("$draft_text", (object?)draftText ?? DBNull.Value);
        command.Parameters.AddWithValue("$coverage_percent", coveragePercent);
        command.Parameters.AddWithValue("$coverage_summary", (object?)coverageSummary ?? DBNull.Value);
        command.Parameters.AddWithValue("$coverage_missing_topics_json", coverageMissingTopicsJson);
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

    private static async Task UpsertRunDurationMetricAsync(
        SqliteConnection connection,
        SqliteTransaction transaction,
        string runId,
        string finishedUtc,
        CancellationToken cancellationToken)
    {
        await using var command = connection.CreateCommand();
        command.Transaction = transaction;
        command.CommandText =
            """
            INSERT INTO run_duration_metrics (
                id,
                bucket,
                account_id,
                username,
                project_id,
                project_name,
                game_name,
                run_id,
                run_type,
                status,
                created_utc,
                started_utc,
                finished_utc,
                queue_position_at_start,
                queue_seconds,
                runtime_seconds,
                exit_code)
            SELECT
                $id,
                CASE
                    WHEN r.run_type = 'prototype-chat' THEN 'chat'
                    WHEN r.run_type = 'project-asset-generation' OR r.run_type = 'asset-generation' THEN 'asset'
                    ELSE 'workflow'
                END,
                a.id,
                a.username,
                p.id,
                p.name,
                p.game_name,
                r.id,
                r.run_type,
                r.status,
                r.created_utc,
                r.started_utc,
                COALESCE(r.finished_utc, $finished_utc),
                r.queue_position_at_start,
                ROUND(CASE
                    WHEN r.started_utc IS NULL THEN NULL
                    ELSE MAX(0.0, (julianday(r.started_utc) - julianday(r.created_utc)) * 86400.0)
                END, 3),
                ROUND(CASE
                    WHEN r.started_utc IS NULL OR COALESCE(r.finished_utc, $finished_utc) IS NULL THEN NULL
                    ELSE MAX(0.0, (julianday(COALESCE(r.finished_utc, $finished_utc)) - julianday(r.started_utc)) * 86400.0)
                END, 3),
                r.exit_code
            FROM runs r
            INNER JOIN projects p ON p.id = r.project_id
            INNER JOIN accounts a ON a.id = p.account_id
            WHERE r.id = $run_id
              AND a.is_admin = 0
            ON CONFLICT(run_id) DO UPDATE SET
                bucket = excluded.bucket,
                account_id = excluded.account_id,
                username = excluded.username,
                project_id = excluded.project_id,
                project_name = excluded.project_name,
                game_name = excluded.game_name,
                run_type = excluded.run_type,
                status = excluded.status,
                created_utc = excluded.created_utc,
                started_utc = excluded.started_utc,
                finished_utc = excluded.finished_utc,
                queue_position_at_start = excluded.queue_position_at_start,
                queue_seconds = excluded.queue_seconds,
                runtime_seconds = excluded.runtime_seconds,
                exit_code = excluded.exit_code;
            """;
        command.Parameters.AddWithValue("$id", NewId());
        command.Parameters.AddWithValue("$run_id", runId);
        command.Parameters.AddWithValue("$finished_utc", finishedUtc);
        await command.ExecuteNonQueryAsync(cancellationToken);
    }

    private static async Task PruneRunDurationMetricsAsync(
        SqliteConnection connection,
        SqliteTransaction transaction,
        CancellationToken cancellationToken)
    {
        await using var workflowCommand = connection.CreateCommand();
        workflowCommand.Transaction = transaction;
        workflowCommand.CommandText =
            """
            DELETE FROM run_duration_metrics
            WHERE bucket = 'workflow'
              AND id NOT IN (
                  SELECT id
                  FROM (
                      SELECT
                          id,
                          ROW_NUMBER() OVER (
                              PARTITION BY account_id
                              ORDER BY created_utc DESC, run_id DESC
                          ) AS rn
                      FROM run_duration_metrics
                      WHERE bucket = 'workflow'
                  )
                  WHERE rn <= 500
              );
            """;
        await workflowCommand.ExecuteNonQueryAsync(cancellationToken);

        await using var chatCommand = connection.CreateCommand();
        chatCommand.Transaction = transaction;
        chatCommand.CommandText =
            """
            DELETE FROM run_duration_metrics
            WHERE bucket = 'chat'
              AND id NOT IN (
                  SELECT id
                  FROM run_duration_metrics
                  WHERE bucket = 'chat'
                  ORDER BY created_utc DESC, run_id DESC
                  LIMIT 500
              );
            """;
        await chatCommand.ExecuteNonQueryAsync(cancellationToken);

        await using var assetCommand = connection.CreateCommand();
        assetCommand.Transaction = transaction;
        assetCommand.CommandText =
            """
            DELETE FROM run_duration_metrics
            WHERE bucket = 'asset'
              AND id NOT IN (
                  SELECT id
                  FROM run_duration_metrics
                  WHERE bucket = 'asset'
                  ORDER BY created_utc DESC, run_id DESC
                  LIMIT 500
              );
            """;
        await assetCommand.ExecuteNonQueryAsync(cancellationToken);
    }

    private static RunDurationMetricSnapshot ReadRunDurationMetricSnapshot(SqliteDataReader reader, int offset = 0)
    {
        return new RunDurationMetricSnapshot(
            reader.GetString(offset + 0),
            reader.GetString(offset + 1),
            reader.GetString(offset + 2),
            reader.GetString(offset + 3),
            reader.GetString(offset + 4),
            reader.GetString(offset + 5),
            reader.GetString(offset + 6),
            reader.GetString(offset + 7),
            reader.GetString(offset + 8),
            reader.IsDBNull(offset + 9) ? null : reader.GetString(offset + 9),
            reader.IsDBNull(offset + 10) ? null : reader.GetString(offset + 10),
            reader.IsDBNull(offset + 11) ? null : reader.GetInt32(offset + 11),
            reader.IsDBNull(offset + 12) ? null : reader.GetDouble(offset + 12),
            reader.IsDBNull(offset + 13) ? null : reader.GetDouble(offset + 13),
            reader.IsDBNull(offset + 14) ? null : reader.GetInt32(offset + 14));
    }

    private static RunSnapshot ReadRunSnapshot(SqliteDataReader reader, int offset = 0)
    {
        return new RunSnapshot(
            reader.GetString(offset + 0),
            reader.GetString(offset + 1),
            reader.IsDBNull(offset + 2) ? null : reader.GetString(offset + 2),
            reader.GetString(offset + 3),
            reader.GetString(offset + 4),
            reader.GetString(offset + 5),
            reader.IsDBNull(offset + 6) ? null : reader.GetString(offset + 6),
            reader.IsDBNull(offset + 7) ? null : reader.GetString(offset + 7),
            reader.IsDBNull(offset + 8) ? null : reader.GetInt32(offset + 8),
            reader.IsDBNull(offset + 9) ? null : reader.GetInt32(offset + 9),
            reader.IsDBNull(offset + 10) ? null : reader.GetString(offset + 10),
            reader.IsDBNull(offset + 11) ? null : reader.GetString(offset + 11),
            reader.IsDBNull(offset + 12) ? null : reader.GetString(offset + 12),
            reader.GetString(offset + 13),
            reader.GetString(offset + 14),
            reader.GetString(offset + 15),
            reader.IsDBNull(offset + 16) ? null : reader.GetString(offset + 16),
            reader.IsDBNull(offset + 17) ? null : reader.GetString(offset + 17),
            reader.IsDBNull(offset + 18) ? null : reader.GetString(offset + 18),
            reader.IsDBNull(offset + 19) ? null : reader.GetString(offset + 19),
            reader.IsDBNull(offset + 20) ? null : reader.GetString(offset + 20));
    }

    private static async Task<ProjectAdminReviewQueueEntry?> GetProjectAdminReviewQueueEntryByKeyAsync(
        SqliteConnection connection,
        SqliteTransaction transaction,
        string projectId,
        string routeId,
        string requirementId,
        CancellationToken cancellationToken)
    {
        await using var command = connection.CreateCommand();
        command.Transaction = transaction;
        command.CommandText =
            """
            SELECT id, account_id, project_id, route_id, requirement_id, severity, blocking_reason,
                   source_artifact_path, evidence_refs_json, status, decision_status, decision_actor_account_id,
                   decision_reason, decision_metadata_json, decision_version, created_utc, updated_utc, decided_utc, project_deleted_utc,
                   supersedes_entry_id, superseded_by_entry_id
            FROM project_admin_review_queue
            WHERE project_id = $project_id
              AND route_id = $route_id
              AND requirement_id = $requirement_id
              AND status <> 'superseded'
            LIMIT 1;
            """;
        command.Parameters.AddWithValue("$project_id", projectId);
        command.Parameters.AddWithValue("$route_id", routeId);
        command.Parameters.AddWithValue("$requirement_id", requirementId);
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        return await reader.ReadAsync(cancellationToken) ? ReadAdminReviewQueueEntry(reader) : null;
    }

    private static async Task<ProjectAdminReviewQueueEntry?> GetProjectAdminReviewQueueEntryByIdAsync(
        SqliteConnection connection,
        string entryId,
        CancellationToken cancellationToken,
        SqliteTransaction? transaction = null)
    {
        await using var command = connection.CreateCommand();
        command.Transaction = transaction;
        command.CommandText =
            """
            SELECT id, account_id, project_id, route_id, requirement_id, severity, blocking_reason,
                   source_artifact_path, evidence_refs_json, status, decision_status, decision_actor_account_id,
                   decision_reason, decision_metadata_json, decision_version, created_utc, updated_utc, decided_utc, project_deleted_utc,
                   supersedes_entry_id, superseded_by_entry_id
            FROM project_admin_review_queue
            WHERE id = $id
            LIMIT 1;
            """;
        command.Parameters.AddWithValue("$id", entryId);
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        return await reader.ReadAsync(cancellationToken) ? ReadAdminReviewQueueEntry(reader) : null;
    }

    private async Task<ProjectAdminReviewQueueEntry?> GetProjectAdminReviewQueueEntryByIdAsync(
        string entryId,
        CancellationToken cancellationToken)
    {
        await using var connection = await OpenConnectionAsync(cancellationToken);
        return await GetProjectAdminReviewQueueEntryByIdAsync(connection, entryId, cancellationToken);
    }

    private static bool HasValidDeferredDecisionMetadata(
        ProjectAdminReviewDecisionRequest request,
        string routeId,
        DateTimeOffset now)
    {
        var hasExpiry = !string.IsNullOrWhiteSpace(request.DeferredUntilUtc);
        var hasValidFutureExpiry = DateTimeOffset.TryParse(request.DeferredUntilUtc, out var deferredUntil) && deferredUntil > now;
        return !string.IsNullOrWhiteSpace(request.DeferredOwner) &&
               (!hasExpiry || hasValidFutureExpiry) &&
               (hasValidFutureExpiry || !string.IsNullOrWhiteSpace(request.RecheckTrigger)) &&
               request.AffectedRoutes is { Count: > 0 } &&
               request.AffectedRoutes.All(route => !string.IsNullOrWhiteSpace(route)) &&
               request.AffectedRoutes.Any(route => string.Equals(route.Trim(), routeId, StringComparison.Ordinal));
    }

    private static string NormalizeAdminReviewEvidenceRefsJson(string evidenceRefsJson)
    {
        JsonArray array;
        try
        {
            array = JsonNode.Parse(evidenceRefsJson) as JsonArray
                ?? throw new ArgumentException("admin_review_evidence_refs_invalid", nameof(evidenceRefsJson));
        }
        catch (JsonException exception)
        {
            throw new ArgumentException("admin_review_evidence_refs_invalid", nameof(evidenceRefsJson), exception);
        }

        foreach (var item in array)
        {
            if (item is not JsonObject evidence ||
                evidence["kind"] is not JsonValue kindValue ||
                !kindValue.TryGetValue<string>(out var kind) ||
                !AdminReviewEvidenceKinds.Contains(kind))
            {
                throw new ArgumentException("admin_review_evidence_ref_kind_invalid", nameof(evidenceRefsJson));
            }

            var path = evidence["path"]?.GetValue<string>()?.Trim() ?? "";
            var artifactId = evidence["artifact_id"]?.GetValue<string>()?.Trim() ?? "";
            if (path.Length == 0 && artifactId.Length == 0)
            {
                throw new ArgumentException("admin_review_evidence_ref_locator_missing", nameof(evidenceRefsJson));
            }
            if (path.Length > 0)
            {
                var normalized = path.Replace('\\', '/');
                if (Path.IsPathRooted(path) ||
                    normalized.Contains("://", StringComparison.Ordinal) ||
                    normalized.Split('/', StringSplitOptions.RemoveEmptyEntries).Any(segment => segment == ".."))
                {
                    throw new ArgumentException("admin_review_evidence_ref_path_invalid", nameof(evidenceRefsJson));
                }
                evidence["path"] = normalized;
            }
        }

        return SecretRedactionPolicy.RedactForPersistence(array.ToJsonString());
    }

    private static string BuildAdminReviewDecisionMetadata(
        ProjectAdminReviewDecisionRequest request,
        string actorAccountId,
        string decisionReason,
        string decisionUtc,
        JsonArray normalizedDecisionEvidenceRefs)
    {
        var metadata = JsonSerializer.Serialize(new
        {
            decision_by = actorAccountId,
            decision_role = "admin",
            decision_reason = decisionReason,
            decision_utc = decisionUtc,
            decision_evidence_refs = normalizedDecisionEvidenceRefs,
            deferred_owner = request.DeferredOwner?.Trim(),
            deferred_until_utc = request.DeferredUntilUtc?.Trim(),
            recheck_trigger = request.RecheckTrigger?.Trim(),
            affected_routes = request.AffectedRoutes?
                .Where(item => !string.IsNullOrWhiteSpace(item))
                .Select(item => item.Trim())
                .ToArray() ?? []
        });
        return SecretRedactionPolicy.RedactForPersistence(metadata);
    }

    private static JsonArray NormalizeAdminReviewDecisionEvidenceRefs(IReadOnlyList<string>? evidenceRefs)
    {
        var normalized = new JsonArray();
        foreach (var raw in evidenceRefs ?? [])
        {
            var value = raw?.Trim() ?? "";
            if (value.Length == 0)
            {
                continue;
            }

            if (value.StartsWith("artifact:", StringComparison.Ordinal))
            {
                var artifactId = value["artifact:".Length..].Trim();
                if (artifactId.Length == 0 || artifactId.Contains('/') || artifactId.Contains('\\'))
                {
                    throw new ArgumentException("admin_review_decision_evidence_ref_invalid");
                }
                normalized.Add(new JsonObject { ["kind"] = "artifact", ["artifact_id"] = artifactId });
                continue;
            }

            var path = value.Replace('\\', '/');
            if (Path.IsPathRooted(value) ||
                path.Contains("://", StringComparison.Ordinal) ||
                path.Split('/', StringSplitOptions.RemoveEmptyEntries).Any(segment => segment == ".."))
            {
                throw new ArgumentException("admin_review_decision_evidence_ref_invalid");
            }
            normalized.Add(new JsonObject { ["kind"] = "sidecar", ["path"] = path });
        }
        return normalized;
    }

    private static async Task<bool> AdminReviewDecisionEvidenceRefsExistAsync(
        SqliteConnection connection,
        SqliteTransaction transaction,
        string projectId,
        JsonArray evidenceRefs,
        CancellationToken cancellationToken)
    {
        if (evidenceRefs.Count == 0)
        {
            return true;
        }

        string repoPath;
        await using (var workspace = connection.CreateCommand())
        {
            workspace.Transaction = transaction;
            workspace.CommandText = "SELECT repo_path FROM workspaces WHERE project_id = $project_id LIMIT 1;";
            workspace.Parameters.AddWithValue("$project_id", projectId);
            repoPath = (await workspace.ExecuteScalarAsync(cancellationToken)) as string ?? "";
        }
        if (string.IsNullOrWhiteSpace(repoPath))
        {
            return false;
        }

        var root = Path.GetFullPath(repoPath);
        foreach (var node in evidenceRefs.OfType<JsonObject>())
        {
            var artifactId = node["artifact_id"]?.GetValue<string>() ?? "";
            if (artifactId.Length > 0)
            {
                await using var artifact = connection.CreateCommand();
                artifact.Transaction = transaction;
                artifact.CommandText = "SELECT relative_path FROM artifacts WHERE id = $artifact_id AND project_id = $project_id LIMIT 1;";
                artifact.Parameters.AddWithValue("$artifact_id", artifactId);
                artifact.Parameters.AddWithValue("$project_id", projectId);
                var artifactRelativePath = (await artifact.ExecuteScalarAsync(cancellationToken)) as string ?? "";
                if (!IsExistingProjectEvidenceFile(root, artifactRelativePath))
                {
                    return false;
                }
                continue;
            }

            var relativePath = node["path"]?.GetValue<string>() ?? "";
            if (!IsExistingProjectEvidenceFile(root, relativePath))
            {
                return false;
            }
        }

        return true;
    }

    private static bool IsExistingProjectEvidenceFile(string root, string relativePath)
    {
        try
        {
            if (string.IsNullOrWhiteSpace(relativePath) || Path.IsPathRooted(relativePath))
            {
                return false;
            }

            var rootFullPath = Path.GetFullPath(root);
            var fullPath = Path.GetFullPath(Path.Combine(rootFullPath, relativePath.Replace('/', Path.DirectorySeparatorChar)));
            var prefix = rootFullPath.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar) + Path.DirectorySeparatorChar;
            var comparison = OperatingSystem.IsWindows() ? StringComparison.OrdinalIgnoreCase : StringComparison.Ordinal;
            if (!fullPath.StartsWith(prefix, comparison) || !File.Exists(fullPath))
            {
                return false;
            }

            var current = rootFullPath;
            if ((File.GetAttributes(current) & FileAttributes.ReparsePoint) != 0)
            {
                return false;
            }
            foreach (var segment in Path.GetRelativePath(rootFullPath, fullPath)
                         .Split([Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar], StringSplitOptions.RemoveEmptyEntries))
            {
                current = Path.Combine(current, segment);
                if ((File.GetAttributes(current) & FileAttributes.ReparsePoint) != 0)
                {
                    return false;
                }
            }

            return true;
        }
        catch (Exception ex) when (ex is ArgumentException or NotSupportedException or PathTooLongException or IOException or UnauthorizedAccessException)
        {
            return false;
        }
    }

    private async Task RefreshAdminReviewQueueSidecarAsync(string projectId, CancellationToken cancellationToken)
    {
        var gate = AdminReviewSidecarLocks.GetOrAdd(projectId, _ => new SemaphoreSlim(1, 1));
        await gate.WaitAsync(cancellationToken);
        try
        {
            var project = await GetProjectSnapshotAsync(projectId, cancellationToken);
            if (project is null)
            {
                return;
            }

            var entries = await ListProjectAdminReviewQueueForProjectAsync(project.AccountId, project.ProjectId, "", 0, cancellationToken);
            await ProjectAdminReviewQueueSidecarWriter.WriteAsync(project, entries, cancellationToken);
        }
        finally
        {
            gate.Release();
        }
    }

    private async Task<ProjectDiagnosticSpoolEntry?> GetProjectDiagnosticSpoolEntryByIdAsync(
        string entryId,
        CancellationToken cancellationToken)
    {
        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT id, diagnostic_id, account_id, project_id, project_name_snapshot, run_id, route_id, failure_family, severity, triage_status,
                   retention_class, redaction_status, spool_ref, safe_summary, user_safe_summary, source_refs_json,
                   evidence_refs_json, source_artifact_path, cleanup_status, replacement_evidence_refs_json, admin_summary, remediation_hint_id,
                   created_utc, updated_utc, resolved_utc, project_deleted_utc, triage_decision_by, triage_decision_reason,
                   deletion_event_id, project_tombstone_id
            FROM project_diagnostic_spool
            WHERE id = $id OR diagnostic_id = $id
            LIMIT 1;
            """;
        command.Parameters.AddWithValue("$id", entryId);
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        return await reader.ReadAsync(cancellationToken) ? ReadDiagnosticSpoolEntry(reader) : null;
    }

    private async Task RecordProjectDeleteTombstoneInsideTransactionAsync(
        SqliteConnection connection,
        SqliteTransaction transaction,
        string projectId,
        CancellationToken cancellationToken)
    {
        var project = await GetProjectSnapshotInsideTransactionAsync(connection, transaction, projectId, cancellationToken);
        if (project is null)
        {
            return;
        }

        var now = DateTimeOffset.UtcNow.ToString("O");
        var deletionEventId = $"delete-{NewId()}";
        var projectTombstoneId = $"tombstone-{project.ProjectId}";
        var unresolvedAdminReviewCount = await CountBlockingAdminReviewEntriesInsideTransactionAsync(
            connection,
            transaction,
            projectId,
            DateTimeOffset.Parse(now),
            cancellationToken);
        var unresolvedDiagnosticCount = await ExecuteScalarLongInsideTransactionAsync(
            connection,
            transaction,
            "SELECT COUNT(*) FROM project_diagnostic_spool WHERE project_id = $project_id AND triage_status IN ('unresolved', 'backlog');",
            cancellationToken,
            ("$project_id", projectId)) ?? 0;

        await using (var tombstone = connection.CreateCommand())
        {
            tombstone.Transaction = transaction;
            tombstone.CommandText =
                """
                INSERT INTO project_delete_tombstones (
                    project_tombstone_id, deletion_event_id, project_id, account_id, project_name, deleted_utc,
                    unresolved_admin_review_count, unresolved_diagnostic_count, evidence_refs_json)
                VALUES (
                    $project_tombstone_id, $deletion_event_id, $project_id, $account_id, $project_name, $deleted_utc,
                    $unresolved_admin_review_count, $unresolved_diagnostic_count, $evidence_refs_json)
                ON CONFLICT(project_id) DO UPDATE SET
                    project_tombstone_id = excluded.project_tombstone_id,
                    deletion_event_id = excluded.deletion_event_id,
                    deleted_utc = excluded.deleted_utc,
                    unresolved_admin_review_count = excluded.unresolved_admin_review_count,
                    unresolved_diagnostic_count = excluded.unresolved_diagnostic_count,
                    evidence_refs_json = excluded.evidence_refs_json;
                """;
            tombstone.Parameters.AddWithValue("$project_tombstone_id", projectTombstoneId);
            tombstone.Parameters.AddWithValue("$deletion_event_id", deletionEventId);
            tombstone.Parameters.AddWithValue("$project_id", project.ProjectId);
            tombstone.Parameters.AddWithValue("$account_id", project.AccountId);
            tombstone.Parameters.AddWithValue("$project_name", project.Name);
            tombstone.Parameters.AddWithValue("$deleted_utc", now);
            tombstone.Parameters.AddWithValue("$unresolved_admin_review_count", unresolvedAdminReviewCount);
            tombstone.Parameters.AddWithValue("$unresolved_diagnostic_count", unresolvedDiagnosticCount);
            tombstone.Parameters.AddWithValue("$evidence_refs_json", """[{"kind":"db_row","path":"project_delete_tombstones"}]""");
            await tombstone.ExecuteNonQueryAsync(cancellationToken);
        }

        foreach (var table in new[] { "project_admin_review_queue", "project_diagnostic_spool", "game_type_maintenance_records" })
        {
            await using var command = connection.CreateCommand();
            command.Transaction = transaction;
            command.CommandText = $"UPDATE {table} SET project_deleted_utc = $deleted_utc WHERE project_id = $project_id AND project_deleted_utc IS NULL;";
            command.Parameters.AddWithValue("$deleted_utc", now);
            command.Parameters.AddWithValue("$project_id", projectId);
            await command.ExecuteNonQueryAsync(cancellationToken);
        }

        await using (var diagnosticIds = connection.CreateCommand())
        {
            diagnosticIds.Transaction = transaction;
            diagnosticIds.CommandText =
                """
                UPDATE project_diagnostic_spool
                SET deletion_event_id = $deletion_event_id,
                    project_tombstone_id = $project_tombstone_id,
                    project_name_snapshot = CASE WHEN project_name_snapshot = '' THEN $project_name ELSE project_name_snapshot END,
                    updated_utc = $updated_utc
                WHERE project_id = $project_id
                  AND deletion_event_id IS NULL;
                """;
            diagnosticIds.Parameters.AddWithValue("$deletion_event_id", deletionEventId);
            diagnosticIds.Parameters.AddWithValue("$project_tombstone_id", projectTombstoneId);
            diagnosticIds.Parameters.AddWithValue("$project_name", project.Name);
            diagnosticIds.Parameters.AddWithValue("$updated_utc", now);
            diagnosticIds.Parameters.AddWithValue("$project_id", projectId);
            await diagnosticIds.ExecuteNonQueryAsync(cancellationToken);
        }

        var diagnosticId = NewId();
        var spoolRef = await WriteDiagnosticSpoolFileAsync(
            diagnosticId,
            new ProjectDiagnosticSpoolCommand(
                project.AccountId,
                project.ProjectId,
                "project-delete",
                "workspace_delete_failed",
                unresolvedAdminReviewCount + unresolvedDiagnosticCount > 0 ? "P2" : "info",
                "Project deletion preserved governance and diagnostic records for admin triage.",
                """[{"kind":"db_row","path":"project_delete_tombstones"}]""",
                "project_delete_tombstones",
                unresolvedAdminReviewCount + unresolvedDiagnosticCount > 0 ? "backlog" : "resolved",
                project.Name,
                SourceRefsJson: """[{"kind":"db_row","path":"projects"}]""",
                RetentionClass: unresolvedAdminReviewCount + unresolvedDiagnosticCount > 0 ? "backlog_audit" : "resolved_audit",
                AdminSummary: "Project deletion tombstone recorded; preserved diagnostics remain outside the hosted workspace.",
                RemediationHintId: "workspace_delete_failed"),
            now,
            cancellationToken);
        await using (var deleteDiagnostic = connection.CreateCommand())
        {
            deleteDiagnostic.Transaction = transaction;
            deleteDiagnostic.CommandText =
                """
                INSERT INTO project_diagnostic_spool (
                    id, diagnostic_id, account_id, project_id, project_name_snapshot, route_id, failure_family, severity,
                    triage_status, retention_class, redaction_status, spool_ref, safe_summary, user_safe_summary,
                    source_refs_json, evidence_refs_json, source_artifact_path, cleanup_status, admin_summary,
                    remediation_hint_id, created_utc, updated_utc, resolved_utc, triage_decision_by,
                    triage_decision_reason, deletion_event_id, project_tombstone_id, project_deleted_utc)
                VALUES (
                    $id, $diagnostic_id, $account_id, $project_id, $project_name_snapshot, 'project-delete', 'workspace_delete_failed', $severity,
                    $triage_status, $retention_class, 'redacted', $spool_ref, $safe_summary, $user_safe_summary,
                    $source_refs_json, $evidence_refs_json, 'project_delete_tombstones', 'preserved', $admin_summary,
                    'workspace_delete_failed', $created_utc, $updated_utc, $resolved_utc, $triage_decision_by,
                    $triage_decision_reason, $deletion_event_id, $project_tombstone_id, $project_deleted_utc);
                """;
            deleteDiagnostic.Parameters.AddWithValue("$id", diagnosticId);
            deleteDiagnostic.Parameters.AddWithValue("$diagnostic_id", diagnosticId);
            deleteDiagnostic.Parameters.AddWithValue("$account_id", project.AccountId);
            deleteDiagnostic.Parameters.AddWithValue("$project_id", project.ProjectId);
            deleteDiagnostic.Parameters.AddWithValue("$project_name_snapshot", project.Name);
            deleteDiagnostic.Parameters.AddWithValue("$severity", unresolvedAdminReviewCount + unresolvedDiagnosticCount > 0 ? "P2" : "info");
            deleteDiagnostic.Parameters.AddWithValue("$triage_status", unresolvedAdminReviewCount + unresolvedDiagnosticCount > 0 ? "backlog" : "resolved");
            deleteDiagnostic.Parameters.AddWithValue("$retention_class", unresolvedAdminReviewCount + unresolvedDiagnosticCount > 0 ? "backlog_audit" : "resolved_audit");
            deleteDiagnostic.Parameters.AddWithValue("$spool_ref", spoolRef);
            deleteDiagnostic.Parameters.AddWithValue("$safe_summary", "Project deletion preserved governance and diagnostic records for admin triage.");
            deleteDiagnostic.Parameters.AddWithValue("$user_safe_summary", "Project deletion preserved governance and diagnostic records for admin triage.");
            deleteDiagnostic.Parameters.AddWithValue("$source_refs_json", """[{"kind":"db_row","path":"projects"}]""");
            deleteDiagnostic.Parameters.AddWithValue("$evidence_refs_json", """[{"kind":"db_row","path":"project_delete_tombstones"}]""");
            deleteDiagnostic.Parameters.AddWithValue("$admin_summary", "Project deletion tombstone recorded; preserved diagnostics remain outside the hosted workspace.");
            deleteDiagnostic.Parameters.AddWithValue("$created_utc", now);
            deleteDiagnostic.Parameters.AddWithValue("$updated_utc", now);
            deleteDiagnostic.Parameters.AddWithValue("$resolved_utc", unresolvedAdminReviewCount + unresolvedDiagnosticCount > 0 ? DBNull.Value : now);
            deleteDiagnostic.Parameters.AddWithValue("$triage_decision_by", DBNull.Value);
            deleteDiagnostic.Parameters.AddWithValue("$triage_decision_reason", "");
            deleteDiagnostic.Parameters.AddWithValue("$deletion_event_id", deletionEventId);
            deleteDiagnostic.Parameters.AddWithValue("$project_tombstone_id", projectTombstoneId);
            deleteDiagnostic.Parameters.AddWithValue("$project_deleted_utc", now);
            await deleteDiagnostic.ExecuteNonQueryAsync(cancellationToken);
        }
    }

    private static async Task<long> CountBlockingAdminReviewEntriesInsideTransactionAsync(
        SqliteConnection connection,
        SqliteTransaction transaction,
        string projectId,
        DateTimeOffset now,
        CancellationToken cancellationToken)
    {
        await using var command = connection.CreateCommand();
        command.Transaction = transaction;
        command.CommandText =
            """
            SELECT id, account_id, project_id, route_id, requirement_id, severity, blocking_reason,
                   source_artifact_path, evidence_refs_json, status, decision_status, decision_actor_account_id,
                   decision_reason, decision_metadata_json, decision_version, created_utc, updated_utc, decided_utc, project_deleted_utc,
                   supersedes_entry_id, superseded_by_entry_id
            FROM project_admin_review_queue
            WHERE project_id = $project_id AND status <> 'superseded';
            """;
        command.Parameters.AddWithValue("$project_id", projectId);
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        long count = 0;
        while (await reader.ReadAsync(cancellationToken))
        {
            if (ProjectAdminReviewQueuePolicy.IsBlocking(ReadAdminReviewQueueEntry(reader), now))
            {
                count++;
            }
        }
        return count;
    }

    private static async Task<ProjectSnapshot?> GetProjectSnapshotInsideTransactionAsync(
        SqliteConnection connection,
        SqliteTransaction transaction,
        string projectId,
        CancellationToken cancellationToken)
    {
        await using var command = connection.CreateCommand();
        command.Transaction = transaction;
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
                w.meta_path,
                p.game_type_match_json
            FROM projects p
            JOIN workspaces w ON w.project_id = p.id
            WHERE p.id = $project_id
            LIMIT 1;
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
            reader.GetString(14),
            reader.GetString(15));
    }

    private static ProjectAdminReviewQueueEntry ReadAdminReviewQueueEntry(SqliteDataReader reader)
    {
        return new ProjectAdminReviewQueueEntry(
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
            reader.GetString(10),
            reader.IsDBNull(11) ? null : reader.GetString(11),
            reader.GetString(12),
            reader.GetString(13),
            checked((int)reader.GetInt64(14)),
            reader.GetString(15),
            reader.GetString(16),
            reader.IsDBNull(17) ? null : reader.GetString(17),
            reader.IsDBNull(18) ? null : reader.GetString(18),
            reader.IsDBNull(19) ? null : reader.GetString(19),
            reader.IsDBNull(20) ? null : reader.GetString(20));
    }

    private static ProjectDiagnosticSpoolEntry ReadDiagnosticSpoolEntry(SqliteDataReader reader)
    {
        return new ProjectDiagnosticSpoolEntry(
            reader.GetString(0),
            reader.IsDBNull(1) || string.IsNullOrWhiteSpace(reader.GetString(1)) ? reader.GetString(0) : reader.GetString(1),
            reader.GetString(2),
            reader.GetString(3),
            reader.GetString(4),
            reader.GetString(5),
            reader.GetString(6),
            reader.GetString(7),
            reader.GetString(8),
            reader.GetString(9),
            reader.GetString(10),
            reader.GetString(11),
            reader.GetString(12),
            reader.GetString(13),
            reader.GetString(14),
            reader.GetString(15),
            reader.GetString(16),
            reader.GetString(17),
            reader.GetString(18),
            reader.GetString(19),
            reader.GetString(20),
            reader.GetString(21),
            reader.GetString(22),
            reader.GetString(23),
            reader.IsDBNull(24) ? null : reader.GetString(24),
            reader.IsDBNull(25) ? null : reader.GetString(25),
            reader.IsDBNull(26) ? null : reader.GetString(26),
            reader.GetString(27),
            reader.IsDBNull(28) ? null : reader.GetString(28),
            reader.IsDBNull(29) ? null : reader.GetString(29));
    }

    private async Task<string> WriteDiagnosticSpoolFileAsync(
        string diagnosticId,
        ProjectDiagnosticSpoolCommand entry,
        string createdUtc,
        CancellationToken cancellationToken)
    {
        var root = ResolveDiagnosticSpoolRoot();
        var directory = Path.Combine(root, SanitizePathSegment(entry.AccountId), SanitizePathSegment(entry.ProjectId));
        Directory.CreateDirectory(directory);
        var fileName = $"{SanitizePathSegment(createdUtc).Replace(':', '-')}-{SanitizePathSegment(diagnosticId)}.json";
        var path = Path.Combine(directory, fileName);
        var relativeRef = Path.Combine(
            "logs",
            "phase-a-innernet",
            "diagnostics",
            "projects",
            SanitizePathSegment(entry.AccountId),
            SanitizePathSegment(entry.ProjectId),
            fileName).Replace('\\', '/');

        var payload = new
        {
            schema_version = "project-diagnostic-spool.v1",
            diagnostic_id = diagnosticId,
            account_id = entry.AccountId,
            project_id = entry.ProjectId,
            project_name = entry.ProjectNameSnapshot,
            deletion_event_id = "",
            project_tombstone_id = "",
            run_id = entry.RunId,
            route = entry.RouteId,
            failure_family = entry.FailureFamily,
            severity = entry.Severity,
            triage_status = entry.TriageStatus,
            created_utc = createdUtc,
            source_refs = ParseJsonArray(entry.SourceRefsJson),
            evidence_refs = ParseJsonArray(entry.EvidenceRefsJson),
            redaction_status = entry.RedactionStatus,
            retention_class = entry.RetentionClass,
            cleanup_status = entry.CleanupStatus,
            replacement_evidence_refs = ParseJsonArray(entry.ReplacementEvidenceRefsJson),
            user_safe_summary = RedactDiagnosticText(entry.SafeSummary),
            admin_summary = RedactDiagnosticText(entry.AdminSummary),
            remediation_hint_id = entry.RemediationHintId
        };

        var temporaryPath = $"{path}.{Guid.NewGuid():N}.tmp";
        try
        {
            await File.WriteAllTextAsync(
                temporaryPath,
                JsonSerializer.Serialize(payload, new JsonSerializerOptions { WriteIndented = true }),
                Encoding.UTF8,
                cancellationToken);
            File.Move(temporaryPath, path, overwrite: true);
        }
        finally
        {
            if (File.Exists(temporaryPath))
            {
                File.Delete(temporaryPath);
            }
        }
        return relativeRef;
    }

    private bool DiagnosticSpoolFileExists(string spoolRef, ProjectDiagnosticSpoolCommand entry)
    {
        return File.Exists(ResolveDiagnosticSpoolFilePath(spoolRef, entry));
    }

    private void DeleteDiagnosticSpoolFile(string spoolRef, ProjectDiagnosticSpoolCommand entry)
    {
        var path = ResolveDiagnosticSpoolFilePath(spoolRef, entry);
        if (File.Exists(path))
        {
            File.Delete(path);
        }
    }

    private string ResolveDiagnosticSpoolFilePath(string spoolRef, ProjectDiagnosticSpoolCommand entry)
    {
        return Path.Combine(
            ResolveDiagnosticSpoolRoot(),
            SanitizePathSegment(entry.AccountId),
            SanitizePathSegment(entry.ProjectId),
            Path.GetFileName(spoolRef.Replace('/', Path.DirectorySeparatorChar)));
    }

    private string ResolveDiagnosticSpoolRoot()
    {
        var dataDirectory = Path.GetDirectoryName(_options.MetadataDatabasePath);
        var phaseRoot = string.IsNullOrWhiteSpace(dataDirectory)
            ? Path.Combine(_options.HostedWorkspaceRoot, "..")
            : Directory.GetParent(dataDirectory)?.FullName;
        if (string.IsNullOrWhiteSpace(phaseRoot))
        {
            phaseRoot = Path.Combine(_options.HostedWorkspaceRoot, "..");
        }

        return Path.GetFullPath(Path.Combine(phaseRoot, "diagnostics", "projects"));
    }

    private static string DefaultDiagnosticRetentionClass(string triageStatus, string severity)
    {
        return (triageStatus, severity) switch
        {
            ("unresolved", "P0" or "P1" or "P2") => "unresolved_blocker",
            ("resolved", _) => "resolved_audit",
            ("ignored", _) => "ignored_audit",
            ("backlog", _) => "backlog_audit",
            (_, "info") => "info_ephemeral",
            _ => "unresolved_blocker"
        };
    }

    private static string RedactDiagnosticText(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "";
        }

        var sanitized = value
            .Replace("\\", "/", StringComparison.Ordinal)
            .Replace("Bearer ", "Bearer [redacted] ", StringComparison.OrdinalIgnoreCase);
        if (sanitized.Contains("C:/", StringComparison.OrdinalIgnoreCase))
        {
            sanitized = "[redacted-host-path]";
        }

        foreach (var token in new[] { "sk-", "token=", "password=", "prompt:" })
        {
            if (sanitized.Contains(token, StringComparison.OrdinalIgnoreCase))
            {
                sanitized = sanitized.Replace(token, "[redacted]", StringComparison.OrdinalIgnoreCase);
            }
        }

        return sanitized;
    }

    private static JsonElement ParseJsonArray(string json)
    {
        try
        {
            using var document = JsonDocument.Parse(string.IsNullOrWhiteSpace(json) ? "[]" : json);
            return document.RootElement.ValueKind == JsonValueKind.Array
                ? document.RootElement.Clone()
                : JsonDocument.Parse("[]").RootElement.Clone();
        }
        catch (JsonException)
        {
            using var document = JsonDocument.Parse("[]");
            return document.RootElement.Clone();
        }
    }

    private static string SanitizePathSegment(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "unknown";
        }

        var builder = new StringBuilder(value.Length);
        foreach (var ch in value)
        {
            builder.Append(char.IsLetterOrDigit(ch) || ch is '-' or '_' or '.' ? ch : '_');
        }

        return builder.ToString();
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

    private static async Task<string?> AssignNextAvailableAiCodeMirrorKeyInsideTransactionAsync(
        SqliteConnection connection,
        SqliteTransaction transaction,
        string accountId,
        string now,
        CancellationToken cancellationToken)
    {
        string? keyName;
        await using (var lookup = connection.CreateCommand())
        {
            lookup.Transaction = transaction;
            lookup.CommandText =
                """
                SELECT key_name
                FROM aicodemirror_key_pool
                WHERE account_id IS NULL
                  AND status = 'available'
                  AND credential_imported = 1
                  AND (expires_utc IS NULL OR expires_utc > $now_utc)
                ORDER BY imported_utc ASC, rowid ASC
                LIMIT 1;
                """;
            lookup.Parameters.AddWithValue("$now_utc", now);
            keyName = await lookup.ExecuteScalarAsync(cancellationToken) as string;
        }

        if (string.IsNullOrWhiteSpace(keyName))
        {
            return null;
        }

        await using (var assign = connection.CreateCommand())
        {
            assign.Transaction = transaction;
            assign.CommandText =
                """
                UPDATE aicodemirror_key_pool
                SET account_id = $account_id,
                    status = 'assigned',
                    assigned_utc = $assigned_utc,
                    updated_utc = $updated_utc
                WHERE key_name = $key_name
                  AND account_id IS NULL
                  AND status = 'available';
                """;
            assign.Parameters.AddWithValue("$account_id", accountId);
            assign.Parameters.AddWithValue("$key_name", keyName);
            assign.Parameters.AddWithValue("$assigned_utc", now);
            assign.Parameters.AddWithValue("$updated_utc", now);
            var rows = await assign.ExecuteNonQueryAsync(cancellationToken);
            return rows > 0 ? keyName : null;
        }
    }

    private async Task SyncAdminSecretsAsync(SqliteConnection connection, string accountId, CancellationToken cancellationToken)
    {
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            UPDATE accounts
            SET username = $username,
                password_hash = $password_hash,
                token_hash = $token_hash
            WHERE id = $id
              AND is_admin = 1;
            """;
        command.Parameters.AddWithValue("$id", accountId);
        command.Parameters.AddWithValue("$username", _options.AdminUsername);
        command.Parameters.AddWithValue("$password_hash", (object?)_options.AdminPasswordHash ?? DBNull.Value);
        command.Parameters.AddWithValue("$token_hash", (object?)_options.AdminTokenHash ?? DBNull.Value);
        await command.ExecuteNonQueryAsync(cancellationToken);
    }

    private static string GenerateAccountToken()
    {
        return Convert.ToHexString(RandomNumberGenerator.GetBytes(24)).ToLowerInvariant();
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

    private async Task<AiCodeMirrorKeyPoolEntry?> GetAiCodeMirrorKeyByNameAsync(
        string keyName,
        CancellationToken cancellationToken)
    {
        await using var connection = await OpenConnectionAsync(cancellationToken);
        return await ReadAiCodeMirrorKeyByNameAsync(connection, keyName, null, cancellationToken);
    }

    private static async Task<AiCodeMirrorKeyPoolEntry?> ReadAiCodeMirrorKeyByNameAsync(
        SqliteConnection connection,
        string keyName,
        SqliteTransaction? transaction,
        CancellationToken cancellationToken)
    {
        await using var command = connection.CreateCommand();
        command.Transaction = transaction;
        command.CommandText =
            """
            SELECT id, key_name, account_id, status, notes, valid_days, expires_utc, credential_imported, imported_utc, assigned_utc, updated_utc
            FROM aicodemirror_key_pool
            WHERE key_name = $key_name;
            """;
        command.Parameters.AddWithValue("$key_name", keyName);
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        return await reader.ReadAsync(cancellationToken) ? ReadAiCodeMirrorKey(reader) : null;
    }

    private static AiCodeMirrorKeyPoolEntry ReadAiCodeMirrorKey(SqliteDataReader reader)
    {
        return new AiCodeMirrorKeyPoolEntry(
            reader.GetString(0),
            reader.GetString(1),
            reader.IsDBNull(2) ? null : reader.GetString(2),
            reader.GetString(3),
            reader.IsDBNull(4) ? null : reader.GetString(4),
            reader.IsDBNull(5) ? null : checked((int)reader.GetInt64(5)),
            reader.IsDBNull(6) ? null : reader.GetString(6),
            reader.GetInt64(7) == 1,
            reader.GetString(8),
            reader.IsDBNull(9) ? null : reader.GetString(9),
            reader.GetString(10));
    }

    private static async Task<string> MergeRunLlmCostJsonAsync(
        SqliteConnection connection,
        string runId,
        string llmCostJson,
        CancellationToken cancellationToken)
    {
        await using var lookup = connection.CreateCommand();
        lookup.CommandText = "SELECT llm_cost_json FROM runs WHERE id = $id;";
        lookup.Parameters.AddWithValue("$id", runId);

        var existing = await lookup.ExecuteScalarAsync(cancellationToken) as string;
        if (string.IsNullOrWhiteSpace(existing))
        {
            return llmCostJson;
        }

        if (string.IsNullOrWhiteSpace(llmCostJson))
        {
            return existing;
        }

        try
        {
            using var existingDocument = JsonDocument.Parse(existing);
            using var incomingDocument = JsonDocument.Parse(llmCostJson);
            var merged = MergeLlmCostJson(existingDocument.RootElement, incomingDocument.RootElement);
            return JsonSerializer.Serialize(merged);
        }
        catch (JsonException)
        {
            return llmCostJson;
        }
    }

    private static object MergeLlmCostJson(JsonElement existing, JsonElement incoming)
    {
        var calls = new List<JsonElement>();
        AppendCostCall(calls, existing);
        AppendCostCall(calls, incoming);
        return new { calls = calls.Select(CloneElement).ToArray() };
    }

    private static void AppendCostCall(List<JsonElement> calls, JsonElement element)
    {
        if (element.ValueKind == JsonValueKind.Object && element.TryGetProperty("calls", out var nestedCalls) && nestedCalls.ValueKind == JsonValueKind.Array)
        {
            foreach (var call in nestedCalls.EnumerateArray())
            {
                calls.Add(CloneElement(call));
            }

            return;
        }

        if (element.ValueKind == JsonValueKind.Array)
        {
            foreach (var call in element.EnumerateArray())
            {
                calls.Add(CloneElement(call));
            }

            return;
        }

        calls.Add(CloneElement(element));
    }

    private static JsonElement CloneElement(JsonElement element)
    {
        using var document = JsonDocument.Parse(element.GetRawText());
        return document.RootElement.Clone();
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

    private static async Task<long?> ExecuteScalarLongInsideTransactionAsync(
        SqliteConnection connection,
        SqliteTransaction transaction,
        string sql,
        CancellationToken cancellationToken,
        params (string Name, object Value)[] parameters)
    {
        await using var command = connection.CreateCommand();
        command.Transaction = transaction;
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
