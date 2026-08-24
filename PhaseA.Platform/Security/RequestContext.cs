namespace PhaseA.Platform.Security;

public sealed record RequestContext(
    string PrincipalId,
    string AccountId,
    IReadOnlySet<string> Roles,
    string CredentialId,
    string CorrelationId)
{
    public bool IsAdmin => Roles.Contains(PhaseAAuth.AdminRole);

    public static RequestContext FromIdentity(
        AccountIdentity identity,
        string principalId,
        string credentialId,
        string correlationId)
    {
        ArgumentNullException.ThrowIfNull(identity);
        return new RequestContext(
            principalId,
            identity.AccountId,
            new HashSet<string>(StringComparer.Ordinal) { identity.Role },
            credentialId,
            correlationId);
    }
}
