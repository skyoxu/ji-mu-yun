using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Tests.Data;
using Xunit;

namespace PhaseA.Platform.Tests.Llm;

public sealed class LlmStopLossServiceTests
{
    [Fact]
    public async Task CheckAsync_BlocksWhenSingleRunEstimateExceedsLimit()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var service = new LlmStopLossService(store, options);

        var decision = await service.CheckAsync(accountId, new LlmCostEstimate(2.01m));

        decision.Allowed.Should().BeFalse();
        decision.FailureCode.Should().Be("llm_run_stop_loss_exceeded");
    }

    [Fact]
    public async Task CheckAsync_BlocksWhenDailyTotalWouldExceedLimit()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["LLM_COST_STOP_LOSS_PER_RUN_CNY"] = "2.00",
            ["LLM_COST_STOP_LOSS_DAILY_ACCOUNT_CNY"] = "2.00"
        });
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var runId = await store.CreateRunAsync(projectId, null, "prototype-7day-playable");
        await store.RecordRunLlmAuditAsync(runId, "new-api", null, "codex", """{"estimated_cost_cny":1.50}""");
        var service = new LlmStopLossService(store, options);

        var decision = await service.CheckAsync(accountId, new LlmCostEstimate(0.60m));

        decision.Allowed.Should().BeFalse();
        decision.FailureCode.Should().Be("llm_daily_stop_loss_exceeded");
    }

    private static async Task<string> CreateProjectAsync(PhaseAMetadataStore store, PhaseAPlatformOptions options, string accountId)
    {
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var result = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Demo Game", "manual", null, null, null, null));
        return result.ProjectId!;
    }
}
