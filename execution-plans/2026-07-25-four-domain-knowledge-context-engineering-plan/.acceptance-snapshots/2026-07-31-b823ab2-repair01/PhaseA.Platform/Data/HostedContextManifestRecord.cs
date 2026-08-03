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
    string CreatedUtc);
