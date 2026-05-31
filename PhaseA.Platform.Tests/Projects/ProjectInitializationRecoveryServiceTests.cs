using FluentAssertions;
using PhaseA.Platform.Data;
using PhaseA.Platform.Projects;
using Xunit;

namespace PhaseA.Platform.Tests.Projects;

public sealed class ProjectInitializationRecoveryServiceTests
{
    [Fact]
    public void SelectTimeoutForTesting_ShouldAllowLongRunningPrototypeQuickFixGoalRepair()
    {
        var run = new InterruptedRunSnapshot(
            "run-1",
            "project-1",
            "prototype-quick-fix",
            "running",
            DateTimeOffset.UtcNow.AddMinutes(-10).ToString("O"),
            DateTimeOffset.UtcNow.AddMinutes(-10).ToString("O"),
            DateTimeOffset.UtcNow.AddMinutes(-10).ToString("O"));

        var timeout = ProjectInitializationRecoveryService.SelectTimeoutForTesting(run);

        timeout.Should().BeGreaterThan(TimeSpan.FromMinutes(12));
    }
}
