namespace PhaseA.Platform.Readback;

public sealed record ProjectPackageListResult(
    string ProjectId,
    bool CanCreatePackage,
    string? DisabledReason,
    IReadOnlyList<ProjectPackageListItem> Packages);
