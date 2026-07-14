using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using FluentAssertions;
using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Prototypes;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Tests.Data;
using PhaseA.Platform.Workspaces;
using PhaseA.Platform.Workflow;
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
        sidecar.RootElement.GetProperty("status_dimension").GetString().Should().Be(RouteStatusVocabulary.SceneRouteConfirmation);
        sidecar.RootElement.GetProperty("status_allowed_values").EnumerateArray()
            .Select(item => item.GetString())
            .Should().Contain("confirmed");
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
        var runId = await fixture.CreateGddPromptRunAsync("ready");

        var result = await service.RecordGeneratedGddAsync(fixture.AccountId, fixture.ProjectId, runId);

        result.Should().NotBeNull();
        result!.Status.Should().Be("ready");
        result.GeneratedGddHash.Should().NotBeNullOrWhiteSpace();
        result.SceneRouteRecordedGeneratedGddHash.Should().Be(result.GeneratedGddHash);
        var project = await fixture.GetProjectAsync();
        var expectedAuthorityHashes = fixture.RecoveryAuthorityHashes(project);
        var documentState = fixture.ReadJson("meta/routes/gdd-document/latest.json");
        documentState.RootElement.GetProperty("status_dimension").GetString().Should().Be(RouteStatusVocabulary.RouteReadback);
        documentState.RootElement.GetProperty("status_allowed_values").EnumerateArray()
            .Select(item => item.GetString())
            .Should().Contain("ready");
        documentState.RootElement.GetProperty("generated_gdd_hash").GetString().Should().Be(result.GeneratedGddHash);
        var boundary = documentState.RootElement.GetProperty("source_boundary");
        boundary.GetProperty("authority_sources").EnumerateArray().Select(item => item.GetString()).Should().ContainInOrder(
            HostedRouteRecoveryContract.ParsedRouteProfileSource,
            HostedRouteRecoveryContract.SelectedRouteSkillPromptBlockSource);
        boundary.GetProperty("source_hashes").GetProperty(HostedRouteRecoveryContract.ParsedRouteProfileHashKey).GetString()
            .Should().Be(expectedAuthorityHashes[HostedRouteRecoveryContract.ParsedRouteProfileHashKey]);
        boundary.GetProperty("source_hashes").GetProperty(HostedRouteRecoveryContract.SelectedRouteSkillPromptBlockHashKey).GetString()
            .Should().Be(expectedAuthorityHashes[HostedRouteRecoveryContract.SelectedRouteSkillPromptBlockHashKey]);
        var sceneState = fixture.ReadJson("meta/routes/scene-route/latest.json");
        sceneState.RootElement.GetProperty("source_generated_gdd_hash").GetString().Should().Be(result.GeneratedGddHash);
        File.Exists(fixture.PathForTest("meta/routes/gdd-document/prompt-evidence.json")).Should().BeTrue();
        var routePromptEvidence = fixture.ReadJson("meta/routes/gdd-document/prompt-evidence.json");
        routePromptEvidence.RootElement.GetProperty("source_hashes")
            .GetProperty(HostedRouteRecoveryContract.ParsedRouteProfileHashKey).GetString()
            .Should().Be(expectedAuthorityHashes[HostedRouteRecoveryContract.ParsedRouteProfileHashKey]);
        routePromptEvidence.RootElement.GetProperty("source_hashes")
            .GetProperty(HostedRouteRecoveryContract.SelectedRouteSkillPromptBlockHashKey).GetString()
            .Should().Be(expectedAuthorityHashes[HostedRouteRecoveryContract.SelectedRouteSkillPromptBlockHashKey]);
        var routeBindings = (await fixture.Store.ListProjectRoutePromptEvidenceBindingsAsync(fixture.ProjectId))
            .ToDictionary(binding => binding.RouteId, StringComparer.Ordinal);
        var routeReadback = new ProjectRouteStateArtifactService().Read(await fixture.GetProjectAsync(), routeBindings);
        routeReadback.BlockingIssues.Should().NotContain(issue =>
            issue.IssueId.StartsWith("meta/routes/gdd-document/latest.json:prompt_evidence", StringComparison.Ordinal));
        var statusReadback = await service.GetGddDocumentStateAsync(fixture.AccountId, fixture.ProjectId);
        statusReadback!.Status.Should().Be("ready");

        using var changedPromptPolicy = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        var staleReadback = new ProjectRouteStateArtifactService().Read(project, routeBindings);
        staleReadback.BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/gdd-document/latest.json:source_hashes_authority_mismatch");
    }

    [Fact]
    public async Task Phase1State_ConfirmSceneRouteAsync_ReusesSameHashWithoutErasingGeneratedGddHash()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        var service = new GddToModulePhase1StateService(fixture.Store);
        var sceneRoute = fixture.DefaultSceneRoute();
        var first = await service.ConfirmSceneRouteAsync(fixture.AccountId, fixture.ProjectId, sceneRoute);
        fixture.WriteGdd("# Deckbuilder\n\n- Player must select a route node.\n");
        var promptRunId = await fixture.CreateGddPromptRunAsync("retry");
        var gdd = await service.RecordGeneratedGddAsync(fixture.AccountId, fixture.ProjectId, promptRunId);

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
    public async Task Phase1State_RecordGeneratedGddAsync_FailsClosedWithoutRunPromptArtifact()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        var service = new GddToModulePhase1StateService(fixture.Store);
        await service.ConfirmSceneRouteAsync(fixture.AccountId, fixture.ProjectId, fixture.DefaultSceneRoute());
        fixture.WriteGdd("# Deckbuilder\n\n- Player must select a route node.\n");
        var project = await fixture.GetProjectAsync();
        var recoveryAuthorityHashes = fixture.RecoveryAuthorityHashes(project);
        var runId = await fixture.Store.CreateRunAsync(fixture.ProjectId, project.WorkspaceId, "game-design-gdd");
        await fixture.Store.CompleteRunAsync(runId, "succeeded", 0, "", "", JsonSerializer.Serialize(new
        {
            generated_gdd_hash = Sha256(NormalizeText(File.ReadAllText(fixture.PathForTest("docs/gdd/GDD.md"), Encoding.UTF8))),
            recovery_source_order_ref = HostedRouteRecoveryContract.ContractId,
            recovery_source_order = HostedRouteRecoveryContract.SourceOrder,
            source_hashes = recoveryAuthorityHashes,
            prompt_manifest = new
            {
                execution_prompt_hash = new string('a', 64),
                persisted_prompt_hash = new string('b', 64),
                prompt_artifact_ref = "logs/phase-a-gdd/missing/prompt.md",
                prompt_source_evidence_ref = "logs/phase-a-gdd/missing/evidence.json",
                redacted = true
            }
        }));

        var result = await service.RecordGeneratedGddAsync(fixture.AccountId, fixture.ProjectId, runId);

        result!.Status.Should().Be("blocked");
        result.BlockingIssues.Should().Contain(issue => issue.DomainCode == "gdd_prompt_evidence_missing");
        File.Exists(fixture.PathForTest("meta/routes/gdd-document/latest.json")).Should().BeFalse();
    }

    [Fact]
    public async Task Phase1State_RecordGeneratedGddAsync_FailsClosedWhenPersistedPromptWasTampered()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        var service = new GddToModulePhase1StateService(fixture.Store);
        await service.ConfirmSceneRouteAsync(fixture.AccountId, fixture.ProjectId, fixture.DefaultSceneRoute());
        fixture.WriteGdd("# Deckbuilder\n\n- Player must select a route node.\n");
        var runId = await fixture.CreateGddPromptRunAsync("tampered");
        var promptArtifact = (await fixture.Store.ListArtifactsForRunAsync(runId))
            .Single(artifact => artifact.ArtifactType == GameDesignDocumentService.PromptArtifactType);
        fixture.WriteText(promptArtifact.RelativePath, "Tampered after source scan.");

        var result = await service.RecordGeneratedGddAsync(fixture.AccountId, fixture.ProjectId, runId);

        result.Should().NotBeNull();
        result!.Status.Should().Be("blocked");
        result.BlockingIssues.Should().Contain(issue => issue.DomainCode == "gdd_forbidden_source_detected");
    }

    [Fact]
    public async Task Phase1State_RecordGeneratedGddAsync_FailsClosedWhenPromptEvidenceAndFilesDivergeFromDatabaseBinding()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        var service = new GddToModulePhase1StateService(fixture.Store);
        await service.ConfirmSceneRouteAsync(fixture.AccountId, fixture.ProjectId, fixture.DefaultSceneRoute());
        fixture.WriteGdd("# Deckbuilder\n\n- Player must select a route node.\n");
        var runId = await fixture.CreateGddPromptRunAsync("coordinated-tamper");
        var artifacts = await fixture.Store.ListArtifactsForRunAsync(runId);
        var promptArtifact = artifacts.Single(artifact => artifact.ArtifactType == GameDesignDocumentService.PromptArtifactType);
        var evidenceArtifact = artifacts.Single(artifact => artifact.ArtifactType == GameDesignDocumentService.PromptSourceEvidenceArtifactType);
        const string tamperedPrompt = "Coordinated tampered prompt and evidence.";
        var tamperedHash = HostedRouteForbiddenSourceGuard.PromptHash(tamperedPrompt);
        fixture.WriteText(promptArtifact.RelativePath, tamperedPrompt);
        var evidenceNode = JsonNode.Parse(File.ReadAllText(fixture.PathForTest(evidenceArtifact.RelativePath), Encoding.UTF8))!.AsObject();
        evidenceNode["prompt_manifest"]!["execution_prompt_hash"] = tamperedHash;
        evidenceNode["prompt_manifest"]!["persisted_prompt_hash"] = tamperedHash;
        evidenceNode["forbidden_source_scan"]!["prompt_hash"] = tamperedHash;
        fixture.WriteJson(evidenceArtifact.RelativePath, evidenceNode.ToJsonString());

        var result = await service.RecordGeneratedGddAsync(fixture.AccountId, fixture.ProjectId, runId);

        result.Should().NotBeNull();
        result!.Status.Should().Be("blocked");
        result.BlockingIssues.Should().Contain(issue => issue.DomainCode == "gdd_prompt_evidence_invalid");
    }

    [Fact]
    public async Task Phase1State_RecordGeneratedGddAsync_FailsClosedWhenSelectedPromptBlockHashIsMissing()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        var service = new GddToModulePhase1StateService(fixture.Store);
        await service.ConfirmSceneRouteAsync(fixture.AccountId, fixture.ProjectId, fixture.DefaultSceneRoute());
        fixture.WriteGdd("# Deckbuilder\n\n- Player must select a route node.\n");
        var runId = await fixture.CreateGddPromptRunAsync("missing-prompt-block-hash");
        var evidenceArtifact = (await fixture.Store.ListArtifactsForRunAsync(runId))
            .Single(artifact => artifact.ArtifactType == GameDesignDocumentService.PromptSourceEvidenceArtifactType);
        var evidenceNode = JsonNode.Parse(File.ReadAllText(fixture.PathForTest(evidenceArtifact.RelativePath), Encoding.UTF8))!.AsObject();
        evidenceNode["source_hashes"]!.AsObject().Remove(HostedRouteRecoveryContract.SelectedRouteSkillPromptBlockHashKey);
        fixture.WriteJson(evidenceArtifact.RelativePath, evidenceNode.ToJsonString());

        var result = await service.RecordGeneratedGddAsync(fixture.AccountId, fixture.ProjectId, runId);

        result.Should().NotBeNull();
        result!.Status.Should().Be("blocked");
        result.BlockingIssues.Should().Contain(issue => issue.DomainCode == "gdd_prompt_evidence_invalid");
    }

    [Fact]
    public async Task Phase1State_RecordGeneratedGddAsync_FailsClosedWhenPromptBlockAuthorityChangesAfterRun()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        var service = new GddToModulePhase1StateService(fixture.Store);
        await service.ConfirmSceneRouteAsync(fixture.AccountId, fixture.ProjectId, fixture.DefaultSceneRoute());
        fixture.WriteGdd("# Deckbuilder\n\n- Player must select a route node.\n");
        var runId = await fixture.CreateGddPromptRunAsync("stale-prompt-block");

        using var changedPromptPolicy = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        var result = await service.RecordGeneratedGddAsync(fixture.AccountId, fixture.ProjectId, runId);

        result.Should().NotBeNull();
        result!.Status.Should().Be("blocked");
        result.BlockingIssues.Should().Contain(issue => issue.DomainCode == "gdd_prompt_authority_stale");
        File.Exists(fixture.PathForTest("meta/routes/gdd-document/latest.json")).Should().BeFalse();
    }

    [Fact]
    public async Task Phase1State_RecordGeneratedGddAsync_FailsClosedWhenGeneratedFileChangedAfterRun()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        var service = new GddToModulePhase1StateService(fixture.Store);
        await service.ConfirmSceneRouteAsync(fixture.AccountId, fixture.ProjectId, fixture.DefaultSceneRoute());
        fixture.WriteGdd("# Deckbuilder\n\n- Original generated content.\n");
        var runId = await fixture.CreateGddPromptRunAsync("generated-file-changed");
        fixture.WriteGdd("# Deckbuilder\n\n- Changed after the successful run.\n");

        var result = await service.RecordGeneratedGddAsync(fixture.AccountId, fixture.ProjectId, runId);

        result.Should().NotBeNull();
        result!.Status.Should().Be("blocked");
        result.BlockingIssues.Should().Contain(issue => issue.DomainCode == "gdd_generated_file_run_mismatch");
        File.Exists(fixture.PathForTest("meta/routes/gdd-document/latest.json")).Should().BeFalse();
    }

    [Fact]
    public async Task Phase1State_RecordGeneratedGddAsync_FailsClosedForAnotherProjectsRun()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        var service = new GddToModulePhase1StateService(fixture.Store);
        await service.ConfirmSceneRouteAsync(fixture.AccountId, fixture.ProjectId, fixture.DefaultSceneRoute());
        fixture.WriteGdd("# Deckbuilder\n\n- Player must select a route node.\n");
        var creation = new ProjectCreationService(
            fixture.Store,
            fixture.Options,
            new ProjectRuleCatalog(),
            new ProjectWorkspaceSeeder(fixture.Options),
            gameTypeMatchService: new FixedGameTypeMatchService());
        var other = await creation.CreateProjectAsync(
            fixture.AccountId,
            new ProjectCreationRequest(null, "Other RPG", "RPG", null, null, null, null));
        var otherProject = await fixture.Store.GetProjectSnapshotAsync(other.ProjectId!);
        var otherRunId = await fixture.Store.CreateRunAsync(other.ProjectId!, otherProject!.WorkspaceId, "game-design-gdd");
        await fixture.Store.CompleteRunAsync(otherRunId, "succeeded", 0, "", "", "{}", CancellationToken.None);

        var result = await service.RecordGeneratedGddAsync(fixture.AccountId, fixture.ProjectId, otherRunId);

        result.Should().NotBeNull();
        result!.Status.Should().Be("blocked");
        result.BlockingIssues.Should().Contain(issue => issue.DomainCode == "gdd_prompt_run_invalid");
    }

    [Fact]
    public async Task Phase1State_GetGddDocumentStateAsync_RejectsIncompleteOrMismatchedWriteThrough()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        var service = new GddToModulePhase1StateService(fixture.Store);
        await service.ConfirmSceneRouteAsync(fixture.AccountId, fixture.ProjectId, fixture.DefaultSceneRoute());
        fixture.WriteGdd("# Deckbuilder\n\n- Player must select a route node.\n");
        var promptRunId = await fixture.CreateGddPromptRunAsync("partial");
        var recorded = await service.RecordGeneratedGddAsync(fixture.AccountId, fixture.ProjectId, promptRunId);
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

    [Theory]
    [InlineData("authority_changed")]
    [InlineData("source_boundary_missing")]
    [InlineData("prompt_evidence_missing")]
    [InlineData("database_binding_mismatch")]
    public async Task Phase1State_GetGddDocumentStateAsync_RevalidatesPromptSourceBoundary(string scenario)
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        var service = new GddToModulePhase1StateService(fixture.Store);
        await service.ConfirmSceneRouteAsync(fixture.AccountId, fixture.ProjectId, fixture.DefaultSceneRoute());
        fixture.WriteGdd("# Deckbuilder\n\n- Player must select a route node.\n");
        var runId = await fixture.CreateGddPromptRunAsync("readback-" + scenario);
        var recorded = await service.RecordGeneratedGddAsync(fixture.AccountId, fixture.ProjectId, runId);
        recorded!.Status.Should().Be("ready");

        IDisposable? authorityOverride = null;
        try
        {
            switch (scenario)
            {
                case "authority_changed":
                    authorityOverride = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
                    break;
                case "source_boundary_missing":
                {
                    var node = JsonNode.Parse(File.ReadAllText(fixture.PathForTest("meta/routes/gdd-document/latest.json"), Encoding.UTF8))!.AsObject();
                    node.Remove("source_boundary");
                    fixture.WriteJson("meta/routes/gdd-document/latest.json", node.ToJsonString());
                    break;
                }
                case "prompt_evidence_missing":
                    File.Delete(fixture.PathForTest("meta/routes/gdd-document/prompt-evidence.json"));
                    break;
                case "database_binding_mismatch":
                {
                    var binding = (await fixture.Store.ListProjectRoutePromptEvidenceBindingsAsync(fixture.ProjectId))
                        .Single(item => item.RouteId == "gdd-document-generation");
                    await fixture.Store.UpsertProjectRoutePromptEvidenceBindingAsync(new ProjectRoutePromptEvidenceBindingCommand(
                        fixture.ProjectId,
                        binding.RouteId,
                        new string('f', 64),
                        binding.PersistedPromptHash,
                        binding.PromptArtifactRef,
                        binding.PromptEvidenceRef));
                    break;
                }
            }

            var result = await service.GetGddDocumentStateAsync(fixture.AccountId, fixture.ProjectId);

            result.Should().NotBeNull();
            result!.Status.Should().Be("blocked");
            result.BlockingIssues.Should().Contain(issue => issue.DomainCode == "gdd_document_source_boundary_invalid");
        }
        finally
        {
            authorityOverride?.Dispose();
        }
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
        File.ReadAllBytes(fixture.PathForTest("meta/routes/gdd-requirements/latest.json"))
            .Take(3)
            .Should().NotEqual([0xEF, 0xBB, 0xBF]);
        sidecar.RootElement.GetProperty("schema_version").GetString().Should().Be("gdd-requirements.v1");
        sidecar.RootElement.GetProperty("source_boundary_enforced").GetBoolean().Should().BeTrue();
        sidecar.RootElement.GetProperty("source_boundary").GetProperty("recovery_source_order").GetArrayLength()
            .Should().Be(HostedRouteRecoveryContract.SourceOrder.Count);
        File.Exists(fixture.PathForTest("meta/routes/gdd-requirements/prompt-evidence.json")).Should().BeTrue();
        var routeBindings = (await fixture.Store.ListProjectRoutePromptEvidenceBindingsAsync(fixture.ProjectId))
            .ToDictionary(binding => binding.RouteId, StringComparer.Ordinal);
        var routeReadback = new ProjectRouteStateArtifactService().Read(await fixture.GetProjectAsync(), routeBindings);
        routeReadback.BlockingIssues.Should().NotContain(issue =>
            issue.IssueId.StartsWith("meta/routes/gdd-requirements/latest.json:prompt_evidence", StringComparison.Ordinal));
        sidecar.RootElement.GetProperty("requirements")[0].GetProperty("requirement_id").GetString().Should().Be("REQ-001");
    }

    [Fact]
    public async Task RequirementMap_CreateAsync_ReconcilesRemovedAdminReviewBlockerWithoutErasingHistory()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        fixture.SeedConfirmedSceneRouteAndGdd();
        var obsolete = await fixture.Store.UpsertProjectAdminReviewQueueEntryAsync(new ProjectAdminReviewQueueCommand(
            fixture.AccountId,
            fixture.ProjectId,
            "gdd-requirements",
            "REQ-OBSOLETE",
            "P1",
            "Requirement REQ-OBSOLETE requires review for status conflict.",
            "meta/routes/gdd-requirements/latest.json",
            "[]"));

        await new GameDesignRequirementMapService(fixture.Store)
            .CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignRequirementMapRequest());

        var rows = await fixture.Store.ListProjectAdminReviewQueueForProjectAsync(
            fixture.AccountId,
            fixture.ProjectId,
            "",
            0);
        rows.Should().Contain(row =>
            row.Id == obsolete.Id && row.Status == "superseded" && !string.IsNullOrWhiteSpace(row.SupersededByEntryId));
        var resolved = rows.Should().ContainSingle(row =>
            row.RequirementId == "REQ-OBSOLETE" && row.Status == "resolved" && row.SupersedesEntryId == obsolete.Id).Subject;
        resolved.DecisionStatus.Should().Be("resolved");
        resolved.DecisionActorAccountId.Should().Be("system");
        resolved.DecisionVersion.Should().Be(1);
        resolved.DecidedUtc.Should().NotBeNullOrWhiteSpace();
        await using var connection = new SqliteConnection(fixture.ConnectionString);
        await connection.OpenAsync();
        await using var history = connection.CreateCommand();
        history.CommandText = "SELECT COUNT(*) FROM project_admin_review_decisions WHERE entry_id = $entry_id AND decision_actor_account_id = 'system';";
        history.Parameters.AddWithValue("$entry_id", resolved.Id);
        Convert.ToInt64(await history.ExecuteScalarAsync()).Should().Be(1);
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
                "validation_method": "camera state test",
                "yaw_pitch_ownership": "camera_rig",
                "camera_relative_movement_boundary": "player_motor",
                "camera_state_validation": "camera state smoke"
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
                "signal_ownership": "combat_state",
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
        using var promptEvidence = fixture.ReadJson("meta/routes/gdd-requirements/prompt-evidence.json");
        var promptManifest = promptEvidence.RootElement.GetProperty("prompt_manifest");
        promptManifest.GetProperty("execution_prompt_hash").GetString().Should().Be(
            HostedRouteForbiddenSourceGuard.PromptHash(engine.Requests[0].Prompt));
        var persistedPrompt = File.ReadAllText(fixture.PathForTest("meta/routes/gdd-requirements/prompt.txt"), Encoding.UTF8);
        promptManifest.GetProperty("persisted_prompt_hash").GetString().Should().Be(
            HostedRouteForbiddenSourceGuard.PromptHash(persistedPrompt));
        promptEvidence.RootElement.GetProperty("forbidden_source_scan").GetProperty("prompt_hash").GetString().Should().Be(
            promptManifest.GetProperty("execution_prompt_hash").GetString());
    }

    [Fact]
    public async Task RequirementMap_ReadbackRejectsCoordinatedPromptEvidenceTamperAgainstDatabaseBinding()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        fixture.SeedConfirmedSceneRouteAndGdd();
        await new GameDesignRequirementMapService(fixture.Store)
            .CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignRequirementMapRequest());
        const string tamperedPrompt = "Coordinated replacement prompt.";
        var tamperedHash = HostedRouteForbiddenSourceGuard.PromptHash(tamperedPrompt);
        fixture.WriteText("meta/routes/gdd-requirements/prompt.txt", tamperedPrompt);
        var evidenceNode = JsonNode.Parse(File.ReadAllText(
            fixture.PathForTest("meta/routes/gdd-requirements/prompt-evidence.json"),
            Encoding.UTF8))!.AsObject();
        evidenceNode["prompt_manifest"]!["execution_prompt_hash"] = tamperedHash;
        evidenceNode["prompt_manifest"]!["persisted_prompt_hash"] = tamperedHash;
        evidenceNode["forbidden_source_scan"]!["prompt_hash"] = tamperedHash;
        fixture.WriteJson("meta/routes/gdd-requirements/prompt-evidence.json", evidenceNode.ToJsonString());
        var bindings = (await fixture.Store.ListProjectRoutePromptEvidenceBindingsAsync(fixture.ProjectId))
            .ToDictionary(binding => binding.RouteId, StringComparer.Ordinal);

        var readback = new ProjectRouteStateArtifactService().Read(await fixture.GetProjectAsync(), bindings);

        readback.BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/gdd-requirements/latest.json:prompt_evidence_invalid" &&
            issue.Severity == "P0");
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
        var queued = queue.Should().ContainSingle(item => item.RequirementId == "REQ-001" && item.RouteId == "gdd-requirements").Subject;
        using (var evidence = JsonDocument.Parse(queued.EvidenceRefsJson))
        {
            var hashSet = evidence.RootElement[0];
            hashSet.GetProperty("source_requirement_map_hash").GetString().Should().Be(requirementMap.SourceRequirementMapHash);
            hashSet.GetProperty("source_gdd_hash").GetString().Should().Be(requirementMap.SourceGddHash);
            hashSet.GetProperty("source_scene_route_hash").GetString().Should().Be(requirementMap.SourceSceneRouteHash);
            hashSet.GetProperty("source_contract_snapshot_hash").GetString().Should().Be(requirementMap.SourceContractSnapshotHash);
            hashSet.GetProperty("source_godot_ui_contract_hash").GetString().Should().Be(requirementMap.SourceGodotUiContractHash);
        }
        contract.Status.Should().Be("blocked");
        contract.BlockingIssues.Should().Contain(issue => issue.DomainCode == "admin_review_blocked");
    }

    [Fact]
    public async Task RequirementMap_CreateAsync_SourceHashChangeSupersedesPriorHumanDecisionEvenWhenRowsStayStable()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        const string firstGdd = """
        # Demo RPG

        - Player must move on the field map and trigger one visible encounter.
        - HUD feedback must show HP, reward, and return-to-map state.
        """;
        const string secondGdd = """
        # Demo RPG


        - Player must move on the field map and trigger one visible encounter.
        - HUD feedback must show HP, reward, and return-to-map state.
        """;
        fixture.SeedConfirmedSceneRouteAndGdd(firstGdd);
        var service = new GameDesignRequirementMapService(fixture.Store, new FixedRequirementMapLlmEngine("""
        {
          "requirements": [
            { "requirement_id": "REQ-001", "normalized_requirement": "Player must move on the field map and trigger one visible encounter.", "priority": "P0", "kind": "scene", "mapped_scene_ids": ["field_map"], "mapped_required_module_ids": ["field_map"], "status": "conflict" },
            { "requirement_id": "REQ-002", "normalized_requirement": "HUD feedback must show HP, reward, and return-to-map state.", "priority": "P1", "kind": "ui", "mapped_scene_ids": ["field_map"], "mapped_required_module_ids": ["combat_hud"], "status": "mapped", "capability_domain_ids": ["ui_component_system"] }
          ]
        }
        """));

        var firstMap = await service.CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignRequirementMapRequest());
        var firstEntry = (await fixture.Store.ListProjectAdminReviewQueueForProjectAsync(fixture.AccountId, fixture.ProjectId, "open")).Single();
        fixture.WriteJson("meta/reviews/first-hash-set.json", "{}");
        (await fixture.Store.DecideProjectAdminReviewQueueEntryAsync(
            firstEntry.Id,
            fixture.AccountId,
            new ProjectAdminReviewDecisionRequest(
                "approved",
                "approved first hash set",
                0,
                ["meta/reviews/first-hash-set.json"]))).Status.Should().Be("updated");

        fixture.SeedConfirmedSceneRouteAndGdd(secondGdd);
        var secondMap = await service.CreateAsync(fixture.AccountId, fixture.ProjectId, new GameDesignRequirementMapRequest(Refresh: true));
        var rows = await fixture.Store.ListProjectAdminReviewQueueForProjectAsync(fixture.AccountId, fixture.ProjectId, "", 0);

        secondMap.Requirements.Select(item => item.RequirementId).Should().Equal(firstMap.Requirements.Select(item => item.RequirementId));
        secondMap.SourceGddHash.Should().NotBe(firstMap.SourceGddHash);
        rows.Should().Contain(item => item.Id == firstEntry.Id && item.Status == "superseded");
        rows.Should().ContainSingle(item => item.Id != firstEntry.Id && item.Status == "open");
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
        canonical.RootElement.GetProperty("status_dimension").GetString().Should().Be(RouteStatusVocabulary.RouteReadback);
        canonical.RootElement.GetProperty("status").GetString().Should().Be("ready");
        canonical.RootElement.GetProperty("status_allowed_values").EnumerateArray()
            .Select(item => item.GetString())
            .Should().Contain("ready");
        canonical.RootElement.GetProperty("source_gdd_hash").GetString().Should().Be(fixture.GddHash);
        mirror.RootElement.GetProperty("contract_hash").GetString().Should().Be(result.ContractHash);
    }

    [Fact]
    public async Task PrototypeContract_WriteFromRequest_PreservesFrozenV2AuthorityAndRepairsMirror()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        await fixture.SeedRequirementMapAsync();
        var frozen = await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        var project = await fixture.GetProjectAsync();
        var canonicalPath = fixture.PathForTest("routes/prototype-contract/latest.json");
        var mirrorPath = fixture.PathForTest("meta/routes/prototype-contract/latest.json");
        var canonicalBefore = File.ReadAllText(canonicalPath, Encoding.UTF8);
        File.WriteAllText(mirrorPath, "{\"schema_version\":1}", Encoding.UTF8);

        var result = new PrototypeContractService().WriteFromRequest(
            project,
            new PrototypeWorkflowRequest(
                "deckbuilder",
                "Changed Name",
                "deckbuilder",
                "manual",
                "Changed hypothesis",
                "Changed fantasy",
                "Changed loop",
                ["Changed success"],
                "Changed feature",
                "Changed gameplay loop",
                "Changed win condition"),
            "docs/prototypes/changed.md",
            "deckbuilder");

        File.ReadAllText(canonicalPath, Encoding.UTF8).Should().Be(canonicalBefore);
        File.ReadAllText(mirrorPath, Encoding.UTF8).Should().Be(canonicalBefore);
        result.Json.Should().Be(canonicalBefore);
        using var document = JsonDocument.Parse(result.Json);
        document.RootElement.GetProperty("contract_hash").GetString().Should().Be(frozen.ContractHash);
    }

    [Fact]
    public async Task ContractFreeze_FreezeAsync_BlocksSceneSemanticTamperWithUnchangedDeclaredHash()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        await fixture.SeedRequirementMapAsync();
        var scenePath = fixture.PathForTest("meta/routes/scene-route/latest.json");
        var scene = JsonNode.Parse(File.ReadAllText(scenePath, Encoding.UTF8))!.AsObject();
        scene["entry_scene"] = "tampered_scene";
        File.WriteAllText(scenePath, scene.ToJsonString(new JsonSerializerOptions { WriteIndented = true }), Encoding.UTF8);

        var result = await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest(Refresh: true));

        result.Status.Should().Be("blocked");
        result.BlockingIssues.Should().Contain(issue =>
            issue.DomainCode == "source_stale" && issue.Severity == "P0");
    }

    [Fact]
    public async Task PrototypeContract_ReadAndWriteFromRequest_FailClosedForTamperedFrozenContract()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        await fixture.SeedRequirementMapAsync();
        await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        var project = await fixture.GetProjectAsync();
        var canonicalPath = fixture.PathForTest("routes/prototype-contract/latest.json");
        var canonical = JsonNode.Parse(File.ReadAllText(canonicalPath, Encoding.UTF8))!.AsObject();
        canonical["source_gdd_hash"] = "tampered-with-old-contract-hash";
        File.WriteAllText(canonicalPath, canonical.ToJsonString(new JsonSerializerOptions { WriteIndented = true }), Encoding.UTF8);
        var service = new PrototypeContractService();

        service.Read(project).Json.Should().BeEmpty();
        var action = () => service.WriteFromRequest(
            project,
            new PrototypeWorkflowRequest(null, null, null, null, null, null, null, null, null, null, null),
            "docs/prototypes/tampered.md",
            "tampered");
        action.Should().Throw<InvalidOperationException>().WithMessage("prototype_contract_frozen_invalid");
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
    [InlineData("game_type_hash_missing", "game_type_structured_stale")]
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
    public async Task ContractFreeze_FreezeAsync_DoesNotMissBlockerAfterFiveHundredRows()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        await fixture.SeedRequirementMapAsync();
        for (var index = 0; index < 500; index++)
        {
            await fixture.Store.UpsertProjectAdminReviewQueueEntryAsync(new ProjectAdminReviewQueueCommand(
                fixture.AccountId, fixture.ProjectId, "gdd-requirements", $"REQ-P2-{index:000}", "P2",
                "non-gating review", "meta/routes/gdd-requirements/latest.json", "[]"));
        }
        await fixture.Store.UpsertProjectAdminReviewQueueEntryAsync(new ProjectAdminReviewQueueCommand(
            fixture.AccountId, fixture.ProjectId, "gdd-requirements", "REQ-BEYOND-500", "P1",
            "must remain visible to the gate", "meta/routes/gdd-requirements/latest.json", "[]"));

        var result = await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());

        result.Status.Should().Be("blocked");
        result.BlockingIssues.Should().Contain(issue => issue.DomainCode == "admin_review_blocked");
    }

    [Theory]
    [InlineData("approved", false)]
    [InlineData("deferred", false)]
    [InlineData("resolved", false)]
    [InlineData("rejected", true)]
    [InlineData("backlog", true)]
    public async Task ContractFreeze_FreezeAsync_UsesBoundedAdminReviewBlockingPolicy(string decisionStatus, bool shouldBlock)
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        await fixture.SeedRequirementMapAsync();
        var entry = await fixture.Store.UpsertProjectAdminReviewQueueEntryAsync(new ProjectAdminReviewQueueCommand(
            fixture.AccountId,
            fixture.ProjectId,
            "gdd-requirements",
            "REQ-POLICY",
            "P1",
            "Review policy probe.",
            "meta/routes/gdd-requirements/latest.json",
            "[]"));
        fixture.WriteJson("meta/reviews/policy-decision.json", "{}");
        var request = decisionStatus == "deferred"
            ? new ProjectAdminReviewDecisionRequest(
                decisionStatus,
                "deferred with a bounded recheck",
                0,
                DeferredOwner: "phase-platform",
                 DeferredUntilUtc: "2099-01-01T00:00:00Z",
                 RecheckTrigger: "requirement map refreshed",
                 AffectedRoutes: ["gdd-requirements", "prototype-contract"],
                 DecisionEvidenceRefs: ["meta/reviews/policy-decision.json"])
            : new ProjectAdminReviewDecisionRequest(
                decisionStatus,
                "policy decision",
                0,
                ["meta/reviews/policy-decision.json"]);
        (await fixture.Store.DecideProjectAdminReviewQueueEntryAsync(entry.Id, fixture.AccountId, request))
            .Status.Should().Be("updated");

        var result = await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());

        if (shouldBlock)
        {
            result.Status.Should().Be("blocked");
            result.BlockingIssues.Should().Contain(issue => issue.DomainCode == "admin_review_blocked");
        }
        else
        {
            result.Status.Should().Be("fresh");
            result.BlockingIssues.Should().NotContain(issue => issue.DomainCode == "admin_review_blocked");
        }
    }

    [Fact]
    public async Task ContractFreeze_FreezeAsync_IgnoresSupersededBlockingHistory()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        await fixture.SeedRequirementMapAsync();
        var oldEntry = await fixture.Store.UpsertProjectAdminReviewQueueEntryAsync(new ProjectAdminReviewQueueCommand(
            fixture.AccountId, fixture.ProjectId, "gdd-requirements", "REQ-HISTORY", "P1", "Historical blocker.",
            "meta/routes/gdd-requirements/latest.json", """[{"kind":"sidecar","path":"meta/reviews/old.json"}]"""));
        fixture.WriteJson("meta/reviews/old.json", "{}");
        await fixture.Store.DecideProjectAdminReviewQueueEntryAsync(
            oldEntry.Id,
            fixture.AccountId,
            new ProjectAdminReviewDecisionRequest("rejected", "old evidence rejected", 0, ["meta/reviews/old.json"]));
        var currentEntry = await fixture.Store.UpsertProjectAdminReviewQueueEntryAsync(new ProjectAdminReviewQueueCommand(
            fixture.AccountId, fixture.ProjectId, "gdd-requirements", "REQ-HISTORY", "P1", "Historical blocker.",
            "meta/routes/gdd-requirements/latest.json", """[{"kind":"sidecar","path":"meta/reviews/new.json"}]"""));
        fixture.WriteJson("meta/reviews/new.json", "{}");
        await fixture.Store.DecideProjectAdminReviewQueueEntryAsync(
            currentEntry.Id,
            fixture.AccountId,
            new ProjectAdminReviewDecisionRequest("approved", "new evidence accepted", 0, ["meta/reviews/new.json"]));

        var result = await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());

        result.Status.Should().Be("fresh");
        result.BlockingIssues.Should().NotContain(issue => issue.DomainCode == "admin_review_blocked");
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

    [Fact]
    public async Task IterationPlan_CreateAsync_PersistsFrozenHashesAndClosedRequirementTraceability()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        using var fixture = await BackendContractFixture.CreateAsync();
        await fixture.SeedRequirementMapAsync();
        var contract = await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        contract.Status.Should().Be("fresh");
        await fixture.SeedPrototypeSkeletonAsync(contract);
        var service = new PrototypeIterationPlanService(fixture.Store);

        var result = await service.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest(
                "Complete field movement, visible encounter feedback, combat HUD, reward feedback, and return to the map.",
                "manual_feedback"));

        result.Status.Should().Be("ready", result.Summary);
        result.SourceHashes.Should().NotBeNull();
        result.SourceHashes!.SourceGddHash.Should().Be(contract.SourceGddHash);
        result.SourceHashes.SourceRequirementMapHash.Should().Be(contract.SourceRequirementMapHash);
        result.SourceHashes.SourceContractHash.Should().Be(contract.ContractHash);
        result.Coverage!.UncoveredRequirementIds.Should().BeEmpty();
        result.Blockers.Should().BeEmpty();
        result.Goals.Should().OnlyContain(goal => goal.RequirementIds!.Count > 0 || goal.InfrastructureReason != null);
        result.RequiredModules.Should().Contain(module => module.RequirementIds!.Count > 0);

        using var sidecar = fixture.ReadJson("meta/routes/iteration-plan/latest.json");
        sidecar.RootElement.GetProperty("source_gdd_hash").GetString().Should().Be(contract.SourceGddHash);
        sidecar.RootElement.GetProperty("source_contract_hash").GetString().Should().Be(contract.ContractHash);
        sidecar.RootElement.GetProperty("source_godot_ui_contract_hash").GetString().Should().Be(contract.SourceGodotUiContractHash);
        sidecar.RootElement.GetProperty("goals")[0].TryGetProperty("requirement_ids", out _).Should().BeTrue();
        sidecar.RootElement.GetProperty("required_modules").EnumerateArray()
            .Any(module => module.TryGetProperty("source_reason", out _))
            .Should().BeTrue();
        foreach (var goal in result.Goals.Where(goal => goal.InteractionRegion is not null))
        {
            var artifactPath = fixture.PathForTest(goal.InteractionRegion!.ArtifactRef);
            File.Exists(artifactPath).Should().BeTrue(goal.InteractionRegion.ArtifactRef);
            using var artifact = JsonDocument.Parse(File.ReadAllText(artifactPath, Encoding.UTF8));
            artifact.RootElement.GetProperty("validation_status").GetString().Should().Be("contract_validated");
            artifact.RootElement.GetProperty("validation_method").GetString().Should().Be(IterationPlanInteractionArtifactValidator.ValidationMethod);
            artifact.RootElement.GetProperty("validated_utc").GetString().Should().NotBeNullOrWhiteSpace();
            artifact.RootElement.GetProperty("artifact_form").GetString().Should().Be("planned-godot-node-map");
            artifact.RootElement.GetProperty("runtime_validation_required").GetBoolean().Should().BeTrue();
            artifact.RootElement.GetProperty("planned_geometry").EnumerateArray().Should().NotBeEmpty();
            artifact.RootElement.GetProperty("planned_geometry").EnumerateArray().Should().OnlyContain(item =>
                !string.IsNullOrWhiteSpace(item.GetProperty("owner_ref").GetString()) &&
                new[] { "control_rect", "collision_shape" }.Contains(item.GetProperty("geometry_kind").GetString()) &&
                !string.IsNullOrWhiteSpace(item.GetProperty("coordinate_space").GetString()) &&
                item.GetProperty("bounds").ValueKind == JsonValueKind.Null &&
                item.GetProperty("bounds_policy").GetString() == "runtime_resolved" &&
                !string.IsNullOrWhiteSpace(item.GetProperty("locator_ref").GetString()) &&
                !string.IsNullOrWhiteSpace(item.GetProperty("resolution_source").GetString()) &&
                !string.IsNullOrWhiteSpace(item.GetProperty("interaction_role").GetString()));
            artifact.RootElement.GetProperty("region_map").GetString().Should().Contain("OWNERS:");
            artifact.RootElement.GetProperty("scene_node_owners").EnumerateArray()
                .Select(owner => owner.GetString())
                .Should().OnlyContain(owner => owner != null && !owner.StartsWith("owner:", StringComparison.Ordinal));
        }
    }

    [Theory]
    [InlineData(false, "blocked", 0)]
    [InlineData(true, "ready", 1)]
    public async Task IterationPlan_SkeletonCoverageRequiresExplicitVerifiedRequirementBinding(
        bool verified,
        string expectedStatus,
        int expectedSkeletonCoverage)
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        using var fixture = await BackendContractFixture.CreateAsync();
        await fixture.SeedRequirementMapAsync("""
        {
          "requirements": [
            { "requirement_id": "REQ-001", "normalized_requirement": "Player moves on the field map.", "priority": "P0", "kind": "scene", "mapped_scene_ids": ["field_map"], "mapped_required_module_ids": [], "mapped_iteration_goal_ids": [], "status": "mapped" },
            { "requirement_id": "REQ-002", "normalized_requirement": "HUD shows HP and reward feedback.", "priority": "P1", "kind": "ui", "mapped_scene_ids": ["field_map"], "mapped_required_module_ids": ["combat_hud"], "status": "mapped", "capability_domain_ids": ["ui_component_system", "ui_overlays_feedback"] }
          ]
        }
        """);
        await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync(verifiedRequirementIds: verified ? ["REQ-001"] : []);

        var result = await new PrototypeIterationPlanService(fixture.Store).CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Create the next iteration plan.", "manual_feedback"));

        result.Status.Should().Be(expectedStatus, result.Summary);
        result.Coverage!.SkeletonCoveredCount.Should().Be(expectedSkeletonCoverage);
        (result.Blockers ?? []).Any(blocker => blocker.DomainCode == "coverage_gap").Should().Be(!verified);
    }

    [Fact]
    public async Task IterationPlan_CreateAsync_RecordsAndDeduplicatesNewChainGuardFailure()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        fixture.SeedConfirmedSceneRouteAndGdd();
        var service = new PrototypeIterationPlanService(fixture.Store);

        var first = await service.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement.", "manual_feedback"));
        var second = await service.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement.", "manual_feedback"));
        var diagnostics = await fixture.Store.ListProjectDiagnosticSpoolForAdminAsync(
            new ProjectDiagnosticSpoolQuery("unresolved", fixture.AccountId, fixture.ProjectId, "iteration-plan", "requirement_map_missing", "P1", 10));

        first.Status.Should().Be("blocked");
        second.Status.Should().Be("blocked");
        diagnostics.Should().ContainSingle();
    }

    [Fact]
    public async Task ExecuteNextAsync_RecordsAndDeduplicatesLegacySourceFailureBeforeRunnerUse()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        var project = await fixture.GetProjectAsync();
        new PrototypeRouteStateWriter().WriteIterationPlanState(project, new
        {
            route = "iteration-plan",
            traceability_contract = "iteration-plan-traceability.v2",
            plan_hash = "legacy-plan-hash"
        });
        var runner = new CountingHostedProcessRunner();
        var service = new PrototypeIterationGoalService(fixture.Store, fixture.Options, runner);

        var first = await service.ExecuteNextAsync(fixture.AccountId, fixture.ProjectId);
        var second = await service.ExecuteNextAsync(fixture.AccountId, fixture.ProjectId);
        var diagnostics = await fixture.Store.ListProjectDiagnosticSpoolForAdminAsync(
            new ProjectDiagnosticSpoolQuery("unresolved", fixture.AccountId, fixture.ProjectId, "execute-next-goal", "legacy_plan_source_unknown", "P1", 10));

        first.Status.Should().Be("legacy_plan_source_unknown");
        second.Status.Should().Be("legacy_plan_source_unknown");
        diagnostics.Should().ContainSingle();
        runner.CallCount.Should().Be(0);
    }

    [Fact]
    public async Task ExecuteNextAsync_RecordsAndDeduplicatesMissingContractFailureBeforeRunnerUse()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        fixture.SeedConfirmedSceneRouteAndGdd();
        var runner = new CountingHostedProcessRunner();
        var service = new PrototypeIterationGoalService(fixture.Store, fixture.Options, runner);

        var first = await service.ExecuteNextAsync(fixture.AccountId, fixture.ProjectId);
        var second = await service.ExecuteNextAsync(fixture.AccountId, fixture.ProjectId);
        var diagnostics = await fixture.Store.ListProjectDiagnosticSpoolForAdminAsync(
            new ProjectDiagnosticSpoolQuery("unresolved", fixture.AccountId, fixture.ProjectId, "execute-next-goal", "requirement_map_missing", "P1", 10));

        first.Status.Should().Be("requirement_map_missing");
        second.Status.Should().Be("requirement_map_missing");
        diagnostics.Should().ContainSingle();
        runner.CallCount.Should().Be(0);
    }

    [Fact]
    public async Task IterationPlan_CreateAsync_RedactsAdminReviewRowIdentityAndRawEvidence()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        await fixture.SeedRequirementMapAsync();
        await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync();
        await fixture.Store.UpsertProjectAdminReviewQueueEntryAsync(new ProjectAdminReviewQueueCommand(
            fixture.AccountId,
            fixture.ProjectId,
            "gdd-requirements",
            "REQ-001",
            "P1",
            "Private admin review reason.",
            @"C:\host\private\admin-review.json",
            """[{"kind":"sidecar","path":"meta/reviews/raw-admin-evidence.json"}]"""));
        var adminRows = await fixture.Store.ListProjectAdminReviewQueueForProjectAsync(
            fixture.AccountId,
            fixture.ProjectId,
            "open");

        var result = await new PrototypeIterationPlanService(fixture.Store).CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement.", "manual_feedback"));
        var serialized = JsonSerializer.Serialize(result);

        result.Blockers.Should().ContainSingle(item => item.DomainCode == "admin_review_blocked");
        result.Blockers!.SelectMany(item => item.EvidenceRefs).Should().Equal("admin-review:required");
        serialized.Should().NotContain(adminRows.Single().Id);
        serialized.Should().NotContain(@"C:\host\private");
        serialized.Should().NotContain("raw-admin-evidence");
    }

    [Fact]
    public async Task IterationPlan_CreateAsync_RedactsDiagnosticIdentityAndRawEvidence()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        await fixture.SeedRequirementMapAsync();
        await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync();
        var diagnostic = await fixture.Store.RecordProjectDiagnosticSpoolEntryAsync(new ProjectDiagnosticSpoolCommand(
            fixture.AccountId,
            fixture.ProjectId,
            "prototype",
            "source_stale",
            "P1",
            "Safe summary.",
            "[\"raw-diagnostic-evidence\"]",
            @"C:\host\private\diagnostic.json",
            SourceRefsJson: "[\"C:\\\\host\\\\private\\\\source.json\"]"));

        var result = await new PrototypeIterationPlanService(fixture.Store).CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement.", "manual_feedback"));
        var serialized = JsonSerializer.Serialize(result);

        result.Blockers.Should().ContainSingle(item => item.DomainCode == "diagnostic_blocked");
        result.Blockers!.SelectMany(item => item.EvidenceRefs).Should().Equal("diagnostic:unresolved");
        serialized.Should().NotContain(diagnostic.Id);
        serialized.Should().NotContain(diagnostic.DiagnosticId);
        serialized.Should().NotContain(@"C:\host\private");
        serialized.Should().NotContain("raw-diagnostic-evidence");
    }

    [Theory]
    [InlineData(false, "prototype_skeleton_missing")]
    [InlineData(true, "prototype_skeleton_stale")]
    public async Task IterationPlan_CreateAsync_BlocksMissingOrStaleSkeletonBeforeLlm(
        bool writeStaleSkeleton,
        string expectedDomainCode)
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        await fixture.SeedRequirementMapAsync();
        var contract = await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        if (writeStaleSkeleton)
        {
            await fixture.SeedPrototypeSkeletonAsync(contract, sourceContractHash: "stale-contract-hash");
        }
        var llm = new CountingLlmRouteEngine();
        var service = new PrototypeIterationPlanService(fixture.Store, new PrototypeRouteStateWriter(), llmRouteEngine: llm);

        var first = await service.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement and HUD feedback.", "manual_feedback"));
        var second = await service.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement and HUD feedback.", "manual_feedback"));
        var diagnostics = await fixture.Store.ListProjectDiagnosticSpoolForAdminAsync(
            new ProjectDiagnosticSpoolQuery("unresolved", fixture.AccountId, fixture.ProjectId, "iteration-plan", expectedDomainCode, "P1", 10));

        first.Status.Should().Be("blocked");
        first.Blockers.Should().ContainSingle(item => item.DomainCode == expectedDomainCode);
        second.Status.Should().Be("blocked");
        llm.Requests.Should().BeEmpty();
        diagnostics.Should().ContainSingle();
    }

    [Fact]
    public async Task IterationPlan_CreateAsync_BlocksSkeletonSnapshotOrMirrorDriftBeforeLlm()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        await fixture.SeedRequirementMapAsync();
        var contract = await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync(contract, sourceContractSnapshotHash: "stale-snapshot-hash");
        var llm = new CountingLlmRouteEngine();
        var service = new PrototypeIterationPlanService(fixture.Store, new PrototypeRouteStateWriter(), llmRouteEngine: llm);

        var snapshotDrift = await service.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement.", "manual_feedback"));

        snapshotDrift.Blockers.Should().ContainSingle(item => item.DomainCode == "prototype_skeleton_stale");
        llm.Requests.Should().BeEmpty();

        await using (var connection = new SqliteConnection(fixture.ConnectionString))
        {
            await connection.OpenAsync();
            await using var command = connection.CreateCommand();
            command.CommandText = "UPDATE project_diagnostic_spool SET triage_status = 'resolved' WHERE project_id = $project_id";
            command.Parameters.AddWithValue("$project_id", fixture.ProjectId);
            await command.ExecuteNonQueryAsync();
        }

        var currentProject = await fixture.GetProjectAsync();
        var externalMetaPath = currentProject.MetaPath + "-external";
        Directory.CreateDirectory(externalMetaPath);
        await using (var connection = new SqliteConnection(fixture.ConnectionString))
        {
            await connection.OpenAsync();
            await using var command = connection.CreateCommand();
            command.CommandText = "UPDATE workspaces SET meta_path = $meta_path WHERE project_id = $project_id";
            command.Parameters.AddWithValue("$meta_path", externalMetaPath);
            command.Parameters.AddWithValue("$project_id", fixture.ProjectId);
            await command.ExecuteNonQueryAsync();
        }
        await fixture.SeedPrototypeSkeletonAsync(contract);
        var project = await fixture.GetProjectAsync();
        var mirrorPath = Path.Combine(project.RepoPath, "meta", "routes", "prototype-skeleton", "latest.json");
        var mirror = JsonNode.Parse(File.ReadAllText(mirrorPath, Encoding.UTF8))!.AsObject();
        mirror["status"] = "failed";
        File.WriteAllText(mirrorPath, mirror.ToJsonString(new JsonSerializerOptions { WriteIndented = true }), Encoding.UTF8);

        var mirrorDrift = await service.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement.", "manual_feedback"));

        mirrorDrift.Status.Should().Be("blocked", mirrorDrift.Summary);
        mirrorDrift.Blockers.Should().ContainSingle(
            item => item.DomainCode == "prototype_skeleton_stale",
            string.Join(",", mirrorDrift.Blockers?.Select(item => item.DomainCode) ?? []));
        llm.Requests.Should().BeEmpty();
    }

    [Theory]
    [InlineData("missing_boundary")]
    [InlineData("invalid_top_level_recovery_order")]
    [InlineData("invalid_nested_recovery_order")]
    [InlineData("missing_authority_source")]
    [InlineData("reordered_authority_sources")]
    [InlineData("nested_hash_mismatch")]
    [InlineData("mixed_evidence_refs")]
    public async Task IterationPlan_CreateAsync_BlocksIncompleteSkeletonSourceBoundaryBeforeLlm(string scenario)
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        await fixture.SeedRequirementMapAsync();
        var contract = await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync(contract);
        await fixture.ApplyPrototypeSkeletonBoundaryScenarioAsync(scenario);
        var llm = new CountingLlmRouteEngine();
        var service = new PrototypeIterationPlanService(fixture.Store, new PrototypeRouteStateWriter(), llmRouteEngine: llm);

        var result = await service.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement.", "manual_feedback"));

        result.Status.Should().Be("blocked");
        result.Blockers.Should().ContainSingle(item => item.DomainCode == "prototype_skeleton_stale");
        llm.Requests.Should().BeEmpty();
    }

    [Fact]
    public async Task ExecuteNextAsync_BlocksCapabilityFailureBeforeRunAndDeduplicatesDiagnostic()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        using var fixture = await BackendContractFixture.CreateAsync();
        await fixture.SeedRequirementMapAsync();
        await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync();
        var plan = await new PrototypeIterationPlanService(fixture.Store).CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest(
                "Please complete the first full playable loop: stable movement, visible encounter trigger, one battle, reward 3 choices, then return to the map.",
                "manual_feedback"));
        plan.Status.Should().Be("ready", plan.Summary);
        var confirmation = await new PrototypeIterationPlanService(fixture.Store).ConfirmAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanConfirmationRequest(plan.SessionId, plan.PlanHash));
        confirmation.Status.Should().Be("confirmed");
        var details = await fixture.Store.GetLatestProjectIterationSessionAsync(fixture.ProjectId);
        var readyEvaluation = JsonSerializer.Serialize(new PrototypeIterationPlanEvaluationResult(
            "ready_to_execute",
            "Ready for preflight.",
            "Test fixture isolates capability preflight.",
            "execute_next_goal"));
        await fixture.Store.UpdateProjectIterationSessionStatusAsync(
            details!.Session.SessionId,
            "ready",
            0,
            details.Session.LatestSummary,
            readyEvaluation,
            null);
        var sidecarPath = fixture.PathForTest("meta/routes/iteration-plan/latest.json");
        var sidecar = JsonNode.Parse(File.ReadAllText(sidecarPath, Encoding.UTF8))!.AsObject();
        var firstGoal = sidecar["goals"]![0]!.AsObject();
        firstGoal["capability_requirements"]!["dynamic_ui_required"] = true;
        firstGoal["godot_ui_update_ownership"] = JsonNode.Parse("""
        {
          "construction_owner": "HudPanel",
          "update_mode": "signal_driven",
          "state_owner": "GameState",
          "cleanup_policy": "disconnect_on_exit",
          "stable_item_identity": "hud_row_id"
        }
        """);
        new PrototypeRouteStateWriter().WriteIterationPlanState(await fixture.GetProjectAsync(), sidecar);
        var runner = new CountingHostedProcessRunner();
        var service = new PrototypeIterationGoalService(fixture.Store, fixture.Options, runner);

        var first = await service.ExecuteNextAsync(fixture.AccountId, fixture.ProjectId);
        var second = await service.ExecuteNextAsync(fixture.AccountId, fixture.ProjectId);
        var diagnostics = await fixture.Store.ListProjectDiagnosticSpoolForAdminAsync(
            new ProjectDiagnosticSpoolQuery("unresolved", fixture.AccountId, fixture.ProjectId, "execute-next-goal", "plan_hash_mismatch", "P1", 10));

        first.Status.Should().Be("plan_hash_mismatch");
        second.Status.Should().Be("plan_hash_mismatch");
        runner.CallCount.Should().Be(0);
        diagnostics.Should().ContainSingle();
    }

    [Fact]
    public async Task ExecuteNextAsync_ShouldRepairInteractionOwnerTamperingFromDatabaseCanonicalState()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        using var fixture = await BackendContractFixture.CreateAsync();
        await fixture.SeedRequirementMapAsync();
        await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync();
        var planService = new PrototypeIterationPlanService(fixture.Store);
        var plan = await planService.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement and HUD feedback.", "manual_feedback"));
        plan.Status.Should().Be("ready", plan.Summary);
        (await planService.ConfirmAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanConfirmationRequest(plan.SessionId, plan.PlanHash))).Status.Should().Be("confirmed");
        var details = await fixture.Store.GetLatestProjectIterationSessionAsync(fixture.ProjectId);
        var interactionGoal = plan.Goals.First(goal => goal.InteractionRegion is not null);
        foreach (var earlierGoal in details!.Goals.Where(goal => goal.GoalIndex < interactionGoal.GoalIndex))
        {
            await fixture.Store.UpdateProjectIterationGoalStatusAsync(earlierGoal.GoalId, "succeeded", "Completed before tamper target.", DateTimeOffset.UtcNow.ToString("O"));
        }
        details = await fixture.Store.GetLatestProjectIterationSessionAsync(fixture.ProjectId);
        await fixture.Store.UpdateProjectIterationSessionStatusAsync(
            details!.Session.SessionId,
            "ready",
            interactionGoal.GoalIndex - 1,
            details.Session.LatestSummary,
            JsonSerializer.Serialize(new PrototypeIterationPlanEvaluationResult(
                "ready_to_execute",
                "Ready for interaction tamper test.",
                "The test changes only the validated artifact owner set.",
                "execute_next_goal")),
            null);
        var artifactPath = fixture.PathForTest(interactionGoal.InteractionRegion!.ArtifactRef);
        var artifact = JsonNode.Parse(File.ReadAllText(artifactPath, Encoding.UTF8))!.AsObject();
        artifact["scene_node_owners"] = new JsonArray("module:tampered:interaction-owner");
        File.WriteAllText(artifactPath, artifact.ToJsonString(new JsonSerializerOptions { WriteIndented = true }), Encoding.UTF8);
        var runner = new CountingHostedProcessRunner();
        var service = new PrototypeIterationGoalService(fixture.Store, fixture.Options, runner);

        var result = await service.ExecuteNextAsync(fixture.AccountId, fixture.ProjectId);

        result.Status.Should().NotBe("interaction_region_missing");
        runner.CallCount.Should().Be(0);
        using var repaired = JsonDocument.Parse(File.ReadAllText(artifactPath, Encoding.UTF8));
        repaired.RootElement.GetProperty("scene_node_owners").EnumerateArray()
            .Select(static item => item.GetString())
            .Should().NotContain("module:tampered:interaction-owner");
    }

    [Fact]
    public async Task IterationPlan_ConfirmationIsHashBoundIdempotentAndRegenerationInvalidatesIt()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        using var fixture = await BackendContractFixture.CreateAsync();
        await fixture.SeedRequirementMapAsync();
        await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync();
        var service = new PrototypeIterationPlanService(fixture.Store);
        var firstPlan = await service.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement and HUD feedback.", "manual_feedback"));

        var confirmed = await service.ConfirmAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanConfirmationRequest(firstPlan.SessionId, firstPlan.PlanHash));
        var retry = await service.ConfirmAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanConfirmationRequest(firstPlan.SessionId, firstPlan.PlanHash));
        var conflict = await service.ConfirmAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanConfirmationRequest(firstPlan.SessionId, "other-plan-hash"));
        var regenerated = await service.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Create a new iteration plan for field movement, HUD feedback, and reward state.", "new_iteration_plan"));

        confirmed.Status.Should().Be("confirmed");
        confirmed.OperationStatus.Should().Be("created_run");
        retry.OperationStatus.Should().Be("returned_existing");
        conflict.Status.Should().Be("conflict");
        conflict.DomainCode.Should().Be("plan_hash_conflict");
        regenerated.SessionId.Should().NotBe(firstPlan.SessionId);
        regenerated.Confirmation!.Status.Should().Be("unconfirmed");
        var rounds = await service.ListAsync(fixture.AccountId, fixture.ProjectId);
        rounds.Should().HaveCount(2);
        rounds[0].RequiredModules.Should().NotBeNullOrEmpty();
        rounds[0].RequiredModules.Should().Contain(module => module.RequirementIds != null && module.RequirementIds.Count > 0);
        rounds[0].TraceabilityGoals.Should().NotBeNullOrEmpty();
        rounds[0].Confirmation!.Status.Should().Be("confirmed");
        rounds[1].Confirmation!.Status.Should().Be("unconfirmed");
    }

    [Fact]
    public async Task IterationPlan_ConfirmedDbAnchorCannotBeReplacedByRecomputedWorkspacePlan()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        using var fixture = await BackendContractFixture.CreateAsync();
        await fixture.SeedRequirementMapAsync();
        await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync();
        var service = new PrototypeIterationPlanService(fixture.Store);
        var plan = await service.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement and HUD feedback.", "manual_feedback"));
        (await service.ConfirmAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanConfirmationRequest(plan.SessionId, plan.PlanHash))).Status.Should().Be("confirmed");
        var project = await fixture.GetProjectAsync();
        var state = JsonNode.Parse(new PrototypeRouteStateWriter().ReadLatestIterationPlanState(project))!.AsObject();
        state["goals"]![0]!["description"] = "Tampered but rehashed plan.";
        using (var document = JsonDocument.Parse(state.ToJsonString()))
        {
            state["plan_hash"] = IterationPlanIntegrity.Compute(document.RootElement);
        }
        state["confirmation"] = new JsonObject
        {
            ["status"] = "unconfirmed",
            ["session_id"] = plan.SessionId,
            ["plan_hash"] = state["plan_hash"]!.GetValue<string>(),
            ["source_hash_ref"] = state["source_hash_ref"]!.GetValue<string>()
        };
        new PrototypeRouteStateWriter().WriteIterationPlanState(project, state);

        var result = await service.ConfirmAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanConfirmationRequest(plan.SessionId, state["plan_hash"]!.GetValue<string>()));
        var details = await fixture.Store.GetLatestProjectIterationSessionAsync(fixture.ProjectId);

        result.Status.Should().Be("conflict");
        result.DomainCode.Should().Be("plan_hash_conflict");
        details!.Session.TraceabilityAnchorJson.Should().Contain(plan.PlanHash);
    }

    [Fact]
    public async Task IterationPlan_ReadbackRequiresReconfirmationWhenDbAnchorIsMissing()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        using var fixture = await BackendContractFixture.CreateAsync();
        await fixture.SeedRequirementMapAsync();
        await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync();
        var service = new PrototypeIterationPlanService(fixture.Store);
        var plan = await service.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement and HUD feedback.", "manual_feedback"));
        (await service.ConfirmAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanConfirmationRequest(plan.SessionId, plan.PlanHash))).Status.Should().Be("confirmed");
        await using (var connection = new SqliteConnection(fixture.ConnectionString))
        {
            await connection.OpenAsync();
            await using var command = connection.CreateCommand();
            command.CommandText = "UPDATE project_iteration_sessions SET traceability_anchor_json = NULL WHERE id = $session_id";
            command.Parameters.AddWithValue("$session_id", plan.SessionId);
            await command.ExecuteNonQueryAsync();
        }

        var readback = await service.GetLatestAsync(fixture.AccountId, fixture.ProjectId);

        readback!.Confirmation!.Status.Should().Be("reconfirm_required");
    }

    [Fact]
    public async Task ConfirmAsync_RestoresCanonicalStateFromDatabaseWhenBothSidecarsAreMissing()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        using var fixture = await BackendContractFixture.CreateAsync();
        await fixture.SeedRequirementMapAsync();
        await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync();
        var service = new PrototypeIterationPlanService(fixture.Store);
        var plan = await service.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement and HUD feedback.", "manual_feedback"));
        var project = await fixture.GetProjectAsync();
        new PrototypeRouteStateWriter().ClearIterationPlanState(project);
        new PrototypeRouteStateWriter().DeleteIterationPlanSessionState(project, plan.SessionId);

        var confirmation = await service.ConfirmAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanConfirmationRequest(plan.SessionId, plan.PlanHash));

        confirmation.Status.Should().Be("confirmed");
        new PrototypeRouteStateWriter().ReadLatestIterationPlanState(project).Should().Contain(plan.SessionId);
        new PrototypeRouteStateWriter().ReadIterationPlanSessionState(project, plan.SessionId).Should().Contain(plan.PlanHash);
    }

    [Fact]
    public async Task ExecuteNextAsync_RestoresConfirmedSidecarFromTrustedDatabaseAnchor()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        using var fixture = await BackendContractFixture.CreateAsync();
        await fixture.SeedRequirementMapAsync();
        await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync();
        var planService = new PrototypeIterationPlanService(fixture.Store);
        var plan = await planService.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement and HUD feedback.", "manual_feedback"));
        (await planService.ConfirmAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanConfirmationRequest(plan.SessionId, plan.PlanHash))).Status.Should().Be("confirmed");
        var details = await fixture.Store.GetLatestProjectIterationSessionAsync(fixture.ProjectId);
        foreach (var goal in details!.Goals)
        {
            await fixture.Store.UpdateProjectIterationGoalStatusAsync(
                goal.GoalId,
                "succeeded",
                "Completed for sidecar recovery test.",
                DateTimeOffset.UtcNow.ToString("O"));
        }
        var project = await fixture.GetProjectAsync();
        var state = JsonNode.Parse(new PrototypeRouteStateWriter().ReadLatestIterationPlanState(project))!.AsObject();
        state["confirmation"]!["status"] = "unconfirmed";
        new PrototypeRouteStateWriter().WriteIterationPlanState(project, state);

        var result = await new PrototypeIterationGoalService(fixture.Store, fixture.Options, new CountingHostedProcessRunner())
            .ExecuteNextAsync(fixture.AccountId, fixture.ProjectId);
        var repaired = JsonNode.Parse(new PrototypeRouteStateWriter().ReadLatestIterationPlanState(project))!.AsObject();

        result.Status.Should().NotBe("plan_confirmation_required");
        repaired["confirmation"]!["status"]!.GetValue<string>().Should().Be("confirmed");
        repaired["confirmation"]!["plan_hash"]!.GetValue<string>().Should().Be(plan.PlanHash);
    }

    [Fact]
    public async Task IterationPlan_ConcurrentSameRequestReusesSingleSession()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        using var fixture = await BackendContractFixture.CreateAsync();
        await fixture.SeedRequirementMapAsync();
        await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync();
        var service = new PrototypeIterationPlanService(fixture.Store);
        var request = new PrototypeIterationPlanRequest("Complete field movement and HUD feedback.", "manual_feedback");

        var results = await Task.WhenAll(Enumerable.Range(0, 4).Select(_ =>
            service.CreateAsync(fixture.AccountId, fixture.ProjectId, request)));

        results.Select(result => result.SessionId).Distinct(StringComparer.Ordinal).Should().ContainSingle();
        results.Count(result => result.OperationStatus == "created_run").Should().Be(1);
        results.Count(result => result.OperationStatus is "returned_existing" or "active_run_reused").Should().Be(3);
    }

    [Fact]
    public async Task IterationPlan_DatabaseIdentityConstraintRejectsSecondStoreDuplicate()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        var secondStore = new PhaseAMetadataStore(fixture.ConnectionString, fixture.Options);
        const string identity = "shared-request-identity";
        var goals = new[] { new ProjectIterationGoalCreateCommand(1, "Goal", "Goal", "Acceptance") };

        var attempts = await Task.WhenAll(
            TryCreate(fixture.Store, "session-a"),
            TryCreate(secondStore, "session-b"));
        var persisted = await fixture.Store.GetProjectIterationSessionByRequestIdentityAsync(
            fixture.AccountId,
            fixture.ProjectId,
            identity);

        attempts.Count(static created => created).Should().Be(1);
        persisted.Should().NotBeNull();

        async Task<bool> TryCreate(PhaseAMetadataStore store, string sessionId)
        {
            try
            {
                await store.CreateProjectIterationSessionAsync(
                    fixture.AccountId,
                    fixture.ProjectId,
                    "manual_feedback",
                    "Same request.",
                    "Plan",
                    goals,
                    sessionId: sessionId,
                    requestIdentityHash: identity,
                    routeStateJson: $"{{\"session_id\":\"{sessionId}\",\"request_identity_hash\":\"{identity}\",\"status\":\"ready\"}}",
                    initialStatus: "ready");
                return true;
            }
            catch (ProjectIterationRequestIdentityConflictException)
            {
                return false;
            }
        }
    }

    [Fact]
    public async Task IterationPlan_RetryRecoversCanonicalPlanFromDatabaseWhenSidecarsAreMissing()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        using var fixture = await BackendContractFixture.CreateAsync();
        await fixture.SeedRequirementMapAsync();
        await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync();
        var service = new PrototypeIterationPlanService(fixture.Store);
        var request = new PrototypeIterationPlanRequest(
            "Complete field movement and HUD feedback.",
            "manual_feedback");
        var first = await service.CreateAsync(fixture.AccountId, fixture.ProjectId, request);
        (await service.ConfirmAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanConfirmationRequest(first.SessionId, first.PlanHash))).Status.Should().Be("confirmed");
        var project = await fixture.GetProjectAsync();
        var latestPath = Path.Combine(project.MetaPath, "routes", "iteration-plan", "latest.json");
        var sessionPath = Path.Combine(project.MetaPath, "routes", "iteration-plan", "sessions", $"{first.SessionId}.json");
        var latestMirrorPath = Path.Combine(project.RepoPath, "meta", "routes", "iteration-plan", "latest.json");
        var sessionMirrorPath = Path.Combine(project.RepoPath, "meta", "routes", "iteration-plan", "sessions", $"{first.SessionId}.json");
        File.Delete(latestPath);
        File.Delete(sessionPath);
        File.Delete(latestMirrorPath);
        File.Delete(sessionMirrorPath);
        foreach (var goal in first.Goals.Where(static goal => goal.InteractionRegion is not null))
        {
            File.WriteAllText(fixture.PathForTest(goal.InteractionRegion!.ArtifactRef), "{ invalid", Encoding.UTF8);
        }

        var latestWithoutSidecars = await service.GetLatestAsync(fixture.AccountId, fixture.ProjectId);
        var roundsWithoutSidecars = await service.ListAsync(fixture.AccountId, fixture.ProjectId);

        latestWithoutSidecars!.PlanHash.Should().Be(first.PlanHash);
        latestWithoutSidecars.RequiredModules.Should().NotBeNullOrEmpty();
        latestWithoutSidecars.Confirmation!.Status.Should().Be("confirmed");
        roundsWithoutSidecars.Should().ContainSingle();
        roundsWithoutSidecars[0].PlanHash.Should().Be(first.PlanHash);
        roundsWithoutSidecars[0].RequiredModules.Should().NotBeNullOrEmpty();
        roundsWithoutSidecars[0].Confirmation!.Status.Should().Be("confirmed");

        var retry = await service.CreateAsync(fixture.AccountId, fixture.ProjectId, request);
        var rounds = await service.ListAsync(fixture.AccountId, fixture.ProjectId);

        retry.SessionId.Should().Be(first.SessionId);
        retry.OperationStatus.Should().Be("returned_existing");
        retry.Confirmation!.Status.Should().Be("confirmed");
        rounds.Should().ContainSingle();
        File.Exists(latestPath).Should().BeTrue();
        File.Exists(sessionPath).Should().BeTrue();
        File.Exists(latestMirrorPath).Should().BeTrue();
        File.Exists(sessionMirrorPath).Should().BeTrue();
        JsonNode.Parse(File.ReadAllText(latestPath, Encoding.UTF8))!["confirmation"]!["status"]!
            .GetValue<string>().Should().Be("confirmed");
        first.Goals.Where(static goal => goal.InteractionRegion is not null)
            .Should().OnlyContain(goal => File.Exists(fixture.PathForTest(goal.InteractionRegion!.ArtifactRef)));
    }

    [Fact]
    public async Task IterationPlan_RetryDoesNotResurrectOlderDatabasePlanOverNewerSession()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        using var fixture = await BackendContractFixture.CreateAsync();
        await fixture.SeedRequirementMapAsync();
        await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync();
        var service = new PrototypeIterationPlanService(fixture.Store);
        var request = new PrototypeIterationPlanRequest(
            "Complete field movement and HUD feedback.",
            "manual_feedback");
        var first = await service.CreateAsync(fixture.AccountId, fixture.ProjectId, request);
        var project = await fixture.GetProjectAsync();
        new PrototypeRouteStateWriter().ClearIterationPlanState(project);
        new PrototypeRouteStateWriter().DeleteIterationPlanSessionState(project, first.SessionId);
        var newer = await fixture.Store.CreateProjectIterationSessionAsync(
            fixture.AccountId,
            fixture.ProjectId,
            "new_iteration_plan",
            "A newer plan already exists.",
            "Newer plan",
            [new ProjectIterationGoalCreateCommand(1, "Newer goal", "Newer goal", "Newer acceptance")]);
        await fixture.Store.UpdateProjectIterationSessionStatusAsync(
            newer.SessionId,
            "ready",
            0,
            "Newer plan is ready.");

        var retry = await service.CreateAsync(fixture.AccountId, fixture.ProjectId, request);
        var latest = await fixture.Store.GetLatestProjectIterationSessionAsync(fixture.ProjectId);
        var latestState = new PrototypeRouteStateWriter().ReadLatestIterationPlanState(project);

        retry.SessionId.Should().Be(first.SessionId);
        retry.OperationStatus.Should().Be("returned_existing");
        latest!.Session.SessionId.Should().Be(newer.SessionId);
        latestState.Should().BeEmpty("a historical idempotent retry must not restore itself as the latest route state");
    }

    [Fact]
    public async Task IterationPlanSessionSnapshot_SerializationHidesCanonicalDatabaseFields()
    {
        using var fixture = await BackendContractFixture.CreateAsync();
        var session = await fixture.Store.CreateProjectIterationSessionAsync(
            fixture.AccountId,
            fixture.ProjectId,
            "manual_feedback",
            "Create a plan.",
            "Plan",
            [new ProjectIterationGoalCreateCommand(1, "Goal", "Goal", "Acceptance")],
            requestIdentityHash: "private-request-hash",
            routeStateJson: "{\"private\":true}");
        var serialized = JsonSerializer.Serialize(session);

        serialized.Should().NotContain("traceabilityAnchorJson");
        serialized.Should().NotContain("requestIdentityHash");
        serialized.Should().NotContain("routeStateJson");
        serialized.Should().NotContain("private-request-hash");
    }

    [Fact]
    public async Task NeedsFixStrict_ShouldRejectUnknownGoalWithoutRunningProjectLevelRepair()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        using var fixture = await BackendContractFixture.CreateAsync();
        await fixture.SeedRequirementMapAsync();
        await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync();
        var planService = new PrototypeIterationPlanService(fixture.Store);
        var plan = await planService.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement and HUD feedback.", "manual_feedback"));
        plan.Status.Should().Be("ready", plan.Summary);
        (await planService.ConfirmAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanConfirmationRequest(plan.SessionId, plan.PlanHash))).Status.Should().Be("confirmed");
        var runner = new CountingHostedProcessRunner();
        var service = new PrototypeNeedsFixRouteService(
            fixture.Store,
            new PrototypeQuickFixService(fixture.Store, fixture.Options, runner),
            new PrototypeRouteStateWriter());

        var result = await service.RunStrictAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeNeedsFixRouteRequest("repair", GoalId: "missing-goal", GoalIndex: 999));

        result.Status.Should().Be("iteration_goal_not_found");
        runner.CallCount.Should().Be(0);

        var details = await fixture.Store.GetLatestProjectIterationSessionAsync(fixture.ProjectId);
        var pendingGoal = details!.Goals.First(goal => goal.Status == "pending");
        var pendingResult = await service.RunStrictAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeNeedsFixRouteRequest("repair pending", GoalId: pendingGoal.GoalId, GoalIndex: pendingGoal.GoalIndex));

        pendingResult.Status.Should().Be("iteration_goal_not_repairable");
        runner.CallCount.Should().Be(0);

        await fixture.Store.UpdateProjectIterationGoalStatusAsync(
            pendingGoal.GoalId,
            "needs_fix",
            "Needs repair for diagnostic coverage.",
            DateTimeOffset.UtcNow.ToString("O"));
        await fixture.Store.UpdateProjectIterationSessionStatusAsync(
            details.Session.SessionId,
            "needs_fix",
            pendingGoal.GoalIndex,
            "Needs repair for diagnostic coverage.",
            details.Session.LatestEvaluationJson,
            null);
        var project = await fixture.GetProjectAsync();
        var state = JsonNode.Parse(new PrototypeRouteStateWriter().ReadLatestIterationPlanState(project))!.AsObject();
        state["source_contract_hash"] = "tampered-contract-hash";
        new PrototypeRouteStateWriter().WriteIterationPlanState(project, state);

        var firstPreflightFailure = await service.RunStrictAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeNeedsFixRouteRequest("repair", GoalId: pendingGoal.GoalId, GoalIndex: pendingGoal.GoalIndex));
        var secondPreflightFailure = await service.RunStrictAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeNeedsFixRouteRequest("repair", GoalId: pendingGoal.GoalId, GoalIndex: pendingGoal.GoalIndex));
        var diagnostics = await fixture.Store.ListProjectDiagnosticSpoolForAdminAsync(
            new ProjectDiagnosticSpoolQuery("unresolved", fixture.AccountId, fixture.ProjectId, "needs-fix", "source_stale", "P1", 10));

        firstPreflightFailure.Status.Should().Be("source_stale");
        secondPreflightFailure.Status.Should().Be("source_stale");
        diagnostics.Should().ContainSingle();
        runner.CallCount.Should().Be(0);
    }

    [Fact]
    public async Task ExecuteNextAsync_ShouldReleaseRunnerLock_WhenGoalRunClaimFails()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        using var fixture = await BackendContractFixture.CreateAsync();
        await fixture.SeedRequirementMapAsync();
        await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync();
        var planService = new PrototypeIterationPlanService(fixture.Store);
        var plan = await planService.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement and HUD feedback.", "manual_feedback"));
        plan.Status.Should().Be("ready", plan.Summary);
        (await planService.ConfirmAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanConfirmationRequest(plan.SessionId, plan.PlanHash))).Status.Should().Be("confirmed");
        var details = await fixture.Store.GetLatestProjectIterationSessionAsync(fixture.ProjectId);
        await fixture.Store.UpdateProjectIterationSessionStatusAsync(
            details!.Session.SessionId,
            "ready",
            0,
            details.Session.LatestSummary,
            JsonSerializer.Serialize(new PrototypeIterationPlanEvaluationResult(
                "ready_to_execute",
                "Ready for claim failure test.",
                "The test forces the goal-run link to fail.",
                "execute_next_goal")),
            null);
        await using (var connection = new SqliteConnection(fixture.ConnectionString))
        {
            await connection.OpenAsync();
            await using var command = connection.CreateCommand();
            command.CommandText = """
                CREATE TRIGGER fail_iteration_goal_run_claim
                BEFORE INSERT ON project_iteration_goal_runs
                BEGIN
                    SELECT RAISE(ABORT, 'forced goal-run claim failure');
                END;
                """;
            await command.ExecuteNonQueryAsync();
        }
        var runner = new CountingHostedProcessRunner();
        var service = new PrototypeIterationGoalService(fixture.Store, fixture.Options, runner);

        var result = await service.ExecuteNextAsync(fixture.AccountId, fixture.ProjectId);
        var project = await fixture.GetProjectAsync();
        var probeRunId = await fixture.Store.CreateRunAsync(fixture.ProjectId, project.WorkspaceId, "runner-lock-probe");
        var reacquired = await fixture.Store.TryAcquireRunnerLockAsync(fixture.ProjectId, probeRunId);

        result.Status.Should().Be("failed");
        reacquired.Should().BeTrue();
        runner.CallCount.Should().Be(0);
        await fixture.Store.ReleaseRunnerLockAsync(fixture.ProjectId, probeRunId);
    }

    [Fact]
    public async Task ExecuteNextAsync_ShouldHoldProjectMutationLeaseUntilExecutionFinishes()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        using var fixture = await BackendContractFixture.CreateAsync();
        await fixture.SeedRequirementMapAsync();
        await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync();
        var planService = new PrototypeIterationPlanService(fixture.Store);
        var plan = await planService.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement and HUD feedback.", "manual_feedback"));
        (await planService.ConfirmAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanConfirmationRequest(plan.SessionId, plan.PlanHash))).Status.Should().Be("confirmed");
        var details = await fixture.Store.GetLatestProjectIterationSessionAsync(fixture.ProjectId);
        await fixture.Store.UpdateProjectIterationSessionStatusAsync(
            details!.Session.SessionId,
            "ready",
            0,
            details.Session.LatestSummary,
            JsonSerializer.Serialize(new PrototypeIterationPlanEvaluationResult(
                "ready_to_execute",
                "Ready for mutation lease test.",
                "The runner blocks while confirmation attempts to acquire the same lease.",
                "execute_next_goal")),
            null);
        var project = await fixture.GetProjectAsync();
        new PrototypeRouteStateWriter().WritePrototypeState(project, new
        {
            route = "prototype-7day-playable",
            status = "succeeded",
            prototype_completion = new { succeeded = true }
        });
        var runner = new BlockingHostedProcessRunner();
        var executionService = new PrototypeIterationGoalService(fixture.Store, fixture.Options, runner);

        var executionTask = executionService.ExecuteNextAsync(fixture.AccountId, fixture.ProjectId);
        await runner.Started.Task.WaitAsync(TimeSpan.FromSeconds(10));
        var confirmationTask = planService.ConfirmAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanConfirmationRequest(plan.SessionId, plan.PlanHash));
        await Task.Delay(150);

        confirmationTask.IsCompleted.Should().BeFalse();
        runner.Release.TrySetResult();
        await executionTask.WaitAsync(TimeSpan.FromSeconds(20));
        (await confirmationTask.WaitAsync(TimeSpan.FromSeconds(20))).Status.Should().Be("confirmed");
    }

    [Fact]
    public async Task ConfirmAsync_ShouldRestoreDatabaseCanonicalState_WhenLatestPlanStateIsMalformed()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        using var fixture = await BackendContractFixture.CreateAsync();
        await fixture.SeedRequirementMapAsync();
        await new PrototypeContractFreezeService(fixture.Store)
            .FreezeAsync(fixture.AccountId, fixture.ProjectId, new PrototypeContractFreezeRequest());
        await fixture.SeedPrototypeSkeletonAsync();
        var service = new PrototypeIterationPlanService(fixture.Store);
        var plan = await service.CreateAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanRequest("Complete field movement and HUD feedback.", "manual_feedback"));
        var project = await fixture.GetProjectAsync();
        File.WriteAllText(fixture.PathForTest("meta/routes/iteration-plan/latest.json"), "{", Encoding.UTF8);
        File.WriteAllText(Path.Combine(project.MetaPath, "routes", "iteration-plan", "latest.json"), "{", Encoding.UTF8);

        var result = await service.ConfirmAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new PrototypeIterationPlanConfirmationRequest(plan.SessionId, plan.PlanHash));
        var diagnostics = await fixture.Store.ListProjectDiagnosticSpoolForAdminAsync(
            new ProjectDiagnosticSpoolQuery("unresolved", fixture.AccountId, fixture.ProjectId, "iteration-plan", "iteration_plan_state_invalid", "P1", 10));

        result.Status.Should().Be("confirmed");
        diagnostics.Should().BeEmpty();
        new PrototypeRouteStateWriter().ReadLatestIterationPlanState(project).Should().Contain(plan.PlanHash);
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
            PhaseAPlatformOptions options,
            string accountId,
            string projectId)
        {
            _database = database;
            _workspaceRoot = workspaceRoot;
            _repoRoot = repoRoot;
            Store = store;
            Options = options;
            AccountId = accountId;
            ProjectId = projectId;
        }

        public PhaseAMetadataStore Store { get; }

        public PhaseAPlatformOptions Options { get; }

        public string AccountId { get; }

        public string ProjectId { get; }

        public string ConnectionString => _database.ConnectionString;

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
            var guideRoot = Path.Combine(repoRoot.Path, "docs", "game-type-guides");
            Directory.CreateDirectory(guideRoot);
            File.WriteAllText(
                Path.Combine(guideRoot, "game-types.csv"),
                "id,name,description,genre_tags,fragment_file\nrpg,RPG,Role-playing game,rpg,rpg.md\n",
                Encoding.UTF8);
            File.WriteAllText(
                Path.Combine(guideRoot, "rpg.md"),
                "# RPG Guide\n\nThis stable guide paragraph defines an RPG field-map, encounter, reward, and return loop for source-boundary fingerprint tests.\n",
                Encoding.UTF8);
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
            var project = await store.GetProjectSnapshotAsync(result.ProjectId!);
            var hostedGuideRoot = Path.Combine(project!.RepoPath, "docs", "game-type-guides");
            Directory.CreateDirectory(hostedGuideRoot);
            File.Copy(Path.Combine(guideRoot, "game-types.csv"), Path.Combine(hostedGuideRoot, "game-types.csv"), overwrite: true);
            File.Copy(Path.Combine(guideRoot, "rpg.md"), Path.Combine(hostedGuideRoot, "rpg.md"), overwrite: true);
            return new BackendContractFixture(database, workspaceRoot, repoRoot, store, options, accountId, result.ProjectId!);
        }

        public async Task<ProjectSnapshot> GetProjectAsync()
        {
            return (await Store.GetProjectSnapshotAsync(ProjectId))!;
        }

        public async Task<string> CreateGddPromptRunAsync(string suffix)
        {
            var project = await GetProjectAsync();
            var runId = await Store.CreateRunAsync(ProjectId, project.WorkspaceId, "game-design-gdd");
            var promptRelativePath = $"logs/phase-a-gdd/test/{suffix}-gdd-prompt.md";
            var parsedRouteProfileJson = JsonSerializer.Serialize(PrototypeRouteSkillPolicy.ResolveProfile(project));
            var selectedRouteSkillPromptBlock = PrototypeRouteSkillPolicy.BuildPromptBlock(project);
            var recoveryAuthorityHashes = RecoveryAuthorityHashes(project);
            var prompt = $"""
                Parsed game-type route profile authority:
                {parsedRouteProfileJson}

                Selected route skill prompt block authority:
                {selectedRouteSkillPromptBlock}

                Generate the GDD from the confirmed scene route.
                """;
            WriteText(promptRelativePath, prompt);
            await Store.AddArtifactAsync(new ArtifactCreationCommand(
                runId,
                ProjectId,
                "game-design-gdd-prompt",
                promptRelativePath,
                "GDD prompt"));
            var fingerprints = new BmadGameTypeDesignCatalog(Options).Entries
                .Where(entry => !string.IsNullOrWhiteSpace(entry.GuideExcerpt))
                .SelectMany(entry => HostedRouteForbiddenSourceGuard.CreateContentFingerprints(
                    entry.FragmentRelativePath,
                    entry.GuideExcerpt))
                .GroupBy(item => item.ContentHash, StringComparer.Ordinal)
                .Select(group => group.First())
                .OrderBy(item => item.ContentHash, StringComparer.Ordinal)
                .ToArray();
            var scan = HostedRouteForbiddenSourceGuard.Scan(
                prompt,
                ["docs/game-type-guides/** raw excerpts", "unapproved raw game-type guide excerpt before contract freeze"],
                fingerprints,
                requireForbiddenContentFingerprints: true);
            var promptEvidenceRelativePath = $"logs/phase-a-gdd/test/{suffix}-gdd-prompt-source-evidence.json";
            WriteJson(promptEvidenceRelativePath, JsonSerializer.Serialize(new
            {
                schema_version = "gdd-prompt-source-evidence.v1",
                route = "gdd-document-generation",
                run_id = runId,
                recovery_source_order_ref = HostedRouteRecoveryContract.ContractId,
                recovery_source_order = HostedRouteRecoveryContract.SourceOrder,
                source_hashes = recoveryAuthorityHashes,
                prompt_manifest = new
                {
                    prompt_count = 1,
                    prompt_artifact_refs = new[] { promptRelativePath },
                    execution_prompt_hash = scan.PromptHash,
                    persisted_prompt_hash = HostedRouteForbiddenSourceGuard.PromptHash(prompt),
                    retention = "internal_recovery_only",
                    browser_readable = false,
                    redacted = true
                },
                allowed_source_references = Array.Empty<string>(),
                forbidden_source_scan = scan
            }));
            await Store.AddArtifactAsync(new ArtifactCreationCommand(
                runId,
                ProjectId,
                GameDesignDocumentService.PromptSourceEvidenceArtifactType,
                promptEvidenceRelativePath,
                "GDD prompt source evidence"));
            await Store.CompleteRunAsync(
                runId,
                "succeeded",
                0,
                "",
                "",
                JsonSerializer.Serialize(new
                {
                    run_type = "game-design-gdd",
                    generated_gdd_hash = Sha256(NormalizeText(File.ReadAllText(PathFor("docs/gdd/GDD.md"), Encoding.UTF8))),
                    recovery_source_order_ref = HostedRouteRecoveryContract.ContractId,
                    recovery_source_order = HostedRouteRecoveryContract.SourceOrder,
                    source_hashes = recoveryAuthorityHashes,
                    prompt_manifest = new
                    {
                        execution_prompt_hash = scan.PromptHash,
                        persisted_prompt_hash = HostedRouteForbiddenSourceGuard.PromptHash(prompt),
                        prompt_artifact_ref = promptRelativePath,
                        prompt_source_evidence_ref = promptEvidenceRelativePath,
                        redacted = true
                    }
                }));
            return runId;
        }

        public Dictionary<string, string> RecoveryAuthorityHashes(ProjectSnapshot project)
        {
            return new Dictionary<string, string>(StringComparer.Ordinal)
            {
                [HostedRouteRecoveryContract.ParsedRouteProfileHashKey] = HostedRouteForbiddenSourceGuard.PromptHash(
                    JsonSerializer.Serialize(PrototypeRouteSkillPolicy.ResolveProfile(project))),
                [HostedRouteRecoveryContract.SelectedRouteSkillPromptBlockHashKey] = HostedRouteForbiddenSourceGuard.PromptHash(
                    PrototypeRouteSkillPolicy.BuildPromptBlock(project))
            };
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
            WriteSceneRoute("confirmed", "", GddHash, StructuredHash());
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

        public async Task SeedRequirementMapAsync(string? requirementMapJson = null)
        {
            SeedConfirmedSceneRouteAndGdd();
            var result = await new GameDesignRequirementMapService(Store, new FixedRequirementMapLlmEngine(requirementMapJson ?? """
            {
              "requirements": [
                { "requirement_id": "REQ-001", "normalized_requirement": "Player moves on the field map.", "priority": "P0", "kind": "scene", "mapped_scene_ids": ["field_map"], "mapped_required_module_ids": ["field_map"], "status": "mapped" },
                { "requirement_id": "REQ-002", "normalized_requirement": "HUD shows HP and reward feedback.", "priority": "P1", "kind": "ui", "mapped_scene_ids": ["field_map"], "mapped_required_module_ids": ["combat_hud"], "status": "mapped", "capability_domain_ids": ["ui_component_system", "ui_overlays_feedback"] }
              ]
            }
            """)).CreateAsync(AccountId, ProjectId, new GameDesignRequirementMapRequest());
            result.Status.Should().Be("ready");
        }

        public async Task SeedPrototypeSkeletonAsync(
            PrototypeContractStatusResult? contract = null,
            string? sourceContractHash = null,
            string? sourceContractSnapshotHash = null,
            IReadOnlyList<string>? verifiedRequirementIds = null)
        {
            contract ??= new PrototypeContractFreezeService(Store).EvaluateNewChainGuard(await GetProjectAsync()).ContractStatus;
            var project = await GetProjectAsync();
            WriteJson("meta/routes/prototype-skeleton/acceptance-evidence.json", "{}");
            var routeStateWriter = new PrototypeRouteStateWriter();
            routeStateWriter.WritePrototypeSkeletonState(project, new
            {
                schema_version = "prototype-skeleton-readback.v1",
                route = "prototype-skeleton",
                status_dimension = RouteStatusVocabulary.RouteReadback,
                status_allowed_values = RouteStatusVocabulary.Values(RouteStatusVocabulary.RouteReadback),
                status = "succeeded",
                source_boundary_enforced = true,
                recovery_source_order_ref = "hosted-route-recovery-order.v1",
                source_boundary = new
                {
                    recovery_source_order_ref = "hosted-route-recovery-order.v1",
                    recovery_source_order = HostedRouteRecoveryContract.SourceOrder,
                    authority_sources = new[]
                    {
                        "game-type-route-profile",
                        PrototypeRouteStateWriter.ProjectExecutionGuideRelativePath,
                        "routes/prototype-contract/latest.json",
                        "meta/routes/gdd-requirements/latest.json",
                        "meta/routes/prototype/latest.json"
                    },
                    source_hashes = new
                    {
                        source_gdd_hash = contract.SourceGddHash,
                        source_scene_route_hash = contract.SourceSceneRouteHash,
                        source_requirement_map_hash = contract.SourceRequirementMapHash,
                        source_contract_hash = sourceContractHash ?? contract.ContractHash,
                        source_contract_snapshot_hash = sourceContractSnapshotHash ?? contract.SourceContractSnapshotHash,
                        source_godot_ui_contract_hash = contract.SourceGodotUiContractHash,
                        source_ui_style_contract_hash = contract.SourceUiStyleContractHash,
                        ui_style_snapshot_hash = contract.UiStyleSnapshotHash
                    },
                    forbidden_source_patterns = new[]
                    {
                        "docs/game-type-guides/** raw excerpts",
                        "assistant summary as acceptance authority"
                    }
                },
                freshness = "fresh",
                source_gdd_hash = contract.SourceGddHash,
                source_scene_route_hash = contract.SourceSceneRouteHash,
                source_requirement_map_hash = contract.SourceRequirementMapHash,
                source_contract_hash = sourceContractHash ?? contract.ContractHash,
                source_contract_snapshot_hash = sourceContractSnapshotHash ?? contract.SourceContractSnapshotHash,
                source_godot_ui_contract_hash = contract.SourceGodotUiContractHash,
                source_ui_style_contract_hash = contract.SourceUiStyleContractHash,
                ui_style_snapshot_hash = contract.UiStyleSnapshotHash,
                verified_scene_ids = new[] { "field_map" },
                verified_requirement_ids = verifiedRequirementIds ?? ["REQ-001", "REQ-002"],
                evidence_refs = new[] { new { kind = "sidecar", path = "meta/routes/prototype-skeleton/acceptance-evidence.json" } },
                updated_utc = DateTimeOffset.UtcNow.ToString("O")
            });
        }

        public async Task ApplyPrototypeSkeletonBoundaryScenarioAsync(string scenario)
        {
            var project = await GetProjectAsync();
            var copies = new PrototypeRouteStateWriter().ReadPrototypeSkeletonStateCopies(project);
            var root = JsonNode.Parse(copies.MetadataState)!.AsObject();
            var boundary = root["source_boundary"]!.AsObject();
            switch (scenario)
            {
                case "missing_boundary":
                    root.Remove("source_boundary");
                    break;
                case "invalid_top_level_recovery_order":
                    root["recovery_source_order_ref"] = "legacy-order.v0";
                    break;
                case "invalid_nested_recovery_order":
                    boundary["recovery_source_order_ref"] = "legacy-order.v0";
                    break;
                case "missing_authority_source":
                    boundary["authority_sources"]!.AsArray().RemoveAt(0);
                    break;
                case "reordered_authority_sources":
                    var sources = boundary["authority_sources"]!.AsArray();
                    var first = sources[0]!.DeepClone();
                    sources[0] = sources[1]!.DeepClone();
                    sources[1] = first;
                    break;
                case "nested_hash_mismatch":
                    boundary["source_hashes"]!["source_contract_hash"] = "stale-contract-hash";
                    break;
                case "mixed_evidence_refs":
                    root["evidence_refs"] = new JsonArray
                    {
                        new JsonObject { ["kind"] = "sidecar", ["path"] = "meta/routes/prototype/latest.json" },
                        new JsonObject { ["kind"] = "sidecar", ["path"] = "../outside.json" }
                    };
                    break;
                default:
                    throw new ArgumentOutOfRangeException(nameof(scenario), scenario, "Unknown skeleton boundary scenario.");
            }

            new PrototypeRouteStateWriter().WritePrototypeSkeletonState(project, root);
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
                case "game_type_hash_missing":
                    WriteSceneRoute("confirmed", SceneRouteHash, GddHash, "");
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
            var project = GetProjectAsync().GetAwaiter().GetResult();
            var node = JsonSerializer.SerializeToNode(new
            {
                schema_version = "scene-route.v1",
                route = "scene-route-confirmation",
                status,
                source_game_type_structured_hash = structuredHash,
                source_gdd_form_hash = "gdd-form-hash-v1",
                source_generated_gdd_hash = gddHash,
                source_contract_snapshot_hash = GddToModuleAuthorityHashes.ComputeContractSnapshotHash(project.GameTypeMatchJson),
                confirmed_scene_route_hash = sceneHash,
                scene_count_intent = "single",
                entry_scene = "field_map",
                scenes = new[]
                {
                    new { scene_id = "field_map", scene_name = "Field Map", role = "hub", m1_required = true, player_goal = "Move and encounter." }
                },
                transitions = Array.Empty<object>(),
                single_scene_confirmation = new { allowed = true, reason = "fixture" },
                notes = Array.Empty<string>()
            })!.AsObject();
            using var document = JsonDocument.Parse(node.ToJsonString());
            SceneRouteHash = GddToModuleAuthorityHashes.ComputeSceneRouteHash(document.RootElement);
            node["confirmed_scene_route_hash"] = SceneRouteHash;
            WriteJson("meta/routes/scene-route/latest.json", node.ToJsonString());
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
            return GddToModuleAuthorityHashes.ComputeStructuredGameTypeHash(
                GetProjectAsync().GetAwaiter().GetResult().GameTypeMatchJson);
        }

        public void WriteText(string relativePath, string text)
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

    private sealed class CountingHostedProcessRunner : IHostedProcessRunner
    {
        public int CallCount { get; private set; }

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            CallCount++;
            throw new InvalidOperationException("Runner must not be called before capability preflight passes.");
        }
    }

    private sealed class BlockingHostedProcessRunner : IHostedProcessRunner
    {
        public TaskCompletionSource Started { get; } = new(TaskCreationOptions.RunContinuationsAsynchronously);

        public TaskCompletionSource Release { get; } = new(TaskCreationOptions.RunContinuationsAsynchronously);

        public async Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Started.TrySetResult();
            await Release.Task.WaitAsync(cancellationToken);
            throw new InvalidOperationException("forced runner completion for mutation lease test");
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

    private sealed class CountingLlmRouteEngine : ILlmRouteEngine
    {
        public List<LlmRouteRequest> Requests { get; } = [];

        public Task<LlmRouteResult> CompleteAsync(LlmRouteRequest request, CancellationToken cancellationToken = default)
        {
            Requests.Add(request);
            throw new InvalidOperationException("The planning LLM must not run before the skeleton authority gate passes.");
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
