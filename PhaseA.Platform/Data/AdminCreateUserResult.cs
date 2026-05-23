namespace PhaseA.Platform.Data;

public sealed record AdminCreateUserResult(
    string AccountId,
    string Username,
    string Token,
    int ProjectLimit,
    string? ValidUntilUtc = null,
    decimal? SpendLimitCny = null,
    string? AiCodeMirrorKeyName = null);
