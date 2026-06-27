namespace PhaseA.Platform.Readback;

public sealed record ProjectPackageListItem(
    string Version,
    string FileName,
    string RelativePath,
    string DownloadUrl,
    long SizeBytes,
    string PackageSha256,
    string CreatedUtc,
    ProjectWebPreviewPackageStatus WebPreview);
