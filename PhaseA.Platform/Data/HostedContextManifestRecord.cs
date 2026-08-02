namespace PhaseA.Platform.Data;

public sealed record HostedContextManifestRecord(
    string ManifestId,
    string AccountId,
    string ProjectId,
    string OperationKey,
    string SnapshotId,
    string PolicyRevision,
    string KeyId,
    string Signature,
    string Nonce,
    string ExpiresUtc,
    string CreatedUtc,
    string SchemaVersion = "jimuyun.hosted-context-manifest-record.v0",
    string? SignedPayloadJson = null,
    string? SignedPayloadSha256 = null)
{
    public static HostedContextManifestRecord FromPayload(HostedContextSignedPayloadV1 payload) => new(
        payload.ManifestId,
        payload.AccountId,
        payload.ProjectId,
        payload.Operation,
        payload.ProjectSnapshotId,
        payload.RoutePolicyRevision,
        string.Empty,
        string.Empty,
        payload.Nonce,
        payload.ExpiresAtUtc,
        payload.IssuedAtUtc,
        HostedContextSignedPayloadV1.Schema,
        payload.CanonicalJson,
        HostedContextSignedPayloadV1.Sha256(payload.CanonicalJson));
}
