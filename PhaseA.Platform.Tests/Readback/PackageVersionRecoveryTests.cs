using PhaseA.Platform.Tests.NodeIdentity;
using System.IO.Compression;
using System.Text;
using System.Text.Json;
using Microsoft.Extensions.Logging.Abstractions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Readback;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Security;
using PhaseA.Platform.Tests.Data;
using PhaseA.Platform.Workspaces;
using Xunit;

namespace PhaseA.Platform.Tests.Readback;

[Collection("PhaseA snapshot environment")]
public sealed class PackageVersionRecoveryTests
{
    // ADR-0035/0038/0061: real Windows registration, immutable version bytes,
    // durable readback, activation and a second restoration after restart.
    [Fact]
    public async Task SelectedVersionBecomesActive_AndHistoricalDownloadsSurviveRestart()
    {
        using var scope = await Scope.CreateAsync();
        using var current = S206TestSupport.EnterCurrentContext(scope.Context);
        var first = await scope.Packages.CreatePackageAsync(scope.Owner.AccountId, scope.Project.ProjectId, requestContext: scope.Context);
        Assert.Equal("succeeded", first.Status);
        Assert.NotNull(first.SnapshotId);
        var zip = await scope.Packages.ReadPackageAsync(scope.Owner.AccountId, scope.Project.ProjectId, first.FileName);
        using (var archive = new ZipArchive(new MemoryStream(zip!.Content)))
        using (var reader = new StreamReader(archive.GetEntry("Game.Core/Version.cs")!.Open()))
            Assert.Equal("version-one", await reader.ReadToEndAsync());
        File.WriteAllText(scope.Source, "version-two");
        var second = await scope.Packages.CreatePackageAsync(scope.Owner.AccountId, scope.Project.ProjectId, requestContext: scope.Context);
        Assert.Equal("succeeded", second.Status);
        await using (var occupied = await scope.Queue.EnterAsync("occupied", scope.Owner.AccountId, scope.BlockingProjectId, "test"))
        {
            var firstRequest = await scope.Restorer.AdmitAsync(scope.Context, scope.Project.ProjectId, first.FileName, "restore-one");
            var duplicate = await scope.Restorer.AdmitAsync(scope.Context, scope.Project.ProjectId, first.FileName, "restore-one");
            Assert.Equal(firstRequest.OperationId, duplicate.OperationId);
            scope.PendingRun = firstRequest.OperationId;
            Assert.Equal("queued", (await scope.Store.GetRunSnapshotAsync(scope.PendingRun!))!.Status);
            Assert.Equal(scope.Project.RepoPath, (await scope.Store.GetProjectSnapshotAsync(scope.Project.ProjectId))!.RepoPath);
        }
        Assert.Equal("succeeded", (await scope.WaitAsync(scope.PendingRun!)).Status);
        var active = (await scope.Store.GetProjectSnapshotAsync(scope.Project.ProjectId))!;
        Assert.NotEqual(scope.Project.RepoPath, active.RepoPath);
        Assert.Equal("version-one", File.ReadAllText(Path.Combine(active.RepoPath, "Game.Core", "Version.cs")));
        Assert.Equal(active.WorkspaceRootPath, Path.GetDirectoryName(active.RepoPath));
        Assert.True(await scope.Store.RequiresRestoreValidationAsync(scope.Owner.AccountId, active.ProjectId));
        Assert.True(RunnerIsolationPolicy.HasExpectedRestoreTreeSecurity(scope.Descriptor, active.RepoPath));
        Assert.NotNull(await scope.Packages.ReadPackageAsync(scope.Owner.AccountId, active.ProjectId, second.FileName));
        Assert.Equal("restore_revalidation_required",
            (await scope.Packages.CreatePackageAsync(scope.Owner.AccountId, active.ProjectId, requestContext: scope.Context)).FailureCode);
        var revalidation = await scope.Store.CreateRunAsync(active.ProjectId, active.WorkspaceId, "prototype-7day-playable");
        await scope.Store.CompleteRunAsync(revalidation, "succeeded", 0, "", "", ValidationEvidence(active));
        var repackaged = await scope.Packages.CreatePackageAsync(scope.Owner.AccountId, active.ProjectId, requestContext: scope.Context);
        Assert.Equal("succeeded", repackaged.Status);
        var activeZip = await scope.Packages.ReadPackageAsync(scope.Owner.AccountId, active.ProjectId, repackaged.FileName);
        using (var archive = new ZipArchive(new MemoryStream(activeZip!.Content)))
        using (var reader = new StreamReader(archive.GetEntry("Game.Core/Version.cs")!.Open()))
            Assert.Equal("version-one", await reader.ReadToEndAsync());
        scope.Storage.SoftDeleteSnapshot(scope.Context, first.SnapshotId!);
        Assert.Equal(scope.PendingRun, (await scope.Restorer.AdmitAsync(scope.Context,
            active.ProjectId, first.FileName, "restore-one")).OperationId);
        // Reload the persisted snapshot catalog and active metadata as a fresh consumer.
        var storage = scope.Store.CreateWorkspaceStorageService();
        var packages = new ProjectPackageService(scope.Store, scope.Options, scope.Queue, processRunner: new HostedProcessRunner(authority: scope.Store), storage: storage);
        var restore = scope.NewRestorer(packages, storage);
        var request = await restore.AdmitAsync(scope.Context, active.ProjectId, second.FileName, "restore-two");
        Assert.Equal("succeeded", (await scope.WaitAsync(request.OperationId!)).Status);
        var latest = (await scope.Store.GetProjectSnapshotAsync(active.ProjectId))!;
        Assert.Equal("version-two", File.ReadAllText(Path.Combine(latest.RepoPath, "Game.Core", "Version.cs")));
        Assert.NotEqual(active.RepoPath, latest.RepoPath);
        Assert.NotNull(await packages.ReadPackageAsync(scope.Owner.AccountId, latest.ProjectId, first.FileName));
        await SqliteMetadataSchema.InitializeSingleNodeTestAsync(scope.Database.ConnectionString,scope.Options);
        Assert.Equal(latest.RepoPath, (await scope.Store.GetProjectSnapshotAsync(latest.ProjectId))!.RepoPath);
        Assert.False(await scope.Store.HasRunnerLockAsync(latest.ProjectId));
        var validation = await scope.Store.CreateRunAsync(latest.ProjectId, latest.WorkspaceId, "prototype-7day-playable");
        await scope.Store.CompleteRunAsync(validation, "succeeded", 0, "", "", ValidationEvidence(latest));
        Assert.False(await scope.Store.RequiresRestoreValidationAsync(scope.Owner.AccountId, latest.ProjectId));
        var failedValidation = await scope.Store.CreateRunAsync(latest.ProjectId, latest.WorkspaceId, "prototype-7day-playable");
        await scope.Store.CompleteRunAsync(failedValidation, "failed", 1, "", "", ValidationEvidence(latest));
        Assert.True(await scope.Store.RequiresRestoreValidationAsync(scope.Owner.AccountId, latest.ProjectId));
    }

