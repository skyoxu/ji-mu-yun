using PhaseA.Platform.Data;

namespace PhaseA.Platform.Readback;

public sealed record ProjectWebPreviewResult(
    string ProjectId,
    string RunId,
    string Status,
    string FileName,
    string PreviewId,
    string PreviewUrl,
    string Mode,
    string CreatedUtc,
    string? FailureCode,
    IReadOnlyList<ArtifactSnapshot> Artifacts);
