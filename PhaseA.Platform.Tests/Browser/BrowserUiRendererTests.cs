using FluentAssertions;
using PhaseA.Platform.Browser;
using PhaseA.Platform.Data;
using PhaseA.Platform.Readback;
using PhaseA.Platform.Runs;
using System.Diagnostics;
using System.Text;
using System.Text.Json;
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
    public void RenderShellV2_PrototypeSkeletonPageShowsM1AndPackageShortcut()
    {
        var html = new BrowserUiRenderer().RenderShellV2();

        html.Should().Contain("prototypeM1SpecStatus");
        html.Should().Contain("M1 游戏场景目标");
        html.Should().Contain("packagePrototypeSkeleton");
        html.Should().Contain("确认 GDD 无误，执行 M1 游戏场景");
        html.Should().Contain("$(\"packagePrototypeSkeleton\").onclick = createProjectPackage");
        html.Should().Contain("prototypeSkeletonM1Completed()");
        html.Should().Contain("M1 游戏场景完成后才可以在这里打包下载项目");
    }

    [Fact]
    public void RenderShellV2_GddQuestionFormModalBehaviorSmoke()
    {
        var node = RequireNodeForGddQuestionFormTests();

        var source = File.ReadAllText(BrowserUiRendererSourcePath());
        var gddQuestionFormScript = ExtractJavaScriptRange(
            source,
            "function currentProjectSnapshot(projectId = state.projectId)",
            "async function startGddDocumentRoute(message, sceneRoute = null)");

        var script = $$"""
            const assert = require("assert");
            let focusedElement = null;

            class ClassList {
              constructor() { this.items = new Set(); }
              add(name) { this.items.add(name); }
              remove(name) { this.items.delete(name); }
              contains(name) { return this.items.has(name); }
              toggle(name, force) {
                if (force) this.items.add(name);
                else this.items.delete(name);
              }
            }

            class Element {
              constructor(id = "") {
                this.id = id;
                this.dataset = {};
                this.disabled = false;
                this.textContent = "";
                this.value = "";
                this.rows = 0;
                this.maxLength = 0;
                this.placeholder = "";
                this.required = false;
                this.style = {};
                this.attributes = new Map();
                this.classList = new ClassList();
                this._innerHTML = "";
              }
              set innerHTML(value) {
                this._innerHTML = value;
                if (this.id !== "gddQuestionForm") return;
                document.inputs.clear();
                document.progressElement = null;
                if (value.includes("gdd-question-progress")) {
                  const progress = new Element("gddQuestionFormProgress");
                  progress.classList.add("gdd-question-progress");
                  elements.set("gddQuestionFormProgress", progress);
                  document.progressElement = progress;
                }
                if (value.includes("gddQuestionFormProgressBar")) {
                  elements.set("gddQuestionFormProgressBar", new Element("gddQuestionFormProgressBar"));
                }
                if (value.includes("gddQuestionFormProgressValue")) {
                  const progressValue = new Element("gddQuestionFormProgressValue");
                  progressValue.textContent = "0%";
                  elements.set("gddQuestionFormProgressValue", progressValue);
                }
                const textareaPattern = /<textarea\b([^>]*)>([\s\S]*?)<\/textarea>/g;
                let match;
                while ((match = textareaPattern.exec(value)) !== null) {
                  const attrs = match[1];
                  const body = match[2] || "";
                  const id = /data-gdd-question-input="([^"]+)"/.exec(attrs)?.[1] || "";
                  const input = new Element(id);
                  input.dataset.gddQuestionInput = id;
                  input.value = body;
                  input.rows = Number(/rows="([^"]+)"/.exec(attrs)?.[1] || 0);
                  input.maxLength = Number(/maxlength="([^"]+)"/.exec(attrs)?.[1] || 0);
                  input.required = /\srequired(?:\s|>|$)/.test(attrs);
                  if (/aria-required="true"/.test(attrs)) input.attributes.set("aria-required", "true");
                  document.inputs.set(id, input);
                }
                const sceneRoutePattern = /<textarea\b([^>]*)>([\s\S]*?)<\/textarea>/g;
                while ((match = sceneRoutePattern.exec(value)) !== null) {
                  const attrs = match[1];
                  if (!/data-gdd-scene-route-json="true"/.test(attrs)) continue;
                  const input = new Element("sceneRouteJson");
                  input.dataset.gddSceneRouteJson = "true";
                  input.value = (match[2] || "")
                    .replaceAll("&quot;", '"')
                    .replaceAll("&lt;", "<")
                    .replaceAll("&gt;", ">")
                    .replaceAll("&amp;", "&");
                  document.sceneRouteInput = input;
                }
              }
              get innerHTML() { return this._innerHTML; }
              getAttribute(name) { return this.attributes.get(name) || null; }
              setAttribute(name, value) { this.attributes.set(name, String(value)); }
              focus() { focusedElement = this; }
            }

            const elements = new Map();
            function addElement(id) {
              const element = new Element(id);
              elements.set(id, element);
              return element;
            }

            const document = {
              inputs: new Map(),
              sceneRouteInput: null,
              progressElement: null,
              querySelector(selector) {
                if (selector === ".gdd-question-progress") return this.progressElement;
                if (selector === `[data-gdd-scene-route-json="true"]`) return this.sceneRouteInput;
                const match = /^\[data-gdd-question-input="([^"]+)"\]$/.exec(selector);
                return match ? this.inputs.get(match[1]) || null : null;
              }
            };
            global.document = document;
            global.window = { open() {} };

            [
              "gddQuestionFormModal",
              "gddQuestionForm",
              "gddQuestionFormMeta",
              "gddQuestionFormHint",
              "confirmGddQuestionForm",
              "cancelGddQuestionForm",
              "createGddDocument",
              "chatMessage",
              "globalModel"
            ].forEach(addElement);
            elements.get("gddQuestionFormModal").classList.add("hidden");
            elements.get("globalModel").value = "gpt-test";

            const state = {
              projectId: "p1",
              projects: [{ projectId: "p1", gameName: "Towerdemo2", name: "Tower Demo", gameTypeSource: "塔防", templateRuleId: "tower-defense" }],
              gddQuestionFormFields: [],
              gddQuestionFormSource: "",
              gddQuestionFormAnswers: [],
              gddQuestionFormMessage: "",
              gddSceneRoute: null,
              gddQuestionFormRequestToken: 0,
              gddQuestionFormAbortController: null,
              gddQuestionFormProgressTimer: null,
              gddQuestionFormProgressStartedAtMs: 0,
              gddQuestionFormCurrentSchemaSignature: "",
              gddQuestionFormDraftCache: new Map(),
              gddQuestionFormSchemaCache: new Map(),
              gddOutlineReady: false,
              localBusy: false
            };
            const gddQuestionFormMessageBudget = 5500;
            const gddQuestionFormSchemaCacheTtlMs = 24 * 60 * 60 * 1000;
            const gddQuestionFormFallbackCacheTtlMs = 5 * 60 * 1000;
            const gddQuestionFormSchemaTimeoutMs = 90 * 1000;
            const gddQuestionFormProgressDurationMs = 20 * 1000;
            const $ = id => elements.get(id) || null;
            function escapeHtml(value) {
              return String(value ?? "")
                .replaceAll("&", "&amp;")
                .replaceAll("<", "&lt;")
                .replaceAll(">", "&gt;")
                .replaceAll('"', "&quot;");
            }
            function setModalVisible(id, visible) {
              const element = $(id);
              if (visible) element.classList.remove("hidden");
              else element.classList.add("hidden");
            }
            function projectRequestContext(projectId = state.projectId) { return { projectId, authEpoch: 0 }; }
            function isCurrentProjectContext(context) { return context?.projectId === state.projectId; }
            function guardGlobalAction() { return true; }
            function callV2() {}
            function out(message) { global.lastOut = message; }
            function showError(error) { global.lastError = error; }
            async function refreshProjects() {}

            let apiCalls = [];
            let resolveApi;
            async function api(path, options) {
              apiCalls.push({ path, options });
              if (path.includes("/gdd/question-form/restore-latest")) return { status: "not_found", answers: [] };
              return await new Promise(resolve => { resolveApi = resolve; });
            }

            {{gddQuestionFormScript}}

            loadGddSceneRouteDraft = async () => fallbackGddSceneRoute();

            let routeCalls = [];
            let routeShouldSucceed = false;
            let routeWaitForResolve = false;
            let resolveRoute;
            async function startGddDocumentRoute(message, sceneRoute = null) {
              routeCalls.push({ message, sceneRoute });
              if (routeWaitForResolve) {
                return await new Promise(resolve => { resolveRoute = () => resolve(routeShouldSucceed); });
              }

              return routeShouldSucceed;
            }

            (async () => {
              const openPromise = openGddQuestionFormModal();
              await Promise.resolve();
              assert.strictEqual($("gddQuestionFormModal").classList.contains("hidden"), false);
              assert.strictEqual(apiCalls.length, 1);
              assert.strictEqual($("gddQuestionFormProgressValue").textContent, "0%");
              assert.strictEqual(document.progressElement.getAttribute("aria-valuenow"), "0");
              assert.ok(state.gddQuestionFormProgressTimer);
              updateGddQuestionFormProgress(99.9);
              assert.strictEqual($("gddQuestionFormProgressValue").textContent, "99%");
              assert.strictEqual($("gddQuestionFormProgressBar").style.width, "99%");
              closeGddQuestionFormModal();
              assert.strictEqual(state.gddQuestionFormProgressTimer, null);
              assert.strictEqual(apiCalls[0].options.signal.aborted, true);
              resolveApi({ fields: fallbackGddQuestionFormFields(), source: "agent" });
              await openPromise;
              assert.strictEqual($("gddQuestionFormModal").classList.contains("hidden"), true);
              assert.strictEqual(state.gddQuestionFormFields.length, 0);

              const invalidRequiredOpenPromise = openGddQuestionFormModal();
              await Promise.resolve();
              resolveApi({ fields: fallbackGddQuestionFormFields().map(field => ({ ...field, required: false })), source: "agent" });
              await invalidRequiredOpenPromise;
              assert.strictEqual($("gddQuestionFormModal").classList.contains("hidden"), false);
              assert.strictEqual(state.gddQuestionFormSource, "fallback");
              assert.strictEqual(state.gddQuestionFormProgressTimer, null);
              assert.ok(state.gddQuestionFormFields.filter(field => field.required).length >= 4);
              closeGddQuestionFormModal();

              const apiCountBeforeCachedOpen = apiCalls.length;
              await openGddQuestionFormModal();
              assert.strictEqual(apiCalls.length, apiCountBeforeCachedOpen + 1);
              assert.ok(apiCalls.at(-1).path.includes("/gdd/question-form/restore-latest"));
              assert.strictEqual($("gddQuestionFormModal").classList.contains("hidden"), false);
              assert.strictEqual(state.gddQuestionFormProgressTimer, null);
              closeGddQuestionFormModal();

              renderGddQuestionForm({ fields: fallbackGddQuestionFormFields(), source: "agent" });
              setModalVisible("gddQuestionFormModal", true);
              assert.strictEqual(document.inputs.get("reference_signal").required, true);
              assert.strictEqual(document.inputs.get("reference_signal").getAttribute("aria-required"), "true");
              assert.strictEqual(document.inputs.get("reference_signal").value, "Towerdemo2 的参考对象、体验目标和禁忌方向。");
              clearGddQuestionFormDraft();
              renderGddQuestionForm({
                fields: fallbackGddQuestionFormFields(),
                source: "agent",
                restoreDraft: { answers: [{ label: "参考信号", answer: "上一次填写的参考信号" }] }
              });
              assert.strictEqual(document.inputs.get("reference_signal").value, "上一次填写的参考信号");
              assert.ok($("gddQuestionFormHint").textContent.includes("已导入上一次填写的 1 项答案"));

              document.inputs.get("reference_signal").value = "";
              await confirmGddQuestionForm();
              assert.strictEqual(routeCalls.length, 0);
              assert.ok($("gddQuestionFormHint").textContent.includes("请先填写必填问题"));
              assert.strictEqual(focusedElement, document.inputs.get("reference_signal"));

              document.inputs.get("reference_signal").value = "过期请求不会切换表单";
              const originalSceneRouteLoader = loadGddSceneRouteDraft;
              loadGddSceneRouteDraft = async () => {
                state.projectId = "p2";
                return fallbackGddSceneRoute();
              };
              await confirmGddQuestionForm();
              assert.strictEqual($("gddQuestionForm").dataset.schema, "question-form");
              assert.strictEqual(routeCalls.length, 0);
              state.projectId = "p1";
              loadGddSceneRouteDraft = originalSceneRouteLoader;
              renderGddQuestionForm({ fields: fallbackGddQuestionFormFields(), source: "agent" });
              setModalVisible("gddQuestionFormModal", true);

              document.inputs.get("reference_signal").value = "玩家修改后的参考标杆";
              routeShouldSucceed = false;
              await confirmGddQuestionForm();
              assert.strictEqual(routeCalls.length, 0);
              assert.strictEqual($("gddQuestionForm").dataset.schema, "scene-route");
              assert.ok(document.sceneRouteInput.value.includes("build_phase"));
              await confirmGddQuestionForm();
              assert.strictEqual(routeCalls.length, 1);
              assert.strictEqual($("gddQuestionFormModal").classList.contains("hidden"), false);
              assert.strictEqual($("confirmGddQuestionForm").disabled, false);

              renderGddQuestionForm({ fields: fallbackGddQuestionFormFields(), source: "agent" });
              setModalVisible("gddQuestionFormModal", true);
              document.inputs.get("reference_signal").value = "关闭前已经填写一半";
              await confirmGddQuestionForm();
              assert.strictEqual($("gddQuestionForm").dataset.schema, "scene-route");
              closeGddQuestionFormModal();
              assert.strictEqual($("gddQuestionFormModal").classList.contains("hidden"), true);
              renderGddQuestionForm({ fields: fallbackGddQuestionFormFields(), source: "agent" });
              setModalVisible("gddQuestionFormModal", true);
              assert.strictEqual(document.inputs.get("reference_signal").value, "关闭前已经填写一半");

              routeShouldSucceed = true;
              routeWaitForResolve = true;
              await confirmGddQuestionForm();
              assert.strictEqual($("gddQuestionForm").dataset.schema, "scene-route");
              const confirmPromise = confirmGddQuestionForm();
              await Promise.resolve();
              assert.strictEqual($("confirmGddQuestionForm").disabled, true);
              assert.strictEqual($("cancelGddQuestionForm").disabled, false);
              resolveRoute();
              await confirmPromise;
              assert.strictEqual(routeCalls.length, 2);
              assert.strictEqual($("gddQuestionFormModal").classList.contains("hidden"), true);
              assert.strictEqual($("cancelGddQuestionForm").disabled, false);
              assert.ok(routeCalls[1].message.includes("GDD question-form raw material:"));
              assert.strictEqual(routeCalls[1].sceneRoute.sceneCountIntent, "multi");
              assert.strictEqual(routeCalls[1].sceneRoute.entryScene, "build_phase");
              renderGddQuestionForm({ fields: fallbackGddQuestionFormFields(), source: "agent" });
              assert.strictEqual(document.inputs.get("reference_signal").value, "Towerdemo2 的参考对象、体验目标和禁忌方向。");
            })().catch(error => {
              console.error(error);
              process.exit(1);
            });
            """;

        RunNodeScript(node, script);
    }

    [Fact]
    public void RenderShellV2_GddQuestionFormStartRouteBehaviorSmoke()
    {
        var node = RequireNodeForGddQuestionFormTests();

        var source = File.ReadAllText(BrowserUiRendererSourcePath());
        var routeScript = ExtractJavaScriptRange(
            source,
            "function scheduleGddPostSuccessRefreshes(projectId, context)",
            "function chatHistoryDownloadFileName(projectId = state.projectId)");

        var script = $$"""
            const assert = require("assert");
            const elements = new Map([
              ["createGddDocument", { disabled: false, textContent: "创建策划大纲" }],
              ["globalModel", { value: "gpt-test" }],
              ["chatMessage", { value: "freeform note" }]
            ]);
            const state = {
              projectId: "p1",
              chatHistory: [],
              chatAttachments: [{ name: "brief.md", content: "raw" }],
              gddOutlineReady: false,
              localBusy: false
            };
            const calls = { api: [], loadHistory: 0, render: 0, save: 0, out: [], loadRuns: 0, loadPackages: 0, clear: 0, refresh: 0, errors: 0, busy: [], openForm: 0, openOutline: 0 };
            let apiMode = "success";
            let loadRunsMode = "failure";
            const $ = id => elements.get(id) || null;
            function guardGlobalAction() { return true; }
            function projectRequestContext() { return { projectId: state.projectId }; }
            function isCurrentProjectContext(context) { return context.projectId === state.projectId; }
            function setLocalBusy(busy, message = "") { state.localBusy = busy; calls.busy.push({ busy, message }); }
            function currentChatAttachmentsForRun() { return [...state.chatAttachments]; }
            async function api(path, options) {
              calls.api.push({ path, options });
              if (apiMode === "failure") throw { payload: { failureCode: "route_failed" } };
              return { summary: "GDD ready", downloadUrl: "/gdd-outline?projectId=p1" };
            }
            async function loadServerChatHistoryForProject() { calls.loadHistory += 1; return new Promise(() => {}); }
            function renderChatHistory() { calls.render += 1; }
            function saveChatHistoryForProject() { calls.save += 1; }
            function out(message) { calls.out.push(message); }
            async function loadRuns() { calls.loadRuns += 1; if (loadRunsMode === "failure") throw new Error("runs failed"); }
            async function loadProjectPackages() { calls.loadPackages += 1; }
            function sanitizePublicChatContent(value) { return String(value || ""); }
            function showError() { calls.errors += 1; }
            function clearChatAttachments() { calls.clear += 1; state.chatAttachments = []; }
            async function refreshActiveRun() { calls.refresh += 1; return new Promise(() => {}); }
            function normalizeGddSceneRoute(route) {
              if (!route) return { scenes: [], entryScene: "" };
              return { ...route, scenes: Array.isArray(route.scenes) ? route.scenes : [], entryScene: route.entryScene || "" };
            }
            function isGddQuestionFormModalOpen() { return false; }
            async function openGddQuestionFormModal() { calls.openForm += 1; }
            function callV2(name) { if (name === "v2OpenGddOutlineTab") calls.openOutline += 1; }
            function withTimeout(promise, label) {
              return new Promise((resolve, reject) => {
                const timeout = setTimeout(() => reject(new Error(`${label} timed out`)), 500);
                Promise.resolve(promise).then(
                  value => {
                    clearTimeout(timeout);
                    resolve(value);
                  },
                  error => {
                    clearTimeout(timeout);
                    reject(error);
                  });
              });
            }

            {{routeScript}}

            (async () => {
              const blocked = await withTimeout(startGddDocumentRoute("raw material"), "blocked GDD route");
              assert.strictEqual(blocked, false);
              assert.strictEqual(calls.api.length, 0);
              assert.strictEqual(calls.openForm, 1);
              assert.strictEqual(calls.out.at(-1), "请先确认场景路由后再创建策划大纲。");

              const sceneRoute = {
                sceneCountIntent: "multi",
                entryScene: "map",
                scenes: [{ id: "map", name: "Map", role: "hub", m1Required: true, playerGoal: "Pick a route." }],
                transitions: []
              };
              const success = await withTimeout(startGddDocumentRoute("raw material", sceneRoute), "success GDD route");
              assert.strictEqual(success, true);
              assert.strictEqual(calls.api[0].path, "/api/projects/p1/gdd");
              const payload = JSON.parse(calls.api[0].options.body);
              assert.strictEqual(payload.message, "raw material");
              assert.strictEqual(payload.model, "gpt-test");
              assert.deepStrictEqual(payload.attachments, [{ name: "brief.md", content: "raw" }]);
              assert.deepStrictEqual(payload.sceneRoute, sceneRoute);
              assert.strictEqual(state.gddOutlineReady, true);
              assert.strictEqual(calls.clear, 1);
              assert.deepStrictEqual(state.chatAttachments, []);
              assert.strictEqual(elements.get("chatMessage").value, "");
              assert.strictEqual(elements.get("createGddDocument").disabled, false);
              assert.strictEqual(elements.get("createGddDocument").textContent, "查阅策划大纲");
              assert.strictEqual(state.localBusy, false);
              assert.strictEqual(calls.refresh, 1);
              assert.strictEqual(calls.loadHistory, 1);
              assert.strictEqual(calls.loadRuns, 0);
              assert.strictEqual(calls.loadPackages, 0);
              assert.strictEqual(calls.errors, 0);

              state.gddOutlineReady = false;
              state.chatAttachments = [{ name: "brief.md", content: "raw" }];
              elements.get("chatMessage").value = "retry note";
              loadRunsMode = "success";
              apiMode = "failure";
              const failure = await withTimeout(startGddDocumentRoute("raw material", sceneRoute), "failure GDD route");
              assert.strictEqual(failure, false);
              assert.strictEqual(calls.clear, 1);
              assert.deepStrictEqual(state.chatAttachments, [{ name: "brief.md", content: "raw" }]);
              assert.strictEqual(elements.get("chatMessage").value, "retry note");
              assert.strictEqual(calls.errors, 1);
              assert.strictEqual(elements.get("createGddDocument").disabled, false);
              assert.strictEqual(elements.get("createGddDocument").textContent, "创建策划大纲");
              assert.strictEqual(state.localBusy, false);
              assert.strictEqual(calls.refresh, 2);
              assert.strictEqual(calls.loadHistory, 2);
            })().catch(error => {
              console.error(error);
              process.exit(1);
            });
            """;

        RunNodeScript(node, script);
    }

    [Theory]
    [InlineData("Towerdemo2", "Tower Demo", "塔防", "tower-defense")]
    [InlineData("Diablo Demo", "Diablo Demo", "Diablolike ARPG", "rpg")]
    [InlineData("Deck Demo", "Deck Demo", "deckbuilder", "deck")]
    [InlineData("Survivor Demo", "Survivor Demo", "survivorslike arena", "arena")]
    [InlineData("Generic Demo", "Generic Demo", "puzzle adventure", "generic")]
    public void RenderShellV2_GddQuestionFormFallbackMatchesBackendCoreContract(
        string gameName,
        string name,
        string gameTypeSource,
        string templateRuleId)
    {
        var node = RequireNodeForGddQuestionFormTests();

        var source = File.ReadAllText(BrowserUiRendererSourcePath());
        var fallbackScript = ExtractJavaScriptRange(
            source,
            "function currentProjectSnapshot(projectId = state.projectId)",
            "function normalizeGddQuestionFormFields(fields)");
        var projectJson = JsonSerializer.Serialize(new Dictionary<string, string?>
        {
            ["projectId"] = "p1",
            ["gameName"] = gameName,
            ["name"] = name,
            ["gameTypeSource"] = gameTypeSource,
            ["templateRuleId"] = templateRuleId
        });
        var script = $$"""
            const state = {
              projectId: "p1",
              projects: [{{projectJson}}]
            };
            {{fallbackScript}}
            const fallbackJson = JSON.stringify(fallbackGddQuestionFormFields().map(field => ({
              id: field.id,
              label: field.label,
              placeholder: field.placeholder,
              rows: field.rows || 3,
              required: !!field.required
            })));
            console.log("__GDD_FALLBACK_JSON_B64__" + Buffer.from(fallbackJson, "utf8").toString("base64"));
            """;

        var output = RunNodeScript(node, script);
        const string marker = "__GDD_FALLBACK_JSON_B64__";
        var markerIndex = output.LastIndexOf(marker, StringComparison.Ordinal);
        markerIndex.Should().BeGreaterThanOrEqualTo(0, "the node smoke should print the fallback contract JSON");
        var frontendJsonBase64 = output[(markerIndex + marker.Length)..]
            .Split(["\r\n", "\n"], StringSplitOptions.None)[0]
            .Trim();
        var frontendJson = Encoding.UTF8.GetString(Convert.FromBase64String(frontendJsonBase64));
        var frontendFields = JsonSerializer.Deserialize<List<GddFallbackFieldContract>>(frontendJson, new JsonSerializerOptions(JsonSerializerDefaults.Web));
        var backendFields = GameDesignQuestionFormService.BuildFallbackFields(ProjectSnapshotForGddQuestionForm("p1", gameName, name, gameTypeSource, templateRuleId))
            .Select(field => new GddFallbackFieldContract(
                field.Id,
                field.Label,
                field.Placeholder,
                field.Rows,
                field.Required))
            .ToList();

        frontendFields.Should().NotBeNull();
        var actualFrontendFields = frontendFields!;
        actualFrontendFields.Should().Equal(backendFields);
        actualFrontendFields.Where(field => field.Required).Should().HaveCount(count => count >= 4 && count <= 6);
        actualFrontendFields.Select(field => field.Id).Should().Contain("reference_signal");
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
            function v2LoadEmbeddedFrame(frameId, url, forceReload = false) {
              const frame = $(frameId);
              if (!frame) return;
              if (forceReload || frame.dataset.src !== url) {
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
              v2OpenTabs.set(tabId, { id: tabId, label, panelId, frameId, url, closable: true });
              v2ActiveTabId = tabId;
              v2ApplySelectedStepVisibility();
              v2LoadEmbeddedFrame(frameId, url, true);
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
            $("v2GddOutlineFrame").src = "about:blank";
            v2OpenEmbeddedTab("gdd-outline", "查阅策划大纲", "v2GddOutlineFramePanel", "v2GddOutlineFrame", "/gdd-outline?projectId=project%201&embedded=1");
            assert($("v2GddOutlineFrame").src === "/gdd-outline?projectId=project%201&embedded=1", "GDD iframe should force reload when reopening the same URL");

            v2CloseTab("gdd-outline");
            assert(v2ActiveTabId === "chat", "closing active embedded tab should return to chat");
            assert(visible("chatPanel"), "chat should be visible again");
            assert(!visible("v2GddOutlineFramePanel"), "GDD panel should be hidden after closing tab");
            assert(renderedTabs === 5 && renderedProgress === 4 && refreshedAcceptance === 2, "render hooks should match tab operations");
            """;

        RunNodeScript(node, script);
    }

    [Fact]
    public void RenderShellV2_GddMilestoneModulePanelBehaviorSmoke()
    {
        var node = FindExecutableOnPath("node.exe") ?? FindExecutableOnPath("node");
        if (node is null)
        {
            return;
        }

        const string script = """
            class Button {
              constructor(dataset = {}, className = "") {
                this.dataset = dataset;
                this.className = className;
                this.disabled = false;
                this.title = "";
                this.onclick = null;
                this.listeners = {};
              }
              addEventListener(name, handler) { this.listeners[name] = handler; }
              click() {
                if (this.disabled) return;
                if (this.onclick) this.onclick();
                if (this.listeners.click) this.listeners.click();
              }
            }
            class Panel {
              constructor() {
                this.className = "";
                this.textContent = "";
                this._innerHTML = "";
                this.stepButtons = [];
                this.navButtons = new Map();
              }
              set innerHTML(value) {
                this._innerHTML = String(value || "");
                this.stepButtons = [];
                this.navButtons = new Map();
                const stepRegex = /<button[^>]*class="([^"]*)"[^>]*data-gdd-milestone-step-id="([^"]*)"/g;
                let match;
                while ((match = stepRegex.exec(this._innerHTML)) !== null) {
                  this.stepButtons.push(new Button({ gddMilestoneStepId: unescapeHtml(match[2]) }, match[1]));
                }
                for (const nav of ["previous", "next"]) {
                  const navRegex = new RegExp(`<button[^>]*data-gdd-milestone-nav="${nav}"([^>]*)>`);
                  const navMatch = navRegex.exec(this._innerHTML);
                  if (navMatch) {
                    const button = new Button({ gddMilestoneNav: nav }, "ghost");
                    button.disabled = navMatch[1].includes("disabled");
                    this.navButtons.set(nav, button);
                  }
                }
              }
              get innerHTML() { return this._innerHTML; }
              querySelectorAll(selector) {
                return selector === "[data-gdd-milestone-step-id]" ? this.stepButtons : [];
              }
              querySelector(selector) {
                if (selector === "[data-gdd-milestone-nav='previous']") return this.navButtons.get("previous") || null;
                if (selector === "[data-gdd-milestone-nav='next']") return this.navButtons.get("next") || null;
                return null;
              }
            }
            function unescapeHtml(value) {
              return String(value || "")
                .replace(/&quot;/g, "\"")
                .replace(/&#039;/g, "'")
                .replace(/&gt;/g, ">")
                .replace(/&lt;/g, "<")
                .replace(/&amp;/g, "&");
            }
            const panel = new Panel();
            const elements = new Map([
              ["gddMilestoneStepStatus", panel],
              ["executeCurrentMilestoneStep", new Button()],
              ["confirmCurrentMilestoneStep", new Button()],
              ["submitCurrentMilestoneFeedback", new Button()]
            ]);
            const $ = id => elements.get(id) || null;
            const state = {
              projectId: "project-1",
              gddMilestoneSteps: null,
              selectedGddMilestoneStepId: "",
              gddMilestoneManualSelection: false
            };
            let cachedPayload = null;
            let cacheWrites = [];
            function readProjectStateCache() { return cachedPayload; }
            function writeProjectStateCache(patch = {}) { cacheWrites.push(patch); }
            function renderIterationPlan() {}
            function renderRunsListFromState() {}
            function renderFeedbackRecords() {}
            function applyDraftToForm() {}
            function renderDraftImportStatus() {}
            function renderPrototypeProgress() {}
            function renderPrototypeAcceptanceSummary() {}
            function setPrototypeFormLocked() {}
            function updateChatPanelVisibility() {}
            function renderProjectPackages() {}
            function renderAssetInventory() {}
            function renderRepairPlan() {}
            function callV2() {}
            function isGlobalBusy() { return false; }
            function setButtonDisabledState(button, disabled, reason) {
              button.disabled = !!disabled;
              button.title = disabled ? reason : "";
            }
            function escapeHtml(value) {
              return String(value || "").replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#039;" }[ch]));
            }
            function statusLabel(value) { return String(value || ""); }
            function applyProjectStateCache(projectId) {
              const cached = readProjectStateCache(projectId);
              if (!cached) return;
            }
            function activeGddMilestoneStep(steps, plan) {
              return steps.find(step => step.stepId === plan?.currentStepId)
                || steps.find(step => ["running", "queued", "executing", "feedback_running"].includes(String(step.status || "").trim().toLowerCase()))
                || steps.find(step => !step.locked && step.status !== "confirmed")
                || null;
            }
            function selectedGddMilestoneStep(steps, active) {
              if (!steps.length) return null;
              const selected = state.selectedGddMilestoneStepId
                ? steps.find(step => step.stepId === state.selectedGddMilestoneStepId)
                : null;
              const next = selected || active || steps[0];
              state.selectedGddMilestoneStepId = next?.stepId || "";
              return next || null;
            }
            function selectGddMilestoneStep(stepId, manual = false) {
              state.selectedGddMilestoneStepId = stepId;
              state.gddMilestoneManualSelection = !!manual;
              writeProjectStateCache({ selectedGddMilestoneStepId: stepId, gddMilestoneManualSelection: state.gddMilestoneManualSelection });
              renderGddMilestoneSteps();
            }
            function selectGddMilestoneByOffset(offset) {
              const steps = Array.isArray(state.gddMilestoneSteps?.steps) ? state.gddMilestoneSteps.steps : [];
              if (!steps.length) return;
              const currentIndex = Math.max(0, steps.findIndex(step => step.stepId === state.selectedGddMilestoneStepId));
              const nextIndex = Math.min(steps.length - 1, Math.max(0, currentIndex + offset));
              selectGddMilestoneStep(steps[nextIndex]?.stepId || "", true);
            }
            function gddMilestoneVisualState(step, active) {
              const status = String(step?.status || "ready").trim().toLowerCase();
              if (status === "confirmed") return "done";
              if (active && step?.stepId === active.stepId) return "running";
              if (step?.locked) return "locked";
              return "pending";
            }
            function renderGddMilestoneProgressButton(step, index, selected, active) {
              const visualState = gddMilestoneVisualState(step, active);
              const activeClass = selected?.stepId === step.stepId ? "active" : "";
              const tooltip = step.title || `${step.stepId || `M${index + 1}`}：${step.description || ""}`.trim();
              return `
                <button type="button" class="milestone-progress-button ${visualState} ${activeClass}" data-gdd-milestone-step-id="${escapeHtml(step.stepId)}" title="${escapeHtml(tooltip)}" data-v2-tooltip="${escapeHtml(tooltip)}">
                  <span>模块 ${escapeHtml(String(index + 1))}</span>
                  <span class="milestone-status-square" aria-hidden="true"></span>
                </button>`;
            }
            function renderGddMilestoneStepItem(step, index, active) {
              const isActive = !!active && active.stepId === step.stepId;
              const steps = Array.isArray(state.gddMilestoneSteps?.steps) ? state.gddMilestoneSteps.steps : [];
              return `
                <div class="milestone-detail ${step.locked || !isActive ? "muted" : ""}">
                  <strong>模块 ${escapeHtml(String(index + 1))} · ${escapeHtml(step.title || step.stepId || "")}</strong>
                  <span>${isActive ? "当前激活模块" : "非激活模块，仅可查看"}</span>
                  <div class="milestone-detail-nav">
                    <button type="button" class="ghost" data-gdd-milestone-nav="previous" ${index <= 0 ? "disabled" : ""}>上一个模块</button>
                    <button type="button" class="ghost" data-gdd-milestone-nav="next" ${index >= steps.length - 1 ? "disabled" : ""}>下一个模块</button>
                  </div>
                </div>`;
            }
            function applyGddMilestoneActionState(selected, active) {
              const canUse = !!state.projectId && !!selected && !!active && selected.stepId === active.stepId && !selected.locked && !isGlobalBusy();
              const canSubmitFeedback = !!selected?.canSubmitFeedback || !!selected?.canConfirm;
              setButtonDisabledState($("executeCurrentMilestoneStep"), !(canUse && selected.canExecute), selected ? "只有当前激活模块可以执行。" : "没有可执行的当前模块。");
              setButtonDisabledState($("confirmCurrentMilestoneStep"), !(canUse && selected.canConfirm), selected ? "只有当前激活模块完成执行后可以确认。" : "没有可确认的当前模块。");
              setButtonDisabledState($("submitCurrentMilestoneFeedback"), !(canUse && canSubmitFeedback), selected ? "只有当前激活模块可以提交反馈。" : "没有可反馈的当前模块。");
            }
            function renderGddMilestoneSteps() {
              const plan = state.gddMilestoneSteps;
              const steps = Array.isArray(plan?.steps) ? plan.steps : [];
              const active = activeGddMilestoneStep(steps, plan);
              const selected = selectedGddMilestoneStep(steps, active);
              applyGddMilestoneActionState(selected, active);
              const completedCount = steps.filter(step => gddMilestoneVisualState(step, active) === "done").length;
              const activeIndex = active ? Math.max(0, steps.findIndex(step => step.stepId === active.stepId)) : steps.length;
              const selectedIndex = selected ? Math.max(0, steps.findIndex(step => step.stepId === selected.stepId)) : -1;
              panel.innerHTML = `
                <div class="milestone-progress-shell">
                  <span>共 ${escapeHtml(String(steps.length))} 个模块 · 完成 ${escapeHtml(String(completedCount))} 个 · 当前 ${escapeHtml(active ? `模块 ${activeIndex + 1}` : "全部完成")}</span>
                  <div class="milestone-progress-track">${steps.map((step, index) => renderGddMilestoneProgressButton(step, index, selected, active)).join("")}</div>
                </div>
                ${selected ? renderGddMilestoneStepItem(selected, selectedIndex, active) : ""}`;
              panel.querySelectorAll("[data-gdd-milestone-step-id]").forEach(button => {
                button.onclick = () => selectGddMilestoneStep(button.dataset.gddMilestoneStepId || "", true);
              });
              panel.querySelector("[data-gdd-milestone-nav='previous']")?.addEventListener("click", () => selectGddMilestoneByOffset(-1));
              panel.querySelector("[data-gdd-milestone-nav='next']")?.addEventListener("click", () => selectGddMilestoneByOffset(1));
            }
            function makeSteps(count) {
              return Array.from({ length: count }, (_, index) => ({
                stepId: `M${index + 1}`,
                title: `M${index + 1}`,
                status: index === 0 ? "ready" : "locked",
                locked: index !== 0,
                canExecute: index === 0,
                canConfirm: false,
                canSubmitFeedback: false
              }));
            }
            function assert(condition, message) {
              if (!condition) throw new Error(message);
            }

            cachedPayload = { gddMilestoneSteps: { currentStepId: "M1", steps: makeSteps(5) }, selectedGddMilestoneStepId: "M5", gddMilestoneManualSelection: true };
            applyProjectStateCache("project-1");
            assert(state.gddMilestoneSteps === null, "cached module list must not render before server refresh");
            assert(state.selectedGddMilestoneStepId === "", "cached selected module must not override server-active module");

            state.gddMilestoneSteps = { currentStepId: "M1", steps: makeSteps(10) };
            renderGddMilestoneSteps();
            assert(panel.innerHTML.includes("共 10 个模块"), "module panel should render ten modules");
            const m1 = panel.stepButtons.find(button => button.dataset.gddMilestoneStepId === "M1");
            const m2 = panel.stepButtons.find(button => button.dataset.gddMilestoneStepId === "M2");
            assert(m1.className.includes("running") && m1.className.includes("active"), "ready active module should show yellow/running and selected");
            assert(panel.innerHTML.includes('title="M1"'), "module button should expose title as hover tooltip");
            assert(!panel.innerHTML.includes("<span>M1</span>"), "module button should not show milestone title inline");
            assert(m2.className.includes("locked"), "locked module should show grey/locked");
            assert(!$("executeCurrentMilestoneStep").disabled, "active ready module can execute");
            assert($("confirmCurrentMilestoneStep").disabled, "ready module cannot confirm before execution");

            m2.click();
            assert(state.selectedGddMilestoneStepId === "M2", "clicking a module selects it");
            assert(state.gddMilestoneManualSelection === true, "clicking a module records manual selection");
            assert($("executeCurrentMilestoneStep").disabled, "non-active module actions are disabled");
            assert(panel.innerHTML.includes("非激活模块，仅可查看"), "non-active module is read-only");

            panel.querySelector("[data-gdd-milestone-nav='next']").click();
            assert(state.selectedGddMilestoneStepId === "M3", "next button switches displayed module");
            assert($("executeCurrentMilestoneStep").disabled, "next locked module remains disabled");

            panel.stepButtons.find(button => button.dataset.gddMilestoneStepId === "M1").click();
            state.gddMilestoneSteps.steps[0] = { ...state.gddMilestoneSteps.steps[0], status: "executed", canExecute: false, canConfirm: true, canSubmitFeedback: true };
            renderGddMilestoneSteps();
            assert($("executeCurrentMilestoneStep").disabled, "executed module no longer executes again");
            assert(!$("confirmCurrentMilestoneStep").disabled, "executed active module can be confirmed");
            assert(!$("submitCurrentMilestoneFeedback").disabled, "executed active module can submit feedback");
            state.gddMilestoneSteps.steps[0] = { ...state.gddMilestoneSteps.steps[0], status: "feedback_submitted", canConfirm: true, canSubmitFeedback: false };
            renderGddMilestoneSteps();
            assert(!$("submitCurrentMilestoneFeedback").disabled, "confirmable active module can still submit feedback when legacy payload omits canSubmitFeedback");
            assert(cacheWrites.some(write => write.selectedGddMilestoneStepId === "M3"), "nav selection should be cached");
            """;

        RunNodeScript(node, script);
    }

    [Fact]
    public void RenderShellV2_MilestoneFeedbackModalBehaviorSmoke()
    {
        var node = FindExecutableOnPath("node.exe") ?? FindExecutableOnPath("node");
        if (node is null)
        {
            return;
        }

        const string script = """
            class ClassList {
              constructor() { this.items = new Set(["hidden"]); }
              add(value) { this.items.add(value); }
              remove(value) { this.items.delete(value); }
              contains(value) { return this.items.has(value); }
            }
            class Element {
              constructor(id) {
                this.id = id;
                this.className = "";
                this.classList = new ClassList();
                this.innerHTML = "";
                this.textContent = "";
                this.value = "";
                this.disabled = false;
                this.focused = false;
              }
              focus() { this.focused = true; }
            }
            const elements = new Map([
              ["milestoneFeedbackModal", new Element("milestoneFeedbackModal")],
              ["milestoneFeedbackMeta", new Element("milestoneFeedbackMeta")],
              ["milestoneFeedbackInput", new Element("milestoneFeedbackInput")],
              ["milestoneFeedbackHint", new Element("milestoneFeedbackHint")],
              ["confirmMilestoneFeedback", new Element("confirmMilestoneFeedback")],
              ["globalModel", new Element("globalModel")]
            ]);
            elements.get("globalModel").value = "gpt-5.5";
            const $ = id => elements.get(id) || null;
            const state = {
              projectId: "project-1",
              gddMilestoneSteps: {
                currentStepId: "M1",
                steps: [{
                  stepId: "M1",
                  title: "M1：首个可玩场景",
                  description: "基础操作和 HUD 反馈。",
                  status: "executed",
                  locked: false,
                  canSubmitFeedback: true
                }]
              }
            };
            const apiCalls = [];
            let rendered = 0;
            let loadedSteps = 0;
            let loadedRuns = 0;
            let busyMessage = "";
            function assert(condition, message) {
              if (!condition) throw new Error(message);
            }
            function guardGlobalAction() { return true; }
            function escapeHtml(value) {
              return String(value || "").replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#039;" }[ch]));
            }
            function setModalVisible(id, visible) {
              const modal = $(id);
              if (!modal) return;
              if (visible) modal.classList.remove("hidden");
              else modal.classList.add("hidden");
            }
            function currentGddMilestoneStep() {
              const steps = Array.isArray(state.gddMilestoneSteps?.steps) ? state.gddMilestoneSteps.steps : [];
              return steps.find(step => step.stepId === state.gddMilestoneSteps?.currentStepId) || null;
            }
            function setLocalBusy(value, message = "") { busyMessage = value ? message : ""; }
            async function refreshActiveRun() {}
            function renderGddMilestoneSteps() { rendered += 1; }
            async function loadGddMilestoneSteps() { loadedSteps += 1; }
            async function loadRuns() { loadedRuns += 1; }
            function out() {}
            function showError(error) { throw error; }
            async function api(url, options) {
              apiCalls.push({ url, options });
              return { plan: { currentStepId: "M1", steps: state.gddMilestoneSteps.steps } };
            }
            function openCurrentMilestoneFeedbackModal() {
              if (!guardGlobalAction()) return;
              const step = currentGddMilestoneStep();
              if (!state.projectId || !step) return out("当前没有可反馈的游戏模块。");
              $("milestoneFeedbackMeta").className = "card muted";
              $("milestoneFeedbackMeta").innerHTML = `
                <strong>${escapeHtml(step.stepId || "当前模块")} · ${escapeHtml(step.title || "")}</strong>
                <p class="muted">${escapeHtml(step.description || "")}</p>
              `;
              $("milestoneFeedbackInput").value = "";
              $("milestoneFeedbackHint").textContent = "";
              setModalVisible("milestoneFeedbackModal", true);
              $("milestoneFeedbackInput").focus();
            }
            async function submitCurrentMilestoneFeedback() {
              if (!guardGlobalAction()) return;
              const step = currentGddMilestoneStep();
              if (!state.projectId || !step) return out("当前没有可反馈的游戏模块。");
              const feedback = $("milestoneFeedbackInput").value || "";
              if (!feedback?.trim()) return;
              setLocalBusy(true, "正在提交当前模块的反馈修复。");
              $("confirmMilestoneFeedback").disabled = true;
              $("confirmMilestoneFeedback").textContent = "提交中...";
              $("milestoneFeedbackHint").textContent = "正在根据当前模块反馈启动修复。";
              try {
                const result = await api(`/api/projects/${state.projectId}/gdd-milestone-steps/${encodeURIComponent(step.stepId)}/feedback-run`, {
                  method: "POST",
                  timeoutMs: 3600000,
                  body: JSON.stringify({ feedback, model: $("globalModel").value || "gpt-5.5" })
                });
                out(result);
                state.gddMilestoneSteps = result.plan || state.gddMilestoneSteps;
                setModalVisible("milestoneFeedbackModal", false);
                renderGddMilestoneSteps();
                await loadGddMilestoneSteps();
                await loadRuns();
              } catch (error) {
                $("milestoneFeedbackHint").textContent = "提交失败，请检查反馈内容或稍后重试。";
                showError(error);
              } finally {
                $("confirmMilestoneFeedback").disabled = false;
                $("confirmMilestoneFeedback").textContent = "提交反馈并修正模块";
                setLocalBusy(false);
                await refreshActiveRun();
              }
            }

            (async () => {
              openCurrentMilestoneFeedbackModal();
              assert(!$("milestoneFeedbackModal").classList.contains("hidden"), "feedback modal should open");
              assert($("milestoneFeedbackInput").focused, "feedback textarea should receive focus");
              assert($("milestoneFeedbackMeta").innerHTML.includes("M1：首个可玩场景"), "modal should show current module context");
              $("milestoneFeedbackInput").value = "首个房间敌人出现太快，请延迟 1 秒。";
              await submitCurrentMilestoneFeedback();
              assert(apiCalls.length === 1, "feedback submit should call api once");
              assert(apiCalls[0].url === "/api/projects/project-1/gdd-milestone-steps/M1/feedback-run", "feedback API URL should target current module");
              const payload = JSON.parse(apiCalls[0].options.body);
              assert(payload.feedback.includes("敌人出现太快"), "feedback payload should contain player feedback");
              assert(payload.model === "gpt-5.5", "feedback payload should include selected model");
              assert($("milestoneFeedbackModal").classList.contains("hidden"), "feedback modal should close after success");
              assert($("confirmMilestoneFeedback").disabled === false, "submit button should be re-enabled");
              assert($("confirmMilestoneFeedback").textContent === "提交反馈并修正模块", "submit button label should reset");
              assert(rendered === 1 && loadedSteps === 1 && loadedRuns === 1, "success should refresh module state and runs");
              assert(busyMessage === "", "local busy state should clear");
            })().catch(error => {
              console.error(error);
              process.exit(1);
            });
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
    public void RenderShellV2_ProgressStatusUsesLatestIterationForServerAcceptance()
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
                  runType: "prototype-7day-playable",
                  status: "succeeded",
                  evidenceJson: "{\"validation_only\":true}",
                  progressUpdatedUtc: "2026-06-09T07:06:39.4240706+00:00",
                  runId: "acceptance-new"
                },
                {
                  runType: "prototype-7day-playable",
                  status: "failed",
                  evidenceJson: "{\"validation_only\":true}",
                  progressUpdatedUtc: "2026-06-09T07:07:39.4240706+00:00",
                  runId: "acceptance-failed-after-module"
                },
                {
                  runType: "prototype-7day-playable",
                  status: "succeeded",
                  evidenceJson: "{\"validation_only\":true,\"skeleton_validation_only\":true}",
                  progressUpdatedUtc: "2026-06-09T07:08:39.4240706+00:00",
                  runId: "skeleton-validation-new"
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
            state.iterationPlans = [state.iterationPlan];
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
              return evidence?.validation_only === true && evidence?.skeleton_validation_only !== true;
            }
            function v2IsSkeletonValidationRun(run) {
              const evidence = v2RunEvidence(run);
              return evidence?.validation_only === true && evidence?.skeleton_validation_only === true;
            }
            function v2LatestValidationOnlyAcceptanceRun() {
              return (state.runs || [])
                .filter(run => String(run.runType || "").toLowerCase() === "prototype-7day-playable" && v2IsValidationOnlyRun(run))
                .sort((a, b) => v2RunTimestamp(b) - v2RunTimestamp(a) || String(b.runId || "").localeCompare(String(a.runId || "")))[0] || null;
            }
            function v2LatestSkeletonValidationRun() {
              return (state.runs || [])
                .filter(run => String(run.runType || "").toLowerCase() === "prototype-7day-playable" && v2IsSkeletonValidationRun(run))
                .sort((a, b) => v2RunTimestamp(b) - v2RunTimestamp(a) || String(b.runId || "").localeCompare(String(a.runId || "")))[0] || null;
            }
            function v2IterationSessionTimestamp(plan = state.iterationPlan) {
              const session = plan?.session || null;
              const goals = Array.isArray(plan?.goals) ? plan.goals : [];
              const goalTime = Math.max(0, ...goals.map(goal => v2IsoTime(goal.completedUtc || goal.updatedUtc || goal.createdUtc || "")));
              return goalTime || v2IsoTime(session?.completedUtc || session?.updatedUtc || session?.createdUtc || "");
            }
            function v2RunIsCurrentForIteration(run, plan = state.iterationPlan) {
              if (!run) return false;
              const sessionTime = v2IterationSessionTimestamp(plan);
              if (!sessionTime) return true;
              const runTime = v2IsoTime(run.progressUpdatedUtc || run.updatedUtc || run.completedUtc || run.createdUtc || "");
              return runTime >= sessionTime;
            }
            function v2LatestIterationPlanForGlobalState() {
              const plans = Array.isArray(state.iterationPlans) ? state.iterationPlans.filter(Boolean) : [];
              return plans.length ? plans[plans.length - 1] : state.iterationPlan;
            }
            function v2IterationPlanDone(plan = v2LatestIterationPlanForGlobalState()) {
              const goals = Array.isArray(plan?.goals) ? plan.goals : [];
              return goals.length > 0 && goals.every(goal => ["succeeded", "completed"].includes(String(goal.status || "").trim().toLowerCase()));
            }
            function v2FinalPrototypeAcceptanceRun() {
              const latestPlan = v2LatestIterationPlanForGlobalState();
              const run = v2LatestValidationOnlyAcceptanceRun();
              if (!run || String(run.status || "").toLowerCase() !== "succeeded") return null;
              if (!v2IterationPlanDone(latestPlan)) return null;
              return v2RunIsCurrentForIteration(run, latestPlan) ? run : null;
            }
            function v2StepStatus(stepId) {
              const progressStatus = state?.prototypeFailure ? "failed" : "";
              const progressText = $("prototypeProgress")?.textContent || "";
              const prototypeStatus = String(state?.v2PrototypeStatus || "").trim().toLowerCase();
              const creationStatus = String(state?.v2PrototypeCreationStatus || prototypeStatus || "").trim().toLowerCase();
              const failed = prototypeStatus === "failed" || progressStatus === "failed" || !!state?.prototypeFailure;
              if (stepId === "create-prototype") {
                const skeletonValidation = v2LatestSkeletonValidationRun();
                const skeletonValidationStatus = String(skeletonValidation?.status || "").trim().toLowerCase();
                if (skeletonValidationStatus === "succeeded") return "done";
                if (skeletonValidationStatus === "failed") return "fix";
                if (!state.projectId || progressText.includes("idle") || !creationStatus) return "pending";
                return creationStatus === "failed" ? "fix" : creationStatus === "succeeded" ? "done" : "pending";
              }
              if (stepId === "prototype-acceptance") {
                if (state.v2PrototypeValidationInvalidatedByIteration) return "pending";
                if (v2FinalPrototypeAcceptanceRun()) return "done";
                const latestPlan = v2LatestIterationPlanForGlobalState();
                const validationRun = v2LatestValidationOnlyAcceptanceRun();
                if (validationRun && v2RunIsCurrentForIteration(validationRun, latestPlan) && String(validationRun.status || "").toLowerCase() === "failed") return "fix";
                return failed && v2IterationPlanDone() ? "fix" : "pending";
              }
              if (stepId === "execute-or-repair") {
                const skeletonValidation = v2LatestSkeletonValidationRun();
                const skeletonValidationStatus = String(skeletonValidation?.status || "").trim().toLowerCase();
                if (skeletonValidationStatus === "succeeded") return "done";
                if (skeletonValidationStatus === "failed") return "fix";
                if (failed && creationStatus !== "succeeded") return "fix";
                return creationStatus === "succeeded" ? "done" : "pending";
              }
              return "pending";
            }
            function assert(condition, message) {
              if (!condition) throw new Error(message);
            }
            assert(v2StepStatus("execute-or-repair") === "done", "successful skeleton validation should mark repair step done");
            assert(v2StepStatus("prototype-acceptance") === "fix", "newer final acceptance failure should be shown only on final acceptance");
            state.runs = state.runs.filter(run => run.runId !== "acceptance-failed-after-module");
            assert(v2StepStatus("prototype-acceptance") === "done", "successful server acceptance should be done");
            state.runs = state.runs.filter(run => run.runId !== "acceptance-new");
            assert(v2StepStatus("prototype-acceptance") === "pending", "skeleton validation alone should not complete final acceptance");
            state.prototypeFailure = "older final acceptance failed";
            state.v2PrototypeStatus = "failed";
            state.v2PrototypeCreationStatus = "failed";
            assert(v2StepStatus("create-prototype") === "done", "skeleton validation keeps creation step done even if later prototype status failed");
            assert(v2StepStatus("execute-or-repair") === "done", "older final acceptance failure should not reopen skeleton repair after skeleton validation succeeded");
            state.runs = state.runs.filter(run => run.runId !== "skeleton-validation-new");
            state.runs.push({
              runId: "skeleton-validation-failed",
              runType: "prototype-skeleton-validation",
              status: "failed",
              createdUtc: "2026-06-23T00:06:00Z",
              progressUpdatedUtc: "2026-06-23T00:06:30Z"
            });
            assert(v2StepStatus("create-prototype") === "fix", "failed skeleton validation should mark creation step as fix");
            state.v2PrototypeValidationInvalidatedByIteration = true;
            assert(v2StepStatus("prototype-acceptance") === "pending", "local invalidation should still block until server progress clears it");
            const historicalPlan = state.iterationPlan;
            const latestPlan = {
              session: { updatedUtc: "2026-06-09T07:20:00.0000000+00:00" },
              goals: [{ status: "succeeded", updatedUtc: "2026-06-09T07:20:00.0000000+00:00" }]
            };
            state.v2PrototypeValidationInvalidatedByIteration = false;
            state.prototypeFailure = "";
            state.v2PrototypeStatus = "succeeded";
            state.v2PrototypeCreationStatus = "succeeded";
            state.iterationPlan = historicalPlan;
            state.iterationPlans = [historicalPlan, latestPlan];
            state.runs = state.runs.filter(run => !String(run.runId || "").startsWith("acceptance-latest-"));
            state.runs.push({
              runId: "acceptance-latest-stale",
              runType: "prototype-7day-playable",
              status: "succeeded",
              evidenceJson: "{\"validation_only\":true}",
              progressUpdatedUtc: "2026-06-09T07:10:00.0000000+00:00"
            });
            assert(v2StepStatus("prototype-acceptance") === "pending", "selected historical round must not make stale validation pass for latest round");
            state.runs.push({
              runId: "acceptance-latest-fresh",
              runType: "prototype-7day-playable",
              status: "succeeded",
              evidenceJson: "{\"validation_only\":true}",
              progressUpdatedUtc: "2026-06-09T07:21:00.0000000+00:00"
            });
            assert(v2StepStatus("prototype-acceptance") === "done", "validation after latest round should pass even when historical round is selected");
            """;

        RunNodeScript(node, script);
    }

    [Fact]
    public void RenderShellV2_IterationStepStatusPrioritizesLatestGoalRepairOverMilestones()
    {
        var node = FindExecutableOnPath("node.exe") ?? FindExecutableOnPath("node");
        if (node is null)
        {
            return;
        }

        const string script = """
            const state = {
              iterationPlans: [
                {
                  session: { sessionId: "latest" },
                  goals: [{ status: "failed" }]
                }
              ],
              gddMilestoneSteps: {
                steps: [{ status: "confirmed", locked: false }]
              }
            };
            function v2LatestIterationPlanForGlobalState() {
              const plans = Array.isArray(state.iterationPlans) ? state.iterationPlans.filter(Boolean) : [];
              return plans.length ? plans[plans.length - 1] : state.iterationPlan;
            }
            function v2GlobalIterationGoals() {
              const plan = v2LatestIterationPlanForGlobalState();
              return Array.isArray(plan?.goals) ? plan.goals : [];
            }
            function v2IsRepairGoalStatus(status) {
              return ["needs_fix", "failed"].includes(String(status || "").trim().toLowerCase());
            }
            function v2StepStatus(stepId) {
              if (stepId !== "iteration-plan") return "pending";
              const goals = v2GlobalIterationGoals();
              const goalsDone = goals.length > 0 && goals.every(goal => ["succeeded", "completed", "done"].includes(String(goal.status || "").trim().toLowerCase()));
              if (goals.length) {
                if (goals.some(goal => v2IsRepairGoalStatus(goal.status))) return "fix";
                if (goals.some(goal => ["pending", "running"].includes(String(goal.status || "").trim().toLowerCase()))) return "continue";
                if (!goalsDone) return "pending";
              }
              const milestoneSteps = Array.isArray(state.gddMilestoneSteps?.steps) ? state.gddMilestoneSteps.steps : [];
              if (milestoneSteps.length) {
                if (milestoneSteps.every(step => String(step.status || "").trim().toLowerCase() === "confirmed")) return "done";
                if (milestoneSteps.some(step => !step.locked && ["needs_fix", "execution_failed", "feedback_failed", "timed_out"].includes(String(step.status || "").trim().toLowerCase()))) return "fix";
                if (milestoneSteps.some(step => !step.locked && String(step.status || "").trim().toLowerCase() !== "confirmed")) return "continue";
              }
              if (!goals.length) return "pending";
              if (goalsDone) return "done";
              return "pending";
            }
            function assert(condition, message) {
              if (!condition) throw new Error(message);
            }
            assert(v2StepStatus("iteration-plan") === "fix", "failed latest goal must override confirmed milestone");
            state.iterationPlans[0].goals = [{ status: "pending" }];
            assert(v2StepStatus("iteration-plan") === "continue", "pending latest goal must override confirmed milestone");
            state.iterationPlans[0].goals = [{ status: "succeeded" }];
            assert(v2StepStatus("iteration-plan") === "done", "confirmed milestone can mark done after latest goals are done");
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
            ["createIterationPlan", "evaluateIterationPlan", "deleteIterationPlan", "executeIterationGoal", "iterationAutoRefreshHint", "iterationPlanStatus", "iterationPlanEvaluation", "iterationNeedsFixStatus", "iterationPlanGoals", "gddMilestoneStepStatus", "gddMilestoneStepActions"].forEach(id => add(id === "iterationAutoRefreshHint" ? "p" : "div", id));
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
            function v2ValidateSkeletonIfAllowed() {}
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
                "iterationPlanGoals",
                "gddMilestoneStepStatus",
                "gddMilestoneStepActions"
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
              skeletonAcceptance.textContent = "场景验收";
              skeletonAcceptance.onclick = v2ValidateSkeletonIfAllowed;
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
            assert($("gddMilestoneStepStatus").parentElement.id === "v2IterationPanel", "GDD milestone step status moves to iteration panel");
            assert($("gddMilestoneStepActions").parentElement.id === "v2IterationPanel", "GDD milestone step actions move to iteration panel");
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
        html.Should().Contain("async function v2RestoreProjectUiState(projectId = state.projectId)");
        html.Should().Contain("const remote = await v2FetchProjectUiState(projectId);");
        html.Should().Contain("v2RestoreProjectUiState(state.projectId);");
        html.Should().Contain("v2LoadProjectUiStateTabState(source)");
        html.Should().Contain("v2RestoredProjectUiStateId = \"\"");
        html.Should().Contain("if (state.projectId && state.projectId !== projectId)");
        html.Should().Contain("state.projectId && !currentProjectVisible");
        html.Should().Contain("v2ActiveTabId = \"chat\";");
        html.Should().Contain("v2SelectedStep = \"new-project\";");
        html.Should().Contain("v2RenderTabs();");
        html.Should().Contain("const currentProjectCancelled = !!state.cancelledActiveRunId && state.cancelledActiveRunProjectId === state.projectId;");
        html.Should().Contain("if (currentProjectCancelled || readCancelledPrototypeMarker(state.projectId)) return false;");
        html.Should().Contain("window.addEventListener(\"beforeunload\", () =>");
        html.Should().Contain("callV2(\"v2WriteProjectUiState\")");
        html.Should().NotContain("window.addEventListener(\"beforeunload\", v2WriteProjectUiState)");
        html.Should().Contain("function v2EmbeddedTabUrl(tab)");
        html.Should().Contain("function v2EmbeddedFrameId(tab)");
        html.Should().Contain("v2LoadEmbeddedFrame(frameId, url, true)");
        html.Should().Contain("function v2LoadEmbeddedFrame(frameId, url, forceReload = false)");
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
        html.Should().NotContain("v2RenderUiOptimizationStatus");
        html.Should().NotContain("游戏界面优化已完成，短验证已通过");
        html.Should().NotContain("左侧进度栏已标记为完成");
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
        html.Should().Contain("skeletonAcceptance.onclick = v2ValidateSkeletonIfAllowed");
        html.Should().Contain("async function validatePrototypeSkeleton(autoTriggered = false)");
        html.Should().Contain("await validatePrototypeSkeleton(true);");
        html.Should().Contain("/prototype-7day-playable/validate-skeleton");
        html.Should().Contain("v2PrototypeAcceptanceBlockReason");
        html.Should().Contain("v2AcceptanceActionStatus");
        html.Should().Contain("await validatePrototype();");
        html.Should().Contain("v2IterationPlanAllowsAcceptance");
        html.Should().NotContain("goals.length === 0) return true");
        html.Should().Contain("请先生成并完成当前游戏模块，所有任务完成后再进行原型项目验收。");
        html.Should().Contain("请先完成当前游戏模块，所有任务完成后再进行原型项目验收。");
        html.Should().Contain("const legacyRerun = $(\"validatePrototype\");");
        html.Should().Contain("if (legacyRerun) setButtonDisabledState(legacyRerun, !!reason, reason || \"\");");
        html.Should().Contain("validatePrototype = async function() {");
        html.Should().Contain("const reason = v2PrototypeAcceptanceBlockReason();");
        html.Should().Contain("原型项目验收入口会在游戏模块完成后启用。");
        html.Should().NotContain("游戏界面优化是可选步骤，不会阻塞验收。");
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
        html.Should().NotContain("if (stepId === \"ui-optimization\") return \"v2UiOptimizationPanel\";");
        html.Should().NotContain("v2CreateUiOptimizationPanel();");
        html.Should().NotContain("$(\"createProjectPackage\")?.click()");
        html.Should().Contain("v2ApplyPrototypeFormLock");
        html.Should().Contain("v2ShouldLockPrototypeForm");
        html.Should().Contain("v2-prototype-locked");
        html.Should().Contain("setPrototypeDraftFileLocked(locked);");
        html.Should().Contain("setButtonDisabledState($(\"importDraft\"), locked");
        html.Should().Contain("游戏场景已验收通过，不能重复创建");
        html.Should().Contain("prototypeSkeletonLocked()");
        html.Should().Contain("M1 游戏场景已完成");
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
        html.Should().Contain("let authEpoch = 0;");
        html.Should().Contain("function bumpAuthEpoch()");
        html.Should().Contain("function projectRequestContext(projectId = state.projectId)");
        html.Should().Contain("function isCurrentProjectRequest(projectId, requestAuthEpoch = authEpoch)");
        html.Should().Contain("function runBelongsToCurrentProject(run)");
        html.Should().Contain("function currentProjectHasBusyRun()");
        html.Should().Contain("function projectSwitchLocked()");
        html.Should().Contain("function updateProjectSwitchAvailability()");
        html.Should().Contain("button.disabled = locked && !!state.projectId;");
        html.Should().Contain("if (projectSwitchLocked() && state.projectId)");
        html.Should().Contain("当前操作完成前不能切换项目。");
        html.Should().Contain("state.chatBusy = true;");
        html.Should().Contain("state.chatBusy = false;");
        html.Should().Contain("state.workflowRouteBusy = true;");
        html.Should().Contain("state.workflowRouteBusy = false;");
        html.Should().Contain("!!state.workflowRouteBusy");
        html.Should().Contain("currentProjectHasBusyRun()");
        html.Should().Contain("async function loadProjectRuntimeState()");
        html.Should().Contain("const projectId = state.projectId;");
        html.Should().Contain("state.prototypeReadyForFeedback = false;");
        html.Should().Contain("state.draftAnalysisRunning = false;");
        html.Should().Contain("state.v2PrototypeAcceptanceStatus = \"\";");
        html.Should().Contain("if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;");
        html.Should().Contain("try { v2RenderProgress(); } catch {}");
        html.Should().Contain("if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return false;");
        html.Should().Contain("state.iterationPlan = null;");
        html.Should().Contain("state.iterationPlans = [];");
        html.Should().Contain("state.selectedIterationSessionId = \"\";");
        html.Should().Contain("const projectStateCacheVersion = 2;");
        html.Should().Contain("function normalizeIterationPlanRounds(rounds)");
        html.Should().Contain("normalizeIterationPlanRounds(Array.isArray(result?.rounds) ? result.rounds : [])");
        html.Should().Contain("normalizeIterationPlanRounds(Array.isArray(cached.iterationPlans) ? cached.iterationPlans : [])");
        html.Should().Contain("writeProjectStateCache({ prototypeProgress: progress }, projectId)");
        html.Should().Contain("writeProjectStateCache({ packageList: result }, projectId)");
        html.Should().Contain("writeProjectStateCache({ assetInventory: result }, projectId)");
        html.Should().Contain("await loadProjectPackages();");
        html.Should().Contain("renderRunsListFromState");
        html.Should().NotContain("if (v2SelectedStep === \"create-prototype\") $(\"prototypeWorkflowPanel\")?.classList.remove(\"hidden\")");
        html.Should().Contain("[\"create-prototype\", \"游戏场景创建\", \"spark\"]");
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
        html.Should().Contain("游戏场景创建");
        html.Should().Contain("完成游戏模块");
        html.Should().Contain("场景验收修复");
        html.IndexOf("[\"execute-or-repair\", \"场景验收修复\", \"wrench\"]", StringComparison.Ordinal).Should().BeLessThan(html.IndexOf("[\"iteration-plan\", \"完成游戏模块\", \"list\"]", StringComparison.Ordinal));
        html.IndexOf("[\"iteration-plan\", \"完成游戏模块\", \"list\"]", StringComparison.Ordinal).Should().BeLessThan(html.IndexOf("[\"prototype-acceptance\", \"原型项目验收\", \"check\"]", StringComparison.Ordinal));
        html.Should().NotContain("[\"ui-optimization\", \"游戏界面优化\", \"layout\"]");
        html.Should().Contain("function v2LatestIterationPlanForGlobalState()");
        html.Should().Contain("function v2GlobalIterationGoals()");
        html.Should().Contain("function v2IsRepairGoalStatus(status)");
        html.Should().Contain("function v2RunIsCurrentForIteration(run, plan = state.iterationPlan)");
        html.Should().Contain("const sessionTime = v2IterationSessionTimestamp(plan);");
        html.Should().Contain("const latestPlan = v2LatestIterationPlanForGlobalState();");
        html.Should().Contain("return v2RunIsCurrentForIteration(run, latestPlan) ? run : null;");
        html.Should().Contain("const goalTime = Math.max(0, ...goals.map(goal => v2IsoTime(goal.completedUtc || goal.updatedUtc || goal.createdUtc || \"\")));");
        html.Should().NotContain("if (!run || !v2RunIsCurrentForIteration(run)) return \"pending\";");
        html.Should().Contain("function v2LatestSkeletonValidationRun()");
        html.Should().Contain("function v2SkeletonValidationSucceeded()");
        html.Should().Contain("acceptanceStatus === \"succeeded\" || v2HasPrototypeSkeleton() || v2SkeletonValidationSucceeded()");
        html.Should().Contain("String(state.v2PrototypeAcceptanceStatus || \"\").trim().toLowerCase() === \"succeeded\" ||");
        html.Should().Contain("const skeletonValidation = v2LatestSkeletonValidationRun();");
        html.Should().Contain("if (skeletonValidationStatus === \"succeeded\") return \"done\";");
        html.Should().Contain("if (skeletonValidationStatus === \"failed\") return \"fix\";");
        html.Should().NotContain("if (substep === \"validation_skipped\") return \"pending\";");
        html.Should().NotContain("if (substep === \"validation_failed\") return \"fix\";");
        html.Should().NotContain("setButtonDisabledState($(\"runUiOptimization\"), true");
        html.Should().NotContain("out(\"游戏界面优化暂未开放。\")");
        html.Should().Contain("v2RepairPanel");
        html.Should().Contain("v2CreateRepairPanel");
        html.Should().Contain("const goals = state.repairPlan?.goals || []");
        html.Should().Contain("if (failed && !v2HasPrototypeSkeleton()) return \"fix\";");
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
        html.Should().Contain("function chatHistoryDownloadFileName(projectId = state.projectId)");
        html.Should().Contain("const projectId = state.projectId;");
        html.Should().Contain("const result = await api(`/api/projects/${projectId}/chat-history`);");
        html.Should().Contain("const requestAuthEpoch = authEpoch;");
        html.Should().Contain("if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return out(\"项目或登录状态已切换，本次聊天记录下载已取消。\");");
        html.Should().Contain("anchor.download = chatHistoryDownloadFileName(projectId);");
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
        html.Should().Contain("/api/projects/${projectId}/gdd");
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
        html.Should().Contain("(mode === \"new\" || mode === \"new-gdd-milestone\") && !typedMessage");
        html.Should().Contain("v2IterationRoundTabs");
        html.Should().Contain("v2-round-tab");
        html.Should().Contain("/iteration-plans");
        html.Should().Contain("selectIterationPlanForDisplay");
        html.Should().Contain("isDisplayingLatestIterationPlan");
        html.Should().Contain("第 ${Number(plan?.roundIndex || index + 1)} 轮");
        html.Should().Contain("v2IterationMainActions");
        html.Should().Contain("legacy-iteration-plan-ui");
        html.Should().Contain("body.v2-detail #iterationPlanEvaluation");
        html.Should().Contain("body.v2-detail #v2IterationSummary");
        html.Should().Contain("body.v2-detail #iterationNeedsFixStatus");
        html.Should().Contain("gddMilestoneManualSelection");
        html.Should().Contain("ensureProjectPageFallback(state.projects, false)");
        html.Should().Contain("showUserLoadingFallback();");
        html.Should().Contain("function recoverVisiblePageFromClientError(error)");
        html.Should().Contain("window.addEventListener(\"error\"");
        html.Should().Contain("window.addEventListener(\"unhandledrejection\"");
        html.Should().Contain("void loadProjectRuntimeState().catch(recoverVisiblePageFromClientError)");
        html.IndexOf("showProjectDetail();", StringComparison.Ordinal).Should().BeLessThan(html.IndexOf("void loadProjectRuntimeState().catch(recoverVisiblePageFromClientError)", StringComparison.Ordinal));
        html.Should().Contain("await Promise.allSettled([");
        html.Should().Contain("正在读取项目列表");
        html.Should().NotContain("state.gddMilestoneSteps = cached.gddMilestoneSteps");
        html.Should().Contain("writeProjectStateCache({ gddMilestoneSteps: result, selectedGddMilestoneStepId: state.selectedGddMilestoneStepId, gddMilestoneManualSelection: state.gddMilestoneManualSelection }, projectId)");
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
        html.Should().Contain("/api/projects/${projectId}/workflow-route");
        html.Should().NotContain("/api/projects/${state.projectId}/workflow-route");
        html.Should().Contain("/api/projects/${projectId}/workflow-route/intent");
        html.Should().Contain("const result = await api(`/api/projects/${projectId}/chat`");
        html.Should().Contain("if (!guardGlobalAction()) return;");
        html.Should().Contain("await loadServerChatHistoryForProject(projectId, context.authEpoch);");
        html.Should().Contain("async function queryWorkflowRoute(intent = null, projectId = state.projectId, allowCurrentBusy = false, requestAuthEpoch = authEpoch)");
        html.Should().Contain("if (!allowCurrentBusy && isGlobalBusy()) return out(\"当前有任务正在执行，请等待当前任务完成后再扫描项目状态。\");");
        html.Should().Contain("const route = await fetchWorkflowRoute(intent, projectId);");
        html.Should().Contain("async function fetchWorkflowRoute(intent = null, projectId = state.projectId)");
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
        html.Should().NotContain("v2OpenStepTab(\"ui-optimization\", false)");
        html.Should().Contain("游戏界面优化当前未作为主流程开放，请继续进行原型项目验收或打包试玩。");
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
        html.Should().Contain("fetchWorkflowRoute(message.workflowIntent, projectId)");
        html.Should().Contain("if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;");
        html.Should().Contain("workflowActionsMatch");
        Regex.IsMatch(
                html,
                @"\}\s*finally\s*\{\s*if \(!isCurrentProjectRequest\(projectId, requestAuthEpoch\)\) return;\s*state\.workflowRouteBusy = false;",
                RegexOptions.CultureInvariant)
            .Should().BeTrue();
        html.Should().Contain("项目进度已经变化，请重新点击");
        html.Should().Contain("无法确认当前项目进度，请重新点击");
        html.Should().Contain("if (message.workflowActionConsumed || state.workflowRouteActionToken !== token) return;");
        html.Should().Contain("let shouldClearChatAttachments = false;");
        html.Should().Contain("shouldClearChatAttachments = true;");
        html.Should().Contain("if (shouldClearChatAttachments) clearChatAttachments();");
        html.Should().NotContain("invalidateWorkflowRouteAction();\n                  switch (action.actionId)");
        html.Should().Contain("if (busy) invalidateWorkflowRouteAction();");
        html.IndexOf("if (routeIntent?.shouldRoute)", StringComparison.Ordinal).Should().BeLessThan(html.IndexOf("const result = await api(`/api/projects/${projectId}/chat`", StringComparison.Ordinal));
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
        html.Should().Contain("/api/projects/${projectId}/prototype-7day-playable/progress");
    }

    [Fact]
    public void RenderProject_IncludesDefaultDetailProgressWithPendingUnrunSteps()
    {
        var project = CreateProjectSnapshot();

        var html = new BrowserUiRenderer().RenderProject(project, []);

        html.Should().Contain("detail-progress");
        html.Should().Contain("grid-template-columns: repeat(7, minmax(5.6rem, 1fr))");
        html.Should().NotContain("grid-template-columns: repeat(9, minmax(5.6rem, 1fr))");
        html.Should().Contain("detail-step-number\">1</span>");
        html.Should().Contain("detail-step-number\">7</span>");
        html.Should().NotContain("detail-step-number\">8</span>");
        html.Should().Contain("打包下载项目");
        html.Should().Contain("detail-step pending");
        html.Should().NotContain("detail-step fix");
        html.Should().NotContain("detail-step done\" href=\"/#prototypeWorkflowPanel\"");
        html.Should().NotContain("detail-step done\" href=\"/assets?projectId=project-1\"");
        html.Should().NotContain("detail-step done\" href=\"/#createProjectPackage\"");
    }

    [Fact]
    public void RenderRun_HidesInternalGeneratorBranding()
    {
        var run = new RunSnapshot(
            "run-1",
            "project-1",
            "workspace-1",
            "game-design-gdd",
            "failed",
            "2026-06-22T00:00:00Z",
            null,
            null,
            null,
            1,
            "BMAD created output through Codex CLI and CODEX.",
            "codex_failed: Codex stderr via codex_cli.",
            "{\"gateway\":\"codex-cli\",\"fallback\":\"codex cli\",\"skill\":\"BMAD\"}");
        var artifact = new ArtifactSnapshot(
            "artifact-1",
            "run-1",
            "project-1",
            "game-design-gdd-codex-output",
            "logs/phase-a-gdd/run-1/codex-output.txt",
            "BMAD Codex output");

        var html = new BrowserUiRenderer().RenderRun(run, [artifact]);

        html.Should().NotContain("BMAD");
        html.Should().NotContain("Codex");
        html.Should().NotContain("CODEX");
        html.Should().NotContain("codex");
        html.Should().NotContain("generation-cli");
        html.Should().NotContain("generation_cli");
        html.Should().Contain("generation");
        html.Should().Contain("Generation result");
        html.Should().NotContain("game-design-gdd-generation-output");
    }

    [Fact]
    public void RenderProject_MarksSkeletonRepairDone_WhenPrototypeCreationSucceededWithoutRepair()
    {
        var project = CreateProjectSnapshot();
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
    public void RenderProject_MarksSkeletonStepsDone_WhenM1MilestoneCompleted()
    {
        var metaPath = Path.Combine(Path.GetTempPath(), $"phasea-meta-{Guid.NewGuid():N}");
        try
        {
            Directory.CreateDirectory(Path.Combine(metaPath, "routes", "gdd-milestones"));
            File.WriteAllText(
                Path.Combine(metaPath, "routes", "gdd-milestones", "latest.json"),
                """
                {
                  "currentStepId": "M2",
                  "steps": [
                    { "stepId": "M1", "status": "needs_fix", "locked": false, "confirmedUtc": "2026-06-24T00:00:00Z" },
                    { "stepId": "M2", "status": "ready", "locked": false }
                  ]
                }
                """);
            var project = CreateProjectSnapshot() with { MetaPath = metaPath };
            var failedPrototypeRun = new RunReadbackItem(
                "run-failed-prototype",
                "project-1",
                "workspace-1",
                "prototype-7day-playable",
                "failed",
                1,
                "",
                "",
                "{\"prototype_completion\":{\"succeeded\":false}}",
                "failed",
                "",
                "Prototype workflow failed.",
                "2026-06-23T08:31:29.4240706+00:00",
                null,
                null,
                null,
                null,
                []);
            var failedRepairRun = new RunReadbackItem(
                "run-failed-repair",
                "project-1",
                "workspace-1",
                "prototype-quick-fix",
                "failed",
                1,
                "",
                "",
                "{}",
                "failed",
                "",
                "Repair failed.",
                "2026-06-23T08:33:29.4240706+00:00",
                null,
                null,
                null,
                null,
                []);

            var html = new BrowserUiRenderer().RenderProject(project, [failedPrototypeRun, failedRepairRun]);

            html.Should().Contain("detail-step done\" href=\"/#prototypeWorkflowPanel\"");
            html.Should().Contain("detail-step done\" href=\"/#v2RepairPanel\"");
            html.Should().NotContain("detail-step fix\" href=\"/#prototypeWorkflowPanel\"");
            html.Should().NotContain("detail-step fix\" href=\"/#v2RepairPanel\"");
        }
        finally
        {
            if (Directory.Exists(metaPath))
            {
                Directory.Delete(metaPath, recursive: true);
            }
        }
    }

    [Fact]
    public void RenderProject_KeepsSkeletonCreationDone_WhenLaterPrototypeRunFailsAfterSkeletonValidationPassed()
    {
        var project = CreateProjectSnapshot();
        var skeletonValidationRun = new RunReadbackItem(
            "run-skeleton-validation",
            "project-1",
            "workspace-1",
            "prototype-7day-playable",
            "succeeded",
            0,
            "",
            "",
            "{\"validation_only\":true,\"skeleton_validation_only\":true}",
            "succeeded",
            "skeleton_validation",
            "Prototype skeleton validation passed.",
            "2026-06-22T18:43:59.4240706+00:00",
            null,
            null,
            null,
            null,
            []);
        var laterFailedPrototypeRun = new RunReadbackItem(
            "run-later-failed-prototype",
            "project-1",
            "workspace-1",
            "prototype-7day-playable",
            "failed",
            1,
            "",
            "",
            "{\"prototype_completion\":{\"succeeded\":false}}",
            "failed",
            "",
            "Prototype workflow failed.",
            "2026-06-23T08:31:29.4240706+00:00",
            null,
            null,
            null,
            null,
            []);

        var html = new BrowserUiRenderer().RenderProject(project, [laterFailedPrototypeRun, skeletonValidationRun]);

        html.Should().Contain("detail-step done\" href=\"/#prototypeWorkflowPanel\"");
        html.Should().Contain("detail-step done\" href=\"/#v2RepairPanel\"");
        html.Should().NotContain("detail-step fix\" href=\"/#prototypeWorkflowPanel\"");
        html.Should().NotContain("detail-step fix\" href=\"/#v2RepairPanel\"");
    }

    [Fact]
    public void RenderProject_MarksFinalAcceptanceDone_OnlyAfterValidationOnlyRunFollowsIteration()
    {
        var project = CreateProjectSnapshot();
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
    public void RenderProject_DoesNotKeepIterationFix_WhenLaterGoalRepairSucceeded()
    {
        var project = CreateProjectSnapshot();
        var failedIterationRun = new RunReadbackItem(
            "run-iteration-failed",
            "project-1",
            "workspace-1",
            "prototype-iteration-goal",
            "failed",
            1,
            "",
            "",
            "{}",
            "failed",
            "",
            "Iteration goal failed.",
            "2026-06-09T07:05:39.4240706+00:00",
            null,
            null,
            null,
            null,
            []);
        var succeededGoalRepair = new RunReadbackItem(
            "run-goal-repair",
            "project-1",
            "workspace-1",
            "prototype-quick-fix",
            "succeeded",
            0,
            "",
            "",
            "{\"quick_fix\":true,\"goal_repair\":true,\"goal_repair_status\":\"succeeded\"}",
            "succeeded",
            "",
            "Goal repair completed.",
            "2026-06-09T07:06:39.4240706+00:00",
            null,
            null,
            null,
            null,
            []);

        var html = new BrowserUiRenderer().RenderProject(project, [succeededGoalRepair, failedIterationRun]);

        html.Should().Contain("detail-step pending\" href=\"/#v2IterationPanel\"");
        html.Should().NotContain("detail-step fix\" href=\"/#v2IterationPanel\"");
    }

    [Fact]
    public void RenderProject_MarksFinalAcceptanceDone_WhenValidationFollowsSuccessfulGoalRepair()
    {
        var project = CreateProjectSnapshot();
        var failedIterationRun = new RunReadbackItem(
            "run-iteration-failed",
            "project-1",
            "workspace-1",
            "prototype-iteration-goal",
            "failed",
            1,
            "",
            "",
            "{}",
            "failed",
            "",
            "Iteration goal failed.",
            "2026-06-09T07:05:39.4240706+00:00",
            null,
            null,
            null,
            null,
            []);
        var succeededGoalRepair = new RunReadbackItem(
            "run-goal-repair",
            "project-1",
            "workspace-1",
            "prototype-quick-fix",
            "succeeded",
            0,
            "",
            "",
            "{\"quick_fix\":true,\"goal_repair\":true,\"goal_repair_status\":\"succeeded\"}",
            "succeeded",
            "",
            "Goal repair completed.",
            "2026-06-09T07:06:39.4240706+00:00",
            null,
            null,
            null,
            null,
            []);
        var finalValidation = new RunReadbackItem(
            "run-final-validation",
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
            "Final validation completed.",
            "2026-06-09T07:07:39.4240706+00:00",
            null,
            null,
            null,
            null,
            []);

        var html = new BrowserUiRenderer().RenderProject(project, [finalValidation, succeededGoalRepair, failedIterationRun]);

        html.Should().Contain("detail-step done\" href=\"/#v2AcceptancePanel\"");
        html.Should().NotContain("detail-step pending\" href=\"/#v2AcceptancePanel\"");
    }

    [Fact]
    public void RenderProject_MarksDownloadDone_WhenPackageExists()
    {
        var project = CreateProjectSnapshot();
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
    public void RenderProject_ShouldNotExposeUiOptimizationAsMainDetailStep()
    {
        var project = CreateProjectSnapshot();
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

        html.Should().NotContain("href=\"/#v2UiOptimizationPanel\"");
        html.Should().NotContain("<span class=\"detail-step-label\">游戏界面优化</span>");
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
        html.Should().Contain("cache: fetchOptions.cache || \"no-store\"");
        html.Should().Contain("cancelActiveRun");
        html.Should().Contain("function canCancelActiveRun(run)");
        html.Should().Contain("function scheduleActiveRunRefresh(attempts = 8, delayMs = 750, requireLocalBusy = true)");
        html.Should().Contain("runBelongsToCurrentProject(run)");
        html.Should().Contain("function runIsBusy(run)");
        html.Should().Contain("game-design-gdd-section-batch");
        html.Should().Contain(@"\u7b56\u5212\u5927\u7eb2\u8865\u5168\u4e2d\uff1a");
        html.Should().Contain("if (!run.runId) return false;");
        html.Should().Contain("status === \"queued\" || status === \"running\"");
        html.Should().Contain("const hadTrackedBusyRun = runIsBusy(state.activeRun) || hasPendingPrototypeSkeletonBannerRun();");
        html.Should().Contain("refreshCurrentProjectAfterActiveRunSettled");
        html.Should().Contain("loadGddMilestoneSteps()");
        html.Should().Contain("state.cancelledActiveRunId && activeRun?.runId === state.cancelledActiveRunId");
        html.Should().Contain("state.cancelledActiveRunProjectId = runProjectId;");
        html.Should().Contain("if (isPrototypeSkeletonCreationRun(run) && runProjectId)");
        html.Should().Contain("writeCancelledPrototypeMarker(runId, runProjectId);");
        html.Should().Contain("if (cancelledCurrentPrototypeRun)");
        html.Should().Contain("writeProjectStateCache({ prototypeProgress: cancelledPrototypeProgressSnapshot() }, runProjectId);");
        html.Should().Contain("state.v2PrototypeCreationStatus = \"idle\";");
        html.Should().Contain("if (!activeRun?.runId)");
        html.Should().Contain("if (hadTrackedBusyRun && state.localBusy)");
        html.Should().Contain("function hideActiveRunBanner()");
        html.Should().Contain("function setButtonVisualState(button, enabled)");
        html.Should().Contain("function setButtonBaseClass(button, baseClassName)");
        html.Should().Contain("function cancelledPrototypeProgressSnapshot()");
        html.Should().Contain("function cancelledPrototypeMarkerKey(projectId = state.projectId)");
        html.Should().Contain("function writeCancelledPrototypeMarker(runId, projectId = state.projectId)");
        html.Should().Contain("function readCancelledPrototypeMarker(projectId = state.projectId)");
        html.Should().Contain("function setPrototypeDraftFileLocked(locked)");
        html.Should().Contain("function setButtonDisabledState(button, disabled, title = \"\")");
        html.Should().Contain("function resetPrototypeActionButtonsVisualState()");
        html.Should().Contain("function unlockPrototypeFormAfterCancel()");
        html.Should().Contain("if (cancelledCurrentPrototypeRun) unlockPrototypeFormAfterCancel();");
        html.Should().Contain("setButtonBaseClass($(\"runPrototype\"), \"secondary\");");
        html.Should().Contain("setButtonBaseClass($(\"importDraft\"), \"secondary import-draft-button\");");
        html.Should().Contain("button.classList.remove(\"button-state-enabled\", \"button-state-disabled\", \"import-draft-ready\");");
        html.Should().Contain("if ([\"queued\", \"running\"].includes(creationStatus))");
        html.Should().Contain("const currentProjectCancelled = !!state.cancelledActiveRunId && state.cancelledActiveRunProjectId === projectId;");
        html.Should().Contain("if (currentProjectCancelled || readCancelledPrototypeMarker(projectId))");
        html.Should().Contain("phaseA.prototypeSkeletonBanner.${projectId || \"none\"}.${runId || \"none\"}");
        html.Should().Contain("phaseA.prototypeSkeletonBanner.current.${projectId || \"none\"}");
        html.Should().Contain("projectId: state.projectId || \"\"");
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
        html.Should().Contain("function prototypeSkeletonBannerStorageKey(runId = state.prototypeSkeletonBannerRunId, projectId = state.projectId)");
        html.Should().Contain("function prototypeSkeletonBannerCurrentKey(projectId = state.projectId)");
        html.Should().Contain("function prototypeSkeletonBannerStoredRunId()");
        html.Should().Contain("runStartupStep(\"restorePrototypeSkeletonBannerFromStorage\", restorePrototypeSkeletonBannerFromStorage);");
        html.Should().Contain("void refreshActiveRun();");
        html.Should().Contain("state.pendingPrototypeSkeletonRun = {");
        html.Should().Contain("state.pendingPrototypeSkeletonRun = null;");
        html.Should().Contain("resetPrototypeSkeletonBannerState(false);");
        html.Should().Contain("const skeletonRun = skeletonBannerRun();");
        html.Should().NotContain("const skeletonRun = skeletonBannerRun() || state.pendingPrototypeSkeletonRun;");
        html.Should().Contain("hasPendingPrototypeSkeletonBannerRun()");
        html.Should().Contain("runIsBusy(state.pendingPrototypeSkeletonRun)");
        html.Should().Contain("if (state.pendingPrototypeSkeletonRun?.runId)");
        html.Should().Contain("activeRun.runId !== pendingRunId");
        html.Should().Contain("state.pendingPrototypeSkeletonRun.status = state.pendingPrototypeSkeletonRun.status || \"running\";");
        html.Should().Contain("if (runIsBusy(state.activeRun) && !isInlineOnlyRun(state.activeRun) && runBelongsToCurrentProject(state.activeRun))");
        html.Should().Contain("const observedProjectId = runProjectId(state.activeRun) || state.projectId;");
        html.Should().Contain("startProjectRunPolling(state.activeRun.runId, observedProjectId, authEpoch);");
        html.Should().Contain("busy: runIsBusy(run)");
        html.Should().Contain("if (!runIsBusy(run))");
        html.Should().Contain("if (state.localBusy) state.localBusy = false;");
        html.Should().Contain("runBelongsToCurrentProject(activeRun)");
        html.Should().Contain("async function refreshPrototypeSkeletonRun(runId, projectId = state.projectId, requestAuthEpoch = authEpoch)");
        html.Should().Contain("const actualProjectId = runProjectId(run) || projectId;");
        html.Should().Contain("if (actualProjectId !== projectId || !isCurrentProjectRequest(projectId, requestAuthEpoch)) return;");
        html.Should().Contain("refreshPrototypeSkeletonRun(skeletonRun.runId, runProjectId(skeletonRun) || state.projectId)");
        html.Should().Contain("localStorage.setItem(prototypeSkeletonBannerCurrentKey(), state.prototypeSkeletonBannerRunId);");
        html.Should().Contain("readPrototypeSkeletonBannerState(run.runId, state.projectId)");
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
        html.Should().Contain("phasea:active-run-refresh");
        html.Should().Contain("const eventRunId = String(event.data?.runId || \"\").trim();");
        html.Should().Contain("startProjectRunPolling(eventRunId, eventProjectId, authEpoch);");
        html.Should().Contain("void refreshActiveRun();");
        html.Should().Contain("scheduleActiveRunRefresh(8, 750, false);");
        html.Should().Contain("function scheduleActiveRunRefresh(attempts = 8, delayMs = 750, requireLocalBusy = true)");
        html.Should().Contain("(!requireLocalBusy || state.localBusy || runIsBusy(state.activeRun) || hasPendingPrototypeSkeletonBannerRun())");
        html.Should().Contain("Access token");
        html.Should().Contain("phaseAAccessToken");
        html.Should().Contain("gddQuestionFormModal");
        html.Should().Contain("gddQuestionForm");
        html.Should().Contain("question-form");
        html.Should().Contain("function fallbackGddQuestionFormFields()");
        html.Should().Contain("async function loadGddQuestionFormSchema(projectId, requestToken, signal)");
        html.Should().Contain("function openGddQuestionFormModal()");
        html.Should().Contain("function confirmGddQuestionForm()");
        html.Should().Contain("function startGddDocumentRoute(message, sceneRoute = null)");
        html.Should().Contain("/gdd/question-form");
        html.Should().Contain("/gdd/question-form/restore-latest");
        html.Should().Contain("function restoreValuesForGddQuestionForm");
        html.Should().Contain("已导入上一次填写的");
        html.Should().Contain("/gdd/scene-route");
        html.Should().Contain("data-gdd-scene-route-json");
        html.Should().Contain("state.gddSceneRoute");
        html.Should().Contain("sceneRoute");
        html.Should().Contain("state.gddQuestionFormFields");
        html.Should().Contain("state.gddQuestionFormAnswers");
        html.Should().Contain("gddQuestionFormRequestToken");
        html.Should().Contain("gddQuestionFormAbortController");
        html.Should().Contain("gddQuestionFormSchemaCache");
        html.Should().Contain("gddQuestionFormDraftCache");
        html.Should().Contain("function saveGddQuestionFormDraft()");
        html.Should().Contain("function readGddQuestionFormDraft(signature)");
        html.Should().Contain("function clearGddQuestionFormDraft()");
        html.Should().Contain("gddQuestionFormProgressTimer");
        html.Should().Contain("gddQuestionFormProgressDurationMs");
        html.Should().Contain("function updateGddQuestionFormProgress(percent)");
        html.Should().Contain("function stopGddQuestionFormProgress()");
        html.Should().Contain("aria-valuemax=\"99\"");
        html.Should().Contain("gddQuestionFormProgressValue");
        html.Should().Contain("maxlength=");
        html.Should().Contain("gddQuestionFormMessageBudget");
        html.Should().Contain("gddQuestionFormFallbackCacheTtlMs");
        html.Should().Contain("gddQuestionFormSchemaTimeoutMs");
        html.Should().Contain("isCurrentGddQuestionFormRequest");
        html.Should().Contain("abortController.signal");
        html.Should().Contain("state.gddQuestionFormAbortController.abort()");
        html.Should().Contain("writeGddQuestionFormSchemaCache");
        html.Should().Contain("GDD question-form raw material:");
        html.Should().Contain("Use these answers as authoritative raw material");
        html.Should().Contain("确认场景路由并创建策划大纲");
        html.Should().Contain("missingRequired");
        html.Should().Contain("请先填写必填问题");
        html.Should().Contain("至少填写 4 个关键问题");
        html.Should().NotContain("closeGddQuestionFormModal();\r\n                  await startGddDocumentRoute(message);");
        html.Should().Contain("confirmGddQuestionForm");
        html.Should().Contain("cancelGddQuestionForm");
        html.Should().Contain("let sessionValidated = false");
        html.Should().Contain("sessionValidated = true");
        html.Should().Contain("if (!sessionValidated)");
        html.Should().Contain("retryOnAuthFailure");
        html.Should().Contain("正在恢复登录状态，请稍候...");
        html.Should().Contain("function restoreSessionFromStoredToken()");
        html.Should().Contain("function runStartupSessionRestore()");
        html.Should().Contain("function runStartupStep(name, action)");
        html.Should().Contain("startup_${name}_error");
        html.Should().Contain("restoreSessionFromStoredToken();");
        html.Should().NotContain("if (token()) refreshProjects(); else showLoggedOut();");
        html.Should().NotContain("if (error?.status === 401 || error?.status === 403)");
        html.Should().Contain("Token 已验证。项目状态刷新失败，请稍后重试。");
        html.Should().Contain("function persistAccessToken(value)");
        html.Should().Contain("function persistAccessTokenFromInput()");
        html.Should().Contain("function readBrowserCookie(name)");
        html.Should().Contain("function writeBrowserCookie(name, value, maxAgeSeconds)");
        html.Should().Contain("function clearBrowserCookie(name)");
        html.Should().Contain("sessionDiagnostics");
        html.Should().NotContain("copySessionProbe");
        html.Should().NotContain("复制登录诊断");
        html.Should().NotContain("sessionProbeOutput");
        html.Should().Contain("function updateSessionDiagnostics(reason = \"\")");
        html.Should().Contain("function recordSessionProbe(reason = \"manual\", extra = {})");
        html.Should().Contain("phaseASessionProbeLog");
        html.Should().Contain("[phasea-session-probe]");
        html.Should().Contain("window.phaseASessionProbeDump");
        html.Should().Contain("api_response_error");
        html.Should().Contain("refreshProjects_error");
        html.Should().Contain("startup_before_restore");
        html.Should().Contain("登录诊断：${location.origin}");
        html.Should().Contain("function recoverVisiblePageFromClientError(error)");
        html.Should().Contain("window.addEventListener(\"error\"");
        html.Should().Contain("window.addEventListener(\"unhandledrejection\"");
        html.Should().Contain("setTimeout(() =>");
        html.Should().Contain("function scheduleAutofillTokenRecovery()");
        html.Should().Contain("autofill_empty_${delayMs}");
        html.Should().Contain("persistTokenInputFromBrowser(\"input\")");
        html.Should().Contain("persistTokenInputFromBrowser(\"change\")");
        html.Should().Contain("Token 已保留");
        html.Should().Contain("busy-banner-prototype-skeleton");
        html.Should().Contain("展开详细信息");
        html.Should().Contain("关闭详细信息");
        html.Should().Contain("系统正在进行游戏场景创建工作，其中可能存在的信息延迟或显示遗漏但不影响实际进程；");
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
        html.Should().Contain("id=\"projectListStatus\"");
        html.Should().Contain("function setProjectListStatus");
        html.Should().Contain("data-delete-project=\"${p.projectId}\">删除项目</button>");
        html.Should().Contain("$(\"projects\").addEventListener(\"click\", event =>");
        html.Should().Contain("void deleteProject(deleteButton.dataset.deleteProject || \"\")");
        html.Should().Contain("正在调用删除 API");
        html.Should().Contain("setProjectListStatus(failureMessage, true)");
        var newGddMilestoneRoundIndex = html.IndexOf("async function createNewGddMilestoneRound", StringComparison.Ordinal);
        newGddMilestoneRoundIndex.Should().BeGreaterThanOrEqualTo(0);
        var newGddMilestoneRoundSource = html[newGddMilestoneRoundIndex..html.IndexOf("async function createIterationPlan", newGddMilestoneRoundIndex, StringComparison.Ordinal)];
        newGddMilestoneRoundSource.Should().NotContain("项目已删除");
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
        html.Should().Contain("确认 GDD 无误，执行 M1 游戏场景");
        html.Should().Contain("prototype-7day-playable/from-gdd");
        html.Should().Contain("refreshPrototypeGddStatus");
        html.Should().Contain("gddMilestoneStepStatus");
        html.IndexOf(@"id=""gddMilestoneStepStatus""", StringComparison.Ordinal).Should().BeGreaterThan(html.IndexOf("主流程：游戏模块", StringComparison.Ordinal));
        html.IndexOf(@"id=""gddMilestoneStepStatus""", StringComparison.Ordinal).Should().BeLessThan(html.IndexOf("异常修复计划", StringComparison.Ordinal));
        html.Should().Contain("执行当前模块");
        html.Should().Contain("快速修复");
        html.Should().Contain("quickRepairCurrentMilestoneStep");
        html.Should().Contain("更新游戏模块内容");
        html.Should().Contain("createNewGddMilestoneRound");
        html.Should().Contain("创建新一轮游戏模块");
        html.Should().Contain("panel.querySelector(\"#createNewGddMilestoneRound\")?.addEventListener(\"click\", () => openIterationPlanUpdateModal(\"new-gdd-milestone\"))");
        html.Should().Contain("/gdd-milestone-steps/new-round");
        html.Should().Contain("有任务正在执行，请等待当前任务完成后再创建新一轮。");
        html.Should().Contain("将基于这里输入的新目标创建独立的新一轮计划，不会更新当前轮游戏模块。");
        html.Should().NotContain("当前游戏模块全部完成后可以创建新一轮。");
        html.Should().Contain("完成当前模块并激活下一模块");
        html.Should().Contain("建议先打包下载试玩验证");
        html.Should().Contain("提交反馈并修正模块");
        html.Should().Contain("milestoneFeedbackModal");
        html.Should().Contain("openCurrentMilestoneFeedbackModal");
        html.Should().Contain("提交反馈并修正模块");
        html.Should().NotContain("prompt(`请输入 ${step.stepId} 的试玩反馈或修改意见：`)");
        html.Should().Contain("当前模块执行进度");
        html.Should().Contain("milestone-progress-button");
        html.Should().Contain("selectGddMilestoneStep(button.dataset.gddMilestoneStepId || \"\", true)");
        html.Should().Contain("data-v2-tooltip=\"${escapeHtml(tooltip)}\"");
        html.Should().NotContain("milestone-progress-title");
        html.Should().Contain("if (active && step?.stepId === active.stepId) return \"running\"");
        html.Should().Contain("当前激活模块");
        html.Should().Contain("自动验收证据");
        html.Should().Contain("模块执行结果");
        html.Should().Contain("玩家试玩验收内容");
        html.Should().Contain("milestone-playtest-panel");
        html.Should().Contain("试玩验收");
        html.Should().Contain("打包试玩");
        html.IndexOf("renderGddMilestoneResultPanel(step)", StringComparison.Ordinal)
            .Should().BeLessThan(html.IndexOf("renderGddMilestonePlaytestPanel(step)", StringComparison.Ordinal));
        html.Should().Contain("executionRunId");
        html.Should().Contain("feedbackRunId");
        html.Should().Contain("最近 run");
        html.Should().Contain("执行结果");
        html.Should().Contain("latestSummary");
        html.Should().Contain("feedbackSummary");
        html.Should().Contain("latestEvidenceRelativePath");
        html.Should().Contain("gddMilestoneEvidence");
        html.Should().Contain("prototype-evidence?path=");
        html.Should().Contain("milestone smoke");
        html.Should().Contain("asset validation");
        html.Should().Contain("上一个模块");
        html.Should().Contain("下一个模块");
        html.Should().Contain("gdd-milestone-steps/latest");
        html.Should().Contain("gdd-milestone-steps/current/execute");
        html.Should().Contain("gddMilestoneActionRunId");
        html.Should().Contain("resultRunId");
        html.Should().Contain("trackProjectRunFromResult");
        html.Should().Contain("startProjectRunPolling");
        html.Should().Contain("startGddMilestoneRunPolling");
        html.Should().Contain("refreshGddMilestoneRun");
        html.Should().Contain("/api/runs/${encodeURIComponent(runId)}");
        html.Should().Contain("projectRunPollTimer = window.setInterval");
        html.Should().Contain("}, 2000);");
        html.Should().Contain("await refreshCurrentProjectAfterActiveRunSettled();");
        html.Should().Contain("const actionRunId = gddMilestoneActionRunId(result, step);");
        html.Should().Contain("await trackProjectRunFromResult({ runId: actionRunId }, projectId, context.authEpoch);");
        html.Should().Contain("await trackProjectRunFromResult(result, projectId, context.authEpoch);");
        var quickRepairSource = html.IndexOf("sourceKind: \"quick_repair\"", StringComparison.Ordinal);
        quickRepairSource.Should().BeGreaterThan(-1);
        html.IndexOf("await trackProjectRunFromResult({ runId: actionRunId }, projectId, context.authEpoch);", quickRepairSource, StringComparison.Ordinal)
            .Should().BeLessThan(html.IndexOf("state.gddMilestoneSteps = result.plan || state.gddMilestoneSteps;", quickRepairSource, StringComparison.Ordinal));
        html.Should().Contain("if (state.activeRun?.runId === runId) state.activeRun = null;");
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
        html.Should().Contain("游戏场景创建");
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
        var pollIndex = html.IndexOf("async function pollProjectInitializationResult", StringComparison.Ordinal);
        html.IndexOf("if (isProjectReady(createdProject))", pollIndex, StringComparison.Ordinal)
            .Should().BeLessThan(html.IndexOf("if (visibleProjects.length > 0)", pollIndex, StringComparison.Ordinal));
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
        html.Should().Contain("M1 游戏场景执行中..刷新页面查阅进度.");
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
        html.Should().Contain("正在生成回复");
        html.Should().Contain("setInterval");
        html.Should().Contain("shouldAutoRefreshIterationPlan");
        html.Should().Contain(@"activeRun?.runType === ""prototype-iteration-goal""");
        html.Should().Contain("const canSubmitFeedback = !!selected?.canSubmitFeedback || !!selected?.canConfirm;");
        html.Should().Contain("updateChatPanelVisibility");
        html.Should().Contain("seedChatFromPrototypeProgress");
        html.Should().Contain("prototypeSeedMessage");
        html.Should().Contain("formatNextStepSource");
        html.Should().Contain("formatNextStepEvaluation");
        html.Should().Contain("下一步建议来源：");
        html.Should().Contain("继续优化评估：");
        html.Should().Contain("生成结果");
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
        html.Should().Contain("const needsFixDisabled = !isLatestPlan || isGlobalBusy();");
        html.Should().Contain("只能修复最新一轮游戏模块。请切回最新轮次后再运行需要修复路由。");
        html.Should().Contain("function latestIterationPlanForAction()");
        html.Should().Contain("function selectLatestIterationPlanForAction()");
        html.Should().Contain("const goals = latestIterationPlanGoalsForAction();");
        html.Should().Contain("const hasNeedsFix = goals.some(goal => v2IsRepairGoalStatus(goal.status));");
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
        html.Should().NotContain("无法启动 needs-fix：当前页面未确认游戏场景已创建。");
        html.Should().Contain("[\"needs_fix\", \"failed\"].includes");
        html.Should().Contain("feedback ? buildNeedsFixFeedbackForUserReport(goal, feedback) : buildNeedsFixFeedbackForGoal(goal)");
        html.Should().NotContain("quickFixPanel");
        html.Should().NotContain("submitQuickFix");
        html.Should().NotContain("prototype-quick-fixes");
        html.Should().NotContain("兼容入口：快速修复");
        html.Should().Contain("submitFormalFeedback");
        html.Should().Contain("提交反馈到需要修复路由");
        html.Should().Contain("const goal = latestNeedsFixRouteGoalForAction();");
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
        html.Should().Contain("iterationPlanRequiredModules");
        html.Should().Contain("requiredModules: result.requiredModules || []");
        html.Should().Contain("必需模块");
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
        html.Should().Contain("const actionPlan = selectLatestIterationPlanForAction();");
        html.Should().Contain("const evaluation = response?.evaluation || response;");
        html.Should().Contain("latestPlan.latestEvaluation = evaluation;");
        html.Should().Contain("state.iterationPlanEvaluation = evaluation;");
        html.Should().Contain("const longLlmTimeoutMs = 1200 * 1000;");
        html.Should().Contain("failureCode: \"client_timeout\"");
        html.Should().Contain("timeoutMs: longLlmTimeoutMs");
        html.Should().Contain("/iteration-plan/execute-next");
        html.Should().Contain("loadIterationPlan");
        html.Should().Contain("renderIterationPlan");
        html.Should().Contain("submitIterationPlanFromFeedback");
        html.Should().NotContain("iteration-plan-request");
        html.Should().NotContain("iteration-plan-result");
        html.Should().Contain("await loadServerChatHistoryForProject(projectId, context.authEpoch);");
        html.Should().Contain("sanitizePublicRunContent");
        html.Should().Contain("publicArtifactLabel");
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
    public void RenderShell_RefreshProjectsDoesNotClearPersistedTokenOnSessionFailure()
    {
        var html = new BrowserUiRenderer().RenderShell();
        var refreshStart = html.IndexOf("async function refreshProjects", StringComparison.Ordinal);
        var refreshEnd = html.IndexOf("function selectDefaultProject", refreshStart, StringComparison.Ordinal);

        refreshStart.Should().BeGreaterThanOrEqualTo(0);
        refreshEnd.Should().BeGreaterThan(refreshStart);

        var refreshProjects = html[refreshStart..refreshEnd];
        refreshProjects.Should().Contain("showLoggedOut();");
        refreshProjects.Should().Contain("retryOnAuthFailure");
        refreshProjects.Should().Contain("showUserLoadingFallback(\"正在恢复登录状态，请稍候...\")");
        refreshProjects.Should().NotContain("clearAccessTokenStorage");
        refreshProjects.Should().NotContain("bumpAuthEpoch();");
    }

    [Fact]
    public void RenderShell_RestoresStoredTokenThroughLoadingStateOnPageRefresh()
    {
        var html = new BrowserUiRenderer().RenderShell();
        var restoreStart = html.IndexOf("function restoreSessionFromStoredToken()", StringComparison.Ordinal);
        var restoreEnd = html.IndexOf("function selectDefaultProject", restoreStart, StringComparison.Ordinal);

        restoreStart.Should().BeGreaterThanOrEqualTo(0);
        restoreEnd.Should().BeGreaterThan(restoreStart);

        var restore = html[restoreStart..restoreEnd];
        restore.Should().Contain("const currentToken = token();");
        restore.Should().Contain("showUserLoadingFallback(\"正在恢复登录状态，请稍候...\")");
        restore.Should().Contain("void refreshProjects({ autoSelect: true });");
        restore.Should().Contain("showLoggedOut();");
    }

    [Fact]
    public void RenderShell_GameModuleLongRunsScheduleActiveRunRefreshForCancellation()
    {
        var html = new BrowserUiRenderer().RenderShell();
        var normalized = html.Replace("\r\n", "\n", StringComparison.Ordinal);

        ShouldScheduleAfter(normalized, "setLocalBusy(true, \"正在执行当前游戏模块。\");");
        ShouldScheduleAfter(normalized, "setLocalBusy(true, \"正在根据当前模块执行结果启动快速修复。\");");
        ShouldScheduleAfter(normalized, "setLocalBusy(true, \"正在确认当前模块并执行下一模块解锁前检查。\");");
        ShouldScheduleAfter(normalized, "setLocalBusy(true, \"正在提交当前模块的反馈修复。\");");

        static void ShouldScheduleAfter(string html, string marker)
        {
            var markerIndex = html.IndexOf(marker, StringComparison.Ordinal);
            markerIndex.Should().BeGreaterThanOrEqualTo(0);
            var scheduleIndex = html.IndexOf("scheduleActiveRunRefresh();", markerIndex, StringComparison.Ordinal);
            scheduleIndex.Should().BeGreaterThan(markerIndex);
            (scheduleIndex - markerIndex).Should().BeLessThan(200);
        }
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
        html.Should().Contain("素材库刷新失败");
        html.Should().Contain("本次没有启动素材判定 run");
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
        html.Should().Contain("saveSection");
        html.Should().Contain("completeAllSections");
        html.Should().Contain("quickCompleteSection");
        html.Should().Contain("generateSectionContent");
        html.Should().Contain("waitForBatchOutlineRun");
        html.Should().Contain("startBatchOutlinePolling");
        html.Should().Contain("attachActiveBatchOutlineRun");
        html.Should().Contain("refreshBatchOutlineRun");
        html.Should().Contain("batchOutlinePollTimer");
        html.Should().Contain("formatBatchRunProgress");
        html.Should().Contain("attempt < 1800");
        html.Should().Contain("/api/runs/${encodeURIComponent(runId)}");
        html.Should().Contain("/api/projects/${projectId}/gdd/outline/sections/complete-missing");
        html.Should().Contain("function notifyActiveRunRefresh(runId = \"\")");
        html.Should().Contain("notifyActiveRunRefresh(result.runId);");
        html.Should().Contain("startBatchOutlinePolling(result.runId, pendingSections.length);");
        html.Should().Contain("loadOutline().then(() => attachActiveBatchOutlineRun()).catch(() => {});");
        html.Should().Contain("api(\"/api/account/active-run\")");
        html.Should().Contain("[\"queued\", \"running\"].includes(String(result.status || \"\").toLowerCase())");
        html.Should().Contain("data-quick-complete-section");
        html.Should().Contain("section-actions");
        html.Should().Contain("editorSkeleton");
        html.Should().Contain("editorContent");
        html.Should().Contain("editorMessage");
        html.Should().Contain("id=\"saveSection\"");
        html.Should().Contain("method:\"PATCH\"");
        html.Should().Contain("skeleton: $(\"editorSkeleton\").value");
        html.Should().Contain("content: $(\"editorContent\").value");
        html.Should().Contain(@"$(""meta"").textContent = ""\u7b56\u5212\u5927\u7eb2\u6761\u76ee\u5df2\u4fdd\u5b58\u3002""");
        html.Should().NotContain("editorSkeleton\" readonly");
        html.Should().NotContain("editorContent\" readonly");
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
    public void Program_DoesNotMapLegacyUserTokenToAdminAccount()
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

        source.Should().Contain("ResolveAccountByTokenHashAsync");
        source.Should().NotContain("legacy-user");
        source.Should().NotContain("new AccountIdentity(adminAccountId, \"legacy-user\"");
    }

    [Fact]
    public void Program_ProjectOwnershipPrecheckDoesNotBlockAdminProjectDeleteRoute()
    {
        var source = File.ReadAllText(Path.GetFullPath(Path.Combine(
            AppContext.BaseDirectory,
            "..",
            "..",
            "..",
            "..",
            "PhaseA.Platform",
            "Program.cs")));

        var middlewareIndex = source.IndexOf("TryReadApiProjectId(context.Request.Path, out var projectId)", StringComparison.Ordinal);
        middlewareIndex.Should().BeGreaterThanOrEqualTo(0);
        var middlewareSource = source[(middlewareIndex - 80)..(middlewareIndex + 260)];
        middlewareSource.Should().Contain("!identity.IsAdmin");
        middlewareSource.Should().Contain("ProjectBelongsToAccountAsync(identity.AccountId, projectId");

        var deleteRouteIndex = source.IndexOf("app.MapDelete(\"/api/projects/{projectId}\"", StringComparison.Ordinal);
        deleteRouteIndex.Should().BeGreaterThan(middlewareIndex);
        var deleteRouteSource = source[deleteRouteIndex..source.IndexOf("app.MapPost(\"/api/projects/{projectId}/chapter2-bootstrap\"", deleteRouteIndex, StringComparison.Ordinal)];
        deleteRouteSource.Should().Contain("CurrentIdentity(context)");
        deleteRouteSource.Should().Contain("ReadFromJsonAsync<ProjectDeletionRequest>");
        deleteRouteSource.Should().Contain("delete_request_invalid");
        deleteRouteSource.Should().Contain("delete_request_required");
        deleteRouteSource.Should().Contain("RecordProjectDeleteDiagnosticAsync");
        deleteRouteSource.Should().Contain("DeleteProjectAsync(identity.AccountId, identity.IsAdmin, projectId");
        source.Should().Contain("project-delete-diagnostics.jsonl");
        source.Should().Contain("RecordUnhandledRequestDiagnosticAsync");
        source.Should().Contain("unhandled-request-diagnostics.jsonl");
    }

    [Fact]
    public void Program_GddQuestionFormEndpointTranslatesConcurrencyLimit()
    {
        var source = File.ReadAllText(Path.GetFullPath(Path.Combine(
            AppContext.BaseDirectory,
            "..",
            "..",
            "..",
            "..",
            "PhaseA.Platform",
            "Program.cs")));

        var routeIndex = source.IndexOf("app.MapPost(\"/api/projects/{projectId}/gdd/question-form\"", StringComparison.Ordinal);
        routeIndex.Should().BeGreaterThanOrEqualTo(0);
        var nextRouteIndex = source.IndexOf("app.MapGet(\"/api/projects/{projectId}/gdd\"", routeIndex, StringComparison.Ordinal);
        nextRouteIndex.Should().BeGreaterThan(routeIndex);
        var endpointSource = source[routeIndex..nextRouteIndex];
        endpointSource.Should().Contain("result.Status == \"rate_limited\"");
        endpointSource.Should().Contain("StatusCodes.Status429TooManyRequests");
    }

    [Fact]
    public void Program_WorkflowReadbackEndpointsApplyNoStore()
    {
        var source = File.ReadAllText(Path.GetFullPath(Path.Combine(
            AppContext.BaseDirectory,
            "..",
            "..",
            "..",
            "..",
            "PhaseA.Platform",
            "Program.cs")));

        AssertEndpointAppliesNoStore(source, "app.MapGet(\"/api/projects/{projectId}/workflow-route\"");
        AssertEndpointAppliesNoStore(source, "app.MapPost(\"/api/projects/{projectId}/workflow-route/intent\"");
        AssertEndpointAppliesNoStore(source, "app.MapGet(\"/api/projects/{projectId}/workflow-recommendation\"");
    }

    [Fact]
    public void Program_AdminGovernanceReadbackEndpointsAreAdminOnlyAndNoStore()
    {
        var source = File.ReadAllText(Path.GetFullPath(Path.Combine(
            AppContext.BaseDirectory,
            "..",
            "..",
            "..",
            "..",
            "PhaseA.Platform",
            "Program.cs")));

        foreach (var marker in new[]
        {
            "app.MapGet(\"/api/admin/project-admin-review-queue\"",
            "app.MapGet(\"/api/admin/project-diagnostic-spool\"",
            "app.MapGet(\"/api/admin/project-delete-tombstones\""
        })
        {
            var endpointSource = ExtractEndpointSource(source, marker);
            endpointSource.Should().Contain("ApplyNoStore(context);");
            endpointSource.Should().Contain("!CurrentIdentity(context).IsAdmin");
            endpointSource.Should().Contain("AdminForbidden()");
        }

        source.Should().Contain("ListProjectAdminReviewQueueForAdminAsync");
        source.Should().Contain("ListProjectDiagnosticSpoolForAdminAsync");
        source.Should().Contain("ListProjectDeleteTombstonesForAdminAsync");
    }

    private static void AssertEndpointAppliesNoStore(string source, string routeMarker)
    {
        ExtractEndpointSource(source, routeMarker).Should().Contain("ApplyNoStore(context);");
    }

    private static string ExtractEndpointSource(string source, string routeMarker)
    {
        var routeIndex = source.IndexOf(routeMarker, StringComparison.Ordinal);
        routeIndex.Should().BeGreaterThanOrEqualTo(0);
        var nextRouteIndex = source.IndexOf("app.Map", routeIndex + routeMarker.Length, StringComparison.Ordinal);
        nextRouteIndex.Should().BeGreaterThan(routeIndex);
        return source[routeIndex..nextRouteIndex];
    }

    [Fact]
    public void AdminGameTypeMatchRecordsPage_ExposesContractSnapshotRefreshControls()
    {
        var html = new BrowserUiRenderer().RenderAdminGameTypeMatchFailures();

        html.Should().Contain("Contract Snapshot");
        html.Should().Contain("data-refresh-snapshot");
        html.Should().Contain("/api/admin/projects/${encodeURIComponent(projectId)}/game-type-contract-snapshot/refresh");
        html.Should().Contain("method: \"POST\"");
    }

    [Fact]
    public void Program_AdminContractSnapshotRefreshEndpointIsAdminOnly()
    {
        var source = File.ReadAllText(Path.GetFullPath(Path.Combine(
            AppContext.BaseDirectory,
            "..",
            "..",
            "..",
            "..",
            "PhaseA.Platform",
            "Program.cs")));

        var routeIndex = source.IndexOf("app.MapPost(\"/api/admin/projects/{projectId}/game-type-contract-snapshot/refresh\"", StringComparison.Ordinal);
        routeIndex.Should().BeGreaterThanOrEqualTo(0);
        var nextRouteIndex = source.IndexOf("app.MapGet(\"/api/projects/{projectId}/runs\"", routeIndex, StringComparison.Ordinal);
        nextRouteIndex.Should().BeGreaterThan(routeIndex);
        var endpointSource = source[routeIndex..nextRouteIndex];
        endpointSource.Should().Contain("!CurrentIdentity(context).IsAdmin");
        endpointSource.Should().Contain("RefreshContractSnapshotAsync(projectId");
        endpointSource.Should().Contain("game_type_not_matched");
        endpointSource.Should().Contain("StatusCodes.Status409Conflict");
    }

    [Fact]
    public void Program_GddQuestionFormRestoreEndpointIsReadOnly()
    {
        var source = File.ReadAllText(Path.GetFullPath(Path.Combine(
            AppContext.BaseDirectory,
            "..",
            "..",
            "..",
            "..",
            "PhaseA.Platform",
            "Program.cs")));

        var routeIndex = source.IndexOf("app.MapGet(\"/api/projects/{projectId}/gdd/question-form/restore-latest\"", StringComparison.Ordinal);
        routeIndex.Should().BeGreaterThanOrEqualTo(0);
        var nextRouteIndex = source.IndexOf("app.MapPost(\"/api/projects/{projectId}/gdd/scene-route\"", routeIndex, StringComparison.Ordinal);
        nextRouteIndex.Should().BeGreaterThan(routeIndex);
        var endpointSource = source[routeIndex..nextRouteIndex];
        endpointSource.Should().Contain("GameDesignQuestionFormRestoreService restore");
        endpointSource.Should().Contain("restore.ReadLatestAsync(CurrentAccountId(context), projectId, cancellationToken)");
        endpointSource.Should().Contain("Results.NotFound(new { error = \"project_not_found\" })");
        endpointSource.Should().NotContain("Upsert");
        endpointSource.Should().NotContain("CreateRunAsync");
    }

    [Fact]
    public void Program_GddSceneRouteEndpointTranslatesConcurrencyLimit()
    {
        var source = File.ReadAllText(Path.GetFullPath(Path.Combine(
            AppContext.BaseDirectory,
            "..",
            "..",
            "..",
            "..",
            "PhaseA.Platform",
            "Program.cs")));

        var routeIndex = source.IndexOf("app.MapPost(\"/api/projects/{projectId}/gdd/scene-route\"", StringComparison.Ordinal);
        routeIndex.Should().BeGreaterThanOrEqualTo(0);
        var nextRouteIndex = source.IndexOf("app.MapGet(\"/api/projects/{projectId}/gdd\"", routeIndex, StringComparison.Ordinal);
        nextRouteIndex.Should().BeGreaterThan(routeIndex);
        var endpointSource = source[routeIndex..nextRouteIndex];
        endpointSource.Should().Contain("Results.NotFound(new { error = \"project_not_found\" })");
        endpointSource.Should().Contain("result.Status == \"rate_limited\"");
        endpointSource.Should().Contain("StatusCodes.Status429TooManyRequests");
    }

    [Fact]
    public void Program_Phase1SceneAndGddEndpointsUsePersistedHashStateInsteadOfPlaceholders()
    {
        var source = File.ReadAllText(Path.GetFullPath(Path.Combine(
            AppContext.BaseDirectory,
            "..",
            "..",
            "..",
            "..",
            "PhaseA.Platform",
            "Program.cs")));

        var confirmIndex = source.IndexOf("app.MapPost(\"/api/projects/{projectId}/gdd/scene-route/confirm\"", StringComparison.Ordinal);
        var requirementMapIndex = source.IndexOf("app.MapPost(\"/api/projects/{projectId}/gdd/requirements-map\"", StringComparison.Ordinal);
        confirmIndex.Should().BeGreaterThanOrEqualTo(0);
        requirementMapIndex.Should().BeGreaterThan(confirmIndex);
        var endpointSource = source[confirmIndex..requirementMapIndex];
        endpointSource.Should().Contain("phase1State.ConfirmSceneRouteAsync");
        endpointSource.Should().Contain("phase1State.RecordGeneratedGddAsync");
        endpointSource.Should().Contain("phase1State.GetSceneRouteAsync");
        endpointSource.Should().Contain("phase1State.GetGddDocumentStateAsync");
        endpointSource.Should().NotContain("confirmedSceneRouteHash = \"\"");
        endpointSource.Should().NotContain("generatedGddHash = \"\"");
        endpointSource.Should().NotContain("sceneRouteRecordedGeneratedGddHash = \"\"");
    }

    [Fact]
    public void Program_Phase1EndpointsApplyServerSideNoStorePolicy()
    {
        var source = File.ReadAllText(Path.GetFullPath(Path.Combine(
            AppContext.BaseDirectory,
            "..",
            "..",
            "..",
            "..",
            "PhaseA.Platform",
            "Program.cs")));
        var routeTokens = new[]
        {
            "app.MapPost(\"/api/projects/{projectId}/gdd/scene-route/confirm\"",
            "app.MapGet(\"/api/projects/{projectId}/gdd/scene-route/latest\"",
            "app.MapPost(\"/api/projects/{projectId}/gdd/document/generate\"",
            "app.MapGet(\"/api/projects/{projectId}/gdd/document/status\"",
            "app.MapPost(\"/api/projects/{projectId}/gdd/requirements-map\"",
            "app.MapGet(\"/api/projects/{projectId}/gdd/requirements-map/latest\"",
            "app.MapPost(\"/api/projects/{projectId}/prototype-contract/freeze\"",
            "app.MapGet(\"/api/projects/{projectId}/prototype-contract/status\""
        };

        foreach (var routeToken in routeTokens)
        {
            var routeIndex = source.IndexOf(routeToken, StringComparison.Ordinal);
            routeIndex.Should().BeGreaterThanOrEqualTo(0, routeToken);
            var nextRouteIndex = source.IndexOf("\n});", routeIndex, StringComparison.Ordinal);
            nextRouteIndex.Should().BeGreaterThan(routeIndex, routeToken);
            source[routeIndex..nextRouteIndex].Should().Contain("ApplyNoStore(context);", routeToken);
        }
    }

    [Fact]
    public void Program_GddEndpointReturnsConflictBeforeAppendingAlreadyExistsToChatHistory()
    {
        var source = File.ReadAllText(Path.GetFullPath(Path.Combine(
            AppContext.BaseDirectory,
            "..",
            "..",
            "..",
            "..",
            "PhaseA.Platform",
            "Program.cs")));

        var routeIndex = source.IndexOf("app.MapPost(\"/api/projects/{projectId}/gdd\"", StringComparison.Ordinal);
        routeIndex.Should().BeGreaterThanOrEqualTo(0);
        var nextRouteIndex = source.IndexOf("app.MapPost(\"/api/projects/{projectId}/gdd/question-form\"", routeIndex, StringComparison.Ordinal);
        nextRouteIndex.Should().BeGreaterThan(routeIndex);
        var endpointSource = source[routeIndex..nextRouteIndex];
        var alreadyExistsIndex = endpointSource.IndexOf("result.FailureCode == \"gdd_already_exists\"", StringComparison.Ordinal);
        var conflictIndex = endpointSource.IndexOf("return Results.Conflict(result);", StringComparison.Ordinal);
        var failureAppendIndex = endpointSource.IndexOf("await chatHistory.AppendAsync(accountId, projectId, \"user\", request.Message, \"gdd-request\", cancellationToken);", endpointSource.IndexOf("var failureSummary", StringComparison.Ordinal), StringComparison.Ordinal);

        alreadyExistsIndex.Should().BeGreaterThanOrEqualTo(0);
        conflictIndex.Should().BeGreaterThan(alreadyExistsIndex);
        failureAppendIndex.Should().BeGreaterThan(conflictIndex);
    }

    [Fact]
    public void Program_WebPreviewRoutesApplySandboxAndCorsHeaders()
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

        source.Should().Contain("ApplyWebPreviewCachePolicy");
        source.Should().Contain("AccessControlAllowOrigin = \"*\"");
        source.Should().Contain("ContentSecurityPolicy");
        source.Should().Contain("sandbox allow-scripts allow-pointer-lock");
        source.Should().Contain("XContentTypeOptions = \"nosniff\"");
        source.Should().Contain("\"user_web_preview_concurrency_limit_exceeded\" => StatusCodes.Status429TooManyRequests");
        source.Should().Contain("failureCode = queued.FailureCode");
        source.Should().Contain("WebPreviewNotFound(context)");
    }

    [Fact]
    public void Program_PrototypeEvidenceEndpointGuardsProjectLocalEvidenceJson()
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

        source.Should().Contain("/api/projects/{projectId}/prototype-evidence");
        source.Should().Contain("evidence_path_required");
        source.Should().Contain("evidence_path_not_allowed");
        source.Should().Contain("prototype_evidence_not_found");
        source.Should().Contain("logs/prototype-evidence/");
        source.Should().Contain("evidenceRoot");
        source.Should().Contain("WorkspacePathPolicy.IsUnderRoot(evidenceRoot, absolutePath)");
        source.Should().Contain("Path.DirectorySeparatorChar}evidence.json");
        source.Should().Contain("JsonDocument.ParseAsync");
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
            "app.MapPost(\"/api/projects/{projectId}/asset-library/import\"",
            "app.MapPost(\"/api/projects/{projectId}/asset-library/select\"",
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
    public void Program_AssetLibraryWriteEndpointsTranslateProjectRunnerBusy()
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

        var routes = new[]
        {
            "app.MapPost(\"/api/projects/{projectId}/asset-library/generate\"",
            "app.MapPost(\"/api/projects/{projectId}/asset-library/import\"",
            "app.MapPost(\"/api/projects/{projectId}/asset-library/select\""
        };

        foreach (var route in routes)
        {
            var routeIndex = source.IndexOf(route, StringComparison.Ordinal);
            routeIndex.Should().BeGreaterThanOrEqualTo(0, $"{route} should exist");
            var nextRouteIndex = source.IndexOf("app.Map", routeIndex + route.Length, StringComparison.Ordinal);
            var endpointSource = source[routeIndex..(nextRouteIndex < 0 ? source.Length : nextRouteIndex)];
            endpointSource.Should().Contain("Project runner is busy.", $"{route} should recognize the project runner lock failure");
            endpointSource.Should().Contain("new { error = \"project_busy\" }", $"{route} should return the standard busy payload");
            endpointSource.Should().Contain("StatusCodes.Status423Locked", $"{route} should return a locked status while another project write run is active");
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
        html.Should().Contain("const previewResult = await waitForWebPreview(fileName, button, payload.runId || \"\")");
        html.Should().Contain("/api/runs/${encodeURIComponent(runId)}");
        html.Should().Contain("await loadPackages()");
        html.Should().Contain("webPreviewFailureCodeFromRun(run)");
        html.Should().Contain("webPreviewQueueText(preview)");
        html.Should().Contain("function formatDuration(seconds)");
        html.Should().Contain("preview.fidelityTier");
        html.Should().Contain("preview.playableSurface");
        html.Should().Contain("preview.gameTypeId");
        html.Should().Contain("\\u5305\\u8f6c\\u6362\\u8bd5\\u73a9\\u7248");
        html.Should().Contain("preview.estimatedWaitSeconds");
        html.Should().Contain("preview.queuePosition");
        html.Should().Contain("user_web_preview_concurrency_limit_exceeded");
        html.Should().Contain("web_preview_signing_secret_missing");
        html.Should().Contain("godot3_shell_patch_failed");
        html.Should().Contain("web_preview_background_failed");
        html.Should().Contain("abandoned_run_recovered");
        html.Should().Contain("web_preview_converter_fingerprint_mismatch");
        html.Should().Contain("const stale = preview.status === \"stale\"");
        html.Should().Contain("converter_schema_outdated");
        html.Should().Contain("package_invalid_zip");
        html.Should().Contain("package_scan_budget_exceeded");
        html.Should().Contain("const maxAttempts = 900;");
        html.Should().NotContain("window.open(previewResult.url");
        html.Should().Contain("target=\"_blank\" rel=\"noopener\"");
        html.Should().NotContain("async function handleWebPreview(button, fileName, previewUrl)");
        html.Should().Contain("/api/projects/${projectId}/gdd/download-ticket");
        html.Should().Contain("下载 GDD.md");
        html.Should().Contain("cache: \"no-store\"");
        html.Should().NotContain("URL.createObjectURL");
        html.Should().Contain("下载失败：");
        html.Should().Contain("下载已提交给浏览器");
    }

    private static ProjectSnapshot CreateProjectSnapshot()
    {
        return new ProjectSnapshot(
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
    }

    private static ProjectSnapshot ProjectSnapshotForGddQuestionForm(
        string projectId,
        string gameName,
        string name,
        string gameTypeSource,
        string templateRuleId)
    {
        return new ProjectSnapshot(
            projectId,
            "account-1",
            name,
            gameName,
            gameTypeSource,
            templateRuleId,
            false,
            "[]",
            "succeeded",
            null,
            "workspace-1",
            "C:\\workspaces",
            $"C:\\workspaces\\{projectId}",
            $"C:\\workspaces\\{projectId}\\runtime",
            $"C:\\workspaces\\{projectId}\\.phasea");
    }

    private sealed record GddFallbackFieldContract(
        string Id,
        string Label,
        string Placeholder,
        int Rows,
        bool Required);

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

    private static string RequireNodeForGddQuestionFormTests()
    {
        var node = FindExecutableOnPath("node.exe") ?? FindExecutableOnPath("node");
        node.Should().NotBeNull("GDD question-form behavior tests execute the generated browser JavaScript");
        return node!;
    }

    private static string BrowserUiRendererSourcePath()
    {
        return Path.GetFullPath(Path.Combine(
            AppContext.BaseDirectory,
            "..",
            "..",
            "..",
            "..",
            "PhaseA.Platform",
            "Browser",
            "BrowserUiRenderer.cs"));
    }

    private static string ExtractJavaScriptRange(string source, string startMarker, string endMarker)
    {
        var start = source.IndexOf(startMarker, StringComparison.Ordinal);
        start.Should().BeGreaterThanOrEqualTo(0, $"{startMarker} should exist in BrowserUiRenderer");
        var end = source.IndexOf(endMarker, start, StringComparison.Ordinal);
        end.Should().BeGreaterThan(start, $"{endMarker} should follow {startMarker}");
        return source[start..end];
    }

    private static string RunNodeScript(string node, string script)
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
            var standardOutput = running.StandardOutput.ReadToEnd();
            var standardError = running.StandardError.ReadToEnd();
            var output = standardOutput + standardError;
            running.ExitCode.Should().Be(0, output);
            return standardOutput.Trim();
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

    [Fact]
    public void DetailView_ShouldRenderGddToModuleWorkflowReadbackSurfaces()
    {
        var html = new BrowserUiRenderer().RenderShellV2();

        html.Should().Contain("const workflowStageTimeline = [");
        html.Should().Contain("[\"gdd\", \"GDD\", [\"gdd-question-form\"]]");
        html.Should().Contain("[\"scene-confirmation\", \"Scene Confirmation\", [\"scene-route-confirmation\"]]");
        html.Should().Contain("[\"gdd-document-generation\", \"GDD Document Generation\", [\"gdd-document-generation\"]]");
        html.Should().Contain("[\"requirement-map\", \"Requirement Map\", [\"gdd-requirements\"]]");
        html.Should().Contain("[\"contract-freeze\", \"Contract Freeze\", [\"prototype-contract\"]]");
        html.Should().Contain("[\"game-modules\", \"Game Modules\", [\"prototype-skeleton\"]]");
        html.Should().Contain("[\"task-execution\", \"Task Execution\", [\"iteration-plan\", \"execute-next-goal\"]]");
        html.Should().Contain("[\"ui-closure\", \"UI Closure\", [\"ui-wiring\"]]");
        html.Should().Contain("[\"preview-package\", \"Preview/Package\", [\"preview-package\"]]");
        html.Should().Contain("const workflowRouteStatusValues = [\"queued\", \"running\", \"ready\", \"blocked\", \"needs_fix\", \"succeeded\", \"failed\", \"cancelled\", \"stale\", \"unknown\"]");
        html.Should().Contain("const workflowStageStatusValues = [\"not_started\", \"ready\", \"running\", \"needs_review\", \"blocked\", \"completed\", \"stale\"]");
        html.Should().Contain("const workflowRequirementStatusValues = [\"mapped\", \"missing_scene\", \"missing_module\", \"needs_review\", \"explicitly_deferred\", \"conflict\"]");
        html.Should().Contain("const workflowUiSurfaceStatusValues = [\"covered\", \"missing_ui\", \"missing_feedback\", \"needs_fix\", \"no_ui_needed\"]");
        html.Should().Contain("routeReadbackToStageStatusMap");
        html.Should().Contain("const workflowUiSurfaceStatusValues = [\"covered\", \"missing_ui\", \"missing_feedback\", \"needs_fix\", \"no_ui_needed\"]");
        html.Should().NotContain("covered: \"completed\"");
        html.Should().Contain("data-workflow-stage-timeline=\"true\"");
        html.Should().Contain("data-requirement-map-review=\"true\"");
        html.Should().Contain("Requirement ID</th><th>Source section</th><th>Requirement</th><th>Priority</th><th>Kind</th><th>Scenes</th><th>Required modules</th><th>Goals</th><th>Status</th><th>Issue / conflict reason");
        html.Should().Contain("data-contract-freshness-banner=\"true\"");
        html.Should().Contain("Generated GDD no longer matches the confirmed scene route");
        html.Should().Contain("Project type analysis changed after scene confirmation");
        html.Should().Contain("data-module-plan-confirmation=\"true\"");
        html.Should().Contain("data-ui-wiring-closure-panel=\"true\"");
        html.Should().Contain("layout, input/focus, feedback, custom drawing, camera/layer, rendering/material, animation, geometry sizing, procedural visualization, typed state");
        html.Should().Contain("data-final-readiness-boundary=\"true\"");
        html.Should().Contain("Ordinary package download is not final readiness");
        html.Should().Contain("workflowRenderRouteReadback(message?.workflowRoute)");
    }

    [Fact]
    public void Renderer_ContextCapturingActionsGuardBusyCleanup()
    {
        var sourcePath = Path.GetFullPath(Path.Combine(
            AppContext.BaseDirectory,
            "..",
            "..",
            "..",
            "..",
            "PhaseA.Platform",
            "Browser",
            "BrowserUiRenderer.cs"));
        var source = File.ReadAllText(sourcePath);

        source.Should().MatchRegex("(?s)async function sendChat\\(\\).*?finally \\{\\s*if \\(!isCurrentProjectContext\\(context\\)\\) return;\\s*state\\.chatBusy = false;");
        source.Should().MatchRegex("(?s)async function startGddDocumentRoute\\(message(?:, sceneRoute = null)?\\).*?finally \\{\\s*if \\(!isCurrentProjectContext\\(context\\)\\) return;\\s*if \\(succeeded\\) clearChatAttachments\\(\\);");
        source.Should().MatchRegex("(?s)async function createRepairPlan\\(\\).*?catch \\(error\\) \\{\\s*if \\(!isCurrentProjectContext\\(context\\)\\) return;\\s*showError\\(error\\);\\s*\\} finally \\{\\s*if \\(!isCurrentProjectContext\\(context\\)\\) return;");
        source.Should().MatchRegex("(?s)async function submitFormalFeedbackText\\(feedback, busyText\\).*?finally \\{\\s*if \\(!isCurrentProjectContext\\(context\\)\\) return;\\s*try \\{\\s*await loadProjectPackages\\(\\);");
        source.Should().MatchRegex("(?s)async function submitNeedsFixRouteRequest\\(payload, busyText\\).*?finally \\{\\s*if \\(!isCurrentProjectContext\\(context\\)\\) return;\\s*try \\{\\s*await refreshActiveRun\\(\\);");
    }

}
