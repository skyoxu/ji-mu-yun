namespace PhaseA.Platform.Data;

public sealed record AdminUserListItem(
    string AccountId,
    string Username,
    bool IsAdmin,
    bool IsDisabled,
    int ProjectLimit,
    int ProjectCount,
    string CreatedUtc);
