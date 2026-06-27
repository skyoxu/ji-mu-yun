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
        options.WebPreviewSigningSecret.Should().BeNull();
        options.MaxConcurrentChats.Should().Be(8);
        options.MaxConcurrentChatsPerAccount.Should().Be(1);
        options.MaxConcurrentQuestionForms.Should().Be(4);
        options.MaxConcurrentQuestionFormsPerAccount.Should().Be(1);
        options.MaxConcurrentProjectCreations.Should().Be(3);
        options.MaxConcurrentProjectCreationsPerAccount.Should().Be(1);
        options.MaxConcurrentOtherRuns.Should().Be(3);
        options.MaxConcurrentPrototypeCreations.Should().Be(2);
        options.MaxConcurrentAssetGenerations.Should().Be(2);
        options.MaxConcurrentWebPreviews.Should().Be(3);
        options.MaxConcurrentWebPreviewsPerAccount.Should().Be(1);
        options.Godot3WebPreviewExportTimeoutSeconds.Should().Be(180);
        options.Godot3WebPreviewExportInactivityTimeoutSeconds.Should().Be(45);
        options.MaxConcurrentAssetGenerationsPerAccount.Should().Be(1);
        options.AssetAllowedUrlPrefixes.Should().BeEmpty();
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
            ["PHASEA_ADMIN_TOKEN_HASH"] = "token-hash",
            ["PHASEA_TICKET_SIGNING_SECRET"] = "ticket-secret",
            ["PHASEA_WEB_PREVIEW_SIGNING_SECRET"] = "web-preview-secret",
            ["PHASEA_MAX_CONCURRENT_CHATS"] = "9",
            ["PHASEA_MAX_CONCURRENT_CHATS_PER_ACCOUNT"] = "3",
            ["PHASEA_MAX_CONCURRENT_GDD_QUESTION_FORMS"] = "5",
            ["PHASEA_MAX_CONCURRENT_GDD_QUESTION_FORMS_PER_ACCOUNT"] = "2",
            ["PHASEA_MAX_CONCURRENT_PROJECT_CREATIONS"] = "4",
            ["PHASEA_MAX_CONCURRENT_PROJECT_CREATIONS_PER_ACCOUNT"] = "2",
            ["PHASEA_MAX_CONCURRENT_OTHER_RUNS"] = "2",
            ["PHASEA_MAX_CONCURRENT_PROTOTYPE_CREATIONS"] = "6",
            ["PHASEA_MAX_CONCURRENT_ASSET_GENERATIONS"] = "5",
            ["PHASEA_MAX_CONCURRENT_WEB_PREVIEWS"] = "7",
            ["PHASEA_MAX_CONCURRENT_WEB_PREVIEWS_PER_ACCOUNT"] = "2",
            ["PHASEA_GODOT3_WEB_PREVIEW_EXPORT_TIMEOUT_SECONDS"] = "240",
            ["PHASEA_GODOT3_WEB_PREVIEW_EXPORT_INACTIVITY_TIMEOUT_SECONDS"] = "60",
            ["PHASEA_MAX_CONCURRENT_ASSET_GENERATIONS_PER_ACCOUNT"] = "1",
            ["PHASEA_ASSET_ALLOWED_URLS"] = "https://assets.example.com/kaykit/; https://cdn.example.com/free/"
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
        options.TicketSigningSecret.Should().Be("ticket-secret");
        options.WebPreviewSigningSecret.Should().Be("web-preview-secret");
        options.MaxConcurrentChats.Should().Be(9);
        options.MaxConcurrentChatsPerAccount.Should().Be(3);
        options.MaxConcurrentQuestionForms.Should().Be(5);
        options.MaxConcurrentQuestionFormsPerAccount.Should().Be(2);
        options.MaxConcurrentProjectCreations.Should().Be(4);
        options.MaxConcurrentProjectCreationsPerAccount.Should().Be(2);
        options.MaxConcurrentOtherRuns.Should().Be(2);
        options.MaxConcurrentPrototypeCreations.Should().Be(6);
        options.MaxConcurrentAssetGenerations.Should().Be(5);
        options.MaxConcurrentWebPreviews.Should().Be(7);
        options.MaxConcurrentWebPreviewsPerAccount.Should().Be(2);
        options.Godot3WebPreviewExportTimeoutSeconds.Should().Be(240);
        options.Godot3WebPreviewExportInactivityTimeoutSeconds.Should().Be(60);
        options.MaxConcurrentAssetGenerationsPerAccount.Should().Be(1);
        options.AssetAllowedUrlPrefixes.Should().Equal("https://assets.example.com/kaykit", "https://cdn.example.com/free");
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
    [InlineData("PHASEA_MAX_CONCURRENT_CHATS", "0")]
    [InlineData("PHASEA_MAX_CONCURRENT_CHATS_PER_ACCOUNT", "0")]
    [InlineData("PHASEA_MAX_CONCURRENT_GDD_QUESTION_FORMS", "0")]
    [InlineData("PHASEA_MAX_CONCURRENT_GDD_QUESTION_FORMS_PER_ACCOUNT", "0")]
    [InlineData("PHASEA_MAX_CONCURRENT_PROJECT_CREATIONS", "0")]
    [InlineData("PHASEA_MAX_CONCURRENT_PROJECT_CREATIONS_PER_ACCOUNT", "0")]
    [InlineData("PHASEA_MAX_CONCURRENT_OTHER_RUNS", "0")]
    [InlineData("PHASEA_MAX_CONCURRENT_PROTOTYPE_CREATIONS", "0")]
    [InlineData("PHASEA_MAX_CONCURRENT_ASSET_GENERATIONS", "0")]
    [InlineData("PHASEA_MAX_CONCURRENT_WEB_PREVIEWS", "0")]
    [InlineData("PHASEA_MAX_CONCURRENT_WEB_PREVIEWS_PER_ACCOUNT", "0")]
    [InlineData("PHASEA_GODOT3_WEB_PREVIEW_EXPORT_TIMEOUT_SECONDS", "0")]
    [InlineData("PHASEA_GODOT3_WEB_PREVIEW_EXPORT_INACTIVITY_TIMEOUT_SECONDS", "0")]
    [InlineData("PHASEA_MAX_CONCURRENT_ASSET_GENERATIONS_PER_ACCOUNT", "0")]
    [InlineData("PHASEA_ASSET_ALLOWED_URLS", "http://assets.example.com/free/")]
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

    [Fact]
    public void StartPhaseA_WebPreviewSigningSecretPrefersPersistentFile()
    {
        var scriptPath = Path.GetFullPath(Path.Combine(
            AppContext.BaseDirectory,
            "..",
            "..",
            "..",
            "..",
            "runtime",
            "phase-a",
            "start-phasea.ps1"));
        var source = File.ReadAllText(scriptPath);

        var fileReadIndex = source.IndexOf("[System.IO.File]::ReadAllText($webPreviewSecretFile).Trim()", StringComparison.Ordinal);
        var hostReadIndex = source.IndexOf("Resolve-HostEnvironmentValue 'PHASEA_WEB_PREVIEW_SIGNING_SECRET'", StringComparison.Ordinal);

        fileReadIndex.Should().BeGreaterThanOrEqualTo(0);
        hostReadIndex.Should().BeGreaterThan(fileReadIndex);
        source.Should().Contain("$env:PHASEA_WEB_PREVIEW_SIGNING_SECRET = $resolvedWebPreviewSecret");
        source.Should().Contain("$psi.Environment['PHASEA_WEB_PREVIEW_SIGNING_SECRET'] = $env:PHASEA_WEB_PREVIEW_SIGNING_SECRET");
    }
}
