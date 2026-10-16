using PhaseA.Platform.Security;
using Xunit;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S57BoundaryTests : IDisposable
{
    private const string ManagedRunnerIdentity = "phase-r-a-p";
    private readonly string _root = Path.Combine(Path.GetTempPath(), "phase-s57-" + Guid.NewGuid().ToString("N"));
    private readonly string _workspace;
    private readonly RunnerIsolationDescriptor _currentProfile;
    private readonly RunnerIsolationHandle _isolation;

    public S57BoundaryTests()
    {
        Directory.CreateDirectory(_root);
        _workspace = Path.Combine(_root, "account-a", "project-a");
        _currentProfile = new RunnerIsolationDescriptor(
            "account-a",
            "project-a",
            ManagedRunnerIdentity,
            _workspace,
            LowPrivilegeRequired: true,
            JobObjectRequired: true,
            NtfsAclRequired: true);
        _isolation = RunnerIsolationPolicy.PrepareWorkspace(_currentProfile);
    }

    [Fact]
    public void O_8E54C403F37E()
    {
        var unsupportedStrongerTierWorkspace = Path.Combine(_root, "stronger-tier");

        var advertised = RunnerIsolationPolicy.TryGetWorkspaceDescriptor(
            unsupportedStrongerTierWorkspace,
            out var advertisedProfile);

        Require(!advertised && advertisedProfile is null, "FAILURE-O-8E54C403F37E");
    }

    [Fact]
    public void O_0181C140F5DD()
    {
        var currentWasSelected = RunnerIsolationPolicy.TryGetWorkspaceDescriptor(_workspace, out var before);
        var unsupportedStrongerTierWorkspace = Path.Combine(_root, "stronger-tier");
        var selectedUnsupportedTier = RunnerIsolationPolicy.TryGetWorkspaceDescriptor(
            unsupportedStrongerTierWorkspace,
            out _);
        var currentRemainsSelected = RunnerIsolationPolicy.TryGetWorkspaceDescriptor(_workspace, out var after);

        Require(
            currentWasSelected &&
            !selectedUnsupportedTier &&
            currentRemainsSelected &&
            before == _currentProfile &&
            after == _currentProfile,
            "FAILURE-O-0181C140F5DD");
    }

    [Fact]
    public void O_D7E8F1CE9703()
    {
        var projected = RunnerIsolationPolicy.TryGetWorkspaceDescriptor(_workspace, out var profile);
        var evidenceConstrainedCurrentTier =
            projected &&
            profile == _currentProfile &&
            profile.LowPrivilegeRequired &&
            profile.JobObjectRequired &&
            profile.NtfsAclRequired;

        Require(evidenceConstrainedCurrentTier, "FAILURE-O-D7E8F1CE9703");
    }

    private static void Require(bool condition, string failureId)
    {
        if (!condition)
        {
            throw new Xunit.Sdk.XunitException($"{failureId}: Runner isolation capability/profile projection did not preserve the evidence-constrained boundary.");
        }
    }

    public void Dispose()
    {
        _isolation.Dispose();
        try { Directory.Delete(_root, recursive: true); }
        catch (IOException) { }
        catch (UnauthorizedAccessException) { }
    }
}
