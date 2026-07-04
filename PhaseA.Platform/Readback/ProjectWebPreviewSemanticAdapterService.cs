using System.Security.Cryptography;
using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.Json.Serialization;
using System.Text.Json.Serialization.Metadata;
using System.Text.RegularExpressions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Workspaces;

namespace PhaseA.Platform.Readback;

public sealed class ProjectWebPreviewSemanticAdapterService
{
    public const string SchemaVersion = "phasea-playable-preview-semantic-adapter-v1";
    public const string CompatibilityId = "phasea-generic-web-preview-semantic-adapter-v2";
    public const string AdapterFileName = "playable-preview-semantic-adapter.json";

    private const string AdapterRootRelativePath = "exports/web-preview-semantic-adapters";
    private const string WorkRootRelativePath = "exports/.web-preview-semantic-adapter-work";
    private const int MaxPromptJsonChars = 80_000;
    private const string ReasoningEffort = "low";

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

    public ProjectWebPreviewSemanticAdapterService(
        PhaseAPlatformOptions options,
        IHostedProcessRunner processRunner,
        AiCodeMirrorKeyPoolService? keyPoolService = null)
        : this(options, processRunner, keyPoolService, enableCodex: true)
    {
    }

    private ProjectWebPreviewSemanticAdapterService(
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

    public static ProjectWebPreviewSemanticAdapterService DeterministicOnly(PhaseAPlatformOptions options)
    {
        return new ProjectWebPreviewSemanticAdapterService(options, null, null, enableCodex: false);
    }

    public async Task<ProjectWebPreviewSemanticAdapterResult> ResolveAsync(
        ProjectWebPreviewSemanticAdapterRequest request,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(request);
        var projectRoot = Path.GetFullPath(request.ProjectRoot);
        if (!WorkspacePathPolicy.IsUnderRoot(_options.HostedWorkspaceRoot, projectRoot))
        {
            throw new InvalidOperationException("Project repository path escaped the hosted workspace root.");
        }

        var adapterRoot = ResolveUnderProject(projectRoot, AdapterRootRelativePath);
        Directory.CreateDirectory(adapterRoot);

        var existing = LoadExistingAdapters(adapterRoot);
        var samePackage = existing.FirstOrDefault(item =>
            string.Equals(item.PackageSha256, request.PackageSha256, StringComparison.OrdinalIgnoreCase));
        if (samePackage is not null)
        {
            return new ProjectWebPreviewSemanticAdapterResult(
                samePackage.Adapter,
                "reused_same_package",
                samePackage.Path,
                new ProjectWebPreviewSemanticAdapterResolution(
                    "reused_same_package",
                    "Adapter package hash matches the selected package.",
                    samePackage.AdapterVersion,
                    samePackage.PackageSha256,
                    samePackage.Path,
                    false,
                    "none",
                    ""));
        }

        var previous = existing
            .OrderByDescending(item => item.LastWriteUtc)
            .FirstOrDefault();
        if (previous is not null)
        {
            var decision = await DecideReuseAsync(request, previous, cancellationToken);
            if (string.Equals(decision.Decision, "reuse", StringComparison.Ordinal))
            {
                return new ProjectWebPreviewSemanticAdapterResult(
                    previous.Adapter,
                    "reused_by_codex_decision",
                    previous.Path,
                    new ProjectWebPreviewSemanticAdapterResolution(
                        "reused_by_codex_decision",
                        decision.Reason,
                        previous.AdapterVersion,
                        previous.PackageSha256,
                        previous.Path,
                        decision.CodexInvoked,
                        decision.Decision,
                        decision.RawOutputTail));
            }
        }

        var generated = await GenerateAsync(request, previous, cancellationToken);
        return generated;
    }

    private async Task<ProjectWebPreviewSemanticAdapterResult> GenerateAsync(
        ProjectWebPreviewSemanticAdapterRequest request,
        ExistingSemanticAdapter? previous,
        CancellationToken cancellationToken)
    {
        var version = PackageVersionFromFileName(request.PackageFile);
        var targetDirectory = ResolveUnderProject(request.ProjectRoot, $"{AdapterRootRelativePath}/{SanitizePathSegment(version)}");
        Directory.CreateDirectory(targetDirectory);
        var targetPath = Path.Combine(targetDirectory, AdapterFileName);
        var workDirectory = ResolveUnderProject(request.ProjectRoot, $"{WorkRootRelativePath}/{request.RunId}");
        Directory.CreateDirectory(workDirectory);
        var outputPath = Path.Combine(workDirectory, $"semantic-adapter-{SanitizePathSegment(version)}.json");

        CodexAdapterRun? codexRun = null;
        if (_enableCodex && _processRunner is not null)
        {
            try
            {
                codexRun = await RunCodexAsync(
                    request,
                    outputPath,
                    BuildGenerationPrompt(request, previous),
                    "workspace-write",
                    cancellationToken);
            }
            catch (Exception ex) when (ex is not OperationCanceledException)
            {
                codexRun = new CodexAdapterRun(-1, ex.ToString(), Tail(ex.ToString(), 2000));
            }

            string? validationError = null;
            if (codexRun.ExitCode == 0 &&
                TryParseAdapterFromFileOrOutput(outputPath, codexRun, request, out var generatedAdapter, out validationError))
            {
                await WriteAdapterAsync(targetPath, generatedAdapter, cancellationToken);
                return new ProjectWebPreviewSemanticAdapterResult(
                    generatedAdapter,
                    "generated_by_codex",
                    targetPath,
                    new ProjectWebPreviewSemanticAdapterResolution(
                        "generated_by_codex",
                        "Codex generated a package-versioned semantic adapter.",
                        version,
                        request.PackageSha256,
                        targetPath,
                        true,
                        "regenerate",
                        codexRun.RawOutputTail));
            }

            var reason = validationError ?? $"Codex exited with {codexRun.ExitCode}.";
            var fallback = BuildFallbackAdapter(request, version, "codex_generation_fallback", reason);
            await WriteAdapterAsync(targetPath, fallback, cancellationToken);
            return new ProjectWebPreviewSemanticAdapterResult(
                fallback,
                "generated_by_fallback",
                targetPath,
                new ProjectWebPreviewSemanticAdapterResolution(
                    "generated_by_fallback",
                    reason,
                    version,
                    request.PackageSha256,
                    targetPath,
                    true,
                    "regenerate",
                    codexRun.RawOutputTail));
        }

        var deterministic = BuildFallbackAdapter(request, version, "deterministic_generation", "Codex semantic adapter generation is disabled for this service instance.");
        await WriteAdapterAsync(targetPath, deterministic, cancellationToken);
        return new ProjectWebPreviewSemanticAdapterResult(
            deterministic,
            "generated_deterministic",
            targetPath,
            new ProjectWebPreviewSemanticAdapterResolution(
                "generated_deterministic",
                "Codex semantic adapter generation is disabled for this service instance.",
                version,
                request.PackageSha256,
                targetPath,
                false,
                "regenerate",
                ""));
    }

    private async Task<AdapterDecision> DecideReuseAsync(
        ProjectWebPreviewSemanticAdapterRequest request,
        ExistingSemanticAdapter previous,
        CancellationToken cancellationToken)
    {
        if (!_enableCodex || _processRunner is null)
        {
            return new AdapterDecision("regenerate", "Codex adapter reuse decision is disabled for this service instance.", false, "");
        }

        var workDirectory = ResolveUnderProject(request.ProjectRoot, $"{WorkRootRelativePath}/{request.RunId}");
        Directory.CreateDirectory(workDirectory);
        var outputPath = Path.Combine(workDirectory, "semantic-adapter-decision.json");
        CodexAdapterRun run;
        try
        {
            run = await RunCodexAsync(
                request,
                outputPath,
                BuildDecisionPrompt(request, previous),
                "read-only",
                cancellationToken);
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            return new AdapterDecision("regenerate", $"Codex decision failed; regenerate conservatively. {ex.Message}", true, Tail(ex.ToString(), 2000));
        }

        if (run.ExitCode != 0)
        {
            return new AdapterDecision("regenerate", $"Codex decision exited with {run.ExitCode}; regenerate conservatively.", true, run.RawOutputTail);
        }

        var raw = ReadOutputText(outputPath, run);
        var json = ExtractJsonObject(raw);
        if (json is null)
        {
            return new AdapterDecision("regenerate", "Codex decision did not return a JSON object; regenerate conservatively.", true, Tail(raw, 2000));
        }

        try
        {
            using var doc = JsonDocument.Parse(json);
            var decision = GetString(doc.RootElement, "decision").ToLowerInvariant();
            var reason = FirstNonEmpty(GetString(doc.RootElement, "reason"), "Codex decision returned no reason.");
            if (decision is "reuse" or "regenerate")
            {
                return new AdapterDecision(decision, reason, true, Tail(raw, 2000));
            }
        }
        catch (JsonException)
        {
        }

        return new AdapterDecision("regenerate", "Codex decision JSON was invalid; regenerate conservatively.", true, Tail(raw, 2000));
    }

    private async Task<CodexAdapterRun> RunCodexAsync(
        ProjectWebPreviewSemanticAdapterRequest request,
        string outputPath,
        string prompt,
        string sandbox,
        CancellationToken cancellationToken)
    {
        var model = CodexModelCatalog.DefaultModel();
        var command = CodexHostedProcessCommandFactory.Build(new CodexHostedProcessRequest(
            request.ProjectRoot,
            outputPath,
            prompt,
            model,
            ReasoningEffort,
            Sandbox: sandbox,
            ExtraEnvironment: new Dictionary<string, string>
            {
                ["PATH"] = CodexHostedProcessCommandFactory.ResolvePathWithRipgrep()
            }));
        var credential = await ResolveRuntimeCredentialAsync(request.AccountId, cancellationToken);
        var result = await _processRunner!.RunAsync(
            CodexHostedProcessCommandFactory.ApplyRuntime(command, credential)
                .WithRunId(request.RunId)
                .WithTimeouts(TimeSpan.FromMinutes(5), TimeSpan.FromMinutes(2)),
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

    private static bool TryParseAdapterFromFileOrOutput(
        string outputPath,
        CodexAdapterRun run,
        ProjectWebPreviewSemanticAdapterRequest request,
        out JsonElement adapter,
        out string? validationError)
    {
        var raw = ReadOutputText(outputPath, run.RawOutput);
        var json = ExtractJsonObject(raw);
        if (json is null)
        {
            adapter = default;
            validationError = "Codex adapter output did not contain a JSON object.";
            return false;
        }

        try
        {
            using var document = JsonDocument.Parse(json);
            if (!ValidateAdapter(document.RootElement, request, out validationError))
            {
                adapter = default;
                return false;
            }

            adapter = document.RootElement.Clone();
            return true;
        }
        catch (JsonException ex)
        {
            adapter = default;
            validationError = ex.Message;
            return false;
        }
    }

    private static bool ValidateAdapter(JsonElement root, ProjectWebPreviewSemanticAdapterRequest request, out string? error)
    {
        if (root.ValueKind != JsonValueKind.Object)
        {
            error = "Adapter root is not an object.";
            return false;
        }

        if (!string.Equals(GetString(root, "schema_version"), SchemaVersion, StringComparison.Ordinal))
        {
            error = "Adapter schema_version is invalid.";
            return false;
        }

        if (!string.Equals(GetString(root, "compatibility_id"), CompatibilityId, StringComparison.Ordinal))
        {
            error = "Adapter compatibility_id is invalid.";
            return false;
        }

        if (!string.Equals(GetString(root, "package_sha256"), request.PackageSha256, StringComparison.OrdinalIgnoreCase))
        {
            error = "Adapter package_sha256 does not match the selected package.";
            return false;
        }

        if (string.IsNullOrWhiteSpace(GetString(root, "adapter_version")))
        {
            error = "Adapter version is empty.";
            return false;
        }

        if (!root.TryGetProperty("entities", out var entities) || entities.ValueKind != JsonValueKind.Array)
        {
            error = "Adapter entities must be an array.";
            return false;
        }

        error = null;
        return true;
    }

    private static JsonElement BuildFallbackAdapter(
        ProjectWebPreviewSemanticAdapterRequest request,
        string version,
        string generationMode,
        string warning)
    {
        var contract = ParseObjectOrEmpty(request.PlayablePreviewContractJson);
        var entities = CloneArrayOrEmpty(contract, "entities");
        if (entities.Count == 0)
        {
            foreach (var scene in request.Scenes.Take(20).Select((value, index) => new { value, index }))
            {
                entities.Add(new JsonObject
                {
                    ["id"] = $"scene_{scene.index + 1}",
                    ["label"] = SceneLabel(scene.value, scene.index),
                    ["role"] = scene.index == 0 ? "entry_scene" : "scene_marker",
                    ["scene"] = scene.value,
                    ["objective"] = scene.index == 0 ? "Enter the playable route." : "Inspect this package scene.",
                    ["priority"] = scene.index + 1
                });
            }
        }
        EnrichRuntimeProfiles(entities);

        var adapter = new JsonObject
        {
            ["schema_version"] = SchemaVersion,
            ["source"] = "phasea-web-preview-semantic-adapter-route",
            ["compatibility_id"] = CompatibilityId,
            ["adapter_version"] = version,
            ["package_version"] = version,
            ["package_file"] = request.PackageFile,
            ["package_sha256"] = request.PackageSha256,
            ["package_size_bytes"] = request.PackageSizeBytes,
            ["project_id"] = request.Project.ProjectId,
            ["project_name"] = request.Project.Name,
            ["game_name"] = request.GameName,
            ["game_type_id"] = request.GameTypeId,
            ["game_type_guide"] = request.GameTypeGuide,
            ["main_scene"] = request.MainScene ?? "",
            ["base_contract_sha256"] = ComputeStringSha256(request.PlayablePreviewContractJson),
            ["generated_utc"] = DateTimeOffset.UtcNow.ToString("O"),
            ["generation"] = new JsonObject
            {
                ["mode"] = generationMode,
                ["warning"] = warning
            },
            ["semantic_profile"] = new JsonObject
            {
                ["gameplay_label"] = FirstNonEmpty(request.GameName, request.Project.Name, "Godot Package"),
                ["playable_surface"] = ResolvePlayableSurface(request.WebPreviewManifestJson),
                ["fidelity_intent"] = "generic_converter_plus_project_semantic_adapter",
                ["first_loop_path"] = BuildFirstLoopPath(entities),
                ["ui_hud_mapping"] = new JsonArray("progress", "energy", "pressure", "reward", "score")
            },
            ["runtime_tuning"] = new JsonObject
            {
                ["movement_speed"] = 5.2,
                ["pressure_speed"] = 1.35,
                ["attack_range"] = ResolveAttackRange(entities),
                ["contact_range"] = 1.15,
                ["skill_targets"] = 2
            },
            ["entities"] = entities,
            ["state_model"] = CloneArrayOrEmpty(contract, "state_model"),
            ["role_interactions"] = CloneArrayOrEmpty(contract, "role_interactions"),
            ["input_actions"] = BuildSemanticInputActions(contract, entities),
            ["win_conditions"] = CloneArrayOrEmpty(contract, "win_conditions"),
            ["loss_conditions"] = CloneArrayOrEmpty(contract, "loss_conditions"),
            ["warnings"] = new JsonArray(warning)
        };

        using var document = JsonDocument.Parse(adapter.ToJsonString(JsonOptions));
        return document.RootElement.Clone();
    }

    private static void EnrichRuntimeProfiles(JsonArray entities)
    {
        foreach (var entity in entities.OfType<JsonObject>())
        {
            var role = entity["role"]?.GetValue<string>() ?? "";
            if (entity["runtime_profile"] is JsonObject)
            {
                continue;
            }

            entity["runtime_profile"] = role switch
            {
                "player_start" => new JsonObject
                {
                    ["shape"] = "capsule",
                    ["movement_speed"] = 5.2
                },
                "pressure_source" => new JsonObject
                {
                    ["shape"] = "capsule",
                    ["pressure_speed"] = 1.35,
                    ["contact_range"] = 1.15,
                    ["hp"] = 1
                },
                "action" => new JsonObject
                {
                    ["shape"] = "trigger",
                    ["attack_range"] = ResolveRangeHint(entity, 3.2)
                },
                "reward" => new JsonObject
                {
                    ["shape"] = "reward",
                    ["contact_range"] = 1.4
                },
                _ => new JsonObject
                {
                    ["shape"] = "marker"
                }
            };
        }
    }

    private static double ResolveAttackRange(JsonArray entities)
    {
        var range = entities
            .OfType<JsonObject>()
            .Where(entity => string.Equals(entity["role"]?.GetValue<string>(), "action", StringComparison.Ordinal))
            .Select(entity => ResolveRangeHint(entity, 0))
            .DefaultIfEmpty(0)
            .Max();
        return range > 0 ? Math.Round(Math.Clamp(range, 2.4, 6.5), 2) : 3.2;
    }

    private static double ResolveRangeHint(JsonObject entity, double fallback)
    {
        if (entity.TryGetPropertyValue("range_hint", out var node) &&
            node is JsonValue value &&
            value.TryGetValue<double>(out var range) &&
            range > 0)
        {
            return Math.Round(Math.Clamp(range, 1.2, 8.0), 2);
        }

        return fallback;
    }

    private static JsonArray BuildFirstLoopPath(JsonArray entities)
    {
        var result = new JsonArray();
        foreach (var entity in entities.Take(8))
        {
            if (entity is not JsonObject obj)
            {
                continue;
            }

            var role = obj["role"]?.GetValue<string>() ?? "entity";
            var label = obj["label"]?.GetValue<string>() ?? role;
            result.Add(new JsonObject
            {
                ["role"] = role,
                ["label"] = label,
                ["action"] = role switch
                {
                    "player_start" => "spawn_and_move",
                    "pressure_source" => "resolve_pressure",
                    "action" => "activate_action",
                    "reward" => "collect_reward",
                    "ui_action" => "press_ui",
                    _ => "inspect"
                }
            });
        }

        return result;
    }

    private static JsonArray BuildSemanticInputActions(JsonObject contract, JsonArray entities)
    {
        var actions = CloneArrayOrEmpty(contract, "input_actions");
        var entityLabels = entities
            .OfType<JsonObject>()
            .Select(item => (item["label"]?.GetValue<string>() ?? "") + " " + (item["role"]?.GetValue<string>() ?? ""))
            .ToArray();

        if (entityLabels.Any(label => ContainsAny(label, "attack", "weapon", "hit", "slash", "shoot")))
        {
            AddInputActionIfMissing(actions, "basic_attack", ["MouseLeft", "Space"], "Trigger the package-derived primary action entity.");
        }

        if (entityLabels.Any(label => ContainsAny(label, "skill", "cast", "roll", "dash", "dodge")))
        {
            AddInputActionIfMissing(actions, "skill_or_roll", ["MouseRight", "Q", "E", "Shift"], "Trigger the package-derived skill, cast, roll, or dodge action.");
        }

        if (entityLabels.Any(label => ContainsAny(label, "reward", "choice", "door", "shop", "chest")))
        {
            AddInputActionIfMissing(actions, "choice", ["1", "2", "3", "Enter"], "Select or collect the package-derived reward/choice entity.");
        }

        if (entityLabels.Any(label => ContainsAny(label, "start", "begin", "play")))
        {
            AddInputActionIfMissing(actions, "start", ["Enter", "MouseLeft"], "Activate the package-derived start action.");
        }

        if (entityLabels.Any(label => ContainsAny(label, "retry", "restart")))
        {
            AddInputActionIfMissing(actions, "retry", ["R", "MouseLeft"], "Activate the package-derived retry action.");
        }

        return actions;
    }

    private static void AddInputActionIfMissing(JsonArray actions, string action, string[] inputs, string behavior)
    {
        if (actions.OfType<JsonObject>().Any(item => string.Equals(item["action"]?.GetValue<string>(), action, StringComparison.OrdinalIgnoreCase)))
        {
            return;
        }

        var inputArray = new JsonArray();
        foreach (var input in inputs)
        {
            inputArray.Add(input);
        }

        actions.Add(new JsonObject
        {
            ["action"] = action,
            ["inputs"] = inputArray,
            ["behavior"] = behavior
        });
    }

    private static bool ContainsAny(string value, params string[] needles)
    {
        return needles.Any(needle => value.Contains(needle, StringComparison.OrdinalIgnoreCase));
    }

    private static string BuildGenerationPrompt(ProjectWebPreviewSemanticAdapterRequest request, ExistingSemanticAdapter? previous)
    {
        return $"""
            You are generating a JSON semantic adapter for the Phase A generic Godot browser preview route.

            Return only one JSON object. Do not include Markdown.

            Required schema:
            - schema_version: "{SchemaVersion}"
            - compatibility_id: "{CompatibilityId}"
            - adapter_version: "{PackageVersionFromFileName(request.PackageFile)}"
            - package_version: "{PackageVersionFromFileName(request.PackageFile)}"
            - package_file: "{EscapeForPrompt(request.PackageFile)}"
            - package_sha256: "{request.PackageSha256}"
            - project_id, project_name, game_name, game_type_id, game_type_guide, main_scene
            - source: "codex-semantic-adapter"
            - generated_utc: ISO-8601 UTC
            - generation: object with mode, notes, previous_adapter_version
            - semantic_profile: object with gameplay_label, playable_surface, fidelity_intent, first_loop_path, ui_hud_mapping
            - runtime_tuning: object with movement_speed, pressure_speed, attack_range, contact_range, and skill_targets.
            - entities: array of semantic entities. Preserve package-derived entities and their world_position/local_position/target_position/range_hint fields; improve labels, roles, objectives, priority, and runtime_profile.
            - state_model, role_interactions, input_actions, win_conditions, loss_conditions: arrays compatible with the base contract.
            - warnings: array of strings.

            Constraints:
            - Do not infer "tower-defense" from the project name or file name.
            - Do not emit executable code.
            - Keep roles project-semantic and generic: player_start, pressure_source, action, reward, ui_action, feedback, play_space, buildable_unit, entry_scene, scene_marker.
            - Use web_preview_manifest.scene_graph_hints and script_behavior_hints to identify the first playable loop. Prefer scenes and scripts that match the project/game/prototype path over generic template, settings, demo, menu, or test scenes.
            - For movement/combat/extraction/shooter packages, do not promote Button, VBoxContainer, Settings, MainMenu, Publish, SaveLoad, Log, AddScore, LoseHp, or other menu/debug UI nodes into gameplay entities unless those nodes are in the selected playable scene. Keep such UI nodes in semantic_profile.ui_hud_mapping or warnings instead.
            - input_actions should use project action IDs from web_preview_manifest.input_map_hints and script_behavior_hints.input_actions whenever available. If action IDs include move/fire/shoot/reload/interact/dash/use semantics, map them to common browser controls: WASD/arrows movement, mouse/primary fire, R reload, E or Space interact, Shift dash.
            - Do not invent click-to-move, numbered selection shortcuts, or menu buttons for movement/combat/extraction/shooter packages unless the package scripts explicitly contain that interaction.
            - input_actions may use project-semantic action IDs derived from package entity labels only when the package does not expose input-map or script action IDs. Do not derive these from the project name.
            - Use world_position from the package contract for spawn/layout whenever present. If you add runtime_profile, keep it data-only: shape, movement_speed, pressure_speed, attack_range, contact_range, hp, damage.
            - Prefer the package contract over filename guessing.
            - The adapter must make the generic browser preview feel closer to the packaged Godot prototype by selecting the right first loop, HUD concepts, roles, and feedback.

            Project:
            {CompactJson(new
            {
                project_id = request.Project.ProjectId,
                project_name = request.Project.Name,
                game_name = request.GameName,
                game_type_source = request.GameTypeSource,
                game_type_id = request.GameTypeId,
                game_type_guide = request.GameTypeGuide,
                package_file = request.PackageFile,
                package_sha256 = request.PackageSha256,
                package_size_bytes = request.PackageSizeBytes,
                main_scene = request.MainScene,
                scenes = request.Scenes.Take(40).ToArray()
            })}

            Web preview manifest:
            {TrimForPrompt(request.WebPreviewManifestJson)}

            Base playable preview contract:
            {TrimForPrompt(request.PlayablePreviewContractJson)}

            Previous adapter summary:
            {(previous is null ? "none" : TrimForPrompt(previous.Adapter.GetRawText()))}
            """;
    }

    private static string BuildDecisionPrompt(ProjectWebPreviewSemanticAdapterRequest request, ExistingSemanticAdapter previous)
    {
        return $"""
            Decide whether an existing Phase A web-preview semantic adapter can be reused for a new package.

            Return only one JSON object with string fields named decision and reason.

            Reuse only if the old adapter's roles, first loop, HUD/state concepts, and entity mappings still fit the new package contract.
            Regenerate if scene/entity roles changed, gameplay loop changed, package contract changed materially, or package identity differs in a way that can affect browser preview behavior.
            Do not infer game type from file names.

            New package:
            {CompactJson(new
            {
                project_id = request.Project.ProjectId,
                project_name = request.Project.Name,
                game_name = request.GameName,
                game_type_source = request.GameTypeSource,
                game_type_id = request.GameTypeId,
                game_type_guide = request.GameTypeGuide,
                package_file = request.PackageFile,
                package_sha256 = request.PackageSha256,
                package_size_bytes = request.PackageSizeBytes,
                main_scene = request.MainScene,
                scenes = request.Scenes.Take(40).ToArray()
            })}

            New base playable preview contract:
            {TrimForPrompt(request.PlayablePreviewContractJson)}

            Existing adapter:
            {TrimForPrompt(previous.Adapter.GetRawText())}
            """;
    }

    private static IReadOnlyList<ExistingSemanticAdapter> LoadExistingAdapters(string adapterRoot)
    {
        if (!Directory.Exists(adapterRoot))
        {
            return Array.Empty<ExistingSemanticAdapter>();
        }

        var result = new List<ExistingSemanticAdapter>();
        foreach (var path in Directory.EnumerateFiles(adapterRoot, AdapterFileName, SearchOption.AllDirectories))
        {
            try
            {
                using var document = JsonDocument.Parse(File.ReadAllText(path, Encoding.UTF8));
                var root = document.RootElement.Clone();
                if (!string.Equals(GetString(root, "schema_version"), SchemaVersion, StringComparison.Ordinal) ||
                    !string.Equals(GetString(root, "compatibility_id"), CompatibilityId, StringComparison.Ordinal))
                {
                    continue;
                }

                result.Add(new ExistingSemanticAdapter(
                    path,
                    root,
                    GetString(root, "adapter_version"),
                    GetString(root, "package_sha256"),
                    File.GetLastWriteTimeUtc(path)));
            }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or JsonException)
            {
            }
        }

        return result;
    }

    private static async Task WriteAdapterAsync(string path, JsonElement adapter, CancellationToken cancellationToken)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        await File.WriteAllTextAsync(path, JsonSerializer.Serialize(adapter, JsonOptions), new UTF8Encoding(false), cancellationToken);
    }

    private static string ResolveUnderProject(string projectRoot, string relativePath)
    {
        var full = Path.GetFullPath(Path.Combine(projectRoot, relativePath.Replace('/', Path.DirectorySeparatorChar)));
        if (!WorkspacePathPolicy.IsUnderRoot(projectRoot, full))
        {
            throw new InvalidOperationException("Resolved semantic adapter path escaped the project root.");
        }

        return full;
    }

    private static JsonObject ParseObjectOrEmpty(string json)
    {
        if (string.IsNullOrWhiteSpace(json))
        {
            return new JsonObject();
        }

        try
        {
            return JsonNode.Parse(json) as JsonObject ?? new JsonObject();
        }
        catch (JsonException)
        {
            return new JsonObject();
        }
    }

    private static JsonArray CloneArrayOrEmpty(JsonObject obj, string propertyName)
    {
        if (obj[propertyName] is not JsonArray array)
        {
            return new JsonArray();
        }

        return JsonNode.Parse(array.ToJsonString()) as JsonArray ?? new JsonArray();
    }

    private static string ResolvePlayableSurface(string manifestJson)
    {
        try
        {
            using var document = JsonDocument.Parse(manifestJson);
            if (document.RootElement.TryGetProperty("conversion_contract", out var contract))
            {
                return GetString(contract, "playable_surface");
            }
        }
        catch (JsonException)
        {
        }

        return "generic_package_exploration_shell";
    }

    private static string ReadOutputText(string outputPath, CodexAdapterRun run)
    {
        return ReadOutputText(outputPath, run.RawOutput);
    }

    private static string ReadOutputText(string outputPath, HostedProcessResult result)
    {
        return ReadOutputText(outputPath, string.Join("\n", result.Stdout, result.Stderr));
    }

    private static string ReadOutputText(string outputPath, string fallback)
    {
        try
        {
            if (File.Exists(outputPath))
            {
                return File.ReadAllText(outputPath, Encoding.UTF8);
            }
        }
        catch (IOException)
        {
        }
        catch (UnauthorizedAccessException)
        {
        }

        return fallback;
    }

    private static string? ExtractJsonObject(string text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return null;
        }

        var fenced = Regex.Match(text, "```(?:json)?\\s*(?<json>\\{.*?\\})\\s*```", RegexOptions.Singleline | RegexOptions.IgnoreCase);
        if (fenced.Success)
        {
            return fenced.Groups["json"].Value;
        }

        var start = text.IndexOf('{');
        var end = text.LastIndexOf('}');
        return start >= 0 && end > start ? text[start..(end + 1)] : null;
    }

