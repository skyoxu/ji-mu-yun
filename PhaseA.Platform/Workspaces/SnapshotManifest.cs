using System.Collections.Immutable;
using System.Security.Cryptography;

namespace PhaseA.Platform.Workspaces;

public sealed record SnapshotFileEntry(string RelativePath, long Length, string Sha256);

public sealed record SnapshotManifest(
    string SnapshotId,
    string WorkspaceId,
    string AccountId,
    string ProjectId,
    string PolicyVersion,
    ImmutableArray<SnapshotFileEntry> Files)
{
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
            .Select(item =>
            {
                var normalized = item.RelativePath.Replace('\\', '/');
                if (Path.IsPathRooted(normalized) || normalized.Split('/').Contains("..", StringComparer.Ordinal))
                    throw new InvalidDataException("snapshot path is unsafe");
                return (normalized, item.Content);
            })
            .Where(item => !excludedExtensions.Contains(Path.GetExtension(item.normalized)))
            .Select(item => new SnapshotFileEntry(
                item.normalized,
                item.Content.LongLength,
                Convert.ToHexString(SHA256.HashData(item.Content)).ToLowerInvariant()))
            .OrderBy(item => item.RelativePath, StringComparer.Ordinal)
            .ToImmutableArray();

        return new SnapshotManifest(snapshotId, workspaceId, accountId, projectId, policyVersion, entries);
    }
}
