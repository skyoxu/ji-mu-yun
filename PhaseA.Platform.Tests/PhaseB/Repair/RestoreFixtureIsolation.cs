using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

internal static class RestoreFixtureIsolation
{
    // ADR-0061: ordinary restore fixtures prepare the same boundary as the API.
    // Security-negative tests call Restore directly and deliberately omit or corrupt it.
    public static RestoreAttempt RestorePrepared(this RestoreService service, RequestContext context,
        SnapshotManifest manifest, string source, string destination, RunnerLease lease, string? key = null,
        RunnerIsolationDescriptor? descriptor = null)
    {
        if (!RunnerIsolationPolicy.TryGetWorkspaceDescriptor(destination, out _))
        {
            using var isolation = RunnerIsolationPolicy.PrepareWorkspace(descriptor ?? new RunnerIsolationDescriptor(
                manifest.AccountId, manifest.ProjectId, "phase-r-a-p", destination, true,
                OperatingSystem.IsWindows(), OperatingSystem.IsWindows()));
        }
        return key is null ? service.Restore(context, manifest, source, destination, lease)
            : service.Restore(context, manifest, source, destination, lease, key);
    }
}
