using Microsoft.AspNetCore.Http;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Security;
using Xunit;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S79BoundaryTests
{
    [Fact]
    public void O_39E75106860B()
    {
        const string adminToken = "s79-supported-admin-bearer";
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_ADMIN_TOKEN_HASH"] = PhaseAAuth.HashTokenForStorage(adminToken),
        });

        var bearerRequest = CreateRequest($"Bearer {adminToken}");
        var basicRequest = CreateRequest("Basic czc5LXVuc3VwcG9ydGVk");
        var unknownSchemeRequest = CreateRequest($"Oidc {adminToken}");

        var supportedBearerRole = PhaseAAuth.GetRole(bearerRequest, options);
        var unsupportedBasicRole = PhaseAAuth.GetRole(basicRequest, options);
        var unsupportedOidcRole = PhaseAAuth.GetRole(unknownSchemeRequest, options);

        Require(
            supportedBearerRole == PhaseAAuth.AdminRole &&
            unsupportedBasicRole is null &&
            unsupportedOidcRole is null,
            "FAILURE-O-39E75106860B",
            "The compatibility boundary did not accept only the declared admin bearer credential kind.");
    }

    private static HttpRequest CreateRequest(string authorization)
    {
        var context = new DefaultHttpContext();
        context.Request.Headers.Authorization = authorization;
        return context.Request;
    }

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
        {
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
        }
    }
}
