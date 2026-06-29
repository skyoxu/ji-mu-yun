using System.Security.Cryptography;
using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.Json.Serialization.Metadata;
using System.Text.RegularExpressions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Workspaces;

namespace PhaseA.Platform.Readback;

public sealed class ProjectWebPreviewDedicatedAdapterService
{
    public const string SchemaVersion = "phasea-web-preview-dedicated-adapter-v1";
    public const string GeneratorVersion = "phasea-project-dedicated-godot3-adapter-v1";
    public const string MainScriptFileName = "Main.gd";
    public const string ManifestFileName = "adapter-manifest.json";

    private const string AdapterRootRelativePath = "exports/web-preview-dedicated-adapters";
    private const string WorkRootRelativePath = "exports/.web-preview-dedicated-adapter-work";
    private const int MaxPromptJsonChars = 80_000;
    private const int MaxReferenceScriptChars = 50_000;
    private const string ReasoningEffort = "medium";

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
        TypeInfoResolver = new DefaultJsonTypeInfoResolver()
    };

    private readonly PhaseAPlatformOptions _options;
    private readonly IHostedProcessRunner? _processRunner;
    private readonly AiCodeMirrorKeyPoolService? _keyPoolService;
    private readonly bool _enableCodex;

    public ProjectWebPreviewDedicatedAdapterService(
        PhaseAPlatformOptions options,
        IHostedProcessRunner processRunner,
        AiCodeMirrorKeyPoolService? keyPoolService = null)
        : this(options, processRunner, keyPoolService, enableCodex: true)
    {
    }

    private ProjectWebPreviewDedicatedAdapterService(
        PhaseAPlatformOptions options,
        IHostedProcessRunner? processRunner,
        AiCodeMirrorKeyPoolService? keyPoolService,
        bool enableCodex)
    {
        _options = options;
        _processRunner = processRunner;
        _keyPoolService = keyPoolService;
        _enableCodex = enableCodex;
    }

    public static ProjectWebPreviewDedicatedAdapterService DeterministicOnly(PhaseAPlatformOptions options)
    {
        return new ProjectWebPreviewDedicatedAdapterService(options, null, null, enableCodex: false);
    }

    public async Task<ProjectWebPreviewDedicatedAdapterResult> ResolveAsync(
        ProjectWebPreviewDedicatedAdapterRequest request,
        string fallbackMainScript,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(request);
        ArgumentException.ThrowIfNullOrWhiteSpace(fallbackMainScript);
        var projectRoot = Path.GetFullPath(request.ProjectRoot);
        if (!WorkspacePathPolicy.IsUnderRoot(_options.HostedWorkspaceRoot, projectRoot))
        {
            throw new InvalidOperationException("Project repository path escaped the hosted workspace root.");
        }

        var version = PackageVersionFromFileName(request.PackageFile);
        var targetDirectory = ResolveUnderProject(projectRoot, $"{AdapterRootRelativePath}/{SanitizePathSegment(version)}");
        Directory.CreateDirectory(targetDirectory);
        var targetPath = Path.Combine(targetDirectory, MainScriptFileName);
        var manifestPath = Path.Combine(targetDirectory, ManifestFileName);
        if (TryReadReusableAdapter(manifestPath, targetPath, request, out var reusable))
        {
            return reusable;
        }

        var fallbackSha256 = ComputeStringSha256(fallbackMainScript);
        if (_enableCodex && _processRunner is not null)
        {
            var workDirectory = ResolveUnderProject(projectRoot, $"{WorkRootRelativePath}/{request.RunId}");
            Directory.CreateDirectory(workDirectory);
            var outputPath = Path.Combine(workDirectory, $"{SanitizePathSegment(version)}.gd");
            CodexAdapterRun? codexRun = null;
            try
            {
                codexRun = await RunCodexAsync(request, outputPath, fallbackMainScript, cancellationToken);
            }
            catch (Exception ex) when (ex is not OperationCanceledException)
            {
                codexRun = new CodexAdapterRun(-1, ex.ToString(), Tail(ex.ToString(), 2000));
            }

            string? validationError = null;
            if (codexRun.ExitCode == 0 &&
                TryReadGeneratedScript(outputPath, codexRun.RawOutput, out var generatedScript, out validationError))
            {
                var generatedSha256 = ComputeStringSha256(generatedScript);
                await WriteAdapterAsync(
                    targetPath,
                    manifestPath,
                    generatedScript,
                    BuildManifest(request, version, "codex-dedicated-adapter", generatedSha256, fallbackSha256, codexInvoked: true, "generated_by_codex", ""),
                    cancellationToken);
                return new ProjectWebPreviewDedicatedAdapterResult(
                    generatedScript,
                    targetPath,
                    new ProjectWebPreviewDedicatedAdapterResolution(
                        "generated_by_codex",
                        "Codex generated a package-versioned Godot3 dedicated adapter.",
                        version,
                        request.PackageSha256,
                        targetPath,
                        generatedSha256,
                        true,
                        codexRun.RawOutputTail));
            }

            var reason = validationError ?? $"Codex exited with {codexRun.ExitCode}.";
            await WriteAdapterAsync(
                targetPath,
                manifestPath,
                fallbackMainScript,
                BuildManifest(request, version, "generic-fallback-adapter", fallbackSha256, fallbackSha256, codexInvoked: true, "generated_by_fallback", reason),
                cancellationToken);
            return new ProjectWebPreviewDedicatedAdapterResult(
                fallbackMainScript,
                targetPath,
                new ProjectWebPreviewDedicatedAdapterResolution(
                    "generated_by_fallback",
                    reason,
                    version,
                    request.PackageSha256,
                    targetPath,
                    fallbackSha256,
                    true,
                    codexRun.RawOutputTail));
        }

        await WriteAdapterAsync(
            targetPath,
            manifestPath,
            fallbackMainScript,
            BuildManifest(request, version, "deterministic-generic-fallback-adapter", fallbackSha256, fallbackSha256, codexInvoked: false, "generated_deterministic", "Codex dedicated adapter generation is disabled."),
            cancellationToken);
        return new ProjectWebPreviewDedicatedAdapterResult(
            fallbackMainScript,
            targetPath,
            new ProjectWebPreviewDedicatedAdapterResolution(
                "generated_deterministic",
                "Codex dedicated adapter generation is disabled.",
                version,
                request.PackageSha256,
                targetPath,
                fallbackSha256,
                false,
                ""));
    }

    private async Task<CodexAdapterRun> RunCodexAsync(
        ProjectWebPreviewDedicatedAdapterRequest request,
        string outputPath,
        string fallbackMainScript,
        CancellationToken cancellationToken)
    {
        var model = CodexModelCatalog.DefaultModel();
        var command = CodexHostedProcessCommandFactory.Build(new CodexHostedProcessRequest(
            request.ProjectRoot,
            outputPath,
            BuildGenerationPrompt(request, fallbackMainScript),
            model,
            ReasoningEffort,
            Json: false,
            Sandbox: "workspace-write",
            ExtraEnvironment: new Dictionary<string, string>
            {
                ["PATH"] = CodexHostedProcessCommandFactory.ResolvePathWithRipgrep()
            }));
        var credential = await ResolveRuntimeCredentialAsync(request.AccountId, cancellationToken);
        var result = await _processRunner!.RunAsync(
            CodexHostedProcessCommandFactory.ApplyRuntime(command, credential)
                .WithRunId(request.RunId)
                .WithTimeouts(TimeSpan.FromMinutes(8), TimeSpan.FromMinutes(3)),
            cancellationToken);
        var raw = ReadOutputText(outputPath, result);
        return new CodexAdapterRun(result.ExitCode, raw, Tail(raw, 2000));
    }

    private async Task<AiCodeMirrorRuntimeCredential> ResolveRuntimeCredentialAsync(string accountId, CancellationToken cancellationToken)
    {
        if (_keyPoolService is null)
        {
            return new AiCodeMirrorRuntimeCredential(accountId, null, null);
        }

        var credential = await _keyPoolService.ResolveRuntimeCredentialForAccountAsync(accountId, cancellationToken);
        return credential.BillingKeyName is null && credential.CodexHomePath is null
            ? new AiCodeMirrorRuntimeCredential(accountId, null, null)
            : credential;
    }

    private static bool TryReadReusableAdapter(
        string manifestPath,
        string mainScriptPath,
        ProjectWebPreviewDedicatedAdapterRequest request,
        out ProjectWebPreviewDedicatedAdapterResult result)
    {
        result = default!;
        if (!File.Exists(manifestPath) || !File.Exists(mainScriptPath))
        {
            return false;
        }

        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(manifestPath, Encoding.UTF8));
            var root = document.RootElement;
            if (!JsonStringEquals(root, "schema_version", SchemaVersion) ||
                !JsonStringEquals(root, "generator_version", GeneratorVersion) ||
                !JsonStringEquals(root, "package_file", request.PackageFile) ||
                !JsonStringEquals(root, "package_sha256", request.PackageSha256))
            {
                return false;
            }

            var mainScript = File.ReadAllText(mainScriptPath, Encoding.UTF8);
            if (!IsUsableGdScript(mainScript, out _))
            {
                return false;
            }

            var adapterSha256 = GetString(root, "adapter_sha256");
            result = new ProjectWebPreviewDedicatedAdapterResult(
                mainScript,
                mainScriptPath,
                new ProjectWebPreviewDedicatedAdapterResolution(
                    "reused_same_package",
                    "Dedicated adapter package hash matches the selected package.",
                    GetString(root, "adapter_version"),
                    request.PackageSha256,
                    mainScriptPath,
                    adapterSha256,
                    false,
                    ""));
            return true;
        }
        catch (JsonException)
        {
            return false;
        }
        catch (IOException)
        {
            return false;
        }
        catch (UnauthorizedAccessException)
        {
            return false;
        }
    }

    private static bool TryReadGeneratedScript(string outputPath, string rawOutput, out string script, out string? validationError)
    {
        script = File.Exists(outputPath) ? File.ReadAllText(outputPath, Encoding.UTF8) : rawOutput;
        script = StripMarkdownFence(script).Trim();
        if (!IsUsableGdScript(script, out validationError))
        {
            return false;
        }

        return true;
    }

    private static bool IsUsableGdScript(string script, out string? validationError)
    {
        validationError = null;
        if (string.IsNullOrWhiteSpace(script))
        {
            validationError = "Generated adapter script is empty.";
            return false;
        }

        if (script.Contains("```", StringComparison.Ordinal))
        {
            validationError = "Generated adapter script still contains Markdown fences.";
            return false;
        }

        if (!script.Contains("extends ", StringComparison.Ordinal) ||
            !script.Contains("func _ready", StringComparison.Ordinal))
        {
            validationError = "Generated adapter script does not look like a Godot script.";
            return false;
        }

        return true;
    }

    private static string StripMarkdownFence(string value)
    {
        var trimmed = value.Trim();
        var match = Regex.Match(trimmed, @"\A```(?:gdscript|gd)?\s*(.*?)\s*```\z", RegexOptions.Singleline | RegexOptions.IgnoreCase);
        return match.Success ? match.Groups[1].Value : trimmed;
    }

    private static object BuildManifest(
        ProjectWebPreviewDedicatedAdapterRequest request,
        string version,
        string source,
        string adapterSha256,
        string fallbackSourceSha256,
        bool codexInvoked,
        string resolutionStatus,
        string reason)
    {
        return new
        {
            schema_version = SchemaVersion,
            generator_version = GeneratorVersion,
            source,
            adapter_version = version,
            adapter_sha256 = adapterSha256,
            fallback_source_sha256 = fallbackSourceSha256,
            project_name = request.ProjectName,
            game_name = request.GameName,
            game_type_id = request.GameTypeId,
            converter_id = request.ConverterId,
            converter_mode = request.ConverterMode,
            package_file = request.PackageFile,
            package_sha256 = request.PackageSha256,
            codex_invoked = codexInvoked,
            resolution_status = resolutionStatus,
            reason,
            generated_utc = DateTimeOffset.UtcNow.ToString("O")
        };
    }

    private static async Task WriteAdapterAsync(
        string targetPath,
        string manifestPath,
        string mainScript,
        object manifest,
        CancellationToken cancellationToken)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(targetPath)!);
        await File.WriteAllTextAsync(targetPath, mainScript, new UTF8Encoding(false), cancellationToken);
        await File.WriteAllTextAsync(manifestPath, JsonSerializer.Serialize(manifest, JsonOptions), new UTF8Encoding(false), cancellationToken);
    }

    private static string BuildGenerationPrompt(ProjectWebPreviewDedicatedAdapterRequest request, string fallbackMainScript)
    {
        return $$"""
        You are generating a project-specific Godot 3.6 `Main.gd` adapter for a browser playable preview.

        Write a complete GDScript file only. Do not use Markdown fences. Do not explain.

        Hard requirements:
        - Godot 3.6 compatible GDScript.
        - The script is attached to a `Control` root scene created by Phase A.
        - It must load `res://preview-package-data.json` in `_ready()`.
        - It must produce an immediately playable browser preview using the package contract and semantic adapter data below.
        - It must preserve sandbox compatibility: no external network calls, no filesystem writes, no dynamic code loading.
        - It must expose keyboard/mouse interaction, clear visual state, and a playable loop derived from the package data.
        - Use the reference adapter as a structural fallback, but specialize labels, roles, loop state, interactions, camera/world layout, and feedback for this package.
        - Avoid hard-coding Towerdemo2 behavior unless the package data explicitly contains those nodes.
        - Return only the final `Main.gd` content.

        Package:
        - project_name: {{request.ProjectName}}
        - game_name: {{request.GameName}}
        - game_type_id: {{request.GameTypeId}}
        - game_type_guide: {{request.GameTypeGuide}}
        - converter_id: {{request.ConverterId}}
        - converter_mode: {{request.ConverterMode}}
        - package_file: {{request.PackageFile}}
        - package_sha256: {{request.PackageSha256}}
        - main_scene: {{request.MainScene}}
        - scenes: {{string.Join(", ", request.Scenes.Take(40))}}

        playable-preview-contract.json:
        {{TrimForPrompt(request.PlayablePreviewContractJson)}}

        semantic_adapter:
        {{TrimForPrompt(request.SemanticAdapterJson)}}

        web_preview_manifest:
        {{TrimForPrompt(request.WebPreviewManifestJson)}}

        Reference generic adapter:
        {{TrimForPrompt(fallbackMainScript, MaxReferenceScriptChars)}}
        """;
    }

    private static string ResolveUnderProject(string projectRoot, string relativePath)
    {
        var fullPath = Path.GetFullPath(Path.Combine(projectRoot, relativePath.Replace('/', Path.DirectorySeparatorChar)));
        if (!WorkspacePathPolicy.IsUnderRoot(projectRoot, fullPath))
        {
            throw new InvalidOperationException("Dedicated adapter path escaped project repository root.");
        }

        return fullPath;
    }

    private static string ReadOutputText(string outputPath, HostedProcessResult result)
    {
        if (File.Exists(outputPath))
        {
            return File.ReadAllText(outputPath, Encoding.UTF8);
        }

        return string.Join("\n", result.Stdout, result.Stderr);
    }

    private static string PackageVersionFromFileName(string packageFile)
    {
        return SanitizePathSegment(Path.GetFileNameWithoutExtension(packageFile));
    }

    private static string ComputeStringSha256(string value)
    {
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(value))).ToLowerInvariant();
    }

    private static bool JsonStringEquals(JsonElement root, string propertyName, string expected)
    {
        return root.ValueKind == JsonValueKind.Object &&
            root.TryGetProperty(propertyName, out var value) &&
            value.ValueKind == JsonValueKind.String &&
            string.Equals(value.GetString(), expected, StringComparison.Ordinal);
    }

    private static string GetString(JsonElement element, string propertyName)
    {
        return element.ValueKind == JsonValueKind.Object &&
            element.TryGetProperty(propertyName, out var property) &&
            property.ValueKind == JsonValueKind.String
            ? property.GetString() ?? ""
            : "";
    }

    private static string SanitizePathSegment(string value)
    {
        var builder = new StringBuilder(value.Length);
        foreach (var ch in value)
        {
            builder.Append(char.IsLetterOrDigit(ch) || ch is '-' or '_' or '.' ? ch : '-');
        }

        var sanitized = builder.ToString().Trim('-', '.', '_');
        return string.IsNullOrWhiteSpace(sanitized) ? "adapter" : sanitized;
    }

    private static string TrimForPrompt(string value, int maxChars = MaxPromptJsonChars)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "{}";
        }

        return value.Length <= maxChars ? value : value[..maxChars] + "\n...<truncated>";
    }

    private static string Tail(string value, int maxLength)
    {
        if (string.IsNullOrEmpty(value) || value.Length <= maxLength)
        {
            return value;
        }

        return value[^maxLength..];
    }

    private sealed record CodexAdapterRun(
        int ExitCode,
        string RawOutput,
        string RawOutputTail);
}

