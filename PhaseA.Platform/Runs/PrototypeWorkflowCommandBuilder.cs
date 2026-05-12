using PhaseA.Platform.Configuration;

namespace PhaseA.Platform.Runs;

public sealed class PrototypeWorkflowCommandBuilder
{
    private readonly PhaseAPlatformOptions _options;

    public PrototypeWorkflowCommandBuilder(PhaseAPlatformOptions options)
    {
        _options = options;
    }

    public HostedProcessCommand Build(PrototypeWorkflowRequest request, string prototypeRecordPath, string repositoryRoot)
    {
        ArgumentNullException.ThrowIfNull(request);
        ArgumentException.ThrowIfNullOrWhiteSpace(prototypeRecordPath);
        ArgumentException.ThrowIfNullOrWhiteSpace(repositoryRoot);

        var arguments = new List<string>
        {
            "-3",
            "scripts/python/dev_cli.py",
            "run-prototype-workflow",
            "--prototype-file",
            prototypeRecordPath
        };

        if (request.Confirm)
        {
            arguments.Add("--confirm");
        }

        if (request.StopAfterDay is not null)
        {
            arguments.Add("--stop-after-day");
            arguments.Add(request.StopAfterDay.Value.ToString(System.Globalization.CultureInfo.InvariantCulture));
        }

        if (!string.IsNullOrWhiteSpace(request.ScoreEngine))
        {
            arguments.Add("--score-engine");
            arguments.Add(request.ScoreEngine);
        }

        if (!string.IsNullOrWhiteSpace(_options.GodotBin))
        {
            arguments.Add("--godot-bin");
            arguments.Add(_options.GodotBin);
        }

        var environment = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        environment["PHASEA_CODEX_DEFAULT_MODEL"] = PrototypeModelPolicy.Normalize(request.Model);
        environment["PHASEA_CODEX_REASONING_EFFORT"] = PrototypeModelPolicy.DefaultReasoningEffort;
        if (!string.IsNullOrWhiteSpace(_options.GodotBin))
        {
            environment["GODOT_BIN"] = _options.GodotBin;
        }

        return new HostedProcessCommand(_options.PythonCommand, arguments, repositoryRoot, environment);
    }
}
