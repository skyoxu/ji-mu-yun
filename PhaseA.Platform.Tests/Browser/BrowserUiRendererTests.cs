using FluentAssertions;
using PhaseA.Platform.Browser;
using PhaseA.Platform.Data;
using PhaseA.Platform.Readback;
using System.Diagnostics;
using System.Text.RegularExpressions;
using Xunit;

namespace PhaseA.Platform.Tests.Browser;

public sealed class BrowserUiRendererTests
{
    [Fact]
    public void RenderShellV2_EmbeddedScriptsAreSyntacticallyValid()
    {
        var html = new BrowserUiRenderer().RenderShellV2();
        var scripts = Regex.Matches(html, "<script>([\\s\\S]*?)</script>")
            .Select(match => match.Groups[1].Value)
            .ToArray();
        scripts.Should().NotBeEmpty();

        var node = FindExecutableOnPath("node.exe") ?? FindExecutableOnPath("node");
        if (node is null)
        {
            return;
        }

        var scriptPath = Path.Combine(Path.GetTempPath(), $"phasea-shell-{Guid.NewGuid():N}.js");
        try
        {
            File.WriteAllText(scriptPath, string.Join("\n;\n", scripts));
            var startInfo = new ProcessStartInfo
            {
                FileName = node,
                RedirectStandardError = true,
                RedirectStandardOutput = true,
                UseShellExecute = false,
                CreateNoWindow = true
            };
            startInfo.ArgumentList.Add("--check");
            startInfo.ArgumentList.Add(scriptPath);
            using var process = Process.Start(startInfo);
            process.Should().NotBeNull();
            var checkedProcess = process!;
            checkedProcess.WaitForExit(10_000).Should().BeTrue();
            var output = checkedProcess.StandardOutput.ReadToEnd() + checkedProcess.StandardError.ReadToEnd();
            checkedProcess.ExitCode.Should().Be(0, output);
        }
        finally
        {
            if (File.Exists(scriptPath))
            {
                File.Delete(scriptPath);
            }
        }
    }

    [Fact]
    public void RenderShellV2_WorkflowIconAssetsAreIndividualTransparentSvgIcons()
    {
        foreach (var fileName in new[]
        {
            "workflow-panel.svg",
            "workflow-spark.svg",
            "workflow-wrench.svg",
            "workflow-list.svg",
            "workflow-layout.svg",
            "workflow-check.svg",
            "workflow-image.svg",
            "workflow-archive.svg",
            "workflow-download.svg"
        })
        {
            var path = Path.GetFullPath(Path.Combine(
                AppContext.BaseDirectory,
                "..",
                "..",
                "..",
                "..",
                "PhaseA.Platform",
                "wwwroot",
                "ui-v2",
                "icons",
                fileName));

            File.Exists(path).Should().BeTrue();
            new FileInfo(path).Length.Should().BeGreaterThan(0);
            var svg = File.ReadAllText(path);
            svg.Should().Contain("<svg");
            svg.Should().Contain("width=\"20\"");
            svg.Should().Contain("height=\"20\"");
            svg.Should().Contain("currentColor");
        }
    }

    [Fact]
    public void RenderShellV2_TabWorkspaceKeepsChatOpenAndWorkflowTabsClosable()
    {
        var html = new BrowserUiRenderer().RenderShellV2();

        html.Should().Contain("const v2OpenTabs = new Map([[\"chat\", { id: \"chat\", label: \"游戏策划创作\", panelId: \"chatPanel\", closable: false }]])");
        html.Should().Contain("v2OpenTabs.set(tabId, { id: tabId, label: v2StepLabel(stepId), panelId, stepId, closable: true })");
        html.Should().Contain("if (!tab || !tab.closable) return");
        html.Should().Contain("const activeTab = v2OpenTabs.get(v2ActiveTabId) || v2OpenTabs.get(\"chat\")");
        html.Should().Contain("if (activeTab?.panelId)");
    }

    [Fact]
    public void RenderShellV2_TabWorkspaceBehaviorSmoke()
    {
        var node = FindExecutableOnPath("node.exe") ?? FindExecutableOnPath("node");
        if (node is null)
        {
            return;
        }

        const string script = """
            let v2SelectedStep = "new-project";
            let v2UserSelectedStep = false;
            let v2ActiveTabId = "chat";
            let applied = 0;
            let renderedTabs = 0;
            let renderedProgress = 0;
            let refreshedAcceptance = 0;
            const actions = [];
            const v2Steps = [
              ["new-project", "Game Detail", 1],
              ["create-prototype", "Prototype", 2],
              ["iteration-plan", "Plan", 4]
            ];
            const v2OpenTabs = new Map([["chat", { id: "chat", label: "Chat", panelId: "chatPanel", closable: false }]]);
            function v2StepLabel(stepId) {
              const item = v2Steps.find(step => step[0] === stepId);
              return item ? item[1] : "Workspace";
            }
            function v2PanelForStep(stepId) {
              if (stepId === "new-project") return "currentProjectPanel";
              if (stepId === "create-prototype") return "prototypeWorkflowPanel";
              if (stepId === "iteration-plan") return "v2IterationPanel";
              return "currentProjectPanel";
            }
            function v2ApplySelectedStepVisibility() { applied += 1; }
            function v2RunStepAction(stepId) { actions.push(stepId); }
            function v2RenderTabs() { renderedTabs += 1; }
            function v2RenderProgress() { renderedProgress += 1; }
            function v2RefreshAcceptanceActionState() { refreshedAcceptance += 1; }
            function v2OpenStepTab(stepId) {
              const panelId = v2PanelForStep(stepId);
              const tabId = `step:${stepId}`;
              v2OpenTabs.set(tabId, { id: tabId, label: v2StepLabel(stepId), panelId, stepId, closable: true });
              v2ActiveTabId = tabId;
              v2SelectedStep = stepId;
              v2UserSelectedStep = true;
              v2ApplySelectedStepVisibility();
              v2RunStepAction(stepId);
              v2RenderTabs();
              v2RenderProgress();
              v2RefreshAcceptanceActionState();
            }
            function v2CloseTab(tabId) {
              const tab = v2OpenTabs.get(tabId);
              if (!tab || !tab.closable) return;
              v2OpenTabs.delete(tabId);
              if (v2ActiveTabId === tabId) {
                v2ActiveTabId = "chat";
              }
              v2RenderTabs();
              v2ApplySelectedStepVisibility();
            }
            function assert(condition, message) {
              if (!condition) throw new Error(message);
            }
            v2CloseTab("chat");
            assert(v2OpenTabs.has("chat"), "chat tab must not be closable");
            v2OpenStepTab("iteration-plan");
            assert(v2ActiveTabId === "step:iteration-plan", "workflow tab should become active");
            assert(v2OpenTabs.get("step:iteration-plan").panelId === "v2IterationPanel", "iteration panel mapping");
            assert(v2SelectedStep === "iteration-plan", "selected step should track opened tab");
            assert(v2UserSelectedStep === true, "manual selection flag should be set");
            assert(actions.length === 1 && actions[0] === "iteration-plan", "step action should run once");
            v2CloseTab("step:iteration-plan");
            assert(!v2OpenTabs.has("step:iteration-plan"), "closable workflow tab should close");
            assert(v2ActiveTabId === "chat", "closing active workflow tab returns to chat");
            assert(applied === 2 && renderedTabs === 2 && renderedProgress === 1 && refreshedAcceptance === 1, "render hooks should be invoked");
            """;

        RunNodeScript(node, script);
    }

    [Fact]
    public void RenderShellV2_TabWorkspaceDomBehaviorSmoke()
    {
        var node = FindExecutableOnPath("node.exe") ?? FindExecutableOnPath("node");
        if (node is null)
        {
            return;
        }

        const string script = """
            class ClassList {
              constructor() { this.items = new Set(); }
              add(value) { this.items.add(value); }
              remove(value) { this.items.delete(value); }
              contains(value) { return this.items.has(value); }
              toggle(value, force) {
                if (force === undefined) {
                  if (this.items.has(value)) this.items.delete(value);
                  else this.items.add(value);
                  return this.items.has(value);
                }
                if (force) this.items.add(value);
                else this.items.delete(value);
                return !!force;
              }
            }
            class Element {
              constructor(id) {
                this.id = id;
                this.classList = new ClassList();
                this.dataset = {};
                this.value = "";
                this.src = "";
              }
            }
            const elements = new Map();
            function add(id) {
              const element = new Element(id);
              elements.set(id, element);
              return element;
            }
            [
              "chatPanel",
              "v2IterationPanel",
              "v2RepairPanel",
              "v2UiOptimizationPanel",
              "v2AcceptancePanel",
              "v2AssetInventoryFramePanel",
              "v2DownloadsFramePanel",
              "v2GddOutlineFramePanel",
              "currentProjectPanel",
              "prototypeWorkflowPanel",
              "prototypeCommandPanel",
              "runsPanel",
              "outputPanel",
              "v2AssetInventoryFrame",
              "v2DownloadsFrame",
              "v2GddOutlineFrame",
              "globalModel"
            ].forEach(add);
            elements.get("globalModel").value = "gpt-5.5";
            const $ = id => elements.get(id) || null;
            const state = { projectId: "project 1" };
            let v2ActiveTabId = "chat";
            let v2SelectedStep = "new-project";
            let v2UserSelectedStep = false;
            let renderedTabs = 0;
            let renderedProgress = 0;
            let refreshedAcceptance = 0;
            const v2Steps = [
              ["new-project", "游戏项目概述", 1],
              ["asset-inventory", "项目素材库", 7],
              ["download-project", "打包下载项目", 8]
            ];
            const v2OpenTabs = new Map([["chat", { id: "chat", label: "游戏策划创作", panelId: "chatPanel", closable: false }]]);
            function v2StepLabel(stepId) {
              const item = v2Steps.find(step => step[0] === stepId);
              return item ? item[1] : "工程页面";
            }
            function v2PanelForStep(stepId) {
              if (stepId === "new-project") return "currentProjectPanel";
              if (stepId === "asset-inventory") return "v2AssetInventoryFramePanel";
              if (stepId === "download-project") return "v2DownloadsFramePanel";
              if (stepId === "gdd-outline") return "v2GddOutlineFramePanel";
              return "currentProjectPanel";
            }
            function v2RenderTabs() { renderedTabs += 1; }
            function v2RenderProgress() { renderedProgress += 1; }
            function v2RefreshAcceptanceActionState() { refreshedAcceptance += 1; }
            function v2LoadEmbeddedFrame(frameId, url) {
              const frame = $(frameId);
              if (!frame) return;
              if (frame.dataset.src !== url) {
                frame.dataset.src = url;
                frame.src = url;
              }
            }
            function v2ApplySelectedStepVisibility() {
              const show = id => $(id)?.classList.remove("hidden");
              const hide = id => $(id)?.classList.add("hidden");
              ["v2IterationPanel", "v2RepairPanel", "v2UiOptimizationPanel", "v2AcceptancePanel", "v2AssetInventoryFramePanel", "v2DownloadsFramePanel", "v2GddOutlineFramePanel", "currentProjectPanel", "prototypeWorkflowPanel", "prototypeCommandPanel", "runsPanel", "outputPanel"].forEach(hide);
              hide("chatPanel");
              const activeTab = v2OpenTabs.get(v2ActiveTabId) || v2OpenTabs.get("chat");
              if (activeTab?.id === "chat") {
                show("chatPanel");
                return;
              }
              if (activeTab?.panelId) {
                show(activeTab.panelId);
              }
            }
            function v2RunStepAction(stepId) {
              if (!state.projectId) return;
              if (stepId === "asset-inventory") {
                v2LoadEmbeddedFrame("v2AssetInventoryFrame", `/assets?projectId=${encodeURIComponent(state.projectId)}&model=${encodeURIComponent($("globalModel").value || "gpt-5.5")}&embedded=1`);
                return;
              }
              if (stepId === "download-project") {
                v2LoadEmbeddedFrame("v2DownloadsFrame", `/downloads?projectId=${encodeURIComponent(state.projectId)}&embedded=1`);
                return;
              }
              if (stepId === "gdd-outline") {
                v2LoadEmbeddedFrame("v2GddOutlineFrame", `/gdd-outline?projectId=${encodeURIComponent(state.projectId)}&embedded=1`);
              }
            }
            function v2OpenEmbeddedTab(tabId, label, panelId, frameId, url) {
              v2OpenTabs.set(tabId, { id: tabId, label, panelId, closable: true });
              v2ActiveTabId = tabId;
              v2ApplySelectedStepVisibility();
              v2LoadEmbeddedFrame(frameId, url);
              v2RenderTabs();
              v2RenderProgress();
            }
            function v2OpenStepTab(stepId) {
              const panelId = v2PanelForStep(stepId);
              const tabId = `step:${stepId}`;
              v2OpenTabs.set(tabId, { id: tabId, label: v2StepLabel(stepId), panelId, stepId, closable: true });
              v2ActiveTabId = tabId;
              v2SelectedStep = stepId;
              v2UserSelectedStep = true;
              v2ApplySelectedStepVisibility();
              v2RunStepAction(stepId);
              v2RenderTabs();
              v2RenderProgress();
              v2RefreshAcceptanceActionState();
            }
            function v2CloseTab(tabId) {
              const tab = v2OpenTabs.get(tabId);
              if (!tab || !tab.closable) return;
              v2OpenTabs.delete(tabId);
              if (v2ActiveTabId === tabId) {
                v2ActiveTabId = "chat";
              }
              v2RenderTabs();
              v2ApplySelectedStepVisibility();
            }
            function assert(condition, message) {
              if (!condition) throw new Error(message);
            }
            function visible(id) {
              return !$(id).classList.contains("hidden");
            }

            v2ApplySelectedStepVisibility();
            assert(visible("chatPanel"), "default chat tab should be visible");
            assert(!visible("v2AssetInventoryFramePanel"), "asset panel should start hidden");

            v2OpenStepTab("asset-inventory");
            assert(v2ActiveTabId === "step:asset-inventory", "asset inventory tab should become active");
            assert(v2SelectedStep === "asset-inventory" && v2UserSelectedStep, "asset inventory step selection should be tracked");
            assert(visible("v2AssetInventoryFramePanel"), "asset iframe panel should be visible");
            assert(!visible("chatPanel"), "chat panel should hide when asset tab is active");
            assert($("v2AssetInventoryFrame").src === "/assets?projectId=project%201&model=gpt-5.5&embedded=1", "asset iframe should use embedded URL");

            v2OpenStepTab("download-project");
            assert(visible("v2DownloadsFramePanel"), "downloads iframe panel should be visible");
            assert(!visible("v2AssetInventoryFramePanel"), "asset panel should hide when downloads tab is active");
            assert($("v2DownloadsFrame").src === "/downloads?projectId=project%201&embedded=1", "downloads iframe should use embedded URL");

            v2OpenEmbeddedTab("gdd-outline", "查阅策划大纲", "v2GddOutlineFramePanel", "v2GddOutlineFrame", "/gdd-outline?projectId=project%201&embedded=1");
            assert(v2OpenTabs.get("gdd-outline").label === "查阅策划大纲", "GDD outline tab should use readable label");
            assert(visible("v2GddOutlineFramePanel"), "GDD outline panel should be visible");
            assert($("v2GddOutlineFrame").dataset.src === "/gdd-outline?projectId=project%201&embedded=1", "GDD iframe should cache embedded URL");

            v2CloseTab("gdd-outline");
            assert(v2ActiveTabId === "chat", "closing active embedded tab should return to chat");
            assert(visible("chatPanel"), "chat should be visible again");
            assert(!visible("v2GddOutlineFramePanel"), "GDD panel should be hidden after closing tab");
            assert(renderedTabs === 4 && renderedProgress === 3 && refreshedAcceptance === 2, "render hooks should match tab operations");
            """;

        RunNodeScript(node, script);
    }