    private static string PackageVersionFromFileName(string packageFile)
    {
        return Path.GetFileNameWithoutExtension(packageFile);
    }

    private static string SanitizePathSegment(string value)
    {
        var builder = new StringBuilder(value.Length);
        foreach (var ch in value)
        {
            builder.Append(char.IsLetterOrDigit(ch) || ch is '-' or '_' or '.' ? ch : '-');
        }

        return builder.Length == 0 ? "adapter" : builder.ToString();
    }

    private static string SceneLabel(string scene, int index)
    {
        var name = Path.GetFileNameWithoutExtension(scene);
        return string.IsNullOrWhiteSpace(name) ? $"Scene {index + 1}" : name;
    }

    private static string CompactJson<T>(T value)
    {
        return JsonSerializer.Serialize(value, new JsonSerializerOptions
        {
            Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping
        });
    }

    private static string TrimForPrompt(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "{}";
        }

        return value.Length <= MaxPromptJsonChars ? value : value[..MaxPromptJsonChars] + "\n...<truncated>";
    }

    private static string EscapeForPrompt(string value)
    {
        return value.Replace("\\", "\\\\", StringComparison.Ordinal).Replace("\"", "\\\"", StringComparison.Ordinal);
    }

    private static string FirstNonEmpty(params string?[] values)
    {
        foreach (var value in values)
        {
            if (!string.IsNullOrWhiteSpace(value))
            {
                return value.Trim();
            }
        }

        return "";
    }

    private static string GetString(JsonElement element, string propertyName)
    {
        return element.TryGetProperty(propertyName, out var value) && value.ValueKind == JsonValueKind.String
            ? value.GetString() ?? ""
            : "";
    }

    private static string ComputeStringSha256(string value)
    {
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(value))).ToLowerInvariant();
    }

    private static string Tail(string value, int maxLength)
    {
        if (string.IsNullOrEmpty(value) || value.Length <= maxLength)
        {
            return value;
        }

        return value[^maxLength..];
    }

    private sealed record ExistingSemanticAdapter(
        string Path,
        JsonElement Adapter,
        string AdapterVersion,
        string PackageSha256,
        DateTime LastWriteUtc);

    private sealed record AdapterDecision(
        string Decision,
        string Reason,
        bool CodexInvoked,
        string RawOutputTail);

    private sealed record CodexAdapterRun(
        int ExitCode,
        string RawOutput,
        string RawOutputTail);
}

