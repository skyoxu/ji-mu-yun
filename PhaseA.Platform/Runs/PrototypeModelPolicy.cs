namespace PhaseA.Platform.Runs;

public static class PrototypeModelPolicy
{
    private const string DefaultPrototypeModel = "gpt-5.5";
    public const string DefaultReasoningEffort = "high";
    private static readonly HashSet<string> Allowed = new(StringComparer.Ordinal)
    {
        "gpt-5.5",
        "gpt-5.4"
    };

    public static string Normalize(string? model)
    {
        return !string.IsNullOrWhiteSpace(model) && Allowed.Contains(model.Trim())
            ? model.Trim()
            : DefaultPrototypeModel;
    }
}
