using PhaseA.Platform.Configuration;
using System.Security.Cryptography;
using System.Text;

namespace PhaseA.Platform.Security;

public static class PhaseAAuth
{
    public const string AuthFailureCode = "authentication_required";
    public const string AdminRole = "admin";
    public const string UserRole = "user";

    public static bool IsConfigured(PhaseAPlatformOptions options)
    {
        ArgumentNullException.ThrowIfNull(options);
        return !string.IsNullOrWhiteSpace(options.AdminTokenHash) ||
               !string.IsNullOrWhiteSpace(options.UserTokenHash) ||
               !string.IsNullOrWhiteSpace(options.AdminPasswordHash);
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

        if (!string.IsNullOrWhiteSpace(options.UserTokenHash) &&
            TokenMatches(token, options.UserTokenHash.Trim()))
        {
            return UserRole;
        }

        return null;
    }

    private static string? ReadToken(HttpRequest request)
    {
        var authorization = request.Headers.Authorization.ToString();
        if (authorization.StartsWith("Bearer ", StringComparison.OrdinalIgnoreCase))
        {
            return authorization["Bearer ".Length..].Trim();
        }

        if (request.Headers.TryGetValue("X-PhaseA-Admin-Token", out var adminTokenHeader))
        {
            return adminTokenHeader.ToString().Trim();
        }

        return null;
    }

    private static bool TokenMatches(string token, string expectedHash)
    {
        if (string.IsNullOrWhiteSpace(token) || string.IsNullOrWhiteSpace(expectedHash))
        {
            return false;
        }

        var actualHash = Convert.ToBase64String(SHA256.HashData(Encoding.UTF8.GetBytes(token.Trim())))
            .TrimEnd('=')
            .Replace('+', '-')
            .Replace('/', '_');

        return CryptographicOperations.FixedTimeEquals(
            Encoding.ASCII.GetBytes(actualHash),
            Encoding.ASCII.GetBytes(expectedHash.Trim()));
    }
}
