using System.Text;
using System.Text.Json;
using System.IO.Compression;
using System.Security.Cryptography;
using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Readback;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Tests.Data;
using Xunit;

namespace PhaseA.Platform.Tests.Readback;

public sealed class ProjectWebPreviewServiceTests
{
    [Theory]
    [InlineData("index.js", true)]
    [InlineData("index.wasm", true)]
    [InlineData("index.pck", true)]
    [InlineData("index.html", false)]
    [InlineData("preview-data.json", false)]
    public void IsImmutablePreviewAsset_ClassifiesGodotWebAssets(string fileName, bool expected)
    {
        ProjectWebPreviewService.IsImmutablePreviewAsset(fileName).Should().Be(expected);
    }

    [Fact]
    public void Godot3HealthSmoke_DoesNotConsumeUserWebPreviewQueue()
    {
        var sourcePath = Path.GetFullPath(Path.Combine(
            AppContext.BaseDirectory,
            "..",
            "..",
            "..",
            "..",
            "PhaseA.Platform",
            "Readback",
            "ProjectWebPreviewService.cs"));
        var source = File.ReadAllText(sourcePath);

        source.Should().Contain("HealthSmokeGate");
        source.Should().NotContain("\"project-web-preview-health\"");
    }

    [Fact]
    public void PackageStatus_UsesCachedPackageShaForPreviewId()
    {
        var sourcePath = Path.GetFullPath(Path.Combine(
            AppContext.BaseDirectory,
            "..",
            "..",
            "..",
            "..",
            "PhaseA.Platform",
            "Readback",
            "ProjectWebPreviewService.cs"));
        var source = File.ReadAllText(sourcePath);

        source.Should().Contain("PackageHashCache");
        source.Should().Contain("ComputeFileSha256Cached(packagePath)");
        source.Should().Contain("PackageHashCacheTtl");
        source.Should().Contain("PackageHashCacheMaxEntries");
        source.Should().Contain("TrimPackageHashCache(now)");
        source.Should().Contain("cached.Length == length");
        source.Should().Contain("cached.LastWriteUtc == lastWriteUtc");
    }

    [Fact]
    public void WebPreviewConverters_UseTowerdemo2WhenFingerprintsMatchAndGenericFallbackOtherwise()
    {
        var sourcePath = Path.GetFullPath(Path.Combine(
            AppContext.BaseDirectory,
            "..",
            "..",
            "..",
            "..",
            "PhaseA.Platform",
            "Readback",
            "ProjectWebPreviewService.cs"));
        var source = File.ReadAllText(sourcePath);

        source.Should().Contain("phasea-web-preview-v4");
        source.Should().Contain("phasea-web-preview-manifest-v1");
        source.Should().Contain("web-preview-manifest.json");
        source.Should().Contain("generated_by_web_preview_converter");
        source.Should().Contain("godot-package-generic-playable-preview");
        source.Should().Contain("godot3-html5-generic-package-preview");
        source.Should().Contain("docs/game-type-guides/survivorslike.md");
        source.Should().Contain("RpgPackageConverter");
        source.Should().Contain("SurvivalPackageConverter");
        source.Should().Contain("SurvivorslikePackageConverter");
        source.Should().Contain("CardPackageConverter");
        source.Should().Contain("TowerDefensePackageConverter");
        source.Should().Contain("ActionPackageConverter");
        source.Should().Contain("NarrativePackageConverter");
        source.Should().Contain("PuzzlePackageConverter");
        source.Should().Contain("StrategyPackageConverter");
        source.Should().Contain("towerdemo2-20260627-source-fingerprint-v1");
        source.Should().Contain(Towerdemo2SceneSha256);
        source.Should().Contain(Towerdemo2TextCatalogSha256);
        source.Should().Contain("BuildWebPreviewManifest(");
        source.Should().Contain("IsTowerdemo2PackageSubset(packageInfo)");
        source.Should().Contain("packageInfo.WebPreviewManifest.DetectedTemplates.Contains(\"towerdemo2\"");
        source.Should().Contain("converter = ResolvePackageConverterByType(packageInfo)");
        source.Should().Contain("!string.IsNullOrWhiteSpace(packageInfo.MainScene) || packageInfo.Scenes.Count > 0");
        source.Should().Contain("CreateGenericGodotPackageProject(");
        source.Should().Contain("RenderPackageAdapterMainScript(converter.AdapterStyle)");
        source.Should().Contain("func _input(event):");
        source.Should().Contain("func playable_semantic_entities():");
        source.Should().Contain("func entity_position(entity, fallback):");
        source.Should().Contain("func configure_world_bounds():");
        source.Should().Contain("func is_pressure_container_entity(entity):");
        source.Should().Contain("runtime_tuning = semantic_adapter.get(\"runtime_tuning\", {})");
        source.Should().Contain("var floor_body = StaticBody.new()");
        source.Should().NotContain("var floor = StaticBody.new()");
        source.Should().NotContain("hp = max(0, hp - counter)");
        source.Should().NotContain("hp = max(0, hp - max(0, 8 + wave * 3 + enemies_remaining() * 2 - guard))");
        source.Should().NotContain("func _unhandled_input(event):");
        source.Should().Contain("ui_font.tres");
        source.Should().Contain("load(\"res://Fonts/ui_font.tres\")");
        source.Should().Contain("PHASEA_WEB_PREVIEW_CJK_FONT_PATH");
        source.Should().NotContain("data.font_path = \"res://Fonts/simhei.ttf\"");
        source.Should().Contain("load_package_data()");
        source.Should().Contain("preview-package-data.json");
        source.Should().Contain("ProjectWebPreviewGameTypeCatalog.ResolveGameTypeId");
        source.Should().Contain("package_scan_budget_exceeded");
        source.Should().Contain("package_invalid_zip");
        source.Should().Contain("ResolveConverterSourceSceneSha256(packageInfo, converter)");
        source.Should().Contain("ResolveConverterTextCatalogSha256(packageInfo, converter)");
        source.Should().Contain("web_preview_manifest = packageInfo.WebPreviewManifest");
        source.Should().Contain("converter_compatibility_id = converter.CompatibilityId");
        source.Should().Contain("converter_coverage = converter.CoverageSummary");
        source.Should().Contain("survival_gather_needs_shelter_preview");
        source.Should().Contain("godot3-html5-survival-package-preview");
        source.Should().NotContain("\"arena-survival\", \"survival\", \"roguelike\"");
    }

    [Fact]
    public void PatchGodotWebShell_VersionsJavascriptWasmAndPackRequests()
    {
        using var temp = TempDirectory.Create("phase-a-web-preview-shell");
        var indexPath = Path.Combine(temp.Path, "index.html");
        var scriptPath = Path.Combine(temp.Path, "index.js");

        File.WriteAllText(indexPath, """
<!DOCTYPE html>
<html>
<head>
	<style>
		#status-progress-inner {
			height: 100%;
		}
	</style>
</head>
<body>
	<div id='status-progress' style='display: none;' oncontextmenu='event.preventDefault();'><div id ='status-progress-inner'></div></div>
	<script type='text/javascript' src='index.js'></script>
	<script type='text/javascript'>
		const GODOT_CONFIG = {"args":[],"canvasResizePolicy":2,"executable":"index","fileSizes":{"index.pck":10,"index.wasm":20}};
		var engine = new Engine(GODOT_CONFIG);
		(function() {
			var statusProgressInner = document.getElementById('status-progress-inner');
			var statusIndeterminate = document.getElementById('status-indeterminate');
			var initializing = true;
			var statusMode = 'hidden';
			[statusProgress, statusIndeterminate, statusNotice].forEach(elem => {
			});
			statusProgress.style.display = 'block';
						break;
			statusIndeterminate.style.display = 'block';
						animationCallbacks.push(animateStatusIndeterminate);
			statusProgressInner.style.width = current/total * 100 + '%';
							setStatusMode('progress');
			setStatusMode('hidden');
					initializing = false;
		})();
	</script>
</body>
</html>
""", Encoding.UTF8);

        File.WriteAllText(scriptPath, """
const Preloader = function () {
	this.preload = function (pathOrBuffer, destPath, fileSize) {};
	this.loadPromise = function (file, fileSize, raw = false) {};
};
var GodotPWA={hasUpdate:false,updateState:function(cb,reg){}};
function _godot_js_pwa_cb(p_update_cb){if("serviceWorker"in navigator){const cb=GodotRuntime.get_func(p_update_cb);navigator.serviceWorker.getRegistration().then(GodotPWA.updateState.bind(null,cb))}}
function _godot_js_pwa_update(){if("serviceWorker"in navigator&&GodotPWA.hasUpdate){navigator.serviceWorker.getRegistration().then(function(reg){if(!reg||!reg.waiting){return}reg.waiting.postMessage("update")});return 0}return 1}
const InternalConfig = function (initConfig) { // eslint-disable-line no-unused-vars
};
Config.prototype.getModuleConfig = function (loadPath, response) {
	return {
			'locateFile': function (path) {
				if (path.endsWith('.worker.js')) {
					return `${loadPath}.worker.js`;
				} else if (path.endsWith('.audio.worklet.js')) {
					return `${loadPath}.audio.worklet.js`;
				} else if (path.endsWith('.js')) {
					return `${loadPath}.js`;
				} else if (path.endsWith('.side.wasm')) {
					return `${loadPath}.side.wasm`;
				} else if (path.endsWith('.wasm')) {
					return `${loadPath}.wasm`;
				}
				return path;
			},
		};
};
const Engine = (function () {
	const preloader = new Preloader();
	let loadPromise = null;
	let loadPath = '';
	Engine.load = function (basePath, size) {
		if (loadPromise == null) {
			loadPath = basePath;
			loadPromise = preloader.loadPromise(`${loadPath}.wasm`, size, true);
		}
	};
	const proto = {
			preloadFile: function (file, path) {
				return preloader.preload(file, path, this.config.fileSizes[file]);
			},
	};
}());
""", Encoding.UTF8);

        ProjectWebPreviewService.PatchGodotWebShell(indexPath, scriptPath, "abc123");

        var html = File.ReadAllText(indexPath, Encoding.UTF8);
        var script = File.ReadAllText(scriptPath, Encoding.UTF8);

        html.Should().Contain("src='index.js?v=abc123'");
        html.Should().Contain("window.__PHASEA_WEB_PREVIEW_ASSET_VERSION = 'abc123'");
        html.Should().Contain("phasea-preview-stage");
        html.Should().Contain("phasea-preview-interact");
        html.Should().Contain("phasea-preview-action-list");
        html.Should().Contain("preview-package-data.json?v=");
        html.Should().Contain("通用试玩层");
        html.Should().Contain("试玩闭环完成");
        html.Should().Contain("WASD");
        html.Should().Contain("applyRoleInteraction");
        html.Should().Contain("semanticAction");
        html.Should().Contain("resolveBasicAttack");
        html.Should().Contain("tickPressureSources");
        html.Should().Contain("basic_attack");
        html.Should().Contain("skill_or_roll");
        html.Should().Contain("initializeContractRules");
        html.Should().Contain("roleInteractions");
        html.Should().Contain("压力源");
        html.Should().Contain("领取奖励");
        script.Should().Contain("function phaseAAppendAssetVersion(file)");
        script.Should().Contain("phaseAAppendAssetVersion(`${loadPath}.wasm`)");
        script.Should().Contain("phaseAAppendAssetVersion(file)");
        script.Should().Contain("this.config.fileSizes[file] || this.config.fileSizes[path]");
        script.Should().Contain("function phaseAGetServiceWorker()");
        script.Should().Contain("phaseAServiceWorker.getRegistration()");
        script.Should().NotContain("navigator.serviceWorker.getRegistration");
        script.Should().NotContain("\"serviceWorker\"in navigator&&");
    }

