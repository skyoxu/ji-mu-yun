using System.Collections.Concurrent;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;

namespace PhaseA.Platform.Readback;

public sealed record ProjectPackageRestoreRequest(string OperationKey);
public sealed record ProjectPackageRestoreAdmission(string? OperationId, string? FailureCode = null);

// ADR-0035/0038/0061: server-bound version, project lock, immutable generation,
// atomic active pointer, additive history, and explicit post-restore validation.
public sealed class ProjectPackageRestoreService(
    PhaseAMetadataStore store, PhaseAPlatformOptions options, ProjectPackageService packages,
    WorkspaceStorageService storage, RestoreService restores, HeavyRunnerQueueService queue,
    RunCancellationService cancellation, ILogger<ProjectPackageRestoreService> logger)
{
    private readonly ConcurrentDictionary<string, SemaphoreSlim> _admissions = new(StringComparer.Ordinal);

    public async Task<ProjectPackageRestoreAdmission> AdmitAsync(RequestContext context, string projectId,
        string fileName, string operationKey, CancellationToken token = default)
    {
        if (string.IsNullOrWhiteSpace(operationKey) || operationKey.Length > 128)
            return new(null, "operation_key_required");
        var gate = _admissions.GetOrAdd(projectId, _ => new SemaphoreSlim(1, 1));
        await gate.WaitAsync(token);
        try
        {
            var project = await store.GetProjectSnapshotAsync(projectId, token);
            if (project is null || project.AccountId != context.AccountId) return new(null, "project_not_found");
            var binding = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(fileName))).ToLowerInvariant();
            var runType = $"project-package-restore:{binding}:{operationKey.Trim()}";
            // ADR-0061: a replay reads the durable operation even if its version
            // was later removed from the snapshot catalog.
            var existing = (await store.ListRunsForProjectAsync(projectId, token)).FirstOrDefault(run => run.RunType == runType);
            if (existing is not null) return new(existing.RunId);
            var catalog = await packages.ListPackagesAsync(context.AccountId, projectId, token);
            var package = catalog?.Packages.FirstOrDefault(item => item.FileName == fileName);
            if (package is null) return new(null, "package_not_found");
            if (package.SnapshotId is null || !storage.ListSnapshots(context.AccountId, projectId)
                .Any(item => item.Manifest.SnapshotId == package.SnapshotId && item.Manifest.WorkspaceId == project.WorkspaceId))
                return new(null, "package_snapshot_unavailable");
            if (project.BootstrapStatus == "running" || await store.HasActiveRunAsync(projectId, token))
                return new(null, "project_busy");
            if (!RunnerIsolationPolicy.TryGetWorkspaceDescriptor(project.WorkspaceRootPath, out var descriptor) ||
                descriptor.AccountId != context.AccountId || descriptor.ProjectId != projectId)
                return new(null, "workspace_isolation_unavailable");
            var run = await store.GetOrCreateProjectOperationRunAsync(projectId, project.WorkspaceId, runType, token);
            if (!await store.TryAcquireRunnerLockAsync(projectId, run.RunId, token))
            {
                if (await store.GetRunnerLockOwnerAsync(projectId, token) == run.RunId)
                    return new(run.RunId);
                await store.CompleteRunAsync(run.RunId, "blocked", 423, "", "Project is busy.", "{}", CancellationToken.None);
                return new(null, "project_busy");
            }
            _ = Task.Run(() => ExecuteAsync(context.ForBackground(run.RunId), project, package, run.RunId));
            return new(run.RunId);
        }
        finally { gate.Release(); }
    }

    private async Task ExecuteAsync(RequestContext context, ProjectSnapshot admittedProject,
        ProjectPackageListItem package, string runId)
    {
        using var cancel = cancellation.CreateLinkedTokenSource(runId, CancellationToken.None);
        try
        {
            await using var slot = await queue.EnterAsync(runId, context.AccountId,
                admittedProject.ProjectId, "project-package-restore", cancel.Token);
            if (!await store.TryMarkRunStartedAsync(runId, slot.QueuePositionAtStart, cancel.Token)) return;
            await store.UpdateRunProgressAsync(runId, "workspace", "restore", "Restoring the selected package version.", cancel.Token);
            var project = await store.GetProjectSnapshotAsync(admittedProject.ProjectId, cancel.Token);
            if (project is null || project.AccountId != context.AccountId || project.RepoPath != admittedProject.RepoPath)
                throw new UnauthorizedAccessException("Project restore authority changed.");
            if (!WorkspacePathPolicy.IsUnderRoot(options.HostedWorkspaceRoot, project.WorkspaceRootPath))
                throw new UnauthorizedAccessException("Workspace is outside the host boundary.");
            var snapshot = storage.ListSnapshots(context.AccountId, project.ProjectId)
                .SingleOrDefault(item => item.Manifest.SnapshotId == package.SnapshotId && item.Manifest.WorkspaceId == project.WorkspaceId)
                ?? throw new InvalidDataException("Package snapshot is unavailable.");
            var download = await packages.ReadPackageAsync(context.AccountId, project.ProjectId, package.FileName, cancel.Token)
                ?? throw new InvalidDataException("Package is unavailable.");
            if (Convert.ToHexString(SHA256.HashData(download.Content)).ToLowerInvariant() != package.PackageSha256)
                throw new InvalidDataException("Package integrity check failed.");
            bool Reauthorize() => !cancel.IsCancellationRequested &&
                store.ResolveAccountByTokenHashAsync(context.CredentialId, cancel.Token).GetAwaiter().GetResult()?.AccountId == context.AccountId;
            var lease = restores.GetAuthoritativeLease(context.AccountId, project.ProjectId)
                ?? throw new InvalidOperationException("Restore lease is unavailable.");
            if (lease.LeaseId != runId) throw new UnauthorizedAccessException("Restore lease changed.");
            var storageRoot = WorkspaceGenerationPaths.StorageRoot(project);
            var restored = restores.RestoreProjectVersion(context, snapshot.Manifest, project.WorkspaceRootPath,
                storageRoot, lease, $"package-restore:{runId}", Reauthorize);
            if (restored.Status != RestoreAttemptStatus.Published)
            {
                await store.CompleteRunAsync(runId, "failed", 409, "", "Snapshot did not publish.",
                    JsonSerializer.Serialize(new { code = "package_restore_failed", category = restored.FailureCategory }), CancellationToken.None);
                return;
            }
            cancel.Token.ThrowIfCancellationRequested();
            if (!Reauthorize()) throw new UnauthorizedAccessException("Restore credential changed.");
            var generation = RunnerIsolationPolicy.RequireContainedPath(storageRoot,
                $".restore-generations/{restored.AttemptId}");
            var published = RunnerIsolationPolicy.RequireContainedPath(storageRoot, ".restore-current");
            Directory.CreateDirectory(Path.GetDirectoryName(generation)!);
            Directory.Move(published, generation);
            foreach (var directory in new[] { "repo", "runtime", "meta" })
                Directory.CreateDirectory(Path.Combine(generation, directory));
            if (!RunnerIsolationPolicy.TryGetWorkspaceDescriptor(project.WorkspaceRootPath, out var descriptor))
                throw new UnauthorizedAccessException("Workspace registration changed.");
            RunnerIsolationPolicy.PrepareRestoreTree(descriptor, generation);
            if (!RunnerIsolationPolicy.HasExpectedRestoreTreeSecurity(descriptor, generation))
                throw new UnauthorizedAccessException("Restored generation ACL check failed.");
            // A crash before this transaction leaves the prior active paths intact.
            // The success receipt commits with the new paths, not after them.
            await store.ActivateWorkspaceGenerationAsync(project, runId, snapshot.Manifest.SnapshotId,
                restored.AttemptId, generation, context.CredentialId, cancel.Token);
        }
        catch (OperationCanceledException)
        {
            await store.CompleteRunAsync(runId, "cancel", 499, "", "Project version restore cancelled.", "{}", CancellationToken.None);
        }
        catch (Exception error)
        {
            logger.LogError(error, "Package restore failed for run {RunId}.", runId);
            await store.CompleteRunAsync(runId, "failed", 500, "", "Project version restore failed.",
                JsonSerializer.Serialize(new { code = "package_restore_failed" }), CancellationToken.None);
        }
        finally
        {
            cancellation.Unregister(runId);
            await store.ReleaseRunnerLockAsync(admittedProject.ProjectId, runId, CancellationToken.None);
        }
    }
}
