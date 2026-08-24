using System.Security.Cryptography;
using PhaseA.Platform.Security;

namespace PhaseA.Platform.Workspaces;

public sealed class RestoreService
{
    public RestoreAttempt Restore(RequestContext context, SnapshotManifest manifest, string sourceRoot, string destinationRoot, RunnerLease lease)
    {
        context.DemandAccount(manifest.AccountId);
        var attempt = new RestoreAttempt(Guid.NewGuid().ToString("N"), manifest.SnapshotId, manifest.WorkspaceId, RestoreAttemptStatus.Requested).Advance(RestoreAttemptStatus.Staging);
        var staging = Path.Combine(destinationRoot, ".restore-staging", attempt.AttemptId);
        Directory.CreateDirectory(staging);
        try
        {
            if (string.IsNullOrWhiteSpace(lease.LeaseId) || lease.Fence <= 0) throw new InvalidOperationException("invalid runner lease");
            foreach (var entry in manifest.Files)
            {
                var target = RunnerIsolationPolicy.RequireContainedPath(staging, entry.RelativePath);
                Directory.CreateDirectory(Path.GetDirectoryName(target)!);
                var source = RunnerIsolationPolicy.RequireContainedPath(sourceRoot, entry.RelativePath);
                if (!File.Exists(source) || Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(source))).ToLowerInvariant() != entry.Sha256)
                    throw new InvalidDataException("restore hash mismatch");
                File.Copy(source, target);
            }
            var published = Path.Combine(destinationRoot, ".restore-current");
            if (Directory.Exists(published)) Directory.Delete(published, true);
            Directory.Move(staging, published);
            return attempt.Advance(RestoreAttemptStatus.Published);
        }
        catch
        {
            var quarantine = Path.Combine(destinationRoot, ".restore-quarantine", attempt.AttemptId);
            Directory.CreateDirectory(Path.GetDirectoryName(quarantine)!);
            if (Directory.Exists(quarantine)) Directory.Delete(quarantine, true);
            if (Directory.Exists(staging)) Directory.Move(staging, quarantine);
            return attempt.Advance(RestoreAttemptStatus.Quarantined);
        }
    }
}
