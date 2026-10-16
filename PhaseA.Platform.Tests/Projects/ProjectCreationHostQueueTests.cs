using PhaseA.Platform.Projects;
using Xunit;

namespace PhaseA.Platform.Tests.Projects;

// ADR-0035: acceptance across accounts waits on the existing host budget.
public sealed class ProjectCreationHostQueueTests
{
    [Fact]
    public async Task FourthAccountWaitsInsteadOfBeingRejectedByAPlatformLimit()
    {
        var limiter = new ProjectCreationConcurrencyLimiter(3);
        var leases = new List<ProjectCreationConcurrencyLease>();
        try
        {
            for (var index = 0; index < 3; index++)
                leases.Add((await limiter.AcquireAsync($"owner-{index}")).Lease!);
            var fourth = limiter.AcquireAsync("owner-four").AsTask();
            Assert.False(fourth.IsCompleted);
            await leases[0].DisposeAsync();
            var admitted = await fourth.WaitAsync(TimeSpan.FromSeconds(5));
            Assert.Null(admitted.FailureCode);
            Assert.NotNull(admitted.Lease);
            await admitted.Lease!.DisposeAsync();
        }
        finally { foreach (var lease in leases) await lease.DisposeAsync(); }
    }

    [Fact]
    public async Task CancelledWaitReleasesItsAccountSlot_AndAccountLimitStillApplies()
    {
        var limiter = new ProjectCreationConcurrencyLimiter(1);
        await using var active = (await limiter.AcquireAsync("active")).Lease!;
        using var cancel = new CancellationTokenSource();
        var pending = limiter.AcquireAsync("waiting", cancel.Token).AsTask();
        Assert.Equal("user_project_creation_concurrency_limit_exceeded", (await limiter.AcquireAsync("waiting")).FailureCode);
        cancel.Cancel();
        await Assert.ThrowsAnyAsync<OperationCanceledException>(() => pending);
        await active.DisposeAsync();
        var next = await limiter.AcquireAsync("waiting");
        Assert.NotNull(next.Lease);
        await next.Lease!.DisposeAsync();
    }
}
