using FluentAssertions;
using PhaseA.Platform.Workspaces;
using Xunit;

namespace PhaseA.Platform.Tests.PhaseB;

public sealed class RestoreRecoveryTests
{
    [Fact]
    public void RestoreAttempt_IsAppendOnlyAndCannotPublishTwiceIntoAnotherState()
    {
        var attempt = new RestoreAttempt("attempt-1", "snapshot-1", "workspace-1", RestoreAttemptStatus.Requested)
            .Advance(RestoreAttemptStatus.Staging)
            .Advance(RestoreAttemptStatus.Published);

        attempt.Status.Should().Be(RestoreAttemptStatus.Published);
        var act = () => attempt.Advance(RestoreAttemptStatus.Quarantined);
        act.Should().Throw<InvalidOperationException>();
    }
}
