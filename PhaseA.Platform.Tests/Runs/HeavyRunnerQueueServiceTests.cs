using PhaseA.Platform.Tests.NodeIdentity;
using PhaseA.Platform.Security;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Tests.Data;
using PhaseA.Platform.Workspaces;
using PhaseA.Platform.Runs;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class HeavyRunnerQueueServiceTests
{
    [Fact]
    public async Task TryEnter_RespectsEveryActiveProjectCapacityAndWaitingWork()
    {
        // ADR-0036: recovery is nonblocking and uses the same project ownership as execution.
        using var fixture = await QueueFixture.CreateAsync(true);
        using var current = S206TestSupport.EnterCurrentContext(fixture.Context);
        var queue = new HeavyRunnerQueueService(TimeSpan.FromSeconds(1), maxConcurrentRuns: 3, authority: fixture.Store);
        await using var first = await queue.EnterAsync("first", fixture.Accounts[0], fixture.Projects[0], "work");
        await using var second = await queue.EnterAsync("second", fixture.Accounts[0], fixture.Projects[1], "work");
        Assert.Null(queue.TryEnter("same-second-project", fixture.Accounts[0], fixture.Projects[1], "recovery"));

        await using var third = queue.TryEnter("third", fixture.Accounts[0], fixture.Projects[2], "recovery");
        Assert.NotNull(third);
        Assert.Null(queue.TryEnter("at-capacity", fixture.Accounts[0], fixture.Projects[3], "recovery"));
        await third!.DisposeAsync();

        using var cancellation = new CancellationTokenSource();
        var waiting = queue.EnterAsync("waiting", fixture.Accounts[0], fixture.Projects[0], "work", cancellation.Token);
        Assert.Equal(1, queue.GetReadback(fixture.Accounts[0], includeAll: true).QueuedCount);
        Assert.Null(queue.TryEnter("bypass-waiting", fixture.Accounts[0], fixture.Projects[3], "recovery"));
        cancellation.Cancel();
        await Assert.ThrowsAnyAsync<OperationCanceledException>(() => waiting);

        await using var available = queue.TryEnter("available", fixture.Accounts[0], fixture.Projects[3], "recovery");
        Assert.NotNull(available);
        Assert.Null(queue.TryEnter("same-available-project", fixture.Accounts[0], fixture.Projects[3], "recovery"));
        await available!.DisposeAsync();
        Assert.Equal(0, queue.GetReadback(fixture.Accounts[0], includeAll: true).QueuedCount);
        await second.DisposeAsync();
        await first.DisposeAsync();
        Assert.False(queue.GetReadback(fixture.Accounts[0], includeAll: true).Running);
    }

    [Fact]
    public async Task ExecuteAsync_RunsHeavyWorkOneAtATimeInFifoOrder()
    {
        using var fixture = await QueueFixture.CreateAsync(false);
        using var current = S206TestSupport.EnterCurrentContext(fixture.Context);
        var queue = new HeavyRunnerQueueService(TimeSpan.FromSeconds(30), maxConcurrentRuns: 1, authority: fixture.Store);
        var waitTimeout = TimeSpan.FromSeconds(60);
        var firstCanFinish = new TaskCompletionSource();
        var firstStarted = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        var secondStarted = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        var order = new List<string>();

        var first = queue.ExecuteAsync(
            "run-1",
            fixture.Accounts[0],
            fixture.Projects[0],
            "prototype-7day-playable",
            async _ =>
            {
                order.Add("first");
                firstStarted.SetResult();
                await firstCanFinish.Task;
                return "first";
            });

        await firstStarted.Task.WaitAsync(waitTimeout);

        var second = queue.ExecuteAsync(
            "run-2",
            fixture.Accounts[1],
            fixture.Projects[1],
            "prototype-quick-fix",
            _ =>
            {
                order.Add("second");
                secondStarted.SetResult();
                return Task.FromResult("second");
            });

        var readback = queue.GetReadback(fixture.Accounts[1], includeAll: false);
        Assert.True(readback.Running);
        Assert.Equal(1, readback.QueuedCount);
        Assert.Equal(1, readback.CurrentAccountPosition);
        Assert.Equal(30, readback.CurrentAccountEstimatedWaitSeconds);
        Assert.False(secondStarted.Task.IsCompleted);

        firstCanFinish.SetResult();

        Assert.Equal("first", await first.WaitAsync(waitTimeout));
        Assert.Equal("second", await second.WaitAsync(waitTimeout));
        Assert.Equal(["first", "second"], order);
        Assert.False(queue.GetReadback(fixture.Accounts[1], includeAll: true).Running);
    }

    [Fact]
    public async Task ExecuteAsync_UsesConfiguredOtherRunConcurrency()
    {
        using var fixture = await QueueFixture.CreateAsync(false);
        using var current = S206TestSupport.EnterCurrentContext(fixture.Context);
        var queue = new HeavyRunnerQueueService(TimeSpan.FromSeconds(30), maxConcurrentRuns: 2, authority: fixture.Store);
        var waitTimeout = TimeSpan.FromSeconds(60);
        var firstCanFinish = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        var secondCanFinish = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        var firstStarted = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        var secondStarted = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        var thirdStarted = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);

        var first = queue.ExecuteAsync(
            "run-1",
            fixture.Accounts[0],
            fixture.Projects[0],
            "prototype-7day-playable",
            async _ =>
            {
                firstStarted.SetResult();
                await firstCanFinish.Task;
                return "first";
            });

        var second = queue.ExecuteAsync(
            "run-2",
            fixture.Accounts[1],
            fixture.Projects[1],
            "prototype-quick-fix",
            async _ =>
            {
                secondStarted.SetResult();
                await secondCanFinish.Task;
                return "second";
            });

        await firstStarted.Task.WaitAsync(waitTimeout);
        await secondStarted.Task.WaitAsync(waitTimeout);

        var third = queue.ExecuteAsync(
            "run-3",
            fixture.Accounts[2],
            fixture.Projects[2],
            "prototype-ui-optimization",
            _ =>
            {
                thirdStarted.SetResult();
                return Task.FromResult("third");
            });

        var readback = queue.GetReadback(fixture.Accounts[2], includeAll: true);
        Assert.True(readback.Running);
        Assert.Equal(1, readback.QueuedCount);
        Assert.Equal(1, readback.CurrentAccountPosition);
        Assert.False(thirdStarted.Task.IsCompleted);

        firstCanFinish.SetResult();

        Assert.Equal("first", await first.WaitAsync(waitTimeout));
        await thirdStarted.Task.WaitAsync(waitTimeout);
        Assert.Equal("third", await third.WaitAsync(waitTimeout));

        secondCanFinish.SetResult();
        Assert.Equal("second", await second.WaitAsync(waitTimeout));
    }

    [Fact]
    public async Task ExecuteAsync_RemovesCancelledWaitingItemFromQueue()
    {
        using var fixture = await QueueFixture.CreateAsync(false);
        using var current = S206TestSupport.EnterCurrentContext(fixture.Context);
        var queue = new HeavyRunnerQueueService(TimeSpan.FromSeconds(30), maxConcurrentRuns: 1, authority: fixture.Store);
        var waitTimeout = TimeSpan.FromSeconds(60);
        var firstCanFinish = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        var firstStarted = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        var thirdStarted = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);

        var first = queue.ExecuteAsync(
            "run-1",
            fixture.Accounts[0],
            fixture.Projects[0],
            "prototype-7day-playable",
            async _ =>
            {
                firstStarted.SetResult();
                await firstCanFinish.Task;
                return "first";
            });

        await firstStarted.Task.WaitAsync(waitTimeout);

        using var cancelled = new CancellationTokenSource();
        var second = queue.ExecuteAsync(
            "run-2",
            fixture.Accounts[1],
            fixture.Projects[1],
            "prototype-quick-fix",
            _ => Task.FromResult("second"),
            cancelled.Token);

        var readbackBeforeCancel = queue.GetReadback(fixture.Accounts[1], includeAll: true);
        Assert.Equal(1, readbackBeforeCancel.QueuedCount);

        await cancelled.CancelAsync();
        await Assert.ThrowsAnyAsync<OperationCanceledException>(() => second.WaitAsync(waitTimeout));

        var third = queue.ExecuteAsync(
            "run-3",
            fixture.Accounts[2],
            fixture.Projects[2],
            "prototype-ui-optimization",
            _ =>
            {
                thirdStarted.SetResult();
                return Task.FromResult("third");
            });

        var readbackAfterCancel = queue.GetReadback(fixture.Accounts[2], includeAll: true);
        Assert.Equal(1, readbackAfterCancel.QueuedCount);

        firstCanFinish.SetResult();

        Assert.Equal("first", await first.WaitAsync(waitTimeout));
        await thirdStarted.Task.WaitAsync(waitTimeout);
        Assert.Equal("third", await third.WaitAsync(waitTimeout));
        Assert.Equal(0, queue.GetReadback(fixture.Accounts[2], includeAll: true).QueuedCount);
    }

    [Fact]
    public async Task ExecuteAsync_ExposesQueuePositionAtStart()
    {
        using var fixture = await QueueFixture.CreateAsync(false);
        using var current = S206TestSupport.EnterCurrentContext(fixture.Context);
        var queue = new HeavyRunnerQueueService(TimeSpan.FromSeconds(30), maxConcurrentRuns: 1, authority: fixture.Store);
        var waitTimeout = TimeSpan.FromSeconds(60);
        var firstCanFinish = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        var firstStarted = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        var secondStartedPosition = new TaskCompletionSource<int>(TaskCreationOptions.RunContinuationsAsynchronously);

        var first = queue.ExecuteAsync(
            "run-1",
            fixture.Accounts[0],
            fixture.Projects[0],
            "prototype-7day-playable",
            async (start, _) =>
            {
                Assert.Equal(1, start.QueuePositionAtStart);
                firstStarted.SetResult();
                await firstCanFinish.Task;
                return "first";
            });

        await firstStarted.Task.WaitAsync(waitTimeout);

        var second = queue.ExecuteAsync(
            "run-2",
            fixture.Accounts[1],
            fixture.Projects[1],
            "prototype-quick-fix",
            (start, _) =>
            {
                secondStartedPosition.SetResult(start.QueuePositionAtStart);
                return Task.FromResult("second");
            });

        firstCanFinish.SetResult();

        Assert.Equal("first", await first.WaitAsync(waitTimeout));
        Assert.Equal("second", await second.WaitAsync(waitTimeout));
        Assert.Equal(2, await secondStartedPosition.Task.WaitAsync(waitTimeout));
    }

    [Fact]
    public async Task EnterAsync_ExposesQueuePositionAtStart()
    {
        using var fixture = await QueueFixture.CreateAsync(false);
        using var current = S206TestSupport.EnterCurrentContext(fixture.Context);
        var queue = new HeavyRunnerQueueService(TimeSpan.FromSeconds(30), HeavyRunnerQueueService.DefaultMaxConcurrentOtherRuns, authority: fixture.Store);
        await using var lease = await queue.EnterAsync(
            "run-1",
            fixture.Accounts[0],
            fixture.Projects[0],
            "prototype-7day-playable");

        Assert.Equal(1, lease.QueuePositionAtStart);
    }
    [Fact]
    public async Task ExplicitFixtureAuthorityKeepsMissingForgedAndRevokedIdentityClosed()
    {
        using var fixture = await QueueFixture.CreateAsync(false);
        var queue = new HeavyRunnerQueueService(null, 1, fixture.Store);
        await Assert.ThrowsAsync<UnauthorizedAccessException>(() => queue.EnterAsync("missing", fixture.Accounts[0], fixture.Projects[0], "work"));
        using (S206TestSupport.EnterCurrentContext(fixture.Context with { CredentialId = "not-the-current-credential" }))
            await Assert.ThrowsAsync<UnauthorizedAccessException>(() => queue.EnterAsync("forged", fixture.Accounts[0], fixture.Projects[0], "work"));
        using (S206TestSupport.EnterCurrentContext(fixture.Context))
        {
            await using (var lease = await queue.EnterAsync("valid", fixture.Accounts[0], fixture.Projects[0], "work"))
                Assert.Equal(1, lease.QueuePositionAtStart);
            await fixture.Store.SetUserDisabledAsync(fixture.Accounts[0], true);
            await Assert.ThrowsAsync<UnauthorizedAccessException>(() => queue.EnterAsync("revoked", fixture.Accounts[0], fixture.Projects[0], "work"));
            await fixture.Store.SetUserDisabledAsync(fixture.Accounts[0], false);
            await using var restored = await queue.EnterAsync("restored", fixture.Accounts[0], fixture.Projects[0], "work");
            Assert.Equal(1, restored.QueuePositionAtStart);
        }
    }

    // ADR-0061: queue scheduling is exercised behind real current node/owner authority.
    private sealed class QueueFixture : IDisposable
    {
        private TempSqliteDatabase _database = null!;
        public PhaseAMetadataStore Store = null!;
        public RequestContext Context = null!;
        public List<string> Accounts = [];
        public List<string> Projects = [];
        public static async Task<QueueFixture> CreateAsync(bool sameOwner)
        {
            var fixture = new QueueFixture { _database = TempSqliteDatabase.Create() };
            var options = S206TestSupport.OwnedNodeOptions(new() { ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath(), ["PHASEA_REPOSITORY_ROOT"] = AppContext.BaseDirectory });
            await SqliteMetadataSchema.InitializeSingleNodeTestAsync(fixture._database.ConnectionString, options);
            fixture.Store = new PhaseAMetadataStore(fixture._database.ConnectionString, options);
            fixture.Context = await fixture.Store.ResolveStartupMaintenanceContextAsync();
            for (var index = 0; index < 4; index++)
            {
                var owner = await fixture.Store.CreateUserAccountAsync("queue-owner-" + index, 5);
                fixture.Accounts.Add(owner.AccountId);
                var account = sameOwner ? fixture.Accounts[0] : owner.AccountId;
                var project = Guid.NewGuid().ToString("N");
                var layout = WorkspaceLayoutBuilder.Build(Path.GetTempPath(), account, project);
                var created = await fixture.Store.CreateProjectAsync(new(project, account, "Queue", "Queue", "manual", "default", false, [],
                    layout.RootPath, layout.RepoPath, layout.RuntimePath, layout.MetaPath));
                Assert.True(created.Succeeded);
                fixture.Projects.Add(project);
            }
            return fixture;
        }
        public void Dispose() => _database.Dispose();
    }
}
