using PhaseA.Platform.Tests.NodeIdentity;
using System.Text.Json;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Security;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S10BoundaryTests
{
    private readonly ITestOutputHelper _output;

    public S10BoundaryTests(ITestOutputHelper output)
    {
        _output = output;
    }

    [Fact]
    public async Task O_3E7CE839D9C3()
    {
        var fixture = await S206QueueFixture.CreateAsync("project-s10");
        using var current = S206TestSupport.EnterCurrentContext(fixture.ControlContext);
        var queue = new HeavyRunnerQueueService(TimeSpan.FromMinutes(1), maxConcurrentRuns: 1, authority: fixture.Store);
        await using var blockingLease = await queue.EnterAsync(
            "blocking-run",
            fixture.AccountId,
            "project-s10",
            "test-run");

        var accountDisabled = false;
        var writeLeaseGranted = false;
        var context = fixture.Context;

        var queuedWork = queue.ExecuteAuthorizedAsync(
            "target-run",
            fixture.AccountId,
            "project-s10",
            "test-run",
            context,
            (_, _) => Task.FromResult(!accountDisabled),
            _ =>
            {
                writeLeaseGranted = true;
                return Task.FromResult("write-lease");
            });

        var queuedBeforeDisable = await WaitUntilAsync(
            () => queue.GetReadback(fixture.AccountId, includeAll: true).QueuedCount == 1,
            TimeSpan.FromSeconds(2));
        accountDisabled = true;
        await blockingLease.DisposeAsync();

        var reauthorizationDenied = false;
        try
        {
            await queuedWork;
        }
        catch (UnauthorizedAccessException)
        {
            reauthorizationDenied = true;
        }

        var afterDispatch = queue.GetReadback(fixture.AccountId, includeAll: true);
        _output.WriteLine("S10_OBSERVATION:" + JsonSerializer.Serialize(new
        {
            queuedBeforeDisable,
            reauthorizationDenied,
            queueDrainedAfterDispatch = afterDispatch.QueuedCount == 0 && !afterDispatch.Running,
            writeLeaseGranted
        }));
    }

    private static async Task<bool> WaitUntilAsync(Func<bool> condition, TimeSpan timeout)
    {
        var deadline = DateTimeOffset.UtcNow + timeout;
        while (DateTimeOffset.UtcNow < deadline)
        {
            if (condition())
            {
                return true;
            }

            await Task.Delay(TimeSpan.FromMilliseconds(10));
        }

        return condition();
    }
}