public sealed record ProjectWebPreviewSemanticAdapterRequest(
    string AccountId,
    string RunId,
    ProjectSnapshot Project,
    string ProjectRoot,
    string PackageFile,
    string PackageSha256,
    long PackageSizeBytes,
    string GameName,
    string GameTypeSource,
    string GameTypeId,
    string GameTypeGuide,
    string? MainScene,
    IReadOnlyList<string> Scenes,
    string PlayablePreviewContractJson,
    string WebPreviewManifestJson);

public sealed record ProjectWebPreviewSemanticAdapterResult(
    JsonElement Adapter,
    string Status,
    string AdapterPath,
    ProjectWebPreviewSemanticAdapterResolution Resolution);

public sealed record ProjectWebPreviewSemanticAdapterResolution(
    [property: JsonPropertyName("status")] string Status,
    [property: JsonPropertyName("reason")] string Reason,
    [property: JsonPropertyName("adapter_version")] string AdapterVersion,
    [property: JsonPropertyName("adapter_package_sha256")] string AdapterPackageSha256,
    [property: JsonPropertyName("adapter_path")] string AdapterPath,
    [property: JsonPropertyName("codex_invoked")] bool CodexInvoked,
    [property: JsonPropertyName("codex_decision")] string CodexDecision,
    [property: JsonPropertyName("codex_output_tail")] string CodexOutputTail);
