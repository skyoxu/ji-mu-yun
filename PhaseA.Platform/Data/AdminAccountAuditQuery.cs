namespace PhaseA.Platform.Data;

public sealed record AdminAccountAuditQuery(
    int Limit = 100,
    int Offset = 0,
    string? Action = null,
    string? TargetAccountId = null);
