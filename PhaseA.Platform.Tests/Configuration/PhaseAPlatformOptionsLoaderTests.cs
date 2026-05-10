using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Workspaces;
using Xunit;

namespace PhaseA.Platform.Tests.Configuration;

public sealed class PhaseAPlatformOptionsLoaderTests
{
    [Fact]
    public void FromDictionary_UsesPhaseADefaults_WhenEnvironmentIsEmpty()
    {
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());

        options.HostedWorkspaceRoot.Should().Be(Path.GetFullPath(@"C:\workspaces").TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar));
        options.HostedProjectLimit.Should().Be(2);
        options.HttpsTermination.Should().Be("caddy");
        options.AppBindUrl.Should().Be("http://127.0.0.1:8080");
        options.PublicBaseUrl.Should().Be("https://localhost");
        options.LlmGatewayProvider.Should().Be("new-api");
        options.LlmGatewayBaseUrl.Should().Be("https://localhost/v1");
        options.LlmGatewayTokenMode.Should().Be("per-account");
        options.LlmGatewayBindingMode.Should().Be("manual-admin");
        options.LlmCostStopLossPerRunCny.Should().Be(2.00m);
        options.LlmCostStopLossDailyAccountCny.Should().Be(20.00m);
        options.RepositoryRoot.Should().Be(Path.GetFullPath(AppContext.BaseDirectory).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar));
        options.PythonCommand.Should().Be("py");
        options.DeliveryProfile.Should().Be("fast-ship");
        options.AdminUsername.Should().Be("admin");
    }

    [Fact]
    public void FromDictionary_ParsesEnvironmentOverrides()
    {
        var values = new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = @"D:\phase-a-workspaces",
            ["HOSTED_PROJECT_LIMIT"] = "4",
            ["HTTPS_TERMINATION"] = "caddy",
            ["APP_BIND_URL"] = "http://127.0.0.1:9090",
            ["PUBLIC_BASE_URL"] = "https://phase-a.example.com",
            ["LLM_GATEWAY_PROVIDER"] = "new-api",
            ["LLM_GATEWAY_BASE_URL"] = "https://llm.example.com/v1",
            ["LLM_GATEWAY_TOKEN_MODE"] = "per-account",
            ["LLM_GATEWAY_BINDING_MODE"] = "manual-admin",
            ["LLM_COST_STOP_LOSS_PER_RUN_CNY"] = "3.50",
            ["LLM_COST_STOP_LOSS_DAILY_ACCOUNT_CNY"] = "30.00",
            ["PHASEA_REPOSITORY_ROOT"] = @"D:\repo-root",
            ["PHASEA_PYTHON_COMMAND"] = "python",
            ["GODOT_BIN"] = @"D:\Godot\Godot.exe",
            ["DELIVERY_PROFILE"] = "playable-ea",
            ["PHASEA_ADMIN_USERNAME"] = "root",
            ["PHASEA_ADMIN_PASSWORD_HASH"] = "password-hash",
            ["PHASEA_ADMIN_TOKEN_HASH"] = "token-hash"
        };

        var options = PhaseAPlatformOptionsLoader.FromDictionary(values);

        options.HostedWorkspaceRoot.Should().Be(Path.GetFullPath(@"D:\phase-a-workspaces").TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar));
        options.HostedProjectLimit.Should().Be(4);
        options.AppBindUrl.Should().Be("http://127.0.0.1:9090");
        options.PublicBaseUrl.Should().Be("https://phase-a.example.com");
        options.LlmGatewayBaseUrl.Should().Be("https://llm.example.com/v1");
        options.LlmCostStopLossPerRunCny.Should().Be(3.50m);
        options.LlmCostStopLossDailyAccountCny.Should().Be(30.00m);
        options.RepositoryRoot.Should().Be(Path.GetFullPath(@"D:\repo-root").TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar));
        options.PythonCommand.Should().Be("python");
        options.GodotBin.Should().Be(@"D:\Godot\Godot.exe");
        options.DeliveryProfile.Should().Be("playable-ea");
        options.AdminUsername.Should().Be("root");
        options.AdminPasswordHash.Should().Be("password-hash");
        options.AdminTokenHash.Should().Be("token-hash");
    }

    [Theory]
    [InlineData("HOSTED_WORKSPACE_ROOT", "relative\\path")]
    [InlineData("HOSTED_PROJECT_LIMIT", "0")]
    [InlineData("PUBLIC_BASE_URL", "http://phase-a.example.com")]
    [InlineData("LLM_GATEWAY_BASE_URL", "http://llm.example.com/v1")]
    [InlineData("LLM_COST_STOP_LOSS_PER_RUN_CNY", "-1")]
    [InlineData("PHASEA_REPOSITORY_ROOT", "relative\\repo")]
    [InlineData("APP_BIND_URL", "http://0.0.0.0:8080")]
    [InlineData("APP_BIND_URL", "https://127.0.0.1:8080")]
    public void FromDictionary_FailsClosed_ForInvalidValues(string key, string value)
    {
        var values = new Dictionary<string, string?> { [key] = value };

        var act = () => PhaseAPlatformOptionsLoader.FromDictionary(values);

        act.Should().Throw<PhaseAPlatformConfigException>();
    }

    [Fact]
    public void WorkspacePathPolicy_RejectsEscapingPaths()
    {
        WorkspacePathPolicy.IsUnderRoot(@"C:\workspaces", @"C:\workspaces\project-a\repo").Should().BeTrue();
        WorkspacePathPolicy.IsUnderRoot(@"C:\workspaces", @"C:\other\project-a").Should().BeFalse();
    }
}
