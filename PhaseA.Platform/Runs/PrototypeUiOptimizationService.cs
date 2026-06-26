using System.Text.Json;
using System.Security.Cryptography;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Workspaces;

namespace PhaseA.Platform.Runs;

public sealed class PrototypeUiOptimizationService
{
    private const string RunType = "prototype-ui-optimization";
    private static readonly TimeSpan DefaultExecutionTimeout = TimeSpan.FromMinutes(20);
    private static readonly TimeSpan GodotSmokeValidationTimeout = TimeSpan.FromSeconds(75);

    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;
    private readonly IHostedProcessRunner _processRunner;
    private readonly IProjectWorkspaceSeeder _workspaceSeeder;
    private readonly AiCodeMirrorKeyPoolService? _keyPoolService;
    private readonly HeavyRunnerQueueService _heavyRunnerQueue;
    private readonly TimeSpan _executionTimeout;

    public PrototypeUiOptimizationService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        IHostedProcessRunner processRunner)
        : this(metadataStore, options, processRunner, new ProjectWorkspaceSeeder(options))
    {
    }

    public PrototypeUiOptimizationService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        IHostedProcessRunner processRunner,
        IProjectWorkspaceSeeder workspaceSeeder,
        AiCodeMirrorKeyPoolService? keyPoolService = null,
        TimeSpan? executionTimeout = null,
        HeavyRunnerQueueService? heavyRunnerQueue = null)
    {
        _metadataStore = metadataStore;
        _options = options;
        _processRunner = processRunner;
        _workspaceSeeder = workspaceSeeder;
        _keyPoolService = keyPoolService;
        _heavyRunnerQueue = heavyRunnerQueue ?? new HeavyRunnerQueueService();
        _executionTimeout = executionTimeout ?? DefaultExecutionTimeout;
    }

    public async Task<PrototypeUiOptimizationResult> RunAsync(
        string accountId,
        string projectId,
        PrototypeUiOptimizationRequest? request = null,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            return new PrototypeUiOptimizationResult("", "project_not_found", "Project was not found.");
        }

        if (project.BootstrapStatus == "running" ||
            await _metadataStore.HasRunnerLockAsync(project.ProjectId, cancellationToken) ||
            await _metadataStore.HasActiveRunAsync(project.ProjectId, cancellationToken))
        {
            return new PrototypeUiOptimizationResult("", "project_busy", "Project is busy.");
        }

        var planReadiness = await ValidateIterationPlanCompleteAsync(project.ProjectId, cancellationToken);
        if (planReadiness is not null)
        {
            return new PrototypeUiOptimizationResult("", planReadiness, FormatReadinessSummary(planReadiness));
        }

        if (!await HasSucceededPrototypeSkeletonAsync(project.ProjectId, cancellationToken))
        {
            return new PrototypeUiOptimizationResult("", "prototype_skeleton_not_ready", "Create the prototype skeleton before running UI optimization.");
        }

        var projectRoot = Path.GetFullPath(project.RepoPath);
        if (!WorkspacePathPolicy.IsUnderRoot(_options.HostedWorkspaceRoot, projectRoot))
        {
            throw new InvalidOperationException("Project repository path escaped the hosted workspace root.");
        }

        _workspaceSeeder.EnsureSeeded(project.RepoPath);
        var runId = await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, RunType, cancellationToken);
        var locked = await _metadataStore.TryAcquireRunnerLockAsync(project.ProjectId, runId, cancellationToken);
        if (!locked)
        {
            await _metadataStore.CompleteRunAsync(runId, "blocked", 423, "", "runner lock already held", "{}", cancellationToken);
            return new PrototypeUiOptimizationResult(runId, "project_busy", "Project is busy.");
        }

        await using var heavyRunnerLease = await _heavyRunnerQueue.EnterAsync(runId, project.AccountId, project.ProjectId, RunType, CancellationToken.None);
        await _metadataStore.MarkRunStartedAsync(runId, heavyRunnerLease.QueuePositionAtStart, CancellationToken.None);
        await _metadataStore.UpdateRunProgressAsync(runId, "running", "prepare", "\u6b63\u5728\u51c6\u5907 UI \u4f18\u5316\u3002", CancellationToken.None);
        var runLogRelativeDir = Path.Combine("logs", "phase-a-ui-optimization", project.ProjectId, runId);
        var promptRelativePath = Path.Combine(runLogRelativeDir, "ui-optimization-prompt.md");
        var outputRelativePath = Path.Combine(runLogRelativeDir, "codex-output.jsonl");
        var promptAbsolutePath = Path.Combine(projectRoot, promptRelativePath);
        var outputAbsolutePath = Path.Combine(projectRoot, outputRelativePath);
        Directory.CreateDirectory(Path.GetDirectoryName(promptAbsolutePath)!);
        Directory.CreateDirectory(Path.GetDirectoryName(outputAbsolutePath)!);
        var codexStartedUtc = DateTimeOffset.MinValue;
        var preCodexPrototypeSnapshot = PrototypeUiWorkspaceSnapshot.Capture(project.RepoPath);

        try
        {
            var model = PrototypeModelPolicy.Normalize(request?.Model);
            var prompt = BuildPrompt(project);
            await File.WriteAllTextAsync(promptAbsolutePath, prompt, System.Text.Encoding.UTF8, CancellationToken.None);
            var command = CodexHostedProcessCommandFactory.Build(new CodexHostedProcessRequest(
                projectRoot,
                outputAbsolutePath,
                prompt,
                model,
                "high",
                Sandbox: "workspace-write",
                Json: true));
            var runtimeCredential = await ResolveRuntimeCredentialAsync(project.AccountId, cancellationToken);
            using var timeout = new CancellationTokenSource(_executionTimeout);
            await _metadataStore.UpdateRunProgressAsync(runId, "running", "generation", "\u6b63\u5728\u8fd0\u884c UI \u4f18\u5316\u8def\u7531\u3002", CancellationToken.None);
            codexStartedUtc = DateTimeOffset.UtcNow;
            var process = await _processRunner.RunAsync(
                CodexHostedProcessCommandFactory.ApplyRuntime(command, runtimeCredential).WithRunId(runId),
                timeout.Token);
            var bomCleanedFiles = StripGodotTextResourceBom(project.RepoPath);
            var smokeScene = process.ExitCode == 0
                ? await ResolveLatestPrototypeSmokeSceneAsync(project, CancellationToken.None)
                : null;
            var godotSmoke = process.ExitCode == 0
                ? await RunGodotSmokeValidationAsync(runId, project, smokeScene, CancellationToken.None)
                : PrototypeGodotSmokeResult.NotRun("codex_ui_optimization_failed", smokeScene);
            var status = process.ExitCode == 0 && godotSmoke.Ran && godotSmoke.ExitCode == 0
                ? "succeeded"
                : "failed";
            var exitCode = process.ExitCode != 0 ? process.ExitCode : godotSmoke.Ran ? godotSmoke.ExitCode : 1;
            var progressSubstep = status == "succeeded"
                ? "completed"
                : process.ExitCode == 0 ? "validation_failed" : "codex_failed";
            var progressLabel = status == "succeeded"
                ? "UI \u4f18\u5316\u5df2\u5b8c\u6210\uff0c\u77ed\u9a8c\u8bc1\u5df2\u901a\u8fc7\u3002"
                : process.ExitCode == 0
                    ? "UI \u4f18\u5316\u5df2\u4fee\u6539\uff0c\u4f46\u77ed\u9a8c\u8bc1\u5931\u8d25\u3002"
                    : "UI \u4f18\u5316\u5931\u8d25\u3002";
            var evidenceJson = JsonSerializer.Serialize(new
            {
                route = RunType,
                model,
                template = ResolveTemplateName(project),
                prompt = promptRelativePath.Replace('\\', '/'),
                output = outputRelativePath.Replace('\\', '/'),
                timeout_seconds = (int)_executionTimeout.TotalSeconds,
                validation_policy = "codex_ui_edit_only_platform_short_godot_smoke",
                codex_exit_code = process.ExitCode,
                godot_text_bom_cleaned = bomCleanedFiles,
                validation_required = process.ExitCode == 0,
                godot_smoke = godotSmoke.ToEvidence()
            });
            await _metadataStore.CompleteRunAsync(runId, status, exitCode, process.Stdout, process.Stderr, evidenceJson, CancellationToken.None);
            await _metadataStore.RecordRunLlmAuditAsync(
                runId,
                "codex-cli",
                null,
                model,
                LlmUsageAuditJson.BuildCodexUsageJson(
                    operation: RunType,
                    model: model,
                    tokenUsage: CodexUsageExtractor.Extract(process.Stdout, process.Stderr),
                    runType: RunType,
                    projectId: project.ProjectId,
                    skillName: "prototype-rpg-ui-optimizer-zh",
                    route: RunType,
                    exitCode: exitCode),
                CancellationToken.None);
            await _metadataStore.AddArtifactAsync(
                new ArtifactCreationCommand(runId, project.ProjectId, "prototype-ui-optimization-prompt", promptRelativePath.Replace('\\', '/'), "UI optimization prompt"),
                CancellationToken.None);
            await _metadataStore.AddArtifactAsync(
                new ArtifactCreationCommand(runId, project.ProjectId, "prototype-ui-optimization-output", outputRelativePath.Replace('\\', '/'), "UI optimization generation output"),
                CancellationToken.None);
            await _metadataStore.UpdateRunProgressAsync(
                runId,
                status,
                progressSubstep,
                progressLabel,
                CancellationToken.None);
            return new PrototypeUiOptimizationResult(
                runId,
                status,
                status == "succeeded"
                    ? "UI optimization completed."
                    : process.ExitCode == 0
                        ? "UI optimization changed files, but short validation failed."
                        : "UI optimization failed.");
        }
        catch (OperationCanceledException ex)
        {
            if (await IsRunCancelledAsync(runId, CancellationToken.None))
            {
                return new PrototypeUiOptimizationResult(runId, "cancel", "UI optimization cancelled.");
            }

            var timeoutRecovery = await TryCompleteTimedOutRunIfValidatedAsync(
                runId,
                project,
                model: PrototypeModelPolicy.Normalize(request?.Model),
                promptRelativePath,
                outputRelativePath,
                codexStartedUtc,
                preCodexPrototypeSnapshot,
                CancellationToken.None);
            if (timeoutRecovery is not null)
            {
                return timeoutRecovery;
            }

            var timeoutChanges = DetectPrototypeUiChanges(project.RepoPath, codexStartedUtc, preCodexPrototypeSnapshot);
            var evidenceJson = JsonSerializer.Serialize(new
            {
                route = RunType,
                timeout_seconds = (int)_executionTimeout.TotalSeconds,
                failure_code = "ui_optimization_codex_timeout",
                validation_policy = "codex_ui_edit_only_platform_short_godot_smoke",
                changed_files_detected = timeoutChanges.ChangedPaths.Count > 0,
                changed_paths = timeoutChanges.ChangedPaths,
                prompt = promptRelativePath.Replace('\\', '/'),
                output = outputRelativePath.Replace('\\', '/')
            });
            await _metadataStore.CompleteRunAsync(runId, "failed", 408, "", ex.ToString(), evidenceJson, CancellationToken.None);
            await _metadataStore.UpdateRunProgressAsync(runId, "failed", "timeout", "UI \u4f18\u5316\u8d85\u65f6\u3002", CancellationToken.None);
            return new PrototypeUiOptimizationResult(runId, "failed", "UI optimization timed out.");
        }
        catch (Exception ex)
        {
            var evidenceJson = JsonSerializer.Serialize(new
            {
                route = RunType,
                failure_code = "ui_optimization_route_error",
                validation_policy = "codex_ui_edit_only_platform_short_godot_smoke",
                prompt = promptRelativePath.Replace('\\', '/'),
                output = outputRelativePath.Replace('\\', '/')
            });
            await _metadataStore.CompleteRunAsync(runId, "failed", 500, "", ex.ToString(), evidenceJson, CancellationToken.None);
            await _metadataStore.UpdateRunProgressAsync(runId, "failed", "error", "UI \u4f18\u5316\u5931\u8d25\u3002", CancellationToken.None);
            return new PrototypeUiOptimizationResult(runId, "failed", "UI optimization failed.");
        }
        finally
        {
            await _metadataStore.ReleaseRunnerLockAsync(project.ProjectId, runId, CancellationToken.None);
        }
    }

    private async Task<PrototypeUiOptimizationResult?> TryCompleteTimedOutRunIfValidatedAsync(
        string runId,
        ProjectSnapshot project,
        string model,
        string promptRelativePath,
        string outputRelativePath,
        DateTimeOffset codexStartedUtc,
        PrototypeUiWorkspaceSnapshot preCodexPrototypeSnapshot,
        CancellationToken cancellationToken)
    {
        var changeDetection = DetectPrototypeUiChanges(project.RepoPath, codexStartedUtc, preCodexPrototypeSnapshot);
        if (changeDetection.ChangedPaths.Count == 0)
        {
            return null;
        }

        var bomCleanedFiles = StripGodotTextResourceBom(project.RepoPath);
        var smokeScene = await ResolveLatestPrototypeSmokeSceneAsync(project, cancellationToken);
        if (string.IsNullOrWhiteSpace(smokeScene))
        {
            if (!changeDetection.HasPrototypeUiFileChanges)
            {
                return null;
            }
        }
        else if (!changeDetection.CanValidateSmokeScene(project.RepoPath, smokeScene))
        {
            return null;
        }

        var godotSmoke = await RunGodotSmokeValidationAsync(runId, project, smokeScene, cancellationToken);
        var validationPassed = godotSmoke.Ran && godotSmoke.ExitCode == 0;
        if (!validationPassed)
        {
            var failedEvidenceJson = JsonSerializer.Serialize(new
            {
                route = RunType,
                model,
                timeout_seconds = (int)_executionTimeout.TotalSeconds,
                failure_code = "ui_optimization_timeout_validation_failed_after_cancel",
                validation_policy = "codex_ui_edit_only_platform_short_godot_smoke",
                changed_files_detected = true,
                prompt = promptRelativePath.Replace('\\', '/'),
                output = outputRelativePath.Replace('\\', '/'),
                changed_paths = changeDetection.ChangedPaths,
                validation_required = true,
                godot_text_bom_cleaned = bomCleanedFiles,
                godot_smoke = godotSmoke.ToEvidence()
            });
            await _metadataStore.CompleteRunAsync(
                runId,
                "failed",
                godotSmoke.Ran ? godotSmoke.ExitCode : 408,
                "",
                "UI optimization timed out and post-timeout short validation failed.",
                failedEvidenceJson,
                CancellationToken.None);
            await _metadataStore.UpdateRunProgressAsync(runId, "failed", "timeout_validation_failed", "UI \u4f18\u5316\u8d85\u65f6\uff0c\u4e14\u77ed\u9a8c\u8bc1\u5931\u8d25\u3002", CancellationToken.None);
            await AddUiOptimizationArtifactsAsync(runId, project.ProjectId, promptRelativePath, outputRelativePath, CancellationToken.None);
            return new PrototypeUiOptimizationResult(runId, "failed", "UI optimization timed out after edits, and short validation failed.");
        }

        var evidenceJson = JsonSerializer.Serialize(new
        {
            route = RunType,
            model,
            template = ResolveTemplateName(project),
            timeout_seconds = (int)_executionTimeout.TotalSeconds,
            failure_code = "ui_optimization_timeout_validated_after_cancel",
            validation_policy = "codex_ui_edit_only_platform_short_godot_smoke",
            changed_files_detected = true,
            prompt = promptRelativePath.Replace('\\', '/'),
            output = outputRelativePath.Replace('\\', '/'),
            changed_paths = changeDetection.ChangedPaths,
            validation_required = true,
            godot_text_bom_cleaned = bomCleanedFiles,
            godot_smoke = godotSmoke.ToEvidence()
        });
        await _metadataStore.CompleteRunAsync(runId, "succeeded", 0, "", "UI optimization timed out after edits; post-timeout short validation passed.", evidenceJson, CancellationToken.None);
        await _metadataStore.RecordRunLlmAuditAsync(
            runId,
            "codex-cli",
            null,
            model,
            LlmUsageAuditJson.BuildCodexUsageJson(
                operation: RunType,
                model: model,
                runType: RunType,
                projectId: project.ProjectId,
                skillName: "prototype-rpg-ui-optimizer-zh",
                route: RunType,
                exitCode: 0),
            CancellationToken.None);
        await AddUiOptimizationArtifactsAsync(runId, project.ProjectId, promptRelativePath, outputRelativePath, CancellationToken.None);
        await _metadataStore.UpdateRunProgressAsync(runId, "succeeded", "completed_after_timeout", "UI \u4f18\u5316\u8d85\u65f6\u540e\u68c0\u6d4b\u5230\u5df2\u5199\u5165\u6539\u52a8\uff0c\u77ed\u9a8c\u8bc1\u5df2\u901a\u8fc7\u3002", CancellationToken.None);
        return new PrototypeUiOptimizationResult(runId, "succeeded", "UI optimization timed out after edits, but short validation passed.");
    }

    private static PrototypeUiChangeDetection DetectPrototypeUiChanges(
        string repoPath,
        DateTimeOffset codexStartedUtc,
        PrototypeUiWorkspaceSnapshot preCodexPrototypeSnapshot)
    {
        if (codexStartedUtc == DateTimeOffset.MinValue)
        {
            return PrototypeUiChangeDetection.Empty;
        }

        var currentSnapshot = PrototypeUiWorkspaceSnapshot.Capture(repoPath);
        var changedPaths = new SortedSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var relativePath in currentSnapshot.Files.Keys.Concat(preCodexPrototypeSnapshot.Files.Keys))
        {
            var currentExists = currentSnapshot.Files.TryGetValue(relativePath, out var current);
            var beforeExists = preCodexPrototypeSnapshot.Files.TryGetValue(relativePath, out var before);
            if (currentExists != beforeExists ||
                current is null ||
                before is null ||
                before.Length != current.Length ||
                !string.Equals(before.Hash, current.Hash, StringComparison.Ordinal) ||
                !string.Equals(before.Status, current.Status, StringComparison.Ordinal))
            {
                changedPaths.Add(relativePath);
            }
        }

        var projectGodotMainSceneChanged = changedPaths.Contains("project.godot") &&
                                           !string.Equals(
                                               preCodexPrototypeSnapshot.ProjectGodotPrototypeMainScene,
                                               currentSnapshot.ProjectGodotPrototypeMainScene,
                                               StringComparison.OrdinalIgnoreCase);
        return new PrototypeUiChangeDetection(
            changedPaths.ToArray(),
            projectGodotMainSceneChanged ? currentSnapshot.ProjectGodotPrototypeMainScene : null);
    }

    private static bool IsPrototypeUiFileExtension(string extension)
    {
        return string.Equals(extension, ".tscn", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(extension, ".gd", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(extension, ".cs", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(extension, ".tres", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(extension, ".res", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(extension, ".png", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(extension, ".jpg", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(extension, ".jpeg", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(extension, ".webp", StringComparison.OrdinalIgnoreCase);
    }

    private sealed record PrototypeUiChangeDetection(IReadOnlyList<string> ChangedPaths, string? ChangedProjectGodotPrototypeMainScene)
    {
        public static PrototypeUiChangeDetection Empty { get; } = new([], null);

        public bool HasPrototypeUiFileChanges => ChangedPaths.Any(path =>
            path.StartsWith("Game.Godot/Prototypes/", StringComparison.OrdinalIgnoreCase));

        public bool CanValidateSmokeScene(string repoPath, string? smokeScene)
        {
            if (string.IsNullOrWhiteSpace(smokeScene))
            {
                return false;
            }

            if (!smokeScene.StartsWith("res://", StringComparison.OrdinalIgnoreCase))
            {
                return false;
            }

            if (!string.IsNullOrWhiteSpace(ChangedProjectGodotPrototypeMainScene) &&
                string.Equals(ChangedProjectGodotPrototypeMainScene, smokeScene, StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }

            var smokeSceneRelativePath = smokeScene["res://".Length..].Replace('\\', '/');
            return ChangedPaths.Any(path =>
                path.StartsWith("Game.Godot/Prototypes/", StringComparison.OrdinalIgnoreCase) &&
                (string.Equals(path, smokeSceneRelativePath, StringComparison.OrdinalIgnoreCase) ||
                 SmokeSceneReferencesPath(repoPath, smokeSceneRelativePath, path)));
        }

        private static bool SmokeSceneReferencesPath(string repoPath, string smokeSceneRelativePath, string changedPath)
        {
            var sceneFullPath = Path.Combine(repoPath, smokeSceneRelativePath.Replace('/', Path.DirectorySeparatorChar));
            if (!File.Exists(sceneFullPath))
            {
                return false;
            }

            var sceneDirectory = Path.GetDirectoryName(smokeSceneRelativePath)?.Replace('\\', '/') ?? "";
            IReadOnlyList<string> referencedPaths;
            try
            {
                referencedPaths = ReadGodotResourceReferencePaths(sceneFullPath, sceneDirectory).ToArray();
            }
            catch (IOException)
            {
                return false;
            }
            catch (UnauthorizedAccessException)
            {
                return false;
            }

            foreach (var referencedPath in referencedPaths)
            {
                if (string.Equals(referencedPath, changedPath, StringComparison.OrdinalIgnoreCase))
                {
                    return true;
                }
            }

            return false;
        }

        private static IEnumerable<string> ReadGodotResourceReferencePaths(string sceneFullPath, string sceneDirectory)
        {
            foreach (var line in File.ReadLines(sceneFullPath))
            {
                var searchStart = 0;
                while (true)
                {
                    var pathStart = line.IndexOf("path=\"", searchStart, StringComparison.Ordinal);
                    if (pathStart < 0)
                    {
                        break;
                    }

                    pathStart += "path=\"".Length;
                    var pathEnd = line.IndexOf('"', pathStart);
                    if (pathEnd < 0)
                    {
                        break;
                    }

                    var reference = line[pathStart..pathEnd];
                    var resolved = ResolveGodotResourceReference(sceneDirectory, reference);
                    if (!string.IsNullOrWhiteSpace(resolved))
                    {
                        yield return resolved;
                    }

                    searchStart = pathEnd + 1;
                }
            }
        }

        private static string? ResolveGodotResourceReference(string sceneDirectory, string reference)
        {
            if (string.IsNullOrWhiteSpace(reference) ||
                reference.StartsWith("uid://", StringComparison.OrdinalIgnoreCase))
            {
                return null;
            }

            if (reference.StartsWith("res://", StringComparison.OrdinalIgnoreCase))
            {
                return reference["res://".Length..].Replace('\\', '/');
            }

            var combined = string.IsNullOrWhiteSpace(sceneDirectory)
                ? reference
                : $"{sceneDirectory}/{reference}";
            return NormalizeRelativeResourcePath(combined);
        }

        private static string NormalizeRelativeResourcePath(string path)
        {
            var parts = new List<string>();
            foreach (var part in path.Replace('\\', '/').Split('/', StringSplitOptions.RemoveEmptyEntries))
            {
                if (part == ".")
                {
                    continue;
                }

                if (part == "..")
                {
                    if (parts.Count > 0)
                    {
                        parts.RemoveAt(parts.Count - 1);
                    }

                    continue;
                }

                parts.Add(part);
            }

            return string.Join("/", parts);
        }
    }

    private sealed record PrototypeUiWorkspaceSnapshot(
        IReadOnlyDictionary<string, PrototypeUiFileSnapshot> Files,
        string? ProjectGodotPrototypeMainScene)
    {
        public static PrototypeUiWorkspaceSnapshot Capture(string repoPath)
        {
            var prototypesRoot = Path.Combine(repoPath, "Game.Godot", "Prototypes");
            var result = new Dictionary<string, PrototypeUiFileSnapshot>(StringComparer.OrdinalIgnoreCase);
            var projectGodotPath = Path.Combine(repoPath, "project.godot");
            if (File.Exists(projectGodotPath))
            {
                result["project.godot"] = CaptureFile(projectGodotPath);
            }

            CaptureDirectory(result, prototypesRoot, "Game.Godot/Prototypes");

            return new PrototypeUiWorkspaceSnapshot(result, ResolveProjectGodotPrototypeMainScene(repoPath));
        }

        private static void CaptureDirectory(Dictionary<string, PrototypeUiFileSnapshot> result, string root, string relativePrefix)
        {
            if (!Directory.Exists(root))
            {
                return;
            }

            foreach (var file in Directory.EnumerateFiles(root, "*", SearchOption.AllDirectories))
            {
                if (!IsPrototypeUiFileExtension(Path.GetExtension(file)))
                {
                    continue;
                }

                var relativePath = relativePrefix + "/" + Path.GetRelativePath(root, file).Replace('\\', '/');
                result[relativePath] = CaptureFile(file);
            }
        }

        private static PrototypeUiFileSnapshot CaptureFile(string file)
        {
            try
            {
                using var stream = File.OpenRead(file);
                var hash = Convert.ToHexString(SHA256.HashData(stream));
                return new PrototypeUiFileSnapshot(stream.Length, hash, "read");
            }
            catch (IOException)
            {
                return new PrototypeUiFileSnapshot(null, null, "io_error");
            }
            catch (UnauthorizedAccessException)
            {
                return new PrototypeUiFileSnapshot(null, null, "unauthorized");
            }
        }
    }

    private sealed record PrototypeUiFileSnapshot(long? Length, string? Hash, string Status);

    private static string? ResolveProjectGodotPrototypeMainScene(string repoPath)
    {
        var projectGodotPath = Path.Combine(repoPath, "project.godot");
        if (!File.Exists(projectGodotPath))
        {
            return null;
        }

        string? resolvedScene = null;
        foreach (var rawLine in File.ReadLines(projectGodotPath))
        {
            var line = rawLine.Trim();
            if (line.StartsWith(";", StringComparison.Ordinal) ||
                line.StartsWith("#", StringComparison.Ordinal))
            {
                continue;
            }

            var separatorIndex = line.IndexOf('=', StringComparison.Ordinal);
            if (separatorIndex < 0 ||
                !string.Equals(line[..separatorIndex].Trim(), "run/main_scene", StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            var value = line[(separatorIndex + 1)..].Trim().Trim('"');
            var scene = PrototypeGodotSmokeService.ResolveSceneReference(repoPath, value);
            if (!string.IsNullOrWhiteSpace(scene) &&
                scene.StartsWith("res://Game.Godot/Prototypes/", StringComparison.OrdinalIgnoreCase))
            {
                resolvedScene = scene;
            }
        }

        return resolvedScene;
    }

    private static IReadOnlyList<string> StripGodotTextResourceBom(string repoPath)
    {
        var prototypesRoot = Path.Combine(repoPath, "Game.Godot", "Prototypes");
        if (!Directory.Exists(prototypesRoot))
        {
            return [];
        }

        var cleaned = new List<string>();
        foreach (var file in Directory.EnumerateFiles(prototypesRoot, "*", SearchOption.AllDirectories))
        {
            if (!IsGodotTextResourceExtension(Path.GetExtension(file)))
            {
                continue;
            }

            var bytes = File.ReadAllBytes(file);
            if (bytes.Length < 3 ||
                bytes[0] != 0xEF ||
                bytes[1] != 0xBB ||
                bytes[2] != 0xBF)
            {
                continue;
            }

            File.WriteAllBytes(file, bytes[3..]);
            cleaned.Add(Path.GetRelativePath(repoPath, file).Replace('\\', '/'));
        }

        return cleaned;
    }

    private static bool IsGodotTextResourceExtension(string extension)
    {
        return string.Equals(extension, ".tscn", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(extension, ".tres", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(extension, ".gd", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(extension, ".cs", StringComparison.OrdinalIgnoreCase);
    }

    private async Task AddUiOptimizationArtifactsAsync(
        string runId,
        string projectId,
        string promptRelativePath,
        string outputRelativePath,
        CancellationToken cancellationToken)
    {
        await _metadataStore.AddArtifactAsync(
            new ArtifactCreationCommand(runId, projectId, "prototype-ui-optimization-prompt", promptRelativePath.Replace('\\', '/'), "UI optimization prompt"),
            cancellationToken);
        await _metadataStore.AddArtifactAsync(
            new ArtifactCreationCommand(runId, projectId, "prototype-ui-optimization-output", outputRelativePath.Replace('\\', '/'), "UI optimization generation output"),
            cancellationToken);
    }

    private async Task<string?> ValidateIterationPlanCompleteAsync(string projectId, CancellationToken cancellationToken)
    {
        var details = await _metadataStore.GetLatestProjectIterationSessionAsync(projectId, cancellationToken);
        if (details is null || details.Goals.Count == 0)
        {
            return "iteration_plan_not_ready";
        }

        return details.Goals.All(goal => IsCompletedGoalStatus(goal.Status))
            ? null
            : "iteration_plan_not_complete";
    }

    private static bool IsCompletedGoalStatus(string? status)
    {
        return string.Equals(status, "succeeded", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(status, "completed", StringComparison.OrdinalIgnoreCase);
    }

    private async Task<bool> HasSucceededPrototypeSkeletonAsync(string projectId, CancellationToken cancellationToken)
    {
        var runs = await _metadataStore.ListRunsForProjectAsync(projectId, cancellationToken);
        return runs.Any(run =>
            string.Equals(run.RunType, "prototype-7day-playable", StringComparison.OrdinalIgnoreCase) &&
            string.Equals(run.Status, "succeeded", StringComparison.OrdinalIgnoreCase));
    }

    private async Task<string?> ResolveLatestPrototypeSmokeSceneAsync(ProjectSnapshot project, CancellationToken cancellationToken)
    {
        return await PrototypeSmokeSceneResolver.ResolveLatestAsync(
            _metadataStore,
            project,
            new PrototypeRouteStateWriter(),
            cancellationToken: cancellationToken);
    }

    private async Task<PrototypeGodotSmokeResult> RunGodotSmokeValidationAsync(string runId, ProjectSnapshot project, string? scenePath, CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(scenePath))
        {
            return PrototypeGodotSmokeResult.NotRun("prototype_smoke_scene_missing");
        }

        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(GodotSmokeValidationTimeout);
        try
        {
            await _metadataStore.UpdateRunProgressAsync(
                runId,
                "running",
                "short_validation",
                "正在运行游戏界面优化短验证。",
                CancellationToken.None);
            return await PrototypeGodotSmokeService.RunAsync(_options, _processRunner, project.RepoPath, scenePath, timeout.Token);
        }
        catch (OperationCanceledException)
        {
            return new PrototypeGodotSmokeResult(
                true,
                408,
                "",
                $"UI optimization Godot smoke validation exceeded the {GodotSmokeValidationTimeout.TotalSeconds:0} second timeout.",
                "ui_optimization_godot_smoke_timeout",
                scenePath);
        }
    }

    private static string FormatReadinessSummary(string status)
    {
        return status switch
        {
            "iteration_plan_not_ready" => "\u8bf7\u5148\u751f\u6210\u5e76\u5b8c\u6210\u8fed\u4ee3\u8ba1\u5212\uff0c\u518d\u8fd0\u884c UI \u4f18\u5316\u3002",
            "iteration_plan_not_complete" => "\u5f53\u524d\u8fed\u4ee3\u8ba1\u5212\u4ecd\u6709\u672a\u5b8c\u6210\u6b65\u9aa4\uff0c\u8bf7\u5148\u5b8c\u6210\u8fed\u4ee3\u8ba1\u5212\uff0c\u518d\u8fd0\u884c UI \u4f18\u5316\u3002",
            _ => status
        };
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

    private static string BuildPrompt(ProjectSnapshot project)
    {
        var templateName = ResolveTemplateName(project);
        return $"""
            You are running the Phase A prototype UI optimization route.
            Invoke `$prototype-rpg-ui-optimizer-zh` when the project is RPG/JRPG/DQ-like.

            Goal:
            - Improve the current Godot prototype UI so it visually and structurally resembles the game-type template.
            - For RPG/JRPG/DQ-like projects, use the He-is-Coming prototype UI as the target reference style.

            Project:
            - ProjectId: {project.ProjectId}
            - ProjectName: {project.Name}
            - GameName: {project.GameName}
            - GameTypeSource: {project.GameTypeSource}
            - TemplateReference: {templateName}

            Recovery protocol:
            - Read AGENTS.md and README.md only for repository-level operating rules; do not use them as project completion memory.
            - Read meta/project-execution-guide.md and meta/project-context.md when present.
            - Read meta/routes/prototype-contract/latest.json as the primary project contract source.
            - Use routes/prototype-contract/latest.json only as a legacy fallback when the meta/routes contract file is missing.
            - Read latest route state under meta/routes/prototype/, meta/routes/iteration-plan/, and meta/routes/execute-next-goal/ when present.
            - Inspect Game.Godot/Prototypes and project.godot before editing.
            - Prefer modifying existing prototype scenes, scripts, labels, layout, theme, and asset references.
            - Do not create a second unrelated prototype. Do not add new workflow rules.
            - Do not leave UI optimization in an unreferenced side scene. If you create an optimized scene such as *UiOptimized.tscn, project.godot must use it as run/main_scene or the existing main prototype scene must instance it before you report success.
            - Prefer improving the actual playable entry path: project.godot -> main scene -> Start Adventure -> MapScene/BattleScene/reward/status/log UI. A thin wrapper scene or a standalone visual mock that is not reachable from this path is incomplete.
            - If the main scene only instances MapScene and BattleScene, improve those child scenes and the main scene HUD together so the launched game has the optimized RPG presentation.
            - Do not delete existing playable logic.

            RPG UI target:
            - Current game should launch into the actual playable RPG prototype, not the generic template Main.tscn demo UI.
            - UI should include RPG-specific status, encounter, map, battle, reward, result, and log panels where applicable.
            - {PrototypePlayerVisibleTextPolicy.PromptRule}
            - If a DefaultRpgTemplate or He-is-Coming-like prototype exists locally, reuse its layout/style patterns rather than inventing a new UI.

            Validation:
            - Keep the Godot project loadable.
            - Preserve existing scenes/scripts unless directly needed for UI alignment.
            - Do not run long Godot/headless validation commands from this route; the platform runs a short Godot smoke after generation exits.
            - If you validate locally, keep checks short and deterministic, such as a C# build or static scene/script inspection.
            - Leave full Godot prototype acceptance to the dedicated prototype acceptance route.
            - Report changed files and remaining gaps.
            """;
    }

    private static string ResolveTemplateName(ProjectSnapshot project)
    {
        var source = $"{project.GameTypeSource} {project.GameName} {project.Name}";
        return source.Contains("rpg", StringComparison.OrdinalIgnoreCase) ||
               source.Contains("jrpg", StringComparison.OrdinalIgnoreCase) ||
               source.Contains("dragon quest", StringComparison.OrdinalIgnoreCase) ||
               source.Contains("he-is-coming", StringComparison.OrdinalIgnoreCase)
            ? "He-is-Coming"
            : "game-type-template";
    }

    private async Task<bool> IsRunCancelledAsync(string runId, CancellationToken cancellationToken)
    {
        var run = await _metadataStore.GetRunSnapshotAsync(runId, cancellationToken);
        return string.Equals(run?.Status, "cancel", StringComparison.Ordinal);
    }
}

public sealed record PrototypeUiOptimizationResult(
    string RunId,
    string Status,
    string Summary);

public sealed record PrototypeUiOptimizationRequest(
    string? Model);
