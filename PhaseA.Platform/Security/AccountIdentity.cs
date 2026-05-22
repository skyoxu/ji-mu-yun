namespace PhaseA.Platform.Security;

public sealed record AccountIdentity(
    string AccountId,
    string Username,
    string Role)
{
    public bool IsAdmin => string.Equals(Role, PhaseAAuth.AdminRole, StringComparison.Ordinal);
}