public sealed record ProjectWebPreviewDedicatedAdapterRequest(
    string AccountId,
    string RunId,
    ProjectSnapshot Project,
    string ProjectRoot,
    string PackageFile,
    string PackageSha256,
    string ProjectName,
    string GameName,
    string GameTypeId,
    string GameTypeGuide,
    string ConverterId,
    string ConverterMode,
    string? MainScene,
    IReadOnlyList<string> Scenes,
    string PlayablePreviewContractJson,
    string SemanticAdapterJson,
    string WebPreviewManifestJson);

public sealed record ProjectWebPreviewDedicatedAdapterResult(
    string MainScript,
    string AdapterPath,
    ProjectWebPreviewDedicatedAdapterResolution Resolution);

public sealed record ProjectWebPreviewDedicatedAdapterResolution(
    [property: JsonPropertyName("status")] string Status,
    [property: JsonPropertyName("reason")] string Reason,
    [property: JsonPropertyName("adapter_version")] string AdapterVersion,
    [property: JsonPropertyName("package_sha256")] string PackageSha256,
    [property: JsonPropertyName("adapter_path")] string AdapterPath,
    [property: JsonPropertyName("adapter_sha256")] string AdapterSha256,
    [property: JsonPropertyName("codex_invoked")] bool CodexInvoked,
    [property: JsonPropertyName("codex_output_tail")] string RawOutputTail);
