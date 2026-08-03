using PhaseA.Platform.Llm;

namespace PhaseA.Platform.Data;

public sealed record HostedContextManifestIssue(
    string AccountId,
    string ProjectId,
    string OperationKey,
    string SnapshotId,
    string PolicyRevision,
    TimeSpan Lifetime);

public sealed class HostedContextManifestIssuer
{
    private static readonly TimeSpan MaximumLifetime = TimeSpan.FromMinutes(15);
    private readonly PhaseAMetadataStore _metadataStore;
    private readonly HostedContextManifestSignatureService _signatureService;
    private readonly TimeProvider _timeProvider;

    public HostedContextManifestIssuer(
        PhaseAMetadataStore metadataStore,
        HostedContextManifestSignatureService signatureService,
        TimeProvider? timeProvider = null)
    {
        _metadataStore = metadataStore;
        _signatureService = signatureService;
        _timeProvider = timeProvider ?? TimeProvider.System;
    }

    public async Task<HostedContextEnvelope> IssueAsync(
        HostedContextManifestIssue issue,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(issue.AccountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(issue.ProjectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(issue.OperationKey);
        ArgumentException.ThrowIfNullOrWhiteSpace(issue.SnapshotId);
        ArgumentException.ThrowIfNullOrWhiteSpace(issue.PolicyRevision);
        if (issue.Lifetime <= TimeSpan.Zero || issue.Lifetime > MaximumLifetime)
        {
            throw new ArgumentOutOfRangeException(nameof(issue), "Hosted Context manifest lifetime must be greater than zero and no more than 15 minutes.");
        }

        var created = _timeProvider.GetUtcNow();
        var record = _signatureService.Sign(new HostedContextManifestRecord(
            Guid.NewGuid().ToString("N"),
            issue.AccountId,
            issue.ProjectId,
            issue.OperationKey,
            issue.SnapshotId,
            issue.PolicyRevision,
            string.Empty,
            string.Empty,
            Guid.NewGuid().ToString("N"),
            created.Add(issue.Lifetime).ToString("O"),
            created.ToString("O")));
        if (!await _metadataStore.SaveHostedContextManifestAsync(record, cancellationToken))
        {
            throw new InvalidOperationException("Hosted Context manifest ID collision.");
        }

        return new HostedContextEnvelope(
            record.ManifestId,
            record.SnapshotId,
            record.PolicyRevision,
            record.Signature,
            SignatureKeyId: record.KeyId,
            AccountId: record.AccountId,
            ProjectId: record.ProjectId,
            OperationKey: record.OperationKey,
            Nonce: record.Nonce,
            ExpiresUtc: record.ExpiresUtc,
            CreatedUtc: record.CreatedUtc);
    }
}
