using PhaseA.Platform.Data;

namespace PhaseA.Platform.Readback;

public sealed record RunReadbackItem(
    string RunId,
    string ProjectId,
    string? WorkspaceId,
    string RunType,
    string Status,
    int? ExitCode,
    string? StdoutText,
    string? StderrText,
    string? EvidenceJson,
    string ProgressStep,
    string ProgressSubstep,
    string ProgressLabel,
    string? ProgressUpdatedUtc,
    string? LlmGateway,
    string? LlmRequestId,
    string? LlmModel,
    string? LlmCostJson,
    IReadOnlyList<ArtifactSnapshot> Artifacts)
{
    public static RunReadbackItem FromSnapshot(RunSnapshot run, IReadOnlyList<ArtifactSnapshot> artifacts)
    {
        return new RunReadbackItem(
            run.RunId,
            run.ProjectId,
            run.WorkspaceId,
            run.RunType,
            run.Status,
            run.ExitCode,
            run.StdoutText,
            run.StderrText,
            run.EvidenceJson,
            run.ProgressStep,
            run.ProgressSubstep,
            run.ProgressLabel,
            run.ProgressUpdatedUtc,
            run.LlmGateway,
            run.LlmRequestId,
            run.LlmModel,
            run.LlmCostJson,
            artifacts);
    }
}