    [Theory]
    [InlineData("package-corruption")]
    [InlineData("snapshot-corruption")]
    [InlineData("credential-revoked")]
    public async Task FailedRestoreKeepsCurrentFiles_AndReleasesTheProject(string fault)
    {
        using var scope = await Scope.CreateAsync();
        using var current = S206TestSupport.EnterCurrentContext(scope.Context);
        var package = await scope.Packages.CreatePackageAsync(scope.Owner.AccountId, scope.Project.ProjectId, requestContext: scope.Context);
        Assert.Equal("succeeded", package.Status);
        File.WriteAllText(scope.Source, "current-work");
        ProjectPackageRestoreAdmission request;
        await using (var occupied = await scope.Queue.EnterAsync("occupied", scope.Owner.AccountId, scope.BlockingProjectId, "test"))
        {
            request = await scope.Restorer.AdmitAsync(scope.Context, scope.Project.ProjectId, package.FileName, "failed-restore");
            Assert.NotNull(request.OperationId);
            if (fault == "package-corruption") File.AppendAllText(Path.Combine(scope.Project.RepoPath, package.RelativePath), "changed");
            if (fault == "snapshot-corruption")
                scope.Storage.ListSnapshots(scope.Owner.AccountId, scope.Project.ProjectId).Single().Manifest.ProtectedContent![30] ^= 1;
            if (fault == "credential-revoked") await scope.Store.RotateUserTokenAsync(scope.Owner.AccountId);
        }
        Assert.Equal("failed", (await scope.WaitAsync(request.OperationId!)).Status);
        Assert.Equal(scope.Project.RepoPath, (await scope.Store.GetProjectSnapshotAsync(scope.Project.ProjectId))!.RepoPath);
        Assert.Equal("current-work", File.ReadAllText(scope.Source));
        Assert.False(await scope.Store.HasRunnerLockAsync(scope.Project.ProjectId));
        Assert.Null(await scope.Store.GetLastWorkspaceActivationUtcAsync(scope.Owner.AccountId, scope.Project.ProjectId));
    }

