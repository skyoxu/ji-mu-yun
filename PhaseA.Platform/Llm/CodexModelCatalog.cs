namespace PhaseA.Platform.Llm;

public static class CodexModelCatalog
{
    private static readonly string[] DefaultAllowedModels =
    [
        "gpt-5.5",
        "gpt-5.4",
        "gpt-5.4-mini",
        "gpt-5.3-codex",
        "gpt-5.2"
    ];

    public static IReadOnlyList<string> AllowedModels()
    {
        var configured = Environment.GetEnvironmentVariable("PHASEA_CODEX_ALLOWED_MODELS");
        if (string.IsNullOrWhiteSpace(configured))
        {
            return DefaultAllowedModels;
        }

        var models = configured
            .Split(',', StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries)
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToArray();
        return models.Length == 0 ? DefaultAllowedModels : models;
    }

    public static string DefaultModel()
    {
        var configured = Environment.GetEnvironmentVariable("PHASEA_CODEX_DEFAULT_MODEL");
        if (!string.IsNullOrWhiteSpace(configured) && IsAllowed(configured))
        {
            return configured.Trim();
        }

        return AllowedModels()[0];
    }

    public static bool IsAllowed(string model)
    {
        return !string.IsNullOrWhiteSpace(model) &&
               AllowedModels().Contains(model.Trim(), StringComparer.OrdinalIgnoreCase);
    }
}
