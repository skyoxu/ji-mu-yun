namespace PhaseA.Platform.Runs;

public static class PrototypeWorkflowValidation
{
    public static IReadOnlyList<string> MissingRequiredFields(PrototypeWorkflowRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);

        var missing = new List<string>();
        AddIfMissing(missing, request.Slug, "slug");
        AddIfMissing(missing, request.Hypothesis, "hypothesis");
        AddIfMissing(missing, request.CorePlayerFantasy, "core_player_fantasy");
        AddIfMissing(missing, request.MinimumPlayableLoop, "minimum_playable_loop");
        if (request.SuccessCriteria is null || request.SuccessCriteria.Count == 0 || request.SuccessCriteria.All(string.IsNullOrWhiteSpace))
        {
            missing.Add("success_criteria");
        }

        AddIfMissing(missing, request.GameFeature, "game_feature");
        AddIfMissing(missing, request.CoreGameplayLoop, "core_gameplay_loop");
        AddIfMissing(missing, request.WinFailConditions, "win_fail_conditions");
        return missing;
    }

    private static void AddIfMissing(List<string> missing, string? value, string fieldName)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            missing.Add(fieldName);
        }
    }
}
