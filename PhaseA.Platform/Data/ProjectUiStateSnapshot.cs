namespace PhaseA.Platform.Data;

public sealed record ProjectUiStateSnapshot(
    string AccountId,
    string ProjectId,
    string StateJson,
    string UpdatedUtc);
