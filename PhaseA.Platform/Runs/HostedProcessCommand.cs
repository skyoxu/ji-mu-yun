namespace PhaseA.Platform.Runs;

public sealed record HostedProcessCommand(
    string FileName,
    IReadOnlyList<string> Arguments,
    string WorkingDirectory,
    IReadOnlyDictionary<string, string> Environment,
    string? StandardInput = null,
    string? RunId = null,
    TimeSpan? TotalTimeout = null,
    TimeSpan? InactivityTimeout = null,
    IReadOnlyList<string>? ActivityWatchPaths = null,
    TimeSpan? ActivityWatchPollInterval = null,
    bool RequireIsolation = false)
{
    public HostedProcessCommand WithRunId(string runId)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(runId);
        return this with { RunId = runId };
    }

    public HostedProcessCommand WithTimeouts(TimeSpan? totalTimeout = null, TimeSpan? inactivityTimeout = null)
    {
        if (totalTimeout is { } total && total <= TimeSpan.Zero)
        {
            throw new ArgumentOutOfRangeException(nameof(totalTimeout), "Total timeout must be positive.");
        }

        if (inactivityTimeout is { } inactive && inactive <= TimeSpan.Zero)
        {
            throw new ArgumentOutOfRangeException(nameof(inactivityTimeout), "Inactivity timeout must be positive.");
        }

        return this with
        {
            TotalTimeout = totalTimeout,
            InactivityTimeout = inactivityTimeout
        };
    }

    public HostedProcessCommand WithActivityWatchPaths(
        IReadOnlyList<string> activityWatchPaths,
        TimeSpan? pollInterval = null)
    {
        ArgumentNullException.ThrowIfNull(activityWatchPaths);
        if (pollInterval is { } interval && interval <= TimeSpan.Zero)
        {
            throw new ArgumentOutOfRangeException(nameof(pollInterval), "Activity watch poll interval must be positive.");
        }

        return this with
        {
            ActivityWatchPaths = activityWatchPaths,
            ActivityWatchPollInterval = pollInterval
        };
    }
}
