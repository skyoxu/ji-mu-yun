using PhaseA.Platform.Configuration;

namespace PhaseA.Platform.Runs;

public sealed class Chapter2BootstrapCommandBuilder
{
    private readonly PhaseAPlatformOptions _options;

    public Chapter2BootstrapCommandBuilder(PhaseAPlatformOptions options)
    {
        _options = options;
    }

    public HostedProcessCommand BuildLocalHardChecksCommand()
    {
        var arguments = new List<string>
        {
            "-3",
            "scripts/python/dev_cli.py",
            "run-local-hard-checks",
            "--delivery-profile",
            _options.DeliveryProfile
        };

        if (!string.IsNullOrWhiteSpace(_options.GodotBin))
        {
            arguments.Add("--godot-bin");
            arguments.Add(_options.GodotBin);
        }

        var environment = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        if (!string.IsNullOrWhiteSpace(_options.GodotBin))
        {
            environment["GODOT_BIN"] = _options.GodotBin;
        }

        return new HostedProcessCommand(_options.PythonCommand, arguments, _options.RepositoryRoot, environment);
    }

    public HostedProcessCommand BuildProjectHealthScanCommand()
    {
        return new HostedProcessCommand(
            _options.PythonCommand,
            ["-3", "scripts/python/dev_cli.py", "project-health-scan", "--repo-root", _options.RepositoryRoot],
            _options.RepositoryRoot,
            new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase));
    }
}
