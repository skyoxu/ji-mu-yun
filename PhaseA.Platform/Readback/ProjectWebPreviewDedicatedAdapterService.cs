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
    public const string GeneratorVersion = "phasea-project-dedicated-godot3-adapter-v8";
    public const string MainScriptFileName = "Main.gd";
    public const string ManifestFileName = "adapter-manifest.json";

    private const string AdapterRootRelativePath = "exports/web-preview-dedicated-adapters";
    private const string WorkRootRelativePath = "exports/.web-preview-dedicated-adapter-work";
    private const int MaxPromptJsonChars = 80_000;
    private const int MaxReferenceScriptChars = 50_000;
    private const string ReasoningEffort = "medium";
    private static readonly TimeSpan CodexAdapterTotalTimeout = TimeSpan.FromMinutes(15);
    private static readonly TimeSpan CodexAdapterInactivityTimeout = TimeSpan.FromMinutes(8);

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
        TypeInfoResolver = new DefaultJsonTypeInfoResolver()
    };

    private readonly PhaseAPlatformOptions _options;
    private readonly IHostedProcessRunner? _processRunner;
    private readonly AiCodeMirrorKeyPoolService? _keyPoolService;
    private readonly HostedContextManifestIssuer? _contextManifestIssuer;
    private readonly HostedContextGatePolicy _contextGatePolicy;
    private readonly IHostedContextManifestValidator? _contextManifestValidator;
    private readonly bool _enableCodex;

    public ProjectWebPreviewDedicatedAdapterService(
        PhaseAPlatformOptions options,
        IHostedProcessRunner processRunner,
        AiCodeMirrorKeyPoolService? keyPoolService = null,
        HostedContextManifestIssuer? contextManifestIssuer = null,
        HostedContextGatePolicy? contextGatePolicy = null,
        IHostedContextManifestValidator? contextManifestValidator = null)
        : this(options, processRunner, keyPoolService, contextManifestIssuer, contextGatePolicy, contextManifestValidator, enableCodex: true)
    {
    }

    private ProjectWebPreviewDedicatedAdapterService(
        PhaseAPlatformOptions options,
        IHostedProcessRunner? processRunner,
        AiCodeMirrorKeyPoolService? keyPoolService,
        HostedContextManifestIssuer? contextManifestIssuer,
        HostedContextGatePolicy? contextGatePolicy,
        IHostedContextManifestValidator? contextManifestValidator,
        bool enableCodex)
    {
        _options = options;
        _processRunner = processRunner;
        _keyPoolService = keyPoolService;
        _contextManifestIssuer = contextManifestIssuer;
        _contextGatePolicy = contextGatePolicy ?? new HostedContextGatePolicy();
        _contextManifestValidator = contextManifestValidator;
        _enableCodex = enableCodex;
    }

    public static ProjectWebPreviewDedicatedAdapterService DeterministicOnly(PhaseAPlatformOptions options)
    {
        return new ProjectWebPreviewDedicatedAdapterService(options, null, null, null, null, null, enableCodex: false);
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
            var fallback = BuildTransientFallbackScript(request, fallbackMainScript);
            var transientFallbackSha256 = ComputeStringSha256(fallback);
            return new ProjectWebPreviewDedicatedAdapterResult(
                fallback,
                "",
                new ProjectWebPreviewDedicatedAdapterResolution(
                    "generated_by_fallback",
                    reason,
                    version,
                    request.PackageSha256,
                    "",
                    transientFallbackSha256,
                    true,
                    codexRun.RawOutputTail));
        }

        var deterministicFallback = BuildTransientFallbackScript(request, fallbackMainScript);
        var deterministicFallbackSha256 = ComputeStringSha256(deterministicFallback);
        return new ProjectWebPreviewDedicatedAdapterResult(
            deterministicFallback,
            "",
            new ProjectWebPreviewDedicatedAdapterResolution(
                "generated_deterministic",
                "Codex dedicated adapter generation is disabled.",
                version,
                request.PackageSha256,
                "",
                deterministicFallbackSha256,
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
        var prompt = BuildGenerationPrompt(request, fallbackMainScript);
        HostedContextEnvelope? envelope = null;
        if (_contextManifestIssuer is not null)
        {
            var snapshotId = ComputeStringSha256(string.Join("\n", request.Project.ProjectId, request.AccountId, request.RunId, request.PackageSha256, prompt));
            envelope = await _contextManifestIssuer.IssueAsync(new HostedContextManifestIssue(
                request.AccountId,
                request.Project.ProjectId,
                "codex:web-preview-dedicated-adapter",
                snapshotId,
                "web-preview-dedicated-adapter.v1",
                TimeSpan.FromMinutes(5),
                prompt,
                request.RunId,
                "workspace-write",
                [request.ProjectRoot],
                [outputPath]), cancellationToken);
        }

        var command = await CodexHostedProcessCommandFactory.BuildAsync(new CodexHostedProcessRequest(
            request.ProjectRoot,
            outputPath,
            prompt,
            model,
            ReasoningEffort,
            Json: false,
            Sandbox: "workspace-write",
            ExtraEnvironment: new Dictionary<string, string>
            {
                ["PATH"] = CodexHostedProcessCommandFactory.ResolvePathWithRipgrep()
            },
            OperationKey: "codex:web-preview-dedicated-adapter",
            ContextEnvelope: envelope),
            _contextGatePolicy,
            _contextManifestValidator,
            cancellationToken);
        var credential = await ResolveRuntimeCredentialAsync(request.AccountId, cancellationToken);
        var result = await _processRunner!.RunAsync(
            CodexHostedProcessCommandFactory.ApplyRuntime(command, credential)
                .WithRunId(request.RunId)
                .WithTimeouts(CodexAdapterTotalTimeout, CodexAdapterInactivityTimeout),
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
                !JsonStringEquals(root, "source", "codex-dedicated-adapter") ||
                !JsonStringEquals(root, "resolution_status", "generated_by_codex") ||
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
        script = NormalizeGodot3Compatibility(StripMarkdownFence(script).Trim());
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

    private static string BuildTransientFallbackScript(ProjectWebPreviewDedicatedAdapterRequest request, string fallbackMainScript)
    {
        if (!fallbackMainScript.Contains("var adapter_style = \"generic\"", StringComparison.Ordinal))
        {
            return fallbackMainScript;
        }

        return fallbackMainScript
            .Replace("elif adapter_style == \"tower-defense\":", "elif false:", StringComparison.Ordinal)
            .Replace("if adapter_style == \"tower-defense\":", "if false:", StringComparison.Ordinal)
            .Replace("last_action = \"放置防御塔，当前火力提升\"", "last_action = \"执行项目动作，当前进度提升\"", StringComparison.Ordinal)
            .Replace("last_action = \"下一波敌人开始推进\"", "last_action = \"下一阶段开始推进\"", StringComparison.Ordinal)
            .Replace("return \"塔防试玩：防御塔 %d  波次 %d  敌军生命 %d  最近动作：%s\" % [tower_count, wave, encounter_hp, last_action]", "return \"项目试玩：进度 %d  阶段 %d  挑战值 %d  最近动作：%s\" % [tower_count, wave, encounter_hp, last_action]", StringComparison.Ordinal);
    }

    private static string StripMarkdownFence(string value)
    {
        var trimmed = value.Trim();
        var match = Regex.Match(trimmed, @"\A```(?:gdscript|gd)?\s*(.*?)\s*```\z", RegexOptions.Singleline | RegexOptions.IgnoreCase);
        return match.Success ? match.Groups[1].Value : trimmed;
    }

    private static string NormalizeGodot3Compatibility(string script)
    {
        if (!Regex.IsMatch(script, @"(?m)^\s*var\s+floor\s*="))
        {
            return script;
        }

        return Regex.Replace(script, @"\bfloor\b", "floor_node");
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
        - The script is attached to a root scene created by Phase A. Phase A will choose the root node type from your `extends` line.
        - It must load `res://preview-package-data.json` in `_ready()`.
        - It must produce an immediately playable browser preview using the package contract and semantic adapter data below.
        - It must preserve sandbox compatibility: no external network calls, no filesystem writes, no dynamic code loading.
        - It must expose keyboard/mouse interaction, clear visual state, and a playable loop derived from the package data.
        - Use the reference adapter as a structural fallback, but specialize labels, roles, loop state, interactions, camera/world layout, and feedback for this package.
        - For action, shooter, extraction, survival, RPG exploration, or movement/combat previews, use Godot physics instead of hand-rolled position-only simulation:
          - Prefer `extends Node2D` for the adapter scene root and create a child `KinematicBody2D` player. This mirrors package scenes whose root owns a world loop, HUD, player, enemies, loot, and extraction zones.
          - Use `extends KinematicBody2D` as the scene root only for very simple player-only previews with no sibling world, enemies, walls, or zones.
          - Create `CollisionShape2D` children for the player and important interactable/threat entities.
          - Use `_physics_process(delta)` for movement and `move_and_slide` or `move_and_collide` on KinematicBody2D nodes.
          - Use `Area2D` plus `CollisionShape2D`, `overlaps_body`, or distance-gated physics bodies for pickup, interact, attack, and threat zones.
          - Keep UI in a `CanvasLayer`/`Control` child instead of making the whole adapter a `Control`.
          - Do not create physics bodies under a parent that is only attached with `call_deferred("add_child", ...)` and then move them in the same frame; attach physics roots synchronously before running movement/collision logic.
          - Do not use `get_parent().add_child(...)` to create sibling physics bodies from the adapter root. Keep world, enemies, walls, loot, extraction, and projectiles under nodes owned by the adapter root so every moving body is inside the same active 2D world.
          - Before calling `move_and_slide` or `move_and_collide` on any non-root KinematicBody2D, guard that the body is still valid and `is_inside_tree()`.
        - Use `extends Control` only for packages that are clearly menu/card/dialogue-only and do not need movement, collision, combat, or spatial interaction.
        - Avoid GDScript built-in function names such as `floor`, `round`, `min`, `max`, `range`, `load`, and `print` as variable names.
        - If `web_preview_manifest.visual_asset_hints` contains `preview_resource_path` values, create Sprite or TextureRect nodes so the preview resembles the package art instead of abstract shapes.
        - Godot 3 HTML5 exports include PreviewAssets as raw image files. For `res://PreviewAssets/...` paths, do not rely only on `load(path)`. Use a reusable texture helper that first tries `load(path)`, then falls back to `Image.new().load(path)` plus `ImageTexture.new().create_from_image(image)` so raw PNG/JPG/WebP assets work in browser exports without console loader errors.
        - If `web_preview_manifest.input_map_hints` or `script_behavior_hints.input_actions` contain project action names, mirror those controls in `_input`/`_physics_process` and HUD text instead of inventing unrelated controls.
        - For movement/combat/extraction/shooter packages, do not implement click-to-move unless script_behavior_hints or input_map_hints explicitly show click/touch movement. Mouse left should fire/attack when the project has fire/shoot/attack behavior; right mouse may aim/secondary action only if useful.
        - For movement/combat/extraction/shooter packages, use WASD/arrow movement, mouse aim, primary fire, reload, interact, and dash mappings inferred from project action names and script excerpts. Do not add numbered selection shortcuts or visible command buttons unless the selected playable scene is menu/card/dialogue-only.
        - For movement/combat/extraction/shooter packages, the generated script must not contain KEY_1, KEY_2, KEY_3, focus_scene_marker, select_marker, Button.new(), or click-to-select/focus mechanics. Those are menu/debug affordances, not gameplay controls.
        - Treat semantic_adapter.entities as lower priority than scene_graph_hints and script_behavior_hints. Ignore semantic entities that come from unrelated template, settings, demo, menu, or debug UI scenes when a more relevant project/prototype scene exists.
        - Do not turn Button, VBoxContainer, Settings, MainMenu, Publish, SaveLoad, Log, AddScore, LoseHp, or generic HUD/debug nodes into world targets for action previews. Keep HUD as status/progress only.
        - Threat/enemy entities in action previews must actively chase or pressure the player and visibly reduce HP/armor when in range, using cooldowns and clear feedback. Avoid passive markers that only react when clicked.
        - If `web_preview_manifest.script_behavior_hints` mention movement, combat, interaction, animation, camera, or sprite behavior, use those hints as the primary behavior model before falling back to generic exploration.
        - If `web_preview_manifest.scene_graph_hints` exists, mirror the package's scene root type, important node names, script-bound entities, physics node types, and texture-bound visual nodes before inventing your own entity model.
        - Avoid hard-coding Towerdemo2 behavior unless the package data explicitly contains those nodes.
        - Return only the final `Main.gd` content.

        Package:
        - project_name: {{request.ProjectName}}
        - game_name: {{request.GameName}}
        - game_type_source: {{request.Project.GameTypeSource}}
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
