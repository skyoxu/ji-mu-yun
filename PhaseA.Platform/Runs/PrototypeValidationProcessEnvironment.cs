namespace PhaseA.Platform.Runs;

internal static class PrototypeValidationProcessEnvironment
{
    public static Dictionary<string, string> Create(string repoPath, IReadOnlyDictionary<string, string>? extra = null)
    {
        var tempRoot = Path.Combine(repoPath, "logs", "phase-a-validation-temp");
        var buildRoot = Path.Combine(repoPath, "logs", "phase-a-validation-build", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(tempRoot);
        Directory.CreateDirectory(buildRoot);

        var environment = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            ["TMP"] = tempRoot,
            ["TEMP"] = tempRoot,
            ["PHASEA_VALIDATION_BUILD_ROOT"] = buildRoot,
            ["DOTNET_SKIP_FIRST_TIME_EXPERIENCE"] = "1",
            ["DOTNET_NOLOGO"] = "1",
            ["MSBUILDDISABLENODEREUSE"] = "1",
            ["UseSharedCompilation"] = "false"
        };

        if (extra is not null)
        {
            foreach (var item in extra)
            {
                environment[item.Key] = item.Value;
            }
        }

        return environment;
    }
}
