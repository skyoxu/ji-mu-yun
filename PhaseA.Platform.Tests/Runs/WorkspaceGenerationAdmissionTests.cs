using System.Text.Json;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Readback;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Security;
using PhaseA.Platform.Tests.Data;
using PhaseA.Platform.Workspaces;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

// ADR-0035/0038/0061: exercise durable generation activation and actual consumers.
// OS publication/ACL coverage remains in PackageVersionRecoveryTests.
public sealed class WorkspaceGenerationAdmissionTests
{
    [Fact]
    public async Task ValidationRejectsThePreflightGenerationWhenActivationCompletesBeforeItsLock()
    {
        await using var scope = await Scope.CreateAsync();
        var prototype = await scope.Store.CreateRunAsync(scope.Project.ProjectId, scope.Project.WorkspaceId, "prototype-7day-playable");
        await scope.Store.CompleteRunAsync(prototype, "succeeded", 0, "", "",
            JsonSerializer.Serialize(new { prototype_record = "docs/prototypes/2026-10-08-demo.md" }));
        var session = await scope.Store.CreateProjectIterationSessionAsync(scope.Project.AccountId, scope.Project.ProjectId,
            "manual_feedback", "Test goal", "Test goal", [new ProjectIterationGoalCreateCommand(1, "Done", "Done", "Done")]);
        var details = await scope.Store.GetLatestProjectIterationSessionAsync(scope.Project.ProjectId);
        await scope.Store.UpdateProjectIterationGoalStatusAsync(details!.Goals.Single().GoalId, "succeeded", "Done", DateTimeOffset.UtcNow.ToString("O"));
        var runner = new RecordingRunner();
        var service = new PrototypeWorkflowService(scope.Store, scope.Options, runner,
            new PrototypeRecordWriter(scope.Options), new PrototypeWorkflowCommandBuilder(scope.Options),
            new PrototypeArtifactIndexer(), new LlmBindingService(scope.Store, scope.Options),
            new LlmStopLossService(scope.Store, scope.Options),
            new CallbackSeeder(scope.ActivateAsync), new GameTypeTemplateCatalog(scope.Options));

        var result = await service.ValidateAsync(scope.Project.AccountId, scope.Project.ProjectId);

        Assert.Equal("project_busy", result.Status);
        Assert.Equal(423, result.ExitCode);
        Assert.Equal(0, runner.Commands);
        Assert.Equal("blocked", (await scope.Store.GetRunSnapshotAsync(result.RunId))!.Status);
        Assert.False(await scope.Store.HasRunnerLockAsync(scope.Project.ProjectId));
        Assert.True(await scope.Store.RequiresRestoreValidationAsync(scope.Project.AccountId, scope.Project.ProjectId));
        Assert.NotEqual(scope.Project.RepoPath, (await scope.Store.GetProjectSnapshotAsync(scope.Project.ProjectId))!.RepoPath);
    }

    [Fact]
    public async Task LockedAdmissionRejectsAnInactiveSnapshotAndAcceptsOnlyTheCurrentOwner()
    {
        await using var scope = await Scope.CreateAsync();
        await scope.ActivateAsync();
        var current = (await scope.Store.GetProjectSnapshotAsync(scope.Project.ProjectId))!;
        var runId = await scope.Store.CreateRunAsync(current.ProjectId, current.WorkspaceId, "project-package");
        Assert.True(await scope.Store.TryAcquireRunnerLockAsync(current.ProjectId, runId));
        Assert.False(await scope.Store.IsCurrentWorkspaceGenerationAsync(scope.Project, runId));
        Assert.True(await scope.Store.IsCurrentWorkspaceGenerationAsync(current, runId));
        Assert.False(await scope.Store.IsCurrentWorkspaceGenerationAsync(current, "another-run"));
        Assert.False(await scope.Store.IsCurrentWorkspaceGenerationAsync(current with { RuntimePath = scope.Project.RuntimePath }, runId));
        Assert.NotEqual(WorkspaceGenerationPaths.SourceGenerationId(scope.Project), WorkspaceGenerationPaths.SourceGenerationId(current));
        await scope.Store.CompleteRunAsync(runId, "blocked", 423, "", "Fixture ended.", "{}");
    }

    [Theory]
    [InlineData("unbound")]
    [InlineData("old-generation")]
    [InlineData("invalid-generation-type")]
    [InlineData("skeleton-only")]
    public async Task ANewerReceiptCannotReleaseRestoreReadinessUnlessItValidatesTheActiveGeneration(string fault)
    {
        await using var scope = await Scope.CreateAsync();
        await scope.ActivateAsync();
        var current = (await scope.Store.GetProjectSnapshotAsync(scope.Project.ProjectId))!;
        await scope.ValidationAsync(current, "succeeded", Scope.Evidence(current));
        Assert.False(await scope.Store.RequiresRestoreValidationAsync(current.AccountId, current.ProjectId));
        var evidence = fault switch
        {
            "unbound" => "{\"validation_only\":true}",
            "old-generation" => Scope.Evidence(scope.Project),
            "invalid-generation-type" => "{\"validation_only\":true,\"workspace_generation_id\":42}",
            _ => JsonSerializer.Serialize(new { validation_only = true, skeleton_validation_only = true,
                workspace_generation_id = WorkspaceGenerationPaths.SourceGenerationId(current) })
        };
        await scope.ValidationAsync(current, "succeeded", evidence);
        // Skeleton-only acceptance never supersedes a current final acceptance.
        var expected = fault != "skeleton-only";
        Assert.Equal(expected, await scope.Store.RequiresRestoreValidationAsync(current.AccountId, current.ProjectId));
        var restarted = new PhaseAMetadataStore(scope.Database.ConnectionString, scope.Options);
        Assert.Equal(expected, await restarted.RequiresRestoreValidationAsync(current.AccountId, current.ProjectId));
        if (expected)
            Assert.Equal("restore_revalidation_required", (await new ProjectPackageService(restarted, scope.Options)
                .CreatePackageAsync(current.AccountId, current.ProjectId)).FailureCode);
        await scope.ValidationAsync(current, "succeeded", Scope.Evidence(current));
        Assert.False(await scope.Store.RequiresRestoreValidationAsync(current.AccountId, current.ProjectId));
        await scope.ValidationAsync(current, "failed", Scope.Evidence(current));
        Assert.True(await scope.Store.RequiresRestoreValidationAsync(current.AccountId, current.ProjectId));
    }

