using FluentAssertions;
using PhaseA.Platform.Browser;
using PhaseA.Platform.Data;
using PhaseA.Platform.Readback;
using Xunit;

namespace PhaseA.Platform.Tests.Browser;

public sealed class BrowserUiRendererTests
{
    [Fact]
    public void RenderShellV2_IncludesProgressComparisonPage()
    {
        var html = new BrowserUiRenderer().RenderShellV2();

        html.Should().Contain("积木云 Phase A 原型控制台");
        html.Should().Contain("v2ProgressShell");
        html.Should().Contain("v2ProgressSteps");
        html.Should().Contain("v2ContentGrid");
        html.Should().Contain("v2EnsureContentGrid");
        html.Should().Contain("grid-template-columns: minmax(0, 1fr) minmax(0, 1fr)");
        html.Should().Contain("grid.appendChild(element)");
        html.Should().Contain("v2JudgeNextStep");
        html.Should().Contain("扫描项目判断下一步建议");
        html.Should().Contain("v2JudgeNextStepLocally");
        html.Should().Contain("v2BuildLocalNextStepSuggestion");
        html.Should().Contain("正在扫描项目状态");
        html.Should().Contain("Promise.allSettled");
        html.Should().Contain("withTimeout(loadProjectPackages(), \"packages\")");
        html.Should().Contain("withTimeout(refreshAssetInventoryAvailability(), \"asset_inventory\")");
        html.Should().Contain("已基于当前缓存状态生成建议");
        html.Should().Contain("点击按钮后扫描项目进度并给出下一步建议。");
        html.Should().Contain("项目状态扫描失败，请稍后重试或先刷新页面。");
        html.Should().NotContain("调用 LLM 判断下一步");
        html.Should().NotContain("v2NextSuggestionHasLlmResult");
        html.Should().Contain("\\u8bf7\\u5148\\u8fdb\\u884c 2. \\u539f\\u578b\\u9aa8\\u67b6\\u521b\\u5efa");
        html.Should().Contain("请先进行 3. 骨架验收修复");
        html.Should().Contain("请先进行 4. 完成迭代计划");
        html.Should().Contain("请进行 6. 原型验收");
        html.Should().Contain("UI 优化是可选步骤，可以在验收前或验收后执行。");
        html.Should().NotContain("function v2Suggestion()");
        html.Should().NotContain("dataset.llmPinned");
        html.Should().Contain("grid-template-columns: repeat(9, minmax(5.6rem, 1fr))");
        html.Should().Contain("body.v2-detail #currentProjectPanel > button { display: none; }");
        html.Should().Contain("v2RunStepAction");
        html.Should().Contain("let v2UserSelectedStep = false");
        html.Should().Contain("function v2ApplySelectedStepVisibility()");
        html.Should().Contain("function v2SelectDefaultStepForPrototypeProgress(progress)");
        html.Should().Contain("if (v2UserSelectedStep || v2SelectedStep !== \"new-project\") return;");
        html.Should().Contain("button.onclick = () => v2ShowStep(button.dataset.v2Step, true)");
        html.Should().Contain("v2AcceptancePanel");
        html.Should().Contain("v2CreateAcceptancePanel");
        html.Should().Contain("原型验收结果");
        html.Should().Contain("重新触发原型验收");
        html.Should().Contain("rerun.onclick = v2ValidatePrototypeIfAllowed");
        html.Should().Contain("skeletonAcceptance.onclick = v2ValidatePrototypeIfAllowed");
        html.Should().Contain("v2PrototypeAcceptanceBlockReason");
        html.Should().Contain("v2AcceptanceActionStatus");
        html.Should().Contain("await validatePrototype();");
        html.Should().Contain("v2IterationPlanAllowsAcceptance");
        html.Should().Contain("请先完成当前迭代计划，所有目标完成后再进行原型验收。");
        html.Should().Contain("UI 优化是可选步骤，不会阻塞验收。");
        html.Should().NotContain("请先完成 UI 优化，再进行原型验收。");
        html.Should().NotContain("if (stepId === \"prototype-acceptance\") {\n                    $(\"validatePrototype\")?.click();");
        html.Should().NotContain("[\"revalidate-prototype\", \"重新验收\"]");
        html.Should().Contain("$(\"loadAssetInventory\")?.click()");
        html.Should().Contain("$(\"createProjectPackage\")?.click()");
        html.Should().Contain("$(\"openProjectDownloads\")?.click()");
        html.Should().Contain("v2ApplyPrototypeFormLock");
        html.Should().Contain("v2ShouldLockPrototypeForm");
        html.Should().Contain("v2-prototype-locked");
        html.Should().Contain("$(\"draftFile\").disabled = locked");
        html.Should().Contain("$(\"importDraft\").disabled = locked");
        html.Should().Contain("原型骨架已创建，不能重复创建");
        html.Should().Contain("setPrototypeFormLocked = function(locked)");
        html.Should().Contain("v2ApplyPrototypeFormSnapshot");
        html.Should().Contain("progress?.form");
        html.Should().Contain("已载入原型记录");
        html.Should().NotContain("if (v2SelectedStep === \"create-prototype\") $(\"prototypeWorkflowPanel\")?.classList.remove(\"hidden\")");
        html.Should().Contain("workflow-icons-color.png");
        html.Should().Contain("workflow-icons-gray.png");
        html.Should().Contain("v2-step-number");
        html.Should().Contain("${index + 1}");
        html.Should().Contain(".v2-step-button.pending .v2-step-mark");
        html.Should().Contain(".v2-step-button.action .v2-step-mark");
        html.Should().Contain("游戏项目详情");
        html.Should().Contain("原型骨架创建");
        html.Should().Contain("完成迭代计划");
        html.Should().Contain("骨架验收修复");
        html.Should().Contain("UI优化");
        html.IndexOf("[\"execute-or-repair\", \"骨架验收修复\", 3]", StringComparison.Ordinal).Should().BeLessThan(html.IndexOf("[\"iteration-plan\", \"完成迭代计划\", 4]", StringComparison.Ordinal));
        html.IndexOf("[\"iteration-plan\", \"完成迭代计划\", 4]", StringComparison.Ordinal).Should().BeLessThan(html.IndexOf("[\"ui-optimization\", \"UI优化\", 5]", StringComparison.Ordinal));
        html.Should().Contain("function v2RunIsCurrentForIteration(run)");
        html.Should().Contain("const sessionTime = v2IterationSessionTimestamp();");
        html.Should().Contain("const goalTime = Math.max(0, ...goals.map(goal => v2IsoTime(goal.completedUtc || goal.updatedUtc || goal.createdUtc || \"\")));");
        html.Should().Contain("if (!run || !v2RunIsCurrentForIteration(run)) return \"pending\";");
        html.Should().Contain("if (substep === \"validation_skipped\") return \"pending\";");
        html.Should().Contain("if (substep === \"validation_failed\") return \"fix\";");
        html.Should().Contain("请先完成原型骨架创建，再运行 UI 优化。");
        html.Should().Contain("v2RepairPanel");
        html.Should().Contain("v2CreateRepairPanel");
        html.Should().Contain("const goals = state.repairPlan?.goals || []");
        html.Should().Contain("if (failed) return \"fix\";");
        html.Should().Contain("确认素材清单");
        html.Should().Contain("打包项目文件");
        html.Should().Contain("下载项目文件");
        html.Should().Contain("if (stepId === \"new-project\") return state.projectId ? \"done\" : \"pending\"");
        html.Should().Contain("if (stepId === \"iteration-plan\") {");
        html.Should().Contain("return \"continue\"");
        html.Should().Contain("•••");
        html.Should().Contain("function v2AssetInventoryConfirmed()");
        html.Should().Contain("if (stepId === \"asset-inventory\") return v2AssetInventoryConfirmed() ? \"done\" : \"pending\"");
        html.Should().Contain("if (stepId === \"package-project\") return v2HasPackages() ? \"done\" : \"pending\"");
        html.Should().Contain("if (stepId === \"download-project\") return v2HasPackages() ? \"action\" : \"pending\"");
        html.Should().Contain("const mark = status === \"done\" ? \"✓\" : status === \"fix\" ? \"×\" : status === \"continue\" ? \"•••\" : \"\"");
        html.Should().Contain("flowTitle?.classList.add(\"hidden\")");
        html.Should().Contain("$(\"feedbackSummary\")?.classList.add(\"hidden\")");
        html.Should().Contain("$(\"feedbackRecords\")?.classList.add(\"hidden\")");
        html.Should().NotContain("重新验收</span>");
        html.Should().Contain("v2-summary-grid");
        html.Should().Contain("chatPanel");
        html.Should().Contain("自由聊天");
        html.Should().Contain("v2IterationPanel");
        html.Should().Contain("v2CreateIterationPanel");
        html.Should().Contain("panel.appendChild(current)");
        html.Should().Contain("show(\"v2IterationPanel\")");
        html.Should().Contain("v2ArrangeChatPanel");
        html.Should().Contain("v2ChatControls");
        html.Should().Contain("v2ChatComposer");
        html.Should().Contain("v2-chat-composer");
        html.Should().Contain("resizeChatComposer");
        html.Should().Contain("v2SkillRow");
        html.Should().Contain("v2-skill-row");
        html.Should().Contain("skillDescription");
        html.Should().Contain("v2CreateIterationPlanFromChat");
        html.Should().Contain("创建新迭代计划");
        html.Should().Contain("downloadChatHistory");
        html.Should().Contain("messageCount: messages.length");
        html.Should().Contain("const result = await api(`/api/projects/${state.projectId}/chat-history`);");
        html.Should().Contain("chatAttachmentFiles");
        html.Should().Contain("currentChatAttachmentsForRun");
        html.Should().Contain("attachments: currentChatAttachmentsForRun()");
        html.Should().Contain("removeChatAttachment");
        html.Should().Contain("existing.concat(attachments)");
        html.Should().Contain("data-index=\"${index}\"");
        html.Should().Contain("v2-attachment-chip");
        html.Should().Contain("v2-attachment-remove");
        html.Should().Contain("v2-attach-button");
        html.Should().Contain("color: var(--danger)");
        html.Should().Contain("attachLabel.title = \"导入 TXT 参考文件\"");
        html.Should().Contain("未导入 TXT 参考文件，只支持 TXT 文件导入。");
        html.Should().Contain("id=\"clearChatAttachments\" class=\"ghost hidden\"");
        html.Should().Contain("最多只能导入 5 个 TXT 参考文件。");
        html.Should().Contain("clearChatAttachments();");
        html.Should().Contain("history: state.chatHistory.slice(-3)");
        html.Should().NotContain("history: state.chatHistory.slice(-10)");
        html.Should().Contain("记录已下载。");
        html.Should().Contain("createGddDocument");
        html.Should().Contain("/api/projects/${state.projectId}/gdd");
        html.Should().Contain("gddOutlineUrl");
        html.Should().Contain("window.open(`/gdd-outline?projectId=${encodeURIComponent(state.projectId)}`");
        html.Should().Contain("state.gddOutlineReady = true;");
        html.Should().Contain("download=\"GDD.md\"");
        html.Should().Contain("result.downloadUrl || \"\"");
        html.Should().Contain("\\u521b\\u5efa\\u7b56\\u5212\\u5927\\u7eb2\\u5931\\u8d25");
        html.Should().Contain("kind: \"gdd-result\"");
        html.Should().Contain("__PHASEA_GDD_LINK_");
        html.Should().Contain("v2CanCreateIterationPlanFromChat");
        html.Should().Contain("v2IterationPlanExists");
        html.Should().Contain("v2IterationPlanCompleted");
        html.Should().Contain("v2PrototypeValidationPassedForPlanning");
        html.Should().Contain("v2SetPrototypeValidationInvalidated(true)");
        html.Should().Contain("v2SetPrototypeValidationInvalidated(false)");
        html.Should().Contain("phaseA:v2PrototypeValidationInvalidated");
        html.Should().Contain("$(\"submitFormalFeedback\")?.classList.add(\"hidden\")");
        html.Should().Contain("根据聊天内容创建新的迭代计划");
        html.Should().Contain("v2IterationMainActions");
        html.Should().Contain("v2RepairActions");
        html.Should().Contain("margin-left: auto");
        html.Should().Contain("$(\"evaluateIterationPlanFromChat\")?.classList.add(\"hidden\")");
        html.Should().Contain("syncChatHistory");
        html.Should().Contain("chatAttachmentFiles");
        html.Should().Contain("clearChatAttachments");
        html.Should().Contain("v2ChatAttachmentPanel");
        html.IndexOf("id=\"chatMessage\"", StringComparison.Ordinal).Should().BeLessThan(html.IndexOf("id=\"chatAttachmentFiles\"", StringComparison.Ordinal));
        html.IndexOf("id=\"chatAttachmentFiles\"", StringComparison.Ordinal).Should().BeLessThan(html.IndexOf("id=\"createGddDocument\"", StringComparison.Ordinal));
        html.Should().Contain("loadServerChatHistoryForProject");
        html.Should().Contain("renderChatHistory");
        html.Should().Contain("v2-chat-message-user");
        html.Should().Contain("v2-chat-message-assistant");
        html.Should().Contain("fit-content");
        html.Should().Contain("renderAssistantChatContent");
        html.Should().Contain("renderInlineMarkdown");
        html.Should().Contain("<pre><code>");
        html.Should().Contain("<li>${renderInlineMarkdown(item)}</li>");
        html.Should().NotContain("message.role === \"assistant\" ? \"助手\" : \"我\"");
        html.Should().Contain("v2OriginalShowProjectDetail");
        html.Should().Contain("v2SelectedStep = \"new-project\"");
        html.Should().Contain("user_project_creation_concurrency_limit_exceeded");
        html.Should().Contain("当前已有项目正在创建中");
        html.Should().NotContain("<strong>最新进度</strong>");
        html.Should().NotContain("<strong>更新时间</strong>");
        html.Should().NotContain("<strong>项目健康检查</strong>");
        html.Should().NotContain("v2ProgressDescription");
        html.Should().NotContain("v2ProgressUpdated");
        html.Should().NotContain("v2ProjectHealth");
        html.Should().Contain("/api/projects/${state.projectId}/prototype-7day-playable/progress");
    }

