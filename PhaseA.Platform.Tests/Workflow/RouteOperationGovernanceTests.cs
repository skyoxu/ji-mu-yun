using FluentAssertions;
using PhaseA.Platform.Workflow;
using System.Text.Json;
using Xunit;

namespace PhaseA.Platform.Tests.Workflow;

public sealed class RouteOperationGovernanceTests
{
    [Fact]
    public void ActionDescriptors_ShouldDeclareExposureClassForEveryAction()
    {
        var allowed = new[] { "user_visible", "admin_visible", "script_only", "internal" };
        RouteActionDescriptors.All.Should().OnlyContain(action =>
            allowed.Contains(action.ExposureClass));
    }

    [Fact]
    public void AdminVisibleActions_ShouldNotMapToOrdinaryUserMutationButtons()
    {
        RouteActionDescriptors.Get("analyze_game_type").ExposureClass.Should().Be("admin_visible");
        RouteActionDescriptors.Get("analyze_game_type").OperationScope.Should().Be("readback");
        RouteActionDescriptors.Get("analyze_game_type").BrowserActionId.Should().Be("currentProjectPanel");
    }

    [Fact]
    public void PreflightCapabilities_ShouldUseKnownActionsAndRedactedVisibility()
    {
        foreach (var capability in RouteOperationPreflight.Capabilities)
        {
            capability.CapabilityId.Should().NotBeNullOrWhiteSpace();
            capability.Source.Should().NotBeNullOrWhiteSpace();
            capability.ReadbackVisibility.Should().BeOneOf("admin_only_redacted", "user_safe_summary");
            capability.RequiredForActionIds.Should().NotBeEmpty();
            capability.RequiredForActionIds.Should().OnlyContain(action => RouteActionDescriptors.CanonicalActionIds.Contains(action));
        }

        RouteOperationPreflight.ForAction("execute_next_goal").Select(capability => capability.CapabilityId)
            .Should()
            .Contain(["codex_command", "godot_binary", "hosted_workspace_root"]);
    }

    [Fact]
    public void SecretRedactionPolicy_ShouldDetectAndRedactTokensProviderKeysAndSecretFields()
    {
        const string text = "Authorization: Bearer abc.def.ghi PHASEA_ADMIN_TOKEN=topsecret OPENAI_API_KEY=sk-abcdefghijklmnop";

        var violations = SecretRedactionPolicy.FindViolations(text);
        var redacted = SecretRedactionPolicy.Redact(text);

        violations.Should().Contain("secret_field:Authorization");
        violations.Should().Contain("secret_field:PHASEA_ADMIN_TOKEN");
        violations.Should().Contain("secret_field:OPENAI_API_KEY");
        violations.Should().Contain("secret_pattern:bearer_token");
        violations.Should().Contain("secret_pattern:provider_key");
        redacted.Should().NotContain("topsecret");
        redacted.Should().NotContain("sk-abcdefghijklmnop");
        redacted.Should().Contain("[redacted]");
    }

    [Fact]
    public void SecretRedactionPolicy_ShouldSanitizePersistencePayloadsAndHostPaths()
    {
        const string text = "Authorization: Bearer abc.def.ghi OPENAI_API_KEY=sk-abcdefghijklmnop C:\\host\\private\\evidence.json";

        var redacted = SecretRedactionPolicy.RedactForPersistence(text);

        redacted.Should().NotContain("abc.def.ghi");
        redacted.Should().NotContain("sk-abcdefghijklmnop");
        redacted.Should().NotContain("C:\\host\\private");
        redacted.Should().Contain("[redacted-host-path]");
    }

    [Fact]
    public void SecretRedactionPolicy_ShouldRedactQuotedJsonSecretFieldsWithoutBreakingJson()
    {
        const string text = """{"api_key":"plain secret with spaces","token_hash":"hash-secret","nested":{"access_token":"access-secret"},"items":[{"provider_key":"array-secret"}]}""";

        var redacted = SecretRedactionPolicy.RedactForPersistence(text);

        redacted.Should().NotContain("plain secret with spaces");
        redacted.Should().NotContain("hash-secret");
        redacted.Should().NotContain("access-secret");
        redacted.Should().NotContain("array-secret");
        using var parsed = JsonDocument.Parse(redacted);
        parsed.RootElement.GetProperty("api_key").GetString().Should().Be("[redacted]");
        parsed.RootElement.GetProperty("nested").GetProperty("access_token").GetString().Should().Be("[redacted]");
    }

