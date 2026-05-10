using PhaseA.Platform.Configuration;

namespace PhaseA.Platform.Runs;

public sealed class PrototypeCommandBuilder
{
    private readonly PhaseAPlatformOptions _options;

    public PrototypeCommandBuilder(PhaseAPlatformOptions options)
    {
        _options = options;
    }

    public HostedProcessCommand BuildTdd(PrototypeTddRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);
        var arguments = new List<string>
        {
            "-3",
            "scripts/python/dev_cli.py",
            "run-prototype-tdd",
            "--slug",
            PrototypeRecordWriter.SanitizeSlug(request.Slug!),
            "--stage",
            request.Stage!.ToLowerInvariant()
        };

        if (!string.IsNullOrWhiteSpace(request.Expect))
        {
            arguments.Add("--expect");
            arguments.Add(request.Expect);
        }

        if (!string.IsNullOrWhiteSpace(request.RecordPath))
        {
            arguments.Add("--record-path");
            arguments.Add(request.RecordPath);
        }

        if (!string.IsNullOrWhiteSpace(request.Filter))
        {
            arguments.Add("--filter");
            arguments.Add(request.Filter);
        }

        foreach (var target in request.DotnetTarget ?? [])
        {
            if (!string.IsNullOrWhiteSpace(target))
            {
                arguments.Add("--dotnet-target");
                arguments.Add(target);
            }
        }

        foreach (var path in request.GdunitPath ?? [])
        {
            if (!string.IsNullOrWhiteSpace(path))
            {
                arguments.Add("--gdunit-path");
                arguments.Add(path);
            }
        }

        if (request.TimeoutSec is not null)
        {
            arguments.Add("--timeout-sec");
            arguments.Add(request.TimeoutSec.Value.ToString(System.Globalization.CultureInfo.InvariantCulture));
        }

        if (!string.IsNullOrWhiteSpace(_options.GodotBin))
        {
            arguments.Add("--godot-bin");
            arguments.Add(_options.GodotBin);
        }

        return Build(arguments);
    }

    public HostedProcessCommand BuildScene(PrototypeSceneRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);
        var arguments = new List<string>
        {
            "-3",
            "scripts/python/dev_cli.py",
            "create-prototype-scene",
            "--slug",
            PrototypeRecordWriter.SanitizeSlug(request.Slug!)
        };

        if (!string.IsNullOrWhiteSpace(request.SceneRoot))
        {
            arguments.Add("--scene-root");
            arguments.Add(request.SceneRoot);
        }

        if (!string.IsNullOrWhiteSpace(request.PrototypeRoot))
        {
            arguments.Add("--prototype-root");
            arguments.Add(request.PrototypeRoot);
        }

        return Build(arguments);
    }

    private HostedProcessCommand Build(IReadOnlyList<string> arguments)
    {
        var environment = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        if (!string.IsNullOrWhiteSpace(_options.GodotBin))
        {
            environment["GODOT_BIN"] = _options.GodotBin;
        }

        return new HostedProcessCommand(_options.PythonCommand, arguments, _options.RepositoryRoot, environment);
    }
}
