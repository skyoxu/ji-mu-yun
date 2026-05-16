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
        html.Should().Contain("activeRunBanner");
        html.Should().Contain("/api/account/active-run");
        html.Should().Contain("当前任务执行中");
        html.Should().Contain("guardGlobalAction");
        html.Should().Contain("data-global-action");
        html.Should().Contain("删除中...");
        html.Should().Contain("setInterval(refreshActiveRun, 5000)");
        html.Should().Contain("Admin token");
        html.Should().Contain("projectName");
        html.Should().Contain("游戏类型/玩法方向");
        html.Should().Contain("Roguelike");
        html.Should().NotContain("打开完整 project-health 页面");
        html.Should().Contain("createProjectPanel");
        html.Should().Contain("projectDetailPanel");
        html.Should().Contain("currentProjectPanel");
        html.Should().Contain("initStatusPanel");
        html.Should().Contain("pollProjectInitializationResult");
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
        html.Should().Contain("draftFile");
        html.Should().Contain("分析草稿并回填");
        html.Should().Contain("prototype-drafts/analyze");
        html.Should().Contain("prototype-drafts/latest");
        html.Should().Contain("loadLatestPrototypeDraft");
        html.Should().Contain("loadLatestPrototypeDraft(true)");
        html.Should().Contain("renderDraftImportStatus");
        html.Should().Contain("draftAnalysisRunning");
        html.Should().Contain("草稿分析仍在进行中");
        html.Should().Contain("草稿分析中..暂不可启动原型.");
        html.Should().Contain("已同步最近一次草稿分析结果，表单已自动补全到最新状态。");
        html.Should().Contain("当前还不能启动：缺少必填项");
        html.Should().NotContain("project-drafts/import");
        html.Should().Contain("repairPrototype");
        html.Should().Contain("修复原型");
        html.Should().Contain("prototype-7day-playable/repair");
        html.Should().Contain("7 步可玩原型");
        html.Should().Contain("prototypeWorkflowPanel");
        html.Should().Contain(@"$(""prototypeWorkflowPanel"").classList.toggle(""hidden"", status === ""succeeded"")");
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
        html.Should().Contain("buildPrototypePayload");
        html.Should().Contain("missingPrototypeFields");
        html.Should().Contain("showPrototypeNotice");
        html.Should().Contain("showPrototypeError");
        html.Should().Contain("正在提交原型创建请求");
        html.Should().Contain("缺少必填项");
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
        html.Should().Contain("phaseAChatHistory");
        html.Should().Contain("chatStorageVersion");
        html.Should().Contain("maxStoredChatMessages");
        html.Should().Contain("loadChatHistoryForProject");
        html.Should().Contain("loadServerChatHistoryForProject");
        html.Should().Contain("chat-history");
        html.Should().Contain("saveChatHistoryForProject");
        html.Should().Contain("chatThinkingPrompts");
        html.Should().Contain("startChatThinkingMessage");
        html.Should().Contain("Codex CLI 正在生成回复");
        html.Should().Contain("setInterval");
        html.Should().Contain("updateChatPanelVisibility");
        html.Should().Contain("seedChatFromPrototypeProgress");
        html.Should().Contain("prototypeSeedMessage");
        html.Should().Contain("sanitizePublicChatContent");
        html.Should().NotContain("latestPrototypeTerminalOutput");
        html.Should().NotContain("stdoutText || run.stderrText");
        html.Should().NotContain("tailText(text");
        html.Should().NotContain("终端输出");
        html.Should().Contain("可以点击“修复原型”继续修复");
        html.Should().NotContain("建议删除该项目后重新创建");
        html.Should().Contain("sendChat");
        html.Should().Contain("submitQuickFix");
        html.Should().Contain("快速修复");
        html.Should().Contain("快速修复：适合修入口接线、文案、状态显示、小范围逻辑问题");
        html.Should().Contain("prototype-quick-fixes");
        html.Should().Contain("submitFormalFeedback");
        html.Should().Contain("提交反馈并继续优化原型");
        html.Should().Contain("continueSuggestedFeedback");
        html.Should().Contain("renderInlineContinueAction");
        html.Should().Contain("data-continue-suggestion");
        html.Should().Contain("同意继续优化");
        html.Should().Contain("nextSuggestedFeedback");
        html.Should().Contain("continueConsumed");
        html.Should().Contain("suggestedFeedback");
        html.Should().Contain("defaultNextSuggestedFeedback");
        html.Should().Contain("updateContinueSuggestionFromText");
        html.Should().Contain("如果你同意|如你同意|若你同意");
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

    [Fact]
    public void RenderDownloads_IncludesRobustPackageDownloadFlow()
    {
        var html = new BrowserUiRenderer().RenderDownloads();

        html.Should().Contain("项目文件下载");
        html.Should().Contain("下载准备中...");
        html.Should().Contain("download-ticket");
        html.Should().Contain("/api/projects/${encodeURIComponent(projectId)}/packages/${encodeURIComponent(fileName)}/download-ticket");
        html.Should().Contain("cache: \"no-store\"");
        html.Should().NotContain("URL.createObjectURL");
        html.Should().Contain("下载失败：");
        html.Should().Contain("下载已提交给浏览器");
    }
}
