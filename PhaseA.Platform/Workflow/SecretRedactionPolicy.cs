using System.Text.RegularExpressions;

namespace PhaseA.Platform.Workflow;

public static partial class SecretRedactionPolicy
{
    public static readonly IReadOnlyList<string> SecretFieldNames =
    [
        "PHASEA_ADMIN_TOKEN",
        "PHASEA_ADMIN_TOKEN_HASH",
        "Authorization",
        "Bearer",
        "OPENAI_API_KEY",
        "AICODEMIRROR_API_KEY",
        "token_hash",
        "provider_key",
        "api_key",
        "access_token"
    ];

    public static IReadOnlyList<string> FindViolations(string text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return [];
        }

        var violations = new List<string>();
        foreach (var field in SecretFieldNames)
        {
            if (text.Contains(field, StringComparison.OrdinalIgnoreCase))
            {
                violations.Add($"secret_field:{field}");
            }
        }

        if (BearerToken().IsMatch(text))
        {
            violations.Add("secret_pattern:bearer_token");
        }

        if (ProviderKey().IsMatch(text))
        {
            violations.Add("secret_pattern:provider_key");
        }

        return violations.Distinct(StringComparer.Ordinal).ToArray();
    }

    public static string Redact(string text)
    {
        if (string.IsNullOrEmpty(text))
        {
            return "";
        }

        var redacted = text;
        redacted = BearerToken().Replace(redacted, "Bearer [redacted]");
        redacted = ProviderKey().Replace(redacted, "[redacted-provider-key]");
        foreach (var field in SecretFieldNames)
        {
            redacted = Regex.Replace(redacted, $"{Regex.Escape(field)}\\s*[:=]\\s*[^\\s,;]+", $"{field}=[redacted]", RegexOptions.IgnoreCase);
        }

        return redacted;
    }

    [GeneratedRegex("Bearer\\s+[A-Za-z0-9._~+\\-/]+=*", RegexOptions.IgnoreCase)]
    private static partial Regex BearerToken();

    [GeneratedRegex("(sk-[A-Za-z0-9]{12,}|aicm-[A-Za-z0-9]{12,})", RegexOptions.IgnoreCase)]
    private static partial Regex ProviderKey();
}