    [Fact]
    public void RenderShellV2_PublicChatSanitizerRemovesPlatformRoutes()
    {
        var node = FindExecutableOnPath("node.exe") ?? FindExecutableOnPath("node");
        if (node is null)
        {
            return;
        }

        const string script = """
            function sanitizePublicChatContent(value) {
              const gddLinks = [];
              return String(value || "")
                .replace(/\/projects\/[^\s`'"，。；：、）)<]+\/gdd\/GDD\.md\?ticket=[^\s`'"，。；：、）)<]+/g, match => {
                  const token = `__PHASEA_GDD_LINK_${gddLinks.length}__`;
                  gddLinks.push(match);
                  return token;
                })
                .replace(/(?:本轮目标：|本轮任务：|Direction lock:|方向锁定：|Project README:|Project Execution Guide:|Recovery source consumed:|已读取恢复来源：|Current goal:|当前任务：|Previous platform rejection:|上一轮平台拒绝：|Task repair ledger:|任务修复台账：|User feedback:|用户反馈：|Scope rule:|范围规则：)[\s\S]*$/gi, "")
                .replace(/(?<![\w])[A-Za-z]:[\\/][^\s`'"，。；：、）)]+/g, "[路径已隐藏]")
                .replace(/\bres:\/\/[^\s`'"，。；：、）)<]+/gi, "[路径已隐藏]")
                .replace(/\/(?:gdd-outline|assets|downloads|runs|projects|admin|api|account)(?:\/[^\s`'"，。；：、）)<]*)?(?:\?[^\s`'"，。；：、）)<]*)?/gi, "")
                .replace(/\b(?:projectId|runId|accountId|ticket|embedded)=[^\s`'"，。；：、）)<]+/gi, "")
                .replace(/(?<![\w.:/])\/(?:[A-Za-z0-9._-]+\/)+[A-Za-z0-9._-]+/g, "[路径已隐藏]")
                .replace(/(?<![\w])(?:[A-Za-z0-9_.-]+[\\/]){1,}[A-Za-z0-9_.-]+/g, "[路径已隐藏]")
                .replace(/(?<![\w.-])[\w.-]+\.(?:ps1|cmd|bat|sh|py|cs|csproj|sln|json|toml|yaml|yml|md|log|txt|tscn|tres|res|gd|png|jpg|jpeg|webp|svg|ogg|wav|mp3|ttf|otf|import|dll|exe|pdb|cache|sqlite|sqlite3|db|zip)(?::\d+(?::\d+)?)?(?![\w.-])/gi, "[文件已隐藏]")
                .replace(/^\s*(?:&\s*)?(?:(?:dotnet\s+(?:test|run|build|publish|restore))|(?:py(?:thon)?\s+[-\w.\/\\])|(?:powershell(?:\.exe)?\s+[-/]\w+)|(?:cmd(?:\.exe)?\s+\/[ck])|(?:codex(?:\.cmd)?\s+(?:exec|run|review|--|-))|(?:caddy(?:\.exe)?\s+(?:run|reload|fmt|--|-))|(?:git\s+\w+)|(?:rg\s+.+)|(?:node\s+.+)|(?:npm\s+\w+))[^\r\n]*/gim, "")
                .replace(/\b(?:logs\/ci|logs\\ci|active-prototypes|workspaces|GODOT_BIN|PHASEA_[A-Z0-9_]+)\b[^\r\n，。；]*/gi, "")
                .replace(/\b(?:Game\.Godot|Tests\.Godot|Game\.Core(?:\.Tests)?|PhaseA\.Platform(?:\.Tests)?|GodotGame)\b/gi, "[模块已隐藏]")
                .replace(/__PHASEA_GDD_LINK_(\d+)__/g, (_, index) => gddLinks[Number(index)] || "")
                .replace(/(?:\[(?:路径已隐藏|文件已隐藏|模块已隐藏)\]\s*){2,}/g, "[详情已隐藏] ")
                .replace(/[ \t]{2,}/g, " ")
                .replace(/\n{3,}/g, "\n\n")
                .trim();
            }
            function assert(condition, message) {
              if (!condition) throw new Error(message);
            }
            const sanitized = sanitizePublicChatContent("查阅策划大纲：/gdd-outline?projectId=406cd69e993c44c3850490b403b7f024&embedded=1");
            assert(!sanitized.includes("/gdd-outline"), "platform route should be hidden");
            assert(!sanitized.includes("projectId="), "platform query should be hidden");
            const link = "/projects/demo/gdd/GDD.md?ticket=abc123";
            assert(sanitizePublicChatContent(`下载：${link}`).includes(link), "GDD download links should stay visible");
            const godot = sanitizePublicChatContent("Godot path res://Game/Scenes/Main.tscn and Main.cs:12");
            assert(!godot.includes("res://Game/Scenes/Main.tscn"), "Godot resource paths should be hidden");
            assert(!godot.includes("Main.cs"), "file names should be hidden");
            assert(godot.includes("[路径已隐藏]"), "path placeholder should remain");
            const chineseRoute = sanitizePublicChatContent("用户可见摘要\n方向锁定：\n- 内部规则\n当前任务：secret");
            assert(chineseRoute === "用户可见摘要", "Chinese route context should be truncated");
            const chineseLedger = sanitizePublicChatContent("本轮结论\n任务修复台账：\n- hidden");
            assert(chineseLedger === "本轮结论", "Chinese repair ledger should be truncated");
            """;

        RunNodeScript(node, script);
    }

    [Fact]
    public void RenderShellV2_ProgressStatusUsesSuccessfulUiOptimizationAndServerAcceptance()
    {
        var node = FindExecutableOnPath("node.exe") ?? FindExecutableOnPath("node");
        if (node is null)
        {
            return;
        }

        const string script = """
            const state = {
              projectId: "project-1",
              runs: [
                {
                  runType: "prototype-ui-optimization",
                  status: "failed",
                  progressSubstep: "validation_failed",
                  progressUpdatedUtc: "2026-06-09T07:01:39.4240706+00:00",
                  runId: "old"
                },
                {
                  runType: "prototype-ui-optimization",
                  status: "succeeded",
                  progressSubstep: "completed",
                  progressUpdatedUtc: "2026-06-09T07:05:39.4240706+00:00",
                  runId: "new"
                },
                {
                  runType: "prototype-7day-playable",
                  status: "succeeded",
                  evidenceJson: "{\"validation_only\":true}",
                  progressUpdatedUtc: "2026-06-09T07:06:39.4240706+00:00",
                  runId: "acceptance-new"
                }
              ],
              prototypeFailure: "",
              v2PrototypeStatus: "succeeded",
              v2PrototypeCreationStatus: "succeeded",
              v2PrototypeValidationInvalidatedByIteration: false,
              iterationPlan: {
                session: {
                  updatedUtc: "2026-06-05T07:43:48.7541844+00:00",
                  completedUtc: "2026-06-05T07:43:48.7541716+00:00"
                },
                goals: [{ status: "succeeded", updatedUtc: "2026-06-05T07:43:48.7541844+00:00" }]
              }
            };
            const elements = new Map([["prototypeProgress", { textContent: "succeeded" }]]);
            const $ = id => elements.get(id) || null;
            function v2IsoTime(value) {
              const time = Date.parse(value || "");
              return Number.isFinite(time) ? time : 0;
            }
            function v2RunTimestamp(run) {
              return v2IsoTime(run?.finishedUtc || run?.progressUpdatedUtc || run?.startedUtc || run?.createdUtc || "");
            }
            function v2LatestRunByType(runType) {
              return (state.runs || [])
                .filter(run => String(run.runType || "").toLowerCase() === String(runType || "").toLowerCase())
                .sort((a, b) => v2RunTimestamp(b) - v2RunTimestamp(a) || String(b.runId || "").localeCompare(String(a.runId || "")))[0] || null;
            }
            function v2RunEvidence(run) {
              if (!run) return null;
              const evidence = run.evidenceJson ?? run.evidence ?? null;
              if (!evidence) return null;
              if (typeof evidence === "object") return evidence;
              try { return JSON.parse(String(evidence)); } catch { return null; }
            }
            function v2IsValidationOnlyRun(run) {
              const evidence = v2RunEvidence(run);
              return evidence?.validation_only === true;
            }
            function v2LatestValidationOnlyAcceptanceRun() {
              return (state.runs || [])
                .filter(run => String(run.runType || "").toLowerCase() === "prototype-7day-playable" && v2IsValidationOnlyRun(run))
                .sort((a, b) => v2RunTimestamp(b) - v2RunTimestamp(a) || String(b.runId || "").localeCompare(String(a.runId || "")))[0] || null;
            }
            function v2IterationSessionTimestamp() {
              const session = state.iterationPlan?.session || null;
              const goals = Array.isArray(state.iterationPlan?.goals) ? state.iterationPlan.goals : [];
              const goalTime = Math.max(0, ...goals.map(goal => v2IsoTime(goal.completedUtc || goal.updatedUtc || goal.createdUtc || "")));
              return goalTime || v2IsoTime(session?.completedUtc || session?.updatedUtc || session?.createdUtc || "");
            }
            function v2RunIsCurrentForIteration(run) {
              if (!run) return false;
              const sessionTime = v2IterationSessionTimestamp();
              if (!sessionTime) return true;
              const runTime = v2IsoTime(run.progressUpdatedUtc || run.updatedUtc || run.completedUtc || run.createdUtc || "");
              return runTime >= sessionTime;
            }
            function v2IterationPlanDone() {
              const goals = Array.isArray(state.iterationPlan?.goals) ? state.iterationPlan.goals : [];
              return goals.length > 0 && goals.every(goal => ["succeeded", "completed"].includes(String(goal.status || "").trim().toLowerCase()));
            }
            function v2FinalPrototypeAcceptanceRun() {
              const run = v2LatestValidationOnlyAcceptanceRun();
              if (!run || String(run.status || "").toLowerCase() !== "succeeded") return null;
              if (!v2IterationPlanDone()) return null;
              return v2RunIsCurrentForIteration(run) ? run : null;
            }
            function v2StepStatus(stepId) {
              const progressStatus = state?.prototypeFailure ? "failed" : "";
              const progressText = $("prototypeProgress")?.textContent || "";
              const prototypeStatus = String(state?.v2PrototypeStatus || "").trim().toLowerCase();
              const creationStatus = String(state?.v2PrototypeCreationStatus || prototypeStatus || "").trim().toLowerCase();
              const succeeded = prototypeStatus === "succeeded";
              const failed = prototypeStatus === "failed" || progressStatus === "failed" || !!state?.prototypeFailure;
              if (stepId === "create-prototype") {
                if (!state.projectId || progressText.includes("idle") || !creationStatus) return "pending";
                return creationStatus === "failed" ? "fix" : creationStatus === "succeeded" ? "done" : "pending";
              }
              if (stepId === "prototype-acceptance") {
                if (state.v2PrototypeValidationInvalidatedByIteration) return "pending";
                if (v2FinalPrototypeAcceptanceRun()) return "done";
                const validationRun = v2LatestValidationOnlyAcceptanceRun();
                if (validationRun && v2RunIsCurrentForIteration(validationRun) && String(validationRun.status || "").toLowerCase() === "failed") return "fix";
                return failed && v2IterationPlanDone() ? "fix" : "pending";
              }
              if (stepId === "ui-optimization") {
                const run = v2LatestRunByType("prototype-ui-optimization");
                if (!run) return "pending";
                const substep = String(run.progressSubstep || "").toLowerCase();
                if (substep === "validation_skipped") return "pending";
                if (substep === "validation_failed") return "fix";
                if (String(run.status || "").toLowerCase() === "succeeded") return "done";
                if (String(run.status || "").toLowerCase() === "failed") return "fix";
                return "pending";
              }
              return "pending";
            }
            function assert(condition, message) {
              if (!condition) throw new Error(message);
            }
            assert(v2StepStatus("ui-optimization") === "done", "successful UI optimization should be done");
            assert(v2StepStatus("prototype-acceptance") === "done", "successful server acceptance should be done");
            state.runs = state.runs.filter(run => run.runId !== "acceptance-new");
            assert(v2StepStatus("prototype-acceptance") === "pending", "prototype creation acceptance alone should not complete final acceptance");
            state.v2PrototypeValidationInvalidatedByIteration = true;
            assert(v2StepStatus("prototype-acceptance") === "pending", "local invalidation should still block until server progress clears it");
            """;

        RunNodeScript(node, script);
    }