    private sealed class CallbackSeeder(Func<Task> activate) : IProjectWorkspaceSeeder
    {
        public void EnsureSeeded(string repo) => Task.Run(activate).GetAwaiter().GetResult();
    }

    private sealed class RecordingRunner : IHostedProcessRunner
    {
        public int Commands { get; private set; }
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken)
        {
            Commands++;
            return Task.FromResult(new HostedProcessResult(0, "", ""));
        }
    }

    private sealed class Scope : IAsyncDisposable
    {
        public TempSqliteDatabase Database = null!;
        public PhaseAMetadataStore Store = null!;
        public PhaseAPlatformOptions Options = null!;
        public ProjectSnapshot Project = null!;
        private string _root = "";
        private string _credential = "";

        public static async Task<Scope> CreateAsync()
        {
            var scope = new Scope { Database = TempSqliteDatabase.Create(),
                _root = Path.Combine(Path.GetTempPath(), "phase-generation-" + Guid.NewGuid().ToString("N")) };
            scope.Options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
                { ["HOSTED_WORKSPACE_ROOT"] = scope._root, ["PHASEA_REPOSITORY_ROOT"] = AppContext.BaseDirectory });
            await SqliteMetadataSchema.InitializeAsync(scope.Database.ConnectionString);
            scope.Store = new PhaseAMetadataStore(scope.Database.ConnectionString, scope.Options);
            var owner = await scope.Store.CreateUserAccountAsync("generation-" + Guid.NewGuid().ToString("N"), 2);
            scope._credential = PhaseAAuth.HashTokenForStorage(owner.Token);
            var id = Guid.NewGuid().ToString("N");
            var layout = WorkspaceLayoutBuilder.Build(scope._root, owner.AccountId, id);
            var created = await scope.Store.CreateProjectAsync(new(id, owner.AccountId, "Generation", "Generation", "default",
                "default", false, [], layout.RootPath, layout.RepoPath, layout.RuntimePath, layout.MetaPath));
            Assert.True(created.Succeeded);
            await scope.Store.SetProjectBootstrapStatusAsync(id, "succeeded", null);
            scope.Project = (await scope.Store.GetProjectSnapshotAsync(id))!;
            Directory.CreateDirectory(layout.RepoPath);
            var skill = PrototypeRouteSkillPolicy.Resolve(scope.Project);
            Write(layout.RepoPath, skill.SkillRelativePath, "Fixture route skill.");
            if (skill.ContractRelativePath is not null) Write(layout.RepoPath, skill.ContractRelativePath, "Fixture contract.");
            Write(layout.RepoPath, "docs/prototypes/2026-10-08-demo.md", "| slug | demo | fixture |\n");
            return scope;
        }

        public async Task ActivateAsync()
        {
            var project = (await Store.GetProjectSnapshotAsync(Project.ProjectId))!;
            var run = await Store.CreateRunAsync(project.ProjectId, project.WorkspaceId, "project-package-restore");
            Assert.True(await Store.TryAcquireRunnerLockAsync(project.ProjectId, run));
            Assert.True(await Store.TryMarkRunStartedAsync(run, 0));
            var generation = Path.Combine(project.WorkspaceRootPath, ".restore-generations", Guid.NewGuid().ToString("N"));
            foreach (var path in new[] { "repo", "runtime", "meta" }) Directory.CreateDirectory(Path.Combine(generation, path));
            await Store.ActivateWorkspaceGenerationAsync(project, run, "fixture-snapshot", "fixture-attempt", generation, _credential);
        }

        public async Task ValidationAsync(ProjectSnapshot project, string status, string evidence)
        {
            var run = await Store.CreateRunAsync(project.ProjectId, project.WorkspaceId, "prototype-7day-playable");
            await Store.CompleteRunAsync(run, status, status == "succeeded" ? 0 : 1, "", "", evidence);
        }

        public static string Evidence(ProjectSnapshot project) => JsonSerializer.Serialize(new
            { validation_only = true, workspace_generation_id = WorkspaceGenerationPaths.SourceGenerationId(project) });

        private static void Write(string root, string path, string content)
        {
            var target = Path.Combine(root, path.Replace('/', Path.DirectorySeparatorChar));
            Directory.CreateDirectory(Path.GetDirectoryName(target)!);
            File.WriteAllText(target, content);
        }

        public async ValueTask DisposeAsync()
        {
            await Database.DisposeAsync();
            if (Directory.Exists(_root)) Directory.Delete(_root, true);
        }
    }
}
