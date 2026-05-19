namespace PhaseA.Platform.Data;

public sealed record ProjectRunMemorySnapshot(
    string MemoryId,
    string ProjectId,
    string Scope,
    string Status,
    string CurrentObjective,
    string CompletedItemsJson,
    string CurrentBlockersJson,
    string NextRecommendedAction,
    string AllowedScopeJson,
    string? LastVerifiedResult,
    string? LastRunOutcome,
    string UpdatedUtc);