    [Fact]
    public void RenderShellV2_WorkflowPanelsDoNotMoveChatContent()
    {
        var node = FindExecutableOnPath("node.exe") ?? FindExecutableOnPath("node");
        if (node is null)
        {
            return;
        }

        const string script = """
            const nodes = new Map();
            function createElement(tagName, id = "") {
              const element = {
                tagName: String(tagName || "").toUpperCase(),
                id,
                className: "",
                children: [],
                parentElement: null,
                textContent: "",
                attributes: {},
                setAttribute(name, value) { this.attributes[name] = value; },
                appendChild(child) {
                  if (!child) return child;
                  if (child.parentElement) {
                    child.parentElement.children = child.parentElement.children.filter(item => item !== child);
                  }
                  child.parentElement = this;
                  this.children.push(child);
                  if (child.id) nodes.set(child.id, child);
                  return child;
                },
                insertAdjacentElement(position, child) {
                  const parent = this.parentElement;
                  if (!parent || position !== "afterend") return this.appendChild(child);
                  if (child.parentElement) {
                    child.parentElement.children = child.parentElement.children.filter(item => item !== child);
                  }
                  const index = parent.children.indexOf(this);
                  child.parentElement = parent;
                  parent.children.splice(index + 1, 0, child);
                  if (child.id) nodes.set(child.id, child);
                  return child;
                },
                querySelectorAll(selector) {
                  const wanted = selector.toUpperCase();
                  const found = [];
                  function walk(item) {
                    item.children.forEach(child => {
                      if (child.tagName === wanted) found.push(child);
                      walk(child);
                    });
                  }
                  walk(this);
                  return found;
                }
              };
              Object.defineProperty(element, "innerHTML", {
                set(value) {
                  this.children = [];
                  if (String(value || "").includes("v2IterationSummary")) {
                    this.appendChild(createElement("div", "v2IterationSummary"));
                  }
                },
                get() { return ""; }
              });
              if (id) nodes.set(id, element);
              return element;
            }
            const document = { createElement };
            const $ = id => nodes.get(id) || null;
            const root = createElement("main", "root");
            const chatPanel = createElement("section", "chatPanel");
            root.appendChild(chatPanel);
            function add(tag, id, text = "") {
              const element = createElement(tag, id);
              element.textContent = text;
              chatPanel.appendChild(element);
              return element;
            }
            add("h2", "chatTitle", "自由对话");
            add("h2", "iterationHeading", "主流程：游戏模块");
            ["createIterationPlan", "evaluateIterationPlan", "deleteIterationPlan", "executeIterationGoal", "iterationAutoRefreshHint", "iterationPlanStatus", "iterationPlanEvaluation", "iterationNeedsFixStatus", "iterationPlanGoals"].forEach(id => add(id === "iterationAutoRefreshHint" ? "p" : "div", id));
            add("h2", "repairHeading", "异常修复计划");
            ["createRepairPlan", "executeRepairStep", "repairPlanStatus", "repairPlanGoals"].forEach(id => add("div", id));
            add("h2", "chatRecordHeading", "聊天记录");
            add("div", "chatHistory");
            add("label", "chatAttachmentLabel");
            add("button", "sendChat");

            function v2ArrangeIterationPanel() {
              v2CreateRepairPanel();
            }
            function v2ValidatePrototypeIfAllowed() {}
            function v2CreateIterationPanel() {
              if ($("v2IterationPanel")) return;
              const chatPanel = $("chatPanel");
              if (!chatPanel) return;
              const panel = document.createElement("section");
              panel.id = "v2IterationPanel";
              panel.className = "stack hidden";
              panel.setAttribute("aria-label", "游戏模块");
              panel.innerHTML = `<div id="v2IterationSummary" class="card muted">尚未生成游戏模块。</div>`;
              chatPanel.insertAdjacentElement("afterend", panel);
              [
                "createIterationPlan",
                "evaluateIterationPlan",
                "deleteIterationPlan",
                "executeIterationGoal",
                "iterationAutoRefreshHint",
                "iterationPlanStatus",
                "iterationPlanEvaluation",
                "iterationNeedsFixStatus",
                "iterationPlanGoals"
              ].map($).filter(Boolean).forEach(element => panel.appendChild(element));
              v2ArrangeIterationPanel();
            }
            function v2CreateRepairPanel() {
              if ($("v2RepairPanel")) return;
              const createRepair = $("createRepairPlan");
              if (!createRepair) return;
              const panel = document.createElement("section");
              panel.id = "v2RepairPanel";
              panel.className = "stack hidden";
              $("v2IterationPanel").insertAdjacentElement("afterend", panel);
              const actions = document.createElement("div");
              actions.id = "v2RepairActions";
              actions.className = "v2-action-row";
              panel.appendChild(actions);
              const skeletonAcceptance = document.createElement("button");
              skeletonAcceptance.id = "v2SkeletonAcceptance";
              skeletonAcceptance.className = "secondary";
              skeletonAcceptance.type = "button";
              skeletonAcceptance.textContent = "骨架验收";
              skeletonAcceptance.onclick = v2ValidatePrototypeIfAllowed;
              [createRepair, $("executeRepairStep"), skeletonAcceptance].filter(Boolean).forEach(button => actions.appendChild(button));
              ["repairPlanStatus", "repairPlanGoals"].map($).filter(Boolean).forEach(element => panel.appendChild(element));
            }
            function assert(condition, message) {
              if (!condition) throw new Error(message);
            }
            v2CreateIterationPanel();
            assert($("chatHistory").parentElement === chatPanel, "chat history must stay in chat panel");
            assert($("sendChat").parentElement === chatPanel, "send button must stay in chat panel until composer arranges it");
            assert($("createIterationPlan").parentElement.id === "v2IterationPanel", "iteration controls move to iteration panel");
            assert($("repairPlanGoals").parentElement.id === "v2RepairPanel", "repair goals move to repair panel");
            assert($("createRepairPlan").parentElement.id === "v2RepairActions", "repair action moves to repair actions");
            """;

        RunNodeScript(node, script);
    }

