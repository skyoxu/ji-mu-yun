namespace PhaseA.Platform.Data;

public sealed record ProjectRoutePromptEvidenceBinding(
    string ProjectId,
    string RouteId,
    string ExecutionPromptHash,
    string PersistedPromptHash,
    string PromptArtifactRef,
    string PromptEvidenceRef,
    string UpdatedUtc);
