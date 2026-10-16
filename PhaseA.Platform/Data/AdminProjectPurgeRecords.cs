namespace PhaseA.Platform.Data;

public sealed record AdminProjectSummary(
    string ProjectId,
    string AccountId,
    string? Username,
    string Name,
    string GameName,
    string BootstrapStatus,
    string CreatedUtc,
    bool SoftDeleted);

public sealed record AdminProjectPurgeRequest(
    IReadOnlyList<string> ProjectIds,
    string Confirm);

public sealed record AdminProjectPurgeItem(
    string ProjectId,
    bool Succeeded,
    string? FailureCode = null,
    bool DatabasePurged = false,
    bool WorkspacePurged = false);

public sealed record AdminProjectPurgeResult(
    string Status,
    IReadOnlyList<AdminProjectPurgeItem> Items,
    int RequestedCount,
    int PurgedCount,
    int FailedCount);

public sealed record ProjectPurgeTarget(
    string ProjectId,
    string AccountId,
    string WorkspaceRootPath);
