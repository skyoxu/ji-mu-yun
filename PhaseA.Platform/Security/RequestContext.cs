namespace PhaseA.Platform.Security;

public sealed record RequestContext
{
    private static readonly AsyncLocal<RequestContext?> CurrentSlot = new();
    internal static RequestContext? Current => CurrentSlot.Value;
    internal string? TicketProjectId { get; init; }
    internal long? TicketAuthorityRevision { get; init; }
    internal bool IsStartupMaintenance { get; init; }

    // ADR-0061 AD17/19: transport only. Every consumer revalidates central facts;
    // constructing or copying a context (including this scope) grants no authority.
    public static IDisposable UseCurrent(RequestContext context)
    {
        ArgumentNullException.ThrowIfNull(context);
        var prior=CurrentSlot.Value;CurrentSlot.Value=context;return new ContextScope(prior);
    }

    private sealed class ContextScope(RequestContext? prior) : IDisposable
    {
        private bool _disposed;
        public void Dispose(){if(_disposed)return;_disposed=true;CurrentSlot.Value=prior;}
    }
    public RequestContext(string principalId, string accountId, IReadOnlySet<string> roles, string credentialId, string correlationId)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(principalId);
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(credentialId);
        ArgumentException.ThrowIfNullOrWhiteSpace(correlationId);
        if (roles is null || roles.Count == 0) throw new ArgumentException("at least one role is required", nameof(roles));
        PrincipalId = principalId; AccountId = accountId; Roles = roles; CredentialId = credentialId; CorrelationId = correlationId;
    }

    public string PrincipalId { get; init; }
    public string AccountId { get; init; }
    public IReadOnlySet<string> Roles { get; init; }
    public string CredentialId { get; init; }
    public string CorrelationId { get; init; }

    public bool IsAdmin => Roles.Contains(PhaseAAuth.AdminRole);

    public RequestContext ForBackground(string correlationId) => this with { CorrelationId = correlationId };

    public RequestContext ForRunner(string projectId, string correlationId)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        return this with { CorrelationId = correlationId };
    }

    public void DemandAccount(string accountId)
    {
        if (!IsAdmin && !StringComparer.Ordinal.Equals(AccountId, accountId))
            throw new UnauthorizedAccessException("account ownership mismatch");
    }

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
