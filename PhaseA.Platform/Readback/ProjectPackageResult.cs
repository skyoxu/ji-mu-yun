using PhaseA.Platform.Data;

namespace PhaseA.Platform.Readback;

public sealed record ProjectPackageResult(
    string ProjectId,
    string RunId,
    string Status,
    string Version,
    string FileName,
    string RelativePath,
    string DownloadUrl,
    long SizeBytes,
    int IncludedFileCount,
    IReadOnlyList<ArtifactSnapshot> Artifacts,
    string? FailureCode = null);
