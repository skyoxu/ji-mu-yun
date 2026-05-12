using FluentAssertions;
using PhaseA.Platform.Browser;
using Xunit;

namespace PhaseA.Platform.Tests.Browser;

public sealed class BrowserUiRendererTests
{
    [Fact]
    public void RenderShell_IncludesPrototypeLaneControls()
    {
        var html = new BrowserUiRenderer().RenderShell();

        html.Should().Contain("Phase A Prototype Console");
        html.Should().Contain("Admin token");
        html.Should().Contain("projectName");
        html.Should().Contain("游戏类型/玩法方向");
        html.Should().Contain("Roguelike");
        html.Should().NotContain("打开完整 project-health 页面");
        html.Should().Contain("createProjectPanel");
        html.Should().Contain("projectDetailPanel");
        html.Should().Contain("currentProjectPanel");
        html.Should().Contain("initStatusPanel");
        html.Should().Contain("showLoggedOut");
        html.Should().Contain("logout");
        html.Should().Contain("退出登录");
        html.Should().Contain("data-delete-project");
        html.Should().Contain("deleteProject");
        html.Should().Contain("loadLatestProjectCreationFailure");
        html.Should().Contain("/api/project-creation-failures/latest");
        html.Should().Contain("listableProjects");
        html.Should().Contain(@"p.bootstrapStatus !== ""running""");
        html.Should().Contain(@"$(""createProjectPanel"").classList.remove(""hidden"")");
        html.Should().Contain(@"$(""stepsPanel"").classList.add(""hidden"")");
        html.Should().Contain(@"$(""sessionPanel"").classList.add(""hidden"")");
        html.Should().Contain("项目初始化配置中");
        html.Should().NotContain(@"$(""chapter2"")");
        html.Should().Contain("runPrototype");
        html.Should().Contain("repairPrototype");
        html.Should().Contain("修复原型");
        html.Should().Contain("prototype-7day-playable/repair");
        html.Should().Contain("7 步可玩原型");
        html.Should().Contain("globalModelPanel");
        html.Should().Contain("globalModel");
        html.IndexOf("id=\"globalModelPanel\"", StringComparison.Ordinal).Should().BeLessThan(html.IndexOf("id=\"stepsPanel\"", StringComparison.Ordinal));
        html.Should().Contain("<option value=\"gpt-5.4\" selected>gpt-5.4</option>");
        html.Should().NotContain("prototypeModel");
        html.Should().NotContain("chatModel");
        html.Should().Contain("gpt-5.5");
        html.Should().Contain("gpt-5.4");
        html.Should().NotContain("gpt-5.4-mini");
        html.Should().NotContain("gpt-5.3-codex");
        html.Should().NotContain("gpt-5.2");
        html.Should().Contain("prototypeProgress");
        html.Should().Contain("refreshPrototypeProgress");
        html.Should().Contain("prototype-7day-playable/progress");
        html.Should().Contain("setPrototypeFormLocked");
        html.Should().Contain("isPrototypeCreationLocked");
        html.Should().Contain("原型创建中..刷新页面查阅创建进度.");
        html.Should().Contain("prototypeCommandPanel");
        html.Should().Contain(@"role !== ""admin""");
        html.Should().NotContain("stopAfterDay");
        html.Should().Contain(@"data-stage=""red""");
        html.Should().Contain("createScene");
        html.Should().Contain("chatPanel");
        html.Should().Contain("chat-scroll");
        html.Should().Contain("updateChatPanelVisibility");
        html.Should().Contain("seedChatFromPrototypeProgress");
        html.Should().Contain("latestPrototypeTerminalOutput");
        html.Should().Contain("stdoutText");
        html.Should().Contain("tailText");
        html.Should().Contain("可以点击“修复原型”继续修复");
        html.Should().NotContain("建议删除该项目后重新创建");
        html.Should().Contain("sendChat");
        html.Should().Contain("submitFormalFeedback");
        html.Should().Contain("提交反馈并继续优化原型");
        html.Should().Contain("feedbackRecords");
        html.Should().Contain("prototype-feedback-iterations");
        html.Should().NotContain("skillActionPanel");
        html.Should().NotContain("skillActionSelect");
        html.Should().NotContain("runSkillAction");
        html.Should().Contain("/api/skill-actions");
        html.Should().Contain("chatSkillMode");
        html.Should().Contain("\u666e\u901a\u6a21\u5f0f");
        html.Should().Contain("skillActionId");
        html.Should().Contain("Codex");
        html.Should().Contain("/chat");
        html.Should().Contain("/api/projects");
        html.Should().Contain("prototype-7day-playable");
        html.Should().Contain("prototype-tdd");
    }
}
