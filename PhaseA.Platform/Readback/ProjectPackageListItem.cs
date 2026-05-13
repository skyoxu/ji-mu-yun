namespace PhaseA.Platform.Readback;

public sealed record ProjectPackageListItem(
    string Version,
    string FileName,
    string RelativePath,
    string DownloadUrl,
    long SizeBytes,
    string CreatedUtc);
