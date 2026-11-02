using System.IO.Compression;
using PhaseA.Platform.Readback;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using FluentAssertions;
using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Prototypes;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Tests.Data;
using PhaseA.Platform.Tests.NodeIdentity;
using PhaseA.Platform.Security;
using PhaseA.Platform.Skills;
using PhaseA.Platform.Workspaces;
using PhaseA.Platform.Workflow;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class GddToModuleBackendContractServiceTests
{

    // ADR-0061 AD19/20: observe the existing shared mutation wait, never a replacement authorization gate.
    internal static async Task<object> ObserveMilestoneMutationWaitsAsync()
    {
        var rows = new List<object>();
        foreach (var entry in new[] { "feedback", "feedback-strict", "iteration-plan", "execute", "execute-strict" })
        foreach (var mode in new[] { "valid", "revoked", "stale-projection", "entry-only", "foreign-home", "foreign-project", "swapped-path" })
        {
            using var fixture = await BackendContractFixture.CreateAsync();
            using var current = fixture.EnterCurrent();
            var project = await fixture.GetProjectAsync();
            var roles = new HashSet<string> { "entry", "production" };
            NodeProjectMetadata node = new PhaseAMetadataStore(fixture.ConnectionString, fixture.Options with { EnabledRoles = roles });
            var queue = new HeavyRunnerQueueService(null, HeavyRunnerQueueService.DefaultMaxConcurrentOtherRuns, node);
            var runner = new PendingOwnedDirectRunner();
            runner.Release();
            var seeder = new ProjectWorkspaceSeeder(fixture.Options, fixture.Store);
            var writer = new PrototypeRouteStateWriter();
            var quickFix = new PrototypeQuickFixService(node, fixture.Options, runner, seeder, new SkillActionCatalog(), heavyRunnerQueue: queue);
            var service = new GddMilestoneStepService(node,
                new PrototypeIterationGoalService(node, fixture.Options, runner, seeder, heavyRunnerQueue: queue),
                new PrototypeNeedsFixRouteService(node, quickFix, writer));
            var gdd = Path.Combine(project.RepoPath, "docs", "gdd", "GDD.md");
            Directory.CreateDirectory(Path.GetDirectoryName(gdd)!);
            await File.WriteAllTextAsync(gdd, "# Two Step GDD\nM1: First playable module.\nM2: Core loop validation.\n");
            var plan = await service.GetOrCreateLatestAsync(fixture.AccountId, fixture.ProjectId);
            if (plan is null || plan.Steps.Count != 2) throw new InvalidOperationException("Actual milestone prerequisite unavailable.");
            // A completed prior-step fixture selects M2; this is not real prior Runner evidence.
            foreach (var path in new[] { Path.Combine(project.MetaPath,"routes","gdd-milestones","latest.json"),
                         Path.Combine(project.RepoPath,"meta","routes","gdd-milestones","latest.json") }.Distinct())
            {
                var state = JsonNode.Parse(await File.ReadAllTextAsync(path))!;
                state["steps"]![0]!["status"] = "confirmed";
                state["steps"]![0]!["confirmedUtc"] = DateTimeOffset.UtcNow.ToString("O");
                state["steps"]![1]!["locked"] = false;
                state["currentStepId"] = plan.Steps[1].StepId;
                await File.WriteAllTextAsync(path,state.ToJsonString());
            }
            var registry = ProjectMutationLockRegistry.Shared;
            IAsyncDisposable? held = await registry.AcquireAsync(fixture.AccountId,fixture.ProjectId,CancellationToken.None);
            try
            {
                var feedback = new GddMilestoneStepFeedbackRequest("Owned current module feedback.");
                Task<GddMilestoneStepActionResult?> operation = entry switch
                {
                    "feedback" => service.SubmitFeedbackAsync(fixture.AccountId,fixture.ProjectId,plan.Steps[1].StepId,feedback),
                    "feedback-strict" => service.SubmitFeedbackStrictAsync(fixture.AccountId,fixture.ProjectId,plan.Steps[1].StepId,feedback),
                    "iteration-plan" => service.CreateIterationPlanForCurrentStepAsync(fixture.AccountId,fixture.ProjectId),
                    "execute" => service.ExecuteCurrentStepAsync(fixture.AccountId,fixture.ProjectId),
                    "execute-strict" => service.ExecuteCurrentStepStrictAsync(fixture.AccountId,fixture.ProjectId),
                    _ => throw new InvalidOperationException("Unknown milestone entry.")
                };
                // Read the existing waiter's count only. No semaphore, source or guard is modified.
                var entries = (System.Collections.IDictionary)typeof(ProjectMutationLockRegistry)
                    .GetField("_entries",System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.Instance)!.GetValue(registry)!;
                int References()
                {
                    var value = entries[fixture.AccountId+":"+fixture.ProjectId]!;
                    return (int)value.GetType().GetProperty("ReferenceCount")!.GetValue(value)!;
                }
                var deadline = System.Diagnostics.Stopwatch.StartNew();
                while (References() < 2 && !operation.IsCompleted && deadline.Elapsed < TimeSpan.FromSeconds(10))
                    await Task.Delay(10);
                if (References() < 2 || operation.IsCompleted)
                    throw new InvalidOperationException("Actual milestone mutation wait unavailable: "+entry+" "+
                        (operation.IsCompleted ? JsonSerializer.Serialize(await operation) : "deadline"));
                Dictionary<string,string> Files() => Directory.EnumerateFiles(project.WorkspaceRootPath,"*",SearchOption.AllDirectories)
                    .ToDictionary(path=>Path.GetRelativePath(project.WorkspaceRootPath,path),path=>Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))),StringComparer.Ordinal);
                var before = Files();
                try { await ApplyOwnedPendingModelFaultAsync(fixture,mode,roles); }
                finally { await held.DisposeAsync(); held=null; }
                var denied=false;
                GddMilestoneStepActionResult? result=null;
                try { result=await operation.WaitAsync(TimeSpan.FromSeconds(20)); }
                catch(UnauthorizedAccessException) { denied=true; }
                var after=Files();
                var changed=before.Keys.Union(after.Keys).Where(path=>!before.TryGetValue(path,out var left)||
                    !after.TryGetValue(path,out var right)||left!=right).Order().ToArray();
                rows.Add(new{entry,mode,waitObserved=true,denied,returned=result is not null,status=result?.Status,runnerCalls=runner.Calls,changed,
                    proofScope="actual caller and current-authority check after shared mutation wait; inherited business preflight outcome is recorded, not execution success"});
            }
            finally { if(held is not null) await held.DisposeAsync(); }
        }
        return rows;
    }

    internal static async Task<object> ObserveRepairExecutionAndNewRoundAsync()
    {
        var rows = new List<object>();
        foreach (var family in new[] { "repair-execute", "new-round" })
        foreach (var mode in new[] { "valid", "revoked", "stale-projection", "entry-only", "foreign-home", "foreign-project", "swapped-path" })
        {
            // A server-approved rebind before a new request is not a stale-request path fault.
            if (family == "new-round" && mode == "swapped-path") continue;
            using var fixture = await BackendContractFixture.CreateAsync();
            using var current = fixture.EnterCurrent();
            var project = await fixture.GetProjectAsync();
            var roles = new HashSet<string> { "entry", "production" };
            NodeProjectMetadata node = new PhaseAMetadataStore(fixture.ConnectionString, fixture.Options with { EnabledRoles = roles });
            var queue = new HeavyRunnerQueueService(null, HeavyRunnerQueueService.DefaultMaxConcurrentOtherRuns, node);
            var runner = new PendingOwnedDirectRunner();
            var seeder = new ProjectWorkspaceSeeder(fixture.Options, fixture.Store);
            var writer = new PrototypeRouteStateWriter();
            var quickFix = new PrototypeQuickFixService(node, fixture.Options, runner, seeder, new SkillActionCatalog(), heavyRunnerQueue: queue);
            var repair = new PrototypeRepairPlanService(node, quickFix, writer);
            var milestone = new GddMilestoneStepService(node,
                new PrototypeIterationGoalService(node, fixture.Options, runner, seeder, heavyRunnerQueue: queue),
                new PrototypeNeedsFixRouteService(node, quickFix, writer));
            var gdd = Path.Combine(project.RepoPath, "docs", "gdd", "GDD.md");
            if (family == "repair-execute")
            {
                var failed = await fixture.Store.CreateRunAsync(fixture.ProjectId, project.WorkspaceId, "prototype-7day-playable");
                await fixture.Store.MarkRunStartedAsync(failed);
                await fixture.Store.CompleteRunAsync(failed, "failed", 1,
                    "Prototype workflow failed.\nDAY4_IMPLEMENTATION_VALIDATION failed",
                    "Permission denied\nrpg_scene_node_contract_drift=Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn", "{}");
                var plan = await repair.CreateAsync(fixture.AccountId, fixture.ProjectId);
                if (plan.Goals.Count == 0) throw new InvalidOperationException("Actual repair plan prerequisite unavailable.");
            }
            else
            {
                Directory.CreateDirectory(Path.GetDirectoryName(gdd)!);
                await File.WriteAllTextAsync(gdd, "# Two Step GDD\nM1: First playable module.\nM2: Core loop validation.\n");
                var plan = await milestone.GetOrCreateLatestAsync(fixture.AccountId, fixture.ProjectId);
                if (plan is null || plan.Steps.Count != 2) throw new InvalidOperationException("Actual two-milestone prerequisite unavailable.");
                foreach (var path in new[] { Path.Combine(project.MetaPath, "routes", "gdd-milestones", "latest.json"),
                             Path.Combine(project.RepoPath, "meta", "routes", "gdd-milestones", "latest.json") }.Distinct())
                {
                    var state = JsonNode.Parse(await File.ReadAllTextAsync(path))!;
                    foreach (var step in state["steps"]!.AsArray())
                    {
                        step!["status"] = "confirmed";
                        step["confirmedUtc"] = DateTimeOffset.UtcNow.ToString("O");
                    }
                    await File.WriteAllTextAsync(path, state.ToJsonString());
                }
            }
            Dictionary<string, string> Files()
            {
                var files = new Dictionary<string, string>(StringComparer.Ordinal);
                foreach (var (prefix, root) in new[] { ("repo/", project.RepoPath), ("meta/", project.MetaPath) })
                    foreach (var path in Directory.EnumerateFiles(root, "*", SearchOption.AllDirectories))
                        files[prefix+Path.GetRelativePath(root,path)] = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path)));
                return files;
            }
            static async Task<object?> Box<T>(Task<T> operation) => await operation;
            Task<object?>? operation = null;
            if (family == "repair-execute")
            {
                operation = Box(repair.ExecuteNextAsync(fixture.AccountId, fixture.ProjectId, new PrototypeRepairStepExecutionRequest()));
                await Task.WhenAny(runner.Started, operation).WaitAsync(TimeSpan.FromSeconds(10));
                if (!runner.Started.IsCompletedSuccessfully)
                    throw new InvalidOperationException("Actual repair execution did not reach runner: " + JsonSerializer.Serialize(await operation));
                if (string.IsNullOrWhiteSpace(runner.RunId)) throw new InvalidOperationException("Actual repair run binding absent.");
            }
            async Task<string> RepairRows()
            {
                var rows = new List<object>();
                await using var connection = new SqliteConnection(fixture.ConnectionString);
                await connection.OpenAsync();
                foreach (var table in new[] { "runs", "project_iteration_sessions", "project_iteration_goals", "project_iteration_goal_runs" })
                {
                    await using var command = connection.CreateCommand();
                    var where = table is "project_iteration_goals" or "project_iteration_goal_runs"
                        ? "session_id IN (SELECT id FROM project_iteration_sessions WHERE project_id=$project)"
                        : "project_id=$project";
                    command.CommandText = "SELECT * FROM " + table + " WHERE " + where + " ORDER BY rowid;";
                    command.Parameters.AddWithValue("$project", fixture.ProjectId);
                    await using var reader = await command.ExecuteReaderAsync();
                    var values = new List<object?[]>();
                    while (await reader.ReadAsync())
                    {
                        var row = new object?[reader.FieldCount];
                        for (var i=0; i<row.Length; i++) row[i] = reader.IsDBNull(i) ? null : reader.GetValue(i);
                        values.Add(row);
                    }
                    rows.Add(new { table, values });
                }
                return Convert.ToHexString(SHA256.HashData(JsonSerializer.SerializeToUtf8Bytes(rows)));
            }
            var before = Files();
            var beforeRows = await RepairRows();
            try { await ApplyOwnedPendingModelFaultAsync(fixture, mode, roles); }
            finally { runner.Release(); }
            if (family == "new-round")
                operation = Box(milestone.CreateNewRoundStepAsync(fixture.AccountId, fixture.ProjectId,
                    new GddMilestoneNewRoundRequest("Owned next module control.")));
            object? result = null;
            var denied = false;
            try { result = await operation!.WaitAsync(TimeSpan.FromSeconds(20)); }
            catch (UnauthorizedAccessException) { denied = true; }
            var after = Files();
            var changed = before.Keys.Union(after.Keys).Where(path =>
                !before.TryGetValue(path,out var left) || !after.TryGetValue(path,out var right) || left != right).Order().ToArray();
            rows.Add(new { family, mode, denied, returned = result is not null,
                status = result?.GetType().GetProperty("Status")?.GetValue(result),
                reachedRunner = runner.Started.IsCompletedSuccessfully, calls = runner.Calls, changed,
                appendedModule = family == "new-round" && File.ReadAllText(gdd).Contains("M3", StringComparison.Ordinal),
                publishedRowsChanged = beforeRows != await RepairRows() });
        }
        return rows;
    }

    // The four remaining direct producers use actual service continuations and owned external providers.
    internal static async Task<object> ObserveDirectExecutionContinuationsAsync()
    {
        var rows = new List<object>();
        foreach (var family in new[] { "skill-action", "chapter2-bootstrap", "prototype-tdd", "prototype-scene" })
        foreach (var mode in new[] { "valid", "revoked", "stale-projection", "entry-only", "foreign-home", "foreign-project", "swapped-path" })
        {
            using var fixture = await BackendContractFixture.CreateAsync();
            using var current = fixture.EnterCurrent();
            var project = await fixture.GetProjectAsync();
            var roles = new HashSet<string> { "entry", "production" };
            NodeProjectMetadata node = new PhaseAMetadataStore(fixture.ConnectionString, fixture.Options with { EnabledRoles = roles });
            var queue = new HeavyRunnerQueueService(null, HeavyRunnerQueueService.DefaultMaxConcurrentOtherRuns, node);
            var seeder = new ProjectWorkspaceSeeder(fixture.Options, fixture.Store);
            var model = new BlockingRequirementMapLlmEngine("Owned current skill reply");
            var runner = new PendingOwnedDirectRunner();
            static async Task<object> Box<T>(Task<T> operation) => (await operation)!;
            Task<object> operation = family switch
            {
                "skill-action" => Box(new SkillActionService(node, fixture.Options, new SkillActionCatalog(), runner, seeder,
                    llmRouteEngine: model, heavyRunnerQueue: queue, assetRunnerQueue: queue)
                    .RunAsync(fixture.AccountId, fixture.ProjectId, "game-design-master", new SkillActionRunRequest("Owned direct caller"))),
                "chapter2-bootstrap" => Box(new Chapter2BootstrapService(node, fixture.Options, runner,
                    new Chapter2BootstrapCommandBuilder(fixture.Options), new ProjectHealthArtifactIndexer(), seeder,
                    heavyRunnerQueue: queue).RunAsync(fixture.AccountId, fixture.ProjectId)),
                "prototype-tdd" => Box(new PrototypeCommandService(node, fixture.Options, runner,
                    new PrototypeCommandBuilder(fixture.Options), new PrototypeTddArtifactIndexer(), seeder, queue)
                    .RunTddAsync(fixture.AccountId, fixture.ProjectId, new PrototypeTddRequest("s236", "green"))),
                "prototype-scene" => Box(new PrototypeCommandService(node, fixture.Options, runner,
                    new PrototypeCommandBuilder(fixture.Options), new PrototypeTddArtifactIndexer(), seeder, queue)
                    .CreateSceneAsync(fixture.AccountId, fixture.ProjectId, new PrototypeSceneRequest("s236"))),
                _ => throw new InvalidOperationException("Unknown direct consumer.")
            };
            var started = family == "skill-action" ? model.Started : runner.Started;
            await Task.WhenAny(started, operation).WaitAsync(TimeSpan.FromSeconds(10));
            if (!started.IsCompletedSuccessfully)
            {
                var premature = await operation;
                throw new InvalidOperationException("Actual direct positive did not reach external boundary: " + family + " " + JsonSerializer.Serialize(premature));
            }
            if (family == "skill-action" && (model.Request?.Purpose != "skill-action" || model.Request.BillingAccountId != fixture.AccountId))
                throw new InvalidOperationException("Actual skill provider request binding unavailable.");
            if (family != "skill-action" && string.IsNullOrWhiteSpace(runner.RunId))
                throw new InvalidOperationException("Actual direct runner request has no real run binding.");
            Dictionary<string, string> Files() => Directory.EnumerateFiles(project.RepoPath, "*", SearchOption.AllDirectories)
                .ToDictionary(path => Path.GetRelativePath(project.RepoPath, path), path => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))), StringComparer.Ordinal);
            async Task<string> PublishedRows()
            {
                var tables = new List<object>();
                await using var connection = new SqliteConnection(fixture.ConnectionString);
                await connection.OpenAsync();
                foreach (var table in new[] { "runs", "artifacts" })
                {
                    await using var command = connection.CreateCommand();
                    command.CommandText = "SELECT * FROM " + table + " WHERE project_id=$project ORDER BY rowid;";
                    command.Parameters.AddWithValue("$project", fixture.ProjectId);
                    await using var reader = await command.ExecuteReaderAsync();
                    var values = new List<object?[]>();
                    while (await reader.ReadAsync())
                    {
                        var row = new object?[reader.FieldCount];
                        for (var i=0; i<row.Length; i++) row[i] = reader.IsDBNull(i) ? null : reader.GetValue(i);
                        values.Add(row);
                    }
                    tables.Add(new { table, values });
                }
                return Convert.ToHexString(SHA256.HashData(JsonSerializer.SerializeToUtf8Bytes(tables)));
            }
            var beforeFiles = Files();
            var beforeRows = await PublishedRows();
            try { await ApplyOwnedPendingModelFaultAsync(fixture, mode, roles); }
            finally { model.Release(); runner.Release(); }
            var denied = false;
            object? result = null;
            try { result = await operation.WaitAsync(TimeSpan.FromSeconds(20)); }
            catch (UnauthorizedAccessException) { denied = true; }
            var afterFiles = Files();
            var changed = beforeFiles.Keys.Union(afterFiles.Keys).Where(path =>
                !beforeFiles.TryGetValue(path, out var left) || !afterFiles.TryGetValue(path, out var right) || left != right).Order().ToArray();
            rows.Add(new { family, mode, denied, reachedProvider = started.IsCompletedSuccessfully,
                calls = family == "skill-action" ? model.CallCount : runner.Calls,
                returned = result is not null, status = result?.GetType().GetProperty("Status")?.GetValue(result),
                changed, publishedRowsChanged = beforeRows != await PublishedRows() });
        }
        return rows;
    }

    private sealed class PendingOwnedDirectRunner : IHostedProcessRunner
    {
        private readonly TaskCompletionSource _started = new(TaskCreationOptions.RunContinuationsAsynchronously);
        private readonly TaskCompletionSource _release = new(TaskCreationOptions.RunContinuationsAsynchronously);
        internal Task Started => _started.Task;
        internal int Calls { get; private set; }
        internal string? RunId { get; private set; }
        internal void Release() => _release.TrySetResult();
        public async Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Calls++; RunId = command.RunId; _started.TrySetResult();
            await _release.Task.WaitAsync(cancellationToken);
            return new HostedProcessResult(0, "Owned external executor result; not real Windows or engine evidence.", "");
        }
    }

    // ADR-0061 AD19/20: the actual chat continuation cannot publish a reply after authority changes.
    internal static async Task<object> ObserveChatReplyBoundaryAsync()
    {
        var rows = new List<object>();
        var oldMode = Environment.GetEnvironmentVariable("PHASEA_CHAT_TEST_MODE");
        var oldBackend = Environment.GetEnvironmentVariable("PHASEA_CHAT_BACKEND");
        var oldOwnedToken = Environment.GetEnvironmentVariable("S206_OWNED_CHAT_TOKEN");
        try
        {
            // Select the real Codex-route service branch with an owned external-provider double.
            // Neither device model configuration nor the production guard is replaced.
            Environment.SetEnvironmentVariable("PHASEA_CHAT_TEST_MODE", null);
            Environment.SetEnvironmentVariable("PHASEA_CHAT_BACKEND", null);
            Environment.SetEnvironmentVariable("S206_OWNED_CHAT_TOKEN", "owned-test-token-not-a-secret");
            foreach (var backend in new[] { "codex-route", "new-api" })
            foreach (var mode in new[] { "valid", "revoked", "stale-projection", "entry-only", "foreign-home", "foreign-project", "swapped-path" })
            {
                using var fixture = await BackendContractFixture.CreateAsync();
                using var current = fixture.EnterCurrent();
                var roles = new HashSet<string> { "entry", "production" };
                NodeProjectMetadata node = new PhaseAMetadataStore(fixture.ConnectionString, fixture.Options with { EnabledRoles = roles });
                var engine = new BlockingRequirementMapLlmEngine("Owned current chat reply");
                var client = new PendingOwnedChatApi();
                var binding = new LlmBindingService(fixture.Store, fixture.Options);
                Environment.SetEnvironmentVariable("PHASEA_CHAT_BACKEND", backend == "new-api" ? "new-api" : null);
                if (backend == "new-api")
                    await binding.BindAsync(fixture.AccountId, new LlmBindingRequest("new-api", "https://owned.invalid", "owned-test-account", "env:S206_OWNED_CHAT_TOKEN"));
                var service = new ChatService(node, fixture.Options,
                    binding, new LlmStopLossService(node, fixture.Options),
                    backend == "new-api" ? client : new UnexpectedClosureNewApi(), new UnexpectedInventoryCodex(),
                    new ProjectWorkspaceSeeder(fixture.Options, fixture.Store), new SkillActionCatalog(), engine);
                var operation = service.SendAsync(fixture.AccountId, fixture.ProjectId, new ChatRequest("Remember this owned project request."));
                var started = backend == "new-api" ? client.Started : engine.Started;
                await Task.WhenAny(started, operation).WaitAsync(TimeSpan.FromSeconds(10));
                if (!started.IsCompletedSuccessfully)
                    throw new InvalidOperationException("Actual chat positive did not reach its provider: " + JsonSerializer.Serialize(await operation));
                if (backend == "codex-route" && (engine.Request?.Purpose != "project-chat" || engine.Request.BillingAccountId != fixture.AccountId || engine.Request.OperationKey != "llm:project-chat"))
                    throw new InvalidOperationException("Actual chat model request binding unavailable.");
                async Task<string> PublishedRows()
                {
                    var tables = new List<object>();
                    await using var connection = new SqliteConnection(fixture.ConnectionString);
                    await connection.OpenAsync();
                    foreach (var table in new[] { "runs", "project_chat_memories" })
                    {
                        await using var command = connection.CreateCommand();
                        command.CommandText = "SELECT * FROM " + table + " WHERE project_id=$project ORDER BY rowid;";
                        command.Parameters.AddWithValue("$project", fixture.ProjectId);
                        await using var reader = await command.ExecuteReaderAsync();
                        var values = new List<object?[]>();
                        while (await reader.ReadAsync())
                        {
                            var row = new object?[reader.FieldCount];
                            for (var i=0; i<row.Length; i++) row[i] = reader.IsDBNull(i) ? null : reader.GetValue(i);
                            values.Add(row);
                        }
                        tables.Add(new { table, values });
                    }
                    return Convert.ToHexString(SHA256.HashData(JsonSerializer.SerializeToUtf8Bytes(tables)));
                }
                var before = await PublishedRows();
                try { await ApplyOwnedPendingModelFaultAsync(fixture, mode, roles); }
                finally { engine.Release(); client.Release(); }
                var denied = false;
                ChatResult? result = null;
                try { result = await operation.WaitAsync(TimeSpan.FromSeconds(20)); }
                catch (UnauthorizedAccessException) { denied = true; }
                var after = await PublishedRows();
                rows.Add(new { backend, mode, denied, reachedModel = started.IsCompletedSuccessfully, calls = backend == "new-api" ? client.Calls : engine.CallCount,
                    returned = result is not null, reply = result?.AssistantMessage, status = result?.Status,
                    publishedRowsChanged = before != after });
            }
        }
        finally
        {
            Environment.SetEnvironmentVariable("PHASEA_CHAT_TEST_MODE", oldMode);
            Environment.SetEnvironmentVariable("PHASEA_CHAT_BACKEND", oldBackend);
            Environment.SetEnvironmentVariable("S206_OWNED_CHAT_TOKEN", oldOwnedToken);
        }
        return rows;
    }

    private sealed class UnexpectedClosureNewApi : INewApiChatClient
    {
        public Task<NewApiChatClientResult> CompleteAsync(LlmBindingSnapshot binding, string bearerToken, string model,
            IReadOnlyList<ChatMessage> messages, CancellationToken cancellationToken = default)
            => throw new InvalidOperationException("Owned chat route unexpectedly attempted the network client.");
    }

    private sealed class PendingOwnedChatApi : INewApiChatClient
    {
        private readonly TaskCompletionSource _started = new(TaskCreationOptions.RunContinuationsAsynchronously);
        private readonly TaskCompletionSource _release = new(TaskCreationOptions.RunContinuationsAsynchronously);
        internal Task Started => _started.Task;
        internal int Calls { get; private set; }
        internal void Release() => _release.TrySetResult();
        public async Task<NewApiChatClientResult> CompleteAsync(LlmBindingSnapshot binding, string bearerToken, string model,
            IReadOnlyList<ChatMessage> messages, CancellationToken cancellationToken = default)
        {
            if (binding.ExternalAccountRef != "owned-test-account" || bearerToken != "owned-test-token-not-a-secret" || messages.Count == 0)
                throw new InvalidOperationException("Actual owned API request binding unavailable.");
            Calls++; _started.TrySetResult();
            await _release.Task.WaitAsync(cancellationToken);
            return new NewApiChatClientResult(true, "Owned current chat reply", null, "owned-request", null);
        }
    }

    // ADR-0061 AD19/20: inventory publication must retain current workspace binding after model wait.
    internal static async Task<object> ObserveAssetInventoryReplyBoundaryAsync()
    {
        var rows = new List<object>();
        foreach (var mode in new[] { "valid", "revoked", "stale-projection", "entry-only", "foreign-home", "foreign-project", "swapped-path" })
        {
            using var fixture = await BackendContractFixture.CreateAsync();
            using var current = fixture.EnterCurrent();
            var project = await fixture.GetProjectAsync();
            await fixture.Store.CreateProjectIterationSessionAsync(fixture.AccountId, fixture.ProjectId,
                "manual_feedback", "Inventory prerequisite", "Inventory prerequisite",
                [new ProjectIterationGoalCreateCommand(1, "Done", "Done", "Done")]);
            var goals = await fixture.Store.GetLatestProjectIterationSessionAsync(fixture.ProjectId);
            foreach (var goal in goals!.Goals)
                await fixture.Store.UpdateProjectIterationGoalStatusAsync(goal.GoalId, "succeeded", "Done", DateTimeOffset.UtcNow.ToString("O"));
            var scene = Path.Combine(project.RepoPath, "Game.Godot", "Scenes", "S236Inventory.tscn");
            Directory.CreateDirectory(Path.GetDirectoryName(scene)!);
            await File.WriteAllTextAsync(scene, "[gd_scene format=3]\n[node name=\"Player\" type=\"Sprite2D\"]\n");
            var roles = new HashSet<string> { "entry", "production" };
            NodeProjectMetadata node = new PhaseAMetadataStore(fixture.ConnectionString, fixture.Options with { EnabledRoles = roles });
            var engine = new BlockingRequirementMapLlmEngine("{\"items\":[]}");
            var queue = new HeavyRunnerQueueService(null, HeavyRunnerQueueService.DefaultMaxConcurrentOtherRuns, node);
            var service = new PhaseA.Platform.Readback.ProjectAssetInventoryService(node, fixture.Options,
                new UnexpectedInventoryCodex(), new ProjectWorkspaceSeeder(fixture.Options, fixture.Store),
                engine, queue, new RunCancellationService());
            var operation = service.GetInventoryAsync(fixture.AccountId, fixture.ProjectId, includeLlmJudgement: true, forceRefresh: true);
            await engine.Started.WaitAsync(TimeSpan.FromSeconds(10));
            if (engine.Request?.Purpose != "asset-inventory-judgement" || engine.Request.BillingAccountId != fixture.AccountId)
                throw new InvalidOperationException("Actual inventory model request binding unavailable.");
            Dictionary<string, string> Files() => Directory.EnumerateFiles(project.RepoPath, "*", SearchOption.AllDirectories)
                .ToDictionary(path => Path.GetRelativePath(project.RepoPath, path).Replace(Path.DirectorySeparatorChar, '/'),
                    path => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))), StringComparer.Ordinal);
            var before = Files();
            try { await ApplyOwnedPendingModelFaultAsync(fixture, mode, roles); }
            finally { engine.Release(); }
            var denied = false;
            PhaseA.Platform.Readback.ProjectAssetInventoryResult? result = null;
            try { result = await operation.WaitAsync(TimeSpan.FromSeconds(20)); }
            catch (UnauthorizedAccessException) { denied = true; }
            var after = Files();
            var changed = before.Keys.Union(after.Keys).Where(path =>
                !before.TryGetValue(path, out var left) || !after.TryGetValue(path, out var right) || left != right).Order().ToArray();
            var cache = Path.Combine(project.RepoPath, "_phasea", "asset-inventory-cache.json");
            var cachedReturn = false;
            if (mode == "valid" && result?.CanReadInventory == true)
            {
                var cached = await service.GetInventoryAsync(fixture.AccountId, fixture.ProjectId, includeLlmJudgement: true);
                cachedReturn = cached?.CanReadInventory == true && cached.GenerationCandidates.Count == result.GenerationCandidates.Count;
            }
            rows.Add(new { mode, denied, reachedModel = engine.Started.IsCompletedSuccessfully, calls = engine.CallCount,
                resultReturned = result is not null, canReadInventory = result?.CanReadInventory,
                candidateCount = result?.GenerationCandidates.Count, changed, cacheExists = File.Exists(cache), cachedReturn });
        }
        return rows;
    }

    private static async Task ApplyOwnedPendingModelFaultAsync(BackendContractFixture fixture, string mode, HashSet<string> roles)
    {
            if (mode == "entry-only") roles.Remove("production");
            else if (mode != "valid")
            {
                await using var connection = new SqliteConnection(fixture.ConnectionString);
                await connection.OpenAsync();
                await using var transaction = connection.BeginTransaction();
                var triggers = new List<string>();
                await using (var read = connection.CreateCommand())
                {
                    read.Transaction = transaction;
                    read.CommandText = "SELECT sql FROM sqlite_master WHERE type='trigger' AND name IN ('account_home_immutable','project_node_immutable','account_node_update') ORDER BY name;";
                    await using var reader = await read.ExecuteReaderAsync();
                    while (await reader.ReadAsync()) triggers.Add(reader.GetString(0));
                }
                if (triggers.Count != 3) throw new InvalidOperationException("Owned inventory trigger prerequisites missing.");
                await using var command = connection.CreateCommand();
                command.Transaction = transaction;
                command.CommandText = "DROP TRIGGER account_home_immutable; DROP TRIGGER project_node_immutable; DROP TRIGGER account_node_update;";
                await command.ExecuteNonQueryAsync();
                command.CommandText = mode switch
                {
                    "revoked" => "UPDATE accounts SET is_disabled=1 WHERE id=$account;",
                    "stale-projection" => "UPDATE account_node_projections SET authority_revision=authority_revision+1 WHERE account_id=$account;",
                    "foreign-home" => "UPDATE accounts SET home_node_id='foreign-node' WHERE id=$account;",
                    "foreign-project" => "UPDATE projects SET node_id='foreign-node' WHERE id=$project;",
                    "swapped-path" => "UPDATE workspaces SET repo_path=repo_path||'-unselected' WHERE project_id=$project;",
                    _ => throw new InvalidOperationException("Unknown owned inventory fault.")
                };
                command.Parameters.AddWithValue("$account", fixture.AccountId);
                command.Parameters.AddWithValue("$project", fixture.ProjectId);
                if (await command.ExecuteNonQueryAsync() != 1) throw new InvalidOperationException("Owned inventory fault changed no row.");
                command.Parameters.Clear();
                foreach (var trigger in triggers) { command.CommandText = trigger; await command.ExecuteNonQueryAsync(); }
                var restored = new List<string>();
                command.CommandText = "SELECT sql FROM sqlite_master WHERE type='trigger' AND name IN ('account_home_immutable','project_node_immutable','account_node_update') ORDER BY name;";
                await using (var reader = await command.ExecuteReaderAsync())
                    while (await reader.ReadAsync()) restored.Add(reader.GetString(0));
                if (!triggers.SequenceEqual(restored)) throw new InvalidOperationException("Owned inventory triggers not restored exactly.");
                await transaction.CommitAsync();
            }
    }

    // ADR-0061 AD19/20: actual repair and milestone publications after pending model results.
    internal static async Task<object> ObserveRepairAndMilestoneReplyBoundaryAsync()
    {
        var rows = new List<object>();
        foreach (var family in new[] { "repair-plan", "gdd-next-step-review" })
        foreach (var mode in new[] { "valid", "revoked", "stale-projection", "entry-only", "foreign-home", "foreign-project", "swapped-path" })
        {
            using var fixture = await BackendContractFixture.CreateAsync();
            using var current = fixture.EnterCurrent();
            var project = await fixture.GetProjectAsync();
            var roles = new HashSet<string> { "entry", "production" };
            NodeProjectMetadata node = new PhaseAMetadataStore(fixture.ConnectionString, fixture.Options with { EnabledRoles = roles });
            var queue = new HeavyRunnerQueueService(null, HeavyRunnerQueueService.DefaultMaxConcurrentOtherRuns, node);
            var seeder = new ProjectWorkspaceSeeder(fixture.Options, fixture.Store);
            var runner = new CountingHostedProcessRunner();
            var quickFix = new PrototypeQuickFixService(node, fixture.Options, runner, seeder, new SkillActionCatalog(), heavyRunnerQueue: queue);
            var engine = new BlockingRequirementMapLlmEngine(family == "repair-plan" ? "{}" : "{\"shouldAdjust\":false,\"summary\":\"Boundary control\"}");
            var repair = new PrototypeRepairPlanService(node, quickFix, new PrototypeRouteStateWriter(), llmRouteEngine: engine);
            var milestone = new GddMilestoneStepService(node,
                new PrototypeIterationGoalService(node, fixture.Options, runner, seeder, heavyRunnerQueue: queue),
                new PrototypeNeedsFixRouteService(node, quickFix, new PrototypeRouteStateWriter()), llmRouteEngine: engine);
            string stepId = "";
            if (family == "repair-plan")
            {
                var failure = await fixture.Store.CreateRunAsync(fixture.ProjectId, project.WorkspaceId, "prototype-boundary-source");
                await fixture.Store.CompleteRunAsync(failure, "failed", 1, "", "Ordinary repair boundary input", "{}");
            }
            else
            {
                var gdd = Path.Combine(project.RepoPath, "docs", "gdd", "GDD.md");
                Directory.CreateDirectory(Path.GetDirectoryName(gdd)!);
                await File.WriteAllTextAsync(gdd, "# Two Step GDD\n\nM1: First playable scene and controls.\nM2: Core loop validation and package prompt.\n");
                var plan = await milestone.GetOrCreateLatestAsync(fixture.AccountId, fixture.ProjectId);
                if (plan is null || plan.Steps.Count < 2) throw new InvalidOperationException("Actual two-milestone prerequisite unavailable.");
                stepId = plan!.Steps[0].StepId;
                // Seed a completed-step prerequisite; this is not a Runner/Windows execution claim.
                foreach (var path in new[] { Path.Combine(project.MetaPath, "routes", "gdd-milestones", "latest.json"),
                             Path.Combine(project.RepoPath, "meta", "routes", "gdd-milestones", "latest.json") }.Distinct())
                {
                    var state = JsonNode.Parse(await File.ReadAllTextAsync(path))!;
                    state["steps"]![0]!["status"] = "executed";
                    await File.WriteAllTextAsync(path, state.ToJsonString());
                }
            }
            var returned = false; string? status = null; var count = 0;
            async Task InvokeAsync()
            {
                if (family == "repair-plan")
                {
                    var result = await repair.CreateAsync(fixture.AccountId, fixture.ProjectId);
                    returned = true; status = result.Status; count = result.Goals.Count;
                }
                else
                {
                    var result = await milestone.ConfirmAsync(fixture.AccountId, fixture.ProjectId, stepId,
                        new GddMilestoneStepConfirmRequest("Boundary completed-step control"));
                    returned = result is not null; status = result?.Status; count = result?.Plan?.Steps.Count ?? 0;
                }
            }
            var operation = InvokeAsync();
            await engine.Started.WaitAsync(TimeSpan.FromSeconds(10));
            if (engine.Request?.Purpose != family || engine.Request.OperationKey != "llm:" + family ||
                (family == "repair-plan" && engine.Request.BillingAccountId != fixture.AccountId))
                throw new InvalidOperationException("Actual scoped model request unavailable.");
            Dictionary<string, string> Files()
            {
                var files = new Dictionary<string, string>(StringComparer.Ordinal);
                foreach (var (prefix, root) in new[] { ("repo/", project.RepoPath), ("meta/", project.MetaPath) })
                    foreach (var path in Directory.EnumerateFiles(root, "*", SearchOption.AllDirectories))
                        files[prefix + Path.GetRelativePath(root, path).Replace(Path.DirectorySeparatorChar, '/')] = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path)));
                return files;
            }
            var before = Files();
            async Task<int> CountSessionsAsync()
            {
                await using var connection = new SqliteConnection(fixture.ConnectionString);
                await connection.OpenAsync();
                await using var command = connection.CreateCommand();
                command.CommandText = "SELECT COUNT(*) FROM project_iteration_sessions WHERE project_id=$project;";
                command.Parameters.AddWithValue("$project", fixture.ProjectId);
                return Convert.ToInt32(await command.ExecuteScalarAsync());
            }
            var beforeSessions = await CountSessionsAsync();
            try { await ApplyOwnedPendingModelFaultAsync(fixture, mode, roles); }
            finally { engine.Release(); }
            var denied = false;
            try { await operation.WaitAsync(TimeSpan.FromSeconds(20)); }
            catch (UnauthorizedAccessException) { denied = true; }
            var after = Files();
            var changed = before.Keys.Union(after.Keys).Where(path =>
                !before.TryGetValue(path, out var left) || !after.TryGetValue(path, out var right) || left != right).Order().ToArray();
            var afterSessions = await CountSessionsAsync();
            rows.Add(new { family, mode, denied, returned, status, count, changed,
                reachedModel = engine.Started.IsCompletedSuccessfully, calls = engine.CallCount,
                beforeSessions, afterSessions });
        }
        return rows;
    }

    // ADR-0061: portable caller publication proof only, never native AI/Godot/Windows evidence.
    internal static async Task<object> ObserveAssetAndPreviewPublicationAsync()
    {
        var rows = new List<object>();
        foreach (var family in new[] { "asset-decision", "preview-direct", "preview-queued" })
        foreach (var mode in new[] { "valid", "revoked", "stale-projection", "entry-only", "foreign-home", "foreign-project", "swapped-path" })
        {
            using var fixture = await BackendContractFixture.CreateAsync();
            using var current = fixture.EnterCurrent();
            var project = await fixture.GetProjectAsync();
            var roles = new HashSet<string> { "entry", "production" };
            var options = fixture.Options with { EnabledRoles = roles, WebPreviewSigningSecret = "owned-synthetic-preview-signing-secret" };
            NodeProjectMetadata node = new PhaseAMetadataStore(fixture.ConnectionString, options);
            var queue = new HeavyRunnerQueueService(null, HeavyRunnerQueueService.DefaultMaxConcurrentOtherRuns, node);
            var engine = new BlockingRequirementMapLlmEngine("{\"actionId\":\"character-making-master\"}");
            var imageRunner = new OwnedImageArtifactStub();
            var assets = new ProjectAssetLibraryService(node, options, CreateOwnedImageGenerator(options, imageRunner, node),
                engine, queue, processRunner: imageRunner);
            var exportRunner = new PendingExportBoundaryRunner();
            var previews = new ProjectWebPreviewService(node, (NodePreviewRuntime)options, queue,
                new ProjectWebPreviewConcurrencyLimiter(1), exportRunner);
            var fakeGodot = Path.Combine(options.RepositoryRoot, "owned-export-provider.bin");
            await File.WriteAllTextAsync(fakeGodot, "Only a provider boundary stub; never executed.");
            var previousGodot = Environment.GetEnvironmentVariable("PHASEA_GODOT3_BIN");
            Environment.SetEnvironmentVariable("PHASEA_GODOT3_BIN", fakeGodot);
            try
            {
                const string packageFile = "S236Preview-v0.1.20261102.001.zip";
                WriteBoundaryGodotPackage(project.RepoPath, packageFile);
                var scene = Path.Combine(project.RepoPath, "Game.Godot", "Scenes", "S236Asset.tscn");
                Directory.CreateDirectory(Path.GetDirectoryName(scene)!);
                await File.WriteAllTextAsync(scene, "[gd_scene format=3]\n[node name=\"Player\" type=\"Sprite2D\"]\n");
                Dictionary<string, string> Files() => Directory.EnumerateFiles(project.RepoPath, "*", SearchOption.AllDirectories)
                    .ToDictionary(path => Path.GetRelativePath(project.RepoPath, path).Replace(Path.DirectorySeparatorChar, '/'),
                        path => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))), StringComparer.Ordinal);
                HashSet<string> Dirs() => Directory.EnumerateDirectories(project.RepoPath, "*", SearchOption.AllDirectories)
                    .Select(path => Path.GetRelativePath(project.RepoPath, path).Replace(Path.DirectorySeparatorChar, '/')).ToHashSet(StringComparer.Ordinal);
                var original = Files();
                var returned = false; var published = false; string? status = null;
                async Task InvokeAsync()
                {
                    if (family == "asset-decision")
                    {
                        var result = await assets.GenerateAsync(fixture.AccountId, fixture.ProjectId,
                            new ProjectAssetGenerationRunRequest("Owned caller boundary", new ProjectAssetUnitRequest(
                                "s236-owned", "Player", "Sprite2D", "res://Game.Godot/Scenes/S236Asset.tscn", null,
                                "sprite", "Player sprite", "Caller boundary control")));
                        returned = result is not null; status = result?.Status;
                        published = result?.Status == "succeeded" && result.Entry.ArtifactPaths.Count > 0 && result.Library.Units.Count > 0;
                    }
                    else
                    {
                        ProjectWebPreviewResult result;
                        if (family == "preview-queued")
                        {
                            var queued = await previews.QueuePreviewAsync(fixture.AccountId, fixture.ProjectId, packageFile);
                            result = await previews.GenerateQueuedPreviewAsync(fixture.AccountId, fixture.ProjectId, packageFile, queued.RunId);
                        }
                        else result = await previews.GeneratePreviewAsync(fixture.AccountId, fixture.ProjectId, packageFile);
                        returned = true; status = result.Status;
                        published = result.Status == "succeeded" && !string.IsNullOrWhiteSpace(result.PreviewUrl);
                    }
                }
                var operation = InvokeAsync();
                await (family == "asset-decision" ? engine.Started : exportRunner.Started).WaitAsync(TimeSpan.FromSeconds(10));
                if (family == "asset-decision" && (engine.Request?.Purpose != "project-asset-library-skill-selection" || engine.Request.BillingAccountId != fixture.AccountId))
                    throw new InvalidOperationException("Actual asset decision request unavailable.");
                var before = Files(); var beforeDirs = Dirs();
                try { await ApplyOwnedPendingModelFaultAsync(fixture, mode, roles); }
                finally { engine.Release(); exportRunner.Release(); }
                var denied = false;
                try { await operation.WaitAsync(TimeSpan.FromSeconds(20)); }
                catch (UnauthorizedAccessException) { denied = true; }
                var after = Files();
                var addedOrChanged = after.Where(pair => !before.TryGetValue(pair.Key, out var old) || old != pair.Value).Select(pair => pair.Key).Order().ToArray();
                var newDirectories = Dirs().Except(beforeDirs).Order().ToArray();
                var originalsUnchanged = original.All(pair => after.TryGetValue(pair.Key, out var value) && value == pair.Value);
                rows.Add(new { family, mode, denied, returned, published, status, addedOrChanged, newDirectories,
                    originalsUnchanged, modelCalls = engine.CallCount, imageCalls = imageRunner.Calls, exportCalls = exportRunner.Calls,
                    boundaryReached = family == "asset-decision" ? engine.Started.IsCompletedSuccessfully : exportRunner.Started.IsCompletedSuccessfully,
                    nativeWindowsOrProviderEvidence = false });
            }
            finally { Environment.SetEnvironmentVariable("PHASEA_GODOT3_BIN", previousGodot); }
        }
        return rows;
    }

    // ADR-0061 AD19/20: the actual import and selection continuations retain current authority.
    internal static async Task<object> ObserveAssetImportAndSelectionAsync()
    {
        var rows = new List<object>();
        foreach (var family in new[] { "asset-import", "asset-import-stream", "asset-import-read", "asset-selection" })
        foreach (var mode in new[] { "valid", "revoked", "stale-projection", "entry-only", "foreign-home", "foreign-project", "swapped-path" })
        {
            var isImport = family.StartsWith("asset-import", StringComparison.Ordinal);
            using var fixture = await BackendContractFixture.CreateAsync();
            using var current = fixture.EnterCurrent();
            var project = await fixture.GetProjectAsync();
            var roles = new HashSet<string> { "entry", "production" };
            var options = fixture.Options with { EnabledRoles = roles, GodotBin = "owned-smoke-provider",
                AssetAllowedUrlPrefixes = new[] { "https://assets.example.invalid/" } };
            NodeProjectMetadata node = new PhaseAMetadataStore(fixture.ConnectionString, options);
            var queue = new HeavyRunnerQueueService(null, HeavyRunnerQueueService.DefaultMaxConcurrentOtherRuns, node);
            var engine = new BlockingRequirementMapLlmEngine("{\"actionId\":\"character-making-master\"}");
            engine.Release();
            var imageRunner = new OwnedImageArtifactStub();
            var smoke = new PendingSelectionSmokeRunner();
            using var handler = new PendingOwnedAssetHandler(family);
            using var http = new HttpClient(handler);
            var assets = new ProjectAssetLibraryService(node, options, CreateOwnedImageGenerator(options, imageRunner, node),
                engine, queue, httpClient: http, processRunner: smoke);
            var scene = Path.Combine(project.RepoPath, "Game.Godot", "Scenes", "S236Decoration.tscn");
            Directory.CreateDirectory(Path.GetDirectoryName(scene)!);
            await File.WriteAllTextAsync(scene, "[gd_scene format=3]\n[node name=\"Decoration\" type=\"Sprite2D\"]\n");
            var unit = new ProjectAssetUnitRequest("s236-decoration", "Decoration", "Sprite2D",
                "res://Game.Godot/Scenes/S236Decoration.tscn", null, "sprite", "Background decoration", "Continuation control");
            string? entryId = null;
            string? unitKey = null;
            if (family == "asset-selection")
            {
                var generated = await assets.GenerateAsync(fixture.AccountId, fixture.ProjectId,
                    new ProjectAssetGenerationRunRequest("Owned selected decoration", unit));
                if (generated?.Status != "succeeded" || generated.Entry.ArtifactPaths.Count == 0)
                    throw new InvalidOperationException("Actual selection prerequisite did not generate an owned artifact.");
                entryId = generated.Entry.EntryId;
                unitKey = generated.Library.Units.Single().Key;
            }
            var initialPaths = Directory.EnumerateFiles(project.RepoPath, "*", SearchOption.AllDirectories).ToHashSet(StringComparer.Ordinal);
            var pausedEmptyFiles = new HashSet<string>(StringComparer.Ordinal);
            string HashOwnedFile(string path)
            {
                try { return Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))); }
                catch (IOException) when (family == "asset-import-read" && handler.BodyStarted.IsCompletedSuccessfully
                    && !handler.BodyReleased && !initialPaths.Contains(path) && new FileInfo(path).Length == 0
                    && path.StartsWith(Path.Combine(project.RepoPath, "logs", "prototype-evidence", project.ProjectId) + Path.DirectorySeparatorChar, StringComparison.Ordinal)
                    && path.EndsWith(Path.Combine("asset-quarantine", "owned.png"), StringComparison.Ordinal))
                {
                    // The real writer is paused before its first read. This first-created owned file has exactly zero bytes.
                    pausedEmptyFiles.Add(Path.GetRelativePath(project.RepoPath, path));
                    return Convert.ToHexString(SHA256.HashData(Array.Empty<byte>()));
                }
            }
            Dictionary<string, string> Files() => Directory.EnumerateFiles(project.RepoPath, "*", SearchOption.AllDirectories)
                .ToDictionary(path => Path.GetRelativePath(project.RepoPath, path).Replace(Path.DirectorySeparatorChar, '/'),
                    HashOwnedFile, StringComparer.Ordinal);
            var returned = false; var published = false; string? status = null;
            async Task InvokeAsync()
            {
                if (isImport)
                {
                    var result = await assets.ImportAsync(fixture.AccountId, fixture.ProjectId,
                        new ProjectAssetImportRequest("https://assets.example.invalid/owned.png", unit));
                    returned = result is not null; status = result?.Status;
                    published = result?.Status == "imported" && result.SourceUrlAllowed && result.Entry.ArtifactPaths.Count > 0;
                }
                else
                {
                    var result = await assets.SelectAsync(fixture.AccountId, fixture.ProjectId,
                        new ProjectAssetSelectionRequest(unitKey!, entryId!, true));
                    returned = result is not null;
                    var selected = result?.Units.Single().Entries.Single(e => e.EntryId == entryId);
                    status = selected?.SelectionValidation?.Status;
                    published = selected?.Selected == true && status == "smoke_passed";
                }
            }
            var operation = InvokeAsync();
            await (isImport ? (family == "asset-import" ? handler.Started : handler.BodyStarted) : smoke.Started).WaitAsync(TimeSpan.FromSeconds(10));
            var before = Files();
            try { await ApplyOwnedPendingModelFaultAsync(fixture, mode, roles); }
            finally { handler.Release(); handler.ReleaseBody(); smoke.Release(); }
            var denied = false;
            try { await operation.WaitAsync(TimeSpan.FromSeconds(20)); }
            catch (UnauthorizedAccessException) { denied = true; }
            var after = Files();
            var changed = after.Where(pair => !before.TryGetValue(pair.Key, out var old) || old != pair.Value).Select(pair => pair.Key).Order().ToArray();
            var removed = before.Keys.Except(after.Keys).Order().ToArray();
            rows.Add(new { family, mode, returned, denied, published, status, changed, removed,
                httpCalls = handler.Calls, smokeCalls = smoke.Calls, imageCalls = imageRunner.Calls, pausedEmptyFiles = pausedEmptyFiles.Order().ToArray(),
                boundaryReached = isImport ? (family == "asset-import" ? handler.Started : handler.BodyStarted).IsCompletedSuccessfully : smoke.Started.IsCompletedSuccessfully,
                externalProviderOrWindowsEvidence = false });
        }
        return rows;
    }

    private sealed class PendingSelectionSmokeRunner : IHostedProcessRunner
    {
        private readonly TaskCompletionSource _started = new(TaskCreationOptions.RunContinuationsAsynchronously);
        private readonly TaskCompletionSource _release = new(TaskCreationOptions.RunContinuationsAsynchronously);
        internal Task Started => _started.Task;
        internal int Calls { get; private set; }
        internal void Release() => _release.TrySetResult();
        public async Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            if (!command.Arguments.Any(arg => arg.EndsWith("smoke_headless.py", StringComparison.Ordinal)))
                throw new InvalidOperationException("Unexpected owned selection provider command.");
            Calls++; _started.TrySetResult();
            await _release.Task.WaitAsync(cancellationToken);
            return new HostedProcessResult(0, "Owned successful smoke callback only; not actual Godot evidence", "");
        }
    }

    private sealed class PendingOwnedAssetHandler(string family) : HttpMessageHandler
    {
        private readonly TaskCompletionSource _started = new(TaskCreationOptions.RunContinuationsAsynchronously);
        private readonly TaskCompletionSource _release = new(TaskCreationOptions.RunContinuationsAsynchronously);
        private readonly PendingOwnedAssetContent _body = new(family);
        internal Task Started => _started.Task;
        internal Task BodyStarted => _body.Started;
        internal bool BodyReleased => _body.Released;
        internal int Calls { get; private set; }
        internal void Release() => _release.TrySetResult();
        internal void ReleaseBody() => _body.Release();
        protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            if (request.RequestUri?.AbsoluteUri != "https://assets.example.invalid/owned.png")
                throw new InvalidOperationException("Unexpected owned import URL.");
            Calls++;
            if (family == "asset-import")
            {
                _started.TrySetResult();
                await _release.Task.WaitAsync(cancellationToken);
            }
            return new HttpResponseMessage(System.Net.HttpStatusCode.OK) { RequestMessage = request,
                Content = family == "asset-import" ? new ByteArrayContent(PendingOwnedAssetContent.Bytes) : _body };
        }
    }

    private sealed class PendingOwnedAssetContent(string family) : HttpContent
    {
        internal static readonly byte[] Bytes = Convert.FromBase64String("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j2N8AAAAASUVORK5CYII=");
        private readonly TaskCompletionSource _started = new(TaskCreationOptions.RunContinuationsAsynchronously);
        private readonly TaskCompletionSource _release = new(TaskCreationOptions.RunContinuationsAsynchronously);
        internal Task Started => _started.Task;
        internal bool Released => _release.Task.IsCompleted;
        internal void Release() => _release.TrySetResult();
        internal async Task WaitForReadAsync(CancellationToken token)
        {
            _started.TrySetResult();
            await _release.Task.WaitAsync(token);
        }
        protected override bool TryComputeLength(out long length) { length = Bytes.Length; return true; }
        protected override Task SerializeToStreamAsync(Stream stream, System.Net.TransportContext? context)
            => throw new InvalidOperationException("Owned import must reach the actual read-stream boundary.");
        protected override Task<Stream> CreateContentReadStreamAsync() => CreateStreamAsync(CancellationToken.None);
        protected override Task<Stream> CreateContentReadStreamAsync(CancellationToken token) => CreateStreamAsync(token);
        private async Task<Stream> CreateStreamAsync(CancellationToken token)
        {
            if (family == "asset-import-stream") await WaitForReadAsync(token);
            return family == "asset-import-read" ? new PendingOwnedAssetReadStream(this) : new MemoryStream(Bytes, writable: false);
        }
    }

    private sealed class PendingOwnedAssetReadStream(PendingOwnedAssetContent owner) : MemoryStream(PendingOwnedAssetContent.Bytes, writable: false)
    {
        public override async ValueTask<int> ReadAsync(Memory<byte> buffer, CancellationToken cancellationToken = default)
        {
            await owner.WaitForReadAsync(cancellationToken);
            return await base.ReadAsync(buffer, cancellationToken);
        }
    }

    private static ProjectAssetImageGenerator CreateOwnedImageGenerator(NodeExecutionOptions options, IHostedProcessRunner runner, NodeProjectMetadata node)
    {
        var guarded = typeof(ProjectAssetImageGenerator).GetConstructor(new[] { typeof(NodeExecutionOptions), typeof(IHostedProcessRunner), typeof(NodeProjectMetadata) });
        return guarded is null ? new ProjectAssetImageGenerator(options, runner)
            : (ProjectAssetImageGenerator)guarded.Invoke(new object?[] { options, runner, node });
    }

    private static ProjectWebPreviewSemanticAdapterService CreateOwnedSemanticProducer(NodeExecutionOptions options, IHostedProcessRunner runner, NodeProjectMetadata node)
    {
        var guarded = typeof(ProjectWebPreviewSemanticAdapterService).GetConstructors()
            .SingleOrDefault(c => c.GetParameters().Length == 7 && c.GetParameters()[6].ParameterType == typeof(NodeProjectMetadata));
        return guarded is null ? new ProjectWebPreviewSemanticAdapterService(options, runner)
            : (ProjectWebPreviewSemanticAdapterService)guarded.Invoke(new object?[] { options, runner, null, null, null, null, node });
    }

    private static ProjectWebPreviewDedicatedAdapterService CreateOwnedDedicatedProducer(NodeExecutionOptions options, IHostedProcessRunner runner, NodeProjectMetadata node)
    {
        var guarded = typeof(ProjectWebPreviewDedicatedAdapterService).GetConstructors()
            .SingleOrDefault(c => c.GetParameters().Length == 7 && c.GetParameters()[6].ParameterType == typeof(NodeProjectMetadata));
        return guarded is null ? new ProjectWebPreviewDedicatedAdapterService(options, runner)
            : (ProjectWebPreviewDedicatedAdapterService)guarded.Invoke(new object?[] { options, runner, null, null, null, null, node });
    }

    // ADR-0061 AD19/20: child producers must not publish after a pending process loses current authority.
    internal static async Task<object> ObserveChildProducerPublicationAsync()
    {
        var rows = new List<object>();
        foreach (var family in new[] { "image-sidecar", "semantic-fallback", "dedicated-adapter" })
        foreach (var mode in new[] { "valid", "revoked", "stale-projection", "entry-only", "foreign-home", "foreign-project", "swapped-path" })
        {
            using var fixture = await BackendContractFixture.CreateAsync();
            using var current = fixture.EnterCurrent();
            var project = await fixture.GetProjectAsync();
            var roles = new HashSet<string> { "entry", "production" };
            var options = fixture.Options with { EnabledRoles = roles };
            NodeProjectMetadata node = new PhaseAMetadataStore(fixture.ConnectionString, options);
            var runId = await node.CreateRunAsync(project.ProjectId, project.WorkspaceId, "owned-child-producer");
            var runner = new PendingChildArtifactRunner(family);
            var images = CreateOwnedImageGenerator(options, runner, node);
            var semantic = CreateOwnedSemanticProducer(options, runner, node);
            var dedicated = CreateOwnedDedicatedProducer(options, runner, node);
            Dictionary<string, string> Files() => Directory.EnumerateFiles(project.RepoPath, "*", SearchOption.AllDirectories)
                .ToDictionary(path => Path.GetRelativePath(project.RepoPath, path).Replace(Path.DirectorySeparatorChar, '/'),
                    path => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))), StringComparer.Ordinal);
            var returned = false; var published = false; string? status = null;
            async Task InvokeAsync()
            {
                const string package = "S236Child-v0.1.20261102.001.zip";
                if (family == "image-sidecar")
                {
                    const string relative = "meta/s236-owned-image";
                    var result = await images.GenerateAsync(project, runId, "Owned producer continuation",
                        Path.Combine(project.RepoPath, relative.Replace('/', Path.DirectorySeparatorChar)), relative, "owned");
                    returned = true; status = result.Status;
                    published = result.Status == "succeeded" && File.Exists(Path.Combine(project.RepoPath, relative, "direct-generation-result.json"));
                }
                else if (family == "semantic-fallback")
                {
                    var result = await semantic.ResolveAsync(new ProjectWebPreviewSemanticAdapterRequest(fixture.AccountId, runId,
                        project, project.RepoPath, package, "owned-package-hash", 1, "Owned Game", "Owned source", "rpg", "Owned guide",
                        "res://Main.tscn", new[] { "res://Main.tscn" }, "{}", "{}"));
                    returned = true; status = result.Status;
                    published = result.Status == "generated_by_fallback" && File.Exists(result.AdapterPath);
                }
                else
                {
                    var result = await dedicated.ResolveAsync(new ProjectWebPreviewDedicatedAdapterRequest(fixture.AccountId, runId,
                        project, project.RepoPath, package, "owned-package-hash", "Owned Project", "Owned Game", "rpg", "Owned guide",
                        "owned-converter", "owned-mode", "res://Main.tscn", new[] { "res://Main.tscn" }, "{}", "{}", "{}"),
                        "extends Node\nfunc _ready():\n    pass\n");
                    returned = true; status = result.Resolution.Status;
                    published = result.Resolution.Status == "generated_by_codex" && File.Exists(result.AdapterPath);
                }
            }
            var operation = InvokeAsync();
            await runner.Started.WaitAsync(TimeSpan.FromSeconds(10));
            var before = Files();
            try { await ApplyOwnedPendingModelFaultAsync(fixture, mode, roles); }
            finally { runner.Release(); }
            var denied = false;
            try { await operation.WaitAsync(TimeSpan.FromSeconds(20)); }
            catch (UnauthorizedAccessException) { denied = true; }
            var after = Files();
            var changed = after.Where(pair => !before.TryGetValue(pair.Key, out var old) || old != pair.Value).Select(pair => pair.Key).Order().ToArray();
            var removed = before.Keys.Except(after.Keys).Order().ToArray();
            rows.Add(new { family, mode, denied, returned, published, status, changed, removed, calls = runner.Calls,
                boundaryReached = runner.Started.IsCompletedSuccessfully, realProviderOrWindowsEvidence = false });
        }
        return rows;
    }

    private sealed class PendingChildArtifactRunner(string family) : IHostedProcessRunner
    {
        private readonly TaskCompletionSource _started = new(TaskCreationOptions.RunContinuationsAsynchronously);
        private readonly TaskCompletionSource _release = new(TaskCreationOptions.RunContinuationsAsynchronously);
        internal Task Started => _started.Task;
        internal int Calls { get; private set; }
        internal void Release() => _release.TrySetResult();
        public async Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Calls++;
            if (family == "image-sidecar")
                await new OwnedImageArtifactStub().RunAsync(command, cancellationToken);
            _started.TrySetResult();
            await _release.Task.WaitAsync(cancellationToken);
            // A real failed provider result exercises semantic fallback; no external model/process is started by this stub.
            return family == "semantic-fallback" ? new HostedProcessResult(1, "{}", "Owned provider failure")
                : new HostedProcessResult(0, "extends Node\nfunc _ready():\n    pass\n", "");
        }
    }

    private sealed class OwnedImageArtifactStub : IHostedProcessRunner
    {
        internal int Calls { get; private set; }
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Calls++;
            var args = command.Arguments.ToList();
            var path = args[args.IndexOf("--out") + 1];
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            File.WriteAllBytes(path, Convert.FromBase64String("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j2N8AAAAASUVORK5CYII="));
            return Task.FromResult(new HostedProcessResult(0, "Owned image artifact stub only", ""));
        }
    }

    private sealed class PendingExportBoundaryRunner : IHostedProcessRunner
    {
        private readonly OwnedExportArtifactStub _stub = new();
        private readonly TaskCompletionSource _started = new(TaskCreationOptions.RunContinuationsAsynchronously);
        private readonly TaskCompletionSource _release = new(TaskCreationOptions.RunContinuationsAsynchronously);
        internal Task Started => _started.Task;
        internal int Calls => _stub.Commands.Count;
        internal void Release() => _release.TrySetResult();
        public async Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            // All provider-owned outputs precede the fault. Only caller continuation can change them afterward.
            var result = await _stub.RunAsync(command, cancellationToken);
            _started.TrySetResult();
            await _release.Task.WaitAsync(cancellationToken);
            return result;
        }
    }

    private static void AddBoundaryZipEntry(ZipArchive archive, string path, string content)
    {
        using var writer = new StreamWriter(archive.CreateEntry(path).Open(), new UTF8Encoding(false));
        writer.Write(content);
    }

    private static void WriteBoundaryGodotPackage(string projectRoot, string packageFile)
    {
        var packagePath = Path.Combine(projectRoot, "exports", packageFile);
        Directory.CreateDirectory(Path.GetDirectoryName(packagePath)!);
        using var stream = File.Create(packagePath);
        using var archive = new ZipArchive(stream, ZipArchiveMode.Create);
        AddBoundaryZipEntry(archive, "PACKAGE-MANIFEST.json", """
        {
          "package_version": "v0.1.20260627.001",
          "project_name": "Towerdemo2",
          "game_name": "Towerdemo2",
          "game_type_source": "Phantom Tower"
        }
        """);
        AddBoundaryZipEntry(archive, "project.godot", """
        config_version=5

        [application]
        config/name="Towerdemo2"
        run/main_scene="res://Game.Godot/Prototypes/Towerdemo2/Towerdemo2Prototype.tscn"
        """);
    }

    private sealed class OwnedExportArtifactStub : IHostedProcessRunner
    {
        public List<HostedProcessCommand> Commands { get; } = [];
        public List<string> MainScripts { get; } = [];
        public List<string> MainScenes { get; } = [];

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Commands.Add(command);
            MainScripts.Add(File.ReadAllText(Path.Combine(command.WorkingDirectory, "Main.gd"), Encoding.UTF8));
            MainScenes.Add(File.ReadAllText(Path.Combine(command.WorkingDirectory, "Main.tscn"), Encoding.UTF8));
            var outputPath = command.Arguments.Last();
            var webRoot = Path.GetDirectoryName(outputPath)!;
            Directory.CreateDirectory(webRoot);
            File.WriteAllText(Path.Combine(webRoot, "index.html"), """
            <!DOCTYPE html>
            <html>
            <head>
                <style>
            		#status-progress-inner {
            			height: 100%;
            		}
                </style>
            </head>
            <body>
                <div id='status-progress' style='display: none;' oncontextmenu='event.preventDefault();'><div id ='status-progress-inner'></div></div>
                <script type='text/javascript' src='index.js'></script>
                <script type='text/javascript'>
                    const GODOT_CONFIG = {"args":[],"canvasResizePolicy":2,"executable":"index","fileSizes":{"index.pck":10,"index.wasm":20}};
                    var engine = new Engine(GODOT_CONFIG);
                    (function() {
            			var statusProgressInner = document.getElementById('status-progress-inner');
            			var statusIndeterminate = document.getElementById('status-indeterminate');
            			var initializing = true;
            			var statusMode = 'hidden';
            			[statusProgress, statusIndeterminate, statusNotice].forEach(elem => {
            			});
            			statusProgress.style.display = 'block';
            						break;
            			statusIndeterminate.style.display = 'block';
            						animationCallbacks.push(animateStatusIndeterminate);
            			statusProgressInner.style.width = current/total * 100 + '%';
            							setStatusMode('progress');
            			setStatusMode('hidden');
            					initializing = false;
                    })();
                </script>
            </body>
            </html>
            """, Encoding.UTF8);
            File.WriteAllText(Path.Combine(webRoot, "index.js"), """
            const Preloader = function () {
                this.preload = function (pathOrBuffer, destPath, fileSize) {};
                this.loadPromise = function (file, fileSize, raw = false) {};
            };
            const InternalConfig = function (initConfig) { // eslint-disable-line no-unused-vars
            };
            Config.prototype.getModuleConfig = function (loadPath, response) {
                return {
                        'locateFile': function (path) {
                            if (path.endsWith('.worker.js')) {
                                return `${loadPath}.worker.js`;
                            } else if (path.endsWith('.audio.worklet.js')) {
                                return `${loadPath}.audio.worklet.js`;
                            } else if (path.endsWith('.js')) {
                                return `${loadPath}.js`;
                            } else if (path.endsWith('.side.wasm')) {
                                return `${loadPath}.side.wasm`;
                            } else if (path.endsWith('.wasm')) {
                                return `${loadPath}.wasm`;
                            }
                            return path;
                        },
                    };
            };
            const Engine = (function () {
                const preloader = new Preloader();
                let loadPromise = null;
                let loadPath = '';
                Engine.load = function (basePath, size) {
                    if (loadPromise == null) {
                        loadPath = basePath;
                        loadPromise = preloader.loadPromise(`${loadPath}.wasm`, size, true);
                    }
                };
                const proto = {
                        preloadFile: function (file, path) {
                            return preloader.preload(file, path, this.config.fileSizes[file]);
                        },
                };
            }());
            """, Encoding.UTF8);
            File.WriteAllBytes(Path.Combine(webRoot, "index.wasm"), [0]);
            File.WriteAllBytes(Path.Combine(webRoot, "index.pck"), [0]);
            return Task.FromResult(new HostedProcessResult(0, "fake export ok", ""));
        }
    }

    private sealed class UnexpectedInventoryCodex : ICodexChatClient
    {
        public Task<CodexChatClientResult> CompleteAsync(string projectRoot, string model, string prompt,
            CodexChatClientOptions? options = null, string? billingApiKeyName = null, CancellationToken cancellationToken = default)
            => throw new InvalidOperationException("Explicit inventory LLM engine was bypassed.");
    }

    // ADR-0061 AD19/20: actual planning model failures cannot return under expired project authority.
    internal static async Task<object> ObserveIterationPlanReplyBoundaryAsync()
    {
        var rows = new List<object>();
        foreach (var reply in new[] { "empty-json", "malformed-json" })
        foreach (var mode in new[] { "valid", "revoked", "stale-projection", "entry-only", "foreign-home", "foreign-project", "swapped-path" })
        {
            using var fixture = await BackendContractFixture.CreateAsync();
            using var current = fixture.EnterCurrent();
            var project = await fixture.GetProjectAsync();
            var roles = new HashSet<string> { "entry", "production" };
            NodeProjectMetadata node = new PhaseAMetadataStore(fixture.ConnectionString, fixture.Options with { EnabledRoles = roles });
            var engine = new BlockingRequirementMapLlmEngine(reply == "empty-json" ? "{}" : "{broken");
            var planner = new PrototypeIterationPlanService(node, new PrototypeRouteStateWriter(), llmRouteEngine: engine);
            var operation = planner.CreateAsync(fixture.AccountId, fixture.ProjectId,
                new PrototypeIterationPlanRequest("Complete field movement and HUD feedback.", "manual_feedback"));
            await engine.Started.WaitAsync(TimeSpan.FromSeconds(10));
            if (engine.Request?.Purpose != "goal-plan" || engine.Request.OperationKey != "llm:goal-plan" ||
                engine.Request.BillingAccountId != fixture.AccountId)
                throw new InvalidOperationException("Actual iteration-plan model request binding unavailable.");
            Dictionary<string, string> Files() => Directory.EnumerateFiles(project.RepoPath, "*", SearchOption.AllDirectories)
                .ToDictionary(path => Path.GetRelativePath(project.RepoPath, path).Replace(Path.DirectorySeparatorChar, '/'),
                    path => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))), StringComparer.Ordinal);
            var before = Files();
            var beforeSessions = await fixture.Store.ListProjectIterationSessionsAsync(fixture.ProjectId);
            try
            {
                if (mode == "entry-only") roles.Remove("production");
                else if (mode != "valid")
                {
                    await using var connection = new SqliteConnection(fixture.ConnectionString);
                    await connection.OpenAsync();
                    await using var transaction = connection.BeginTransaction();
                    var triggers = new List<string>();
                    await using (var read = connection.CreateCommand())
                    {
                        read.Transaction = transaction;
                        read.CommandText = "SELECT sql FROM sqlite_master WHERE type='trigger' AND name IN ('account_home_immutable','project_node_immutable','account_node_update') ORDER BY name;";
                        await using var reader = await read.ExecuteReaderAsync();
                        while (await reader.ReadAsync()) triggers.Add(reader.GetString(0));
                    }
                    if (triggers.Count != 3) throw new InvalidOperationException("Owned planning immutable-trigger prerequisites missing.");
                    await using var command = connection.CreateCommand();
                    command.Transaction = transaction;
                    // Existing disposable-fault protocol: restore exact production triggers before consumer resumes.
                    command.CommandText = "DROP TRIGGER account_home_immutable; DROP TRIGGER project_node_immutable; DROP TRIGGER account_node_update;";
                    await command.ExecuteNonQueryAsync();
                    command.CommandText = mode switch
                    {
                        "revoked" => "UPDATE accounts SET is_disabled=1 WHERE id=$account;",
                        "stale-projection" => "UPDATE account_node_projections SET authority_revision=authority_revision+1 WHERE account_id=$account;",
                        "foreign-home" => "UPDATE accounts SET home_node_id='foreign-node' WHERE id=$account;",
                        "foreign-project" => "UPDATE projects SET node_id='foreign-node' WHERE id=$project;",
                        "swapped-path" => "UPDATE workspaces SET repo_path=repo_path||'-unselected' WHERE project_id=$project;",
                        _ => throw new InvalidOperationException("Unknown owned planning fault.")
                    };
                    command.Parameters.AddWithValue("$account", fixture.AccountId);
                    command.Parameters.AddWithValue("$project", fixture.ProjectId);
                    if (await command.ExecuteNonQueryAsync() != 1)
                        throw new InvalidOperationException("Owned planning fault changed no row.");
                    command.Parameters.Clear();
                    foreach (var trigger in triggers) { command.CommandText = trigger; await command.ExecuteNonQueryAsync(); }
                    var restored = new List<string>();
                    command.CommandText = "SELECT sql FROM sqlite_master WHERE type='trigger' AND name IN ('account_home_immutable','project_node_immutable','account_node_update') ORDER BY name;";
                    await using (var reader = await command.ExecuteReaderAsync())
                        while (await reader.ReadAsync()) restored.Add(reader.GetString(0));
                    if (!triggers.SequenceEqual(restored)) throw new InvalidOperationException("Owned planning triggers were not restored exactly.");
                    await transaction.CommitAsync();
                }
            }
            finally { engine.Release(); }
            var denied = false;
            PrototypeIterationPlanResult? result = null;
            try { result = await operation.WaitAsync(TimeSpan.FromSeconds(20)); }
            catch (UnauthorizedAccessException) { denied = true; }
            var after = Files();
            var changed = before.Keys.Union(after.Keys).Where(path =>
                !before.TryGetValue(path, out var left) || !after.TryGetValue(path, out var right) || left != right).Order().ToArray();
            var afterSessions = await fixture.Store.ListProjectIterationSessionsAsync(fixture.ProjectId);
            rows.Add(new { reply, mode, denied, reachedModel = engine.Started.IsCompletedSuccessfully,
                calls = engine.CallCount, resultReturned = result is not null, status = result?.Status,
                changed, beforeSessions = beforeSessions.Count, afterSessions = afterSessions.Count });
        }
        return rows;
    }

    // ADR-0061 AD19/20: every backfill entry must guard before source dispatch or cached return.
    internal static async Task<object> ObserveGameTypeBackfillEntriesAsync()
    {
        var rows = new List<object>();
        foreach (var entry in new[] { "existing", "resolve", "refresh" })
        foreach (var mode in new[] { "valid", "entry-only", "revoked", "stale-projection", "foreign-home", "foreign-project", "swapped-path", "no-context", "forged-context" })
        {
            using var fixture = await BackendContractFixture.CreateAsync();
            var original = await fixture.GetProjectAsync();
            if (entry == "resolve")
                await fixture.Store.UpdateProjectGameTypeMatchAsync(fixture.ProjectId,
                    ProjectGameTypeMatchEvidence.Empty("not_resolved").ToJson());
            var project = await fixture.GetProjectAsync();
            var before = project.GameTypeMatchJson;
            var roles = new HashSet<string> { "entry", "production" };
            NodeProjectMetadata node = new PhaseAMetadataStore(fixture.ConnectionString, fixture.Options with { EnabledRoles = roles });
            var matcher = new BackfillObservationMatcher(ProjectGameTypeMatchEvidence.FromJson(original.GameTypeMatchJson));
            var service = new ProjectGameTypeMatchBackfillService(node, matcher, fixture.Options);
            if (mode == "entry-only") roles.Remove("production");
            else if (mode is not ("valid" or "no-context" or "forged-context"))
            {
                await using var connection = new SqliteConnection(fixture.ConnectionString);
                await connection.OpenAsync();
                await using var transaction = connection.BeginTransaction();
                var triggers = new List<string>();
                await using (var read = connection.CreateCommand())
                {
                    read.Transaction = transaction;
                    read.CommandText = "SELECT sql FROM sqlite_master WHERE type='trigger' AND name IN ('account_home_immutable','project_node_immutable','account_node_update') ORDER BY name;";
                    await using var reader = await read.ExecuteReaderAsync();
                    while (await reader.ReadAsync()) triggers.Add(reader.GetString(0));
                }
                if (triggers.Count != 3) throw new InvalidOperationException("Owned backfill trigger prerequisites missing.");
                await using var command = connection.CreateCommand(); command.Transaction = transaction;
                command.CommandText = "DROP TRIGGER account_home_immutable; DROP TRIGGER project_node_immutable; DROP TRIGGER account_node_update;";
                await command.ExecuteNonQueryAsync();
                command.CommandText = mode switch
                {
                    "revoked" => "UPDATE accounts SET is_disabled=1 WHERE id=$account;",
                    "stale-projection" => "UPDATE account_node_projections SET authority_revision=authority_revision+1 WHERE account_id=$account;",
                    "foreign-home" => "UPDATE accounts SET home_node_id='foreign-node' WHERE id=$account;",
                    "foreign-project" => "UPDATE projects SET node_id='foreign-node' WHERE id=$project;",
                    "swapped-path" => "UPDATE workspaces SET repo_path=repo_path||'-unselected' WHERE project_id=$project;",
                    _ => throw new InvalidOperationException("Unknown owned backfill fault.")
                };
                command.Parameters.AddWithValue("$account", fixture.AccountId);
                command.Parameters.AddWithValue("$project", fixture.ProjectId);
                if (await command.ExecuteNonQueryAsync() != 1) throw new InvalidOperationException("Owned backfill fault changed no row.");
                command.Parameters.Clear();
                foreach (var trigger in triggers) { command.CommandText = trigger; await command.ExecuteNonQueryAsync(); }
                var restored = new List<string>();
                command.CommandText = "SELECT sql FROM sqlite_master WHERE type='trigger' AND name IN ('account_home_immutable','project_node_immutable','account_node_update') ORDER BY name;";
                await using (var reader = await command.ExecuteReaderAsync())
                    while (await reader.ReadAsync()) restored.Add(reader.GetString(0));
                if (!triggers.SequenceEqual(restored)) throw new InvalidOperationException("Owned backfill triggers not restored.");
                await transaction.CommitAsync();
            }
            var filesBefore = Directory.EnumerateFiles(project.RepoPath, "*", SearchOption.AllDirectories)
                .ToDictionary(path => path, path => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))));
            var denied = false; var returned = false; string? status = null;
            using (var current = mode == "no-context" ? null : mode == "forged-context"
                ? S206TestSupport.EnterCurrentContext(new RequestContext(fixture.AccountId, fixture.AccountId,
                    new HashSet<string> { PhaseAAuth.AdminRole }, "unregistered-synthetic-credential", "owned-backfill-fault"))
                : fixture.EnterCurrent())
            {
                try
                {
                    if (entry == "refresh")
                    {
                        var result = await service.RefreshContractSnapshotAsync(project.ProjectId);
                        returned = result.ProjectId == fixture.ProjectId; status = result.Status;
                    }
                    else
                    {
                        var result = await service.EnsureResolvedAsync(project);
                        returned = result.ProjectId == fixture.ProjectId;
                        status = ProjectGameTypeMatchEvidence.FromJson(result.GameTypeMatchJson).Status;
                    }
                }
                catch (UnauthorizedAccessException) { denied = true; }
            }
            var after = (await fixture.GetProjectAsync()).GameTypeMatchJson;
            var filesAfter = Directory.EnumerateFiles(project.RepoPath, "*", SearchOption.AllDirectories)
                .ToDictionary(path => path, path => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))));
            rows.Add(new { entry, mode, denied, returned, status, calls = matcher.Calls,
                metadataUnchanged = before == after,
                filesUnchanged = filesBefore.Count == filesAfter.Count && filesBefore.All(pair => filesAfter.TryGetValue(pair.Key, out var value) && value == pair.Value) });
        }
        return rows;
    }

    private sealed class BackfillObservationMatcher(ProjectGameTypeMatchEvidence evidence) : IProjectGameTypeMatchService
    {
        internal int Calls { get; private set; }
        public Task<ProjectGameTypeMatchEvidence> ResolveAsync(string source, CancellationToken cancellationToken)
        { Calls++; return Task.FromResult(evidence); }
    }

    // ADR-0061 AD19/20: actual scene-route result/fallback cannot outlive current authority.
    internal static async Task<object> ObserveSceneReplyBoundaryAsync()
    {
        var rows = new List<object>();
        foreach (var reply in new[] { "valid-json", "invalid-json", "invalid-shape" })
        foreach (var mode in new[] { "valid", "revoked", "stale-projection", "entry-only" })
        {
            using var fixture = await BackendContractFixture.CreateAsync();
            using var current = fixture.EnterCurrent();
            var project = await fixture.GetProjectAsync();
            var marker = "owned-scene-" + fixture.ProjectId[..8];
            var validJson = JsonSerializer.Serialize(new
            {
                sceneCountIntent = "multi", entryScene = "map",
                scenes = new[] {
                    new { id = "map", name = marker, role = "hub", m1Required = true, playerGoal = "Choose encounter" },
                    new { id = "combat", name = "Combat", role = "combat", m1Required = true, playerGoal = "Win encounter" }
                },
                transitions = new[] { new { from = "map", to = "combat", trigger = "Choose", returnsTo = "map", stateCarried = new[] { "hp" } } },
                singleSceneConfirmation = new { allowed = false, reason = "Multiple scenes" }, notes = new[] { "Owned scene observation" }
            });
            var engine = new BlockingRequirementMapLlmEngine(reply == "valid-json" ? validJson : reply == "invalid-json" ? "{broken" : "{}");
            var roles = new HashSet<string> { "entry", "production" };
            var options = fixture.Options with { EnabledRoles = roles };
            NodeProjectMetadata node = new PhaseAMetadataStore(fixture.ConnectionString, options);
            var service = new GameDesignSceneRouteService(node, options, engine);
            var operation = service.CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignSceneRouteDraftRequest("Owned current scene route"));
            await engine.Started.WaitAsync(TimeSpan.FromSeconds(10));
            if (engine.Request?.Purpose != "gdd-scene-route-draft" || engine.Request.OperationKey != "llm:gdd-scene-route-draft"
                || engine.Request.BillingAccountId != fixture.AccountId)
                throw new InvalidOperationException("Actual scene-route model request binding unavailable.");
            Dictionary<string, string> Files() => Directory.EnumerateFiles(project.RepoPath, "*", SearchOption.AllDirectories)
                .ToDictionary(path => Path.GetRelativePath(project.RepoPath, path).Replace(Path.DirectorySeparatorChar, '/'),
                    path => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))), StringComparer.Ordinal);
            var before = Files();
            try
            {
                if (mode == "entry-only")
                {
                    if (!roles.Remove("production") || !roles.SetEquals(new[] { "entry" }))
                        throw new InvalidOperationException("Owned scene responsibility closure was not applied.");
                }
                else if (mode != "valid")
                {
                    await using var connection = new SqliteConnection(fixture.ConnectionString);
                    await connection.OpenAsync();
                    await using var command = connection.CreateCommand();
                    command.CommandText = mode == "revoked"
                        ? "UPDATE accounts SET is_disabled=1 WHERE id=$account;"
                        : "UPDATE account_node_projections SET authority_revision=authority_revision+1 WHERE account_id=$account;";
                    command.Parameters.AddWithValue("$account", fixture.AccountId);
                    if (await command.ExecuteNonQueryAsync() != 1) throw new InvalidOperationException("Owned scene fault changed no row.");
                    command.CommandText = mode == "revoked"
                        ? "SELECT count(*) FROM accounts WHERE id=$account AND is_disabled=1;"
                        : "SELECT count(*) FROM account_node_projections pr JOIN accounts a ON a.id=pr.account_id WHERE a.id=$account AND pr.authority_revision<>a.authority_revision;";
                    if (Convert.ToInt64(await command.ExecuteScalarAsync()) != 1) throw new InvalidOperationException("Owned scene fault was not verified.");
                }
            }
            finally { engine.Release(); }
            var denied = false;
            GameDesignSceneRouteDraftResult? result = null;
            try { result = await operation.WaitAsync(TimeSpan.FromSeconds(20)); }
            catch (UnauthorizedAccessException) { denied = true; }
            var after = Files();
            var changed = before.Keys.Union(after.Keys).Where(path =>
                !before.TryGetValue(path, out var left) || !after.TryGetValue(path, out var right) || left != right).Order().ToArray();
            rows.Add(new { reply, mode, reachedModel = engine.Started.IsCompletedSuccessfully, calls = engine.CallCount,
                denied, resultReturned = result is not null, source = result?.Source, status = result?.Status,
                payloadMatches = result?.SceneRoute.Scenes.Any(scene => scene.Name == marker) == true,
                failureCode = result?.FailureCode, changed });
        }
        return rows;
    }

    // ADR-0061 AD19: cache decisions must not dispatch a new model under expired authority.
    internal static async Task<object> ObserveWarmQuestionFormAsync()
    {
        var rows = new List<object>();
        foreach (var decision in new[] { "keep", "rebuild" })
        foreach (var mode in new[] { "valid", "revoked", "stale-projection" })
        {
            using var fixture = await BackendContractFixture.CreateAsync();
            using var current = fixture.EnterCurrent();
            const string formJson = """{"fields": [{"id": "reference_signal", "label": "\u53c2\u8003\u6807\u6746", "placeholder": "\u53c2\u8003\u5bf9\u8c61\u548c\u7981\u5fcc\u65b9\u5411\u3002", "inputType": "textarea", "rows": 2, "maxLength": 300, "required": true}, {"id": "player_fantasy", "label": "\u73a9\u5bb6\u5e7b\u60f3", "placeholder": "\u73a9\u5bb6\u7b2c\u4e00\u5206\u949f\u7684\u611f\u53d7\u3002", "inputType": "textarea", "rows": 3, "maxLength": 500, "required": true}, {"id": "combat_loop", "label": "\u6218\u6597\u5faa\u73af", "placeholder": "\u8fdb\u5165\u3001\u6218\u6597\u3001\u6389\u843d\u3001\u56de\u57ce\u3002", "inputType": "textarea", "rows": 3, "maxLength": 500, "required": true}, {"id": "first_dungeon", "label": "\u9996\u4e2a\u5730\u7262", "placeholder": "\u5730\u56fe\u3001\u654c\u4eba\u3001\u76ee\u6807\u3002", "inputType": "textarea", "rows": 3, "maxLength": 500, "required": true}, {"id": "controls_camera", "label": "\u64cd\u4f5c\u89c6\u89d2", "placeholder": "\u79fb\u52a8\u3001\u6280\u80fd\u3001\u955c\u5934\u3002", "inputType": "textarea", "rows": 3, "maxLength": 500, "required": true}, {"id": "pressure_fail", "label": "\u538b\u529b\u5931\u8d25", "placeholder": "\u53d7\u538b\u548c\u5931\u8d25\u6761\u4ef6\u3002", "inputType": "textarea", "rows": 3, "maxLength": 500, "required": true}, {"id": "loot_growth", "label": "\u6389\u843d\u6210\u957f", "placeholder": "\u88c5\u5907\u3001\u6280\u80fd\u3001\u6570\u503c\u3002", "inputType": "textarea", "rows": 3, "maxLength": 500, "required": false}, {"id": "hud_feedback", "label": "HUD\u53cd\u9988", "placeholder": "\u8840\u91cf\u3001\u8d44\u6e90\u3001\u6389\u843d\u63d0\u793a\u3002", "inputType": "textarea", "rows": 3, "maxLength": 500, "required": false}]}""";
            var firstMarker = "owned-initial-" + fixture.ProjectId[..8];
            var nextMarker = "owned-rebuilt-" + fixture.ProjectId[..8];
            string Reply(string marker)
            {
                var json = JsonNode.Parse(formJson)!;
                json["fields"]!.AsArray()[0]!.AsObject()["placeholder"] = marker;
                return json.ToJsonString();
            }
            var engine = new WarmQuestionFormLlmEngine(Reply(firstMarker), Reply(nextMarker), decision == "rebuild");
            var service = new GameDesignQuestionFormService(fixture.Store, fixture.Options, engine);
            var first = await service.CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignQuestionFormRequest());
            System.Collections.IDictionary Cache() => (System.Collections.IDictionary)typeof(GameDesignQuestionFormService)
                .GetField("_schemaCache", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic)!.GetValue(service)!;
            if (first?.Source != "agent" || !first.Fields.Any(field => field.Placeholder == firstMarker) || Cache().Count != 1)
                throw new InvalidOperationException("Actual initial private schema/cache positive control unavailable.");
            var priorCache = Cache().Values.Cast<object>().Single();
            var operation = service.CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignQuestionFormRequest());
            await engine.DecisionStarted.Task.WaitAsync(TimeSpan.FromSeconds(10));
            if (engine.Decision?.Purpose != "gdd-question-form-cache-decision"
                || engine.Decision.OperationKey != "llm:gdd-question-form-cache-decision"
                || engine.Decision.BillingAccountId != fixture.AccountId)
                throw new InvalidOperationException("Actual cache-decision model request binding unavailable.");
            try
            {
                if (mode != "valid")
                {
                    await using var connection = new SqliteConnection(fixture.ConnectionString);
                    await connection.OpenAsync();
                    await using var command = connection.CreateCommand();
                    command.CommandText = mode == "revoked"
                        ? "UPDATE accounts SET is_disabled=1 WHERE id=$account;"
                        : "UPDATE account_node_projections SET authority_revision=authority_revision+1 WHERE account_id=$account;";
                    command.Parameters.AddWithValue("$account", fixture.AccountId);
                    if (await command.ExecuteNonQueryAsync() != 1) throw new InvalidOperationException("Owned cache fault changed no row.");
                    command.CommandText = mode == "revoked"
                        ? "SELECT count(*) FROM accounts WHERE id=$account AND is_disabled=1;"
                        : "SELECT count(*) FROM account_node_projections pr JOIN accounts a ON a.id=pr.account_id WHERE a.id=$account AND pr.authority_revision<>a.authority_revision;";
                    if (Convert.ToInt64(await command.ExecuteScalarAsync()) != 1) throw new InvalidOperationException("Owned cache fault was not verified.");
                }
            }
            finally { engine.DecisionRelease.TrySetResult(); }
            var denied = false;
            GameDesignQuestionFormResult? result = null;
            try { result = await operation.WaitAsync(TimeSpan.FromSeconds(20)); }
            catch (UnauthorizedAccessException) { denied = true; }
            var expectedMarker = decision == "rebuild" ? nextMarker : firstMarker;
            rows.Add(new { decision, mode, denied, resultReturned = result is not null, calls = engine.Calls,
                payloadMatches = result?.Source == "agent" && result.Fields.Any(field => field.Placeholder == expectedMarker),
                cacheCount = Cache().Count, cacheUnchanged = Cache().Count == 1 && ReferenceEquals(priorCache, Cache().Values.Cast<object>().Single()),
                reachedDecision = engine.DecisionStarted.Task.IsCompletedSuccessfully,
                scope = "actual existing schema/cache decision; external JSON engine supplies no current authorization" });
        }
        return rows;
    }

    private sealed class WarmQuestionFormLlmEngine(string first, string next, bool rebuild) : ILlmRouteEngine
    {
        public TaskCompletionSource DecisionStarted { get; } = new(TaskCreationOptions.RunContinuationsAsynchronously);
        public TaskCompletionSource DecisionRelease { get; } = new(TaskCreationOptions.RunContinuationsAsynchronously);
        public int Calls { get; private set; }
        public LlmRouteRequest? Decision { get; private set; }
        public async Task<LlmRouteResult> CompleteAsync(LlmRouteRequest request, CancellationToken cancellationToken = default)
        {
            Calls++;
            string json;
            if (Calls == 1) json = first;
            else if (Calls == 2)
            {
                Decision = request;
                DecisionStarted.TrySetResult();
                await DecisionRelease.Task.WaitAsync(cancellationToken);
                json = rebuild ? "{\"rebuild\":true}" : "{\"rebuild\":false}";
            }
            else if (Calls == 3 && rebuild) json = next;
            else throw new InvalidOperationException("Unexpected schema model dispatch.");
            return new LlmRouteResult(true, json, json, request.Model, null, null, 0, "", "", null,
                1, request.Prompt.Length, Encoding.UTF8.GetByteCount(request.Prompt), 1);
        }
    }


    // ADR-0061 AD19: a completed structured model reply cannot retain current project authority.
    internal static async Task<object> ObserveModelReplyBoundaryAsync(string family)
    {
        var rows = new List<object>();
        foreach (var mode in new[] { "valid", "revoked", "stale-projection" })
        {
            using var fixture = await BackendContractFixture.CreateAsync();
            using var current = fixture.EnterCurrent();
            var project = await fixture.GetProjectAsync();
            if (family == "requirements") fixture.SeedConfirmedSceneRouteAndGdd();
            const string formJson = """{"fields": [{"id": "reference_signal", "label": "\u53c2\u8003\u6807\u6746", "placeholder": "\u53c2\u8003\u5bf9\u8c61\u548c\u7981\u5fcc\u65b9\u5411\u3002", "inputType": "textarea", "rows": 2, "maxLength": 300, "required": true}, {"id": "player_fantasy", "label": "\u73a9\u5bb6\u5e7b\u60f3", "placeholder": "\u73a9\u5bb6\u7b2c\u4e00\u5206\u949f\u7684\u611f\u53d7\u3002", "inputType": "textarea", "rows": 3, "maxLength": 500, "required": true}, {"id": "combat_loop", "label": "\u6218\u6597\u5faa\u73af", "placeholder": "\u8fdb\u5165\u3001\u6218\u6597\u3001\u6389\u843d\u3001\u56de\u57ce\u3002", "inputType": "textarea", "rows": 3, "maxLength": 500, "required": true}, {"id": "first_dungeon", "label": "\u9996\u4e2a\u5730\u7262", "placeholder": "\u5730\u56fe\u3001\u654c\u4eba\u3001\u76ee\u6807\u3002", "inputType": "textarea", "rows": 3, "maxLength": 500, "required": true}, {"id": "controls_camera", "label": "\u64cd\u4f5c\u89c6\u89d2", "placeholder": "\u79fb\u52a8\u3001\u6280\u80fd\u3001\u955c\u5934\u3002", "inputType": "textarea", "rows": 3, "maxLength": 500, "required": true}, {"id": "pressure_fail", "label": "\u538b\u529b\u5931\u8d25", "placeholder": "\u53d7\u538b\u548c\u5931\u8d25\u6761\u4ef6\u3002", "inputType": "textarea", "rows": 3, "maxLength": 500, "required": true}, {"id": "loot_growth", "label": "\u6389\u843d\u6210\u957f", "placeholder": "\u88c5\u5907\u3001\u6280\u80fd\u3001\u6570\u503c\u3002", "inputType": "textarea", "rows": 3, "maxLength": 500, "required": false}, {"id": "hud_feedback", "label": "HUD\u53cd\u9988", "placeholder": "\u8840\u91cf\u3001\u8d44\u6e90\u3001\u6389\u843d\u63d0\u793a\u3002", "inputType": "textarea", "rows": 3, "maxLength": 500, "required": false}]}""";
            var marker = "owned-private-form-" + fixture.ProjectId[..8];
            var form = JsonNode.Parse(formJson)!;
            form["fields"]!.AsArray()[0]!.AsObject()["placeholder"] = marker;
            const string requirementsJson = """
                {"requirements":[
                {"requirement_id":"REQ-001","normalized_requirement":"Player moves on the field map.","priority":"P0","kind":"scene","mapped_scene_ids":["field_map"],"mapped_required_module_ids":["field_map"],"status":"mapped"},
                {"requirement_id":"REQ-002","normalized_requirement":"HUD shows HP and reward feedback.","priority":"P1","kind":"ui","mapped_scene_ids":["field_map"],"mapped_required_module_ids":["combat_hud"],"status":"mapped","capability_domain_ids":["ui_component_system","ui_overlays_feedback"]}]}
                """;
            var engine = new BlockingRequirementMapLlmEngine(family == "requirements" ? requirementsJson : form.ToJsonString());
            GameDesignRequirementMapResult? mapResult = null;
            GameDesignQuestionFormResult? formResult = null;
            var formService = family == "question-form" ? new GameDesignQuestionFormService(fixture.Store, fixture.Options, engine) : null;
            async Task RunConsumerAsync()
            {
                if (family == "requirements")
                    mapResult = await new GameDesignRequirementMapService(fixture.Store, engine)
                        .CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignRequirementMapRequest());
                else if (formService is not null)
                    formResult = await formService.CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignQuestionFormRequest());
                else throw new InvalidOperationException("Unknown model-boundary family.");
            }
            var operation = RunConsumerAsync();
            await engine.Started.WaitAsync(TimeSpan.FromSeconds(10));
            var purpose = family == "requirements" ? "gdd-requirement-map" : "gdd-question-form";
            if (engine.Request?.Purpose != purpose || engine.Request.OperationKey != "llm:" + purpose
                || engine.Request.BillingAccountId != fixture.AccountId)
                throw new InvalidOperationException("Actual project model request binding unavailable.");
            Dictionary<string, string> Files() => Directory.EnumerateFiles(project.RepoPath, "*", SearchOption.AllDirectories)
                .ToDictionary(path => Path.GetRelativePath(project.RepoPath, path).Replace(Path.DirectorySeparatorChar, '/'),
                    path => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))), StringComparer.Ordinal);
            var before = Files();
            try
            {
                if (mode != "valid")
                {
                    await using var connection = new SqliteConnection(fixture.ConnectionString);
                    await connection.OpenAsync();
                    await using var command = connection.CreateCommand();
                    command.CommandText = mode == "revoked"
                        ? "UPDATE accounts SET is_disabled=1 WHERE id=$account;"
                        : "UPDATE account_node_projections SET authority_revision=authority_revision+1 WHERE account_id=$account;";
                    command.Parameters.AddWithValue("$account", fixture.AccountId);
                    if (await command.ExecuteNonQueryAsync() != 1) throw new InvalidOperationException("Owned model-boundary fault changed no row.");
                    command.CommandText = mode == "revoked"
                        ? "SELECT count(*) FROM accounts WHERE id=$account AND is_disabled=1;"
                        : "SELECT count(*) FROM account_node_projections pr JOIN accounts a ON a.id=pr.account_id WHERE a.id=$account AND pr.authority_revision<>a.authority_revision;";
                    if (Convert.ToInt64(await command.ExecuteScalarAsync()) != 1) throw new InvalidOperationException("Owned model-boundary fault was not verified.");
                }
            }
            finally { engine.Release(); }
            var denied = false;
            try { await operation.WaitAsync(TimeSpan.FromSeconds(20)); }
            catch (UnauthorizedAccessException) { denied = true; }
            var after = Files();
            var changed = before.Keys.Union(after.Keys).Where(path =>
                !before.TryGetValue(path, out var left) || !after.TryGetValue(path, out var right) || left != right).Order().ToArray();
            var cacheCount = formService is null ? 0 : ((System.Collections.IDictionary)typeof(GameDesignQuestionFormService)
                .GetField("_schemaCache", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic)!
                .GetValue(formService)!).Count;
            var matches = family == "requirements" ? mapResult?.Status == "ready"
                && mapResult.SourceGddHash == fixture.GddHash
                && mapResult.Requirements.Select(item => item.RequirementId).Order().SequenceEqual(new[] { "REQ-001", "REQ-002" })
                : formResult?.Status == "ready" && formResult.ProjectId == fixture.ProjectId && formResult.Source == "agent"
                && formResult.Fields.Any(field => field.Placeholder == marker);
            rows.Add(new { family, mode, reachedModel = engine.Started.IsCompletedSuccessfully, calls = engine.CallCount,
                denied, resultReturned = mapResult is not null || formResult is not null, payloadMatches = matches,
                cacheCount, changed, scope = "actual structured service; model double returns JSON only and supplies no authorization" });
        }
        return rows;
    }

    // ADR-0061 AD19: real feedback and UI consumers must retain current write authority after an executor wait.
    internal static async Task<object> ObservePostprocessConsumersAsync()
    {
        var rows = new List<object>();
        foreach (var family in new[] { "feedback", "ui" })
        foreach (var mode in new[] { "valid", "revoked", "stale-projection" })
        {
            using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
            using var fixture = await BackendContractFixture.CreateAsync();
            using var current = fixture.EnterCurrent();
            var project = await fixture.GetProjectAsync();
            if (family == "ui")
            {
                await fixture.SeedRequirementMapAsync();
                if ((await new PrototypeContractFreezeService(fixture.Store).FreezeAsync(fixture.AccountId,
                        fixture.ProjectId, new PrototypeContractFreezeRequest())).Status != "fresh")
                    throw new InvalidOperationException("Actual UI contract prerequisite unavailable.");
                await fixture.SeedPrototypeSkeletonAsync();
                var planner = new PrototypeIterationPlanService(fixture.Store);
                var plan = await planner.CreateAsync(fixture.AccountId, fixture.ProjectId,
                    new PrototypeIterationPlanRequest("Complete field movement and HUD feedback.", "manual_feedback"));
                if ((await planner.ConfirmAsync(fixture.AccountId, fixture.ProjectId,
                        new PrototypeIterationPlanConfirmationRequest(plan.SessionId, plan.PlanHash))).Status != "confirmed")
                    throw new InvalidOperationException("Actual UI iteration prerequisite unavailable.");
                var details = await fixture.Store.GetLatestProjectIterationSessionAsync(fixture.ProjectId)
                    ?? throw new InvalidOperationException("Actual UI persisted session unavailable.");
                foreach (var goal in details.Goals)
                    await fixture.Store.UpdateProjectIterationGoalStatusAsync(goal.GoalId, "completed", "Owned completed prerequisite.", DateTimeOffset.UtcNow.ToString("O"));
            }
            var prerequisite = await fixture.Store.CreateRunAsync(fixture.ProjectId, project.WorkspaceId, "prototype-7day-playable");
            await fixture.Store.CompleteRunAsync(prerequisite, "succeeded", 0, "Owned prerequisite fixture.", "", "{}");
            var marker = "owned-feedback-" + Guid.NewGuid().ToString("N");
            var bomFile = Path.Combine(project.RepoPath, "Game.Godot", "Prototypes", "S236OwnedBoundary", "OwnedBoundary.tscn");
            var expectedGodotBytes = new UTF8Encoding(false).GetBytes("[gd_scene format=3]\n[node name=\"OwnedBoundary\" type=\"Node\"]\n");
            if (family == "ui")
            {
                Directory.CreateDirectory(Path.GetDirectoryName(bomFile)!);
                await File.WriteAllBytesAsync(bomFile, new byte[] { 0xef, 0xbb, 0xbf }.Concat(expectedGodotBytes).ToArray());
            }
            var runner = new PublicationObservationRunner();
            async Task<string> RunConsumerAsync()
            {
                if (family == "feedback")
                {
                    var result = await new PrototypeFeedbackIterationService(fixture.Store, fixture.Options, runner,
                        new ProjectWorkspaceSeeder(fixture.Options, fixture.Store), new SkillActionCatalog(), heavyRunnerQueue: fixture.Queue)
                        .SubmitAsync(fixture.AccountId, fixture.ProjectId, new PrototypeFeedbackRequest(marker, "gpt-5.4"));
                    return result.RunId;
                }
                var ui = await new PrototypeUiOptimizationService(fixture.Store, fixture.Options, runner,
                    new ProjectWorkspaceSeeder(fixture.Options, fixture.Store), heavyRunnerQueue: fixture.Queue)
                    .RunAsync(fixture.AccountId, fixture.ProjectId);
                return ui.RunId;
            }
            var operation = RunConsumerAsync();
            await runner.Started.Task.WaitAsync(TimeSpan.FromSeconds(10));
            var actualRunId = runner.RunId ?? throw new InvalidOperationException("Actual consumer run binding missing.");
            var actualRun = await fixture.Store.GetRunSnapshotAsync(actualRunId);
            if (actualRun?.ProjectId != fixture.ProjectId) throw new InvalidOperationException("Consumer executor run belongs to another project.");
            Dictionary<string, string> Files() => Directory.EnumerateFiles(project.RepoPath, "*", SearchOption.AllDirectories)
                .ToDictionary(path => Path.GetRelativePath(project.RepoPath, path).Replace(Path.DirectorySeparatorChar, '/'),
                    path => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))), StringComparer.Ordinal);
            var before = Files();
            var beforeRun = JsonSerializer.Serialize(actualRun);
            try
            {
                if (mode != "valid")
                {
                    await using var connection = new SqliteConnection(fixture.ConnectionString);
                    await connection.OpenAsync();
                    await using var command = connection.CreateCommand();
                    command.CommandText = mode == "revoked"
                        ? "UPDATE accounts SET is_disabled=1 WHERE id=$account;"
                        : "UPDATE account_node_projections SET authority_revision=authority_revision+1 WHERE account_id=$account;";
                    command.Parameters.AddWithValue("$account", fixture.AccountId);
                    if (await command.ExecuteNonQueryAsync() != 1) throw new InvalidOperationException("Owned current fault did not affect exactly one row.");
                    command.CommandText = mode == "revoked"
                        ? "SELECT count(*) FROM accounts WHERE id=$account AND is_disabled=1;"
                        : "SELECT count(*) FROM account_node_projections pr JOIN accounts a ON a.id=pr.account_id WHERE a.id=$account AND pr.authority_revision<>a.authority_revision;";
                    if (Convert.ToInt64(await command.ExecuteScalarAsync()) != 1) throw new InvalidOperationException("Owned current fault was not confirmed.");
                }
            }
            finally { runner.Release.TrySetResult(); }
            var denied = false;
            string? returnedRunId = null;
            try { returnedRunId = await operation.WaitAsync(TimeSpan.FromSeconds(20)); }
            catch (UnauthorizedAccessException) { denied = true; }
            var after = Files();
            var changed = before.Keys.Union(after.Keys).Where(path =>
                !before.TryGetValue(path, out var left) || !after.TryGetValue(path, out var right) || left != right).Order().ToArray();
            var payloadMatches = family == "ui" ? File.ReadAllBytes(bomFile).SequenceEqual(expectedGodotBytes)
                : changed.Where(path => path.EndsWith("/result-log.md", StringComparison.Ordinal)).Any(path =>
                    File.ReadAllText(Path.Combine(project.RepoPath, path)).Contains(marker, StringComparison.Ordinal)
                    && File.ReadAllText(Path.Combine(project.RepoPath, path)).Contains(actualRunId, StringComparison.Ordinal));
            rows.Add(new { family, mode, reachedExecutor = runner.Started.Task.IsCompletedSuccessfully, calls = runner.Calls,
                denied, resultReturned = returnedRunId == actualRunId, changed, payloadMatches,
                runUnchanged = beforeRun == JsonSerializer.Serialize(await fixture.Store.GetRunSnapshotAsync(actualRunId)),
                scope = "actual service and owned project; executor double performs no file edits and supplies no authority" });
        }
        return rows;
    }

    // ADR-0061 AD19: executor completion is not permission to publish retained project state.
    internal static async Task<object> ObserveGoalPublicationAfterProcessAsync()
    {
        var rows = new List<object>();
        foreach (var mode in new[] { "valid", "revoked", "stale-projection" })
        {
            using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
            using var fixture = await BackendContractFixture.CreateAsync();
            using var current = fixture.EnterCurrent();
            await fixture.SeedRequirementMapAsync();
            var frozen = await new PrototypeContractFreezeService(fixture.Store)
                .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
            if (frozen.Status != "fresh") throw new InvalidOperationException("Actual contract prerequisite unavailable.");
            await fixture.SeedPrototypeSkeletonAsync();
            var planner = new PrototypeIterationPlanService(fixture.Store);
            var plan = await planner.CreateAsync(fixture.AccountId, fixture.ProjectId,
                new PrototypeIterationPlanRequest("Complete field movement and HUD feedback.", "manual_feedback"));
            if ((await planner.ConfirmAsync(fixture.AccountId, fixture.ProjectId,
                    new PrototypeIterationPlanConfirmationRequest(plan.SessionId, plan.PlanHash))).Status != "confirmed")
                throw new InvalidOperationException("Actual confirmed iteration prerequisite unavailable.");
            var details = await fixture.Store.GetLatestProjectIterationSessionAsync(fixture.ProjectId)
                ?? throw new InvalidOperationException("Actual persisted iteration session unavailable.");
            await fixture.Store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "ready", 0,
                details.Session.LatestSummary, JsonSerializer.Serialize(new PrototypeIterationPlanEvaluationResult(
                    "ready_to_execute", "Owned publication-boundary control.", "Actual external executor pause.", "execute_next_goal")), null);
            var project = await fixture.GetProjectAsync();
            new PrototypeRouteStateWriter().WritePrototypeState(project, new
            {
                route = "prototype-7day-playable", status = "succeeded", prototype_completion = new { succeeded = true }
            });
            var runner = new PublicationObservationRunner();
            var service = new PrototypeIterationGoalService(fixture.Store, fixture.Options, runner,
                new ProjectWorkspaceSeeder(fixture.Options, fixture.Store), heavyRunnerQueue: fixture.Queue);
            var operation = service.ExecuteNextAsync(fixture.AccountId, fixture.ProjectId);
            await runner.Started.Task.WaitAsync(TimeSpan.FromSeconds(10));
            Dictionary<string, string> Files() => Directory.EnumerateFiles(project.RepoPath, "*", SearchOption.AllDirectories)
                .ToDictionary(path => Path.GetRelativePath(project.RepoPath, path).Replace(Path.DirectorySeparatorChar, '/'),
                    path => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))), StringComparer.Ordinal);
            var before = Files();
            var earlierSession = JsonSerializer.Serialize(await fixture.Store.GetLatestProjectIterationSessionAsync(fixture.ProjectId));
            try
            {
                if (mode != "valid")
                {
                    await using var connection = new SqliteConnection(fixture.ConnectionString);
                    await connection.OpenAsync();
                    await using var command = connection.CreateCommand();
                    command.CommandText = mode == "revoked"
                        ? "UPDATE accounts SET is_disabled=1 WHERE id=$account;"
                        : "UPDATE account_node_projections SET authority_revision=authority_revision+1 WHERE account_id=$account;";
                    command.Parameters.AddWithValue("$account", fixture.AccountId);
                    if (await command.ExecuteNonQueryAsync() != 1) throw new InvalidOperationException("Owned projection fault unavailable.");
                    command.CommandText = mode == "revoked"
                        ? "SELECT count(*) FROM accounts WHERE id=$account AND is_disabled=1;"
                        : "SELECT count(*) FROM account_node_projections pr JOIN accounts a ON a.id=pr.account_id WHERE a.id=$account AND pr.authority_revision<>a.authority_revision;";
                    if (Convert.ToInt64(await command.ExecuteScalarAsync()) != 1)
                        throw new InvalidOperationException("Owned authority fault was not confirmed before executor completion.");
                }
            }
            finally { runner.Release.TrySetResult(); }
            var denied = false;
            PrototypeIterationGoalExecutionResult? result = null;
            try { result = await operation.WaitAsync(TimeSpan.FromSeconds(20)); }
            catch (UnauthorizedAccessException) { denied = true; }
            var after = Files();
            var changed = before.Keys.Union(after.Keys).Where(path =>
                !before.TryGetValue(path, out var left) || !after.TryGetValue(path, out var right) || left != right).Order().ToArray();
            rows.Add(new { mode, reachedExecutor = runner.Started.Task.IsCompletedSuccessfully, calls = runner.Calls,
                denied, resultReturned = result is not null, changed,
                resultLogPublished = changed.Any(path => path.EndsWith("/goal-result.md", StringComparison.Ordinal)),
                sessionUnchanged = earlierSession == JsonSerializer.Serialize(await fixture.Store.GetLatestProjectIterationSessionAsync(fixture.ProjectId)),
                scope = "actual iteration service and own project; external process double writes no project bytes and grants no authority" });
        }
        return rows;
    }

    private sealed class PublicationObservationRunner : IHostedProcessRunner
    {
        public TaskCompletionSource Started { get; } = new(TaskCreationOptions.RunContinuationsAsynchronously);
        public TaskCompletionSource Release { get; } = new(TaskCreationOptions.RunContinuationsAsynchronously);
        public int Calls { get; private set; }
        public string? RunId { get; private set; }
        public async Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Calls++;
            RunId = command.RunId;
            Started.TrySetResult();
            await Release.Task.WaitAsync(cancellationToken);
            return new HostedProcessResult(1, "", "Owned external executor control finished without changes.");
        }
    }

    // ADR-0061 AD19: the actual contract writer must recheck after its real project lease wait.
    internal static async Task<object> ObserveContractFreezeAfterMutationWaitAsync()
    {
        var rows = new List<object>();
        foreach (var mode in new[] { "valid", "revoked", "foreign-home", "stale-projection", "foreign-project" })
        {
            using var fixture = await BackendContractFixture.CreateAsync();
            using var current = fixture.EnterCurrent();
            await fixture.SeedRequirementMapAsync();
            var service = new PrototypeContractFreezeService(fixture.Store);
            var control = await service.FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
            if (control.Status != "fresh" || string.IsNullOrEmpty(control.ContractHash))
                throw new InvalidOperationException("Actual contract writer positive control unavailable.");
            NodeProjectMetadata node = fixture.Store;
            var earlierProject = await node.GetProjectSnapshotAsync(fixture.ProjectId)
                ?? throw new InvalidOperationException("Actual pre-wait project authority unavailable.");
            Dictionary<string, string> Files() => Directory.EnumerateFiles(earlierProject.RepoPath, "*", SearchOption.AllDirectories)
                .ToDictionary(path => Path.GetRelativePath(earlierProject.RepoPath, path).Replace(Path.DirectorySeparatorChar, '/'),
                    path => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))), StringComparer.Ordinal);
            var before = Files();
            var lease = await ProjectMutationLockRegistry.Shared.AcquireAsync(fixture.AccountId, fixture.ProjectId, CancellationToken.None);
            Task<PrototypeContractStatusResult> operation;
            bool waited;
            var triggersPreserved = true;
            try
            {
                operation = service.FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest(Refresh: true));
                waited = !operation.IsCompleted;
                if (!waited) throw new InvalidOperationException("Actual contract writer did not wait for its owned project lease.");
                if (mode != "valid")
                {
                    await using var connection = new SqliteConnection(fixture.ConnectionString);
                    await connection.OpenAsync();
                    await using var transaction = connection.BeginTransaction();
                    var triggers = new List<string>();
                    await using (var read = connection.CreateCommand())
                    {
                        read.Transaction = transaction;
                        read.CommandText = "SELECT sql FROM sqlite_master WHERE type='trigger' AND name IN ('account_home_immutable','project_node_immutable','account_node_update') ORDER BY name;";
                        await using var reader = await read.ExecuteReaderAsync();
                        while (await reader.ReadAsync()) triggers.Add(reader.GetString(0));
                    }
                    if (triggers.Count != 3) throw new InvalidOperationException("Owned immutable-node trigger prerequisites missing.");
                    await using var command = connection.CreateCommand();
                    command.Transaction = transaction;
                    // Existing disposable-fault protocol: restore exact production triggers before releasing the real consumer.
                    command.CommandText = "DROP TRIGGER account_home_immutable; DROP TRIGGER project_node_immutable; DROP TRIGGER account_node_update;";
                    await command.ExecuteNonQueryAsync();
                    command.CommandText = mode switch
                    {
                        "revoked" => "UPDATE accounts SET is_disabled=1 WHERE id=$account;",
                        "foreign-home" => "UPDATE accounts SET home_node_id='foreign-node' WHERE id=$account;",
                        "stale-projection" => "UPDATE account_node_projections SET authority_revision=authority_revision+1 WHERE account_id=$account;",
                        "foreign-project" => "UPDATE projects SET node_id='foreign-node' WHERE id=$project;",
                        _ => throw new InvalidOperationException("Unknown owned fault.")
                    };
                    command.Parameters.AddWithValue("$account", fixture.AccountId);
                    command.Parameters.AddWithValue("$project", fixture.ProjectId);
                    if (await command.ExecuteNonQueryAsync() != 1)
                        throw new InvalidOperationException("Owned current-authority fault did not affect exactly one row.");
                    command.Parameters.Clear();
                    foreach (var trigger in triggers) { command.CommandText = trigger; await command.ExecuteNonQueryAsync(); }
                    var restored = new List<string>();
                    command.CommandText = "SELECT sql FROM sqlite_master WHERE type='trigger' AND name IN ('account_home_immutable','project_node_immutable','account_node_update') ORDER BY name;";
                    await using (var reader = await command.ExecuteReaderAsync())
                        while (await reader.ReadAsync()) restored.Add(reader.GetString(0));
                    triggersPreserved = triggers.SequenceEqual(restored);
                    if (!triggersPreserved) throw new InvalidOperationException("Owned fault did not restore exact production triggers.");
                    await transaction.CommitAsync();
                }
            }
            finally { await lease.DisposeAsync(); }
            var denied = false;
            PrototypeContractStatusResult? result = null;
            try { result = await operation.WaitAsync(TimeSpan.FromSeconds(10)); }
            catch (UnauthorizedAccessException) { denied = true; }
            var after = Files();
            var changed = before.Keys.Union(after.Keys).Where(path =>
                !before.TryGetValue(path, out var left) || !after.TryGetValue(path, out var right) || left != right).Order().ToArray();
            rows.Add(new { mode, waited, triggersPreserved, earlierProjectObserved = earlierProject.ProjectId == fixture.ProjectId,
                denied, fresh = result?.Status == "fresh", contractHashRetained = result?.ContractHash == control.ContractHash,
                changed, scope = "actual contract writer after the existing project mutation lease; owned temporary database only" });
        }
        return rows;
    }

    [Fact]
    public async Task Phase1State_ConfirmSceneRouteAsync_WritesAuthoritySidecarAndRealHashReadback()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        var service = new GddToModulePhase1StateService(fixture.Store);
        var sceneRoute = new GameDesignSceneRouteDocument(
            "gdd-scene-route.v1",
            "multi",
            "route_map",
            [
                new GameDesignSceneRouteScene("route_map", "Route Map", "hub", true, "Choose the next node."),
                new GameDesignSceneRouteScene("combat", "Combat", "combat", true, "Win the encounter.")
            ],
            [new GameDesignSceneRouteTransition("route_map", "combat", "Select encounter", "route_map", ["hp", "deck"])],
            new GameDesignSingleSceneConfirmation(false, "Multiple states are required."),
            []);

        var result = await service.ConfirmSceneRouteAsync(fixture.AccountId, fixture.ProjectId, sceneRoute);
        var readback = await service.GetSceneRouteAsync(fixture.AccountId, fixture.ProjectId);

        result.Should().NotBeNull();
        result!.Status.Should().Be("confirmed");
        result.ConfirmedSceneRouteHash.Should().NotBeNullOrWhiteSpace();
        result.SourceGameTypeStructuredHash.Should().NotBeNullOrWhiteSpace();
        result.SourceContractSnapshotHash.Should().NotBeNullOrWhiteSpace();
        readback.Should().BeEquivalentTo(result, options => options.Excluding(item => item.OperationStatus));
        var sidecar = fixture.ReadJson("meta/routes/scene-route/latest.json");
        sidecar.RootElement.GetProperty("schema_version").GetString().Should().Be("scene-route.v1");
        sidecar.RootElement.GetProperty("status_dimension").GetString().Should().Be(RouteStatusVocabulary.SceneRouteConfirmation);
        sidecar.RootElement.GetProperty("status_allowed_values").EnumerateArray()
            .Select(item => item.GetString())
            .Should().Contain("confirmed");
        sidecar.RootElement.GetProperty("confirmed_scene_route_hash").GetString().Should().Be(result.ConfirmedSceneRouteHash);
        sidecar.RootElement.GetProperty("scenes")[0].GetProperty("scene_id").GetString().Should().Be("route_map");
        sidecar.RootElement.GetProperty("source_boundary").GetProperty("authority_sources").GetArrayLength().Should().BeGreaterThan(0);
    }

    [Fact]
    public async Task Phase1State_RecordGeneratedGddAsync_WritesDocumentStateAndSceneHashThrough()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        var service = new GddToModulePhase1StateService(fixture.Store);
        await service.ConfirmSceneRouteAsync(fixture.AccountId, fixture.ProjectId, fixture.DefaultSceneRoute());
        fixture.WriteGdd("# Deckbuilder\n\n- Player must select a route node.\n");
        var runId = await fixture.CreateGddPromptRunAsync("ready");

        var result = await service.RecordGeneratedGddAsync(fixture.AccountId, fixture.ProjectId, runId);

        result.Should().NotBeNull();
        result!.Status.Should().Be("ready");
        result.GeneratedGddHash.Should().NotBeNullOrWhiteSpace();
        result.SceneRouteRecordedGeneratedGddHash.Should().Be(result.GeneratedGddHash);
        var project = await fixture.GetProjectAsync();
        var expectedAuthorityHashes = fixture.RecoveryAuthorityHashes(project);
        var documentState = fixture.ReadJson("meta/routes/gdd-document/latest.json");
        documentState.RootElement.GetProperty("status_dimension").GetString().Should().Be(RouteStatusVocabulary.RouteReadback);
        documentState.RootElement.GetProperty("status_allowed_values").EnumerateArray()
            .Select(item => item.GetString())
            .Should().Contain("ready");
        documentState.RootElement.GetProperty("generated_gdd_hash").GetString().Should().Be(result.GeneratedGddHash);
        var boundary = documentState.RootElement.GetProperty("source_boundary");
        boundary.GetProperty("authority_sources").EnumerateArray().Select(item => item.GetString()).Should().ContainInOrder(
            HostedRouteRecoveryContract.ParsedRouteProfileSource,
            HostedRouteRecoveryContract.SelectedRouteSkillPromptBlockSource);
        boundary.GetProperty("source_hashes").GetProperty(HostedRouteRecoveryContract.ParsedRouteProfileHashKey).GetString()
            .Should().Be(expectedAuthorityHashes[HostedRouteRecoveryContract.ParsedRouteProfileHashKey]);
        boundary.GetProperty("source_hashes").GetProperty(HostedRouteRecoveryContract.SelectedRouteSkillPromptBlockHashKey).GetString()
            .Should().Be(expectedAuthorityHashes[HostedRouteRecoveryContract.SelectedRouteSkillPromptBlockHashKey]);
        var sceneState = fixture.ReadJson("meta/routes/scene-route/latest.json");
        sceneState.RootElement.GetProperty("source_generated_gdd_hash").GetString().Should().Be(result.GeneratedGddHash);
        File.Exists(fixture.PathForTest("meta/routes/gdd-document/prompt-evidence.json")).Should().BeTrue();
        var routePromptEvidence = fixture.ReadJson("meta/routes/gdd-document/prompt-evidence.json");
        routePromptEvidence.RootElement.GetProperty("source_hashes")
            .GetProperty(HostedRouteRecoveryContract.ParsedRouteProfileHashKey).GetString()
            .Should().Be(expectedAuthorityHashes[HostedRouteRecoveryContract.ParsedRouteProfileHashKey]);
        routePromptEvidence.RootElement.GetProperty("source_hashes")
            .GetProperty(HostedRouteRecoveryContract.SelectedRouteSkillPromptBlockHashKey).GetString()
            .Should().Be(expectedAuthorityHashes[HostedRouteRecoveryContract.SelectedRouteSkillPromptBlockHashKey]);
        var routeBindings = (await fixture.Store.ListProjectRoutePromptEvidenceBindingsAsync(fixture.ProjectId))
            .ToDictionary(binding => binding.RouteId, StringComparer.Ordinal);
        var routeReadback = new ProjectRouteStateArtifactService(fixture.Store).Read(await fixture.GetProjectAsync(), routeBindings);
        routeReadback.BlockingIssues.Should().NotContain(issue =>
            issue.IssueId.StartsWith("meta/routes/gdd-document/latest.json:prompt_evidence", StringComparison.Ordinal));
        var statusReadback = await service.GetGddDocumentStateAsync(fixture.AccountId, fixture.ProjectId);
        statusReadback!.Status.Should().Be("ready");

        using var changedPromptPolicy = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        var staleReadback = new ProjectRouteStateArtifactService(fixture.Store).Read(project, routeBindings);
        staleReadback.BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/gdd-document/latest.json:source_hashes_authority_mismatch");
    }

    [Fact]
    public async Task Phase1State_ConfirmSceneRouteAsync_ReusesSameHashWithoutErasingGeneratedGddHash()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        var service = new GddToModulePhase1StateService(fixture.Store);
        var sceneRoute = fixture.DefaultSceneRoute();
        var first = await service.ConfirmSceneRouteAsync(fixture.AccountId, fixture.ProjectId, sceneRoute);
        fixture.WriteGdd("# Deckbuilder\n\n- Player must select a route node.\n");
        var promptRunId = await fixture.CreateGddPromptRunAsync("retry");
        var gdd = await service.RecordGeneratedGddAsync(fixture.AccountId, fixture.ProjectId, promptRunId);

        var retry = await service.ConfirmSceneRouteAsync(fixture.AccountId, fixture.ProjectId, sceneRoute);

        first!.OperationStatus.Should().Be("created_run");
        retry!.OperationStatus.Should().Be("returned_existing");
        retry.ConfirmedSceneRouteHash.Should().Be(first.ConfirmedSceneRouteHash);
        retry.SourceGeneratedGddHash.Should().Be(gdd!.GeneratedGddHash);
    }

    [Fact]
    public async Task Phase1State_RecordGeneratedGddAsync_FailsClosedForInvalidSceneState()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        fixture.WriteGdd("# Deckbuilder\n\n- Player must select a route node.\n");
        fixture.WriteJson("meta/routes/scene-route/latest.json", "{ invalid");
        var service = new GddToModulePhase1StateService(fixture.Store);

        var result = await service.RecordGeneratedGddAsync(fixture.AccountId, fixture.ProjectId, "run-gdd-2");

        result.Should().NotBeNull();
        result!.Status.Should().Be("blocked");
        result.BlockingIssues.Should().Contain(issue => issue.DomainCode == "gdd_scene_hash_write_failed");
        File.Exists(fixture.PathForTest("meta/routes/gdd-document/latest.json")).Should().BeFalse();
    }

    [Fact]
    public async Task Phase1State_RecordGeneratedGddAsync_FailsClosedWithoutRunPromptArtifact()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        var service = new GddToModulePhase1StateService(fixture.Store);
        await service.ConfirmSceneRouteAsync(fixture.AccountId, fixture.ProjectId, fixture.DefaultSceneRoute());
        fixture.WriteGdd("# Deckbuilder\n\n- Player must select a route node.\n");
        var project = await fixture.GetProjectAsync();
        var recoveryAuthorityHashes = fixture.RecoveryAuthorityHashes(project);
        var runId = await fixture.Store.CreateRunAsync(fixture.ProjectId, project.WorkspaceId, "game-design-gdd");
        await fixture.Store.CompleteRunAsync(runId, "succeeded", 0, "", "", JsonSerializer.Serialize(new
        {
            generated_gdd_hash = Sha256(NormalizeText(File.ReadAllText(fixture.PathForTest("docs/gdd/GDD.md"), Encoding.UTF8))),
            recovery_source_order_ref = HostedRouteRecoveryContract.ContractId,
            recovery_source_order = HostedRouteRecoveryContract.SourceOrder,
            source_hashes = recoveryAuthorityHashes,
            prompt_manifest = new
            {
                execution_prompt_hash = new string('a', 64),
                persisted_prompt_hash = new string('b', 64),
                prompt_artifact_ref = "logs/phase-a-gdd/missing/prompt.md",
                prompt_source_evidence_ref = "logs/phase-a-gdd/missing/evidence.json",
                redacted = true
            }
        }));

        var result = await service.RecordGeneratedGddAsync(fixture.AccountId, fixture.ProjectId, runId);

        result!.Status.Should().Be("blocked");
        result.BlockingIssues.Should().Contain(issue => issue.DomainCode == "gdd_prompt_evidence_missing");
        File.Exists(fixture.PathForTest("meta/routes/gdd-document/latest.json")).Should().BeFalse();
    }

    [Fact]
    public async Task Phase1State_RecordGeneratedGddAsync_FailsClosedWhenPersistedPromptWasTampered()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        var service = new GddToModulePhase1StateService(fixture.Store);
        await service.ConfirmSceneRouteAsync(fixture.AccountId, fixture.ProjectId, fixture.DefaultSceneRoute());
        fixture.WriteGdd("# Deckbuilder\n\n- Player must select a route node.\n");
        var runId = await fixture.CreateGddPromptRunAsync("tampered");
        var promptArtifact = (await fixture.Store.ListArtifactsForRunAsync(runId))
            .Single(artifact => artifact.ArtifactType == GameDesignDocumentService.PromptArtifactType);
        fixture.WriteText(promptArtifact.RelativePath, "Tampered after source scan.");

        var result = await service.RecordGeneratedGddAsync(fixture.AccountId, fixture.ProjectId, runId);

        result.Should().NotBeNull();
        result!.Status.Should().Be("blocked");
        result.BlockingIssues.Should().Contain(issue => issue.DomainCode == "gdd_forbidden_source_detected");
    }

    [Fact]
    public async Task Phase1State_RecordGeneratedGddAsync_FailsClosedWhenPromptEvidenceAndFilesDivergeFromDatabaseBinding()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        var service = new GddToModulePhase1StateService(fixture.Store);
        await service.ConfirmSceneRouteAsync(fixture.AccountId, fixture.ProjectId, fixture.DefaultSceneRoute());
        fixture.WriteGdd("# Deckbuilder\n\n- Player must select a route node.\n");
        var runId = await fixture.CreateGddPromptRunAsync("coordinated-tamper");
        var artifacts = await fixture.Store.ListArtifactsForRunAsync(runId);
        var promptArtifact = artifacts.Single(artifact => artifact.ArtifactType == GameDesignDocumentService.PromptArtifactType);
        var evidenceArtifact = artifacts.Single(artifact => artifact.ArtifactType == GameDesignDocumentService.PromptSourceEvidenceArtifactType);
        const string tamperedPrompt = "Coordinated tampered prompt and evidence.";
        var tamperedHash = HostedRouteForbiddenSourceGuard.PromptHash(tamperedPrompt);
        fixture.WriteText(promptArtifact.RelativePath, tamperedPrompt);
        var evidenceNode = JsonNode.Parse(File.ReadAllText(fixture.PathForTest(evidenceArtifact.RelativePath), Encoding.UTF8))!.AsObject();
        evidenceNode["prompt_manifest"]!["execution_prompt_hash"] = tamperedHash;
        evidenceNode["prompt_manifest"]!["persisted_prompt_hash"] = tamperedHash;
        evidenceNode["forbidden_source_scan"]!["prompt_hash"] = tamperedHash;
        fixture.WriteJson(evidenceArtifact.RelativePath, evidenceNode.ToJsonString());

        var result = await service.RecordGeneratedGddAsync(fixture.AccountId, fixture.ProjectId, runId);

        result.Should().NotBeNull();
        result!.Status.Should().Be("blocked");
        result.BlockingIssues.Should().Contain(issue => issue.DomainCode == "gdd_prompt_evidence_invalid");
    }

    [Fact]
    public async Task Phase1State_RecordGeneratedGddAsync_FailsClosedWhenSelectedPromptBlockHashIsMissing()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        var service = new GddToModulePhase1StateService(fixture.Store);
        await service.ConfirmSceneRouteAsync(fixture.AccountId, fixture.ProjectId, fixture.DefaultSceneRoute());
        fixture.WriteGdd("# Deckbuilder\n\n- Player must select a route node.\n");
        var runId = await fixture.CreateGddPromptRunAsync("missing-prompt-block-hash");
        var evidenceArtifact = (await fixture.Store.ListArtifactsForRunAsync(runId))
            .Single(artifact => artifact.ArtifactType == GameDesignDocumentService.PromptSourceEvidenceArtifactType);
        var evidenceNode = JsonNode.Parse(File.ReadAllText(fixture.PathForTest(evidenceArtifact.RelativePath), Encoding.UTF8))!.AsObject();
        evidenceNode["source_hashes"]!.AsObject().Remove(HostedRouteRecoveryContract.SelectedRouteSkillPromptBlockHashKey);
        fixture.WriteJson(evidenceArtifact.RelativePath, evidenceNode.ToJsonString());

        var result = await service.RecordGeneratedGddAsync(fixture.AccountId, fixture.ProjectId, runId);

        result.Should().NotBeNull();
        result!.Status.Should().Be("blocked");
        result.BlockingIssues.Should().Contain(issue => issue.DomainCode == "gdd_prompt_evidence_invalid");
    }

    [Fact]
    public async Task Phase1State_RecordGeneratedGddAsync_FailsClosedWhenPromptBlockAuthorityChangesAfterRun()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        var service = new GddToModulePhase1StateService(fixture.Store);
        await service.ConfirmSceneRouteAsync(fixture.AccountId, fixture.ProjectId, fixture.DefaultSceneRoute());
        fixture.WriteGdd("# Deckbuilder\n\n- Player must select a route node.\n");
        var runId = await fixture.CreateGddPromptRunAsync("stale-prompt-block");

        using var changedPromptPolicy = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        var result = await service.RecordGeneratedGddAsync(fixture.AccountId, fixture.ProjectId, runId);

        result.Should().NotBeNull();
        result!.Status.Should().Be("blocked");
        result.BlockingIssues.Should().Contain(issue => issue.DomainCode == "gdd_prompt_authority_stale");
        File.Exists(fixture.PathForTest("meta/routes/gdd-document/latest.json")).Should().BeFalse();
    }

    [Fact]
    public async Task Phase1State_RecordGeneratedGddAsync_FailsClosedWhenGeneratedFileChangedAfterRun()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        var service = new GddToModulePhase1StateService(fixture.Store);
        await service.ConfirmSceneRouteAsync(fixture.AccountId, fixture.ProjectId, fixture.DefaultSceneRoute());
        fixture.WriteGdd("# Deckbuilder\n\n- Original generated content.\n");
        var runId = await fixture.CreateGddPromptRunAsync("generated-file-changed");
        fixture.WriteGdd("# Deckbuilder\n\n- Changed after the successful run.\n");

        var result = await service.RecordGeneratedGddAsync(fixture.AccountId, fixture.ProjectId, runId);

        result.Should().NotBeNull();
        result!.Status.Should().Be("blocked");
        result.BlockingIssues.Should().Contain(issue => issue.DomainCode == "gdd_generated_file_run_mismatch");
        File.Exists(fixture.PathForTest("meta/routes/gdd-document/latest.json")).Should().BeFalse();
    }

    [Fact]
    public async Task Phase1State_RecordGeneratedGddAsync_FailsClosedForAnotherProjectsRun()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        var service = new GddToModulePhase1StateService(fixture.Store);
        await service.ConfirmSceneRouteAsync(fixture.AccountId, fixture.ProjectId, fixture.DefaultSceneRoute());
        fixture.WriteGdd("# Deckbuilder\n\n- Player must select a route node.\n");
        var creation = new ProjectCreationService(
            fixture.Store,
            fixture.Options,
            new ProjectRuleCatalog(),
            new ProjectWorkspaceSeeder(fixture.Options, fixture.Store),
            gameTypeMatchService: new FixedGameTypeMatchService());
        var other = await creation.CreateProjectAsync(
            fixture.AccountId,
            new ProjectCreationRequest(null, "Other RPG", "RPG", null, null, null, null));
        var otherProject = await fixture.Store.GetProjectSnapshotAsync(other.ProjectId!);
        var otherRunId = await fixture.Store.CreateRunAsync(other.ProjectId!, otherProject!.WorkspaceId, "game-design-gdd");
        await fixture.Store.CompleteRunAsync(otherRunId, "succeeded", 0, "", "", "{}", CancellationToken.None);

        var result = await service.RecordGeneratedGddAsync(fixture.AccountId, fixture.ProjectId, otherRunId);

        result.Should().NotBeNull();
        result!.Status.Should().Be("blocked");
        result.BlockingIssues.Should().Contain(issue => issue.DomainCode == "gdd_prompt_run_invalid");
    }

    [Fact]
    public async Task Phase1State_GetGddDocumentStateAsync_RejectsIncompleteOrMismatchedWriteThrough()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        var service = new GddToModulePhase1StateService(fixture.Store);
        await service.ConfirmSceneRouteAsync(fixture.AccountId, fixture.ProjectId, fixture.DefaultSceneRoute());
        fixture.WriteGdd("# Deckbuilder\n\n- Player must select a route node.\n");
        var promptRunId = await fixture.CreateGddPromptRunAsync("partial");
        var recorded = await service.RecordGeneratedGddAsync(fixture.AccountId, fixture.ProjectId, promptRunId);
        recorded!.Status.Should().Be("ready");

        var documentNode = JsonNode.Parse(File.ReadAllText(fixture.PathForTest("meta/routes/gdd-document/latest.json"), Encoding.UTF8))!.AsObject();
        documentNode["status"] = "writing";
        fixture.WriteJson("meta/routes/gdd-document/latest.json", documentNode.ToJsonString());
        var incomplete = await service.GetGddDocumentStateAsync(fixture.AccountId, fixture.ProjectId);
        incomplete!.BlockingIssues.Should().Contain(issue => issue.DomainCode == "gdd_document_write_incomplete");

        documentNode["status"] = "ready";
        fixture.WriteJson("meta/routes/gdd-document/latest.json", documentNode.ToJsonString());
        var sceneNode = JsonNode.Parse(File.ReadAllText(fixture.PathForTest("meta/routes/scene-route/latest.json"), Encoding.UTF8))!.AsObject();
        sceneNode["source_generated_gdd_hash"] = "partial-write-hash";
        fixture.WriteJson("meta/routes/scene-route/latest.json", sceneNode.ToJsonString());
        var mismatched = await service.GetGddDocumentStateAsync(fixture.AccountId, fixture.ProjectId);
        mismatched!.BlockingIssues.Should().Contain(issue => issue.DomainCode == "gdd_document_state_stale");
    }

    [Theory]
    [InlineData("authority_changed")]
    [InlineData("source_boundary_missing")]
    [InlineData("prompt_evidence_missing")]
    [InlineData("database_binding_mismatch")]
    public async Task Phase1State_GetGddDocumentStateAsync_RevalidatesPromptSourceBoundary(string scenario)
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        var service = new GddToModulePhase1StateService(fixture.Store);
        await service.ConfirmSceneRouteAsync(fixture.AccountId, fixture.ProjectId, fixture.DefaultSceneRoute());
        fixture.WriteGdd("# Deckbuilder\n\n- Player must select a route node.\n");
        var runId = await fixture.CreateGddPromptRunAsync("readback-" + scenario);
        var recorded = await service.RecordGeneratedGddAsync(fixture.AccountId, fixture.ProjectId, runId);
        recorded!.Status.Should().Be("ready");

        IDisposable? authorityOverride = null;
        try
        {
            switch (scenario)
            {
                case "authority_changed":
                    authorityOverride = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
                    break;
                case "source_boundary_missing":
                {
                    var node = JsonNode.Parse(File.ReadAllText(fixture.PathForTest("meta/routes/gdd-document/latest.json"), Encoding.UTF8))!.AsObject();
                    node.Remove("source_boundary");
                    fixture.WriteJson("meta/routes/gdd-document/latest.json", node.ToJsonString());
                    break;
                }
                case "prompt_evidence_missing":
                    File.Delete(fixture.PathForTest("meta/routes/gdd-document/prompt-evidence.json"));
                    break;
                case "database_binding_mismatch":
                {
                    var binding = (await fixture.Store.ListProjectRoutePromptEvidenceBindingsAsync(fixture.ProjectId))
                        .Single(item => item.RouteId == "gdd-document-generation");
                    await fixture.Store.UpsertProjectRoutePromptEvidenceBindingAsync(new ProjectRoutePromptEvidenceBindingCommand(
                        fixture.ProjectId,
                        binding.RouteId,
                        new string('f', 64),
                        binding.PersistedPromptHash,
                        binding.PromptArtifactRef,
                        binding.PromptEvidenceRef));
                    break;
                }
            }

            var result = await service.GetGddDocumentStateAsync(fixture.AccountId, fixture.ProjectId);

            result.Should().NotBeNull();
            result!.Status.Should().Be("blocked");
            result.BlockingIssues.Should().Contain(issue => issue.DomainCode == "gdd_document_source_boundary_invalid");
        }
        finally
        {
            authorityOverride?.Dispose();
        }
    }

    [Fact]
    public async Task Phase1State_ReadAndWriteOperations_EnforceAccountBoundary()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        var service = new GddToModulePhase1StateService(fixture.Store);

        var confirm = await service.ConfirmSceneRouteAsync("other-account", fixture.ProjectId, fixture.DefaultSceneRoute());
        var sceneReadback = await service.GetSceneRouteAsync("other-account", fixture.ProjectId);
        var gddReadback = await service.GetGddDocumentStateAsync("other-account", fixture.ProjectId);

        confirm.Should().BeNull();
        sceneReadback.Should().BeNull();
        gddReadback.Should().BeNull();
        File.Exists(fixture.PathForTest("meta/routes/scene-route/latest.json")).Should().BeFalse();
    }

    [Fact]
    public async Task RequirementMap_CreateAsync_WritesStableRowsAndSourceBoundary()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        fixture.SeedConfirmedSceneRouteAndGdd();
        var service = new GameDesignRequirementMapService(fixture.Store);

        var result = await service.CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignRequirementMapRequest());

        result.Status.Should().Be("needs_review");
        result.OperationStatus.Should().Be("created_run");
        result.Requirements.Select(item => item.RequirementId).Should().Equal("REQ-001", "REQ-002");
        result.Requirements.Should().Contain(item => item.Kind == "ui");
        result.Requirements.Should().OnlyContain(item => item.AcceptanceMarkers.Contains("structured_llm_fallback:llm_unavailable"));
        var sidecar = fixture.ReadJson("meta/routes/gdd-requirements/latest.json");
        File.ReadAllBytes(fixture.PathForTest("meta/routes/gdd-requirements/latest.json"))
            .Take(3)
            .Should().NotEqual([0xEF, 0xBB, 0xBF]);
        sidecar.RootElement.GetProperty("schema_version").GetString().Should().Be("gdd-requirements.v1");
        sidecar.RootElement.GetProperty("source_boundary_enforced").GetBoolean().Should().BeTrue();
        sidecar.RootElement.GetProperty("source_boundary").GetProperty("recovery_source_order").GetArrayLength()
            .Should().Be(HostedRouteRecoveryContract.SourceOrder.Count);
        File.Exists(fixture.PathForTest("meta/routes/gdd-requirements/prompt-evidence.json")).Should().BeTrue();
        var routeBindings = (await fixture.Store.ListProjectRoutePromptEvidenceBindingsAsync(fixture.ProjectId))
            .ToDictionary(binding => binding.RouteId, StringComparer.Ordinal);
        var routeReadback = new ProjectRouteStateArtifactService(fixture.Store).Read(await fixture.GetProjectAsync(), routeBindings);
        routeReadback.BlockingIssues.Should().NotContain(issue =>
            issue.IssueId.StartsWith("meta/routes/gdd-requirements/latest.json:prompt_evidence", StringComparison.Ordinal));
        sidecar.RootElement.GetProperty("requirements")[0].GetProperty("requirement_id").GetString().Should().Be("REQ-001");
    }

    [Fact]
    public async Task RequirementMap_CreateAsync_ReconcilesRemovedAdminReviewBlockerWithoutErasingHistory()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        fixture.SeedConfirmedSceneRouteAndGdd();
        var obsolete = await fixture.Store.UpsertProjectAdminReviewQueueEntryAsync(new ProjectAdminReviewQueueCommand(
            fixture.AccountId,
            fixture.ProjectId,
            "gdd-requirements",
            "REQ-OBSOLETE",
            "P1",
            "Requirement REQ-OBSOLETE requires review for status conflict.",
            "meta/routes/gdd-requirements/latest.json",
            "[]"));

        await new GameDesignRequirementMapService(fixture.Store)
            .CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignRequirementMapRequest());

        var rows = await fixture.Store.ListProjectAdminReviewQueueForProjectAsync(
            fixture.AccountId,
            fixture.ProjectId,
            "",
            0);
        rows.Should().Contain(row =>
            row.Id == obsolete.Id && row.Status == "superseded" && !string.IsNullOrWhiteSpace(row.SupersededByEntryId));
        var resolved = rows.Should().ContainSingle(row =>
            row.RequirementId == "REQ-OBSOLETE" && row.Status == "resolved" && row.SupersedesEntryId == obsolete.Id).Subject;
        resolved.DecisionStatus.Should().Be("resolved");
        resolved.DecisionActorAccountId.Should().Be("system");
        resolved.DecisionVersion.Should().Be(1);
        resolved.DecidedUtc.Should().NotBeNullOrWhiteSpace();
        await using var connection = new SqliteConnection(fixture.ConnectionString);
        await connection.OpenAsync();
        await using var history = connection.CreateCommand();
        history.CommandText = "SELECT COUNT(*) FROM project_admin_review_decisions WHERE entry_id = $entry_id AND decision_actor_account_id = 'system';";
        history.Parameters.AddWithValue("$entry_id", resolved.Id);
        Convert.ToInt64(await history.ExecuteScalarAsync()).Should().Be(1);
    }

    [Fact]
    public async Task RequirementMap_CreateAsync_UsesStructuredLlmAndPreservesCapabilityEvidence()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        fixture.SeedConfirmedSceneRouteAndGdd();
        var engine = new FixedRequirementMapLlmEngine("""
        {
          "requirements": [
            {
              "requirement_id": "REQ-001",
              "normalized_requirement": "Player selects the next route node.",
              "priority": "P0",
              "kind": "scene",
              "mapped_scene_ids": ["field_map"],
              "mapped_required_module_ids": ["route_map"],
              "status": "mapped",
              "capability_domain_ids": ["ui_layout_scale_coordinates", "ui_input_pointer_gesture"],
              "godot_third_person_camera_profile": {
                "rig_ref": "res://camera/third_person_rig.tscn",
                "target_owner": "player",
                "input_owner": "camera_input",
                "collision_owner": "camera_rig",
                "validation_method": "camera state test",
                "yaw_pitch_ownership": "camera_rig",
                "camera_relative_movement_boundary": "player_motor",
                "camera_state_validation": "camera state smoke"
              },
              "acceptance_markers": ["route node selection is visible"]
            },
            {
              "requirement_id": "REQ-002",
              "normalized_requirement": "HUD shows HP and reward feedback.",
              "priority": "P1",
              "kind": "ui",
              "mapped_scene_ids": ["field_map"],
              "mapped_required_module_ids": ["combat_hud", "reward_panel"],
              "status": "mapped",
              "capability_domain_ids": ["ui_component_system", "ui_overlays_feedback"],
              "godot_ui_update_ownership": {
                "construction_owner": "combat_hud",
                "update_mode": "signal_driven",
                "state_owner": "combat_state",
                "cleanup_policy": "disconnect_signals_on_exit",
                "signal_ownership": "combat_state",
                "stable_item_identity": "reward_id"
              },
              "acceptance_markers": ["HP feedback is visible", "reward selection is actionable"]
            }
          ]
        }
        """);
        var issuer = new HostedContextManifestIssuer(
            fixture.Store,
            new HostedContextManifestSignatureService("test-key", new Dictionary<string, string>
            {
                ["test-key"] = "test-hosted-context-signing-secret"
            }));
        var service = new GameDesignRequirementMapService(fixture.Store, engine, issuer);

        var result = await service.CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignRequirementMapRequest(Model: "gpt-5.1-codex"));

        result.Status.Should().Be("ready");
        engine.Requests.Should().ContainSingle();
        engine.Requests[0].RequireJsonObject.Should().BeTrue();
        engine.Requests[0].OperationKey.Should().Be("llm:gdd-requirement-map");
        engine.Requests[0].ContextEnvelope.Should().NotBeNull();
        var envelope = engine.Requests[0].ContextEnvelope!;
        envelope.AccountId.Should().Be(fixture.AccountId);
        envelope.ProjectId.Should().Be(fixture.ProjectId);
        envelope.OperationKey.Should().Be("llm:gdd-requirement-map");
        envelope.SignatureKeyId.Should().Be("test-key");
        engine.Requests[0].Prompt.Should().NotContain("docs/game-type-guides/");
        result.Requirements[1].CapabilityDomainIds.Should().Contain("ui_overlays_feedback");
        result.Requirements[1].GodotUiUpdateOwnership.Should().NotBeNull();
        result.Requirements[0].GodotThirdPersonCameraProfile.Should().NotBeNull();
        var sidecar = fixture.ReadJson("meta/routes/gdd-requirements/latest.json");
        sidecar.RootElement.GetProperty("requirements")[1].GetProperty("godot_ui_update_ownership").GetProperty("state_owner").GetString().Should().Be("combat_state");
        sidecar.RootElement.GetProperty("source_boundary").GetProperty("prompt_evidence_refs").GetArrayLength().Should().Be(1);
        using var promptEvidence = fixture.ReadJson("meta/routes/gdd-requirements/prompt-evidence.json");
        var promptManifest = promptEvidence.RootElement.GetProperty("prompt_manifest");
        promptManifest.GetProperty("execution_prompt_hash").GetString().Should().Be(
            HostedRouteForbiddenSourceGuard.PromptHash(engine.Requests[0].Prompt));
        var persistedPrompt = File.ReadAllText(fixture.PathForTest("meta/routes/gdd-requirements/prompt.txt"), Encoding.UTF8);
        promptManifest.GetProperty("persisted_prompt_hash").GetString().Should().Be(
            HostedRouteForbiddenSourceGuard.PromptHash(persistedPrompt));
        promptEvidence.RootElement.GetProperty("forbidden_source_scan").GetProperty("prompt_hash").GetString().Should().Be(
            promptManifest.GetProperty("execution_prompt_hash").GetString());
    }

    [Fact]
    public async Task RequirementMap_ReadbackRejectsCoordinatedPromptEvidenceTamperAgainstDatabaseBinding()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        fixture.SeedConfirmedSceneRouteAndGdd();
        await new GameDesignRequirementMapService(fixture.Store)
            .CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignRequirementMapRequest());
        const string tamperedPrompt = "Coordinated replacement prompt.";
        var tamperedHash = HostedRouteForbiddenSourceGuard.PromptHash(tamperedPrompt);
        fixture.WriteText("meta/routes/gdd-requirements/prompt.txt", tamperedPrompt);
        var evidenceNode = JsonNode.Parse(File.ReadAllText(
            fixture.PathForTest("meta/routes/gdd-requirements/prompt-evidence.json"),
            Encoding.UTF8))!.AsObject();
        evidenceNode["prompt_manifest"]!["execution_prompt_hash"] = tamperedHash;
        evidenceNode["prompt_manifest"]!["persisted_prompt_hash"] = tamperedHash;
        evidenceNode["forbidden_source_scan"]!["prompt_hash"] = tamperedHash;
        fixture.WriteJson("meta/routes/gdd-requirements/prompt-evidence.json", evidenceNode.ToJsonString());
        var bindings = (await fixture.Store.ListProjectRoutePromptEvidenceBindingsAsync(fixture.ProjectId))
            .ToDictionary(binding => binding.RouteId, StringComparer.Ordinal);

        var readback = new ProjectRouteStateArtifactService(fixture.Store).Read(await fixture.GetProjectAsync(), bindings);

        readback.BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/gdd-requirements/latest.json:prompt_evidence_invalid" &&
            issue.Severity == "P0");
    }

    [Theory]
    [InlineData("{ invalid", "llm_json_parse_failed")]
    [InlineData("{\"requirements\":[{\"requirement_id\":\"REQ-001\"},{\"requirement_id\":\"REQ-001\"}]}", "duplicate_requirement_id")]
    [InlineData("{\"requirements\":[{\"requirement_id\":\"REQ-001\",\"normalized_requirement\":\"Only one row\",\"priority\":\"P0\",\"kind\":\"scene\",\"mapped_scene_ids\":[\"field_map\"],\"mapped_required_module_ids\":[\"route_map\"],\"status\":\"mapped\"}]}", "llm_requirement_coverage_incomplete")]
    public async Task RequirementMap_CreateAsync_FallsBackToNeedsReviewForInvalidStructuredLlm(string json, string marker)
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        fixture.SeedConfirmedSceneRouteAndGdd();
        var service = new GameDesignRequirementMapService(fixture.Store, new FixedRequirementMapLlmEngine(json));

        var result = await service.CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignRequirementMapRequest());

        result.Status.Should().Be("needs_review");
        result.Requirements.Should().NotBeEmpty();
        result.Requirements.Should().Contain(item => item.AcceptanceMarkers.Contains($"structured_llm_fallback:{marker}"));
    }

    [Fact]
    public async Task RequirementMap_CreateAsync_RejectsSameCountLlmRowsThatReplaceTheDeterministicFloor()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        fixture.SeedConfirmedSceneRouteAndGdd();
        var service = new GameDesignRequirementMapService(fixture.Store, new FixedRequirementMapLlmEngine("""
        {
          "requirements": [
            { "requirement_id": "REQ-101", "normalized_requirement": "Replacement one", "priority": "P0", "kind": "scene", "mapped_scene_ids": ["field_map"], "mapped_required_module_ids": ["field_map"], "status": "mapped" },
            { "requirement_id": "REQ-102", "normalized_requirement": "Replacement two", "priority": "P1", "kind": "ui", "mapped_scene_ids": ["field_map"], "mapped_required_module_ids": ["combat_hud"], "status": "mapped", "capability_domain_ids": ["ui_component_system"] }
          ]
        }
        """));

        var result = await service.CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignRequirementMapRequest());

        result.Status.Should().Be("needs_review");
        result.Requirements.Select(item => item.RequirementId).Should().Equal("REQ-001", "REQ-002");
        result.Requirements.Should().OnlyContain(item => item.AcceptanceMarkers.Contains("structured_llm_fallback:llm_requirement_coverage_incomplete"));
    }

    [Fact]
    public async Task RequirementMap_CreateAsync_ReusesSingleFlightForConcurrentSameProjectRequests()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        fixture.SeedConfirmedSceneRouteAndGdd();
        var engine = new BlockingRequirementMapLlmEngine("""
        {
          "requirements": [
            {
              "requirement_id": "REQ-001",
              "normalized_requirement": "Player moves on the field map.",
              "priority": "P0",
              "kind": "scene",
              "mapped_scene_ids": ["field_map"],
              "mapped_required_module_ids": ["field_map"],
              "status": "mapped"
            },
            {
              "requirement_id": "REQ-002",
              "normalized_requirement": "HUD shows HP and reward feedback.",
              "priority": "P1",
              "kind": "ui",
              "mapped_scene_ids": ["field_map"],
              "mapped_required_module_ids": ["combat_hud"],
              "status": "mapped",
              "capability_domain_ids": ["ui_component_system"]
            }
          ]
        }
        """);
        var service = new GameDesignRequirementMapService(fixture.Store, engine);

        var first = service.CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignRequirementMapRequest(Refresh: true));
        await engine.Started;
        var second = service.CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignRequirementMapRequest());
        await Task.Delay(50);
        engine.CallCount.Should().Be(1);
        engine.Release();

        var results = await Task.WhenAll(first, second);
        results.Select(item => item.SourceRequirementMapHash).Distinct().Should().ContainSingle();
        engine.CallCount.Should().Be(1);
        results.Should().Contain(item => item.OperationStatus == "created_run");
        results.Should().Contain(item => item.OperationStatus == "returned_existing");
    }

    [Theory]
    [InlineData("missing_gdd", "gdd_not_found")]
    [InlineData("missing_scene", "scene_route_missing")]
    [InlineData("unconfirmed_scene", "scene_route_unconfirmed")]
    [InlineData("stale_scene", "scene_route_stale")]
    [InlineData("game_type_hash_mismatch", "game_type_structured_stale")]
    [InlineData("gdd_hash_mismatch", "generated_gdd_hash_mismatch")]
    public async Task RequirementMap_CreateAsync_FailsClosedForInvalidSources(string scenario, string domainCode)
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        fixture.SeedConfirmedSceneRouteAndGdd();
        fixture.ApplyRequirementMapScenario(scenario);
        var service = new GameDesignRequirementMapService(fixture.Store);

        var result = await service.CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignRequirementMapRequest());

        result.Status.Should().Be("blocked");
        result.OperationStatus.Should().Be("rejected");
        result.BlockingIssues.Should().Contain(issue => issue.DomainCode == domainCode);
        var diagnostics = await fixture.Store.ListProjectDiagnosticSpoolForAccountAsync(fixture.AccountId, fixture.ProjectId);
        diagnostics.Should().Contain(item => item.RouteId == "gdd-requirements" && item.FailureFamily == domainCode && item.Severity == "P1");
    }

    [Fact]
    public async Task RequirementMap_CreateAsync_DeduplicatesUnresolvedDiagnosticsAcrossRetries()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        fixture.SeedConfirmedSceneRouteAndGdd();
        fixture.ApplyRequirementMapScenario("missing_gdd");
        var service = new GameDesignRequirementMapService(fixture.Store);

        await service.CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignRequirementMapRequest());
        await service.CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignRequirementMapRequest());

        var diagnostics = await fixture.Store.ListProjectDiagnosticSpoolForAccountAsync(fixture.AccountId, fixture.ProjectId);
        diagnostics.Count(item => item.RouteId == "gdd-requirements" && item.FailureFamily == "gdd_not_found").Should().Be(1);
    }

    [Fact]
    public async Task RequirementMap_CreateAsync_QueuesConflictForAdminReviewAndContractFreezeFailsClosed()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        fixture.SeedConfirmedSceneRouteAndGdd();
        var service = new GameDesignRequirementMapService(fixture.Store, new FixedRequirementMapLlmEngine("""
        {
          "requirements": [
            { "requirement_id": "REQ-001", "normalized_requirement": "First requirement", "priority": "P0", "kind": "scene", "mapped_scene_ids": ["field_map"], "mapped_required_module_ids": ["field_map"], "status": "conflict" },
            { "requirement_id": "REQ-002", "normalized_requirement": "Second requirement", "priority": "P1", "kind": "ui", "mapped_scene_ids": ["field_map"], "mapped_required_module_ids": ["combat_hud"], "status": "mapped", "capability_domain_ids": ["ui_component_system"] }
          ]
        }
        """));

        var requirementMap = await service.CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignRequirementMapRequest());
        var queue = await fixture.Store.ListProjectAdminReviewQueueForProjectAsync(fixture.AccountId, fixture.ProjectId, "open");
        var contract = await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());

        requirementMap.Status.Should().Be("needs_review");
        var queued = queue.Should().ContainSingle(item => item.RequirementId == "REQ-001" && item.RouteId == "gdd-requirements").Subject;
        using (var evidence = JsonDocument.Parse(queued.EvidenceRefsJson))
        {
            var hashSet = evidence.RootElement[0];
            hashSet.GetProperty("source_requirement_map_hash").GetString().Should().Be(requirementMap.SourceRequirementMapHash);
            hashSet.GetProperty("source_gdd_hash").GetString().Should().Be(requirementMap.SourceGddHash);
            hashSet.GetProperty("source_scene_route_hash").GetString().Should().Be(requirementMap.SourceSceneRouteHash);
            hashSet.GetProperty("source_contract_snapshot_hash").GetString().Should().Be(requirementMap.SourceContractSnapshotHash);
            hashSet.GetProperty("source_godot_ui_contract_hash").GetString().Should().Be(requirementMap.SourceGodotUiContractHash);
        }
        contract.Status.Should().Be("blocked");
        contract.BlockingIssues.Should().Contain(issue => issue.DomainCode == "admin_review_blocked");
    }

    [Fact]
    public async Task RequirementMap_CreateAsync_SourceHashChangeSupersedesPriorHumanDecisionEvenWhenRowsStayStable()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        const string firstGdd = """
        # Demo RPG

        - Player must move on the field map and trigger one visible encounter.
        - HUD feedback must show HP, reward, and return-to-map state.
        """;
        const string secondGdd = """
        # Demo RPG


        - Player must move on the field map and trigger one visible encounter.
        - HUD feedback must show HP, reward, and return-to-map state.
        """;
        fixture.SeedConfirmedSceneRouteAndGdd(firstGdd);
        var service = new GameDesignRequirementMapService(fixture.Store, new FixedRequirementMapLlmEngine("""
        {
          "requirements": [
            { "requirement_id": "REQ-001", "normalized_requirement": "Player must move on the field map and trigger one visible encounter.", "priority": "P0", "kind": "scene", "mapped_scene_ids": ["field_map"], "mapped_required_module_ids": ["field_map"], "status": "conflict" },
            { "requirement_id": "REQ-002", "normalized_requirement": "HUD feedback must show HP, reward, and return-to-map state.", "priority": "P1", "kind": "ui", "mapped_scene_ids": ["field_map"], "mapped_required_module_ids": ["combat_hud"], "status": "mapped", "capability_domain_ids": ["ui_component_system"] }
          ]
        }
        """));

        var firstMap = await service.CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignRequirementMapRequest());
        var firstEntry = (await fixture.Store.ListProjectAdminReviewQueueForProjectAsync(fixture.AccountId, fixture.ProjectId, "open")).Single();
        fixture.WriteJson("meta/reviews/first-hash-set.json", "{}");
        (await fixture.Store.DecideProjectAdminReviewQueueEntryAsync(
            firstEntry.Id,
            fixture.AccountId,
            new ProjectAdminReviewDecisionRequest(
                "approved",
                "approved first hash set",
                0,
                ["meta/reviews/first-hash-set.json"]))).Status.Should().Be("updated");

        fixture.SeedConfirmedSceneRouteAndGdd(secondGdd);
        var secondMap = await service.CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignRequirementMapRequest(Refresh: true));
        var rows = await fixture.Store.ListProjectAdminReviewQueueForProjectAsync(fixture.AccountId, fixture.ProjectId, "", 0);

        secondMap.Requirements.Select(item => item.RequirementId).Should().Equal(firstMap.Requirements.Select(item => item.RequirementId));
        secondMap.SourceGddHash.Should().NotBe(firstMap.SourceGddHash);
        rows.Should().Contain(item => item.Id == firstEntry.Id && item.Status == "superseded");
        rows.Should().ContainSingle(item => item.Id != firstEntry.Id && item.Status == "open");
    }

    [Fact]
    public async Task ContractFreeze_FreezeAsync_BlocksNeedsReviewRequirementMapWithoutAdminQueueRow()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        fixture.SeedConfirmedSceneRouteAndGdd();
        await new GameDesignRequirementMapService(fixture.Store, new FixedRequirementMapLlmEngine("{ invalid"))
            .CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignRequirementMapRequest());

        var contract = await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());

        contract.Status.Should().Be("blocked");
        contract.BlockingIssues.Should().Contain(issue => issue.DomainCode == "requirement_map_invalid");
        File.Exists(fixture.PathForTest("routes/prototype-contract/latest.json")).Should().BeFalse();
    }

    [Fact]
    public async Task RequirementMap_CreateAsync_FallsBackToNeedsReviewRowWhenNoRequirementCanBeExtracted()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        fixture.SeedConfirmedSceneRouteAndGdd("# Empty\n\nShort.");
        var service = new GameDesignRequirementMapService(fixture.Store);

        var result = await service.CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignRequirementMapRequest());

        result.Status.Should().Be("needs_review");
        result.Requirements.Should().ContainSingle();
        result.Requirements[0].RequirementId.Should().Be("REQ-001");
        result.Requirements[0].Status.Should().Be("needs_review");
    }

    [Fact]
    public async Task ContractFreeze_FreezeAsync_WritesV2ContractWithSourceHashesAndMirror()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        await fixture.SeedRequirementMapAsync();
        var service = new PrototypeContractFreezeService(fixture.Store);

        var result = await service.FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());

        result.Status.Should().Be("fresh");
        result.ContractHash.Should().NotBeNullOrWhiteSpace();
        result.SourceGddHash.Should().Be(fixture.GddHash);
        result.SourceSceneRouteHash.Should().Be(fixture.SceneRouteHash);
        result.SourceRequirementMapHash.Should().NotBeNullOrWhiteSpace();
        result.SourceGodotUiContractHash.Should().NotBe("unknown").And.NotBeNullOrWhiteSpace();
        result.UiStyleId.Should().Be("godot_cosmic");
        result.UiStyleVersion.Should().Be("1");
        result.SourceUiStyleContractHash.Should().NotBe("unknown").And.NotBeNullOrWhiteSpace();
        result.UiStyleSnapshotHash.Should().NotBe("unknown").And.NotBeNullOrWhiteSpace();
        var canonical = fixture.ReadJson("routes/prototype-contract/latest.json");
        var mirror = fixture.ReadJson("meta/routes/prototype-contract/latest.json");
        canonical.RootElement.GetProperty("schema_version").GetString().Should().Be("prototype-contract.v2");
        canonical.RootElement.GetProperty("status_dimension").GetString().Should().Be(RouteStatusVocabulary.RouteReadback);
        canonical.RootElement.GetProperty("status").GetString().Should().Be("ready");
        canonical.RootElement.GetProperty("status_allowed_values").EnumerateArray()
            .Select(item => item.GetString())
            .Should().Contain("ready");
        canonical.RootElement.GetProperty("source_gdd_hash").GetString().Should().Be(fixture.GddHash);
        mirror.RootElement.GetProperty("contract_hash").GetString().Should().Be(result.ContractHash);
    }

    [Fact]
    public async Task PrototypeContract_WriteFromRequest_PreservesFrozenV2AuthorityAndRepairsMirror()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        await fixture.SeedRequirementMapAsync();
        var frozen = await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        var project = await fixture.GetProjectAsync();
        var canonicalPath = fixture.PathForTest("routes/prototype-contract/latest.json");
        var mirrorPath = fixture.PathForTest("meta/routes/prototype-contract/latest.json");
        var canonicalBefore = File.ReadAllText(canonicalPath, Encoding.UTF8);
        File.WriteAllText(mirrorPath, "{\"schema_version\":1}", Encoding.UTF8);

        var result = new PrototypeContractService().WriteFromRequest(
            project,
            new PrototypeWorkflowRequest(
                "deckbuilder",
                "Changed Name",
                "deckbuilder",
                "manual",
                "Changed hypothesis",
                "Changed fantasy",
                "Changed loop",
                ["Changed success"],
                "Changed feature",
                "Changed gameplay loop",
                "Changed win condition"),
            "docs/prototypes/changed.md",
            "deckbuilder");

        File.ReadAllText(canonicalPath, Encoding.UTF8).Should().Be(canonicalBefore);
        File.ReadAllText(mirrorPath, Encoding.UTF8).Should().Be(canonicalBefore);
        result.Json.Should().Be(canonicalBefore);
        using var document = JsonDocument.Parse(result.Json);
        document.RootElement.GetProperty("contract_hash").GetString().Should().Be(frozen.ContractHash);
    }

    [Fact]
    public async Task ContractFreeze_FreezeAsync_BlocksSceneSemanticTamperWithUnchangedDeclaredHash()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        await fixture.SeedRequirementMapAsync();
        var scenePath = fixture.PathForTest("meta/routes/scene-route/latest.json");
        var scene = JsonNode.Parse(File.ReadAllText(scenePath, Encoding.UTF8))!.AsObject();
        scene["entry_scene"] = "tampered_scene";
        File.WriteAllText(scenePath, scene.ToJsonString(new JsonSerializerOptions { WriteIndented = true }), Encoding.UTF8);

        var result = await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest(Refresh: true));

        result.Status.Should().Be("blocked");
        result.BlockingIssues.Should().Contain(issue =>
            issue.DomainCode == "source_stale" && issue.Severity == "P0");
    }

    [Fact]
    public async Task PrototypeContract_ReadAndWriteFromRequest_FailClosedForTamperedFrozenContract()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        await fixture.SeedRequirementMapAsync();
        await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        var project = await fixture.GetProjectAsync();
        var canonicalPath = fixture.PathForTest("routes/prototype-contract/latest.json");
        var canonical = JsonNode.Parse(File.ReadAllText(canonicalPath, Encoding.UTF8))!.AsObject();
        canonical["source_gdd_hash"] = "tampered-with-old-contract-hash";
        File.WriteAllText(canonicalPath, canonical.ToJsonString(new JsonSerializerOptions { WriteIndented = true }), Encoding.UTF8);
        var service = new PrototypeContractService();

        service.Read(project).Json.Should().BeEmpty();
        var action = () => service.WriteFromRequest(
            project,
            new PrototypeWorkflowRequest(null, null, null, null, null, null, null, null, null, null, null),
            "docs/prototypes/tampered.md",
            "tampered");
        action.Should().Throw<InvalidOperationException>().WithMessage("prototype_contract_frozen_invalid");
    }

    [Fact]
    public async Task ContractFreeze_GetStatusAsync_AcceptsMirrorWithMatchingContractHashAndRejectsMismatch()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        await fixture.SeedRequirementMapAsync();
        var service = new PrototypeContractFreezeService(fixture.Store);
        var frozen = await service.FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        fixture.WriteJson("meta/routes/prototype-contract/latest.json", $$"""
        {
          "schema_version": "prototype-contract.v2",
          "contract_hash": "{{frozen.ContractHash}}",
          "updated_utc": "mirror-readback-only"
        }
        """);

        var matching = await service.GetStatusAsync(fixture.AccountId, fixture.ProjectId);

        matching!.Status.Should().Be("fresh");
        fixture.WriteJson("meta/routes/prototype-contract/latest.json", """
        {
          "schema_version": "prototype-contract.v2",
          "contract_hash": "different"
        }
        """);
        var mismatched = await service.GetStatusAsync(fixture.AccountId, fixture.ProjectId);
        mismatched!.Status.Should().Be("stale");
        mismatched.Freshness.StaleReasons.Should().Contain("mirror_hash_mismatch");
    }

    [Fact]
    public async Task ContractFreeze_GetStatusAsync_RejectsTamperedCanonicalHashAndMissingFreshnessField()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        await fixture.SeedRequirementMapAsync();
        var service = new PrototypeContractFreezeService(fixture.Store);
        await service.FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        var canonicalPath = fixture.PathForTest("routes/prototype-contract/latest.json");
        var node = JsonNode.Parse(File.ReadAllText(canonicalPath, Encoding.UTF8))!.AsObject();
        node["requirement_traceability"] = new JsonArray();
        node.Remove("source_ui_style_contract_hash");
        fixture.WriteJson("routes/prototype-contract/latest.json", node.ToJsonString());

        var status = await service.GetStatusAsync(fixture.AccountId, fixture.ProjectId);

        status!.Status.Should().Be("stale");
        status.Freshness.StaleReasons.Should().Contain("contract_hash_mismatch");
        status.Freshness.StaleReasons.Should().Contain("source_ui_style_contract_hash");
    }

    [Fact]
    public async Task ContractFreeze_FreezeAsync_IsIdempotentForUnchangedSources()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        await fixture.SeedRequirementMapAsync();
        var service = new PrototypeContractFreezeService(fixture.Store);

        var first = await service.FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        var second = await service.FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());

        second.Status.Should().Be("fresh");
        second.OperationStatus.Should().Be("returned_existing");
        second.ContractHash.Should().Be(first.ContractHash);
    }

    [Fact]
    public async Task ContractFreeze_FreezeAsync_SerializesConcurrentSameProjectWrites()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        await fixture.SeedRequirementMapAsync();
        var service = new PrototypeContractFreezeService(fixture.Store);

        var results = await Task.WhenAll(Enumerable.Range(0, 20).Select(index =>
            service.FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest(Refresh: index == 0))));

        results.Should().OnlyContain(item => item.Status == "fresh");
        results.Select(item => item.ContractHash).Distinct().Should().ContainSingle();
        using var canonical = fixture.ReadJson("routes/prototype-contract/latest.json");
        using var mirror = fixture.ReadJson("meta/routes/prototype-contract/latest.json");
        canonical.RootElement.GetProperty("contract_hash").GetString().Should().Be(results[0].ContractHash);
        mirror.RootElement.GetProperty("contract_hash").GetString().Should().Be(results[0].ContractHash);
    }

    [Theory]
    [InlineData("stale_scene", "scene_route_stale")]
    [InlineData("game_type_hash_mismatch", "game_type_structured_stale")]
    [InlineData("game_type_hash_missing", "game_type_structured_stale")]
    [InlineData("gdd_hash_mismatch", "generated_gdd_hash_mismatch")]
    [InlineData("requirement_map_scene_hash_mismatch", "requirement_map_invalid")]
    public async Task ContractFreeze_FreezeAsync_BlocksStaleOrMismatchedSources(string scenario, string domainCode)
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        await fixture.SeedRequirementMapAsync();
        fixture.ApplyContractScenario(scenario);
        var service = new PrototypeContractFreezeService(fixture.Store);

        var result = await service.FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());

        result.Status.Should().Be("blocked");
        result.OperationStatus.Should().Be("rejected");
        result.BlockingIssues.Should().Contain(issue => issue.DomainCode == domainCode);
    }

    [Fact]
    public async Task ContractFreeze_FreezeAsync_BlocksOpenP0P1AdminReviewQueueItems()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        await fixture.SeedRequirementMapAsync();
        await fixture.Store.UpsertProjectAdminReviewQueueEntryAsync(new ProjectAdminReviewQueueCommand(
            fixture.AccountId,
            fixture.ProjectId,
            "gdd-requirements",
            "REQ-001",
            "P1",
            "Requirement conflict requires admin review.",
            "meta/routes/gdd-requirements/latest.json",
            "[]"));
        var service = new PrototypeContractFreezeService(fixture.Store);

        var result = await service.FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());

        result.Status.Should().Be("blocked");
        result.BlockingIssues.Should().Contain(issue => issue.DomainCode == "admin_review_blocked");
        result.BlockingIssues.SelectMany(issue => issue.EvidenceRefs).Should().NotContain(item => item.Path.Contains("metadata:", StringComparison.Ordinal));
        result.BlockingIssues.Should().NotContain(issue => issue.IssueId.Contains("admin-review:", StringComparison.Ordinal));
        var diagnostics = await fixture.Store.ListProjectDiagnosticSpoolForAccountAsync(fixture.AccountId, fixture.ProjectId);
        diagnostics.Should().Contain(item => item.RouteId == "prototype-contract" && item.FailureFamily == "admin_review_blocked");
    }

    [Fact]
    public async Task ContractFreeze_FreezeAsync_DoesNotMissBlockerAfterFiveHundredRows()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        await fixture.SeedRequirementMapAsync();
        for (var index = 0; index < 500; index++)
        {
            await fixture.Store.UpsertProjectAdminReviewQueueEntryAsync(new ProjectAdminReviewQueueCommand(
                fixture.AccountId, fixture.ProjectId, "gdd-requirements", $"REQ-P2-{index:000}", "P2",
                "non-gating review", "meta/routes/gdd-requirements/latest.json", "[]"));
        }
        await fixture.Store.UpsertProjectAdminReviewQueueEntryAsync(new ProjectAdminReviewQueueCommand(
            fixture.AccountId, fixture.ProjectId, "gdd-requirements", "REQ-BEYOND-500", "P1",
            "must remain visible to the gate", "meta/routes/gdd-requirements/latest.json", "[]"));

        var result = await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());

        result.Status.Should().Be("blocked");
        result.BlockingIssues.Should().Contain(issue => issue.DomainCode == "admin_review_blocked");
    }

    [Theory]
    [InlineData("approved", false)]
    [InlineData("deferred", false)]
    [InlineData("resolved", false)]
    [InlineData("rejected", true)]
    [InlineData("backlog", true)]
    public async Task ContractFreeze_FreezeAsync_UsesBoundedAdminReviewBlockingPolicy(string decisionStatus, bool shouldBlock)
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        await fixture.SeedRequirementMapAsync();
        var entry = await fixture.Store.UpsertProjectAdminReviewQueueEntryAsync(new ProjectAdminReviewQueueCommand(
            fixture.AccountId,
            fixture.ProjectId,
            "gdd-requirements",
            "REQ-POLICY",
            "P1",
            "Review policy probe.",
            "meta/routes/gdd-requirements/latest.json",
            "[]"));
        fixture.WriteJson("meta/reviews/policy-decision.json", "{}");
        var request = decisionStatus == "deferred"
            ? new ProjectAdminReviewDecisionRequest(
                decisionStatus,
                "deferred with a bounded recheck",
                0,
                DeferredOwner: "phase-platform",
                 DeferredUntilUtc: "2099-01-01T00:00:00Z",
                 RecheckTrigger: "requirement map refreshed",
                 AffectedRoutes: ["gdd-requirements", "prototype-contract"],
                 DecisionEvidenceRefs: ["meta/reviews/policy-decision.json"])
            : new ProjectAdminReviewDecisionRequest(
                decisionStatus,
                "policy decision",
                0,
                ["meta/reviews/policy-decision.json"]);
        (await fixture.Store.DecideProjectAdminReviewQueueEntryAsync(entry.Id, fixture.AccountId, request))
            .Status.Should().Be("updated");

        var result = await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());

        if (shouldBlock)
        {
            result.Status.Should().Be("blocked");
            result.BlockingIssues.Should().Contain(issue => issue.DomainCode == "admin_review_blocked");
        }
        else
        {
            result.Status.Should().Be("fresh");
            result.BlockingIssues.Should().NotContain(issue => issue.DomainCode == "admin_review_blocked");
        }
    }

    [Fact]
    public async Task ContractFreeze_FreezeAsync_IgnoresSupersededBlockingHistory()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        await fixture.SeedRequirementMapAsync();
        var oldEntry = await fixture.Store.UpsertProjectAdminReviewQueueEntryAsync(new ProjectAdminReviewQueueCommand(
            fixture.AccountId, fixture.ProjectId, "gdd-requirements", "REQ-HISTORY", "P1", "Historical blocker.",
            "meta/routes/gdd-requirements/latest.json", """[{"kind":"sidecar","path":"meta/reviews/old.json"}]"""));
        fixture.WriteJson("meta/reviews/old.json", "{}");
        await fixture.Store.DecideProjectAdminReviewQueueEntryAsync(
            oldEntry.Id,
            fixture.AccountId,
            new ProjectAdminReviewDecisionRequest("rejected", "old evidence rejected", 0, ["meta/reviews/old.json"]));
        var currentEntry = await fixture.Store.UpsertProjectAdminReviewQueueEntryAsync(new ProjectAdminReviewQueueCommand(
            fixture.AccountId, fixture.ProjectId, "gdd-requirements", "REQ-HISTORY", "P1", "Historical blocker.",
            "meta/routes/gdd-requirements/latest.json", """[{"kind":"sidecar","path":"meta/reviews/new.json"}]"""));
        fixture.WriteJson("meta/reviews/new.json", "{}");
        await fixture.Store.DecideProjectAdminReviewQueueEntryAsync(
            currentEntry.Id,
            fixture.AccountId,
            new ProjectAdminReviewDecisionRequest("approved", "new evidence accepted", 0, ["meta/reviews/new.json"]));

        var result = await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());

        result.Status.Should().Be("fresh");
        result.BlockingIssues.Should().NotContain(issue => issue.DomainCode == "admin_review_blocked");
    }

    [Fact]
    public async Task ContractFreeze_FreezeAsync_DoesNotLoseProjectBlockerBehindGlobalQueueLimit()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        await fixture.SeedRequirementMapAsync();
        await fixture.Store.UpsertProjectAdminReviewQueueEntryAsync(new ProjectAdminReviewQueueCommand(
            fixture.AccountId,
            fixture.ProjectId,
            "gdd-requirements",
            "REQ-TARGET",
            "P1",
            "Target project blocker.",
            "meta/routes/gdd-requirements/latest.json",
            "[]"));
        await Task.Delay(5);
        for (var index = 0; index < 500; index++)
        {
            await fixture.Store.UpsertProjectAdminReviewQueueEntryAsync(new ProjectAdminReviewQueueCommand(
                fixture.AccountId,
                $"other-project-{index:D3}",
                "gdd-requirements",
                $"REQ-{index:D3}",
                "P1",
                $"Unrelated blocker {index}.",
                "meta/routes/gdd-requirements/latest.json",
                "[]"));
        }

        var result = await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());

        result.Status.Should().Be("blocked");
        result.BlockingIssues.Should().Contain(issue => issue.DomainCode == "admin_review_blocked");
    }

    [Fact]
    public async Task ProjectMutationLockRegistry_ReclaimsIdleProjectEntries()
    {
        var registry = new ProjectMutationLockRegistry();
        var first = await registry.AcquireAsync("account", "project", CancellationToken.None);
        var secondTask = registry.AcquireAsync("account", "project", CancellationToken.None).AsTask();
        registry.EntryCount.Should().Be(1);
        await first.DisposeAsync();
        var second = await secondTask;
        await second.DisposeAsync();

        registry.EntryCount.Should().Be(0);
    }

    [Fact]
    public async Task DeckbuilderChain_PreservesRouteHandHudRewardAndStyleEvidence()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        fixture.SeedConfirmedSceneRouteAndGdd("""
        # Deckbuilder

        - Player must select a route map node with visible action feedback.
        - Player must drag a hand card with payload identity, cancel, commit, and rollback behavior.
        - Combat HUD must show health, energy, enemy intent, and action feedback.
        - Reward selection must expose actionable card choices and confirmation state.
        """);
        var engine = new FixedRequirementMapLlmEngine("""
        {
          "requirements": [
            {"requirement_id":"REQ-001","normalized_requirement":"Select a route map node.","priority":"P0","kind":"ui","mapped_scene_ids":["field_map"],"mapped_required_module_ids":["route_map"],"status":"mapped","capability_domain_ids":["ui_layout_scale_coordinates","ui_input_pointer_gesture"],"acceptance_markers":["route_map interaction region"]},
            {"requirement_id":"REQ-002","normalized_requirement":"Drag a hand card with cancel, commit, and rollback.","priority":"P1","kind":"input","mapped_scene_ids":["field_map"],"mapped_required_module_ids":["deck_hand"],"status":"mapped","capability_domain_ids":["ui_input_pointer_gesture","ui_state_data_binding"],"acceptance_markers":["payload identity","cancel","commit","rollback","keyboard gamepad equivalent"]},
            {"requirement_id":"REQ-003","normalized_requirement":"Combat HUD shows health, energy, and enemy intent.","priority":"P1","kind":"ui","mapped_scene_ids":["field_map"],"mapped_required_module_ids":["combat_hud"],"status":"mapped","capability_domain_ids":["ui_component_system","ui_overlays_feedback"],"acceptance_markers":["combat HUD feedback visible"]},
            {"requirement_id":"REQ-004","normalized_requirement":"Reward selection exposes actionable card choices.","priority":"P1","kind":"ui","mapped_scene_ids":["field_map"],"mapped_required_module_ids":["reward_panel"],"status":"mapped","capability_domain_ids":["ui_component_system","ui_state_data_binding"],"acceptance_markers":["reward option confirmation"]}
          ]
        }
        """);
        var requirementMap = await new GameDesignRequirementMapService(fixture.Store, engine)
            .CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignRequirementMapRequest(Refresh: true));
        var contract = await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());

        requirementMap.Status.Should().Be("ready", JsonSerializer.Serialize(requirementMap.Requirements));
        requirementMap.Requirements.SelectMany(item => item.MappedRequiredModuleIds).Should().Contain(["route_map", "deck_hand", "combat_hud", "reward_panel"]);
        requirementMap.Requirements.Single(item => item.RequirementId == "REQ-002").AcceptanceMarkers.Should().Contain(["payload identity", "cancel", "commit", "rollback", "keyboard gamepad equivalent"]);
        contract.Status.Should().Be("fresh");
        contract.UiStyleId.Should().Be("godot_cosmic");
        contract.SourceGodotUiContractHash.Should().NotBeNullOrWhiteSpace();
        contract.SourceUiStyleContractHash.Should().NotBeNullOrWhiteSpace();
        contract.UiStyleSnapshotHash.Should().NotBeNullOrWhiteSpace();
    }

    [Fact]
    public async Task NewChainGuard_DoesNotBlockLegacyPrototypeContract()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        fixture.WriteJson("routes/prototype-contract/latest.json", """
        {
          "schema_version": 1,
          "route": "prototype-contract",
          "form_fields": {
            "game_type": "RPG"
          }
        }
        """);
        var project = await fixture.GetProjectAsync();
        var service = new PrototypeContractFreezeService(fixture.Store);

        var guard = service.EvaluateNewChainGuard(project);

        guard.NewChainActive.Should().BeFalse();
        guard.Allowed.Should().BeTrue();
        guard.Status.Should().Be("legacy_compatibility");
    }

    [Fact]
    public async Task NewChainGuard_BlocksExplicitNewChainUntilFreshContractExists()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        fixture.SeedConfirmedSceneRouteAndGdd();
        var project = await fixture.GetProjectAsync();
        var service = new PrototypeContractFreezeService(fixture.Store);

        var guard = service.EvaluateNewChainGuard(project);

        guard.NewChainActive.Should().BeTrue();
        guard.Allowed.Should().BeFalse();
        guard.Status.Should().Be("contract_missing");
    }

    [Fact]
    public async Task IterationPlan_CreateAsync_PersistsFrozenHashesAndClosedRequirementTraceability()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        await fixture.SeedRequirementMapAsync();
        var contract = await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        contract.Status.Should().Be("fresh");
        await fixture.SeedPrototypeSkeletonAsync(contract);
        var service = new PrototypeIterationPlanService(fixture.Store);

        var result = await service.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest(
                "Complete field movement, visible encounter feedback, combat HUD, reward feedback, and return to the map.",
                "manual_feedback"));

        result.Status.Should().Be("ready", result.Summary);
        result.SourceHashes.Should().NotBeNull();
        result.SourceHashes!.SourceGddHash.Should().Be(contract.SourceGddHash);
        result.SourceHashes.SourceRequirementMapHash.Should().Be(contract.SourceRequirementMapHash);
        result.SourceHashes.SourceContractHash.Should().Be(contract.ContractHash);
        result.Coverage!.UncoveredRequirementIds.Should().BeEmpty();
        result.Blockers.Should().BeEmpty();
        result.Goals.Should().OnlyContain(goal => goal.RequirementIds!.Count > 0 || goal.InfrastructureReason != null);
        result.RequiredModules.Should().Contain(module => module.RequirementIds!.Count > 0);

        using var sidecar = fixture.ReadJson("meta/routes/iteration-plan/latest.json");
        sidecar.RootElement.GetProperty("source_gdd_hash").GetString().Should().Be(contract.SourceGddHash);
        sidecar.RootElement.GetProperty("source_contract_hash").GetString().Should().Be(contract.ContractHash);
        sidecar.RootElement.GetProperty("source_godot_ui_contract_hash").GetString().Should().Be(contract.SourceGodotUiContractHash);
        sidecar.RootElement.GetProperty("goals")[0].TryGetProperty("requirement_ids", out _).Should().BeTrue();
        sidecar.RootElement.GetProperty("required_modules").EnumerateArray()
            .Any(module => module.TryGetProperty("source_reason", out _))
            .Should().BeTrue();
        foreach (var goal in result.Goals.Where(goal => goal.InteractionRegion is not null))
        {
            var artifactPath = fixture.PathForTest(goal.InteractionRegion!.ArtifactRef);
            File.Exists(artifactPath).Should().BeTrue(goal.InteractionRegion.ArtifactRef);
            using var artifact = JsonDocument.Parse(File.ReadAllText(artifactPath, Encoding.UTF8));
            artifact.RootElement.GetProperty("validation_status").GetString().Should().Be("contract_validated");
            artifact.RootElement.GetProperty("validation_method").GetString().Should().Be(IterationPlanInteractionArtifactValidator.ValidationMethod);
            artifact.RootElement.GetProperty("validated_utc").GetString().Should().NotBeNullOrWhiteSpace();
            artifact.RootElement.GetProperty("artifact_form").GetString().Should().Be("planned-godot-node-map");
            artifact.RootElement.GetProperty("runtime_validation_required").GetBoolean().Should().BeTrue();
            artifact.RootElement.GetProperty("planned_geometry").EnumerateArray().Should().NotBeEmpty();
            artifact.RootElement.GetProperty("planned_geometry").EnumerateArray().Should().OnlyContain(item =>
                !string.IsNullOrWhiteSpace(item.GetProperty("owner_ref").GetString()) &&
                new[] { "control_rect", "collision_shape" }.Contains(item.GetProperty("geometry_kind").GetString()) &&
                !string.IsNullOrWhiteSpace(item.GetProperty("coordinate_space").GetString()) &&
                item.GetProperty("bounds").ValueKind == JsonValueKind.Null &&
                item.GetProperty("bounds_policy").GetString() == "runtime_resolved" &&
                !string.IsNullOrWhiteSpace(item.GetProperty("locator_ref").GetString()) &&
                !string.IsNullOrWhiteSpace(item.GetProperty("resolution_source").GetString()) &&
                !string.IsNullOrWhiteSpace(item.GetProperty("interaction_role").GetString()));
            artifact.RootElement.GetProperty("region_map").GetString().Should().Contain("OWNERS:");
            artifact.RootElement.GetProperty("scene_node_owners").EnumerateArray()
                .Select(owner => owner.GetString())
                .Should().OnlyContain(owner => owner != null && !owner.StartsWith("owner:", StringComparison.Ordinal));
        }
    }

    [Theory]
    [InlineData(false, "blocked", 0)]
    [InlineData(true, "ready", 1)]
    public async Task IterationPlan_SkeletonCoverageRequiresExplicitVerifiedRequirementBinding(
        bool verified,
        string expectedStatus,
        int expectedSkeletonCoverage)
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        await fixture.SeedRequirementMapAsync("""
        {
          "requirements": [
            { "requirement_id": "REQ-001", "normalized_requirement": "Player moves on the field map.", "priority": "P0", "kind": "scene", "mapped_scene_ids": ["field_map"], "mapped_required_module_ids": [], "mapped_iteration_goal_ids": [], "status": "mapped" },
            { "requirement_id": "REQ-002", "normalized_requirement": "HUD shows HP and reward feedback.", "priority": "P1", "kind": "ui", "mapped_scene_ids": ["field_map"], "mapped_required_module_ids": ["combat_hud"], "status": "mapped", "capability_domain_ids": ["ui_component_system", "ui_overlays_feedback"] }
          ]
        }
        """);
        await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync(verifiedRequirementIds: verified ? ["REQ-001"] : []);

        var result = await new PrototypeIterationPlanService(fixture.Store).CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Create the next iteration plan.", "manual_feedback"));

        result.Status.Should().Be(expectedStatus, result.Summary);
        result.Coverage!.SkeletonCoveredCount.Should().Be(expectedSkeletonCoverage);
        (result.Blockers ?? []).Any(blocker => blocker.DomainCode == "coverage_gap").Should().Be(!verified);
    }

    [Fact]
    public async Task IterationPlan_CreateAsync_RecordsAndDeduplicatesNewChainGuardFailure()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        fixture.SeedConfirmedSceneRouteAndGdd();
        var service = new PrototypeIterationPlanService(fixture.Store);

        var first = await service.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement.", "manual_feedback"));
        var second = await service.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement.", "manual_feedback"));
        var diagnostics = await fixture.Store.ListProjectDiagnosticSpoolForAdminAsync(
            new ProjectDiagnosticSpoolQuery("unresolved", fixture.AccountId, fixture.ProjectId, "iteration-plan", "requirement_map_missing", "P1", 10));

        first.Status.Should().Be("blocked");
        second.Status.Should().Be("blocked");
        diagnostics.Should().ContainSingle();
    }

    [Fact]
    public async Task ExecuteNextAsync_RecordsAndDeduplicatesLegacySourceFailureBeforeRunnerUse()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        var project = await fixture.GetProjectAsync();
        new PrototypeRouteStateWriter().WriteIterationPlanState(project, new
        {
            route = "iteration-plan",
            traceability_contract = "iteration-plan-traceability.v2",
            plan_hash = "legacy-plan-hash"
        });
        var runner = new CountingHostedProcessRunner();
        var service = new PrototypeIterationGoalService(fixture.Store, fixture.Options, runner, new ProjectWorkspaceSeeder(fixture.Options, fixture.Store), heavyRunnerQueue: fixture.Queue);

        var first = await service.ExecuteNextAsync(fixture.AccountId, fixture.ProjectId);
        var second = await service.ExecuteNextAsync(fixture.AccountId, fixture.ProjectId);
        var diagnostics = await fixture.Store.ListProjectDiagnosticSpoolForAdminAsync(
            new ProjectDiagnosticSpoolQuery("unresolved", fixture.AccountId, fixture.ProjectId, "execute-next-goal", "legacy_plan_source_unknown", "P1", 10));

        first.Status.Should().Be("legacy_plan_source_unknown");
        second.Status.Should().Be("legacy_plan_source_unknown");
        diagnostics.Should().ContainSingle();
        runner.CallCount.Should().Be(0);
    }

    [Fact]
    public async Task ExecuteNextAsync_RecordsAndDeduplicatesMissingContractFailureBeforeRunnerUse()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        fixture.SeedConfirmedSceneRouteAndGdd();
        var runner = new CountingHostedProcessRunner();
        var service = new PrototypeIterationGoalService(fixture.Store, fixture.Options, runner, new ProjectWorkspaceSeeder(fixture.Options, fixture.Store), heavyRunnerQueue: fixture.Queue);

        var first = await service.ExecuteNextAsync(fixture.AccountId, fixture.ProjectId);
        var second = await service.ExecuteNextAsync(fixture.AccountId, fixture.ProjectId);
        var diagnostics = await fixture.Store.ListProjectDiagnosticSpoolForAdminAsync(
            new ProjectDiagnosticSpoolQuery("unresolved", fixture.AccountId, fixture.ProjectId, "execute-next-goal", "requirement_map_missing", "P1", 10));

        first.Status.Should().Be("requirement_map_missing");
        second.Status.Should().Be("requirement_map_missing");
        diagnostics.Should().ContainSingle();
        runner.CallCount.Should().Be(0);
    }

    [Fact]
    public async Task IterationPlan_CreateAsync_RedactsAdminReviewRowIdentityAndRawEvidence()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        await fixture.SeedRequirementMapAsync();
        await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync();
        await fixture.Store.UpsertProjectAdminReviewQueueEntryAsync(new ProjectAdminReviewQueueCommand(
            fixture.AccountId,
            fixture.ProjectId,
            "gdd-requirements",
            "REQ-001",
            "P1",
            "Private admin review reason.",
            @"C:\host\private\admin-review.json",
            """[{"kind":"sidecar","path":"meta/reviews/raw-admin-evidence.json"}]"""));
        var adminRows = await fixture.Store.ListProjectAdminReviewQueueForProjectAsync(
            fixture.AccountId,
            fixture.ProjectId,
            "open");

        var result = await new PrototypeIterationPlanService(fixture.Store).CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement.", "manual_feedback"));
        var serialized = JsonSerializer.Serialize(result);

        result.Blockers.Should().ContainSingle(item => item.DomainCode == "admin_review_blocked");
        result.Blockers!.SelectMany(item => item.EvidenceRefs).Should().Equal("admin-review:required");
        serialized.Should().NotContain(adminRows.Single().Id);
        serialized.Should().NotContain(@"C:\host\private");
        serialized.Should().NotContain("raw-admin-evidence");
    }

    [Fact]
    public async Task IterationPlan_CreateAsync_RedactsDiagnosticIdentityAndRawEvidence()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        await fixture.SeedRequirementMapAsync();
        await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync();
        var diagnostic = await fixture.Store.RecordProjectDiagnosticSpoolEntryAsync(new ProjectDiagnosticSpoolCommand(
            fixture.AccountId,
            fixture.ProjectId,
            "prototype",
            "source_stale",
            "P1",
            "Safe summary.",
            "[\"raw-diagnostic-evidence\"]",
            @"C:\host\private\diagnostic.json",
            SourceRefsJson: "[\"C:\\\\host\\\\private\\\\source.json\"]"));

        var result = await new PrototypeIterationPlanService(fixture.Store).CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement.", "manual_feedback"));
        var serialized = JsonSerializer.Serialize(result);

        result.Blockers.Should().ContainSingle(item => item.DomainCode == "diagnostic_blocked");
        result.Blockers!.SelectMany(item => item.EvidenceRefs).Should().Equal("diagnostic:unresolved");
        serialized.Should().NotContain(diagnostic.Id);
        serialized.Should().NotContain(diagnostic.DiagnosticId);
        serialized.Should().NotContain(@"C:\host\private");
        serialized.Should().NotContain("raw-diagnostic-evidence");
    }

    [Theory]
    [InlineData(false, "prototype_skeleton_missing")]
    [InlineData(true, "prototype_skeleton_stale")]
    public async Task IterationPlan_CreateAsync_BlocksMissingOrStaleSkeletonBeforeLlm(
        bool writeStaleSkeleton,
        string expectedDomainCode)
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        await fixture.SeedRequirementMapAsync();
        var contract = await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        if (writeStaleSkeleton)
        {
            await fixture.SeedPrototypeSkeletonAsync(contract, sourceContractHash: "stale-contract-hash");
        }
        var llm = new CountingLlmRouteEngine();
        var service = new PrototypeIterationPlanService(fixture.Store, new PrototypeRouteStateWriter(), llmRouteEngine: llm);

        var first = await service.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement and HUD feedback.", "manual_feedback"));
        var second = await service.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement and HUD feedback.", "manual_feedback"));
        var diagnostics = await fixture.Store.ListProjectDiagnosticSpoolForAdminAsync(
            new ProjectDiagnosticSpoolQuery("unresolved", fixture.AccountId, fixture.ProjectId, "iteration-plan", expectedDomainCode, "P1", 10));

        first.Status.Should().Be("blocked");
        first.Blockers.Should().ContainSingle(item => item.DomainCode == expectedDomainCode);
        second.Status.Should().Be("blocked");
        llm.Requests.Should().BeEmpty();
        diagnostics.Should().ContainSingle();
    }

    [Fact]
    public async Task IterationPlan_CreateAsync_BlocksSkeletonSnapshotOrMirrorDriftBeforeLlm()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        await fixture.SeedRequirementMapAsync();
        var contract = await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync(contract, sourceContractSnapshotHash: "stale-snapshot-hash");
        var llm = new CountingLlmRouteEngine();
        var service = new PrototypeIterationPlanService(fixture.Store, new PrototypeRouteStateWriter(), llmRouteEngine: llm);

        var snapshotDrift = await service.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement.", "manual_feedback"));

        snapshotDrift.Blockers.Should().ContainSingle(item => item.DomainCode == "prototype_skeleton_stale");
        llm.Requests.Should().BeEmpty();

        await using (var connection = new SqliteConnection(fixture.ConnectionString))
        {
            await connection.OpenAsync();
            await using var command = connection.CreateCommand();
            command.CommandText = "UPDATE project_diagnostic_spool SET triage_status = 'resolved' WHERE project_id = $project_id";
            command.Parameters.AddWithValue("$project_id", fixture.ProjectId);
            await command.ExecuteNonQueryAsync();
        }

        var currentProject = await fixture.GetProjectAsync();
        var externalMetaPath = currentProject.MetaPath + "-external";
        Directory.CreateDirectory(externalMetaPath);
        await using (var connection = new SqliteConnection(fixture.ConnectionString))
        {
            await connection.OpenAsync();
            await using var command = connection.CreateCommand();
            command.CommandText = "UPDATE workspaces SET meta_path = $meta_path WHERE project_id = $project_id";
            command.Parameters.AddWithValue("$meta_path", externalMetaPath);
            command.Parameters.AddWithValue("$project_id", fixture.ProjectId);
            await command.ExecuteNonQueryAsync();
        }
        await fixture.SeedPrototypeSkeletonAsync(contract);
        var project = await fixture.GetProjectAsync();
        var mirrorPath = Path.Combine(project.RepoPath, "meta", "routes", "prototype-skeleton", "latest.json");
        var mirror = JsonNode.Parse(File.ReadAllText(mirrorPath, Encoding.UTF8))!.AsObject();
        mirror["status"] = "failed";
        File.WriteAllText(mirrorPath, mirror.ToJsonString(new JsonSerializerOptions { WriteIndented = true }), Encoding.UTF8);

        var mirrorDrift = await service.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement.", "manual_feedback"));

        mirrorDrift.Status.Should().Be("blocked", mirrorDrift.Summary);
        mirrorDrift.Blockers.Should().ContainSingle(
            item => item.DomainCode == "prototype_skeleton_stale",
            string.Join(",", mirrorDrift.Blockers?.Select(item => item.DomainCode) ?? []));
        llm.Requests.Should().BeEmpty();
    }

    [Theory]
    [InlineData("missing_boundary")]
    [InlineData("invalid_top_level_recovery_order")]
    [InlineData("invalid_nested_recovery_order")]
    [InlineData("missing_authority_source")]
    [InlineData("reordered_authority_sources")]
    [InlineData("nested_hash_mismatch")]
    [InlineData("mixed_evidence_refs")]
    public async Task IterationPlan_CreateAsync_BlocksIncompleteSkeletonSourceBoundaryBeforeLlm(string scenario)
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        await fixture.SeedRequirementMapAsync();
        var contract = await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync(contract);
        await fixture.ApplyPrototypeSkeletonBoundaryScenarioAsync(scenario);
        var llm = new CountingLlmRouteEngine();
        var service = new PrototypeIterationPlanService(fixture.Store, new PrototypeRouteStateWriter(), llmRouteEngine: llm);

        var result = await service.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement.", "manual_feedback"));

        result.Status.Should().Be("blocked");
        result.Blockers.Should().ContainSingle(item => item.DomainCode == "prototype_skeleton_stale");
        llm.Requests.Should().BeEmpty();
    }

    [Fact]
    public async Task ExecuteNextAsync_BlocksCapabilityFailureBeforeRunAndDeduplicatesDiagnostic()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        await fixture.SeedRequirementMapAsync();
        await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync();
        var plan = await new PrototypeIterationPlanService(fixture.Store).CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest(
                "Please complete the first full playable loop: stable movement, visible encounter trigger, one battle, reward 3 choices, then return to the map.",
                "manual_feedback"));
        plan.Status.Should().Be("ready", plan.Summary);
        var confirmation = await new PrototypeIterationPlanService(fixture.Store).ConfirmAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanConfirmationRequest(plan.SessionId, plan.PlanHash));
        confirmation.Status.Should().Be("confirmed");
        var details = await fixture.Store.GetLatestProjectIterationSessionAsync(fixture.ProjectId);
        var readyEvaluation = JsonSerializer.Serialize(new PrototypeIterationPlanEvaluationResult(
            "ready_to_execute",
            "Ready for preflight.",
            "Test fixture isolates capability preflight.",
            "execute_next_goal"));
        await fixture.Store.UpdateProjectIterationSessionStatusAsync(
            details!.Session.SessionId,
            "ready",
            0,
            details.Session.LatestSummary,
            readyEvaluation,
            null);
        var sidecarPath = fixture.PathForTest("meta/routes/iteration-plan/latest.json");
        var sidecar = JsonNode.Parse(File.ReadAllText(sidecarPath, Encoding.UTF8))!.AsObject();
        var firstGoal = sidecar["goals"]![0]!.AsObject();
        firstGoal["capability_requirements"]!["dynamic_ui_required"] = true;
        firstGoal["godot_ui_update_ownership"] = JsonNode.Parse("""
        {
          "construction_owner": "HudPanel",
          "update_mode": "signal_driven",
          "state_owner": "GameState",
          "cleanup_policy": "disconnect_on_exit",
          "stable_item_identity": "hud_row_id"
        }
        """);
        new PrototypeRouteStateWriter().WriteIterationPlanState(await fixture.GetProjectAsync(), sidecar);
        var runner = new CountingHostedProcessRunner();
        var service = new PrototypeIterationGoalService(fixture.Store, fixture.Options, runner, new ProjectWorkspaceSeeder(fixture.Options, fixture.Store), heavyRunnerQueue: fixture.Queue);

        var first = await service.ExecuteNextAsync(fixture.AccountId, fixture.ProjectId);
        var second = await service.ExecuteNextAsync(fixture.AccountId, fixture.ProjectId);
        var diagnostics = await fixture.Store.ListProjectDiagnosticSpoolForAdminAsync(
            new ProjectDiagnosticSpoolQuery("unresolved", fixture.AccountId, fixture.ProjectId, "execute-next-goal", "plan_hash_mismatch", "P1", 10));

        first.Status.Should().Be("plan_hash_mismatch");
        second.Status.Should().Be("plan_hash_mismatch");
        runner.CallCount.Should().Be(0);
        diagnostics.Should().ContainSingle();
    }

    [Fact]
    public async Task ExecuteNextAsync_ShouldRepairInteractionOwnerTamperingFromDatabaseCanonicalState()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        await fixture.SeedRequirementMapAsync();
        await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync();
        var planService = new PrototypeIterationPlanService(fixture.Store);
        var plan = await planService.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement and HUD feedback.", "manual_feedback"));
        plan.Status.Should().Be("ready", plan.Summary);
        (await planService.ConfirmAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanConfirmationRequest(plan.SessionId, plan.PlanHash))).Status.Should().Be("confirmed");
        var details = await fixture.Store.GetLatestProjectIterationSessionAsync(fixture.ProjectId);
        var interactionGoal = plan.Goals.First(goal => goal.InteractionRegion is not null);
        foreach (var earlierGoal in details!.Goals.Where(goal => goal.GoalIndex < interactionGoal.GoalIndex))
        {
            await fixture.Store.UpdateProjectIterationGoalStatusAsync(earlierGoal.GoalId, "succeeded", "Completed before tamper target.", DateTimeOffset.UtcNow.ToString("O"));
        }
        details = await fixture.Store.GetLatestProjectIterationSessionAsync(fixture.ProjectId);
        await fixture.Store.UpdateProjectIterationSessionStatusAsync(
            details!.Session.SessionId,
            "ready",
            interactionGoal.GoalIndex - 1,
            details.Session.LatestSummary,
            JsonSerializer.Serialize(new PrototypeIterationPlanEvaluationResult(
                "ready_to_execute",
                "Ready for interaction tamper test.",
                "The test changes only the validated artifact owner set.",
                "execute_next_goal")),
            null);
        var artifactPath = fixture.PathForTest(interactionGoal.InteractionRegion!.ArtifactRef);
        var artifact = JsonNode.Parse(File.ReadAllText(artifactPath, Encoding.UTF8))!.AsObject();
        artifact["scene_node_owners"] = new JsonArray("module:tampered:interaction-owner");
        File.WriteAllText(artifactPath, artifact.ToJsonString(new JsonSerializerOptions { WriteIndented = true }), Encoding.UTF8);
        var runner = new CountingHostedProcessRunner();
        var service = new PrototypeIterationGoalService(fixture.Store, fixture.Options, runner, new ProjectWorkspaceSeeder(fixture.Options, fixture.Store), heavyRunnerQueue: fixture.Queue);

        var result = await service.ExecuteNextAsync(fixture.AccountId, fixture.ProjectId);

        result.Status.Should().NotBe("interaction_region_missing");
        runner.CallCount.Should().Be(0);
        using var repaired = JsonDocument.Parse(File.ReadAllText(artifactPath, Encoding.UTF8));
        repaired.RootElement.GetProperty("scene_node_owners").EnumerateArray()
            .Select(static item => item.GetString())
            .Should().NotContain("module:tampered:interaction-owner");
    }

    [Fact]
    public async Task IterationPlan_ConfirmationIsHashBoundIdempotentAndRegenerationInvalidatesIt()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        await fixture.SeedRequirementMapAsync();
        await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync();
        var service = new PrototypeIterationPlanService(fixture.Store);
        var firstPlan = await service.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement and HUD feedback.", "manual_feedback"));

        var confirmed = await service.ConfirmAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanConfirmationRequest(firstPlan.SessionId, firstPlan.PlanHash));
        var retry = await service.ConfirmAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanConfirmationRequest(firstPlan.SessionId, firstPlan.PlanHash));
        var conflict = await service.ConfirmAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanConfirmationRequest(firstPlan.SessionId, "other-plan-hash"));
        var regenerated = await service.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Create a new iteration plan for field movement, HUD feedback, and reward state.", "new_iteration_plan"));

        confirmed.Status.Should().Be("confirmed");
        confirmed.OperationStatus.Should().Be("created_run");
        retry.OperationStatus.Should().Be("returned_existing");
        conflict.Status.Should().Be("conflict");
        conflict.DomainCode.Should().Be("plan_hash_conflict");
        regenerated.SessionId.Should().NotBe(firstPlan.SessionId);
        regenerated.Confirmation!.Status.Should().Be("unconfirmed");
        var rounds = await service.ListAsync(fixture.AccountId, fixture.ProjectId);
        rounds.Should().HaveCount(2);
        rounds[0].RequiredModules.Should().NotBeNullOrEmpty();
        rounds[0].RequiredModules.Should().Contain(module => module.RequirementIds != null && module.RequirementIds.Count > 0);
        rounds[0].TraceabilityGoals.Should().NotBeNullOrEmpty();
        rounds[0].Confirmation!.Status.Should().Be("confirmed");
        rounds[1].Confirmation!.Status.Should().Be("unconfirmed");
    }

    [Fact]
    public async Task IterationPlan_ConfirmedDbAnchorCannotBeReplacedByRecomputedWorkspacePlan()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        await fixture.SeedRequirementMapAsync();
        await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync();
        var service = new PrototypeIterationPlanService(fixture.Store);
        var plan = await service.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement and HUD feedback.", "manual_feedback"));
        (await service.ConfirmAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanConfirmationRequest(plan.SessionId, plan.PlanHash))).Status.Should().Be("confirmed");
        var project = await fixture.GetProjectAsync();
        var state = JsonNode.Parse(new PrototypeRouteStateWriter().ReadLatestIterationPlanState(project))!.AsObject();
        state["goals"]![0]!["description"] = "Tampered but rehashed plan.";
        using (var document = JsonDocument.Parse(state.ToJsonString()))
        {
            state["plan_hash"] = IterationPlanIntegrity.Compute(document.RootElement);
        }
        state["confirmation"] = new JsonObject
        {
            ["status"] = "unconfirmed",
            ["session_id"] = plan.SessionId,
            ["plan_hash"] = state["plan_hash"]!.GetValue<string>(),
            ["source_hash_ref"] = state["source_hash_ref"]!.GetValue<string>()
        };
        new PrototypeRouteStateWriter().WriteIterationPlanState(project, state);

        var result = await service.ConfirmAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanConfirmationRequest(plan.SessionId, state["plan_hash"]!.GetValue<string>()));
        var details = await fixture.Store.GetLatestProjectIterationSessionAsync(fixture.ProjectId);

        result.Status.Should().Be("conflict");
        result.DomainCode.Should().Be("plan_hash_conflict");
        details!.Session.TraceabilityAnchorJson.Should().Contain(plan.PlanHash);
    }

    [Fact]
    public async Task IterationPlan_ReadbackRequiresReconfirmationWhenDbAnchorIsMissing()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        await fixture.SeedRequirementMapAsync();
        await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync();
        var service = new PrototypeIterationPlanService(fixture.Store);
        var plan = await service.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement and HUD feedback.", "manual_feedback"));
        (await service.ConfirmAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanConfirmationRequest(plan.SessionId, plan.PlanHash))).Status.Should().Be("confirmed");
        await using (var connection = new SqliteConnection(fixture.ConnectionString))
        {
            await connection.OpenAsync();
            await using var command = connection.CreateCommand();
            command.CommandText = "UPDATE project_iteration_sessions SET traceability_anchor_json = NULL WHERE id = $session_id";
            command.Parameters.AddWithValue("$session_id", plan.SessionId);
            await command.ExecuteNonQueryAsync();
        }

        var readback = await service.GetLatestAsync(fixture.AccountId, fixture.ProjectId);

        readback!.Confirmation!.Status.Should().Be("reconfirm_required");
    }

    [Fact]
    public async Task ConfirmAsync_RestoresCanonicalStateFromDatabaseWhenBothSidecarsAreMissing()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        await fixture.SeedRequirementMapAsync();
        await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync();
        var service = new PrototypeIterationPlanService(fixture.Store);
        var plan = await service.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement and HUD feedback.", "manual_feedback"));
        var project = await fixture.GetProjectAsync();
        new PrototypeRouteStateWriter().ClearIterationPlanState(project);
        new PrototypeRouteStateWriter().DeleteIterationPlanSessionState(project, plan.SessionId);

        var confirmation = await service.ConfirmAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanConfirmationRequest(plan.SessionId, plan.PlanHash));

        confirmation.Status.Should().Be("confirmed");
        new PrototypeRouteStateWriter().ReadLatestIterationPlanState(project).Should().Contain(plan.SessionId);
        new PrototypeRouteStateWriter().ReadIterationPlanSessionState(project, plan.SessionId).Should().Contain(plan.PlanHash);
    }

    [Fact]
    public async Task ExecuteNextAsync_RestoresConfirmedSidecarFromTrustedDatabaseAnchor()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        await fixture.SeedRequirementMapAsync();
        await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync();
        var planService = new PrototypeIterationPlanService(fixture.Store);
        var plan = await planService.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement and HUD feedback.", "manual_feedback"));
        (await planService.ConfirmAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanConfirmationRequest(plan.SessionId, plan.PlanHash))).Status.Should().Be("confirmed");
        var details = await fixture.Store.GetLatestProjectIterationSessionAsync(fixture.ProjectId);
        foreach (var goal in details!.Goals)
        {
            await fixture.Store.UpdateProjectIterationGoalStatusAsync(
                goal.GoalId,
                "succeeded",
                "Completed for sidecar recovery test.",
                DateTimeOffset.UtcNow.ToString("O"));
        }
        var project = await fixture.GetProjectAsync();
        var state = JsonNode.Parse(new PrototypeRouteStateWriter().ReadLatestIterationPlanState(project))!.AsObject();
        state["confirmation"]!["status"] = "unconfirmed";
        new PrototypeRouteStateWriter().WriteIterationPlanState(project, state);

        var result = await new PrototypeIterationGoalService(fixture.Store, fixture.Options, new CountingHostedProcessRunner(), new ProjectWorkspaceSeeder(fixture.Options, fixture.Store), heavyRunnerQueue: fixture.Queue)
            .ExecuteNextAsync(fixture.AccountId, fixture.ProjectId);
        var repaired = JsonNode.Parse(new PrototypeRouteStateWriter().ReadLatestIterationPlanState(project))!.AsObject();

        result.Status.Should().NotBe("plan_confirmation_required");
        repaired["confirmation"]!["status"]!.GetValue<string>().Should().Be("confirmed");
        repaired["confirmation"]!["plan_hash"]!.GetValue<string>().Should().Be(plan.PlanHash);
    }

    [Fact]
    public async Task IterationPlan_ConcurrentSameRequestReusesSingleSession()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        await fixture.SeedRequirementMapAsync();
        await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync();
        var service = new PrototypeIterationPlanService(fixture.Store);
        var request = new PrototypeIterationPlanRequest("Complete field movement and HUD feedback.", "manual_feedback");

        var results = await Task.WhenAll(Enumerable.Range(0, 4).Select(_ =>
            service.CreateAsync(fixture.AccountId, fixture.ProjectId, request)));

        results.Select(result => result.SessionId).Distinct(StringComparer.Ordinal).Should().ContainSingle();
        results.Count(result => result.OperationStatus == "created_run").Should().Be(1);
        results.Count(result => result.OperationStatus is "returned_existing" or "active_run_reused").Should().Be(3);
    }

    [Fact]
    public async Task IterationPlan_DatabaseIdentityConstraintRejectsSecondStoreDuplicate()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        var secondStore = new PhaseAMetadataStore(fixture.ConnectionString, fixture.Options);
        const string identity = "shared-request-identity";
        var goals = new[] { new ProjectIterationGoalCreateCommand(1, "Goal", "Goal", "Acceptance") };

        var attempts = await Task.WhenAll(
            TryCreate(fixture.Store, "session-a"),
            TryCreate(secondStore, "session-b"));
        var persisted = await fixture.Store.GetProjectIterationSessionByRequestIdentityAsync(
            fixture.AccountId,
            fixture.ProjectId,
            identity);

        attempts.Count(static created => created).Should().Be(1);
        persisted.Should().NotBeNull();

        async Task<bool> TryCreate(PhaseAMetadataStore store, string sessionId)
        {
            try
            {
                await store.CreateProjectIterationSessionAsync(
                    fixture.AccountId,
                    fixture.ProjectId,
                    "manual_feedback",
                    "Same request.",
                    "Plan",
                    goals,
                    sessionId: sessionId,
                    requestIdentityHash: identity,
                    routeStateJson: $"{{\"session_id\":\"{sessionId}\",\"request_identity_hash\":\"{identity}\",\"status\":\"ready\"}}",
                    initialStatus: "ready");
                return true;
            }
            catch (ProjectIterationRequestIdentityConflictException)
            {
                return false;
            }
        }
    }

    [Fact]
    public async Task IterationPlan_RetryRecoversCanonicalPlanFromDatabaseWhenSidecarsAreMissing()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        await fixture.SeedRequirementMapAsync();
        await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync();
        var service = new PrototypeIterationPlanService(fixture.Store);
        var request = new PrototypeIterationPlanRequest(
            "Complete field movement and HUD feedback.",
            "manual_feedback");
        var first = await service.CreateAsync(fixture.AccountId, fixture.ProjectId, request);
        (await service.ConfirmAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanConfirmationRequest(first.SessionId, first.PlanHash))).Status.Should().Be("confirmed");
        var project = await fixture.GetProjectAsync();
        var latestPath = Path.Combine(project.MetaPath, "routes", "iteration-plan", "latest.json");
        var sessionPath = Path.Combine(project.MetaPath, "routes", "iteration-plan", "sessions", $"{first.SessionId}.json");
        var latestMirrorPath = Path.Combine(project.RepoPath, "meta", "routes", "iteration-plan", "latest.json");
        var sessionMirrorPath = Path.Combine(project.RepoPath, "meta", "routes", "iteration-plan", "sessions", $"{first.SessionId}.json");
        File.Delete(latestPath);
        File.Delete(sessionPath);
        File.Delete(latestMirrorPath);
        File.Delete(sessionMirrorPath);
        foreach (var goal in first.Goals.Where(static goal => goal.InteractionRegion is not null))
        {
            File.WriteAllText(fixture.PathForTest(goal.InteractionRegion!.ArtifactRef), "{ invalid", Encoding.UTF8);
        }

        var latestWithoutSidecars = await service.GetLatestAsync(fixture.AccountId, fixture.ProjectId);
        var roundsWithoutSidecars = await service.ListAsync(fixture.AccountId, fixture.ProjectId);

        latestWithoutSidecars!.PlanHash.Should().Be(first.PlanHash);
        latestWithoutSidecars.RequiredModules.Should().NotBeNullOrEmpty();
        latestWithoutSidecars.Confirmation!.Status.Should().Be("confirmed");
        roundsWithoutSidecars.Should().ContainSingle();
        roundsWithoutSidecars[0].PlanHash.Should().Be(first.PlanHash);
        roundsWithoutSidecars[0].RequiredModules.Should().NotBeNullOrEmpty();
        roundsWithoutSidecars[0].Confirmation!.Status.Should().Be("confirmed");

        var retry = await service.CreateAsync(fixture.AccountId, fixture.ProjectId, request);
        var rounds = await service.ListAsync(fixture.AccountId, fixture.ProjectId);

        retry.SessionId.Should().Be(first.SessionId);
        retry.OperationStatus.Should().Be("returned_existing");
        retry.Confirmation!.Status.Should().Be("confirmed");
        rounds.Should().ContainSingle();
        File.Exists(latestPath).Should().BeTrue();
        File.Exists(sessionPath).Should().BeTrue();
        File.Exists(latestMirrorPath).Should().BeTrue();
        File.Exists(sessionMirrorPath).Should().BeTrue();
        JsonNode.Parse(File.ReadAllText(latestPath, Encoding.UTF8))!["confirmation"]!["status"]!
            .GetValue<string>().Should().Be("confirmed");
        first.Goals.Where(static goal => goal.InteractionRegion is not null)
            .Should().OnlyContain(goal => File.Exists(fixture.PathForTest(goal.InteractionRegion!.ArtifactRef)));
    }

    [Fact]
    public async Task IterationPlan_RetryDoesNotResurrectOlderDatabasePlanOverNewerSession()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        await fixture.SeedRequirementMapAsync();
        await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync();
        var service = new PrototypeIterationPlanService(fixture.Store);
        var request = new PrototypeIterationPlanRequest(
            "Complete field movement and HUD feedback.",
            "manual_feedback");
        var first = await service.CreateAsync(fixture.AccountId, fixture.ProjectId, request);
        var project = await fixture.GetProjectAsync();
        new PrototypeRouteStateWriter().ClearIterationPlanState(project);
        new PrototypeRouteStateWriter().DeleteIterationPlanSessionState(project, first.SessionId);
        var newer = await fixture.Store.CreateProjectIterationSessionAsync(
            fixture.AccountId,
            fixture.ProjectId,
            "new_iteration_plan",
            "A newer plan already exists.",
            "Newer plan",
            [new ProjectIterationGoalCreateCommand(1, "Newer goal", "Newer goal", "Newer acceptance")]);
        await fixture.Store.UpdateProjectIterationSessionStatusAsync(
            newer.SessionId,
            "ready",
            0,
            "Newer plan is ready.");

        var retry = await service.CreateAsync(fixture.AccountId, fixture.ProjectId, request);
        var latest = await fixture.Store.GetLatestProjectIterationSessionAsync(fixture.ProjectId);
        var latestState = new PrototypeRouteStateWriter().ReadLatestIterationPlanState(project);

        retry.SessionId.Should().Be(first.SessionId);
        retry.OperationStatus.Should().Be("returned_existing");
        latest!.Session.SessionId.Should().Be(newer.SessionId);
        latestState.Should().BeEmpty("a historical idempotent retry must not restore itself as the latest route state");
    }

    [Fact]
    public async Task IterationPlanSessionSnapshot_SerializationHidesCanonicalDatabaseFields()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        var session = await fixture.Store.CreateProjectIterationSessionAsync(
            fixture.AccountId,
            fixture.ProjectId,
            "manual_feedback",
            "Create a plan.",
            "Plan",
            [new ProjectIterationGoalCreateCommand(1, "Goal", "Goal", "Acceptance")],
            requestIdentityHash: "private-request-hash",
            routeStateJson: "{\"private\":true}");
        var serialized = JsonSerializer.Serialize(session);

        serialized.Should().NotContain("traceabilityAnchorJson");
        serialized.Should().NotContain("requestIdentityHash");
        serialized.Should().NotContain("routeStateJson");
        serialized.Should().NotContain("private-request-hash");
    }

    [Fact]
    public async Task NeedsFixStrict_ShouldRejectUnknownGoalWithoutRunningProjectLevelRepair()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        await fixture.SeedRequirementMapAsync();
        await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync();
        var planService = new PrototypeIterationPlanService(fixture.Store);
        var plan = await planService.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement and HUD feedback.", "manual_feedback"));
        plan.Status.Should().Be("ready", plan.Summary);
        (await planService.ConfirmAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanConfirmationRequest(plan.SessionId, plan.PlanHash))).Status.Should().Be("confirmed");
        var runner = new CountingHostedProcessRunner();
        var service = new PrototypeNeedsFixRouteService(
            fixture.Store,
            new PrototypeQuickFixService(fixture.Store, fixture.Options, runner, new ProjectWorkspaceSeeder(fixture.Options, fixture.Store), new SkillActionCatalog(), heavyRunnerQueue: fixture.Queue),
            new PrototypeRouteStateWriter());

        var result = await service.RunStrictAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeNeedsFixRouteRequest("repair", GoalId: "missing-goal", GoalIndex: 999));

        result.Status.Should().Be("iteration_goal_not_found");
        runner.CallCount.Should().Be(0);

        var details = await fixture.Store.GetLatestProjectIterationSessionAsync(fixture.ProjectId);
        var pendingGoal = details!.Goals.First(goal => goal.Status == "pending");
        var pendingResult = await service.RunStrictAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeNeedsFixRouteRequest("repair pending", GoalId: pendingGoal.GoalId, GoalIndex: pendingGoal.GoalIndex));

        pendingResult.Status.Should().Be("iteration_goal_not_repairable");
        runner.CallCount.Should().Be(0);

        await fixture.Store.UpdateProjectIterationGoalStatusAsync(
            pendingGoal.GoalId,
            "needs_fix",
            "Needs repair for diagnostic coverage.",
            DateTimeOffset.UtcNow.ToString("O"));
        await fixture.Store.UpdateProjectIterationSessionStatusAsync(
            details.Session.SessionId,
            "needs_fix",
            pendingGoal.GoalIndex,
            "Needs repair for diagnostic coverage.",
            details.Session.LatestEvaluationJson,
            null);
        var project = await fixture.GetProjectAsync();
        var state = JsonNode.Parse(new PrototypeRouteStateWriter().ReadLatestIterationPlanState(project))!.AsObject();
        state["source_contract_hash"] = "tampered-contract-hash";
        new PrototypeRouteStateWriter().WriteIterationPlanState(project, state);

        var firstPreflightFailure = await service.RunStrictAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeNeedsFixRouteRequest("repair", GoalId: pendingGoal.GoalId, GoalIndex: pendingGoal.GoalIndex));
        var secondPreflightFailure = await service.RunStrictAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeNeedsFixRouteRequest("repair", GoalId: pendingGoal.GoalId, GoalIndex: pendingGoal.GoalIndex));
        var diagnostics = await fixture.Store.ListProjectDiagnosticSpoolForAdminAsync(
            new ProjectDiagnosticSpoolQuery("unresolved", fixture.AccountId, fixture.ProjectId, "needs-fix", "source_stale", "P1", 10));

        firstPreflightFailure.Status.Should().Be("source_stale");
        secondPreflightFailure.Status.Should().Be("source_stale");
        diagnostics.Should().ContainSingle();
        runner.CallCount.Should().Be(0);
    }

    [Fact]
    public async Task ExecuteNextAsync_ShouldReleaseRunnerLock_WhenGoalRunClaimFails()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        await fixture.SeedRequirementMapAsync();
        await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync();
        var planService = new PrototypeIterationPlanService(fixture.Store);
        var plan = await planService.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement and HUD feedback.", "manual_feedback"));
        plan.Status.Should().Be("ready", plan.Summary);
        (await planService.ConfirmAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanConfirmationRequest(plan.SessionId, plan.PlanHash))).Status.Should().Be("confirmed");
        var details = await fixture.Store.GetLatestProjectIterationSessionAsync(fixture.ProjectId);
        await fixture.Store.UpdateProjectIterationSessionStatusAsync(
            details!.Session.SessionId,
            "ready",
            0,
            details.Session.LatestSummary,
            JsonSerializer.Serialize(new PrototypeIterationPlanEvaluationResult(
                "ready_to_execute",
                "Ready for claim failure test.",
                "The test forces the goal-run link to fail.",
                "execute_next_goal")),
            null);
        await using (var connection = new SqliteConnection(fixture.ConnectionString))
        {
            await connection.OpenAsync();
            await using var command = connection.CreateCommand();
            command.CommandText = """
                CREATE TRIGGER fail_iteration_goal_run_claim
                BEFORE INSERT ON project_iteration_goal_runs
                BEGIN
                    SELECT RAISE(ABORT, 'forced goal-run claim failure');
                END;
                """;
            await command.ExecuteNonQueryAsync();
        }
        var runner = new CountingHostedProcessRunner();
        var service = new PrototypeIterationGoalService(fixture.Store, fixture.Options, runner, new ProjectWorkspaceSeeder(fixture.Options, fixture.Store), heavyRunnerQueue: fixture.Queue);

        var result = await service.ExecuteNextAsync(fixture.AccountId, fixture.ProjectId);
        var project = await fixture.GetProjectAsync();
        var probeRunId = await fixture.Store.CreateRunAsync(fixture.ProjectId, project.WorkspaceId, "runner-lock-probe");
        var reacquired = await fixture.Store.TryAcquireRunnerLockAsync(fixture.ProjectId, probeRunId);

        result.Status.Should().Be("failed");
        reacquired.Should().BeTrue();
        runner.CallCount.Should().Be(0);
        await fixture.Store.ReleaseRunnerLockAsync(fixture.ProjectId, probeRunId);
    }

    [Fact]
    public async Task ExecuteNextAsync_ShouldHoldProjectMutationLeaseUntilExecutionFinishes()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        await fixture.SeedRequirementMapAsync();
        await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync();
        var planService = new PrototypeIterationPlanService(fixture.Store);
        var plan = await planService.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement and HUD feedback.", "manual_feedback"));
        (await planService.ConfirmAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanConfirmationRequest(plan.SessionId, plan.PlanHash))).Status.Should().Be("confirmed");
        var details = await fixture.Store.GetLatestProjectIterationSessionAsync(fixture.ProjectId);
        await fixture.Store.UpdateProjectIterationSessionStatusAsync(
            details!.Session.SessionId,
            "ready",
            0,
            details.Session.LatestSummary,
            JsonSerializer.Serialize(new PrototypeIterationPlanEvaluationResult(
                "ready_to_execute",
                "Ready for mutation lease test.",
                "The runner blocks while confirmation attempts to acquire the same lease.",
                "execute_next_goal")),
            null);
        var project = await fixture.GetProjectAsync();
        new PrototypeRouteStateWriter().WritePrototypeState(project, new
        {
            route = "prototype-7day-playable",
            status = "succeeded",
            prototype_completion = new { succeeded = true }
        });
        var runner = new BlockingHostedProcessRunner();
        var executionService = new PrototypeIterationGoalService(fixture.Store, fixture.Options, runner, new ProjectWorkspaceSeeder(fixture.Options, fixture.Store), heavyRunnerQueue: fixture.Queue);

        var executionTask = executionService.ExecuteNextAsync(fixture.AccountId, fixture.ProjectId);
        await runner.Started.Task.WaitAsync(TimeSpan.FromSeconds(10));
        var confirmationTask = planService.ConfirmAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanConfirmationRequest(plan.SessionId, plan.PlanHash));
        await Task.Delay(150);

        confirmationTask.IsCompleted.Should().BeFalse();
        runner.Release.TrySetResult();
        await executionTask.WaitAsync(TimeSpan.FromSeconds(20));
        (await confirmationTask.WaitAsync(TimeSpan.FromSeconds(20))).Status.Should().Be("confirmed");
    }

    [Fact]
    public async Task ConfirmAsync_ShouldRestoreDatabaseCanonicalState_WhenLatestPlanStateIsMalformed()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        using var fixture = await BackendContractFixture.CreateAsync();
        using var current = fixture.EnterCurrent();
        await fixture.SeedRequirementMapAsync();
        await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync();
        var service = new PrototypeIterationPlanService(fixture.Store);
        var plan = await service.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement and HUD feedback.", "manual_feedback"));
        var project = await fixture.GetProjectAsync();
        File.WriteAllText(fixture.PathForTest("meta/routes/iteration-plan/latest.json"), "{", Encoding.UTF8);
        File.WriteAllText(Path.Combine(project.MetaPath, "routes", "iteration-plan", "latest.json"), "{", Encoding.UTF8);

        var result = await service.ConfirmAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanConfirmationRequest(plan.SessionId, plan.PlanHash));
        var diagnostics = await fixture.Store.ListProjectDiagnosticSpoolForAdminAsync(
            new ProjectDiagnosticSpoolQuery("unresolved", fixture.AccountId, fixture.ProjectId, "iteration-plan", "iteration_plan_state_invalid", "P1", 10));

        result.Status.Should().Be("confirmed");
        diagnostics.Should().BeEmpty();
        new PrototypeRouteStateWriter().ReadLatestIterationPlanState(project).Should().Contain(plan.PlanHash);
    }

    // ADR-0061: the final Python business verdict owns S2 database disposal.
    private sealed class BackendFixtureDatabase : IDisposable
    {
        private readonly string _root;
        private readonly bool _pythonOwned;
        private BackendFixtureDatabase(string root, bool pythonOwned)
        {
            _root = root;
            _pythonOwned = pythonOwned;
            ConnectionString = new SqliteConnectionStringBuilder
            {
                DataSource = Path.Combine(root, "metadata.sqlite3"), Pooling = false
            }.ToString();
        }
        internal string ConnectionString { get; }
        internal static BackendFixtureDatabase Create()
        {
            var root = S206TestSupport.CreateOwnedFixtureRoot("phase-a-backend-db-");
            Directory.CreateDirectory(root);
            return new BackendFixtureDatabase(root,
                !string.IsNullOrWhiteSpace(Environment.GetEnvironmentVariable("S206_OWNED_FIXTURE_ROOT")));
        }
        public void Dispose()
        {
            if (!_pythonOwned && Directory.Exists(_root)) Directory.Delete(_root, recursive: true);
        }
    }

    private sealed class BackendContractFixture : IDisposable
    {
        private readonly BackendFixtureDatabase _database;
        private readonly TempDirectory _workspaceRoot;
        private readonly TempDirectory _repoRoot;

        private BackendContractFixture(
            BackendFixtureDatabase database,
            TempDirectory workspaceRoot,
            TempDirectory repoRoot,
            PhaseAMetadataStore store,
            PhaseAPlatformOptions options,
            string accountId,
            string projectId,
            RequestContext context)
        {
            _database = database;
            _workspaceRoot = workspaceRoot;
            _repoRoot = repoRoot;
            Store = store;
            Queue = new HeavyRunnerQueueService(null, HeavyRunnerQueueService.DefaultMaxConcurrentOtherRuns, store);
            Options = options;
            AccountId = accountId;
            ProjectId = projectId;
            _context = context;
        }

        private readonly RequestContext _context;

        public IDisposable? EnterCurrent() => S206TestSupport.EnterCurrentContext(_context);

        public HeavyRunnerQueueService Queue { get; }

        public PhaseAMetadataStore Store { get; }

        public PhaseAPlatformOptions Options { get; }

        public string AccountId { get; }

        public string ProjectId { get; }

        public string ConnectionString => _database.ConnectionString;

        public string GddHash { get; private set; } = "";

        public string SceneRouteHash { get; private set; } = "scene-route-hash-v1";

        public static async Task<BackendContractFixture> CreateAsync()
        {
            var database = BackendFixtureDatabase.Create();
            var workspaceRoot = TempDirectory.Create("phase-a-backend-contract-workspaces");
            var repoRoot = TempDirectory.Create("phase-a-backend-contract-repo");
            var token = Guid.NewGuid().ToString("N");
            var credential = PhaseAAuth.HashTokenForStorage(token);
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
            {
                ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot.Path,
                ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspaceRoot.Path, "metadata.sqlite3"),
                ["PHASEA_REPOSITORY_ROOT"] = repoRoot.Path,
                ["PHASEA_SERVICE_STATE"] = "test",
                ["PHASEA_NODE_ID"] = "backend-contract-test-node",
                ["PHASEA_NODE_SCOPE"] = "single_node_test",
                ["PHASEA_NODE_TOPOLOGY"] = "single_service",
                ["PHASEA_ENABLED_ROLES"] = "entry,production",
                ["PHASEA_ACCEPT_NEW_ACCOUNTS"] = "true",
                ["PHASEA_ADMIN_TOKEN_HASH"] = credential
            });
            var guideRoot = Path.Combine(repoRoot.Path, "docs", "game-type-guides");
            Directory.CreateDirectory(guideRoot);
            File.WriteAllText(
                Path.Combine(guideRoot, "game-types.csv"),
                "id,name,description,genre_tags,fragment_file\nrpg,RPG,Role-playing game,rpg,rpg.md\n",
                Encoding.UTF8);
            File.WriteAllText(
                Path.Combine(guideRoot, "rpg.md"),
                "# RPG Guide\n\nThis stable guide paragraph defines an RPG field-map, encounter, reward, and return loop for source-boundary fingerprint tests.\n",
                Encoding.UTF8);
            await SqliteMetadataSchema.InitializeSingleNodeTestAsync(database.ConnectionString, options);
            var store = new PhaseAMetadataStore(database.ConnectionString, options);
            var account = await store.ResolveAccountByTokenHashAsync(credential)
                ?? throw new InvalidOperationException("Current fixture credential did not authenticate.");
            var accountId = account.AccountId;
            var context = RequestContext.FromIdentity(
                new AccountIdentity(accountId, account.Username, PhaseAAuth.AdminRole),
                accountId, credential, "backend-contract-fixture");
            using var current = S206TestSupport.EnterCurrentContext(context);
            var creation = new ProjectCreationService(
                store,
                options,
                new ProjectRuleCatalog(),
                new ProjectWorkspaceSeeder(options, store),
                gameTypeMatchService: new FixedGameTypeMatchService());
            var result = await creation.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Demo RPG", "RPG", null, null, null, null));
            if (!result.Succeeded || result.ProjectId is null)
                throw new InvalidOperationException("Backend fixture project creation failed: " + result.FailureCode);
            await store.SetProjectBootstrapStatusAsync(result.ProjectId!, "succeeded", null);
            var project = await store.GetProjectSnapshotAsync(result.ProjectId!);
            if (!OperatingSystem.IsWindows()) S206TestSupport.RegisterLogicalReadbackProject(project!);
            var hostedGuideRoot = Path.Combine(project!.RepoPath, "docs", "game-type-guides");
            Directory.CreateDirectory(hostedGuideRoot);
            File.Copy(Path.Combine(guideRoot, "game-types.csv"), Path.Combine(hostedGuideRoot, "game-types.csv"), overwrite: true);
            File.Copy(Path.Combine(guideRoot, "rpg.md"), Path.Combine(hostedGuideRoot, "rpg.md"), overwrite: true);
            return new BackendContractFixture(database, workspaceRoot, repoRoot, store, options, accountId, result.ProjectId!, context);
        }

        public async Task<ProjectSnapshot> GetProjectAsync()
        {
            return (await Store.GetProjectSnapshotAsync(ProjectId))!;
        }

        public async Task<string> CreateGddPromptRunAsync(string suffix)
        {
            var project = await GetProjectAsync();
            var runId = await Store.CreateRunAsync(ProjectId, project.WorkspaceId, "game-design-gdd");
            var promptRelativePath = $"logs/phase-a-gdd/test/{suffix}-gdd-prompt.md";
            var parsedRouteProfileJson = JsonSerializer.Serialize(PrototypeRouteSkillPolicy.ResolveProfile(project));
            var selectedRouteSkillPromptBlock = PrototypeRouteSkillPolicy.BuildPromptBlock(project);
            var recoveryAuthorityHashes = RecoveryAuthorityHashes(project);
            var prompt = $"""
                Parsed game-type route profile authority:
                {parsedRouteProfileJson}

                Selected route skill prompt block authority:
                {selectedRouteSkillPromptBlock}

                Generate the GDD from the confirmed scene route.
                """;
            WriteText(promptRelativePath, prompt);
            await Store.AddArtifactAsync(new ArtifactCreationCommand(
                runId,
                ProjectId,
                "game-design-gdd-prompt",
                promptRelativePath,
                "GDD prompt"));
            var fingerprints = new BmadGameTypeDesignCatalog(Options).Entries
                .Where(entry => !string.IsNullOrWhiteSpace(entry.GuideExcerpt))
                .SelectMany(entry => HostedRouteForbiddenSourceGuard.CreateContentFingerprints(
                    entry.FragmentRelativePath,
                    entry.GuideExcerpt))
                .GroupBy(item => item.ContentHash, StringComparer.Ordinal)
                .Select(group => group.First())
                .OrderBy(item => item.ContentHash, StringComparer.Ordinal)
                .ToArray();
            var scan = HostedRouteForbiddenSourceGuard.Scan(
                prompt,
                ["docs/game-type-guides/** raw excerpts", "unapproved raw game-type guide excerpt before contract freeze"],
                fingerprints,
                requireForbiddenContentFingerprints: true);
            var promptEvidenceRelativePath = $"logs/phase-a-gdd/test/{suffix}-gdd-prompt-source-evidence.json";
            WriteJson(promptEvidenceRelativePath, JsonSerializer.Serialize(new
            {
                schema_version = "gdd-prompt-source-evidence.v1",
                route = "gdd-document-generation",
                run_id = runId,
                recovery_source_order_ref = HostedRouteRecoveryContract.ContractId,
                recovery_source_order = HostedRouteRecoveryContract.SourceOrder,
                source_hashes = recoveryAuthorityHashes,
                prompt_manifest = new
                {
                    prompt_count = 1,
                    prompt_artifact_refs = new[] { promptRelativePath },
                    execution_prompt_hash = scan.PromptHash,
                    persisted_prompt_hash = HostedRouteForbiddenSourceGuard.PromptHash(prompt),
                    retention = "internal_recovery_only",
                    browser_readable = false,
                    redacted = true
                },
                allowed_source_references = Array.Empty<string>(),
                forbidden_source_scan = scan
            }));
            await Store.AddArtifactAsync(new ArtifactCreationCommand(
                runId,
                ProjectId,
                GameDesignDocumentService.PromptSourceEvidenceArtifactType,
                promptEvidenceRelativePath,
                "GDD prompt source evidence"));
            await Store.CompleteRunAsync(
                runId,
                "succeeded",
                0,
                "",
                "",
                JsonSerializer.Serialize(new
                {
                    run_type = "game-design-gdd",
                    generated_gdd_hash = Sha256(NormalizeText(File.ReadAllText(PathFor("docs/gdd/GDD.md"), Encoding.UTF8))),
                    recovery_source_order_ref = HostedRouteRecoveryContract.ContractId,
                    recovery_source_order = HostedRouteRecoveryContract.SourceOrder,
                    source_hashes = recoveryAuthorityHashes,
                    prompt_manifest = new
                    {
                        execution_prompt_hash = scan.PromptHash,
                        persisted_prompt_hash = HostedRouteForbiddenSourceGuard.PromptHash(prompt),
                        prompt_artifact_ref = promptRelativePath,
                        prompt_source_evidence_ref = promptEvidenceRelativePath,
                        redacted = true
                    }
                }));
            return runId;
        }

        public Dictionary<string, string> RecoveryAuthorityHashes(ProjectSnapshot project)
        {
            return new Dictionary<string, string>(StringComparer.Ordinal)
            {
                [HostedRouteRecoveryContract.ParsedRouteProfileHashKey] = HostedRouteForbiddenSourceGuard.PromptHash(
                    JsonSerializer.Serialize(PrototypeRouteSkillPolicy.ResolveProfile(project))),
                [HostedRouteRecoveryContract.SelectedRouteSkillPromptBlockHashKey] = HostedRouteForbiddenSourceGuard.PromptHash(
                    PrototypeRouteSkillPolicy.BuildPromptBlock(project))
            };
        }

        public void SeedConfirmedSceneRouteAndGdd(string? gddText = null)
        {
            var text = gddText ?? """
            # Demo RPG

            - Player must move on the field map and trigger one visible encounter.
            - HUD feedback must show HP, reward, and return-to-map state.
            """;
            WriteText("docs/gdd/GDD.md", text);
            GddHash = Sha256(NormalizeText(text));
            WriteSceneRoute("confirmed", "", GddHash, StructuredHash());
            WriteJson("meta/routes/gdd-document/latest.json", $$"""
            {
              "schema_version": "gdd-document-generation.v1",
              "route": "gdd-document-generation",
              "status": "ready",
              "generated_gdd_hash": "{{GddHash}}",
              "source_scene_route_hash": "{{SceneRouteHash}}"
            }
            """);
        }

        public GameDesignSceneRouteDocument DefaultSceneRoute()
        {
            return new GameDesignSceneRouteDocument(
                "gdd-scene-route.v1",
                "multi",
                "route_map",
                [
                    new GameDesignSceneRouteScene("route_map", "Route Map", "hub", true, "Choose the next node."),
                    new GameDesignSceneRouteScene("combat", "Combat", "combat", true, "Win the encounter.")
                ],
                [new GameDesignSceneRouteTransition("route_map", "combat", "Select encounter", "route_map", ["hp", "deck"])],
                new GameDesignSingleSceneConfirmation(false, "Multiple states are required."),
                []);
        }

        public void WriteGdd(string text)
        {
            WriteText("docs/gdd/GDD.md", text);
        }

        public string PathForTest(string relativePath)
        {
            return PathFor(relativePath);
        }

        public async Task SeedRequirementMapAsync(string? requirementMapJson = null)
        {
            SeedConfirmedSceneRouteAndGdd();
            var result = await new GameDesignRequirementMapService(Store, new FixedRequirementMapLlmEngine(requirementMapJson ?? """
            {
              "requirements": [
                { "requirement_id": "REQ-001", "normalized_requirement": "Player moves on the field map.", "priority": "P0", "kind": "scene", "mapped_scene_ids": ["field_map"], "mapped_required_module_ids": ["field_map"], "status": "mapped" },
                { "requirement_id": "REQ-002", "normalized_requirement": "HUD shows HP and reward feedback.", "priority": "P1", "kind": "ui", "mapped_scene_ids": ["field_map"], "mapped_required_module_ids": ["combat_hud"], "status": "mapped", "capability_domain_ids": ["ui_component_system", "ui_overlays_feedback"] }
              ]
            }
            """)).CreateAsync(AccountId, ProjectId, new GameDesignRequirementMapRequest());
            result.Status.Should().Be("ready");
        }

        public async Task SeedPrototypeSkeletonAsync(
            PrototypeContractStatusResult? contract = null,
            string? sourceContractHash = null,
            string? sourceContractSnapshotHash = null,
            IReadOnlyList<string>? verifiedRequirementIds = null)
        {
            contract ??= new PrototypeContractFreezeService(Store).EvaluateNewChainGuard(await GetProjectAsync()).ContractStatus;
            var project = await GetProjectAsync();
            WriteJson("meta/routes/prototype-skeleton/acceptance-evidence.json", "{}");
            var routeStateWriter = new PrototypeRouteStateWriter();
            routeStateWriter.WritePrototypeSkeletonState(project, new
            {
                schema_version = "prototype-skeleton-readback.v1",
                route = "prototype-skeleton",
                status_dimension = RouteStatusVocabulary.RouteReadback,
                status_allowed_values = RouteStatusVocabulary.Values(RouteStatusVocabulary.RouteReadback),
                status = "succeeded",
                source_boundary_enforced = true,
                recovery_source_order_ref = "hosted-route-recovery-order.v1",
                source_boundary = new
                {
                    recovery_source_order_ref = "hosted-route-recovery-order.v1",
                    recovery_source_order = HostedRouteRecoveryContract.SourceOrder,
                    authority_sources = new[]
                    {
                        "game-type-route-profile",
                        PrototypeRouteStateWriter.ProjectExecutionGuideRelativePath,
                        "routes/prototype-contract/latest.json",
                        "meta/routes/gdd-requirements/latest.json",
                        "meta/routes/prototype/latest.json"
                    },
                    source_hashes = new
                    {
                        source_gdd_hash = contract.SourceGddHash,
                        source_scene_route_hash = contract.SourceSceneRouteHash,
                        source_requirement_map_hash = contract.SourceRequirementMapHash,
                        source_contract_hash = sourceContractHash ?? contract.ContractHash,
                        source_contract_snapshot_hash = sourceContractSnapshotHash ?? contract.SourceContractSnapshotHash,
                        source_godot_ui_contract_hash = contract.SourceGodotUiContractHash,
                        source_ui_style_contract_hash = contract.SourceUiStyleContractHash,
                        ui_style_snapshot_hash = contract.UiStyleSnapshotHash
                    },
                    forbidden_source_patterns = new[]
                    {
                        "docs/game-type-guides/** raw excerpts",
                        "assistant summary as acceptance authority"
                    }
                },
                freshness = "fresh",
                source_gdd_hash = contract.SourceGddHash,
                source_scene_route_hash = contract.SourceSceneRouteHash,
                source_requirement_map_hash = contract.SourceRequirementMapHash,
                source_contract_hash = sourceContractHash ?? contract.ContractHash,
                source_contract_snapshot_hash = sourceContractSnapshotHash ?? contract.SourceContractSnapshotHash,
                source_godot_ui_contract_hash = contract.SourceGodotUiContractHash,
                source_ui_style_contract_hash = contract.SourceUiStyleContractHash,
                ui_style_snapshot_hash = contract.UiStyleSnapshotHash,
                verified_scene_ids = new[] { "field_map" },
                verified_requirement_ids = verifiedRequirementIds ?? ["REQ-001", "REQ-002"],
                evidence_refs = new[] { new { kind = "sidecar", path = "meta/routes/prototype-skeleton/acceptance-evidence.json" } },
                updated_utc = DateTimeOffset.UtcNow.ToString("O")
            });
        }

        public async Task ApplyPrototypeSkeletonBoundaryScenarioAsync(string scenario)
        {
            var project = await GetProjectAsync();
            var copies = new PrototypeRouteStateWriter().ReadPrototypeSkeletonStateCopies(project);
            var root = JsonNode.Parse(copies.MetadataState)!.AsObject();
            var boundary = root["source_boundary"]!.AsObject();
            switch (scenario)
            {
                case "missing_boundary":
                    root.Remove("source_boundary");
                    break;
                case "invalid_top_level_recovery_order":
                    root["recovery_source_order_ref"] = "legacy-order.v0";
                    break;
                case "invalid_nested_recovery_order":
                    boundary["recovery_source_order_ref"] = "legacy-order.v0";
                    break;
                case "missing_authority_source":
                    boundary["authority_sources"]!.AsArray().RemoveAt(0);
                    break;
                case "reordered_authority_sources":
                    var sources = boundary["authority_sources"]!.AsArray();
                    var first = sources[0]!.DeepClone();
                    sources[0] = sources[1]!.DeepClone();
                    sources[1] = first;
                    break;
                case "nested_hash_mismatch":
                    boundary["source_hashes"]!["source_contract_hash"] = "stale-contract-hash";
                    break;
                case "mixed_evidence_refs":
                    root["evidence_refs"] = new JsonArray
                    {
                        new JsonObject { ["kind"] = "sidecar", ["path"] = "meta/routes/prototype/latest.json" },
                        new JsonObject { ["kind"] = "sidecar", ["path"] = "../outside.json" }
                    };
                    break;
                default:
                    throw new ArgumentOutOfRangeException(nameof(scenario), scenario, "Unknown skeleton boundary scenario.");
            }

            new PrototypeRouteStateWriter().WritePrototypeSkeletonState(project, root);
        }

        public void ApplyRequirementMapScenario(string scenario)
        {
            switch (scenario)
            {
                case "missing_gdd":
                    Delete("docs/gdd/GDD.md");
                    break;
                case "missing_scene":
                    Delete("meta/routes/scene-route/latest.json");
                    break;
                case "unconfirmed_scene":
                    WriteSceneRoute("draft", SceneRouteHash, GddHash, StructuredHash());
                    break;
                case "stale_scene":
                    WriteSceneRoute("stale", SceneRouteHash, GddHash, StructuredHash());
                    break;
                case "game_type_hash_mismatch":
                    WriteSceneRoute("confirmed", SceneRouteHash, GddHash, "old-game-type-hash");
                    break;
                case "gdd_hash_mismatch":
                    WriteSceneRoute("confirmed", SceneRouteHash, "old-gdd-hash", StructuredHash());
                    break;
            }
        }

        public void ApplyContractScenario(string scenario)
        {
            switch (scenario)
            {
                case "stale_scene":
                    WriteSceneRoute("stale", SceneRouteHash, GddHash, StructuredHash());
                    break;
                case "game_type_hash_mismatch":
                    WriteSceneRoute("confirmed", SceneRouteHash, GddHash, "old-game-type-hash");
                    break;
                case "game_type_hash_missing":
                    WriteSceneRoute("confirmed", SceneRouteHash, GddHash, "");
                    break;
                case "gdd_hash_mismatch":
                    WriteSceneRoute("confirmed", SceneRouteHash, "old-gdd-hash", StructuredHash());
                    break;
                case "requirement_map_scene_hash_mismatch":
                    PatchRequirementMapSourceSceneHash("other-scene-hash");
                    break;
            }
        }

        public JsonDocument ReadJson(string relativePath)
        {
            return JsonDocument.Parse(File.ReadAllText(PathFor(relativePath), Encoding.UTF8));
        }

        public void WriteJson(string relativePath, string json)
        {
            WriteText(relativePath, json);
        }

        private void WriteSceneRoute(string status, string sceneHash, string gddHash, string structuredHash)
        {
            var project = GetProjectAsync().GetAwaiter().GetResult();
            var node = JsonSerializer.SerializeToNode(new
            {
                schema_version = "scene-route.v1",
                route = "scene-route-confirmation",
                status,
                source_game_type_structured_hash = structuredHash,
                source_gdd_form_hash = "gdd-form-hash-v1",
                source_generated_gdd_hash = gddHash,
                source_contract_snapshot_hash = GddToModuleAuthorityHashes.ComputeContractSnapshotHash(project.GameTypeMatchJson),
                confirmed_scene_route_hash = sceneHash,
                scene_count_intent = "single",
                entry_scene = "field_map",
                scenes = new[]
                {
                    new { scene_id = "field_map", scene_name = "Field Map", role = "hub", m1_required = true, player_goal = "Move and encounter." }
                },
                transitions = Array.Empty<object>(),
                single_scene_confirmation = new { allowed = true, reason = "fixture" },
                notes = Array.Empty<string>()
            })!.AsObject();
            using var document = JsonDocument.Parse(node.ToJsonString());
            SceneRouteHash = GddToModuleAuthorityHashes.ComputeSceneRouteHash(document.RootElement);
            node["confirmed_scene_route_hash"] = SceneRouteHash;
            WriteJson("meta/routes/scene-route/latest.json", node.ToJsonString());
        }

        private void PatchRequirementMapSourceSceneHash(string value)
        {
            using var document = ReadJson("meta/routes/gdd-requirements/latest.json");
            var node = JsonSerializer.Deserialize<Dictionary<string, object?>>(document.RootElement.GetRawText())!;
            node["source_scene_route_hash"] = value;
            WriteJson("meta/routes/gdd-requirements/latest.json", JsonSerializer.Serialize(node, new JsonSerializerOptions(JsonSerializerDefaults.Web)
            {
                WriteIndented = true
            }));
        }

        private string StructuredHash()
        {
            return GddToModuleAuthorityHashes.ComputeStructuredGameTypeHash(
                GetProjectAsync().GetAwaiter().GetResult().GameTypeMatchJson);
        }

        public void WriteText(string relativePath, string text)
        {
            var path = PathFor(relativePath);
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            File.WriteAllText(path, NormalizeText(text), Encoding.UTF8);
        }

        private void Delete(string relativePath)
        {
            var path = PathFor(relativePath);
            if (File.Exists(path))
            {
                File.Delete(path);
            }
        }

        private string PathFor(string relativePath)
        {
            var project = GetProjectAsync().GetAwaiter().GetResult();
            return Path.Combine(project.RepoPath, relativePath.Replace('/', Path.DirectorySeparatorChar));
        }

        public void Dispose()
        {
            _database.Dispose();
            _workspaceRoot.Dispose();
            _repoRoot.Dispose();
        }
    }

    private sealed class CountingHostedProcessRunner : IHostedProcessRunner
    {
        public int CallCount { get; private set; }

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            CallCount++;
            throw new InvalidOperationException("Runner must not be called before capability preflight passes.");
        }
    }

    private sealed class BlockingHostedProcessRunner : IHostedProcessRunner
    {
        public TaskCompletionSource Started { get; } = new(TaskCreationOptions.RunContinuationsAsynchronously);

        public TaskCompletionSource Release { get; } = new(TaskCreationOptions.RunContinuationsAsynchronously);

        public async Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Started.TrySetResult();
            await Release.Task.WaitAsync(cancellationToken);
            throw new InvalidOperationException("forced runner completion for mutation lease test");
        }
    }

    private sealed class FixedGameTypeMatchService : IProjectGameTypeMatchService
    {
        public Task<ProjectGameTypeMatchEvidence> ResolveAsync(string gameTypeSource, CancellationToken cancellationToken)
        {
            var now = DateTimeOffset.UtcNow.ToString("O");
            return Task.FromResult(new ProjectGameTypeMatchEvidence(
                1,
                "matched",
                "matched_by_test",
                "test",
                gameTypeSource,
                "",
                "",
                ["RPG"],
                [],
                ["RPG"],
                ["rpg"],
                "rpg",
                "docs/game-type-guides/rpg.md",
                100,
                [],
                "",
                "test-catalog",
                now,
                now));
        }
    }

    private sealed class FixedRequirementMapLlmEngine : ILlmRouteEngine
    {
        private readonly string _json;

        public FixedRequirementMapLlmEngine(string json)
        {
            _json = json;
        }

        public List<LlmRouteRequest> Requests { get; } = [];

        public Task<LlmRouteResult> CompleteAsync(LlmRouteRequest request, CancellationToken cancellationToken = default)
        {
            Requests.Add(request);
            var valid = _json.TrimStart().StartsWith('{') && !_json.Contains("{ invalid", StringComparison.Ordinal);
            return Task.FromResult(new LlmRouteResult(
                valid,
                _json,
                valid ? _json : null,
                request.Model,
                valid ? null : "llm_json_parse_failed",
                valid ? null : "invalid_json",
                valid ? 0 : 1,
                "",
                "",
                null,
                1,
                request.Prompt.Length,
                Encoding.UTF8.GetByteCount(request.Prompt),
                1));
        }
    }

    private sealed class CountingLlmRouteEngine : ILlmRouteEngine
    {
        public List<LlmRouteRequest> Requests { get; } = [];

        public Task<LlmRouteResult> CompleteAsync(LlmRouteRequest request, CancellationToken cancellationToken = default)
        {
            Requests.Add(request);
            throw new InvalidOperationException("The planning LLM must not run before the skeleton authority gate passes.");
        }
    }

    private sealed class BlockingRequirementMapLlmEngine : ILlmRouteEngine
    {
        private readonly string _json;
        private readonly TaskCompletionSource _started = new(TaskCreationOptions.RunContinuationsAsynchronously);
        private readonly TaskCompletionSource _release = new(TaskCreationOptions.RunContinuationsAsynchronously);
        private int _callCount;

        public BlockingRequirementMapLlmEngine(string json)
        {
            _json = json;
        }

        public Task Started => _started.Task;

        public LlmRouteRequest? Request { get; private set; }

        public int CallCount => Volatile.Read(ref _callCount);

        public void Release() => _release.TrySetResult();

        public async Task<LlmRouteResult> CompleteAsync(LlmRouteRequest request, CancellationToken cancellationToken = default)
        {
            Request = request;
            Interlocked.Increment(ref _callCount);
            _started.TrySetResult();
            await _release.Task.WaitAsync(cancellationToken);
            return new LlmRouteResult(true, _json, _json, request.Model, null, null, 0, "", "", null, 1, request.Prompt.Length, Encoding.UTF8.GetByteCount(request.Prompt), 1);
        }
    }

    private sealed class TempDirectory : IDisposable
    {
        private readonly bool _pythonOwned;
        private TempDirectory(string path)
        {
            Path = path;
            _pythonOwned = !string.IsNullOrWhiteSpace(Environment.GetEnvironmentVariable("S206_OWNED_FIXTURE_ROOT"));
        }

        public string Path { get; }

        public static TempDirectory Create(string prefix)
        {
            var path = S206TestSupport.CreateOwnedFixtureRoot(prefix + "-");
            Directory.CreateDirectory(path);
            return new TempDirectory(path);
        }

        public void Dispose()
        {
            if (!_pythonOwned && Directory.Exists(Path))
            {
                Directory.Delete(Path, recursive: true);
            }
        }
    }

    private static string Sha256(string value)
    {
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(value))).ToLowerInvariant();
    }

    private static string NormalizeText(string text)
    {
        return text.Replace("\r\n", "\n").Trim();
    }
}
