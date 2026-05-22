namespace PhaseA.Platform.Readback;

public sealed record AdminLlmAccountUsageItem(
    string AccountId,
    string Username,
    bool IsAdmin,
    bool IsDisabled,
    int ProjectCount,
    int CallCount,
    decimal EstimatedCostCny);
