namespace PhaseA.Platform.Readback;

public sealed record AccountLlmUsageReadback(
    string UtcDay,
    int CallCount,
    decimal EstimatedCostCny,
    IReadOnlyList<RunReadbackItem> RecentRuns);