    [Fact]
    public void RenderShellV2_IncludesProgressComparisonPage()
    {
        var html = new BrowserUiRenderer().RenderShellV2();

        html.Should().Contain("Game Ren");
        html.Should().Contain("<title>Game Ren</title>");
        html.Should().Contain("document.title = isAdmin ? \"Game Ren Admin\" : \"Game Ren\"");
        html.Should().Contain("document.title = \"Game Ren\"");
        html.Should().NotContain("<title>积木云 Phase A 原型控制台</title>");
        html.Should().NotContain("Phase A Prototype Console");
        html.Should().Contain("v2ProgressShell");
        html.Should().Contain("v2ProgressSteps");
        html.Should().Contain("v2ContentGrid");
        html.Should().Contain("v2EnsureContentGrid");
        html.Should().Contain("position: fixed");
        html.Should().Contain("inset: 80px 0 0 0");
        html.Should().Contain("top: 0");
        html.Should().Contain("body { padding-top: 80px; }");
        html.Should().Contain("grid-template-columns: minmax(15rem, 25%) minmax(0, 75%)");
        html.Should().Contain("grid-template-rows: minmax(0, 1fr)");
        html.Should().Contain("align-items: stretch");
        html.Should().Contain("height: 100vh");
        html.Should().Contain("overflow: hidden");
        html.Should().Contain("height: 100%");
        html.Should().Contain("height: 100%");
        html.Should().Contain("v2LeftRail");
        html.Should().Contain("overflow-y: auto");
        html.Should().Contain("overflow-y: scroll");
        html.Should().Contain("scrollbar-gutter: stable");
        html.Should().Contain("grid-template-rows: minmax(10rem, 34%) minmax(0, 1fr)");
        html.Should().Contain("overscroll-behavior: contain");
        html.Should().Contain("align-self: stretch");
        html.Should().Contain("-webkit-mask: var(--step-icon)");
        html.Should().Contain("mask: var(--step-icon)");
        html.Should().NotContain("image-rendering: pixelated");
        html.Should().Contain("v2RightWorkspace");
        html.Should().Contain("v2WorkspaceTabs");
        html.Should().Contain("v2OpenStepTab");
        html.Should().Contain("phaseA.projectUiState.v");
        html.Should().Contain("const v2ProjectUiStateVersion = 2;");
        html.Should().Contain("v2ReadProjectUiState");
        html.Should().Contain("function v2LegacyProjectUiStateKey(projectId = state.projectId)");
        html.Should().Contain("function v2NormalizeProjectUiState(cached)");
        html.Should().Contain("legacyCached");
        html.Should().Contain("function v2BuildProjectUiStateSeed(projectId = state.projectId)");
        html.Should().Contain("function v2EnsureProjectUiStateSeed(projectId = state.projectId)");
        html.Should().Contain("function v2ChooseProjectUiStateSource(...sources)");
        html.Should().Contain("v2ChooseProjectUiStateSource(remote, cached)");
        html.Should().Contain("schemaVersion: v2ProjectUiStateVersion");
        html.Should().Contain("v2WriteProjectUiState");
        html.Should().Contain("v2RestoreProjectUiState");
        html.Should().Contain("v2LoadProjectUiStateTabState(source)");
        html.Should().Contain("v2RestoredProjectUiStateId = \"\"");
        html.Should().Contain("if (state.projectId && state.projectId !== projectId)");
        html.Should().Contain("state.projectId && !currentProjectVisible");
        html.Should().Contain("v2ActiveTabId = \"chat\";");
        html.Should().Contain("v2SelectedStep = \"new-project\";");
        html.Should().Contain("v2RenderTabs();");
        html.Should().Contain("if (state.cancelledActiveRunId || readCancelledPrototypeMarker()) return false;");
        html.Should().Contain("window.addEventListener(\"beforeunload\", () =>");
        html.Should().Contain("callV2(\"v2WriteProjectUiState\")");
        html.Should().NotContain("window.addEventListener(\"beforeunload\", v2WriteProjectUiState)");
        html.Should().Contain("function v2EmbeddedTabUrl(tab)");
        html.Should().Contain("function v2EmbeddedFrameId(tab)");
        html.Should().Contain("if (tab.id === \"step:asset-inventory\") return \"v2AssetInventoryFrame\"");
        html.Should().Contain("if (tab.id === \"step:download-project\") return \"v2DownloadsFrame\"");
        html.Should().Contain("url: v2EmbeddedTabUrl({ id, frameId })");
        html.Should().Contain("const activeTab = v2OpenTabs.get(v2ActiveTabId)");
        html.Should().Contain("v2SelectedStep = activeTab.stepId");
        html.Should().Contain("frameId: tab.frameId || \"\"");
        html.Should().Contain("url: tab.url || \"\"");
        html.Should().Contain("advancedPlanningMode");
        html.Should().Contain("chatSkillMode");
        html.Should().Contain("projectAnalysisMode: !!state.projectAnalysisMode");
        html.Should().Contain("v2PendingProjectUiSkillMode");
        html.Should().Contain("select.value = v2PendingProjectUiSkillMode");
        html.Should().Contain("function v2ShowChatTab()");
        html.Should().Contain("v2WriteProjectUiState();");
        html.Should().Contain("gap: 0");
        html.Should().Contain("background: #e2e0dc");
        html.Should().Contain("border-radius: 0.65rem 0.65rem 0 0");
        html.Should().Contain("border-bottom-color: #fffdf8");
        html.Should().Contain("font-weight: 800");
        html.Should().Contain("body.v2-detail .v2-tab.active > span:first-child");
        html.Should().Contain("position: sticky");
        html.Should().Contain("v2AppendOnce");
        html.Should().Contain("if (!parent || !element || element.parentElement === parent) return");
        html.Should().Contain("v2-left-project-button ${current ? \"current\" : \"\"}");
        html.Should().Contain("v2AppendOnce(grid, element)");
        html.Should().Contain("v2JudgeNextStep");
        html.Should().Contain("nextStepButton.textContent = \"下一步建议\"");
        html.Should().Contain("nextStepButton.title = \"扫描当前项目状态，并在聊天窗口显示系统下一步建议\"");
        html.Should().Contain("advancedPlanning, projectAnalysis, nextStepButton");
        html.Should().NotContain("v2NextSuggestion");
        html.Should().NotContain("v2-next");
        html.Should().NotContain("扫描项目判断下一步建议");
        html.Should().Contain("正在扫描项目状态");
        html.Should().Contain("v2ShowChatTab");
        html.Should().Contain("startChatThinkingMessage(\"正在扫描项目状态...\")");
        html.Should().NotContain("系统扫描结果：");
        html.Should().Contain("workflow-route");
        html.Should().Contain("buildWorkflowRouteChatContent");
        html.Should().Contain("renderWorkflowRouteAction");
        html.Should().Contain("function v2RunTimestamp(run)");
        html.Should().Contain("v2RenderUiOptimizationStatus");
        html.Should().Contain("游戏界面优化已完成，短验证已通过");
        html.Should().Contain("左侧进度栏已标记为完成");
        html.Should().Contain("workflowRouteActionConsumed");
        html.Should().NotContain("withTimeout(loadProjectPackages(), \"packages\")");
        html.Should().NotContain("已基于当前缓存状态生成建议");
        html.Should().Contain("workflowRouteFailureMessage(error)");
        html.Should().Contain("项目状态扫描失败：登录状态无效，请重新输入登录 token。");
        html.Should().Contain("项目状态扫描失败：当前项目不可访问，请刷新项目列表后重新选择项目。");
        html.Should().Contain("项目状态扫描失败：项目状态读取异常，请稍后重试或联系管理员查看后台记录。");
        html.Should().NotContain("调用 LLM 判断下一步");
        html.Should().NotContain("v2NextSuggestionHasLlmResult");
        html.Should().Contain("推荐页面：${actions.map(action => action.runName || action.label || action.actionId).join(\"、\")}");
        html.Should().Contain("系统不会自动启动 run。需要你点击下方一次性按钮打开对应页面，再在页面内确认执行。");
        html.Should().NotContain("workflow_route_queried");
        html.Should().NotContain("function v2Suggestion()");
        html.Should().NotContain("dataset.llmPinned");
        html.Should().Contain("function v2StepIconUrl(iconName)");
        html.Should().Contain("return `/ui-v2/icons/workflow-${safe}.svg`");
        html.Should().Contain("原型工程列表");
        html.Should().Contain("项目列表");
        html.Should().Contain("body.v2-detail #currentProjectPanel > button { display: none; }");
        html.Should().Contain("v2RunStepAction");
        html.Should().Contain("let v2UserSelectedStep = false");
        html.Should().Contain("function v2ApplySelectedStepVisibility()");
        html.Should().Contain("function v2SelectDefaultStepForPrototypeProgress(progress)");
        html.Should().Contain("function v2OpenStepTab(stepId, runAction = true)");
        html.Should().Contain("button.onclick = () => v2ShowStep(button.dataset.v2Step, true)");
        html.Should().Contain("v2AcceptancePanel");
        html.Should().Contain("v2CreateAcceptancePanel");
        html.Should().Contain("原型项目验收结果");
        html.Should().Contain("重新触发原型项目验收");
        html.Should().Contain("rerun.onclick = v2ValidatePrototypeIfAllowed");
        html.Should().Contain("skeletonAcceptance.onclick = v2ValidatePrototypeIfAllowed");
        html.Should().Contain("v2PrototypeAcceptanceBlockReason");
        html.Should().Contain("v2AcceptanceActionStatus");
        html.Should().Contain("await validatePrototype();");
        html.Should().Contain("v2IterationPlanAllowsAcceptance");
        html.Should().Contain("请先完成当前游戏模块，所有任务完成后再进行原型项目验收。");
        html.Should().Contain("游戏界面优化是可选步骤，不会阻塞验收。");
        html.Should().NotContain("请先完成游戏界面优化，再进行原型项目验收。");
        html.Should().NotContain("if (stepId === \"prototype-acceptance\") {\n                    $(\"validatePrototype\")?.click();");
        html.Should().NotContain("[\"revalidate-prototype\", \"重新验收\"]");
        html.Should().Contain("v2AssetInventoryFramePanel");
        html.Should().Contain("v2DownloadsFramePanel");
        html.Should().Contain("v2GddOutlineFramePanel");
        html.Should().Contain("v2LoadEmbeddedFrame(\"v2AssetInventoryFrame\"");
        html.Should().Contain("v2LoadEmbeddedFrame(\"v2DownloadsFrame\"");
        html.Should().Contain("v2LoadEmbeddedFrame(\"v2GddOutlineFrame\"");
        html.Should().Contain("embedded=1");
        html.Should().Contain("v2OpenEmbeddedTab");
        html.Should().Contain("if (typeof v2OpenStepTab === \"function\")");
        html.Should().Contain("v2OpenStepTab(\"download-project\")");
        html.Should().Contain("v2OpenStepTab(\"asset-inventory\")");
        html.Should().NotContain("$(\"createProjectPackage\")?.click()");
        html.Should().Contain("v2ApplyPrototypeFormLock");
        html.Should().Contain("v2ShouldLockPrototypeForm");
        html.Should().Contain("v2-prototype-locked");
        html.Should().Contain("setPrototypeDraftFileLocked(locked);");
        html.Should().Contain("setButtonDisabledState($(\"importDraft\"), locked");
        html.Should().Contain("原型骨架已创建，不能重复创建");
        html.Should().Contain("setPrototypeFormLocked = function(locked)");
        html.Should().Contain("v2ApplyPrototypeFormSnapshot");
        html.Should().Contain("progress?.form");
        html.Should().NotContain("已载入原型记录");
        html.Should().Contain("游戏原型ID");
        html.Should().Contain("prototype-draft-row");
        html.Should().Contain("updateDraftImportButtonState");
        html.Should().Contain("$(\"draftFile\").onchange = updateDraftImportButtonState");
        html.Should().Contain("projectStateCacheKey");
        html.Should().Contain("applyProjectStateCache(projectId)");
        html.Should().Contain("/api/projects/${encodeURIComponent(projectId)}/ui-state");
        html.Should().Contain("async function v2FetchProjectUiState(projectId = state.projectId)");
        html.Should().Contain("async function v2WriteProjectUiState()");
        html.Should().Contain("state.iterationPlan = null;");
        html.Should().Contain("state.iterationPlans = [];");
        html.Should().Contain("state.selectedIterationSessionId = \"\";");
        html.Should().Contain("const projectStateCacheVersion = 2;");
        html.Should().Contain("function normalizeIterationPlanRounds(rounds)");
        html.Should().Contain("normalizeIterationPlanRounds(Array.isArray(result?.rounds) ? result.rounds : [])");
        html.Should().Contain("normalizeIterationPlanRounds(Array.isArray(cached.iterationPlans) ? cached.iterationPlans : [])");
        html.Should().Contain("writeProjectStateCache({ prototypeProgress: progress })");
        html.Should().Contain("writeProjectStateCache({ packageList: result })");
        html.Should().Contain("writeProjectStateCache({ assetInventory: result })");
        html.Should().Contain("await loadProjectPackages();");
        html.Should().Contain("renderRunsListFromState");
        html.Should().NotContain("if (v2SelectedStep === \"create-prototype\") $(\"prototypeWorkflowPanel\")?.classList.remove(\"hidden\")");
        html.Should().Contain("[\"create-prototype\", \"原型骨架创建\", \"spark\"]");
        html.Should().Contain("v2-step-number");
        html.Should().Contain(".v2-step-number { display: inline-flex;");
        html.Should().NotContain(".v2-step-number { display: none;");
        html.Should().Contain("<span class=\"v2-step-icon\"></span><span class=\"v2-step-number\">${index + 1}.</span>");
        html.Should().Contain("<span class=\"v2-step-label\">${label}</span>");
        html.Should().Contain("v2StepIconUrl(iconName)");
        html.Should().Contain("--step-icon:url");
        html.Should().NotContain("spriteIndex");
        html.Should().Contain(".v2-step-button.pending .v2-step-mark");
        html.Should().Contain(".v2-step-button.action .v2-step-mark");
        html.Should().Contain("游戏项目概述");
        html.Should().Contain("原型骨架创建");
        html.Should().Contain("创建游戏模块");
        html.Should().Contain("骨架验收修复");
        html.Should().Contain("游戏界面优化");
        html.IndexOf("[\"execute-or-repair\", \"骨架验收修复\", \"wrench\"]", StringComparison.Ordinal).Should().BeLessThan(html.IndexOf("[\"iteration-plan\", \"创建游戏模块\", \"list\"]", StringComparison.Ordinal));
        html.IndexOf("[\"iteration-plan\", \"创建游戏模块\", \"list\"]", StringComparison.Ordinal).Should().BeLessThan(html.IndexOf("[\"ui-optimization\", \"游戏界面优化\", \"layout\"]", StringComparison.Ordinal));
        html.Should().Contain("function v2RunIsCurrentForIteration(run)");
        html.Should().Contain("const sessionTime = v2IterationSessionTimestamp();");
        html.Should().Contain("const goalTime = Math.max(0, ...goals.map(goal => v2IsoTime(goal.completedUtc || goal.updatedUtc || goal.createdUtc || \"\")));");
        html.Should().Contain("if (!run) return \"pending\";");
        html.Should().NotContain("if (!run || !v2RunIsCurrentForIteration(run)) return \"pending\";");
        html.Should().Contain("if (substep === \"validation_skipped\") return \"pending\";");
        html.Should().Contain("if (substep === \"validation_failed\") return \"fix\";");
        html.Should().Contain("请先完成原型骨架创建，再运行游戏界面优化。");
        html.Should().Contain("v2RepairPanel");
        html.Should().Contain("v2CreateRepairPanel");
        html.Should().Contain("const goals = state.repairPlan?.goals || []");
        html.Should().Contain("if (failed) return \"fix\";");
        html.Should().Contain("if (!goals.length && v2HasPrototypeSkeleton()) return \"done\";");
        html.Should().Contain("项目素材库");
        html.Should().Contain("打包项目文件");
        html.Should().Contain("打包下载项目");
        html.Should().Contain("if (stepId === \"new-project\") return state.projectId ? \"done\" : \"pending\"");
        html.Should().Contain("if (stepId === \"iteration-plan\") {");
        html.Should().Contain("return \"continue\"");
        html.Should().Contain("•••");
        html.Should().Contain("function v2AssetInventoryConfirmed()");
        html.Should().Contain("if (stepId === \"asset-inventory\") return v2AssetInventoryConfirmed() ? \"done\" : \"pending\"");
        html.Should().Contain("if (stepId === \"download-project\") return v2HasPackages() ? \"done\" : \"pending\"");
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
        html.Should().Contain("v2IterationSummary");
        html.Should().Contain("游戏模块摘要");
        html.Should().NotContain("panel.appendChild(current)");
        html.Should().Contain("\"iterationPlanGoals\"");
        html.Should().Contain("\"repairPlanGoals\"");
        html.Should().Contain("\"createRepairPlan\"");
        html.Should().Contain("function v2PanelForStep(stepId)");
        html.Should().Contain("if (stepId === \"iteration-plan\") return \"v2IterationPanel\"");
        html.Should().Contain("if (activeTab?.panelId)");
        html.Should().Contain("show(activeTab.panelId)");
        html.Should().Contain("closable: false");
        html.Should().Contain("if (!tab || !tab.closable) return");
        html.Should().Contain("v2ArrangeChatPanel");
        html.Should().Contain("v2ChatControls");
        html.Should().Contain("v2ChatComposer");
        html.Should().Contain("v2-chat-composer");
        html.Should().Contain("resizeChatComposer");
        html.Should().Contain("v2SkillRow");
        html.Should().Contain("v2AdvancedPlanningMode");
        html.Should().Contain("高级策划模式");
        html.Should().Contain("game-design-master");
        html.Should().Contain("激活高级策划模式，帮助梳理玩法、GDD、机制、叙事与原型设计建议");
        html.Should().Contain("body.v2-detail #chatSkillDescription");
        html.Should().Contain("display: none !important");
        html.Should().Contain("body.v2-detail #chatPanel > h2");
        html.Should().Contain("body.v2-detail #chatPanel #feedbackSummary");
        html.Should().Contain("body.v2-detail #chatPanel #feedbackRecords");
        html.Should().Contain("display: none !important");
        html.Should().Contain("function v2HideLegacyChatFeedback()");
        html.Should().Contain("[\"自由聊天\", \"自由对话\", \"聊天记录\"].includes");
        html.Should().Contain("v2InstallFastTooltips");
        html.Should().Contain("setTimeout(() =>");
        html.Should().Contain("}, 120)");
        html.Should().Contain("v2-fast-tooltip");
        html.Should().Contain("body.v2-detail #chatPanel { min-height: 100%; height: 100%; display: grid; grid-template-rows: minmax(0, 1fr) auto");
        html.Should().Contain("body.v2-detail #chatHistory.chat-scroll { min-height: 0; max-height: none; height: 100%; overflow-y: auto; }");
        html.Should().Contain(".import-draft-button.import-draft-ready:not(:disabled)");
        html.Should().Contain("button.button-state-enabled");
        html.Should().Contain("button.button-state-disabled");
        html.Should().Contain("button[disabled]");
        html.Should().Contain("opacity: 0.45 !important");
        html.Should().Contain("background-color: #9ca3af !important");
        html.Should().Contain("v2-skill-row");
        html.Should().Contain("skillDescription");
        html.Should().NotContain("v2CreateIterationPlanFromChat");
        html.Should().Contain("iterationPlanUpdateModal");
        html.Should().Contain(".modal-card > .stack { min-height: 0; max-height: calc(min(90vh, 54rem) - 2rem); overflow-y: auto;");
        html.Should().Contain("#iterationPlanUpdateModal .modal-card > .stack { max-height: calc(100vh - 4rem); }");
        html.Should().Contain("confirmIterationPlanUpdate");
        html.Should().Contain("deleteIterationPlan");
        html.Should().Contain("[createPlan, evaluatePlan, executeGoal, deletePlan]");
        html.Should().Contain("删除当前轮游戏模块");
        html.Should().Contain("该操作不会删除其他轮次");
        html.Should().Contain("/iteration-plans/${encodeURIComponent(sessionId)}");
        html.Should().Contain("重新生成游戏模块");
        html.Should().Contain("创建新的游戏模块");
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
        html.Should().Contain("v2-file-button");
        html.Should().Contain("attachLabel.className = \"ghost v2-file-button\"");
        html.Should().Contain("\\u5bfc\\u5165\\u6587\\u4ef6");
        html.Should().Contain("attachLabel.title = \"导入 TXT 参考文件\"");
        html.Should().Contain("未导入 TXT 参考文件，只支持 TXT 文件导入。");
        html.Should().Contain("id=\"clearChatAttachments\" class=\"ghost hidden\"");
        html.Should().Contain("最多只能导入 5 个 TXT 参考文件。");
        html.Should().Contain("clearChatAttachments();");
        html.Should().Contain("v2ProjectAnalysisMode");
        html.Should().Contain("项目分析模式");
        html.Should().Contain("系统会扫描项目进度后回复问题，速度慢，可以使用下一步建议按钮替代");
        html.Should().Contain("projectAnalysisMode: false");
        html.Should().Contain("function v2ToggleProjectAnalysisMode()");
        html.Should().Contain("function v2RenderProjectAnalysisMode()");
        html.Should().Contain("if (state.projectAnalysisMode)");
        html.Should().Contain("function recentChatHistoryForLlm()");
        html.Should().Contain("message.kind !== \"workflow-route\"");
        html.Should().Contain("history: recentChatHistoryForLlm()");
        html.Should().NotContain("history: state.chatHistory.slice(-3)");
        html.Should().NotContain("history: state.chatHistory.slice(-10)");
        html.Should().Contain("记录已下载。");
        html.Should().Contain("createGddDocument");
        html.Should().Contain("/api/projects/${state.projectId}/gdd");
        html.Should().Contain("gddOutlineUrl");
        html.Should().Contain("v2OpenGddOutlineTab");
        html.Should().Contain("v2OpenEmbeddedTab(");
        html.Should().Contain("查阅策划大纲");
        html.Should().Contain("if (!state.projectId) return out(\"请先选择一个项目。\")");
        html.Should().Contain("`/gdd-outline?projectId=${encodeURIComponent(state.projectId)}&embedded=1`");
        html.Should().Contain("Array.isArray(outlineStatus?.sections) && outlineStatus.sections.length > 0");
        html.Should().Contain("download=\"GDD.md\"");
        html.Should().Contain("result.downloadUrl || \"\"");
        html.Should().Contain("\\u521b\\u5efa\\u7b56\\u5212\\u5927\\u7eb2\\u5931\\u8d25");
        html.Should().Contain("kind: \"gdd-result\"");
        html.Should().Contain("__PHASEA_GDD_LINK_");
        html.Should().Contain("v2CanCreateIterationPlanFromChat");
        html.Should().Contain("v2IterationPlanExists");
        html.Should().Contain("v2IterationPlanCompleted");
        html.Should().Contain("v2PrototypeValidationPassedForPlanning");
        html.Should().Contain("result?.status === \"ready\" && state.iterationPlan?.session");
        html.Should().Contain("v2SetPrototypeValidationInvalidated(true)");
        html.Should().Contain("v2SetPrototypeValidationInvalidated(false)");
        html.Should().Contain("if (acceptanceStatus === \"succeeded\")");
        html.Should().Contain("phaseA:v2PrototypeValidationInvalidated");
        html.Should().Contain("$(\"submitFormalFeedback\")?.classList.add(\"hidden\")");
        html.Should().NotContain("根据聊天内容创建新的游戏模块");
        html.Should().Contain("openIterationPlanUpdateModal");
        html.Should().Contain("confirmIterationPlanUpdate");
        html.Should().Contain("请输入第二轮游戏模块目标。");
        html.Should().Contain("mode === \"new\" && !typedMessage");
        html.Should().Contain("v2IterationRoundTabs");
        html.Should().Contain("v2-round-tab");
        html.Should().Contain("/iteration-plans");
        html.Should().Contain("selectIterationPlanForDisplay");
        html.Should().Contain("isDisplayingLatestIterationPlan");
        html.Should().Contain("第 ${Number(plan?.roundIndex || index + 1)} 轮");
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
        html.Should().Contain("function v2HandleChatMessageKeydown(event)");
        html.Should().Contain("if (event.key !== \"Enter\" || event.shiftKey");
        html.Should().Contain("if (!$(\"sendChat\")?.disabled) sendChat();");
        html.Should().Contain("const localWorkflowRouteEntries = state.chatHistory");
        html.Should().Contain("function mergeLocalWorkflowRouteMessages(serverMessages, localWorkflowRouteEntries)");
        html.Should().Contain("merged.splice(previousIndex + 1, 0, entry.message);");
        html.Should().Contain("merged.splice(nextIndex, 0, entry.message);");
        html.Should().Contain("renderChatHistory");
        html.Should().Contain("/api/projects/${state.projectId}/workflow-route");
        html.Should().Contain("/api/projects/${state.projectId}/workflow-route/intent");
        html.Should().Contain("queryWorkflowRoute");
        html.Should().Contain("runWorkflowRecommendedAction");
        html.Should().Contain("function workflowRouteActions(route)");
        html.Should().Contain("route?.actions");
        html.Should().Contain("workflowActions: actions");
        html.Should().Contain("data-workflow-route-action-id");
        html.Should().Contain("actions.map(action =>");
        html.Should().Contain("runWorkflowRecommendedAction(button.dataset.workflowRouteActionToken, button.dataset.workflowRouteActionId || \"\")");
        html.Should().Contain("function v2OpenStepTab(stepId, runAction = true)");
        html.Should().Contain("if (runAction) v2RunStepAction(stepId)");
        html.Should().Contain("v2OpenStepTab(\"create-prototype\", false)");
        html.Should().Contain("v2OpenStepTab(\"execute-or-repair\", false)");
        html.Should().Contain("v2OpenStepTab(\"iteration-plan\", false)");
        html.Should().Contain("openIterationPlanUpdateModal(\"new\")");
        html.Should().Contain("v2OpenStepTab(\"ui-optimization\", false)");
        html.Should().NotContain("await runPrototype();");
        html.Should().NotContain("await createIterationPlan();");
        html.Should().NotContain("await runUiOptimization();");
        html.Should().NotContain("await createProjectPackage();");
        html.Should().NotContain("openIterationPlanUpdateModal(\"new\", message.workflowIntent?.feedbackSummary || \"\")");
        html.Should().Contain("data-workflow-route-action-token");
        html.Should().Contain("workflowActionToken");
        html.Should().Contain("进度已变更");
        html.Should().Contain("const consumed = !!message.workflowActionConsumed || state.workflowRouteActionToken !== message.workflowActionToken;");
        html.Should().NotContain("!!message.workflowActionConsumed || state.workflowRouteActionConsumed || state.workflowRouteActionToken !== message.workflowActionToken");
        html.Should().Contain("系统不会自动启动 run");
        html.Should().NotContain("触发原因：");
        html.Should().Contain("invalidateWorkflowRouteAction");
        html.Should().Contain("restoreWorkflowRouteActionFromHistory");
        html.Should().Contain("state.workflowRouteActionToken = latest.workflowActionToken");
        html.Should().Contain("fetchWorkflowRoute(message.workflowIntent)");
        html.Should().Contain("workflowActionsMatch");
        html.Should().Contain("项目进度已经变化，请重新点击");
        html.Should().Contain("无法确认当前项目进度，请重新点击");
        html.Should().Contain("if (message.workflowActionConsumed || state.workflowRouteActionToken !== token) return;");
        html.Should().Contain("let shouldClearChatAttachments = false;");
        html.Should().Contain("shouldClearChatAttachments = true;");
        html.Should().Contain("if (shouldClearChatAttachments) clearChatAttachments();");
        html.Should().NotContain("invalidateWorkflowRouteAction();\n                  switch (action.actionId)");
        html.Should().Contain("if (busy) invalidateWorkflowRouteAction();");
        html.IndexOf("if (routeIntent?.shouldRoute)", StringComparison.Ordinal).Should().BeLessThan(html.IndexOf("const result = await api(`/api/projects/${state.projectId}/chat`", StringComparison.Ordinal));
        html.Should().Contain("nextStepButton.onclick = () => queryWorkflowRoute()");
        html.Should().NotContain("v2BuildLocalNextStepSuggestion");
        html.Should().NotContain("v2JudgeNextStepLocally");
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
        html.Should().Contain("detail-step-number\">8</span>");
        html.Should().Contain("打包下载项目");
        html.Should().Contain("detail-step pending");
        html.Should().NotContain("detail-step fix");
        html.Should().NotContain("detail-step done\" href=\"/#prototypeWorkflowPanel\"");
        html.Should().NotContain("detail-step done\" href=\"/assets?projectId=project-1\"");
        html.Should().NotContain("detail-step done\" href=\"/#createProjectPackage\"");
    }

