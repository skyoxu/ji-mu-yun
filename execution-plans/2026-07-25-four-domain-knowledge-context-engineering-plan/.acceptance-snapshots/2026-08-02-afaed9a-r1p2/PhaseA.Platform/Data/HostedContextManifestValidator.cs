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

    public async Task<bool> ValidateAndConsumeAsync(
        HostedContextEnvelope envelope,
        string operationKey,
        CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(envelope.ManifestId) ||
            envelope.SchemaVersion != HostedContextSignedPayloadV1.Schema ||
            string.IsNullOrWhiteSpace(envelope.SignedPayloadSha256))
        {
            return false;
        }
        var record = await _metadataStore.GetHostedContextManifestAsync(envelope.ManifestId, cancellationToken);
        if (record is null || record.SchemaVersion != HostedContextSignedPayloadV1.Schema ||
            !string.Equals(record.OperationKey, operationKey, StringComparison.Ordinal) ||
            !string.Equals(record.Signature, envelope.Signature, StringComparison.Ordinal) ||
            !string.Equals(record.KeyId, envelope.SignatureKeyId, StringComparison.Ordinal) ||
            !string.Equals(record.SignedPayloadSha256, envelope.SignedPayloadSha256, StringComparison.Ordinal) ||
            (!string.IsNullOrWhiteSpace(envelope.AccountId) && !string.Equals(record.AccountId, envelope.AccountId, StringComparison.Ordinal)) ||
            (!string.IsNullOrWhiteSpace(envelope.ProjectId) && !string.Equals(record.ProjectId, envelope.ProjectId, StringComparison.Ordinal)) ||
            (!string.IsNullOrWhiteSpace(envelope.OperationKey) && !string.Equals(record.OperationKey, envelope.OperationKey, StringComparison.Ordinal)))
        {
            return false;
        }
        HostedContextSignedPayloadV1 payload;
        try
        {
            payload = HostedContextSignedPayloadV1.Parse(record.SignedPayloadJson ?? string.Empty);
        }
        catch (ArgumentException)
        {
            return false;
        }
        var now = DateTimeOffset.UtcNow;
        if (!DateTimeOffset.TryParse(payload.NotBeforeUtc, out var notBefore) ||
            !DateTimeOffset.TryParse(payload.ExpiresAtUtc, out var expires) ||
            now < notBefore || now >= expires)
        {
            return false;
        }
        return _signatureService.Verify(record) &&
            await _metadataStore.ValidateAndConsumeHostedContextAsync(record, cancellationToken);
    }
}
