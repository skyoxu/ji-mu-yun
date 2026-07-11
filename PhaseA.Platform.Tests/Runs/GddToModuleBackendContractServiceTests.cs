using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
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
    public async Task Phase1State_ConfirmSceneRouteAsync_WritesAuthoritySidecarAndRealHashReadback()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        var service = new GddToModulePhase1StateService(fixture.Store);
        var sceneRoute = new GameDesignSceneRouteDocument(
            "gdd-scene-route.v1",
            "multi",
            "route_map",
            [
                new GameDesignSceneRouteScene("route_map", "Route Map", "hub", true, "Choose the next node."),
                new GameDesignSceneRouteScene("combat", "Combat", "combat", true, "Win the encounter.")
            ],
            [new GameDesignSceneRouteTransition("route_map", "combat", "Select encounter", "route_map", ["hp", "deck"])],
            new GameDesignSingleSceneConfirmation(false, "Multiple states are required."),
            []);

        var result = await service.ConfirmSceneRouteAsync(fixture.AccountId, fixture.ProjectId, sceneRoute);
        var readback = await service.GetSceneRouteAsync(fixture.AccountId, fixture.ProjectId);

        result.Should().NotBeNull();
        result!.Status.Should().Be("confirmed");
        result.ConfirmedSceneRouteHash.Should().NotBeNullOrWhiteSpace();
        result.SourceGameTypeStructuredHash.Should().NotBeNullOrWhiteSpace();
        result.SourceContractSnapshotHash.Should().NotBeNullOrWhiteSpace();
        readback.Should().BeEquivalentTo(result, options => options.Excluding(item => item.OperationStatus));
        var sidecar = fixture.ReadJson("meta/routes/scene-route/latest.json");
        sidecar.RootElement.GetProperty("schema_version").GetString().Should().Be("scene-route.v1");
        sidecar.RootElement.GetProperty("confirmed_scene_route_hash").GetString().Should().Be(result.ConfirmedSceneRouteHash);
        sidecar.RootElement.GetProperty("scenes")[0].GetProperty("scene_id").GetString().Should().Be("route_map");
        sidecar.RootElement.GetProperty("source_boundary").GetProperty("authority_sources").GetArrayLength().Should().BeGreaterThan(0);
    }

    [Fact]
    public async Task Phase1State_RecordGeneratedGddAsync_WritesDocumentStateAndSceneHashThrough()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        var service = new GddToModulePhase1StateService(fixture.Store);
        await service.ConfirmSceneRouteAsync(fixture.AccountId, fixture.ProjectId, fixture.DefaultSceneRoute());
        fixture.WriteGdd("# Deckbuilder\n\n- Player must select a route node.\n");

        var result = await service.RecordGeneratedGddAsync(fixture.AccountId, fixture.ProjectId, "run-gdd-1");

        result.Should().NotBeNull();
        result!.Status.Should().Be("ready");
        result.GeneratedGddHash.Should().NotBeNullOrWhiteSpace();
        result.SceneRouteRecordedGeneratedGddHash.Should().Be(result.GeneratedGddHash);
        var documentState = fixture.ReadJson("meta/routes/gdd-document/latest.json");
        documentState.RootElement.GetProperty("generated_gdd_hash").GetString().Should().Be(result.GeneratedGddHash);
        var sceneState = fixture.ReadJson("meta/routes/scene-route/latest.json");
        sceneState.RootElement.GetProperty("source_generated_gdd_hash").GetString().Should().Be(result.GeneratedGddHash);
    }

    [Fact]
    public async Task Phase1State_ConfirmSceneRouteAsync_ReusesSameHashWithoutErasingGeneratedGddHash()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        var service = new GddToModulePhase1StateService(fixture.Store);
        var sceneRoute = fixture.DefaultSceneRoute();
        var first = await service.ConfirmSceneRouteAsync(fixture.AccountId, fixture.ProjectId, sceneRoute);
        fixture.WriteGdd("# Deckbuilder\n\n- Player must select a route node.\n");
        var gdd = await service.RecordGeneratedGddAsync(fixture.AccountId, fixture.ProjectId, "run-gdd-retry");

        var retry = await service.ConfirmSceneRouteAsync(fixture.AccountId, fixture.ProjectId, sceneRoute);

        first!.OperationStatus.Should().Be("created_run");
        retry!.OperationStatus.Should().Be("returned_existing");
        retry.ConfirmedSceneRouteHash.Should().Be(first.ConfirmedSceneRouteHash);
        retry.SourceGeneratedGddHash.Should().Be(gdd!.GeneratedGddHash);
    }

    [Fact]
    public async Task Phase1State_RecordGeneratedGddAsync_FailsClosedForInvalidSceneState()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        fixture.WriteGdd("# Deckbuilder\n\n- Player must select a route node.\n");
        fixture.WriteJson("meta/routes/scene-route/latest.json", "{ invalid");
        var service = new GddToModulePhase1StateService(fixture.Store);

        var result = await service.RecordGeneratedGddAsync(fixture.AccountId, fixture.ProjectId, "run-gdd-2");

        result.Should().NotBeNull();
        result!.Status.Should().Be("blocked");
        result.BlockingIssues.Should().Contain(issue => issue.DomainCode == "gdd_scene_hash_write_failed");
        File.Exists(fixture.PathForTest("meta/routes/gdd-document/latest.json")).Should().BeFalse();
    }

    [Fact]
    public async Task Phase1State_GetGddDocumentStateAsync_RejectsIncompleteOrMismatchedWriteThrough()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        var service = new GddToModulePhase1StateService(fixture.Store);
        await service.ConfirmSceneRouteAsync(fixture.AccountId, fixture.ProjectId, fixture.DefaultSceneRoute());
        fixture.WriteGdd("# Deckbuilder\n\n- Player must select a route node.\n");
        var recorded = await service.RecordGeneratedGddAsync(fixture.AccountId, fixture.ProjectId, "run-gdd-partial");
        recorded!.Status.Should().Be("ready");

        var documentNode = JsonNode.Parse(File.ReadAllText(fixture.PathForTest("meta/routes/gdd-document/latest.json"), Encoding.UTF8))!.AsObject();
        documentNode["status"] = "writing";
        fixture.WriteJson("meta/routes/gdd-document/latest.json", documentNode.ToJsonString());
        var incomplete = await service.GetGddDocumentStateAsync(fixture.AccountId, fixture.ProjectId);
        incomplete!.BlockingIssues.Should().Contain(issue => issue.DomainCode == "gdd_document_write_incomplete");

        documentNode["status"] = "ready";
        fixture.WriteJson("meta/routes/gdd-document/latest.json", documentNode.ToJsonString());
        var sceneNode = JsonNode.Parse(File.ReadAllText(fixture.PathForTest("meta/routes/scene-route/latest.json"), Encoding.UTF8))!.AsObject();
        sceneNode["source_generated_gdd_hash"] = "partial-write-hash";
        fixture.WriteJson("meta/routes/scene-route/latest.json", sceneNode.ToJsonString());
        var mismatched = await service.GetGddDocumentStateAsync(fixture.AccountId, fixture.ProjectId);
        mismatched!.BlockingIssues.Should().Contain(issue => issue.DomainCode == "gdd_document_state_stale");
    }

    [Fact]
    public async Task Phase1State_ReadAndWriteOperations_EnforceAccountBoundary()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        var service = new GddToModulePhase1StateService(fixture.Store);

        var confirm = await service.ConfirmSceneRouteAsync("other-account", fixture.ProjectId, fixture.DefaultSceneRoute());
        var sceneReadback = await service.GetSceneRouteAsync("other-account", fixture.ProjectId);
        var gddReadback = await service.GetGddDocumentStateAsync("other-account", fixture.ProjectId);

        confirm.Should().BeNull();
        sceneReadback.Should().BeNull();
        gddReadback.Should().BeNull();
        File.Exists(fixture.PathForTest("meta/routes/scene-route/latest.json")).Should().BeFalse();
    }

    [Fact]
    public async Task RequirementMap_CreateAsync_WritesStableRowsAndSourceBoundary()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        fixture.SeedConfirmedSceneRouteAndGdd();
        var service = new GameDesignRequirementMapService(fixture.Store);

        var result = await service.CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignRequirementMapRequest());

        result.Status.Should().Be("needs_review");
        result.OperationStatus.Should().Be("created_run");
        result.Requirements.Select(item => item.RequirementId).Should().Equal("REQ-001", "REQ-002");
        result.Requirements.Should().Contain(item => item.Kind == "ui");
        result.Requirements.Should().OnlyContain(item => item.AcceptanceMarkers.Contains("structured_llm_fallback:llm_unavailable"));
        var sidecar = fixture.ReadJson("meta/routes/gdd-requirements/latest.json");
        sidecar.RootElement.GetProperty("schema_version").GetString().Should().Be("gdd-requirements.v1");
        sidecar.RootElement.GetProperty("source_boundary_enforced").GetBoolean().Should().BeTrue();
        sidecar.RootElement.GetProperty("requirements")[0].GetProperty("requirement_id").GetString().Should().Be("REQ-001");
    }

    [Fact]
    public async Task RequirementMap_CreateAsync_UsesStructuredLlmAndPreservesCapabilityEvidence()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        fixture.SeedConfirmedSceneRouteAndGdd();
        var engine = new FixedRequirementMapLlmEngine("""
        {
          "requirements": [
            {
              "requirement_id": "REQ-001",
              "normalized_requirement": "Player selects the next route node.",
              "priority": "P0",
              "kind": "scene",
              "mapped_scene_ids": ["field_map"],
              "mapped_required_module_ids": ["route_map"],
              "status": "mapped",
              "capability_domain_ids": ["ui_layout_scale_coordinates", "ui_input_pointer_gesture"],
              "godot_third_person_camera_profile": {
                "rig_ref": "res://camera/third_person_rig.tscn",
                "target_owner": "player",
                "input_owner": "camera_input",
                "collision_owner": "camera_rig",
                "validation_method": "camera state test"
              },
              "acceptance_markers": ["route node selection is visible"]
            },
            {
              "requirement_id": "REQ-002",
              "normalized_requirement": "HUD shows HP and reward feedback.",
              "priority": "P1",
              "kind": "ui",
              "mapped_scene_ids": ["field_map"],
              "mapped_required_module_ids": ["combat_hud", "reward_panel"],
              "status": "mapped",
              "capability_domain_ids": ["ui_component_system", "ui_overlays_feedback"],
              "godot_ui_update_ownership": {
                "construction_owner": "combat_hud",
                "update_mode": "signal_driven",
                "state_owner": "combat_state",
                "cleanup_policy": "disconnect_signals_on_exit",
                "stable_item_identity": "reward_id"
              },
              "acceptance_markers": ["HP feedback is visible", "reward selection is actionable"]
            }
          ]
        }
        """);
        var service = new GameDesignRequirementMapService(fixture.Store, engine);

        var result = await service.CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignRequirementMapRequest(Model: "gpt-5.1-codex"));

        result.Status.Should().Be("ready");
        engine.Requests.Should().ContainSingle();
        engine.Requests[0].RequireJsonObject.Should().BeTrue();
        engine.Requests[0].Prompt.Should().NotContain("docs/game-type-guides/");
        result.Requirements[1].CapabilityDomainIds.Should().Contain("ui_overlays_feedback");
        result.Requirements[1].GodotUiUpdateOwnership.Should().NotBeNull();
        result.Requirements[0].GodotThirdPersonCameraProfile.Should().NotBeNull();
        var sidecar = fixture.ReadJson("meta/routes/gdd-requirements/latest.json");
        sidecar.RootElement.GetProperty("requirements")[1].GetProperty("godot_ui_update_ownership").GetProperty("state_owner").GetString().Should().Be("combat_state");
        sidecar.RootElement.GetProperty("source_boundary").GetProperty("prompt_evidence_refs").GetArrayLength().Should().Be(1);
    }

    [Theory]
    [InlineData("{ invalid", "llm_json_parse_failed")]
    [InlineData("{\"requirements\":[{\"requirement_id\":\"REQ-001\"},{\"requirement_id\":\"REQ-001\"}]}", "duplicate_requirement_id")]
    [InlineData("{\"requirements\":[{\"requirement_id\":\"REQ-001\",\"normalized_requirement\":\"Only one row\",\"priority\":\"P0\",\"kind\":\"scene\",\"mapped_scene_ids\":[\"field_map\"],\"mapped_required_module_ids\":[\"route_map\"],\"status\":\"mapped\"}]}", "llm_requirement_coverage_incomplete")]
    public async Task RequirementMap_CreateAsync_FallsBackToNeedsReviewForInvalidStructuredLlm(string json, string marker)
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        fixture.SeedConfirmedSceneRouteAndGdd();
        var service = new GameDesignRequirementMapService(fixture.Store, new FixedRequirementMapLlmEngine(json));

        var result = await service.CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignRequirementMapRequest());

        result.Status.Should().Be("needs_review");
        result.Requirements.Should().NotBeEmpty();
        result.Requirements.Should().Contain(item => item.AcceptanceMarkers.Contains($"structured_llm_fallback:{marker}"));
    }

    [Fact]
    public async Task RequirementMap_CreateAsync_RejectsSameCountLlmRowsThatReplaceTheDeterministicFloor()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        fixture.SeedConfirmedSceneRouteAndGdd();
        var service = new GameDesignRequirementMapService(fixture.Store, new FixedRequirementMapLlmEngine("""
        {
          "requirements": [
            { "requirement_id": "REQ-101", "normalized_requirement": "Replacement one", "priority": "P0", "kind": "scene", "mapped_scene_ids": ["field_map"], "mapped_required_module_ids": ["field_map"], "status": "mapped" },
            { "requirement_id": "REQ-102", "normalized_requirement": "Replacement two", "priority": "P1", "kind": "ui", "mapped_scene_ids": ["field_map"], "mapped_required_module_ids": ["combat_hud"], "status": "mapped", "capability_domain_ids": ["ui_component_system"] }
          ]
        }
        """));

        var result = await service.CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignRequirementMapRequest());

        result.Status.Should().Be("needs_review");
        result.Requirements.Select(item => item.RequirementId).Should().Equal("REQ-001", "REQ-002");
        result.Requirements.Should().OnlyContain(item => item.AcceptanceMarkers.Contains("structured_llm_fallback:llm_requirement_coverage_incomplete"));
    }

    [Fact]
    public async Task RequirementMap_CreateAsync_ReusesSingleFlightForConcurrentSameProjectRequests()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        fixture.SeedConfirmedSceneRouteAndGdd();
        var engine = new BlockingRequirementMapLlmEngine("""
        {
          "requirements": [
            {
              "requirement_id": "REQ-001",
              "normalized_requirement": "Player moves on the field map.",
              "priority": "P0",
              "kind": "scene",
              "mapped_scene_ids": ["field_map"],
              "mapped_required_module_ids": ["field_map"],
              "status": "mapped"
            },
            {
              "requirement_id": "REQ-002",
              "normalized_requirement": "HUD shows HP and reward feedback.",
              "priority": "P1",
              "kind": "ui",
              "mapped_scene_ids": ["field_map"],
              "mapped_required_module_ids": ["combat_hud"],
              "status": "mapped",
              "capability_domain_ids": ["ui_component_system"]
            }
          ]
        }
        """);
        var service = new GameDesignRequirementMapService(fixture.Store, engine);

        var first = service.CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignRequirementMapRequest(Refresh: true));
        await engine.Started;
        var second = service.CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignRequirementMapRequest());
        await Task.Delay(50);
        engine.CallCount.Should().Be(1);
        engine.Release();

        var results = await Task.WhenAll(first, second);
        results.Select(item => item.SourceRequirementMapHash).Distinct().Should().ContainSingle();
        engine.CallCount.Should().Be(1);
        results.Should().Contain(item => item.OperationStatus == "created_run");
        results.Should().Contain(item => item.OperationStatus == "returned_existing");
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
        var diagnostics = await fixture.Store.ListProjectDiagnosticSpoolForAccountAsync(fixture.AccountId, fixture.ProjectId);
        diagnostics.Should().Contain(item => item.RouteId == "gdd-requirements" && item.FailureFamily == domainCode && item.Severity == "P1");
    }

    [Fact]
    public async Task RequirementMap_CreateAsync_DeduplicatesUnresolvedDiagnosticsAcrossRetries()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        fixture.SeedConfirmedSceneRouteAndGdd();
        fixture.ApplyRequirementMapScenario("missing_gdd");
        var service = new GameDesignRequirementMapService(fixture.Store);

        await service.CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignRequirementMapRequest());
        await service.CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignRequirementMapRequest());

        var diagnostics = await fixture.Store.ListProjectDiagnosticSpoolForAccountAsync(fixture.AccountId, fixture.ProjectId);
        diagnostics.Count(item => item.RouteId == "gdd-requirements" && item.FailureFamily == "gdd_not_found").Should().Be(1);
    }

    [Fact]
    public async Task RequirementMap_CreateAsync_QueuesConflictForAdminReviewAndContractFreezeFailsClosed()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        fixture.SeedConfirmedSceneRouteAndGdd();
        var service = new GameDesignRequirementMapService(fixture.Store, new FixedRequirementMapLlmEngine("""
        {
          "requirements": [
            { "requirement_id": "REQ-001", "normalized_requirement": "First requirement", "priority": "P0", "kind": "scene", "mapped_scene_ids": ["field_map"], "mapped_required_module_ids": ["field_map"], "status": "conflict" },
            { "requirement_id": "REQ-002", "normalized_requirement": "Second requirement", "priority": "P1", "kind": "ui", "mapped_scene_ids": ["field_map"], "mapped_required_module_ids": ["combat_hud"], "status": "mapped", "capability_domain_ids": ["ui_component_system"] }
          ]
        }
        """));

        var requirementMap = await service.CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignRequirementMapRequest());
        var queue = await fixture.Store.ListProjectAdminReviewQueueForProjectAsync(fixture.AccountId, fixture.ProjectId, "open");
        var contract = await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());

        requirementMap.Status.Should().Be("needs_review");
        queue.Should().Contain(item => item.RequirementId == "REQ-001" && item.RouteId == "gdd-requirements");
        contract.Status.Should().Be("blocked");
        contract.BlockingIssues.Should().Contain(issue => issue.DomainCode == "admin_review_blocked");
    }

    [Fact]
    public async Task ContractFreeze_FreezeAsync_BlocksNeedsReviewRequirementMapWithoutAdminQueueRow()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        fixture.SeedConfirmedSceneRouteAndGdd();
        await new GameDesignRequirementMapService(fixture.Store, new FixedRequirementMapLlmEngine("{ invalid"))
            .CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignRequirementMapRequest());

        var contract = await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());

        contract.Status.Should().Be("blocked");
        contract.BlockingIssues.Should().Contain(issue => issue.DomainCode == "requirement_map_invalid");
        File.Exists(fixture.PathForTest("routes/prototype-contract/latest.json")).Should().BeFalse();
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
        result.SourceGodotUiContractHash.Should().NotBe("unknown").And.NotBeNullOrWhiteSpace();
        result.UiStyleId.Should().Be("godot_cosmic");
        result.UiStyleVersion.Should().Be("1");
        result.SourceUiStyleContractHash.Should().NotBe("unknown").And.NotBeNullOrWhiteSpace();
        result.UiStyleSnapshotHash.Should().NotBe("unknown").And.NotBeNullOrWhiteSpace();
        var canonical = fixture.ReadJson("routes/prototype-contract/latest.json");
        var mirror = fixture.ReadJson("meta/routes/prototype-contract/latest.json");
        canonical.RootElement.GetProperty("schema_version").GetString().Should().Be("prototype-contract.v2");
        canonical.RootElement.GetProperty("source_gdd_hash").GetString().Should().Be(fixture.GddHash);
        mirror.RootElement.GetProperty("contract_hash").GetString().Should().Be(result.ContractHash);
    }

    [Fact]
    public async Task ContractFreeze_GetStatusAsync_AcceptsMirrorWithMatchingContractHashAndRejectsMismatch()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        await fixture.SeedRequirementMapAsync();
        var service = new PrototypeContractFreezeService(fixture.Store);
        var frozen = await service.FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        fixture.WriteJson("meta/routes/prototype-contract/latest.json", $$"""
        {
          "schema_version": "prototype-contract.v2",
          "contract_hash": "{{frozen.ContractHash}}",
          "updated_utc": "mirror-readback-only"
        }
        """);

        var matching = await service.GetStatusAsync(fixture.AccountId, fixture.ProjectId);

        matching!.Status.Should().Be("fresh");
        fixture.WriteJson("meta/routes/prototype-contract/latest.json", """
        {
          "schema_version": "prototype-contract.v2",
          "contract_hash": "different"
        }
        """);
        var mismatched = await service.GetStatusAsync(fixture.AccountId, fixture.ProjectId);
        mismatched!.Status.Should().Be("stale");
        mismatched.Freshness.StaleReasons.Should().Contain("mirror_hash_mismatch");
    }

    [Fact]
    public async Task ContractFreeze_GetStatusAsync_RejectsTamperedCanonicalHashAndMissingFreshnessField()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        await fixture.SeedRequirementMapAsync();
        var service = new PrototypeContractFreezeService(fixture.Store);
        await service.FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        var canonicalPath = fixture.PathForTest("routes/prototype-contract/latest.json");
        var node = JsonNode.Parse(File.ReadAllText(canonicalPath, Encoding.UTF8))!.AsObject();
        node["requirement_traceability"] = new JsonArray();
        node.Remove("source_ui_style_contract_hash");
        fixture.WriteJson("routes/prototype-contract/latest.json", node.ToJsonString());

        var status = await service.GetStatusAsync(fixture.AccountId, fixture.ProjectId);

        status!.Status.Should().Be("stale");
        status.Freshness.StaleReasons.Should().Contain("contract_hash_mismatch");
        status.Freshness.StaleReasons.Should().Contain("source_ui_style_contract_hash");
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

    [Fact]
    public async Task ContractFreeze_FreezeAsync_SerializesConcurrentSameProjectWrites()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        await fixture.SeedRequirementMapAsync();
        var service = new PrototypeContractFreezeService(fixture.Store);

        var results = await Task.WhenAll(Enumerable.Range(0, 20).Select(index =>
            service.FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest(Refresh: index == 0))));

        results.Should().OnlyContain(item => item.Status == "fresh");
        results.Select(item => item.ContractHash).Distinct().Should().ContainSingle();
        using var canonical = fixture.ReadJson("routes/prototype-contract/latest.json");
        using var mirror = fixture.ReadJson("meta/routes/prototype-contract/latest.json");
        canonical.RootElement.GetProperty("contract_hash").GetString().Should().Be(results[0].ContractHash);
        mirror.RootElement.GetProperty("contract_hash").GetString().Should().Be(results[0].ContractHash);
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
    public async Task ContractFreeze_FreezeAsync_BlocksOpenP0P1AdminReviewQueueItems()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        await fixture.SeedRequirementMapAsync();
        await fixture.Store.UpsertProjectAdminReviewQueueEntryAsync(new ProjectAdminReviewQueueCommand(
            fixture.AccountId,
            fixture.ProjectId,
            "gdd-requirements",
            "REQ-001",
            "P1",
            "Requirement conflict requires admin review.",
            "meta/routes/gdd-requirements/latest.json",
            "[]"));
        var service = new PrototypeContractFreezeService(fixture.Store);

        var result = await service.FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());

        result.Status.Should().Be("blocked");
        result.BlockingIssues.Should().Contain(issue => issue.DomainCode == "admin_review_blocked");
        result.BlockingIssues.SelectMany(issue => issue.EvidenceRefs).Should().NotContain(item => item.Path.Contains("metadata:", StringComparison.Ordinal));
        result.BlockingIssues.Should().NotContain(issue => issue.IssueId.Contains("admin-review:", StringComparison.Ordinal));
        var diagnostics = await fixture.Store.ListProjectDiagnosticSpoolForAccountAsync(fixture.AccountId, fixture.ProjectId);
        diagnostics.Should().Contain(item => item.RouteId == "prototype-contract" && item.FailureFamily == "admin_review_blocked");
    }

    [Fact]
    public async Task ContractFreeze_FreezeAsync_DoesNotLoseProjectBlockerBehindGlobalQueueLimit()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        await fixture.SeedRequirementMapAsync();
        await fixture.Store.UpsertProjectAdminReviewQueueEntryAsync(new ProjectAdminReviewQueueCommand(
            fixture.AccountId,
            fixture.ProjectId,
            "gdd-requirements",
            "REQ-TARGET",
            "P1",
            "Target project blocker.",
            "meta/routes/gdd-requirements/latest.json",
            "[]"));
        await Task.Delay(5);
        for (var index = 0; index < 500; index++)
        {
            await fixture.Store.UpsertProjectAdminReviewQueueEntryAsync(new ProjectAdminReviewQueueCommand(
                fixture.AccountId,
                $"other-project-{index:D3}",
                "gdd-requirements",
                $"REQ-{index:D3}",
                "P1",
                $"Unrelated blocker {index}.",
                "meta/routes/gdd-requirements/latest.json",
                "[]"));
        }

        var result = await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());

        result.Status.Should().Be("blocked");
        result.BlockingIssues.Should().Contain(issue => issue.DomainCode == "admin_review_blocked");
    }

    [Fact]
    public async Task ProjectMutationLockRegistry_ReclaimsIdleProjectEntries()
    {
        var registry = new ProjectMutationLockRegistry();
        var first = await registry.AcquireAsync("account", "project", CancellationToken.None);
        var secondTask = registry.AcquireAsync("account", "project", CancellationToken.None).AsTask();
        registry.EntryCount.Should().Be(1);
        await first.DisposeAsync();
        var second = await secondTask;
        await second.DisposeAsync();

        registry.EntryCount.Should().Be(0);
    }

    [Fact]
    public async Task DeckbuilderChain_PreservesRouteHandHudRewardAndStyleEvidence()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        fixture.SeedConfirmedSceneRouteAndGdd("""
        # Deckbuilder

        - Player must select a route map node with visible action feedback.
        - Player must drag a hand card with payload identity, cancel, commit, and rollback behavior.
        - Combat HUD must show health, energy, enemy intent, and action feedback.
        - Reward selection must expose actionable card choices and confirmation state.
        """);
        var engine = new FixedRequirementMapLlmEngine("""
        {
          "requirements": [
            {"requirement_id":"REQ-001","normalized_requirement":"Select a route map node.","priority":"P0","kind":"ui","mapped_scene_ids":["field_map"],"mapped_required_module_ids":["route_map"],"status":"mapped","capability_domain_ids":["ui_layout_scale_coordinates","ui_input_pointer_gesture"],"acceptance_markers":["route_map interaction region"]},
            {"requirement_id":"REQ-002","normalized_requirement":"Drag a hand card with cancel, commit, and rollback.","priority":"P1","kind":"input","mapped_scene_ids":["field_map"],"mapped_required_module_ids":["deck_hand"],"status":"mapped","capability_domain_ids":["ui_input_pointer_gesture","ui_state_data_binding"],"acceptance_markers":["payload identity","cancel","commit","rollback","keyboard gamepad equivalent"]},
            {"requirement_id":"REQ-003","normalized_requirement":"Combat HUD shows health, energy, and enemy intent.","priority":"P1","kind":"ui","mapped_scene_ids":["field_map"],"mapped_required_module_ids":["combat_hud"],"status":"mapped","capability_domain_ids":["ui_component_system","ui_overlays_feedback"],"acceptance_markers":["combat HUD feedback visible"]},
            {"requirement_id":"REQ-004","normalized_requirement":"Reward selection exposes actionable card choices.","priority":"P1","kind":"ui","mapped_scene_ids":["field_map"],"mapped_required_module_ids":["reward_panel"],"status":"mapped","capability_domain_ids":["ui_component_system","ui_state_data_binding"],"acceptance_markers":["reward option confirmation"]}
          ]
        }
        """);
        var requirementMap = await new GameDesignRequirementMapService(fixture.Store, engine)
            .CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignRequirementMapRequest(Refresh: true));
        var contract = await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());

        requirementMap.Status.Should().Be("ready", JsonSerializer.Serialize(requirementMap.Requirements));
        requirementMap.Requirements.SelectMany(item => item.MappedRequiredModuleIds).Should().Contain(["route_map", "deck_hand", "combat_hud", "reward_panel"]);
        requirementMap.Requirements.Single(item => item.RequirementId == "REQ-002").AcceptanceMarkers.Should().Contain(["payload identity", "cancel", "commit", "rollback", "keyboard gamepad equivalent"]);
        contract.Status.Should().Be("fresh");
        contract.UiStyleId.Should().Be("godot_cosmic");
        contract.SourceGodotUiContractHash.Should().NotBeNullOrWhiteSpace();
        contract.SourceUiStyleContractHash.Should().NotBeNullOrWhiteSpace();
        contract.UiStyleSnapshotHash.Should().NotBeNullOrWhiteSpace();
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

        public GameDesignSceneRouteDocument DefaultSceneRoute()
        {
            return new GameDesignSceneRouteDocument(
                "gdd-scene-route.v1",
                "multi",
                "route_map",
                [
                    new GameDesignSceneRouteScene("route_map", "Route Map", "hub", true, "Choose the next node."),
                    new GameDesignSceneRouteScene("combat", "Combat", "combat", true, "Win the encounter.")
                ],
                [new GameDesignSceneRouteTransition("route_map", "combat", "Select encounter", "route_map", ["hp", "deck"])],
                new GameDesignSingleSceneConfirmation(false, "Multiple states are required."),
                []);
        }

        public void WriteGdd(string text)
        {
            WriteText("docs/gdd/GDD.md", text);
        }

        public string PathForTest(string relativePath)
        {
            return PathFor(relativePath);
        }

        public async Task SeedRequirementMapAsync()
        {
            SeedConfirmedSceneRouteAndGdd();
            var result = await new GameDesignRequirementMapService(Store, new FixedRequirementMapLlmEngine("""
            {
              "requirements": [
                { "requirement_id": "REQ-001", "normalized_requirement": "Player moves on the field map.", "priority": "P0", "kind": "scene", "mapped_scene_ids": ["field_map"], "mapped_required_module_ids": ["field_map"], "status": "mapped" },
                { "requirement_id": "REQ-002", "normalized_requirement": "HUD shows HP and reward feedback.", "priority": "P1", "kind": "ui", "mapped_scene_ids": ["field_map"], "mapped_required_module_ids": ["combat_hud"], "status": "mapped", "capability_domain_ids": ["ui_component_system", "ui_overlays_feedback"] }
              ]
            }
            """)).CreateAsync(AccountId, ProjectId, new GameDesignRequirementMapRequest());
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

    private sealed class FixedRequirementMapLlmEngine : ILlmRouteEngine
    {
        private readonly string _json;

        public FixedRequirementMapLlmEngine(string json)
        {
            _json = json;
        }

        public List<LlmRouteRequest> Requests { get; } = [];

        public Task<LlmRouteResult> CompleteAsync(LlmRouteRequest request, CancellationToken cancellationToken = default)
        {
            Requests.Add(request);
            var valid = _json.TrimStart().StartsWith('{') && !_json.Contains("{ invalid", StringComparison.Ordinal);
            return Task.FromResult(new LlmRouteResult(
                valid,
                _json,
                valid ? _json : null,
                request.Model,
                valid ? null : "llm_json_parse_failed",
                valid ? null : "invalid_json",
                valid ? 0 : 1,
                "",
                "",
                null,
                1,
                request.Prompt.Length,
                Encoding.UTF8.GetByteCount(request.Prompt),
                1));
        }
    }

    private sealed class BlockingRequirementMapLlmEngine : ILlmRouteEngine
    {
        private readonly string _json;
        private readonly TaskCompletionSource _started = new(TaskCreationOptions.RunContinuationsAsynchronously);
        private readonly TaskCompletionSource _release = new(TaskCreationOptions.RunContinuationsAsynchronously);
        private int _callCount;

        public BlockingRequirementMapLlmEngine(string json)
        {
            _json = json;
        }

        public Task Started => _started.Task;

        public int CallCount => Volatile.Read(ref _callCount);

        public void Release() => _release.TrySetResult();

        public async Task<LlmRouteResult> CompleteAsync(LlmRouteRequest request, CancellationToken cancellationToken = default)
        {
            Interlocked.Increment(ref _callCount);
            _started.TrySetResult();
            await _release.Task.WaitAsync(cancellationToken);
            return new LlmRouteResult(true, _json, _json, request.Model, null, null, 0, "", "", null, 1, request.Prompt.Length, Encoding.UTF8.GetByteCount(request.Prompt), 1);
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
