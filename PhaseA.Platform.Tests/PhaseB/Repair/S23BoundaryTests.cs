using System.Text.Json;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Security;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S23BoundaryTests
{
    private readonly ITestOutputHelper _output;

    public S23BoundaryTests(ITestOutputHelper output) => _output = output;

    [Fact]
    public async Task O_7E028CBB46E6()
    {
        var queue = new HeavyRunnerQueueService(TimeSpan.FromMinutes(1), 1);
        await using var blocker = await queue.EnterAsync("blocker", "account-s23", "project-s23", "test-run");
        var revoked = false;
        var workRan = false;
        var task = queue.ExecuteAuthorizedAsync("target", "account-s23", "project-s23", "test-run",
            Context(), (_, _) => Task.FromResult(!revoked), _ => { workRan = true; return Task.FromResult("lease"); });
        var queued = await WaitUntilAsync(() => queue.GetReadback("account-s23", true).QueuedCount == 1);
        revoked = true;
        await blocker.DisposeAsync();
        var denied = await IsUnauthorized(task);
        var readback = queue.GetReadback("account-s23", true);
        _output.WriteLine("S23_OBSERVATION:" + JsonSerializer.Serialize(new { queued, denied, drained = readback.QueuedCount == 0 && !readback.Running, workRan }));
    }

    [Fact]
    public async Task O_C81702C3110F()
    {
        var queue = new HeavyRunnerQueueService(TimeSpan.FromMinutes(1), 1);
        await using var blocker = await queue.EnterAsync("blocker", "account-s23", "project-s23", "test-run");
        var disabled = false;
        var workRan = false;
        var task = queue.ExecuteAuthorizedAsync("target", "account-s23", "project-s23", "test-run",
            Context(), (_, _) => Task.FromResult(!disabled), _ => { workRan = true; return Task.FromResult("lease"); });
        var queued = await WaitUntilAsync(() => queue.GetReadback("account-s23", true).QueuedCount == 1);
        disabled = true;
        await blocker.DisposeAsync();
        var denied = await IsUnauthorized(task);
        _output.WriteLine("S23_OBSERVATION:" + JsonSerializer.Serialize(new { queued, denied, writeLeaseGranted = workRan }));
    }

    [Fact]
    public async Task O_E48D8E1001E0()
    {
        var queue = new HeavyRunnerQueueService(TimeSpan.FromMinutes(1), 1);
        await using var blocker = await queue.EnterAsync("blocker", "account-s23", "project-s23", "test-run");
        var revoked = false;
        var workRan = false;
        var task = queue.ExecuteAuthorizedAsync("target", "account-s23", "project-s23", "test-run",
            Context(), (_, _) => Task.FromResult(!revoked), _ => { workRan = true; return Task.FromResult("lease"); });
        var queued = await WaitUntilAsync(() => queue.GetReadback("account-s23", true).QueuedCount == 1);
        revoked = true;
        await blocker.DisposeAsync();
        var denied = await IsUnauthorized(task);
        _output.WriteLine("S23_OBSERVATION:" + JsonSerializer.Serialize(new { queued, denied, writeLeaseGranted = workRan }));
    }

    private static RequestContext Context() => new("principal-s23", "account-s23", new HashSet<string>(StringComparer.Ordinal) { PhaseAAuth.UserRole }, "credential-s23", "correlation-s23");

    private static async Task<bool> IsUnauthorized(Task<string> task)
    {
        try { await task; return false; }
        catch (UnauthorizedAccessException) { return true; }
    }

    private static async Task<bool> WaitUntilAsync(Func<bool> condition)
    {
        var deadline = DateTimeOffset.UtcNow.AddSeconds(2);
        while (DateTimeOffset.UtcNow < deadline)
        {
            if (condition()) return true;
            await Task.Delay(10);
        }
        return condition();
    }
}
