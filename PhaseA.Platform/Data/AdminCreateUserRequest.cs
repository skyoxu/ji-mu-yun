namespace PhaseA.Platform.Data;

public sealed record AdminCreateUserRequest(
    string? Username,
    int? ProjectLimit,
    int? ValidDays = null,
    decimal? SpendLimitCny = null);
