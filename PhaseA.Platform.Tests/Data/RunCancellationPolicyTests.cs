using FluentAssertions;
using PhaseA.Platform.Data;
using Xunit;

namespace PhaseA.Platform.Tests.Data;

public sealed class RunCancellationPolicyTests
{
    [Theory]
    [InlineData("chapter2-bootstrap")]
    [InlineData("project-creation")]
    [InlineData("project-asset-generation")]
    [InlineData("asset-generation")]
    [InlineData("project-web-preview")]
    public void IsCancellationBlocked_ShouldRejectCreationAndAssetRuns(string runType)
    {
        RunCancellationPolicy.IsCancellationBlocked(runType).Should().BeTrue();
    }

    [Theory]
    [InlineData("prototype-iteration-goal")]
    [InlineData("prototype-quick-fix")]
    [InlineData("project-package")]
    public void IsCancellationBlocked_ShouldAllowOtherWorkflowRuns(string runType)
    {
        RunCancellationPolicy.IsCancellationBlocked(runType).Should().BeFalse();
    }
}
