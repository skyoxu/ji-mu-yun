namespace PhaseA.Platform.Readback;

public sealed record AdminLlmUsageAggregateReadback(
    string Grain,
    string Split,
    string FromUtc,
    string ToUtc,
    int BucketCount,
    int CallCount,
    decimal EstimatedCostCny,
    IReadOnlyList<AdminLlmUsageAggregateItem> Items);

public sealed record AdminLlmUsageAggregateItem(
    string BucketUtc,
    string AccountId,
    string Username,
    string? ProjectId,
    string? ProjectName,
    string? GameName,
    int CallCount,
    decimal EstimatedCostCny);
