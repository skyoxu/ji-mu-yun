namespace PhaseA.Platform.Data;

public sealed record AdminUpdateUserLimitsRequest(
    int? ValidDays,
    decimal? SpendLimitCny);
