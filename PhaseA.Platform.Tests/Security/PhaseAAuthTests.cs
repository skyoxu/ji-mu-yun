using FluentAssertions;
using Microsoft.AspNetCore.Http;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Security;
using Xunit;

namespace PhaseA.Platform.Tests.Security;

public sealed class PhaseAAuthTests
{
    [Fact]
    public void IsAuthorized_ReturnsFalse_WhenAdminSecretIsNotConfigured()
    {
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());
        var context = new DefaultHttpContext();

        var authorized = PhaseAAuth.IsAuthorized(context.Request, options);

        authorized.Should().BeFalse();
    }

    [Fact]
    public void IsAuthorized_AcceptsBearerToken_WhenItMatchesConfiguredAdminTokenHash()
    {
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_ADMIN_TOKEN_HASH"] = "local-admin-token"
        });
        var context = new DefaultHttpContext();
        context.Request.Headers.Authorization = "Bearer local-admin-token";

        var authorized = PhaseAAuth.IsAuthorized(context.Request, options);

        authorized.Should().BeTrue();
    }

    [Fact]
    public void IsAuthorized_RejectsWrongToken()
    {
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_ADMIN_TOKEN_HASH"] = "local-admin-token"
        });
        var context = new DefaultHttpContext();
        context.Request.Headers.Authorization = "Bearer wrong";

        var authorized = PhaseAAuth.IsAuthorized(context.Request, options);

        authorized.Should().BeFalse();
    }
}
