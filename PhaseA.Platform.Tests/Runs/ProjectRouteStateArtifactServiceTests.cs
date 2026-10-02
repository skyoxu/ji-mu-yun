using FluentAssertions;
using System.Text.Json;
using System.Text.Json.Nodes;
using PhaseA.Platform.Data;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Workflow;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class ProjectRouteStateArtifactServiceTests
{
    // ADR-0036/0038: final closure cannot be inferred from a success string.
    [Fact]
    public void Read_WhenSuccessfulUiClosureOmitsLedgerAndCurrentInputs_BlocksFinalReadiness()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/ui-wiring/latest.json", """
        { "schema_version": "ui-wiring-closure.v1", "status": "succeeded", "ui_surface_matrix": [] }
        """);
        var readback = fixture.Read();
        readback.BlockingIssues.Should().Contain(issue => issue.IssueId.EndsWith(":missing_ledger_row"));
        readback.BlockingIssues.Should().Contain(issue => issue.IssueId == "ui-wiring:final-sources:source_contract_hash:missing_or_stale");
        readback.BlockingIssues.Should().Contain(issue => issue.IssueId == "ui-wiring:final-sources:validation_not_succeeded");
    }

    [Fact]
    public void Read_WhenFullTargetLedgerDuplicatesCapabilityOrOmitsMetadata_BlocksClosure()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/ui-wiring/latest.json", """
        {
          "schema_version": "ui-wiring-closure.v1", "status": "succeeded", "ui_surface_matrix": [],
          "full_target_closure_ledger": [
            { "capability_id": "ui_component_system", "status": "covered" },
            { "capability_id": "ui_component_system", "status": "covered" }
          ]
        }
        """);
        var issues = fixture.Read().BlockingIssues;
        issues.Should().Contain(issue => issue.IssueId == "ui-wiring:full-target:ui_component_system:duplicate_ledger_row");
        issues.Should().Contain(issue => issue.IssueId == "ui-wiring:full-target:ui_component_system:missing_owner_expiry_or_validation_evidence");
    }

    [Fact]
    public void Read_ProjectsUiHashesAndRejectsChangedIterationSource()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/iteration-plan/latest.json", """
        { "schema_version": "iteration-plan.v1", "status": "ready", "plan_hash": "current-plan" }
        """);
        fixture.WriteJson("meta/routes/ui-wiring/latest.json", """
        {
          "schema_version": "ui-wiring-closure.v1", "status": "succeeded", "ui_surface_matrix": [],
          "source_iteration_session_hash": "old-plan", "source_validation_input_hash": "validation-input",
          "source_contract_hash": "contract", "source_requirement_map_hash": "requirements",
          "source_godot_ui_contract_hash": "godot", "source_ui_style_contract_hash": "style", "ui_style_snapshot_hash": "snapshot"
        }
        """);
        var readback = fixture.Read();
        var ui = readback.Artifacts.Single(artifact => artifact.Route == "ui-wiring");
        ui.SourceIterationSessionHash.Should().Be("old-plan");
        ui.SourceValidationInputHash.Should().Be("validation-input");
        ui.SourceContractHash.Should().Be("contract");
        readback.BlockingIssues.Should().Contain(issue => issue.IssueId == "ui-wiring:final-sources:source_iteration_session_hash:missing_or_stale");
    }

    [Fact]
    public void Read_WhenFinalUiLedgerAndSourceBindingsMatch_HasNoLedgerOrFinalSourceBlockers()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteFinalUiSourcesAndLedger();
        fixture.Read().BlockingIssues.Should().NotContain(issue =>
            issue.IssueId.StartsWith("ui-wiring:full-target:") || issue.IssueId.StartsWith("ui-wiring:final-sources:"));
    }

    // ADR-0036/0038: matching hashes do not erase source-validator errors.
    [Theory]
    [InlineData("schema_version")]
    [InlineData("status_dimension")]
    [InlineData("source_boundary_enforced")]
    public void Read_WhenValidationSourceOmitsRequiredMetadata_BlocksFinalSources(string field)
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteFinalUiSourcesAndLedger();
        fixture.UpdateJson("meta/routes/validation/latest.json", node => node.Remove(field));
        fixture.Read().BlockingIssues.Should().Contain(issue =>
            issue.Severity == "P1" && issue.IssueId.StartsWith("ui-wiring:final-sources:meta/routes/validation/latest.json:"));
    }

    [Theory]
    [InlineData("stale", "fresh")]
    [InlineData("ready", "stale")]
    [InlineData("blocked", "fresh")]
    public void Read_WhenIterationStatusOrFreshnessIsInvalid_BlocksDespiteMatchingHash(string status, string freshness)
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteFinalUiSourcesAndLedger();
        fixture.UpdateJson("meta/routes/iteration-plan/latest.json", node =>
        {
            node["status"] = status;
            node["freshness"] = new JsonObject { ["status"] = freshness };
        });
        fixture.Read().BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "ui-wiring:final-sources:iteration_not_ready_or_fresh");
    }

    [Fact]
    public void Read_WhenIterationPayloadChangesWithoutChangingDeclaredHash_BlocksFinalSources()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteFinalUiSourcesAndLedger();
        fixture.UpdateJson("meta/routes/iteration-plan/latest.json", node =>
            node["goals"] = new JsonArray(new JsonObject { ["goal"] = "changed" }));
        fixture.Read().BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "ui-wiring:final-sources:iteration_plan_integrity_invalid");
    }

    [Fact]
    public void Read_WhenIterationPromptEvidenceLosesProjectBinding_BlocksFinalSources()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteFinalUiSourcesAndLedger();
        fixture.RemovePromptBinding("iteration-plan");
        fixture.Read().BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "ui-wiring:final-sources:meta/routes/iteration-plan/latest.json:prompt_evidence_invalid");
    }

    [Theory]
    [InlineData("covered")]
    [InlineData("reviewed_not_applicable")]
    [InlineData("explicitly_deferred")]
    public void Read_WhenLedgerReferencesMissingEvidence_BlocksEveryFinalClosureStatus(string status)
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteFinalUiSourcesAndLedger(status);
        fixture.UpdateJson("meta/routes/ui-wiring/latest.json", node =>
        {
            foreach (var row in node["full_target_closure_ledger"]!.AsArray())
            {
                row!["validation_evidence_refs"] = new JsonArray("meta/routes/validation/missing.json");
                row["phase_exit_review_ref"] = "meta/reviews/missing.json";
            }
        });
        var issues = fixture.Read().BlockingIssues;
        issues.Should().Contain(issue => issue.IssueId.EndsWith(":validation_evidence_unavailable"));
        issues.Should().Contain(issue => issue.IssueId.EndsWith(":phase_exit_review_unavailable"));
    }

    [Fact]
    public void Read_WhenLedgerReferenceLeavesProjectBoundary_BlocksExistingForeignFile()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteFinalUiSourcesAndLedger();
        fixture.WriteText("../foreign-evidence.json", "{}");
        fixture.UpdateJson("meta/routes/ui-wiring/latest.json", node =>
            node["full_target_closure_ledger"]![0]!["validation_evidence_refs"] = new JsonArray("../foreign-evidence.json"));
        fixture.Read().BlockingIssues.Should().Contain(issue =>
            issue.IssueId.EndsWith(":validation_evidence_unavailable"));
    }

    [Fact]
    public void Read_WhenLedgerReferencesReparseEvidence_Blocks()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteFinalUiSourcesAndLedger();
        var link = Path.Combine(fixture.Project.RepoPath, "meta", "reviews", "linked.json");
        File.CreateSymbolicLink(link, Path.Combine(fixture.Project.RepoPath, "meta", "reviews", "final.json"));
        fixture.UpdateJson("meta/routes/ui-wiring/latest.json", node =>
            node["full_target_closure_ledger"]![0]!["phase_exit_review_ref"] = "meta/reviews/linked.json");
        fixture.Read().BlockingIssues.Should().Contain(issue =>
            issue.IssueId.EndsWith(":phase_exit_review_unavailable"));
    }

    [Theory]
    [InlineData("null")]
    [InlineData("\"ready\"")]
    [InlineData("[]")]
    public void Read_WhenRouteArtifactJsonRootIsNotObject_FailsClosed(string json)
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/gdd-requirements/latest.json", json);

        var readback = fixture.Read();

        readback.Artifacts.Single(artifact => artifact.Route == "gdd-requirements").Status.Should().Be("failed");
        readback.BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/gdd-requirements/latest.json:invalid_root");
    }

    [Fact]
    public void Read_WhenPromptRouteOmitsBoundaryDetails_BlocksWithSourceBoundaryIssue()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/gdd-requirements/latest.json", """
        {
          "schema_version": "gdd-requirements.v1",
          "route": "gdd-requirements",
          "status_dimension": "route_readback",
          "status_allowed_values": ["ready", "needs_review", "blocked", "stale", "unknown"],
          "status": "ready",
          "source_boundary_enforced": true,
          "source_boundary": {
            "authority_sources": ["docs/gdd/GDD.md"]
          },
          "requirements": []
        }
        """);

        var readback = fixture.Read();

        readback.Status.Should().Be("blocked");
        readback.BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/gdd-requirements/latest.json:source_boundary_incomplete" &&
            issue.Severity == "P0");
    }

    [Fact]
    public void Read_WhenPromptRouteHasCompleteBoundaryAndSavedEvidence_DoesNotReportBoundaryIssues()
    {
        using var fixture = RouteStateFixture.Create();
        const string gdd = "# GDD\n\n- Stable requirement.";
        var gddHash = RouteStateFixture.Hash(gdd);
        fixture.WriteText("docs/gdd/GDD.md", gdd);
        fixture.WritePromptEvidence(
            "meta/routes/gdd-requirements/prompt-evidence.json",
            "Use only the frozen GDD.",
            new Dictionary<string, string> { ["docs/gdd/GDD.md"] = gddHash },
            ["assistant summary as acceptance authority"]);
        fixture.WriteJson("meta/routes/gdd-requirements/latest.json", $$"""
        {
          "schema_version": "gdd-requirements.v1",
          "route": "gdd-requirements",
          "status": "ready",
          "source_boundary_enforced": true,
          "source_boundary": {
            "recovery_source_order_ref": "hosted-route-recovery-order.v1",
            "recovery_source_order": ["parsed game-type route profile", "selected route skill prompt block", "meta/project-execution-guide.md", "routes/prototype-contract/latest.json", "current route latest state", "current goal/step/session state when applicable", "repair ledger and failing acceptance/Godot diagnostic evidence when applicable", "latest live platform acceptance blocker"],
            "authority_sources": ["docs/gdd/GDD.md"],
            "source_hashes": { "docs/gdd/GDD.md": "{{gddHash}}" },
            "forbidden_source_patterns": ["assistant summary as acceptance authority"],
            "prompt_evidence_refs": ["meta/routes/gdd-requirements/prompt-evidence.json"]
          },
          "requirements": []
        }
        """);

        var readback = fixture.Read();

        readback.BlockingIssues.Should().NotContain(issue =>
            issue.IssueId.Contains("source_boundary", StringComparison.Ordinal) ||
            issue.IssueId.Contains("recovery_source_order", StringComparison.Ordinal) ||
            issue.IssueId.Contains("source_hashes", StringComparison.Ordinal) ||
            issue.IssueId.Contains("prompt_evidence", StringComparison.Ordinal));
    }

    [Fact]
    public void Read_WhenPromptEvidenceDeclaresExtraAuthorityHash_Blocks()
    {
        using var fixture = RouteStateFixture.Create();
        const string gdd = "# GDD\n\n- Stable requirement.";
        var gddHash = RouteStateFixture.Hash(gdd);
        fixture.WriteText("docs/gdd/GDD.md", gdd);
        fixture.WritePromptEvidence(
            "meta/routes/gdd-requirements/prompt-evidence.json",
            "Use only the frozen GDD.",
            new Dictionary<string, string>
            {
                ["docs/gdd/GDD.md"] = gddHash,
                ["meta/project-execution-guide.md"] = new string('a', 64)
            },
            ["assistant summary as acceptance authority"]);
        fixture.WriteJson("meta/routes/gdd-requirements/latest.json", JsonSerializer.Serialize(new
        {
            schema_version = "gdd-requirements.v1",
            route = "gdd-requirements",
            status_dimension = RouteStatusVocabulary.RouteReadback,
            status_allowed_values = RouteStatusVocabulary.Values(RouteStatusVocabulary.RouteReadback),
            status = "ready",
            source_boundary_enforced = true,
            source_boundary = new
            {
                recovery_source_order_ref = HostedRouteRecoveryContract.ContractId,
                recovery_source_order = HostedRouteRecoveryContract.SourceOrder,
                authority_sources = new[] { "docs/gdd/GDD.md" },
                source_hashes = new Dictionary<string, string> { ["docs/gdd/GDD.md"] = gddHash },
                forbidden_source_patterns = new[] { "assistant summary as acceptance authority" },
                prompt_evidence_refs = new[] { "meta/routes/gdd-requirements/prompt-evidence.json" }
            },
            requirements = Array.Empty<object>()
        }));

        fixture.Read().BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/gdd-requirements/latest.json:prompt_evidence_invalid");
    }

    [Fact]
    public void Read_WhenPromptEvidenceIsBoundToAnotherRoute_Blocks()
    {
        using var fixture = RouteStateFixture.Create();
        const string gdd = "# GDD\n\n- Stable requirement.";
        var gddHash = RouteStateFixture.Hash(gdd);
        fixture.WriteText("docs/gdd/GDD.md", gdd);
        fixture.WritePromptEvidence(
            "meta/routes/gdd-document/cross-route-prompt-evidence.json",
            "Use only the frozen GDD.",
            new Dictionary<string, string> { ["docs/gdd/GDD.md"] = gddHash },
            ["assistant summary as acceptance authority"]);
        fixture.WriteJson("meta/routes/gdd-requirements/latest.json", JsonSerializer.Serialize(new
        {
            schema_version = "gdd-requirements.v1",
            route = "gdd-requirements",
            status_dimension = RouteStatusVocabulary.RouteReadback,
            status_allowed_values = RouteStatusVocabulary.Values(RouteStatusVocabulary.RouteReadback),
            status = "ready",
            source_boundary_enforced = true,
            source_boundary = new
            {
                recovery_source_order_ref = HostedRouteRecoveryContract.ContractId,
                recovery_source_order = HostedRouteRecoveryContract.SourceOrder,
                authority_sources = new[] { "docs/gdd/GDD.md" },
                source_hashes = new Dictionary<string, string> { ["docs/gdd/GDD.md"] = gddHash },
                forbidden_source_patterns = new[] { "assistant summary as acceptance authority" },
                prompt_evidence_refs = new[] { "meta/routes/gdd-document/cross-route-prompt-evidence.json" }
            },
            requirements = Array.Empty<object>()
        }));

        fixture.Read().BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/gdd-requirements/latest.json:prompt_evidence_invalid");
    }

    [Fact]
    public void Read_WhenPromptEvidenceRepeatsAHashThatDoesNotMatchAuthority_Blocks()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteText("docs/gdd/GDD.md", "# Actual GDD");
        fixture.WritePromptEvidence(
            "meta/routes/gdd-requirements/prompt-evidence.json",
            "Use only the frozen GDD.",
            new Dictionary<string, string> { ["docs/gdd/GDD.md"] = "self-declared-but-wrong" },
            ["assistant summary as acceptance authority"]);
        fixture.WriteJson("meta/routes/gdd-requirements/latest.json", """
        {
          "route": "gdd-requirements",
          "status": "ready",
          "source_boundary_enforced": true,
          "source_boundary": {
            "recovery_source_order_ref": "hosted-route-recovery-order.v1",
            "recovery_source_order": ["parsed game-type route profile", "selected route skill prompt block", "meta/project-execution-guide.md", "routes/prototype-contract/latest.json", "current route latest state", "current goal/step/session state when applicable", "repair ledger and failing acceptance/Godot diagnostic evidence when applicable", "latest live platform acceptance blocker"],
            "authority_sources": ["docs/gdd/GDD.md"],
            "source_hashes": { "docs/gdd/GDD.md": "self-declared-but-wrong" },
            "forbidden_source_patterns": ["assistant summary as acceptance authority"],
            "prompt_evidence_refs": ["meta/routes/gdd-requirements/prompt-evidence.json"]
          }
        }
        """);

        var readback = fixture.Read();

        readback.BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/gdd-requirements/latest.json:source_hashes_authority_mismatch" &&
            issue.Severity == "P0");
    }

    [Fact]
    public void Read_WhenAuthoritySourceHasNoMatchingSourceHash_Blocks()
    {
        using var fixture = RouteStateFixture.Create();
        const string gdd = "# GDD";
        var gddHash = RouteStateFixture.Hash(gdd);
        fixture.WriteText("docs/gdd/GDD.md", gdd);
        fixture.WritePromptEvidence(
            "meta/routes/gdd-requirements/prompt-evidence.json",
            "Use frozen GDD authority only.",
            new Dictionary<string, string> { ["docs/gdd/GDD.md"] = gddHash },
            ["assistant summary as acceptance authority"]);
        fixture.WriteJson("meta/routes/gdd-requirements/latest.json", JsonSerializer.Serialize(new
        {
            schema_version = "gdd-requirements.v1",
            route = "gdd-requirements",
            status_dimension = RouteStatusVocabulary.RouteReadback,
            status_allowed_values = RouteStatusVocabulary.Values(RouteStatusVocabulary.RouteReadback),
            status = "ready",
            source_boundary_enforced = true,
            source_boundary = new
            {
                recovery_source_order_ref = HostedRouteRecoveryContract.ContractId,
                recovery_source_order = HostedRouteRecoveryContract.SourceOrder,
                authority_sources = new[] { "docs/gdd/GDD.md", "meta/routes/scene-route/latest.json" },
                source_hashes = new Dictionary<string, string> { ["docs/gdd/GDD.md"] = gddHash },
                forbidden_source_patterns = new[] { "assistant summary as acceptance authority" },
                prompt_evidence_refs = new[] { "meta/routes/gdd-requirements/prompt-evidence.json" }
            }
        }));

        fixture.Read().BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/gdd-requirements/latest.json:source_hashes_missing" && issue.Severity == "P0");

        fixture.WriteJson("meta/routes/gdd-requirements/latest.json", JsonSerializer.Serialize(new
        {
            schema_version = "gdd-requirements.v1",
            route = "gdd-requirements",
            status_dimension = RouteStatusVocabulary.RouteReadback,
            status_allowed_values = RouteStatusVocabulary.Values(RouteStatusVocabulary.RouteReadback),
            status = "ready",
            source_boundary_enforced = true,
            source_boundary = new
            {
                recovery_source_order_ref = HostedRouteRecoveryContract.ContractId,
                recovery_source_order = HostedRouteRecoveryContract.SourceOrder,
                authority_sources = new[] { "docs/gdd/GDD.md", "opaque-runtime-memory" },
                source_hashes = new Dictionary<string, string> { ["docs/gdd/GDD.md"] = gddHash },
                forbidden_source_patterns = new[] { "assistant summary as acceptance authority" },
                prompt_evidence_refs = new[] { "meta/routes/gdd-requirements/prompt-evidence.json" }
            }
        }));
        fixture.Read().BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/gdd-requirements/latest.json:source_hashes_missing" && issue.Severity == "P0");
    }

    [Fact]
    public void Read_WhenRouteProfileAndSelectedPromptBlockAreIndependentAuthorities_OmissionFailsClosed()
    {
        using var fixture = RouteStateFixture.Create();
        var sourceHashes = new Dictionary<string, string>
        {
            [HostedRouteRecoveryContract.ParsedRouteProfileHashKey] = HostedRouteForbiddenSourceGuard.PromptHash(
                JsonSerializer.Serialize(PrototypeRouteSkillPolicy.ResolveProfile(fixture.Project))),
            [HostedRouteRecoveryContract.SelectedRouteSkillPromptBlockHashKey] = HostedRouteForbiddenSourceGuard.PromptHash(
                PrototypeRouteSkillPolicy.BuildPromptBlock(fixture.Project))
        };
        fixture.WritePromptEvidence(
            "meta/routes/gdd-requirements/prompt-evidence.json",
            "Use the independently bound route profile and selected route skill prompt block.",
            sourceHashes,
            ["assistant summary as acceptance authority"]);

        object Boundary(IReadOnlyDictionary<string, string> hashes) => new
        {
            recovery_source_order_ref = HostedRouteRecoveryContract.ContractId,
            recovery_source_order = HostedRouteRecoveryContract.SourceOrder,
            authority_sources = new[]
            {
                HostedRouteRecoveryContract.ParsedRouteProfileSource,
                HostedRouteRecoveryContract.SelectedRouteSkillPromptBlockSource
            },
            source_hashes = hashes,
            forbidden_source_patterns = new[] { "assistant summary as acceptance authority" },
            prompt_evidence_refs = new[] { "meta/routes/gdd-requirements/prompt-evidence.json" }
        };

        fixture.WriteJson("meta/routes/gdd-requirements/latest.json", JsonSerializer.Serialize(new
        {
            schema_version = "gdd-requirements.v1",
            route = "gdd-requirements",
            status = "ready",
            source_boundary_enforced = true,
            source_boundary = Boundary(sourceHashes),
            requirements = Array.Empty<object>()
        }));

        fixture.Read().BlockingIssues.Should().NotContain(issue =>
            issue.IssueId.Contains("source_hashes", StringComparison.Ordinal) ||
            issue.IssueId.Contains("recovery_source_order", StringComparison.Ordinal) ||
            issue.IssueId.Contains("prompt_evidence", StringComparison.Ordinal));

        var missingPromptBlockHash = new Dictionary<string, string>(sourceHashes);
        missingPromptBlockHash.Remove(HostedRouteRecoveryContract.SelectedRouteSkillPromptBlockHashKey);
        fixture.WriteJson("meta/routes/gdd-requirements/latest.json", JsonSerializer.Serialize(new
        {
            schema_version = "gdd-requirements.v1",
            route = "gdd-requirements",
            status = "ready",
            source_boundary_enforced = true,
            source_boundary = Boundary(missingPromptBlockHash),
            requirements = Array.Empty<object>()
        }));

        fixture.Read().BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/gdd-requirements/latest.json:source_hashes_missing" &&
            issue.Severity == "P0");
    }

    [Theory]
    [InlineData(HostedRouteRecoveryContract.ParsedRouteProfileSource)]
    [InlineData(HostedRouteRecoveryContract.SelectedRouteSkillPromptBlockSource)]
    public void Read_WhenPromptRouteSelfConsistentlyOmitsRequiredRecoveryAuthority_Blocks(string omittedSource)
    {
        using var fixture = RouteStateFixture.Create();
        var authorities = new Dictionary<string, string>(StringComparer.Ordinal)
        {
            [HostedRouteRecoveryContract.ParsedRouteProfileSource] = HostedRouteForbiddenSourceGuard.PromptHash(
                JsonSerializer.Serialize(PrototypeRouteSkillPolicy.ResolveProfile(fixture.Project))),
            [HostedRouteRecoveryContract.SelectedRouteSkillPromptBlockSource] = HostedRouteForbiddenSourceGuard.PromptHash(
                PrototypeRouteSkillPolicy.BuildPromptBlock(fixture.Project))
        };
        authorities.Remove(omittedSource);
        var sourceHashes = authorities.ToDictionary(
            pair => pair.Key == HostedRouteRecoveryContract.ParsedRouteProfileSource
                ? HostedRouteRecoveryContract.ParsedRouteProfileHashKey
                : HostedRouteRecoveryContract.SelectedRouteSkillPromptBlockHashKey,
            pair => pair.Value,
            StringComparer.Ordinal);
        fixture.WritePromptEvidence(
            "meta/routes/gdd-requirements/prompt-evidence.json",
            "Use the declared route authorities.",
            sourceHashes,
            ["assistant summary as acceptance authority"]);
        fixture.WriteJson("meta/routes/gdd-requirements/latest.json", JsonSerializer.Serialize(new
        {
            schema_version = "gdd-requirements.v1",
            route = "gdd-requirements",
            status = "ready",
            source_boundary_enforced = true,
            source_boundary = new
            {
                recovery_source_order_ref = HostedRouteRecoveryContract.ContractId,
                recovery_source_order = HostedRouteRecoveryContract.SourceOrder,
                authority_sources = authorities.Keys.ToArray(),
                source_hashes = sourceHashes,
                forbidden_source_patterns = new[] { "assistant summary as acceptance authority" },
                prompt_evidence_refs = new[] { "meta/routes/gdd-requirements/prompt-evidence.json" }
            },
            requirements = Array.Empty<object>()
        }));

        fixture.Read().BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/gdd-requirements/latest.json:prompt_recovery_authorities_missing" &&
            issue.Severity == "P0");
    }

    [Fact]
    public void Read_WhenSceneSemanticContentChangesButDeclaredHashesStayOld_Blocks()
    {
        using var fixture = RouteStateFixture.Create();
        const string sceneTemplate = """
        {
          "schema_version": "scene-route.v1",
          "route": "scene-route-confirmation",
          "status_dimension": "scene_route_confirmation",
          "status": "confirmed",
          "scene_count_intent": "multi",
          "entry_scene": "field_map",
          "scenes": [{"scene_id":"field_map","scene_name":"Field","role":"hub","m1_required":true,"player_goal":"Move"}],
          "transitions": [],
          "single_scene_confirmation": {"allowed":false,"reason":"multi"},
          "notes": []
        }
        """;
        fixture.WriteJson("meta/routes/scene-route/latest.json", sceneTemplate);
        using var sceneDocument = JsonDocument.Parse(sceneTemplate);
        var sceneHash = GddToModuleAuthorityHashes.ComputeSceneRouteHash(sceneDocument.RootElement);
        var contractHash = GddToModuleAuthorityHashes.ComputeContractSnapshotHash(fixture.Project.GameTypeMatchJson);
        var sourceHashes = new Dictionary<string, string>
        {
            ["meta/routes/scene-route/latest.json"] = sceneHash,
            ["project-contract-snapshot"] = contractHash
        };
        fixture.WritePromptEvidence(
            "meta/routes/gdd-requirements/prompt-evidence.json",
            "Use frozen scene and contract.",
            sourceHashes,
            ["assistant summary as acceptance authority"]);
        fixture.WriteJson("meta/routes/gdd-requirements/latest.json", JsonSerializer.Serialize(new
        {
            schema_version = "gdd-requirements.v1",
            route = "gdd-requirements",
            status_dimension = "route_readback",
            status_allowed_values = new[] { "ready", "needs_review", "blocked", "stale", "unknown" },
            status = "ready",
            source_boundary_enforced = true,
            source_boundary = new
            {
                recovery_source_order_ref = HostedRouteRecoveryContract.ContractId,
                recovery_source_order = HostedRouteRecoveryContract.SourceOrder,
                authority_sources = new[] { "meta/routes/scene-route/latest.json", "project-contract-snapshot" },
                source_hashes = sourceHashes,
                forbidden_source_patterns = new[] { "assistant summary as acceptance authority" },
                prompt_evidence_refs = new[] { "meta/routes/gdd-requirements/prompt-evidence.json" }
            }
        }));
        fixture.WriteJson("meta/routes/scene-route/latest.json", sceneTemplate.Replace("\"scene_name\":\"Field\"", "\"scene_name\":\"Tampered\"", StringComparison.Ordinal));

        fixture.Read().BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/gdd-requirements/latest.json:source_hashes_authority_mismatch" &&
            issue.Severity == "P0");
    }

    [Fact]
    public void Read_WhenPromptEvidencePathIsAFileSymlinkOutsideProject_Blocks()
    {
        using var fixture = RouteStateFixture.Create();
        const string gdd = "# GDD";
        var gddHash = RouteStateFixture.Hash(gdd);
        fixture.WriteText("docs/gdd/GDD.md", gdd);
        var outside = Path.Combine(Path.GetTempPath(), "phasea-prompt-evidence-outside-" + Guid.NewGuid().ToString("N") + ".json");
        File.WriteAllText(outside, System.Text.Json.JsonSerializer.Serialize(new
        {
            recovery_source_order_ref = HostedRouteRecoveryContract.ContractId,
            recovery_source_order = HostedRouteRecoveryContract.SourceOrder,
            source_hashes = new Dictionary<string, string> { ["docs/gdd/GDD.md"] = gddHash }
        }));
        try
        {
            var link = Path.Combine(fixture.Project.RepoPath, "meta", "routes", "gdd-requirements", "prompt-evidence.json");
            Directory.CreateDirectory(Path.GetDirectoryName(link)!);
            File.CreateSymbolicLink(link, outside);
            fixture.WriteJson("meta/routes/gdd-requirements/latest.json", $$"""
            {
              "route": "gdd-requirements",
              "status": "ready",
              "source_boundary_enforced": true,
              "source_boundary": {
                "recovery_source_order_ref": "hosted-route-recovery-order.v1",
                "recovery_source_order": {{System.Text.Json.JsonSerializer.Serialize(HostedRouteRecoveryContract.SourceOrder)}},
                "authority_sources": ["docs/gdd/GDD.md"],
                "source_hashes": { "docs/gdd/GDD.md": "{{gddHash}}" },
                "forbidden_source_patterns": ["raw guide"],
                "prompt_evidence_refs": ["meta/routes/gdd-requirements/prompt-evidence.json"]
              }
            }
            """);

            var readback = fixture.Read();

            readback.BlockingIssues.Should().Contain(issue =>
                issue.IssueId == "meta/routes/gdd-requirements/latest.json:prompt_evidence_missing" &&
                issue.Severity == "P0");
        }
        finally
        {
            File.Delete(outside);
        }
    }

    [Fact]
    public void Read_WhenProjectRepoRootIsDirectorySymlink_FailsClosed()
    {
        using var fixture = RouteStateFixture.CreateWithRepoSymlink();
        fixture.WriteJson("meta/routes/gdd-requirements/latest.json", """
        {
          "schema_version": "gdd-requirements.v1",
          "route": "gdd-requirements",
          "status_dimension": "route_readback",
          "status_allowed_values": ["ready", "needs_review", "blocked", "stale", "unknown"],
          "status": "ready",
          "source_boundary_enforced": true
        }
        """);

        var readback = fixture.Read();

        readback.Artifacts.Single(artifact => artifact.Route == "gdd-requirements").Status.Should().Be("missing");
    }

    [Fact]
    public void Read_WhenPromptEvidenceDoesNotProveRecoveryOrderAndHashes_Blocks()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteText("meta/routes/gdd-requirements/prompt-evidence.json", "{ \"purpose\": \"gdd-requirements\" }");
        fixture.WriteJson("meta/routes/gdd-requirements/latest.json", """
        {
          "route": "gdd-requirements",
          "status": "ready",
          "source_boundary_enforced": true,
          "source_boundary": {
            "recovery_source_order_ref": "hosted-route-recovery-order.v1",
            "recovery_source_order": ["parsed game-type route profile", "selected route skill prompt block", "meta/project-execution-guide.md", "routes/prototype-contract/latest.json", "current route latest state", "current goal/step/session state when applicable", "repair ledger and failing acceptance/Godot diagnostic evidence when applicable", "latest live platform acceptance blocker"],
            "authority_sources": ["docs/gdd/GDD.md"],
            "source_hashes": { "docs/gdd/GDD.md": "gdd-hash" },
            "forbidden_source_patterns": ["raw guide"],
            "prompt_evidence_refs": ["meta/routes/gdd-requirements/prompt-evidence.json"]
          }
        }
        """);

        var readback = fixture.Read();

        readback.BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/gdd-requirements/latest.json:prompt_evidence_invalid" &&
            issue.Severity == "P0");
    }

    [Fact]
    public void Read_WhenNonPromptRouteDisablesBoundaryWithoutReason_Blocks()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/ui-wiring/latest.json", """
        {
          "schema_version": "ui-wiring-closure.v1",
          "status": "ready",
          "source_boundary_enforced": false,
          "ui_surface_matrix": []
        }
        """);

        var readback = fixture.Read();

        readback.BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/ui-wiring/latest.json:source_boundary_not_applicable_invalid");
    }

    [Theory]
    [InlineData("")]
    [InlineData(", \"source_boundary_enforced\": null")]
    [InlineData(", \"source_boundary_enforced\": \"true\"")]
    public void Read_WhenPromptRouteBoundaryFlagIsMissingNullOrWrongType_Blocks(string boundaryFlag)
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/gdd-requirements/latest.json", $$"""
        {
          "route": "gdd-requirements",
          "status": "ready"{{boundaryFlag}}
        }
        """);

        var readback = fixture.Read();

        readback.BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/gdd-requirements/latest.json:source_boundary_enforced_invalid" &&
            issue.Severity == "P0");
    }

    [Fact]
    public void Read_WhenPromptRouteDeclaresNotApplicableBoundary_Blocks()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/gdd-requirements/latest.json", """
        {
          "route": "gdd-requirements",
          "status": "ready",
          "source_boundary_enforced": false,
          "source_boundary_not_applicable": {
            "reason": "readback_only",
            "checked_utc": "2026-07-12T00:00:00Z",
            "decision_by": "system",
            "evidence_refs": []
          }
        }
        """);

        var readback = fixture.Read();

        readback.BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/gdd-requirements/latest.json:source_boundary_enforcement_required" &&
            issue.Severity == "P0");
    }

    [Fact]
    public void Read_WhenPrototypeSkeletonPromptRouteDeclaresNotApplicableBoundary_Blocks()
    {
        using var fixture = RouteStateFixture.Create();
        const string relativePath = "meta/routes/prototype-skeleton/latest.json";
        const string route = "prototype-skeleton";
        fixture.WriteJson(relativePath, JsonSerializer.Serialize(new
        {
            route,
            status = "ready",
            source_boundary_enforced = false,
            source_boundary_not_applicable = new
            {
                reason = "readback_only",
                checked_utc = "2026-07-12T00:00:00Z",
                decision_by = "system",
                evidence_refs = Array.Empty<object>()
            }
        }));

        fixture.Read().BlockingIssues.Should().Contain(issue =>
            issue.IssueId == $"{relativePath}:source_boundary_enforcement_required" && issue.Severity == "P0");
    }

    [Fact]
    public void Read_WhenNonPromptRouteHasStructuredNotApplicableBoundary_AllowsExemption()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteText("meta/routes/ui-wiring/exemption-evidence.json", "{}");
        fixture.WriteJson("meta/routes/ui-wiring/latest.json", """
        {
          "schema_version": "ui-wiring-closure.v1",
          "status": "ready",
          "source_boundary_enforced": false,
          "source_boundary_not_applicable": {
            "reason": "static_browser_projection",
            "checked_utc": "2026-07-12T00:00:00Z",
            "decision_by": "system",
            "evidence_refs": [{ "kind": "sidecar", "path": "meta/routes/ui-wiring/exemption-evidence.json" }]
          },
          "ui_surface_matrix": []
        }
        """);

        var readback = fixture.Read();

        readback.BlockingIssues.Should().NotContain(issue =>
            issue.IssueId.Contains("source_boundary", StringComparison.Ordinal));
    }

    [Fact]
    public void Read_WhenNonPromptRouteNotApplicableEvidenceIsEmpty_Blocks()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/ui-wiring/latest.json", """
        {
          "schema_version": "ui-wiring-closure.v1",
          "status_dimension": "route_readback",
          "status_allowed_values": ["ready", "blocked"],
          "status": "ready",
          "source_boundary_enforced": false,
          "source_boundary_not_applicable": {
            "reason": "static_browser_projection",
            "checked_utc": "2026-07-12T00:00:00Z",
            "decision_by": "system",
            "evidence_refs": []
          }
        }
        """);

        fixture.Read().BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/ui-wiring/latest.json:source_boundary_not_applicable_invalid" && issue.Severity == "P0");
    }

    [Fact]
    public void Read_WhenEvidenceRefHasNoSafeLocator_Blocks()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteText("meta/routes/ui-wiring/exemption-evidence.json", "{}");
        fixture.WriteJson("meta/routes/ui-wiring/latest.json", """
        {
          "schema_version": "ui-wiring-closure.v1",
          "status_dimension": "route_readback",
          "status_allowed_values": ["ready", "blocked"],
          "status": "ready",
          "source_boundary_enforced": false,
          "source_boundary_not_applicable": {
            "reason": "static_browser_projection",
            "checked_utc": "2026-07-12T00:00:00Z",
            "decision_by": "system",
            "evidence_refs": [{ "kind": "sidecar", "path": "meta/routes/ui-wiring/exemption-evidence.json" }]
          },
          "evidence_refs": [{ "kind": "sidecar" }]
        }
        """);

        fixture.Read().BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/ui-wiring/latest.json:evidence_ref_locator_invalid" && issue.Severity == "P2");
    }

    [Fact]
    public void Read_WhenEvidenceRefsContainsScalar_BlocksWithoutThrowing()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteText("meta/routes/ui-wiring/exemption-evidence.json", "{}");
        fixture.WriteJson("meta/routes/ui-wiring/latest.json", """
        {
          "schema_version": "ui-wiring-closure.v1",
          "status_dimension": "route_readback",
          "status_allowed_values": ["ready", "blocked"],
          "status": "ready",
          "source_boundary_enforced": false,
          "source_boundary_not_applicable": {
            "reason": "static_browser_projection",
            "checked_utc": "2026-07-12T00:00:00Z",
            "decision_by": "system",
            "evidence_refs": [{ "kind": "sidecar", "path": "meta/routes/ui-wiring/exemption-evidence.json" }]
          },
          "evidence_refs": ["not-an-object"]
        }
        """);

        fixture.Read().BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/ui-wiring/latest.json:evidence_ref_invalid");
    }

    [Fact]
    public void Read_WhenStatusIsOutsideDimension_FreshnessIsUnknown()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/ui-wiring/latest.json", """
        {
          "schema_version": "ui-wiring-closure.v1",
          "status_dimension": "route_readback",
          "status_allowed_values": ["ready", "blocked"],
          "status": "surprising",
          "source_boundary_enforced": false,
          "source_boundary_not_applicable": {
            "reason": "static_browser_projection",
            "checked_utc": "2026-07-12T00:00:00Z",
            "decision_by": "system",
            "evidence_refs": []
          }
        }
        """);

        fixture.Read().Artifacts.Single(artifact => artifact.Route == "ui-wiring").Freshness.Should().Be("unknown");
    }

    [Theory]
    [InlineData("{\"scene_count_intent\":1,\"entry_scene\":\"field\",\"scenes\":[],\"transitions\":[],\"single_scene_confirmation\":{}}")]
    [InlineData("{\"scene_count_intent\":\"single\",\"entry_scene\":\"field\",\"scenes\":{},\"transitions\":[],\"single_scene_confirmation\":{}}")]
    [InlineData("{\"scene_count_intent\":\"single\",\"entry_scene\":\"field\",\"scenes\":[],\"transitions\":[],\"single_scene_confirmation\":[],\"notes\":[1]}")]
    public void ComputeSceneRouteHash_WhenAuthorityShapeIsMalformed_ReturnsEmpty(string json)
    {
        using var document = JsonDocument.Parse(json);

        GddToModuleAuthorityHashes.ComputeSceneRouteHash(document.RootElement).Should().BeEmpty();
    }

    [Fact]
    public void Read_WhenEvidenceRefUsesOwnedArtifactId_AllowsLocator()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.AddArtifactId("artifact-owned");
        fixture.WriteText("meta/routes/ui-wiring/exemption-evidence.json", "{}");
        fixture.WriteJson("meta/routes/ui-wiring/latest.json", """
        {
          "schema_version": "ui-wiring-closure.v1",
          "status_dimension": "route_readback",
          "status_allowed_values": ["ready", "blocked"],
          "status": "ready",
          "source_boundary_enforced": false,
          "source_boundary_not_applicable": {
            "reason": "static_browser_projection",
            "checked_utc": "2026-07-12T00:00:00Z",
            "decision_by": "system",
            "evidence_refs": [{ "kind": "sidecar", "path": "meta/routes/ui-wiring/exemption-evidence.json" }]
          },
          "evidence_refs": [{ "kind": "artifact", "artifact_id": "artifact-owned" }]
        }
        """);

        fixture.Read().BlockingIssues.Should().NotContain(issue =>
            issue.IssueId == "meta/routes/ui-wiring/latest.json:evidence_ref_locator_invalid");
    }

    [Fact]
    public void Read_WhenEvidenceRefUsesUnknownArtifactId_BlocksLocator()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteText("meta/routes/ui-wiring/exemption-evidence.json", "{}");
        fixture.WriteJson("meta/routes/ui-wiring/latest.json", """
        {
          "schema_version": "ui-wiring-closure.v1",
          "status_dimension": "route_readback",
          "status_allowed_values": ["ready", "blocked"],
          "status": "ready",
          "source_boundary_enforced": false,
          "source_boundary_not_applicable": {
            "reason": "static_browser_projection",
            "checked_utc": "2026-07-12T00:00:00Z",
            "decision_by": "system",
            "evidence_refs": [{ "kind": "sidecar", "path": "meta/routes/ui-wiring/exemption-evidence.json" }]
          },
          "evidence_refs": [{ "kind": "artifact", "artifact_id": "artifact-other-project" }]
        }
        """);

        fixture.Read().BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/ui-wiring/latest.json:evidence_ref_locator_invalid" && issue.Severity == "P2");
    }

    [Fact]
    public void Read_WhenPromptEvidenceRefIsDirectory_BlocksWithoutSamplingFiles()
    {
        using var fixture = RouteStateFixture.Create();
        const string gdd = "# GDD";
        var gddHash = RouteStateFixture.Hash(gdd);
        fixture.WriteText("docs/gdd/GDD.md", gdd);
        for (var index = 0; index < 25; index++)
        {
            fixture.WriteJson($"meta/routes/gdd-requirements/prompt-evidence/{index:D2}.json", "{}");
        }
        fixture.WriteJson("meta/routes/gdd-requirements/latest.json", JsonSerializer.Serialize(new
        {
            schema_version = "gdd-requirements.v1",
            route = "gdd-requirements",
            status_dimension = RouteStatusVocabulary.RouteReadback,
            status_allowed_values = RouteStatusVocabulary.Values(RouteStatusVocabulary.RouteReadback),
            status = "ready",
            source_boundary_enforced = true,
            source_boundary = new
            {
                recovery_source_order_ref = HostedRouteRecoveryContract.ContractId,
                recovery_source_order = HostedRouteRecoveryContract.SourceOrder,
                authority_sources = new[] { "docs/gdd/GDD.md" },
                source_hashes = new Dictionary<string, string> { ["docs/gdd/GDD.md"] = gddHash },
                forbidden_source_patterns = new[] { "assistant summary as acceptance authority" },
                prompt_evidence_refs = new[] { "meta/routes/gdd-requirements/prompt-evidence" }
            }
        }));

        fixture.Read().BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/gdd-requirements/latest.json:prompt_evidence_directory_forbidden" && issue.Severity == "P0");
    }

    [Fact]
    public void Read_WhenStatusIsOutsideDeclaredSubset_Blocks()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/gdd-document/latest.json", """
        {
          "schema_version": "gdd-document-generation.v1",
          "status_dimension": "route_readback",
          "status_allowed_values": ["ready", "blocked"],
          "status": "surprising"
        }
        """);

        var readback = fixture.Read();

        readback.BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/gdd-document/latest.json:status_outside_declared_subset");
    }

    [Fact]
    public void Read_WhenVersionedSidecarOmitsStatusDimension_Blocks()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/ui-wiring/latest.json", """
        {
          "schema_version": "ui-wiring-closure.v1",
          "status": "ready",
          "source_boundary_enforced": false,
          "source_boundary_not_applicable": {
            "reason": "static_browser_projection",
            "checked_utc": "2026-07-12T00:00:00Z",
            "decision_by": "system",
            "evidence_refs": []
          }
        }
        """);

        fixture.Read().BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/ui-wiring/latest.json:status_dimension_missing");
    }

    [Fact]
    public void Read_WhenSidecarOmitsBothSchemaVersionAndStatusDimension_BlocksBothMissingFields()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/gdd-document/latest.json", """
        {
          "status_allowed_values": ["ready", "blocked"],
          "status": "ready",
          "source_boundary_enforced": false,
          "source_boundary_not_applicable": {
            "reason": "legacy_static_projection",
            "checked_utc": "2026-07-12T00:00:00Z",
            "decision_by": "system",
            "evidence_refs": []
          }
        }
        """);

        var issues = fixture.Read().BlockingIssues;

        issues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/gdd-document/latest.json:schema_version_missing");
        issues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/gdd-document/latest.json:status_dimension_missing");
    }

    [Fact]
    public void Read_WhenForbiddenSourceScanReportsViolation_BlocksPromptEvidence()
    {
        using var fixture = RouteStateFixture.Create();
        const string gdd = "# GDD";
        var gddHash = RouteStateFixture.Hash(gdd);
        fixture.WriteText("docs/gdd/GDD.md", gdd);
        var scan = HostedRouteForbiddenSourceGuard.Scan(
            "Read docs/game-type-guides/rpg.md",
            ["docs/game-type-guides/** raw excerpts"]);
        fixture.WriteJson("meta/routes/gdd-requirements/prompt-evidence.json", JsonSerializer.Serialize(new
        {
            recovery_source_order_ref = HostedRouteRecoveryContract.ContractId,
            recovery_source_order = HostedRouteRecoveryContract.SourceOrder,
            source_hashes = new Dictionary<string, string> { ["docs/gdd/GDD.md"] = gddHash },
            forbidden_source_scan = scan
        }));
        fixture.WriteJson("meta/routes/gdd-requirements/latest.json", JsonSerializer.Serialize(new
        {
            schema_version = "gdd-requirements.v1",
            route = "gdd-requirements",
            status_dimension = RouteStatusVocabulary.RouteReadback,
            status_allowed_values = new[] { "ready", "needs_review", "blocked", "stale", "unknown" },
            status = "blocked",
            source_boundary_enforced = true,
            source_boundary = new
            {
                recovery_source_order_ref = HostedRouteRecoveryContract.ContractId,
                recovery_source_order = HostedRouteRecoveryContract.SourceOrder,
                authority_sources = new[] { "docs/gdd/GDD.md" },
                source_hashes = new Dictionary<string, string> { ["docs/gdd/GDD.md"] = gddHash },
                forbidden_source_patterns = new[] { "docs/game-type-guides/** raw excerpts" },
                prompt_evidence_refs = new[] { "meta/routes/gdd-requirements/prompt-evidence.json" }
            }
        }));

        fixture.Read().BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/gdd-requirements/latest.json:prompt_evidence_invalid" &&
            issue.Severity == "P0");
    }

    [Fact]
    public void Read_WhenPromptEvidenceDeclaresRawPromptPersistence_Blocks()
    {
        using var fixture = RouteStateFixture.Create();
        const string gdd = "# GDD";
        var hash = RouteStateFixture.Hash(gdd);
        fixture.WriteText("docs/gdd/GDD.md", gdd);
        fixture.WriteJson("meta/routes/gdd-requirements/prompt-evidence.json", System.Text.Json.JsonSerializer.Serialize(new
        {
            recovery_source_order_ref = HostedRouteRecoveryContract.ContractId,
            recovery_source_order = HostedRouteRecoveryContract.SourceOrder,
            source_hashes = new Dictionary<string, string> { ["docs/gdd/GDD.md"] = hash },
            raw_prompt_persisted = true
        }));
        fixture.WriteJson("meta/routes/gdd-requirements/latest.json", System.Text.Json.JsonSerializer.Serialize(new
        {
            route = "gdd-requirements",
            status = "ready",
            source_boundary_enforced = true,
            source_boundary = new
            {
                recovery_source_order_ref = HostedRouteRecoveryContract.ContractId,
                recovery_source_order = HostedRouteRecoveryContract.SourceOrder,
                authority_sources = new[] { "docs/gdd/GDD.md" },
                source_hashes = new Dictionary<string, string> { ["docs/gdd/GDD.md"] = hash },
                forbidden_source_patterns = new[] { "raw guide" },
                prompt_evidence_refs = new[] { "meta/routes/gdd-requirements/prompt-evidence.json" }
            }
        }));

        fixture.Read().BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/gdd-requirements/latest.json:raw_prompt_persisted_forbidden");
    }

    [Fact]
    public void Read_WhenSidecarUsesStatusFromWrongDimension_Blocks()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/gdd-document/latest.json", """
        {
          "schema_version": "gdd-document-generation.v1",
          "status_dimension": "route_readback",
          "status_allowed_values": ["ready", "completed"],
          "status": "completed"
        }
        """);

        var readback = fixture.Read();

        readback.BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/gdd-document/latest.json:status_allowed_values_outside_dimension");
        readback.BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/gdd-document/latest.json:status_outside_dimension");
    }

    [Fact]
    public void Read_WhenCanonicalArtifactClaimsWrongRegisteredContract_BlocksExactRegistryMismatch()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/gdd-document/latest.json", """
        {
          "schema_version": "prototype-contract.v2",
          "route": "prototype-contract",
          "status_dimension": "readiness_label",
          "status_allowed_values": ["ready", "blocked", "stale", "unknown"],
          "status": "ready",
          "source_boundary_enforced": false,
          "source_boundary_not_applicable": {
            "reason": "static_browser_projection",
            "checked_utc": "2026-07-12T00:00:00Z",
            "decision_by": "system",
            "evidence_refs": []
          }
        }
        """);

        var issues = fixture.Read().BlockingIssues;
        issues.Should().Contain(issue => issue.IssueId.EndsWith(":schema_version_unexpected", StringComparison.Ordinal));
        issues.Should().Contain(issue => issue.IssueId.EndsWith(":route_unexpected", StringComparison.Ordinal));
        issues.Should().Contain(issue => issue.IssueId.EndsWith(":status_dimension_unexpected", StringComparison.Ordinal));
        issues.Should().Contain(issue => issue.IssueId.EndsWith(":status_allowed_values_unexpected", StringComparison.Ordinal));
    }

    [Fact]
    public void Read_WhenPersistedPromptChangesAfterScan_BlocksPromptEvidenceHashBinding()
    {
        using var fixture = RouteStateFixture.Create();
        const string gdd = "# GDD";
        var gddHash = RouteStateFixture.Hash(gdd);
        fixture.WriteText("docs/gdd/GDD.md", gdd);
        fixture.WritePromptEvidence(
            "meta/routes/gdd-requirements/prompt-evidence.json",
            "Use only the frozen GDD.",
            new Dictionary<string, string> { ["docs/gdd/GDD.md"] = gddHash },
            ["assistant summary as acceptance authority"]);
        fixture.WriteText("meta/routes/gdd-requirements/prompt-evidence.prompt.txt", "Tampered after scan.");
        fixture.WriteJson("meta/routes/gdd-requirements/latest.json", JsonSerializer.Serialize(new
        {
            schema_version = "gdd-requirements.v1",
            route = "gdd-requirements",
            status_dimension = RouteStatusVocabulary.RouteReadback,
            status_allowed_values = new[] { "ready", "needs_review", "blocked", "stale", "unknown" },
            status = "ready",
            source_boundary_enforced = true,
            source_boundary = new
            {
                recovery_source_order_ref = HostedRouteRecoveryContract.ContractId,
                recovery_source_order = HostedRouteRecoveryContract.SourceOrder,
                authority_sources = new[] { "docs/gdd/GDD.md" },
                source_hashes = new Dictionary<string, string> { ["docs/gdd/GDD.md"] = gddHash },
                forbidden_source_patterns = new[] { "assistant summary as acceptance authority" },
                prompt_evidence_refs = new[] { "meta/routes/gdd-requirements/prompt-evidence.json" }
            }
        }));

        fixture.Read().BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/gdd-requirements/latest.json:prompt_evidence_invalid" &&
            issue.Severity == "P0");
    }

    [Fact]
    public void Read_WhenAllowedGuideReferenceIsTamperedInBothBoundaryAndEvidence_Blocks()
    {
        using var fixture = RouteStateFixture.Create();
        const string guide = "# RPG Guide\n\nThis stable RPG guide paragraph defines the field, encounter, reward, and return loop used by the approved authority.";
        fixture.WriteText("docs/game-type-guides/game-types.csv", "id,name,description,genre_tags,fragment_file\nrpg,RPG,Role-playing,rpg,rpg.md\n");
        fixture.WriteText("docs/game-type-guides/rpg.md", guide);
        var guideHash = HostedRouteForbiddenSourceGuard.ContentHash(guide);
        var sourceHashes = new Dictionary<string, string> { ["game-type-guide:rpg"] = guideHash };
        var tamperedReference = "docs/game-type-guides/other.md";
        fixture.WritePromptEvidence(
            "meta/routes/gdd-requirements/prompt-evidence.json",
            "Use the approved guide authority.",
            sourceHashes,
            ["assistant summary as acceptance authority"],
            [tamperedReference]);
        fixture.WriteJson("meta/routes/gdd-requirements/latest.json", JsonSerializer.Serialize(new
        {
            schema_version = "gdd-requirements.v1",
            route = "gdd-requirements",
            status_dimension = RouteStatusVocabulary.RouteReadback,
            status_allowed_values = new[] { "ready", "needs_review", "blocked", "stale", "unknown" },
            status = "ready",
            source_boundary_enforced = true,
            source_boundary = new
            {
                recovery_source_order_ref = HostedRouteRecoveryContract.ContractId,
                recovery_source_order = HostedRouteRecoveryContract.SourceOrder,
                authority_sources = new[] { "game-type-guide:rpg" },
                source_hashes = sourceHashes,
                forbidden_source_patterns = new[] { "assistant summary as acceptance authority" },
                allowed_source_references = new[] { tamperedReference },
                prompt_evidence_refs = new[] { "meta/routes/gdd-requirements/prompt-evidence.json" }
            }
        }));

        fixture.Read().BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/gdd-requirements/latest.json:prompt_evidence_invalid" &&
            issue.Severity == "P0");
    }

    [Fact]
    public void Read_WhenCanonicalAndMirrorContractDiffer_MarksCanonicalStale()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("routes/prototype-contract/latest.json", """
        {
          "schema_version": "prototype-contract.v1",
          "status": "fresh",
          "contract_hash": "canonical"
        }
        """);
        fixture.WriteJson("meta/routes/prototype-contract/latest.json", """
        {
          "schema_version": "prototype-contract.v1",
          "status": "fresh",
          "contract_hash": "mirror"
        }
        """);

        var readback = fixture.Read();

        var contract = readback.Artifacts.Single(artifact => artifact.Route == "prototype-contract");
        contract.Authority.Should().Be("authority");
        contract.Freshness.Should().Be("stale");
        contract.BlockingIssueIds.Should().Contain("prototype-contract:mirror_hash_mismatch");
    }

    [Fact]
    public void Read_WhenP0RequirementHasGap_BlocksContractFreeze()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/gdd-requirements/latest.json", """
        {
          "schema_version": "gdd-requirements.v1",
          "status": "ready",
          "source_boundary_enforced": true,
          "source_boundary": {
            "authority_sources": ["docs/gdd/GDD.md"],
            "forbidden_source_patterns": ["docs/game-type-guides/** raw excerpts"]
          },
          "requirements": [
            {
              "requirement_id": "REQ-001",
              "priority": "P0",
              "status": "missing_module"
            }
          ]
        }
        """);

        var readback = fixture.Read();

        readback.BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "gdd-requirements:REQ-001:requirement_p0_gap" &&
            issue.DomainCode == "requirement_p0_gap" &&
            issue.Severity == "P0");
    }

    [Fact]
    public void Read_WhenP1DeferredBySystem_BlocksForAdminDecision()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/gdd-requirements/latest.json", """
        {
          "schema_version": "gdd-requirements.v1",
          "status": "ready",
          "requirements": [
            {
              "requirement_id": "REQ-002",
              "priority": "P1",
              "status": "explicitly_deferred",
              "decision_by": "system",
              "decision_role": "system",
              "decision_utc": "2026-07-10T00:00:00Z",
              "decision_reason": "fallback",
              "affected_requirement_ids": ["REQ-002"]
            }
          ]
        }
        """);

        var readback = fixture.Read();

        readback.BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "gdd-requirements:REQ-002:admin_decision_required" &&
            issue.DomainCode == "admin_review_blocked");
    }

    [Fact]
    public void Read_WhenUiWiringSurfaceOmitsRequiredFields_BlocksClosure()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/ui-wiring/latest.json", """
        {
          "schema_version": "ui-wiring-closure.v1",
          "status": "ready",
          "ui_surface_matrix": [
            {
              "feature": "route_map",
              "status": "covered",
              "godot_surface_type": "control"
            }
          ]
        }
        """);

        var readback = fixture.Read();

        readback.BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "ui-wiring:route_map:godot_ui_surface_incomplete" &&
            issue.DomainCode == "diagnostic_blocked");
    }

    [Fact]
    public void Read_WhenP1NoUiNeededLacksReviewMetadata_BlocksClosure()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/ui-wiring/latest.json", """
        {
          "schema_version": "ui-wiring-closure.v1",
          "status": "ready",
          "ui_surface_matrix": [
            {
              "feature": "combat_hud",
              "priority": "P1",
              "status": "no_ui_needed",
              "capability_domain_ids": ["hud_menus_overlays"]
            }
          ]
        }
        """);

        var readback = fixture.Read();

        readback.BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "ui-wiring:combat_hud:godot_ui_no_ui_needed_review_missing" &&
            issue.DomainCode == "admin_review_blocked" &&
            issue.Severity == "P1");
    }

    [Fact]
    public void Read_WhenUiSurfaceUsesUnknownProfilesOrForbiddenTechnology_BlocksClosure()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/ui-wiring/latest.json", """
        {
          "schema_version": "ui-wiring-closure.v1",
          "status": "ready",
          "ui_surface_matrix": [
            {
              "feature": "reward_screen",
              "priority": "P1",
              "status": "covered",
              "capability_domain_ids": ["rendering_materials_shaders", "animation_state_machines"],
              "godot_scene_path": "res://Scenes/UI/RewardScreen.tscn",
              "godot_surface_type": "control",
              "layout_strategy": "responsive_control_layout",
              "input_paths": ["ui_accept"],
              "feedback_states": ["hover", "selected"],
              "camera_layer_boundary": "CanvasLayer:ui",
              "viewport_mode": "responsive_control_layout",
              "ui_update_ownership_mode": "invented",
              "state_boundary": "RewardScreenState",
              "material_profile": "PBRNoTexture",
              "rendering_profile": "invented",
              "animation_profile": "raw_strings"
            }
          ]
        }
        """);

        var readback = fixture.Read();

        readback.BlockingIssues.Select(issue => issue.IssueId).Should().Contain([
            "ui-wiring:reward_screen:technology_stack_leakage",
            "ui-wiring:reward_screen:ui_update_ownership_missing",
            "ui-wiring:reward_screen:material_profile_missing",
            "ui-wiring:reward_screen:rendering_profile_missing",
            "ui-wiring:reward_screen:animation_state_profile_missing"
        ]);
    }

    [Fact]
    public void Read_WhenUiSurfaceHasCompleteGodotCapabilityEvidence_AllowsClosure()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/ui-wiring/latest.json", """
        {
          "schema_version": "ui-wiring-closure.v1",
          "status": "ready",
          "ui_surface_matrix": [
            {
              "feature": "route_map",
              "priority": "P1",
              "status": "covered",
              "capability_domain_ids": ["ui_scene_architecture", "custom_2d_drawing", "input_focus_navigation"],
              "godot_scene_path": "res://Scenes/UI/RouteMap.tscn",
              "godot_surface_type": "control",
              "layout_strategy": "responsive_container",
              "input_paths": ["ui_accept", "ui_cancel"],
              "feedback_states": ["hover", "selected", "disabled"],
              "camera_layer_boundary": "CanvasLayer:ui",
              "viewport_mode": "responsive_control_layout",
              "ui_update_ownership_mode": "registered_control_map",
              "state_boundary": "RouteMapViewState",
              "material_profile": "solid_2d_canvas",
              "rendering_profile": "rendering_not_applicable",
              "animation_profile": "animation_not_applicable",
              "third_person_camera_required": true,
              "camera_controller_profile": "Game.Godot/Scenes/Camera/ThirdPersonCameraRig.tscn"
            }
          ]
        }
        """);

        var readback = fixture.Read();

        readback.BlockingIssues.Should().NotContain(issue => issue.IssueId.StartsWith("ui-wiring:route_map:", StringComparison.Ordinal));
    }

    [Fact]
    public void Read_WhenStyleGapRowsContainUnresolvedP1Drift_BlocksFinalReadiness()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/ui-wiring/latest.json", """
        {
          "schema_version": "ui-wiring-closure.v1",
          "status": "ready",
          "ui_surface_matrix": [],
          "style_gap_rows": [
            {
              "gap_id": "gap-1",
              "style_drift_family": "palette",
              "requirement_ids": ["REQ-001"],
              "scene_node_path": "res://Scenes/UI/Hud.tscn/HudRoot",
              "expected_style_token_or_rule": "color.primary",
              "observed_drift": "Button uses an ad hoc red.",
              "severity": "P1",
              "affected_viewport_or_component_state": "desktop:hover",
              "visual_evidence_method": "screenshot",
              "follow_up_goal_recommendation": "Repair HUD button token mapping.",
              "status": "open"
            }
          ]
        }
        """);

        var readback = fixture.Read();

        readback.BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "ui-wiring:style-gap:gap-1:unresolved_final_readiness_blocker" &&
            issue.Severity == "P1");
    }

    [Fact]
    public void Read_WhenStyleGapFamilyIsUnknown_BlocksClosure()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/ui-wiring/latest.json", """
        {
          "schema_version": "ui-wiring-closure.v1",
          "status": "ready",
          "ui_surface_matrix": [],
          "style_gap_rows": [
            {
              "gap_id": "gap-2",
              "style_drift_family": "mutable_heading",
              "requirement_ids": ["REQ-002"],
              "scene_node_path": "res://Scenes/UI/Menu.tscn/Menu",
              "expected_style_token_or_rule": "typography.title",
              "observed_drift": "Unknown taxonomy.",
              "severity": "P2",
              "affected_viewport_or_component_state": "desktop:default",
              "visual_evidence_method": "ui_tree_readback",
              "follow_up_goal_recommendation": "Normalize taxonomy.",
              "status": "open"
            }
          ]
        }
        """);

        var readback = fixture.Read();

        readback.BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "ui-wiring:style-gap:gap-2:style_gap_family_unknown");
    }

    [Fact]
    public void Read_WhenStyleRepairPromptInputsAreIncomplete_BlocksClosure()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/ui-wiring/latest.json", """
        {
          "schema_version": "ui-wiring-closure.v1",
          "status": "ready",
          "ui_surface_matrix": [],
          "style_repair_prompt_inputs": {
            "frozen_style_snapshot_ref": "meta/routes/ui-style-snapshot/latest.json"
          }
        }
        """);

        var readback = fixture.Read();

        readback.BlockingIssues.Select(issue => issue.IssueId).Should().Contain([
            "ui-wiring:style-repair-prompt:missing_runtime_environment_ref",
            "ui-wiring:style-repair-prompt:missing_ui_tree_readback_refs"
        ]);
    }

    [Fact]
    public void Read_WhenFullTargetClosureUsesInterimStatus_BlocksFinalReadiness()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/ui-wiring/latest.json", """
        {
          "schema_version": "ui-wiring-closure.v1",
          "status": "ready",
          "ui_surface_matrix": [],
          "full_target_closure_ledger": [
            {
              "capability_id": "ui_final_readiness_style_gate",
              "status": "not_consumed_by_first_slice"
            }
          ]
        }
        """);

        var readback = fixture.Read();

        readback.BlockingIssues.Select(issue => issue.IssueId).Should().Contain([
            "ui-wiring:full-target:ui_final_readiness_style_gate:invalid_final_readiness_status",
            "ui-wiring:full-target:ui_final_readiness_style_gate:interim_status_not_final"
        ]);
    }

    [Fact]
    public void BuildRecommendation_UsesSingleDescriptorCatalogForAllCanonicalActions()
    {
        using var fixture = RouteStateFixture.Create();
        var artifacts = fixture.Read();
        var recommendation = fixture.Service.BuildRecommendation(
            fixture.Project,
            artifacts,
            new ProjectWorkflowNextAction("create-prototype", "Create", "Create", "Create", "create-prototype", true));

        recommendation.ActionDescriptorRef.DescriptorId.Should().Be(RouteActionDescriptors.DescriptorId);
        recommendation.ActionDescriptorRef.DescriptorVersion.Should().Be(RouteActionDescriptors.DescriptorVersion);
        recommendation.AllowedActions.Concat(recommendation.ForbiddenActions)
            .Select(action => action.ActionId)
            .Should()
            .BeEquivalentTo(RouteActionDescriptors.CanonicalActionIds);
        recommendation.AllowedActions.Concat(recommendation.ForbiddenActions)
            .Should()
            .OnlyContain(action => action.DescriptorHash == recommendation.ActionDescriptorRef.DescriptorHash);
        recommendation.ForbiddenActions
            .Where(action => action.DisabledDomainCode is not null)
            .Should()
            .OnlyContain(action => RouteActionDescriptors.DisabledDomainCodes.Contains(action.DisabledDomainCode!));
    }

    [Fact]
    public void Read_WhenEvidenceRefKindIsOutsideStandardsEnum_Blocks()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/gdd-document/latest.json", """
        {
          "schema_version": "gdd-document-generation.v1",
          "status_dimension": "route_readback",
          "status_allowed_values": ["ready", "blocked"],
          "status": "ready",
          "evidence_refs": [
            { "kind": "raw_prompt", "path": "meta/routes/gdd-document/prompt.txt" }
          ]
        }
        """);

        var readback = fixture.Read();

        readback.BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/gdd-document/latest.json:evidence_ref_kind_invalid");
    }

    [Fact]
    public void BuildRecommendation_WhenLegacyGddExistsWithoutForm_RecommendsImport()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteText("docs/gdd/GDD.md", "# GDD\n");
        var artifacts = fixture.Read();

        var recommendation = fixture.Service.BuildRecommendation(
            fixture.Project,
            artifacts,
            new ProjectWorkflowNextAction("create-prototype", "Create", "Create", "Create", "create-prototype", true));

        recommendation.RecommendedAction.Should().Be("import_gdd_form");
        recommendation.ForbiddenActions.Should().Contain(action =>
            action.ActionId == "create_iteration_plan" &&
            action.DisabledDomainCode == "route_contract_not_active");
    }

    private sealed class RouteStateFixture : IDisposable
    {
        private readonly string _root;
        private readonly string? _outsideRoot;
        private readonly Dictionary<string, ProjectRoutePromptEvidenceBinding> _promptBindings = new(StringComparer.Ordinal);
        private readonly HashSet<string> _artifactIds = new(StringComparer.Ordinal);

        private RouteStateFixture(string root, bool symlinkRepo = false)
        {
            _root = root;
            var repoPath = Path.Combine(root, "repo");
            if (symlinkRepo)
            {
                _outsideRoot = Path.Combine(Path.GetTempPath(), "phasea-route-state-repo-target-" + Guid.NewGuid().ToString("N"));
                Directory.CreateDirectory(_outsideRoot);
                Directory.CreateDirectory(root);
                Directory.CreateSymbolicLink(repoPath, _outsideRoot);
            }
            Project = new ProjectSnapshot(
                "project-1",
                "account-1",
                "Demo",
                "Demo",
                "RPG",
                "default",
                false,
                "[]",
                "succeeded",
                null,
                "workspace-1",
                Path.Combine(root, "workspace"),
                repoPath,
                Path.Combine(root, "runtime"),
                Path.Combine(repoPath, "meta"));
            Directory.CreateDirectory(Project.RepoPath);
            Directory.CreateDirectory(Project.MetaPath);
            Service = new ProjectRouteStateArtifactService();
        }

        public ProjectSnapshot Project { get; }

        public ProjectRouteStateArtifactService Service { get; }

        public ProjectRouteStateArtifactReadback Read()
        {
            return Service.Read(Project, _promptBindings, _artifactIds);
        }

        public void AddArtifactId(string artifactId) => _artifactIds.Add(artifactId);

        public void RemovePromptBinding(string route) => _promptBindings.Remove(route);

        public void UpdateJson(string relativePath, Action<JsonObject> update)
        {
            var path = Path.Combine(Project.RepoPath, relativePath.Replace('/', Path.DirectorySeparatorChar));
            var node = JsonNode.Parse(File.ReadAllText(path))!.AsObject();
            update(node);
            WriteJson(relativePath, node.ToJsonString());
        }

        public void WriteFinalUiSourcesAndLedger(string closureStatus = "covered")
        {
            var hash = new string('a', 64);
            WriteJson("meta/routes/gdd-requirements/latest.json", "{}");
            WriteJson("routes/prototype-contract/latest.json", JsonSerializer.Serialize(new
            { contract_hash = hash, source_godot_ui_contract_hash = hash, source_ui_style_contract_hash = hash, ui_style_snapshot_hash = hash }));
            const string gdd = "# Current fixture GDD";
            WriteText("docs/gdd/GDD.md", gdd);
            var sourceHashes = new Dictionary<string, string>
            {
                ["docs/gdd/GDD.md"] = Hash(gdd),
                [HostedRouteRecoveryContract.ParsedRouteProfileHashKey] = HostedRouteForbiddenSourceGuard.PromptHash(JsonSerializer.Serialize(PrototypeRouteSkillPolicy.ResolveProfile(Project))),
                [HostedRouteRecoveryContract.SelectedRouteSkillPromptBlockHashKey] = HostedRouteForbiddenSourceGuard.PromptHash(PrototypeRouteSkillPolicy.BuildPromptBlock(Project))
            };
            const string promptRef = "meta/routes/iteration-plan/prompt-evidence.json";
            WritePromptEvidence(promptRef, "Build from current structured fixture sources.", sourceHashes,
                ["assistant summary as acceptance authority"], routeOverride: "iteration-plan");
            var goals = Array.Empty<object>();
            var modules = Array.Empty<object>();
            var blockers = Array.Empty<object>();
            var coverage = new { uncovered_requirement_ids = Array.Empty<string>() };
            var planHash = IterationPlanIntegrity.Compute("fixture-current-sources", goals, modules, blockers, coverage);
            WriteJson("meta/routes/iteration-plan/latest.json", JsonSerializer.Serialize(new
            {
                schema_version = "iteration-plan.v1", route = "iteration-plan", status = "ready",
                status_dimension = RouteStatusVocabulary.RouteReadback,
                status_allowed_values = RouteStatusVocabulary.Values(RouteStatusVocabulary.RouteReadback),
                freshness = new { status = "fresh" }, source_boundary_enforced = true,
                source_boundary = new
                {
                    recovery_source_order_ref = HostedRouteRecoveryContract.ContractId,
                    recovery_source_order = HostedRouteRecoveryContract.SourceOrder,
                    authority_sources = new[] { "docs/gdd/GDD.md", HostedRouteRecoveryContract.ParsedRouteProfileSource, HostedRouteRecoveryContract.SelectedRouteSkillPromptBlockSource },
                    source_hashes = sourceHashes,
                    forbidden_source_patterns = new[] { "assistant summary as acceptance authority" },
                    prompt_evidence_refs = new[] { promptRef }
                },
                source_hash_ref = "fixture-current-sources", plan_hash = planHash,
                goals, required_modules = modules, blockers, coverage
            }));
            WriteJson("meta/routes/validation/result.json", "{}");
            WriteJson("meta/routes/validation/latest.json", JsonSerializer.Serialize(new
            {
                schema_version = "validation.v1", route = "validation", validation_input_hash = hash, status = "succeeded",
                status_dimension = RouteStatusVocabulary.RouteReadback,
                status_allowed_values = RouteStatusVocabulary.Values(RouteStatusVocabulary.RouteReadback),
                freshness = new { status = "fresh" }, source_boundary_enforced = false,
                source_boundary_not_applicable = new
                {
                    reason = "deterministic_state_transition", checked_utc = DateTimeOffset.UtcNow.ToString("O"), decision_by = "system",
                    evidence_refs = new[] { new { kind = "sidecar", path = "meta/routes/validation/result.json" } }
                }
            }));
            WriteJson("meta/reviews/final.json", "{}");
            WriteJson("meta/routes/ui-wiring/latest.json", JsonSerializer.Serialize(new
            {
                schema_version = "ui-wiring-closure.v1", status = "succeeded", ui_surface_matrix = Array.Empty<object>(),
                source_iteration_session_hash = planHash, source_validation_input_hash = hash, source_contract_hash = hash,
                source_requirement_map_hash = GddToModuleAuthorityHashes.Sha256("{}"), source_godot_ui_contract_hash = hash,
                source_ui_style_contract_hash = hash, ui_style_snapshot_hash = hash,
                full_target_closure_ledger = GddToModuleFirstSlice.CapabilityIds.Select(id => new
                {
                    capability_id = id, closure_status = closureStatus, currentCoverageStatus = "covered",
                    affected_routes = new[] { "ui-wiring" }, owner = "Phase service", expiry_or_recheck_trigger = "source-change",
                    validation_evidence_refs = new[] { "meta/routes/validation/latest.json" }, phase_exit_review_ref = "meta/reviews/final.json",
                    defer_reason = closureStatus == "explicitly_deferred" ? "fixture deferral" : ""
                })
            }));
        }

        public static RouteStateFixture Create()
        {
            var root = Path.Combine(Path.GetTempPath(), "phasea-route-state-artifacts-" + Guid.NewGuid().ToString("N"));
            return new RouteStateFixture(root);
        }

        public static RouteStateFixture CreateWithRepoSymlink()
        {
            var root = Path.Combine(Path.GetTempPath(), "phasea-route-state-artifacts-" + Guid.NewGuid().ToString("N"));
            return new RouteStateFixture(root, symlinkRepo: true);
        }

        public void WriteJson(string relativePath, string json)
        {
            WriteText(relativePath, json);
        }

        public void WriteText(string relativePath, string text)
        {
            var path = Path.Combine(Project.RepoPath, relativePath.Replace('/', Path.DirectorySeparatorChar));
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            File.WriteAllText(path, text.Replace("\r\n", "\n"));
        }

        public void WritePromptEvidence(
            string evidenceRelativePath,
            string prompt,
            IReadOnlyDictionary<string, string> sourceHashes,
            IReadOnlyList<string> forbiddenPatterns,
            IReadOnlyList<string>? allowedSourceReferences = null,
            string? routeOverride = null)
        {
            var promptRelativePath = evidenceRelativePath.Replace(".json", ".prompt.txt", StringComparison.Ordinal);
            WriteText(promptRelativePath, prompt);
            var scan = HostedRouteForbiddenSourceGuard.Scan(
                prompt,
                forbiddenPatterns,
                allowedSourceReferences: allowedSourceReferences);
            var persistedPromptHash = HostedRouteForbiddenSourceGuard.PromptHash(prompt);
            var route = routeOverride ?? (evidenceRelativePath.Contains("gdd-document", StringComparison.Ordinal)
                ? "gdd-document-generation"
                : "gdd-requirements");
            WriteJson(evidenceRelativePath, JsonSerializer.Serialize(new
            {
                route,
                recovery_source_order_ref = HostedRouteRecoveryContract.ContractId,
                recovery_source_order = HostedRouteRecoveryContract.SourceOrder,
                source_hashes = sourceHashes,
                forbidden_source_scan = scan,
                prompt_manifest = new
                {
                    prompt_count = 1,
                    prompt_artifact_refs = new[] { promptRelativePath },
                    execution_prompt_hash = scan.PromptHash,
                    persisted_prompt_hash = persistedPromptHash,
                    retention = "internal_recovery_only",
                    browser_readable = false,
                    redacted = true
                }
            }));
            _promptBindings[route] = new ProjectRoutePromptEvidenceBinding(
                Project.ProjectId,
                route,
                scan.PromptHash,
                persistedPromptHash,
                promptRelativePath,
                evidenceRelativePath,
                DateTimeOffset.UtcNow.ToString("O"));
        }

        public static string Hash(string text)
        {
            var normalized = text.Replace("\r\n", "\n").Trim();
            return Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(System.Text.Encoding.UTF8.GetBytes(normalized))).ToLowerInvariant();
        }

        public void Dispose()
        {
            if (Directory.Exists(_root))
            {
                Directory.Delete(_root, recursive: true);
            }
            if (_outsideRoot is not null && Directory.Exists(_outsideRoot))
            {
                Directory.Delete(_outsideRoot, recursive: true);
            }
        }
    }
}