    [Fact]
    public async Task OtherAccountAndMissingSnapshotCannotAdmitRestoration()
    {
        using var scope = await Scope.CreateAsync();
        using var current = S206TestSupport.EnterCurrentContext(scope.Context);
        var package = await scope.Packages.CreatePackageAsync(scope.Owner.AccountId, scope.Project.ProjectId, requestContext: scope.Context);
        var other = await scope.Store.CreateUserAccountAsync("other-" + Guid.NewGuid().ToString("N"), 2);
        var context = new RequestContext(other.Username, other.AccountId, new HashSet<string> { "user" },
            PhaseAAuth.HashTokenForStorage(other.Token), "other-request");
        Assert.Equal("project_not_found", (await scope.Restorer.AdmitAsync(context, scope.Project.ProjectId, package.FileName, "other")).FailureCode);
        scope.Storage.SoftDeleteSnapshot(scope.Context, package.SnapshotId!);
        Assert.Equal("package_snapshot_unavailable", (await scope.Restorer.AdmitAsync(scope.Context, scope.Project.ProjectId, package.FileName, "expired")).FailureCode);
        Assert.False((await scope.Packages.ListPackagesAsync(scope.Owner.AccountId, scope.Project.ProjectId))!.Packages.Single().CanRestore);
    }

    [Fact]
    public async Task SnapshotFailureCannotPublishAPackageWithoutRecovery()
    {
        using var scope = await Scope.CreateAsync();
        using var current = S206TestSupport.EnterCurrentContext(scope.Context);
        new CentralWorkspaceStorageBackend(scope.Database.ConnectionString).SetQuota(scope.Owner.AccountId, 0);
        Assert.Equal("failed", (await scope.Packages.CreatePackageAsync(scope.Owner.AccountId, scope.Project.ProjectId, requestContext: scope.Context)).Status);
        Assert.Empty((await scope.Packages.ListPackagesAsync(scope.Owner.AccountId, scope.Project.ProjectId))!.Packages);
        Assert.Empty(scope.Storage.ListSnapshots(scope.Owner.AccountId, scope.Project.ProjectId));
        Assert.False(await scope.Store.HasRunnerLockAsync(scope.Project.ProjectId));
    }

    private static string ValidationEvidence(ProjectSnapshot project) => JsonSerializer.Serialize(new
        { validation_only = true, workspace_generation_id = WorkspaceGenerationPaths.SourceGenerationId(project) });