    [Fact]
    public void SecretRedactionPolicy_ShouldRedactDriveUncExtendedAndSpaceBearingHostPaths()
    {
        const string text = "drive=C:\\host private\\decision.txt; unc=\\\\server\\private share\\evidence.json; root=\\\\server\\share; extended=\\\\?\\C:\\secret root\\trace.log";

        var redacted = SecretRedactionPolicy.RedactForPersistence(text);

        redacted.Should().NotContain("host private");
        redacted.Should().NotContain("server");
        redacted.Should().NotContain("secret root");
        redacted.Should().NotContain("\\\\server\\share");
        redacted.Should().Contain("[redacted-host-path]");
    }

    [Fact]
    public void SecretRedactionPolicy_ShouldRedactJsonRootStringWithoutThrowing()
    {
        var redacted = SecretRedactionPolicy.RedactForPersistence("\"Authorization: Bearer abc.def.ghi\"");

        redacted.Should().Be("\"Authorization: [redacted] [redacted]\"");
    }

    [Fact]
    public void HostedRouteForbiddenSourceGuard_ShouldValidateCleanScanEvidenceAndRejectForbiddenPath()
    {
        var patterns = new[] { "docs/game-type-guides/** raw excerpts" };
        var clean = HostedRouteForbiddenSourceGuard.Scan("Use frozen project artifacts only.", patterns);
        var blocked = HostedRouteForbiddenSourceGuard.Scan("Read docs/game-type-guides/rpg.md", patterns);
        var approvedRelative = HostedRouteForbiddenSourceGuard.Scan(
            "Approved source: docs/game-type-guides/rpg.md",
            patterns,
            allowedSourceReferences: ["docs/game-type-guides/rpg.md"]);
        var absoluteHostPath = HostedRouteForbiddenSourceGuard.Scan(
            @"Read C:\private\docs\game-type-guides\rpg.md",
            patterns,
            allowedSourceReferences: ["docs/game-type-guides/rpg.md"]);
        using var document = JsonDocument.Parse(JsonSerializer.Serialize(new { forbidden_source_scan = clean }));

        HostedRouteForbiddenSourceGuard.IsValidEvidence(document.RootElement, patterns).Should().BeTrue();
        blocked.Status.Should().Be("blocked");
        blocked.Violations.Should().ContainSingle();
        approvedRelative.Status.Should().Be("clean");
        absoluteHostPath.Status.Should().Be("blocked");
    }

    [Fact]
    public void HostedRouteForbiddenSourceGuard_ShouldBlockCopiedGuideParagraphAndMissingFingerprintSet()
    {
        const string guide = """
        # Guide

        This distinctive guide paragraph defines the full route, encounter, reward, and return loop that must not be copied after contract freeze.

        Another stable paragraph defines the visible player feedback and deterministic acceptance boundary for this guide.
        """;
        var patterns = new[] { "raw mutable game-type guide excerpt after freeze" };
        var fingerprints = HostedRouteForbiddenSourceGuard.CreateContentFingerprints("guide:rpg", guide);
        var copiedParagraph = HostedRouteForbiddenSourceGuard.Scan(
            "Plan: This distinctive guide paragraph defines the full route, encounter, reward, and return loop that must not be copied after contract freeze.",
            patterns,
            fingerprints,
            requireForbiddenContentFingerprints: true);
        var missingCatalog = HostedRouteForbiddenSourceGuard.Scan(
            "Use frozen artifacts only.",
            patterns,
            [],
            requireForbiddenContentFingerprints: true);

        copiedParagraph.Status.Should().Be("blocked");
        copiedParagraph.MatchedContentHashes.Should().NotBeEmpty();
        missingCatalog.Status.Should().Be("blocked");
        missingCatalog.FingerprintSetStatus.Should().Be("missing");
    }

    [Fact]
    public void HostedRouteForbiddenSourceGuard_ShouldBlockIncompleteFingerprintCatalog()
    {
        var fingerprints = HostedRouteForbiddenSourceGuard.CreateContentFingerprints(
            "guide:partial",
            "This loaded guide paragraph is present while another catalog entry failed to load.");

        var result = HostedRouteForbiddenSourceGuard.Scan(
            "Use frozen artifacts only.",
            ["raw mutable game-type guide excerpt after freeze"],
            fingerprints,
            requireForbiddenContentFingerprints: true,
            forbiddenContentFingerprintSetComplete: false);

        result.Status.Should().Be("blocked");
        result.FingerprintSetStatus.Should().Be("incomplete");
        result.Violations.Should().Contain("forbidden_content_fingerprint_set_incomplete");
    }