    [Fact]
    public void RenderProject_IncludesDefaultDetailProgressWithPendingUnrunSteps()
    {
        var project = new ProjectSnapshot(
            "project-1",
            "account-1",
            "Demo Project",
            "Demo Game",
            "rpg",
            "godot-prototype-default",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-1",
            "C:\\workspaces",
            "C:\\workspaces\\project-1",
            "C:\\workspaces\\project-1\\runtime",
            "C:\\workspaces\\project-1\\.phasea");

        var html = new BrowserUiRenderer().RenderProject(project, []);

        html.Should().Contain("detail-progress");
        html.Should().Contain("detail-step-number\">1</span>");
        html.Should().Contain("detail-step-number\">9</span>");
        html.Should().Contain("打包项目文件");
        html.Should().Contain("detail-step pending");
        html.Should().NotContain("detail-step fix");
        html.Should().NotContain("detail-step done\" href=\"/#prototypeWorkflowPanel\"");
        html.Should().NotContain("detail-step done\" href=\"/assets?projectId=project-1\"");
        html.Should().NotContain("detail-step done\" href=\"/#createProjectPackage\"");
    }

    [Fact]
    public void RenderProject_ShouldNotMarkUiOptimizationDone_WhenShortValidationWasSkipped()
    {
        var project = new ProjectSnapshot(
            "project-1",
            "account-1",
            "Demo Project",
            "Demo Game",
            "rpg",
            "godot-prototype-default",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-1",
            "C:\\workspaces",
            "C:\\workspaces\\project-1",
            "C:\\workspaces\\project-1\\runtime",
            "C:\\workspaces\\project-1\\.phasea");
        var run = new RunReadbackItem(
            "run-ui",
            "project-1",
            "workspace-1",
            "prototype-ui-optimization",
            "succeeded",
            0,
            "",
            "",
            "{\"godot_smoke\":{\"ran\":false,\"reason\":\"prototype_smoke_scene_missing\"}}",
            "succeeded",
            "validation_skipped",
            "UI optimization completed, short validation skipped.",
            DateTimeOffset.UtcNow.ToString("O"),
            null,
            null,
            null,
            null,
            []);

        var html = new BrowserUiRenderer().RenderProject(project, [run]);

        html.Should().Contain("detail-step pending\" href=\"/#v2UiOptimizationPanel\"");
        html.Should().NotContain("detail-step done\" href=\"/#v2UiOptimizationPanel\"");
    }

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
        html.Should().Contain("Access token");
        html.Should().Contain("phaseAAccessToken");
        html.Should().Contain("projectName");
        html.Should().Contain("游戏类型/玩法方向");
        html.Should().Contain("Roguelike");
        html.Should().NotContain("打开完整 project-health 页面");
        html.Should().Contain("createProjectPanel");
        html.Should().Contain("projectDetailPanel");
        html.Should().Contain("currentProjectPanel");
        html.Should().Contain("initStatusPanel");
        html.Should().Contain("pollProjectInitializationResult");
        html.Should().Contain(@"const createdProjectId = result.projectId || result.ProjectId || """";");
        html.Should().Contain("await pollProjectInitializationResult(createdProjectId)");
        html.Should().Contain("await refreshProjects({ autoSelect: false })");
        html.Should().Contain("selectProject(createdProject.projectId)");
        html.Should().Contain("projectCreationErrorMessage");
        html.Should().Contain("project_initialization_in_progress");
        html.Should().Contain("project_quota_exceeded");
        html.Should().Contain("project_creation_failed");
        html.Should().Contain("showLoggedOut");
        html.Should().Contain("logout");
        html.Should().Contain("退出登录");
        html.Should().Contain("data-delete-project");
        html.Should().Contain("deleteProject");
        html.Should().Contain("loadLatestProjectCreationFailure");
        html.Should().Contain("/api/project-creation-failures/latest");
        html.Should().Contain("listableProjects");
        html.Should().Contain(@"p.bootstrapStatus !== ""running""");
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
        html.Should().Contain("生成修复计划");
        html.Should().Contain("repair-plan");
        html.Should().Contain("executeRepairStep");
        html.Should().Contain("执行下一项修复");
        html.Should().Contain("原型骨架创建");
        html.Should().Contain("prototypeWorkflowPanel");
        html.Should().Contain(@"$(""prototypeWorkflowPanel"").classList.toggle(""hidden"", status === ""succeeded"")");
        html.Should().Contain("userTopActions");
        html.Should().Contain("top-actions");
        html.Should().Contain("user-only-action");
        html.Should().Contain("openCreateProjectPage");
        html.Should().Contain("openProjectListModal");
        html.Should().Contain("projectListModal");
        html.Should().Contain("closeProjectListModal");
        html.Should().Contain("showCreateProjectPage");
        html.Should().Contain("selectDefaultProject");
        html.Should().Contain("latestProject");
        html.Should().Contain("projectTimestamp");
        html.Should().Contain("globalModel");
        html.Should().NotContain("globalModelPanel");
        html.Should().NotContain("stepsPanel");
        html.Should().NotContain("codexConfigPanel");
        html.IndexOf("id=\"globalModel\"", StringComparison.Ordinal).Should().BeLessThan(html.IndexOf("id=\"openCreateProjectPage\"", StringComparison.Ordinal));
        html.IndexOf("id=\"openCreateProjectPage\"", StringComparison.Ordinal).Should().BeLessThan(html.IndexOf("id=\"openProjectListModal\"", StringComparison.Ordinal));
        html.IndexOf("id=\"openProjectListModal\"", StringComparison.Ordinal).Should().BeLessThan(html.IndexOf("id=\"logout\"", StringComparison.Ordinal));
        html.Should().Contain("<option value=\"gpt-5.5\" selected>5.5</option>");
        html.Should().Contain("<option value=\"gpt-5.4\">5.4</option>");
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
        html.Should().Contain("validatePrototype");
        html.Should().Contain("重新验收原型");
        html.Should().Contain("prototype-7day-playable/validate");
        html.Should().Contain("buildPrototypePayload");
        html.Should().Contain("missingPrototypeFields");
        html.Should().Contain("showPrototypeNotice");
        html.Should().Contain("showPrototypeError");
        html.Should().Contain("正在提交原型创建请求");
        html.Should().Contain("缺少必填项");
        html.Should().Contain("setPrototypeFormLocked");
        html.Should().Contain("isPrototypeCreationLocked");
        html.Should().Contain("原型骨架创建中..刷新页面查阅创建进度.");
        html.Should().Contain("prototypeCommandPanel");
        html.Should().Contain(@"role !== ""admin""");
        html.Should().Contain("id=\"loadRuns\" class=\"ghost hidden\"");
        html.Should().Contain("id=\"runsPanel\" class=\"hidden\"");
        html.Should().Contain("id=\"outputPanel\" class=\"hidden\"");
        html.Should().Contain(@"$(""loadRuns"").classList.toggle(""hidden"", !isAdmin)");
        html.Should().Contain(@"$(""runsPanel"").classList.toggle(""hidden"", !isAdmin)");
        html.Should().Contain(@"$(""outputPanel"").classList.toggle(""hidden"", !isAdmin)");
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
        html.Should().Contain("shouldAutoRefreshIterationPlan");
        html.Should().Contain(@"activeRun?.runType === ""prototype-iteration-goal""");
        html.Should().Contain("updateChatPanelVisibility");
        html.Should().Contain("seedChatFromPrototypeProgress");
        html.Should().Contain("prototypeSeedMessage");
        html.Should().Contain("formatNextStepSource");
        html.Should().Contain("formatNextStepEvaluation");
        html.Should().Contain("下一步建议来源：");
        html.Should().Contain("继续优化评估：");
        html.Should().Contain("Codex 输出");
        html.Should().Contain("原型记录");
        html.Should().Contain("系统生成");
        html.Should().Contain("建议继续");
        html.Should().Contain("建议谨慎");
        html.Should().Contain("暂不建议");
        html.Should().Contain("sanitizePublicChatContent");
        html.Should().Contain("Recovery source consumed:");
        html.Should().NotContain("latestPrototypeTerminalOutput");
        html.Should().NotContain("stdoutText || run.stderrText");
        html.Should().NotContain("tailText(text");
        html.Should().NotContain("终端输出");
        html.Should().Contain("可以点击“生成修复计划”");
        html.Should().NotContain("建议删除该项目后重新创建");
        html.Should().Contain("sendChat");
        html.Should().Contain("<button id=\"sendChat\" class=\"secondary\">发送</button>");
        html.Should().NotContain("<button id=\"sendChat\" class=\"secondary\" data-global-action=\"true\">");
        html.Should().Contain("accountAdminPanel");
        html.IndexOf("id=\"accountAdminPanel\"", StringComparison.Ordinal).Should().BeGreaterThan(html.IndexOf("id=\"adminPanel\"", StringComparison.Ordinal));
        html.Should().Contain("setUserTopActionsVisible(true, isAdmin)");
        html.Should().Contain("Admin project creation and project list are disabled.");
        html.Should().Contain("createUserAccount");
        html.Should().Contain("refreshUserAccounts");
        html.Should().Contain("loadUserAccounts");
        html.Should().Contain("/api/admin/users");
        html.Should().Contain("updateUserStatus");
        html.Should().Contain("rotateUserToken");
        html.Should().Contain("rotate-token");
        html.Should().Contain("llmGatewayBaseUrl");
        html.Should().Contain("saveLlmBinding");
        html.Should().Contain("loadLlmBinding");
        html.Should().Contain("/api/account/llm-binding");
        html.Should().Contain("loadLlmUsage");
        html.Should().Contain("/api/account/llm-usage");
        html.Should().Contain("loadAdminLlmUsage");
        html.Should().Contain("/api/admin/llm-usage");
        html.Should().Contain("downloadAdminLlmUsageCsv");
        html.Should().Contain("/api/admin/llm-usage.csv");
        html.Should().Contain("loadAdminLlmRuns");
        html.Should().Contain("/api/admin/llm-runs");
        html.Should().Contain("loadAdminRunMetrics");
        html.Should().Contain("openAdminRunDurationMetrics");
        html.Should().Contain("openAdminChatAverageMetrics");
        html.Should().Contain("admin-only-action");
        html.Should().Contain("location.href = \"/admin/run-duration-metrics\"");
        html.Should().Contain("location.href = \"/admin/chat-average-metrics\"");
        html.Should().Contain("prototype-chat");
        html.Should().Contain("/api/admin/run-metrics");
        html.Should().Contain("adminRunMetricsAccount");
        html.Should().Contain("adminRunMetricsType");
        html.Should().Contain("loadAccountAudit");
        html.Should().Contain("/api/admin/account-audit");
        html.Should().Contain("downloadAccountAuditCsv");
        html.Should().Contain("/api/admin/account-audit.csv");
        html.Should().Contain("syncChatHistory");
        html.Should().Contain("同步记录");
        html.Should().Contain("下载记录");
        html.Should().Contain("导入");
        html.Should().Contain("history.scrollTop = history.scrollHeight");
        html.Should().Contain("\\u521b\\u5efa\\u7b56\\u5212\\u5927\\u7eb2");
        html.Should().Contain("服务器聊天记录已同步。");
        html.Should().Contain("未输入优化目标，已使用当前下一步建议生成迭代计划。");
        html.Should().Contain("typedMessage ? \"manual_feedback\" : \"completion_suggestion\"");
        html.Should().Contain("evaluateIterationPlanFromChat");
        html.Should().Contain("评估当前计划是否值得继续");
        html.Should().Contain("needs-fix-route");
        html.Should().Contain("submitNeedsFixRouteRequest");
        html.Should().Contain("运行 Needs Fix 路由");
        html.Should().Contain("data-needs-fix-goal");
        html.Should().Contain("type=\"button\" class=\"secondary\" data-needs-fix-goal");
        html.Should().Contain("onclick=\"event.stopPropagation(); runNeedsFixIterationGoal('");
        html.Should().Contain("needsFixDisabledAttrs");
        html.Should().Contain("document.querySelectorAll(\"[data-needs-fix-goal]\").forEach");
        html.Should().Contain("document.addEventListener(\"click\", event =>");
        html.Should().Contain("event.target?.closest?.(\"[data-needs-fix-goal]\")");
        html.Should().Contain("<div class=\"v2-action-row\"><button type=\"button\" class=\"secondary\" data-needs-fix-goal");
        html.Should().NotContain("data-global-action=\"true\" data-needs-fix-goal");
        html.Should().NotContain("async function submitNeedsFixRouteRequest(payload, busyText) {\n                  if (!guardGlobalAction()) return;");
        html.Should().Contain("await loadPrototypeProgress();");
        html.Should().Contain("iterationNeedsFixStatus");
        html.Should().Contain("正在准备提交 step");
        html.Should().Contain("Needs Fix 路由已提交，正在等待后台 run 创建。");
        html.Should().Contain("当前有任务正在执行，请等待当前 run 完成后再启动 Needs Fix 路由。");
        html.Should().NotContain("无法启动 needs-fix：当前页面未确认原型骨架已创建。");
        html.Should().Contain("[\"needs_fix\", \"failed\"].includes");
        html.Should().Contain("feedback ? buildNeedsFixFeedbackForUserReport(goal, feedback) : buildNeedsFixFeedbackForGoal(goal)");
        html.Should().NotContain("quickFixPanel");
        html.Should().NotContain("submitQuickFix");
        html.Should().NotContain("prototype-quick-fixes");
        html.Should().NotContain("兼容入口：快速修复");
        html.Should().Contain("submitFormalFeedback");
        html.Should().Contain("提交反馈到 Needs Fix 路由");
        html.Should().Contain("buildNeedsFixFeedbackForUserReport(goal, feedback)");
        html.Should().Contain("goalId: goal?.goalId || null");
        html.Should().Contain("如果当前项目还没有可修复目标，请返回明确的前置条件提示，不要生成迭代计划");
        html.Should().Contain("continueSuggestedFeedback");
        html.Should().Contain("await executeIterationGoal()");
        html.Should().Contain("await submitIterationPlanFromFeedback(suggestion, \"正在生成迭代计划...\", \"completion_suggestion\")");
        html.Should().Contain("renderFeedbackRecords");
        html.Should().Contain("iterationGoalRecords");
        html.Should().Contain("goalRuns");
        html.Should().Contain("latestGoalRunByGoalId");
        html.Should().Contain("该目标尚未产出结果摘要");
        html.Should().Contain("该目标尚未关联执行记录");
        html.Should().NotContain("evidence.goal_id === goal.goalId");
        html.Should().NotContain("data-continue-suggestion");
        html.Should().NotContain("renderInlineContinueAction");
        html.Should().NotContain("inlineContinueActionLabelForMessage");
        html.Should().Contain("applyChatWorkflowActions");
        html.Should().Contain("继续当前迭代目标");
        html.Should().Contain("继续评估当前计划");
        html.Should().Contain("nextSuggestedFeedback");
        html.Should().Contain("continueConsumed");
        html.Should().Contain("suggestedFeedback");
        html.Should().Contain("defaultNextSuggestedFeedback");
        html.Should().Contain("updateContinueSuggestionFromText");
        html.Should().Contain("如果你同意|如你同意|若你同意");
        html.Should().Contain("如需执行，请使用迭代计划或 Needs Fix 的固定功能按钮。");
        html.Should().Contain("feedbackRecords");
        html.Should().Contain("流程记录");
        html.Should().Contain("feedbackSummary");
        html.Should().Contain("renderFeedbackSummary");
        html.Should().Contain("renderFeedbackPrimaryAction");
        html.Should().Contain("feedbackPrimaryActionState");
        html.Should().Contain("runFeedbackPrimaryAction");
        html.Should().Contain("feedbackPrimaryAction");
        html.Should().Contain("当前推荐动作");
        html.Should().Contain("来源：");
        html.Should().Contain("当前计划评估");
        html.Should().Contain("目标执行结果");
        html.Should().Contain("计划摘要");
        html.Should().Contain("总目标数");
        html.Should().Contain("已完成");
        html.Should().Contain("当前目标");
        html.Should().Contain("下一目标");
        html.Should().Contain("goal-card-current");
        html.Should().Contain("goal-card-next");
        html.Should().Contain("goal-badges");
        html.Should().Contain("goal-badge-current");
        html.Should().Contain("goal-badge-next");
        html.Should().Contain("goal-badge-succeeded");
        html.Should().Contain("goal-badge-running");
        html.Should().Contain("goal-badge-pending");
        html.Should().Contain("goal-badge-failed");
        html.Should().Contain("goal-badge-needs-fix");
        html.Should().Contain("iterationGoalMarkers");
        html.Should().Contain("normalizeGoalStatus");
        html.Should().Contain("statusLabel");
        html.Should().Contain("goalBadge");
        html.Should().Contain("进行中");
        html.Should().Contain("待执行");
        html.Should().Contain("失败");
        html.Should().Contain("需修复");
        html.Should().Contain("prototype-feedback-iterations");
        html.Should().Contain("formal-feedback-failed");
        html.Should().Contain("assistantMessage");
        html.Should().NotContain("skillActionPanel");
        html.Should().NotContain("skillActionSelect");
        html.Should().NotContain("runSkillAction");
        html.Should().Contain("/api/skill-actions");
        html.Should().Contain("chatSkillMode");
        html.Should().Contain("\u666e\u901a\u6a21\u5f0f");
        html.Should().Contain("skillActionId");
        html.Should().Contain("createIterationPlan");
        html.Should().Contain("evaluateIterationPlan");
        html.Should().Contain("buildIterationPlanEvaluationChatMessage");
        html.Should().Contain("resolveIterationPlanEvaluationSuggestedFeedback");
        html.Should().Contain("__iteration_plan_evaluate__");
        html.Should().Contain("__iteration_plan_execute_next__");
        html.Should().Contain("iteration-plan-evaluation");
        html.Should().Contain("$(\"evaluateIterationPlanFromChat\").onclick = () => evaluateIterationPlan(true);");
        html.Should().Contain("executeIterationGoal");
        html.Should().Contain("<button id=\"executeIterationGoal\" class=\"secondary\" data-global-action=\"true\">执行下一目标</button>");
        html.Should().Contain("$(\"executeIterationGoal\").disabled = hasNeedsFix");
        html.Should().Contain("? isGlobalBusy()");
        html.Should().Contain("iterationAutoRefreshHint");
        html.Should().Contain("await runNeedsFixIterationGoal(needsFixGoal.goalIndex);");
        html.Should().Contain("运行 Needs Fix 路由");
        html.Should().Contain("执行中会自动刷新进度");
        html.Should().Contain("iterationPlanStatus");
        html.Should().Contain("iterationPlanEvaluation");
        html.Should().Contain("iterationPlanGoals");
        html.Should().Contain("需要定制路线");
        html.Should().Contain("联系管理员创建定制游戏类型路线");
        html.Should().Contain("主流程：迭代计划");
        html.Should().Contain("评估当前迭代计划");
        html.Should().Contain("renderIterationPlanEvaluation");
        html.Should().Contain("页面建议：");
        html.Should().Contain("suggestedPromptForRegeneration");
        html.Should().Contain("根据评估更新迭代计划");
        html.Should().Contain("建议先重拆迭代计划");
        html.Should().Contain("提交反馈到 Needs Fix 路由");
        html.Should().NotContain("当前已有未完成计划，请先执行下一目标");
        html.Should().Contain("生成新的迭代计划");
        html.Should().NotContain("\"当前已有未完成计划\"");
        html.Should().NotContain("\"当前计划需先修复\"");
        html.Should().Contain("请先生成迭代计划");
        html.Should().Contain("当前没有待执行目标");
        html.Should().Contain("请先修复当前目标");
        html.Should().Contain("/iteration-plan");
        html.Should().Contain("/iteration-plan/evaluate");
        html.Should().Contain("const longLlmTimeoutMs = 1200 * 1000;");
        html.Should().Contain("failureCode: \"client_timeout\"");
        html.Should().Contain("timeoutMs: longLlmTimeoutMs");
        html.Should().Contain("/iteration-plan/execute-next");
        html.Should().Contain("loadIterationPlan");
        html.Should().Contain("renderIterationPlan");
        html.Should().Contain("submitIterationPlanFromFeedback");
        html.Should().Contain("iteration-plan-request");
        html.Should().Contain("iteration-plan-result");
        html.Should().Contain("await loadServerChatHistoryForProject(state.projectId);");
        html.Should().Contain("Codex");
        html.Should().Contain("/chat");
        html.Should().Contain("/api/projects");
        html.Should().Contain("prototype-7day-playable");
        html.Should().Contain("prototype-tdd");
        html.Should().Contain("loadAssetInventory");
        html.Should().Contain("assetInventoryStatus");
        html.Should().Contain("查看素材清单");
        html.Should().Contain("/assets?projectId=");
        html.Should().Contain("asset-inventory");
        html.Should().Contain("asset-preview");
        html.Should().Contain("final step 完成后才可以查看素材清单");
        html.Should().Contain("renderAssetInventory");
        html.Should().Contain("refreshAssetInventoryAvailability");
        html.Should().Contain("assetInventoryExpanded");
        html.Should().Contain("renderAssetInventory(state.assetInventory, state.assetInventoryExpanded)");
        html.Should().Contain("用途：");
        html.Should().Contain("asset-grid");
    }

    [Fact]
    public void RenderAssets_IncludesAssetInventoryPageAndPreviewTickets()
    {
        var html = new BrowserUiRenderer().RenderAssets();

        html.Should().Contain("Project Asset Library");
        html.Should().Contain("asset-inventory?judge=true");
        html.Should().Contain("asset-library");
        html.Should().Contain("asset-library/generate");
        html.Should().Contain("asset-library/select");
        html.Should().Contain("asset-preview-ticket");
        html.Should().Contain("createPreviewUrl");
        html.Should().Contain("hydrateLibraryPreviewUrls");
        html.Should().Contain("previewResourcePath");
        html.Should().Contain("previewUrl");
        html.Should().Contain("素材生成未完成");
        html.Should().Contain("floatingPrompt");
        html.Should().Contain("刷新素材库");
        html.Should().Contain("素材列表");
        html.Should().Contain("assetHistoryModal");
        html.Should().Contain("showAssetHistory");
        html.Should().Contain("openAssetDetail");
        html.Should().Contain("data-asset-detail-key");
        html.Should().Contain("data-select-unit-key");
        html.Should().Contain("addEventListener(\"click\"");
        html.Should().NotContain("onclick=");
        html.Should().NotContain("onchange=");
        html.Should().Contain("asset-detail-grid");
        html.Should().Contain("素材详情及替换");
        html.Should().Contain("image-to-image");
        html.Should().Contain("referenceImageFile");
        html.Should().Contain("assetGenerationCount");
        html.Should().Contain("readReferenceImagePayload");
        html.Should().Contain("generationMode");
        html.Should().Contain("selectEntry");
        html.Should().Contain("phaseA.assetLibrary");
        html.Should().Contain("已载入缓存素材库");
        html.Should().Contain("已刷新素材库");
        html.Should().Contain("assetPixelSize");
        html.Should().Contain("pixelWidth");
        html.Should().Contain("pixelHeight");
        html.Should().Contain("创建素材");
        html.Should().Contain("intendedUse");
    }

    [Fact]
    public void RenderAdminRunDurationMetrics_IncludesStandaloneMetricsPage()
    {
        var html = new BrowserUiRenderer().RenderAdminRunDurationMetrics();

        html.Should().Contain("普通用户 run 花费时间记录");
        html.Should().Contain("/api/admin/users");
        html.Should().Contain("/api/admin/run-metrics");
        html.Should().Contain("renderRunDurations");
        html.Should().Contain("queuePositionAtStart");
        html.Should().Contain("runTypeLabel");
        html.Should().Contain("返回控制台");
    }

    [Fact]
    public void RenderAdminChatAverageMetrics_IncludesStandaloneChatAveragePage()
    {
        var html = new BrowserUiRenderer().RenderAdminChatAverageMetrics();

        html.Should().Contain("普通用户聊天平均响应时长");
        html.Should().Contain("/api/admin/users");
        html.Should().Contain("/api/admin/run-metrics");
        html.Should().Contain("prototype-chat");
        html.Should().Contain("renderChatAverages");
        html.Should().Contain("averageRuntimeSeconds");
        html.Should().Contain("runTypeLabel");
        html.Should().Contain("style.display = \"none\"");
    }

    [Fact]
    public void RenderGddOutline_IncludesOutlineEditorFlow()
    {
        var html = new BrowserUiRenderer().RenderGddOutline();

        html.Should().Contain("/api/projects/${projectId}/gdd/outline");
        html.Should().Contain("/api/projects/${projectId}/gdd/outline/sections/${encodeURIComponent(selectedSection.id)}");
        html.Should().Contain("generateSection");
        html.Should().Contain("editorSkeleton");
        html.Should().Contain("editorContent");
        html.Should().Contain("editorMessage");
        html.Should().Contain("showModal");
        html.Should().Contain("exportGddMarkdown");
        html.Should().Contain("/api/projects/${projectId}/gdd/outline/export");
        html.Should().Contain("/downloads?projectId=");
    }

    [Fact]
    public void RenderDownloads_IncludesRobustPackageDownloadFlow()
    {
        var html = new BrowserUiRenderer().RenderDownloads();

        html.Should().Contain("项目文件下载");
        html.Should().Contain("下载准备中...");
        html.Should().Contain("download-ticket");
        html.Should().Contain("/api/projects/${encodeURIComponent(projectId)}/packages/${encodeURIComponent(fileName)}/download-ticket");
        html.Should().Contain("/api/projects/${projectId}/gdd/download-ticket");
        html.Should().Contain("下载 GDD.md");
        html.Should().Contain("cache: \"no-store\"");
        html.Should().NotContain("URL.createObjectURL");
        html.Should().Contain("下载失败：");
        html.Should().Contain("下载已提交给浏览器");
    }
}
