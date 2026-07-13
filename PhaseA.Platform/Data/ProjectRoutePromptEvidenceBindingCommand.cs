namespace PhaseA.Platform.Data;

public sealed record ProjectRoutePromptEvidenceBindingCommand(
    string ProjectId,
    string RouteId,
    string ExecutionPromptHash,
    string PersistedPromptHash,
    string PromptArtifactRef,
    string PromptEvidenceRef);
