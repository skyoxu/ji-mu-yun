using System.Collections.Concurrent;
using System.IO.Compression;
using System.Security.Cryptography;
using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.Json.Nodes;
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
    private const string PlayablePreviewContractFileName = "playable-preview-contract.json";
    private const string DedicatedAdapterRootDirectory = "exports/web-preview-dedicated-adapters";
    private const string DedicatedAdapterManifestFileName = "adapter-manifest.json";
    private const string DedicatedAdapterMainScriptFileName = "Main.gd";
    private const string DedicatedAdapterSchemaVersion = "phasea-web-preview-dedicated-adapter-v1";
    private const int MaxVisualAssetHints = 24;
    private const int MaxInputMapHints = 24;
    private const int MaxScriptBehaviorHints = 24;
    private const int MaxSceneGraphHints = 16;
    private const int MaxSceneGraphNodeHints = 32;
    private const long MaxPreviewCopiedAssetBytes = 512 * 1024;
    private const long MaxPreviewSceneGraphBytes = 512 * 1024;
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
    private const long MaxPlayablePreviewContractBytes = 256L * 1024L;
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
    private readonly ProjectWebPreviewSemanticAdapterService _semanticAdapterService;
    private readonly ProjectWebPreviewDedicatedAdapterService _dedicatedAdapterService;
    private readonly ConcurrentDictionary<string, ProjectWebPreviewConcurrencyLease> _reservedAccountConcurrencyLeases = new(StringComparer.Ordinal);

    public ProjectWebPreviewService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        [FromKeyedServices("web-preview")] HeavyRunnerQueueService? webPreviewQueue = null,
        ProjectWebPreviewConcurrencyLimiter? webPreviewConcurrencyLimiter = null,
        IHostedProcessRunner? processRunner = null,
        ProjectWebPreviewSemanticAdapterService? semanticAdapterService = null,
        ProjectWebPreviewDedicatedAdapterService? dedicatedAdapterService = null)
    {
        _metadataStore = metadataStore;
        _options = options;
        _webPreviewQueue = webPreviewQueue ?? new HeavyRunnerQueueService(TimeSpan.FromMinutes(3), options.MaxConcurrentWebPreviews);
        _webPreviewConcurrencyLimiter = webPreviewConcurrencyLimiter ?? new ProjectWebPreviewConcurrencyLimiter(options.MaxConcurrentWebPreviewsPerAccount);
        _processRunner = processRunner ?? new HostedProcessRunner();
        _semanticAdapterService = semanticAdapterService ?? ProjectWebPreviewSemanticAdapterService.DeterministicOnly(options);
        _dedicatedAdapterService = dedicatedAdapterService ?? ProjectWebPreviewDedicatedAdapterService.DeterministicOnly(options);
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
                    ConversionContract = BuildWebPreviewContract(converter, packageInfo.MainScene, packageInfo.Scenes, packageInfo.Texts.Count, packageInfo.PlayablePreviewContract.HasValue)
                }
            };
            var manifestJson = SerializeWebPreviewManifest(packageInfo.WebPreviewManifest);
            var semanticAdapter = await _semanticAdapterService.ResolveAsync(
                new ProjectWebPreviewSemanticAdapterRequest(
                    project.AccountId,
                    runId,
                    project,
                    projectRoot,
                    fileName,
                    packageInfo.PackageSha256,
                    packageInfo.PackageSizeBytes,
                    packageInfo.GameName,
                    packageInfo.GameTypeSource,
                    packageInfo.GameTypeId,
                    packageInfo.GameTypeGuide,
                    packageInfo.MainScene,
                    packageInfo.Scenes,
                    packageInfo.PlayablePreviewContract?.GetRawText() ?? "{}",
                    manifestJson),
                cancellationToken);
            packageInfo = packageInfo with
            {
                SemanticAdapter = FilterSemanticAdapterForPreview(packageInfo.WebPreviewManifest, semanticAdapter.Adapter),
                SemanticAdapterResolution = semanticAdapter.Resolution
            };
            string? dedicatedMainScript = null;
            if (!string.Equals(converter.Id, Towerdemo2Converter.Id, StringComparison.Ordinal))
            {
                var dedicatedAdapter = await _dedicatedAdapterService.ResolveAsync(
                    new ProjectWebPreviewDedicatedAdapterRequest(
                        project.AccountId,
                        runId,
                        project,
                        projectRoot,
                        fileName,
                        packageInfo.PackageSha256,
                        packageInfo.ProjectName,
                        packageInfo.GameName,
                        packageInfo.GameTypeId,
                        packageInfo.GameTypeGuide,
                        converter.Id,
                        converter.Mode,
                        packageInfo.MainScene,
                        packageInfo.Scenes,
                        packageInfo.PlayablePreviewContract?.GetRawText() ?? "{}",
                        packageInfo.SemanticAdapter?.GetRawText() ?? "{}",
                        manifestJson),
                    RenderPackageAdapterMainScript(converter.AdapterStyle),
                    cancellationToken);
                dedicatedMainScript = dedicatedAdapter.MainScript;
                packageInfo = packageInfo with
                {
                    DedicatedAdapterResolution = dedicatedAdapter.Resolution
                };
            }

            var previewId = ComputePreviewIdFromSha(packagePath, packageInfo.PackageSha256);
            var previewRelativeRoot = $"{PreviewRootDirectory}/{previewId}";
            var previewRoot = ResolveUnderProject(projectRoot, previewRelativeRoot);
            workPreviewRoot = ResolveUnderProject(projectRoot, $"{PreviewRootDirectory}/.{previewId}.{runId}.build");
            var godotProjectRoot = Path.Combine(workPreviewRoot, "godot3-project");
            var webRoot = Path.Combine(workPreviewRoot, "web");
            DeleteDirectoryIfExists(workPreviewRoot);

            Directory.CreateDirectory(godotProjectRoot);
            Directory.CreateDirectory(webRoot);
            CreateGodot3Project(projectRoot, godotProjectRoot, packageInfo, converter, dedicatedMainScript);

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
                File.Copy(
                    Path.Combine(godotProjectRoot, "preview-package-data.json"),
                    Path.Combine(webRoot, "preview-package-data.json"),
                    overwrite: true);
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
                playable_preview_contract = packageInfo.PlayablePreviewContract,
                semantic_adapter = packageInfo.SemanticAdapter,
                semantic_adapter_resolution = packageInfo.SemanticAdapterResolution,
                dedicated_adapter_resolution = packageInfo.DedicatedAdapterResolution,
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
                semantic_adapter = packageInfo.SemanticAdapter,
                semantic_adapter_resolution = packageInfo.SemanticAdapterResolution,
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
        string repositoryRoot,
        string godotProjectRoot,
        PackageInfo packageInfo,
        ProjectWebPreviewConverterDescriptor converter,
        string? dedicatedMainScript)
    {
        if (string.Equals(converter.Id, Towerdemo2Converter.Id, StringComparison.Ordinal))
        {
            CreateTowerdemo2Godot3Project(repositoryRoot, godotProjectRoot, packageInfo, converter);
            return;
        }

        CreateGenericGodotPackageProject(godotProjectRoot, packageInfo, converter, dedicatedMainScript);
    }

    private static void CreateTowerdemo2Godot3Project(
        string repositoryRoot,
        string godotProjectRoot,
        PackageInfo packageInfo,
        ProjectWebPreviewConverterDescriptor converter)
    {
        var mainScript = ResolveDedicatedMainScript(repositoryRoot, packageInfo, converter, RenderMainScript());
        WriteGodot3ProjectFiles(godotProjectRoot, packageInfo, converter, RenderMainScene("Towerdemo2WebPreview"), mainScript);
    }

    private static void CreateGenericGodotPackageProject(
        string projectRoot,
        PackageInfo packageInfo,
        ProjectWebPreviewConverterDescriptor converter,
        string? dedicatedMainScript)
    {
        var mainScript = string.IsNullOrWhiteSpace(dedicatedMainScript)
            ? RenderPackageAdapterMainScript(converter.AdapterStyle)
            : dedicatedMainScript;
        WriteGodot3ProjectFiles(
            projectRoot,
            packageInfo,
            converter,
            RenderMainScene("GenericPackageWebPreview", SelectMainSceneNodeType(mainScript)),
            mainScript);
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
        CopyPreviewVisualAssets(packageInfo, Path.Combine(projectRoot, "PreviewAssets"));
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
                playable_preview_contract = packageInfo.PlayablePreviewContract,
                semantic_adapter = packageInfo.SemanticAdapter,
                semantic_adapter_resolution = packageInfo.SemanticAdapterResolution,
                dedicated_adapter_resolution = packageInfo.DedicatedAdapterResolution,
                web_preview_manifest = packageInfo.WebPreviewManifest,
                texts = packageInfo.Texts
            }, GodotJsonOptions),
            new UTF8Encoding(false));
    }

    private static string ResolveDedicatedMainScript(
        string projectRoot,
        PackageInfo packageInfo,
        ProjectWebPreviewConverterDescriptor converter,
        string builtInMainScript)
    {
        var packageVersion = SanitizePathSegment(Path.GetFileNameWithoutExtension(packageInfo.FileName));
        var adapterDirectory = ResolveUnderProject(projectRoot, $"{DedicatedAdapterRootDirectory}/{packageVersion}");
        var mainScriptPath = Path.Combine(adapterDirectory, DedicatedAdapterMainScriptFileName);
        var manifestPath = Path.Combine(adapterDirectory, DedicatedAdapterManifestFileName);
        var adapterSourceSha256 = ComputeStringSha256(builtInMainScript);
        if (TryReadReusableDedicatedMainScript(manifestPath, mainScriptPath, packageInfo, converter, adapterSourceSha256, out var cachedMainScript))
        {
            return cachedMainScript;
        }

        Directory.CreateDirectory(adapterDirectory);
        File.WriteAllText(mainScriptPath, builtInMainScript, new UTF8Encoding(false));
        File.WriteAllText(
            manifestPath,
            JsonSerializer.Serialize(new
            {
                schema_version = DedicatedAdapterSchemaVersion,
                source = "towerdemo2-built-in-template",
                adapter_version = packageVersion,
                converter_id = converter.Id,
                converter_compatibility_id = converter.CompatibilityId,
                mode = converter.Mode,
                adapter_source_sha256 = adapterSourceSha256,
                package_file = packageInfo.FileName,
                package_sha256 = packageInfo.PackageSha256,
                generated_utc = DateTimeOffset.UtcNow.ToString("O")
            }, GodotJsonOptions),
            new UTF8Encoding(false));
        return builtInMainScript;
    }

    private static bool TryReadReusableDedicatedMainScript(
        string manifestPath,
        string mainScriptPath,
        PackageInfo packageInfo,
        ProjectWebPreviewConverterDescriptor converter,
        string adapterSourceSha256,
        out string mainScript)
    {
        mainScript = "";
        if (!File.Exists(manifestPath) || !File.Exists(mainScriptPath))
        {
            return false;
        }

        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(manifestPath, Encoding.UTF8));
            var root = document.RootElement;
            if (!JsonStringEquals(root, "schema_version", DedicatedAdapterSchemaVersion) ||
                !JsonStringEquals(root, "converter_id", converter.Id) ||
                !JsonStringEquals(root, "adapter_source_sha256", adapterSourceSha256) ||
                !JsonStringEquals(root, "package_file", packageInfo.FileName) ||
                !JsonStringEquals(root, "package_sha256", packageInfo.PackageSha256))
            {
                return false;
            }

            mainScript = File.ReadAllText(mainScriptPath, Encoding.UTF8);
            return !string.IsNullOrWhiteSpace(mainScript);
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

    private static bool JsonStringEquals(JsonElement root, string propertyName, string expected)
    {
        return root.ValueKind == JsonValueKind.Object &&
            root.TryGetProperty(propertyName, out var value) &&
            value.ValueKind == JsonValueKind.String &&
            string.Equals(value.GetString(), expected, StringComparison.Ordinal);
    }

    private static JsonElement FilterSemanticAdapterForPreview(PackageWebPreviewManifest manifest, JsonElement adapter)
    {
        if (adapter.ValueKind != JsonValueKind.Object || !HasActionGameplayHints(manifest))
        {
            return adapter.Clone();
        }

        JsonObject? root;
        try
        {
            root = JsonNode.Parse(adapter.GetRawText()) as JsonObject;
        }
        catch (JsonException)
        {
            return adapter.Clone();
        }

        if (root is null || root["entities"] is not JsonArray entities)
        {
            return adapter.Clone();
        }

        var allowedScenes = BuildAllowedSemanticEntityScenes(manifest);
        if (allowedScenes.Count == 0)
        {
            return adapter.Clone();
        }

        var filtered = new JsonArray();
        foreach (var entity in entities)
        {
            if (entity is not JsonObject entityObject)
            {
                continue;
            }

            var scene = NormalizeResourcePath(entityObject["scene"]?.GetValue<string>() ?? "");
            var nodeType = entityObject["node_type"]?.GetValue<string>() ?? "";
            var label = entityObject["label"]?.GetValue<string>() ?? "";
            if (allowedScenes.Contains(scene) && !IsMenuOrDebugUiEntity(nodeType, label))
            {
                filtered.Add(entityObject.DeepClone());
            }
        }

        root["entities"] = filtered;
        using var document = JsonDocument.Parse(root.ToJsonString(JsonOptions));
        return document.RootElement.Clone();
    }

    private static bool HasActionGameplayHints(PackageWebPreviewManifest manifest)
    {
        return manifest.ScriptBehaviorHints.Any(hint =>
            hint.Roles.Contains("movement", StringComparer.Ordinal) ||
            hint.Roles.Contains("combat", StringComparer.Ordinal) ||
            hint.Roles.Contains("physics", StringComparer.Ordinal) ||
            hint.Roles.Contains("interaction", StringComparer.Ordinal));
    }

    private static HashSet<string> BuildAllowedSemanticEntityScenes(PackageWebPreviewManifest manifest)
    {
        var allowed = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var firstNonControlScene = manifest.SceneGraphHints
            .Where(hint => !string.Equals(hint.RootNodeType, "Control", StringComparison.Ordinal))
            .Take(1)
            .ToArray();
        foreach (var hint in firstNonControlScene.Length > 0 ? firstNonControlScene : manifest.SceneGraphHints.Take(1))
        {
            allowed.Add(NormalizeResourcePath(hint.Path));
        }

        return allowed;
    }

    private static string NormalizeResourcePath(string path)
    {
        return path.Replace('\\', '/').Replace("res://", "", StringComparison.OrdinalIgnoreCase);
    }

    private static bool IsMenuOrDebugUiEntity(string nodeType, string label)
    {
        if (string.Equals(nodeType, "Button", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(nodeType, "VBoxContainer", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(nodeType, "HBoxContainer", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(nodeType, "MarginContainer", StringComparison.OrdinalIgnoreCase))
        {
            return true;
        }

        return ContainsAny(label, "settings", "mainmenu", "publish", "saveload", "logbtn", "addscore", "losehp", "quit", "debug");
    }

    private static bool IsPreviewVisualAsset(string path)
    {
        var extension = Path.GetExtension(path).ToLowerInvariant();
        return extension is ".png" or ".jpg" or ".jpeg" or ".webp" or ".svg";
    }

    private static bool IsPreviewScriptAsset(string path)
    {
        var extension = Path.GetExtension(path).ToLowerInvariant();
        return extension is ".gd" or ".cs";
    }

    private static bool IsPreviewRuntimePath(string path)
    {
        var normalized = path.Replace('\\', '/');
        var lower = normalized.ToLowerInvariant();
        if (lower.StartsWith("tests.", StringComparison.Ordinal) ||
            lower.StartsWith("tests/", StringComparison.Ordinal) ||
            lower.Contains("/tests/", StringComparison.Ordinal) ||
            lower.Contains("/addons/", StringComparison.Ordinal) ||
            lower.Contains("/bin/", StringComparison.Ordinal) ||
            lower.Contains("/obj/", StringComparison.Ordinal))
        {
            return false;
        }

        return true;
    }

    private static bool IsPreviewRuntimeScriptPath(string path)
    {
        if (!IsPreviewRuntimePath(path))
        {
            return false;
        }

        var lower = path.Replace('\\', '/').ToLowerInvariant();
        if (lower.Contains(".tests/", StringComparison.Ordinal) ||
            lower.Contains(".tests.", StringComparison.Ordinal))
        {
            return false;
        }

        return lower.StartsWith("game.godot/", StringComparison.Ordinal) ||
            lower.StartsWith("game.core/", StringComparison.Ordinal) ||
            lower.Contains("/scripts/", StringComparison.Ordinal) ||
            lower.Contains("/prototypes/", StringComparison.Ordinal) ||
            lower.Contains("/scenes/", StringComparison.Ordinal);
    }

    private static string SanitizePreviewAssetName(string sourcePath)
    {
        var withoutPrefix = sourcePath
            .Replace('\\', '/')
            .Replace("res://", "", StringComparison.OrdinalIgnoreCase);
        var sanitized = Regex.Replace(withoutPrefix, @"[^A-Za-z0-9._-]+", "-", RegexOptions.CultureInvariant).Trim('-', '.', '_');
        return string.IsNullOrWhiteSpace(sanitized) ? "asset" + Path.GetExtension(sourcePath) : sanitized;
    }

    private static string ClassifyVisualAssetRole(string sourcePath)
    {
        var text = sourcePath.ToLowerInvariant();
        if (ContainsAny(text, "player", "hero", "character", "avatar", "actor"))
        {
            return "player_sprite";
        }

        if (ContainsAny(text, "enemy", "monster", "mob", "boss", "threat"))
        {
            return "threat_sprite";
        }

        if (ContainsAny(text, "item", "loot", "pickup", "reward", "weapon", "inventory"))
        {
            return "item_sprite";
        }

        if (ContainsAny(text, "tile", "terrain", "floor", "wall", "map", "level", "background"))
        {
            return "environment_sprite";
        }

        if (ContainsAny(text, "ui", "hud", "button", "icon", "panel"))
        {
            return "ui_sprite";
        }

        return "visual_asset";
    }

    private static int ScorePathRelevance(string path, string projectName, string gameName, string? mainScene)
    {
        var normalizedPath = NormalizeSearchToken(path);
        var score = 0;
        foreach (var token in BuildRelevanceTokens(projectName, gameName, mainScene))
        {
            if (normalizedPath.Contains(token, StringComparison.Ordinal))
            {
                score += 100;
            }
        }

        if (normalizedPath.Contains("prototype", StringComparison.Ordinal))
        {
            score += 15;
        }

        if (normalizedPath.Contains("gamegodot", StringComparison.Ordinal))
        {
            score += 10;
        }

        if (normalizedPath.Contains("gamecore", StringComparison.Ordinal))
        {
            score += 5;
        }

        return score;
    }

    private static IReadOnlyList<string> BuildRelevanceTokens(string projectName, string gameName, string? mainScene)
    {
        var tokens = new List<string>();
        foreach (var value in new[] { projectName, gameName, mainScene ?? "" })
        {
            var token = NormalizeSearchToken(value);
            if (token.Length >= 4 && !tokens.Contains(token, StringComparer.Ordinal))
            {
                tokens.Add(token);
            }

            foreach (var part in Regex.Split(value, @"[^A-Za-z0-9]+"))
            {
                var partToken = NormalizeSearchToken(part);
                if (partToken.Length >= 3 && !tokens.Contains(partToken, StringComparer.Ordinal))
                {
                    tokens.Add(partToken);
                }
            }
        }

        return tokens;
    }

    private static string NormalizeSearchToken(string value)
    {
        return Regex.Replace(value.ToLowerInvariant(), @"[^a-z0-9]+", "", RegexOptions.CultureInvariant);
    }

    private static int ScoreVisualRole(string role)
    {
        return role switch
        {
            "player_sprite" => 50,
            "threat_sprite" => 45,
            "item_sprite" => 35,
            "environment_sprite" => 25,
            "ui_sprite" => 10,
            _ => 0
        };
    }

    private static bool ContainsAny(string text, params string[] needles)
    {
        return needles.Any(needle => text.Contains(needle, StringComparison.OrdinalIgnoreCase));
    }

    private static IReadOnlyList<PackageWebPreviewInputMapHint> ExtractInputMapHints(string projectConfigText)
    {
        var hints = new List<PackageWebPreviewInputMapHint>();
        var inInputSection = false;
        using var reader = new StringReader(projectConfigText);
        while (reader.ReadLine() is { } line)
        {
            var trimmed = line.Trim();
            if (trimmed.StartsWith("[", StringComparison.Ordinal) && trimmed.EndsWith("]", StringComparison.Ordinal))
            {
                inInputSection = string.Equals(trimmed, "[input]", StringComparison.OrdinalIgnoreCase);
                continue;
            }

            if (!inInputSection || string.IsNullOrWhiteSpace(trimmed) || !trimmed.Contains('=', StringComparison.Ordinal))
            {
                continue;
            }

            var parts = trimmed.Split('=', 2);
            var action = parts[0].Trim().Trim('"');
            if (string.IsNullOrWhiteSpace(action))
            {
                continue;
            }

            hints.Add(new PackageWebPreviewInputMapHint(action, ExtractInputTokens(parts[1]), TrimForManifest(parts[1], 260)));
            if (hints.Count >= MaxInputMapHints)
            {
                break;
            }
        }

        return hints;
    }

    private static IReadOnlyList<string> ExtractInputTokens(string raw)
    {
        var tokens = new List<string>();
        foreach (Match match in Regex.Matches(raw, "\"(?<value>[A-Za-z0-9_+ .-]{1,48})\""))
        {
            var value = match.Groups["value"].Value.Trim();
            if (!string.IsNullOrWhiteSpace(value) && !tokens.Contains(value, StringComparer.OrdinalIgnoreCase))
            {
                tokens.Add(value);
            }
        }

        foreach (Match match in Regex.Matches(raw, @"(?:physical_keycode|keycode|button_index|axis)\s*:\s*(?<value>-?\d+)"))
        {
            var value = match.Groups["value"].Value.Trim();
            if (!tokens.Contains(value, StringComparer.OrdinalIgnoreCase))
            {
                tokens.Add(value);
            }
        }

        return tokens.Take(12).ToArray();
    }

    private static PackageWebPreviewScriptBehaviorHint BuildScriptBehaviorHint(string path, ZipArchiveEntry entry)
    {
        string text;
        using (var reader = new StreamReader(entry.Open(), Encoding.UTF8, detectEncodingFromByteOrderMarks: true))
        {
            text = reader.ReadToEnd();
        }

        var roles = new List<string>();
        AddRoleIf(text, roles, "input", "Input.", "_input", "_unhandled_input");
        AddRoleIf(text, roles, "physics", "_physics_process", "move_and_slide", "move_and_collide", "RigidBody", "CharacterBody", "KinematicBody");
        AddRoleIf(text, roles, "movement", "velocity", "speed", "direction", "move_");
        AddRoleIf(text, roles, "combat", "attack", "damage", "weapon", "shoot", "hit");
        AddRoleIf(text, roles, "interaction", "interact", "pickup", "loot", "use_", "collect");
        AddRoleIf(text, roles, "animation", "AnimatedSprite", "AnimationPlayer", "play(");
        AddRoleIf(text, roles, "camera", "Camera2D", "Camera3D", "camera");
        AddRoleIf(text, roles, "sprite", "Sprite", "Texture", "texture");

        var inputActions = ExtractScriptInputActions(text)
            .Distinct(StringComparer.Ordinal)
            .Take(16)
            .ToArray();
        var nodeRefs = Regex.Matches(text, @"\b(?<node>AnimatedSprite2D|AnimatedSprite|Sprite2D|Sprite3D|Sprite|TextureRect|AnimationPlayer|Camera2D|Camera3D|Area2D|CollisionShape2D|CharacterBody2D|KinematicBody2D|RigidBody2D|StaticBody2D)\b")
            .Select(match => match.Groups["node"].Value)
            .Distinct(StringComparer.Ordinal)
            .Take(16)
            .ToArray();

        return new PackageWebPreviewScriptBehaviorHint(
            path,
            Path.GetExtension(path).Equals(".cs", StringComparison.OrdinalIgnoreCase) ? "csharp" : "gdscript",
            roles.Distinct(StringComparer.Ordinal).Order(StringComparer.Ordinal).ToArray(),
            inputActions,
            nodeRefs,
            ExtractScriptExcerpt(text));
    }

    private static IReadOnlyList<string> ExtractScriptInputActions(string text)
    {
        var actions = new List<string>();
        foreach (Match match in Regex.Matches(text, @"Input\.(?:is_action_pressed|is_action_just_pressed|is_action_just_released|get_action_strength)\(\s*[""'](?<action>[^""']+)[""']"))
        {
            AddDistinct(actions, match.Groups["action"].Value);
        }

        foreach (Match match in Regex.Matches(text, @"(?m)\b(?:private|public|protected|internal)?\s*(?:const|static\s+readonly)\s+string\s+(?<name>[A-Za-z0-9_]*?(?:Action|Move|Fire|Shoot|Reload|Interact|Dash|Use)[A-Za-z0-9_]*)\s*=\s*""(?<action>[^""]+)"""))
        {
            AddDistinct(actions, match.Groups["action"].Value);
        }

        return actions;
    }

    private static void AddDistinct(List<string> values, string value)
    {
        if (!string.IsNullOrWhiteSpace(value) && !values.Contains(value, StringComparer.Ordinal))
        {
            values.Add(value);
        }
    }

    private static PackageWebPreviewSceneGraphHint BuildSceneGraphHint(string path, ZipArchiveEntry entry)
    {
        string text;
        using (var reader = new StreamReader(entry.Open(), Encoding.UTF8, detectEncodingFromByteOrderMarks: true))
        {
            text = reader.ReadToEnd();
        }

        var extResources = ParseTscnExtResources(text);
        var nodes = new List<PackageWebPreviewSceneNodeHint>();
        var nodeMatches = Regex.Matches(text, @"(?m)^\[node\s+(?<attrs>[^\]]+)\]\s*(?<body>.*?)(?=^\[|\z)", RegexOptions.Singleline);
        foreach (Match match in nodeMatches)
        {
            var attrs = ParseTscnAttributes(match.Groups["attrs"].Value);
            var body = match.Groups["body"].Value;
            var name = attrs.GetValueOrDefault("name", "");
            var type = attrs.GetValueOrDefault("type", "");
            var parent = attrs.GetValueOrDefault("parent", "");
            var scriptPath = ResolveTscnResourcePath(body, "script", extResources);
            var texturePath = ResolveTscnResourcePath(body, "texture", extResources);
            if (string.IsNullOrWhiteSpace(name) && string.IsNullOrWhiteSpace(type))
            {
                continue;
            }

            nodes.Add(new PackageWebPreviewSceneNodeHint(name, type, parent, scriptPath, texturePath));
            if (nodes.Count >= MaxSceneGraphNodeHints)
            {
                break;
            }
        }

        var root = nodes.FirstOrDefault();
        var scriptPaths = nodes
            .Select(node => node.ScriptPath)
            .Where(path => !string.IsNullOrWhiteSpace(path))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .Take(16)
            .ToArray();
        var texturePaths = nodes
            .Select(node => node.TexturePath)
            .Where(path => !string.IsNullOrWhiteSpace(path))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .Take(16)
            .ToArray();
        var physicsNodeTypes = nodes
            .Select(node => node.Type)
            .Where(IsPhysicsNodeType)
            .Distinct(StringComparer.Ordinal)
            .Take(16)
            .ToArray();

        return new PackageWebPreviewSceneGraphHint(
            path,
            root?.Name ?? "",
            root?.Type ?? "",
            nodes,
            scriptPaths,
            texturePaths,
            physicsNodeTypes);
    }

    private static IReadOnlyDictionary<string, string> ParseTscnExtResources(string text)
    {
        var resources = new Dictionary<string, string>(StringComparer.Ordinal);
        foreach (Match match in Regex.Matches(text, @"(?m)^\[ext_resource\s+(?<attrs>[^\]]+)\]"))
        {
            var attrs = ParseTscnAttributes(match.Groups["attrs"].Value);
            if (attrs.TryGetValue("id", out var id) &&
                attrs.TryGetValue("path", out var path) &&
                !string.IsNullOrWhiteSpace(id) &&
                !string.IsNullOrWhiteSpace(path))
            {
                resources[id] = path;
            }
        }

        return resources;
    }

    private static IReadOnlyDictionary<string, string> ParseTscnAttributes(string attrs)
    {
        var values = new Dictionary<string, string>(StringComparer.Ordinal);
        foreach (Match match in Regex.Matches(attrs, @"(?<key>[A-Za-z_][A-Za-z0-9_]*)=(?:""(?<quoted>[^""]*)""|(?<bare>[^\s]+))"))
        {
            values[match.Groups["key"].Value] = match.Groups["quoted"].Success
                ? match.Groups["quoted"].Value
                : match.Groups["bare"].Value;
        }

        return values;
    }

    private static string ResolveTscnResourcePath(
        string nodeBody,
        string propertyName,
        IReadOnlyDictionary<string, string> extResources)
    {
        var pattern = @"(?m)^\s*" + Regex.Escape(propertyName) + @"\s*=\s*ExtResource\(\s*(?:""(?<quoted>[^""]+)""|(?<bare>[^)\s]+))\s*\)";
        var match = Regex.Match(nodeBody, pattern);
        if (!match.Success)
        {
            return "";
        }

        var id = match.Groups["quoted"].Success ? match.Groups["quoted"].Value : match.Groups["bare"].Value;
        return extResources.TryGetValue(id, out var path) ? path : "";
    }

    private static bool IsPhysicsNodeType(string nodeType)
    {
        return nodeType is "Area2D" or "CollisionShape2D" or "CollisionPolygon2D" or "KinematicBody2D" or
            "CharacterBody2D" or "RigidBody2D" or "StaticBody2D" or "RayCast2D";
    }

    private static void AddRoleIf(string text, List<string> roles, string role, params string[] needles)
    {
        if (needles.Any(needle => text.Contains(needle, StringComparison.OrdinalIgnoreCase)))
        {
            roles.Add(role);
        }
    }

    private static IReadOnlyList<string> ExtractScriptExcerpt(string text)
    {
        var lines = text.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries)
            .Select(line => line.Trim())
            .Where(line => line.Length > 0)
            .Where(line => ContainsAny(line.ToLowerInvariant(), "input", "physics_process", "move_and", "velocity", "attack", "damage", "interact", "sprite", "animation", "camera"))
            .Select(line => TrimForManifest(line, 180))
            .Distinct(StringComparer.Ordinal)
            .Take(10)
            .ToArray();
        return lines;
    }

    private static string TrimForManifest(string value, int maxChars)
    {
        return value.Length <= maxChars ? value : value[..maxChars] + "...";
    }

    private static void CopyPreviewVisualAssets(PackageInfo packageInfo, string targetDirectory)
    {
        var hints = packageInfo.WebPreviewManifest.VisualAssetHints;
        if (hints.Count == 0 || !File.Exists(packageInfo.PackagePath))
        {
            return;
        }

        Directory.CreateDirectory(targetDirectory);
        var fullTargetDirectory = Path.GetFullPath(targetDirectory);
        using var archive = ZipFile.OpenRead(packageInfo.PackagePath);
        foreach (var hint in hints)
        {
            var entry = archive.GetEntry(hint.SourcePath);
            if (entry is null || entry.Length <= 0 || entry.Length > MaxPreviewCopiedAssetBytes)
            {
                continue;
            }

            var targetPath = Path.Combine(targetDirectory, SanitizePreviewAssetName(hint.SourcePath));
            var fullTargetPath = Path.GetFullPath(targetPath);
            if (!WorkspacePathPolicy.IsUnderRoot(fullTargetDirectory, fullTargetPath))
            {
                continue;
            }

            entry.ExtractToFile(fullTargetPath, overwrite: true);
        }
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
include_filter="preview-package-data.json,web-preview-manifest.json,Fonts/*.ttf,Fonts/*.tres,PreviewAssets/*.png,PreviewAssets/*.jpg,PreviewAssets/*.jpeg,PreviewAssets/*.webp,PreviewAssets/*.svg"
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

    private static string RenderMainScene(string nodeName, string nodeType = "Spatial")
    {
        var safeNodeName = EscapeGodotString(string.IsNullOrWhiteSpace(nodeName) ? "WebPreview" : nodeName);
        return $$"""
[gd_scene load_steps=2 format=2]

[ext_resource path="res://Main.gd" type="Script" id=1]

[node name="{{safeNodeName}}" type="{{nodeType}}"]
script = ExtResource( 1 )
""";
    }

    private static string SelectMainSceneNodeType(string mainScript)
    {
        using var reader = new StringReader(mainScript);
        while (reader.ReadLine() is { } line)
        {
            var trimmed = line.Trim();
            if (!trimmed.StartsWith("extends ", StringComparison.Ordinal))
            {
                continue;
            }

            var nodeType = trimmed["extends ".Length..].Trim().Split([' ', '\t'], StringSplitOptions.RemoveEmptyEntries).FirstOrDefault();
            return nodeType switch
            {
                "Control" => "Control",
                "Spatial" => "Spatial",
                "Node2D" => "Node2D",
                "KinematicBody2D" => "KinematicBody2D",
                "Area2D" => "Area2D",
                "RigidBody2D" => "RigidBody2D",
                "StaticBody2D" => "StaticBody2D",
                "Node" => "Node",
                _ => "Spatial"
            };
        }

        return "Spatial";
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
    pressure_timer = 0

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
    if enemies_remaining() > 0 and dodged:
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
    tick_cooldowns("")
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
var pressure_bodies = []
var action_bodies = []
var reward_bodies = []
var selected_marker = 0
var semantic_adapter = {}
var semantic_entities = []
var runtime_tuning = {}
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
var preview_hp = 3
var last_action = "准备试玩"
var world_min_x = -6.8
var world_max_x = 6.8
var world_min_z = -5.3
var world_max_z = 5.3

func _ready():
    load_package_data()
    create_ui()
    render_all()
    create_world()
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
    semantic_adapter = package_data.get("semantic_adapter", {})
    if typeof(semantic_adapter) == TYPE_DICTIONARY:
        semantic_entities = semantic_adapter.get("entities", [])
        runtime_tuning = semantic_adapter.get("runtime_tuning", {})
    if typeof(semantic_entities) != TYPE_ARRAY:
        semantic_entities = []
    if typeof(runtime_tuning) != TYPE_DICTIONARY:
        runtime_tuning = {}
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
    configure_world_bounds()

    var camera = Camera.new()
    camera.name = "Camera"
    camera.current = true
    camera.fov = 58
    camera.translation = Vector3(world_center_x(), max(8.2, world_span_z() * 0.72), world_max_z + max(6.5, world_span_z() * 0.55))
    camera.rotation_degrees = Vector3(-42, 0, 0)
    add_child(camera)

    var floor_body = StaticBody.new()
    floor_body.name = "PackagePreviewFloor"
    add_child(floor_body)
    var floor_size = Vector3(max(15.0, world_span_x() + 4.0), 0.25, max(12.0, world_span_z() + 4.0))
    var floor_center = Vector3(world_center_x(), -0.125, world_center_z())
    floor_body.add_child(mesh_instance(cube_mesh(floor_size), Color(0.16, 0.17, 0.20), floor_center))
    floor_body.add_child(collision_box(Vector3(floor_size.x, 0.35, floor_size.z), floor_center))

    player = KinematicBody.new()
    player.name = "PreviewPlayer"
    player.translation = semantic_player_position(Vector3(0, 0.85, 4.2))
    player.set_meta("movement_speed", tuning_number("movement_speed", 5.2))
    add_child(player)
    player.add_child(capsule_actor(Color(0.36, 0.72, 0.95), 0.34, 1.45))
    player.add_child(collision_capsule(0.34, 1.45))

    var playable_entities = playable_semantic_entities()
    var marker_count = max(1, min(12, playable_entities.size() if playable_entities.size() > 0 else scenes.size()))
    for i in range(marker_count):
        var entity = playable_entities[i] if playable_entities.size() > i and typeof(playable_entities[i]) == TYPE_DICTIONARY else {}
        var role = str(entity.get("role", "scene_marker"))
        var marker = KinematicBody.new() if role == "pressure_source" else StaticBody.new()
        marker.name = "SceneMarker%d" % [i + 1]
        var angle = PI * 2.0 * float(i) / float(marker_count)
        marker.translation = entity_position(entity, Vector3(cos(angle) * 4.2, 0.55, sin(angle) * 3.2 - 0.7))
        marker.set_meta("role", role)
        marker.set_meta("label", str(entity.get("label", selected_scene_text_for_index(i))))
        marker.set_meta("done", false)
        marker.set_meta("pressure_speed", entity_number(entity, "pressure_speed", tuning_number("pressure_speed", 1.35)))
        marker.set_meta("contact_range", entity_number(entity, "contact_range", tuning_number("contact_range", 1.15)))
        marker.set_meta("attack_range", entity_number(entity, "attack_range", tuning_number("attack_range", 3.2)))
        add_child(marker)
        marker.add_child(mesh_instance(cube_mesh(Vector3(0.85, 0.85, 0.85)), marker_color_for_role(role, i), Vector3()))
        marker.add_child(collision_box(Vector3(0.9, 0.9, 0.9), Vector3()))
        marker_bodies.append(marker)
        if role == "pressure_source":
            pressure_bodies.append(marker)
        elif role == "action":
            action_bodies.append(marker)
        elif role == "reward":
            reward_bodies.append(marker)

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
    buttons.attack = add_button(root, "AttackButton", "攻击", Rect2(396, 44, 110, 42), "_on_attack_pressed")
    buttons.skill = add_button(root, "SkillButton", "技能/闪避", Rect2(522, 44, 140, 42), "_on_skill_pressed")
    buttons.reward = add_button(root, "RewardButton", "选择奖励", Rect2(678, 44, 140, 42), "_on_reward_pressed")
    buttons.retry = add_button(root, "RetryButton", "重试", Rect2(834, 44, 110, 42), "_on_retry_semantic_pressed")
    labels.header = add_label(root, Rect2(44, 110, 900, 30), "")
    labels.summary = add_label(root, Rect2(44, 150, 1040, 28), "")
    labels.main_scene = add_label(root, Rect2(44, 184, 1160, 28), "")
    labels.scene = add_label(root, Rect2(44, 230, 1180, 28), "")
    labels.capabilities = add_label(root, Rect2(44, 264, 1180, 28), "")
    labels.package = add_label(root, Rect2(44, 298, 1180, 28), "")
    labels.coverage = add_label(root, Rect2(44, 344, 1200, 54), "")
    labels.controls = add_label(root, Rect2(44, 820, 1100, 28), "WASD移动  F/鼠标左键攻击  Q技能/闪避  E选择奖励  R重试  数字键选择节点")

func _physics_process(delta):
    pulse += delta
    apply_player_motion(delta)
    animate_markers()
    tick_semantic_pressure(delta)

func _input(event):
    if event is InputEventMouseButton and event.pressed and event.button_index == BUTTON_LEFT:
        primary_action()
    elif event is InputEventKey and event.pressed and not event.echo:
        if event.scancode == KEY_SPACE:
            primary_action()
        elif event.scancode == KEY_F:
            semantic_primary_action()
        elif event.scancode == KEY_Q:
            semantic_skill_action()
        elif event.scancode == KEY_E:
            semantic_reward_action()
        elif event.scancode == KEY_R:
            semantic_retry()
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
    player.move_and_slide(dir * float(player.get_meta("movement_speed")), Vector3.UP)
    player.translation.x = clamp(player.translation.x, world_min_x, world_max_x)
    player.translation.z = clamp(player.translation.z, world_min_z, world_max_z)

func animate_markers():
    for i in range(marker_bodies.size()):
        var marker = marker_bodies[i]
        if marker.get_meta("done"):
            continue
        var base_y = 0.55
        marker.translation.y = base_y + (0.22 if i == selected_marker else 0.06) * sin(pulse * 3.0 + i)
        marker.scale = Vector3(1.25, 1.25, 1.25) if i == selected_marker else Vector3(1, 1, 1)

func tick_semantic_pressure(delta):
    if player == null or pressure_bodies.size() == 0:
        return
    for pressure in pressure_bodies:
        if pressure.get_meta("done"):
            continue
        var direction = player.translation - pressure.translation
        direction.y = 0
        if direction.length() > 0.1:
            pressure.move_and_slide(direction.normalized() * float(pressure.get_meta("pressure_speed")), Vector3.UP)
        if pressure.translation.distance_to(player.translation) < float(pressure.get_meta("contact_range")):
            preview_hp = max(1, preview_hp - 1)
            encounter_hp = min(encounter_max_hp, encounter_hp + 1)
            last_action = "%s 逼近，生命降至 %d" % [pressure.get_meta("label"), preview_hp]
            render_all()

func advance_marker():
    if marker_bodies.size() == 0:
        return
    selected_marker = (selected_marker + 1) % marker_bodies.size()
    render_all()

func primary_action():
    action_count += 1
    if semantic_entities.size() > 0 and adapter_style == "generic":
        semantic_primary_action()
        return
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

func semantic_primary_action():
    action_count += 1
    var target = closest_active_body(pressure_bodies)
    if target == null:
        target = closest_active_body(action_bodies)
    if target == null:
        last_action = "攻击挥空，未发现压力源"
        render_all()
        return
    selected_marker = max(0, marker_bodies.find(target))
    if target.translation.distance_to(player.translation) <= semantic_attack_range() or action_bodies.has(target):
        target.set_meta("done", true)
        target.visible = false
        encounter_hp = max(0, encounter_hp - 7)
        last_action = "攻击命中 %s，压力下降" % [target.get_meta("label")]
    else:
        last_action = "%s 距离过远，靠近后再攻击" % [target.get_meta("label")]
    render_all()

func semantic_skill_action():
    action_count += 1
    energy = max(0, energy - 1)
    var handled = 0
    var candidates = []
    for item in pressure_bodies:
        if not item.get_meta("done"):
            candidates.append(item)
    for item in action_bodies:
        if not item.get_meta("done"):
            candidates.append(item)
    candidates.sort_custom(self, "_sort_body_distance_to_player")
    var skill_targets = int(tuning_number("skill_targets", 2))
    for item in candidates:
        if handled >= skill_targets:
            break
        item.set_meta("done", true)
        item.visible = false
        handled += 1
    encounter_hp = max(0, encounter_hp - handled * 5)
    last_action = "技能/闪避处理 %d 个压力节点，能量 %d/3" % [handled, energy]
    render_all()

func semantic_reward_action():
    action_count += 1
    var reward = closest_active_body(reward_bodies)
    if reward == null:
        last_action = "没有可领取的奖励"
        render_all()
        return
    reward.set_meta("done", true)
    reward.visible = false
    tower_count += 1
    wave += 1
    energy = 3
    encounter_hp = encounter_max_hp + wave * 4
    last_action = "选择奖励 %s，进入波次 %d" % [reward.get_meta("label"), wave]
    render_all()

func semantic_retry():
    for body in marker_bodies:
        body.set_meta("done", false)
        body.visible = true
    preview_hp = 3
    energy = 3
    wave = 1
    encounter_hp = encounter_max_hp
    selected_marker = 0
    last_action = "重试：生命、能量和压力已重置"
    render_all()

func closest_active_body(values):
    var best = null
    var best_distance = 99999.0
    for body in values:
        if body.get_meta("done"):
            continue
        var distance = body.translation.distance_to(player.translation)
        if distance < best_distance:
            best = body
            best_distance = distance
    return best

func _sort_body_distance_to_player(a, b):
    return a.translation.distance_to(player.translation) < b.translation.distance_to(player.translation)

func render_all():
    labels.header.text = "%s 浏览器试玩预览" % [game_name]
    labels.summary.text = "项目 %s  类型 %s  文本键 %d  场景 %d" % [empty_text(project_name), empty_text(game_type_source), text_key_count, scenes.size()]
    labels.main_scene.text = "主场景：%s" % [empty_text(main_scene)]
    labels.scene.text = "当前包内场景：%s" % [selected_scene_text()]
    labels.capabilities.text = "转换能力：%s" % [join_first(capabilities, 8)]
    labels.package.text = "文件包：%s  SHA256：%s" % [empty_text(package_file), short_sha(package_sha256)]
    labels.coverage.text = "%s\n%s" % [converter_coverage, adapter_status_text()]

func adapter_status_text():
    if semantic_entities.size() > 0:
        return "语义物理试玩：生命 %d/3  能量 %d/3  波次 %d  压力节点 %d  最近动作：%s" % [preview_hp, energy, wave, pressure_bodies.size(), last_action]
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

func playable_semantic_entities():
    var result = []
    for entity in semantic_entities:
        if typeof(entity) != TYPE_DICTIONARY:
            continue
        var role = str(entity.get("role", ""))
        if role == "player_start" or role == "feedback" or role == "play_space" or role == "ui_action":
            continue
        if is_pressure_container_entity(entity):
            continue
        result.append(entity)
    if result.size() == 0:
        for entity in semantic_entities:
            if typeof(entity) == TYPE_DICTIONARY and str(entity.get("role", "")) != "player_start":
                result.append(entity)
    return result

func is_pressure_container_entity(entity):
    if str(entity.get("role", "")) != "pressure_source":
        return false
    var node_type = str(entity.get("node_type", "")).to_lower()
    if node_type.find("body") >= 0 or node_type.find("area") >= 0:
        return false
    var node_path = str(entity.get("node_path", ""))
    if node_path == "":
        return false
    for other in semantic_entities:
        if typeof(other) != TYPE_DICTIONARY or other == entity:
            continue
        if str(other.get("role", "")) != "pressure_source":
            continue
        var other_path = str(other.get("node_path", ""))
        if other_path.begins_with(node_path + "/"):
            return true
    return false

func configure_world_bounds():
    var found = false
    var min_x = 0.0
    var max_x = 0.0
    var min_z = 0.0
    var max_z = 0.0
    for entity in semantic_entities:
        if typeof(entity) != TYPE_DICTIONARY:
            continue
        var role = str(entity.get("role", ""))
        if role == "feedback" or role == "ui_action":
            continue
        if not entity_has_position(entity):
            continue
        var pos = entity_position(entity, Vector3())
        if not found:
            min_x = pos.x
            max_x = pos.x
            min_z = pos.z
            max_z = pos.z
            found = true
        else:
            min_x = min(min_x, pos.x)
            max_x = max(max_x, pos.x)
            min_z = min(min_z, pos.z)
            max_z = max(max_z, pos.z)
    if found:
        world_min_x = min(world_min_x, min_x - 2.0)
        world_max_x = max(world_max_x, max_x + 2.0)
        world_min_z = min(world_min_z, min_z - 2.0)
        world_max_z = max(world_max_z, max_z + 2.0)

func entity_has_position(entity):
    if typeof(entity) != TYPE_DICTIONARY:
        return false
    var world_position = entity.get("world_position", {})
    if typeof(world_position) == TYPE_DICTIONARY and world_position.has("x") and world_position.has("z"):
        return true
    var local_position = entity.get("local_position", {})
    return typeof(local_position) == TYPE_DICTIONARY and local_position.has("x") and local_position.has("z")

func world_center_x():
    return (world_min_x + world_max_x) * 0.5

func world_center_z():
    return (world_min_z + world_max_z) * 0.5

func world_span_x():
    return max(1.0, world_max_x - world_min_x)

func world_span_z():
    return max(1.0, world_max_z - world_min_z)

func semantic_player_position(fallback):
    for entity in semantic_entities:
        if typeof(entity) == TYPE_DICTIONARY and str(entity.get("role", "")) == "player_start":
            return entity_position(entity, fallback)
    return fallback

func entity_position(entity, fallback):
    var world_position = entity.get("world_position", {})
    if typeof(world_position) == TYPE_DICTIONARY:
        return vector_from_dictionary(world_position, fallback)
    var local_position = entity.get("local_position", {})
    if typeof(local_position) == TYPE_DICTIONARY:
        return vector_from_dictionary(local_position, fallback)
    return fallback

func vector_from_dictionary(value, fallback):
    if typeof(value) != TYPE_DICTIONARY:
        return fallback
    if not value.has("x") or not value.has("z"):
        return fallback
    return Vector3(float(value.get("x", fallback.x)), float(value.get("y", fallback.y)), float(value.get("z", fallback.z)))

func tuning_number(key, fallback):
    if typeof(runtime_tuning) == TYPE_DICTIONARY and runtime_tuning.has(key):
        return float(runtime_tuning.get(key, fallback))
    return fallback

func entity_number(entity, key, fallback):
    if typeof(entity) != TYPE_DICTIONARY:
        return fallback
    var runtime_profile = entity.get("runtime_profile", {})
    if typeof(runtime_profile) == TYPE_DICTIONARY and runtime_profile.has(key):
        return float(runtime_profile.get(key, fallback))
    var movement_profile = entity.get("movement_profile", {})
    if typeof(movement_profile) == TYPE_DICTIONARY and movement_profile.has(key):
        return float(movement_profile.get(key, fallback))
    if entity.has(key):
        return float(entity.get(key, fallback))
    return fallback

func semantic_attack_range():
    var value = tuning_number("attack_range", 3.2)
    for action in action_bodies:
        value = max(value, float(action.get_meta("attack_range")))
    return value

func selected_scene_text():
    if scenes.size() == 0:
        return "未在文件包中发现 .tscn 场景"
    var index = int(clamp(selected_marker, 0, scenes.size() - 1))
    return str(scenes[index])

func selected_scene_text_for_index(index):
    if scenes.size() == 0:
        return "Entity %d" % [index + 1]
    return str(scenes[int(clamp(index, 0, scenes.size() - 1))])

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

func _on_attack_pressed():
    semantic_primary_action()

func _on_skill_pressed():
    semantic_skill_action()

func _on_reward_pressed():
    semantic_reward_action()

func _on_retry_semantic_pressed():
    semantic_retry()

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

func marker_color_for_role(role, index):
    if role == "pressure_source":
        return Color(0.88, 0.22, 0.22)
    if role == "action":
        return Color(0.55, 0.35, 0.95)
    if role == "reward":
        return Color(0.12, 0.72, 0.42)
    if role == "ui_action":
        return Color(0.10, 0.62, 0.58)
    return marker_color(index)

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
        var visualAssetHints = new List<PackageWebPreviewVisualAssetHint>();
        var scriptBehaviorHints = new List<PackageWebPreviewScriptBehaviorHint>();
        var sceneGraphHints = new List<PackageWebPreviewSceneGraphHint>();
        IReadOnlyList<PackageWebPreviewInputMapHint> inputMapHints = [];
        JsonElement? playablePreviewContract = null;

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
            using var stream = projectConfig.Open();
            using var memory = new MemoryStream();
            stream.CopyTo(memory);
            var projectConfigText = Encoding.UTF8.GetString(memory.ToArray());
            using var reader = new StringReader(projectConfigText);
            while (reader.ReadLine() is { } line)
            {
                if (line.StartsWith("run/main_scene=", StringComparison.Ordinal))
                {
                    mainScene = line.Split('=', 2)[1].Trim().Trim('"');
                    break;
                }
            }

            inputMapHints = ExtractInputMapHints(projectConfigText);
        }

        foreach (var entry in archive.Entries.OrderBy(entry => entry.FullName, StringComparer.OrdinalIgnoreCase))
        {
            var normalized = entry.FullName.Replace('\\', '/');
            if (normalized.EndsWith(".tscn", StringComparison.OrdinalIgnoreCase))
            {
                scenes.Add(normalized);
                if (entry.Length > 0 &&
                    entry.Length <= MaxPreviewSceneGraphBytes &&
                    IsPreviewRuntimePath(normalized))
                {
                    sceneGraphHints.Add(BuildSceneGraphHint(normalized, entry));
                }
            }

            if (IsPreviewVisualAsset(normalized) &&
                entry.Length > 0 &&
                entry.Length <= MaxPreviewCopiedAssetBytes &&
                IsPreviewRuntimePath(normalized))
            {
                visualAssetHints.Add(new PackageWebPreviewVisualAssetHint(
                    normalized,
                    $"res://PreviewAssets/{SanitizePreviewAssetName(normalized)}",
                    ClassifyVisualAssetRole(normalized),
                    Path.GetFileName(normalized),
                    entry.Length));
            }

            if (IsPreviewScriptAsset(normalized) &&
                entry.Length > 0 &&
                entry.Length <= MaxPreviewCopiedAssetBytes &&
                IsPreviewRuntimeScriptPath(normalized))
            {
                scriptBehaviorHints.Add(BuildScriptBehaviorHint(normalized, entry));
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

        var playablePreviewContractEntry = archive.GetEntry(PlayablePreviewContractFileName);
        if (playablePreviewContractEntry is not null)
        {
            if (playablePreviewContractEntry.Length > MaxPlayablePreviewContractBytes)
            {
                throw new InvalidOperationException("Package playable preview contract exceeds the web preview scan budget.");
            }

            try
            {
                using var document = JsonDocument.Parse(playablePreviewContractEntry.Open());
                playablePreviewContract = document.RootElement.Clone();
            }
            catch (JsonException)
            {
                playablePreviewContract = null;
            }
        }

        var packageSizeBytes = new FileInfo(packagePath).Length;
        var packageSha256 = ComputeFileSha256(packagePath);
        gameTypeId = FirstNonEmpty(
            ProjectWebPreviewGameTypeCatalog.ResolveGameTypeId(gameTypeId, gameTypeGuide, gameTypeSource, gameName, projectName),
            ProjectWebPreviewGameTypeCatalog.NormalizeGameTypeToken(gameTypeId));
        var catalogGameTypeGuide = ProjectWebPreviewGameTypeCatalog.ResolveGameTypeGuide(gameTypeId);
        gameTypeGuide = FirstNonEmpty(catalogGameTypeGuide, gameTypeGuide);
        var hasSupportedTowerdemo2Template = HasSupportedTowerdemo2Template(
            isTowerdemo2,
            towerdemo2SourceSceneSha256,
            towerdemo2TextCatalogSha256);
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
            visualAssetHints
                .OrderByDescending(item => ScorePathRelevance(item.SourcePath, projectName, gameName, mainScene))
                .ThenByDescending(item => ScoreVisualRole(item.Role))
                .ThenBy(item => item.SourcePath, StringComparer.OrdinalIgnoreCase)
                .Take(MaxVisualAssetHints)
                .ToArray(),
            inputMapHints,
            scriptBehaviorHints
                .OrderByDescending(item => ScorePathRelevance(item.Path, projectName, gameName, mainScene))
                .ThenByDescending(item => item.Roles.Count)
                .ThenBy(item => item.Path, StringComparer.OrdinalIgnoreCase)
                .Take(MaxScriptBehaviorHints)
                .ToArray(),
            sceneGraphHints
                .OrderByDescending(item => ScorePathRelevance(item.Path, projectName, gameName, mainScene))
                .ThenByDescending(item => item.PhysicsNodeTypes.Count)
                .ThenByDescending(item => item.ScriptPaths.Count)
                .ThenBy(item => item.Path, StringComparer.OrdinalIgnoreCase)
                .Take(MaxSceneGraphHints)
                .ToArray(),
            texts.Count,
            hasSupportedTowerdemo2Template,
            playablePreviewContract.HasValue);

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
            packagePath,
            isTowerdemo2,
            towerdemo2SourceSceneSha256,
            towerdemo2TextCatalogSha256,
            packageSizeBytes,
            packageSha256,
            playablePreviewContract,
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
        IReadOnlyList<PackageWebPreviewVisualAssetHint> visualAssetHints,
        IReadOnlyList<PackageWebPreviewInputMapHint> inputMapHints,
        IReadOnlyList<PackageWebPreviewScriptBehaviorHint> scriptBehaviorHints,
        IReadOnlyList<PackageWebPreviewSceneGraphHint> sceneGraphHints,
        int textKeyCount,
        bool isTowerdemo2,
        bool hasPlayablePreviewContract)
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

        if (hasPlayablePreviewContract)
        {
            detectedCapabilities.Add("playable_preview_contract");
        }

        if (visualAssetHints.Count > 0)
        {
            detectedCapabilities.Add("visual_asset_hints");
        }

        if (inputMapHints.Count > 0)
        {
            detectedCapabilities.Add("input_map_hints");
        }

        if (scriptBehaviorHints.Count > 0)
        {
            detectedCapabilities.Add("script_behavior_hints");
        }

        if (sceneGraphHints.Count > 0)
        {
            detectedCapabilities.Add("scene_graph_hints");
        }

        var contract = BuildWebPreviewContract(isTowerdemo2 ? Towerdemo2Converter : GenericGodotPackageConverter, mainScene, scenes, textKeyCount, hasPlayablePreviewContract);

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
            visualAssetHints,
            inputMapHints,
            scriptBehaviorHints,
            sceneGraphHints,
            textKeyCount,
            detectedTemplates.Order(StringComparer.Ordinal).ToArray(),
            detectedCapabilities.Distinct(StringComparer.Ordinal).Order(StringComparer.Ordinal).ToArray(),
            contract);
    }

    private static PackageWebPreviewContract BuildWebPreviewContract(
        ProjectWebPreviewConverterDescriptor converter,
        string? mainScene,
        IReadOnlyList<string> scenes,
        int textKeyCount,
        bool hasPlayablePreviewContract)
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

        if (hasPlayablePreviewContract)
        {
            dataSources.Add(PlayablePreviewContractFileName);
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
                !IsPreviewFingerprintCompatible(converter, sourceSceneSha256, textCatalogSha256, isLegacyPreview))
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

    private static bool IsPreviewFingerprintCompatible(
        ProjectWebPreviewConverterDescriptor converter,
        string sourceSceneSha256,
        string textCatalogSha256,
        bool isLegacyPreview)
    {
        if (!isLegacyPreview &&
            string.Equals(converter.Id, Towerdemo2Converter.Id, StringComparison.Ordinal) &&
            !string.IsNullOrWhiteSpace(sourceSceneSha256) &&
            !string.IsNullOrWhiteSpace(textCatalogSha256))
        {
            return true;
        }

        return string.Equals(sourceSceneSha256, converter.SourceSceneSha256, StringComparison.OrdinalIgnoreCase) &&
            string.Equals(textCatalogSha256, converter.TextCatalogSha256, StringComparison.OrdinalIgnoreCase);
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

        if (!html.Contains("phasea-preview-fallback", StringComparison.Ordinal))
        {
            html = html.Replace(
                "</body>",
                $$$"""
	<div id="phasea-preview-fallback" aria-live="polite">
		<style>
			#phasea-preview-fallback{display:none;position:fixed;inset:0;z-index:10000;background:#0b1020;color:#f8fafc;font-family:'Microsoft YaHei','Segoe UI',sans-serif}
			#phasea-preview-fallback *{box-sizing:border-box}
			#phasea-preview-fallback .phasea-shell{min-height:100vh;display:grid;grid-template-columns:minmax(0,1fr) 320px;background:radial-gradient(circle at 30% 20%,rgba(57,120,255,.22),transparent 28%),linear-gradient(145deg,#101827,#0b1020 58%,#152018)}
			#phasea-preview-fallback .phasea-stage{position:relative;min-height:100vh;overflow:hidden;border-right:1px solid rgba(255,255,255,.12)}
			#phasea-preview-fallback .phasea-grid{position:absolute;inset:0;background-image:linear-gradient(rgba(255,255,255,.07) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.07) 1px,transparent 1px);background-size:64px 64px;opacity:.36}
			#phasea-preview-fallback .phasea-node{position:absolute;width:40px;height:40px;border-radius:50%;border:2px solid #93c5fd;background:#1d4ed8;color:white;cursor:pointer;transform:translate(-50%,-50%);box-shadow:0 0 24px rgba(96,165,250,.38)}
			#phasea-preview-fallback .phasea-node.role-pressure_source{background:#b91c1c;border-color:#fecaca;box-shadow:0 0 24px rgba(248,113,113,.48)}
			#phasea-preview-fallback .phasea-node.role-action{background:#7c3aed;border-color:#ddd6fe;box-shadow:0 0 24px rgba(167,139,250,.46)}
			#phasea-preview-fallback .phasea-node.role-reward{background:#047857;border-color:#a7f3d0;box-shadow:0 0 24px rgba(52,211,153,.46)}
			#phasea-preview-fallback .phasea-node.role-ui_action{background:#0f766e;border-color:#99f6e4}
			#phasea-preview-fallback .phasea-node.active{border-color:#fbbf24;background:#b45309;box-shadow:0 0 28px rgba(251,191,36,.55)}
			#phasea-preview-fallback .phasea-node.done{border-color:#86efac;background:#15803d}
			#phasea-preview-fallback .phasea-player{position:absolute;width:34px;height:34px;border-radius:50%;background:#67e8f9;border:3px solid #ecfeff;transform:translate(-50%,-50%);box-shadow:0 0 28px rgba(103,232,249,.9);transition:left .08s linear,top .08s linear}
			#phasea-preview-fallback .phasea-player:after{content:'';position:absolute;left:9px;top:6px;width:10px;height:10px;border-radius:50%;background:#0f172a}
			#phasea-preview-fallback .phasea-hud{position:absolute;left:24px;top:22px;right:24px;display:flex;gap:10px;flex-wrap:wrap;align-items:center}
			#phasea-preview-fallback .phasea-pill{border:1px solid rgba(255,255,255,.15);border-radius:8px;background:rgba(15,23,42,.76);padding:8px 10px;font-size:13px;line-height:1.25}
			#phasea-preview-fallback .phasea-side{padding:20px;background:rgba(15,23,42,.88);display:flex;flex-direction:column;gap:14px;overflow:auto}
			#phasea-preview-fallback h1{margin:0;font-size:20px;line-height:1.25}
			#phasea-preview-fallback p{margin:0;color:#cbd5e1;font-size:13px;line-height:1.55}
			#phasea-preview-fallback .phasea-meter{height:10px;border-radius:8px;background:#1f2937;overflow:hidden;border:1px solid rgba(255,255,255,.12)}
			#phasea-preview-fallback .phasea-meter span{display:block;height:100%;background:#22c55e;width:0}
			#phasea-preview-fallback .phasea-action-list{display:grid;grid-template-columns:1fr 1fr;gap:8px}
			#phasea-preview-fallback .phasea-action-list:empty{display:none}
			#phasea-preview-fallback .phasea-actions{display:grid;grid-template-columns:1fr 1fr;gap:8px}
			#phasea-preview-fallback button.phasea-btn{height:38px;border:1px solid rgba(255,255,255,.18);border-radius:8px;background:#2563eb;color:white;cursor:pointer;font-size:13px}
			#phasea-preview-fallback button.phasea-btn.secondary{background:rgba(255,255,255,.06)}
			#phasea-preview-fallback .phasea-pad{display:grid;grid-template-columns:repeat(3,44px);grid-template-rows:repeat(3,40px);gap:6px;align-self:center}
			#phasea-preview-fallback .phasea-pad button{border-radius:8px;border:1px solid rgba(255,255,255,.18);background:rgba(255,255,255,.08);color:white;cursor:pointer}
			#phasea-preview-fallback .phasea-log{min-height:88px;border:1px solid rgba(255,255,255,.12);border-radius:8px;background:rgba(2,6,23,.55);padding:10px;color:#dbeafe;font-size:12px;line-height:1.5}
			#phasea-preview-fallback.minimized{inset:auto 18px 18px auto;width:270px;height:auto;border:1px solid rgba(255,255,255,.2);border-radius:8px;overflow:hidden}
			#phasea-preview-fallback.minimized .phasea-stage,#phasea-preview-fallback.minimized .phasea-meter,#phasea-preview-fallback.minimized .phasea-pad,#phasea-preview-fallback.minimized .phasea-log,#phasea-preview-fallback.minimized .phasea-actions .secondary{display:none}
			#phasea-preview-fallback.minimized .phasea-shell{min-height:auto;display:block}
			#phasea-preview-fallback.minimized .phasea-side{padding:14px}
			@media (max-width: 820px){#phasea-preview-fallback .phasea-shell{grid-template-columns:1fr;grid-template-rows:minmax(360px,58vh) auto}#phasea-preview-fallback .phasea-stage{min-height:360px;border-right:0;border-bottom:1px solid rgba(255,255,255,.12)}}
		</style>
		<div class="phasea-shell">
			<div id="phasea-preview-stage" class="phasea-stage">
				<div class="phasea-grid"></div>
				<div class="phasea-hud">
					<div id="phasea-preview-title" class="phasea-pill">通用浏览器试玩</div>
					<div id="phasea-preview-objective" class="phasea-pill">读取包数据中...</div>
					<div id="phasea-preview-stats" class="phasea-pill">进度 0%</div>
				</div>
			</div>
			<aside class="phasea-side">
				<h1 id="phasea-preview-name">通用浏览器试玩</h1>
				<p id="phasea-preview-summary">正在读取文件包信息...</p>
				<div class="phasea-meter"><span id="phasea-preview-meter"></span></div>
				<div id="phasea-preview-action-list" class="phasea-action-list"></div>
				<div class="phasea-actions">
					<button id="phasea-preview-interact" class="phasea-btn">互动</button>
					<button id="phasea-preview-next" class="phasea-btn secondary">下一个场景</button>
					<button id="phasea-preview-reset" class="phasea-btn secondary">重置</button>
					<button id="phasea-preview-minimize" class="phasea-btn secondary">缩小</button>
				</div>
				<div class="phasea-pad" aria-label="Movement controls">
					<span></span><button data-phasea-move="0,-1">W</button><span></span>
					<button data-phasea-move="-1,0">A</button><button data-phasea-action="interact">●</button><button data-phasea-move="1,0">D</button>
					<span></span><button data-phasea-move="0,1">S</button><span></span>
				</div>
				<p>WASD 移动，鼠标点击地面移动，空格/互动键检查最近场景节点。数字 1/2/3 可快速选择包内场景。</p>
				<div id="phasea-preview-log" class="phasea-log">等待包数据...</div>
			</aside>
		</div>
	</div>
	<script>
	(function () {
		const version = "{{{assetVersion}}}";
		const panel = document.getElementById("phasea-preview-fallback");
		const stage = document.getElementById("phasea-preview-stage");
		const title = document.getElementById("phasea-preview-title");
		const name = document.getElementById("phasea-preview-name");
		const summary = document.getElementById("phasea-preview-summary");
		const objective = document.getElementById("phasea-preview-objective");
		const stats = document.getElementById("phasea-preview-stats");
		const meter = document.getElementById("phasea-preview-meter");
		const log = document.getElementById("phasea-preview-log");
		const actionList = document.getElementById("phasea-preview-action-list");
		const interactButton = document.getElementById("phasea-preview-interact");
		const nextButton = document.getElementById("phasea-preview-next");
		const resetButton = document.getElementById("phasea-preview-reset");
		const minimizeButton = document.getElementById("phasea-preview-minimize");
		let scenes = [];
		let nodes = [];
		let selected = 0;
		let dataLoaded = null;
		let previewContract = null;
		let previewSemanticAdapter = null;
		let roleInteractions = {};
		let stateBounds = {};
		let player = { x: 50, y: 64 };
		let progress = 0;
		let energy = 3;
		let actions = 0;
		let phase = 1;
		let runState = { score: 0, pressure: 0, rewards: 0, hp: 3 };
		let semanticActions = [];
		let lastAction = "inspect";
		let started = false;
		let wave = 1;
		let lastPressureTick = 0;
		let message = "移动到发光节点并互动，验证这个包的可试玩路径。";
		function esc(value) {
			return String(value || "").replace(/[&<>"']/g, function (ch) {
				return {"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[ch];
			});
		}
		function clamp(value, min, max) {
			return Math.max(min, Math.min(max, value));
		}
		function distanceToPlayer(node) {
			const dx = node.x - player.x;
			const dy = node.y - player.y;
			return Math.sqrt(dx * dx + dy * dy);
		}
		function sceneLabel(path, index) {
			const raw = String(path || "Scene " + (index + 1));
			const file = raw.split("/").pop() || raw;
			return file.replace(/\.tscn$/i, "") || ("Scene " + (index + 1));
		}
		function makeNodes() {
			const adapterEntities = previewSemanticAdapter && Array.isArray(previewSemanticAdapter.entities) ? previewSemanticAdapter.entities : [];
			const contractEntities = previewContract && Array.isArray(previewContract.entities) ? previewContract.entities : [];
			const sourceEntities = adapterEntities.length ? adapterEntities : contractEntities;
			const source = sourceEntities.length
				? sourceEntities.slice(0, 12)
				: (scenes.length ? scenes.slice(0, 8) : ["Package Root", "Main Scene", "Interaction Loop"]);
			nodes = source.map(function (item, index) {
				const scene = typeof item === "string" ? item : (item.scene || item.path || item.id || ("Scene " + (index + 1)));
				const angle = (Math.PI * 2 * index / source.length) - Math.PI / 2;
				const ring = index % 2 === 0 ? 31 : 22;
				return {
					scene: scene,
					label: typeof item === "string" ? sceneLabel(scene, index) : (item.label || sceneLabel(scene, index)),
					role: typeof item === "string" ? "scene_marker" : (item.role || "contract_entity"),
					objective: typeof item === "string" ? "Inspect this package scene." : (item.objective || "Inspect this contract entity."),
					x: typeof item === "string" ? clamp(50 + Math.cos(angle) * ring, 12, 88) : clamp(Number(item.x || (50 + Math.cos(angle) * ring)), 12, 88),
					y: typeof item === "string" ? clamp(50 + Math.sin(angle) * ring, 18, 82) : clamp(Number(item.y || (50 + Math.sin(angle) * ring)), 18, 82),
					done: false
				};
			});
		}
		function formatActionLabel(action) {
			const value = String(action || "");
			if (value === "basic_attack") return "攻击";
			if (value === "skill_or_roll") return "技能/闪避";
			if (value === "choice") return "选择奖励";
			if (value === "start") return "开始";
			if (value === "retry") return "重试";
			if (value === "interact") return "互动";
			if (value === "select_scene") return "选择场景";
			return value.replace(/_/g, " ") || "动作";
		}
		function initializeSemanticActions(adapter, contract) {
			actionList.innerHTML = "";
			const adapterActions = adapter && Array.isArray(adapter.input_actions) ? adapter.input_actions : [];
			const contractActions = contract && Array.isArray(contract.input_actions) ? contract.input_actions : [];
			const source = adapterActions.length ? adapterActions : contractActions;
			const seen = {};
			semanticActions = source.filter(function (item) {
				if (!item || !item.action || seen[item.action] || item.action === "move") return false;
				seen[item.action] = true;
				return true;
			}).slice(0, 6);
			semanticActions.forEach(function (item) {
				const button = document.createElement("button");
				button.className = "phasea-btn";
				button.textContent = formatActionLabel(item.action);
				button.title = Array.isArray(item.inputs) ? item.inputs.join(" / ") : item.action;
				button.onclick = function () { semanticAction(item.action); };
				actionList.appendChild(button);
			});
		}
		function findNodeForAction(action) {
			const normalized = String(action || "").toLowerCase();
			const byRole = function (role) { return nodes.find(function (node) { return node.role === role && !node.done; }) || nodes.find(function (node) { return node.role === role; }); };
			const byLabel = function (pattern) { return nodes.find(function (node) { return pattern.test(String(node.label || "")); }); };
			if (normalized === "basic_attack") return byLabel(/attack|weapon|hit|slash|shoot/i) || byRole("action") || byRole("pressure_source");
			if (normalized === "skill_or_roll") return byLabel(/skill|cast|roll|dash|dodge/i) || byRole("action");
			if (normalized === "choice") return byRole("reward") || byLabel(/reward|choice|door|shop|chest/i);
			if (normalized === "start") return byLabel(/start|begin|play/i) || byRole("ui_action") || byRole("entry_scene");
			if (normalized === "retry") return byLabel(/retry|restart/i) || byRole("ui_action");
			if (normalized === "select_scene") return nodes[(selected + 1) % Math.max(1, nodes.length)];
			return byRole("action") || byRole("ui_action") || nodes[selected];
		}
		function findClosestNode(predicate) {
			let best = null;
			let bestDistance = Number.MAX_VALUE;
			nodes.forEach(function (node) {
				if (predicate && !predicate(node)) return;
				const distance = distanceToPlayer(node);
				if (distance < bestDistance) {
					best = node;
					bestDistance = distance;
				}
			});
			return best ? { node: best, distance: bestDistance } : null;
		}
		function initializeContractRules(contract, adapter) {
			roleInteractions = {};
			stateBounds = {};
			const stateModel = adapter && Array.isArray(adapter.state_model) && adapter.state_model.length ? adapter.state_model : (contract && Array.isArray(contract.state_model) ? contract.state_model : []);
			const interactions = adapter && Array.isArray(adapter.role_interactions) && adapter.role_interactions.length ? adapter.role_interactions : (contract && Array.isArray(contract.role_interactions) ? contract.role_interactions : []);
			if (Array.isArray(stateModel)) {
				stateModel.forEach(function (field) {
					if (!field || !field.id) return;
					stateBounds[field.id] = { min: Number(field.min || 0), max: Number(field.max || 999) };
					const initial = Number(field.initial || 0);
					if (field.id === "energy") energy = initial;
					else if (field.id === "phase") phase = initial;
					else runState[field.id] = initial;
				});
			}
			if (Array.isArray(interactions)) {
				interactions.forEach(function (rule) {
					if (rule && rule.role) roleInteractions[rule.role] = rule;
				});
			}
		}
		function nearestNode() {
			if (!nodes.length) return null;
			let best = nodes[0];
			let bestDistance = Number.MAX_VALUE;
			nodes.forEach(function (node, index) {
				const dx = node.x - player.x;
				const dy = node.y - player.y;
				const distance = Math.sqrt(dx * dx + dy * dy);
				if (distance < bestDistance) {
					best = node;
					bestDistance = distance;
					selected = index;
				}
			});
			return { node: best, distance: bestDistance };
		}
		function render() {
			if (!dataLoaded) return;
			document.querySelectorAll("#phasea-preview-fallback .phasea-node,#phasea-preview-fallback .phasea-player").forEach(function (item) { item.remove(); });
			nodes.forEach(function (node, index) {
				const button = document.createElement("button");
				button.className = "phasea-node role-" + String(node.role || "entity").replace(/[^a-z0-9_-]/gi, "_") + (index === selected ? " active" : "") + (node.done ? " done" : "");
				button.style.left = node.x + "%";
				button.style.top = node.y + "%";
				button.title = node.scene;
				button.textContent = String(index + 1);
				button.onclick = function () {
					selected = index;
					player.x = clamp(node.x - 5, 8, 92);
					player.y = clamp(node.y + 4, 12, 88);
					message = "已接近 " + node.label + "，点击互动继续。";
					render();
				};
				stage.appendChild(button);
			});
			const avatar = document.createElement("div");
			avatar.className = "phasea-player";
			avatar.style.left = player.x + "%";
			avatar.style.top = player.y + "%";
			stage.appendChild(avatar);
			const doneCount = nodes.filter(function (node) { return node.done; }).length;
			const percent = nodes.length ? Math.round(doneCount / nodes.length * 100) : progress;
			title.textContent = (dataLoaded.game_name || dataLoaded.project_name || "Godot Package") + " · 语义试玩层";
			objective.textContent = doneCount >= nodes.length ? "目标完成：所有场景节点已验证" : "目标：移动并互动 " + doneCount + "/" + nodes.length;
			stats.textContent = "进度 " + percent + "% · 波次 " + wave + " · 动作 " + formatActionLabel(lastAction) + " · 能量 " + energy + " · 压力 " + runState.pressure + " · 生命 " + runState.hp + " · 奖励 " + runState.rewards + " · 分数 " + runState.score;
			meter.style.width = percent + "%";
			log.innerHTML = esc(message) + "<br>当前节点：" + esc(nodes[selected] ? nodes[selected].label : "package root") + "<br>节点角色：" + esc(nodes[selected] ? nodes[selected].role : "none") + "<br>操作次数：" + actions;
		}
		function initialize(data) {
			dataLoaded = data;
			const manifest = data.web_preview_manifest || {};
			previewContract = data.playable_preview_contract || null;
			previewSemanticAdapter = data.semantic_adapter || null;
			initializeContractRules(previewContract, previewSemanticAdapter);
			scenes = Array.isArray(manifest.scenes) ? manifest.scenes : [];
			makeNodes();
			initializeSemanticActions(previewSemanticAdapter, previewContract);
			const semanticProfile = previewSemanticAdapter && previewSemanticAdapter.semantic_profile ? previewSemanticAdapter.semantic_profile : {};
			name.textContent = semanticProfile.gameplay_label || data.game_name || data.project_name || "Godot Package";
			const objectives = previewContract && Array.isArray(previewContract.objectives) ? previewContract.objectives : [];
			if (semanticProfile.first_loop_path && semanticProfile.first_loop_path.length) {
				message = "语义试玩路径：" + semanticProfile.first_loop_path.map(function (step) { return step.label || step.role || step.action; }).slice(0, 5).join(" → ");
			} else if (objectives.length && objectives[0].label) {
				message = objectives[0].label;
			}
			summary.textContent = previewSemanticAdapter
				? "这是通用试玩基座叠加项目语义适配器生成的浏览器试玩层；不依赖项目名称硬编码。"
				: previewContract
				? "这是基于 playable-preview-contract.json 生成的通用试玩层；不依赖项目名称，也不使用专用游戏转换器。"
				: "这是基于包 manifest 和场景清单生成的通用试玩层；不依赖项目名称，也不使用专用游戏转换器。";
			panel.style.display = "block";
			render();
		}
		function move(dx, dy) {
			player.x = clamp(player.x + dx * 5.5, 7, 93);
			player.y = clamp(player.y + dy * 5.5, 10, 90);
			const near = nearestNode();
			message = near && near.distance < 13 ? "靠近 " + near.node.label + "，可以互动。" : "移动中：寻找下一个可检查节点。";
			render();
		}
		function interact() {
			if (!nodes.length) return;
			const near = nearestNode();
			actions += 1;
			lastAction = "interact";
			if (near && near.distance <= 16) {
				near.node.done = true;
				progress += 1;
				if (!roleInteractions[near.node.role]) {
					energy = Math.max(0, energy - 1);
				}
				message = applyRoleInteraction(near.node);
				if (energy === 0) {
					energy = 3;
					phase += 1;
					message += " 能量恢复，进入下一阶段。";
				}
			} else {
				message = "距离场景节点太远，先移动到发光节点附近。";
			}
			if (nodes.every(function (node) { return node.done; })) {
				message = "试玩闭环完成：移动、选择场景、互动和进度反馈均可用。";
			}
			render();
		}
		function semanticAction(action) {
			if (!nodes.length) return;
			const normalized = String(action || "").toLowerCase();
			if (normalized === "basic_attack") {
				resolveBasicAttack();
				return;
			}
			if (normalized === "skill_or_roll") {
				resolveSkillOrRoll();
				return;
			}
			if (normalized === "choice") {
				resolveChoice();
				return;
			}
			if (normalized === "start" || normalized === "retry") {
				resolveStartOrRetry(normalized);
				return;
			}
			const node = findNodeForAction(action);
			if (!node) {
				message = "没有找到可匹配的语义动作节点：" + formatActionLabel(action) + "。";
				render();
				return;
			}
			selected = Math.max(0, nodes.indexOf(node));
			player.x = clamp(node.x - 4, 8, 92);
			player.y = clamp(node.y + 3, 12, 88);
			node.done = true;
			actions += 1;
			lastAction = action;
			message = formatActionLabel(action) + " → " + applyRoleInteraction(node);
			if (nodes.every(function (item) { return item.done; })) {
				message += " 试玩闭环完成。";
			}
			render();
		}
		function resolveBasicAttack() {
			const target = findClosestNode(function (node) { return !node.done && (node.role === "pressure_source" || node.role === "challenge"); }) ||
				findClosestNode(function (node) { return !node.done && node.role === "action"; });
			actions += 1;
			lastAction = "basic_attack";
			if (!target) {
				message = "攻击挥空：当前没有可处理的压力源。";
				render();
				return;
			}
			selected = Math.max(0, nodes.indexOf(target.node));
			player.x = clamp(target.node.x - 6, 8, 92);
			player.y = clamp(target.node.y + 4, 12, 88);
			if (target.distance <= 28 || target.node.role === "action") {
				target.node.done = true;
				runState.score += 3;
				runState.pressure = Math.max(0, runState.pressure - 1);
				message = "攻击命中 " + target.node.label + "，压力下降。";
			} else {
				runState.pressure += 1;
				message = "攻击距离不足，" + target.node.label + " 继续逼近。";
			}
			render();
		}
		function resolveSkillOrRoll() {
			actions += 1;
			lastAction = "skill_or_roll";
			energy = Math.max(0, energy - 1);
			const targets = nodes
				.filter(function (node) { return !node.done && (node.role === "pressure_source" || node.role === "challenge" || node.role === "action"); })
				.sort(function (a, b) { return distanceToPlayer(a) - distanceToPlayer(b); })
				.slice(0, energy > 0 ? 2 : 1);
			if (!targets.length) {
				player.x = clamp(player.x + 8, 7, 93);
				message = "技能/闪避调整站位，当前没有可命中的压力源。";
				render();
				return;
			}
			targets.forEach(function (node) {
				node.done = true;
				runState.score += 2;
			});
			runState.pressure = Math.max(0, runState.pressure - targets.length);
			selected = Math.max(0, nodes.indexOf(targets[0]));
			message = "技能/闪避处理 " + targets.map(function (node) { return node.label; }).join("、") + "，压力被压低。";
			render();
		}
		function resolveChoice() {
			const reward = findClosestNode(function (node) { return !node.done && node.role === "reward"; }) || findClosestNode(function (node) { return !node.done && /reward|door|choice|chest/i.test(node.label); });
			actions += 1;
			lastAction = "choice";
			if (!reward) {
				message = "当前没有可领取的奖励选择。";
				render();
				return;
			}
			reward.node.done = true;
			selected = Math.max(0, nodes.indexOf(reward.node));
			runState.rewards += 1;
			runState.score += 4;
			energy = 3;
			phase += 1;
			wave += 1;
			message = "选择奖励 " + reward.node.label + "，能量恢复并进入波次 " + wave + "。";
			render();
		}
		function resolveStartOrRetry(action) {
			actions += 1;
			lastAction = action;
			if (action === "retry") {
				reset();
				started = true;
				message = "重试后重新开始，压力和生命已恢复。";
				render();
				return;
			}
			started = true;
			const startNode = findNodeForAction("start");
			if (startNode) {
				startNode.done = true;
				selected = Math.max(0, nodes.indexOf(startNode));
			}
			message = "开始试玩：压力源会推进，使用攻击、技能/闪避和奖励选择完成闭环。";
			render();
		}
		function tickPressureSources() {
			if (!dataLoaded || panel.style.display === "none" || panel.classList.contains("minimized")) return;
			if (!started) return;
			const now = Date.now();
			if (now - lastPressureTick < 1100) return;
			lastPressureTick = now;
			let active = 0;
			nodes.forEach(function (node) {
				if (node.done || node.role !== "pressure_source") return;
				active += 1;
				const dx = player.x - node.x;
				const dy = player.y - node.y;
				const length = Math.max(1, Math.sqrt(dx * dx + dy * dy));
				node.x = clamp(node.x + dx / length * 1.8, 8, 92);
				node.y = clamp(node.y + dy / length * 1.8, 12, 88);
				if (distanceToPlayer(node) < 12) {
					runState.pressure += 1;
					runState.hp = Math.max(1, runState.hp - 1);
					message = node.label + " 逼近造成压力，使用攻击或技能处理。";
				}
			});
			if (active > 0) {
				runState.pressure = clamp(runState.pressure + 0.15, 0, 9);
				render();
			}
		}
		function applyStateDelta(delta) {
			if (!delta) return;
			Object.keys(delta).forEach(function (key) {
				const amount = Number(delta[key] || 0);
				const bounds = stateBounds[key] || { min: 0, max: 999 };
				if (key === "energy") {
					energy = clamp(energy + amount, bounds.min, bounds.max);
				} else if (key === "phase") {
					phase = clamp(phase + amount, bounds.min, bounds.max);
				} else {
					runState[key] = clamp(Number(runState[key] || 0) + amount, bounds.min, bounds.max);
				}
			});
			if (runState.pressure >= 3 && runState.hp > 1) {
				runState.hp -= 1;
			}
		}
		function formatContractFeedback(template, node) {
			return String(template || "已执行 " + node.role + "：" + node.label)
				.replace(/\{label\}/g, node.label || "节点")
				.replace(/\{role\}/g, node.role || "entity")
				.replace(/\{phase\}/g, String(phase))
				.replace(/\{hp\}/g, String(runState.hp));
		}
		function applyRoleInteraction(node) {
			const label = node.label || "节点";
			const contractRule = roleInteractions[node.role];
			if (contractRule) {
				applyStateDelta(contractRule.state_delta || {});
				return formatContractFeedback(contractRule.feedback, node);
			}
			if (node.role === "player_start") {
				runState.score += 1;
				return "已定位可控角色 " + label + "，移动与交互链路就绪。";
			}
			if (node.role === "pressure_source" || node.role === "challenge") {
				runState.pressure += 1;
				runState.score += 2;
				if (runState.pressure >= 3) {
					runState.hp = Math.max(1, runState.hp - 1);
					return "处理压力源 " + label + "，压力升高但仍可继续；当前生命 " + runState.hp + "。";
				}
				return "遭遇 " + label + "，完成一次通用战斗/压力验证。";
			}
			if (node.role === "action") {
				runState.score += 2;
				runState.pressure = Math.max(0, runState.pressure - 1);
				return "触发动作节点 " + label + "，压力下降并获得反馈。";
			}
			if (node.role === "reward") {
				runState.rewards += 1;
				runState.score += 3;
				energy = 3;
				phase += 1;
				return "领取奖励 " + label + "，能量恢复并进入阶段 " + phase + "。";
			}
			if (node.role === "ui_action") {
				runState.score += 1;
				if (label.toLowerCase().indexOf("retry") >= 0) {
					runState.hp = 3;
					runState.pressure = 0;
					return "触发重试入口 " + label + "，生命和压力已重置。";
				}
				return "触发界面动作 " + label + "，流程按钮可响应。";
			}
			if (node.role === "feedback") {
				return "读取反馈节点 " + label + "，HUD/日志信息可追踪。";
			}
			if (node.role === "transition") {
				phase += 1;
				return "通过转场节点 " + label + "，进入阶段 " + phase + "。";
			}
			if (node.role === "play_space") {
				return "确认可导航空间 " + label + "，移动区域可验证。";
			}
			if (node.role === "buildable_unit") {
				runState.score += 1;
				return "检查可构筑/防御单位 " + label + "，构筑类节点可被通用契约表达。";
			}
			runState.score += 1;
			return "已完成 " + label + " 的通用互动验证：" + node.objective;
		}
		function selectNode(index) {
			if (!nodes.length) return;
			selected = clamp(index, 0, nodes.length - 1);
			player.x = clamp(nodes[selected].x - 5, 8, 92);
			player.y = clamp(nodes[selected].y + 4, 12, 88);
			message = "已选择 " + nodes[selected].label + "。";
			render();
		}
		function reset() {
			player = { x: 50, y: 64 };
			progress = 0;
			energy = 3;
			actions = 0;
			phase = 1;
			runState = { score: 0, pressure: 0, rewards: 0, hp: 3 };
			lastAction = "reset";
			started = false;
			wave = 1;
			lastPressureTick = 0;
			initializeContractRules(previewContract, previewSemanticAdapter);
			selected = 0;
			nodes.forEach(function (node) { node.done = false; });
			message = "已重置，移动到发光节点并互动。";
			render();
		}
		stage.addEventListener("click", function (event) {
			if (event.target.classList.contains("phasea-node")) return;
			const rect = stage.getBoundingClientRect();
			player.x = clamp((event.clientX - rect.left) / rect.width * 100, 7, 93);
			player.y = clamp((event.clientY - rect.top) / rect.height * 100, 10, 90);
			const near = nearestNode();
			message = near && near.distance < 13 ? "已移动到 " + near.node.label + " 附近。" : "已移动到目标位置。";
			render();
		});
		interactButton.onclick = interact;
		nextButton.onclick = function () { selectNode((selected + 1) % Math.max(1, nodes.length)); };
		resetButton.onclick = reset;
		minimizeButton.onclick = function () {
			panel.classList.toggle("minimized");
			minimizeButton.textContent = panel.classList.contains("minimized") ? "展开" : "缩小";
		};
		document.querySelectorAll("[data-phasea-move]").forEach(function (button) {
			const parts = button.getAttribute("data-phasea-move").split(",").map(Number);
			button.onclick = function () { move(parts[0], parts[1]); };
		});
		document.querySelectorAll("[data-phasea-action='interact']").forEach(function (button) {
			button.onclick = interact;
		});
		document.addEventListener("keydown", function (event) {
			if (panel.style.display === "none") return;
			const key = event.key.toLowerCase();
			if (["w", "a", "s", "d", "q", "e", "r", "f", " ", "enter", "1", "2", "3"].indexOf(key) >= 0) {
				event.preventDefault();
			}
			if (key === "w") move(0, -1);
			else if (key === "s") move(0, 1);
			else if (key === "a") move(-1, 0);
			else if (key === "d") move(1, 0);
			else if (key === " " || key === "enter") interact();
			else if (key === "f") semanticAction("basic_attack");
			else if (key === "q") semanticAction("skill_or_roll");
			else if (key === "e") semanticAction("choice");
			else if (key === "r") semanticAction("retry");
			else if (key === "1") selectNode(0);
			else if (key === "2") selectNode(1);
			else if (key === "3") selectNode(2);
		});
		setInterval(tickPressureSources, 250);
		setTimeout(function () {
			fetch("preview-package-data.json?v=" + encodeURIComponent(version), { cache: "no-store" })
				.then(function (response) { return response.ok ? response.json() : null; })
				.then(function (data) {
					if (!data || !data.converter_id || data.converter_id.indexOf("godot-package-") !== 0) return;
					if (data.semantic_adapter) return;
					initialize(data);
				})
				.catch(function () {});
		}, 1200);
	}());
	</script>
</body>
""",
                StringComparison.Ordinal);
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

        if (!script.Contains("phaseAGetServiceWorker", StringComparison.Ordinal) &&
            (script.Contains("navigator.serviceWorker", StringComparison.Ordinal) ||
             script.Contains("\"serviceWorker\"in navigator", StringComparison.Ordinal)))
        {
            script = script.Replace(
                "var GodotPWA=",
                """
function phaseAGetServiceWorker() {
	try {
		return ("serviceWorker" in navigator) ? navigator.serviceWorker : null;
	} catch (e) {
		return null;
	}
}
var GodotPWA=
""",
                StringComparison.Ordinal);
            script = script.Replace(
                "function _godot_js_pwa_cb(p_update_cb){if(\"serviceWorker\"in navigator){const cb=GodotRuntime.get_func(p_update_cb);navigator.serviceWorker.getRegistration().then(GodotPWA.updateState.bind(null,cb))}}",
                "function _godot_js_pwa_cb(p_update_cb){const phaseAServiceWorker=phaseAGetServiceWorker();if(phaseAServiceWorker){const cb=GodotRuntime.get_func(p_update_cb);phaseAServiceWorker.getRegistration().then(GodotPWA.updateState.bind(null,cb))}}",
                StringComparison.Ordinal);
            script = script.Replace(
                "function _godot_js_pwa_update(){if(\"serviceWorker\"in navigator&&GodotPWA.hasUpdate){navigator.serviceWorker.getRegistration().then(function(reg){if(!reg||!reg.waiting){return}reg.waiting.postMessage(\"update\")});return 0}return 1}",
                "function _godot_js_pwa_update(){const phaseAServiceWorker=phaseAGetServiceWorker();if(phaseAServiceWorker&&GodotPWA.hasUpdate){phaseAServiceWorker.getRegistration().then(function(reg){if(!reg||!reg.waiting){return}reg.waiting.postMessage(\"update\")});return 0}return 1}",
                StringComparison.Ordinal);
        }

        if (!script.Contains("phaseAAppendAssetVersion(`${loadPath}.wasm`)", StringComparison.Ordinal) ||
            !script.Contains("phaseAAppendAssetVersion(file)", StringComparison.Ordinal))
        {
            throw new InvalidOperationException("Failed to version Godot web preview JavaScript assets.");
        }

        if (script.Contains("navigator.serviceWorker.getRegistration", StringComparison.Ordinal) ||
            script.Contains("\"serviceWorker\"in navigator&&", StringComparison.Ordinal))
        {
            throw new InvalidOperationException("Failed to sandbox-guard Godot web preview service worker access.");
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
            try
            {
                Directory.Move(targetDirectory, backupDirectory);
            }
            catch (IOException)
            {
                CopyDirectory(sourceDirectory, targetDirectory, overwrite: true);
                TryDeleteDirectoryIfExists(sourceDirectory);
                return;
            }
            catch (UnauthorizedAccessException)
            {
                CopyDirectory(sourceDirectory, targetDirectory, overwrite: true);
                TryDeleteDirectoryIfExists(sourceDirectory);
                return;
            }
        }

        try
        {
            try
            {
                Directory.Move(sourceDirectory, targetDirectory);
            }
            catch (IOException)
            {
                CopyDirectory(sourceDirectory, targetDirectory, overwrite: false);
                TryDeleteDirectoryIfExists(sourceDirectory);
            }
            catch (UnauthorizedAccessException)
            {
                CopyDirectory(sourceDirectory, targetDirectory, overwrite: false);
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

    private static void CopyDirectory(string sourceDirectory, string targetDirectory, bool overwrite)
    {
        if (Directory.Exists(targetDirectory) && !overwrite)
        {
            throw new IOException("Target directory already exists.");
        }

        Directory.CreateDirectory(targetDirectory);
        foreach (var sourceFile in Directory.EnumerateFiles(sourceDirectory, "*", SearchOption.AllDirectories))
        {
            var relativePath = Path.GetRelativePath(sourceDirectory, sourceFile);
            var targetFile = Path.Combine(targetDirectory, relativePath);
            Directory.CreateDirectory(Path.GetDirectoryName(targetFile)!);
            File.Copy(sourceFile, targetFile, overwrite);
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

        if (IsTowerdemo2PackageSubset(packageInfo) || IsTowerdemo2SemanticPackage(packageInfo))
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

    private static bool IsTowerdemo2PackageSubset(PackageInfo packageInfo)
    {
        return HasSupportedTowerdemo2Template(
            packageInfo.WebPreviewManifest.DetectedTemplates.Contains("towerdemo2", StringComparer.Ordinal),
            packageInfo.Towerdemo2SourceSceneSha256,
            packageInfo.Towerdemo2TextCatalogSha256);
    }

    private static bool IsTowerdemo2SemanticPackage(PackageInfo packageInfo)
    {
        if (packageInfo.PlayablePreviewContract is not { } contract ||
            contract.ValueKind != JsonValueKind.Object ||
            !contract.TryGetProperty("entities", out var entities) ||
            entities.ValueKind != JsonValueKind.Array)
        {
            return false;
        }

        var hasPlayer = false;
        var hasAttackArea = false;
        var hasSkillShapeCast = false;
        var hasRewardDoor = false;
        var hasEnemyPressure = false;
        var hasTowerdemo2Scene = packageInfo.Scenes.Any(scene =>
            scene.Contains("/Towerdemo2/", StringComparison.OrdinalIgnoreCase));

        foreach (var entity in entities.EnumerateArray())
        {
            if (entity.ValueKind != JsonValueKind.Object)
            {
                continue;
            }

            var label = GetJsonString(entity, "label");
            var role = GetJsonString(entity, "role");
            var nodePath = GetJsonString(entity, "node_path");
            var scene = GetJsonString(entity, "scene");
            var text = $"{label} {role} {nodePath} {scene}";
            hasPlayer |= string.Equals(role, "player_start", StringComparison.Ordinal) &&
                text.Contains("Player", StringComparison.OrdinalIgnoreCase);
            hasAttackArea |= string.Equals(role, "action", StringComparison.Ordinal) &&
                text.Contains("AttackArea", StringComparison.OrdinalIgnoreCase);
            hasSkillShapeCast |= string.Equals(role, "action", StringComparison.Ordinal) &&
                text.Contains("SkillShapeCast", StringComparison.OrdinalIgnoreCase);
            hasRewardDoor |= string.Equals(role, "reward", StringComparison.Ordinal) &&
                text.Contains("RewardDoor", StringComparison.OrdinalIgnoreCase);
            hasEnemyPressure |= string.Equals(role, "pressure_source", StringComparison.Ordinal) &&
                (text.Contains("Enemy", StringComparison.OrdinalIgnoreCase) ||
                    text.Contains("Spawn", StringComparison.OrdinalIgnoreCase));
            hasTowerdemo2Scene |= scene.Contains("/Towerdemo2/", StringComparison.OrdinalIgnoreCase);
        }

        return hasTowerdemo2Scene &&
            hasPlayer &&
            hasAttackArea &&
            hasSkillShapeCast &&
            hasRewardDoor &&
            hasEnemyPressure;
    }

    private static string GetJsonString(JsonElement element, string propertyName)
    {
        return element.ValueKind == JsonValueKind.Object &&
            element.TryGetProperty(propertyName, out var property) &&
            property.ValueKind == JsonValueKind.String
            ? property.GetString() ?? ""
            : "";
    }

    private static bool HasSupportedTowerdemo2Template(
        bool hasTowerdemo2SourceScene,
        string sourceSceneSha256,
        string textCatalogSha256)
    {
        return hasTowerdemo2SourceScene &&
            string.Equals(sourceSceneSha256, Towerdemo2Converter.SourceSceneSha256, StringComparison.OrdinalIgnoreCase) &&
            string.Equals(textCatalogSha256, Towerdemo2Converter.TextCatalogSha256, StringComparison.OrdinalIgnoreCase);
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
            packageInfo.GameTypeSource
        };

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
        [property: JsonPropertyName("visual_asset_hints")] IReadOnlyList<PackageWebPreviewVisualAssetHint> VisualAssetHints,
        [property: JsonPropertyName("input_map_hints")] IReadOnlyList<PackageWebPreviewInputMapHint> InputMapHints,
        [property: JsonPropertyName("script_behavior_hints")] IReadOnlyList<PackageWebPreviewScriptBehaviorHint> ScriptBehaviorHints,
        [property: JsonPropertyName("scene_graph_hints")] IReadOnlyList<PackageWebPreviewSceneGraphHint> SceneGraphHints,
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

    private sealed record PackageWebPreviewVisualAssetHint(
        [property: JsonPropertyName("source_path")] string SourcePath,
        [property: JsonPropertyName("preview_resource_path")] string PreviewResourcePath,
        [property: JsonPropertyName("role")] string Role,
        [property: JsonPropertyName("file_name")] string FileName,
        [property: JsonPropertyName("size_bytes")] long SizeBytes);

    private sealed record PackageWebPreviewInputMapHint(
        [property: JsonPropertyName("action")] string Action,
        [property: JsonPropertyName("tokens")] IReadOnlyList<string> Tokens,
        [property: JsonPropertyName("raw")] string Raw);

    private sealed record PackageWebPreviewScriptBehaviorHint(
        [property: JsonPropertyName("path")] string Path,
        [property: JsonPropertyName("language")] string Language,
        [property: JsonPropertyName("roles")] IReadOnlyList<string> Roles,
        [property: JsonPropertyName("input_actions")] IReadOnlyList<string> InputActions,
        [property: JsonPropertyName("node_refs")] IReadOnlyList<string> NodeRefs,
        [property: JsonPropertyName("excerpt")] IReadOnlyList<string> Excerpt);

    private sealed record PackageWebPreviewSceneGraphHint(
        [property: JsonPropertyName("path")] string Path,
        [property: JsonPropertyName("root_node_name")] string RootNodeName,
        [property: JsonPropertyName("root_node_type")] string RootNodeType,
        [property: JsonPropertyName("nodes")] IReadOnlyList<PackageWebPreviewSceneNodeHint> Nodes,
        [property: JsonPropertyName("script_paths")] IReadOnlyList<string> ScriptPaths,
        [property: JsonPropertyName("texture_paths")] IReadOnlyList<string> TexturePaths,
        [property: JsonPropertyName("physics_node_types")] IReadOnlyList<string> PhysicsNodeTypes);

    private sealed record PackageWebPreviewSceneNodeHint(
        [property: JsonPropertyName("name")] string Name,
        [property: JsonPropertyName("type")] string Type,
        [property: JsonPropertyName("parent")] string Parent,
        [property: JsonPropertyName("script_path")] string ScriptPath,
        [property: JsonPropertyName("texture_path")] string TexturePath);

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
        string PackagePath,
        bool IsTowerdemo2,
        string Towerdemo2SourceSceneSha256,
        string Towerdemo2TextCatalogSha256,
        long PackageSizeBytes,
        string PackageSha256,
        JsonElement? PlayablePreviewContract,
        PackageWebPreviewManifest WebPreviewManifest,
        JsonElement? SemanticAdapter = null,
        ProjectWebPreviewSemanticAdapterResolution? SemanticAdapterResolution = null,
        ProjectWebPreviewDedicatedAdapterResolution? DedicatedAdapterResolution = null);
}
