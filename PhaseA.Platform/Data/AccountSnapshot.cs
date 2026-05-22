namespace PhaseA.Platform.Data;

public sealed record AccountSnapshot(
    string AccountId,
    string Username,
    bool IsAdmin,
    bool IsDisabled);
