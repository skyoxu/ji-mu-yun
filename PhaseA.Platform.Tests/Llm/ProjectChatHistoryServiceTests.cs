using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Tests.Data;
using Xunit;

namespace PhaseA.Platform.Tests.Llm;

public sealed class ProjectChatHistoryServiceTests
{
    [Fact]
    public async Task ListAsync_ShouldExtractOnlyActionableNextStep_WithoutContinueHint()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var service = new ProjectChatHistoryService(store);
        var assistantMessage = """
            原型创建完成。

            下一步建议：
            请继续把当前 RPG 原型补成一个完整首轮闭环：优先让玩家能稳定移动、触发遇敌、完成一场战斗，并在胜利后完成一次奖励 3 选 1 再返回地图。

            如果你同意，可以点击这条消息下方的“同意继续优化”，系统会把这条建议作为正式反馈继续提交。
            """;

        await service.AppendAsync(accountId, projectId, "assistant", assistantMessage, "prototype-seed");
        var history = await service.ListAsync(accountId, projectId);

        history.Should().NotBeNull();
        history!.Messages.Should().ContainSingle();
        history.Messages[0].SuggestedFeedback.Should().Be("请继续把当前 RPG 原型补成一个完整首轮闭环：优先让玩家能稳定移动、触发遇敌、完成一场战斗，并在胜利后完成一次奖励 3 选 1 再返回地图。");
        history.Messages[0].SuggestedFeedback.Should().NotContain("如果你同意");
    }

    private static async Task<string> CreateProjectAsync(PhaseAMetadataStore store, PhaseAPlatformOptions options, string accountId)
    {
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var result = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Demo Game", "manual", null, null, null, null));
        return result.ProjectId!;
    }
}
