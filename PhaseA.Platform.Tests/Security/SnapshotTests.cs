using FluentAssertions;
using PhaseA.Platform.Workspaces;
using Xunit;

namespace PhaseA.Platform.Tests.PhaseB;

public sealed class SnapshotTests
{
    [Fact]
    public void Create_ProducesImmutableAccountOwnedManifestAndAppliesBlacklist()
    {
        var manifest = SnapshotManifest.Create(
            "snapshot-1", "workspace-1", "account-1", "project-1", "policy-v1",
            [("project.godot", "content"u8.ToArray()), ("art.jpg", [1, 2, 3])],
            new HashSet<string>(StringComparer.OrdinalIgnoreCase) { ".jpg" });

        manifest.WorkspaceId.Should().Be("workspace-1");
        manifest.AccountId.Should().Be("account-1");
        manifest.ProjectId.Should().Be("project-1");
        manifest.PolicyVersion.Should().Be("policy-v1");
        manifest.Files.Should().ContainSingle().Which.RelativePath.Should().Be("project.godot");
    }
}
