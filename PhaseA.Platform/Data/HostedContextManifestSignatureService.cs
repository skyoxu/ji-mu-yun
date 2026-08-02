using System.Security.Cryptography;
using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;

namespace PhaseA.Platform.Data;

public sealed class HostedContextManifestSignatureService
{
    private readonly string _primaryKeyId;
    private readonly IReadOnlyDictionary<string, byte[]> _keys;

    public string PrimaryKeyId => _primaryKeyId;

    public HostedContextManifestSignatureService(string primaryKeyId, IReadOnlyDictionary<string, string> keys)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(primaryKeyId);
        ArgumentNullException.ThrowIfNull(keys);

        _primaryKeyId = primaryKeyId;
        _keys = keys.ToDictionary(
            pair => pair.Key,
            pair => Encoding.UTF8.GetBytes(pair.Value),
            StringComparer.Ordinal);
        if (!_keys.TryGetValue(_primaryKeyId, out var primary) || primary.Length == 0 ||
            _keys.Any(pair => string.IsNullOrWhiteSpace(pair.Key) || pair.Value.Length == 0))
        {
            throw new ArgumentException("Hosted Context signing keys must include a non-empty primary key.", nameof(keys));
        }
    }

    public HostedContextManifestRecord Sign(HostedContextManifestRecord record)
    {
        var unsigned = Normalize(record with { KeyId = _primaryKeyId, Signature = string.Empty });
        return unsigned with { Signature = ComputeBase64(unsigned, _keys[_primaryKeyId]) };
    }

    public bool Verify(HostedContextManifestRecord record)
    {
        if (string.IsNullOrWhiteSpace(record.KeyId) || string.IsNullOrWhiteSpace(record.Signature) ||
            !_keys.TryGetValue(record.KeyId, out var key))
        {
            return false;
        }

        byte[] provided;
        try
        {
            provided = Convert.FromBase64String(record.Signature);
        }
        catch (FormatException)
        {
            return false;
        }

        HostedContextManifestRecord normalized;
        try
        {
            normalized = Normalize(record with { Signature = string.Empty });
        }
        catch (ArgumentException)
        {
            return false;
        }
        if (!string.Equals(normalized.SignedPayloadJson, record.SignedPayloadJson, StringComparison.Ordinal) ||
            !string.Equals(normalized.SignedPayloadSha256, record.SignedPayloadSha256, StringComparison.Ordinal))
        {
            return false;
        }
        var expected = Convert.FromBase64String(ComputeBase64(normalized, key));
        return CryptographicOperations.FixedTimeEquals(provided, expected);
    }

    internal static string Canonicalize(HostedContextManifestRecord record)
    {
        if (record.SchemaVersion == HostedContextSignedPayloadV1.Schema && !string.IsNullOrWhiteSpace(record.SignedPayloadJson))
        {
            return HostedContextSignedPayloadV1.Parse(record.SignedPayloadJson).CanonicalJson;
        }
        using var stream = new MemoryStream();
        using (var writer = new Utf8JsonWriter(stream, new JsonWriterOptions { Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping }))
        {
            writer.WriteStartObject();
            writer.WriteString("account_id", record.AccountId);
            writer.WriteString("created_utc", record.CreatedUtc);
            writer.WriteString("expires_utc", record.ExpiresUtc);
            writer.WriteString("key_id", record.KeyId);
            writer.WriteString("manifest_id", record.ManifestId);
            writer.WriteString("nonce", record.Nonce);
            writer.WriteString("operation_key", record.OperationKey);
            writer.WriteString("policy_revision", record.PolicyRevision);
            writer.WriteString("project_id", record.ProjectId);
            writer.WriteString("schema_version", "jimuyun.hosted-context-manifest-record.v1");
            writer.WriteString("snapshot_id", record.SnapshotId);
            writer.WriteEndObject();
        }

        return Encoding.UTF8.GetString(stream.ToArray());
    }

    private static string ComputeBase64(HostedContextManifestRecord record, byte[] key)
    {
        using var hmac = new HMACSHA256(key);
        return Convert.ToBase64String(hmac.ComputeHash(Encoding.UTF8.GetBytes(Canonicalize(record))));
    }

    private static HostedContextManifestRecord Normalize(HostedContextManifestRecord record)
    {
        if (record.SchemaVersion != HostedContextSignedPayloadV1.Schema)
        {
            return record;
        }
        var payload = HostedContextSignedPayloadV1.Parse(record.SignedPayloadJson ?? string.Empty);
        if (!string.Equals(payload.ManifestId, record.ManifestId, StringComparison.Ordinal) ||
            !string.Equals(payload.AccountId, record.AccountId, StringComparison.Ordinal) ||
            !string.Equals(payload.ProjectId, record.ProjectId, StringComparison.Ordinal) ||
            !string.Equals(payload.Operation, record.OperationKey, StringComparison.Ordinal) ||
            !string.Equals(payload.ProjectSnapshotId, record.SnapshotId, StringComparison.Ordinal) ||
            !string.Equals(payload.RoutePolicyRevision, record.PolicyRevision, StringComparison.Ordinal) ||
            !string.Equals(payload.Nonce, record.Nonce, StringComparison.Ordinal) ||
            !string.Equals(payload.ExpiresAtUtc, record.ExpiresUtc, StringComparison.Ordinal) ||
            !string.Equals(payload.IssuedAtUtc, record.CreatedUtc, StringComparison.Ordinal))
        {
            throw new ArgumentException("Hosted Context indexed fields do not match the signed payload.", nameof(record));
        }
        return record with
        {
            SignedPayloadJson = payload.CanonicalJson,
            SignedPayloadSha256 = HostedContextSignedPayloadV1.Sha256(payload.CanonicalJson)
        };
    }
}
