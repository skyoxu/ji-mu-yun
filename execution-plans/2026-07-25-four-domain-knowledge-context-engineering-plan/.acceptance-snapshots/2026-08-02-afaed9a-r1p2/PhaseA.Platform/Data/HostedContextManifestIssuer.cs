using PhaseA.Platform.Llm;

namespace PhaseA.Platform.Data;

public sealed record HostedContextManifestIssue(
    string AccountId,
    string ProjectId,
    string OperationKey,
    string SnapshotId,
    string PolicyRevision,
    TimeSpan Lifetime,
    string ExecutionPrompt,
    string? RunId = null,
    string Sandbox = "read-only",
    IReadOnlyList<string>? AllowedWritePaths = null,
    IReadOnlyList<string>? OutputTargets = null);

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
        ArgumentException.ThrowIfNullOrWhiteSpace(issue.ExecutionPrompt);
        if (issue.Lifetime <= TimeSpan.Zero || issue.Lifetime > MaximumLifetime)
        {
            throw new ArgumentOutOfRangeException(nameof(issue), "Hosted Context manifest lifetime must be greater than zero and no more than 15 minutes.");
        }

        var created = _timeProvider.GetUtcNow();
        var project = await _metadataStore.GetProjectSnapshotAsync(issue.ProjectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, issue.AccountId, StringComparison.Ordinal))
        {
            throw new InvalidOperationException("Hosted Context project authority is unavailable.");
        }
        var manifestId = Guid.NewGuid().ToString("N");
        var nonce = Guid.NewGuid().ToString("N");
        var issuedAtUtc = created.UtcDateTime.ToString("yyyy-MM-dd'T'HH:mm:ss'Z'");
        var expiresAtUtc = created.Add(issue.Lifetime).UtcDateTime.ToString("yyyy-MM-dd'T'HH:mm:ss'Z'");
        var payload = HostedContextSignedPayloadV1.CreateServerDerived(
            manifestId,
            project,
            issue.OperationKey,
            issue.SnapshotId,
            issue.PolicyRevision,
            nonce,
            issuedAtUtc,
            expiresAtUtc,
            issue.ExecutionPrompt,
            persistedPrompt: null,
            requestedRunId: issue.RunId,
            sandbox: issue.Sandbox,
            allowedWritePaths: issue.AllowedWritePaths,
            outputTargets: issue.OutputTargets);
        var record = _signatureService.Sign(HostedContextManifestRecord.FromPayload(payload));
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
            CreatedUtc: record.CreatedUtc,
            SchemaVersion: record.SchemaVersion,
            SignedPayloadSha256: record.SignedPayloadSha256);
    }
}
