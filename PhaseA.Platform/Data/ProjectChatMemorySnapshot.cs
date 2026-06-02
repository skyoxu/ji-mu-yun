namespace PhaseA.Platform.Data;

public sealed record ProjectChatMemorySnapshot(
    string AccountId,
    string ProjectId,
    string MemorySummary,
    string? ProviderSessionRef,
    string UpdatedUtc);