    private sealed class Scope : IDisposable
    {
        public TempSqliteDatabase Database = null!;
        public PhaseAPlatformOptions Options = null!;
        public PhaseAMetadataStore Store = null!;
        public AdminCreateUserResult Owner = null!;
        public ProjectSnapshot Project = null!;
        public RunnerIsolationDescriptor Descriptor = null!;
        public WorkspaceStorageService Storage = null!;
        public ProjectPackageService Packages = null!;
        public ProjectPackageRestoreService Restorer = null!;
        public HeavyRunnerQueueService Queue = null!;
        public RequestContext Context = null!;
        public string BlockingProjectId = "";
        public string Root = "";
        public string? PendingRun;
        private string? _previousKeys;
        public string Source => Path.Combine(Project.RepoPath, "Game.Core", "Version.cs");
        public static async Task<Scope> CreateAsync()
        {
            Assert.True(OperatingSystem.IsWindows(), "Recovery activation requires native Windows ACL evidence.");
            var scope = new Scope { Database = TempSqliteDatabase.Create(), Root = Path.Combine(Path.GetTempPath(), "phase-version-" + Guid.NewGuid().ToString("N")) };
            scope._previousKeys = Environment.GetEnvironmentVariable("PHASEA_SNAPSHOT_KEY_ROOT");
            Environment.SetEnvironmentVariable("PHASEA_SNAPSHOT_KEY_ROOT", Path.Combine(scope.Root, "keys"));
            scope.Options = S206TestSupport.OwnedNodeOptions(new Dictionary<string, string?>
            { ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(scope.Root, "workspaces"), ["PHASEA_REPOSITORY_ROOT"] = AppContext.BaseDirectory,
                ["PHASEA_NODE_ID"] = "test-physical-node", ["PHASEA_NODE_SCOPE"] = "single_node_test",
                ["PHASEA_NODE_TOPOLOGY"] = "single_service", ["PHASEA_ENABLED_ROLES"] = "entry,production",
                ["PHASEA_ACCEPT_NEW_ACCOUNTS"] = "true" });
            await SqliteMetadataSchema.InitializeSingleNodeTestAsync(scope.Database.ConnectionString,scope.Options);
            scope.Store = new PhaseAMetadataStore(scope.Database.ConnectionString, scope.Options);
            scope.Owner = await scope.Store.CreateUserAccountAsync("version-owner-" + Guid.NewGuid().ToString("N"), 2);
            scope.Context = await S206TestSupport.FixtureContextAsync(scope.Store, PhaseAAuth.HashTokenForStorage(scope.Owner.Token));
            using var current = S206TestSupport.EnterCurrentContext(scope.Context);
            scope.Queue = new HeavyRunnerQueueService(TimeSpan.FromSeconds(1), 1, scope.Store);
            var creator = new ProjectCreationService(scope.Store, scope.Options, new ProjectRuleCatalog(), new Seed(),
                runnerProvisioner: new WindowsProjectRunnerProvisioner(scope.Options));
            var created = await creator.CreateProjectAsync(scope.Owner.AccountId, new(null, "Version Game", "default", null, null, null, null));
            Assert.True(created.Succeeded, created.FailureCode);
            // This fixture tests recovery after bootstrap; no bootstrap worker
            // runs in the test process. Production marks this after Chapter 2.
            await scope.Store.SetProjectBootstrapStatusAsync(created.ProjectId!, "succeeded", null);
            scope.Project = (await scope.Store.GetProjectSnapshotAsync(created.ProjectId!))!;
            Assert.True(RunnerIsolationPolicy.TryGetWorkspaceDescriptor(scope.Project.WorkspaceRootPath, out scope.Descriptor));
            var run = await scope.Store.CreateRunAsync(created.ProjectId!, scope.Project.WorkspaceId, "prototype-7day-playable");
            await scope.Store.CompleteRunAsync(run, "succeeded", 0, "", "", "{}");
            scope.BlockingProjectId = Guid.NewGuid().ToString("N");
            var blockedLayout = WorkspaceLayoutBuilder.Build(scope.Options.HostedWorkspaceRoot, scope.Owner.AccountId, scope.BlockingProjectId);
            var blocking = await scope.Store.CreateProjectAsync(new(scope.BlockingProjectId, scope.Owner.AccountId,
                "Queue blocker", "Queue blocker", "manual", "default", false, [], blockedLayout.RootPath,
                blockedLayout.RepoPath, blockedLayout.RuntimePath, blockedLayout.MetaPath));
            Assert.True(blocking.Succeeded);
            scope.Storage = scope.Store.CreateWorkspaceStorageService();
            scope.Packages = new ProjectPackageService(scope.Store, scope.Options, scope.Queue, processRunner: new HostedProcessRunner(authority: scope.Store), storage: scope.Storage);
            scope.Restorer = scope.NewRestorer(scope.Packages, scope.Storage);
            return scope;
        }
        public ProjectPackageRestoreService NewRestorer(ProjectPackageService packages, WorkspaceStorageService storage) =>
            new(Store, Options, packages, storage, Store.CreateRestoreService(), Queue,
                new RunCancellationService(), NullLogger<ProjectPackageRestoreService>.Instance);
        public async Task<RunSnapshot> WaitAsync(string id)
        {
            using var deadline = new CancellationTokenSource(TimeSpan.FromSeconds(45));
            while (true)
            {
                var run = (await Store.GetRunSnapshotAsync(id, deadline.Token))!;
                if (run.Status is not ("queued" or "running")) return run;
                await Task.Delay(50, deadline.Token);
            }
        }
        public void Dispose()
        {
            if (Descriptor is not null) WindowsProjectRunnerProvisioner.RemoveTestRegistration(Descriptor);
            Database.Dispose();
            Environment.SetEnvironmentVariable("PHASEA_SNAPSHOT_KEY_ROOT", _previousKeys);
            if (Directory.Exists(Root)) Directory.Delete(Root, true);
        }
    }
    private sealed class Seed : IProjectWorkspaceSeeder
    {
        public void EnsureSeeded(string repo)
        {
            Directory.CreateDirectory(Path.Combine(repo, "Game.Core"));
            File.WriteAllText(Path.Combine(repo, "Game.Core", "Version.cs"), "version-one");
            File.WriteAllText(Path.Combine(repo, "project.godot"), "config_version=5\n");
        }
    }
}