    [Fact]
    public void PrunePreviewScratchDirectories_RemovesOnlyOldScratchDirectories()
    {
        using var temp = TempDirectory.Create("phase-a-web-preview-prune");
        var previewRoot = Path.Combine(temp.Path, "exports", "web-previews");
        var ready = Path.Combine(previewRoot, "ready-preview");
        var oldBuild = Path.Combine(previewRoot, ".ready-preview.run.build");
        var oldBackup = Path.Combine(previewRoot, "ready-preview.replace-abc.bak");
        var freshBuild = Path.Combine(previewRoot, ".fresh-preview.run.build");

        Directory.CreateDirectory(ready);
        Directory.CreateDirectory(oldBuild);
        Directory.CreateDirectory(oldBackup);
        Directory.CreateDirectory(freshBuild);
        Directory.SetLastWriteTimeUtc(oldBuild, new DateTime(2026, 6, 26, 0, 0, 0, DateTimeKind.Utc));
        Directory.SetLastWriteTimeUtc(oldBackup, new DateTime(2026, 6, 26, 0, 0, 0, DateTimeKind.Utc));
        Directory.SetLastWriteTimeUtc(freshBuild, new DateTime(2026, 6, 27, 5, 30, 0, DateTimeKind.Utc));

        ProjectWebPreviewService.PrunePreviewScratchDirectories(
            temp.Path,
            new DateTimeOffset(2026, 6, 27, 6, 0, 0, TimeSpan.Zero));

        Directory.Exists(ready).Should().BeTrue();
        Directory.Exists(freshBuild).Should().BeTrue();
        Directory.Exists(oldBuild).Should().BeFalse();
        Directory.Exists(oldBackup).Should().BeFalse();
    }

    [Fact]
    public async Task ProjectWebPreviewConcurrencyLimiter_LimitsOneRunPerAccount()
    {
        var limiter = new ProjectWebPreviewConcurrencyLimiter(maxConcurrentWebPreviewsPerAccount: 1);

        var first = await limiter.TryAcquireAsync("account-a");
        await using var firstLease = first.Lease!;
        var second = await limiter.TryAcquireAsync("account-a");
        var otherAccount = await limiter.TryAcquireAsync("account-b");
        await using var otherLease = otherAccount.Lease!;

        first.FailureCode.Should().BeNull();
        second.Lease.Should().BeNull();
        second.FailureCode.Should().Be("user_web_preview_concurrency_limit_exceeded");
        otherAccount.FailureCode.Should().BeNull();
    }

