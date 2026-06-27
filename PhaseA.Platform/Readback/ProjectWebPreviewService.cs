using System.Collections.Concurrent;
using System.IO.Compression;
using System.Security.Cryptography;
using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.RegularExpressions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Workspaces;
using Microsoft.Extensions.DependencyInjection;

namespace PhaseA.Platform.Readback;

public sealed class ProjectWebPreviewService
{
    private const string RunType = "project-web-preview";
    private const string PreviewArtifactType = "project-web-preview-html5";
    private const string PreviewRootDirectory = "exports/web-previews";
    private const string PreviewSchemaVersion = "phasea-web-preview-v5";
    private const string LegacyPreviewSchemaVersion = "phasea-web-preview-v4";
    private const string PreviewManifestSchemaVersion = "phasea-web-preview-manifest-v1";
    private const string PreviewManifestFileName = "web-preview-manifest.json";
    private static readonly ProjectWebPreviewConverterDescriptor Towerdemo2Converter = new(
        "towerdemo2-template-subset",
        "godot3-html5-towerdemo2-template-subset",
        "towerdemo2-20260627-source-fingerprint-v1",
        "towerdemo2",
        ["towerdemo2", "tower-defense"],
        "Game.Godot/Prototypes/Towerdemo2/Towerdemo2Prototype.tscn",
        "Game.Godot/Prototypes/Towerdemo2/Scripts/Data/PrototypeTextCatalog.cs",
        "0ffcf4b962ac246f3af182fb49775f2517cca12a19772bae67464ca92fba33c5",
        "f4f97dfd524150b36bf36545aa3ed9a95f90a7ec4ba67000ed6763dcae028652",
        "Towerdemo2 Godot4 package subset: scene layout, text catalog, core tower placement, wave combat, economy, room progression, and loss/win loop are represented by a Godot3 browser-playable approximation.",
        "Only the towerdemo2 Godot4 package subset is supported by the current Godot3 web preview converter.");
    private static readonly ProjectWebPreviewConverterDescriptor GenericGodotPackageConverter = new(
        "godot-package-generic-playable-preview",
        "godot3-html5-generic-package-preview",
        "godot-package-manifest-capability-v1",
        "generic",
        ["generic"],
        "",
        "",
        "",
        "",
        "Generic Godot package preview: package manifest, main scene, scene inventory, text catalog count, and package-derived scene markers are represented by a Godot3 browser-playable exploration shell.",
        "The package does not expose enough Godot project metadata for a browser-playable preview.");
    private static readonly ProjectWebPreviewConverterDescriptor RpgPackageConverter = new(
        "godot-package-rpg-playable-preview",
        "godot3-html5-rpg-package-preview",
        "game-type-guide-rpg-v1",
        "rpg",
        ["rpg", "jrpg", "role-playing", "roleplaying"],
        "",
        "",
        "",
        "",
        "RPG package preview: package metadata, scene inventory, and RPG guide capabilities are converted into a Godot3 browser-playable encounter, exploration, and reward approximation.",
        "The package does not expose enough RPG scene metadata for a browser-playable preview.");
    private static readonly ProjectWebPreviewConverterDescriptor SurvivorslikePackageConverter = new(
        "godot-package-survivorslike-playable-preview",
        "godot3-html5-survivorslike-package-preview",
        "game-type-guide-survivorslike-v1",
        "survivorslike",
        ["survivorslike", "survivor", "vampire-survivors", "arena-survival", "roguelike"],
        "",
        "",
        "",
        "",
        "Survivorslike package preview: package metadata and scene inventory are converted into a Godot3 browser-playable arena movement and attack loop approximation.",
        "The package does not expose enough survivorslike scene metadata for a browser-playable preview.");
    private static readonly ProjectWebPreviewConverterDescriptor SurvivalPackageConverter = new(
        "godot-package-survival-playable-preview",
        "godot3-html5-survival-package-preview",
        "game-type-guide-survival-v1",
        "survival",
        ["survival"],
        "",
        "",
        "",
        "",
        "Survival package preview: package metadata and scene inventory are converted into a Godot3 browser-playable gathering, needs, and shelter-state approximation.",
        "The package does not expose enough survival scene metadata for a browser-playable preview.");
    private static readonly ProjectWebPreviewConverterDescriptor CardPackageConverter = new(
        "godot-package-card-playable-preview",
        "godot3-html5-card-package-preview",
        "game-type-guide-card-v1",
        "card",
        ["card", "card-game", "deckbuilder", "deck-building", "roguelike-deckbuilder"],
        "",
        "",
        "",
        "",
        "Card package preview: package metadata and scene inventory are converted into a Godot3 browser-playable hand, energy, and encounter approximation.",
        "The package does not expose enough card-game scene metadata for a browser-playable preview.");
    private static readonly ProjectWebPreviewConverterDescriptor TowerDefensePackageConverter = new(
        "godot-package-tower-defense-playable-preview",
        "godot3-html5-tower-defense-package-preview",
        "game-type-guide-tower-defense-v1",
        "tower-defense",
        ["tower-defense", "towerdefense", "td"],
        "",
        "",
        "",
        "",
        "Tower-defense package preview: package metadata and scene inventory are converted into a Godot3 browser-playable placement, wave, and base-defense approximation.",
        "The package does not expose enough tower-defense scene metadata for a browser-playable preview.");
    private static readonly ProjectWebPreviewConverterDescriptor ActionPackageConverter = new(
        "godot-package-action-playable-preview",
        "godot3-html5-action-package-preview",
        "game-type-guide-action-v1",
        "survivorslike",
        ["action", "action-platformer", "platformer", "metroidvania", "shooter", "fighting", "horror"],
        "",
        "",
        "",
        "",
        "Action package preview: package metadata and scene inventory are converted into a Godot3 browser-playable movement, pressure, and attack approximation.",
        "The package does not expose enough action scene metadata for a browser-playable preview.");
    private static readonly ProjectWebPreviewConverterDescriptor NarrativePackageConverter = new(
        "godot-package-narrative-playable-preview",
        "godot3-html5-narrative-package-preview",
        "game-type-guide-narrative-v1",
        "generic",
        ["visual-novel", "text-based", "adventure"],
        "",
        "",
        "",
        "",
        "Narrative package preview: package metadata and scene inventory are converted into a Godot3 browser-playable scene inspection and choice-surface approximation.",
        "The package does not expose enough narrative scene metadata for a browser-playable preview.");
    private static readonly ProjectWebPreviewConverterDescriptor PuzzlePackageConverter = new(
        "godot-package-puzzle-playable-preview",
        "godot3-html5-puzzle-package-preview",
        "game-type-guide-puzzle-v1",
        "generic",
        ["puzzle", "rhythm", "racing", "sports", "party-game"],
        "",
        "",
        "",
        "",
        "Puzzle and rules package preview: package metadata and scene inventory are converted into a Godot3 browser-playable inspection and interaction approximation.",
        "The package does not expose enough puzzle/rules scene metadata for a browser-playable preview.");
    private static readonly ProjectWebPreviewConverterDescriptor StrategyPackageConverter = new(
        "godot-package-strategy-playable-preview",
        "godot3-html5-strategy-package-preview",
        "game-type-guide-strategy-v1",
        "tower-defense",
        ["strategy", "turn-based-tactics", "simulation", "sandbox", "moba", "idle-incremental"],
        "",
        "",
        "",
        "",
        "Strategy package preview: package metadata and scene inventory are converted into a Godot3 browser-playable placement, wave, and system-state approximation.",
        "The package does not expose enough strategy scene metadata for a browser-playable preview.");
    private static readonly IReadOnlyList<ProjectWebPreviewConverterDescriptor> ConverterRegistry =
    [
        Towerdemo2Converter,
        RpgPackageConverter,
        SurvivalPackageConverter,
        SurvivorslikePackageConverter,
        CardPackageConverter,
        TowerDefensePackageConverter,
        ActionPackageConverter,
        NarrativePackageConverter,
        PuzzlePackageConverter,
        StrategyPackageConverter,
        GenericGodotPackageConverter
    ];
    private static readonly TimeSpan DefaultGodot3ExportTimeout = TimeSpan.FromMinutes(3);
    private static readonly TimeSpan DefaultGodot3ExportInactivityTimeout = TimeSpan.FromSeconds(45);
    private static readonly TimeSpan PreviewScratchRetention = TimeSpan.FromHours(6);
    private static readonly TimeSpan PackageHashCacheTtl = TimeSpan.FromMinutes(30);
    private const int PackageHashCacheMaxEntries = 512;
    private const long MaxPreviewPackageSizeBytes = 512L * 1024L * 1024L;
    private const int MaxPreviewPackageEntryCount = 5000;
    private const long MaxPreviewTextCatalogBytes = 2L * 1024L * 1024L;
    private static readonly TimeSpan HealthSmokeCacheTtl = TimeSpan.FromMinutes(10);
    private static readonly SemaphoreSlim HealthSmokeGate = new(1, 1);
    private static readonly ConcurrentDictionary<string, PackageHashCacheEntry> PackageHashCache = new(StringComparer.OrdinalIgnoreCase);
    private static ProjectWebPreviewHealth? _cachedHealthSmoke;
    private static DateTimeOffset _cachedHealthSmokeUtc;

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping
    };

    private static readonly JsonSerializerOptions GodotJsonOptions = new()
    {
        WriteIndented = true
    };

    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;
    private readonly HeavyRunnerQueueService _webPreviewQueue;
    private readonly ProjectWebPreviewConcurrencyLimiter _webPreviewConcurrencyLimiter;
    private readonly IHostedProcessRunner _processRunner;
    private readonly ConcurrentDictionary<string, ProjectWebPreviewConcurrencyLease> _reservedAccountConcurrencyLeases = new(StringComparer.Ordinal);

    public ProjectWebPreviewService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        [FromKeyedServices("web-preview")] HeavyRunnerQueueService? webPreviewQueue = null,
        ProjectWebPreviewConcurrencyLimiter? webPreviewConcurrencyLimiter = null,
        IHostedProcessRunner? processRunner = null)
    {
        _metadataStore = metadataStore;
        _options = options;
        _webPreviewQueue = webPreviewQueue ?? new HeavyRunnerQueueService(TimeSpan.FromMinutes(3), options.MaxConcurrentWebPreviews);
        _webPreviewConcurrencyLimiter = webPreviewConcurrencyLimiter ?? new ProjectWebPreviewConcurrencyLimiter(options.MaxConcurrentWebPreviewsPerAccount);
        _processRunner = processRunner ?? new HostedProcessRunner();
    }

    private TimeSpan Godot3ExportTimeout => _options.Godot3WebPreviewExportTimeoutSeconds > 0
        ? TimeSpan.FromSeconds(_options.Godot3WebPreviewExportTimeoutSeconds)
        : DefaultGodot3ExportTimeout;

    private TimeSpan Godot3ExportInactivityTimeout => _options.Godot3WebPreviewExportInactivityTimeoutSeconds > 0
        ? TimeSpan.FromSeconds(_options.Godot3WebPreviewExportInactivityTimeoutSeconds)
        : DefaultGodot3ExportInactivityTimeout;

    public async Task<ProjectWebPreviewResult> GeneratePreviewAsync(
        string accountId,
        string projectId,
        string fileName,
        CancellationToken cancellationToken = default)
    {
        return await GeneratePreviewAsync(accountId, projectId, fileName, null, cancellationToken);
    }

    public async Task<ProjectWebPreviewResult> GenerateQueuedPreviewAsync(
        string accountId,
        string projectId,
        string fileName,
        string runId,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(runId);
        return await GeneratePreviewAsync(accountId, projectId, fileName, runId, cancellationToken);
    }

    private async Task<ProjectWebPreviewResult> GeneratePreviewAsync(
        string accountId,
        string projectId,
        string fileName,
        string? queuedRunId,
        CancellationToken cancellationToken)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(fileName);

        ProjectWebPreviewConcurrencyLease? accountConcurrencyLease = queuedRunId is not null &&
            _reservedAccountConcurrencyLeases.TryRemove(queuedRunId, out var reservedAccountConcurrencyLease)
                ? reservedAccountConcurrencyLease
                : null;

        ProjectWebPreviewConverterDescriptor? selectedConverter = null;

        try
        {
        if (!IsSafeFileName(fileName))
        {
            if (queuedRunId is not null)
            {
                await CompletePreviewFailureAsync(queuedRunId, fileName, "package_not_found", "Package file name is invalid.", CancellationToken.None);
            }

            return Failure(projectId, "", fileName, "package_not_found");
        }

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            if (queuedRunId is not null)
            {
                await CompletePreviewFailureAsync(queuedRunId, fileName, "project_not_found", "Project does not exist or does not belong to the current account.", CancellationToken.None);
            }

            return Failure(projectId, "", fileName, "project_not_found");
        }

        var projectRoot = Path.GetFullPath(project.RepoPath);
        if (!WorkspacePathPolicy.IsUnderRoot(_options.HostedWorkspaceRoot, projectRoot))
        {
            throw new InvalidOperationException("Project repository path escaped the hosted workspace root.");
        }

        var packagePath = ResolveUnderProject(projectRoot, $"exports/{fileName}");
        if (!File.Exists(packagePath))
        {
            if (queuedRunId is not null)
            {
                await CompletePreviewFailureAsync(queuedRunId, fileName, "package_not_found", "Package file no longer exists.", CancellationToken.None);
            }

            return Failure(projectId, "", fileName, "package_not_found");
        }

        var budgetFailure = ValidatePackageScanBudget(packagePath);
        if (budgetFailure is not null)
        {
            if (queuedRunId is not null)
            {
                await CompletePreviewFailureAsync(queuedRunId, fileName, budgetFailure.Value.Code, budgetFailure.Value.Message, CancellationToken.None);
            }

            return Failure(projectId, queuedRunId ?? "", fileName, budgetFailure.Value.Code);
        }

        PrunePreviewScratchDirectories(projectRoot);

        if (queuedRunId is null &&
            (project.BootstrapStatus == "running" ||
             await _metadataStore.HasRunnerLockAsync(project.ProjectId, cancellationToken)))
        {
            return Failure(projectId, "", fileName, "project_busy");
        }

        var runId = queuedRunId ?? await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, RunType, cancellationToken);
        await _metadataStore.UpdateRunProgressAsync(
            runId,
            RunType,
            fileName,
            "Queued Godot 3 browser preview.",
            cancellationToken);
        if (accountConcurrencyLease is null)
        {
            var accountConcurrency = await _webPreviewConcurrencyLimiter.TryAcquireAsync(project.AccountId, cancellationToken);
            if (accountConcurrency.Lease is null)
            {
                var failureCode = accountConcurrency.FailureCode ?? "user_web_preview_concurrency_limit_exceeded";
                await CompletePreviewFailureAsync(
                    runId,
                    fileName,
                    failureCode,
                    "This account already has a web preview generation running.",
                    CancellationToken.None);
                return Failure(projectId, runId, fileName, failureCode);
            }

            accountConcurrencyLease = accountConcurrency.Lease;
        }

        await using var webPreviewQueueLease = await _webPreviewQueue.EnterAsync(
            runId,
            project.AccountId,
            project.ProjectId,
            RunType,
            cancellationToken);
        var locked = await _metadataStore.TryAcquireRunnerLockAsync(project.ProjectId, runId, cancellationToken);
        if (!locked)
        {
            await CompletePreviewFailureAsync(
                runId,
                fileName,
                "project_busy",
                "Project runner lock is already held.",
                cancellationToken);
            return Failure(projectId, runId, fileName, "project_busy");
        }

        var started = await _metadataStore.TryMarkRunStartedAsync(runId, webPreviewQueueLease.QueuePositionAtStart, cancellationToken);
        if (!started)
        {
            await _metadataStore.ReleaseRunnerLockAsync(project.ProjectId, runId, CancellationToken.None);
            return Failure(projectId, runId, fileName, "web_preview_run_not_active");
        }

        await _metadataStore.UpdateRunProgressAsync(
            runId,
            RunType,
            fileName,
            "Generating Godot 3 browser preview.",
            cancellationToken);

        string? workPreviewRoot = null;
        PackageInfo? packageInfo = null;

        try
        {
            var godot3Bin = ResolveGodot3Bin();
            if (godot3Bin is null)
            {
                await CompletePreviewFailureAsync(runId, fileName, "godot3_bin_not_configured", "PHASEA_GODOT3_BIN does not point to an existing Godot 3 executable.", cancellationToken);
                return Failure(projectId, runId, fileName, "godot3_bin_not_configured");
            }

            if (string.IsNullOrWhiteSpace(ResolvePreviewSigningSecret()))
            {
                await CompletePreviewFailureAsync(runId, fileName, "web_preview_signing_secret_missing", "A server-side signing secret is required before publishing guest web previews.", cancellationToken);
                return Failure(projectId, runId, fileName, "web_preview_signing_secret_missing");
            }

            packageInfo = ExtractPackageInfo(project, fileName, packagePath);
            if (!TryResolveConverter(packageInfo, out var converter, out var converterFailureCode, out var converterFailureMessage))
            {
                await CompletePreviewFailureAsync(runId, fileName, converterFailureCode, converterFailureMessage, cancellationToken);
                return Failure(projectId, runId, fileName, converterFailureCode);
            }
            selectedConverter = converter;
            packageInfo = packageInfo with
            {
                WebPreviewManifest = packageInfo.WebPreviewManifest with
                {
                    ConversionContract = BuildWebPreviewContract(converter, packageInfo.MainScene, packageInfo.Scenes, packageInfo.Texts.Count)
                }
            };

            var previewId = ComputePreviewIdFromSha(packagePath, packageInfo.PackageSha256);
            var previewRelativeRoot = $"{PreviewRootDirectory}/{previewId}";
            var previewRoot = ResolveUnderProject(projectRoot, previewRelativeRoot);
            workPreviewRoot = ResolveUnderProject(projectRoot, $"{PreviewRootDirectory}/.{previewId}.{runId}.build");
            var godotProjectRoot = Path.Combine(workPreviewRoot, "godot3-project");
            var webRoot = Path.Combine(workPreviewRoot, "web");
            DeleteDirectoryIfExists(workPreviewRoot);

            Directory.CreateDirectory(godotProjectRoot);
            Directory.CreateDirectory(webRoot);
            CreateGodot3Project(godotProjectRoot, packageInfo, converter);

            var exportResult = await ExportGodot3ProjectAsync(godot3Bin, godotProjectRoot, webRoot, runId, cancellationToken);
            if (exportResult.Process.ExitCode != 0 || !HasExpectedWebExport(webRoot))
            {
                var stderr = string.IsNullOrWhiteSpace(exportResult.Process.Stderr)
                    ? "Godot3 export did not produce index.html/index.js/index.wasm/index.pck."
                    : exportResult.Process.Stderr;
                await CompletePreviewFailureAsync(runId, fileName, "godot3_export_failed", stderr, CancellationToken.None, exportResult.Process.Stdout, converter.Mode);
                return Failure(projectId, runId, fileName, "godot3_export_failed");
            }

            var createdUtc = DateTimeOffset.UtcNow.ToString("O");
            var assetVersion = ComputeWebAssetVersion(packageInfo.PackageSha256, createdUtc);
            var previewUrl = $"/projects/{project.ProjectId}/web-previews/{previewId}/index.html?v={Uri.EscapeDataString(createdUtc)}";
            var sourceSceneSha256 = ResolveConverterSourceSceneSha256(packageInfo, converter);
            var textCatalogSha256 = ResolveConverterTextCatalogSha256(packageInfo, converter);
            var manifestJson = SerializeWebPreviewManifest(packageInfo.WebPreviewManifest);
            var manifestSha256 = ComputeStringSha256(manifestJson);
            var previewSignature = ComputePreviewSignature(
                project.ProjectId,
                previewId,
                packageInfo.PackageSha256,
                assetVersion,
                createdUtc,
                converter.Mode,
                converter.Id,
                converter.CompatibilityId,
                sourceSceneSha256,
                textCatalogSha256,
                manifestSha256);

            var loadingEstimatePatched = false;
            try
            {
                loadingEstimatePatched = PatchGodotWebShell(
                    Path.Combine(webRoot, "index.html"),
                    Path.Combine(webRoot, "index.js"),
                    assetVersion);
            }
            catch (InvalidOperationException ex)
            {
                await CompletePreviewFailureAsync(runId, fileName, "godot3_shell_patch_failed", ex.Message, CancellationToken.None, converterMode: converter.Mode);
                return Failure(projectId, runId, fileName, "godot3_shell_patch_failed");
            }

            await ProjectWebPreviewContractWriter.WriteAsync(
                webRoot,
                new ProjectWebPreviewContractSnapshot(
                    "",
                    project.ProjectId,
                    project.Name,
                    packageInfo.GameName,
                    packageInfo.GameTypeId,
                    packageInfo.GameTypeGuide,
                    fileName,
                    packageInfo.PackageSha256,
                    packageInfo.PackageSizeBytes,
                    previewId,
                    assetVersion,
                    converter.Mode,
                    converter.Id,
                    converter.CompatibilityId,
                    packageInfo.WebPreviewManifest.ConversionContract.FidelityTier,
                    packageInfo.WebPreviewManifest.ConversionContract.PlayableSurface,
                    sourceSceneSha256,
                    textCatalogSha256,
                    manifestSha256,
                    createdUtc),
                cancellationToken);

            var data = new
            {
                schema_version = PreviewSchemaVersion,
                project_id = project.ProjectId,
                project_name = project.Name,
                game_name = packageInfo.GameName,
                game_type_source = project.GameTypeSource,
                game_type_id = packageInfo.GameTypeId,
                game_type_guide = packageInfo.GameTypeGuide,
                package_file = fileName,
                package_sha256 = packageInfo.PackageSha256,
                package_size_bytes = packageInfo.PackageSizeBytes,
                preview_id = previewId,
                preview_url = previewUrl,
                asset_version = assetVersion,
                converter_id = converter.Id,
                converter_compatibility_id = converter.CompatibilityId,
                converter_coverage = converter.CoverageSummary,
                mode = converter.Mode,
                godot3_export_mode = exportResult.ExportMode,
                godot3_bin = godot3Bin,
                loading_estimate_patched = loadingEstimatePatched,
                created_utc = createdUtc,
                signature = previewSignature,
                source_scene = converter.SourceScenePath,
                source_scene_sha256 = sourceSceneSha256,
                text_catalog = converter.TextCatalogPath,
                text_catalog_sha256 = textCatalogSha256,
                manifest_sha256 = manifestSha256,
                web_preview_manifest = packageInfo.WebPreviewManifest,
                main_scene = "res://Main.tscn",
                scenes = packageInfo.Scenes,
                text_key_count = packageInfo.Texts.Count
            };

            await File.WriteAllTextAsync(
                Path.Combine(workPreviewRoot, PreviewManifestFileName),
                manifestJson,
                new UTF8Encoding(false),
                cancellationToken);

            await File.WriteAllTextAsync(
                Path.Combine(workPreviewRoot, "preview-data.json"),
                JsonSerializer.Serialize(data, GodotJsonOptions),
                new UTF8Encoding(false),
                cancellationToken);

            var exportedFiles = Directory
                .EnumerateFiles(webRoot)
                .Select(Path.GetFileName)
                .Order(StringComparer.OrdinalIgnoreCase)
                .ToArray();

            ReplaceDirectory(workPreviewRoot, previewRoot);
            workPreviewRoot = null;

            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(
                runId,
                project.ProjectId,
                PreviewArtifactType,
                $"{previewRelativeRoot}/web/index.html",
                "Guest Godot 3 HTML5 playable preview page"), cancellationToken);
            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(
                runId,
                project.ProjectId,
                "project-web-preview-manifest",
                $"{previewRelativeRoot}/{PreviewManifestFileName}",
                "Godot 3 web preview conversion manifest"), cancellationToken);
            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(
                runId,
                project.ProjectId,
                "project-web-preview-data",
                $"{previewRelativeRoot}/preview-data.json",
                "Godot 3 web preview signed readback data"), cancellationToken);
            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(
                runId,
                project.ProjectId,
                "project-web-preview-contract",
                $"{previewRelativeRoot}/web/{ProjectWebPreviewContractWriter.FileName}",
                "Guest-readable web preview package and converter contract"), cancellationToken);

            var evidence = JsonSerializer.Serialize(new
            {
                run_type = RunType,
                preview_id = previewId,
                preview_url = previewUrl,
                mode = converter.Mode,
                package_file = fileName,
                package_sha256 = packageInfo.PackageSha256,
                game_type_id = packageInfo.GameTypeId,
                game_type_guide = packageInfo.GameTypeGuide,
                asset_version = assetVersion,
                source_scene = converter.SourceScenePath,
                source_scene_sha256 = sourceSceneSha256,
                text_catalog = converter.TextCatalogPath,
                text_catalog_sha256 = textCatalogSha256,
                converter_id = converter.Id,
                converter_compatibility_id = converter.CompatibilityId,
                converter_coverage = converter.CoverageSummary,
                manifest_sha256 = manifestSha256,
                web_preview_manifest = packageInfo.WebPreviewManifest,
                godot3_export = new
                {
                    mode = exportResult.ExportMode,
                    exit_code = exportResult.Process.ExitCode,
                    stdout_tail = Tail(exportResult.Process.Stdout, 4000),
                    stderr_tail = Tail(exportResult.Process.Stderr, 4000),
                    files = exportedFiles
                },
                created_utc = createdUtc
            }, JsonOptions);
            await _metadataStore.CompleteRunAsync(runId, "succeeded", 0, $"Created {previewUrl}", "", evidence, cancellationToken);
            var artifacts = await _metadataStore.ListArtifactsForRunAsync(runId, cancellationToken);

            return new ProjectWebPreviewResult(
                project.ProjectId,
                runId,
                "succeeded",
                fileName,
                previewId,
                previewUrl,
                converter.Mode,
                createdUtc,
                null,
                artifacts);
        }
        catch (Exception ex)
        {
            var evidence = JsonSerializer.Serialize(new
            {
                run_type = RunType,
                package_file = fileName,
                package_sha256 = packageInfo?.PackageSha256,
                failure_code = "web_preview_failed",
                mode = selectedConverter?.Mode ?? ""
            }, JsonOptions);
            await _metadataStore.CompleteRunAsync(runId, "failed", 500, "", ex.ToString(), evidence, CancellationToken.None);
            return Failure(projectId, runId, fileName, "web_preview_failed");
        }
        finally
        {
            try
            {
                if (!string.IsNullOrWhiteSpace(workPreviewRoot))
                {
                    TryDeleteDirectoryIfExists(workPreviewRoot);
                }
            }
            finally
            {
                await _metadataStore.ReleaseRunnerLockAsync(project.ProjectId, runId, CancellationToken.None);
                PrunePreviewScratchDirectories(projectRoot);
            }
        }
        }
        finally
        {
            if (accountConcurrencyLease is not null)
            {
                await accountConcurrencyLease.DisposeAsync();
            }
        }
    }

    public async Task<string?> ValidatePreviewQueueAsync(
        string accountId,
        string projectId,
        string fileName,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(fileName);

        if (!IsSafeFileName(fileName))
        {
            return "package_not_found";
        }

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            return "project_not_found";
        }

        var projectRoot = Path.GetFullPath(project.RepoPath);
        if (!WorkspacePathPolicy.IsUnderRoot(_options.HostedWorkspaceRoot, projectRoot))
        {
            throw new InvalidOperationException("Project repository path escaped the hosted workspace root.");
        }

        var packagePath = ResolveUnderProject(projectRoot, $"exports/{fileName}");
        if (!File.Exists(packagePath))
        {
            return "package_not_found";
        }

        var budgetFailure = ValidatePackageScanBudget(packagePath);
        if (budgetFailure is not null)
        {
            return budgetFailure.Value.Code;
        }

        if (project.BootstrapStatus == "running" ||
            await _metadataStore.HasRunnerLockAsync(project.ProjectId, cancellationToken))
        {
            return "project_busy";
        }

        return null;
    }

    public async Task<ProjectWebPreviewQueueResult> QueuePreviewAsync(
        string accountId,
        string projectId,
        string fileName,
        CancellationToken cancellationToken = default)
    {
        var failureCode = await ValidatePreviewQueueAsync(accountId, projectId, fileName, cancellationToken);
        if (!string.IsNullOrWhiteSpace(failureCode))
        {
            return new ProjectWebPreviewQueueResult(projectId, "", "failed", fileName, failureCode);
        }

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            return new ProjectWebPreviewQueueResult(projectId, "", "failed", fileName, "project_not_found");
        }

        var accountConcurrency = await _webPreviewConcurrencyLimiter.TryAcquireAsync(project.AccountId, cancellationToken);
        if (accountConcurrency.Lease is null)
        {
            return new ProjectWebPreviewQueueResult(
                project.ProjectId,
                "",
                "failed",
                fileName,
                accountConcurrency.FailureCode ?? "user_web_preview_concurrency_limit_exceeded");
        }

        ProjectWebPreviewConcurrencyLease? reservedLease = accountConcurrency.Lease;
        try
        {
        var runId = await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, RunType, cancellationToken);
        await _metadataStore.UpdateRunProgressAsync(
            runId,
            RunType,
            fileName,
            "Queued Godot 3 browser preview.",
            cancellationToken);
        if (!_reservedAccountConcurrencyLeases.TryAdd(runId, reservedLease))
        {
            await reservedLease.DisposeAsync();
            reservedLease = null;
            return new ProjectWebPreviewQueueResult(project.ProjectId, "", "failed", fileName, "user_web_preview_concurrency_limit_exceeded");
        }

        reservedLease = null;

        return new ProjectWebPreviewQueueResult(project.ProjectId, runId, "queued", fileName, null);
        }
        finally
        {
            if (reservedLease is not null)
            {
                await reservedLease.DisposeAsync();
            }
        }
    }

    public async Task RecordUnexpectedPreviewFailureAsync(
        string runId,
        string fileName,
        Exception exception,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(runId);
        ArgumentException.ThrowIfNullOrWhiteSpace(fileName);
        ArgumentNullException.ThrowIfNull(exception);

        await CompletePreviewFailureAsync(
            runId,
            fileName,
            "web_preview_background_failed",
            exception.ToString(),
            cancellationToken);
    }

    public async Task<ProjectWebPreviewPackageStatus> ResolvePreviewForPackageAsync(ProjectSnapshot project, string fileName, CancellationToken cancellationToken = default)
    {
        var runs = await _metadataStore.ListRunsForProjectAsync(project.ProjectId, cancellationToken);
        var latestRunsByPackage = BuildLatestWebPreviewRunsByPackage(runs);
        return ResolvePreviewForPackage(project, fileName, latestRunsByPackage);
    }

    public IReadOnlyDictionary<string, ProjectWebPreviewPackageStatus> ResolvePreviewsForPackages(
        ProjectSnapshot project,
        IEnumerable<string> fileNames,
        IReadOnlyList<RunSnapshot> runs)
    {
        ArgumentNullException.ThrowIfNull(project);
        ArgumentNullException.ThrowIfNull(fileNames);
        ArgumentNullException.ThrowIfNull(runs);

        var latestRunsByPackage = BuildLatestWebPreviewRunsByPackage(runs);
        var results = new Dictionary<string, ProjectWebPreviewPackageStatus>(StringComparer.Ordinal);
        foreach (var fileName in fileNames.Distinct(StringComparer.Ordinal))
        {
            results[fileName] = ResolvePreviewForPackage(project, fileName, latestRunsByPackage);
        }

        return results;
    }

    private ProjectWebPreviewPackageStatus ResolvePreviewForPackage(
        ProjectSnapshot project,
        string fileName,
        IReadOnlyDictionary<string, RunSnapshot> latestRunsByPackage)
    {
        if (!IsSafeFileName(fileName))
        {
            return new ProjectWebPreviewPackageStatus("missing", null, null, null, null);
        }

        var packagePath = ResolveUnderProject(project.RepoPath, $"exports/{fileName}");
        if (!File.Exists(packagePath))
        {
            return new ProjectWebPreviewPackageStatus("missing", null, null, null, null);
        }

        var previewId = ComputePreviewId(project.ProjectId, packagePath);
        var previewRoot = ResolveUnderProject(project.RepoPath, $"{PreviewRootDirectory}/{previewId}");
        var indexPath = Path.Combine(previewRoot, "web", "index.html");
        var dataPath = Path.Combine(previewRoot, "preview-data.json");
        if (!File.Exists(indexPath) ||
            !TryReadReadyPreviewData(dataPath, project.ProjectId, previewId, out var readyData, allowLegacyPreview: false))
        {
            if (File.Exists(indexPath) &&
                TryReadReadyPreviewData(dataPath, project.ProjectId, previewId, out var staleData))
            {
                return new ProjectWebPreviewPackageStatus(
                    "stale",
                    previewId,
                    null,
                    staleData.Mode,
                    staleData.CreatedUtc,
                    FailureCode: "converter_schema_outdated",
                    FidelityTier: staleData.FidelityTier,
                    PlayableSurface: staleData.PlayableSurface,
                    GameTypeId: staleData.GameTypeId,
                    GameTypeGuide: staleData.GameTypeGuide);
            }

            if (!latestRunsByPackage.TryGetValue(fileName, out var latestRun))
            {
                return new ProjectWebPreviewPackageStatus("not_generated", previewId, null, null, null);
            }

            var status = latestRun.Status switch
            {
                "queued" => "queued",
                "running" => "running",
                "failed" or "blocked" or "cancel" => "failed",
                _ => "not_generated"
            };
            var updatedUtc = latestRun.FinishedUtc ?? latestRun.ProgressUpdatedUtc ?? latestRun.StartedUtc ?? latestRun.CreatedUtc;
            var queueItem = status is "queued" or "running"
                ? FindWebPreviewQueueItem(project.AccountId, latestRun.RunId)
                : null;
            return new ProjectWebPreviewPackageStatus(
                status,
                previewId,
                null,
                null,
                null,
                latestRun.RunId,
                status == "failed" ? ReadFailureCode(latestRun) : null,
                updatedUtc,
                queueItem?.Position,
                queueItem?.EstimatedWaitSeconds);
        }

        latestRunsByPackage.TryGetValue(fileName, out var latestReadyRun);
        var latestFailure = latestReadyRun is not null &&
                            latestReadyRun.Status is "failed" or "blocked" or "cancel" &&
                            IsRunNewerThan(latestReadyRun, readyData.CreatedUtc)
            ? latestReadyRun
            : null;

        return new ProjectWebPreviewPackageStatus(
            "ready",
            previewId,
            $"/projects/{project.ProjectId}/web-previews/{previewId}/index.html?v={Uri.EscapeDataString(readyData.CreatedUtc)}",
            readyData.Mode,
            readyData.CreatedUtc,
            latestFailure?.RunId,
            latestFailure is null ? null : ReadFailureCode(latestFailure),
            latestFailure?.FinishedUtc ?? latestFailure?.ProgressUpdatedUtc ?? latestFailure?.StartedUtc ?? latestFailure?.CreatedUtc,
            FidelityTier: readyData.FidelityTier,
            PlayableSurface: readyData.PlayableSurface,
            GameTypeId: readyData.GameTypeId,
            GameTypeGuide: readyData.GameTypeGuide);
    }

    public async Task<ProjectWebPreviewReadResult?> ReadPreviewAsync(
        string projectId,
        string previewId,
        string? previewPath,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(previewId);

        if (!IsSafePathSegment(previewId))
        {
            return null;
        }

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null)
        {
            return null;
        }

        var previewContainer = ResolveUnderProject(project.RepoPath, $"{PreviewRootDirectory}/{previewId}");
        if (!TryReadReadyPreviewData(Path.Combine(previewContainer, "preview-data.json"), project.ProjectId, previewId, out _))
        {
            return null;
        }

        var relativePreviewPath = string.IsNullOrWhiteSpace(previewPath) ? "index.html" : previewPath.Replace('\\', '/');
        if (relativePreviewPath.StartsWith("/", StringComparison.Ordinal) ||
            relativePreviewPath.Split('/').Any(part => part is "" or "." or ".."))
        {
            return null;
        }

        var previewRoot = Path.Combine(previewContainer, "web");
        var fullPath = Path.GetFullPath(Path.Combine(previewRoot, relativePreviewPath.Replace('/', Path.DirectorySeparatorChar)));
        if (!WorkspacePathPolicy.IsUnderRoot(previewRoot, fullPath) || !File.Exists(fullPath))
        {
            return null;
        }

        return new ProjectWebPreviewReadResult(
            Path.GetFileName(fullPath),
            ResolveContentType(fullPath),
            fullPath);
    }

    public static bool IsImmutablePreviewAsset(string fileName)
    {
        return Path.GetExtension(fileName).ToLowerInvariant() switch
        {
            ".js" or ".wasm" or ".pck" or ".png" or ".jpg" or ".jpeg" or ".webp" or ".svg" or ".ttf" or ".otf" or ".woff" or ".woff2" or ".worklet" => true,
            _ => false
        };
    }

    public static ProjectWebPreviewHealth GetGodot3Health()
    {
        var godot3Bin = ResolveGodot3Bin();
        var templateDirectory = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "Godot",
            "templates",
            "3.6.2.stable");
        var hasHtml5Templates =
            File.Exists(Path.Combine(templateDirectory, "webassembly_debug.zip")) &&
            File.Exists(Path.Combine(templateDirectory, "webassembly_release.zip"));
        var binExists = !string.IsNullOrWhiteSpace(godot3Bin) && File.Exists(godot3Bin);
        return new ProjectWebPreviewHealth(
            binExists && hasHtml5Templates ? "healthy" : "unhealthy",
            godot3Bin,
            binExists,
            templateDirectory,
            hasHtml5Templates,
            "not_run",
            null);
    }

    public async Task<ProjectWebPreviewHealth> GetGodot3HealthAsync(CancellationToken cancellationToken = default)
    {
        var now = DateTimeOffset.UtcNow;
        if (_cachedHealthSmoke is not null && now - _cachedHealthSmokeUtc < HealthSmokeCacheTtl)
        {
            return _cachedHealthSmoke;
        }

        await HealthSmokeGate.WaitAsync(cancellationToken);
        try
        {
            now = DateTimeOffset.UtcNow;
            if (_cachedHealthSmoke is not null && now - _cachedHealthSmokeUtc < HealthSmokeCacheTtl)
            {
                return _cachedHealthSmoke;
            }

            var basic = GetGodot3Health() with
            {
                ExportTimeoutSeconds = _options.Godot3WebPreviewExportTimeoutSeconds,
                ExportInactivityTimeoutSeconds = _options.Godot3WebPreviewExportInactivityTimeoutSeconds
            };
            if (!string.Equals(basic.Status, "healthy", StringComparison.Ordinal) ||
                string.IsNullOrWhiteSpace(basic.Godot3Bin))
            {
                var skipped = basic with { SmokeStatus = "skipped" };
                _cachedHealthSmoke = skipped;
                _cachedHealthSmokeUtc = now;
                return skipped;
            }

            var tempRoot = Path.Combine(Path.GetTempPath(), $"phase-a-godot3-health-{Guid.NewGuid():N}");
            try
            {
            var godotProjectRoot = Path.Combine(tempRoot, "project");
            var webRoot = Path.Combine(tempRoot, "web");
            Directory.CreateDirectory(godotProjectRoot);
            Directory.CreateDirectory(webRoot);
            var encoding = new UTF8Encoding(false);
            File.WriteAllText(Path.Combine(godotProjectRoot, "project.godot"), """
; Engine configuration file.

config_version=4

[application]

config/name="PhaseA Godot3 Web Preview Health"
run/main_scene="res://Main.tscn"

[rendering]

quality/driver/driver_name="GLES2"
""", encoding);
            File.WriteAllText(Path.Combine(godotProjectRoot, "export_presets.cfg"), RenderExportPresets(), encoding);
            File.WriteAllText(Path.Combine(godotProjectRoot, "Main.tscn"), """
[gd_scene load_steps=2 format=2]

[ext_resource path="res://Main.gd" type="Script" id=1]

[node name="Main" type="Spatial"]
script = ExtResource( 1 )
""", encoding);
            File.WriteAllText(Path.Combine(godotProjectRoot, "Main.gd"), RenderPackageAdapterMainScript("generic"), encoding);
            File.WriteAllText(
                Path.Combine(godotProjectRoot, "preview-package-data.json"),
                """
{
  "game_name": "PhaseA Godot3 Web Preview Health",
  "project_name": "Health Smoke",
  "game_type_source": "generic",
  "package_file": "health.zip",
  "package_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "converter_coverage": "Health smoke validates the generated package adapter script.",
  "web_preview_manifest": {
    "main_scene": "res://Main.tscn",
    "scenes": ["Main.tscn"],
    "detected_capabilities": ["godot_package_zip", "godot_scene_inventory"],
    "text_key_count": 0
  }
}
""",
                encoding);

            var healthRunId = $"godot3-health-{Guid.NewGuid():N}";
            var result = await ExportGodot3ProjectAsync(
                basic.Godot3Bin,
                godotProjectRoot,
                webRoot,
                healthRunId,
                cancellationToken);
            var smokePassed = result.Process.ExitCode == 0 && HasExpectedWebExport(webRoot);
            var health = basic with
            {
                Status = smokePassed ? "healthy" : "unhealthy",
                SmokeStatus = smokePassed ? "passed" : "failed",
                SmokeError = smokePassed ? null : Tail(string.Join("\n", result.Process.Stdout, result.Process.Stderr), 2000)
            };
            _cachedHealthSmoke = health;
            _cachedHealthSmokeUtc = now;
            return health;
            }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or InvalidOperationException)
            {
            var health = basic with
            {
                Status = "unhealthy",
                SmokeStatus = "failed",
                SmokeError = ex.Message
            };
            _cachedHealthSmoke = health;
            _cachedHealthSmokeUtc = now;
            return health;
            }
            finally
            {
                TryDeleteExternalDirectory(tempRoot);
            }
        }
        finally
        {
            HealthSmokeGate.Release();
        }
    }

    private async Task<Godot3ExportResult> ExportGodot3ProjectAsync(
        string godot3Bin,
        string godotProjectRoot,
        string webRoot,
        string runId,
        CancellationToken cancellationToken)
    {
        var releaseResult = await RunGodot3ExportAsync(godot3Bin, godotProjectRoot, webRoot, runId, debug: false, cancellationToken);
        if (releaseResult.ExitCode == 0 && HasExpectedWebExport(webRoot))
        {
            return new Godot3ExportResult(
                releaseResult with { Stdout = $"Godot3 HTML5 release export succeeded.\n{releaseResult.Stdout}" },
                "release");
        }

        ClearWebExportOutput(webRoot);
        var debugResult = await RunGodot3ExportAsync(godot3Bin, godotProjectRoot, webRoot, runId, debug: true, cancellationToken);
        return new Godot3ExportResult(
            debugResult with
            {
                Stdout = string.Join(
                "\n",
                "Godot3 HTML5 release export failed; debug export fallback was attempted.",
                "Release stdout:",
                releaseResult.Stdout,
                "Debug stdout:",
                debugResult.Stdout),
                Stderr = string.Join(
                "\n",
                "Release stderr:",
                releaseResult.Stderr,
                "Debug stderr:",
                debugResult.Stderr)
            },
            debugResult.ExitCode == 0 && HasExpectedWebExport(webRoot) ? "debug" : "failed");
    }

    private async Task<HostedProcessResult> RunGodot3ExportAsync(
        string godot3Bin,
        string godotProjectRoot,
        string webRoot,
        string runId,
        bool debug,
        CancellationToken cancellationToken)
    {
        var godotDirectory = Path.GetDirectoryName(godot3Bin) ?? "";
        var environment = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            ["GODOT_BIN"] = godot3Bin,
            ["MESA_LOADER_DRIVER_OVERRIDE"] = "llvmpipe",
            ["GALLIUM_DRIVER"] = "llvmpipe",
            ["PATH"] = string.IsNullOrWhiteSpace(godotDirectory)
                ? Environment.GetEnvironmentVariable("PATH") ?? ""
                : $"{godotDirectory};{Environment.GetEnvironmentVariable("PATH") ?? ""}"
        };

        var command = new HostedProcessCommand(
                godot3Bin,
                [
                    "--path",
                    godotProjectRoot,
                    "--audio-driver",
                    "Dummy",
                    "--video-driver",
                    "GLES2",
                    "--no-window",
                    debug ? "--export-debug" : "--export",
                    "HTML5",
                    Path.Combine(webRoot, "index.html")
                ],
                godotProjectRoot,
                environment,
                RunId: runId,
                TotalTimeout: Godot3ExportTimeout,
                InactivityTimeout: Godot3ExportInactivityTimeout,
                ActivityWatchPaths: [webRoot],
                ActivityWatchPollInterval: TimeSpan.FromSeconds(1))
            .WithRunId(runId);

        return await _processRunner.RunAsync(command, cancellationToken);
    }

    private static void ClearWebExportOutput(string webRoot)
    {
        Directory.CreateDirectory(webRoot);
        foreach (var file in Directory.EnumerateFiles(webRoot))
        {
            try
            {
                File.Delete(file);
            }
            catch (IOException)
            {
            }
            catch (UnauthorizedAccessException)
            {
            }
        }
    }

    private static string? ResolveGodot3Bin()
    {
        var candidates = new[]
        {
            Environment.GetEnvironmentVariable("PHASEA_GODOT3_BIN"),
            @"C:\Godot\3.6.2\Godot_v3.6.2-stable_win64.exe",
            @"C:\Godot\3.6.2-mono\Godot_v3.6.2-stable_mono_win64\Godot_v3.6.2-stable_mono_win64.exe"
        };

        return candidates.FirstOrDefault(path => !string.IsNullOrWhiteSpace(path) && File.Exists(path));
    }

    private static string? ResolveCjkFontPath()
    {
        var configured = Environment.GetEnvironmentVariable("PHASEA_WEB_PREVIEW_CJK_FONT_PATH");
        if (!string.IsNullOrWhiteSpace(configured) && File.Exists(configured))
        {
            return configured;
        }

        var windowsFonts = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.Windows),
            "Fonts");
        var candidates = new[]
        {
            Path.Combine(windowsFonts, "simhei.ttf"),
            Path.Combine(windowsFonts, "msyh.ttc"),
            Path.Combine(windowsFonts, "simsun.ttc")
        };

        return candidates.FirstOrDefault(File.Exists);
    }

    private static void CreateGodot3Project(
        string projectRoot,
        PackageInfo packageInfo,
        ProjectWebPreviewConverterDescriptor converter)
    {
        if (string.Equals(converter.Id, Towerdemo2Converter.Id, StringComparison.Ordinal))
        {
            CreateTowerdemo2Godot3Project(projectRoot, packageInfo, converter);
            return;
        }

        CreateGenericGodotPackageProject(projectRoot, packageInfo, converter);
    }

    private static void CreateTowerdemo2Godot3Project(
        string projectRoot,
        PackageInfo packageInfo,
        ProjectWebPreviewConverterDescriptor converter)
    {
        WriteGodot3ProjectFiles(projectRoot, packageInfo, converter, RenderMainScene("Towerdemo2WebPreview"), RenderMainScript());
    }

    private static void CreateGenericGodotPackageProject(
        string projectRoot,
        PackageInfo packageInfo,
        ProjectWebPreviewConverterDescriptor converter)
    {
        WriteGodot3ProjectFiles(projectRoot, packageInfo, converter, RenderMainScene("GenericPackageWebPreview"), RenderPackageAdapterMainScript(converter.AdapterStyle));
    }

    private static void WriteGodot3ProjectFiles(
        string projectRoot,
        PackageInfo packageInfo,
        ProjectWebPreviewConverterDescriptor converter,
        string mainScene,
        string mainScript)
    {
        Directory.CreateDirectory(projectRoot);
        Directory.CreateDirectory(Path.Combine(projectRoot, "web"));
        Directory.CreateDirectory(Path.Combine(projectRoot, "Fonts"));
        var godotTextEncoding = new UTF8Encoding(false);
        var cjkFontPath = ResolveCjkFontPath();
        if (cjkFontPath is not null)
        {
            File.Copy(cjkFontPath, Path.Combine(projectRoot, "Fonts", "simhei.ttf"), overwrite: true);
            File.WriteAllText(Path.Combine(projectRoot, "Fonts", "ui_font.tres"), RenderUiFontResource(), godotTextEncoding);
        }

        File.WriteAllText(Path.Combine(projectRoot, "project.godot"), RenderProjectGodot(packageInfo), godotTextEncoding);
        File.WriteAllText(Path.Combine(projectRoot, "export_presets.cfg"), RenderExportPresets(), godotTextEncoding);
        File.WriteAllText(Path.Combine(projectRoot, "Main.tscn"), mainScene, godotTextEncoding);
        File.WriteAllText(Path.Combine(projectRoot, "Main.gd"), mainScript, new UTF8Encoding(false));
        File.WriteAllText(
            Path.Combine(projectRoot, PreviewManifestFileName),
            SerializeWebPreviewManifest(packageInfo.WebPreviewManifest),
            new UTF8Encoding(false));
        File.WriteAllText(
            Path.Combine(projectRoot, "preview-package-data.json"),
            JsonSerializer.Serialize(new
            {
                game_name = packageInfo.GameName,
                project_name = packageInfo.ProjectName,
                game_type_source = packageInfo.GameTypeSource,
                game_type_id = packageInfo.GameTypeId,
                game_type_guide = packageInfo.GameTypeGuide,
                converter_id = converter.Id,
                converter_compatibility_id = converter.CompatibilityId,
                converter_coverage = converter.CoverageSummary,
                mode = converter.Mode,
                source_scene = converter.SourceScenePath,
                source_scene_sha256 = ResolveConverterSourceSceneSha256(packageInfo, converter),
                text_catalog = converter.TextCatalogPath,
                text_catalog_sha256 = ResolveConverterTextCatalogSha256(packageInfo, converter),
                package_file = packageInfo.FileName,
                package_sha256 = packageInfo.PackageSha256,
                web_preview_manifest = packageInfo.WebPreviewManifest,
                texts = packageInfo.Texts
            }, GodotJsonOptions),
            new UTF8Encoding(false));
    }

    private static string RenderProjectGodot(PackageInfo packageInfo)
    {
        var gameName = EscapeGodotString(string.IsNullOrWhiteSpace(packageInfo.GameName) ? "Godot Package" : packageInfo.GameName);
        return $$"""
; Engine configuration file.

config_version=4

[application]

config/name="{{gameName}} Web Preview"
run/main_scene="res://Main.tscn"

[display]

window/size/width=1600
window/size/height=900
window/stretch/mode="viewport"
window/stretch/aspect="keep"

[rendering]

quality/driver/driver_name="GLES2"
quality/2d/use_pixel_snap=true
""";
    }

    private static string RenderUiFontResource()
    {
        return """
[gd_resource type="DynamicFont" load_steps=2 format=2]

[ext_resource path="res://Fonts/simhei.ttf" type="DynamicFontData" id=1]

[resource]
size = 18
font_data = ExtResource( 1 )
""";
    }

    private static string RenderExportPresets()
    {
        return """
[preset.0]

name="HTML5"
platform="HTML5"
runnable=true
custom_features=""
export_filter="all_resources"
include_filter="preview-package-data.json,web-preview-manifest.json,Fonts/*.ttf,Fonts/*.tres"
exclude_filter=""
export_path="web/index.html"
script_export_mode=1
script_encryption_key=""

[preset.0.options]

custom_template/debug=""
custom_template/release=""
variant/export_type=0
vram_texture_compression/for_desktop=true
vram_texture_compression/for_mobile=false
html/export_icon=false
html/custom_html_shell=""
html/head_include=""
html/canvas_resize_policy=2
html/focus_canvas_on_start=true
html/experimental_virtual_keyboard=false
progressive_web_app/enabled=false
""";
    }

    private static string RenderMainScene(string nodeName)
    {
        var safeNodeName = EscapeGodotString(string.IsNullOrWhiteSpace(nodeName) ? "WebPreview" : nodeName);
        return $$"""
[gd_scene load_steps=2 format=2]

[ext_resource path="res://Main.gd" type="Script" id=1]

[node name="{{safeNodeName}}" type="Spatial"]
script = ExtResource( 1 )
""";
    }

    private static string RenderMainScript()
    {
        return """
extends Spatial

var package_data = {}
var texts = {}
var phase = "ready"
var run_seed = 0
var room_index = 0
var wave = 0
var battles_won = 0
var hp = 100
var max_hp = 100
var souls = 0
var xp = 0
var level = 1
var next_level_xp = 30
var damage_bonus = 0
var cdr = 0
var guard = 0
var combo = 0
var reward_options = []
var level_options = []
var skills = {}
var enemies = []
var room_path = []
var last_log = "state_ready"
var last_hint = "hint_press_start"
var last_reward = ""
var last_levelup = ""
var roll_timer = 0.0
var pressure_timer = 0.0
var player = null
var enemy_bodies = []
var reward_door = null
var labels = {}
var buttons = {}
var ui_font = null

func _ready():
    load_package_data()
    create_world()
    create_ui()
    create_initial_state()
    reset_world_positions()
    render_all()

func load_package_data():
    package_data = {}
    texts = {}
    var file = File.new()
    if not file.file_exists("res://preview-package-data.json"):
        return
    if file.open("res://preview-package-data.json", File.READ) != OK:
        return
    var raw = file.get_as_text()
    file.close()
    if raw.strip_edges() == "":
        return
    var parsed = JSON.parse(raw)
    if parsed.error != OK or typeof(parsed.result) != TYPE_DICTIONARY:
        return
    package_data = parsed.result
    var parsed_texts = package_data.get("texts", {})
    if typeof(parsed_texts) == TYPE_DICTIONARY:
        texts = parsed_texts

func tr_text(key):
    if texts.has(key):
        return str(texts[key])
    var fallback = {
        "ui.start": "开始跑团",
        "ui.retry": "重新挑战",
        "ui.continue": "进入下一房间",
        "hud.header": "Towerdemo2：幻影塔试炼",
        "hud.controls": "WASD移动  鼠标转向  左键攻击  空格翻滚  右键/Q/E技能  1/2/3选择",
        "objective.ready": "目标：开始试炼并清掉第一轮敌人。",
        "objective.playing": "目标：清理当前波次敌人，保持走位与技能轮转。",
        "objective.levelup": "目标：完成升级选择，再进入奖励房。",
        "objective.rewarding": "目标：选择奖励并准备进入下一房间。",
        "objective.cleared": "完成：本房间闭环已达成，可以进入下一房间验证构筑变化。",
        "objective.dead": "失败：本局暂时结束，可保留灵魂货币后重新挑战。",
        "door.locked": "奖励门：未开启",
        "door.open": "奖励门：已开启",
        "reward.title": "奖励房：选择一个本局增益后继续深入。",
        "levelup.title": "升级三选一：本局强化会持续到本次跑团结束。"
    }
    return fallback.get(key, key)

func event_text(key):
    if texts.has(key):
        return str(texts[key])
    if key.begins_with("log_"):
        var dotted = "log." + key.substr(4, key.length())
        if texts.has(dotted):
            return str(texts[dotted])
    return tr_text(key)

func create_initial_state():
    phase = "ready"
    run_seed = 0
    room_index = 0
    wave = 0
    battles_won = 0
    hp = 100
    max_hp = 100
    souls = 0
    xp = 0
    level = 1
    next_level_xp = 30
    damage_bonus = 0
    cdr = 0
    guard = 0
    combo = 0
    reward_options = []
    level_options = []
    skills = {
        "basic": {"name": "Basic Combo", "cd": 0, "remain": 0},
        "right": {"name": "Right Cleave", "cd": 2, "remain": 0},
        "q": {"name": "Q Shock Ring", "cd": 3, "remain": 0},
        "e": {"name": "E Phantom Lance", "cd": 4, "remain": 0}
    }
    enemies = []
    room_path = []
    last_log = "state_ready"
    last_hint = "hint_press_start"

func create_world():
    var light = DirectionalLight.new()
    light.light_energy = 1.25
    light.rotation_degrees = Vector3(-54, 0, -35)
    add_child(light)

    var camera_rig = Spatial.new()
    camera_rig.name = "CameraRig"
    add_child(camera_rig)
    var camera = Camera.new()
    camera.name = "Camera"
    camera.current = true
    camera.fov = 58
    camera.translation = Vector3(0, 7.2, 9.5)
    camera.rotation_degrees = Vector3(-40, 0, 0)
    camera_rig.add_child(camera)

    var floor_body = StaticBody.new()
    floor_body.name = "Floor"
    add_child(floor_body)
    floor_body.add_child(mesh_instance(cube_mesh(Vector3(14, 0.25, 12)), Color(0.16, 0.15, 0.19), Vector3(0, -0.125, 0)))
    floor_body.add_child(collision_box(Vector3(14, 0.35, 12), Vector3(0, 0, 0)))

    add_wall("NorthWall", Vector3(0, 0.75, -6.1), Vector3(14, 1.5, 0.25))
    add_wall("SouthWall", Vector3(0, 0.75, 6.1), Vector3(14, 1.5, 0.25))
    add_wall("ObstacleA", Vector3(-2, 0.6, 0.8), Vector3(1.4, 1.2, 1.4))
    add_wall("ObstacleB", Vector3(2.2, 0.6, 0.2), Vector3(1.4, 1.2, 1.4))

    player = KinematicBody.new()
    player.name = "Player"
    add_child(player)
    player.add_child(capsule_actor(Color(0.35, 0.78, 0.92), 0.35, 1.5))
    player.add_child(collision_capsule(0.35, 1.5))

    var enemy_specs = [
        ["EnemyShadeA", Vector3(-3, 0, -2), Color(0.83, 0.22, 0.24)],
        ["EnemyShadeB", Vector3(3, 0, -2), Color(0.83, 0.22, 0.24)],
        ["EnemyLancerC", Vector3(0, 0, -4.2), Color(0.86, 0.74, 0.28)]
    ]
    for spec in enemy_specs:
        var body = KinematicBody.new()
        body.name = spec[0]
        body.translation = spec[1] + Vector3(0, 0.9, 0)
        add_child(body)
        body.add_child(capsule_actor(spec[2], 0.32, 1.3))
        body.add_child(collision_capsule(0.32, 1.3))
        enemy_bodies.append(body)

    reward_door = MeshInstance.new()
    reward_door.name = "RewardDoor"
    reward_door.mesh = cube_mesh(Vector3(2.2, 2.6, 0.25))
    reward_door.material_override = material(Color(0.86, 0.74, 0.28))
    reward_door.translation = Vector3(0, 1.3, -5.8)
    reward_door.visible = false
    add_child(reward_door)

func add_wall(name, pos, size):
    var body = StaticBody.new()
    body.name = name
    body.translation = pos
    add_child(body)
    body.add_child(mesh_instance(cube_mesh(size), Color(0.28, 0.26, 0.33), Vector3()))
    body.add_child(collision_box(size, Vector3()))

func cube_mesh(size):
    var mesh = CubeMesh.new()
    mesh.size = size
    return mesh

func material(color):
    var mat = SpatialMaterial.new()
    mat.albedo_color = color
    return mat

func mesh_instance(mesh, color, local_pos):
    var node = MeshInstance.new()
    node.mesh = mesh
    node.material_override = material(color)
    node.translation = local_pos
    return node

func capsule_actor(color, radius, height):
    var node = MeshInstance.new()
    var mesh = CapsuleMesh.new()
    mesh.radius = radius
    mesh.mid_height = max(0.1, height - radius * 2.0)
    node.mesh = mesh
    node.material_override = material(color)
    return node

func collision_box(size, local_pos):
    var collision = CollisionShape.new()
    var shape = BoxShape.new()
    shape.extents = size * 0.5
    collision.shape = shape
    collision.translation = local_pos
    return collision

func collision_capsule(radius, height):
    var collision = CollisionShape.new()
    var shape = CapsuleShape.new()
    shape.radius = radius
    shape.height = max(0.1, height - radius * 2.0)
    collision.shape = shape
    return collision

func create_ui():
    ui_font = load_ui_font()
    var layer = CanvasLayer.new()
    add_child(layer)
    var root = Control.new()
    root.anchor_right = 1
    root.anchor_bottom = 1
    layer.add_child(root)

    buttons.start = add_button(root, "StartButton", tr_text("ui.start"), Rect2(44, 44, 176, 44), "_on_start_pressed")
    buttons.retry = add_button(root, "RetryButton", tr_text("ui.retry"), Rect2(44, 96, 176, 44), "_on_retry_pressed")
    buttons.continue = add_button(root, "ContinueButton", tr_text("ui.continue"), Rect2(44, 96, 216, 44), "_on_continue_pressed")

    labels.header = add_label(root, Rect2(44, 150, 680, 28), tr_text("hud.header"))
    labels.stats = add_label(root, Rect2(44, 182, 680, 28), "")
    labels.objective = add_label(root, Rect2(44, 214, 760, 28), "")
    labels.skills = add_label(root, Rect2(44, 246, 880, 28), tr_text("hud.controls"))
    labels.cooldown = add_label(root, Rect2(44, 278, 680, 28), "")
    labels.range = add_label(root, Rect2(44, 310, 760, 28), "")
    labels.room = add_label(root, Rect2(44, 356, 900, 28), "")
    labels.door = add_label(root, Rect2(44, 388, 720, 28), "")
    labels.route = add_label(root, Rect2(44, 420, 1000, 28), "")
    labels.battle = add_label(root, Rect2(44, 468, 760, 28), "")
    labels.log = add_label(root, Rect2(44, 500, 960, 28), "")
    labels.hint = add_label(root, Rect2(44, 532, 960, 28), "")
    labels.reward_title = add_label(root, Rect2(960, 110, 520, 30), tr_text("reward.title"))
    buttons.reward1 = add_button(root, "RewardButton1", "", Rect2(960, 150, 420, 42), "_on_reward1")
    buttons.reward2 = add_button(root, "RewardButton2", "", Rect2(960, 198, 420, 42), "_on_reward2")
    buttons.reward3 = add_button(root, "RewardButton3", "", Rect2(960, 246, 420, 42), "_on_reward3")
    labels.level_title = add_label(root, Rect2(960, 330, 520, 30), tr_text("levelup.title"))
    buttons.level1 = add_button(root, "ChoiceButton1", "", Rect2(960, 370, 460, 42), "_on_level1")
    buttons.level2 = add_button(root, "ChoiceButton2", "", Rect2(960, 418, 460, 42), "_on_level2")
    buttons.level3 = add_button(root, "ChoiceButton3", "", Rect2(960, 466, 460, 42), "_on_level3")

func add_label(parent, rect, text):
    var label = Label.new()
    label.rect_position = rect.position
    label.rect_size = rect.size
    label.text = text
    if ui_font != null:
        label.add_font_override("font", ui_font)
    parent.add_child(label)
    return label

func add_button(parent, name, text, rect, method):
    var button = Button.new()
    button.name = name
    button.rect_position = rect.position
    button.rect_size = rect.size
    button.text = text
    if ui_font != null:
        button.add_font_override("font", ui_font)
    button.connect("pressed", self, method)
    parent.add_child(button)
    return button

func load_ui_font():
    var font = load("res://Fonts/ui_font.tres")
    if font is DynamicFont:
        return font
    return null

func _physics_process(delta):
    if phase != "playing":
        return
    roll_timer = max(0, roll_timer - delta)
    apply_player_motion(delta)
    update_enemy_pressure(delta)
    sync_enemy_bodies(delta)

func _input(event):
    if event is InputEventMouseButton and event.pressed:
        if event.button_index == BUTTON_LEFT:
            simulate_attack("basic")
        elif event.button_index == BUTTON_RIGHT:
            simulate_attack("right")
    elif event is InputEventKey and event.pressed and not event.echo:
        if event.scancode == KEY_ENTER:
            if phase == "ready":
                start_run()
            elif phase == "cleared":
                continue_run()
        elif event.scancode == KEY_SPACE:
            simulate_roll()
        elif event.scancode == KEY_Q:
            simulate_attack("q")
        elif event.scancode == KEY_E:
            simulate_attack("e")
        elif event.scancode == KEY_R and phase == "dead":
            retry_run()
        elif event.scancode == KEY_1:
            choose_primary_action(0)
        elif event.scancode == KEY_2:
            choose_primary_action(1)
        elif event.scancode == KEY_3:
            choose_primary_action(2)

func apply_player_motion(delta):
    var dir = Vector3()
    if Input.is_key_pressed(KEY_W):
        dir.z -= 1
    if Input.is_key_pressed(KEY_S):
        dir.z += 1
    if Input.is_key_pressed(KEY_A):
        dir.x -= 1
    if Input.is_key_pressed(KEY_D):
        dir.x += 1
    if dir.length() > 0:
        dir = dir.normalized()
    var speed = 9.0 if roll_timer > 0 else 5.0
    player.move_and_slide(dir * speed, Vector3.UP)
    player.translation.x = clamp(player.translation.x, -6.3, 6.3)
    player.translation.z = clamp(player.translation.z, -5.3, 5.3)

func sync_enemy_bodies(delta):
    for i in range(enemy_bodies.size()):
        var body = enemy_bodies[i]
        var alive = i < enemies.size() and enemies[i].alive
        body.visible = alive
        if alive:
            var to_player = player.translation - body.translation
            to_player.y = 0
            if to_player.length() > 0.7:
                body.move_and_slide(to_player.normalized() * (1.0 + wave * 0.2), Vector3.UP)

func update_enemy_pressure(delta):
    pressure_timer += delta
    if pressure_timer >= 3.0:
        pressure_timer = 0
        resolve_enemy_pressure()
        render_all()

func reset_world_positions():
    if player:
        player.translation = Vector3(0, 0.9, 4)
    var positions = [Vector3(-3, 0.9, -2), Vector3(3, 0.9, -2), Vector3(0, 0.9, -4.2)]
    for i in range(enemy_bodies.size()):
        enemy_bodies[i].translation = positions[i]

func start_run():
    run_seed += 17
    if run_seed == 17:
        run_seed = 4117
    room_path = build_room_path(run_seed)
    phase = "playing"
    room_index = 1
    wave = 1
    reward_options = []
    level_options = []
    last_log = "run_start"
    last_hint = "hint_wave1"
    reset_world_positions()
    spawn_wave()
    render_all()

func continue_run():
    if phase != "cleared":
        return
    room_index += 1
    wave = 1
    hp = min(max_hp, hp + 10)
    phase = "playing"
    reward_options = []
    level_options = []
    last_log = "log_elite_room_entered" if current_room_type() == "elite" else "log_room_continue"
    last_hint = "hint_elite_room" if current_room_type() == "elite" else "hint_next_room"
    reset_world_positions()
    spawn_wave()
    render_all()

func retry_run():
    var kept_souls = souls
    create_initial_state()
    souls = kept_souls
    start_run()
    last_log = "log_retry_started"
    last_hint = "hint_retry_started"
    render_all()

func simulate_roll():
    if phase != "playing":
        return
    roll_timer = 0.75
    tick_cooldowns("")
    last_log = "log_roll_window"
    last_hint = "hint_counter_window"
    render_all()

func simulate_attack(skill):
    if phase != "playing":
        return
    if skills[skill].remain > 0:
        last_log = "log_cooldown_blocked"
        last_hint = "hint_cooldown_blocked"
        render_all()
        return
    var hit_count = get_hit_count(skill)
    resolve_attack_turn(skill, hit_count, roll_timer > 0)
    render_all()

func resolve_attack_turn(skill, hit_count, dodged):
    combo = (combo % 3) + 1 if skill == "basic" else 1
    var log_key = "log_attack_whiff"
    if hit_count > 0:
        var damage = resolve_damage(skill)
        for i in range(enemies.size()):
            if hit_count <= 0:
                break
            if enemies[i].alive:
                enemies[i].health -= damage
                hit_count -= 1
                log_key = "log_attack_hit"
                if enemies[i].health <= 0:
                    enemies[i].alive = false
                    xp += enemies[i].xp
                    souls += enemies[i].souls
                    log_key = "log_enemy_defeated"
    if enemies_remaining() > 0:
        var counter = 0 if dodged else max(0, 5 + wave * 2 + enemies_remaining() * 2 - guard)
        hp = max(0, hp - counter)
        if counter == 0:
            log_key = "log_counter_avoided"
    tick_cooldowns(skill)
    last_log = log_key
    last_hint = resolve_skill_hint(skill, log_key != "log_attack_whiff")
    if hp <= 0:
        phase = "dead"
        last_log = "log_death"
        last_hint = "hint_retry"
        return
    if enemies_remaining() > 0:
        return
    if wave < 2:
        wave += 1
        last_log = "log_wave_cleared"
        last_hint = "hint_wave2"
        spawn_wave()
        return
    battles_won += 1
    if xp >= next_level_xp:
        phase = "levelup"
        level_options = ["levelup_damage", "levelup_vitality", "levelup_rhythm"]
        reward_options = []
        last_log = "log_levelup_ready"
        last_hint = "hint_levelup_choice"
    else:
        phase = "rewarding"
        reward_options = ["reward_heal", "reward_soul", "reward_guard"]
        level_options = []
        last_log = "log_reward_ready"
        last_hint = "hint_reward_choice"

func resolve_enemy_pressure():
    if phase != "playing":
        return
    hp = max(0, hp - max(0, 8 + wave * 3 + enemies_remaining() * 2 - guard))
    tick_cooldowns("")
    if hp <= 0:
        phase = "dead"
        last_log = "log_death"
        last_hint = "hint_retry"
    else:
        last_log = "log_enemy_pressure"
        last_hint = "hint_pressure"

func choose_primary_action(index):
    if phase == "levelup":
        apply_levelup(index)
    elif phase == "rewarding":
        apply_reward(index)

func apply_levelup(index):
    if phase != "levelup":
        return
    var id = level_options[index] if index < level_options.size() else "levelup_damage"
    last_levelup = id
    if id == "levelup_vitality":
        max_hp += 20
        hp += 20
    elif id == "levelup_rhythm":
        cdr += 1
        for key in skills.keys():
            if key != "basic":
                skills[key].cd = max(1, skills[key].cd - 1)
                skills[key].remain = max(0, skills[key].remain - 1)
    else:
        damage_bonus += 8
    level += 1
    next_level_xp += 40
    phase = "rewarding"
    reward_options = ["reward_heal", "reward_soul", "reward_guard"]
    level_options = []
    last_log = "log_levelup_applied"
    last_hint = "hint_reward_choice"
    render_all()

func apply_reward(index):
    if phase != "rewarding":
        return
    var id = reward_options[index] if index < reward_options.size() else "reward_heal"
    last_reward = id
    if id == "reward_soul":
        souls += 12
    elif id == "reward_guard":
        guard += 4
    else:
        hp = min(max_hp, hp + 25)
    phase = "cleared"
    reward_options = []
    last_log = "log_reward_applied"
    last_hint = "hint_continue_room"
    render_all()

func spawn_wave():
    var room_type = current_room_type()
    var count = 2
    if wave >= 2:
        count = 3
    if room_type == "elite":
        count = 3
    enemies = []
    for i in range(count):
        var base_hp = 30 + wave * 5 + room_index * 2
        if room_type == "elite" and i == 2:
            base_hp += 20
        enemies.append({"name": "Shade" if i < 2 else "Lancer", "health": base_hp, "alive": true, "xp": 12 + i * 4, "souls": 4 + i * 2})
    var positions = [Vector3(-3, 0.9, -2), Vector3(3, 0.9, -2), Vector3(0, 0.9, -4.2)]
    for i in range(enemy_bodies.size()):
        enemy_bodies[i].translation = positions[i]

func get_hit_count(skill):
    var attack_range = 1.8
    if skill == "right":
        attack_range = 2.8
    elif skill == "q":
        attack_range = 3.3
    elif skill == "e":
        attack_range = 4.8
    var count = 0
    for body in enemy_bodies:
        if body.visible and body.translation.distance_to(player.translation) <= attack_range:
            count += 1
    if skill == "e":
        return min(count, 2)
    if skill == "basic":
        return min(count, 1)
    return count

func resolve_damage(skill):
    var base = 12 + damage_bonus
    if skill == "right":
        base += 8
    elif skill == "q":
        base += 6
    elif skill == "e":
        base += 14
    else:
        base += combo * 3
    return base

func tick_cooldowns(used):
    for key in skills.keys():
        skills[key].remain = max(0, skills[key].remain - 1)
    if used != "" and used != "basic":
        skills[used].remain = max(1, skills[used].cd - cdr)

func enemies_remaining():
    var count = 0
    for enemy in enemies:
        if enemy.alive:
            count += 1
    return count

func build_room_path(seed_value):
    var paths = [
        ["combat", "reward", "elite", "combat"],
        ["combat", "combat", "reward", "elite"],
        ["combat", "reward", "combat", "elite"]
    ]
    return paths[seed_value % paths.size()]

func current_room_type():
    if room_path.size() == 0:
        return "entrance"
    var idx = clamp(room_index - 1, 0, room_path.size() - 1)
    return room_path[idx]

func next_room_type():
    if room_path.size() == 0:
        return "combat"
    var idx = clamp(room_index, 0, room_path.size() - 1)
    return room_path[idx]

func resolve_skill_hint(skill, hit):
    if hit:
        return "hint_hit_" + skill
    return "hint_miss_" + skill

func render_all():
    labels.header.text = tr_text("hud.header")
    labels.stats.text = "生命 %d/%d  灵魂 %d  经验 %d/%d  等级 %d  房间 %d" % [hp, max_hp, souls, xp, next_level_xp, level, room_index]
    labels.objective.text = tr_text("objective." + phase)
    labels.skills.text = tr_text("hud.controls")
    labels.cooldown.text = "冷却：右键:%s  Q:%s  E:%s" % [cooldown_text("right"), cooldown_text("q"), cooldown_text("e")]
    labels.range.text = "范围提示：前方目标 %d 个，翻滚窗口 %.1fs" % [get_hit_count("q"), roll_timer]
    labels.room.text = "房间 %d · %s · 波次 %d · Godot3 网页试玩由包内 Towerdemo2 原型转换生成" % [room_index, current_room_type(), wave]
    labels.door.text = tr_text("door.open") if phase == "cleared" else tr_text("door.locked")
    labels.route.text = "种子 %d · 当前 %s · 下一房 %s · 路径 %s" % [run_seed, current_room_type(), next_room_type(), "->".join(room_path)]
    labels.battle.text = "波次 %d  敌人 %d  当前敌人生命 %s" % [wave, enemies_remaining(), first_enemy_health()]
    labels.log.text = event_text(last_log)
    labels.hint.text = event_text(last_hint)
    reward_door.visible = phase == "cleared"
    buttons.start.visible = phase == "ready"
    buttons.retry.visible = phase == "dead"
    buttons.continue.visible = phase == "cleared"
    labels.reward_title.visible = phase == "rewarding"
    labels.level_title.visible = phase == "levelup"
    render_option_buttons("reward", reward_options, phase == "rewarding")
    render_option_buttons("level", level_options, phase == "levelup")
    for i in range(enemy_bodies.size()):
        enemy_bodies[i].visible = i < enemies.size() and enemies[i].alive and phase == "playing"

func cooldown_text(skill):
    var remain = skills[skill].remain
    return "就绪" if remain <= 0 else str(remain)

func first_enemy_health():
    for enemy in enemies:
        if enemy.alive:
            return str(enemy.health)
    return "-"

func render_option_buttons(prefix, options, visible):
    for i in range(3):
        var key = prefix + str(i + 1)
        buttons[key].visible = visible and i < options.size()
        if i < options.size():
            buttons[key].text = tr_text(prefix.replace("level", "levelup") + "." + options[i])

func _on_start_pressed():
    start_run()

func _on_retry_pressed():
    retry_run()

func _on_continue_pressed():
    continue_run()

func _on_reward1():
    apply_reward(0)

func _on_reward2():
    apply_reward(1)

func _on_reward3():
    apply_reward(2)

func _on_level1():
    apply_levelup(0)

func _on_level2():
    apply_levelup(1)

func _on_level3():
    apply_levelup(2)
""";
    }

    private static string RenderPackageAdapterMainScript(string adapterStyle)
    {
        return """
extends Spatial

var adapter_style = "__PHASEA_ADAPTER_STYLE__"
var package_data = {}
var manifest = {}
var scenes = []
var capabilities = []
var labels = {}
var buttons = {}
var ui_font = null
var player = null
var marker_bodies = []
var selected_marker = 0
var pulse = 0.0
var game_name = "Godot Package"
var project_name = ""
var game_type_source = ""
var main_scene = ""
var package_file = ""
var package_sha256 = ""
var converter_coverage = ""
var text_key_count = 0
var action_count = 0
var encounter_hp = 36
var encounter_max_hp = 36
var energy = 3
var tower_count = 0
var wave = 1
var last_action = "准备试玩"

func _ready():
    load_package_data()
    create_world()
    create_ui()
    render_all()

func load_package_data():
    var file = File.new()
    if not file.file_exists("res://preview-package-data.json"):
        return
    if file.open("res://preview-package-data.json", File.READ) != OK:
        return
    var raw = file.get_as_text()
    file.close()
    if raw.strip_edges() == "":
        return
    var parsed = JSON.parse(raw)
    if parsed.error != OK or typeof(parsed.result) != TYPE_DICTIONARY:
        return
    package_data = parsed.result
    game_name = str(package_data.get("game_name", "Godot Package"))
    project_name = str(package_data.get("project_name", ""))
    game_type_source = str(package_data.get("game_type_source", ""))
    package_file = str(package_data.get("package_file", ""))
    package_sha256 = str(package_data.get("package_sha256", ""))
    converter_coverage = str(package_data.get("converter_coverage", ""))
    manifest = package_data.get("web_preview_manifest", {})
    if typeof(manifest) == TYPE_DICTIONARY:
        main_scene = str(manifest.get("main_scene", ""))
        scenes = manifest.get("scenes", [])
        capabilities = manifest.get("detected_capabilities", [])
        text_key_count = int(manifest.get("text_key_count", 0))
    if typeof(scenes) != TYPE_ARRAY:
        scenes = []
    if typeof(capabilities) != TYPE_ARRAY:
        capabilities = []

func create_world():
    var light = DirectionalLight.new()
    light.light_energy = 1.15
    light.rotation_degrees = Vector3(-52, 18, -28)
    add_child(light)

    var camera = Camera.new()
    camera.name = "Camera"
    camera.current = true
    camera.fov = 58
    camera.translation = Vector3(0, 8.2, 10.5)
    camera.rotation_degrees = Vector3(-42, 0, 0)
    add_child(camera)

    var floor = StaticBody.new()
    floor.name = "PackagePreviewFloor"
    add_child(floor)
    floor.add_child(mesh_instance(cube_mesh(Vector3(15, 0.25, 12)), Color(0.16, 0.17, 0.20), Vector3(0, -0.125, 0)))
    floor.add_child(collision_box(Vector3(15, 0.35, 12), Vector3()))

    player = KinematicBody.new()
    player.name = "PreviewPlayer"
    player.translation = Vector3(0, 0.85, 4.2)
    add_child(player)
    player.add_child(capsule_actor(Color(0.36, 0.72, 0.95), 0.34, 1.45))
    player.add_child(collision_capsule(0.34, 1.45))

    var marker_count = max(1, min(8, scenes.size()))
    for i in range(marker_count):
        var marker = StaticBody.new()
        marker.name = "SceneMarker%d" % [i + 1]
        var angle = PI * 2.0 * float(i) / float(marker_count)
        marker.translation = Vector3(cos(angle) * 4.2, 0.55, sin(angle) * 3.2 - 0.7)
        add_child(marker)
        marker.add_child(mesh_instance(cube_mesh(Vector3(0.85, 0.85, 0.85)), marker_color(i), Vector3()))
        marker.add_child(collision_box(Vector3(0.9, 0.9, 0.9), Vector3()))
        marker_bodies.append(marker)

func create_ui():
    ui_font = load_ui_font()
    var layer = CanvasLayer.new()
    add_child(layer)
    var root = Control.new()
    root.anchor_right = 1
    root.anchor_bottom = 1
    layer.add_child(root)

    buttons.inspect = add_button(root, "InspectButton", "检查场景", Rect2(44, 44, 150, 42), "_on_inspect_pressed")
    buttons.next = add_button(root, "NextButton", "下一个场景", Rect2(210, 44, 170, 42), "_on_next_scene")
    labels.header = add_label(root, Rect2(44, 110, 900, 30), "")
    labels.summary = add_label(root, Rect2(44, 150, 1040, 28), "")
    labels.main_scene = add_label(root, Rect2(44, 184, 1160, 28), "")
    labels.scene = add_label(root, Rect2(44, 230, 1180, 28), "")
    labels.capabilities = add_label(root, Rect2(44, 264, 1180, 28), "")
    labels.package = add_label(root, Rect2(44, 298, 1180, 28), "")
    labels.coverage = add_label(root, Rect2(44, 344, 1200, 54), "")
    labels.controls = add_label(root, Rect2(44, 820, 1100, 28), "WASD移动  鼠标左键/空格检查下一个包内场景  Enter回到第一个场景")

func _physics_process(delta):
    pulse += delta
    apply_player_motion(delta)
    animate_markers()

func _input(event):
    if event is InputEventMouseButton and event.pressed and event.button_index == BUTTON_LEFT:
        primary_action()
    elif event is InputEventKey and event.pressed and not event.echo:
        if event.scancode == KEY_SPACE:
            primary_action()
        elif event.scancode == KEY_ENTER:
            selected_marker = 0
            render_all()
        elif event.scancode == KEY_1:
            selected_marker = 0
            render_all()
        elif event.scancode == KEY_2:
            selected_marker = min(1, max(0, marker_bodies.size() - 1))
            render_all()
        elif event.scancode == KEY_3:
            selected_marker = min(2, max(0, marker_bodies.size() - 1))
            render_all()

func apply_player_motion(delta):
    if player == null:
        return
    var dir = Vector3()
    if Input.is_key_pressed(KEY_W):
        dir.z -= 1
    if Input.is_key_pressed(KEY_S):
        dir.z += 1
    if Input.is_key_pressed(KEY_A):
        dir.x -= 1
    if Input.is_key_pressed(KEY_D):
        dir.x += 1
    if dir.length() > 0:
        dir = dir.normalized()
    player.move_and_slide(dir * 5.2, Vector3.UP)
    player.translation.x = clamp(player.translation.x, -6.8, 6.8)
    player.translation.z = clamp(player.translation.z, -5.3, 5.3)

func animate_markers():
    for i in range(marker_bodies.size()):
        var marker = marker_bodies[i]
        var base_y = 0.55
        marker.translation.y = base_y + (0.22 if i == selected_marker else 0.06) * sin(pulse * 3.0 + i)
        marker.scale = Vector3(1.25, 1.25, 1.25) if i == selected_marker else Vector3(1, 1, 1)

func advance_marker():
    if marker_bodies.size() == 0:
        return
    selected_marker = (selected_marker + 1) % marker_bodies.size()
    render_all()

func primary_action():
    action_count += 1
    if adapter_style == "rpg":
        encounter_hp = max(0, encounter_hp - 7)
        last_action = "普通攻击命中，遭遇生命 -7"
        if encounter_hp <= 0:
            wave += 1
            encounter_max_hp += 8
            encounter_hp = encounter_max_hp
            last_action = "遭遇结束，进入下一段探索"
            advance_marker()
            return
    elif adapter_style == "survivorslike":
        encounter_hp = max(0, encounter_hp - 5)
        last_action = "自动武器扫射，清理近身敌群"
        if action_count % 4 == 0:
            wave += 1
            encounter_hp = encounter_max_hp + wave * 5
            last_action = "新一波敌群进入竞技场"
    elif adapter_style == "survival":
        energy = min(6, energy + 1)
        encounter_hp = max(0, encounter_hp - 3)
        last_action = "采集资源，短暂缓解生存压力"
        if action_count % 3 == 0:
            tower_count += 1
            wave += 1
            encounter_hp = encounter_max_hp + wave * 4
            last_action = "搭建营地设施，进入下一天"
    elif adapter_style == "card":
        if energy <= 0:
            energy = 3
            last_action = "回合结束，能量刷新"
        else:
            energy -= 1
            encounter_hp = max(0, encounter_hp - 6)
            last_action = "打出手牌，消耗 1 能量"
            if encounter_hp <= 0:
                wave += 1
                energy = 3
                encounter_hp = encounter_max_hp + wave * 4
                advance_marker()
                return
    elif adapter_style == "tower-defense":
        tower_count += 1
        encounter_hp = max(0, encounter_hp - 4 - tower_count)
        last_action = "放置防御塔，当前火力提升"
        if action_count % 3 == 0:
            wave += 1
            encounter_hp = encounter_max_hp + wave * 6
            last_action = "下一波敌人开始推进"
    else:
        last_action = "检查包内场景标记"
        advance_marker()
        return
    render_all()

func render_all():
    labels.header.text = "%s 浏览器试玩预览" % [game_name]
    labels.summary.text = "项目 %s  类型 %s  文本键 %d  场景 %d" % [empty_text(project_name), empty_text(game_type_source), text_key_count, scenes.size()]
    labels.main_scene.text = "主场景：%s" % [empty_text(main_scene)]
    labels.scene.text = "当前包内场景：%s" % [selected_scene_text()]
    labels.capabilities.text = "转换能力：%s" % [join_first(capabilities, 8)]
    labels.package.text = "文件包：%s  SHA256：%s" % [empty_text(package_file), short_sha(package_sha256)]
    labels.coverage.text = "%s\n%s" % [converter_coverage, adapter_status_text()]

func adapter_status_text():
    if adapter_style == "rpg":
        return "RPG 试玩：遭遇生命 %d/%d  段落 %d  最近动作：%s" % [encounter_hp, encounter_max_hp, wave, last_action]
    if adapter_style == "survivorslike":
        return "Survivorslike 试玩：波次 %d  敌群压力 %d  最近动作：%s" % [wave, encounter_hp, last_action]
    if adapter_style == "survival":
        return "生存试玩：资源 %d/6  营地设施 %d  第 %d 天  生存压力 %d  最近动作：%s" % [energy, tower_count, wave, encounter_hp, last_action]
    if adapter_style == "card":
        return "卡牌试玩：能量 %d/3  遭遇生命 %d/%d  最近动作：%s" % [energy, encounter_hp, encounter_max_hp, last_action]
    if adapter_style == "tower-defense":
        return "塔防试玩：防御塔 %d  波次 %d  敌军生命 %d  最近动作：%s" % [tower_count, wave, encounter_hp, last_action]
    return "通用试玩：左键/空格检查包内场景，最近动作：%s" % [last_action]

func selected_scene_text():
    if scenes.size() == 0:
        return "未在文件包中发现 .tscn 场景"
    var index = int(clamp(selected_marker, 0, scenes.size() - 1))
    return str(scenes[index])

func join_first(values, limit):
    if values.size() == 0:
        return "godot_package_zip"
    var parts = []
    var count = min(limit, values.size())
    for i in range(count):
        parts.append(str(values[i]))
    if values.size() > limit:
        parts.append("+%d" % [values.size() - limit])
    return PoolStringArray(parts).join(", ")

func short_sha(value):
    if value.length() <= 16:
        return empty_text(value)
    return value.substr(0, 16)

func empty_text(value):
    return "未提供" if str(value).strip_edges() == "" else str(value)

func _on_inspect_pressed():
    advance_marker()

func _on_next_scene():
    advance_marker()

func add_label(parent, rect, text):
    var label = Label.new()
    label.rect_position = rect.position
    label.rect_size = rect.size
    label.text = text
    label.autowrap = true
    if ui_font != null:
        label.add_font_override("font", ui_font)
    parent.add_child(label)
    return label

func add_button(parent, name, text, rect, method):
    var button = Button.new()
    button.name = name
    button.rect_position = rect.position
    button.rect_size = rect.size
    button.text = text
    if ui_font != null:
        button.add_font_override("font", ui_font)
    button.connect("pressed", self, method)
    parent.add_child(button)
    return button

func load_ui_font():
    var font = load("res://Fonts/ui_font.tres")
    if font is DynamicFont:
        return font
    return null

func cube_mesh(size):
    var mesh = CubeMesh.new()
    mesh.size = size
    return mesh

func marker_color(index):
    var colors = [
        Color(0.36, 0.72, 0.95),
        Color(0.92, 0.68, 0.28),
        Color(0.58, 0.78, 0.42),
        Color(0.82, 0.40, 0.48)
    ]
    return colors[index % colors.size()]

func material(color):
    var mat = SpatialMaterial.new()
    mat.albedo_color = color
    return mat

func mesh_instance(mesh, color, local_pos):
    var node = MeshInstance.new()
    node.mesh = mesh
    node.material_override = material(color)
    node.translation = local_pos
    return node

func capsule_actor(color, radius, height):
    var node = MeshInstance.new()
    var mesh = CapsuleMesh.new()
    mesh.radius = radius
    mesh.mid_height = max(0.1, height - radius * 2.0)
    node.mesh = mesh
    node.material_override = material(color)
    return node

func collision_box(size, local_pos):
    var collision = CollisionShape.new()
    var shape = BoxShape.new()
    shape.extents = size * 0.5
    collision.shape = shape
    collision.translation = local_pos
    return collision

func collision_capsule(radius, height):
    var collision = CollisionShape.new()
    var shape = CapsuleShape.new()
    shape.radius = radius
    shape.height = max(0.1, height - radius * 2.0)
    collision.shape = shape
    return collision
""".Replace("__PHASEA_ADAPTER_STYLE__", EscapeGodotString(adapterStyle), StringComparison.Ordinal);
    }

    private static PackageInfo ExtractPackageInfo(ProjectSnapshot project, string fileName, string packagePath)
    {
        var scenes = new List<string>();
        var texts = new Dictionary<string, string>(StringComparer.Ordinal);
        string? mainScene = null;
        var gameName = project.GameName;
        var projectName = project.Name;
        var gameTypeSource = project.GameTypeSource;
        var gameTypeId = "";
        var gameTypeGuide = "";
        var isTowerdemo2 = false;
        var towerdemo2SourceSceneSha256 = "";
        var towerdemo2TextCatalogSha256 = "";
        var sourceFingerprints = new List<PackageWebPreviewSourceFingerprint>();

        using var archive = ZipFile.OpenRead(packagePath);
        var packageManifestEntry = archive.GetEntry("PACKAGE-MANIFEST.json");
        if (packageManifestEntry is not null)
        {
            try
            {
                using var document = JsonDocument.Parse(packageManifestEntry.Open());
                if (document.RootElement.TryGetProperty("game_name", out var gameNameElement) &&
                    !string.IsNullOrWhiteSpace(gameNameElement.GetString()))
                {
                    gameName = gameNameElement.GetString()!;
                }

                if (document.RootElement.TryGetProperty("project_name", out var projectNameElement) &&
                    !string.IsNullOrWhiteSpace(projectNameElement.GetString()))
                {
                    projectName = projectNameElement.GetString()!;
                }

                if (document.RootElement.TryGetProperty("game_type_source", out var gameTypeSourceElement) &&
                    !string.IsNullOrWhiteSpace(gameTypeSourceElement.GetString()))
                {
                    gameTypeSource = gameTypeSourceElement.GetString()!;
                }

                gameTypeId = FirstNonEmpty(
                    ReadJsonString(document.RootElement, "game_type_id"),
                    ReadJsonString(document.RootElement, "game_type"),
                    gameTypeId);
                gameTypeGuide = FirstNonEmpty(ReadJsonString(document.RootElement, "game_type_guide"), gameTypeGuide);
            }
            catch (JsonException)
            {
                gameName = project.GameName;
                projectName = project.Name;
                gameTypeSource = project.GameTypeSource;
            }
        }

        var projectConfig = archive.GetEntry("project.godot");
        if (projectConfig is not null)
        {
            using var reader = new StreamReader(projectConfig.Open(), Encoding.UTF8);
            while (reader.ReadLine() is { } line)
            {
                if (line.StartsWith("run/main_scene=", StringComparison.Ordinal))
                {
                    mainScene = line.Split('=', 2)[1].Trim().Trim('"');
                    break;
                }
            }
        }

        foreach (var entry in archive.Entries.OrderBy(entry => entry.FullName, StringComparer.OrdinalIgnoreCase))
        {
            var normalized = entry.FullName.Replace('\\', '/');
            if (normalized.EndsWith(".tscn", StringComparison.OrdinalIgnoreCase))
            {
                scenes.Add(normalized);
            }

            if (string.Equals(normalized, Towerdemo2Converter.SourceScenePath, StringComparison.OrdinalIgnoreCase))
            {
                isTowerdemo2 = true;
                towerdemo2SourceSceneSha256 = ComputeZipEntrySha256(entry);
                sourceFingerprints.Add(new PackageWebPreviewSourceFingerprint(
                    normalized,
                    "towerdemo2_source_scene",
                    towerdemo2SourceSceneSha256));
            }
        }

        var textCatalog = archive.GetEntry(Towerdemo2Converter.TextCatalogPath);
        if (textCatalog is not null)
        {
            if (textCatalog.Length > MaxPreviewTextCatalogBytes)
            {
                throw new InvalidOperationException("Package text catalog exceeds the web preview scan budget.");
            }

            towerdemo2TextCatalogSha256 = ComputeZipEntrySha256(textCatalog);
            sourceFingerprints.Add(new PackageWebPreviewSourceFingerprint(
                Towerdemo2Converter.TextCatalogPath,
                "towerdemo2_text_catalog",
                towerdemo2TextCatalogSha256));
            using var reader = new StreamReader(textCatalog.Open(), Encoding.UTF8);
            foreach (Match match in Regex.Matches(
                         reader.ReadToEnd(),
                         "\\[\"(?<key>[^\"]+)\"\\]\\s*=\\s*\"(?<value>(?:\\\\.|[^\"])*)\""))
            {
                texts[match.Groups["key"].Value] = Regex.Unescape(match.Groups["value"].Value);
            }
        }

        var packageSizeBytes = new FileInfo(packagePath).Length;
        var packageSha256 = ComputeFileSha256(packagePath);
        gameTypeId = FirstNonEmpty(
            ProjectWebPreviewGameTypeCatalog.ResolveGameTypeId(gameTypeId, gameTypeGuide, gameTypeSource, gameName, projectName),
            isTowerdemo2 ? "tower-defense" : "",
            ProjectWebPreviewGameTypeCatalog.NormalizeGameTypeToken(gameTypeId));
        var catalogGameTypeGuide = ProjectWebPreviewGameTypeCatalog.ResolveGameTypeGuide(gameTypeId);
        gameTypeGuide = FirstNonEmpty(catalogGameTypeGuide, gameTypeGuide);
        var manifest = BuildWebPreviewManifest(
            project,
            fileName,
            projectName,
            gameName,
            gameTypeSource,
            gameTypeId,
            gameTypeGuide,
            packageSha256,
            packageSizeBytes,
            mainScene,
            scenes.Take(80).ToArray(),
            sourceFingerprints.OrderBy(item => item.Path, StringComparer.OrdinalIgnoreCase).ToArray(),
            texts.Count,
            isTowerdemo2);

        return new PackageInfo(
            fileName,
            projectName,
            gameName,
            gameTypeSource,
            gameTypeId,
            gameTypeGuide,
            mainScene,
            scenes.Take(80).ToArray(),
            texts,
            isTowerdemo2,
            towerdemo2SourceSceneSha256,
            towerdemo2TextCatalogSha256,
            packageSizeBytes,
            packageSha256,
            manifest);
    }

    private static (string Code, string Message)? ValidatePackageScanBudget(string packagePath)
    {
        var info = new FileInfo(packagePath);
        if (info.Length > MaxPreviewPackageSizeBytes)
        {
            return (
                "package_scan_budget_exceeded",
                $"Package size exceeds the web preview scan budget of {MaxPreviewPackageSizeBytes} bytes.");
        }

        try
        {
            using var archive = ZipFile.OpenRead(packagePath);
            if (archive.Entries.Count > MaxPreviewPackageEntryCount)
            {
                return (
                    "package_scan_budget_exceeded",
                    $"Package entry count exceeds the web preview scan budget of {MaxPreviewPackageEntryCount} entries.");
            }

            var textCatalog = archive.GetEntry(Towerdemo2Converter.TextCatalogPath);
            if (textCatalog is not null && textCatalog.Length > MaxPreviewTextCatalogBytes)
            {
                return (
                    "package_scan_budget_exceeded",
                    $"Package text catalog exceeds the web preview scan budget of {MaxPreviewTextCatalogBytes} bytes.");
            }
        }
        catch (InvalidDataException ex)
        {
            return ("package_invalid_zip", ex.Message);
        }

        return null;
    }

    private static PackageWebPreviewManifest BuildWebPreviewManifest(
        ProjectSnapshot project,
        string fileName,
        string projectName,
        string gameName,
        string gameTypeSource,
        string gameTypeId,
        string gameTypeGuide,
        string packageSha256,
        long packageSizeBytes,
        string? mainScene,
        IReadOnlyList<string> scenes,
        IReadOnlyList<PackageWebPreviewSourceFingerprint> sourceFingerprints,
        int textKeyCount,
        bool isTowerdemo2)
    {
        var detectedTemplates = new List<string>();
        var detectedCapabilities = new List<string>
        {
            "godot_package_zip"
        };

        if (!string.IsNullOrWhiteSpace(mainScene))
        {
            detectedCapabilities.Add("godot_main_scene");
        }

        if (scenes.Count > 0)
        {
            detectedCapabilities.Add("godot_scene_inventory");
        }

        if (textKeyCount > 0)
        {
            detectedCapabilities.Add("prototype_text_catalog");
        }

        if (isTowerdemo2)
        {
            detectedTemplates.Add("towerdemo2");
            detectedCapabilities.Add("towerdemo2_room_wave_loop");
            detectedCapabilities.Add("towerdemo2_template_subset");
        }

        var contract = BuildWebPreviewContract(isTowerdemo2 ? Towerdemo2Converter : GenericGodotPackageConverter, mainScene, scenes, textKeyCount);

        return new PackageWebPreviewManifest(
            PreviewManifestSchemaVersion,
            "generated_by_web_preview_converter",
            project.ProjectId,
            projectName,
            gameName,
            gameTypeSource,
            gameTypeId,
            gameTypeGuide,
            fileName,
            packageSha256,
            packageSizeBytes,
            mainScene ?? "",
            scenes,
            sourceFingerprints,
            textKeyCount,
            detectedTemplates.Order(StringComparer.Ordinal).ToArray(),
            detectedCapabilities.Distinct(StringComparer.Ordinal).Order(StringComparer.Ordinal).ToArray(),
            contract);
    }

    private static PackageWebPreviewContract BuildWebPreviewContract(
        ProjectWebPreviewConverterDescriptor converter,
        string? mainScene,
        IReadOnlyList<string> scenes,
        int textKeyCount)
    {
        var dataSources = new List<string>
        {
            "PACKAGE-MANIFEST.json",
            "project.godot"
        };
        if (!string.IsNullOrWhiteSpace(mainScene))
        {
            dataSources.Add("project.godot:run/main_scene");
        }

        if (scenes.Count > 0)
        {
            dataSources.Add("zip:*.tscn");
        }

        if (textKeyCount > 0)
        {
            dataSources.Add(Towerdemo2Converter.TextCatalogPath);
        }

        if (string.Equals(converter.Id, Towerdemo2Converter.Id, StringComparison.Ordinal))
        {
            return new PackageWebPreviewContract(
                "capability_routed",
                "towerdemo2_high_fidelity_subset",
                "template_high_fidelity",
                dataSources.Distinct(StringComparer.Ordinal).ToArray(),
                [
                    new PackageWebPreviewInputAction("move", ["W", "A", "S", "D"], "Move the converted player avatar inside the preview arena."),
                    new PackageWebPreviewInputAction("basic_attack", ["MouseLeft"], "Run the converted basic attack loop."),
                    new PackageWebPreviewInputAction("skill_or_roll", ["MouseRight", "Q", "E", "Space"], "Run converted skill and dodge interactions."),
                    new PackageWebPreviewInputAction("choice", ["1", "2", "3"], "Select converted reward and level-up choices.")
                ]);
        }

        if (string.Equals(converter.AdapterStyle, "rpg", StringComparison.Ordinal))
        {
            return new PackageWebPreviewContract(
                "package_manifest_and_game_type_guide",
                "rpg_encounter_exploration_reward_preview",
                "game_type_adapter_preview",
                dataSources.Concat(["docs/game-type-guides/rpg.md"]).Distinct(StringComparer.Ordinal).ToArray(),
                [
                    new PackageWebPreviewInputAction("move", ["W", "A", "S", "D"], "Move through the package-derived exploration floor."),
                    new PackageWebPreviewInputAction("basic_attack", ["MouseLeft", "Space"], "Advance a package-derived RPG encounter approximation."),
                    new PackageWebPreviewInputAction("scene_focus", ["1", "2", "3", "Enter"], "Select a package scene marker.")
                ]);
        }

        if (string.Equals(converter.AdapterStyle, "survivorslike", StringComparison.Ordinal))
        {
            return new PackageWebPreviewContract(
                "package_manifest_and_game_type_guide",
                "survivorslike_arena_pressure_preview",
                "game_type_adapter_preview",
                dataSources.Concat(["docs/game-type-guides/survivorslike.md", "docs/game-type-guides/action-platformer.md", "docs/game-type-guides/survival.md", "docs/game-type-guides/roguelike.md"]).Distinct(StringComparer.Ordinal).ToArray(),
                [
                    new PackageWebPreviewInputAction("move", ["W", "A", "S", "D"], "Move through the package-derived arena."),
                    new PackageWebPreviewInputAction("attack", ["MouseLeft", "Space"], "Advance an arena enemy pressure approximation."),
                    new PackageWebPreviewInputAction("scene_focus", ["1", "2", "3", "Enter"], "Select a package scene marker.")
                ]);
        }

        if (string.Equals(converter.AdapterStyle, "survival", StringComparison.Ordinal))
        {
            return new PackageWebPreviewContract(
                "package_manifest_and_game_type_guide",
                "survival_gather_needs_shelter_preview",
                "game_type_adapter_preview",
                dataSources.Concat(["docs/game-type-guides/survival.md"]).Distinct(StringComparer.Ordinal).ToArray(),
                [
                    new PackageWebPreviewInputAction("move", ["W", "A", "S", "D"], "Move through the package-derived survival space."),
                    new PackageWebPreviewInputAction("gather", ["MouseLeft", "Space"], "Gather resources, reduce needs pressure, and advance shelter state."),
                    new PackageWebPreviewInputAction("scene_focus", ["1", "2", "3", "Enter"], "Select a package scene marker.")
                ]);
        }

        if (string.Equals(converter.AdapterStyle, "card", StringComparison.Ordinal))
        {
            return new PackageWebPreviewContract(
                "package_manifest_and_game_type_guide",
                "card_hand_energy_encounter_preview",
                "game_type_adapter_preview",
                dataSources.Concat(["docs/game-type-guides/card-game.md"]).Distinct(StringComparer.Ordinal).ToArray(),
                [
                    new PackageWebPreviewInputAction("move", ["W", "A", "S", "D"], "Move between package scene markers."),
                    new PackageWebPreviewInputAction("play_card", ["MouseLeft", "Space"], "Play a package-derived card encounter approximation."),
                    new PackageWebPreviewInputAction("scene_focus", ["1", "2", "3", "Enter"], "Select a package scene marker.")
                ]);
        }

        if (string.Equals(converter.AdapterStyle, "tower-defense", StringComparison.Ordinal))
        {
            return new PackageWebPreviewContract(
                "package_manifest_and_game_type_guide",
                "tower_defense_placement_wave_preview",
                "game_type_adapter_preview",
                dataSources.Concat(["docs/game-type-guides/tower-defense.md"]).Distinct(StringComparer.Ordinal).ToArray(),
                [
                    new PackageWebPreviewInputAction("move", ["W", "A", "S", "D"], "Move across the package-derived defense board."),
                    new PackageWebPreviewInputAction("place_tower", ["MouseLeft", "Space"], "Place a tower and advance wave pressure."),
                    new PackageWebPreviewInputAction("scene_focus", ["1", "2", "3", "Enter"], "Select a package scene marker.")
                ]);
        }

        return new PackageWebPreviewContract(
            "package_manifest_scene_inventory",
            "generic_package_exploration_shell",
            "generic_package_preview",
            dataSources.Distinct(StringComparer.Ordinal).ToArray(),
            [
                new PackageWebPreviewInputAction("move", ["W", "A", "S", "D"], "Move through the package-derived preview floor."),
                new PackageWebPreviewInputAction("inspect_scene", ["MouseLeft", "Space"], "Inspect the next package scene marker."),
                new PackageWebPreviewInputAction("jump_to_scene", ["1", "2", "3", "Enter"], "Select a package scene marker.")
            ]);
    }

    private static IReadOnlyDictionary<string, RunSnapshot> BuildLatestWebPreviewRunsByPackage(IReadOnlyList<RunSnapshot> runs)
    {
        var latestRunsByPackage = new Dictionary<string, RunSnapshot>(StringComparer.Ordinal);
        foreach (var run in runs
                     .Where(run => string.Equals(run.RunType, RunType, StringComparison.Ordinal))
                     .OrderByDescending(run => run.CreatedUtc, StringComparer.Ordinal)
                     .ThenByDescending(run => run.RunId, StringComparer.Ordinal))
        {
            var packageFile = TryReadRunPackageFile(run);
            if (packageFile is not null && !latestRunsByPackage.ContainsKey(packageFile))
            {
                latestRunsByPackage[packageFile] = run;
            }
        }

        return latestRunsByPackage;
    }

    private HeavyRunnerQueueItemReadback? FindWebPreviewQueueItem(string accountId, string runId)
    {
        var readback = _webPreviewQueue.GetReadback(accountId, includeAll: true);
        if (readback.Current is not null &&
            string.Equals(readback.Current.RunId, runId, StringComparison.Ordinal))
        {
            return readback.Current;
        }

        return readback.Items.FirstOrDefault(item => string.Equals(item.RunId, runId, StringComparison.Ordinal));
    }

    private static string? TryReadRunPackageFile(RunSnapshot run)
    {
        if (IsSafeFileName(run.ProgressSubstep))
        {
            return run.ProgressSubstep;
        }

        if (string.IsNullOrWhiteSpace(run.EvidenceJson))
        {
            return null;
        }

        try
        {
            using var document = JsonDocument.Parse(run.EvidenceJson);
            if (document.RootElement.TryGetProperty("package_file", out var packageElement) &&
                IsSafeFileName(packageElement.GetString() ?? ""))
            {
                return packageElement.GetString();
            }
        }
        catch (JsonException)
        {
        }
        catch (IOException)
        {
        }
        catch (UnauthorizedAccessException)
        {
        }

        return null;
    }

    private static string? ReadFailureCode(RunSnapshot run)
    {
        if (!string.IsNullOrWhiteSpace(run.EvidenceJson))
        {
            try
            {
                using var document = JsonDocument.Parse(run.EvidenceJson);
                if (document.RootElement.TryGetProperty("failure_code", out var failureElement) &&
                    !string.IsNullOrWhiteSpace(failureElement.GetString()))
                {
                    return failureElement.GetString();
                }
            }
            catch (JsonException)
            {
                // Fall back to stderr/progress below.
            }
        }

        if (!string.IsNullOrWhiteSpace(run.StderrText))
        {
            return "web_preview_failed";
        }

        return string.IsNullOrWhiteSpace(run.ProgressLabel) ? null : run.ProgressLabel;
    }

    private static bool IsRunNewerThan(RunSnapshot run, string createdUtc)
    {
        if (!DateTimeOffset.TryParse(createdUtc, out var previewCreatedUtc))
        {
            return false;
        }

        var runUpdatedUtc = run.FinishedUtc ?? run.ProgressUpdatedUtc ?? run.StartedUtc ?? run.CreatedUtc;
        return DateTimeOffset.TryParse(runUpdatedUtc, out var parsedRunUpdatedUtc) &&
               parsedRunUpdatedUtc > previewCreatedUtc;
    }

    internal static void PrunePreviewScratchDirectories(string projectRoot, DateTimeOffset? utcNow = null)
    {
        var previewRoot = ResolveUnderProject(projectRoot, PreviewRootDirectory);
        if (!Directory.Exists(previewRoot))
        {
            return;
        }

        var cutoffUtc = (utcNow ?? DateTimeOffset.UtcNow) - PreviewScratchRetention;
        foreach (var directory in Directory.EnumerateDirectories(previewRoot))
        {
            var name = Path.GetFileName(directory);
            if (!IsPreviewScratchDirectoryName(name))
            {
                continue;
            }

            DateTime lastWriteUtc;
            try
            {
                lastWriteUtc = Directory.GetLastWriteTimeUtc(directory);
            }
            catch (IOException)
            {
                continue;
            }
            catch (UnauthorizedAccessException)
            {
                continue;
            }

            if (lastWriteUtc > cutoffUtc.UtcDateTime)
            {
                continue;
            }

            try
            {
                Directory.Delete(directory, recursive: true);
            }
            catch (IOException)
            {
                // Best-effort cleanup; a live export may still hold the directory.
            }
            catch (UnauthorizedAccessException)
            {
                // Best-effort cleanup; permission issues should not block preview generation.
            }
        }
    }

    private static bool IsPreviewScratchDirectoryName(string name)
    {
        return name.StartsWith(".", StringComparison.Ordinal) ||
               name.Contains(".replace-", StringComparison.Ordinal);
    }

    private async Task CompletePreviewFailureAsync(
        string runId,
        string fileName,
        string failureCode,
        string stderr,
        CancellationToken cancellationToken,
        string stdout = "",
        string converterMode = "")
    {
        var evidence = JsonSerializer.Serialize(new
        {
            run_type = RunType,
            package_file = fileName,
            failure_code = failureCode,
            mode = converterMode
        }, JsonOptions);
        await _metadataStore.CompleteRunAsync(runId, "failed", 1, stdout, stderr, evidence, cancellationToken);
    }

    private bool TryReadReadyPreviewData(
        string dataPath,
        string expectedProjectId,
        string expectedPreviewId,
        out PreviewReadyData readyData,
        bool allowLegacyPreview = true)
    {
        readyData = PreviewReadyData.Empty;
        if (!File.Exists(dataPath))
        {
            return false;
        }

        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(dataPath, Encoding.UTF8));
            var root = document.RootElement;
            var schemaVersion = ReadJsonString(root, "schema_version");
            var projectId = ReadJsonString(root, "project_id");
            var previewId = ReadJsonString(root, "preview_id");
            var packageFile = ReadJsonString(root, "package_file");
            var packageSha256 = ReadJsonString(root, "package_sha256");
            var assetVersion = ReadJsonString(root, "asset_version");
            var converterId = ReadJsonString(root, "converter_id");
            var converterCompatibilityId = ReadJsonString(root, "converter_compatibility_id");
            var sourceSceneSha256 = ReadJsonString(root, "source_scene_sha256");
            var textCatalogSha256 = ReadJsonString(root, "text_catalog_sha256");
            var manifestSha256 = ReadJsonString(root, "manifest_sha256");
            var mode = ReadJsonString(root, "mode");
            var gameTypeId = ReadJsonString(root, "game_type_id");
            var gameTypeGuide = ReadJsonString(root, "game_type_guide");
            var createdUtc = ReadJsonString(root, "created_utc");
            var signature = ReadJsonString(root, "signature");
            var converter = ConverterRegistry.FirstOrDefault(item => string.Equals(mode, item.Mode, StringComparison.Ordinal));
            var isLegacyPreview = string.Equals(schemaVersion, LegacyPreviewSchemaVersion, StringComparison.Ordinal);

            if ((!string.Equals(schemaVersion, PreviewSchemaVersion, StringComparison.Ordinal) && !isLegacyPreview) ||
                (isLegacyPreview && !allowLegacyPreview) ||
                !string.Equals(projectId, expectedProjectId, StringComparison.Ordinal) ||
                !string.Equals(previewId, expectedPreviewId, StringComparison.Ordinal) ||
                !IsSafeFileName(packageFile) ||
                string.IsNullOrWhiteSpace(packageSha256) ||
                string.IsNullOrWhiteSpace(assetVersion) ||
                string.IsNullOrWhiteSpace(createdUtc) ||
                string.IsNullOrWhiteSpace(signature) ||
                converter is null ||
                !string.Equals(converterId, converter.Id, StringComparison.Ordinal) ||
                !string.Equals(converterCompatibilityId, converter.CompatibilityId, StringComparison.Ordinal) ||
                !string.Equals(sourceSceneSha256, converter.SourceSceneSha256, StringComparison.OrdinalIgnoreCase) ||
                !string.Equals(textCatalogSha256, converter.TextCatalogSha256, StringComparison.OrdinalIgnoreCase))
            {
                return false;
            }

            if (!isLegacyPreview)
            {
                if (string.IsNullOrWhiteSpace(manifestSha256))
                {
                    return false;
                }

                var manifestPath = Path.Combine(Path.GetDirectoryName(dataPath) ?? "", PreviewManifestFileName);
                if (!File.Exists(manifestPath) ||
                    !string.Equals(ComputeStringSha256(File.ReadAllText(manifestPath, Encoding.UTF8)), manifestSha256, StringComparison.OrdinalIgnoreCase))
                {
                    return false;
                }
            }

            var expectedSignature = isLegacyPreview
                ? ComputeLegacyPreviewSignature(
                    projectId,
                    previewId,
                    packageSha256,
                    assetVersion,
                    createdUtc,
                    mode,
                    converterId,
                    converterCompatibilityId,
                    sourceSceneSha256,
                    textCatalogSha256)
                : ComputePreviewSignature(
                projectId,
                previewId,
                packageSha256,
                assetVersion,
                createdUtc,
                mode,
                converterId,
                converterCompatibilityId,
                sourceSceneSha256,
                textCatalogSha256,
                manifestSha256);
            if (!CryptographicOperations.FixedTimeEquals(
                    Encoding.ASCII.GetBytes(signature),
                    Encoding.ASCII.GetBytes(expectedSignature)))
            {
                return false;
            }

            var fidelityTier = "";
            var playableSurface = "";
            if (root.TryGetProperty("web_preview_manifest", out var previewManifest) &&
                previewManifest.TryGetProperty("conversion_contract", out var conversionContract))
            {
                fidelityTier = ReadJsonString(conversionContract, "fidelity_tier");
                playableSurface = ReadJsonString(conversionContract, "playable_surface");
            }

            readyData = new PreviewReadyData(mode, createdUtc, packageFile, packageSha256, fidelityTier, playableSurface, gameTypeId, gameTypeGuide);
            return true;
        }
        catch (JsonException)
        {
            return false;
        }
    }

    private static bool HasExpectedWebExport(string webRoot)
    {
        return File.Exists(Path.Combine(webRoot, "index.html")) &&
               File.Exists(Path.Combine(webRoot, "index.js")) &&
               File.Exists(Path.Combine(webRoot, "index.wasm")) &&
               File.Exists(Path.Combine(webRoot, "index.pck"));
    }

    internal static bool PatchGodotWebShell(string indexPath, string scriptPath, string assetVersion)
    {
        var loadingEstimatePatched = TryPatchGodotLoadingEstimate(indexPath);
        PatchGodotAssetVersioning(indexPath, scriptPath, assetVersion);
        return loadingEstimatePatched;
    }

    private static void PatchGodotAssetVersioning(string indexPath, string scriptPath, string assetVersion)
    {
        if (!File.Exists(indexPath) || !File.Exists(scriptPath))
        {
            throw new InvalidOperationException("Godot web export shell is missing index.html or index.js.");
        }

        var html = File.ReadAllText(indexPath, Encoding.UTF8);
        if (!html.Contains($"index.js?v={assetVersion}", StringComparison.Ordinal))
        {
            html = html.Replace(
                "<script type='text/javascript' src='index.js'></script>",
                $"<script type='text/javascript' src='index.js?v={assetVersion}'></script>",
                StringComparison.Ordinal);
            html = Regex.Replace(
                html,
                "<script\\s+type=(['\"])text/javascript\\1\\s+src=(['\"])index\\.js\\2\\s*></script>",
                $"<script type='text/javascript' src='index.js?v={assetVersion}'></script>",
                RegexOptions.IgnoreCase);
        }

        if (!html.Contains("window.__PHASEA_WEB_PREVIEW_ASSET_VERSION", StringComparison.Ordinal))
        {
            html = html.Replace(
                "\n\t\tvar engine = new Engine(GODOT_CONFIG);",
                $"\n\t\twindow.__PHASEA_WEB_PREVIEW_ASSET_VERSION = '{assetVersion}';\n\t\tvar engine = new Engine(GODOT_CONFIG);",
                StringComparison.Ordinal);
            if (!html.Contains("window.__PHASEA_WEB_PREVIEW_ASSET_VERSION", StringComparison.Ordinal))
            {
                html = Regex.Replace(
                    html,
                    "(\\n\\s*)var\\s+engine\\s*=\\s*new\\s+Engine\\(GODOT_CONFIG\\);",
                    $"$1window.__PHASEA_WEB_PREVIEW_ASSET_VERSION = '{assetVersion}';$1var engine = new Engine(GODOT_CONFIG);",
                    RegexOptions.None,
                    TimeSpan.FromSeconds(1));
            }
        }

        if (!html.Contains($"index.js?v={assetVersion}", StringComparison.Ordinal) ||
            !html.Contains($"window.__PHASEA_WEB_PREVIEW_ASSET_VERSION = '{assetVersion}'", StringComparison.Ordinal))
        {
            throw new InvalidOperationException("Failed to version Godot web preview HTML assets.");
        }

        File.WriteAllText(indexPath, html, new UTF8Encoding(false));

        var script = File.ReadAllText(scriptPath, Encoding.UTF8);
        if (!script.Contains("phaseAAppendAssetVersion", StringComparison.Ordinal))
        {
            script = script.Replace(
                "const InternalConfig = function (initConfig) { // eslint-disable-line no-unused-vars",
                """
function phaseAAppendAssetVersion(file) {
	const version = (typeof window !== 'undefined' && window.__PHASEA_WEB_PREVIEW_ASSET_VERSION) || '';
	if (!version || typeof file !== 'string' || file.indexOf('?') !== -1 || file.indexOf('data:') === 0 || file.indexOf('blob:') === 0) {
		return file;
	}
	return `${file}?v=${encodeURIComponent(version)}`;
}

const InternalConfig = function (initConfig) { // eslint-disable-line no-unused-vars
""",
                StringComparison.Ordinal);

            script = script.Replace(
                "return `${loadPath}.worker.js`;",
                "return phaseAAppendAssetVersion(`${loadPath}.worker.js`);",
                StringComparison.Ordinal);
            script = script.Replace(
                "return `${loadPath}.audio.worklet.js`;",
                "return phaseAAppendAssetVersion(`${loadPath}.audio.worklet.js`);",
                StringComparison.Ordinal);
            script = script.Replace(
                "return `${loadPath}.js`;",
                "return phaseAAppendAssetVersion(`${loadPath}.js`);",
                StringComparison.Ordinal);
            script = script.Replace(
                "return `${loadPath}.side.wasm`;",
                "return phaseAAppendAssetVersion(`${loadPath}.side.wasm`);",
                StringComparison.Ordinal);
            script = script.Replace(
                "return `${loadPath}.wasm`;",
                "return phaseAAppendAssetVersion(`${loadPath}.wasm`);",
                StringComparison.Ordinal);
            script = script.Replace(
                "loadPromise = preloader.loadPromise(`${loadPath}.wasm`, size, true);",
                "loadPromise = preloader.loadPromise(phaseAAppendAssetVersion(`${loadPath}.wasm`), size, true);",
                StringComparison.Ordinal);
            script = script.Replace(
                "return preloader.preload(file, path, this.config.fileSizes[file]);",
                "return preloader.preload(phaseAAppendAssetVersion(file), path, this.config.fileSizes[file] || this.config.fileSizes[path]);",
                StringComparison.Ordinal);
        }

        if (!script.Contains("phaseAAppendAssetVersion(`${loadPath}.wasm`)", StringComparison.Ordinal) ||
            !script.Contains("phaseAAppendAssetVersion(file)", StringComparison.Ordinal))
        {
            throw new InvalidOperationException("Failed to version Godot web preview JavaScript assets.");
        }

        File.WriteAllText(scriptPath, script, new UTF8Encoding(false));
    }

    private static string ComputeWebAssetVersion(string packageSha256, string createdUtc)
    {
        var input = Encoding.UTF8.GetBytes($"{packageSha256}:{createdUtc}");
        return Convert.ToHexString(SHA256.HashData(input)).ToLowerInvariant()[..16];
    }

    private static string SerializeWebPreviewManifest(PackageWebPreviewManifest manifest)
    {
        return JsonSerializer.Serialize(manifest, GodotJsonOptions);
    }

    private static string ComputeStringSha256(string value)
    {
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(value))).ToLowerInvariant();
    }

    private string ComputePreviewSignature(
        string projectId,
        string previewId,
        string packageSha256,
        string assetVersion,
        string createdUtc,
        string mode,
        string converterId,
        string converterCompatibilityId,
        string sourceSceneSha256,
        string textCatalogSha256,
        string manifestSha256)
    {
        var secret = ResolvePreviewSigningSecret();
        if (string.IsNullOrWhiteSpace(secret))
        {
            throw new InvalidOperationException("A web preview signing secret is not configured.");
        }

        var payload = string.Join(
            '\n',
            projectId,
            previewId,
            packageSha256,
            assetVersion,
            createdUtc,
            mode,
            converterId,
            converterCompatibilityId,
            sourceSceneSha256,
            textCatalogSha256,
            manifestSha256);
        using var hmac = new HMACSHA256(Encoding.UTF8.GetBytes(secret));
        return Convert.ToHexString(hmac.ComputeHash(Encoding.UTF8.GetBytes(payload))).ToLowerInvariant();
    }

    private string ComputeLegacyPreviewSignature(
        string projectId,
        string previewId,
        string packageSha256,
        string assetVersion,
        string createdUtc,
        string mode,
        string converterId,
        string converterCompatibilityId,
        string sourceSceneSha256,
        string textCatalogSha256)
    {
        var secret = ResolvePreviewSigningSecret();
        if (string.IsNullOrWhiteSpace(secret))
        {
            throw new InvalidOperationException("A web preview signing secret is not configured.");
        }

        var payload = string.Join(
            '\n',
            projectId,
            previewId,
            packageSha256,
            assetVersion,
            createdUtc,
            mode,
            converterId,
            converterCompatibilityId,
            sourceSceneSha256,
            textCatalogSha256);
        using var hmac = new HMACSHA256(Encoding.UTF8.GetBytes(secret));
        return Convert.ToHexString(hmac.ComputeHash(Encoding.UTF8.GetBytes(payload))).ToLowerInvariant();
    }

    private string? ResolvePreviewSigningSecret()
    {
        return _options.WebPreviewSigningSecret;
    }

    private static string ReadJsonString(JsonElement root, string name)
    {
        return root.TryGetProperty(name, out var element) ? element.GetString() ?? "" : "";
    }

    private static bool TryPatchGodotLoadingEstimate(string indexPath)
    {
        if (!File.Exists(indexPath))
        {
            return false;
        }

        var html = File.ReadAllText(indexPath, Encoding.UTF8);
        if (html.Contains("phasea-loading-estimate", StringComparison.Ordinal))
        {
            return true;
        }

        html = html.Replace(
            "#status-progress-inner {\n\t\t\theight: 100%;",
            """
#phasea-loading-estimate {
			margin-top: 18px;
			min-width: 366px;
			text-align: center;
			font-size: 15px;
			line-height: 1.45;
			visibility: visible;
			padding: 5px 8px;
		}

		#status-progress-inner {
			height: 100%;
""",
            StringComparison.Ordinal);

        html = html.Replace(
            "align-items: center;\n\t\t\t/* don't consume click events - make children visible explicitly */",
            "align-items: center;\n\t\t\tflex-direction: column;\n\t\t\t/* don't consume click events - make children visible explicitly */",
            StringComparison.Ordinal);

        html = html.Replace(
            "<div id='status-progress' style='display: none;' oncontextmenu='event.preventDefault();'><div id ='status-progress-inner'></div></div>",
            "<div id='status-progress' style='display: none;' oncontextmenu='event.preventDefault();'><div id ='status-progress-inner'></div></div>\n\t\t<div id='phasea-loading-estimate' class='godot' style='display: none;'>游戏加载中...预计进度0%</div>",
            StringComparison.Ordinal);

        html = html.Replace(
            "var statusProgressInner = document.getElementById('status-progress-inner');\n\t\t\tvar statusIndeterminate = document.getElementById('status-indeterminate');",
            "var statusProgressInner = document.getElementById('status-progress-inner');\n\t\t\tvar phaseALoadingEstimate = document.getElementById('phasea-loading-estimate');\n\t\t\tvar statusIndeterminate = document.getElementById('status-indeterminate');",
            StringComparison.Ordinal);

        html = html.Replace(
            "var initializing = true;\n\t\t\tvar statusMode = 'hidden';",
            """
var initializing = true;
			var statusMode = 'hidden';
			var phaseAEstimatedPercent = 0;
			var phaseAHasRealProgress = false;
			var phaseAEstimateTimer = setInterval(function() {
				if (!initializing)
					return;
				if (phaseAHasRealProgress && statusProgressInner) {
					var barPercent = parseFloat(statusProgressInner.style.width || '0');
					if (!Number.isNaN(barPercent))
						phaseAEstimatedPercent = Math.min(99, barPercent);
				} else {
					phaseAEstimatedPercent = Math.min(99, phaseAEstimatedPercent + (phaseAEstimatedPercent < 55 ? 1 : 0.5));
				}
				setPhaseALoadingEstimate(phaseAEstimatedPercent);
			}, 450);

			function setPhaseALoadingEstimate(percent) {
				if (!phaseALoadingEstimate)
					return;
				var value = Math.max(0, Math.min(99, Math.floor(percent)));
				phaseALoadingEstimate.textContent = '游戏加载中...预计进度' + value + '%';
			}
""",
            StringComparison.Ordinal);

        html = html.Replace(
            "[statusProgress, statusIndeterminate, statusNotice].forEach(elem => {",
            "[statusProgress, statusIndeterminate, statusNotice, phaseALoadingEstimate].forEach(elem => {",
            StringComparison.Ordinal);

        html = html.Replace(
            "statusProgress.style.display = 'block';\n\t\t\t\t\t\tbreak;",
            "statusProgress.style.display = 'block';\n\t\t\t\t\t\tphaseALoadingEstimate.style.display = 'block';\n\t\t\t\t\t\tbreak;",
            StringComparison.Ordinal);

        html = html.Replace(
            "statusIndeterminate.style.display = 'block';\n\t\t\t\t\t\tanimationCallbacks.push(animateStatusIndeterminate);",
            "statusIndeterminate.style.display = 'block';\n\t\t\t\t\t\tphaseALoadingEstimate.style.display = 'block';\n\t\t\t\t\t\tanimationCallbacks.push(animateStatusIndeterminate);",
            StringComparison.Ordinal);

        html = html.Replace(
            "statusProgressInner.style.width = current/total * 100 + '%';\n\t\t\t\t\t\t\tsetStatusMode('progress');",
            "var phaseAProgressPercent = Math.min(99, current/total * 100);\n\t\t\t\t\t\t\tphaseAHasRealProgress = true;\n\t\t\t\t\t\t\tphaseAEstimatedPercent = phaseAProgressPercent;\n\t\t\t\t\t\t\tstatusProgressInner.style.width = current/total * 100 + '%';\n\t\t\t\t\t\t\tsetPhaseALoadingEstimate(phaseAEstimatedPercent);\n\t\t\t\t\t\t\tsetStatusMode('progress');",
            StringComparison.Ordinal);

        html = html.Replace(
            "setStatusMode('hidden');\n\t\t\t\t\tinitializing = false;",
            "setStatusMode('hidden');\n\t\t\t\t\tinitializing = false;\n\t\t\t\t\tclearInterval(phaseAEstimateTimer);",
            StringComparison.Ordinal);

        if (!html.Contains("phasea-loading-estimate", StringComparison.Ordinal) ||
            !html.Contains("setPhaseALoadingEstimate", StringComparison.Ordinal) ||
            !html.Contains("游戏加载中...预计进度", StringComparison.Ordinal))
        {
            return false;
        }

        File.WriteAllText(indexPath, html, new UTF8Encoding(false));
        return true;
    }

    private static ProjectWebPreviewResult Failure(string projectId, string runId, string fileName, string failureCode)
    {
        return new ProjectWebPreviewResult(projectId, runId, failureCode, fileName, "", "", "", "", failureCode, []);
    }

    private static string ComputePreviewId(string projectId, string packagePath)
    {
        var sha = ComputeFileSha256Cached(packagePath);
        return ComputePreviewIdFromSha(packagePath, sha);
    }

    private static string ComputePreviewIdFromSha(string packagePath, string sha)
    {
        var fileName = Path.GetFileNameWithoutExtension(packagePath);
        return $"{SanitizePathSegment(fileName)}-{sha[..16]}";
    }

    private static string ComputeFileSha256Cached(string path)
    {
        var fullPath = Path.GetFullPath(path);
        var info = new FileInfo(fullPath);
        var lastWriteUtc = info.LastWriteTimeUtc;
        var length = info.Length;
        var now = DateTimeOffset.UtcNow;
        if (PackageHashCache.TryGetValue(fullPath, out var cached) &&
            cached.Length == length &&
            cached.LastWriteUtc == lastWriteUtc &&
            now - cached.LastAccessUtc <= PackageHashCacheTtl)
        {
            PackageHashCache[fullPath] = cached with { LastAccessUtc = now };
            return cached.Sha256;
        }

        var sha = ComputeFileSha256(fullPath);
        PackageHashCache[fullPath] = new PackageHashCacheEntry(length, lastWriteUtc, sha, now);
        TrimPackageHashCache(now);
        return sha;
    }

    private static void TrimPackageHashCache(DateTimeOffset now)
    {
        foreach (var item in PackageHashCache)
        {
            if (now - item.Value.LastAccessUtc > PackageHashCacheTtl)
            {
                PackageHashCache.TryRemove(item.Key, out _);
            }
        }

        var overflow = PackageHashCache.Count - PackageHashCacheMaxEntries;
        if (overflow <= 0)
        {
            return;
        }

        foreach (var item in PackageHashCache
                     .OrderBy(item => item.Value.LastAccessUtc)
                     .ThenBy(item => item.Key, StringComparer.OrdinalIgnoreCase)
                     .Take(overflow))
        {
            PackageHashCache.TryRemove(item.Key, out _);
        }
    }

    private static string ComputeFileSha256(string path)
    {
        using var stream = File.OpenRead(path);
        return Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
    }

    private static string ComputeZipEntrySha256(ZipArchiveEntry entry)
    {
        using var stream = entry.Open();
        return Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
    }

    private static string ResolveUnderProject(string projectRoot, string relativePath)
    {
        var fullPath = Path.GetFullPath(Path.Combine(projectRoot, relativePath.Replace('/', Path.DirectorySeparatorChar)));
        if (!WorkspacePathPolicy.IsUnderRoot(projectRoot, fullPath))
        {
            throw new InvalidOperationException("Web preview path escaped project repository root.");
        }

        return fullPath;
    }

    private static void ReplaceDirectory(string sourceDirectory, string targetDirectory)
    {
        var backupDirectory = $"{targetDirectory}.replace-{Guid.NewGuid():N}.bak";
        DeleteDirectoryIfExists(backupDirectory);

        if (Directory.Exists(targetDirectory))
        {
            Directory.Move(targetDirectory, backupDirectory);
        }

        try
        {
            try
            {
                Directory.Move(sourceDirectory, targetDirectory);
            }
            catch (IOException)
            {
                CopyDirectory(sourceDirectory, targetDirectory);
                TryDeleteDirectoryIfExists(sourceDirectory);
            }
            catch (UnauthorizedAccessException)
            {
                CopyDirectory(sourceDirectory, targetDirectory);
                TryDeleteDirectoryIfExists(sourceDirectory);
            }

            TryDeleteDirectoryIfExists(backupDirectory);
        }
        catch
        {
            if (!Directory.Exists(targetDirectory) && Directory.Exists(backupDirectory))
            {
                Directory.Move(backupDirectory, targetDirectory);
            }

            throw;
        }
    }

    private static void CopyDirectory(string sourceDirectory, string targetDirectory)
    {
        if (Directory.Exists(targetDirectory))
        {
            throw new IOException("Target directory already exists.");
        }

        Directory.CreateDirectory(targetDirectory);
        foreach (var sourceFile in Directory.EnumerateFiles(sourceDirectory, "*", SearchOption.AllDirectories))
        {
            var relativePath = Path.GetRelativePath(sourceDirectory, sourceFile);
            var targetFile = Path.Combine(targetDirectory, relativePath);
            Directory.CreateDirectory(Path.GetDirectoryName(targetFile)!);
            File.Copy(sourceFile, targetFile, overwrite: false);
        }
    }

    private static void DeleteDirectoryIfExists(string directory)
    {
        if (Directory.Exists(directory))
        {
            Directory.Delete(directory, recursive: true);
        }
    }

    private static void TryDeleteDirectoryIfExists(string directory)
    {
        try
        {
            DeleteDirectoryIfExists(directory);
        }
        catch (IOException)
        {
            // Best-effort cleanup; Windows may keep Godot export files locked briefly.
        }
        catch (UnauthorizedAccessException)
        {
            // Best-effort cleanup; lock release and generated previews must not depend on deletion.
        }
    }

    private static void TryDeleteExternalDirectory(string directory)
    {
        try
        {
            if (Directory.Exists(directory))
            {
                Directory.Delete(directory, recursive: true);
            }
        }
        catch (IOException)
        {
            // Best-effort cleanup for health-smoke temp directories.
        }
        catch (UnauthorizedAccessException)
        {
            // Best-effort cleanup for health-smoke temp directories.
        }
    }

    private static bool IsSafeFileName(string fileName)
    {
        return !string.IsNullOrWhiteSpace(fileName) &&
               string.Equals(fileName, Path.GetFileName(fileName), StringComparison.Ordinal) &&
               fileName.EndsWith(".zip", StringComparison.OrdinalIgnoreCase);
    }

    private static bool IsSafePathSegment(string segment)
    {
        return !string.IsNullOrWhiteSpace(segment) &&
               segment.All(ch => char.IsLetterOrDigit(ch) || ch is '-' or '_' or '.');
    }

    private static string SanitizePathSegment(string value)
    {
        var builder = new StringBuilder(value.Length);
        foreach (var ch in value)
        {
            builder.Append(char.IsLetterOrDigit(ch) || ch is '-' or '_' or '.' ? ch : '-');
        }

        var sanitized = builder.ToString().Trim('-', '.', '_');
        return string.IsNullOrWhiteSpace(sanitized) ? "preview" : sanitized;
    }

    private static string ResolveContentType(string path)
    {
        return Path.GetExtension(path).ToLowerInvariant() switch
        {
            ".html" => "text/html; charset=utf-8",
            ".json" => "application/json; charset=utf-8",
            ".js" => "text/javascript; charset=utf-8",
            ".css" => "text/css; charset=utf-8",
            ".png" => "image/png",
            ".jpg" or ".jpeg" => "image/jpeg",
            ".webp" => "image/webp",
            ".svg" => "image/svg+xml",
            ".wasm" => "application/wasm",
            ".pck" => "application/octet-stream",
            ".worklet" => "text/javascript; charset=utf-8",
            _ => "application/octet-stream"
        };
    }

    private static string EscapeGodotString(string value)
    {
        return value.Replace("\\", "\\\\", StringComparison.Ordinal).Replace("\"", "\\\"", StringComparison.Ordinal);
    }

    private static string Tail(string value, int maxLength)
    {
        if (string.IsNullOrEmpty(value) || value.Length <= maxLength)
        {
            return value;
        }

        return value[^maxLength..];
    }

    private static bool TryResolveConverter(
        PackageInfo packageInfo,
        out ProjectWebPreviewConverterDescriptor converter,
        out string failureCode,
        out string failureMessage)
    {
        converter = GenericGodotPackageConverter;
        failureCode = "";
        failureMessage = "";

        if (packageInfo.WebPreviewManifest.DetectedTemplates.Contains("towerdemo2", StringComparer.Ordinal) &&
            string.Equals(packageInfo.Towerdemo2SourceSceneSha256, Towerdemo2Converter.SourceSceneSha256, StringComparison.OrdinalIgnoreCase) &&
            string.Equals(packageInfo.Towerdemo2TextCatalogSha256, Towerdemo2Converter.TextCatalogSha256, StringComparison.OrdinalIgnoreCase))
        {
            converter = Towerdemo2Converter;
            return true;
        }

        if (!string.IsNullOrWhiteSpace(packageInfo.MainScene) || packageInfo.Scenes.Count > 0)
        {
            converter = ResolvePackageConverterByType(packageInfo);
            return true;
        }

        failureCode = "unsupported_package_template";
        failureMessage = UnsupportedPackageTemplateMessage();
        return false;
    }

    private static ProjectWebPreviewConverterDescriptor ResolvePackageConverterByType(PackageInfo packageInfo)
    {
        var candidates = BuildPackageTypeCandidates(packageInfo);
        foreach (var candidate in candidates)
        {
            var converter = ConverterRegistry
                .Skip(1)
                .Where(item => !string.Equals(item.Id, GenericGodotPackageConverter.Id, StringComparison.Ordinal))
                .FirstOrDefault(item => item.GameTypeIds.Contains(candidate, StringComparer.Ordinal));
            if (converter is not null)
            {
                return converter;
            }
        }

        return GenericGodotPackageConverter;
    }

    private static IReadOnlyList<string> BuildPackageTypeCandidates(PackageInfo packageInfo)
    {
        var values = new List<string>
        {
            packageInfo.GameTypeId,
            packageInfo.GameTypeGuide,
            packageInfo.GameTypeSource,
            packageInfo.GameName,
            packageInfo.ProjectName
        };
        values.AddRange(packageInfo.Scenes);

        var candidates = new List<string>();
        foreach (var value in values)
        {
            var normalized = ProjectWebPreviewGameTypeCatalog.NormalizeGameTypeToken(value);
            if (!string.IsNullOrWhiteSpace(normalized))
            {
                candidates.Add(normalized);
            }

            var knownTypeId = ProjectWebPreviewGameTypeCatalog.ResolveGameTypeId(value);
            if (!string.IsNullOrWhiteSpace(knownTypeId))
            {
                candidates.Add(knownTypeId);
            }

            var lower = value.ToLowerInvariant();
            if (lower.Contains("deck", StringComparison.Ordinal) || lower.Contains("card", StringComparison.Ordinal))
            {
                candidates.Add("card");
                candidates.Add("deckbuilder");
            }

            if (lower.Contains("survivor", StringComparison.Ordinal) || lower.Contains("arena", StringComparison.Ordinal))
            {
                candidates.Add("survivorslike");
            }

            if (lower.Contains("tower", StringComparison.Ordinal) && lower.Contains("defen", StringComparison.Ordinal))
            {
                candidates.Add("tower-defense");
            }

            if (lower.Contains("rpg", StringComparison.Ordinal) || lower.Contains("role", StringComparison.Ordinal) || lower.Contains("battle", StringComparison.Ordinal))
            {
                candidates.Add("rpg");
            }
        }

        return candidates.Distinct(StringComparer.Ordinal).ToArray();
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

    private static string ResolveConverterSourceSceneSha256(
        PackageInfo packageInfo,
        ProjectWebPreviewConverterDescriptor converter)
    {
        return string.Equals(converter.Id, Towerdemo2Converter.Id, StringComparison.Ordinal)
            ? packageInfo.Towerdemo2SourceSceneSha256
            : "";
    }

    private static string ResolveConverterTextCatalogSha256(
        PackageInfo packageInfo,
        ProjectWebPreviewConverterDescriptor converter)
    {
        return string.Equals(converter.Id, Towerdemo2Converter.Id, StringComparison.Ordinal)
            ? packageInfo.Towerdemo2TextCatalogSha256
            : "";
    }

    private static string UnsupportedPackageTemplateMessage()
    {
        return string.Join(" ", ConverterRegistry.Select(converter => converter.UnsupportedPackageMessage));
    }

    private sealed record ProjectWebPreviewConverterDescriptor(
        string Id,
        string Mode,
        string CompatibilityId,
        string AdapterStyle,
        IReadOnlyList<string> GameTypeIds,
        string SourceScenePath,
        string TextCatalogPath,
        string SourceSceneSha256,
        string TextCatalogSha256,
        string CoverageSummary,
        string UnsupportedPackageMessage);

    private sealed record Godot3ExportResult(
        HostedProcessResult Process,
        string ExportMode);

    private sealed record PackageHashCacheEntry(
        long Length,
        DateTime LastWriteUtc,
        string Sha256,
        DateTimeOffset LastAccessUtc);

    private sealed record PreviewReadyData(
        string Mode,
        string CreatedUtc,
        string PackageFile,
        string PackageSha256,
        string FidelityTier,
        string PlayableSurface,
        string GameTypeId,
        string GameTypeGuide)
    {
        public static PreviewReadyData Empty { get; } = new("", "", "", "", "", "", "", "");
    }

    private sealed record PackageWebPreviewManifest(
        [property: JsonPropertyName("schema_version")] string SchemaVersion,
        [property: JsonPropertyName("source")] string Source,
        [property: JsonPropertyName("project_id")] string ProjectId,
        [property: JsonPropertyName("project_name")] string ProjectName,
        [property: JsonPropertyName("game_name")] string GameName,
        [property: JsonPropertyName("game_type_source")] string GameTypeSource,
        [property: JsonPropertyName("game_type_id")] string GameTypeId,
        [property: JsonPropertyName("game_type_guide")] string GameTypeGuide,
        [property: JsonPropertyName("package_file")] string PackageFile,
        [property: JsonPropertyName("package_sha256")] string PackageSha256,
        [property: JsonPropertyName("package_size_bytes")] long PackageSizeBytes,
        [property: JsonPropertyName("main_scene")] string MainScene,
        [property: JsonPropertyName("scenes")] IReadOnlyList<string> Scenes,
        [property: JsonPropertyName("source_fingerprints")] IReadOnlyList<PackageWebPreviewSourceFingerprint> SourceFingerprints,
        [property: JsonPropertyName("text_key_count")] int TextKeyCount,
        [property: JsonPropertyName("detected_templates")] IReadOnlyList<string> DetectedTemplates,
        [property: JsonPropertyName("detected_capabilities")] IReadOnlyList<string> DetectedCapabilities,
        [property: JsonPropertyName("conversion_contract")] PackageWebPreviewContract ConversionContract);

    private sealed record PackageWebPreviewContract(
        [property: JsonPropertyName("selection_policy")] string SelectionPolicy,
        [property: JsonPropertyName("playable_surface")] string PlayableSurface,
        [property: JsonPropertyName("fidelity_tier")] string FidelityTier,
        [property: JsonPropertyName("data_sources")] IReadOnlyList<string> DataSources,
        [property: JsonPropertyName("input_actions")] IReadOnlyList<PackageWebPreviewInputAction> InputActions);

    private sealed record PackageWebPreviewInputAction(
        [property: JsonPropertyName("action")] string Action,
        [property: JsonPropertyName("inputs")] IReadOnlyList<string> Inputs,
        [property: JsonPropertyName("behavior")] string Behavior);

    private sealed record PackageWebPreviewSourceFingerprint(
        [property: JsonPropertyName("path")] string Path,
        [property: JsonPropertyName("role")] string Role,
        [property: JsonPropertyName("sha256")] string Sha256);

    private sealed record PackageInfo(
        string FileName,
        string ProjectName,
        string GameName,
        string GameTypeSource,
        string GameTypeId,
        string GameTypeGuide,
        string? MainScene,
        IReadOnlyList<string> Scenes,
        IReadOnlyDictionary<string, string> Texts,
        bool IsTowerdemo2,
        string Towerdemo2SourceSceneSha256,
        string Towerdemo2TextCatalogSha256,
        long PackageSizeBytes,
        string PackageSha256,
        PackageWebPreviewManifest WebPreviewManifest);
}