    [Fact]
    public void RenderProject_MarksSkeletonRepairDone_WhenPrototypeCreationSucceededWithoutRepair()
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
        var prototypeRun = new RunReadbackItem(
            "run-prototype",
            "project-1",
            "workspace-1",
            "prototype-7day-playable",
            "succeeded",
            0,
            "",
            "",
            "{}",
            "succeeded",
            "strict_headless_main_menu_navigation",
            "Prototype creation completed.",
            DateTimeOffset.UtcNow.ToString("O"),
            null,
            null,
            null,
            null,
            []);

        var html = new BrowserUiRenderer().RenderProject(project, [prototypeRun]);

        html.Should().Contain("detail-step done\" href=\"/#prototypeWorkflowPanel\"");
        html.Should().Contain("detail-step done\" href=\"/#v2RepairPanel\"");
        html.Should().NotContain("detail-step fix\" href=\"/#v2RepairPanel\"");
        html.Should().Contain("detail-step pending\" href=\"/#v2AcceptancePanel\"");
        html.Should().NotContain("detail-step done\" href=\"/#v2AcceptancePanel\"");
    }

    [Fact]
    public void RenderProject_MarksFinalAcceptanceDone_OnlyAfterValidationOnlyRunFollowsIteration()
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
        var iterationRun = new RunReadbackItem(
            "run-iteration",
            "project-1",
            "workspace-1",
            "prototype-iteration-goal",
            "succeeded",
            0,
            "",
            "",
            "{}",
            "completed",
            "",
            "Iteration completed.",
            "2026-06-09T07:05:39.4240706+00:00",
            null,
            null,
            null,
            null,
            []);
        var oldValidation = new RunReadbackItem(
            "run-old-validation",
            "project-1",
            "workspace-1",
            "prototype-7day-playable",
            "succeeded",
            0,
            "",
            "",
            "{\"validation_only\":true}",
            "succeeded",
            "",
            "Old validation.",
            "2026-06-09T07:01:39.4240706+00:00",
            null,
            null,
            null,
            null,
            []);
        var newValidation = oldValidation with
        {
            RunId = "run-new-validation",
            ProgressUpdatedUtc = "2026-06-09T07:06:39.4240706+00:00"
        };

        var oldHtml = new BrowserUiRenderer().RenderProject(project, [iterationRun, oldValidation]);
        oldHtml.Should().Contain("detail-step pending\" href=\"/#v2AcceptancePanel\"");
        oldHtml.Should().NotContain("detail-step done\" href=\"/#v2AcceptancePanel\"");

        var newHtml = new BrowserUiRenderer().RenderProject(project, [iterationRun, newValidation]);
        newHtml.Should().Contain("detail-step done\" href=\"/#v2AcceptancePanel\"");
    }

    [Fact]
    public void RenderProject_MarksDownloadDone_WhenPackageExists()
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
        var packageRun = new RunReadbackItem(
            "run-package",
            "project-1",
            "workspace-1",
            "project-package",
            "succeeded",
            0,
            "",
            "",
            "{}",
            "",
            "",
            "",
            DateTimeOffset.UtcNow.ToString("O"),
            null,
            null,
            null,
            null,
            []);

        var html = new BrowserUiRenderer().RenderProject(project, [packageRun]);

        html.Should().Contain("detail-step done\" href=\"/downloads?projectId=project-1\"");
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

        html.Should().Contain("Game Ren");
        html.Should().NotContain("Phase A Prototype Console");
        html.Should().Contain("activeRunBanner");
        html.Should().Contain("<div id=\"activeRunBanner\" class=\"busy-banner hidden\" role=\"status\" aria-live=\"polite\"></div>");
        html.Should().Contain("#activeRunBanner");
        html.Should().Contain(".busy-banner");
        html.Should().Contain("position: absolute");
        html.Should().Contain("top: 0;");
        html.Should().Contain("left: 50%;");
        html.Should().Contain("transform: translateX(-50%)");
        html.Should().Contain("pointer-events: none;");
        html.Should().Contain(".busy-banner > span,");
        html.Should().Contain(".busy-banner .busy-banner-lines,");
        html.Should().Contain(".busy-banner .busy-banner-actions,");
        html.Should().Contain("user-select: text;");
        html.Should().Contain(".busy-banner button");
        html.Should().Contain("pointer-events: auto;");
        html.Should().Contain("max-height: 100px");
        html.Should().Contain("height: 100px");
        html.Should().Contain("border-radius: 0 0 0.9rem 0.9rem");
        html.Should().Contain(".busy-banner button");
        html.Should().Contain("width: auto;");
        html.Should().Contain("white-space: nowrap;");
        html.Should().Contain("role=\"status\" aria-live=\"polite\"");
        html.Should().Contain("/api/account/active-run");
        html.Should().Contain("cancelActiveRun");
        html.Should().Contain("function canCancelActiveRun(run)");
        html.Should().Contain("function runIsBusy(run)");
        html.Should().Contain("if (!run.runId) return false;");
        html.Should().Contain("status === \"queued\" || status === \"running\"");
        html.Should().Contain("state.cancelledActiveRunId && activeRun?.runId === state.cancelledActiveRunId");
        html.Should().Contain("writeCancelledPrototypeMarker(runId);");
        html.Should().Contain("writeProjectStateCache({ prototypeProgress: cancelledPrototypeProgressSnapshot() });");
        html.Should().Contain("state.v2PrototypeCreationStatus = \"idle\";");
        html.Should().Contain("if (!activeRun?.runId)");
        html.Should().Contain("function hideActiveRunBanner()");
        html.Should().Contain("function setButtonVisualState(button, enabled)");
        html.Should().Contain("function setButtonBaseClass(button, baseClassName)");
        html.Should().Contain("function cancelledPrototypeProgressSnapshot()");
        html.Should().Contain("function cancelledPrototypeMarkerKey(projectId = state.projectId)");
        html.Should().Contain("function writeCancelledPrototypeMarker(runId)");
        html.Should().Contain("function readCancelledPrototypeMarker(projectId = state.projectId)");
        html.Should().Contain("function setPrototypeDraftFileLocked(locked)");
        html.Should().Contain("function setButtonDisabledState(button, disabled, title = \"\")");
        html.Should().Contain("function resetPrototypeActionButtonsVisualState()");
        html.Should().Contain("function unlockPrototypeFormAfterCancel()");
        html.Should().Contain("unlockPrototypeFormAfterCancel();");
        html.Should().Contain("setButtonBaseClass($(\"runPrototype\"), \"secondary\");");
        html.Should().Contain("setButtonBaseClass($(\"importDraft\"), \"secondary import-draft-button\");");
        html.Should().Contain("button.classList.remove(\"button-state-enabled\", \"button-state-disabled\", \"import-draft-ready\");");
        html.Should().Contain("if ([\"queued\", \"running\"].includes(creationStatus))");
        html.Should().Contain("if (state.cancelledActiveRunId || readCancelledPrototypeMarker())");
        html.Should().Contain("if ($(\"draftFile\")) $(\"draftFile\").disabled = true;");
        html.Should().Contain("button.classList.toggle(\"button-state-enabled\", !!enabled);");
        html.Should().Contain("button.classList.toggle(\"button-state-disabled\", !enabled);");
        html.Should().Contain("busy-banner-actions");
        html.Should().Contain("取消任务");
        html.Should().Contain("startedAtMs: Math.max(0, state.prototypeSkeletonBannerStartedAtMs || 0)");
        html.Should().Contain("function prototypeSkeletonRunStartedAtMs(run)");
        html.Should().Contain("prototypeSkeletonRunStartedAtMs(run) || prototypeSkeletonNowMs()");
        html.Should().Contain("runCreatedUtc: state.pendingPrototypeSkeletonRun?.createdUtc || state.activeRun?.createdUtc || \"\"");
        html.Should().Contain("runStartedUtc: state.pendingPrototypeSkeletonRun?.startedUtc || state.activeRun?.startedUtc || \"\"");
        html.Should().Contain("cachedRunTime");
        html.Should().Contain("function prototypeSkeletonDisplayCountFromStartedAt(startedAtMs)");
        html.Should().Contain("Math.floor(elapsedMs / 20000) + 1");
        html.Should().Contain("const changed = syncPrototypeSkeletonBannerDisplayedCount();");
        html.Should().Contain("function prototypeSkeletonBannerStorageKey(runId = state.prototypeSkeletonBannerRunId)");
        html.Should().Contain("function prototypeSkeletonBannerCurrentKey()");
        html.Should().Contain("function prototypeSkeletonBannerStoredRunId()");
        html.Should().Contain("restorePrototypeSkeletonBannerFromStorage();");
        html.Should().Contain("void refreshActiveRun();");
        html.Should().Contain("state.pendingPrototypeSkeletonRun = {");
        html.Should().Contain("const skeletonRun = skeletonBannerRun() || state.pendingPrototypeSkeletonRun;");
        html.Should().Contain("hasPendingPrototypeSkeletonBannerRun()");
        html.Should().Contain("state.pendingPrototypeSkeletonRun.status = state.pendingPrototypeSkeletonRun.status || \"running\";");
        html.Should().Contain("busy: runIsBusy(run)");
        html.Should().Contain("if (!runIsBusy(run))");
        html.Should().Contain("localStorage.setItem(prototypeSkeletonBannerCurrentKey(), state.prototypeSkeletonBannerRunId);");
        html.Should().Contain("readPrototypeSkeletonBannerState(run.runId)");
        html.Should().Contain("writePrototypeSkeletonBannerState()");
        html.Should().Contain("function prototypeSkeletonVisibleNotes()");
        html.Should().Contain("function prototypeSkeletonBannerNotes()");
        html.Should().Contain("state.prototypeSkeletonBannerExpanded ? notes : notes.slice(Math.max(0, notes.length - 2))");
        html.Should().Contain("function scrollPrototypeSkeletonNotesToBottom(container)");
        html.Should().Contain("container.scrollTop = container.scrollHeight");
        html.Should().Contain("busy-banner-note-window");
        html.Should().Contain("pointer-events: auto;");
        html.Should().NotContain("prototypeSkeletonBannerLine2(run)");
        html.Should().NotContain("??????ID?");
        html.Should().Contain("state.pendingPrototypeSkeletonRun = state.activeRun;");
        html.Should().NotContain("state.prototypeSkeletonBannerIndex + 22");
        html.Should().NotContain("if (state.prototypeSkeletonBannerExpanded) return;");
        html.Should().Contain("!state.pendingPrototypeSkeletonRun?.runId && !prototypeSkeletonBannerStoredRunId()");
        html.Should().Contain("\"chapter2-bootstrap\", \"project-creation\", \"project-asset-generation\", \"asset-generation\"");
        html.Should().Contain("/api/runs/${encodeURIComponent(runId)}/cancel");
        html.Should().Contain("当前任务执行中");
        html.Should().Contain("guardGlobalAction");
        html.Should().Contain("data-global-action");
        html.Should().Contain("删除中...");
        html.Should().Contain("setInterval(refreshActiveRun, 5000)");
        html.Should().Contain("Access token");
        html.Should().Contain("phaseAAccessToken");
        html.Should().Contain("let sessionValidated = false");
        html.Should().Contain("sessionValidated = true");
        html.Should().Contain("if (!sessionValidated)");
        html.Should().Contain("if (error?.status === 401 || error?.status === 403)");
        html.Should().Contain("Token 已验证。项目状态刷新失败，请稍后重试。");
        html.Should().Contain("function persistAccessTokenFromInput()");
        html.Should().Contain("function readBrowserCookie(name)");
        html.Should().Contain("function writeBrowserCookie(name, value, maxAgeSeconds)");
        html.Should().Contain("function clearBrowserCookie(name)");
        html.Should().NotContain("sessionDiagnostics");
        html.Should().NotContain("function updateSessionDiagnostics(reason = \"\")");
        html.Should().NotContain("登录诊断：${location.origin}");
        html.Should().NotContain("window.addEventListener(\"error\"");
        html.Should().Contain("setTimeout(() =>");
        html.Should().NotContain("autofill_empty");
        html.Should().Contain("$(\"token\").addEventListener(\"input\", persistAccessTokenFromInput)");
        html.Should().Contain("$(\"token\").addEventListener(\"change\", persistAccessTokenFromInput)");
        html.Should().Contain("Token 已保留");
        html.Should().Contain("busy-banner-prototype-skeleton");
        html.Should().Contain("展开详细信息");
        html.Should().Contain("关闭详细信息");
        html.Should().Contain("系统正在进行游戏原型骨架创建工作，其中可能存在的信息延迟或显示遗漏但不影响实际进程；");
        html.Should().Contain("projectName");
        html.Should().Contain("projectNameError");
        html.Should().Contain("gameNameError");
        html.Should().Contain("gameTypeSourceError");
        html.Should().Contain("createProjectValidation");
        html.Should().Contain("validateCreateProjectForm");
        html.Should().Contain("setCreateProjectFieldError");
        html.Should().Contain("输入信息过少");
        html.Should().Contain("请输入游戏名称");
        html.Should().Contain("请输入参考游戏类型或游戏名称");
        html.Should().Contain("游戏类型/玩法方向");
        html.Should().Contain("Roguelike");
        html.Should().NotContain("打开完整 project-health 页面");
        html.Should().Contain("createProjectPanel");
        html.Should().Contain("projectDetailPanel");
        html.Should().Contain("currentProjectPanel");
        html.Should().Contain("initStatusPanel");
        html.Should().Contain("pollProjectInitializationResult");
        html.Should().Contain(@"const createdProjectId = result.projectId || result.ProjectId || """";");
        html.Should().Contain("if (createdProjectId) {");
        html.Should().NotContain("selectProject(createdProjectId)");
        html.Should().Contain("showInitialization(\"running\", \"\")");
        html.Should().Contain("await pollProjectInitializationResult(createdProjectId, creationAttemptStartedAt)");
        html.Should().Contain("await refreshProjects({ autoSelect: false })");
        html.Should().Contain("isProjectCreationFailureForAttempt(latestFailure, createdProjectId, attemptStartedAt)");
        html.Should().Contain("function isProjectReady(project)");
        html.Should().Contain("function isProjectPendingInitialization(project)");
        html.Should().Contain("const createdProject = projects.find(project => project.projectId === createdProjectId)");
        html.Should().Contain("if (isProjectReady(createdProject))");
        html.Should().Contain("selectProject(createdProject.projectId)");
        html.Should().Contain("if (createdProjectId && isProjectPendingInitialization(createdProject))");
        html.Should().Contain("projectCreationErrorMessage");
        html.Should().Contain("project_initialization_in_progress");
        html.Should().Contain("project_quota_exceeded");
        html.Should().Contain("project_creation_failed");
        html.Should().Contain(@"$(""projectDetailPanel"").classList.add(""hidden"")");
        html.Should().Contain(@"$(""chatPanel"").classList.add(""hidden"")");
        html.Should().Contain("showLoggedOut");
        html.Should().Contain("logout");
        html.Should().Contain("退出登录");
        html.Should().Contain("data-delete-project");
        html.Should().Contain("deleteProject");
        html.Should().Contain("loadLatestProjectCreationFailure");
        html.Should().Contain("/api/project-creation-failures/latest");
        html.Should().Contain("listableProjects");
        html.Should().Contain("projects.filter(isProjectReady)");
        html.Should().Contain(@"classList.toggle(""hidden"", !initializing)");
        html.Should().NotContain("showInitialization(\"running\", \"\");\n                      out(projects);\n                      return;");
        html.Should().Contain(@"$(""sessionPanel"").classList.add(""hidden"")");
        html.Should().Contain("项目初始化配置中");
        html.Should().NotContain(@"$(""chapter2"")");
        html.Should().Contain("runPrototype");
        html.Should().Contain("prototypeGddStatus");
        html.Should().Contain("确认 GDD 无误，创建原型骨架");
        html.Should().Contain("prototype-7day-playable/from-gdd");
        html.Should().Contain("refreshPrototypeGddStatus");
        html.Should().Contain("gddMilestoneStepStatus");
        html.Should().Contain("生成当前 Step 实施计划");
        html.Should().Contain("下载验证后确认完成");
        html.Should().Contain("提交当前 Step 反馈");
        html.Should().Contain("gdd-milestone-steps/latest");
        html.Should().Contain("gdd-milestone-steps/current/iteration-plan");
        html.Should().Contain("loadGddMilestoneSteps");
        html.Should().Contain("请先创建策划大纲");
        html.Should().Contain("draftFile");
        html.Should().Contain(@"id=""importDraft"" class=""secondary import-draft-button""");
        html.Should().NotContain(@"id=""importDraft"" class=""ghost import-draft-button""");
        html.Should().NotContain("导入原型草稿 TXT");
        html.Should().Contain("prototype-drafts/analyze");
        html.Should().Contain("prototype-drafts/latest");
        html.Should().Contain("loadLatestPrototypeDraft");
        html.Should().Contain("renderDraftImportStatus");
        html.Should().Contain("draftAnalysisRunning");
        html.Should().Contain("resetPrototypeActionButtonsVisualState();");
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
        html.Should().Contain("const currentProjectVisible = !!state.projectId && visibleProjects.some(project => project.projectId === state.projectId);");
        html.Should().Contain("} else if (state.projectId && !currentProjectVisible) {");
        html.Should().Contain("writeSelectedProjectId(\"\");");
        html.Should().Contain("const current = state.projectId ? projects.find(project => project.projectId === state.projectId) : null;");
        html.Should().Contain("void selectProject(current.projectId);");
        html.Should().Contain("latestProject");
        html.Should().Contain("projectTimestamp");
        html.Should().Contain("project.lastActivityUtc || project.updatedUtc");
        html.Should().Contain("globalModel");
        html.Should().NotContain("globalModelPanel");
        html.Should().NotContain("stepsPanel");
        html.Should().NotContain("codexConfigPanel");
        html.IndexOf("id=\"globalModel\"", StringComparison.Ordinal).Should().BeLessThan(html.IndexOf("id=\"openCreateProjectPage\"", StringComparison.Ordinal));
        html.IndexOf("id=\"openCreateProjectPage\"", StringComparison.Ordinal).Should().BeLessThan(html.IndexOf("id=\"openProjectListModal\"", StringComparison.Ordinal));
        html.IndexOf("id=\"openProjectListModal\"", StringComparison.Ordinal).Should().BeLessThan(html.IndexOf("id=\"logout\"", StringComparison.Ordinal));
        html.IndexOf("if (isProjectReady(createdProject))", StringComparison.Ordinal)
            .Should().BeLessThan(html.IndexOf("if (visibleProjects.length > 0)", StringComparison.Ordinal));
        html.Should().NotContain("项目初始化超时，请稍后重试。");
        html.Should().Contain("<h1>Game Ren</h1>");
        html.Should().Contain("<title>Game Ren</title>");
        html.Should().NotContain("Phase A Prototype Console");
        html.Should().Contain("<option value=\"gpt-5.5\" selected>ChatGPT 5.5</option>");
        html.Should().Contain("<option value=\"gpt-5.4\">ChatGPT 5.4</option>");
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
        html.Should().Contain("重新触发原型项目验收");
        html.Should().Contain("prototype-7day-playable/validate");
        html.Should().Contain("buildPrototypePayload");
        html.Should().Contain("missingPrototypeFields");
        html.Should().Contain("showPrototypeNotice");
        html.Should().Contain("showPrototypeError");
        html.Should().Contain("正在提交原型创建请求");
        html.Should().Contain("缺少必填项");
        html.Should().Contain("setPrototypeFormLocked");
        html.Should().Contain("isPrototypeCreationLocked");
        html.Should().Contain("![\"idle\", \"failed\", \"cancel\"].includes(status)");
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
        html.Should().Contain("const sceneSlug = $(\"tddSlug\").value.trim() || $(\"protoSlug\").value.trim();");
        html.Should().Contain("const prototypePayload = { ...buildPrototypePayload(), slug: sceneSlug };");
        html.Should().Contain("slug: sceneSlug");
        html.Should().Contain("gameType: prototypePayload.gameType");
        html.Should().Contain("hypothesis: prototypePayload.hypothesis");
        html.Should().Contain("corePlayerFantasy: prototypePayload.corePlayerFantasy");
        html.Should().Contain("minimumPlayableLoop: prototypePayload.minimumPlayableLoop");
        html.Should().NotContain("function inferPrototypeEngineRecommendation");
        html.Should().Contain("chatPanel");
        html.Should().Contain("chat-scroll");
        html.Should().Contain("phaseAChatHistory");
        html.Should().Contain("chatStorageVersion");
        html.Should().Contain("maxStoredChatMessages");
        html.Should().Contain("loadChatHistoryForProject");
        html.Should().Contain("loadServerChatHistoryForProject");
        html.Should().Contain("chat-history");
        html.Should().Contain("saveChatHistoryForProject");
        html.Should().Contain("Chat persistence is best-effort");
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
        html.Should().Contain("/(?:gdd-outline|assets|downloads|runs|projects|admin|api|account)");
        html.Should().Contain("(?:projectId|runId|accountId|ticket|embedded)");
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
        html.Should().Contain("history.scrollTop = history.scrollHeight");
        html.Should().Contain("\\u521b\\u5efa\\u7b56\\u5212\\u5927\\u7eb2");
        html.Should().Contain("服务器聊天记录已同步。");
        html.Should().Contain("未输入优化目标，已使用当前下一步建议生成游戏模块。");
        html.Should().Contain("当前游戏模块已经开始执行，不允许更新游戏模块。");
        html.Should().Contain("游戏模块已经全部完成，不可以删除。");
        html.Should().Contain("typedMessage ? \"manual_feedback\" : \"completion_suggestion\"");
        html.Should().Contain("evaluateIterationPlanFromChat");
        html.Should().Contain("评估当前计划是否值得继续");
        html.Should().Contain("needs-fix-route");
        html.Should().Contain("submitNeedsFixRouteRequest");
        html.Should().Contain("运行需要修复路由");
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
        html.Should().Contain("正在准备提交任务");
        html.Should().Contain("需要修复路由已提交，正在等待后台 run 创建。");
        html.Should().Contain("当前有任务正在执行，请等待当前 run 完成后再启动需要修复路由。");
        html.Should().NotContain("无法启动 needs-fix：当前页面未确认原型骨架已创建。");
        html.Should().Contain("[\"needs_fix\", \"failed\"].includes");
        html.Should().Contain("feedback ? buildNeedsFixFeedbackForUserReport(goal, feedback) : buildNeedsFixFeedbackForGoal(goal)");
        html.Should().NotContain("quickFixPanel");
        html.Should().NotContain("submitQuickFix");
        html.Should().NotContain("prototype-quick-fixes");
        html.Should().NotContain("兼容入口：快速修复");
        html.Should().Contain("submitFormalFeedback");
        html.Should().Contain("提交反馈到需要修复路由");
        html.Should().Contain("buildNeedsFixFeedbackForUserReport(goal, feedback)");
        html.Should().Contain("goalId: goal?.goalId || null");
        html.Should().Contain("如果当前项目还没有可修复目标，请返回明确的前置条件提示，不要生成游戏模块");
        html.Should().Contain("continueSuggestedFeedback");
        html.Should().Contain("await executeIterationGoal()");
        html.Should().Contain("await submitIterationPlanFromFeedback(suggestion, \"正在生成游戏模块...\", \"completion_suggestion\")");
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
        html.Should().Contain("继续评估当前计划");
        html.Should().Contain("nextSuggestedFeedback");
        html.Should().Contain("continueConsumed");
        html.Should().Contain("suggestedFeedback");
        html.Should().Contain("defaultNextSuggestedFeedback");
        html.Should().Contain("updateContinueSuggestionFromText");
        html.Should().Contain("如果你同意|如你同意|若你同意");
        html.Should().Contain("如需执行，请使用游戏模块或需要修复的固定功能按钮。");
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
        html.Should().Contain("计划摘要");
        html.Should().Contain("message.kind !== \"prototype-seed\"");
        html.Should().Contain("function isVisibleChatMessage(message)");
        html.Should().Contain("总任务数");
        html.Should().Contain("已完成");
        html.Should().Contain("当前任务");
        html.Should().Contain("下一任务");
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
        html.Should().Contain("执行中");
        html.Should().Contain("待执行");
        html.Should().Contain("失败");
        html.Should().Contain("需要修复");
        html.Should().Contain("prototype-feedback-iterations");
        html.Should().NotContain("formal-feedback-failed");
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
        html.Should().NotContain("buildIterationPlanEvaluationChatMessage");
        html.Should().NotContain("resolveIterationPlanEvaluationSuggestedFeedback");
        html.Should().Contain("__iteration_plan_evaluate__");
        html.Should().Contain("__iteration_plan_execute_next__");
        html.Should().NotContain("kind: \"iteration-plan-evaluation\"");
        html.Should().Contain("$(\"evaluateIterationPlanFromChat\").onclick = () => evaluateIterationPlan(true);");
        html.Should().Contain("executeIterationGoal");
        html.Should().Contain("<button id=\"executeIterationGoal\" class=\"secondary\" data-global-action=\"true\">执行下一任务</button>");
        html.Should().Contain("$(\"executeIterationGoal\").disabled = hasNeedsFix");
        html.Should().Contain("? isGlobalBusy()");
        html.Should().Contain("iterationAutoRefreshHint");
        html.Should().Contain("await runNeedsFixIterationGoal(needsFixGoal.goalIndex);");
        html.Should().Contain("运行需要修复路由");
        html.Should().Contain("执行中会自动刷新进度");
        html.Should().Contain("iterationPlanStatus");
        html.Should().Contain("iterationPlanEvaluation");
        html.Should().Contain("iterationPlanGoals");
        html.Should().Contain("需要定制路线");
        html.Should().Contain("联系管理员创建定制游戏类型路线");
        html.Should().Contain("主流程：游戏模块");
        html.Should().Contain("评估当前游戏模块");
        html.Should().Contain("renderIterationPlanEvaluation");
        html.Should().Contain("iterationPlanEvaluationRunning");
        html.Should().Contain("正在评估当前游戏模块");
        html.Should().Contain("isInlineOnlyRun");
        html.Should().Contain("prototype-iteration-plan-evaluation");
        html.Should().NotContain("setLocalBusy(true, \"正在评估当前游戏模块");
        html.Should().Contain("页面建议：");
        html.Should().Contain("suggestedPromptForRegeneration");
        html.Should().Contain("重新生成游戏模块");
        html.Should().Contain("删除当前轮游戏模块");
        html.Should().Contain("建议先重拆游戏模块");
        html.Should().Contain("提交反馈到需要修复路由");
        html.Should().NotContain("当前已有未完成计划，请先执行下一任务");
        html.Should().Contain("生成新的游戏模块");
        html.Should().NotContain("\"当前已有未完成计划\"");
        html.Should().NotContain("\"当前计划需先修复\"");
        html.Should().Contain("请先生成游戏模块");
        html.Should().Contain("当前没有待执行任务");
        html.Should().Contain("请先修复当前任务");
        html.Should().Contain("/iteration-plan");
        html.Should().Contain("/iteration-plan/evaluate");
        html.Should().Contain("state.iterationPlanEvaluation = response?.evaluation || response;");
        html.Should().Contain("const longLlmTimeoutMs = 1200 * 1000;");
        html.Should().Contain("failureCode: \"client_timeout\"");
        html.Should().Contain("timeoutMs: longLlmTimeoutMs");
        html.Should().Contain("/iteration-plan/execute-next");
        html.Should().Contain("loadIterationPlan");
        html.Should().Contain("renderIterationPlan");
        html.Should().Contain("submitIterationPlanFromFeedback");
        html.Should().NotContain("iteration-plan-request");
        html.Should().NotContain("iteration-plan-result");
        html.Should().Contain("await loadServerChatHistoryForProject(state.projectId);");
        html.Should().Contain("Codex");
        html.Should().Contain("/chat");
        html.Should().Contain("/api/projects");
        html.Should().Contain("prototype-7day-playable");
        html.Should().Contain("prototype-tdd");
        html.Should().Contain("loadAssetInventory");
        html.Should().Contain("assetInventoryStatus");
        html.Should().Contain("查看项目素材库");
        html.Should().Contain("/assets?projectId=");
        html.Should().Contain("asset-inventory");
        html.Should().Contain("asset-preview");
        html.Should().Contain("当前项目素材库还没有足够的可检查内容");
        html.Should().Contain("renderAssetInventory");
        html.Should().Contain("refreshAssetInventoryAvailability");
        html.Should().Contain("assetInventoryExpanded");
        html.Should().Contain("renderAssetInventory(state.assetInventory, state.assetInventoryExpanded)");
        html.Should().Contain("用途：");
        html.Should().Contain("asset-grid");
    }

    [Fact]
    public void RenderShellV2_ShowsSanitizedIterationPlanFailureReasonInUserUi()
    {
        var html = new BrowserUiRenderer().RenderShellV2();

        html.Should().Contain("publicIterationPlanFailureMessage(summary)");
        html.Should().Contain("sanitizePublicFailureContent");
        html.Should().Contain("路径和文件名已隐藏");
        html.Should().Contain("sanitizePublicIterationPlanText");
        html.Should().Contain("publicIterationGoalResultSummary(goal)");
        html.Should().Contain("后台记录会保留完整证据");
        html.Should().NotContain("evaluation.reason ? `<p");
        html.Should().NotContain("escapeHtml(evaluation.reason");
        html.Should().NotContain("escapeHtml(goal.resultSummary)");
        html.Should().NotContain("out(state.iterationPlanEvaluation)");
        html.Should().NotContain("state.iterationPlanFailure = summary");
    }

    [Fact]
    public void RenderAssets_IncludesAssetInventoryPageAndPreviewTickets()
    {
        var html = new BrowserUiRenderer().RenderAssets();

        html.Should().Contain("Project Asset Library");
        html.Should().Contain("asset-inventory?judge=true");
        html.Should().Contain("asset-library");
        html.Should().Contain("asset-library/generate");
        html.Should().Contain("asset-library/import");
        html.Should().Contain("asset-library/select");
        html.Should().Contain("modalImportAsset");
        html.Should().Contain("assetImportQuery");
        html.Should().Contain("非白名单 URL 只按关键词分析");
        html.Should().Contain("selectionValidation");
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
        html.Should().Contain("data-asset-download-url");
        html.Should().Contain("assetOriginalPreviewOverlay");
        html.Should().Contain("assetOriginalPreviewLayer");
        html.Should().Contain("closeAssetOriginalPreviewButton");
        html.Should().Contain("downloadAsset");
        html.Should().Contain("asset-unit-name");
        html.Should().Contain("assetUnitName");
        html.Should().Contain("使用单位：");
        html.Should().Contain("asset-role");
        html.Should().Contain("assetRoleText");
        html.Should().Contain("grid-template-columns: minmax(9.5rem, 1fr) minmax(4rem, 0.5fr)");
        html.Should().Contain("align-items: center");
        html.Should().Contain("asset-original-preview-close");
        html.Should().Contain("data-select-unit-key");
        html.Should().Contain("addEventListener(\"click\"");
        html.Should().NotContain("addEventListener(\"mouseover\"");
        html.Should().NotContain("addEventListener(\"mousemove\"");
        html.Should().NotContain("addEventListener(\"mouseout\"");
        html.Should().NotContain("positionAssetOriginalPreview");
        html.Should().NotContain("setTimeout(hideAssetOriginalPreview, 3000)");
        html.Should().NotContain("onclick=");
        html.Should().NotContain("onchange=");
        html.Should().Contain("asset-detail-grid");
        html.Should().Contain("body.embedded main");
        html.Should().Contain("params.get(\"embedded\") === \"1\"");
        html.Should().Contain("page-header-actions");
        html.Should().Contain("refreshButton.disabled = true");
        html.Should().Contain("refreshButton.textContent = force ? \"刷新中...\" : \"读取中...\"");
        html.Should().Contain("refreshButton.textContent = \"刷新素材库\"");
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
        html.Should().Contain("loadAssets();");
        html.Should().Contain("loadAssets(true)");
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
        html.Should().Contain("assetRuns");
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
        html.Should().Contain("chatRuns");
        html.Should().Contain("recentRunsSection");
        html.Should().Contain("最近聊天 run 明细");
        html.Should().Contain("没有最近聊天 run 明细");
        html.Should().Contain("averageRuntimeSeconds");
        html.Should().Contain("runTypeLabel");
        html.Should().Contain("style.display = \"none\"");
    }

    [Fact]
    public void RenderGddOutline_IncludesOutlineEditorFlow()
    {
        var html = new BrowserUiRenderer().RenderGddOutline();

        html.Should().Contain("/api/projects/${projectId}/gdd/outline");
        html.Should().Contain("/api/projects/${projectId}/gdd/outline/sections/${encodeURIComponent(sectionId)}");
        html.Should().Contain("generateSection");
        html.Should().Contain("completeAllSections");
        html.Should().Contain("quickCompleteSection");
        html.Should().Contain("generateSectionContent");
        html.Should().Contain("waitForBatchOutlineRun");
        html.Should().Contain("formatBatchRunProgress");
        html.Should().Contain("attempt < 600");
        html.Should().Contain("/api/runs/${encodeURIComponent(runId)}");
        html.Should().Contain("/api/projects/${projectId}/gdd/outline/sections/complete-missing");
        html.Should().Contain("data-quick-complete-section");
        html.Should().Contain("section-actions");
        html.Should().Contain("editorSkeleton");
        html.Should().Contain("editorContent");
        html.Should().Contain("editorMessage");
        html.Should().Contain("showModal");
        html.Should().Contain("exportGddMarkdown");
        html.Should().Contain("/api/projects/${projectId}/gdd/outline/export");
        html.Should().Contain("deleteGddOutline");
        html.Should().Contain("outline-toolbar");
        html.Should().Contain("body.embedded .outline-toolbar");
        html.Should().Contain("/api/projects/${projectId}/gdd/outline`, { method:\"DELETE\" }");
        html.Should().Contain("phasea:gdd-outline-deleted");
        html.Should().Contain("/downloads?projectId=");
        html.Should().Contain("window.parent?.document?.getElementById?.(\"token\")");
        html.Should().Contain("当前策划大纲不可用，请删除后重新创建。");
        html.Should().Contain(".grid { display:grid; grid-template-columns: minmax(0,1fr); gap:.8rem; }");
        html.Should().Contain(".section-header");
        html.Should().Contain("<div class=\"section-header\">");
        html.Should().Contain("type=\"button\" data-edit-section");
        html.Should().Contain("已载入策划大纲");
        html.Should().Contain("button.textContent = \"\\u751f\\u6210\\u4e2d...\"");
        html.Should().Contain("button.textContent = \"\\u751f\\u6210\\u5177\\u4f53\\u5185\\u5bb9\"");
        html.Should().Contain("button.textContent = \"\\u5bfc\\u51fa\\u4e2d...\"");
        html.Should().Contain("button.textContent = \"\\u5bfc\\u51fa\\u4e3a GDD.md\"");
        html.Should().NotContain("outline.relativePath");
        html.Should().NotContain("docs/gdd/gdd-outline.json");
        html.Should().NotContain("???");
        html.Should().NotContain("repeat(auto-fit,minmax(18rem,1fr))");
    }

    [Fact]
    public void Program_AllowsGddOutlinePageBeforeBearerTokenMiddleware()
    {
        var sourcePath = Path.GetFullPath(Path.Combine(
            AppContext.BaseDirectory,
            "..",
            "..",
            "..",
            "..",
            "PhaseA.Platform",
            "Program.cs"));
        var source = File.ReadAllText(sourcePath);

        var whitelistIndex = source.IndexOf("context.Request.Path == \"/gdd-outline\"", StringComparison.Ordinal);
        var authFailureIndex = source.IndexOf("PhaseAAuth.AuthFailureCode", StringComparison.Ordinal);
        whitelistIndex.Should().BeGreaterThanOrEqualTo(0);
        whitelistIndex.Should().BeLessThan(authFailureIndex);
    }


    [Fact]
    public void Program_SynchronousRunEndpointsTranslateServerSideRunCancellation()
    {
        var sourcePath = Path.GetFullPath(Path.Combine(
            AppContext.BaseDirectory,
            "..",
            "..",
            "..",
            "..",
            "PhaseA.Platform",
            "Program.cs"));
        var source = File.ReadAllText(sourcePath);

        source.Should().Contain("static IResult CancelledRunResult()");
        source.Should().Contain("new { status = \"cancel\", error = \"run_cancelled\" }");
        source.Should().Contain("statusCode: 499");
        source.Should().Contain("RunCancellationPolicy.IsCancellationBlocked(run.RunType)");
        source.Should().Contain("run_cancel_not_allowed");

        var routes = new[]
        {
            "app.MapPost(\"/api/projects/{projectId}/packages\"",
            "app.MapPost(\"/api/projects/{projectId}/gdd\"",
            "app.MapPost(\"/api/projects/{projectId}/gdd/outline/sections/{sectionId}\"",
            "app.MapPost(\"/api/projects/{projectId}/asset-library/generate\"",
            "app.MapPost(\"/api/projects/{projectId}/chat\"",
            "app.MapPost(\"/api/projects/{projectId}/iteration-plan/execute-next\"",
            "app.MapPost(\"/api/projects/{projectId}/ui-optimization\"",
            "app.MapPost(\"/api/projects/{projectId}/prototype-feedback-iterations\"",
            "app.MapPost(\"/api/projects/{projectId}/needs-fix-route\"",
            "app.MapPost(\"/api/projects/{projectId}/repair-plan/execute-next\"",
            "app.MapPost(\"/api/projects/{projectId}/skill-actions/{actionId}\"",
            "app.MapPost(\"/api/projects/{projectId}/prototype-drafts/analyze\"",
            "app.MapPost(\"/api/projects/{projectId}/chapter2-bootstrap\"",
            "app.MapPost(\"/api/projects/{projectId}/prototype-7day-playable/validate\"",
            "app.MapPost(\"/api/projects/{projectId}/prototype-tdd\"",
            "app.MapPost(\"/api/projects/{projectId}/prototype-scene\""
        };

        foreach (var route in routes)
        {
            var routeIndex = source.IndexOf(route, StringComparison.Ordinal);
            routeIndex.Should().BeGreaterThanOrEqualTo(0, $"{route} should exist");
            var nextRouteIndex = source.IndexOf("app.Map", routeIndex + route.Length, StringComparison.Ordinal);
            var endpointSource = source[routeIndex..(nextRouteIndex < 0 ? source.Length : nextRouteIndex)];
            endpointSource.Should().Contain("catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)", $"{route} should translate queued or running cancellation");
            endpointSource.Should().Contain("return CancelledRunResult();", $"{route} should return the standard cancel payload");
        }
    }

    [Fact]
    public void RenderDownloads_IncludesRobustPackageDownloadFlow()
    {
        var html = new BrowserUiRenderer().RenderDownloads();

        html.Should().Contain("项目文件下载");
        html.Should().Contain("id=\"createPackage\"");
        html.Should().Contain("打包项目文件");
        html.Should().Contain("function renderCreatePackageAction(payload)");
        html.Should().Contain("async function createPackage()");
        html.Should().Contain("fetch(`/api/projects/${projectId}/packages`, { method: \"POST\"");
        html.Should().Contain("$(\"createPackage\").onclick = createPackage");
        html.Should().Contain("body.embedded main");
        html.Should().Contain("params.get(\"embedded\") === \"1\"");
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

    private static string? FindExecutableOnPath(string name)
    {
        var path = Environment.GetEnvironmentVariable("PATH");
        if (string.IsNullOrWhiteSpace(path))
        {
            return null;
        }

        foreach (var directory in path.Split(Path.PathSeparator))
        {
            if (string.IsNullOrWhiteSpace(directory))
            {
                continue;
            }

            var candidate = Path.Combine(directory.Trim(), name);
            if (File.Exists(candidate))
            {
                return candidate;
            }
        }

        return null;
    }

    private static void RunNodeScript(string node, string script)
    {
        var scriptPath = Path.Combine(Path.GetTempPath(), $"phasea-browser-smoke-{Guid.NewGuid():N}.js");
        try
        {
            File.WriteAllText(scriptPath, script);
            var startInfo = new ProcessStartInfo
            {
                FileName = node,
                RedirectStandardError = true,
                RedirectStandardOutput = true,
                UseShellExecute = false,
                CreateNoWindow = true
            };
            startInfo.ArgumentList.Add(scriptPath);
            using var process = Process.Start(startInfo);
            process.Should().NotBeNull();
            var running = process!;
            running.WaitForExit(10_000).Should().BeTrue();
            var output = running.StandardOutput.ReadToEnd() + running.StandardError.ReadToEnd();
            running.ExitCode.Should().Be(0, output);
        }
        finally
        {
            if (File.Exists(scriptPath))
            {
                File.Delete(scriptPath);
            }
        }
    }

    [Fact]
    public void PrototypeSkeletonRunNotes_AreEmbeddedAsResource()
    {
        var assembly = typeof(BrowserUiRenderer).Assembly;
        var names = assembly.GetManifestResourceNames();
        names.Should().Contain(name => name.EndsWith("Browser.Assets.PrototypeSkeletonRunNotes.txt", StringComparison.OrdinalIgnoreCase));
    }

}
