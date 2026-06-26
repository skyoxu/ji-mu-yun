using FluentAssertions;
using Microsoft.AspNetCore.Http;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Security;
using System.Security.Cryptography;
using System.Text;
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
    public void IsConfigured_ReturnsFalse_WhenOnlyAdminPasswordHashIsConfigured()
    {
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_ADMIN_PASSWORD_HASH"] = HashToken("local-admin-password")
        });
        var context = new DefaultHttpContext();
        context.Request.Headers.Authorization = "Bearer local-admin-password";

        PhaseAAuth.IsConfigured(options).Should().BeFalse();
        PhaseAAuth.IsAuthorized(context.Request, options).Should().BeFalse();
        PhaseAAuth.GetRole(context.Request, options).Should().BeNull();
    }

    [Fact]
    public void IsAuthorized_AcceptsBearerToken_WhenSha256HashMatchesConfiguredAdminTokenHash()
    {
        const string token = "local-admin-token";
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_ADMIN_TOKEN_HASH"] = PhaseAAuth.HashTokenForStorage(token)
        });
        var context = new DefaultHttpContext();
        context.Request.Headers.Authorization = $"Bearer {token}";

        var authorized = PhaseAAuth.IsAuthorized(context.Request, options);

        authorized.Should().BeTrue();
        PhaseAAuth.GetRole(context.Request, options).Should().Be(PhaseAAuth.AdminRole);
    }

    [Fact]
    public void GetRole_ReturnsNull_WhenSha256HashMatchesDeprecatedUserTokenHash()
    {
        const string token = "local-user-token";
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_ADMIN_TOKEN_HASH"] = HashToken("local-admin-token"),
            ["PHASEA_USER_TOKEN_HASH"] = PhaseAAuth.HashTokenForStorage(token)
        });
        var context = new DefaultHttpContext();
        context.Request.Headers.Authorization = $"Bearer {token}";

        var role = PhaseAAuth.GetRole(context.Request, options);

        role.Should().BeNull();
        PhaseAAuth.IsAuthorized(context.Request, options).Should().BeFalse();
    }

    [Fact]
    public void GetRole_ReturnsNull_WhenSha256HashMatchesDeprecatedUserAccessTokenCookie()
    {
        const string token = "local-user-token";
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_ADMIN_TOKEN_HASH"] = HashToken("local-admin-token"),
            ["PHASEA_USER_TOKEN_HASH"] = PhaseAAuth.HashTokenForStorage(token)
        });
        var context = new DefaultHttpContext();
        context.Request.Headers.Cookie = $"{PhaseAAuth.AccessTokenCookieName}={token}";

        var role = PhaseAAuth.GetRole(context.Request, options);

        role.Should().BeNull();
        PhaseAAuth.IsAuthorized(context.Request, options).Should().BeFalse();
    }

    [Fact]
    public void GetRole_FallsBackToAccessTokenCookie_WhenBearerHeaderIsEmpty()
    {
        const string token = "local-admin-token";
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_ADMIN_TOKEN_HASH"] = PhaseAAuth.HashTokenForStorage(token)
        });
        var context = new DefaultHttpContext();
        context.Request.Headers.Authorization = "Bearer ";
        context.Request.Headers.Cookie = $"{PhaseAAuth.AccessTokenCookieName}={token}";

        var role = PhaseAAuth.GetRole(context.Request, options);

        role.Should().Be(PhaseAAuth.AdminRole);
        PhaseAAuth.IsAuthorized(context.Request, options).Should().BeTrue();
    }

    [Fact]
    public void HashTokenForStorage_MatchesExistingSha256Base64UrlFormat()
    {
        PhaseAAuth.HashTokenForStorage("local-admin-token").Should().Be(HashToken("local-admin-token"));
    }

    [Fact]
    public void IsAuthorized_RejectsWrongToken()
    {
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_ADMIN_TOKEN_HASH"] = HashToken("local-admin-token")
        });
        var context = new DefaultHttpContext();
        context.Request.Headers.Authorization = "Bearer wrong";

        var authorized = PhaseAAuth.IsAuthorized(context.Request, options);

        authorized.Should().BeFalse();
    }

    private static string HashToken(string token)
    {
        return Convert.ToBase64String(SHA256.HashData(Encoding.UTF8.GetBytes(token)))
            .TrimEnd('=')
            .Replace('+', '-')
            .Replace('/', '_');
    }
}
