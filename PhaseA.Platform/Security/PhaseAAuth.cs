using PhaseA.Platform.Configuration;
using System.Security.Cryptography;
using System.Text;

namespace PhaseA.Platform.Security;

public static class PhaseAAuth
{
    public const string AuthFailureCode = "authentication_required";
    public const string AdminRole = "admin";
    public const string UserRole = "user";
    public const string AccessTokenCookieName = "phaseAAccessToken";

    public static bool IsConfigured(PhaseAPlatformOptions options)
    {
        ArgumentNullException.ThrowIfNull(options);
        return !string.IsNullOrWhiteSpace(options.AdminTokenHash);
    }

    public static bool IsAuthorized(HttpRequest request, PhaseAPlatformOptions options)
    {
        return GetRole(request, options) is not null;
    }

    public static string? GetRole(HttpRequest request, PhaseAPlatformOptions options)
    {
        ArgumentNullException.ThrowIfNull(request);
        ArgumentNullException.ThrowIfNull(options);

        if (!IsConfigured(options))
        {
            return null;
        }

        var token = ReadToken(request);
        if (token is null)
        {
            return null;
        }

        if (!string.IsNullOrWhiteSpace(options.AdminTokenHash))
        {
            if (TokenMatches(token, options.AdminTokenHash.Trim()))
            {
                return AdminRole;
            }
        }

        return null;
    }

    public static string? ReadBearerOrHeaderToken(HttpRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);
        return ReadToken(request);
    }

    public static string HashTokenForStorage(string token)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(token);
        return Convert.ToBase64String(SHA256.HashData(Encoding.UTF8.GetBytes(token.Trim())))
            .TrimEnd('=')
            .Replace('+', '-')
            .Replace('/', '_');
    }

    private static string? ReadToken(HttpRequest request)
    {
        var authorization = request.Headers.Authorization.ToString();
        if (authorization.StartsWith("Bearer ", StringComparison.OrdinalIgnoreCase))
        {
            var bearerToken = authorization["Bearer ".Length..].Trim();
            if (!string.IsNullOrWhiteSpace(bearerToken))
            {
                return bearerToken;
            }
        }

        if (request.Headers.TryGetValue("X-PhaseA-Admin-Token", out var adminTokenHeader))
        {
            return adminTokenHeader.ToString().Trim();
        }

        if (request.Cookies.TryGetValue(AccessTokenCookieName, out var accessTokenCookie) &&
            !string.IsNullOrWhiteSpace(accessTokenCookie))
        {
            return accessTokenCookie.Trim();
        }

        return null;
    }

    private static bool TokenMatches(string token, string expectedHash)
    {
        if (string.IsNullOrWhiteSpace(token) || string.IsNullOrWhiteSpace(expectedHash))
        {
            return false;
        }

        var actualHash = HashTokenForStorage(token);

        return CryptographicOperations.FixedTimeEquals(
            Encoding.ASCII.GetBytes(actualHash),
            Encoding.ASCII.GetBytes(expectedHash.Trim()));
    }
}