    [Fact]
    public void HostedRouteForbiddenSourceGuard_ShouldCoverShortLateAndLightlyEditedGuideChunks()
    {
        const string shortParagraph = "Short guide rule stays raw.";
        const string longParagraph = "This distinctive route guide defines visible combat rewards deterministic return flow camera ownership interaction feedback and acceptance evidence while preserving player agency scene transitions recovery state module boundaries input semantics diagnostic ownership preview readiness package readiness and repeatable smoke validation.";
        var manyParagraphs = string.Join(
            "\n\n",
            Enumerable.Range(1, 300).Select(index =>
                $"Guide paragraph {index:D3} defines a unique deterministic route encounter reward return and visible acceptance boundary for this game type."));
        var guide = $"{shortParagraph}\n\n{longParagraph}\n\n{manyParagraphs}";
        var fingerprints = HostedRouteForbiddenSourceGuard.CreateContentFingerprints("guide:large", guide);
        var patterns = new[] { "raw mutable game-type guide excerpt after freeze" };

        var shortCopy = HostedRouteForbiddenSourceGuard.Scan(shortParagraph, patterns, fingerprints, true);
        var lateCopy = HostedRouteForbiddenSourceGuard.Scan(
            "Guide paragraph 300 defines a unique deterministic route encounter reward return and visible acceptance boundary for this game type.",
            patterns,
            fingerprints,
            true);
        var lightEdit = HostedRouteForbiddenSourceGuard.Scan(
            longParagraph.Replace("combat", "battle", StringComparison.Ordinal),
            patterns,
            fingerprints,
            true);

        shortCopy.Status.Should().Be("blocked");
        lateCopy.Status.Should().Be("blocked");
        lightEdit.Status.Should().Be("blocked");
        fingerprints.Count.Should().BeGreaterThan(256);
    }

    [Fact]
    public void HostedRouteForbiddenSourceGuard_ShouldBlockSystematicWindowEdits()
    {
        const string guide = "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima mike november oscar papa quebec romeo sierra tango uniform victor whiskey xray yankee zulu amber bronze cobalt denim ember frost granite hazel ivory jade khaki linen";
        var fingerprints = HostedRouteForbiddenSourceGuard.CreateContentFingerprints("guide:systematic-edit", guide);
        var editedWords = guide.Split(' ');
        for (var index = 7; index < editedWords.Length; index += 8)
        {
            editedWords[index] = $"changed-{index}";
        }

        var result = HostedRouteForbiddenSourceGuard.Scan(
            string.Join(' ', editedWords),
            ["raw mutable game-type guide excerpt after freeze"],
            fingerprints,
            requireForbiddenContentFingerprints: true);

        result.Status.Should().Be("blocked");
        result.MatchedContentHashes.Should().NotBeEmpty();
    }

    [Fact]
    public void HostedRouteForbiddenSourceGuard_ShouldBlockSkillGuidePathsUnlessExplicitlyAllowed()
    {
        var patterns = new[] { "unapproved raw game-type guide excerpt before contract freeze" };
        const string skillGuide = ".agents/skills/gds-gdd/assets/game-types/card-game.md";

        var blocked = HostedRouteForbiddenSourceGuard.Scan($"Read {skillGuide}", patterns);
        var allowed = HostedRouteForbiddenSourceGuard.Scan(
            $"Read {skillGuide}",
            patterns,
            allowedSourceReferences: [skillGuide]);

        blocked.Status.Should().Be("blocked");
        allowed.Status.Should().Be("clean");
    }

    [Fact]
    public void HostedRouteForbiddenSourceGuard_ShouldBlockShortAndDenserSystematicEdits()
    {
        const string shortGuide = "short distinctive guide rule stays raw";
        const string longGuide = "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima mike november oscar papa quebec romeo sierra tango uniform victor whiskey xray yankee zulu amber bronze cobalt denim ember frost granite hazel ivory jade khaki linen";
        var shortFingerprints = HostedRouteForbiddenSourceGuard.CreateContentFingerprints("guide:short-edit", shortGuide);
        var longFingerprints = HostedRouteForbiddenSourceGuard.CreateContentFingerprints("guide:dense-edit", longGuide);
        var editedWords = longGuide.Split(' ');
        for (var index = 5; index < editedWords.Length; index += 6)
        {
            editedWords[index] = $"changed-{index}";
        }

        var shortResult = HostedRouteForbiddenSourceGuard.Scan(
            "short distinctive guide policy stays raw",
            ["raw mutable game-type guide excerpt after freeze"],
            shortFingerprints,
            true);
        var denseResult = HostedRouteForbiddenSourceGuard.Scan(
            string.Join(' ', editedWords),
            ["raw mutable game-type guide excerpt after freeze"],
            longFingerprints,
            true);

        shortResult.Status.Should().Be("blocked");
        denseResult.Status.Should().Be("blocked");
    }

