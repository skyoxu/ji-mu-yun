namespace PhaseA.Platform.Llm;

public static class LlmTokenResolver
{
    public static string? Resolve(string tokenRef)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(tokenRef);

        if (tokenRef.StartsWith("env:", StringComparison.OrdinalIgnoreCase))
        {
            var name = tokenRef["env:".Length..].Trim();
            return string.IsNullOrWhiteSpace(name) ? null : Environment.GetEnvironmentVariable(name);
        }

        if (tokenRef.StartsWith("host-secret:", StringComparison.OrdinalIgnoreCase))
        {
            var name = tokenRef["host-secret:".Length..].Trim();
            if (string.IsNullOrWhiteSpace(name))
            {
                return null;
            }

            return Environment.GetEnvironmentVariable("PHASEA_HOST_SECRET_" + SanitizeSecretName(name));
        }

        return null;
    }

    private static string SanitizeSecretName(string value)
    {
        var chars = value.Select(ch => char.IsLetterOrDigit(ch) ? char.ToUpperInvariant(ch) : '_').ToArray();
        return new string(chars);
    }
}
