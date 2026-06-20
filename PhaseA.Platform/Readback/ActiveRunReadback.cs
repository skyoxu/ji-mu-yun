namespace PhaseA.Platform.Readback;

public sealed record ActiveRunReadback(
    bool Busy,
    string? RunId,
    string? ProjectId,
    string? RunType,
    string? Status,
    string? ProgressStep,
    string? ProgressLabel,
    string? CreatedUtc = null,
    string? StartedUtc = null,
    string? ProgressUpdatedUtc = null,
    int HeavyRunnerQueuedCount = 0,
    int? HeavyRunnerQueuePosition = null,
    int? HeavyRunnerEstimatedWaitSeconds = null,
    bool HeavyRunnerRunning = false);
