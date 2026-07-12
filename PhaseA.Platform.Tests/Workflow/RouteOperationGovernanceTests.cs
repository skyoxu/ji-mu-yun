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
        const string text = "drive=C:\\host private\\decision.txt; unc=\\\\server\\private share\\evidence.json; extended=\\\\?\\C:\\secret root\\trace.log";

        var redacted = SecretRedactionPolicy.RedactForPersistence(text);

        redacted.Should().NotContain("host private");
        redacted.Should().NotContain("server");
        redacted.Should().NotContain("secret root");
        redacted.Should().Contain("[redacted-host-path]");
    }
}
