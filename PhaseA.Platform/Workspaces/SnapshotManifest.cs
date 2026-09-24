using System.Collections.Immutable;
using System.Security.Cryptography;
using System.Text;

namespace PhaseA.Platform.Workspaces;

public sealed record SnapshotFileEntry(string RelativePath, long Length, string Sha256);

// Snapshot metadata is additive under Accepted ADR-0061.
public sealed record SnapshotManifest(
    string SnapshotId,
    string WorkspaceId,
    string AccountId,
    string ProjectId,
    string PolicyVersion,
    string SchemaVersion,
    string PlatformCompatibilityVersion,
    string StorageCompatibilityVersion,
    string KeyReference,
    string Creator,
    string CreationAction,
    DateTimeOffset CreatedAt,
    string Retention,
    ImmutableArray<string> ContentExclusions,
    long ContentSize,
    string OwnershipPolicyReference,
    string AclPolicyReference,
    string RecoveryConditions,
    string RecoveryPrerequisites,
    string RecoveryRebuildInstructions,
    ImmutableArray<SnapshotFileEntry> Files)
{
    private static readonly byte[] SnapshotProtectionHeader = "S22-AES-256-GCM-V1\0"u8.ToArray();
    private const int SnapshotProtectionNonceLength = 12;
    private const int SnapshotProtectionTagLength = 16;

    // ADR-0061: retain authenticated snapshot content so restore does not depend
    // on the mutable workspace that was captured.
    public byte[]? ProtectedContent { get; init; }

    public static SnapshotManifest Create(
        string snapshotId,
        string workspaceId,
        string accountId,
        string projectId,
        string policyVersion,
        IEnumerable<(string RelativePath, byte[] Content)> files,
        ISet<string>? excludedExtensions = null)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(snapshotId);
        ArgumentException.ThrowIfNullOrWhiteSpace(workspaceId);
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(policyVersion);
        ArgumentNullException.ThrowIfNull(files);
        excludedExtensions ??= new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var materialized = files.ToArray();
        if (materialized.Length > 10_000) throw new InvalidOperationException("snapshot file count exceeds fixture limit");
        var entries = materialized
            .Select(item => (RelativePath: NormalizeRelativePath(item.RelativePath), item.Content))
            .Where(item => !excludedExtensions.Contains(Path.GetExtension(item.RelativePath)))
            .Select(item => new SnapshotFileEntry(
                item.RelativePath,
                item.Content.LongLength,
                Convert.ToHexString(SHA256.HashData(item.Content)).ToLowerInvariant()))
            .OrderBy(item => item.RelativePath, StringComparer.Ordinal)
            .ToImmutableArray();

        var keyReference = CreateKeyReference(policyVersion);
        return new SnapshotManifest(
            snapshotId,
            workspaceId,
            accountId,
            projectId,
            policyVersion,
            "snapshot-manifest/v1",
            "phase-a/v1",
            "workspace-storage/v1",
            keyReference,
            accountId,
            "create-snapshot",
            DateTimeOffset.UtcNow,
            "30-day",
            excludedExtensions.OrderBy(extension => extension, StringComparer.OrdinalIgnoreCase).ToImmutableArray(),
            entries.Sum(entry => entry.Length),
            $"ownership:{policyVersion}",
            $"acl:{policyVersion}",
            "account-and-project-ownership",
            "workspace-root-and-policy",
            "rebuild-derived-cache-and-runtime-state",
            entries);
    }

    internal static byte[] ProtectContent((string RelativePath, byte[] Content)[] files, string keyReference)
    {
        var plaintext = files.SelectMany(file => file.Content).ToArray();
        var nonce = RandomNumberGenerator.GetBytes(SnapshotProtectionNonceLength);
        var ciphertext = new byte[plaintext.Length];
        var tag = new byte[SnapshotProtectionTagLength];
        var key = SHA256.HashData(Encoding.UTF8.GetBytes($"s22-static-profile/{keyReference}"));
        using var aes = new AesGcm(key, SnapshotProtectionTagLength);
        aes.Encrypt(nonce, plaintext, ciphertext, tag, Encoding.UTF8.GetBytes(keyReference));

        var protectedContent = new byte[SnapshotProtectionHeader.Length + nonce.Length + ciphertext.Length + tag.Length];
        SnapshotProtectionHeader.CopyTo(protectedContent, 0);
        nonce.CopyTo(protectedContent, SnapshotProtectionHeader.Length);
        ciphertext.CopyTo(protectedContent, SnapshotProtectionHeader.Length + nonce.Length);
        tag.CopyTo(protectedContent, SnapshotProtectionHeader.Length + nonce.Length + ciphertext.Length);
        return protectedContent;
    }

    internal IReadOnlyDictionary<string, byte[]> ReadProtectedContent()
    {
        var protectedContent = ProtectedContent
            ?? throw new InvalidDataException("snapshot content is unavailable");
        var minimumLength = SnapshotProtectionHeader.Length + SnapshotProtectionNonceLength + SnapshotProtectionTagLength;
        if (protectedContent.Length < minimumLength ||
            !protectedContent.AsSpan(0, SnapshotProtectionHeader.Length).SequenceEqual(SnapshotProtectionHeader))
            throw new InvalidDataException("snapshot content is invalid");

        var nonceOffset = SnapshotProtectionHeader.Length;
        var ciphertextOffset = nonceOffset + SnapshotProtectionNonceLength;
        var ciphertextLength = protectedContent.Length - ciphertextOffset - SnapshotProtectionTagLength;
        var plaintext = new byte[ciphertextLength];
        var key = SHA256.HashData(Encoding.UTF8.GetBytes($"s22-static-profile/{KeyReference}"));
        using (var aes = new AesGcm(key, SnapshotProtectionTagLength))
        {
            aes.Decrypt(
                protectedContent.AsSpan(nonceOffset, SnapshotProtectionNonceLength),
                protectedContent.AsSpan(ciphertextOffset, ciphertextLength),
                protectedContent.AsSpan(ciphertextOffset + ciphertextLength, SnapshotProtectionTagLength),
                plaintext,
                Encoding.UTF8.GetBytes(KeyReference));
        }

        var offset = 0;
        var files = new Dictionary<string, byte[]>(StringComparer.Ordinal);
        foreach (var entry in Files)
        {
            if (entry.Length < 0 || entry.Length > plaintext.Length - offset)
                throw new InvalidDataException("snapshot content length is invalid");
            var length = checked((int)entry.Length);
            files.Add(entry.RelativePath, plaintext.AsSpan(offset, length).ToArray());
            offset += length;
        }

        if (offset != plaintext.Length)
            throw new InvalidDataException("snapshot content length is invalid");
        return files;
    }

    private static string NormalizeRelativePath(string relativePath)
    {
        var normalized = relativePath.Replace('\\', '/');
        if (Path.IsPathRooted(normalized) || normalized.Split('/').Contains("..", StringComparer.Ordinal))
            throw new InvalidDataException("snapshot path is unsafe");

        return normalized;
    }

    private static string CreateKeyReference(string policyVersion)
    {
        var policyIdentifier = policyVersion.StartsWith("policy-", StringComparison.Ordinal)
            ? policyVersion["policy-".Length..]
            : policyVersion;
        return $"keyref-{policyIdentifier}-approved";
    }
}
