using System.Text;
using System.Text.Json;
using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Readback;
using PhaseA.Platform.Runs;
using Xunit;

namespace PhaseA.Platform.Tests.Readback;

public sealed class ProjectWebPreviewSemanticAdapterServiceTests
{
    [Fact]
    public async Task ResolveAsync_GeneratesVersionedAdapterWhenNoneExists()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-semantic-adapter-workspaces");
        var projectRoot = Path.Combine(workspaceRoot.Path, "project");
        Directory.CreateDirectory(projectRoot);
        var request = Request(workspaceRoot.Path, projectRoot, "Towerdemo2-v0.1.20260628.010.zip", "aaaaaaaa");
        var runner = new SemanticAdapterRunner(command => AdapterJson(request, "Towerdemo2-v0.1.20260628.010", "codex-semantic-adapter"));
        var service = new ProjectWebPreviewSemanticAdapterService(Options(workspaceRoot.Path), runner);

        var result = await service.ResolveAsync(request);

        result.Status.Should().Be("generated_by_codex");
        result.Adapter.GetProperty("adapter_version").GetString().Should().Be("Towerdemo2-v0.1.20260628.010");
        result.AdapterPath.Should().Contain(Path.Combine("web-preview-semantic-adapters", "Towerdemo2-v0.1.20260628.010"));
        File.Exists(result.AdapterPath).Should().BeTrue();
        runner.Commands.Should().HaveCount(1);
        runner.Commands[0].Arguments.Should().Contain("--sandbox");
        runner.Commands[0].Arguments.Should().Contain("workspace-write");
        runner.Commands[0].Arguments.Should().Contain("-");
        runner.Commands[0].StandardInput.Should().Contain(ProjectWebPreviewSemanticAdapterService.SchemaVersion);
        result.Resolution.CodexInvoked.Should().BeTrue();
    }

    [Fact]
    public async Task ResolveAsync_ReusesSamePackageAdapterWithoutCodex()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-semantic-adapter-reuse-same");
        var projectRoot = Path.Combine(workspaceRoot.Path, "project");
        Directory.CreateDirectory(projectRoot);
        var request = Request(workspaceRoot.Path, projectRoot, "Demo-v0.1.001.zip", "bbbbbbbb");
        SeedAdapter(projectRoot, "Demo-v0.1.001", AdapterJson(request, "Demo-v0.1.001", "seeded"));
        var runner = new SemanticAdapterRunner(_ => throw new InvalidOperationException("Codex should not run."));
        var service = new ProjectWebPreviewSemanticAdapterService(Options(workspaceRoot.Path), runner);

        var result = await service.ResolveAsync(request);

        result.Status.Should().Be("reused_same_package");
        result.Resolution.CodexInvoked.Should().BeFalse();
        runner.Commands.Should().BeEmpty();
    }

    [Fact]
    public async Task ResolveAsync_AsksCodexBeforeReusingPreviousPackageAdapter()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-semantic-adapter-reuse-decision");
        var projectRoot = Path.Combine(workspaceRoot.Path, "project");
        Directory.CreateDirectory(projectRoot);
        var oldRequest = Request(workspaceRoot.Path, projectRoot, "Demo-v0.1.001.zip", "cccccccc");
        var newRequest = Request(workspaceRoot.Path, projectRoot, "Demo-v0.1.002.zip", "dddddddd");
        SeedAdapter(projectRoot, "Demo-v0.1.001", AdapterJson(oldRequest, "Demo-v0.1.001", "seeded"));
        var runner = new SemanticAdapterRunner(_ => """{"decision":"reuse","reason":"Semantic roles still match."}""");
        var service = new ProjectWebPreviewSemanticAdapterService(Options(workspaceRoot.Path), runner);

        var result = await service.ResolveAsync(newRequest);

        result.Status.Should().Be("reused_by_codex_decision");
        result.Adapter.GetProperty("adapter_version").GetString().Should().Be("Demo-v0.1.001");
        result.Resolution.CodexDecision.Should().Be("reuse");
        runner.Commands.Should().HaveCount(1);
        runner.Commands[0].Arguments.Should().Contain("read-only");
    }

    [Fact]
    public async Task ResolveAsync_RegeneratesVersionedAdapterWhenCodexDecisionRequiresIt()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-semantic-adapter-regenerate");
        var projectRoot = Path.Combine(workspaceRoot.Path, "project");
        Directory.CreateDirectory(projectRoot);
        var oldRequest = Request(workspaceRoot.Path, projectRoot, "Demo-v0.1.001.zip", "eeeeeeee");
        var newRequest = Request(workspaceRoot.Path, projectRoot, "Demo-v0.1.002.zip", "ffffffff");
        SeedAdapter(projectRoot, "Demo-v0.1.001", AdapterJson(oldRequest, "Demo-v0.1.001", "seeded"));
        var call = 0;
        var runner = new SemanticAdapterRunner(_ =>
        {
            call += 1;
            return call == 1
                ? """{"decision":"regenerate","reason":"Entity roles changed."}"""
                : AdapterJson(newRequest, "Demo-v0.1.002", "codex-semantic-adapter");
        });
        var service = new ProjectWebPreviewSemanticAdapterService(Options(workspaceRoot.Path), runner);

        var result = await service.ResolveAsync(newRequest);

        result.Status.Should().Be("generated_by_codex");
        result.Adapter.GetProperty("adapter_version").GetString().Should().Be("Demo-v0.1.002");
        result.Adapter.GetProperty("package_sha256").GetString().Should().Be("ffffffff");
        runner.Commands.Should().HaveCount(2);
        runner.Commands[0].Arguments.Should().Contain("read-only");
        runner.Commands[1].Arguments.Should().Contain("workspace-write");
    }

    [Fact]
    public async Task ResolveAsync_DeterministicFallbackAddsRuntimeTuning()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-semantic-adapter-runtime");
        var projectRoot = Path.Combine(workspaceRoot.Path, "project");
        Directory.CreateDirectory(projectRoot);
        var request = Request(workspaceRoot.Path, projectRoot, "Demo-v0.1.003.zip", "abababab");
        var service = ProjectWebPreviewSemanticAdapterService.DeterministicOnly(Options(workspaceRoot.Path));

        var result = await service.ResolveAsync(request);

        result.Status.Should().Be("generated_deterministic");
        result.Adapter.GetProperty("runtime_tuning").GetProperty("movement_speed").GetDouble().Should().Be(5.2);
        result.Adapter.GetProperty("entities")[0].GetProperty("runtime_profile").GetProperty("movement_speed").GetDouble().Should().Be(5.2);
        result.Resolution.CodexInvoked.Should().BeFalse();
    }

    private static ProjectWebPreviewSemanticAdapterRequest Request(
        string workspaceRoot,
        string projectRoot,
        string packageFile,
        string packageSha256)
    {
        var project = new ProjectSnapshot(
            "project-1",
            "account-1",
            "Demo Project",
            "Demo Game",
            "",
            "manual",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-1",
            workspaceRoot,
            projectRoot,
            Path.Combine(projectRoot, "runtime"),
            Path.Combine(projectRoot, "meta"));
        return new ProjectWebPreviewSemanticAdapterRequest(
            project.AccountId,
            $"run-{Guid.NewGuid():N}",
            project,
            projectRoot,
            packageFile,
            packageSha256,
            1234,
            project.GameName,
            project.GameTypeSource,
            "",
            "",
            "res://Main.tscn",
            ["res://Main.tscn"],
            """
            {
              "schema_version": "phasea-playable-preview-contract-v1",
              "entities": [
                { "id": "player", "label": "Player", "role": "player_start", "scene": "res://Main.tscn", "objective": "Spawn and move." }
              ],
              "state_model": [{ "id": "energy", "min": 0, "max": 3, "initial": 3 }],
              "role_interactions": [{ "role": "player_start", "state_delta": { "score": 1 }, "feedback": "Player ready." }]
            }
            """,
            """
            {
              "schema_version": "phasea-web-preview-manifest-v1",
              "conversion_contract": { "playable_surface": "generic_package_exploration_shell" }
            }
            """);
    }

    private static PhaseAPlatformOptions Options(string workspaceRoot)
    {
        return PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspaceRoot, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = workspaceRoot,
            ["WEB_PREVIEW_SIGNING_SECRET"] = "test-secret"
        });
    }

    private static void SeedAdapter(string projectRoot, string version, string json)
    {
        var directory = Path.Combine(projectRoot, "exports", "web-preview-semantic-adapters", version);
        Directory.CreateDirectory(directory);
        File.WriteAllText(Path.Combine(directory, ProjectWebPreviewSemanticAdapterService.AdapterFileName), json, new UTF8Encoding(false));
    }

    private static string AdapterJson(ProjectWebPreviewSemanticAdapterRequest request, string version, string source)
    {
        return JsonSerializer.Serialize(new
        {
            schema_version = ProjectWebPreviewSemanticAdapterService.SchemaVersion,
            source,
            compatibility_id = ProjectWebPreviewSemanticAdapterService.CompatibilityId,
            adapter_version = version,
            package_version = version,
            package_file = request.PackageFile,
            package_sha256 = request.PackageSha256,
            project_id = request.Project.ProjectId,
            project_name = request.Project.Name,
            game_name = request.GameName,
            game_type_id = request.GameTypeId,
            game_type_guide = request.GameTypeGuide,
            main_scene = request.MainScene,
            generated_utc = DateTimeOffset.UtcNow.ToString("O"),
            generation = new { mode = source },
            semantic_profile = new
            {
                gameplay_label = request.GameName,
                playable_surface = "generic_package_exploration_shell",
                fidelity_intent = "generic_converter_plus_project_semantic_adapter",
                first_loop_path = new[] { new { role = "player_start", label = "Player", action = "spawn_and_move" } },
                ui_hud_mapping = new[] { "progress", "energy" }
            },
            entities = new[]
            {
                new { id = "player", label = "Player", role = "player_start", scene = "res://Main.tscn", objective = "Spawn and move.", priority = 1 }
            },
            state_model = new[] { new { id = "energy", min = 0, max = 3, initial = 3 } },
            role_interactions = new[] { new { role = "player_start", feedback = "Player ready." } },
            input_actions = new[] { new { action = "move", inputs = new[] { "W", "A", "S", "D" }, behavior = "Move." } },
            win_conditions = Array.Empty<object>(),
            loss_conditions = Array.Empty<object>(),
            warnings = Array.Empty<string>()
        });
    }

    private sealed class SemanticAdapterRunner(Func<HostedProcessCommand, string> responseFactory) : IHostedProcessRunner
    {
        public List<HostedProcessCommand> Commands { get; } = [];

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Commands.Add(command);
            var outputPath = command.Arguments.SkipWhile(item => item != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, responseFactory(command), new UTF8Encoding(false));
            return Task.FromResult(new HostedProcessResult(0, "", ""));
        }
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
