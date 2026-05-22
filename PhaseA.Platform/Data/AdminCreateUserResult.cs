namespace PhaseA.Platform.Data;

public sealed record AdminCreateUserResult(
    string AccountId,
    string Username,
    string Token,
    int ProjectLimit);
