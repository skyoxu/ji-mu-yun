using PhaseA.Platform.Data;

namespace PhaseA.Platform.Runs;

public sealed record GameDesignDocumentResult(
    string ProjectId,
    string RunId,
    string Status,
    string RelativePath,
    string DownloadUrl,
    IReadOnlyList<ArtifactSnapshot> Artifacts,
    string? FailureCode = null,
    string? Summary = null);
