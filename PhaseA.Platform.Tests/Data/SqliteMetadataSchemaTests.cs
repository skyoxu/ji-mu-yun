using FluentAssertions;
using System.Text;
using System.Text.Json;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workflow;
using Xunit;

namespace PhaseA.Platform.Tests.Data;

public sealed class SqliteMetadataSchemaTests
{
    [Fact]
    public async Task InitializeAsync_CreatesExpectedTables_AndIsRepeatable()
    {
        using var database = TempSqliteDatabase.Create();

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);

        var tables = await database.ReadTableNamesAsync();

        tables.Should().Contain([
            "accounts",
            "projects",
            "workspaces",
            "runs",
            "artifacts",
            "approvals",
            "project_limits",
            "runner_locks",
            "account_llm_bindings",
            "aicodemirror_key_pool",
            "project_chat_messages",
            "project_chat_memories",
            "admin_account_audit_events",
            "project_prototype_drafts",
            "project_iteration_sessions",
            "project_iteration_goals",
            "project_iteration_goal_runs",
            "project_route_prompt_evidence_bindings",
            "project_admin_review_queue",
            "project_admin_review_decisions",
            "project_diagnostic_spool",
            "project_delete_tombstones",
            "game_type_maintenance_records"
        ]);
    }

    [Fact]
    public async Task InitializeAsync_CreatesGovernanceIndexesForAdminReadback()
    {
        using var database = TempSqliteDatabase.Create();

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var indexes = await ReadIndexNamesAsync(database.ConnectionString);

        indexes.Should().Contain([
            "ix_project_admin_review_queue_status_created",
            "ix_project_admin_review_queue_project_status",
            "ix_project_admin_review_queue_project_route_requirement_reason",
            "ix_project_admin_review_decisions_entry_version",
            "ix_project_diagnostic_spool_triage_created",
            "ix_project_diagnostic_spool_project_triage",
            "ix_project_diagnostic_spool_diagnostic_id",
            "ix_project_diagnostic_spool_triage_severity_updated",
            "ix_project_diagnostic_spool_account_project_triage",
            "ix_project_diagnostic_spool_deleted_lookup",
            "ix_project_diagnostic_spool_route_family_created",
            "ix_project_diagnostic_spool_retention_cleanup",
            "ix_project_diagnostic_spool_unresolved_scope",
            "ix_project_delete_tombstones_deleted",
            "ix_project_delete_tombstones_tombstone_event",
            "ix_game_type_maintenance_records_status_created"
        ]);
    }

    [Fact]
    public async Task InitializeAsync_UpgradesLegacyAdminReviewQueueWithoutLosingRows()
    {
        using var database = TempSqliteDatabase.Create();
        await using (var connection = new Microsoft.Data.Sqlite.SqliteConnection(database.ConnectionString))
        {
            await connection.OpenAsync();
            await using var command = connection.CreateCommand();
            command.CommandText =
                """
                CREATE TABLE project_admin_review_queue (
                    id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    route_id TEXT NOT NULL,
                    requirement_id TEXT NOT NULL DEFAULT '',
                    severity TEXT NOT NULL,
                    blocking_reason TEXT NOT NULL,
                    source_artifact_path TEXT NOT NULL,
                    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL,
                    decision_status TEXT NOT NULL DEFAULT 'pending',
                    decision_actor_account_id TEXT NULL,
                    decision_reason TEXT NOT NULL DEFAULT '',
                    decision_metadata_json TEXT NOT NULL DEFAULT '{}',
                    decision_version INTEGER NOT NULL DEFAULT 0,
                    created_utc TEXT NOT NULL,
                    updated_utc TEXT NOT NULL,
                    decided_utc TEXT NULL,
                    project_deleted_utc TEXT NULL
                );
                CREATE UNIQUE INDEX ix_project_admin_review_queue_project_route_requirement_reason
                ON project_admin_review_queue(project_id, route_id, requirement_id, blocking_reason);
                INSERT INTO project_admin_review_queue (
                    id, account_id, project_id, route_id, requirement_id, severity, blocking_reason,
                    source_artifact_path, evidence_refs_json, status, created_utc, updated_utc)
                VALUES (
                    'legacy-entry', 'legacy-account', 'legacy-project', 'gdd-requirements', 'REQ-LEGACY', 'P1', 'legacy blocker',
                    'meta/routes/gdd-requirements/latest.json', '[]', 'open', '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z');
                INSERT INTO project_admin_review_queue (
                    id, account_id, project_id, route_id, requirement_id, severity, blocking_reason,
                    source_artifact_path, evidence_refs_json, status, decision_status, created_utc, updated_utc)
                VALUES (
                    'legacy-approved', 'legacy-account', 'legacy-project', 'gdd-requirements', 'REQ-LEGACY', 'P2', 'newer approved reason',
                    'meta/routes/gdd-requirements/latest.json', '[]', 'approved', 'approved', '2026-07-02T00:00:00Z', '2026-07-02T00:00:00Z');
                INSERT INTO project_admin_review_queue (
                    id, account_id, project_id, route_id, requirement_id, severity, blocking_reason,
                    source_artifact_path, evidence_refs_json, status, decision_status, decision_metadata_json, created_utc, updated_utc)
                VALUES (
                    'legacy-expired-deferred', 'legacy-account', 'legacy-project', 'prototype-contract', 'REQ-DEFERRED', 'P2', 'expired deferred blocker',
                    'meta/routes/prototype-contract/latest.json', '[]', 'deferred', 'deferred',
                    '{"deferred_owner":"platform","recheck_trigger":"timer","deferred_until_utc":"2000-01-01T00:00:00Z","affected_routes":["prototype-contract"]}',
                    '2026-07-03T00:00:00Z', '2026-07-03T00:00:00Z');
                INSERT INTO project_admin_review_queue (
                    id, account_id, project_id, route_id, requirement_id, severity, blocking_reason,
                    source_artifact_path, evidence_refs_json, status, decision_status, created_utc, updated_utc)
                VALUES (
                    'legacy-deferred-approved', 'legacy-account', 'legacy-project', 'prototype-contract', 'REQ-DEFERRED', 'P0', 'approved after deferral',
                    'meta/routes/prototype-contract/latest.json', '[]', 'approved', 'approved', '2026-07-04T00:00:00Z', '2026-07-04T00:00:00Z');
                """;
            await command.ExecuteNonQueryAsync();
        }

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);

        await using var verify = new Microsoft.Data.Sqlite.SqliteConnection(database.ConnectionString);
        await verify.OpenAsync();
        var columns = new HashSet<string>(StringComparer.Ordinal);
        await using (var columnCommand = verify.CreateCommand())
        {
            columnCommand.CommandText = "PRAGMA table_info(project_admin_review_queue);";
            await using var reader = await columnCommand.ExecuteReaderAsync();
            while (await reader.ReadAsync())
            {
                columns.Add(reader.GetString(1));
            }
        }

        columns.Should().Contain(["supersedes_entry_id", "superseded_by_entry_id"]);
        (await ScalarLongAsync(verify, "SELECT COUNT(*) FROM project_admin_review_queue WHERE id = 'legacy-entry';"))
            .Should().Be(1);
        (await ScalarStringAsync(verify, "SELECT status FROM project_admin_review_queue WHERE id = 'legacy-entry';"))
            .Should().Be("open");
        (await ScalarStringAsync(verify, "SELECT status FROM project_admin_review_queue WHERE id = 'legacy-approved';"))
            .Should().Be("superseded");
        (await ScalarStringAsync(verify, "SELECT superseded_by_entry_id FROM project_admin_review_queue WHERE id = 'legacy-approved';"))
            .Should().Be("legacy-entry");
        (await ScalarLongAsync(verify, "SELECT COUNT(*) FROM project_admin_review_migration_lineage WHERE predecessor_entry_id = 'legacy-approved' AND successor_entry_id = 'legacy-entry';"))
            .Should().Be(1);
        (await ScalarStringAsync(verify, "SELECT supersedes_entry_id FROM project_admin_review_queue WHERE id = 'legacy-entry';"))
            .Should().Be("legacy-approved");
        (await ScalarStringAsync(verify, "SELECT status FROM project_admin_review_queue WHERE id = 'legacy-expired-deferred';"))
            .Should().Be("deferred");
        (await ScalarStringAsync(verify, "SELECT status FROM project_admin_review_queue WHERE id = 'legacy-deferred-approved';"))
            .Should().Be("superseded");
        (await ScalarStringAsync(verify, "SELECT superseded_by_entry_id FROM project_admin_review_queue WHERE id = 'legacy-deferred-approved';"))
            .Should().Be("legacy-expired-deferred");
        var indexSql = await ScalarStringAsync(
            verify,
            "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = 'ix_project_admin_review_queue_project_route_requirement_reason';");
        indexSql.Should().Contain("WHERE status <> 'superseded'");
    }

    [Fact]
    public async Task InitializeAsync_ClearsOlderDuplicateRequestIdentitiesBeforeCreatingUniqueIndex()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var project = await store.CreateProjectAsync(CreateCommand(accountId, "identity-project", "Identity Game"));
        await store.CreateProjectIterationSessionAsync(
            accountId,
            project.ProjectId!,
            "manual_feedback",
            "First request.",
            "First plan",
            [],
            sessionId: "session-old",
            requestIdentityHash: "duplicate-identity");
        await using (var connection = new Microsoft.Data.Sqlite.SqliteConnection(database.ConnectionString))
        {
            await connection.OpenAsync();
            await using var command = connection.CreateCommand();
            command.CommandText =
                """
                DROP INDEX ix_project_iteration_sessions_request_identity;
                INSERT INTO project_iteration_sessions (
                    id, project_id, account_id, source_kind, source_message, overall_goal, status,
                    current_goal_index, request_identity_hash, created_utc, updated_utc)
                VALUES (
                    'session-new', $project_id, $account_id, 'manual_feedback', 'New request.', 'New plan', 'ready',
                    0, 'duplicate-identity', '2099-01-02T00:00:00Z', '2099-01-02T00:00:00Z');
                """;
            command.Parameters.AddWithValue("$project_id", project.ProjectId!);
            command.Parameters.AddWithValue("$account_id", accountId);
            await command.ExecuteNonQueryAsync();
        }

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);

        await using var verify = new Microsoft.Data.Sqlite.SqliteConnection(database.ConnectionString);
        await verify.OpenAsync();
        (await ScalarLongAsync(verify, "SELECT COUNT(*) FROM project_iteration_sessions WHERE request_identity_hash = 'duplicate-identity';"))
            .Should().Be(1);
        (await ScalarStringAsync(verify, "SELECT id FROM project_iteration_sessions WHERE request_identity_hash = 'duplicate-identity';"))
            .Should().Be("session-new");
    }

    [Fact]
    public async Task DiagnosticSpool_DedupeScopeIsAtomicAcrossStoreInstances()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var firstStore = new PhaseAMetadataStore(database.ConnectionString, options);
        var secondStore = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await firstStore.EnsureSingleAdminAsync();
        var project = await firstStore.CreateProjectAsync(CreateCommand(accountId, "diagnostic-dedupe", "Diagnostic Game"));
        var command = new ProjectDiagnosticSpoolCommand(
            accountId,
            project.ProjectId!,
            "execute-next-goal",
            "plan_hash_mismatch",
            "P1",
            "Plan hash mismatch.",
            "[]",
            DedupeScopeKey: "stable-scope-key");

        var results = await Task.WhenAll(
            firstStore.RecordProjectDiagnosticSpoolEntryAsync(command),
            secondStore.RecordProjectDiagnosticSpoolEntryAsync(command));
        var rows = await firstStore.ListProjectDiagnosticSpoolForAdminAsync(
            new ProjectDiagnosticSpoolQuery("unresolved", accountId, project.ProjectId, "execute-next-goal", "plan_hash_mismatch", "P1", 10));

        results.Select(static row => row.Id).Distinct(StringComparer.Ordinal).Should().ContainSingle();
        rows.Should().ContainSingle();
    }

    [Fact]
    public async Task DiagnosticSpool_DedupeRetryRepairsMissingEvidenceForClaimedScope()
    {
        var root = Path.Combine(Path.GetTempPath(), "phase-a-diagnostic-repair", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(Path.Combine(root, "data"));
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(root, "data", "phase-a-platform.sqlite3")
        });
        var connectionString = new Microsoft.Data.Sqlite.SqliteConnectionStringBuilder
        {
            DataSource = options.MetadataDatabasePath,
            Pooling = false
        }.ToString();
        try
        {
            await SqliteMetadataSchema.InitializeAsync(connectionString);
            var store = new PhaseAMetadataStore(connectionString, options);
            var accountId = await store.EnsureSingleAdminAsync();
            var project = await store.CreateProjectAsync(CreateCommand(accountId, "diagnostic-repair", "Diagnostic Repair"));
            var command = new ProjectDiagnosticSpoolCommand(
                accountId,
                project.ProjectId!,
                "execute-next-goal",
                "source_stale",
                "P1",
                "Source is stale.",
                "[]",
                DedupeScopeKey: "repair-scope-key");
            var first = await store.RecordProjectDiagnosticSpoolEntryAsync(command);
            var fileName = Path.GetFileName(first.SpoolRef.Replace('/', Path.DirectorySeparatorChar));
            var evidencePath = Path.Combine(root, "diagnostics", "projects", accountId, project.ProjectId!, fileName);
            File.Delete(evidencePath);
            await using (var connection = new Microsoft.Data.Sqlite.SqliteConnection(connectionString))
            {
                await connection.OpenAsync();
                await using var update = connection.CreateCommand();
                update.CommandText = "UPDATE project_diagnostic_spool SET spool_ref = '' WHERE id = $id;";
                update.Parameters.AddWithValue("$id", first.Id);
                await update.ExecuteNonQueryAsync();
            }

            var repaired = await store.RecordProjectDiagnosticSpoolEntryAsync(command with
            {
                SafeSummary = "Conflicting retry summary must not replace canonical evidence.",
                EvidenceRefsJson = "[\"conflicting-retry\"]"
            });

            repaired.Id.Should().Be(first.Id);
            repaired.SpoolRef.Should().NotBeNullOrWhiteSpace();
            File.Exists(evidencePath).Should().BeTrue();
            using var evidence = System.Text.Json.JsonDocument.Parse(File.ReadAllText(evidencePath));
            evidence.RootElement.GetProperty("user_safe_summary").GetString().Should().Be("Source is stale.");
            evidence.RootElement.GetProperty("evidence_refs").ToString().Should().NotContain("conflicting-retry");
        }
        finally
        {
            if (Directory.Exists(root))
            {
                Directory.Delete(root, recursive: true);
            }
        }
    }

    [Fact]
    public async Task AdminReviewQueueDecision_IsIdempotentForSamePayloadAndConflictsForDifferentPayload()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var project = await store.CreateProjectAsync(CreateCommand(accountId, "queue-project", "Queue Game"));
        await WriteDecisionEvidenceFilesAsync(store, project.ProjectId!, "meta/reviews/D-1.json", "meta/reviews/D-3.json");
        var entry = await store.UpsertProjectAdminReviewQueueEntryAsync(new ProjectAdminReviewQueueCommand(
            accountId,
            project.ProjectId!,
            "gdd-requirements",
            "REQ-001",
            "P1",
            "requirement conflict",
            "meta/routes/gdd-requirements/latest.json",
            """[{"kind":"sidecar","path":"meta/routes/gdd-requirements/latest.json"}]"""));

        var approved = await store.DecideProjectAdminReviewQueueEntryAsync(
            entry.Id,
            accountId,
            new ProjectAdminReviewDecisionRequest(
                "approved",
                @"accepted Authorization: Bearer abc.def.ghi C:\host private\decision.txt",
                ExpectedDecisionVersion: 0,
                DecisionEvidenceRefs: ["meta/reviews/D-1.json"]));
        var retry = await store.DecideProjectAdminReviewQueueEntryAsync(
            entry.Id,
            accountId,
            new ProjectAdminReviewDecisionRequest(
                "approved",
                @"accepted Authorization: Bearer abc.def.ghi C:\host private\decision.txt",
                ExpectedDecisionVersion: 0,
                DecisionEvidenceRefs: ["meta/reviews/D-1.json"]));
        var replayedProducerPayload = await store.UpsertProjectAdminReviewQueueEntryAsync(new ProjectAdminReviewQueueCommand(
            accountId,
            project.ProjectId!,
            "gdd-requirements",
            "REQ-001",
            "P1",
            "requirement conflict",
            "meta/routes/gdd-requirements/latest.json",
            """[{"kind":"sidecar","path":"meta/routes/gdd-requirements/latest.json"}]"""));
        var conflict = await store.DecideProjectAdminReviewQueueEntryAsync(
            entry.Id,
            accountId,
            new ProjectAdminReviewDecisionRequest(
                "rejected",
                "different decision",
                ExpectedDecisionVersion: 0,
                DecisionEvidenceRefs: ["meta/reviews/D-2.json"]));
        var revised = await store.DecideProjectAdminReviewQueueEntryAsync(
            entry.Id,
            accountId,
            new ProjectAdminReviewDecisionRequest(
                "resolved",
                "follow-up evidence closed the blocker",
                ExpectedDecisionVersion: 1,
                DecisionEvidenceRefs: ["meta/reviews/D-3.json"]));

        approved.Status.Should().Be("updated");
        approved.Entry!.DecisionVersion.Should().Be(1);
        approved.Entry.DecisionReason.Should().NotContain("abc.def.ghi");
        approved.Entry.DecisionReason.Should().NotContain(@"C:\host private");
        approved.Entry.DecisionMetadataJson.Should().Contain("decision_by");
        approved.Entry.DecisionMetadataJson.Should().Contain("decision_role");
        approved.Entry.DecisionMetadataJson.Should().Contain("decision_utc");
        approved.Entry.DecisionMetadataJson.Should().Contain("meta/reviews/D-1.json");
        retry.Status.Should().Be("returned_existing");
        retry.Entry!.DecisionVersion.Should().Be(1);
        replayedProducerPayload.Id.Should().Be(entry.Id);
        replayedProducerPayload.Status.Should().Be("approved");
        conflict.Status.Should().Be("conflict");
        conflict.FailureCode.Should().Be("decision_version_conflict");
        revised.Status.Should().Be("updated");
        revised.Entry!.DecisionVersion.Should().Be(2);
        DateTimeOffset.Parse(revised.Entry.DecidedUtc!).Should().BeAfter(DateTimeOffset.Parse(approved.Entry.DecidedUtc!));
        using (var metadata = System.Text.Json.JsonDocument.Parse(revised.Entry.DecisionMetadataJson))
        {
            metadata.RootElement.GetProperty("decision_utc").GetString().Should().Be(revised.Entry.DecidedUtc);
        }
        await using var connection = new Microsoft.Data.Sqlite.SqliteConnection(database.ConnectionString);
        await connection.OpenAsync();
        (await ScalarLongAsync(connection, $"SELECT COUNT(*) FROM project_admin_review_decisions WHERE entry_id = '{entry.Id}';"))
            .Should().Be(2);
        (await ScalarStringAsync(connection, $"SELECT decision_reason FROM project_admin_review_decisions WHERE entry_id = '{entry.Id}' ORDER BY decision_version LIMIT 1;"))
            .Should().NotContain("abc.def.ghi");
    }

    [Fact]
    public async Task AdminReviewQueueDecision_ConcurrentSamePayloadCreatesOneHistoryVersion()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var project = await store.CreateProjectAsync(CreateCommand(accountId, "queue-concurrency", "Queue Concurrency"));
        await WriteDecisionEvidenceFilesAsync(store, project.ProjectId!, "meta/reviews/concurrent.json");
        var entry = await store.UpsertProjectAdminReviewQueueEntryAsync(new ProjectAdminReviewQueueCommand(
            accountId, project.ProjectId!, "gdd-requirements", "REQ-CONCURRENT", "P1", "concurrent decision",
            "meta/routes/gdd-requirements/latest.json", "[]"));
        var request = new ProjectAdminReviewDecisionRequest(
            "approved",
            "same concurrent payload",
            0,
            DecisionEvidenceRefs: ["meta/reviews/concurrent.json"]);

        var results = await Task.WhenAll(
            store.DecideProjectAdminReviewQueueEntryAsync(entry.Id, accountId, request),
            store.DecideProjectAdminReviewQueueEntryAsync(entry.Id, accountId, request));

        results.Select(result => result.Status).Should().BeEquivalentTo(["updated", "returned_existing"]);
        await using var connection = new Microsoft.Data.Sqlite.SqliteConnection(database.ConnectionString);
        await connection.OpenAsync();
        (await ScalarLongAsync(connection, $"SELECT COUNT(*) FROM project_admin_review_decisions WHERE entry_id = '{entry.Id}';"))
            .Should().Be(1);
        var projectSnapshot = await store.GetProjectSnapshotAsync(project.ProjectId!);
        var sidecarPath = Path.Combine(projectSnapshot!.RepoPath, "meta", "routes", "admin-review-queue", "latest.json");
        using var sidecar = System.Text.Json.JsonDocument.Parse(await File.ReadAllTextAsync(sidecarPath));
        var sidecarText = sidecar.RootElement.ToString();
        sidecarText.Should().Contain("Administrative review is not currently blocking this route.");
        sidecar.RootElement.GetProperty("status_dimension").GetString().Should().Be("route_readback");
        sidecar.RootElement.GetProperty("entry_status_dimension").GetString().Should().Be("admin_review_queue");
        sidecarText.Should().NotContain("decision_version");
        sidecarText.Should().NotContain("decision_reason");
        sidecarText.Should().NotContain("decision_by");
    }

    [Fact]
    public async Task AdminReviewQueueUpsert_ConcurrentDifferentPayloadsSerializeOneCurrentVersion()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var project = await store.CreateProjectAsync(CreateCommand(accountId, "queue-upsert-concurrency", "Queue Upsert Concurrency"));

        var results = await Task.WhenAll(
            store.UpsertProjectAdminReviewQueueEntryAsync(new ProjectAdminReviewQueueCommand(
                accountId, project.ProjectId!, "gdd-requirements", "REQ-CONCURRENT-UPSERT", "P1", "first payload",
                "meta/routes/gdd-requirements/latest.json", "[]")),
            store.UpsertProjectAdminReviewQueueEntryAsync(new ProjectAdminReviewQueueCommand(
                accountId, project.ProjectId!, "gdd-requirements", "REQ-CONCURRENT-UPSERT", "P0", "second payload",
                "meta/routes/gdd-requirements/latest.json", "[]")));

        results.Should().HaveCount(2);
        var rows = await store.ListProjectAdminReviewQueueForAdminAsync(new ProjectAdminReviewQueueQuery(
            Status: "", ProjectId: project.ProjectId, RouteId: "gdd-requirements", Limit: 10));
        rows.Should().HaveCount(2);
        rows.Should().ContainSingle(row => row.Status != "superseded");
        rows.Should().ContainSingle(row => row.Status == "superseded");
        rows.Single(row => row.Status == "superseded").SupersededByEntryId.Should().Be(rows.Single(row => row.Status != "superseded").Id);
    }

    [Fact]
    public async Task AdminReviewQueueDecision_ExpiredDeferredSamePayloadRetryRemainsIdempotent()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var project = await store.CreateProjectAsync(CreateCommand(accountId, "deferred-retry", "Deferred Retry"));
        await WriteDecisionEvidenceFilesAsync(store, project.ProjectId!, "meta/reviews/expiry.json");
        var entry = await store.UpsertProjectAdminReviewQueueEntryAsync(new ProjectAdminReviewQueueCommand(
            accountId, project.ProjectId!, "gdd-requirements", "REQ-DEFERRED", "P1", "deferred retry",
            "meta/routes/gdd-requirements/latest.json", "[]"));
        var request = new ProjectAdminReviewDecisionRequest(
            "deferred", "bounded deferral", 0,
            DeferredOwner: "platform",
            DeferredUntilUtc: DateTimeOffset.UtcNow.AddMilliseconds(750).ToString("O"),
            RecheckTrigger: "timer",
            AffectedRoutes: ["gdd-requirements"],
            DecisionEvidenceRefs: ["meta/reviews/expiry.json"]);

        (await store.DecideProjectAdminReviewQueueEntryAsync(entry.Id, accountId, request)).Status.Should().Be("updated");
        await Task.Delay(1000);
        var retry = await store.DecideProjectAdminReviewQueueEntryAsync(entry.Id, accountId, request);

        retry.Status.Should().Be("returned_existing");
        ProjectAdminReviewQueuePolicy.IsBlocking(retry.Entry!).Should().BeTrue();
    }

    [Fact]
    public async Task AdminReviewQueueDecision_DeferredAcceptsExpiryOrRecheckButRequiresEvidence()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var project = await store.CreateProjectAsync(CreateCommand(accountId, "deferred-or", "Deferred Or"));
        await WriteDecisionEvidenceFilesAsync(store, project.ProjectId!, "meta/reviews/deferred-or.json");
        async Task<ProjectAdminReviewQueueEntry> Entry(string requirementId) =>
            await store.UpsertProjectAdminReviewQueueEntryAsync(new ProjectAdminReviewQueueCommand(
                accountId, project.ProjectId!, "gdd-requirements", requirementId, "P1", requirementId,
                "meta/routes/gdd-requirements/latest.json", "[]"));
        var expiryEntry = await Entry("REQ-EXPIRY");
        var recheckEntry = await Entry("REQ-RECHECK");
        var noEvidenceEntry = await Entry("REQ-NO-EVIDENCE");

        var expiryOnly = await store.DecideProjectAdminReviewQueueEntryAsync(
            expiryEntry.Id,
            accountId,
            new ProjectAdminReviewDecisionRequest(
                "deferred", "expiry only", 0,
                DecisionEvidenceRefs: ["meta/reviews/deferred-or.json"],
                DeferredOwner: "platform",
                DeferredUntilUtc: "2099-01-01T00:00:00Z",
                AffectedRoutes: ["gdd-requirements"]));
        var recheckOnly = await store.DecideProjectAdminReviewQueueEntryAsync(
            recheckEntry.Id,
            accountId,
            new ProjectAdminReviewDecisionRequest(
                "deferred", "recheck only", 0,
                DecisionEvidenceRefs: ["meta/reviews/deferred-or.json"],
                DeferredOwner: "platform",
                RecheckTrigger: "contract regenerated",
                AffectedRoutes: ["gdd-requirements"]));
        var noEvidence = await store.DecideProjectAdminReviewQueueEntryAsync(
            noEvidenceEntry.Id,
            accountId,
            new ProjectAdminReviewDecisionRequest(
                "deferred", "unsupported", 0,
                DeferredOwner: "platform",
                RecheckTrigger: "contract regenerated",
                AffectedRoutes: ["gdd-requirements"]));

        expiryOnly.Status.Should().Be("updated");
        recheckOnly.Status.Should().Be("updated");
        ProjectAdminReviewQueuePolicy.IsBlocking(expiryOnly.Entry!).Should().BeFalse();
        ProjectAdminReviewQueuePolicy.IsBlocking(recheckOnly.Entry!).Should().BeFalse();
        noEvidence.Status.Should().Be("rejected");
        noEvidence.FailureCode.Should().Be("admin_review_decision_evidence_required");
    }

    [Fact]
    public async Task AdminReviewQueueProducerRecheck_ReopensSameDeferredBlockerPayload()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var project = await store.CreateProjectAsync(CreateCommand(accountId, "deferred-recheck", "Deferred Recheck"));
        await WriteDecisionEvidenceFilesAsync(store, project.ProjectId!, "meta/reviews/deferred-recheck.json");
        var command = new ProjectAdminReviewQueueCommand(
            accountId,
            project.ProjectId!,
            "gdd-requirements",
            "REQ-RECHECK-OPEN",
            "P1",
            "same blocker payload",
            "meta/routes/gdd-requirements/latest.json",
            "[]");
        var entry = await store.UpsertProjectAdminReviewQueueEntryAsync(command);
        var deferred = await store.DecideProjectAdminReviewQueueEntryAsync(
            entry.Id,
            accountId,
            new ProjectAdminReviewDecisionRequest(
                "deferred",
                "recheck when requirement map is produced again",
                0,
                DecisionEvidenceRefs: ["meta/reviews/deferred-recheck.json"],
                DeferredOwner: "platform",
                RecheckTrigger: "requirement map producer rerun",
                AffectedRoutes: ["gdd-requirements"]));

        deferred.Status.Should().Be("updated");
        ProjectAdminReviewQueuePolicy.IsBlocking(deferred.Entry!).Should().BeFalse();

        var reopened = await store.UpsertProjectAdminReviewQueueEntryAsync(command);
        var rows = await store.ListProjectAdminReviewQueueForProjectAsync(accountId, project.ProjectId!, "", 0);

        reopened.Id.Should().NotBe(entry.Id);
        reopened.Status.Should().Be("open");
        ProjectAdminReviewQueuePolicy.IsBlocking(reopened).Should().BeTrue();
        rows.Should().ContainSingle(row => row.Id == entry.Id && row.Status == "superseded");
        rows.Should().ContainSingle(row => row.Id == reopened.Id && row.Status == "open");
    }

    [Theory]
    [InlineData("approved")]
    [InlineData("rejected")]
    [InlineData("backlog")]
    [InlineData("resolved")]
    public async Task AdminReviewQueueDecision_AllTerminalDecisionsRequireEvidence(string decisionStatus)
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var project = await store.CreateProjectAsync(CreateCommand(accountId, $"decision-evidence-{decisionStatus}", "Decision Evidence"));
        var entry = await store.UpsertProjectAdminReviewQueueEntryAsync(new ProjectAdminReviewQueueCommand(
            accountId, project.ProjectId!, "gdd-requirements", $"REQ-{decisionStatus.ToUpperInvariant()}", "P1", "evidence required",
            "meta/routes/gdd-requirements/latest.json", "[]"));

        var result = await store.DecideProjectAdminReviewQueueEntryAsync(
            entry.Id,
            accountId,
            new ProjectAdminReviewDecisionRequest(decisionStatus, "decision without evidence", 0));

        result.Status.Should().Be("rejected");
        result.FailureCode.Should().Be("admin_review_decision_evidence_required");
    }

    [Fact]
    public async Task AdminReviewQueueDecision_RejectsUnsafeOrMissingEvidenceRefsAndPersistsStructuredRefs()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var project = await store.CreateProjectAsync(CreateCommand(accountId, "decision-evidence", "Decision Evidence"));
        var entry = await store.UpsertProjectAdminReviewQueueEntryAsync(new ProjectAdminReviewQueueCommand(
            accountId, project.ProjectId!, "gdd-requirements", "REQ-EVIDENCE", "P1", "decision evidence",
            "meta/routes/gdd-requirements/latest.json", "[]"));

        var unsafeRef = await store.DecideProjectAdminReviewQueueEntryAsync(
            entry.Id,
            accountId,
            new ProjectAdminReviewDecisionRequest("approved", "unsafe", 0, ["../escape.json"]));
        var missingRef = await store.DecideProjectAdminReviewQueueEntryAsync(
            entry.Id,
            accountId,
            new ProjectAdminReviewDecisionRequest("approved", "missing", 0, ["meta/reviews/missing.json"]));
        var runId = await store.CreateRunAsync(project.ProjectId!, null, "admin-review-evidence");
        await store.AddArtifactAsync(new ArtifactCreationCommand(
            runId, project.ProjectId!, "admin-review-evidence", "meta/reviews/missing-artifact.json", "Missing artifact"));
        var missingArtifact = (await store.ListArtifactsForRunAsync(runId)).Single();
        var missingArtifactRef = await store.DecideProjectAdminReviewQueueEntryAsync(
            entry.Id,
            accountId,
            new ProjectAdminReviewDecisionRequest("approved", "missing artifact", 0, [$"artifact:{missingArtifact.ArtifactId}"]));
        var projectSnapshot = await store.GetProjectSnapshotAsync(project.ProjectId!);
        var evidenceDirectory = Path.Combine(projectSnapshot!.RepoPath, "meta", "reviews", "directory-only");
        Directory.CreateDirectory(evidenceDirectory);
        var directoryRef = await store.DecideProjectAdminReviewQueueEntryAsync(
            entry.Id,
            accountId,
            new ProjectAdminReviewDecisionRequest("approved", "directory", 0, ["meta/reviews/directory-only"]));
        var outsideEvidence = Path.Combine(Path.GetTempPath(), $"phase-a-outside-evidence-{Guid.NewGuid():N}");
        Directory.CreateDirectory(outsideEvidence);
        File.WriteAllText(Path.Combine(outsideEvidence, "outside.json"), "{}");
        var linkPath = Path.Combine(projectSnapshot.RepoPath, "meta", "reviews", "linked-outside");
        ProjectAdminReviewDecisionResult linkedRef;
        try
        {
            Directory.CreateSymbolicLink(linkPath, outsideEvidence);
            linkedRef = await store.DecideProjectAdminReviewQueueEntryAsync(
                entry.Id,
                accountId,
                new ProjectAdminReviewDecisionRequest("approved", "linked", 0, ["meta/reviews/linked-outside/outside.json"]));
        }
        finally
        {
            Directory.Delete(outsideEvidence, recursive: true);
        }
        await WriteDecisionEvidenceFilesAsync(store, project.ProjectId!, "meta/reviews/present.json");
        var accepted = await store.DecideProjectAdminReviewQueueEntryAsync(
            entry.Id,
            accountId,
            new ProjectAdminReviewDecisionRequest("approved", "present", 0, ["meta/reviews/present.json"]));

        unsafeRef.Status.Should().Be("rejected");
        unsafeRef.FailureCode.Should().Be("admin_review_decision_evidence_ref_invalid");
        missingRef.Status.Should().Be("rejected");
        missingRef.FailureCode.Should().Be("admin_review_decision_evidence_ref_not_found");
        missingArtifactRef.FailureCode.Should().Be("admin_review_decision_evidence_ref_not_found");
        directoryRef.FailureCode.Should().Be("admin_review_decision_evidence_ref_not_found");
        linkedRef.FailureCode.Should().Be("admin_review_decision_evidence_ref_not_found");
        accepted.Status.Should().Be("updated");
        accepted.Entry!.DecisionMetadataJson.Should().Contain("\"kind\":\"sidecar\"");
        accepted.Entry.DecisionMetadataJson.Should().Contain("meta/reviews/present.json");
    }

    [Fact]
    public async Task AdminReviewQueue_RejectsUnboundedStatusAndSeverityValues()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var project = await store.CreateProjectAsync(CreateCommand(accountId, "queue-vocabulary", "Queue Vocabulary"));

        Func<Task> invalidStatus = () => store.UpsertProjectAdminReviewQueueEntryAsync(new ProjectAdminReviewQueueCommand(
            accountId, project.ProjectId!, "gdd-requirements", "REQ-STATUS", "P1", "invalid status",
            "meta/routes/gdd-requirements/latest.json", "[]", "looks_complete"));
        Func<Task> invalidSeverity = () => store.UpsertProjectAdminReviewQueueEntryAsync(new ProjectAdminReviewQueueCommand(
            accountId, project.ProjectId!, "gdd-requirements", "REQ-SEVERITY", "critical", "invalid severity",
            "meta/routes/gdd-requirements/latest.json", "[]"));

        await invalidStatus.Should().ThrowAsync<ArgumentOutOfRangeException>()
            .WithMessage("*admin_review_queue_status_invalid*");
        await invalidSeverity.Should().ThrowAsync<ArgumentOutOfRangeException>()
            .WithMessage("*admin_review_queue_severity_invalid*");
    }

    [Theory]
    [InlineData("not-json")]
    [InlineData("[\"legacy-string\"]")]
    [InlineData("[{\"kind\":\"sidecar\",\"path\":\"../escape.json\"}]")]
    [InlineData("[{\"kind\":\"sidecar\",\"path\":\"C:\\\\host\\\\escape.json\"}]")]
    [InlineData("[{\"kind\":\"unknown\",\"path\":\"meta/evidence.json\"}]")]
    public async Task AdminReviewQueue_RejectsMalformedOrUnsafeEvidenceRefs(string evidenceRefsJson)
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var project = await store.CreateProjectAsync(CreateCommand(accountId, "unsafe-evidence", "Unsafe Evidence"));

        Func<Task> action = () => store.UpsertProjectAdminReviewQueueEntryAsync(new ProjectAdminReviewQueueCommand(
            accountId, project.ProjectId!, "gdd-requirements", "REQ-UNSAFE", "P1", "unsafe evidence",
            "meta/routes/gdd-requirements/latest.json", evidenceRefsJson));

        await action.Should().ThrowAsync<ArgumentException>().WithMessage("*admin_review_evidence_ref*");
    }

    [Fact]
    public async Task AdminReviewQueue_RegenerationSupersedesHistoryAndSupportsFiltersDeferredValidationAndSidecar()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var createCommand = CreateCommand(accountId, "queue-history", "Queue History");
        var project = await store.CreateProjectAsync(createCommand);
        await WriteDecisionEvidenceFilesAsync(store, project.ProjectId!, "meta/reviews/first.json", "meta/reviews/deferred.json");
        var first = await store.UpsertProjectAdminReviewQueueEntryAsync(new ProjectAdminReviewQueueCommand(
            accountId,
            project.ProjectId!,
            "gdd-requirements",
            "REQ-002",
            "P1",
            "stale requirement map",
            @"C:\host\secret\gdd-requirements\latest.json",
            """[{"kind":"sidecar","path":"meta/routes/gdd-requirements/v1.json","token":"Authorization: Bearer abc.def.ghi"}]"""));
        var approved = await store.DecideProjectAdminReviewQueueEntryAsync(
            first.Id,
            accountId,
            new ProjectAdminReviewDecisionRequest(
                "approved",
                "first evidence accepted",
                ExpectedDecisionVersion: 0,
                DecisionEvidenceRefs: ["meta/reviews/first.json"]));

        var regenerated = await store.UpsertProjectAdminReviewQueueEntryAsync(new ProjectAdminReviewQueueCommand(
            accountId,
            project.ProjectId!,
            "gdd-requirements",
            "REQ-002",
            "P0",
            "stale requirement map",
            @"C:\host\secret\gdd-requirements\latest.json",
            """[{"kind":"sidecar","path":"meta/routes/gdd-requirements/v2.json","apiKey":"sk-abcdefghijklmnop"}]"""));
        var supersededDecision = await store.DecideProjectAdminReviewQueueEntryAsync(
            first.Id,
            accountId,
            new ProjectAdminReviewDecisionRequest(
                "resolved",
                "must not rewrite superseded history",
                ExpectedDecisionVersion: 1));
        var invalidDeferred = await store.DecideProjectAdminReviewQueueEntryAsync(
            regenerated.Id,
            accountId,
            new ProjectAdminReviewDecisionRequest(
                "deferred",
                "missing expiry and route ownership",
                ExpectedDecisionVersion: 0,
                DeferredOwner: "platform"));
        var expiredDeferred = await store.DecideProjectAdminReviewQueueEntryAsync(
            regenerated.Id,
            accountId,
            new ProjectAdminReviewDecisionRequest(
                "deferred",
                "expired deferral",
                ExpectedDecisionVersion: 0,
                DeferredOwner: "platform",
                DeferredUntilUtc: "2000-01-01T00:00:00Z",
                RecheckTrigger: "route contract regenerated",
                AffectedRoutes: ["gdd-requirements"]));
        var unrelatedDeferred = await store.DecideProjectAdminReviewQueueEntryAsync(
            regenerated.Id,
            accountId,
            new ProjectAdminReviewDecisionRequest(
                "deferred",
                "unrelated route deferral",
                ExpectedDecisionVersion: 0,
                DeferredOwner: "platform",
                DeferredUntilUtc: "2099-01-01T00:00:00Z",
                RecheckTrigger: "route contract regenerated",
                AffectedRoutes: ["prototype-contract"]));
        var deferred = await store.DecideProjectAdminReviewQueueEntryAsync(
            regenerated.Id,
            accountId,
            new ProjectAdminReviewDecisionRequest(
                "deferred",
                "scheduled contract refresh",
                ExpectedDecisionVersion: 0,
                DecisionEvidenceRefs: ["meta/reviews/deferred.json"],
                DeferredOwner: "platform",
                DeferredUntilUtc: "2099-01-01T00:00:00Z",
                RecheckTrigger: "route contract regenerated",
                AffectedRoutes: ["gdd-requirements"]));

        var allRows = await store.ListProjectAdminReviewQueueForAdminAsync(
            new ProjectAdminReviewQueueQuery(Status: "", ProjectId: project.ProjectId, RouteId: "gdd-requirements", Limit: 10));
        var filtered = await store.ListProjectAdminReviewQueueForAdminAsync(
            new ProjectAdminReviewQueueQuery(Status: "deferred", ProjectId: project.ProjectId, RouteId: "gdd-requirements", Severity: "P0", Limit: 10));
        var tooOld = await store.ListProjectAdminReviewQueueForAdminAsync(
            new ProjectAdminReviewQueueQuery(Status: "", ProjectId: project.ProjectId, MinimumAgeMinutes: 60, Limit: 10));

        approved.Status.Should().Be("updated");
        supersededDecision.Status.Should().Be("conflict");
        supersededDecision.FailureCode.Should().Be("admin_review_entry_superseded");
        invalidDeferred.Status.Should().Be("rejected");
        invalidDeferred.FailureCode.Should().Be("admin_review_deferred_metadata_invalid");
        expiredDeferred.FailureCode.Should().Be("admin_review_deferred_metadata_invalid");
        unrelatedDeferred.FailureCode.Should().Be("admin_review_deferred_metadata_invalid");
        deferred.Status.Should().Be("updated");
        allRows.Should().HaveCount(2);
        allRows.Should().Contain(row => row.Id == first.Id && row.Status == "superseded" && row.SupersededByEntryId == regenerated.Id);
        allRows.Should().Contain(row => row.Id == regenerated.Id && row.SupersedesEntryId == first.Id && row.Status == "deferred");
        allRows.Should().OnlyContain(row =>
            !row.SourceArtifactPath.Contains(@"C:\host\secret", StringComparison.Ordinal) &&
            !row.EvidenceRefsJson.Contains("abc.def.ghi", StringComparison.Ordinal) &&
            !row.EvidenceRefsJson.Contains("sk-abcdefghijklmnop", StringComparison.Ordinal));
        filtered.Should().ContainSingle(row => row.Id == regenerated.Id);
        tooOld.Should().BeEmpty();

        var sidecarPath = Path.Combine(createCommand.RepoPath, "meta", "routes", "admin-review-queue", "latest.json");
        File.Exists(sidecarPath).Should().BeTrue();
        using var sidecar = System.Text.Json.JsonDocument.Parse(File.ReadAllText(sidecarPath));
        sidecar.RootElement.GetProperty("entries").GetArrayLength().Should().Be(2);
        sidecar.RootElement.GetProperty("status").GetString().Should().Be("unknown");
        sidecar.RootElement.GetProperty("status_authority").GetString().Should().Be("metadata_db_live");
        sidecar.RootElement.GetProperty("live_recheck_required").GetBoolean().Should().BeTrue();
        var sidecarText = sidecar.RootElement.ToString();
        sidecarText.Should().Contain("Deferred review status requires a live metadata recheck.");
        sidecar.RootElement.GetProperty("entries").EnumerateArray()
            .Single(item => item.GetProperty("status").GetString() == "deferred")
            .GetProperty("is_blocking").ValueKind.Should().Be(JsonValueKind.Null);
        sidecarText.Should().NotContain(first.Id);
        sidecarText.Should().NotContain(regenerated.Id);
        sidecarText.Should().NotContain("deferred_owner");
        sidecarText.Should().NotContain("blocking_reason");
    }

    [Fact]
    public async Task AdminAccountAudit_PersistenceRedactsSecretsAndHostPaths()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        await store.RecordAdminAccountAuditEventAsync(
            accountId,
            "redaction_probe",
            null,
            new
            {
                authorization = "Bearer abc.def.ghi",
                api_key = "sk-abcdefghijklmnop",
                evidence_path = @"C:\host\private\audit.json"
            });

        var item = (await store.ListAdminAccountAuditEventsAsync()).Single(entry => entry.Action == "redaction_probe");
        item.MetadataJson.Should().NotContain("abc.def.ghi");
        item.MetadataJson.Should().NotContain("sk-abcdefghijklmnop");
        item.MetadataJson.Should().NotContain(@"C:\host\private");
        item.MetadataJson.Should().Contain("[redacted-host-path]");
    }

    [Fact]
    public async Task DeleteProjectAsync_PreservesGovernanceRecordsAndWritesTombstone()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var project = await store.CreateProjectAsync(CreateCommand(accountId, "deleted-project", "Deleted Game"));
        await store.UpsertProjectAdminReviewQueueEntryAsync(new ProjectAdminReviewQueueCommand(
            accountId,
            project.ProjectId!,
            "prototype-contract",
            "REQ-002",
            "P0",
            "admin review blocked",
            "routes/prototype-contract/latest.json",
            """[{"kind":"db_row","path":"project_admin_review_queue"}]"""));
        await store.RecordProjectDiagnosticSpoolEntryAsync(new ProjectDiagnosticSpoolCommand(
            accountId,
            project.ProjectId!,
            "ui-wiring",
            "missing_ui_surface",
            "P1",
            "UI closure surface is missing.",
            """[{"kind":"validator","path":"meta/routes/ui-wiring/latest.json"}]""",
            ProjectNameSnapshot: "Deleted Game",
            SourceRefsJson: """[{"kind":"sidecar","path":"meta/routes/ui-wiring/latest.json"}]""",
            RemediationHintId: "missing_ui_surface"));

        await store.DeleteProjectAsync(project.ProjectId!);

        var queue = await store.ListProjectAdminReviewQueueForAdminAsync();
        var diagnostics = await store.ListProjectDiagnosticSpoolForAdminAsync("");
        var tombstones = await store.ListProjectDeleteTombstonesForAdminAsync();

        queue.Should().ContainSingle(entry => entry.ProjectId == project.ProjectId && entry.ProjectDeletedUtc != null);
        diagnostics.Where(entry => entry.ProjectId == project.ProjectId && entry.ProjectDeletedUtc != null)
            .Should()
            .HaveCount(2);
        tombstones.Should().ContainSingle(tombstone =>
            tombstone.ProjectId == project.ProjectId &&
            !string.IsNullOrWhiteSpace(tombstone.ProjectTombstoneId) &&
            !string.IsNullOrWhiteSpace(tombstone.DeletionEventId) &&
            tombstone.UnresolvedAdminReviewCount == 1 &&
            tombstone.UnresolvedDiagnosticCount == 1);
        diagnostics.Should().OnlyContain(entry =>
            entry.ProjectTombstoneId == tombstones[0].ProjectTombstoneId &&
            entry.DeletionEventId == tombstones[0].DeletionEventId);
        diagnostics.Should().Contain(entry => entry.RouteId == "project-delete" && entry.FailureFamily == "workspace_delete_failed");
    }

    [Fact]
    public async Task DeleteProjectAsync_CountsMalformedDeferredAdminReviewEntriesAsUnresolved()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var project = await store.CreateProjectAsync(CreateCommand(accountId, "deleted-malformed-deferred", "Deleted Deferred"));
        var malformedMetadata = new[]
        {
            """{"deferred_owner":"platform","recheck_trigger":"timer","deferred_until_utc":"not-a-date","affected_routes":["route-a"]}""",
            """{"deferred_owner":"platform","recheck_trigger":"timer","deferred_until_utc":"2099-01-01T00:00:00Z","affected_routes":["other-route"]}""",
            """{"deferred_until_utc":"2099-01-01T00:00:00Z","affected_routes":["route-c"]}"""
        };

        await using (var connection = new Microsoft.Data.Sqlite.SqliteConnection(database.ConnectionString))
        {
            await connection.OpenAsync();
            for (var index = 0; index < malformedMetadata.Length; index++)
            {
                var routeId = $"route-{(char)('a' + index)}";
                var entry = await store.UpsertProjectAdminReviewQueueEntryAsync(new ProjectAdminReviewQueueCommand(
                    accountId, project.ProjectId!, routeId, $"REQ-{index}", "P1", $"malformed deferred {index}",
                    $"meta/routes/{routeId}/latest.json", "[]"));
                await using var update = connection.CreateCommand();
                update.CommandText = "UPDATE project_admin_review_queue SET status = 'deferred', decision_status = 'deferred', decision_metadata_json = $metadata WHERE id = $id;";
                update.Parameters.AddWithValue("$metadata", malformedMetadata[index]);
                update.Parameters.AddWithValue("$id", entry.Id);
                await update.ExecuteNonQueryAsync();
            }
        }

        await store.DeleteProjectAsync(project.ProjectId!);

        (await store.ListProjectDeleteTombstonesForAdminAsync()).Should().ContainSingle(tombstone =>
            tombstone.ProjectId == project.ProjectId && tombstone.UnresolvedAdminReviewCount == 3);
    }

    [Fact]
    public async Task DiagnosticSpool_WritesOutsideWorkspace_AndSupportsAdminTriageWithoutRewritingHistory()
    {
        var root = Path.Combine(Path.GetTempPath(), "phase-a-diagnostic-test", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        var metadataPath = Path.Combine(root, "data", "phase-a-platform.sqlite3");
        Directory.CreateDirectory(Path.GetDirectoryName(metadataPath)!);
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_METADATA_DB_PATH"] = metadataPath,
            // ADR-0061: this fixture creates its project below the OS temporary root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });
        var connectionString = new Microsoft.Data.Sqlite.SqliteConnectionStringBuilder
        {
            DataSource = metadataPath,
            Pooling = false
        }.ToString();

        await SqliteMetadataSchema.InitializeAsync(connectionString);
        var store = new PhaseAMetadataStore(connectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var project = await store.CreateProjectAsync(CreateCommand(accountId, "diagnostic-project", "Diagnostic Game"));
        var projectSnapshot = await store.GetProjectSnapshotAsync(project.ProjectId!);

        var entry = await store.RecordProjectDiagnosticSpoolEntryAsync(new ProjectDiagnosticSpoolCommand(
            accountId,
            project.ProjectId!,
            "preview-package",
            "preview_blank",
            "P1",
            "C:/secret/path prompt: sk-test should be redacted.",
            """[{"kind":"screenshot","path":"artifacts/preview.png"}]""",
            ProjectNameSnapshot: "Diagnostic Game",
            RunId: "run-one",
            SourceRefsJson: """[{"kind":"source_hash","path":"routes/prototype-contract/latest.json"}]""",
            AdminSummary: "C:/secret/admin/path token=value",
            RemediationHintId: "preview_blank"));

        entry.DiagnosticId.Should().Be(entry.Id);
        entry.SpoolRef.Should().StartWith("logs/phase-a-innernet/diagnostics/projects/");
        entry.SpoolRef.Should().NotContain(projectSnapshot!.RepoPath.Replace('\\', '/'));
        entry.UserSafeSummary.Should().NotContain("C:/secret");
        entry.UserSafeSummary.Should().NotContain("sk-test");
        var spoolFileName = Path.GetFileName(entry.SpoolRef.Replace('/', Path.DirectorySeparatorChar));
        File.Exists(Path.Combine(root, "diagnostics", "projects", accountId, project.ProjectId!, spoolFileName)).Should().BeTrue();

        var filtered = await store.ListProjectDiagnosticSpoolForAdminAsync(new ProjectDiagnosticSpoolQuery(
            "unresolved",
            accountId,
            project.ProjectId,
            "preview-package",
            "preview_blank",
            "P1"));
        filtered.Should().ContainSingle(item => item.DiagnosticId == entry.DiagnosticId);
        (await store.CountUnresolvedBlockingDiagnosticsAsync(accountId, project.ProjectId!)).Should().Be(1);

        var decided = await store.DecideProjectDiagnosticSpoolEntryAsync(
            entry.DiagnosticId,
            accountId,
            "resolved",
            "Fixed through rebuilt preview.",
            """[{"kind":"screenshot","path":"artifacts/preview-fixed.png"}]""");

        decided.Status.Should().Be("updated");
        decided.Entry!.FailureFamily.Should().Be("preview_blank");
        decided.Entry.SpoolRef.Should().Be(entry.SpoolRef);
        decided.Entry.TriageStatus.Should().Be("resolved");
        decided.Entry.RetentionClass.Should().Be("resolved_audit");
        decided.Entry.TriageDecisionBy.Should().Be(accountId);
        (await store.CountUnresolvedBlockingDiagnosticsAsync(accountId, project.ProjectId!)).Should().Be(0);
    }

    [Fact]
    public async Task DiagnosticSpool_UserReadback_IsScopedToCurrentAccount()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var owner = await store.CreateUserAccountAsync("diagnostic-owner", 1);
        var other = await store.CreateUserAccountAsync("diagnostic-other", 1);
        var project = await store.CreateProjectAsync(CreateCommand(owner.AccountId, "owned-diagnostic", "Owned Game"));
        await store.RecordProjectDiagnosticSpoolEntryAsync(new ProjectDiagnosticSpoolCommand(
            owner.AccountId,
            project.ProjectId!,
            "execute-next-goal",
            "contract_stale",
            "P1",
            "Contract is stale.",
            "[]"));

        var ownerRows = await store.ListProjectDiagnosticSpoolForAccountAsync(owner.AccountId, project.ProjectId!);
        var otherRows = await store.ListProjectDiagnosticSpoolForAccountAsync(other.AccountId, project.ProjectId!);

        ownerRows.Should().ContainSingle(row => row.FailureFamily == "contract_stale");
        otherRows.Should().BeEmpty();
    }

    [Fact]
    public async Task InitializeAsync_MigratesLegacyProjectsBeforeCreatingLastActivityIndexesAndTriggers()
    {
        using var database = TempSqliteDatabase.Create();
        await CreateLegacyDatabaseWithoutProjectLastActivityAsync(database.ConnectionString);

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);

        await using var connection = new Microsoft.Data.Sqlite.SqliteConnection(database.ConnectionString);
        await connection.OpenAsync();
        var columns = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        await using (var command = connection.CreateCommand())
        {
            command.CommandText = "PRAGMA table_info(projects);";
            await using var reader = await command.ExecuteReaderAsync();
            while (await reader.ReadAsync())
            {
                columns.Add(reader.GetString(1));
            }
        }

        columns.Should().Contain("last_activity_utc");
        var lastActivityUtc = await ScalarStringAsync(connection, "SELECT last_activity_utc FROM projects WHERE id = 'legacy-project';");
        var lastActivityIndexCount = await ScalarLongAsync(connection, "SELECT COUNT(*) FROM sqlite_master WHERE type = 'index' AND name = 'ix_projects_account_last_activity';");
        var lastActivityTriggerCount = await ScalarLongAsync(connection, "SELECT COUNT(*) FROM sqlite_master WHERE type = 'trigger' AND name LIKE '%last_activity%';");

        lastActivityUtc.Should().Be("2099-01-02T00:00:00.0000000Z");
        lastActivityIndexCount.Should().Be(1);
        lastActivityTriggerCount.Should().BeGreaterThan(0);
    }

    [Fact]
    public async Task InitializeAsync_MigratesLegacyGameTypeMatchFailureTableToRecordsShape()
    {
        using var database = TempSqliteDatabase.Create();
        await using (var connection = new Microsoft.Data.Sqlite.SqliteConnection(database.ConnectionString))
        {
            await connection.OpenAsync();
            await using var command = connection.CreateCommand();
            command.CommandText =
                """
                CREATE TABLE project_game_type_match_failures (
                    id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    project_name TEXT NOT NULL,
                    game_name TEXT NOT NULL,
                    game_type_source TEXT NOT NULL,
                    match_status TEXT NOT NULL,
                    status_reason TEXT NOT NULL,
                    reference_query TEXT NOT NULL,
                    normalized_genre_tags_json TEXT NOT NULL DEFAULT '[]',
                    candidate_scores_json TEXT NOT NULL DEFAULT '[]',
                    missing_guide_path TEXT NOT NULL DEFAULT '',
                    created_utc TEXT NOT NULL
                );
                """;
            await command.ExecuteNonQueryAsync();
        }

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        await store.RecordProjectGameTypeMatchFailureAsync(new ProjectGameTypeMatchFailureCommand(
            "account-one",
            "project-one",
            "Project One",
            "Game One",
            "manual",
            "matched",
            "matched_by_genre_tags",
            "manual",
            """["deckbuilding"]""",
            """[]""",
            "",
            "card-game",
            "docs/game-type-guides/card-game.md",
            "646570",
            "Slay the Spire",
            "Slay the Spire",
            """["manual","Slay the Spire"]"""));

        var records = await store.ListProjectGameTypeMatchRecordsForAdminAsync(10);

        records.Should().ContainSingle();
        records[0].MatchedGameTypeId.Should().Be("card-game");
        records[0].MatchedGuidePath.Should().Be("docs/game-type-guides/card-game.md");
        records[0].SteamAppId.Should().Be("646570");
        records[0].SteamName.Should().Be("Slay the Spire");
        records[0].SteamResolvedQuery.Should().Be("Slay the Spire");
        records[0].SteamAttemptedQueriesJson.Should().Contain("Slay the Spire");
    }

    [Fact]
    public async Task EnsureSingleAdminAsync_BootstrapsAdminWithDefaultProjectLimit()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);

        var accountId = await store.EnsureSingleAdminAsync();
        var repeatedAccountId = await store.EnsureSingleAdminAsync();
        var projectLimit = await store.GetProjectLimitAsync(accountId);

        repeatedAccountId.Should().Be(accountId);
        projectLimit.Should().Be(2);
    }

    [Fact]
    public async Task CreateUserAccountAsync_StoresTokenHashAndProjectLimit()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);

        var result = await store.CreateUserAccountAsync("phaseb-user", 1);
        var resolved = await store.ResolveAccountByTokenHashAsync(PhaseAAuth.HashTokenForStorage(result.Token));
        var projectLimit = await store.GetProjectLimitAsync(result.AccountId);

        resolved.Should().NotBeNull();
        resolved!.AccountId.Should().Be(result.AccountId);
        resolved.Username.Should().Be("phaseb-user");
        resolved.IsAdmin.Should().BeFalse();
        resolved.IsDisabled.Should().BeFalse();
        projectLimit.Should().Be(1);
    }

    [Fact]
    public async Task AiCodeMirrorKeyPool_ImportsAndAssignsKeysToAccounts()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var first = await store.CreateUserAccountAsync("key-user-one", 1);
        var second = await store.CreateUserAccountAsync("key-user-two", 1);
        await store.UpsertAiCodeMirrorKeyAsync(new AiCodeMirrorKeyImportCommand("upstream-key-one", CredentialImported: true));
        await store.UpsertAiCodeMirrorKeyAsync(new AiCodeMirrorKeyImportCommand("upstream-key-two", CredentialImported: true));

        var assigned = await store.AssignAiCodeMirrorKeyToAccountAsync("upstream-key-one", first.AccountId);
        var conflict = await store.AssignAiCodeMirrorKeyToAccountAsync("upstream-key-one", second.AccountId);
        var reassigned = await store.AssignAiCodeMirrorKeyToAccountAsync("upstream-key-two", first.AccountId);
        var keys = await store.ListAiCodeMirrorKeysAsync();

        assigned.Succeeded.Should().BeTrue();
        assigned.Entry!.AccountId.Should().Be(first.AccountId);
        conflict.Succeeded.Should().BeFalse();
        conflict.FailureCode.Should().Be("aicodemirror_key_already_assigned");
        reassigned.Succeeded.Should().BeTrue();
        reassigned.Entry!.KeyName.Should().Be("upstream-key-two");
        keys.Should().Contain(item => item.KeyName == "upstream-key-one" && item.AccountId == null && item.Status == "available");
        keys.Should().Contain(item => item.KeyName == "upstream-key-two" && item.AccountId == first.AccountId && item.Status == "assigned");
    }

    [Fact]
    public async Task AiCodeMirrorKeyPool_ImportedApiKeyCreatesIsolatedCodexHome()
    {
        using var database = TempSqliteDatabase.Create();
        var codexHomeRoot = Path.Combine(Path.GetTempPath(), "phasea-test-codex-home", Guid.NewGuid().ToString("N"));
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["AICODEMIRROR_CODEX_HOME_ROOT"] = codexHomeRoot
        });

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var user = await store.CreateUserAccountAsync("key-user-runtime", 1);
        var keyPool = new AiCodeMirrorKeyPoolService(store, options);

        var imported = await keyPool.ImportAsync(new AiCodeMirrorKeyImportRequest(
            KeyName: "runtime-key-one",
            ApiKey: "sk-test-runtime-secret",
            Notes: "runtime credential"));
        var assigned = await keyPool.AssignAsync(new AiCodeMirrorKeyAssignRequest(user.AccountId, "runtime-key-one"));
        var credential = await keyPool.ResolveRuntimeCredentialForAccountAsync(user.AccountId);

        imported.Should().NotBeNull();
        assigned.Succeeded.Should().BeTrue();
        credential.Ready.Should().BeTrue();
        credential.BillingKeyName.Should().Be("runtime-key-one");
        credential.CodexHomePath.Should().NotBeNullOrWhiteSpace();
        File.Exists(Path.Combine(credential.CodexHomePath!, "auth.json")).Should().BeTrue();
        File.Exists(Path.Combine(credential.CodexHomePath!, "config.toml")).Should().BeTrue();
        (await store.ListAiCodeMirrorKeysAsync()).Should().OnlyContain(item => !item.ToString()!.Contains("sk-test-runtime-secret", StringComparison.Ordinal));
    }

    [Fact]
    public async Task CreateUserAccountAsync_WhenRequired_AssignsNextAvailableAiCodeMirrorKey()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        await store.UpsertAiCodeMirrorKeyAsync(new AiCodeMirrorKeyImportCommand("first-key", CredentialImported: true));
        await store.UpsertAiCodeMirrorKeyAsync(new AiCodeMirrorKeyImportCommand("second-key", CredentialImported: true));

        var user = await store.CreateUserAccountAsync("auto-key-user", 1, validDays: 7, spendLimitCny: 12.5m, requireAiCodeMirrorKey: true);
        var keys = await store.ListAiCodeMirrorKeysAsync();
        var users = await store.ListAccountsAsync();

        user.AiCodeMirrorKeyName.Should().Be("first-key");
        user.ValidUntilUtc.Should().NotBeNullOrWhiteSpace();
        user.SpendLimitCny.Should().Be(12.5m);
        keys.Should().Contain(item => item.KeyName == "first-key" && item.AccountId == user.AccountId && item.Status == "assigned");
        users.Should().Contain(item => item.AccountId == user.AccountId && item.AiCodeMirrorKeyName == "first-key" && item.SpendLimitCny == 12.5m);
    }

    [Fact]
    public async Task ProjectBelongsToAccountAsync_ReturnsFalseForOtherAccounts()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var owner = await store.EnsureSingleAdminAsync();
        var other = await store.CreateUserAccountAsync("other-user", 1);
        var project = await store.CreateProjectAsync(CreateCommand(owner, "project-one", "Game One"));

        (await store.ProjectBelongsToAccountAsync(owner, project.ProjectId!)).Should().BeTrue();
        (await store.ProjectBelongsToAccountAsync(other.AccountId, project.ProjectId!)).Should().BeFalse();
    }

    [Fact]
    public async Task ListAccountsAsync_ReturnsProjectCountsAndLimits()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var admin = await store.EnsureSingleAdminAsync();
        var user = await store.CreateUserAccountAsync("listed-user", 1);
        await store.CreateProjectAsync(CreateCommand(user.AccountId, "project-one", "Game One"));

        var accounts = await store.ListAccountsAsync();

        accounts.Should().Contain(account => account.AccountId == admin && account.IsAdmin);
        accounts.Should().Contain(account =>
            account.AccountId == user.AccountId &&
            account.Username == "listed-user" &&
            !account.IsAdmin &&
            !account.IsDisabled &&
            account.ProjectLimit == 1 &&
            account.ProjectCount == 1);
    }

    [Fact]
    public async Task SetUserDisabledAsync_BlocksTokenResolution()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var user = await store.CreateUserAccountAsync("disabled-user", 1);
        var tokenHash = PhaseAAuth.HashTokenForStorage(user.Token);

        (await store.SetUserDisabledAsync(user.AccountId, true)).Should().BeTrue();
        (await store.ResolveAccountByTokenHashAsync(tokenHash)).Should().BeNull();

        (await store.SetUserDisabledAsync(user.AccountId, false)).Should().BeTrue();
        (await store.ResolveAccountByTokenHashAsync(tokenHash)).Should().NotBeNull();
    }

    [Fact]
    public async Task RotateUserTokenAsync_InvalidatesPreviousToken()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var user = await store.CreateUserAccountAsync("rotate-user", 1);
        var oldHash = PhaseAAuth.HashTokenForStorage(user.Token);

        var rotated = await store.RotateUserTokenAsync(user.AccountId);

        rotated.Should().NotBeNull();
        rotated!.Token.Should().NotBe(user.Token);
        (await store.ResolveAccountByTokenHashAsync(oldHash)).Should().BeNull();
        (await store.ResolveAccountByTokenHashAsync(PhaseAAuth.HashTokenForStorage(rotated.Token))).Should().NotBeNull();
    }

    [Fact]
    public async Task AdminAccountAuditEvents_AreRecordedAndListed()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var admin = await store.EnsureSingleAdminAsync();
        var user = await store.CreateUserAccountAsync("audit-user", 1);

        await store.RecordAdminAccountAuditEventAsync(
            admin,
            "user_created",
            user.AccountId,
            new { username = user.Username, project_limit = user.ProjectLimit });

        var events = await store.ListAdminAccountAuditEventsAsync();

        events.Should().ContainSingle();
        events[0].ActorAccountId.Should().Be(admin);
        events[0].TargetAccountId.Should().Be(user.AccountId);
        events[0].Action.Should().Be("user_created");
        events[0].MetadataJson.Should().Contain("audit-user");
        events[0].MetadataJson.Should().NotContain(user.Token);
    }

    [Fact]
    public async Task ListAdminAccountAuditEventsAsync_FiltersAndOffsetsResults()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var admin = await store.EnsureSingleAdminAsync();
        var first = await store.CreateUserAccountAsync("audit-first", 1);
        var second = await store.CreateUserAccountAsync("audit-second", 1);

        await store.RecordAdminAccountAuditEventAsync(admin, "user_created", first.AccountId, new { username = first.Username });
        await store.RecordAdminAccountAuditEventAsync(admin, "user_disabled", first.AccountId, new { disabled = true });
        await store.RecordAdminAccountAuditEventAsync(admin, "user_created", second.AccountId, new { username = second.Username });

        var filtered = await store.ListAdminAccountAuditEventsAsync(
            new AdminAccountAuditQuery(Limit: 10, Offset: 0, Action: "user_created", TargetAccountId: first.AccountId));
        var offset = await store.ListAdminAccountAuditEventsAsync(
            new AdminAccountAuditQuery(Limit: 1, Offset: 1, Action: "user_created", TargetAccountId: null));

        filtered.Should().ContainSingle();
        filtered[0].Action.Should().Be("user_created");
        filtered[0].TargetAccountId.Should().Be(first.AccountId);
        offset.Should().ContainSingle();
        offset[0].TargetAccountId.Should().Be(first.AccountId);
    }

    [Fact]
    public async Task CreateProjectAsync_EnforcesDefaultAccountQuota()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();

        var first = await store.CreateProjectAsync(CreateCommand(accountId, "project-one", "Game One"));
        first.Succeeded.Should().BeTrue();
        await store.SetProjectBootstrapStatusAsync(first.ProjectId!, "succeeded", null);
        var second = await store.CreateProjectAsync(CreateCommand(accountId, "project-two", "Game Two"));
        second.Succeeded.Should().BeTrue();
        await store.SetProjectBootstrapStatusAsync(second.ProjectId!, "succeeded", null);
        var third = await store.CreateProjectAsync(CreateCommand(accountId, "project-three", "Game Three"));

        third.Succeeded.Should().BeFalse();
        third.FailureCode.Should().Be("project_quota_exceeded");
        third.ProjectLimit.Should().Be(2);
    }

    [Fact]
    public async Task ListProjectsAsync_ReturnsCreatedUtcAndLastActivityUtc()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();

        var first = await store.CreateProjectAsync(CreateCommand(accountId, "project-one", "Game One"));
        first.Succeeded.Should().BeTrue();
        var second = await store.CreateProjectAsync(CreateCommand(accountId, "project-two", "Game Two"));
        second.Succeeded.Should().BeTrue();
        var firstCreatedUtc = "2099-06-01T00:00:00.0000000Z";
        var secondCreatedUtc = "2099-06-02T00:00:00.0000000Z";
        var firstRunFinishedUtc = "2099-06-03T00:00:00.0000000Z";

        await SetProjectCreatedUtcAsync(database.ConnectionString, first.ProjectId!, firstCreatedUtc);
        await SetProjectCreatedUtcAsync(database.ConnectionString, second.ProjectId!, secondCreatedUtc);
        var firstRun = await store.CreateRunAsync(first.ProjectId!, first.WorkspaceId, "prototype-chat");
        await SetRunTimingAsync(database.ConnectionString, firstRun, firstCreatedUtc, firstCreatedUtc, firstRunFinishedUtc);

        var projects = await store.ListProjectsAsync(accountId);

        projects.Should().HaveCount(2);
        projects.Single(project => project.ProjectId == first.ProjectId).CreatedUtc.Should().Be(firstCreatedUtc);
        projects.Single(project => project.ProjectId == first.ProjectId).LastActivityUtc.Should().Be(firstRunFinishedUtc);
        projects.Single(project => project.ProjectId == second.ProjectId).LastActivityUtc.Should().Be(secondCreatedUtc);
        projects.Last().ProjectId.Should().Be(first.ProjectId);
    }

    [Fact]
    public async Task ProjectChatMessages_AreAccountAndProjectScoped_AndRetained()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var project = await store.CreateProjectAsync(CreateCommand(accountId, "project-one", "Game One"));

        await store.AddProjectChatMessageAsync(accountId, project.ProjectId!, "user", "hello", retainLatest: 2);
        await store.AddProjectChatMessageAsync(accountId, project.ProjectId!, "assistant", "world", retainLatest: 2);
        await store.AddProjectChatMessageAsync(accountId, project.ProjectId!, "user", "latest", retainLatest: 2);

        var messages = await store.ListProjectChatMessagesAsync(accountId, project.ProjectId!, limit: 10);
        var otherAccountMessages = await store.ListProjectChatMessagesAsync("other-account", project.ProjectId!, limit: 10);

        messages.Select(message => message.Content).Should().Equal("world", "latest");
        messages.Select(message => message.Role).Should().Equal("assistant", "user");
        otherAccountMessages.Should().BeEmpty();
    }

    [Fact]
    public async Task ProjectChatMemory_IsAccountAndProjectScoped()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var project = await store.CreateProjectAsync(CreateCommand(accountId, "project-one", "Game One"));

        await store.UpsertProjectChatMemoryAsync(accountId, project.ProjectId!, "memory v1", "session-1");
        await store.UpsertProjectChatMemoryAsync(accountId, project.ProjectId!, "memory v2", "session-2");

        var memory = await store.GetProjectChatMemoryAsync(accountId, project.ProjectId!);
        var otherAccountMemory = await store.GetProjectChatMemoryAsync("other-account", project.ProjectId!);

        memory.Should().NotBeNull();
        memory!.MemorySummary.Should().Be("memory v2");
        memory.ProviderSessionRef.Should().Be("session-2");
        otherAccountMemory.Should().BeNull();
    }

    [Fact]
    public async Task ProjectChatHistory_MarksLatestSuggestedAssistantMessageConsumed_AfterFormalFeedback()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var project = await store.CreateProjectAsync(CreateCommand(accountId, "project-one", "Game One"));
        var chatHistory = new ProjectChatHistoryService(store);

        await store.AddProjectChatMessageAsync(
            accountId,
            project.ProjectId!,
            "assistant",
            "本轮继续优化已完成。\n\n下一步建议：继续优化首分钟体验。",
            "formal-feedback-result",
            retainLatest: 10);
        await store.AddProjectChatMessageAsync(
            accountId,
            project.ProjectId!,
            "user",
            "我同意，继续。",
            "formal-feedback",
            retainLatest: 10);

        var result = await chatHistory.ListAsync(accountId, project.ProjectId!);

        result.Should().NotBeNull();
        result!.Messages.Should().HaveCount(2);
        result.Messages[0].SuggestedFeedback.Should().Be("继续优化首分钟体验。");
        result.Messages[0].ContinueConsumed.Should().BeTrue();
        result.Messages[1].ContinueConsumed.Should().BeFalse();
    }

    [Fact]
    public async Task ProjectChatHistory_RemovesInternalRouteBlocks_WhenListingStoredMessages()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var project = await store.CreateProjectAsync(CreateCommand(accountId, "project-one", "Game One"));
        var chatHistory = new ProjectChatHistoryService(store);

        await store.AddProjectChatMessageAsync(
            accountId,
            project.ProjectId!,
            "assistant",
            "目标 1 修复已执行。\n本轮目标：\nDirection lock:\nProject README:\nC:\\host\\secret",
            "needs-fix-route-result",
            retainLatest: 10);

        var result = await chatHistory.ListAsync(accountId, project.ProjectId!);

        result.Should().NotBeNull();
        result!.Messages.Single().Content.Should().Be("目标 1 修复已执行。");
    }

    [Fact]
    public async Task ReconcileAbandonedRunsAsync_FailsOnlyRunsThatExceededHeartbeatTimeout()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var staleCreated = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Stale Game", "manual", null, null, null, null));
        await store.SetProjectBootstrapStatusAsync(staleCreated.ProjectId!, "succeeded", null);
        var freshCreated = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Fresh Game", "manual", null, null, null, null));
        await store.SetProjectBootstrapStatusAsync(freshCreated.ProjectId!, "succeeded", null);
        var staleProject = await store.GetProjectSnapshotAsync(staleCreated.ProjectId!);
        var freshProject = await store.GetProjectSnapshotAsync(freshCreated.ProjectId!);
        var staleRunId = await store.CreateRunAsync(staleProject!.ProjectId, staleProject.WorkspaceId, "prototype-feedback-iteration");
        var freshRunId = await store.CreateRunAsync(freshProject!.ProjectId, freshProject.WorkspaceId, "prototype-feedback-iteration");
        await store.MarkRunStartedAsync(staleRunId);
        await store.MarkRunStartedAsync(freshRunId);
        await store.TryAcquireRunnerLockAsync(staleProject.ProjectId, staleRunId);
        await store.TryAcquireRunnerLockAsync(freshProject.ProjectId, freshRunId);

        await using (var connection = new Microsoft.Data.Sqlite.SqliteConnection(database.ConnectionString))
        {
            await connection.OpenAsync();
            await using var command = connection.CreateCommand();
            command.CommandText = """
                UPDATE runs
                SET started_utc = $old_utc,
                    progress_updated_utc = $old_utc
                WHERE id = $run_id;
                """;
            command.Parameters.AddWithValue("$old_utc", DateTimeOffset.UtcNow.AddHours(-2).ToString("O"));
            command.Parameters.AddWithValue("$run_id", staleRunId);
            await command.ExecuteNonQueryAsync();
        }

        var recovered = await store.ReconcileAbandonedRunsAsync(
            run => run.RunType == "prototype-feedback-iteration" ? TimeSpan.FromHours(1) : null,
            run => $"timeout:{run.RunType}");
        var staleRun = await store.GetRunSnapshotAsync(staleRunId);
        var freshRun = await store.GetRunSnapshotAsync(freshRunId);

        recovered.Should().Be(1);
        staleRun!.Status.Should().Be("failed");
        staleRun.StderrText.Should().Contain("timeout:prototype-feedback-iteration");
        freshRun!.Status.Should().Be("running");
        (await store.HasRunnerLockAsync(staleProject.ProjectId)).Should().BeFalse();
        (await store.HasRunnerLockAsync(freshProject.ProjectId)).Should().BeTrue();
    }

    [Fact]
    public async Task ReconcileAbandonedRunsAsync_FailsQueuedWebPreviewFromPreviousProcess()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var created = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Preview Game", "manual", null, null, null, null));
        await store.SetProjectBootstrapStatusAsync(created.ProjectId!, "succeeded", null);
        var project = await store.GetProjectSnapshotAsync(created.ProjectId!);
        var runId = await store.CreateRunAsync(project!.ProjectId, project.WorkspaceId, "project-web-preview");
        var processStartedUtc = DateTimeOffset.UtcNow;

        await using (var connection = new Microsoft.Data.Sqlite.SqliteConnection(database.ConnectionString))
        {
            await connection.OpenAsync();
            await using var command = connection.CreateCommand();
            command.CommandText = """
                UPDATE runs
                SET created_utc = $old_utc,
                    progress_updated_utc = $old_utc
                WHERE id = $run_id;
                """;
            command.Parameters.AddWithValue("$old_utc", processStartedUtc.AddSeconds(-5).ToString("O"));
            command.Parameters.AddWithValue("$run_id", runId);
            await command.ExecuteNonQueryAsync();
        }

        var recovered = await store.ReconcileAbandonedRunsAsync(
            run => ProjectInitializationRecoveryService.SelectTimeoutForTesting(run, options, processStartedUtc),
            run => ProjectInitializationRecoveryService.BuildFailureMessageForTesting(run, processStartedUtc));
        var recoveredRun = await store.GetRunSnapshotAsync(runId);

        recovered.Should().Be(1);
        recoveredRun!.Status.Should().Be("failed");
        recoveredRun.StderrText.Should().Contain("server restarted");
    }

    [Fact]
    public async Task HasActiveRunAsync_IgnoresRunningChatRuns()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var created = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Chat Game", "manual", null, null, null, null));
        await store.SetProjectBootstrapStatusAsync(created.ProjectId!, "succeeded", null);
        var project = await store.GetProjectSnapshotAsync(created.ProjectId!);
        var chatRunId = await store.CreateRunAsync(project!.ProjectId, project.WorkspaceId, "prototype-chat");
        await store.MarkRunStartedAsync(chatRunId);

        var chatOnlyActive = await store.HasActiveRunAsync(project.ProjectId);

        chatOnlyActive.Should().BeFalse();

        var workflowRunId = await store.CreateRunAsync(project.ProjectId, project.WorkspaceId, "prototype-iteration-goal");
        await store.MarkRunStartedAsync(workflowRunId);

        var workflowActive = await store.HasActiveRunAsync(project.ProjectId);

        workflowActive.Should().BeTrue();
    }

    [Fact]
    public async Task CancelRunAsync_ShouldMarkRunningRunCancelKeepLockAndIgnoreLateCompletion()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("account-one", 10);
        var accountId = account.AccountId;
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var created = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Cancel Game", "RPG", null, null, null, null));
        await store.SetProjectBootstrapStatusAsync(created.ProjectId!, "succeeded", null);
        var project = await store.GetProjectSnapshotAsync(created.ProjectId!);
        var runId = await store.CreateRunAsync(project!.ProjectId, project.WorkspaceId, "prototype-iteration-goal");
        await store.MarkRunStartedAsync(runId);
        (await store.TryAcquireRunnerLockAsync(project.ProjectId, runId)).Should().BeTrue();

        var result = await store.CancelRunAsync(accountId, runId);
        await store.UpdateRunProgressAsync(runId, "failed", "late_progress", "Late failure should not replace cancel.");
        await store.CompleteRunAsync(runId, "succeeded", 0, "late stdout", "", "{}", CancellationToken.None);

        result.Should().Be(RunCancelResult.Cancelled);
        var run = await store.GetRunSnapshotAsync(runId);
        run!.Status.Should().Be("cancel");
        run.ExitCode.Should().Be(499);
        run.StderrText.Should().Contain("Cancelled by user.");
        run.ProgressStep.Should().Be("cancel");
        run.ProgressSubstep.Should().Be("user_cancelled");
        run.ProgressLabel.Should().Be("\u7528\u6237\u5df2\u53d6\u6d88\u5f53\u524d run\u3002");
        (await store.HasRunnerLockAsync(project.ProjectId)).Should().BeFalse();
        (await store.HasActiveRunAsync(project.ProjectId)).Should().BeFalse();
        var active = await store.GetActiveRunForAccountAsync(accountId);
        active.Should().BeNull();
        var nextRunId = await store.CreateRunAsync(project.ProjectId, project.WorkspaceId, "prototype-iteration-goal");
        (await store.TryAcquireRunnerLockAsync(project.ProjectId, nextRunId)).Should().BeTrue();

        await store.ReleaseRunnerLockAsync(project.ProjectId, nextRunId);
        (await store.HasRunnerLockAsync(project.ProjectId)).Should().BeFalse();
        var metrics = await store.ListRunMetricsForAdminAsync(accountId, null);
        metrics.Should().ContainSingle(row => row.Metric.RunId == runId && row.Metric.Status == "cancel");
    }

    [Fact]
    public async Task CancelRunAsync_ShouldReleaseQueuedRunLock()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("account-one", 10);
        var accountId = account.AccountId;
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var created = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Queued Cancel Game", "RPG", null, null, null, null));
        await store.SetProjectBootstrapStatusAsync(created.ProjectId!, "succeeded", null);
        var project = await store.GetProjectSnapshotAsync(created.ProjectId!);
        var runId = await store.CreateRunAsync(project!.ProjectId, project.WorkspaceId, "prototype-iteration-goal");
        (await store.TryAcquireRunnerLockAsync(project.ProjectId, runId)).Should().BeTrue();

        var result = await store.CancelRunAsync(accountId, runId);

        result.Should().Be(RunCancelResult.Cancelled);
        var run = await store.GetRunSnapshotAsync(runId);
        run!.Status.Should().Be("cancel");
        (await store.HasRunnerLockAsync(project.ProjectId)).Should().BeFalse();
        var nextRunId = await store.CreateRunAsync(project.ProjectId, project.WorkspaceId, "prototype-iteration-goal");
        (await store.TryAcquireRunnerLockAsync(project.ProjectId, nextRunId)).Should().BeTrue();
    }

    [Fact]
    public async Task HasRunnerLockAsync_ShouldIgnoreCancelledRunLocks()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("account-one", 10);
        var accountId = account.AccountId;
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var created = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Lock Game", "RPG", null, null, null, null));
        await store.SetProjectBootstrapStatusAsync(created.ProjectId!, "succeeded", null);
        var project = await store.GetProjectSnapshotAsync(created.ProjectId!);
        var runId = await store.CreateRunAsync(project!.ProjectId, project.WorkspaceId, "prototype-iteration-goal");
        await store.MarkRunStartedAsync(runId);
        (await store.TryAcquireRunnerLockAsync(project.ProjectId, runId)).Should().BeTrue();
        await store.CancelRunAsync(accountId, runId);

        (await store.HasRunnerLockAsync(project.ProjectId)).Should().BeFalse();
    }

    [Fact]
    public async Task MarkRunStartedAsync_ShouldNotReviveCancelledQueuedRun()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("account-one", 10);
        var accountId = account.AccountId;
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var created = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Queued Race Game", "RPG", null, null, null, null));
        await store.SetProjectBootstrapStatusAsync(created.ProjectId!, "succeeded", null);
        var project = await store.GetProjectSnapshotAsync(created.ProjectId!);
        var runId = await store.CreateRunAsync(project!.ProjectId, project.WorkspaceId, "prototype-iteration-goal");
        (await store.TryAcquireRunnerLockAsync(project.ProjectId, runId)).Should().BeTrue();

        var result = await store.CancelRunAsync(accountId, runId);
        var act = () => store.MarkRunStartedAsync(runId, 1);

        result.Should().Be(RunCancelResult.Cancelled);
        await act.Should().ThrowAsync<OperationCanceledException>();
        var run = await store.GetRunSnapshotAsync(runId);
        run!.Status.Should().Be("cancel");
        run.StartedUtc.Should().BeNull();
        run.QueuePositionAtStart.Should().BeNull();
        (await store.HasRunnerLockAsync(project.ProjectId)).Should().BeFalse();
    }

    [Fact]
    public async Task TryMarkRunStartedAsync_ShouldNotReviveFailedQueuedRun()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("account-one", 10);
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var created = await service.CreateProjectAsync(account.AccountId, new ProjectCreationRequest(null, "Failed Queue Game", "RPG", null, null, null, null));
        await store.SetProjectBootstrapStatusAsync(created.ProjectId!, "succeeded", null);
        var project = await store.GetProjectSnapshotAsync(created.ProjectId!);
        var runId = await store.CreateRunAsync(project!.ProjectId, project.WorkspaceId, "project-web-preview");
        await store.CompleteRunAsync(runId, "failed", 500, "", "recovered", """{"failure_code":"abandoned_run_recovered"}""");

        var started = await store.TryMarkRunStartedAsync(runId, 1);

        started.Should().BeFalse();
        var run = await store.GetRunSnapshotAsync(runId);
        run!.Status.Should().Be("failed");
        run.StartedUtc.Should().BeNull();
        run.QueuePositionAtStart.Should().BeNull();
    }

    [Fact]
    public async Task ReconcileAbandonedRunsAsync_CanRecoverPrototypeQuickFixRuns()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var created = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Quick Fix Game", "RPG", null, null, null, null));
        await store.SetProjectBootstrapStatusAsync(created.ProjectId!, "succeeded", null);
        var project = await store.GetProjectSnapshotAsync(created.ProjectId!);
        var runId = await store.CreateRunAsync(project!.ProjectId, project.WorkspaceId, "prototype-quick-fix");
        await store.MarkRunStartedAsync(runId);
        await store.TryAcquireRunnerLockAsync(project.ProjectId, runId);

        await using (var connection = new Microsoft.Data.Sqlite.SqliteConnection(database.ConnectionString))
        {
            await connection.OpenAsync();
            await using var command = connection.CreateCommand();
            command.CommandText = """
                UPDATE runs
                SET started_utc = $old_utc,
                    progress_updated_utc = $old_utc
                WHERE id = $run_id;
                """;
            command.Parameters.AddWithValue("$old_utc", DateTimeOffset.UtcNow.AddMinutes(-10).ToString("O"));
            command.Parameters.AddWithValue("$run_id", runId);
            await command.ExecuteNonQueryAsync();
        }

        var recovered = await store.ReconcileAbandonedRunsAsync(
            run => run.RunType == "prototype-quick-fix" ? TimeSpan.FromMinutes(3) : null,
            run => $"timeout:{run.RunType}");
        var recoveredRun = await store.GetRunSnapshotAsync(runId);

        recovered.Should().Be(1);
        recoveredRun!.Status.Should().Be("failed");
        recoveredRun.StderrText.Should().Contain("timeout:prototype-quick-fix");
        (await store.HasRunnerLockAsync(project.ProjectId)).Should().BeFalse();
    }

    [Fact]
    public async Task GetLatestProjectIterationSessionAsync_ReturnsStructuredGoalRuns()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            // ADR-0061: this suite creates disposable projects beneath the OS temp root.
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var project = await store.CreateProjectAsync(CreateCommand(accountId, "project-one", "Game One"));
        await store.SetProjectBootstrapStatusAsync(project.ProjectId!, "succeeded", null);

        var session = await store.CreateProjectIterationSessionAsync(
            accountId,
            project.ProjectId!,
            "manual_feedback",
            "improve prototype",
            "overall goal",
            [
                new ProjectIterationGoalCreateCommand(1, "Goal 1", "Desc 1", "Hint 1"),
                new ProjectIterationGoalCreateCommand(2, "Goal 2", "Desc 2", "Hint 2")
            ]);

        var runId = await store.CreateRunAsync(project.ProjectId!, project.WorkspaceId, "prototype-iteration-goal");
        var details = await store.GetLatestProjectIterationSessionAsync(project.ProjectId!);
        details.Should().NotBeNull();
        await store.LinkProjectIterationGoalRunAsync(session.SessionId, details!.Goals[0].GoalId, runId, "prototype-iteration-goal");

        details = await store.GetLatestProjectIterationSessionAsync(project.ProjectId!);

        details.Should().NotBeNull();
        details!.Goals.Should().HaveCount(2);
        details.GoalRuns.Should().ContainSingle();
        details.GoalRuns[0].GoalId.Should().Be(details.Goals[0].GoalId);
        details.GoalRuns[0].RunId.Should().Be(runId);
        details.GoalRuns[0].RunType.Should().Be("prototype-iteration-goal");
    }

    private static ProjectCreationCommand CreateCommand(string accountId, string projectName, string gameName)
    {
        var projectId = Guid.NewGuid().ToString("N");
        var root = Path.Combine(Path.GetTempPath(), projectId);
        return new ProjectCreationCommand(
            projectId,
            accountId,
            projectName,
            gameName,
            "admin-rule",
            "godot-prototype-default",
            true,
            ["chapter2-bootstrap", "prototype-7day-playable", "prototype-tdd", "prototype-scene"],
            root,
            Path.Combine(root, "repo"),
            Path.Combine(root, "runtime"),
            Path.Combine(root, "meta"));
    }

    private static async Task WriteDecisionEvidenceFilesAsync(
        PhaseAMetadataStore store,
        string projectId,
        params string[] relativePaths)
    {
        var project = await store.GetProjectSnapshotAsync(projectId);
        foreach (var relativePath in relativePaths)
        {
            var path = Path.Combine(project!.RepoPath, relativePath.Replace('/', Path.DirectorySeparatorChar));
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            await File.WriteAllTextAsync(path, "{}", Encoding.UTF8);
        }
    }

    private static async Task SetProjectCreatedUtcAsync(string connectionString, string projectId, string createdUtc)
    {
        await using var connection = new Microsoft.Data.Sqlite.SqliteConnection(connectionString);
        await connection.OpenAsync();
        await using var command = connection.CreateCommand();
        command.CommandText = "UPDATE projects SET created_utc = $created_utc, last_activity_utc = $created_utc WHERE id = $project_id;";
        command.Parameters.AddWithValue("$project_id", projectId);
        command.Parameters.AddWithValue("$created_utc", createdUtc);
        await command.ExecuteNonQueryAsync();
    }

    private static async Task SetRunTimingAsync(string connectionString, string runId, string createdUtc, string startedUtc, string finishedUtc)
    {
        await using var connection = new Microsoft.Data.Sqlite.SqliteConnection(connectionString);
        await connection.OpenAsync();
        await using var command = connection.CreateCommand();
        command.CommandText = """
            UPDATE runs
            SET created_utc = $created_utc,
                started_utc = $started_utc,
                finished_utc = $finished_utc,
                progress_updated_utc = $finished_utc
            WHERE id = $run_id;
            """;
        command.Parameters.AddWithValue("$run_id", runId);
        command.Parameters.AddWithValue("$created_utc", createdUtc);
        command.Parameters.AddWithValue("$started_utc", startedUtc);
        command.Parameters.AddWithValue("$finished_utc", finishedUtc);
        await command.ExecuteNonQueryAsync();
    }

    private static async Task CreateLegacyDatabaseWithoutProjectLastActivityAsync(string connectionString)
    {
        await using var connection = new Microsoft.Data.Sqlite.SqliteConnection(connectionString);
        await connection.OpenAsync();
        await using var command = connection.CreateCommand();
        command.CommandText = """
            CREATE TABLE accounts (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NULL,
                token_hash TEXT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0,
                created_utc TEXT NOT NULL
            );
            CREATE TABLE projects (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                name TEXT NOT NULL,
                game_name TEXT NOT NULL,
                game_type_source TEXT NOT NULL,
                template_rule_id TEXT NOT NULL,
                llm_binding_required INTEGER NOT NULL DEFAULT 0,
                allowed_workflows_json TEXT NOT NULL DEFAULT '[]',
                bootstrap_status TEXT NOT NULL DEFAULT 'initial',
                bootstrap_error TEXT NULL,
                created_utc TEXT NOT NULL,
                FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
            );
            CREATE TABLE runs (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                workspace_id TEXT NULL,
                run_type TEXT NOT NULL,
                status TEXT NOT NULL,
                created_utc TEXT NOT NULL,
                started_utc TEXT NULL,
                finished_utc TEXT NULL,
                exit_code INTEGER NULL,
                stdout_text TEXT NULL,
                stderr_text TEXT NULL,
                evidence_json TEXT NULL,
                progress_step TEXT NOT NULL DEFAULT '',
                progress_substep TEXT NOT NULL DEFAULT '',
                progress_label TEXT NOT NULL DEFAULT '',
                progress_updated_utc TEXT NULL,
                queue_position_at_start INTEGER NULL,
                llm_gateway TEXT NULL,
                llm_request_id TEXT NULL,
                llm_model TEXT NULL,
                llm_cost_json TEXT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
            INSERT INTO accounts (id, username, is_admin, created_utc)
            VALUES ('legacy-account', 'legacy', 0, '2099-01-01T00:00:00.0000000Z');
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
                created_utc)
            VALUES (
                'legacy-project',
                'legacy-account',
                'Legacy Project',
                'Legacy Game',
                'manual',
                'godot-prototype-default',
                0,
                '[]',
                'succeeded',
                '2099-01-01T00:00:00.0000000Z');
            INSERT INTO runs (
                id,
                project_id,
                run_type,
                status,
                created_utc,
                started_utc,
                finished_utc,
                progress_updated_utc)
            VALUES (
                'legacy-run',
                'legacy-project',
                'prototype-chat',
                'succeeded',
                '2099-01-01T00:00:00.0000000Z',
                '2099-01-01T00:00:00.0000000Z',
                '2099-01-02T00:00:00.0000000Z',
                '2099-01-02T00:00:00.0000000Z');
            """;
        await command.ExecuteNonQueryAsync();
    }

    private static async Task<string?> ScalarStringAsync(Microsoft.Data.Sqlite.SqliteConnection connection, string sql)
    {
        await using var command = connection.CreateCommand();
        command.CommandText = sql;
        return await command.ExecuteScalarAsync() as string;
    }

    private static async Task<long> ScalarLongAsync(Microsoft.Data.Sqlite.SqliteConnection connection, string sql)
    {
        await using var command = connection.CreateCommand();
        command.CommandText = sql;
        var value = await command.ExecuteScalarAsync();
        return Convert.ToInt64(value);
    }

    private static async Task<IReadOnlySet<string>> ReadIndexNamesAsync(string connectionString)
    {
        await using var connection = new Microsoft.Data.Sqlite.SqliteConnection(connectionString);
        await connection.OpenAsync();
        await using var command = connection.CreateCommand();
        command.CommandText = "SELECT name FROM sqlite_master WHERE type = 'index';";
        var indexes = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        await using var reader = await command.ExecuteReaderAsync();
        while (await reader.ReadAsync())
        {
            indexes.Add(reader.GetString(0));
        }

        return indexes;
    }
}

