using PhaseA.Platform.Runs;
using PhaseA.Platform.Security;
using Xunit;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S9BoundaryTests
{
    [Fact]
    public async Task O_05CB0734E7E0()
    {
        var queue = new HeavyRunnerQueueService(TimeSpan.Zero, maxConcurrentRuns: 1);
        var queuedContext = new RequestContext(
            "s9-role-principal",
            "s9-role-account",
            new HashSet<string>(StringComparer.Ordinal) { PhaseAAuth.AdminRole },
            "s9-role-credential",
            "s9-role-correlation");
        var currentServerRoles = queuedContext.Roles.ToHashSet(StringComparer.Ordinal);
        var blockerStarted = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
        var releaseBlocker = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
        var blocker = queue.ExecuteAsync(
            "s9-role-blocker",
            queuedContext.AccountId,
            "s9-role-project",
            "s9-role-blocker",
            async cancellationToken =>
            {
                blockerStarted.TrySetResult(true);
                await releaseBlocker.Task.WaitAsync(cancellationToken);
                return true;
            });

        await blockerStarted.Task.WaitAsync(TimeSpan.FromSeconds(10));

        var deferredWorkStarted = false;
        IReadOnlySet<string>? rolesRecordedAtExecution = null;
        var deferred = queue.ExecuteAuthorizedAsync(
            "s9-role-deferred",
            queuedContext.AccountId,
            "s9-role-project",
            "s9-role-deferred",
            queuedContext,
            (_, _) =>
            {
                rolesRecordedAtExecution = new HashSet<string>(currentServerRoles, StringComparer.Ordinal);
                return Task.FromResult(currentServerRoles.Contains(PhaseAAuth.AdminRole));
            },
            cancellationToken =>
            {
                deferredWorkStarted = true;
                return Task.FromResult(true);
            });

        currentServerRoles.Remove(PhaseAAuth.AdminRole);
        releaseBlocker.TrySetResult(true);
        await blocker;
        var deferredDenied = await IsDeniedAsync(deferred);

        Require(
            deferredDenied &&
            !deferredWorkStarted &&
            rolesRecordedAtExecution is not null &&
            !rolesRecordedAtExecution.Contains(PhaseAAuth.AdminRole),
            "FAILURE-O-05CB0734E7E0",
            "Deferred work started after the required role was removed instead of being denied at execution.");
    }

    [Fact]
    public async Task O_12B44DD27432()
    {
        var queue = new HeavyRunnerQueueService(TimeSpan.Zero, maxConcurrentRuns: 1);
        var blockerStarted = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
        var releaseBlocker = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
        var blocker = queue.ExecuteAsync(
            "s9-disabled-blocker",
            "s9-disabled-account",
            "s9-disabled-project",
            "s9-disabled-blocker",
            async cancellationToken =>
            {
                blockerStarted.TrySetResult(true);
                await releaseBlocker.Task.WaitAsync(cancellationToken);
                return true;
            });

        await blockerStarted.Task.WaitAsync(TimeSpan.FromSeconds(10));

        var accountDisabled = false;
        var subsequentWorkStarted = false;
        var disabledContext = new RequestContext(
            "s9-disabled-principal",
            "s9-disabled-account",
            new HashSet<string>(StringComparer.Ordinal) { PhaseAAuth.UserRole },
            "s9-disabled-credential",
            "s9-disabled-correlation");
        var deferred = queue.ExecuteAuthorizedAsync(
            "s9-disabled-deferred",
            "s9-disabled-account",
            "s9-disabled-project",
            "s9-disabled-deferred",
            disabledContext,
            (_, _) => Task.FromResult(!accountDisabled),
            cancellationToken =>
            {
                subsequentWorkStarted = true;
                return Task.FromResult(true);
            });

        accountDisabled = true;
        releaseBlocker.TrySetResult(true);
        await blocker;
        var deferredDenied = await IsDeniedAsync(deferred);

        Require(
            accountDisabled && deferredDenied && !subsequentWorkStarted,
            "FAILURE-O-12B44DD27432",
            "Subsequent work started after the Account was disabled instead of being denied at execution.");
    }

    private static async Task<bool> IsDeniedAsync(Task operation)
    {
        try
        {
            await operation;
            return false;
        }
        catch (UnauthorizedAccessException)
        {
            return true;
        }
    }

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
        {
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
        }
    }
}
