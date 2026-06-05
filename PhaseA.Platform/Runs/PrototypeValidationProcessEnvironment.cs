namespace PhaseA.Platform.Runs;

internal static class PrototypeValidationProcessEnvironment
{
    private const string BuildRootEnvironmentKey = "PHASEA_VALIDATION_BUILD_ROOT";

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
            [BuildRootEnvironmentKey] = buildRoot,
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

    public static string[] CreateMsBuildIsolationArguments(IReadOnlyDictionary<string, string> environment, string scope)
    {
        if (!environment.TryGetValue(BuildRootEnvironmentKey, out var buildRoot) ||
            string.IsNullOrWhiteSpace(buildRoot))
        {
            return [];
        }

        var safeScope = string.Join(
            "_",
            scope.Split(Path.GetInvalidFileNameChars(), StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries));
        if (string.IsNullOrWhiteSpace(safeScope))
        {
            safeScope = "validation";
        }

        var intermediateRoot = EnsureTrailingSeparator(Path.Combine(buildRoot, safeScope, "obj", "$(MSBuildProjectName)"));
        var outputRoot = EnsureTrailingSeparator(Path.Combine(buildRoot, safeScope, "bin", "$(MSBuildProjectName)"));
        Directory.CreateDirectory(Path.Combine(buildRoot, safeScope));
        return
        [
            $"-p:BaseIntermediateOutputPath={intermediateRoot}",
            $"-p:BaseOutputPath={outputRoot}",
            "-p:UseSharedCompilation=false",
            "-p:NodeReuse=false",
            "-m:1",
            "-p:BuildInParallel=false"
        ];
    }

    public static string[] CreateMsBuildStabilityArguments()
    {
        return
        [
            "-p:UseSharedCompilation=false",
            "-p:NodeReuse=false",
            "-m:1",
            "-p:BuildInParallel=false"
        ];
    }

    private static string EnsureTrailingSeparator(string path)
    {
        return path.EndsWith(Path.DirectorySeparatorChar) || path.EndsWith(Path.AltDirectorySeparatorChar)
            ? path
            : path + Path.DirectorySeparatorChar;
    }
}
