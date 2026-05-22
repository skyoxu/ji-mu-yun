namespace PhaseA.Platform.Data;

public sealed record AdminRotateUserTokenResult(
    string AccountId,
    string Username,
    string Token);