    [Fact]
    public async Task ResolvePreviewForPackageAsync_ReturnsFailedRunStatus_WhenPreviewIsNotReady()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-web-preview-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-web-preview-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, Path.Combine(workspaceRoot.Path, "metadata.sqlite3"));
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("web-preview-status-user", 1);
        var projectId = await CreateProjectAsync(store, options, account.AccountId);
        var project = await store.GetProjectSnapshotAsync(projectId);
        project.Should().NotBeNull();
        var packageFile = "Towerdemo2-v0.1.20260627.002.zip";
        var packagePath = Path.Combine(project!.RepoPath, "exports", packageFile);
        Directory.CreateDirectory(Path.GetDirectoryName(packagePath)!);
        await File.WriteAllTextAsync(packagePath, "fake zip bytes", Encoding.UTF8);

        var runId = await store.CreateRunAsync(project.ProjectId, project.WorkspaceId, "project-web-preview");
        await store.MarkRunStartedAsync(runId);
        await store.UpdateRunProgressAsync(runId, "project-web-preview", packageFile, "Generating Godot 3 browser preview.");
        await store.CompleteRunAsync(
            runId,
            "failed",
            1,
            "",
            "export failed",
            """
            {"run_type":"project-web-preview","package_file":"Towerdemo2-v0.1.20260627.002.zip","failure_code":"godot3_export_failed","mode":"godot3-html5-towerdemo2-template-subset"}
            """);

        var service = new ProjectWebPreviewService(store, options);
        var status = await service.ResolvePreviewForPackageAsync(project, packageFile);

        status.Status.Should().Be("failed");
        status.RunId.Should().Be(runId);
        status.FailureCode.Should().Be("godot3_export_failed");
        status.PreviewId.Should().NotBeNullOrWhiteSpace();
        status.PreviewUrl.Should().BeNull();
    }

    [Fact]
    public async Task QueuePreviewAsync_CreatesQueuedRunVisibleInPackageStatus()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-web-preview-queue-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-web-preview-queue-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, Path.Combine(workspaceRoot.Path, "metadata.sqlite3"));
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("web-preview-queue-user", 1);
        var projectId = await CreateProjectAsync(store, options, account.AccountId);
        var project = (await store.GetProjectSnapshotAsync(projectId))!;
        var packageFile = "Towerdemo2-v0.1.20260627.002.zip";
        WriteMinimalGodotPackage(project.RepoPath, packageFile);

        var service = new ProjectWebPreviewService(store, options);
        var queued = await service.QueuePreviewAsync(account.AccountId, project.ProjectId, packageFile);
        var status = await service.ResolvePreviewForPackageAsync(project, packageFile);

        queued.Status.Should().Be("queued");
        queued.RunId.Should().NotBeNullOrWhiteSpace();
        status.Status.Should().Be("queued");
        status.RunId.Should().Be(queued.RunId);
        status.FailureCode.Should().BeNull();
    }

    [Fact]
    public async Task QueuePreviewAsync_FailsFast_WhenPackageZipIsInvalid()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-web-preview-invalid-zip-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-web-preview-invalid-zip-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, Path.Combine(workspaceRoot.Path, "metadata.sqlite3"));
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("web-preview-invalid-zip-user", 1);
        var projectId = await CreateProjectAsync(store, options, account.AccountId);
        var project = (await store.GetProjectSnapshotAsync(projectId))!;
        var packageFile = "BrokenPackage-v0.1.20260627.001.zip";
        WritePackage(project.RepoPath, packageFile, "not a zip");
        var service = new ProjectWebPreviewService(store, options);

        var validation = await service.ValidatePreviewQueueAsync(account.AccountId, project.ProjectId, packageFile);
        var queued = await service.QueuePreviewAsync(account.AccountId, project.ProjectId, packageFile);

        validation.Should().Be("package_invalid_zip");
        queued.Status.Should().Be("failed");
        queued.FailureCode.Should().Be("package_invalid_zip");
        queued.RunId.Should().BeEmpty();
    }

    [Fact]
    public async Task ResolvePreviewForPackageAsync_KeepsReadyPreviewAndReportsNewerFailure()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-web-preview-ready-failure-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-web-preview-ready-failure-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, Path.Combine(workspaceRoot.Path, "metadata.sqlite3"));
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("web-preview-ready-failure-user", 1);
        var projectId = await CreateProjectAsync(store, options, account.AccountId);
        var project = (await store.GetProjectSnapshotAsync(projectId))!;
        var packageFile = "Towerdemo2-v0.1.20260627.002.zip";
        var packageBytes = Encoding.UTF8.GetBytes("fake zip bytes");
        WritePackage(project.RepoPath, packageFile, packageBytes);
        var previewId = $"{Path.GetFileNameWithoutExtension(packageFile)}-{ShortSha(packageBytes)}";
        var previewRoot = Path.Combine(project.RepoPath, "exports", "web-previews", previewId);
        Directory.CreateDirectory(Path.Combine(previewRoot, "web"));
        await File.WriteAllTextAsync(Path.Combine(previewRoot, "web", "index.html"), "<html></html>", Encoding.UTF8);
        var manifestJson = Towerdemo2PreviewManifest();
        await File.WriteAllTextAsync(Path.Combine(previewRoot, "web-preview-manifest.json"), manifestJson, Encoding.UTF8);
        var manifestSha256 = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(manifestJson))).ToLowerInvariant();
        await File.WriteAllTextAsync(
            Path.Combine(previewRoot, "preview-data.json"),
            SignedPreviewData(
                project.ProjectId,
                previewId,
                packageFile,
                FullSha(packageBytes),
                "asset-version",
                "2026-01-01T00:00:00.0000000+00:00",
                manifestSha256,
                manifestJson),
            Encoding.UTF8);
        var runId = await store.CreateRunAsync(project.ProjectId, project.WorkspaceId, "project-web-preview");
        await store.MarkRunStartedAsync(runId);
        await store.UpdateRunProgressAsync(runId, "project-web-preview", packageFile, "Generating Godot 3 browser preview.");
        await store.CompleteRunAsync(
            runId,
            "failed",
            1,
            "",
            "export failed",
            """
            {"run_type":"project-web-preview","package_file":"Towerdemo2-v0.1.20260627.002.zip","failure_code":"godot3_export_failed","mode":"godot3-html5-towerdemo2-template-subset"}
            """);

        var service = new ProjectWebPreviewService(store, options);
        var status = await service.ResolvePreviewForPackageAsync(project, packageFile);

        status.Status.Should().Be("ready");
        status.PreviewUrl.Should().NotBeNullOrWhiteSpace();
        status.RunId.Should().Be(runId);
        status.FailureCode.Should().Be("godot3_export_failed");
        status.FidelityTier.Should().Be("template_high_fidelity");
        status.PlayableSurface.Should().Be("towerdemo2_high_fidelity_subset");
    }

    [Fact]
    public async Task ResolvePreviewForPackageAsync_TreatsLegacyPreviewDataAsNotGeneratedButKeepsGuestReadback()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-web-preview-legacy-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-web-preview-legacy-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, Path.Combine(workspaceRoot.Path, "metadata.sqlite3"));
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("web-preview-legacy-user", 1);
        var projectId = await CreateProjectAsync(store, options, account.AccountId);
        var project = (await store.GetProjectSnapshotAsync(projectId))!;
        var packageFile = "Towerdemo2-v0.1.20260627.002.zip";
        var packageBytes = Encoding.UTF8.GetBytes("fake zip bytes");
        WritePackage(project.RepoPath, packageFile, packageBytes);
        var previewId = $"{Path.GetFileNameWithoutExtension(packageFile)}-{ShortSha(packageBytes)}";
        var previewRoot = Path.Combine(project.RepoPath, "exports", "web-previews", previewId);
        Directory.CreateDirectory(Path.Combine(previewRoot, "web"));
        await File.WriteAllTextAsync(Path.Combine(previewRoot, "web", "index.html"), "<html></html>", Encoding.UTF8);
        await File.WriteAllTextAsync(
            Path.Combine(previewRoot, "preview-data.json"),
            SignedLegacyPreviewData(
                project.ProjectId,
                previewId,
                packageFile,
                FullSha(packageBytes),
                "asset-version",
                "2026-01-01T00:00:00.0000000+00:00"),
            Encoding.UTF8);

        var service = new ProjectWebPreviewService(store, options);
        var status = await service.ResolvePreviewForPackageAsync(project, packageFile);
        var read = await service.ReadPreviewAsync(project.ProjectId, previewId, "index.html");

        status.Status.Should().Be("stale");
        status.PreviewId.Should().Be(previewId);
        status.PreviewUrl.Should().BeNull();
        status.FailureCode.Should().Be("converter_schema_outdated");
        read.Should().NotBeNull();
    }

    [Fact]
    public async Task ResolvePreviewForPackageAsync_RejectsUnsignedPreviewData()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-web-preview-unsigned-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-web-preview-unsigned-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, Path.Combine(workspaceRoot.Path, "metadata.sqlite3"));
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("web-preview-unsigned-user", 1);
        var projectId = await CreateProjectAsync(store, options, account.AccountId);
        var project = (await store.GetProjectSnapshotAsync(projectId))!;
        var packageFile = "Towerdemo2-v0.1.20260627.002.zip";
        var packageBytes = Encoding.UTF8.GetBytes("fake zip bytes");
        WritePackage(project.RepoPath, packageFile, packageBytes);
        var previewId = $"{Path.GetFileNameWithoutExtension(packageFile)}-{ShortSha(packageBytes)}";
        var previewRoot = Path.Combine(project.RepoPath, "exports", "web-previews", previewId);
        Directory.CreateDirectory(Path.Combine(previewRoot, "web"));
        await File.WriteAllTextAsync(Path.Combine(previewRoot, "web", "index.html"), "<html></html>", Encoding.UTF8);
        await File.WriteAllTextAsync(Path.Combine(previewRoot, "preview-data.json"), """
        {"mode":"godot3-html5-towerdemo2-template-subset","created_utc":"2026-01-01T00:00:00.0000000+00:00"}
        """, Encoding.UTF8);

        var service = new ProjectWebPreviewService(store, options);
        var status = await service.ResolvePreviewForPackageAsync(project, packageFile);
        var read = await service.ReadPreviewAsync(project.ProjectId, previewId, "index.html");

        status.Status.Should().Be("not_generated");
        read.Should().BeNull();
    }

    [Fact]
    public async Task ResolvePreviewsForPackages_UsesProvidedRunsForMultiplePackages()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-web-preview-batch-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-web-preview-batch-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, Path.Combine(workspaceRoot.Path, "metadata.sqlite3"));
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("web-preview-batch-user", 1);
        var projectId = await CreateProjectAsync(store, options, account.AccountId);
        var project = (await store.GetProjectSnapshotAsync(projectId))!;
        var failedPackage = "Towerdemo2-v0.1.20260627.002.zip";
        var queuedPackage = "Towerdemo2-v0.1.20260627.003.zip";
        WritePackage(project.RepoPath, failedPackage, "failed package bytes");
        WritePackage(project.RepoPath, queuedPackage, "queued package bytes");
        var failedRunId = await store.CreateRunAsync(project.ProjectId, project.WorkspaceId, "project-web-preview");
        await store.MarkRunStartedAsync(failedRunId);
        await store.CompleteRunAsync(
            failedRunId,
            "failed",
            1,
            "",
            "export failed",
            $$"""
            {"run_type":"project-web-preview","package_file":"{{failedPackage}}","failure_code":"godot3_export_failed","mode":"godot3-html5-towerdemo2-template-subset"}
            """);
        var queuedRunId = await store.CreateRunAsync(project.ProjectId, project.WorkspaceId, "project-web-preview");
        await store.UpdateRunProgressAsync(queuedRunId, "project-web-preview", queuedPackage, "Queued Godot 3 browser preview.");
        var runs = await store.ListRunsForProjectAsync(project.ProjectId);
        var service = new ProjectWebPreviewService(store, options);

        var statuses = service.ResolvePreviewsForPackages(project, [failedPackage, queuedPackage], runs);

        statuses[failedPackage].Status.Should().Be("failed");
        statuses[failedPackage].FailureCode.Should().Be("godot3_export_failed");
        statuses[queuedPackage].Status.Should().Be("queued");
        statuses[queuedPackage].RunId.Should().Be(queuedRunId);
    }

    [Fact]
    public void ProjectPackageService_UsesBatchedWebPreviewStatusResolution()
    {
        var sourcePath = Path.GetFullPath(Path.Combine(
            AppContext.BaseDirectory,
            "..",
            "..",
            "..",
            "..",
            "PhaseA.Platform",
            "Readback",
            "ProjectPackageService.cs"));
        var source = File.ReadAllText(sourcePath);
        var listPackagesStart = source.IndexOf("public async Task<ProjectPackageListResult?> ListPackagesAsync", StringComparison.Ordinal);
        var listPackagesEnd = source.IndexOf("public async Task<ProjectPackageReadResult?> ReadPackageAsync", StringComparison.Ordinal);
        listPackagesStart.Should().BeGreaterThanOrEqualTo(0);
        listPackagesEnd.Should().BeGreaterThan(listPackagesStart);
        var listPackagesSource = source[listPackagesStart..listPackagesEnd];

        source.Should().Contain("ResolvePreviewsForPackages(");
        source.Should().NotContain("await _webPreviews.ResolvePreviewForPackageAsync(project, fileName");
        listPackagesSource.Should().Contain("ListArtifactsForRunsAsync(");
        listPackagesSource.Should().NotContain("ListArtifactsForRunAsync(");
    }

    [Fact]
    public async Task GenerateQueuedPreviewAsync_WaitsForDedicatedWebPreviewQueue()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-web-preview-dedicated-queue-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-web-preview-dedicated-queue-repo");
        // ADR-0005: configure a deterministic failing engine for this queue-boundary test.
        using var godotRoot = TempDirectory.Create("phase-a-web-preview-queue-engine");
        var fakeGodot = Path.Combine(godotRoot.Path, "Godot_v3.6.2-stable_win64.exe");
        await File.WriteAllTextAsync(fakeGodot, "fixture engine", Encoding.UTF8);
        var previousGodot = Environment.GetEnvironmentVariable("PHASEA_GODOT3_BIN");
        Environment.SetEnvironmentVariable("PHASEA_GODOT3_BIN", fakeGodot);
        try
        {
            var options = Options(workspaceRoot.Path, repoRoot.Path, Path.Combine(workspaceRoot.Path, "metadata.sqlite3"));
            await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
            var store = new PhaseAMetadataStore(database.ConnectionString, options);
            var account = await store.CreateUserAccountAsync("web-preview-dedicated-queue-user", 1);
            var projectId = await CreateProjectAsync(store, options, account.AccountId);
            var project = (await store.GetProjectSnapshotAsync(projectId))!;
            var packageFile = "ExperimentalPreview-v0.1.20260627.001.zip";
            WriteGenericGodotPackage(project.RepoPath, packageFile, "ExperimentalPreview", "Experimental Preview");
            var webPreviewQueue = new HeavyRunnerQueueService(TimeSpan.FromSeconds(30), maxConcurrentRuns: 1);
            await using var queueBlocker = await webPreviewQueue.EnterAsync(
                "held-web-preview-run",
                account.AccountId,
                project.ProjectId,
                "project-web-preview");
            var exportRunner = new FailingQueueWebExportRunner();
            var service = new ProjectWebPreviewService(store, options, webPreviewQueue,
                new ProjectWebPreviewConcurrencyLimiter(maxConcurrentWebPreviewsPerAccount: 1),
                exportRunner);
            var queued = await service.QueuePreviewAsync(account.AccountId, project.ProjectId, packageFile);
    
            var generation = service.GenerateQueuedPreviewAsync(account.AccountId, project.ProjectId, packageFile, queued.RunId);
            await Task.Delay(200);
    
            var runWhileQueued = await store.GetRunSnapshotAsync(queued.RunId);
            var queueReadback = webPreviewQueue.GetReadback(account.AccountId, includeAll: true);
            runWhileQueued!.Status.Should().Be("queued");
            queueReadback.QueuedCount.Should().Be(1);
            queueReadback.Items.Single().RunId.Should().Be(queued.RunId);
    
            await queueBlocker.DisposeAsync();
            // ADR-0005: fixture drain readiness; export failure and FIFO assertions remain unchanged.
            var result = await generation.WaitAsync(TimeSpan.FromSeconds(30));
            result.Status.Should().Be("godot3_export_failed");
            // ADR-0005: a failed release export is followed by the existing debug fallback.
            exportRunner.Commands.Select(command => command.Arguments.Single(argument =>
                argument is "--export" or "--export-debug")).Should().Equal("--export", "--export-debug");
            webPreviewQueue.GetReadback(account.AccountId, includeAll: true).QueuedCount.Should().Be(0);
        }
        finally { Environment.SetEnvironmentVariable("PHASEA_GODOT3_BIN", previousGodot); }
    }

    [Fact]
    public async Task QueuePreviewAsync_FailsFast_WhenAccountWebPreviewLimitIsHeld()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-web-preview-account-limit-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-web-preview-account-limit-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, Path.Combine(workspaceRoot.Path, "metadata.sqlite3"));
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("web-preview-account-limit-user", 1);
        var projectId = await CreateProjectAsync(store, options, account.AccountId);
        var project = (await store.GetProjectSnapshotAsync(projectId))!;
        var packageFile = "Towerdemo2-v0.1.20260627.002.zip";
        WriteMinimalGodotPackage(project.RepoPath, packageFile);
        var webPreviewQueue = new HeavyRunnerQueueService(TimeSpan.FromSeconds(30), maxConcurrentRuns: 1);
        var accountLimiter = new ProjectWebPreviewConcurrencyLimiter(maxConcurrentWebPreviewsPerAccount: 1);
        var held = await accountLimiter.TryAcquireAsync(account.AccountId);
        await using var heldLease = held.Lease!;
        var service = new ProjectWebPreviewService(store, options, webPreviewQueue, accountLimiter);
        var queued = await service.QueuePreviewAsync(account.AccountId, project.ProjectId, packageFile);

        queued.Status.Should().Be("failed");
        queued.FailureCode.Should().Be("user_web_preview_concurrency_limit_exceeded");
        queued.RunId.Should().BeEmpty();
        webPreviewQueue.GetReadback(account.AccountId, includeAll: true).QueuedCount.Should().Be(0);
    }

    [Fact]
    public async Task GenerateQueuedPreviewAsync_RecordsProjectBusyFailure_WhenRunnerLockIsTakenBeforeExecution()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-web-preview-project-busy-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-web-preview-project-busy-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, Path.Combine(workspaceRoot.Path, "metadata.sqlite3"));
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("web-preview-project-busy-user", 1);
        var projectId = await CreateProjectAsync(store, options, account.AccountId);
        var project = (await store.GetProjectSnapshotAsync(projectId))!;
        var packageFile = "BusyPreview-v0.1.20260627.001.zip";
        WriteMinimalGodotPackage(project.RepoPath, packageFile);
        var service = new ProjectWebPreviewService(store, options);
        var queued = await service.QueuePreviewAsync(account.AccountId, project.ProjectId, packageFile);
        var lockRunId = await store.CreateRunAsync(project.ProjectId, project.WorkspaceId, "prototype-7day-playable");
        (await store.TryAcquireRunnerLockAsync(project.ProjectId, lockRunId)).Should().BeTrue();

        var result = await service.GenerateQueuedPreviewAsync(account.AccountId, project.ProjectId, packageFile, queued.RunId);
        var run = await store.GetRunSnapshotAsync(queued.RunId);

        result.Status.Should().Be("project_busy");
        result.FailureCode.Should().Be("project_busy");
        run!.Status.Should().Be("failed");
        run.EvidenceJson.Should().NotBeNullOrWhiteSpace();
        using var evidence = JsonDocument.Parse(run.EvidenceJson!);
        evidence.RootElement.GetProperty("failure_code").GetString().Should().Be("project_busy");
    }

    [Fact]
    public async Task GeneratePreviewAsync_UsesGenericConverterForNonTowerdemoGodotPackage()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-web-preview-generic-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-web-preview-generic-repo");
        using var godotRoot = TempDirectory.Create("phase-a-web-preview-godot3-bin");
        var fakeGodot = Path.Combine(godotRoot.Path, "Godot_v3.6.2-stable_win64.exe");
        await File.WriteAllTextAsync(fakeGodot, "fake godot", Encoding.UTF8);
        var previousGodot = Environment.GetEnvironmentVariable("PHASEA_GODOT3_BIN");
        Environment.SetEnvironmentVariable("PHASEA_GODOT3_BIN", fakeGodot);
        try
        {
            var options = Options(workspaceRoot.Path, repoRoot.Path, Path.Combine(workspaceRoot.Path, "metadata.sqlite3"));
            await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
            var store = new PhaseAMetadataStore(database.ConnectionString, options);
            var account = await store.CreateUserAccountAsync("web-preview-generic-user", 1);
            var projectId = await CreateProjectAsync(store, options, account.AccountId);
            var project = (await store.GetProjectSnapshotAsync(projectId))!;
            var packageFile = "ExperimentalPreview-v0.1.20260627.001.zip";
            WriteGenericGodotPackage(project.RepoPath, packageFile, "ExperimentalPreview", "Experimental Preview");
            var runner = new FakeGodot3WebExportRunner();
            var service = new ProjectWebPreviewService(
                store,
                options,
                new HeavyRunnerQueueService(TimeSpan.FromSeconds(30), maxConcurrentRuns: 1),
                new ProjectWebPreviewConcurrencyLimiter(maxConcurrentWebPreviewsPerAccount: 1),
                runner);

            var result = await service.GeneratePreviewAsync(account.AccountId, project.ProjectId, packageFile);
            var previewDataPath = Path.Combine(project.RepoPath, "exports", "web-previews", result.PreviewId, "preview-data.json");
            var manifestPath = Path.Combine(project.RepoPath, "exports", "web-previews", result.PreviewId, "web-preview-manifest.json");
            var previewContractPath = Path.Combine(project.RepoPath, "exports", "web-previews", result.PreviewId, "web", "preview-contract.json");
            var previewPackageDataPath = Path.Combine(project.RepoPath, "exports", "web-previews", result.PreviewId, "web", "preview-package-data.json");
            var read = await service.ReadPreviewAsync(project.ProjectId, result.PreviewId, "index.html");
            var contractRead = await service.ReadPreviewAsync(project.ProjectId, result.PreviewId, "preview-contract.json");
            var status = await service.ResolvePreviewForPackageAsync(project, packageFile);
            using var previewData = JsonDocument.Parse(await File.ReadAllTextAsync(previewDataPath, Encoding.UTF8));
            using var previewPackageData = JsonDocument.Parse(await File.ReadAllTextAsync(previewPackageDataPath, Encoding.UTF8));
            using var previewContract = JsonDocument.Parse(await File.ReadAllTextAsync(previewContractPath, Encoding.UTF8));
            var manifestSha256 = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(await File.ReadAllTextAsync(manifestPath, Encoding.UTF8)))).ToLowerInvariant();

            result.Status.Should().Be("succeeded");
            result.Mode.Should().Be("godot3-html5-generic-package-preview");
            runner.Commands.Should().HaveCount(1);
            runner.Commands[0].Arguments.Should().Contain("--export");
            runner.Commands[0].Arguments.Should().NotContain("--export-debug");
            read.Should().NotBeNull();
            contractRead.Should().NotBeNull();
            previewData.RootElement.GetProperty("schema_version").GetString().Should().Be("phasea-web-preview-v5");
            previewData.RootElement.GetProperty("manifest_sha256").GetString().Should().Be(manifestSha256);
            previewData.RootElement.GetProperty("godot3_export_mode").GetString().Should().Be("release");
            previewData.RootElement.GetProperty("converter_id").GetString().Should().Be("godot-package-generic-playable-preview");
            previewData.RootElement.GetProperty("playable_preview_contract").GetProperty("schema_version").GetString().Should().Be("phasea-playable-preview-contract-v1");
            previewPackageData.RootElement.GetProperty("playable_preview_contract").GetProperty("entities").EnumerateArray().Should().Contain(entity =>
                entity.GetProperty("label").GetString() == "StartNode" &&
                entity.GetProperty("role").GetString() == "entry_scene");
            previewData.RootElement.GetProperty("game_type_id").GetString().Should().BeEmpty();
            previewData.RootElement.GetProperty("game_type_guide").GetString().Should().BeEmpty();
            previewData.RootElement
                .GetProperty("web_preview_manifest")
                .GetProperty("detected_capabilities")
                .EnumerateArray()
                .Select(item => item.GetString())
                .Should()
                .Contain("playable_preview_contract");
            var detectedCapabilities = previewData.RootElement
                .GetProperty("web_preview_manifest")
                .GetProperty("detected_capabilities")
                .EnumerateArray()
                .Select(item => item.GetString())
                .ToArray();
            detectedCapabilities.Should().Contain("visual_asset_hints");
            detectedCapabilities.Should().Contain("input_map_hints");
            detectedCapabilities.Should().Contain("script_behavior_hints");
            detectedCapabilities.Should().Contain("scene_graph_hints");
            previewData.RootElement
                .GetProperty("web_preview_manifest")
                .GetProperty("visual_asset_hints")
                .EnumerateArray()
                .Should()
                .Contain(item => item.GetProperty("preview_resource_path").GetString() == "res://PreviewAssets/Game.Godot-Prototypes-ExperimentalPreview-Art-player.png");
            previewData.RootElement
                .GetProperty("web_preview_manifest")
                .GetProperty("input_map_hints")
                .EnumerateArray()
                .Should()
                .Contain(item => item.GetProperty("action").GetString() == "dash");
            previewData.RootElement
                .GetProperty("web_preview_manifest")
                .GetProperty("script_behavior_hints")
                .EnumerateArray()
                .Should()
                .Contain(item => item.GetProperty("path").GetString() == "Game.Godot/Prototypes/ExperimentalPreview/PlayerController.gd");
            previewData.RootElement
                .GetProperty("web_preview_manifest")
                .GetProperty("scene_graph_hints")
                .EnumerateArray()
                .Should()
                .Contain(item =>
                    item.GetProperty("path").GetString() == "Game.Godot/Prototypes/ExperimentalPreview/ExperimentalPreviewPrototype.tscn" &&
                    item.GetProperty("root_node_type").GetString() == "Node2D" &&
                    item.GetProperty("script_paths").EnumerateArray().Any(script => script.GetString() == "res://Game.Godot/Prototypes/ExperimentalPreview/PlayerController.gd") &&
                    item.GetProperty("texture_paths").EnumerateArray().Any(texture => texture.GetString() == "res://Game.Godot/Prototypes/ExperimentalPreview/Art/player.png"));
            File.Exists(Path.Combine(project.RepoPath, "exports", "web-previews", result.PreviewId, "godot3-project", "PreviewAssets", "Game.Godot-Prototypes-ExperimentalPreview-Art-player.png")).Should().BeTrue();
            var exportPresets = await File.ReadAllTextAsync(Path.Combine(project.RepoPath, "exports", "web-previews", result.PreviewId, "godot3-project", "export_presets.cfg"), Encoding.UTF8);
            exportPresets.Should().Contain("PreviewAssets/*.png");
            previewData.RootElement
                .GetProperty("web_preview_manifest")
                .GetProperty("conversion_contract")
                .GetProperty("data_sources")
                .EnumerateArray()
                .Select(item => item.GetString())
                .Should()
                .Contain("playable-preview-contract.json");
            previewData.RootElement
                .GetProperty("web_preview_manifest")
                .GetProperty("conversion_contract")
                .GetProperty("fidelity_tier")
                .GetString()
                .Should()
                .Be("generic_package_preview");
            previewData.RootElement
                .GetProperty("web_preview_manifest")
                .GetProperty("game_type_source")
                .GetString()
                .Should()
                .Be("Experimental Preview");
            previewContract.RootElement.GetProperty("schema_version").GetString().Should().Be("phasea-web-preview-contract-v1");
            previewContract.RootElement.GetProperty("package_file").GetString().Should().Be(packageFile);
            previewContract.RootElement.GetProperty("package_sha256").GetString().Should().Be(previewData.RootElement.GetProperty("package_sha256").GetString());
            previewContract.RootElement.GetProperty("mode").GetString().Should().Be(result.Mode);
            previewContract.RootElement.GetProperty("converter_id").GetString().Should().Be("godot-package-generic-playable-preview");
            previewContract.RootElement.GetProperty("manifest_sha256").GetString().Should().Be(manifestSha256);
            previewContract.RootElement.GetProperty("fidelity_tier").GetString().Should().Be("generic_package_preview");
            previewContract.RootElement.GetProperty("playable_surface").GetString().Should().Be("generic_package_exploration_shell");
            status.Status.Should().Be("ready");
            status.FidelityTier.Should().Be("generic_package_preview");
            status.PlayableSurface.Should().Be("generic_package_exploration_shell");
            status.GameTypeId.Should().BeEmpty();
            status.GameTypeGuide.Should().BeEmpty();
        }
        finally
        {
            Environment.SetEnvironmentVariable("PHASEA_GODOT3_BIN", previousGodot);
        }
    }

    [Fact]
    public async Task GeneratePreviewAsync_UsesGeneratedDedicatedAdapterForNonTowerdemoPackage()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-web-preview-generic-dedicated-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-web-preview-generic-dedicated-repo");
        using var godotRoot = TempDirectory.Create("phase-a-web-preview-generic-dedicated-godot3-bin");
        var fakeGodot = Path.Combine(godotRoot.Path, "Godot_v3.6.2-stable_win64.exe");
        await File.WriteAllTextAsync(fakeGodot, "fake godot", Encoding.UTF8);
        var previousGodot = Environment.GetEnvironmentVariable("PHASEA_GODOT3_BIN");
        Environment.SetEnvironmentVariable("PHASEA_GODOT3_BIN", fakeGodot);
        try
        {
            var options = Options(workspaceRoot.Path, repoRoot.Path, Path.Combine(workspaceRoot.Path, "metadata.sqlite3"));
            await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
            var store = new PhaseAMetadataStore(database.ConnectionString, options);
            var account = await store.CreateUserAccountAsync("web-preview-generic-dedicated-user", 1);
            var projectId = await CreateProjectAsync(store, options, account.AccountId);
            var project = (await store.GetProjectSnapshotAsync(projectId))!;
            var packageFile = "GenericAdventure-v0.1.20260628.006.zip";
            WriteGenericGodotPackage(project.RepoPath, packageFile, "GenericAdventure");
            var godotRunner = new FakeGodot3WebExportRunner();
            var dedicatedRunner = new DedicatedAdapterRunner("""
            extends KinematicBody2D

            var velocity = Vector2.ZERO

            func _ready():
                var floor = ColorRect.new()
                floor.name = "Floor"
                print("codex dedicated adapter")

            func _physics_process(delta):
                velocity = move_and_slide(velocity)
            """);
            var dedicatedService = new ProjectWebPreviewDedicatedAdapterService(options, dedicatedRunner);
            var service = new ProjectWebPreviewService(
                store,
                options,
                new HeavyRunnerQueueService(TimeSpan.FromSeconds(30), maxConcurrentRuns: 1),
                new ProjectWebPreviewConcurrencyLimiter(maxConcurrentWebPreviewsPerAccount: 1),
                godotRunner,
                dedicatedAdapterService: dedicatedService);

            var result = await service.GeneratePreviewAsync(account.AccountId, project.ProjectId, packageFile);
            var previewDataPath = Path.Combine(project.RepoPath, "exports", "web-previews", result.PreviewId, "preview-data.json");
            var adapterVersion = Path.GetFileNameWithoutExtension(packageFile);
            var dedicatedMainScriptPath = Path.Combine(project.RepoPath, "exports", "web-preview-dedicated-adapters", adapterVersion, "Main.gd");
            var dedicatedManifestPath = Path.Combine(project.RepoPath, "exports", "web-preview-dedicated-adapters", adapterVersion, "adapter-manifest.json");
            using var previewData = JsonDocument.Parse(await File.ReadAllTextAsync(previewDataPath, Encoding.UTF8));
            using var dedicatedManifest = JsonDocument.Parse(await File.ReadAllTextAsync(dedicatedManifestPath, Encoding.UTF8));
            var resolution = previewData.RootElement.GetProperty("dedicated_adapter_resolution");

            result.Status.Should().Be("succeeded");
            result.Mode.Should().NotBe("godot3-html5-towerdemo2-template-subset");
            dedicatedRunner.Commands.Should().HaveCount(1);
            dedicatedRunner.Commands[0].Arguments.Should().Contain("workspace-write");
            dedicatedRunner.Commands[0].Arguments.Should().NotContain("--json");
            dedicatedRunner.Commands[0].StandardInput.Should().Contain("Write a complete GDScript file only");
            dedicatedRunner.Commands[0].StandardInput.Should().Contain("Prefer `extends Node2D`");
            dedicatedRunner.Commands[0].StandardInput.Should().Contain("child `KinematicBody2D` player");
            dedicatedRunner.Commands[0].StandardInput.Should().Contain("CollisionShape2D");
            dedicatedRunner.Commands[0].StandardInput.Should().Contain("move_and_slide");
            dedicatedRunner.Commands[0].StandardInput.Should().Contain("Avoid GDScript built-in function names");
            dedicatedRunner.Commands[0].StandardInput.Should().Contain("visual_asset_hints");
            dedicatedRunner.Commands[0].StandardInput.Should().Contain("input_map_hints");
            dedicatedRunner.Commands[0].StandardInput.Should().Contain("script_behavior_hints");
            dedicatedRunner.Commands[0].StandardInput.Should().Contain("scene_graph_hints");
            dedicatedRunner.Commands[0].StandardInput.Should().Contain("ImageTexture");
            dedicatedRunner.Commands[0].StandardInput.Should().Contain("call_deferred");
            dedicatedRunner.Commands[0].StandardInput.Should().Contain("get_parent().add_child");
            dedicatedRunner.Commands[0].StandardInput.Should().Contain("do not implement click-to-move");
            dedicatedRunner.Commands[0].StandardInput.Should().Contain("Mouse left should fire/attack");
            dedicatedRunner.Commands[0].StandardInput.Should().Contain("Do not add numbered selection shortcuts");
            dedicatedRunner.Commands[0].StandardInput.Should().Contain("must not contain KEY_1");
            dedicatedRunner.Commands[0].StandardInput.Should().Contain("visibly reduce HP/armor");
            godotRunner.MainScripts.Should().ContainSingle(script => script.Contains("codex dedicated adapter", StringComparison.Ordinal));
            godotRunner.MainScripts.Single().Should().Contain("var floor_node = ColorRect.new()");
            godotRunner.MainScripts.Single().Should().NotContain("var floor =");
            godotRunner.MainScenes.Should().ContainSingle(scene => scene.Contains("type=\"KinematicBody2D\"", StringComparison.Ordinal));
            File.Exists(dedicatedMainScriptPath).Should().BeTrue();
            resolution.GetProperty("status").GetString().Should().Be("generated_by_codex");
            resolution.GetProperty("codex_invoked").GetBoolean().Should().BeTrue();
            dedicatedManifest.RootElement.GetProperty("schema_version").GetString().Should().Be("phasea-web-preview-dedicated-adapter-v1");
            dedicatedManifest.RootElement.GetProperty("generator_version").GetString().Should().Be("phasea-project-dedicated-godot3-adapter-v8");
            dedicatedManifest.RootElement.GetProperty("source").GetString().Should().Be("codex-dedicated-adapter");
            dedicatedManifest.RootElement.GetProperty("package_file").GetString().Should().Be(packageFile);
        }
        finally
        {
            Environment.SetEnvironmentVariable("PHASEA_GODOT3_BIN", previousGodot);
        }
    }

    [Fact]
    public async Task GeneratePreviewAsync_DoesNotCacheDedicatedFallbackForNonTowerdemoPackage()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-web-preview-generic-dedicated-fallback-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-web-preview-generic-dedicated-fallback-repo");
        using var godotRoot = TempDirectory.Create("phase-a-web-preview-generic-dedicated-fallback-godot3-bin");
        var fakeGodot = Path.Combine(godotRoot.Path, "Godot_v3.6.2-stable_win64.exe");
        await File.WriteAllTextAsync(fakeGodot, "fake godot", Encoding.UTF8);
        var previousGodot = Environment.GetEnvironmentVariable("PHASEA_GODOT3_BIN");
        Environment.SetEnvironmentVariable("PHASEA_GODOT3_BIN", fakeGodot);
        try
        {
            var options = Options(workspaceRoot.Path, repoRoot.Path, Path.Combine(workspaceRoot.Path, "metadata.sqlite3"));
            await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
            var store = new PhaseAMetadataStore(database.ConnectionString, options);
            var account = await store.CreateUserAccountAsync("web-preview-generic-dedicated-fallback-user", 1);
            var projectId = await CreateProjectAsync(store, options, account.AccountId);
            var project = (await store.GetProjectSnapshotAsync(projectId))!;
            var packageFile = "PlainDemo-v0.1.20260628.007.zip";
            WriteGenericGodotPackage(project.RepoPath, packageFile, "PlainDemo");
            var godotRunner = new FakeGodot3WebExportRunner();
            var dedicatedRunner = new FailingDedicatedAdapterRunner();
            var dedicatedService = new ProjectWebPreviewDedicatedAdapterService(options, dedicatedRunner);
            var service = new ProjectWebPreviewService(
                store,
                options,
                new HeavyRunnerQueueService(TimeSpan.FromSeconds(30), maxConcurrentRuns: 1),
                new ProjectWebPreviewConcurrencyLimiter(maxConcurrentWebPreviewsPerAccount: 1),
                godotRunner,
                dedicatedAdapterService: dedicatedService);

            var result = await service.GeneratePreviewAsync(account.AccountId, project.ProjectId, packageFile);
            var previewDataPath = Path.Combine(project.RepoPath, "exports", "web-previews", result.PreviewId, "preview-data.json");
            var adapterVersion = Path.GetFileNameWithoutExtension(packageFile);
            var dedicatedMainScriptPath = Path.Combine(project.RepoPath, "exports", "web-preview-dedicated-adapters", adapterVersion, "Main.gd");
            var dedicatedManifestPath = Path.Combine(project.RepoPath, "exports", "web-preview-dedicated-adapters", adapterVersion, "adapter-manifest.json");
            using var previewData = JsonDocument.Parse(await File.ReadAllTextAsync(previewDataPath, Encoding.UTF8));
            var resolution = previewData.RootElement.GetProperty("dedicated_adapter_resolution");
            var generatedScript = godotRunner.MainScripts.Single();

            result.Status.Should().Be("succeeded");
            dedicatedRunner.Commands.Should().HaveCount(1);
            dedicatedRunner.Commands[0].TotalTimeout.Should().Be(TimeSpan.FromMinutes(15));
            dedicatedRunner.Commands[0].InactivityTimeout.Should().Be(TimeSpan.FromMinutes(8));
            File.Exists(dedicatedMainScriptPath).Should().BeFalse();
            File.Exists(dedicatedManifestPath).Should().BeFalse();
            resolution.GetProperty("status").GetString().Should().Be("generated_by_fallback");
            resolution.GetProperty("adapter_path").GetString().Should().BeEmpty();
            generatedScript.Should().NotContain("塔防试玩");
            generatedScript.Should().NotContain("放置防御塔");
        }
        finally
        {
            Environment.SetEnvironmentVariable("PHASEA_GODOT3_BIN", previousGodot);
        }
    }

    [Fact]
    public async Task GeneratePreviewAsync_UsesTowerdemo2DedicatedAdapterWhenSemanticSignatureMatches()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-web-preview-towerdemo2-changed-scene-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-web-preview-towerdemo2-changed-scene-repo");
        using var godotRoot = TempDirectory.Create("phase-a-web-preview-towerdemo2-changed-scene-godot3-bin");
        var fakeGodot = Path.Combine(godotRoot.Path, "Godot_v3.6.2-stable_win64.exe");
        await File.WriteAllTextAsync(fakeGodot, "fake godot", Encoding.UTF8);
        var previousGodot = Environment.GetEnvironmentVariable("PHASEA_GODOT3_BIN");
        Environment.SetEnvironmentVariable("PHASEA_GODOT3_BIN", fakeGodot);
        try
        {
            var options = Options(workspaceRoot.Path, repoRoot.Path, Path.Combine(workspaceRoot.Path, "metadata.sqlite3"));
            await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
            var store = new PhaseAMetadataStore(database.ConnectionString, options);
            var account = await store.CreateUserAccountAsync("web-preview-towerdemo2-changed-scene-user", 1);
            var projectId = await CreateProjectAsync(store, options, account.AccountId);
            var project = (await store.GetProjectSnapshotAsync(projectId))!;
            var packageFile = "Towerdemo2-v0.1.20260628.004.zip";
            WriteTowerdemo2PackageWithChangedScene(project.RepoPath, packageFile);
            var runner = new FakeGodot3WebExportRunner();
            var service = new ProjectWebPreviewService(
                store,
                options,
                new HeavyRunnerQueueService(TimeSpan.FromSeconds(30), maxConcurrentRuns: 1),
                new ProjectWebPreviewConcurrencyLimiter(maxConcurrentWebPreviewsPerAccount: 1),
                runner);

            var result = await service.GeneratePreviewAsync(account.AccountId, project.ProjectId, packageFile);
            var previewDataPath = Path.Combine(project.RepoPath, "exports", "web-previews", result.PreviewId, "preview-data.json");
            var adapterVersion = Path.GetFileNameWithoutExtension(packageFile);
            var dedicatedAdapterRoot = Path.Combine(project.RepoPath, "exports", "web-preview-dedicated-adapters", adapterVersion);
            var dedicatedMainScriptPath = Path.Combine(dedicatedAdapterRoot, "Main.gd");
            var dedicatedManifestPath = Path.Combine(dedicatedAdapterRoot, "adapter-manifest.json");
            using var previewData = JsonDocument.Parse(await File.ReadAllTextAsync(previewDataPath, Encoding.UTF8));
            using var dedicatedManifest = JsonDocument.Parse(await File.ReadAllTextAsync(dedicatedManifestPath, Encoding.UTF8));
            var manifest = previewData.RootElement.GetProperty("web_preview_manifest");
            var contract = manifest.GetProperty("conversion_contract");
            var detectedTemplates = manifest
                .GetProperty("detected_templates")
                .EnumerateArray()
                .Select(item => item.GetString())
                .ToArray();
            var status = await service.ResolvePreviewForPackageAsync(project, packageFile);

            result.Status.Should().Be("succeeded");
            result.Mode.Should().Be("godot3-html5-towerdemo2-template-subset");
            previewData.RootElement.GetProperty("converter_id").GetString().Should().Be("towerdemo2-template-subset");
            previewData.RootElement.GetProperty("source_scene_sha256").GetString().Should().NotBeEmpty();
            previewData.RootElement.GetProperty("text_catalog_sha256").GetString().Should().NotBeEmpty();
            previewData.RootElement.GetProperty("game_type_id").GetString().Should().BeEmpty();
            previewData.RootElement.GetProperty("game_type_guide").GetString().Should().BeEmpty();
            detectedTemplates.Should().NotContain("towerdemo2");
            contract.GetProperty("fidelity_tier").GetString().Should().Be("template_high_fidelity");
            contract.GetProperty("playable_surface").GetString().Should().Be("towerdemo2_high_fidelity_subset");
            status.Status.Should().Be("ready");
            status.FidelityTier.Should().Be("template_high_fidelity");
            status.PlayableSurface.Should().Be("towerdemo2_high_fidelity_subset");
            status.GameTypeId.Should().BeEmpty();
            status.GameTypeGuide.Should().BeEmpty();
            File.Exists(dedicatedMainScriptPath).Should().BeTrue();
            dedicatedManifest.RootElement.GetProperty("schema_version").GetString().Should().Be("phasea-web-preview-dedicated-adapter-v1");
            dedicatedManifest.RootElement.GetProperty("source").GetString().Should().Be("towerdemo2-built-in-template");
            dedicatedManifest.RootElement.GetProperty("adapter_version").GetString().Should().Be(adapterVersion);
            dedicatedManifest.RootElement.GetProperty("converter_id").GetString().Should().Be("towerdemo2-template-subset");
            dedicatedManifest.RootElement.GetProperty("adapter_source_sha256").GetString().Should().NotBeNullOrWhiteSpace();
            dedicatedManifest.RootElement.GetProperty("package_file").GetString().Should().Be(packageFile);
            dedicatedManifest.RootElement.GetProperty("package_sha256").GetString().Should().Be(previewData.RootElement.GetProperty("package_sha256").GetString());
        }
        finally
        {
            Environment.SetEnvironmentVariable("PHASEA_GODOT3_BIN", previousGodot);
        }
    }

    [Fact]
    public async Task GeneratePreviewAsync_ReusesTowerdemo2DedicatedAdapterForSamePackage()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-web-preview-towerdemo2-adapter-reuse-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-web-preview-towerdemo2-adapter-reuse-repo");
        using var godotRoot = TempDirectory.Create("phase-a-web-preview-towerdemo2-adapter-reuse-godot3-bin");
        var fakeGodot = Path.Combine(godotRoot.Path, "Godot_v3.6.2-stable_win64.exe");
        await File.WriteAllTextAsync(fakeGodot, "fake godot", Encoding.UTF8);
        var previousGodot = Environment.GetEnvironmentVariable("PHASEA_GODOT3_BIN");
        Environment.SetEnvironmentVariable("PHASEA_GODOT3_BIN", fakeGodot);
        try
        {
            var options = Options(workspaceRoot.Path, repoRoot.Path, Path.Combine(workspaceRoot.Path, "metadata.sqlite3"));
            await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
            var store = new PhaseAMetadataStore(database.ConnectionString, options);
            var account = await store.CreateUserAccountAsync("web-preview-towerdemo2-adapter-reuse-user", 1);
            var projectId = await CreateProjectAsync(store, options, account.AccountId);
            var project = (await store.GetProjectSnapshotAsync(projectId))!;
            var packageFile = "Towerdemo2-v0.1.20260628.005.zip";
            WriteTowerdemo2PackageWithChangedScene(project.RepoPath, packageFile);
            var runner = new FakeGodot3WebExportRunner();
            var service = new ProjectWebPreviewService(
                store,
                options,
                new HeavyRunnerQueueService(TimeSpan.FromSeconds(30), maxConcurrentRuns: 1),
                new ProjectWebPreviewConcurrencyLimiter(maxConcurrentWebPreviewsPerAccount: 1),
                runner);

            var first = await service.GeneratePreviewAsync(account.AccountId, project.ProjectId, packageFile);
            var adapterVersion = Path.GetFileNameWithoutExtension(packageFile);
            var dedicatedMainScriptPath = Path.Combine(project.RepoPath, "exports", "web-preview-dedicated-adapters", adapterVersion, "Main.gd");
            var cachedScript = """
            extends Control

            func _ready():
                print("cached dedicated adapter")
            """;
            await File.WriteAllTextAsync(dedicatedMainScriptPath, cachedScript, new UTF8Encoding(false));

            var second = await service.GeneratePreviewAsync(account.AccountId, project.ProjectId, packageFile);
            var generatedMainScript = runner.MainScripts.Last();

            first.Status.Should().Be("succeeded");
            second.Status.Should().Be("succeeded");
            runner.Commands.Should().HaveCount(2);
            generatedMainScript.Should().Be(cachedScript);
        }
        finally
        {
            Environment.SetEnvironmentVariable("PHASEA_GODOT3_BIN", previousGodot);
        }
    }

    [Fact]
    public async Task GeneratePreviewAsync_DoesNotBackfillTowerDefenseTypeForLegacyTowerdemoPackage()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-web-preview-legacy-tower-type-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-web-preview-legacy-tower-type-repo");
        using var godotRoot = TempDirectory.Create("phase-a-web-preview-legacy-tower-type-godot3-bin");
        var fakeGodot = Path.Combine(godotRoot.Path, "Godot_v3.6.2-stable_win64.exe");
        await File.WriteAllTextAsync(fakeGodot, "fake godot", Encoding.UTF8);
        var previousGodot = Environment.GetEnvironmentVariable("PHASEA_GODOT3_BIN");
        Environment.SetEnvironmentVariable("PHASEA_GODOT3_BIN", fakeGodot);
        try
        {
            var options = Options(workspaceRoot.Path, repoRoot.Path, Path.Combine(workspaceRoot.Path, "metadata.sqlite3"));
            await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
            var store = new PhaseAMetadataStore(database.ConnectionString, options);
            var account = await store.CreateUserAccountAsync("web-preview-legacy-tower-type-user", 1);
            var projectId = await CreateProjectAsync(store, options, account.AccountId);
            var project = (await store.GetProjectSnapshotAsync(projectId))!;
            var packageFile = "Towerdemo2-v0.1.20260627.004.zip";
            WriteLegacyTowerdemoPackage(project.RepoPath, packageFile);
            var runner = new FakeGodot3WebExportRunner();
            var service = new ProjectWebPreviewService(
                store,
                options,
                new HeavyRunnerQueueService(TimeSpan.FromSeconds(30), maxConcurrentRuns: 1),
                new ProjectWebPreviewConcurrencyLimiter(maxConcurrentWebPreviewsPerAccount: 1),
                runner);

            var result = await service.GeneratePreviewAsync(account.AccountId, project.ProjectId, packageFile);
            var previewDataPath = Path.Combine(project.RepoPath, "exports", "web-previews", result.PreviewId, "preview-data.json");
            using var previewData = JsonDocument.Parse(await File.ReadAllTextAsync(previewDataPath, Encoding.UTF8));

            result.Status.Should().Be("succeeded");
            result.Mode.Should().Be("godot3-html5-generic-package-preview");
            previewData.RootElement.GetProperty("game_type_id").GetString().Should().BeEmpty();
            previewData.RootElement.GetProperty("game_type_guide").GetString().Should().BeEmpty();
            previewData.RootElement.GetProperty("web_preview_manifest").GetProperty("game_type_id").GetString().Should().BeEmpty();
            previewData.RootElement.GetProperty("web_preview_manifest").GetProperty("game_type_guide").GetString().Should().BeEmpty();
        }
        finally
        {
            Environment.SetEnvironmentVariable("PHASEA_GODOT3_BIN", previousGodot);
        }
    }

    [Fact]
    public async Task GeneratePreviewAsync_UsesGameTypeAdapterForRpgPackage()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-web-preview-rpg-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-web-preview-rpg-repo");
        using var godotRoot = TempDirectory.Create("phase-a-web-preview-rpg-godot3-bin");
        var fakeGodot = Path.Combine(godotRoot.Path, "Godot_v3.6.2-stable_win64.exe");
        await File.WriteAllTextAsync(fakeGodot, "fake godot", Encoding.UTF8);
        var previousGodot = Environment.GetEnvironmentVariable("PHASEA_GODOT3_BIN");
        Environment.SetEnvironmentVariable("PHASEA_GODOT3_BIN", fakeGodot);
        try
        {
            var options = Options(workspaceRoot.Path, repoRoot.Path, Path.Combine(workspaceRoot.Path, "metadata.sqlite3"));
            await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
            var store = new PhaseAMetadataStore(database.ConnectionString, options);
            var account = await store.CreateUserAccountAsync("web-preview-rpg-user", 1);
            var projectId = await CreateProjectAsync(store, options, account.AccountId);
            var project = (await store.GetProjectSnapshotAsync(projectId))!;
            var packageFile = "RpgQuest-v0.1.20260627.001.zip";
            WriteRpgGodotPackage(project.RepoPath, packageFile);
            var runner = new FakeGodot3WebExportRunner();
            var service = new ProjectWebPreviewService(
                store,
                options,
                new HeavyRunnerQueueService(TimeSpan.FromSeconds(30), maxConcurrentRuns: 1),
                new ProjectWebPreviewConcurrencyLimiter(maxConcurrentWebPreviewsPerAccount: 1),
                runner);

            var result = await service.GeneratePreviewAsync(account.AccountId, project.ProjectId, packageFile);
            var previewDataPath = Path.Combine(project.RepoPath, "exports", "web-previews", result.PreviewId, "preview-data.json");
            using var previewData = JsonDocument.Parse(await File.ReadAllTextAsync(previewDataPath, Encoding.UTF8));
            var contract = previewData.RootElement.GetProperty("web_preview_manifest").GetProperty("conversion_contract");
            var status = await service.ResolvePreviewForPackageAsync(project, packageFile);

            result.Status.Should().Be("succeeded");
            result.Mode.Should().Be("godot3-html5-rpg-package-preview");
            previewData.RootElement.GetProperty("converter_id").GetString().Should().Be("godot-package-rpg-playable-preview");
            previewData.RootElement.GetProperty("game_type_id").GetString().Should().Be("rpg");
            previewData.RootElement.GetProperty("game_type_guide").GetString().Should().Be("docs/game-type-guides/rpg.md");
            previewData.RootElement.GetProperty("web_preview_manifest").GetProperty("game_type_id").GetString().Should().Be("rpg");
            previewData.RootElement.GetProperty("web_preview_manifest").GetProperty("game_type_guide").GetString().Should().Be("docs/game-type-guides/rpg.md");
            contract.GetProperty("fidelity_tier").GetString().Should().Be("game_type_adapter_preview");
            contract.GetProperty("playable_surface").GetString().Should().Be("rpg_encounter_exploration_reward_preview");
            contract.GetProperty("data_sources").EnumerateArray().Select(item => item.GetString()).Should().Contain("docs/game-type-guides/rpg.md");
            status.Status.Should().Be("ready");
            status.FidelityTier.Should().Be("game_type_adapter_preview");
            status.PlayableSurface.Should().Be("rpg_encounter_exploration_reward_preview");
            status.GameTypeId.Should().Be("rpg");
            status.GameTypeGuide.Should().Be("docs/game-type-guides/rpg.md");
        }
        finally
        {
            Environment.SetEnvironmentVariable("PHASEA_GODOT3_BIN", previousGodot);
        }
    }

    [Theory]
    [InlineData("SurvivalRun", "survival", "godot3-html5-survival-package-preview", "godot-package-survival-playable-preview", "survival_gather_needs_shelter_preview")]
    [InlineData("SurvivorArena", "survivorslike", "godot3-html5-survivorslike-package-preview", "godot-package-survivorslike-playable-preview", "survivorslike_arena_pressure_preview")]
    [InlineData("RogueRun", "roguelike", "godot3-html5-survivorslike-package-preview", "godot-package-survivorslike-playable-preview", "survivorslike_arena_pressure_preview")]
    [InlineData("DeckFight", "card-game", "godot3-html5-card-package-preview", "godot-package-card-playable-preview", "card_hand_energy_encounter_preview")]
    [InlineData("TowerPlan", "tower-defense", "godot3-html5-tower-defense-package-preview", "godot-package-tower-defense-playable-preview", "tower_defense_placement_wave_preview")]
    [InlineData("ActionQuest", "action-platformer", "godot3-html5-action-package-preview", "godot-package-action-playable-preview", "survivorslike_arena_pressure_preview")]
    [InlineData("PuzzleBox", "puzzle", "godot3-html5-puzzle-package-preview", "godot-package-puzzle-playable-preview", "generic_package_exploration_shell")]
    [InlineData("StrategyMap", "strategy", "godot3-html5-strategy-package-preview", "godot-package-strategy-playable-preview", "tower_defense_placement_wave_preview")]
    [InlineData("StoryChoice", "visual-novel", "godot3-html5-narrative-package-preview", "godot-package-narrative-playable-preview", "generic_package_exploration_shell")]
    public async Task GeneratePreviewAsync_UsesRegisteredGameTypeAdapters(
        string gameName,
        string gameTypeId,
        string expectedMode,
        string expectedConverterId,
        string expectedPlayableSurface)
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create($"phase-a-web-preview-{gameTypeId}-workspaces");
        using var repoRoot = TempDirectory.Create($"phase-a-web-preview-{gameTypeId}-repo");
        using var godotRoot = TempDirectory.Create($"phase-a-web-preview-{gameTypeId}-godot3-bin");
        var fakeGodot = Path.Combine(godotRoot.Path, "Godot_v3.6.2-stable_win64.exe");
        await File.WriteAllTextAsync(fakeGodot, "fake godot", Encoding.UTF8);
        var previousGodot = Environment.GetEnvironmentVariable("PHASEA_GODOT3_BIN");
        Environment.SetEnvironmentVariable("PHASEA_GODOT3_BIN", fakeGodot);
        try
        {
            var options = Options(workspaceRoot.Path, repoRoot.Path, Path.Combine(workspaceRoot.Path, "metadata.sqlite3"));
            await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
            var store = new PhaseAMetadataStore(database.ConnectionString, options);
            var account = await store.CreateUserAccountAsync($"web-preview-{gameTypeId}-user", 1);
            var projectId = await CreateProjectAsync(store, options, account.AccountId);
            var project = (await store.GetProjectSnapshotAsync(projectId))!;
            var packageFile = $"{gameName}-v0.1.20260627.001.zip";
            WriteTypedGodotPackage(project.RepoPath, packageFile, gameName, gameTypeId);
            var runner = new FakeGodot3WebExportRunner();
            var service = new ProjectWebPreviewService(
                store,
                options,
                new HeavyRunnerQueueService(TimeSpan.FromSeconds(30), maxConcurrentRuns: 1),
                new ProjectWebPreviewConcurrencyLimiter(maxConcurrentWebPreviewsPerAccount: 1),
                runner);

            var result = await service.GeneratePreviewAsync(account.AccountId, project.ProjectId, packageFile);
            var previewDataPath = Path.Combine(project.RepoPath, "exports", "web-previews", result.PreviewId, "preview-data.json");
            using var previewData = JsonDocument.Parse(await File.ReadAllTextAsync(previewDataPath, Encoding.UTF8));
            var contract = previewData.RootElement.GetProperty("web_preview_manifest").GetProperty("conversion_contract");

            result.Status.Should().Be("succeeded");
            result.Mode.Should().Be(expectedMode);
            previewData.RootElement.GetProperty("converter_id").GetString().Should().Be(expectedConverterId);
            previewData.RootElement.GetProperty("game_type_id").GetString().Should().Be(gameTypeId);
            previewData.RootElement.GetProperty("game_type_guide").GetString().Should().Be($"docs/game-type-guides/{gameTypeId}.md");
            contract.GetProperty("fidelity_tier").GetString().Should().Be(gameTypeId is "puzzle" or "visual-novel" ? "generic_package_preview" : "game_type_adapter_preview");
            contract.GetProperty("playable_surface").GetString().Should().Be(expectedPlayableSurface);
        }
        finally
        {
            Environment.SetEnvironmentVariable("PHASEA_GODOT3_BIN", previousGodot);
        }
    }

    [Fact]
    public async Task GeneratePreviewAsync_NormalizesKnownGameTypeGuideFromCatalog()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-web-preview-guide-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-web-preview-guide-repo");
        using var godotRoot = TempDirectory.Create("phase-a-web-preview-guide-godot3-bin");
        var fakeGodot = Path.Combine(godotRoot.Path, "Godot_v3.6.2-stable_win64.exe");
        await File.WriteAllTextAsync(fakeGodot, "fake godot", Encoding.UTF8);
        var previousGodot = Environment.GetEnvironmentVariable("PHASEA_GODOT3_BIN");
        Environment.SetEnvironmentVariable("PHASEA_GODOT3_BIN", fakeGodot);
        try
        {
            var options = Options(workspaceRoot.Path, repoRoot.Path, Path.Combine(workspaceRoot.Path, "metadata.sqlite3"));
            await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
            var store = new PhaseAMetadataStore(database.ConnectionString, options);
            var account = await store.CreateUserAccountAsync("web-preview-guide-user", 1);
            var projectId = await CreateProjectAsync(store, options, account.AccountId);
            var project = (await store.GetProjectSnapshotAsync(projectId))!;
            var packageFile = "GuideMismatch-v0.1.20260627.001.zip";
            WriteTypedGodotPackage(project.RepoPath, packageFile, "GuideMismatch", "rpg", "docs/game-type-guides/puzzle.md");
            var runner = new FakeGodot3WebExportRunner();
            var service = new ProjectWebPreviewService(
                store,
                options,
                new HeavyRunnerQueueService(TimeSpan.FromSeconds(30), maxConcurrentRuns: 1),
                new ProjectWebPreviewConcurrencyLimiter(maxConcurrentWebPreviewsPerAccount: 1),
                runner);

            var result = await service.GeneratePreviewAsync(account.AccountId, project.ProjectId, packageFile);
            var previewDataPath = Path.Combine(project.RepoPath, "exports", "web-previews", result.PreviewId, "preview-data.json");
            using var previewData = JsonDocument.Parse(await File.ReadAllTextAsync(previewDataPath, Encoding.UTF8));

            result.Status.Should().Be("succeeded");
            previewData.RootElement.GetProperty("game_type_id").GetString().Should().Be("rpg");
            previewData.RootElement.GetProperty("game_type_guide").GetString().Should().Be("docs/game-type-guides/rpg.md");
            previewData.RootElement.GetProperty("web_preview_manifest").GetProperty("game_type_guide").GetString().Should().Be("docs/game-type-guides/rpg.md");
        }
        finally
        {
            Environment.SetEnvironmentVariable("PHASEA_GODOT3_BIN", previousGodot);
        }
    }

    private static async Task<string> CreateProjectAsync(PhaseAMetadataStore store, PhaseAPlatformOptions options, string accountId)
    {
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var result = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Demo Game", "manual", null, null, null, null));
        result.Succeeded.Should().BeTrue(result.FailureCode);
        await store.SetProjectBootstrapStatusAsync(result.ProjectId!, "succeeded", null);
        return result.ProjectId!;
    }

    private static PhaseAPlatformOptions Options(string workspaceRoot, string repoRoot, string databasePath)
    {
        return PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot,
            ["PHASEA_METADATA_DB_PATH"] = databasePath,
            ["PHASEA_REPOSITORY_ROOT"] = repoRoot,
            ["PHASEA_WEB_PREVIEW_SIGNING_SECRET"] = TestPreviewSigningSecret
        });
    }

    private static void WritePackage(string projectRoot, string packageFile, string content)
    {
        WritePackage(projectRoot, packageFile, Encoding.UTF8.GetBytes(content));
    }

    private static void WritePackage(string projectRoot, string packageFile, byte[] content)
    {
        var packagePath = Path.Combine(projectRoot, "exports", packageFile);
        Directory.CreateDirectory(Path.GetDirectoryName(packagePath)!);
        File.WriteAllBytes(packagePath, content);
    }

    private static void WriteGenericGodotPackage(
        string projectRoot,
        string packageFile,
        string gameName = "GenericAdventure",
        string gameTypeSource = "Generic Adventure")
    {
        var packagePath = Path.Combine(projectRoot, "exports", packageFile);
        Directory.CreateDirectory(Path.GetDirectoryName(packagePath)!);
        using var stream = File.Create(packagePath);
        using var archive = new ZipArchive(stream, ZipArchiveMode.Create);
        AddZipEntry(archive, "PACKAGE-MANIFEST.json", $$"""
        {
          "package_version": "v0.1.20260627.001",
          "project_name": "{{gameName}}",
          "game_name": "{{gameName}}",
          "game_type_source": "{{gameTypeSource}}"
        }
        """);
        AddZipEntry(archive, "project.godot", $$"""
        config_version=5

        [application]
        config/name="{{gameName}}"
        run/main_scene="res://Game.Godot/Prototypes/{{gameName}}/{{gameName}}Prototype.tscn"

        [input]
        dash={
        "deadzone": 0.5,
        "events": [Object(InputEventKey,"physical_keycode":4194321)]
        }
        """);
        AddZipEntry(archive, $"Game.Godot/Prototypes/{gameName}/{gameName}Prototype.tscn", $$"""
        [gd_scene load_steps=3 format=3]

        [ext_resource type="Script" path="res://Game.Godot/Prototypes/{{gameName}}/PlayerController.gd" id="1"]
        [ext_resource type="Texture2D" path="res://Game.Godot/Prototypes/{{gameName}}/Art/player.png" id="2"]

        [node name="GenericAdventurePrototype" type="Node2D"]

        [node name="Player" type="CharacterBody2D" parent="."]
        script = ExtResource("1")

        [node name="PlayerSprite" type="Sprite2D" parent="Player"]
        texture = ExtResource("2")
        """);
        AddZipEntry(archive, $"Game.Godot/Prototypes/{gameName}/PlayerController.gd", """
        extends CharacterBody2D

        func _physics_process(delta):
            var direction = Input.get_vector("move_left", "move_right", "move_up", "move_down")
            velocity = direction * 240
            move_and_slide()

        func _input(event):
            if Input.is_action_just_pressed("dash"):
                attack()

        func attack():
            pass
        """);
        AddZipEntry(archive, $"Game.Godot/Prototypes/{gameName}/Art/player.png", "fake image");
        AddZipEntry(archive, "playable-preview-contract.json", $$"""
        {
          "schema_version": "phasea-playable-preview-contract-v1",
          "source": "project-package-service",
          "project_name": "{{gameName}}",
          "game_name": "{{gameName}}",
          "main_scene": "res://Game.Godot/Prototypes/{{gameName}}/{{gameName}}Prototype.tscn",
          "objectives": [
            {
              "id": "first_playable_loop",
              "label": "Move to the start node and interact.",
              "success": "The preview loop reports progress."
            }
          ],
          "entities": [
            {
              "id": "start",
              "label": "StartNode",
              "role": "entry_scene",
              "scene": "res://Game.Godot/Prototypes/{{gameName}}/{{gameName}}Prototype.tscn",
              "objective": "Start the generic contract route."
            }
          ],
          "input_actions": [
            {
              "action": "interact",
              "inputs": ["Space"],
              "behavior": "Activate the selected contract node."
            }
          ]
        }
        """);
    }

    private static void WriteRpgGodotPackage(string projectRoot, string packageFile)
    {
        var packagePath = Path.Combine(projectRoot, "exports", packageFile);
        Directory.CreateDirectory(Path.GetDirectoryName(packagePath)!);
        using var stream = File.Create(packagePath);
        using var archive = new ZipArchive(stream, ZipArchiveMode.Create);
        AddZipEntry(archive, "PACKAGE-MANIFEST.json", """
        {
          "package_version": "v0.1.20260627.001",
          "project_name": "RpgQuest",
          "game_name": "RpgQuest",
          "game_type_source": "RPG",
          "game_type_id": "rpg",
          "game_type_guide": "docs/game-type-guides/rpg.md"
        }
        """);
        AddZipEntry(archive, "project.godot", """
        config_version=5

        [application]
        config/name="RpgQuest"
        run/main_scene="res://Game.Godot/Prototypes/RpgQuest/RpgQuestPrototype.tscn"
        """);
        AddZipEntry(archive, "Game.Godot/Prototypes/RpgQuest/RpgQuestPrototype.tscn", """
        [gd_scene format=3]

        [node name="RpgQuestPrototype" type="Node2D"]
        """);
        AddZipEntry(archive, "Game.Godot/Prototypes/RpgQuest/BattleScene.tscn", """
        [gd_scene format=3]

        [node name="BattleScene" type="Node2D"]
        """);
    }

    private static void WriteMinimalGodotPackage(string projectRoot, string packageFile)
    {
        var packagePath = Path.Combine(projectRoot, "exports", packageFile);
        Directory.CreateDirectory(Path.GetDirectoryName(packagePath)!);
        using var stream = File.Create(packagePath);
        using var archive = new ZipArchive(stream, ZipArchiveMode.Create);
        AddZipEntry(archive, "PACKAGE-MANIFEST.json", """
        {
          "package_version": "v0.1.20260627.001",
          "project_name": "Towerdemo2",
          "game_name": "Towerdemo2",
          "game_type_source": "Phantom Tower"
        }
        """);
        AddZipEntry(archive, "project.godot", """
        config_version=5

        [application]
        config/name="Towerdemo2"
        run/main_scene="res://Game.Godot/Prototypes/Towerdemo2/Towerdemo2Prototype.tscn"
        """);
    }

    private static void WriteLegacyTowerdemoPackage(string projectRoot, string packageFile)
    {
        var packagePath = Path.Combine(projectRoot, "exports", packageFile);
        Directory.CreateDirectory(Path.GetDirectoryName(packagePath)!);
        using var stream = File.Create(packagePath);
        using var archive = new ZipArchive(stream, ZipArchiveMode.Create);
        AddZipEntry(archive, "PACKAGE-MANIFEST.json", """
        {
          "package_version": "v0.1.20260627.004",
          "project_name": "Towerdemo2",
          "game_name": "Towerdemo2",
          "game_type_source": "Phantom Tower"
        }
        """);
        AddZipEntry(archive, "project.godot", """
        config_version=5

        [application]
        config/name="Towerdemo2"
        run/main_scene="res://Game.Godot/Prototypes/Towerdemo2/Towerdemo2Prototype.tscn"
        """);
        AddZipEntry(archive, "Game.Godot/Prototypes/Towerdemo2/Towerdemo2Prototype.tscn", """
        [gd_scene format=3]

        [node name="Towerdemo2Prototype" type="Node2D"]
        """);
    }

    private static void WriteTowerdemo2PackageWithChangedScene(string projectRoot, string packageFile)
    {
        var packagePath = Path.Combine(projectRoot, "exports", packageFile);
        Directory.CreateDirectory(Path.GetDirectoryName(packagePath)!);
        using var stream = File.Create(packagePath);
        using var archive = new ZipArchive(stream, ZipArchiveMode.Create);
        AddZipEntry(archive, "PACKAGE-MANIFEST.json", """
        {
          "package_version": "v0.1.20260628.004",
          "project_name": "Towerdemo2",
          "game_name": "Towerdemo2",
          "game_type_source": "Phantom Tower"
        }
        """);
        AddZipEntry(archive, "project.godot", """
        config_version=5

        [application]
        config/name="Towerdemo2"
        run/main_scene="res://Game.Godot/Scenes/Main.tscn"
        """);
        AddZipEntry(archive, "Game.Godot/Prototypes/Towerdemo2/Towerdemo2Prototype.tscn", """
        [gd_scene format=3]

        [node name="Towerdemo2Prototype" type="Node2D"]
        position = Vector2(12, 18)

        [node name="Player" type="CharacterBody3D" parent="MapScene"]
        transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0.9, 4)

        [node name="AttackArea" type="Area3D" parent="MapScene/Player"]

        [node name="SkillShapeCast" type="ShapeCast3D" parent="MapScene/Player"]

        [node name="EnemySpawnA" type="Node3D" parent="MapScene"]

        [node name="EnemyShadeA" type="CharacterBody3D" parent="MapScene/EnemySpawnA"]

        [node name="RewardDoor" type="Node3D" parent="MapScene"]
        """);
        AddZipEntry(archive, "Game.Godot/Prototypes/Towerdemo2/Scripts/Data/PrototypeTextCatalog.cs", """
        namespace Game.Godot.Prototypes.Towerdemo2.Scripts.Data;

        public static class PrototypeTextCatalog
        {
            public static readonly System.Collections.Generic.Dictionary<string, string> Text = new()
            {
                ["hud.header"] = "Towerdemo2 Web Preview"
            };
        }
        """);
        AddZipEntry(archive, "playable-preview-contract.json", """
        {
          "schema_version": "phasea-playable-preview-contract-v1",
          "source": "project-package-service",
          "main_scene": "res://Game.Godot/Scenes/Main.tscn",
          "entities": [
            { "id": "player", "label": "Player", "role": "player_start", "scene": "res://Game.Godot/Prototypes/Towerdemo2/Towerdemo2Prototype.tscn", "node_path": "MapScene/Player", "objective": "Move." },
            { "id": "attack", "label": "AttackArea", "role": "action", "scene": "res://Game.Godot/Prototypes/Towerdemo2/Towerdemo2Prototype.tscn", "node_path": "MapScene/Player/AttackArea", "objective": "Attack." },
            { "id": "skill", "label": "SkillShapeCast", "role": "action", "scene": "res://Game.Godot/Prototypes/Towerdemo2/Towerdemo2Prototype.tscn", "node_path": "MapScene/Player/SkillShapeCast", "objective": "Skill." },
            { "id": "enemy", "label": "EnemyShadeA", "role": "pressure_source", "scene": "res://Game.Godot/Prototypes/Towerdemo2/Towerdemo2Prototype.tscn", "node_path": "MapScene/EnemySpawnA/EnemyShadeA", "objective": "Enemy pressure." },
            { "id": "reward", "label": "RewardDoor", "role": "reward", "scene": "res://Game.Godot/Prototypes/Towerdemo2/Towerdemo2Prototype.tscn", "node_path": "MapScene/RewardDoor", "objective": "Reward." }
          ]
        }
        """);
    }

    private static void WriteTypedGodotPackage(
        string projectRoot,
        string packageFile,
        string gameName,
        string gameTypeId,
        string? gameTypeGuide = null)
    {
        var packagePath = Path.Combine(projectRoot, "exports", packageFile);
        Directory.CreateDirectory(Path.GetDirectoryName(packagePath)!);
        gameTypeGuide ??= $"docs/game-type-guides/{gameTypeId}.md";
        using var stream = File.Create(packagePath);
        using var archive = new ZipArchive(stream, ZipArchiveMode.Create);
        AddZipEntry(archive, "PACKAGE-MANIFEST.json", $$"""
        {
          "package_version": "v0.1.20260627.001",
          "project_name": "{{gameName}}",
          "game_name": "{{gameName}}",
          "game_type_source": "{{gameTypeId}}",
          "game_type_id": "{{gameTypeId}}",
          "game_type_guide": "{{gameTypeGuide}}"
        }
        """);
        AddZipEntry(archive, "project.godot", $$"""
        config_version=5

        [application]
        config/name="{{gameName}}"
        run/main_scene="res://Game.Godot/Prototypes/{{gameName}}/{{gameName}}Prototype.tscn"
        """);
        AddZipEntry(archive, $"Game.Godot/Prototypes/{gameName}/{gameName}Prototype.tscn", """
        [gd_scene format=3]

        [node name="TypedPrototype" type="Node2D"]
        """);
    }

    private static void AddZipEntry(ZipArchive archive, string path, string content)
    {
        var entry = archive.CreateEntry(path);
        using var writer = new StreamWriter(entry.Open(), new UTF8Encoding(false));
        writer.Write(content);
    }

    private static string ShortSha(byte[] content)
    {
        return FullSha(content)[..16];
    }

    private static string FullSha(byte[] content)
    {
        return Convert.ToHexString(SHA256.HashData(content)).ToLowerInvariant();
    }

    private const string TestPreviewSigningSecret = "test-preview-signing-secret";
    private const string Towerdemo2SceneSha256 = "0ffcf4b962ac246f3af182fb49775f2517cca12a19772bae67464ca92fba33c5";
    private const string Towerdemo2TextCatalogSha256 = "f4f97dfd524150b36bf36545aa3ed9a95f90a7ec4ba67000ed6763dcae028652";
    private const string Towerdemo2ConverterId = "towerdemo2-template-subset";
    private const string Towerdemo2ConverterCompatibilityId = "towerdemo2-20260627-source-fingerprint-v1";

    private sealed class FailingQueueWebExportRunner : IHostedProcessRunner
    {
        public List<HostedProcessCommand> Commands { get; } = [];
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Commands.Add(command);
            return Task.FromResult(new HostedProcessResult(1, string.Empty, "queue fixture export failure"));
        }
    }

    private sealed class FakeGodot3WebExportRunner : IHostedProcessRunner
    {
        public List<HostedProcessCommand> Commands { get; } = [];
        public List<string> MainScripts { get; } = [];
        public List<string> MainScenes { get; } = [];

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Commands.Add(command);
            MainScripts.Add(File.ReadAllText(Path.Combine(command.WorkingDirectory, "Main.gd"), Encoding.UTF8));
            MainScenes.Add(File.ReadAllText(Path.Combine(command.WorkingDirectory, "Main.tscn"), Encoding.UTF8));
            var outputPath = command.Arguments.Last();
            var webRoot = Path.GetDirectoryName(outputPath)!;
            Directory.CreateDirectory(webRoot);
            File.WriteAllText(Path.Combine(webRoot, "index.html"), """
            <!DOCTYPE html>
            <html>
            <head>
                <style>
            		#status-progress-inner {
            			height: 100%;
            		}
                </style>
            </head>
            <body>
                <div id='status-progress' style='display: none;' oncontextmenu='event.preventDefault();'><div id ='status-progress-inner'></div></div>
                <script type='text/javascript' src='index.js'></script>
                <script type='text/javascript'>
                    const GODOT_CONFIG = {"args":[],"canvasResizePolicy":2,"executable":"index","fileSizes":{"index.pck":10,"index.wasm":20}};
                    var engine = new Engine(GODOT_CONFIG);
                    (function() {
            			var statusProgressInner = document.getElementById('status-progress-inner');
            			var statusIndeterminate = document.getElementById('status-indeterminate');
            			var initializing = true;
            			var statusMode = 'hidden';
            			[statusProgress, statusIndeterminate, statusNotice].forEach(elem => {
            			});
            			statusProgress.style.display = 'block';
            						break;
            			statusIndeterminate.style.display = 'block';
            						animationCallbacks.push(animateStatusIndeterminate);
            			statusProgressInner.style.width = current/total * 100 + '%';
            							setStatusMode('progress');
            			setStatusMode('hidden');
            					initializing = false;
                    })();
                </script>
            </body>
            </html>
            """, Encoding.UTF8);
            File.WriteAllText(Path.Combine(webRoot, "index.js"), """
            const Preloader = function () {
                this.preload = function (pathOrBuffer, destPath, fileSize) {};
                this.loadPromise = function (file, fileSize, raw = false) {};
            };
            const InternalConfig = function (initConfig) { // eslint-disable-line no-unused-vars
            };
            Config.prototype.getModuleConfig = function (loadPath, response) {
                return {
                        'locateFile': function (path) {
                            if (path.endsWith('.worker.js')) {
                                return `${loadPath}.worker.js`;
                            } else if (path.endsWith('.audio.worklet.js')) {
                                return `${loadPath}.audio.worklet.js`;
                            } else if (path.endsWith('.js')) {
                                return `${loadPath}.js`;
                            } else if (path.endsWith('.side.wasm')) {
                                return `${loadPath}.side.wasm`;
                            } else if (path.endsWith('.wasm')) {
                                return `${loadPath}.wasm`;
                            }
                            return path;
                        },
                    };
            };
            const Engine = (function () {
                const preloader = new Preloader();
                let loadPromise = null;
                let loadPath = '';
                Engine.load = function (basePath, size) {
                    if (loadPromise == null) {
                        loadPath = basePath;
                        loadPromise = preloader.loadPromise(`${loadPath}.wasm`, size, true);
                    }
                };
                const proto = {
                        preloadFile: function (file, path) {
                            return preloader.preload(file, path, this.config.fileSizes[file]);
                        },
                };
            }());
            """, Encoding.UTF8);
            File.WriteAllBytes(Path.Combine(webRoot, "index.wasm"), [0]);
            File.WriteAllBytes(Path.Combine(webRoot, "index.pck"), [0]);
            return Task.FromResult(new HostedProcessResult(0, "fake export ok", ""));
        }
    }

    private sealed class DedicatedAdapterRunner(string script) : IHostedProcessRunner
    {
        public List<HostedProcessCommand> Commands { get; } = [];

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Commands.Add(command);
            var outputPath = command.Arguments.SkipWhile(argument => argument != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, script, new UTF8Encoding(false));
            return Task.FromResult(new HostedProcessResult(0, script, ""));
        }
    }

    private sealed class FailingDedicatedAdapterRunner : IHostedProcessRunner
    {
        public List<HostedProcessCommand> Commands { get; } = [];

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Commands.Add(command);
            return Task.FromResult(new HostedProcessResult(408, "", "timeout"));
        }
    }

    private static string SignedPreviewData(
        string projectId,
        string previewId,
        string packageFile,
        string packageSha256,
        string assetVersion,
        string createdUtc,
        string manifestSha256,
        string manifestJson)
    {
        const string mode = "godot3-html5-towerdemo2-template-subset";
        var payload = string.Join(
            '\n',
            projectId,
            previewId,
            packageSha256,
            assetVersion,
            createdUtc,
            mode,
            Towerdemo2ConverterId,
            Towerdemo2ConverterCompatibilityId,
            Towerdemo2SceneSha256,
            Towerdemo2TextCatalogSha256,
            manifestSha256);
        using var hmac = new HMACSHA256(Encoding.UTF8.GetBytes(TestPreviewSigningSecret));
        var signature = Convert.ToHexString(hmac.ComputeHash(Encoding.UTF8.GetBytes(payload))).ToLowerInvariant();
        return $$"""
        {
          "schema_version": "phasea-web-preview-v5",
          "project_id": "{{projectId}}",
          "preview_id": "{{previewId}}",
          "package_file": "{{packageFile}}",
          "package_sha256": "{{packageSha256}}",
          "asset_version": "{{assetVersion}}",
          "converter_id": "{{Towerdemo2ConverterId}}",
          "converter_compatibility_id": "{{Towerdemo2ConverterCompatibilityId}}",
          "source_scene_sha256": "{{Towerdemo2SceneSha256}}",
          "text_catalog_sha256": "{{Towerdemo2TextCatalogSha256}}",
          "manifest_sha256": "{{manifestSha256}}",
          "mode": "{{mode}}",
          "created_utc": "{{createdUtc}}",
          "signature": "{{signature}}",
          "web_preview_manifest": {{manifestJson}}
        }
        """;
    }

    private static string SignedLegacyPreviewData(
        string projectId,
        string previewId,
        string packageFile,
        string packageSha256,
        string assetVersion,
        string createdUtc)
    {
        const string mode = "godot3-html5-towerdemo2-template-subset";
        var payload = string.Join(
            '\n',
            projectId,
            previewId,
            packageSha256,
            assetVersion,
            createdUtc,
            mode,
            Towerdemo2ConverterId,
            Towerdemo2ConverterCompatibilityId,
            Towerdemo2SceneSha256,
            Towerdemo2TextCatalogSha256);
        using var hmac = new HMACSHA256(Encoding.UTF8.GetBytes(TestPreviewSigningSecret));
        var signature = Convert.ToHexString(hmac.ComputeHash(Encoding.UTF8.GetBytes(payload))).ToLowerInvariant();
        return $$"""
        {
          "schema_version": "phasea-web-preview-v4",
          "project_id": "{{projectId}}",
          "preview_id": "{{previewId}}",
          "package_file": "{{packageFile}}",
          "package_sha256": "{{packageSha256}}",
          "asset_version": "{{assetVersion}}",
          "converter_id": "{{Towerdemo2ConverterId}}",
          "converter_compatibility_id": "{{Towerdemo2ConverterCompatibilityId}}",
          "source_scene_sha256": "{{Towerdemo2SceneSha256}}",
          "text_catalog_sha256": "{{Towerdemo2TextCatalogSha256}}",
          "mode": "{{mode}}",
          "created_utc": "{{createdUtc}}",
          "signature": "{{signature}}"
        }
        """;
    }

    private static string Towerdemo2PreviewManifest()
    {
        return """
        {
          "schema_version": "phasea-web-preview-manifest-v1",
          "source": "generated_by_web_preview_converter",
          "project_id": "test-project",
          "project_name": "Towerdemo2",
          "game_name": "Towerdemo2",
          "game_type_source": "Tower Defense",
          "game_type_id": "tower-defense",
          "game_type_guide": "docs/game-type-guides/tower-defense.md",
          "package_file": "Towerdemo2-v0.1.20260627.002.zip",
          "package_sha256": "test-package-sha256",
          "package_size_bytes": 14,
          "main_scene": "res://Game.Godot/Prototypes/Towerdemo2/Towerdemo2Prototype.tscn",
          "scenes": [],
          "source_fingerprints": [],
          "text_key_count": 0,
          "detected_templates": ["towerdemo2"],
          "detected_capabilities": ["godot_package_zip"],
          "conversion_contract": {
            "selection_policy": "capability_routed",
            "playable_surface": "towerdemo2_high_fidelity_subset",
            "fidelity_tier": "template_high_fidelity",
            "data_sources": ["PACKAGE-MANIFEST.json", "project.godot"],
            "input_actions": []
          }
        }
        """;
    }

    private sealed class TempDirectory : IDisposable
    {
        private TempDirectory(string path)
        {
            Path = path;
        }

        public string Path { get; }

        public static TempDirectory Create(string prefix)
        {
            var path = System.IO.Path.Combine(System.IO.Path.GetTempPath(), $"{prefix}-{Guid.NewGuid():N}");
            Directory.CreateDirectory(path);
            return new TempDirectory(path);
        }

        public void Dispose()
        {
            if (Directory.Exists(Path))
            {
                Directory.Delete(Path, recursive: true);
            }
        }
    }
}
