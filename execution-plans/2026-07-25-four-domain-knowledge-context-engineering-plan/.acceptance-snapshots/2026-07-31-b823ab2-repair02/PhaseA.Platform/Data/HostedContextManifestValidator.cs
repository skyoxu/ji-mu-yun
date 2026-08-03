using PhaseA.Platform.Llm;

namespace PhaseA.Platform.Data;

public sealed class HostedContextManifestValidator : IHostedContextManifestValidator
{
    private readonly PhaseAMetadataStore _metadataStore;
    private readonly HostedContextManifestSignatureService _signatureService;

    public HostedContextManifestValidator(
        PhaseAMetadataStore metadataStore,
        HostedContextManifestSignatureService signatureService)
    {
        _metadataStore = metadataStore;
        _signatureService = signatureService;
    }

    public Task<bool> ValidateAndConsumeAsync(
        HostedContextEnvelope envelope,
        string operationKey,
        CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(envelope.AccountId) ||
            string.IsNullOrWhiteSpace(envelope.ProjectId) ||
            string.IsNullOrWhiteSpace(envelope.Nonce) ||
            (!string.IsNullOrWhiteSpace(envelope.OperationKey) &&
             !string.Equals(envelope.OperationKey, operationKey, StringComparison.Ordinal)))
        {
            return Task.FromResult(false);
        }

        var record = new HostedContextManifestRecord(
            envelope.ManifestId,
            envelope.AccountId,
            envelope.ProjectId,
            operationKey,
            envelope.SnapshotId,
            envelope.PolicyRevision,
            envelope.SignatureKeyId ?? string.Empty,
            envelope.Signature,
            envelope.Nonce,
            envelope.ExpiresUtc ?? string.Empty,
            envelope.CreatedUtc ?? string.Empty);
        return _signatureService.Verify(record)
            ? _metadataStore.ValidateAndConsumeHostedContextAsync(record, cancellationToken)
            : Task.FromResult(false);
    }
}
