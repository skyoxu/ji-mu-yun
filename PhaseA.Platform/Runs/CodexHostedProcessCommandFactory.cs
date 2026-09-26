using PhaseA.Platform.Llm;

namespace PhaseA.Platform.Runs;

public sealed record CodexHostedProcessRequest(
    string RepositoryRoot,
    string OutputPath,
    string Prompt,
    string Model,
    string ReasoningEffort,
    string Sandbox = "workspace-write",
    bool Json = true,
    bool ApprovalNever = true,
    string OutputArgument = "-o",
    string ChangeDirectoryArgument = "--cd",
    IReadOnlyDictionary<string, string>? ExtraEnvironment = null,
    string? OperationKey = null,
    HostedContextEnvelope? ContextEnvelope = null);

public static class CodexHostedProcessCommandFactory
{
    public static HostedProcessCommand Build(CodexHostedProcessRequest request, HostedContextGatePolicy? contextGatePolicy = null)
    {
        ArgumentNullException.ThrowIfNull(request);
        ArgumentException.ThrowIfNullOrWhiteSpace(request.RepositoryRoot);
        ArgumentException.ThrowIfNullOrWhiteSpace(request.OutputPath);
        ArgumentException.ThrowIfNullOrWhiteSpace(request.Prompt);
        ArgumentException.ThrowIfNullOrWhiteSpace(request.Model);
        var gate = HostedContextGate.Evaluate((contextGatePolicy ?? new HostedContextGatePolicy()).Resolve(request.OperationKey), request.ContextEnvelope);
        if (!gate.Allowed)
        {
            throw new InvalidOperationException(gate.FailureCode);
        }

        var sandbox = string.IsNullOrWhiteSpace(request.Sandbox) ? "workspace-write" : request.Sandbox.Trim();
        var arguments = new List<string> { "exec" };
        if (request.Json)
        {
            arguments.Add("--json");
        }

        arguments.Add("--sandbox");
        arguments.Add(sandbox);
        arguments.Add("-m");
        arguments.Add(request.Model);
        if (request.ApprovalNever)
        {
            arguments.Add("-c");
            arguments.Add("approval_policy=\"never\"");
        }

        if (!string.IsNullOrWhiteSpace(request.ReasoningEffort))
        {
            arguments.Add("-c");
            arguments.Add($"model_reasoning_effort=\"{request.ReasoningEffort.Trim()}\"");
        }

        arguments.Add(string.IsNullOrWhiteSpace(request.ChangeDirectoryArgument) ? "--cd" : request.ChangeDirectoryArgument.Trim());
        arguments.Add(request.RepositoryRoot);
        arguments.Add(string.IsNullOrWhiteSpace(request.OutputArgument) ? "-o" : request.OutputArgument.Trim());
        arguments.Add(request.OutputPath);
        arguments.Add("-");

        var environment = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            ["PHASEA_CODEX_DEFAULT_MODEL"] = request.Model
        };
        if (!string.IsNullOrWhiteSpace(request.ReasoningEffort))
        {
            environment["PHASEA_CODEX_REASONING_EFFORT"] = request.ReasoningEffort.Trim();
        }

        foreach (var item in request.ExtraEnvironment ?? new Dictionary<string, string>())
        {
            environment[item.Key] = item.Value;
        }

        return new HostedProcessCommand(
            ResolveCodexCommand(),
            arguments,
            request.RepositoryRoot,
            environment,
            request.Prompt,
            RequireIsolation: true);
    }

    public static async Task<HostedProcessCommand> BuildAsync(
        CodexHostedProcessRequest request,
        HostedContextGatePolicy? contextGatePolicy,
        IHostedContextManifestValidator? contextManifestValidator,
        CancellationToken cancellationToken = default)
    {
        var command = Build(request, contextGatePolicy);
        var gateMode = (contextGatePolicy ?? new HostedContextGatePolicy()).Resolve(request.OperationKey);
        if (gateMode != HostedContextGateMode.Enforce)
        {
            return command;
        }

        if (request.ContextEnvelope is null ||
            contextManifestValidator is null ||
            !await contextManifestValidator.ValidateAndConsumeAsync(
                request.ContextEnvelope,
                request.OperationKey ?? string.Empty,
                cancellationToken))
        {
            throw new InvalidOperationException("context_manifest_invalid");
        }

        return command;
    }

    public static HostedProcessCommand ApplyRuntime(HostedProcessCommand command, AiCodeMirrorRuntimeCredential credential)
    {
        return command with { Environment = CodexRuntimeEnvironment.Merge(command.Environment, credential) };
    }

    public static string ResolveCodexCommand()
    {
        var configured = Environment.GetEnvironmentVariable("PHASEA_CODEX_COMMAND");
        if (!string.IsNullOrWhiteSpace(configured))
        {
            return configured;
        }

        var candidates = new[]
        {
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "npm", "codex.cmd"),
            @"C:\Windows\System32\config\systemprofile\AppData\Roaming\npm\codex.cmd",
            @"C:\Users\Administrator\AppData\Roaming\npm\codex.cmd"
        };

        return candidates.FirstOrDefault(File.Exists) ?? "codex";
    }

    public static string ResolvePathWithRipgrep()
    {
        var currentPath = Environment.GetEnvironmentVariable("PATH") ?? "";
        var configuredRipgrepDir = Environment.GetEnvironmentVariable("PHASEA_RIPGREP_DIR");
        var defaultRipgrepDir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "npm",
            "node_modules",
            "@openai",
            "codex",
            "node_modules",
            "@openai",
            "codex-win32-x64",
            "vendor",
            "x86_64-pc-windows-msvc",
            "path");
        var ripgrepDir = !string.IsNullOrWhiteSpace(configuredRipgrepDir)
            ? configuredRipgrepDir
            : defaultRipgrepDir;
        if (!Directory.Exists(ripgrepDir))
        {
            return currentPath;
        }

        var paths = currentPath.Split(Path.PathSeparator, StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        return paths.Contains(ripgrepDir, StringComparer.OrdinalIgnoreCase)
            ? currentPath
            : string.IsNullOrWhiteSpace(currentPath)
                ? ripgrepDir
                : $"{ripgrepDir}{Path.PathSeparator}{currentPath}";
    }
}
