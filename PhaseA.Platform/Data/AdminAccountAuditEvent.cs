namespace PhaseA.Platform.Data;

public sealed record AdminAccountAuditEvent(
    string EventId,
    string ActorAccountId,
    string Action,
    string? TargetAccountId,
    string MetadataJson,
    string CreatedUtc);
