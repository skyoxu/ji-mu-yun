using FluentAssertions;
using PhaseA.Platform.Workflow;
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
}
