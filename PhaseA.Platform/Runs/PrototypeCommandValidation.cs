namespace PhaseA.Platform.Runs;

public static class PrototypeCommandValidation
{
    private static readonly HashSet<string> AllowedStages = new(StringComparer.OrdinalIgnoreCase)
    {
        "red",
        "green",
        "refactor"
    };

    public static IReadOnlyList<string> MissingTddFields(PrototypeTddRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);

        var missing = new List<string>();
        if (string.IsNullOrWhiteSpace(request.Slug))
        {
            missing.Add("slug");
        }

        if (string.IsNullOrWhiteSpace(request.Stage) || !AllowedStages.Contains(request.Stage))
        {
            missing.Add("stage");
        }

        return missing;
    }

    public static IReadOnlyList<string> MissingSceneFields(PrototypeSceneRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);
        return string.IsNullOrWhiteSpace(request.Slug) ? ["slug"] : [];
    }
}
