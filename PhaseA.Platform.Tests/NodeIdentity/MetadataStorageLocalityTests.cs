using PhaseA.Platform.Configuration;
using Xunit;

namespace PhaseA.Platform.Tests.NodeIdentity;

// ADR-0033/0061: lexical parser regressions only. These paths are never opened,
// enumerated or connected to. This is not a native workflow RED/admission receipt.
public sealed class MetadataStorageLocalityTests
{
    [Theory]
    [InlineData(@"\\s164-lexical.invalid\share\metadata.sqlite3")]
    [InlineData(@"\\?\UNC\s164-lexical.invalid\share\metadata.sqlite3")]
    public void NetworkMetadataNamespacesAreRejectedBeforeStorageAccess(string path)
    {
        Assert.True(OperatingSystem.IsWindows(), "Real Windows parser observation is required.");
        Assert.Throws<PhaseAPlatformConfigException>(() => LoadAndValidate(path));
    }

    [Theory]
    [InlineData(@"C:\s164-lexical-only\metadata.sqlite3")]
    [InlineData(@"\\?\C:\s164-lexical-only\metadata.sqlite3")]
    public void LocalDriveMetadataPathsRemainAccepted(string path)
    {
        Assert.True(OperatingSystem.IsWindows(), "Real Windows parser observation is required.");
        var options = LoadAndValidate(path);
        Assert.Equal(Path.GetFullPath(path), options.MetadataDatabasePath);
    }

    private static PhaseAPlatformOptions LoadAndValidate(string path)
    {
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_METADATA_DB_PATH"] = path,
            ["HOSTED_WORKSPACE_ROOT"] = @"C:\s164-lexical-only\workspaces",
            ["PHASEA_SERVICE_STATE"] = "test",
            ["PHASEA_NODE_ID"] = "s164-lexical-only",
            ["PHASEA_NODE_SCOPE"] = "single_node_test",
            ["PHASEA_NODE_TOPOLOGY"] = "single_service",
            ["PHASEA_ENABLED_ROLES"] = "entry,production",
            ["PHASEA_ACCEPT_NEW_ACCOUNTS"] = "false"
        });
        options.ValidateServiceIdentity();
        return options;
    }
}
