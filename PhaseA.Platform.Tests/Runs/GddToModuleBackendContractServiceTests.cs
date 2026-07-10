using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Prototypes;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Tests.Data;
using PhaseA.Platform.Workspaces;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class GddToModuleBackendContractServiceTests
{
    [Fact]
    public async Task RequirementMap_CreateAsync_WritesStableRowsAndSourceBoundary()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        fixture.SeedConfirmedSceneRouteAndGdd();
        var service = new GameDesignRequirementMapService(fixture.Store);

        var result = await service.CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignRequirementMapRequest());

        result.Status.Should().Be("ready");
        result.OperationStatus.Should().Be("returned_existing");
        result.Requirements.Select(item => item.RequirementId).Should().Equal("REQ-001", "REQ-002");
        result.Requirements.Should().Contain(item => item.Kind == "ui");
        var sidecar = fixture.ReadJson("meta/routes/gdd-requirements/latest.json");
        sidecar.RootElement.GetProperty("schema_version").GetString().Should().Be("gdd-requirements.v1");
        sidecar.RootElement.GetProperty("source_boundary_enforced").GetBoolean().Should().BeTrue();
        sidecar.RootElement.GetProperty("requirements")[0].GetProperty("requirement_id").GetString().Should().Be("REQ-001");
    }

    [Theory]
    [InlineData("missing_gdd", "gdd_not_found")]
    [InlineData("missing_scene", "scene_route_missing")]
    [InlineData("unconfirmed_scene", "scene_route_unconfirmed")]
    [InlineData("stale_scene", "scene_route_stale")]
    [InlineData("game_type_hash_mismatch", "game_type_structured_stale")]
    [InlineData("gdd_hash_mismatch", "generated_gdd_hash_mismatch")]
    public async Task RequirementMap_CreateAsync_FailsClosedForInvalidSources(string scenario, string domainCode)
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        fixture.SeedConfirmedSceneRouteAndGdd();
        fixture.ApplyRequirementMapScenario(scenario);
        var service = new GameDesignRequirementMapService(fixture.Store);

        var result = await service.CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignRequirementMapRequest());

        result.Status.Should().Be("blocked");
        result.OperationStatus.Should().Be("rejected");
        result.BlockingIssues.Should().Contain(issue => issue.DomainCode == domainCode);
    }

    [Fact]
    public async Task RequirementMap_CreateAsync_FallsBackToNeedsReviewRowWhenNoRequirementCanBeExtracted()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        fixture.SeedConfirmedSceneRouteAndGdd("# Empty\n\nShort.");
        var service = new GameDesignRequirementMapService(fixture.Store);

        var result = await service.CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignRequirementMapRequest());

        result.Status.Should().Be("needs_review");
        result.Requirements.Should().ContainSingle();
        result.Requirements[0].RequirementId.Should().Be("REQ-001");
        result.Requirements[0].Status.Should().Be("needs_review");
    }

    [Fact]
    public async Task ContractFreeze_FreezeAsync_WritesV2ContractWithSourceHashesAndMirror()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        await fixture.SeedRequirementMapAsync();
        var service = new PrototypeContractFreezeService(fixture.Store);

        var result = await service.FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());

        result.Status.Should().Be("fresh");
        result.ContractHash.Should().NotBeNullOrWhiteSpace();
        result.SourceGddHash.Should().Be(fixture.GddHash);
        result.SourceSceneRouteHash.Should().Be(fixture.SceneRouteHash);
        result.SourceRequirementMapHash.Should().NotBeNullOrWhiteSpace();
        var canonical = fixture.ReadJson("routes/prototype-contract/latest.json");
        var mirror = fixture.ReadJson("meta/routes/prototype-contract/latest.json");
        canonical.RootElement.GetProperty("schema_version").GetString().Should().Be("prototype-contract.v2");
        canonical.RootElement.GetProperty("source_gdd_hash").GetString().Should().Be(fixture.GddHash);
        mirror.RootElement.GetProperty("contract_hash").GetString().Should().Be(result.ContractHash);
    }

    [Fact]
    public async Task ContractFreeze_FreezeAsync_IsIdempotentForUnchangedSources()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        await fixture.SeedRequirementMapAsync();
        var service = new PrototypeContractFreezeService(fixture.Store);

        var first = await service.FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        var second = await service.FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());

        second.Status.Should().Be("fresh");
        second.OperationStatus.Should().Be("returned_existing");
        second.ContractHash.Should().Be(first.ContractHash);
    }

    [Theory]
    [InlineData("stale_scene", "scene_route_stale")]
    [InlineData("game_type_hash_mismatch", "game_type_structured_stale")]
    [InlineData("gdd_hash_mismatch", "generated_gdd_hash_mismatch")]
    [InlineData("requirement_map_scene_hash_mismatch", "requirement_map_invalid")]
    public async Task ContractFreeze_FreezeAsync_BlocksStaleOrMismatchedSources(string scenario, string domainCode)
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        await fixture.SeedRequirementMapAsync();
        fixture.ApplyContractScenario(scenario);
        var service = new PrototypeContractFreezeService(fixture.Store);

        var result = await service.FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());

        result.Status.Should().Be("blocked");
        result.OperationStatus.Should().Be("rejected");
        result.BlockingIssues.Should().Contain(issue => issue.DomainCode == domainCode);
    }

    [Fact]
    public async Task NewChainGuard_DoesNotBlockLegacyPrototypeContract()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        fixture.WriteJson("routes/prototype-contract/latest.json", """
        {
          "schema_version": 1,
          "route": "prototype-contract",
          "form_fields": {
            "game_type": "RPG"
          }
        }
        """);
        var project = await fixture.GetProjectAsync();
        var service = new PrototypeContractFreezeService(fixture.Store);

        var guard = service.EvaluateNewChainGuard(project);

        guard.NewChainActive.Should().BeFalse();
        guard.Allowed.Should().BeTrue();
        guard.Status.Should().Be("legacy_compatibility");
    }

    [Fact]
    public async Task NewChainGuard_BlocksExplicitNewChainUntilFreshContractExists()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        fixture.SeedConfirmedSceneRouteAndGdd();
        var project = await fixture.GetProjectAsync();
        var service = new PrototypeContractFreezeService(fixture.Store);

        var guard = service.EvaluateNewChainGuard(project);

        guard.NewChainActive.Should().BeTrue();
        guard.Allowed.Should().BeFalse();
        guard.Status.Should().Be("contract_missing");
    }

    private sealed class BackendContractFixture : IDisposable
    {
        private readonly TempSqliteDatabase _database;
        private readonly TempDirectory _workspaceRoot;
        private readonly TempDirectory _repoRoot;

        private BackendContractFixture(
            TempSqliteDatabase database,
            TempDirectory workspaceRoot,
            TempDirectory repoRoot,
            PhaseAMetadataStore store,
            string accountId,
            string projectId)
        {
            _database = database;
            _workspaceRoot = workspaceRoot;
            _repoRoot = repoRoot;
            Store = store;
            AccountId = accountId;
            ProjectId = projectId;
        }

        public PhaseAMetadataStore Store { get; }

        public string AccountId { get; }

        public string ProjectId { get; }

        public string GddHash { get; private set; } = "";

        public string SceneRouteHash { get; private set; } = "scene-route-hash-v1";

        public static async Task<BackendContractFixture> CreateAsync()
        {
            var database = TempSqliteDatabase.Create();
            var workspaceRoot = TempDirectory.Create("phase-a-backend-contract-workspaces");
            var repoRoot = TempDirectory.Create("phase-a-backend-contract-repo");
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
            {
                ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot.Path,
                ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspaceRoot.Path, "metadata.sqlite3"),
                ["PHASEA_REPOSITORY_ROOT"] = repoRoot.Path
            });
            await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
            var store = new PhaseAMetadataStore(database.ConnectionString, options);
            var accountId = await store.EnsureSingleAdminAsync();
            var creation = new ProjectCreationService(
                store,
                options,
                new ProjectRuleCatalog(),
                new ProjectWorkspaceSeeder(options),
                gameTypeMatchService: new FixedGameTypeMatchService());
            var result = await creation.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Demo RPG", "RPG", null, null, null, null));
            await store.SetProjectBootstrapStatusAsync(result.ProjectId!, "succeeded", null);
            return new BackendContractFixture(database, workspaceRoot, repoRoot, store, accountId, result.ProjectId!);
        }

        public async Task<ProjectSnapshot> GetProjectAsync()
        {
            return (await Store.GetProjectSnapshotAsync(ProjectId))!;
        }

        public void SeedConfirmedSceneRouteAndGdd(string? gddText = null)
        {
            var text = gddText ?? """
            # Demo RPG

            - Player must move on the field map and trigger one visible encounter.
            - HUD feedback must show HP, reward, and return-to-map state.
            """;
            WriteText("docs/gdd/GDD.md", text);
            GddHash = Sha256(NormalizeText(text));
            SceneRouteHash = "scene-route-hash-v1";
            WriteSceneRoute("confirmed", SceneRouteHash, GddHash, StructuredHash());
            WriteJson("meta/routes/gdd-document/latest.json", $$"""
            {
              "schema_version": "gdd-document-generation.v1",
              "route": "gdd-document-generation",
              "status": "ready",
              "generated_gdd_hash": "{{GddHash}}",
              "source_scene_route_hash": "{{SceneRouteHash}}"
            }
            """);
        }

        public async Task SeedRequirementMapAsync()
        {
            SeedConfirmedSceneRouteAndGdd();
            var result = await new GameDesignRequirementMapService(Store).CreateAsync(AccountId, ProjectId, new GameDesignRequirementMapRequest());
            result.Status.Should().Be("ready");
        }

        public void ApplyRequirementMapScenario(string scenario)
        {
            switch (scenario)
            {
                case "missing_gdd":
                    Delete("docs/gdd/GDD.md");
                    break;
                case "missing_scene":
                    Delete("meta/routes/scene-route/latest.json");
                    break;
                case "unconfirmed_scene":
                    WriteSceneRoute("draft", SceneRouteHash, GddHash, StructuredHash());
                    break;
                case "stale_scene":
                    WriteSceneRoute("stale", SceneRouteHash, GddHash, StructuredHash());
                    break;
                case "game_type_hash_mismatch":
                    WriteSceneRoute("confirmed", SceneRouteHash, GddHash, "old-game-type-hash");
                    break;
                case "gdd_hash_mismatch":
                    WriteSceneRoute("confirmed", SceneRouteHash, "old-gdd-hash", StructuredHash());
                    break;
            }
        }

        public void ApplyContractScenario(string scenario)
        {
            switch (scenario)
            {
                case "stale_scene":
                    WriteSceneRoute("stale", SceneRouteHash, GddHash, StructuredHash());
                    break;
                case "game_type_hash_mismatch":
                    WriteSceneRoute("confirmed", SceneRouteHash, GddHash, "old-game-type-hash");
                    break;
                case "gdd_hash_mismatch":
                    WriteSceneRoute("confirmed", SceneRouteHash, "old-gdd-hash", StructuredHash());
                    break;
                case "requirement_map_scene_hash_mismatch":
                    PatchRequirementMapSourceSceneHash("other-scene-hash");
                    break;
            }
        }

        public JsonDocument ReadJson(string relativePath)
        {
            return JsonDocument.Parse(File.ReadAllText(PathFor(relativePath), Encoding.UTF8));
        }

        public void WriteJson(string relativePath, string json)
        {
            WriteText(relativePath, json);
        }

        private void WriteSceneRoute(string status, string sceneHash, string gddHash, string structuredHash)
        {
            WriteJson("meta/routes/scene-route/latest.json", $$"""
            {
              "schema_version": "scene-route.v1",
              "route": "scene-route-confirmation",
              "status": "{{status}}",
              "source_game_type_structured_hash": "{{structuredHash}}",
              "source_gdd_form_hash": "gdd-form-hash-v1",
              "source_generated_gdd_hash": "{{gddHash}}",
              "source_contract_snapshot_hash": "contract-snapshot-hash-v1",
              "confirmed_scene_route_hash": "{{sceneHash}}",
              "scenes": [
                {
                  "scene_id": "field_map"
                }
              ]
            }
            """);
        }

        private void PatchRequirementMapSourceSceneHash(string value)
        {
            using var document = ReadJson("meta/routes/gdd-requirements/latest.json");
            var node = JsonSerializer.Deserialize<Dictionary<string, object?>>(document.RootElement.GetRawText())!;
            node["source_scene_route_hash"] = value;
            WriteJson("meta/routes/gdd-requirements/latest.json", JsonSerializer.Serialize(node, new JsonSerializerOptions(JsonSerializerDefaults.Web)
            {
                WriteIndented = true
            }));
        }

        private string StructuredHash()
        {
            return Sha256(NormalizeText(GetProjectAsync().GetAwaiter().GetResult().GameTypeMatchJson));
        }

        private void WriteText(string relativePath, string text)
        {
            var path = PathFor(relativePath);
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            File.WriteAllText(path, NormalizeText(text), Encoding.UTF8);
        }

        private void Delete(string relativePath)
        {
            var path = PathFor(relativePath);
            if (File.Exists(path))
            {
                File.Delete(path);
            }
        }

        private string PathFor(string relativePath)
        {
            var project = GetProjectAsync().GetAwaiter().GetResult();
            return Path.Combine(project.RepoPath, relativePath.Replace('/', Path.DirectorySeparatorChar));
        }

        public void Dispose()
        {
            _database.Dispose();
            _workspaceRoot.Dispose();
            _repoRoot.Dispose();
        }
    }

    private sealed class FixedGameTypeMatchService : IProjectGameTypeMatchService
    {
        public Task<ProjectGameTypeMatchEvidence> ResolveAsync(string gameTypeSource, CancellationToken cancellationToken)
        {
            var now = DateTimeOffset.UtcNow.ToString("O");
            return Task.FromResult(new ProjectGameTypeMatchEvidence(
                1,
                "matched",
                "matched_by_test",
                "test",
                gameTypeSource,
                "",
                "",
                ["RPG"],
                [],
                ["RPG"],
                ["rpg"],
                "rpg",
                "docs/game-type-guides/rpg.md",
                100,
                [],
                "",
                "test-catalog",
                now,
                now));
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

    private static string Sha256(string value)
    {
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(value))).ToLowerInvariant();
    }

    private static string NormalizeText(string text)
    {
        return text.Replace("\r\n", "\n").Trim();
    }
}
