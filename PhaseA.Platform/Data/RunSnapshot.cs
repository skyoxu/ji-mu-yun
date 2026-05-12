namespace PhaseA.Platform.Data;

public sealed record RunSnapshot(
    string RunId,
    string ProjectId,
    string? WorkspaceId,
    string RunType,
    string Status,
    int? ExitCode,
    string? StdoutText,
    string? StderrText,
    string? EvidenceJson,
    string ProgressStep = "",
    string ProgressSubstep = "",
    string ProgressLabel = "",
    string? ProgressUpdatedUtc = null,
    string? LlmGateway = null,
    string? LlmRequestId = null,
    string? LlmModel = null,
    string? LlmCostJson = null);
