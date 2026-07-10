using FluentAssertions;
using PhaseA.Platform.Workflow;
using Xunit;

namespace PhaseA.Platform.Tests.Workflow;

public sealed class RouteReadbackPathPolicyTests
{
    [Theory]
    [InlineData("meta/routes/gdd-requirements/latest.json")]
    [InlineData("routes/prototype-contract/latest.json")]
    [InlineData("project-package.zip")]
    public void IsBrowserSafePath_AllowsProjectRelativePaths(string value)
    {
        RouteReadbackPathPolicy.IsBrowserSafePath(value).Should().BeTrue();
    }

    [Theory]
    [InlineData(@"C:\jimuyun\logs\phase-a-innernet\workspaces\p\repo\secret.txt")]
    [InlineData("/var/phasea/workspaces/p/repo/secret.txt")]
    [InlineData("../outside.txt")]
    [InlineData("file:///C:/secret.txt")]
    [InlineData("https://example.invalid/package.zip")]
    public void IsBrowserSafePath_RejectsHostOrExternalPaths(string value)
    {
        RouteReadbackPathPolicy.IsBrowserSafePath(value).Should().BeFalse();
    }

    [Theory]
    [InlineData(@"C:\jimuyun\logs\phase-a-innernet\workspaces\p\repo\secret.txt", "secret.txt")]
    [InlineData("../outside.txt", "outside.txt")]
    public void ToBrowserSafePath_RedactsToFileName(string value, string expected)
    {
        RouteReadbackPathPolicy.ToBrowserSafePath(value).Should().Be(expected);
    }

    [Theory]
    [InlineData("prototype-package.zip", true)]
    [InlineData("nested/prototype-package.zip", false)]
    [InlineData(@"C:\tmp\prototype-package.zip", false)]
    [InlineData("prototype-package.exe", false)]
    public void IsSafePackageFileName_BlocksAbsoluteOrNestedPackageInputs(string value, bool expected)
    {
        RouteReadbackPathPolicy.IsSafePackageFileName(value).Should().Be(expected);
    }
}