    [Fact]
    public void HostedRouteForbiddenSourceGuard_ShouldBlockInsertedAndDeletedGuideWords()
    {
        const string guide = "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima mike november oscar papa";
        var fingerprints = HostedRouteForbiddenSourceGuard.CreateContentFingerprints("guide:token-shift", guide);
        var patterns = new[] { "raw mutable game-type guide excerpt after freeze" };

        var inserted = HostedRouteForbiddenSourceGuard.Scan(
            "alpha bravo charlie delta echo foxtrot golf inserted hotel india juliet kilo lima mike november oscar papa",
            patterns,
            fingerprints,
            true);
        var deleted = HostedRouteForbiddenSourceGuard.Scan(
            "alpha bravo charlie delta echo foxtrot golf india juliet kilo lima mike november oscar papa",
            patterns,
            fingerprints,
            true);

        inserted.Status.Should().Be("blocked");
        deleted.Status.Should().Be("blocked");
    }

    [Fact]
    public void HostedRouteForbiddenSourceGuard_ShouldBlockDeletionBeforeRepeatedRarestAnchor()
    {
        const string guide = "alpha bravo charlie delta echo foxtrot golf hotel india juliet alpha lima mike november oscar papa";
        var fingerprints = HostedRouteForbiddenSourceGuard.CreateContentFingerprints("guide:repeated-anchor", guide);

        var result = HostedRouteForbiddenSourceGuard.Scan(
            "bravo charlie delta echo foxtrot golf hotel india juliet alpha lima mike november oscar papa",
            ["raw mutable game-type guide excerpt after freeze"],
            fingerprints,
            true);

        result.Status.Should().Be("blocked");
    }

    [Fact]
    public void HostedRouteForbiddenSourceGuard_ShouldExcludeOnlyExplicitlyAllowedGuideContent()
    {
        const string allowedGuide = "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima mike november oscar papa";
        const string forbiddenGuide = "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima mike november oscar quartz";
        var fingerprints = HostedRouteForbiddenSourceGuard.CreateContentFingerprints("guide:forbidden", forbiddenGuide);

        var allowedOnly = HostedRouteForbiddenSourceGuard.Scan(
            $"Use approved content: {allowedGuide}",
            ["raw mutable game-type guide excerpt after freeze"],
            fingerprints,
            true,
            allowedContentExcerpts: [allowedGuide]);
        var forbiddenCopy = HostedRouteForbiddenSourceGuard.Scan(
            $"Use approved content: {allowedGuide}. Also copy: {forbiddenGuide}",
            ["raw mutable game-type guide excerpt after freeze"],
            fingerprints,
            true,
            allowedContentExcerpts: [allowedGuide]);

        allowedOnly.Status.Should().Be("clean");
        forbiddenCopy.Status.Should().Be("blocked");
    }

    [Fact]
    public void HostedRouteForbiddenSourceGuard_ShouldBlockMarkdownTableAndCaseVariants()
    {
        const string guide = """
        | Route | Encounter | Reward | Return |
        | --- | --- | --- | --- |
        | Ember Path | Ash Guardian | Fire Relic | Camp Gate |
        """;
        var patterns = new[] { "raw mutable game-type guide excerpt after freeze" };
        var fingerprints = HostedRouteForbiddenSourceGuard.CreateContentFingerprints("guide:table", guide);

        var exactTable = HostedRouteForbiddenSourceGuard.Scan(guide, patterns, fingerprints, true);
        var caseVariant = HostedRouteForbiddenSourceGuard.Scan(guide.ToUpperInvariant(), patterns, fingerprints, true);

        fingerprints.Should().NotBeEmpty();
        exactTable.Status.Should().Be("blocked");
        caseVariant.Status.Should().Be("blocked");
    }
}
