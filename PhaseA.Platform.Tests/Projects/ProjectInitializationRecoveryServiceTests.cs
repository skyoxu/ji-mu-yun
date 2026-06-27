using FluentAssertions;
using PhaseA.Platform.Configuration;
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

    [Fact]
    public void SelectTimeoutForTesting_ShouldUseShortWebPreviewRecoveryTimeoutByDefault()
    {
        var run = new InterruptedRunSnapshot(
            "run-1",
            "project-1",
            "project-web-preview",
            "running",
            DateTimeOffset.UtcNow.AddMinutes(-10).ToString("O"),
            DateTimeOffset.UtcNow.AddMinutes(-10).ToString("O"),
            DateTimeOffset.UtcNow.AddMinutes(-10).ToString("O"));

        var timeout = ProjectInitializationRecoveryService.SelectTimeoutForTesting(run);

        timeout.Should().Be(TimeSpan.FromMinutes(5));
    }

    [Fact]
    public void SelectTimeoutForTesting_ShouldAllowLongerWebPreviewQueueWait()
    {
        var run = new InterruptedRunSnapshot(
            "run-1",
            "project-1",
            "project-web-preview",
            "queued",
            DateTimeOffset.UtcNow.AddMinutes(-10).ToString("O"),
            null,
            DateTimeOffset.UtcNow.AddMinutes(-10).ToString("O"));

        var timeout = ProjectInitializationRecoveryService.SelectTimeoutForTesting(run);

        timeout.Should().Be(TimeSpan.FromMinutes(30));
    }

    [Fact]
    public void SelectTimeoutForTesting_ShouldRecoverQueuedWebPreviewCreatedBeforeCurrentProcess()
    {
        var processStartedUtc = DateTimeOffset.UtcNow;
        var run = new InterruptedRunSnapshot(
            "run-1",
            "project-1",
            "project-web-preview",
            "queued",
            processStartedUtc.AddSeconds(-5).ToString("O"),
            null,
            processStartedUtc.AddSeconds(-5).ToString("O"));

        var timeout = ProjectInitializationRecoveryService.SelectTimeoutForTesting(
            run,
            processStartedUtc: processStartedUtc);
        var message = ProjectInitializationRecoveryService.BuildFailureMessageForTesting(
            run,
            processStartedUtc);

        timeout.Should().Be(TimeSpan.Zero);
        message.Should().Contain("server restarted");
    }

    [Fact]
    public void SelectTimeoutForTesting_ShouldKeepCurrentProcessQueuedWebPreviewWait()
    {
        var processStartedUtc = DateTimeOffset.UtcNow;
        var run = new InterruptedRunSnapshot(
            "run-1",
            "project-1",
            "project-web-preview",
            "queued",
            processStartedUtc.AddSeconds(5).ToString("O"),
            null,
            processStartedUtc.AddSeconds(5).ToString("O"));

        var timeout = ProjectInitializationRecoveryService.SelectTimeoutForTesting(
            run,
            processStartedUtc: processStartedUtc);

        timeout.Should().Be(TimeSpan.FromMinutes(30));
    }

    [Fact]
    public void SelectTimeoutForTesting_ShouldHonorConfiguredWebPreviewExportTimeout()
    {
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_GODOT3_WEB_PREVIEW_EXPORT_TIMEOUT_SECONDS"] = "240"
        });
        var run = new InterruptedRunSnapshot(
            "run-1",
            "project-1",
            "project-web-preview",
            "running",
            DateTimeOffset.UtcNow.AddMinutes(-10).ToString("O"),
            DateTimeOffset.UtcNow.AddMinutes(-10).ToString("O"),
            DateTimeOffset.UtcNow.AddMinutes(-10).ToString("O"));

        var timeout = ProjectInitializationRecoveryService.SelectTimeoutForTesting(run, options);

        timeout.Should().Be(TimeSpan.FromMinutes(6));
    }
}
