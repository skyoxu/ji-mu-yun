using PhaseA.Platform.Configuration;

namespace PhaseA.Platform.Security;

public static class PhaseAAuth
{
    public const string AuthFailureCode = "authentication_required";

    public static bool IsConfigured(PhaseAPlatformOptions options)
    {
        ArgumentNullException.ThrowIfNull(options);
        return !string.IsNullOrWhiteSpace(options.AdminTokenHash) ||
               !string.IsNullOrWhiteSpace(options.AdminPasswordHash);
    }

    public static bool IsAuthorized(HttpRequest request, PhaseAPlatformOptions options)
    {
        ArgumentNullException.ThrowIfNull(request);
        ArgumentNullException.ThrowIfNull(options);

        if (!IsConfigured(options))
        {
            return false;
        }

        if (!string.IsNullOrWhiteSpace(options.AdminTokenHash))
        {
            var expected = options.AdminTokenHash.Trim();
            var authorization = request.Headers.Authorization.ToString();
            if (authorization.StartsWith("Bearer ", StringComparison.OrdinalIgnoreCase))
            {
                var token = authorization["Bearer ".Length..].Trim();
                if (string.Equals(token, expected, StringComparison.Ordinal))
                {
                    return true;
                }
            }

            if (request.Headers.TryGetValue("X-PhaseA-Admin-Token", out var tokenHeader) &&
                string.Equals(tokenHeader.ToString(), expected, StringComparison.Ordinal))
            {
                return true;
            }
        }

        return false;
    }
}
