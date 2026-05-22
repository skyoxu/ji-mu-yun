namespace PhaseA.Platform.Readback;

public sealed record AdminLlmUsageReadback(
    string UtcDay,
    int AccountCount,
    int CallCount,
    decimal EstimatedCostCny,
    IReadOnlyList<AdminLlmAccountUsageItem> Accounts);
