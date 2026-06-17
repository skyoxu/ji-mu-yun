using System.Net;
using PhaseA.Platform.Data;
using PhaseA.Platform.Readback;

namespace PhaseA.Platform.Browser;

public sealed class BrowserUiRenderer
{
    public string RenderShellV2()
    {
        return RenderShell()
            .Replace("<h2>自由对话</h2>", "<h2>自由聊天</h2>")
            .Replace("</style>", RenderV2EnhancementCss())
            .Replace("<section id=\"currentProjectPanel\" class=\"stack\">", RenderV2ProgressShell())
            .Replace("</body>", RenderV2EnhancementScript());
    }

    private static string RenderV2EnhancementCss()
    {
        return """
                body.v2-detail #projectDetailPanel {
                  display: grid;
                  gap: 0.9rem;
                  align-items: start;
                }
                body.v2-detail {
                  height: 100vh;
                  overflow: hidden;
                }
                body.v2-detail main {
                  position: fixed;
                  inset: 80px 0 0 0;
                  height: auto;
                  min-height: 0;
                  overflow: hidden;
                  padding-top: 1rem;
                  padding-bottom: 1rem;
                  grid-template-rows: minmax(0, 1fr);
                  align-items: stretch;
                  box-sizing: border-box;
                }
                body.v2-detail #projectDetailPanel.v2-workspace-shell {
                  display: grid;
                  grid-template-columns: minmax(15rem, 25%) minmax(0, 75%);
                  gap: 1rem;
                  height: 100%;
                  max-height: 100%;
                  min-height: 0;
                  overflow: hidden;
                  align-self: stretch;
                  background: transparent;
                  border: 0;
                  box-shadow: none;
                  padding: 0;
                }
                body.v2-detail #v2LeftRail,
                body.v2-detail #v2RightWorkspace {
                  min-height: 0;
                  height: 100%;
                  max-height: 100%;
                  overflow-x: hidden;
                  padding-right: 0.2rem;
                  overscroll-behavior: contain;
                  align-self: stretch;
                  box-sizing: border-box;
                }
                body.v2-detail #v2LeftRail {
                  display: grid;
                  align-content: start;
                  gap: 0;
                  background: var(--panel);
                  border: 1px solid var(--line);
                  border-radius: 1rem;
                  padding: 0.8rem;
                  box-shadow: 0 1rem 2.4rem rgba(57, 43, 24, 0.08);
                  overflow-y: scroll;
                  scrollbar-gutter: stable;
                }
                body.v2-detail #v2RightWorkspace {
                  display: grid;
                  grid-template-rows: auto minmax(0, 1fr);
                  gap: 0;
                  overflow: hidden;
                  min-width: 0;
                }
                body.v2-detail #v2ProgressShell { grid-column: 1; background: transparent; border: 0; box-shadow: none; padding: 0; }
                body.v2-detail #v2ContentGrid {
                  display: grid;
                  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
                  gap: 0.9rem;
                  align-items: start;
                }
                body.v2-detail #v2ContentGrid.v2-tab-content {
                  display: block;
                  min-height: 0;
                  height: 100%;
                  max-height: 100%;
                  overflow-y: scroll;
                  overflow-x: hidden;
                  overscroll-behavior: contain;
                  min-width: 0;
                  box-sizing: border-box;
                  scrollbar-gutter: stable;
                }
                body.v2-detail #chatPanel { grid-column: 1; grid-row: 1; align-self: start; }
                body.v2-detail #v2IterationPanel { grid-column: 2; grid-row: 1; align-self: start; }
                body.v2-detail #v2RepairPanel { grid-column: 2; grid-row: 1; align-self: start; }
                body.v2-detail #v2UiOptimizationPanel { grid-column: 2; grid-row: 1; align-self: start; }
                body.v2-detail #v2AcceptancePanel { grid-column: 2; grid-row: 1; align-self: start; }
                body.v2-detail #currentProjectPanel,
                body.v2-detail #prototypeWorkflowPanel,
                body.v2-detail #prototypeCommandPanel,
                body.v2-detail #runsPanel { grid-column: 2; grid-row: 1; align-self: start; }
                body.v2-detail .prototype-draft-row { display: grid; grid-template-columns: max-content auto; justify-content: start; gap: 0.35rem; align-items: end; }
                body.v2-detail .prototype-draft-row label { display: inline-flex; align-items: center; gap: 0.45rem; white-space: nowrap; }
                body.v2-detail #draftFile { width: 15rem; max-width: 100%; }
                body.v2-detail .prototype-draft-row button { width: auto; min-width: 8.5rem; white-space: nowrap; }
                body.v2-detail .prototype-draft-row .import-draft-button:not(:disabled) { background: #d92d20; border-color: #d92d20; color: #fff; font-weight: 800; box-shadow: 0 8px 18px rgba(217, 45, 32, 0.18); }
                body.v2-detail .prototype-draft-row .import-draft-button:not(:disabled):hover { background: #b42318; border-color: #b42318; }
                body.v2-detail #outputPanel { grid-column: 1 / -1; }
                body.v2-detail .v2-progress-row { display: grid; gap: 0.35rem; overflow: visible; padding: 0; }
                body.v2-detail .v2-step-button { position: relative; width: 100%; min-height: 2.45rem; display: grid; grid-template-columns: 1.7rem 1.45rem minmax(0, 1fr) 1.35rem; align-items: center; gap: 0.4rem; padding: 0.35rem 0.45rem; color: var(--ink); background: #fffdf8; border: 1px solid var(--line); border-radius: 0.65rem; text-align: left; }
                body.v2-detail .v2-step-button.active { outline: 2px solid var(--accent-2); border-color: var(--accent-2); }
                body.v2-detail .v2-step-number { display: inline-flex; align-items: center; justify-content: flex-end; color: var(--accent); font-size: 0.82rem; line-height: 1; font-weight: 800; font-family: Arial, sans-serif; }
                body.v2-detail .v2-step-icon { width: 20px; height: 20px; background: currentColor; color: #24362e; -webkit-mask: var(--step-icon) center / 20px 20px no-repeat; mask: var(--step-icon) center / 20px 20px no-repeat; }
                body.v2-detail .v2-step-button.pending,
                body.v2-detail .v2-step-button.action { color: var(--muted); }
                body.v2-detail .v2-step-button.done,
                body.v2-detail .v2-step-button.fix,
                body.v2-detail .v2-step-button.continue { color: var(--ink); }
                body.v2-detail .v2-step-button.done .v2-step-icon { color: #15905f; }
                body.v2-detail .v2-step-button.fix .v2-step-icon { color: #b73732; }
                body.v2-detail .v2-step-button.pending .v2-step-icon,
                body.v2-detail .v2-step-button.action .v2-step-icon { color: #a8afad; }
                body.v2-detail .v2-step-label { min-width: 0; font-size: 0.86rem; line-height: 1.15; text-align: left; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
                body.v2-detail .v2-step-mark { justify-self: end; width: 1.05rem; height: 1.05rem; border-radius: 999px; color: white; font-size: 0.75rem; display: grid; place-items: center; font-family: Arial, sans-serif; font-weight: 800; }
                body.v2-detail .v2-step-button.pending .v2-step-mark,
                body.v2-detail .v2-step-button.action .v2-step-mark { background: #a8afad; }
                body.v2-detail .v2-step-button.done .v2-step-mark { background: #15905f; }
                body.v2-detail .v2-step-button.fix .v2-step-mark { background: #b73732; }
                body.v2-detail .v2-step-button.continue .v2-step-mark { width: auto; height: auto; background: transparent; color: #15905f; font-size: 1.2rem; letter-spacing: 0.08rem; line-height: 1; }
                body.v2-detail .v2-summary-grid { display: grid; grid-template-columns: 2fr 1fr 1fr; gap: 0.7rem; }
                body.v2-detail .v2-left-spacer { height: 50px; }
                body.v2-detail .v2-left-title { margin: 0 0 0.55rem; font-size: 1rem; }
                body.v2-detail .v2-left-projects { display: grid; gap: 0.35rem; }
                body.v2-detail .v2-left-project-button { width: 100%; display: grid; gap: 0.1rem; text-align: left; border: 1px solid transparent; background: transparent; color: var(--ink); border-radius: 0.65rem; padding: 0.5rem 0.55rem; }
                body.v2-detail .v2-left-project-button.current { background: #f2d16b; border-color: #d7a924; font-weight: 800; }
                body.v2-detail .v2-left-project-meta { color: var(--muted); font-size: 0.76rem; font-weight: 400; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
                body.v2-detail .v2-tabs { position: sticky; top: 0; z-index: 5; display: flex; align-items: end; gap: 0.12rem; overflow-x: auto; padding: 0 0.45rem; margin-bottom: -1px; border-bottom: 0; background: transparent; }
                body.v2-detail .v2-tab { width: auto; min-width: 6.5rem; max-width: 13rem; display: inline-flex; align-items: center; justify-content: center; gap: 0.35rem; border: 1px solid var(--line); border-bottom-color: transparent; background: #e2e0dc; color: var(--muted); border-radius: 0.65rem 0.65rem 0 0; padding: 0.52rem 0.72rem 0.58rem; white-space: nowrap; box-shadow: inset 0 -0.3rem 0.45rem rgba(57, 43, 24, 0.035); }
                body.v2-detail .v2-tab.active { background: #fffdf8; color: var(--ink); border-color: var(--line); border-bottom-color: #fffdf8; box-shadow: none; position: relative; z-index: 2; font-weight: 800; }
                body.v2-detail .v2-tab.active > span:first-child { font-weight: 800; }
                  body.v2-detail .v2-tab-close { width: 1.15rem; height: 1.15rem; min-width: 1.15rem; display: grid; place-items: center; border: 0; background: transparent; color: var(--muted); padding: 0; font-weight: 900; }
                  body.v2-detail .v2-tab-close:hover { color: var(--danger); }
                  body.v2-detail .v2-tab-pane { min-height: 0; }
                  body.v2-detail .v2-tab-pane.hidden { display: none !important; }
                  body.v2-detail #v2ContentGrid.v2-tab-content { background: #fffdf8; border: 0; border-radius: 0; padding: 0.9rem; box-shadow: none; }
                  body.v2-detail .v2-round-tabs { display: flex; align-items: center; gap: 0.4rem; overflow-x: auto; padding: 0.2rem 0 0.35rem; }
                  body.v2-detail .v2-round-tab { width: auto; border: 1px solid var(--line); background: #f4f1ea; color: var(--muted); border-radius: 999px; padding: 0.38rem 0.75rem; font-weight: 700; white-space: nowrap; }
                  body.v2-detail .v2-round-tab.active { background: var(--accent); color: #fff; border-color: var(--accent); }
                body.v2-detail #v2ContentGrid > section { border: 0; border-radius: 0; box-shadow: none; background: transparent; padding: 0; }
                body.v2-detail #v2ContentGrid > section > h2:first-child,
                body.v2-detail #v2ContentGrid > section > p.muted:first-of-type,
                body.v2-detail #chatPanel > h2,
                body.v2-detail #chatPanel > p.muted:first-of-type { display: none; }
                body.v2-detail #chatPanel #feedbackSummary,
                body.v2-detail #chatPanel #feedbackRecords { display: none !important; }
                body.v2-detail .v2-embedded-frame { width: 100%; height: calc(100vh - 172px); min-height: 32rem; border: 0; background: #fffdf8; border-radius: 0.5rem; display: block; }
                body.v2-detail #chatPanel { min-height: 100%; height: 100%; display: grid; grid-template-rows: minmax(0, 1fr) auto; align-content: stretch; gap: 0.65rem; }
                body.v2-detail #chatHistory.chat-scroll { min-height: 0; max-height: none; height: 100%; overflow-y: auto; }
                body.v2-detail .v2-action-row { display: flex; flex-wrap: wrap; align-items: end; gap: 0.5rem; }
                body.v2-detail .v2-chat-composer { display: grid; gap: 0.55rem; border: 1px solid var(--line); border-radius: 0.9rem; background: #fffdf8; padding: 0.65rem; box-shadow: inset 0 0 0 1px rgba(23, 33, 27, 0.025); }
                body.v2-detail .v2-chat-composer .v2-message-field { margin: 0; display: block; }
                body.v2-detail .v2-chat-composer #chatMessage { min-height: 4.25rem; max-height: 11rem; width: 100%; border: 0; border-radius: 0.55rem; padding: 0.45rem 0.35rem; background: transparent; resize: none; overflow-y: auto; box-shadow: none; }
                body.v2-detail .v2-chat-composer #chatMessage:focus { outline: 2px solid rgba(15, 107, 87, 0.16); }
                body.v2-detail .v2-chat-attachments { display: grid; gap: 0.45rem; }
                body.v2-detail .v2-attachment-list { display: flex; flex-wrap: wrap; gap: 0.4rem; align-items: center; min-height: 1.35rem; }
                body.v2-detail .v2-attachment-chip { display: inline-flex; align-items: center; gap: 0.35rem; max-width: 100%; border: 1px solid var(--line); border-radius: 999px; background: #f7efe2; color: var(--ink); padding: 0.24rem 0.28rem 0.24rem 0.55rem; font-size: 0.82rem; line-height: 1.15; }
                body.v2-detail .v2-attachment-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 12rem; }
                body.v2-detail .v2-attachment-meta { color: var(--muted); font-size: 0.76rem; }
                body.v2-detail .v2-attachment-remove { width: 1.35rem; height: 1.35rem; min-width: 1.35rem; border-radius: 999px; padding: 0; display: grid; place-items: center; }
                body.v2-detail .v2-chat-controls { display: flex; flex-wrap: wrap; align-items: center; gap: 0.4rem; }
                body.v2-detail .v2-skill-row,
                body.v2-detail #chatSkillDescription,
                body.v2-detail #chatSkillMode { display: none !important; }
                body.v2-detail #currentProjectPanel > button { display: none; }
                body.v2-detail #prototypeWorkflowPanel.v2-prototype-locked input,
                body.v2-detail #prototypeWorkflowPanel.v2-prototype-locked textarea,
                body.v2-detail #prototypeWorkflowPanel.v2-prototype-locked select,
                body.v2-detail #prototypeWorkflowPanel.v2-prototype-locked button { opacity: 0.55; }
                body.v2-detail .v2-action-row button,
                body.v2-detail .v2-chat-controls button,
                body.v2-detail .v2-chat-controls label,
                body.v2-detail .v2-chat-controls select { width: auto; min-height: 2.35rem; padding: 0.5rem 0.72rem; border-radius: 999px; font-size: 0.88rem; }
                body.v2-detail .v2-chat-controls .v2-file-button.ghost { display: inline-flex; align-items: center; justify-content: center; background: transparent; color: var(--accent); border: 1px solid var(--accent); cursor: pointer; font-weight: 700; line-height: 1; }
                body.v2-detail .v2-chat-controls .v2-file-button.ghost:hover { background: rgba(15, 107, 87, 0.08); }
                body.v2-detail .v2-chat-controls .v2-file-button input { display: none; }
                body.v2-detail .v2-chat-controls #v2AdvancedPlanningMode,
                body.v2-detail .v2-chat-controls #v2ProjectAnalysisMode { display: inline-flex; align-items: center; justify-content: center; background: transparent; color: var(--accent); border: 1px solid var(--accent); cursor: pointer; font-weight: 700; line-height: 1; }
                body.v2-detail .v2-chat-controls #v2AdvancedPlanningMode.active,
                body.v2-detail .v2-chat-controls #v2ProjectAnalysisMode.active { color: white; background: var(--accent-2); border-color: var(--accent-2); }
                body.v2-detail .v2-chat-controls .v2-attach-button { display: inline-flex; align-items: center; justify-content: center; min-width: 2.35rem; cursor: pointer; color: var(--danger); border: 0; background: transparent; font-weight: 900; font-size: 1.65rem; line-height: 1; padding: 0.25rem 0.45rem; }
                body.v2-detail .v2-chat-controls .v2-attach-button input { display: none; }
                body.v2-detail .v2-chat-controls #sendChat { margin-left: auto; min-width: 4.2rem; background: var(--accent-2); }
                body.v2-detail .v2-workflow-action-row { display: flex; flex-wrap: wrap; align-items: center; gap: 0.45rem; margin-top: 0.55rem; }
                body.v2-detail .v2-workflow-route-action { width: auto; border-radius: 999px; padding: 0.48rem 0.8rem; }
                body.v2-detail .v2-workflow-route-action[disabled] { opacity: 0.55; cursor: not-allowed; }
                .v2-fast-tooltip { position: fixed; z-index: 2500; max-width: min(28rem, calc(100vw - 2rem)); pointer-events: none; background: rgba(23, 33, 27, 0.94); color: #fffdf8; border-radius: 0.45rem; padding: 0.42rem 0.55rem; font-size: 0.82rem; line-height: 1.35; box-shadow: 0 0.75rem 1.8rem rgba(23, 33, 27, 0.22); opacity: 0; transform: translateY(0.15rem); transition: opacity 80ms ease, transform 80ms ease; }
                .v2-fast-tooltip.open { opacity: 1; transform: translateY(0); }
                body.v2-detail #v2IterationPanel,
                body.v2-detail #iterationPlanGoals,
                body.v2-detail #iterationPlanGoals .card { position: relative; z-index: 2; pointer-events: auto; }
                body.v2-detail [data-needs-fix-goal] { position: relative; z-index: 5; pointer-events: auto; cursor: pointer; }
                @media (max-width: 1000px) {
                  body.v2-detail,
                  body.v2-detail main {
                    overflow: hidden;
                  }
                  body.v2-detail #projectDetailPanel.v2-workspace-shell {
                    grid-template-columns: 1fr;
                    grid-template-rows: minmax(10rem, 34%) minmax(0, 1fr);
                    height: 100%;
                    max-height: 100%;
                    min-height: 0;
                    overflow: hidden;
                  }
                  body.v2-detail #v2LeftRail,
                  body.v2-detail #v2RightWorkspace {
                    min-height: 0;
                    overflow-y: auto;
                  }
                  body.v2-detail #v2ContentGrid,
                  body.v2-detail .v2-summary-grid,
                  body.v2-detail .v2-skill-row { grid-template-columns: 1fr; }
                  body.v2-detail #chatPanel,
                  body.v2-detail #v2IterationPanel,
                  body.v2-detail #v2RepairPanel,
                  body.v2-detail #v2UiOptimizationPanel,
                  body.v2-detail #v2AcceptancePanel,
                  body.v2-detail #currentProjectPanel,
                  body.v2-detail #prototypeWorkflowPanel,
                  body.v2-detail #prototypeCommandPanel,
                  body.v2-detail #runsPanel,
                  body.v2-detail #outputPanel { grid-column: 1; grid-row: auto; }
                  body.v2-detail .v2-chat-controls #sendChat { margin-left: 0; }
                }
              </style>
              """;
    }

    private static string RenderV2ProgressShell()
    {
        return """
                  <section id="v2ProgressShell" class="stack">
                    <h2 class="v2-left-title">原型工程列表</h2>
                    <div id="v2ProgressSteps" class="v2-progress-row"></div>
                  </section>
                  <section id="currentProjectPanel" class="stack">
                  """;
    }

    private static string RenderV2EnhancementScript()
    {
        return """
              <script>
                document.body.classList.add("v2-detail");
                const v2Steps = [
                  ["new-project", "游戏项目详情", "panel"],
                  ["create-prototype", "原型骨架创建", "spark"],
                  ["execute-or-repair", "骨架验收修复", "wrench"],
                  ["iteration-plan", "完成游戏模块", "list"],
                  ["ui-optimization", "游戏界面优化", "layout"],
                  ["prototype-acceptance", "原型验收", "check"],
                  ["asset-inventory", "确认素材清单", "image"],
                  ["download-project", "打包下载项目", "download"]
                ];
                let v2SelectedStep = "new-project";
                let v2UserSelectedStep = false;
                let v2CurrentProjectId = "";
                let v2ActiveTabId = "chat";
                let v2RestoredProjectUiStateId = "";
                let v2PendingProjectUiSkillMode = "";
                const v2ProjectUiStateVersion = 1;
                const v2OpenTabs = new Map([["chat", { id: "chat", label: "游戏策划创作", panelId: "chatPanel", closable: false }]]);
                function v2ProjectUiStateKey(projectId = state.projectId) {
                  return `phaseA.projectUiState.v${v2ProjectUiStateVersion}.${projectId || "none"}`;
                }
                function v2ReadProjectUiState(projectId = state.projectId) {
                  if (!projectId) return null;
                  try {
                    const cached = JSON.parse(localStorage.getItem(v2ProjectUiStateKey(projectId)) || "null");
                    return cached && cached.projectId === projectId ? cached : null;
                  } catch {
                    return null;
                  }
                }
                function v2WriteProjectUiState() {
                  if (!state.projectId) return;
                  const tabs = Array.from(v2OpenTabs.values())
                    .filter(tab => tab.id !== "chat")
                    .map(tab => ({
                      id: tab.id,
                      label: tab.label,
                      panelId: tab.panelId,
                      stepId: tab.stepId || "",
                      closable: tab.closable !== false,
                      frameId: tab.frameId || "",
                      url: tab.url || ""
                    }));
                  const settings = {
                    advancedPlanningMode: ($("chatSkillMode")?.value || "normal") === "game-design-master",
                    chatSkillMode: $("chatSkillMode")?.value || "normal",
                    projectAnalysisMode: !!state.projectAnalysisMode
                  };
                  const payload = {
                    projectId: state.projectId,
                    activeTabId: v2ActiveTabId,
                    selectedStep: v2SelectedStep,
                    userSelectedStep: !!v2UserSelectedStep,
                    tabs,
                    settings,
                    updatedAt: new Date().toISOString()
                  };
                  try { localStorage.setItem(v2ProjectUiStateKey(state.projectId), JSON.stringify(payload)); } catch {}
                }
                function v2EmbeddedTabUrl(tab) {
                  if (!state.projectId || !tab) return "";
                  if (tab.frameId === "v2AssetInventoryFrame" || tab.id === "step:asset-inventory") {
                    return `/assets?projectId=${encodeURIComponent(state.projectId)}&model=${encodeURIComponent($("globalModel")?.value || "gpt-5.5")}&embedded=1`;
                  }
                  if (tab.frameId === "v2DownloadsFrame" || tab.id === "step:download-project") {
                    return `/downloads?projectId=${encodeURIComponent(state.projectId)}&embedded=1`;
                  }
                  if (tab.frameId === "v2GddOutlineFrame" || tab.id === "gdd-outline" || tab.id === "step:gdd-outline") {
                    return `/gdd-outline?projectId=${encodeURIComponent(state.projectId)}&embedded=1`;
                  }
                  return "";
                }
                function v2EmbeddedFrameId(tab) {
                  if (!tab) return "";
                  if (tab.frameId) return tab.frameId;
                  if (tab.id === "step:asset-inventory") return "v2AssetInventoryFrame";
                  if (tab.id === "step:download-project") return "v2DownloadsFrame";
                  if (tab.id === "gdd-outline" || tab.id === "step:gdd-outline") return "v2GddOutlineFrame";
                  return "";
                }
                function v2RestoreProjectUiState() {
                  if (!state.projectId || v2RestoredProjectUiStateId === state.projectId) return;
                  v2RestoredProjectUiStateId = state.projectId;
                  const cached = v2ReadProjectUiState(state.projectId);
                  if (!cached) {
                    state.projectAnalysisMode = false;
                    v2PendingProjectUiSkillMode = "";
                    if ($("chatSkillMode")) $("chatSkillMode").value = "normal";
                    renderSelectedSkillAction();
                    v2RenderProjectAnalysisMode();
                    return;
                  }
                  Array.from(v2OpenTabs.keys()).forEach(tabId => {
                    if (tabId !== "chat") v2OpenTabs.delete(tabId);
                  });
                  for (const tab of Array.isArray(cached.tabs) ? cached.tabs : []) {
                    const id = String(tab.id || "");
                    const panelId = String(tab.panelId || "");
                    if (!id || id === "chat" || !panelId || !$(panelId)) continue;
                    const frameId = v2EmbeddedFrameId({ id, frameId: String(tab.frameId || "") });
                    v2OpenTabs.set(id, {
                      id,
                      label: String(tab.label || "工程页面"),
                      panelId,
                      stepId: String(tab.stepId || ""),
                      closable: tab.closable !== false,
                      frameId,
                      url: v2EmbeddedTabUrl({ id, frameId })
                    });
                  }
                  const activeTabId = String(cached.activeTabId || "chat");
                  v2ActiveTabId = v2OpenTabs.has(activeTabId) ? activeTabId : "chat";
                  if (typeof cached.selectedStep === "string" && cached.selectedStep) {
                    v2SelectedStep = cached.selectedStep;
                  }
                  v2UserSelectedStep = !!cached.userSelectedStep;
                  const activeTab = v2OpenTabs.get(v2ActiveTabId);
                  if (activeTab?.stepId) {
                    v2SelectedStep = activeTab.stepId;
                    v2UserSelectedStep = true;
                  }
                  state.projectAnalysisMode = !!cached.settings?.projectAnalysisMode;
                  const skillMode = cached.settings?.advancedPlanningMode ? "game-design-master" : String(cached.settings?.chatSkillMode || "");
                  if ($("chatSkillMode") && Array.from($("chatSkillMode").options).some(option => option.value === skillMode)) {
                    $("chatSkillMode").value = skillMode || "normal";
                    v2PendingProjectUiSkillMode = "";
                  } else {
                    v2PendingProjectUiSkillMode = skillMode || "";
                  }
                  for (const tab of v2OpenTabs.values()) {
                    if (tab.frameId && tab.url) v2LoadEmbeddedFrame(tab.frameId, tab.url);
                  }
                  renderSelectedSkillAction();
                  v2RenderProjectAnalysisMode();
                }
                function v2StepLabel(stepId) {
                  const item = v2Steps.find(step => step[0] === stepId);
                  return item ? item[1] : "工程页面";
                }
                function v2StepIconUrl(iconName) {
                  const safe = String(iconName || "panel").replace(/[^a-z0-9-]/gi, "");
                  return `/ui-v2/icons/workflow-${safe}.svg`;
                }
                function v2PanelForStep(stepId) {
                  if (stepId === "new-project") return "currentProjectPanel";
                  if (stepId === "create-prototype") return "prototypeWorkflowPanel";
                  if (stepId === "prototype-acceptance") return "v2AcceptancePanel";
                  if (stepId === "iteration-plan") return "v2IterationPanel";
                  if (stepId === "ui-optimization") return "v2UiOptimizationPanel";
                  if (stepId === "execute-or-repair") return "v2RepairPanel";
                  if (stepId === "asset-inventory") return "v2AssetInventoryFramePanel";
                  if (stepId === "download-project") return "v2DownloadsFramePanel";
                  if (stepId === "gdd-outline") return "v2GddOutlineFramePanel";
                  return "currentProjectPanel";
                }
                function v2OpenEmbeddedTab(tabId, label, panelId, frameId, url) {
                  v2OpenTabs.set(tabId, { id: tabId, label, panelId, frameId, url, closable: true });
                  v2ActiveTabId = tabId;
                  v2ApplySelectedStepVisibility();
                  v2LoadEmbeddedFrame(frameId, url);
                  v2RenderTabs();
                  v2RenderProgress();
                  v2WriteProjectUiState();
                }
                function v2OpenStepTab(stepId, runAction = true) {
                  const panelId = v2PanelForStep(stepId);
                  const tabId = `step:${stepId}`;
                  v2OpenTabs.set(tabId, { id: tabId, label: v2StepLabel(stepId), panelId, stepId, closable: true });
                  v2ActiveTabId = tabId;
                  v2SelectedStep = stepId;
                  v2UserSelectedStep = true;
                  v2ApplySelectedStepVisibility();
                  if (runAction) v2RunStepAction(stepId);
                  v2RenderTabs();
                  v2RenderProgress();
                  v2RefreshAcceptanceActionState();
                  v2WriteProjectUiState();
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
                  v2WriteProjectUiState();
                }
                function v2RenderTabs() {
                  const tabs = $("v2WorkspaceTabs");
                  if (!tabs) return;
                  tabs.innerHTML = Array.from(v2OpenTabs.values()).map(tab => `
                    <button type="button" class="v2-tab ${v2ActiveTabId === tab.id ? "active" : ""}" data-v2-tab="${escapeHtml(tab.id)}">
                      <span>${escapeHtml(tab.label)}</span>
                      ${tab.closable ? `<span class="v2-tab-close" data-v2-tab-close="${escapeHtml(tab.id)}" aria-label="关闭">×</span>` : ""}
                    </button>
                  `).join("");
                  tabs.querySelectorAll("[data-v2-tab]").forEach(button => {
                    button.onclick = event => {
                      const close = event.target?.closest?.("[data-v2-tab-close]");
                      if (close) {
                        event.preventDefault();
                        event.stopPropagation();
                        v2CloseTab(close.dataset.v2TabClose);
                        return;
                      }
                      v2ActiveTabId = button.dataset.v2Tab;
                      const tab = v2OpenTabs.get(v2ActiveTabId);
                      if (tab?.stepId) {
                        v2SelectedStep = tab.stepId;
                        v2UserSelectedStep = true;
                      }
                      v2RenderTabs();
                      v2ApplySelectedStepVisibility();
                      v2RenderProgress();
                      v2WriteProjectUiState();
                    };
                  });
                }
                function v2SortedProjects() {
                  return listableProjects(state.projects || [])
                    .slice()
                    .sort((a, b) => (projectTimestamp(b) || 0) - (projectTimestamp(a) || 0) || String(b.projectId || "").localeCompare(String(a.projectId || "")));
                }
                function v2RenderLeftProjectList() {
                  const shell = $("v2LeftProjects");
                  if (!shell) return;
                  const projects = v2SortedProjects();
                  shell.innerHTML = projects.map(project => {
                    const current = project.projectId === state.projectId;
                    const title = project.name || project.gameName || project.projectId;
                    const created = project.createdUtc || project.createdAtUtc || "";
                    return `
                      <button type="button" class="v2-left-project-button ${current ? "current" : ""}" data-v2-left-project="${escapeHtml(project.projectId)}">
                        <span>${escapeHtml(title)}</span>
                        <span class="v2-left-project-meta">${escapeHtml(project.gameName || project.templateRuleId || "")}${created ? ` · ${escapeHtml(created.slice(0, 10))}` : ""}</span>
                      </button>
                    `;
                  }).join("") || "<p class='muted'>还没有项目。</p>";
                  shell.querySelectorAll("[data-v2-left-project]").forEach(button => {
                    button.onclick = () => selectProject(button.dataset.v2LeftProject);
                  });
                }
                function v2HasPackages() {
                  if (Array.isArray(state.packageList)) return state.packageList.length > 0;
                  return Array.isArray(state.packageList?.packages) && state.packageList.packages.length > 0;
                }
                function v2AssetInventoryConfirmed() {
                  return !!state.assetInventory?.canReadInventory;
                }
                function v2RunTimestamp(run) {
                  return v2IsoTime(run?.finishedUtc || run?.progressUpdatedUtc || run?.startedUtc || run?.createdUtc || "");
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
                function v2LatestRunByType(runType) {
                  return (state.runs || [])
                    .filter(run => String(run.runType || "").toLowerCase() === String(runType || "").toLowerCase())
                    .sort((a, b) => v2RunTimestamp(b) - v2RunTimestamp(a) || String(b.runId || "").localeCompare(String(a.runId || "")))[0] || null;
                }
                function v2LatestValidationOnlyAcceptanceRun() {
                  return (state.runs || [])
                    .filter(run => String(run.runType || "").toLowerCase() === "prototype-7day-playable" && v2IsValidationOnlyRun(run))
                    .sort((a, b) => v2RunTimestamp(b) - v2RunTimestamp(a) || String(b.runId || "").localeCompare(String(a.runId || "")))[0] || null;
                }
                function v2IsoTime(value) {
                  const time = Date.parse(value || "");
                  return Number.isFinite(time) ? time : 0;
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
                  if (stepId === "new-project") return state.projectId ? "done" : "pending";
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
                  if (stepId === "iteration-plan") {
                    const goals = Array.isArray(state.iterationPlan?.goals) ? state.iterationPlan.goals : [];
                    if (!goals.length) return "pending";
                    if (goals.some(goal => ["needs_fix", "failed"].includes(String(goal.status || "").trim().toLowerCase()))) return "fix";
                    if (goals.every(goal => ["succeeded", "completed"].includes(String(goal.status || "").trim().toLowerCase()))) return "done";
                    if (goals.some(goal => ["pending", "running"].includes(String(goal.status || "").trim().toLowerCase()))) return "continue";
                    return "pending";
                  }
                  if (stepId === "execute-or-repair") {
                    const goals = state.repairPlan?.goals || [];
                    if (failed) return "fix";
                    if (goals.some(goal => goal.status === "needs_fix" || goal.status === "failed")) return "fix";
                    if (goals.length && goals.every(goal => goal.status === "succeeded" || goal.status === "completed")) return "done";
                    if (!goals.length && v2HasPrototypeSkeleton()) return "done";
                    return "pending";
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
                  if (stepId === "asset-inventory") return v2AssetInventoryConfirmed() ? "done" : "pending";
                  if (stepId === "download-project") return v2HasPackages() ? "done" : "pending";
                  return "pending";
                }
                function v2RenderUiOptimizationStatus() {
                  const status = $("uiOptimizationStatus");
                  if (!status) return;
                  const run = v2LatestRunByType("prototype-ui-optimization");
                  if (!run) {
                    status.className = "card muted";
                    status.textContent = "完成游戏模块后运行。系统会尝试复用现有原型场景和节点，不创建第二套无关 UI。";
                    return;
                  }
                  const runStatus = String(run.status || "").toLowerCase();
                  const substep = String(run.progressSubstep || "").toLowerCase();
                  if (runStatus === "succeeded" && substep !== "validation_skipped") {
                    status.className = "card";
                    status.textContent = run.progressLabel || "游戏界面优化已完成，短验证已通过。左侧进度栏已标记为完成；如需再次调整，可以重新运行游戏界面优化。";
                    return;
                  }
                  if (runStatus === "failed" || substep === "validation_failed") {
                    status.className = "card";
                    status.textContent = run.progressLabel || "最近一次游戏界面优化失败，请检查运行记录后重新运行。";
                    return;
                  }
                  if (runStatus === "running" || runStatus === "queued") {
                    status.className = "card muted";
                    status.textContent = run.progressLabel || "游戏界面优化正在运行，请等待后台任务完成。";
                    return;
                  }
                  status.className = "card muted";
                  status.textContent = run.progressLabel || `最近一次游戏界面优化状态：${run.status || "未知"}。`;
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
                function v2ShowChatTab() {
                  v2ActiveTabId = "chat";
                  v2RenderTabs();
                  v2ApplySelectedStepVisibility();
                  v2RenderProgress();
                  v2WriteProjectUiState();
                }
                function v2ShowStep(stepId, userInitiated = false) {
                  if (userInitiated) {
                    v2OpenStepTab(stepId);
                    return;
                  }
                  v2SelectedStep = stepId;
                  v2ApplySelectedStepVisibility();
                  v2ApplyPrototypeFormLock();
                  v2RunStepAction(stepId);
                  v2RenderProgress();
                  v2RefreshAcceptanceActionState();
                  v2WriteProjectUiState();
                }
                function v2ShouldDefaultToPrototypeCreation(progress) {
                  const status = String(progress?.status || "").trim().toLowerCase();
                  return !status || status === "idle";
                }
                function v2SelectDefaultStepForPrototypeProgress(progress) {
                  return;
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
                function v2LoadEmbeddedFrame(frameId, url) {
                  const frame = $(frameId);
                  if (!frame) return;
                  if (frame.dataset.src !== url) {
                    frame.dataset.src = url;
                    frame.src = url;
                  }
                }
                function v2AppendOnce(parent, element) {
                  if (!parent || !element || element.parentElement === parent) return;
                  parent.appendChild(element);
                }
                function v2InstallFastTooltips() {
                  if (document.body.dataset.v2FastTooltips === "1") return;
                  document.body.dataset.v2FastTooltips = "1";
                  const tooltip = document.createElement("div");
                  tooltip.id = "v2FastTooltip";
                  tooltip.className = "v2-fast-tooltip";
                  document.body.appendChild(tooltip);
                  let timer = 0;
                  let active = null;
                  const titleOf = element => element?.getAttribute?.("data-v2-tooltip") || element?.getAttribute?.("title") || "";
                  const close = () => {
                    clearTimeout(timer);
                    timer = 0;
                    tooltip.classList.remove("open");
                    if (active?.dataset?.v2NativeTitle) {
                      active.setAttribute("title", active.dataset.v2NativeTitle);
                      delete active.dataset.v2NativeTitle;
                    }
                    active = null;
                  };
                  const position = event => {
                    const margin = 12;
                    const rect = tooltip.getBoundingClientRect();
                    let left = Math.min(window.innerWidth - rect.width - margin, event.clientX + margin);
                    let top = Math.min(window.innerHeight - rect.height - margin, event.clientY + margin);
                    tooltip.style.left = `${Math.max(margin, left)}px`;
                    tooltip.style.top = `${Math.max(margin, top)}px`;
                  };
                  document.addEventListener("pointerover", event => {
                    const target = event.target?.closest?.("[title], [data-v2-tooltip]");
                    if (!target) return;
                    const title = titleOf(target);
                    if (!title) return;
                    close();
                    active = target;
                    if (target.hasAttribute("title")) {
                      target.dataset.v2NativeTitle = target.getAttribute("title");
                      target.removeAttribute("title");
                    }
                    tooltip.textContent = title;
                    position(event);
                    timer = setTimeout(() => {
                      tooltip.classList.add("open");
                      position(event);
                    }, 120);
                  });
                  document.addEventListener("pointermove", event => {
                    if (active) position(event);
                  });
                  document.addEventListener("pointerout", event => {
                    if (active && !event.relatedTarget?.closest?.("[title], [data-v2-tooltip]")) close();
                  });
                  document.addEventListener("scroll", close, true);
                }
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
                function v2EnsureContentGrid() {
                  const detailPanel = $("projectDetailPanel");
                  const progressShell = $("v2ProgressShell");
                  if (!detailPanel || !progressShell) return;
                  detailPanel.classList.add("v2-workspace-shell");
                  let leftRail = $("v2LeftRail");
                  if (!leftRail) {
                    leftRail = document.createElement("aside");
                    leftRail.id = "v2LeftRail";
                    detailPanel.insertBefore(leftRail, detailPanel.firstChild);
                  }
                  let leftProjects = $("v2LeftProjectsShell");
                  if (!leftProjects) {
                    leftProjects = document.createElement("section");
                    leftProjects.id = "v2LeftProjectsShell";
                    leftProjects.className = "stack";
                    leftProjects.innerHTML = `<h2 class="v2-left-title">项目列表</h2><div id="v2LeftProjects" class="v2-left-projects"></div>`;
                  }
                  v2AppendOnce(leftRail, progressShell);
                  if (!$("v2LeftSpacer")) {
                    const spacer = document.createElement("div");
                    spacer.id = "v2LeftSpacer";
                    spacer.className = "v2-left-spacer";
                    leftRail.appendChild(spacer);
                  }
                  v2AppendOnce(leftRail, leftProjects);
                  let rightWorkspace = $("v2RightWorkspace");
                  if (!rightWorkspace) {
                    rightWorkspace = document.createElement("div");
                    rightWorkspace.id = "v2RightWorkspace";
                    detailPanel.appendChild(rightWorkspace);
                  }
                  let tabs = $("v2WorkspaceTabs");
                  if (!tabs) {
                    tabs = document.createElement("div");
                    tabs.id = "v2WorkspaceTabs";
                    tabs.className = "v2-tabs";
                    rightWorkspace.appendChild(tabs);
                  }
                  let grid = $("v2ContentGrid");
                  if (!grid) {
                    grid = document.createElement("div");
                    grid.id = "v2ContentGrid";
                    grid.className = "v2-content-grid v2-tab-content";
                    rightWorkspace.appendChild(grid);
                  }
                  v2CreateAcceptancePanel();
                  v2CreateUiOptimizationPanel();
                  v2CreateEmbeddedFramePanel("v2AssetInventoryFramePanel", "v2AssetInventoryFrame", "项目素材库");
                  v2CreateEmbeddedFramePanel("v2DownloadsFramePanel", "v2DownloadsFrame", "打包下载项目");
                  v2CreateEmbeddedFramePanel("v2GddOutlineFramePanel", "v2GddOutlineFrame", "查阅策划大纲");
                  ["chatPanel", "v2IterationPanel", "v2RepairPanel", "v2UiOptimizationPanel", "v2AcceptancePanel", "v2AssetInventoryFramePanel", "v2DownloadsFramePanel", "v2GddOutlineFramePanel", "currentProjectPanel", "prototypeWorkflowPanel", "prototypeCommandPanel", "runsPanel"].forEach(id => {
                    const element = $(id);
                    v2AppendOnce(grid, element);
                  });
                  v2RenderTabs();
                  v2RenderLeftProjectList();
                }
                function v2CreateEmbeddedFramePanel(panelId, frameId, title) {
                  if ($(panelId)) return;
                  const panel = document.createElement("section");
                  panel.id = panelId;
                  panel.className = "stack hidden";
                  panel.setAttribute("aria-label", title);
                  panel.innerHTML = `<iframe id="${frameId}" class="v2-embedded-frame" title="${escapeHtml(title)}"></iframe>`;
                  $("v2ContentGrid")?.appendChild(panel);
                }
                function v2CreateAcceptancePanel() {
                  if ($("v2AcceptancePanel")) return;
                  const summary = $("prototypeAcceptanceSummary");
                  if (!summary) return;
                  const panel = document.createElement("section");
                  panel.id = "v2AcceptancePanel";
                  panel.className = "stack hidden";
                  panel.innerHTML = "<h2>原型验收结果</h2>";
                  summary.insertAdjacentElement("beforebegin", panel);
                  panel.appendChild(summary);
                  const actions = document.createElement("div");
                  actions.className = "v2-action-row";
                  const rerun = document.createElement("button");
                  rerun.id = "v2RevalidatePrototype";
                  rerun.className = "secondary";
                  rerun.type = "button";
                  rerun.textContent = "重新触发原型验收";
                  rerun.onclick = v2ValidatePrototypeIfAllowed;
                  actions.appendChild(rerun);
                  panel.appendChild(actions);
                  const status = document.createElement("div");
                  status.id = "v2AcceptanceActionStatus";
                  status.className = "card muted";
                  status.textContent = "原型验收入口会在游戏模块完成后启用。游戏界面优化是可选步骤，不会阻塞验收。";
                  panel.appendChild(status);
                }
                function v2CreateUiOptimizationPanel() {
                  if ($("v2UiOptimizationPanel")) return;
                  const panel = document.createElement("section");
                  panel.id = "v2UiOptimizationPanel";
                  panel.className = "stack hidden";
                  panel.innerHTML = `
                    <h2>游戏界面优化</h2>
                    <p class="muted">按照当前游戏类型模板重新对齐原型 UI。RPG 项目会优先参考 He-is-Coming 的地图、战斗、奖励、状态和日志布局。</p>
                    <button id="runUiOptimization" class="secondary" type="button" data-global-action="true">运行游戏界面优化</button>
                    <div id="uiOptimizationStatus" class="card muted">完成游戏模块后运行。系统会尝试复用现有原型场景和节点，不创建第二套无关 UI。</div>
                  `;
                  $("v2AcceptancePanel")?.insertAdjacentElement("beforebegin", panel);
                  $("runUiOptimization").onclick = runUiOptimization;
                }
                function v2IterationPlanAllowsAcceptance() {
                  const goals = state.iterationPlan?.goals;
                  if (!Array.isArray(goals) || goals.length === 0) return true;
                  return goals.every(goal => ["succeeded", "completed"].includes(String(goal.status || "").trim().toLowerCase()));
                }
                function v2PrototypeAcceptanceBlockReason() {
                  if (!v2IterationPlanAllowsAcceptance()) {
                    return "请先完成当前游戏模块，所有目标完成后再进行原型验收。";
                  }
                  if (isGlobalBusy()) {
                    return "当前有任务正在执行，请等待当前 run 完成后再进行原型验收。";
                  }
                  return "";
                }
                function v2RefreshAcceptanceActionState() {
                  const rerun = $("v2RevalidatePrototype");
                  const status = $("v2AcceptanceActionStatus");
                  if (!rerun || !status) return;
                  const reason = v2PrototypeAcceptanceBlockReason();
                  rerun.disabled = !!reason;
                  rerun.title = reason || "";
                  status.className = reason ? "card muted" : "card";
                  status.textContent = reason || "当前已满足原型验收条件，点击按钮会创建一条原型验收 run。";
                }
                async function v2ValidatePrototypeIfAllowed() {
                  const reason = v2PrototypeAcceptanceBlockReason();
                  if (reason) {
                    const status = $("v2AcceptanceActionStatus");
                    if (status) {
                      status.className = "card muted";
                      status.textContent = reason;
                    }
                    out(reason);
                    return;
                  }
                  await validatePrototype();
                }
                function v2ArrangeIterationPanel() {
                  const panel = $("v2IterationPanel");
                  if (!panel || $("v2IterationMainActions")) return;
                  const mainActions = document.createElement("div");
                  mainActions.id = "v2IterationMainActions";
                  mainActions.className = "v2-action-row";
                  const createPlan = $("createIterationPlan");
                  const evaluatePlan = $("evaluateIterationPlan");
                  const executeGoal = $("executeIterationGoal");
                  const deletePlan = $("deleteIterationPlan");
                  createPlan?.insertAdjacentElement("beforebegin", mainActions);
                  const roundTabs = document.createElement("div");
                  roundTabs.id = "v2IterationRoundTabs";
                  roundTabs.className = "v2-round-tabs hidden";
                  mainActions.insertAdjacentElement("beforebegin", roundTabs);
                  [createPlan, evaluatePlan, executeGoal, deletePlan].filter(Boolean).forEach(button => mainActions.appendChild(button));

                  v2CreateRepairPanel();
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
                function resizeChatComposer() {
                  const textarea = $("chatMessage");
                  if (!textarea) return;
                  textarea.style.height = "auto";
                  textarea.style.height = `${Math.min(textarea.scrollHeight, 176)}px`;
                }
                function v2HandleChatMessageKeydown(event) {
                  if (event.key !== "Enter" || event.shiftKey || event.ctrlKey || event.altKey || event.metaKey || event.isComposing) return;
                  event.preventDefault();
                  if (!$("sendChat")?.disabled) sendChat();
                }
                function v2HideLegacyChatFeedback() {
                  if (!document.body.classList.contains("v2-detail")) return;
                  $("feedbackSummary")?.classList.add("hidden");
                  $("feedbackRecords")?.classList.add("hidden");
                }
                function v2ArrangeChatPanel() {
                  const chatPanel = $("chatPanel");
                  if (!chatPanel) return;
                  const title = Array.from(chatPanel.querySelectorAll("h2")).find(heading => ["自由聊天", "自由对话", "聊天记录"].includes(heading.textContent.trim()));
                  title?.classList.add("hidden");
                  if (title?.nextElementSibling?.tagName === "P") title.nextElementSibling.classList.add("hidden");
                  const chatRecordTitle = Array.from(chatPanel.querySelectorAll("h2")).find(heading => heading.textContent.trim() === "聊天记录");
                  chatRecordTitle?.classList.add("hidden");
                  const flowTitle = Array.from(chatPanel.querySelectorAll("h2")).find(heading => heading.textContent.trim() === "流程记录");
                  flowTitle?.classList.add("hidden");
                  v2HideLegacyChatFeedback();
                  $("evaluateIterationPlanFromChat")?.classList.add("hidden");
                  if ($("v2ChatControls")) return;
                  const messageLabel = $("chatMessage")?.closest("label");
                  messageLabel?.classList.add("v2-message-field");
                  if (messageLabel?.childNodes?.[0]?.nodeType === Node.TEXT_NODE) messageLabel.childNodes[0].textContent = "";
                  if (!$("v2ChatComposer")) {
                    const composer = document.createElement("div");
                    composer.id = "v2ChatComposer";
                    composer.className = "v2-chat-composer";
                    ($("chatHistory") || chatPanel).insertAdjacentElement("afterend", composer);
                    if (!$("v2SkillRow")) {
                      const skillRow = document.createElement("div");
                      skillRow.id = "v2SkillRow";
                      skillRow.className = "v2-skill-row";
                      const skillLabel = $("chatSkillMode")?.closest("label");
                      const skillDescription = $("chatSkillDescription");
                      [skillLabel, skillDescription].filter(Boolean).forEach(element => skillRow.appendChild(element));
                      composer.appendChild(skillRow);
                    }
                    if (messageLabel) composer.appendChild(messageLabel);
                  }
                  const composer = $("v2ChatComposer");
                  if (!$("v2ChatAttachmentPanel")) {
                    const attachmentPanel = document.createElement("div");
                    attachmentPanel.id = "v2ChatAttachmentPanel";
                    attachmentPanel.className = "v2-chat-attachments";
                    composer?.appendChild(attachmentPanel);
                    [$("chatAttachmentStatus")].filter(Boolean).forEach(element => attachmentPanel.appendChild(element));
                  }
                  const attachmentPanel = $("v2ChatAttachmentPanel");
                  const controls = document.createElement("div");
                  controls.id = "v2ChatControls";
                  controls.className = "v2-chat-controls";
                  composer?.appendChild(controls);
                  $("submitFormalFeedback")?.classList.add("hidden");
                  const attachLabel = $("chatAttachmentFiles")?.closest("label");
                  if (attachLabel) {
                    attachLabel.className = "ghost v2-file-button";
                    if (attachLabel.childNodes?.[0]?.nodeType === Node.TEXT_NODE) attachLabel.childNodes[0].textContent = "\u5bfc\u5165\u6587\u4ef6";
                    attachLabel.title = "导入 TXT 参考文件";
                  }
                  let advancedPlanning = $("v2AdvancedPlanningMode");
                  if (!advancedPlanning) {
                    advancedPlanning = document.createElement("button");
                    advancedPlanning.id = "v2AdvancedPlanningMode";
                    advancedPlanning.type = "button";
                    advancedPlanning.className = "ghost";
                    advancedPlanning.textContent = "高级策划模式";
                    advancedPlanning.title = "激活高级策划模式，帮助梳理玩法、GDD、机制、叙事与原型设计建议";
                    advancedPlanning.onclick = v2ToggleAdvancedPlanningMode;
                  }
                  let nextStepButton = $("v2JudgeNextStep");
                  if (!nextStepButton) {
                    nextStepButton = document.createElement("button");
                    nextStepButton.id = "v2JudgeNextStep";
                    nextStepButton.type = "button";
                    nextStepButton.className = "ghost";
                    nextStepButton.textContent = "下一步建议";
                    nextStepButton.title = "扫描当前项目状态，并在聊天窗口显示系统下一步建议";
                    nextStepButton.onclick = () => queryWorkflowRoute();
                  }
                  let projectAnalysis = $("v2ProjectAnalysisMode");
                  if (!projectAnalysis) {
                    projectAnalysis = document.createElement("button");
                    projectAnalysis.id = "v2ProjectAnalysisMode";
                    projectAnalysis.type = "button";
                    projectAnalysis.className = "ghost";
                    projectAnalysis.textContent = "项目分析模式";
                    projectAnalysis.title = "系统会扫描项目进度后回复问题，速度慢，可以使用下一步建议按钮替代";
                    projectAnalysis.onclick = v2ToggleProjectAnalysisMode;
                  }
                  if ($("clearChatAttachments")) $("clearChatAttachments").textContent = "清空";
                  [$("chatAttachmentFiles")?.closest("label"), advancedPlanning, projectAnalysis, nextStepButton, $("clearChatAttachments"), $("syncChatHistory"), $("downloadChatHistory"), $("createGddDocument"), $("sendChat")].filter(Boolean).forEach(element => controls.appendChild(element));
                  v2RenderAdvancedPlanningMode();
                  v2RenderProjectAnalysisMode();
                  $("chatMessage").removeEventListener("input", v2RenderChatIterationPlanButtonState);
                  $("chatMessage").removeEventListener("input", resizeChatComposer);
                  $("chatMessage").removeEventListener("keydown", v2HandleChatMessageKeydown);
                  $("chatMessage").addEventListener("input", v2RenderChatIterationPlanButtonState);
                  $("chatMessage").addEventListener("input", resizeChatComposer);
                  $("chatMessage").addEventListener("keydown", v2HandleChatMessageKeydown);
                  resizeChatComposer();
                  v2RenderChatIterationPlanButtonState();
                }
                function v2ToggleAdvancedPlanningMode() {
                  const select = $("chatSkillMode");
                  if (!select) return;
                  select.value = select.value === "game-design-master" ? "normal" : "game-design-master";
                  renderSelectedSkillAction();
                  v2WriteProjectUiState();
                }
                function v2RenderAdvancedPlanningMode() {
                  const button = $("v2AdvancedPlanningMode");
                  const select = $("chatSkillMode");
                  if (!button || !select) return;
                  const active = select.value === "game-design-master";
                  button.classList.toggle("active", active);
                  button.setAttribute("aria-pressed", active ? "true" : "false");
                }
                function v2ToggleProjectAnalysisMode() {
                  state.projectAnalysisMode = !state.projectAnalysisMode;
                  v2RenderProjectAnalysisMode();
                  v2WriteProjectUiState();
                }
                function v2RenderProjectAnalysisMode() {
                  const button = $("v2ProjectAnalysisMode");
                  if (!button) return;
                  const active = !!state.projectAnalysisMode;
                  button.classList.toggle("active", active);
                  button.setAttribute("aria-pressed", active ? "true" : "false");
                }
                function v2IterationPlanExists() {
                  return Array.isArray(state.iterationPlan?.goals) && state.iterationPlan.goals.length > 0;
                }
                function v2IterationPlanCompleted() {
                  const goals = Array.isArray(state.iterationPlan?.goals) ? state.iterationPlan.goals : [];
                  return goals.length > 0 && goals.every(goal => ["succeeded", "completed"].includes(String(goal.status || "").trim().toLowerCase()));
                }
                function v2PrototypeValidationPassedForPlanning() {
                  return state.prototypeReadyForFeedback && !state.v2PrototypeValidationInvalidatedByIteration;
                }
                function v2PrototypeValidationInvalidationKey() {
                  return `phaseA:v2PrototypeValidationInvalidated:${state.projectId || "none"}`;
                }
                function v2LoadPrototypeValidationInvalidation() {
                  state.v2PrototypeValidationInvalidatedByIteration = localStorage.getItem(v2PrototypeValidationInvalidationKey()) === "true";
                }
                function v2SetPrototypeValidationInvalidated(value) {
                  state.v2PrototypeValidationInvalidatedByIteration = !!value;
                  if (!state.projectId) return;
                  if (value) localStorage.setItem(v2PrototypeValidationInvalidationKey(), "true");
                  else localStorage.removeItem(v2PrototypeValidationInvalidationKey());
                }
                function v2CanCreateIterationPlanFromChat() {
                  return v2IterationPlanExists() && v2IterationPlanCompleted() && v2PrototypeValidationPassedForPlanning() && !isGlobalBusy();
                }
                function v2RenderChatIterationPlanButtonState() {
                  return;
                }
                function v2PrototypeStatus() {
                  const text = $("prototypeProgress")?.textContent || "";
                  if (text.includes("succeeded")) return "succeeded";
                  if (text.includes("running")) return "running";
                  if (text.includes("failed")) return "failed";
                  if (text.includes("idle")) return "idle";
                  return state.v2PrototypeStatus || "";
                }
                function v2ShouldLockPrototypeForm() {
                  const status = String(state?.v2PrototypeCreationStatus || v2PrototypeStatus() || "").trim().toLowerCase();
                  return !!state.projectId && status !== "" && !["idle", "failed"].includes(status);
                }
                function v2ApplyPrototypeFormLock() {
                  const locked = v2ShouldLockPrototypeForm();
                  $("prototypeWorkflowPanel")?.classList.toggle("v2-prototype-locked", locked);
                  prototypeInputIds.forEach(id => { if ($(id)) $(id).disabled = locked; });
                  if ($("draftFile")) $("draftFile").disabled = locked;
                  if ($("importDraft")) $("importDraft").disabled = locked;
                  if ($("runPrototype")) {
                    $("runPrototype").disabled = locked || isGlobalBusy();
                    $("runPrototype").textContent = locked ? "原型骨架已创建，不能重复创建" : "运行原型骨架创建";
                  }
                }
                function v2ApplyPrototypeFormSnapshot(progress) {
                  const form = progress?.form;
                  if (!form) return;
                  if (form.prototypeSlug) $("protoSlug").value = form.prototypeSlug;
                  if (form.hypothesis) $("hypothesis").value = form.hypothesis;
                  if (form.corePlayerFantasy) $("corePlayerFantasy").value = form.corePlayerFantasy;
                  if (form.minimumPlayableLoop) $("minimumPlayableLoop").value = form.minimumPlayableLoop;
                  if (Array.isArray(form.successCriteria) && form.successCriteria.length) $("successCriteria").value = form.successCriteria.join("\n");
                  if (form.gameFeature) $("gameFeature").value = form.gameFeature;
                  if (form.coreGameplayLoop) $("coreGameplayLoop").value = form.coreGameplayLoop;
                  if (form.winFailConditions) $("winFailConditions").value = form.winFailConditions;
                }
                function v2CompletedIterationStatus(status) {
                  return ["succeeded", "completed", "done"].includes(String(status || "").trim().toLowerCase());
                }
                function v2CurrentPrototypeStatus() {
                  return String(state?.v2PrototypeStatus || "").trim().toLowerCase();
                }
                function v2HasPrototypeSkeleton() {
                  const status = String(state?.v2PrototypeCreationStatus || state?.v2PrototypeStatus || "").trim().toLowerCase();
                  return status === "succeeded";
                }
                function v2HasFailedPrototypeAcceptance() {
                  return v2CurrentPrototypeStatus() === "failed" || !!state.prototypeFailure;
                }
                function v2RepairPlanHasRunnableStep() {
                  const goals = Array.isArray(state.repairPlan?.goals) ? state.repairPlan.goals : [];
                  return goals.some(goal => ["pending", "needs_fix", "failed"].includes(String(goal.status || "").trim().toLowerCase()));
                }
                function v2RepairPlanCompletedOrEmpty() {
                  const goals = Array.isArray(state.repairPlan?.goals) ? state.repairPlan.goals : [];
                  return goals.length === 0 || goals.every(goal => ["succeeded", "completed", "done"].includes(String(goal.status || "").trim().toLowerCase()));
                }
                function v2IterationPlanGoalState() {
                  const goals = Array.isArray(state.iterationPlan?.goals) ? state.iterationPlan.goals : [];
                  const hasPlan = !!state.iterationPlan?.session && goals.length > 0;
                  const hasNeedsFix = goals.some(goal => ["needs_fix", "failed"].includes(String(goal.status || "").trim().toLowerCase()));
                  const hasPending = goals.some(goal => ["pending", "running"].includes(String(goal.status || "").trim().toLowerCase()));
                  const allCompleted = hasPlan && goals.every(goal => v2CompletedIterationStatus(goal.status));
                  return { goals, hasPlan, hasNeedsFix, hasPending, allCompleted };
                }
                function buildWorkflowRouteChatContent(route, intent = null) {
                  const lines = [
                    route?.summary || "",
                    "",
                    route?.recommendation || ""
                  ];
                  const actions = workflowRouteActions(route);
                  if (actions.length) {
                    lines.push("", `推荐页面：${actions.map(action => action.runName || action.label || action.actionId).join("、")}`);
                    lines.push("系统不会自动启动 run。需要你点击下方一次性按钮打开对应页面，再在页面内确认执行。");
                  }
                  return lines.filter(line => line !== null && line !== undefined).join("\n").trim();
                }

                function buildWorkflowRouteMessageExtra(route, intent = null) {
                  invalidateWorkflowRouteAction(false);
                  const actions = workflowRouteActions(route);
                  const action = actions[0] || null;
                  const token = actions.length
                    ? `workflow-${Date.now()}-${Math.random().toString(16).slice(2)}`
                    : "";
                  if (token) {
                    state.workflowRouteActionToken = token;
                    state.workflowRouteActionConsumed = false;
                  }
                  return {
                    workflowRoute: route,
                    workflowIntent: intent,
                    workflowAction: action,
                    workflowActions: actions,
                    workflowActionToken: token,
                    workflowActionConsumed: false
                  };
                }

                function appendWorkflowRouteMessage(route, intent = null) {
                  state.chatHistory.push({
                    role: "assistant",
                    kind: "workflow-route",
                    content: buildWorkflowRouteChatContent(route, intent),
                    ...buildWorkflowRouteMessageExtra(route, intent)
                  });
                  renderChatHistory();
                  saveChatHistoryForProject();
                }

                function invalidateWorkflowRouteAction(render = true) {
                  if (!state.workflowRouteActionToken) return;
                  state.workflowRouteActionConsumed = true;
                  state.chatHistory.forEach(message => {
                    if (message.workflowActionToken === state.workflowRouteActionToken) {
                      message.workflowActionConsumed = true;
                    }
                  });
                  state.workflowRouteActionToken = "";
                  if (render) {
                    renderChatHistory();
                    saveChatHistoryForProject();
                  }
                }

                function workflowRouteActions(route) {
                  const actions = Array.isArray(route?.actions) && route.actions.length ? route.actions : [route?.nextAction].filter(Boolean);
                  return actions.filter(action => action?.enabled !== false && action?.actionId && action.actionId !== "none");
                }

                function workflowMessageActions(message) {
                  const actions = Array.isArray(message?.workflowActions) && message.workflowActions.length ? message.workflowActions : [message?.workflowAction].filter(Boolean);
                  return actions.filter(action => action?.enabled !== false && action?.actionId && action.actionId !== "none");
                }

                async function runWorkflowRecommendedAction(token, actionId = "") {
                  const message = state.chatHistory.find(item => item.workflowActionToken === token);
                  const action = workflowMessageActions(message).find(item => item.actionId === actionId) || workflowMessageActions(message)[0];
                  if (!message || !action || message.workflowActionConsumed || state.workflowRouteActionToken !== token) return;
                  let currentRoute = null;
                  try {
                    currentRoute = await fetchWorkflowRoute(message.workflowIntent);
                  } catch (error) {
                    showError(error);
                    return out("无法确认当前项目进度，请重新点击“下一步建议”后再打开推荐页面。");
                  }
                  if (message.workflowActionConsumed || state.workflowRouteActionToken !== token) return;
                  const currentActions = workflowRouteActions(currentRoute);
                  if (!currentActions.some(currentAction => workflowActionsMatch(currentAction, action))) {
                    message.workflowActionConsumed = true;
                    state.workflowRouteActionConsumed = true;
                    state.workflowRouteActionToken = "";
                    renderChatHistory();
                    saveChatHistoryForProject();
                    return out("项目进度已经变化，请重新点击“下一步建议”获取新的推荐。");
                  }
                  switch (action.actionId) {
                    case "create-prototype":
                      v2OpenStepTab("create-prototype", false);
                      return;
                    case "create-repair-plan":
                      v2OpenStepTab("execute-or-repair", false);
                      return;
                    case "execute-repair-step":
                      v2OpenStepTab("execute-or-repair", false);
                      return;
                    case "prototype-acceptance":
                      v2OpenStepTab(action.uiTarget === "execute-or-repair" ? "execute-or-repair" : "prototype-acceptance", false);
                      return;
                    case "create-iteration-plan":
                      v2OpenStepTab("iteration-plan", false);
                      return;
                    case "execute-iteration-goal":
                      v2OpenStepTab("iteration-plan", false);
                      return;
                    case "needs-fix-route":
                      v2OpenStepTab("iteration-plan", false);
                      return;
                    case "ui-optimization":
                      v2OpenStepTab("ui-optimization", false);
                      return;
                    case "asset-inventory":
                      v2OpenStepTab("asset-inventory");
                      return;
                    case "download-project":
                      v2OpenStepTab("download-project");
                      return;
                    case "create-next-iteration-plan":
                      openIterationPlanUpdateModal("new");
                      return;
                    default:
                      out(`暂不支持的推荐动作：${action.actionId}`);
                  }
                }

                async function queryWorkflowRoute(intent = null) {
                  if (!state.projectId) return out("请先选择一个项目。");
                  const button = $("v2JudgeNextStep");
                  if (button) {
                    button.disabled = true;
                    button.textContent = "扫描中...";
                  }
                  v2ShowChatTab();
                  const thinking = startChatThinkingMessage("正在扫描项目状态...");
                  try {
                    const route = await fetchWorkflowRoute(intent);
                    thinking.complete(buildWorkflowRouteChatContent(route, intent), false, "workflow-route", buildWorkflowRouteMessageExtra(route, intent));
                  } catch (error) {
                    const failure = workflowRouteFailureMessage(error);
                    thinking.complete(failure, true, "workflow-route");
                    showError(error);
                  } finally {
                    if (button) {
                      button.disabled = false;
                      button.textContent = "下一步建议";
                    }
                  }
                }
                function workflowRouteFailureMessage(error) {
                  const code = error?.payload?.failureCode || error?.payload?.error || error?.payload?.status || error?.status || "unknown_error";
                  if (code === "authentication_required" || error?.status === 401) {
                    return "项目状态扫描失败：登录状态无效，请重新输入登录 token。";
                  }
                  if (code === "project_not_found" || error?.status === 404) {
                    return "项目状态扫描失败：当前项目不可访问，请刷新项目列表后重新选择项目。";
                  }
                  if (code === "workflow_route_failed") {
                    return "项目状态扫描失败：项目状态读取异常，请稍后重试或联系管理员查看后台记录。";
                  }
                  return `项目状态扫描失败：${String(code || "unknown_error")}。请稍后重试或先刷新页面。`;
                }
                function workflowRouteQueryForIntent(intent = null) {
                  return intent?.intent === "playtest_feedback" && intent.feedbackSummary
                    ? `?playtestFeedback=${encodeURIComponent(intent.feedbackSummary)}`
                    : "";
                }
                async function fetchWorkflowRoute(intent = null) {
                  return await api(`/api/projects/${state.projectId}/workflow-route${workflowRouteQueryForIntent(intent)}`);
                }
                function workflowActionsMatch(currentAction, storedAction) {
                  if (!currentAction || !storedAction) return false;
                  return currentAction.enabled !== false &&
                    currentAction.actionId === storedAction.actionId &&
                    currentAction.uiTarget === storedAction.uiTarget;
                }
                function v2RenderProgress() {
                  const shell = $("v2ProgressSteps");
                  if (!shell) return;
                  shell.innerHTML = v2Steps.map(([id, label, iconName], index) => {
                    const status = v2StepStatus(id);
                    const mark = status === "done" ? "✓" : status === "fix" ? "×" : status === "continue" ? "•••" : "";
                    return `<button class="v2-step-button ${status} ${v2SelectedStep === id ? "active" : ""}" data-v2-step="${id}" style="--step-icon:url('${v2StepIconUrl(iconName)}')"><span class="v2-step-icon"></span><span class="v2-step-number">${index + 1}.</span><span class="v2-step-label">${label}</span><span class="v2-step-mark">${mark}</span></button>`;
                  }).join("");
                  document.querySelectorAll("[data-v2-step]").forEach(button => button.onclick = () => v2ShowStep(button.dataset.v2Step, true));
                  v2RenderChatIterationPlanButtonState();
                  v2RefreshAcceptanceActionState();
                  v2RenderUiOptimizationStatus();
                }
                const v2OriginalShowProjectDetail = showProjectDetail;
                showProjectDetail = function() {
                  if (v2CurrentProjectId !== state.projectId) {
                    v2CurrentProjectId = state.projectId;
                    v2RestoredProjectUiStateId = "";
                    v2SelectedStep = "new-project";
                    v2UserSelectedStep = false;
                    Array.from(v2OpenTabs.keys()).forEach(tabId => {
                      if (tabId !== "chat") v2OpenTabs.delete(tabId);
                    });
                    v2ActiveTabId = "chat";
                  }
                  v2CreateIterationPanel();
                  v2ArrangeChatPanel();
                  v2EnsureContentGrid();
                  v2OriginalShowProjectDetail();
                  v2LoadPrototypeValidationInvalidation();
                  v2EnsureContentGrid();
                  v2RestoreProjectUiState();
                  $("chatPanel")?.classList.remove("hidden");
                  v2ApplySelectedStepVisibility();
                  v2RenderTabs();
                  v2RenderLeftProjectList();
                  v2RenderProgress();
                  v2ApplyPrototypeFormLock();
                };
                const v2OriginalUpdateChatPanelVisibility = updateChatPanelVisibility;
                updateChatPanelVisibility = function(progress) {
                  state.v2PrototypeStatus = progress?.acceptanceStatus || progress?.status || "";
                  state.v2PrototypeCreationStatus = progress?.prototypeCreationStatus || progress?.status || "";
                  v2CreateIterationPanel();
                  v2ArrangeChatPanel();
                  v2EnsureContentGrid();
                  v2OriginalUpdateChatPanelVisibility(progress);
                  v2EnsureContentGrid();
                  v2SelectDefaultStepForPrototypeProgress(progress);
                  v2ApplySelectedStepVisibility();
                  v2ApplyPrototypeFormSnapshot(progress);
                  v2ApplyPrototypeFormLock();
                  v2RenderTabs();
                  v2RenderProgress();
                };
                const v2OriginalSubmitIterationPlanFromFeedback = submitIterationPlanFromFeedback;
                submitIterationPlanFromFeedback = async function(message, busyText, sourceKind = "manual_feedback") {
                  const result = await v2OriginalSubmitIterationPlanFromFeedback(message, busyText, sourceKind);
                  if (result?.status === "ready" && state.iterationPlan?.session) {
                    v2SetPrototypeValidationInvalidated(true);
                    setFormalFeedbackAvailability(false);
                  }
                  v2RenderChatIterationPlanButtonState();
                };
                const v2OriginalValidatePrototype = validatePrototype;
                validatePrototype = async function() {
                  await v2OriginalValidatePrototype();
                  if (state.prototypeReadyForFeedback) {
                    v2SetPrototypeValidationInvalidated(false);
                  }
                  v2RenderChatIterationPlanButtonState();
                };
                const v2OriginalSetPrototypeFormLocked = setPrototypeFormLocked;
                setPrototypeFormLocked = function(locked) {
                  v2OriginalSetPrototypeFormLocked(locked);
                  v2ApplyPrototypeFormLock();
                };
                v2CreateIterationPanel();
                v2ArrangeChatPanel();
                v2EnsureContentGrid();
                v2InstallFastTooltips();
                if ($("v2JudgeNextStep")) $("v2JudgeNextStep").onclick = () => queryWorkflowRoute();
                setInterval(v2RenderProgress, 2000);
              </script>
            </body>
            """;
    }

    public string RenderShell()
    {
        return """
            <!doctype html>
            <html lang="zh-CN">
            <head>
              <meta charset="utf-8">
              <meta name="viewport" content="width=device-width, initial-scale=1">
              <title>Game Ren</title>
              <style>
                :root {
                  color-scheme: light;
                  --ink: #17211b;
                  --muted: #66736b;
                  --paper: #fbf7ef;
                  --panel: rgba(255, 252, 245, 0.88);
                  --line: #ded4c4;
                  --accent: #0f6b57;
                  --accent-2: #c65f2d;
                  --danger: #a2342f;
                }
                * { box-sizing: border-box; }
                body {
                  margin: 0;
                  overflow-x: hidden;
                  font-family: Georgia, "Times New Roman", serif;
                  color: var(--ink);
                  background:
                    radial-gradient(circle at 15% 10%, rgba(198, 95, 45, 0.22), transparent 34rem),
                    radial-gradient(circle at 85% 0%, rgba(15, 107, 87, 0.18), transparent 32rem),
                    linear-gradient(135deg, #fbf7ef, #efe5d3);
                }
                header {
                  position: fixed;
                  top: 0;
                  left: 0;
                  right: 0;
                  z-index: 30;
                  min-height: 80px;
                  padding: 0.8rem clamp(1rem, 3vw, 2.2rem);
                  display: grid;
                  gap: 0.45rem;
                  align-items: center;
                  background:
                    radial-gradient(circle at 15% 10%, rgba(198, 95, 45, 0.22), transparent 34rem),
                    radial-gradient(circle at 85% 0%, rgba(15, 107, 87, 0.18), transparent 32rem),
                    linear-gradient(135deg, rgba(251, 247, 239, 0.96), rgba(239, 229, 211, 0.96));
                  border-bottom: 1px solid rgba(222, 212, 196, 0.7);
                  backdrop-filter: blur(10px);
                }
                body { padding-top: 80px; }
                .header-row {
                  display: grid;
                  grid-template-columns: minmax(0, 1fr) auto;
                  gap: 1rem;
                  align-items: center;
                }
                .top-actions {
                  display: flex;
                  flex-wrap: wrap;
                  justify-content: flex-end;
                  align-items: end;
                  gap: 0.5rem;
                  max-width: min(100%, 42rem);
                }
                .top-actions label {
                  min-width: 8rem;
                }
                .top-actions select {
                  min-width: 7rem;
                }
                .top-actions button {
                  width: auto;
                  min-width: 6.5rem;
                  white-space: nowrap;
                }
                h1 { margin: 0; font-size: clamp(1.55rem, 3vw, 2.2rem); letter-spacing: 0; line-height: 1; }
                h2 { margin: 0 0 1rem; font-size: 1.15rem; }
                p { color: var(--muted); }
                main {
                  display: grid;
                  grid-template-columns: minmax(0, 1fr);
                  gap: 1rem;
                  padding: 1rem clamp(1rem, 4vw, 4rem) 4rem;
                  width: 100%;
                  max-width: 100%;
                }
                main > *, .stack, section, aside { min-width: 0; }
                section, aside {
                  background: var(--panel);
                  border: 1px solid var(--line);
                  border-radius: 1.2rem;
                  box-shadow: 0 1.2rem 3rem rgba(57, 43, 24, 0.11);
                  padding: 1rem;
                }
                .stack { display: grid; gap: 1rem; align-content: start; }
                .stack > * { min-width: 0; }
                label { display: grid; gap: 0.35rem; color: var(--muted); font-size: 0.9rem; }
                input, textarea, select, button {
                  width: 100%;
                  border-radius: 0.75rem;
                  border: 1px solid var(--line);
                  padding: 0.75rem;
                  font: inherit;
                  background: #fffdf8;
                  color: var(--ink);
                }
                textarea { min-height: 5.5rem; resize: vertical; }
                button {
                  cursor: pointer;
                  border: 0;
                  color: #fff;
                  background: var(--accent);
                  font-weight: 700;
                }
                button.secondary { background: var(--accent-2); }
                button.ghost { background: transparent; color: var(--accent); border: 1px solid var(--accent); }
                button.danger-button { background: var(--danger); }
                button:disabled { cursor: not-allowed; opacity: 0.45; }
                label.field-invalid input,
                label.field-invalid textarea,
                label.field-invalid select {
                  border-color: var(--danger);
                  box-shadow: 0 0 0 0.16rem rgba(162, 52, 47, 0.16);
                }
                .field-error {
                  color: var(--danger);
                  border: 1px solid rgba(162, 52, 47, 0.35);
                  border-radius: 0.55rem;
                  background: #fff5f3;
                  padding: 0.4rem 0.55rem;
                  font-size: 0.86rem;
                }
                .form-error {
                  color: var(--danger);
                  border: 1px solid rgba(162, 52, 47, 0.45);
                  border-radius: 0.7rem;
                  background: #fff5f3;
                  padding: 0.7rem 0.8rem;
                }
                .grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; }
                .card-list { display: grid; gap: 0.6rem; }
                .card {
                  border: 1px solid var(--line);
                  border-radius: 0.9rem;
                  background: #fffdf8;
                  padding: 0.8rem;
                  min-width: 0;
                  overflow-wrap: anywhere;
                  word-break: break-word;
                }
                .card strong { display: block; }
                .muted { color: var(--muted); }
                .danger { color: var(--danger); }
                pre {
                  max-height: 28rem;
                  overflow: auto;
                  white-space: pre-wrap;
                  background: #1e2620;
                  color: #edf4ec;
                  border-radius: 0.9rem;
                  padding: 1rem;
                }
                .split-actions { display: grid; grid-template-columns: repeat(auto-fit, minmax(8rem, 1fr)); gap: 0.5rem; }
                .health-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr)); gap: 0.6rem; }
                .metric { border: 1px solid var(--line); border-radius: 0.8rem; background: #fffdf8; padding: 0.7rem; }
                .metric strong { display: block; font-size: 1.15rem; }
                .metric span, .metric strong { overflow-wrap: anywhere; word-break: break-word; }
                .chat-frame { overflow: visible; }
                .chat-scroll { min-height: 16rem; max-height: 24rem; overflow-y: auto; padding-right: 0.25rem; align-content: start; }
                .v2-chat-message { display: grid; gap: 0.2rem; max-width: min(100%, 46rem); white-space: pre-wrap; line-height: 1.5; overflow-wrap: anywhere; }
                .v2-chat-message-user { justify-self: end; width: fit-content; max-width: min(82%, 34rem); background: #eef0ec; border: 1px solid #d9ded8; border-radius: 0.85rem; padding: 0.55rem 0.72rem; color: var(--ink); }
                .v2-chat-message-assistant { justify-self: start; width: 100%; padding: 0.35rem 0.05rem; color: var(--ink); background: transparent; border: 0; box-shadow: none; }
                .v2-chat-message-assistant p { margin: 0.25rem 0 0.55rem; }
                .v2-chat-message-assistant h3,
                .v2-chat-message-assistant h4 { margin: 0.7rem 0 0.35rem; line-height: 1.25; letter-spacing: 0; }
                .v2-chat-message-assistant ul,
                .v2-chat-message-assistant ol { margin: 0.25rem 0 0.65rem; padding-left: 1.3rem; }
                .v2-chat-message-assistant li { margin: 0.16rem 0; }
                .v2-chat-message-assistant code { border: 1px solid var(--line); border-radius: 0.35rem; background: #f3ead9; padding: 0.08rem 0.28rem; font-family: Consolas, "Courier New", monospace; font-size: 0.9em; }
                .v2-chat-message-assistant pre { max-height: 18rem; margin: 0.45rem 0 0.7rem; overflow: auto; white-space: pre; background: #1e2620; color: #edf4ec; border-radius: 0.65rem; padding: 0.75rem; }
                .v2-chat-message-assistant pre code { border: 0; background: transparent; color: inherit; padding: 0; }
                .v2-chat-message-pending { color: var(--muted); }
                .v2-chat-pending-label { color: var(--muted); font-size: 0.78rem; }
                .feedback-scroll { max-height: 14rem; overflow-y: auto; padding-right: 0.25rem; }
                .status-ok { color: var(--accent); }
                .status-warn { color: var(--accent-2); }
                .status-fail { color: var(--danger); }
                .goal-card-current { border-color: var(--accent-2); box-shadow: inset 0 0 0 1px rgba(198, 95, 45, 0.18); }
                .goal-card-next { border-color: var(--accent); box-shadow: inset 0 0 0 1px rgba(15, 107, 87, 0.18); }
                .goal-badges { display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.35rem 0 0.5rem; }
                .goal-badge {
                  display: inline-flex;
                  align-items: center;
                  border-radius: 999px;
                  padding: 0.2rem 0.55rem;
                  font-size: 0.8rem;
                  font-weight: 700;
                  background: #f3ead9;
                  color: var(--ink);
                }
                .goal-badge-current { background: #fff0d9; color: var(--accent-2); }
                .goal-badge-next { background: #e6f4ef; color: var(--accent); }
                .goal-badge-succeeded { background: #e6f4ef; color: var(--accent); }
                .goal-badge-running { background: #fff0d9; color: var(--accent-2); }
                .goal-badge-pending { background: #f3ead9; color: var(--muted); }
                .goal-badge-failed { background: #f8e1df; color: var(--danger); }
                .goal-badge-needs-fix { background: #f8e1df; color: var(--danger); }
                .asset-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr)); gap: 0.6rem; }
                .asset-preview {
                  width: 100%;
                  height: 8rem;
                  object-fit: contain;
                  border: 1px solid var(--line);
                  border-radius: 0.75rem;
                  background: #f3ead9;
                }
                .asset-history {
                  display: flex;
                  flex-wrap: wrap;
                  gap: 0.55rem;
                  margin-top: 0.65rem;
                }
                .asset-history-item {
                  width: 6.25rem;
                  border: 1px solid var(--line);
                  border-radius: 0.5rem;
                  background: #fffdf8;
                  padding: 0.3rem;
                  color: var(--ink);
                  text-align: left;
                  cursor: pointer;
                }
                .asset-history-item.selected {
                  border-color: var(--accent);
                  box-shadow: inset 0 0 0 1px var(--accent);
                }
                .asset-history-number {
                  display: block;
                  font-size: 0.75rem;
                  font-weight: 800;
                  line-height: 1;
                  margin-bottom: 0.25rem;
                }
                .asset-history-thumb {
                  width: 90px;
                  height: 90px;
                  object-fit: contain;
                  border: 1px solid var(--line);
                  border-radius: 0.35rem;
                  background: #f3ead9;
                }
                .asset-history-time {
                  display: block;
                  margin-top: 0.25rem;
                  font-size: 0.7rem;
                  color: var(--muted);
                  line-height: 1.15;
                }
                .busy-banner {
                  position: fixed;
                  top: 0.75rem;
                  left: 50%;
                  z-index: 1200;
                  width: min(calc(100vw - 2rem), 72rem);
                  min-height: 2.75rem;
                  transform: translateX(-50%);
                  display: flex;
                  align-items: center;
                  justify-content: space-between;
                  gap: 0.75rem;
                  border: 1px solid var(--accent-2);
                  background: #fff8e6;
                  border-radius: 0.9rem;
                  box-shadow: 0 0.85rem 2.5rem rgba(57, 43, 24, 0.2);
                  padding: 0.7rem 1rem;
                  color: var(--ink);
                  font-weight: 700;
                  line-height: 1.35;
                  text-align: center;
                  max-height: min(7rem, calc(100vh - 1.5rem));
                  overflow-y: auto;
                  overflow-wrap: break-word;
                  word-break: normal;
                  pointer-events: auto;
                }
                .busy-banner > span { flex: 1 1 auto; min-width: 0; text-align: left; }
                .busy-banner button {
                  flex: 0 0 auto;
                  width: auto;
                  min-width: 4.5rem;
                  max-width: 8rem;
                  padding: 0.45rem 0.8rem;
                  white-space: nowrap;
                }
                .modal-backdrop {
                  position: fixed;
                  inset: 0;
                  z-index: 1000;
                  display: grid;
                  place-items: center;
                  padding: 1rem;
                  background: rgba(23, 33, 27, 0.45);
                }
                .modal-card {
                  width: min(42rem, 100%);
                  max-height: min(90vh, 54rem);
                  background: #fffdf8;
                  border: 1px solid var(--line);
                  border-radius: 1.2rem;
                  box-shadow: 0 2rem 5rem rgba(23, 33, 27, 0.28);
                  padding: 1rem;
                  display: grid;
                  gap: 0.8rem;
                  overflow: hidden;
                }
                .modal-card.modal-card-large { width: min(58rem, 100%); }
                .modal-card > .stack { min-height: 0; max-height: calc(min(90vh, 54rem) - 2rem); overflow-y: auto; overscroll-behavior: contain; padding-right: 0.25rem; }
                #iterationPlanUpdateModal .modal-card > .stack { max-height: calc(100vh - 4rem); }
                .modal-scroll { max-height: min(70vh, 42rem); overflow-y: auto; padding-right: 0.25rem; }
                .login-shell { max-width: 34rem; justify-self: center; width: 100%; }
                .token-box {
                  min-height: 7rem;
                  font-family: Consolas, "Courier New", monospace;
                  overflow-wrap: anywhere;
                  word-break: break-all;
                }
                .hidden { display: none !important; }
                @media (max-width: 920px) {
                  .header-row, main, .grid, .health-grid { grid-template-columns: 1fr; }
                  .top-actions { justify-content: stretch; }
                  .top-actions button, .top-actions label, .top-actions select { width: 100%; }
                }
              </style>
            </head>
            <body>
              <header>
                <div class="header-row">
                  <div>
                    <h1>Game Ren</h1>
                  </div>
                  <div id="userTopActions" class="top-actions hidden">
                    <label class="user-only-action"><select id="globalModel" aria-label="模型"><option value="gpt-5.5" selected>ChatGPT 5.5</option><option value="gpt-5.4">ChatGPT 5.4</option></select></label>
                    <button id="openCreateProjectPage" class="secondary user-only-action" data-global-action="true">创建项目</button>
                    <button id="openProjectListModal" class="ghost user-only-action">项目列表</button>
                    <button id="openAdminRunDurationMetrics" class="ghost admin-only-action hidden">普通用户Run耗时</button>
                    <button id="openAdminChatAverageMetrics" class="ghost admin-only-action hidden">聊天平均响应</button>
                    <button id="logout" class="danger-button">退出登录</button>
                  </div>
                </div>
                <div id="activeRunBanner" class="busy-banner hidden" role="status" aria-live="polite"></div>
              </header>
              <div id="oneTimeTokenModal" class="modal-backdrop hidden" role="dialog" aria-modal="true" aria-labelledby="oneTimeTokenTitle">
                <div class="modal-card">
                  <h2 id="oneTimeTokenTitle">One-time token</h2>
                  <p class="muted" id="oneTimeTokenMeta">Token plaintext is shown once. Save it now.</p>
                  <textarea id="oneTimeTokenValue" class="token-box" readonly></textarea>
                  <div class="split-actions">
                    <button id="copyOneTimeToken" class="secondary">Copy token</button>
                    <button id="closeOneTimeToken" class="ghost">Close</button>
                  </div>
                  <p id="oneTimeTokenCopyStatus" class="muted"></p>
                </div>
              </div>
              <div id="projectListModal" class="modal-backdrop hidden" role="dialog" aria-modal="true" aria-labelledby="projectListTitle">
                <div class="modal-card modal-card-large">
                  <section id="projectListPanel" class="stack">
                    <h2 id="projectListTitle">项目列表</h2>
                    <div class="split-actions">
                      <button id="refreshProjects" class="ghost">刷新项目列表</button>
                      <button id="closeProjectListModal" class="ghost">关闭</button>
                    </div>
                    <div id="projects" class="card-list modal-scroll"></div>
                  </section>
                </div>
              </div>
              <div id="iterationPlanUpdateModal" class="modal-backdrop hidden" role="dialog" aria-modal="true" aria-labelledby="iterationPlanUpdateTitle">
                <div class="modal-card modal-card-large">
                  <section class="stack">
                    <h2 id="iterationPlanUpdateTitle">重新生成游戏模块</h2>
                    <div id="iterationPlanUpdateEvaluation" class="card muted">尚未评估当前游戏模块。</div>
                    <label>补充要求
                      <textarea id="iterationPlanUpdateInput" rows="1" placeholder="输入本次更新游戏模块的补充要求。"></textarea>
                    </label>
                    <div class="split-actions">
                      <button id="confirmIterationPlanUpdate" class="secondary" data-global-action="true">更新游戏模块</button>
                      <button id="closeIterationPlanUpdateModal" class="ghost" type="button">关闭</button>
                    </div>
                    <p id="iterationPlanUpdateHint" class="muted"></p>
                  </section>
                </div>
              </div>
              <main>
                <section id="sessionPanel" class="stack login-shell">
                  <h2>会话</h2>
                  <label>Access token <input id="token" type="password" autocomplete="off" placeholder="Paste the server-issued token"></label>
                  <button id="saveToken">验证并进入</button>
                  <p id="sessionStatus" class="muted">Token 只保存在当前浏览器 localStorage，不会写入仓库。</p>
                </section>
                <section id="createProjectPanel" class="stack hidden">
                  <h2 id="createProjectTitle">创建项目</h2>
                  <label id="projectNameField">项目名 <input id="projectName" placeholder="可选，不填会自动生成"><span id="projectNameError" class="field-error hidden"></span></label>
                  <label id="gameNameField">游戏名 <input id="gameName" placeholder="例如：Demo Game"><span id="gameNameError" class="field-error hidden"></span></label>
                  <label id="gameTypeSourceField">游戏类型/玩法方向 <input id="gameTypeSource" placeholder="例如：RPG、塔防、Roguelike、平台跳跃、解谜冒险"><span id="gameTypeSourceError" class="field-error hidden"></span></label>
                  <p id="createProjectValidation" class="form-error hidden"></p>
                  <button id="createProject" data-global-action="true">创建项目</button>
                </section>
                <div id="llmBindingStatus" class="hidden"></div>
                <div id="llmUsageStatus" class="hidden"></div>
                <div id="adminPanel" class="stack hidden">
                  <section id="accountAdminPanel" class="stack hidden">
                    <h2>Account Admin</h2>
                    <label>Username <input id="newUsername" placeholder="phaseb-user"></label>
                    <label>Project limit <input id="newUserProjectLimit" type="number" min="1" value="2"></label>
                    <label>User valid days <input id="newUserValidDays" type="number" min="1" placeholder="blank = no expiry"></label>
                    <label>User spend limit CNY <input id="newUserSpendLimitCny" type="number" min="0" step="0.01" placeholder="blank = no limit"></label>
                    <button id="createUserAccount" class="secondary" data-global-action="true">Create user token</button>
                    <hr>
                    <h3>AiCodeMirror API Key Pool</h3>
                    <p class="muted">CSV columns: key_name, api_key, description, valid_days. The api_key column is required for real per-user Codex execution.</p>
                    <input id="aicodemirrorKeyCsv" type="file" accept=".csv,text/csv">
                    <button id="downloadAiCodeMirrorKeyTemplate" class="ghost">Download key CSV template</button>
                    <button id="importAiCodeMirrorKeyCsv" class="secondary" data-global-action="true">Import key CSV</button>
                    <button id="refreshAiCodeMirrorKeys" class="ghost">Refresh key pool</button>
                    <div id="aicodemirrorKeyImportResult" class="card muted">No key CSV imported.</div>
                    <div id="aicodemirrorKeyPool" class="card-list"></div>
                    <button id="refreshUserAccounts" class="ghost">Refresh users</button>
                    <button id="loadAdminLlmUsage" class="ghost">Load admin LLM usage</button>
                    <button id="downloadAdminLlmUsageCsv" class="ghost">Download admin LLM usage CSV</button>
                    <div class="split-actions">
                      <label>Cost grain <select id="adminLlmUsageGrain"><option value="day">Day</option><option value="month">Month</option><option value="hour">Hour</option></select></label>
                      <label>Cost split <select id="adminLlmUsageSplit"><option value="account">User</option><option value="project">Project</option><option value="account-project">User + Project</option></select></label>
                      <button id="loadAdminLlmUsageAggregate" class="ghost">Open cost aggregate page</button>
                    </div>
                    <button id="loadAdminLlmRuns" class="ghost">Load admin LLM run audit</button>
                    <div class="split-actions">
                      <label>Run user <select id="adminRunMetricsAccount"><option value="">All users</option></select></label>
                      <label>Run type <input id="adminRunMetricsType" placeholder="blank = all run types"></label>
                      <button id="loadAdminRunMetrics" class="ghost">Load run metrics</button>
                    </div>
                    <button id="loadAccountAudit" class="ghost">Load account audit</button>
                    <button id="downloadAccountAuditCsv" class="ghost">Download account audit CSV</button>
                    <div id="createUserAccountResult" class="card muted">Admin only. The token is shown once after creation.</div>
                    <div id="userAccounts" class="card-list"></div>
                    <div id="adminLlmUsageStatus" class="card muted">No admin LLM usage loaded.</div>
                    <div id="adminLlmRunsStatus" class="card muted">No admin LLM run audit loaded.</div>
                    <div id="adminRunMetricsStatus" class="card muted">No run metrics loaded.</div>
                    <div id="accountAuditStatus" class="card muted">No account audit loaded.</div>
                  </section>
                  <section id="initStatusPanel" class="stack hidden">
                    <h2>项目初始化</h2>
                    <p id="initStatusText" class="muted">项目初始化配置中...请稍等 2-5 分钟后刷新页面。</p>
                  </section>
                  <section id="projectDetailPanel" class="stack hidden">
                  <section id="currentProjectPanel" class="stack">
                    <h2>当前项目</h2>
                    <p id="selectedProject" class="muted">尚未选择项目。</p>
                    <button id="loadRuns" class="ghost hidden">加载运行记录</button>
                    <button id="refreshPrototypeProgress" class="ghost">刷新原型进度</button>
                    <button id="validatePrototype" class="ghost" data-global-action="true">重新验收原型</button>
                    <button id="createProjectPackage" class="secondary" data-global-action="true" disabled>打包项目文件</button>
                    <button id="openProjectDownloads" class="ghost" disabled>打开项目文件下载页</button>
                    <button id="loadAssetInventory" class="ghost" disabled>查看素材清单</button>
                    <div id="prototypeProgress" class="card muted">尚未开始原型骨架创建。</div>
                    <div id="prototypeAcceptanceSummary" class="card muted">原型完成后，这里会显示默认场景、验证摘要数量和建议试玩重点。</div>
                    <div id="projectHealthSummary" class="card muted">选择项目后显示项目健康摘要。</div>
                    <div id="projectPackageStatus" class="card muted">尚未生成项目压缩包。</div>
                    <div id="assetInventoryStatus" class="card muted">final step 完成后可查看项目素材清单。</div>
                  </section>
                  <section id="prototypeWorkflowPanel" class="stack">
                    <h2>原型骨架创建</h2>
                    <div class="prototype-draft-row">
                      <label>导入原型草稿 TXT <input id="draftFile" type="file" accept=".txt,text/plain"></label>
                      <button id="importDraft" class="ghost import-draft-button" data-global-action="true" disabled>分析草稿并回填</button>
                    </div>
                    <div id="draftImportStatus" class="card muted hidden"></div>
                    <label>游戏原型ID <input id="protoSlug" placeholder="demo-prototype"></label>
                    <label>原型假设 <textarea id="hypothesis" placeholder="这个原型要验证什么？"></textarea></label>
                    <label>核心玩家幻想 <textarea id="corePlayerFantasy" placeholder="玩家应该感受到什么？"></textarea></label>
                    <label>最小可玩循环 <textarea id="minimumPlayableLoop" placeholder="玩家反复执行的最小闭环是什么？"></textarea></label>
                    <label>成功标准，每行一条 <textarea id="successCriteria" placeholder="例如：30 秒内能理解目标"></textarea></label>
                    <label>游戏功能 <textarea id="gameFeature" placeholder="本次要实现或验证的核心功能"></textarea></label>
                    <label>核心玩法循环 <textarea id="coreGameplayLoop" placeholder="输入、反馈、奖励、升级或失败的循环"></textarea></label>
                    <label>胜利/失败条件 <textarea id="winFailConditions" placeholder="如何判定玩家成功或失败"></textarea></label>
                    <button id="runPrototype" class="secondary" data-global-action="true">运行原型骨架创建</button>
                  </section>
                  <section id="prototypeCommandPanel" class="stack hidden">
                    <h2>原型命令</h2>
                    <div class="grid">
                      <label>TDD 原型标识 <input id="tddSlug" placeholder="demo-prototype"></label>
                      <label>Godot 场景根节点 <input id="sceneRoot" value="Node2D"></label>
                    </div>
                    <label>.NET 测试目标，每行一个 <textarea id="dotnetTarget">Game.Core.Tests/Game.Core.Tests.csproj</textarea></label>
                    <label>可选测试过滤器 <input id="testFilter" placeholder="可选"></label>
                    <div class="split-actions">
                      <button data-stage="red" class="runTdd" data-global-action="true">TDD 红灯</button>
                      <button data-stage="green" class="runTdd" data-global-action="true">TDD 绿灯</button>
                      <button data-stage="refactor" class="runTdd" data-global-action="true">TDD 重构</button>
                    </div>
                    <button id="createScene" class="ghost" data-global-action="true">创建原型场景</button>
                  </section>
                  <section id="chatPanel" class="stack hidden chat-frame">
                    <h2>自由对话</h2>
                    <p class="muted">选择项目后即可聊天。后端会映射到服务器本机 Codex CLI 配置；需要执行工作流时仍使用上方固定按钮。</p>
                    <label>能力模式 <select id="chatSkillMode"><option value="normal">普通模式</option></select></label>
                    <div id="chatSkillDescription" class="card muted">普通模式：不激活 skills。</div>
                    <h2>主流程：游戏模块</h2>
                    <p class="muted">推荐流程：先把较大的优化目标拆成 3-7 个小目标，再逐个执行。每次只推进一个目标，完成后停下，由你决定是否继续。</p>
                    <button id="createIterationPlan" class="ghost" data-global-action="true">生成游戏模块</button>
                    <button id="evaluateIterationPlan" class="ghost" data-global-action="true">评估当前游戏模块</button>
                    <button id="deleteIterationPlan" class="ghost" data-global-action="true">删除当前轮游戏模块</button>
                    <button id="executeIterationGoal" class="secondary" data-global-action="true">执行下一目标</button>
                    <p id="iterationAutoRefreshHint" class="muted">执行中会自动刷新进度，你可以停留在当前页面直接查看状态变化。</p>
                    <div id="iterationPlanStatus" class="card muted">尚未生成游戏模块。</div>
                    <div id="iterationPlanEvaluation" class="card muted">尚未评估当前游戏模块。</div>
                    <div id="iterationNeedsFixStatus" class="card muted">step 进入 needs fix 后，可在对应 step 卡片里启动 Needs Fix 路由。</div>
                    <div id="iterationPlanGoals" class="card-list"></div>
                    <h2>异常修复计划</h2>
                    <p class="muted">用于把原型或验收失败拆成多个小修复步骤。每次只执行一个修复步骤，最后一步做全量验收。</p>
                    <button id="createRepairPlan" class="ghost" data-global-action="true">生成修复计划</button>
                    <button id="executeRepairStep" class="secondary" data-global-action="true">执行下一项修复</button>
                    <div id="repairPlanStatus" class="card muted">尚未生成修复计划。</div>
                    <div id="repairPlanGoals" class="card-list"></div>
                    <h2>聊天记录</h2>
                    <button id="syncChatHistory" class="ghost">同步记录</button>
                    <button id="downloadChatHistory" class="ghost">下载记录</button>
                    <div id="chatHistory" class="card-list chat-scroll"></div>
                    <label>消息 <textarea id="chatMessage" placeholder="例如：帮我把这个原型想法拆成最小可玩循环"></textarea></label>
                    <label>+ <input id="chatAttachmentFiles" type="file" accept=".txt,text/plain" multiple></label>
                    <div id="chatAttachmentStatus" class="card muted">未导入 TXT 参考文件，只支持 TXT 文件导入。</div>
                    <button id="clearChatAttachments" class="ghost hidden">清空参考文件</button>
                    <button id="createGddDocument" class="ghost" data-global-action="true">&#21019;&#24314;&#31574;&#21010;&#22823;&#32434;</button>
                    <button id="sendChat" class="secondary">发送</button>
                    <button id="evaluateIterationPlanFromChat" class="ghost" data-global-action="true">评估当前计划是否值得继续</button>
                    <button id="submitFormalFeedback" class="ghost" data-global-action="true">提交反馈到 Needs Fix 路由</button>
                    <h2>流程记录</h2>
                    <div id="feedbackSummary" class="card muted">尚未生成游戏模块。</div>
                    <div id="feedbackRecords" class="card-list feedback-scroll"></div>
                  </section>
                  <section id="runsPanel" class="hidden">
                    <h2>运行记录</h2>
                    <div id="runs" class="card-list"></div>
                  </section>
                  <section id="outputPanel" class="hidden">
                    <h2>输出</h2>
                    <pre id="output">就绪。</pre>
                  </section>
                  </section>
                </div>
              </main>
              <script>
                const state = { projectId: "", projects: [], runs: [], packageList: null, assetInventory: null, assetInventoryExpanded: false, chatHistory: [], chatAttachments: [], skillActions: [], authenticated: false, prototypeReadyForFeedback: false, activeRun: null, localBusy: false, nextSuggestedFeedback: "", draftAnalysisRunning: false, prototypeFailure: "", v2PrototypeStatus: "", v2PrototypeCreationStatus: "", iterationPlan: null, iterationPlans: [], selectedIterationSessionId: "", iterationPlanEvaluation: null, iterationPlanFailure: "", iterationPlanUpdateMode: "update", iterationPlanEvaluationRunning: false, gddOutlineReady: false, workflowRouteActionToken: "", workflowRouteActionConsumed: false, projectAnalysisMode: false };
                const prototypeInputIds = ["protoSlug", "hypothesis", "corePlayerFantasy", "minimumPlayableLoop", "successCriteria", "gameFeature", "coreGameplayLoop", "winFailConditions"];
                const projectStateCacheVersion = 2;
                const chatStorageVersion = "v2";
                const maxStoredChatMessages = 30;
                const chatThinkingPrompts = [
                  "正在理解你的问题...",
                  "正在结合当前项目上下文...",
                  "Codex CLI 正在生成回复...",
                  "正在整理可读答案...",
                  "还在处理中，请稍等..."
                ];
                const $ = id => document.getElementById(id);
                const out = value => $("output").textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
                function storedAccessToken() {
                  return localStorage.getItem("phaseAAccessToken") || readBrowserCookie("phaseAAccessToken") || localStorage.getItem("phaseAAdminToken") || "";
                }
                function token() {
                  const inputValue = $("token").value.trim();
                  if (inputValue) return inputValue;
                  const stored = storedAccessToken();
                  if (stored) {
                    $("token").value = stored;
                    if (!localStorage.getItem("phaseAAccessToken")) localStorage.setItem("phaseAAccessToken", stored);
                    if (!readBrowserCookie("phaseAAccessToken")) writeBrowserCookie("phaseAAccessToken", stored, 60 * 60 * 24 * 30);
                  }
                  return stored;
                }
                function headers() {
                  const currentToken = token();
                  return currentToken
                    ? { "Authorization": `Bearer ${currentToken}`, "Content-Type": "application/json" }
                    : { "Content-Type": "application/json" };
                }

                function setModalVisible(id, visible) {
                  $(id).classList.toggle("hidden", !visible);
                }

                function closeUserModals() {
                  setModalVisible("projectListModal", false);
                }

                function setUserTopActionsVisible(visible, logoutOnly = false) {
                  $("userTopActions").classList.toggle("hidden", !visible);
                  document.querySelectorAll("#userTopActions .user-only-action").forEach(element => {
                    element.classList.toggle("hidden", logoutOnly);
                  });
                  document.querySelectorAll("#userTopActions .admin-only-action").forEach(element => {
                    element.classList.toggle("hidden", !logoutOnly);
                  });
                }

                function showCreateProjectPage() {
                  closeUserModals();
                  $("sessionPanel").classList.add("hidden");
                  $("adminPanel").classList.add("hidden");
                  $("projectDetailPanel").classList.add("hidden");
                  $("chatPanel").classList.add("hidden");
                  $("createProjectPanel").classList.remove("hidden");
                }

                function hideCreateProjectPage() {
                  $("createProjectPanel").classList.add("hidden");
                }

                function setTokenFromStorage() {
                  $("token").value = storedAccessToken();
                }
                function readBrowserCookie(name) {
                  const prefix = `${encodeURIComponent(name)}=`;
                  return document.cookie
                    .split(";")
                    .map(part => part.trim())
                    .filter(Boolean)
                    .map(part => part.startsWith(prefix) ? decodeURIComponent(part.slice(prefix.length)) : "")
                    .find(Boolean) || "";
                }
                function writeBrowserCookie(name, value, maxAgeSeconds) {
                  const secure = location.protocol === "https:" ? "; Secure" : "";
                  document.cookie = `${encodeURIComponent(name)}=${encodeURIComponent(value || "")}; Max-Age=${Number(maxAgeSeconds) || 0}; Path=/; SameSite=Lax${secure}`;
                }
                function clearBrowserCookie(name) {
                  writeBrowserCookie(name, "", 0);
                }
                function persistAccessTokenFromInput() {
                  const value = token();
                  if (!value) return;
                  localStorage.setItem("phaseAAccessToken", value);
                  localStorage.removeItem("phaseAAdminToken");
                  writeBrowserCookie("phaseAAccessToken", value, 60 * 60 * 24 * 30);
                }

                function callV2(name, ...args) {
                  const fn = globalThis[name];
                  return typeof fn === "function" ? fn(...args) : undefined;
                }

                function renderChatHistory() {
                  applyChatWorkflowActions();
                  state.chatHistory.forEach(message => {
                    if (typeof message.content === "string") message.content = sanitizePublicChatContent(message.content);
                  });
                  const visibleMessages = state.chatHistory.filter(isVisibleChatMessage);
                  $("chatHistory").innerHTML = visibleMessages.map((message, index) => {
                    const roleClass = message.role === "user" ? "v2-chat-message-user" : "v2-chat-message-assistant";
                    const pendingClass = message.pending ? " v2-chat-message-pending" : "";
                    const pendingLabel = message.pending ? "<span class=\"v2-chat-pending-label\">生成中</span>" : "";
                    const contentHtml = message.role === "user"
                      ? `<span>${escapeHtml(message.content)}</span>`
                      : renderAssistantChatContent(message.content, message);
                    return `
                      <div class="v2-chat-message ${roleClass}${pendingClass}">
                        ${pendingLabel}
                        ${contentHtml}
                      </div>
                    `;
                  }).join("") || "<p class='muted'>还没有对话。</p>";
                  requestAnimationFrame(() => {
                    const history = $("chatHistory");
                    if (history) history.scrollTop = history.scrollHeight;
                  });
                  document.querySelectorAll(".v2-open-gdd-outline").forEach(button => {
                    button.onclick = () => callV2("v2OpenGddOutlineTab");
                  });
                  document.querySelectorAll("[data-workflow-route-action-token]").forEach(button => {
                    button.onclick = () => runWorkflowRecommendedAction(button.dataset.workflowRouteActionToken, button.dataset.workflowRouteActionId || "");
                  });
                }

                function renderAssistantChatContent(content, message = null) {
                  const lines = String(content || "").replace(/\r/g, "").split("\n");
                  const parts = [];
                  let paragraph = [];
                  let listItems = [];
                  let listType = "";
                  let codeLines = [];
                  let inCode = false;

                  const flushParagraph = () => {
                    if (!paragraph.length) return;
                    parts.push(`<p>${renderInlineMarkdown(paragraph.join(" "))}</p>`);
                    paragraph = [];
                  };
                  const flushList = () => {
                    if (!listItems.length) return;
                    const tag = listType === "ol" ? "ol" : "ul";
                    parts.push(`<${tag}>${listItems.map(item => `<li>${renderInlineMarkdown(item)}</li>`).join("")}</${tag}>`);
                    listItems = [];
                    listType = "";
                  };
                  const flushCode = () => {
                    parts.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
                    codeLines = [];
                  };

                  for (const rawLine of lines) {
                    const line = rawLine.trimEnd();
                    if (line.trim().startsWith("```")) {
                      if (inCode) {
                        flushCode();
                        inCode = false;
                      } else {
                        flushParagraph();
                        flushList();
                        inCode = true;
                        codeLines = [];
                      }
                      continue;
                    }
                    if (inCode) {
                      codeLines.push(rawLine);
                      continue;
                    }
                    if (!line.trim()) {
                      flushParagraph();
                      flushList();
                      continue;
                    }
                    const heading = line.match(/^(#{1,3})\s+(.+)$/);
                    if (heading) {
                      flushParagraph();
                      flushList();
                      const tag = heading[1].length === 1 ? "h3" : "h4";
                      parts.push(`<${tag}>${renderInlineMarkdown(heading[2])}</${tag}>`);
                      continue;
                    }
                    const bullet = line.match(/^[-*]\s+(.+)$/);
                    if (bullet) {
                      flushParagraph();
                      if (listType && listType !== "ul") flushList();
                      listType = "ul";
                      listItems.push(bullet[1]);
                      continue;
                    }
                    const ordered = line.match(/^\d+[\.)]\s+(.+)$/);
                    if (ordered) {
                      flushParagraph();
                      if (listType && listType !== "ol") flushList();
                      listType = "ol";
                      listItems.push(ordered[1]);
                      continue;
                    }
                    paragraph.push(line.trim());
                  }

                  if (inCode) flushCode();
                  flushParagraph();
                  flushList();
                  const outlineButton = message?.gddOutlineUrl
                    ? `<p><button class="secondary v2-open-gdd-outline" type="button">&#26597;&#38405;&#31574;&#21010;&#22823;&#32434;</button></p>`
                    : "";
                  return (parts.join("") || "<p></p>") + outlineButton + renderWorkflowRouteAction(message);
                }

                function renderWorkflowRouteAction(message) {
                  const actions = workflowMessageActions(message);
                  if (!actions.length) return "";
                  const consumed = !!message.workflowActionConsumed || state.workflowRouteActionToken !== message.workflowActionToken;
                  return `
                    <div class="v2-workflow-action-row">
                      ${actions.map(action => {
                        const label = consumed ? "进度已变更" : (action.buttonLabel || action.runName || action.label || "执行下一步");
                        return `<button type="button" class="secondary v2-workflow-route-action" data-workflow-route-action-token="${escapeHtml(message.workflowActionToken || "")}" data-workflow-route-action-id="${escapeHtml(action.actionId || "")}" ${consumed ? "disabled" : ""}>${escapeHtml(label)}</button>`;
                      }).join("")}
                    </div>
                  `;
                }

                function renderInlineMarkdown(value) {
                  let html = escapeHtml(value || "");
                  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
                  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
                  html = html.replace(/(https?:\/\/[^\s<]+|\/projects\/[^\s<]+\/gdd\/GDD\.md\?ticket=[^\s<]+)/g, match => `<a href="${match}" target="_blank" rel="noopener" download="GDD.md">${match.includes("/gdd/GDD.md") ? "下载 GDD.md" : match}</a>`);
                  return html;
                }

                function applyChatWorkflowActions() {
                  const goals = Array.isArray(state.iterationPlan?.goals) ? state.iterationPlan.goals : [];
                  const shouldOfferPlanEvaluation = goals.some(goal => goal.status === "pending" || goal.status === "needs_fix");
                  let latestGoalResultIndex = -1;
                  for (let index = state.chatHistory.length - 1; index >= 0; index--) {
                    const message = state.chatHistory[index];
                    if (message?.role === "assistant" && (message.kind === "iteration-goal-result" || message.kind === "iteration-goal-failed")) {
                      latestGoalResultIndex = index;
                      break;
                    }
                  }

                  state.chatHistory.forEach((message, index) => {
                    if (message?.role !== "assistant" || message.pending) return;
                    if (message.kind === "iteration-goal-result" || message.kind === "iteration-goal-failed") {
                      if (message.continueConsumed || index !== latestGoalResultIndex || !shouldOfferPlanEvaluation) {
                        if (message.suggestedFeedback === "__iteration_plan_evaluate__") {
                          message.suggestedFeedback = "";
                        }
                        return;
                      }
                      message.suggestedFeedback = "__iteration_plan_evaluate__";
                    }
                  });
                }

                function chatStorageKey(projectId = state.projectId) {
                  return `phaseAChatHistory:${chatStorageVersion}:${projectId || "none"}`;
                }

                function loadChatHistoryForProject(projectId) {
                  try {
                    const raw = localStorage.getItem(chatStorageKey(projectId));
                    const parsed = raw ? JSON.parse(raw) : [];
                    state.chatHistory = Array.isArray(parsed)
                      ? parsed.filter(isStoredChatMessage).slice(-maxStoredChatMessages)
                      : [];
                    state.chatHistory.forEach(message => message.content = sanitizePublicChatContent(message.content));
                  } catch {
                    state.chatHistory = [];
                  }
                  restoreWorkflowRouteActionFromHistory();
                  renderChatHistory();
                }

                async function loadServerChatHistoryForProject(projectId) {
                  if (!projectId) return;
                  try {
                    const localWorkflowRouteEntries = state.chatHistory
                      .map((message, index) => ({ message, previousKey: previousStoredMessageKey(index), nextKey: nextStoredMessageKey(index) }))
                      .filter(entry => entry.message?.kind === "workflow-route");
                    const result = await api(`/api/projects/${projectId}/chat-history`);
                    const serverMessages = (result.messages || [])
                      .map(message => ({
                        role: message.role,
                        content: sanitizePublicChatContent(message.content),
                        kind: message.kind || null,
                        continueConsumed: !!message.continueConsumed,
                        suggestedFeedback: sanitizePublicChatContent(message.suggestedFeedback || ""),
                        workflowAction: message.workflowAction || null,
                        workflowActions: message.workflowActions || null,
                        workflowActionToken: message.workflowActionToken || "",
                        workflowActionConsumed: !!message.workflowActionConsumed,
                        workflowRoute: message.workflowRoute || null,
                        workflowIntent: message.workflowIntent || null
                      }))
                      .filter(isStoredChatMessage)
                      .slice(-maxStoredChatMessages);
                    state.chatHistory = mergeLocalWorkflowRouteMessages(serverMessages, localWorkflowRouteEntries)
                      .slice(-maxStoredChatMessages);
                    restoreWorkflowRouteActionFromHistory();
                    renderChatHistory();
                    saveChatHistoryForProject();
                    updateContinueSuggestionFromText(state.chatHistory.filter(message => message.role === "assistant").slice(-1)[0]?.content || "");
                  } catch {
                    renderChatHistory();
                  }
                }

                async function loadIterationPlan() {
                  if (!state.projectId) {
                    state.iterationPlan = null;
                    state.iterationPlans = [];
                    state.selectedIterationSessionId = "";
                    state.iterationPlanEvaluation = null;
                    renderIterationPlan();
                    return;
                  }
                  try {
                    const result = await api(`/api/projects/${state.projectId}/iteration-plans`);
                    state.iterationPlans = normalizeIterationPlanRounds(Array.isArray(result?.rounds) ? result.rounds : []);
                    state.iterationPlan = selectIterationPlanForDisplay(state.iterationPlans);
                    state.iterationPlanEvaluation = state.iterationPlan?.latestEvaluation || null;
                    state.iterationPlanFailure = "";
                    syncIterationPlanRegenerationSuggestion();
                    writeProjectStateCache({ iterationPlan: state.iterationPlan, iterationPlans: state.iterationPlans, selectedIterationSessionId: state.selectedIterationSessionId, iterationPlanEvaluation: state.iterationPlanEvaluation, iterationPlanFailure: "" });
                  } catch (error) {
                    if (error?.status === 404) {
                      state.iterationPlan = null;
                      state.iterationPlans = [];
                      state.selectedIterationSessionId = "";
                      state.iterationPlanEvaluation = null;
                      state.iterationPlanFailure = "";
                      writeProjectStateCache({ iterationPlan: null, iterationPlans: [], selectedIterationSessionId: "", iterationPlanEvaluation: null, iterationPlanFailure: "" });
                    } else {
                      showError(error);
                    }
                  }
                  renderIterationPlan();
                  await loadProjectPackages();
                }

                function selectIterationPlanForDisplay(rounds) {
                  const plans = Array.isArray(rounds) ? rounds : [];
                  if (!plans.length) {
                    state.selectedIterationSessionId = "";
                    return null;
                  }
                  const selected = state.selectedIterationSessionId
                    ? plans.find(plan => plan?.session?.sessionId === state.selectedIterationSessionId)
                    : null;
                  const plan = selected || plans[plans.length - 1];
                  state.selectedIterationSessionId = plan?.session?.sessionId || "";
                  return plan || null;
                }

                function normalizeIterationPlanRounds(rounds) {
                  const plans = Array.isArray(rounds) ? rounds.filter(Boolean) : [];
                  if (plans.length <= 1) return plans;
                  const timestamp = plan => Date.parse(plan?.session?.createdUtc || plan?.session?.updatedUtc || "") || 0;
                  const isNewRound = plan => String(plan?.session?.sourceKind || "").toLowerCase() === "new_iteration_plan";
                  const baseRound = plans
                    .filter(plan => !isNewRound(plan))
                    .sort((a, b) => timestamp(b) - timestamp(a))[0] || null;
                  const realNewRounds = plans
                    .filter(isNewRound)
                    .sort((a, b) => timestamp(a) - timestamp(b));
                  return baseRound ? [baseRound, ...realNewRounds] : realNewRounds;
                }

                function isDisplayingLatestIterationPlan() {
                  const plans = Array.isArray(state.iterationPlans) ? state.iterationPlans : [];
                  if (!plans.length || !state.iterationPlan?.session) return true;
                  return plans[plans.length - 1]?.session?.sessionId === state.iterationPlan.session.sessionId;
                }

                async function loadRepairPlan() {
                  if (!state.projectId) {
                    state.repairPlan = null;
                    renderRepairPlan();
                    return;
                  }
                  try {
                    state.repairPlan = await api(`/api/projects/${state.projectId}/repair-plan/latest`);
                    writeProjectStateCache({ repairPlan: state.repairPlan });
                  } catch (error) {
                    if (error?.status === 404) {
                      state.repairPlan = null;
                      writeProjectStateCache({ repairPlan: null });
                    } else {
                      showError(error);
                    }
                  }
                  renderRepairPlan();
                }

                function renderRepairPlan() {
                  const plan = state.repairPlan;
                  if (!plan || !plan.sessionId) {
                    $("repairPlanStatus").className = "card muted";
                    $("repairPlanStatus").textContent = "尚未生成修复计划。";
                    $("repairPlanGoals").innerHTML = "";
                    $("createRepairPlan").disabled = isGlobalBusy();
                    $("executeRepairStep").disabled = true;
                    $("executeRepairStep").textContent = "请先生成修复计划";
                    $("v2SkeletonAcceptance")?.classList.remove("hidden");
                    return;
                  }
                  const goals = Array.isArray(plan.goals) ? plan.goals : [];
                  const hasRunnable = goals.some(goal => ["pending", "needs_fix", "failed"].includes(String(goal.status || "").trim().toLowerCase()));
                  $("repairPlanStatus").className = "card";
                  $("repairPlanStatus").innerHTML = `
                    <strong>${escapeHtml(plan.status || "ready")}</strong>
                    <p>${escapeHtml(plan.summary || "")}</p>
                    <p class="muted">修复计划 ID：${escapeHtml(plan.sessionId || "")}</p>
                  `;
                  $("createRepairPlan").disabled = isGlobalBusy();
                  $("executeRepairStep").disabled = !hasRunnable || isGlobalBusy();
                  $("executeRepairStep").textContent = hasRunnable ? "执行下一项修复" : "修复计划已无待执行步骤";
                  $("v2SkeletonAcceptance")?.classList.toggle("hidden", hasRunnable);
                  $("repairPlanGoals").innerHTML = goals.map(goal => `
                    <div class="card">
                      <strong>repair-step${String(goal.goalIndex || 0).padStart(2, "0")} · ${escapeHtml(goal.status || "pending")}</strong>
                      <p>${escapeHtml(goal.title || "")}</p>
                      <p class="muted">${escapeHtml(repairGoalDisplayText(goal.description || ""))}</p>
                      ${goal.acceptanceHint ? `<p class="muted">验收：${escapeHtml(goal.acceptanceHint)}</p>` : ""}
                      ${goal.resultSummary ? `<p class="muted">结果：${escapeHtml(publicIterationGoalResultSummary(goal))}</p>` : ""}
                    </div>`).join("");
                }

                function repairGoalDisplayText(description) {
                  const text = String(description || "").replace(/\r/g, "").trim();
                  const evidenceMarkers = [
                    "\nLatest failure evidence:",
                    "\nFailure evidence:",
                    "\nPrototype contract:",
                    "\nRPG GdUnit validation context:"
                  ];
                  let end = text.length;
                  evidenceMarkers.forEach(marker => {
                    const index = text.indexOf(marker);
                    if (index >= 0) end = Math.min(end, index);
                  });
                  const concise = text.slice(0, end).trim() || text;
                  return concise.length > 900 ? `${concise.slice(0, 900).trim()}...` : concise;
                }

                function focusRepairPlanPanel() {
                  $("chatPanel").classList.remove("hidden");
                  $("repairPlanStatus").scrollIntoView({ behavior: "smooth", block: "center" });
                }

                function renderIterationRoundTabs() {
                  const tabs = $("v2IterationRoundTabs");
                  if (!tabs) return;
                  const plans = Array.isArray(state.iterationPlans) ? state.iterationPlans : [];
                  if (plans.length <= 1) {
                    tabs.classList.add("hidden");
                    tabs.innerHTML = "";
                    return;
                  }
                  tabs.classList.remove("hidden");
                  tabs.innerHTML = plans.map((plan, index) => {
                    const sessionId = plan?.session?.sessionId || "";
                    const active = sessionId && state.iterationPlan?.session?.sessionId === sessionId;
                    const label = `第 ${Number(plan?.roundIndex || index + 1)} 轮`;
                    return `<button type="button" class="v2-round-tab ${active ? "active" : ""}" data-iteration-session-id="${escapeHtml(sessionId)}">${escapeHtml(label)}</button>`;
                  }).join("");
                  tabs.querySelectorAll("[data-iteration-session-id]").forEach(button => {
                    button.onclick = () => {
                      const sessionId = button.dataset.iterationSessionId || "";
                      const plan = plans.find(item => item?.session?.sessionId === sessionId) || null;
                      if (!plan) return;
                      state.selectedIterationSessionId = sessionId;
                      state.iterationPlan = plan;
                      state.iterationPlanEvaluation = plan.latestEvaluation || null;
                      writeProjectStateCache({ iterationPlan: state.iterationPlan, iterationPlans: state.iterationPlans, selectedIterationSessionId: state.selectedIterationSessionId, iterationPlanEvaluation: state.iterationPlanEvaluation });
                      renderIterationPlan();
                    };
                  });
                }

                function renderIterationPlan() {
                  renderIterationRoundTabs();
                  const plan = state.iterationPlan;
                  if (!plan || !plan.session) {
                    $("v2IterationSummary").className = state.iterationPlanFailure ? "card" : "card muted";
                    $("v2IterationSummary").innerHTML = state.iterationPlanFailure
                      ? `<strong>游戏模块摘要</strong><p>${escapeHtml(state.iterationPlanFailure)}</p>`
                      : "尚未生成游戏模块。";
                    $("iterationPlanStatus").className = state.iterationPlanFailure ? "card" : "card muted";
                    const customRouteRequired = state.iterationPlanFailure && state.iterationPlanFailure.includes("联系管理员创建定制游戏类型路线");
                    $("iterationPlanStatus").innerHTML = state.iterationPlanFailure
                      ? `<strong>${customRouteRequired ? "需要定制路线" : "游戏模块生成失败"}</strong><p>${escapeHtml(state.iterationPlanFailure)}</p>`
                      : "尚未生成游戏模块。";
                  $("iterationPlanEvaluation").className = "card muted";
                  $("iterationPlanEvaluation").textContent = "尚未评估当前游戏模块。";
                  $("iterationNeedsFixStatus").className = "card muted";
                  $("iterationNeedsFixStatus").textContent = "step 进入 needs fix 后，可在对应 step 卡片里启动 Needs Fix 路由。";
                  $("iterationPlanGoals").innerHTML = "";
                    $("createIterationPlan").disabled = isGlobalBusy();
                    $("createIterationPlan").textContent = "生成新的游戏模块";
                    $("deleteIterationPlan").classList.add("hidden");
                    $("deleteIterationPlan").disabled = true;
                    $("evaluateIterationPlan").disabled = true;
                    $("evaluateIterationPlan").textContent = "请先生成游戏模块";
                    $("evaluateIterationPlanFromChat").disabled = true;
                    $("evaluateIterationPlanFromChat").textContent = "请先生成游戏模块";
                    $("executeIterationGoal").disabled = true;
                    $("executeIterationGoal").textContent = "请先生成游戏模块";
                    return;
                  }
                  const session = plan.session;
                  const goals = Array.isArray(plan.goals) ? plan.goals : [];
                  const planningAnalysis = plan.planningAnalysis || null;
                  const hasNeedsFix = goals.some(goal => goal.status === "needs_fix");
                  const hasPending = goals.some(goal => goal.status === "pending");
                  const evaluationDecision = currentIterationPlanDecision();
                  const shouldRefinePlan = evaluationDecision === "should_refine_plan";
                  const blockedByCurrentGoal = evaluationDecision === "blocked_by_current_goal" || evaluationDecision === "llm_failed";
                  const planComplete = isIterationPlanComplete();
                  const planStarted = isIterationPlanStarted();
                  const isLatestPlan = isDisplayingLatestIterationPlan();
                  const canUpdatePlan = !planStarted;
                  $("v2IterationSummary").className = "card";
                  $("v2IterationSummary").innerHTML = `
                    <strong>游戏模块摘要</strong>
                    ${state.iterationPlanFailure ? `<p class="danger">${escapeHtml(state.iterationPlanFailure)}</p>` : ""}
                    <p>${escapeHtml(session.overallGoal || "")}</p>
                    ${session.latestSummary ? `<p class="muted">${escapeHtml(session.latestSummary)}</p>` : ""}
                    ${planningAnalysis ? `<p class="muted">生成依据：${escapeHtml(planningAnalysis.analysisSummary || "")}</p>` : ""}
                  `;
                  $("iterationPlanStatus").className = "card";
                  $("iterationPlanStatus").innerHTML = `
                    <strong>${escapeHtml(session.status || "ready")}</strong>
                    ${state.iterationPlanFailure ? `<p class="danger">${escapeHtml(state.iterationPlanFailure)}</p>` : ""}
                    <p>${escapeHtml(session.overallGoal || "")}</p>
                    ${session.latestSummary ? `<p class="muted">${escapeHtml(session.latestSummary)}</p>` : ""}
                    <p class="muted">当前目标序号：${escapeHtml(String(session.currentGoalIndex || 0))}</p>
                    ${planningAnalysis ? `<p class="muted">生成依据：${escapeHtml(planningAnalysis.analysisSummary || "")}</p>` : ""}
                    ${planningAnalysis ? `<p class="muted">原型状态：${escapeHtml(planningAnalysis.latestPrototypeStatus || "未知")} · 草稿覆盖率：${escapeHtml(String(planningAnalysis.draftCoveragePercent ?? 0))}%${planningAnalysis.templateId ? ` · 模板：${escapeHtml(planningAnalysis.templateId)}` : ""}</p>` : ""}
                    ${planningAnalysis && Array.isArray(planningAnalysis.fieldCoverage) && planningAnalysis.fieldCoverage.length
                      ? `<p class="muted">字段判断：${escapeHtml(planningAnalysis.fieldCoverage.map(item => `${item.field}:${item.status}${item.missingReason ? `(${item.missingReason})` : item.evidence ? `(${item.evidence})` : ""}`).join(" · "))}</p>`
                      : ""}
                  `;
                  $("createIterationPlan").disabled = !isLatestPlan || (planComplete ? isGlobalBusy() : (!canUpdatePlan || blockedByCurrentGoal || isGlobalBusy()));
                  $("createIterationPlan").textContent = planComplete ? "创建新的游戏模块" : "重新生成游戏模块";
                  $("deleteIterationPlan").classList.remove("hidden");
                  $("deleteIterationPlan").textContent = "删除当前轮游戏模块";
                  $("deleteIterationPlan").disabled = !isLatestPlan || planComplete || isGlobalBusy();
                  $("evaluateIterationPlan").disabled = !isLatestPlan || isGlobalBusy() || state.iterationPlanEvaluationRunning;
                  $("evaluateIterationPlan").textContent = state.iterationPlanEvaluationRunning ? "评估中..." : "评估当前游戏模块";
                  $("evaluateIterationPlanFromChat").disabled = !isLatestPlan || isGlobalBusy() || state.iterationPlanEvaluationRunning;
                  $("evaluateIterationPlanFromChat").textContent = state.iterationPlanEvaluationRunning ? "评估中..." : "评估当前计划是否值得继续";
                  $("executeIterationGoal").disabled = hasNeedsFix
                    ? (!isLatestPlan || isGlobalBusy())
                    : (!isLatestPlan || !hasPending || shouldRefinePlan || blockedByCurrentGoal || isGlobalBusy());
                  $("executeIterationGoal").textContent = hasNeedsFix
                    ? "运行 Needs Fix 路由"
                    : shouldRefinePlan
                      ? "建议先重拆游戏模块"
                      : hasPending
                        ? "执行下一目标"
                        : "当前没有待执行目标";
                  renderIterationPlanEvaluation();
                  $("iterationNeedsFixStatus").className = hasNeedsFix ? "card" : "card muted";
                  $("iterationNeedsFixStatus").textContent = hasNeedsFix
                    ? "当前有 step 需要修复。点击对应 step 卡片里的“运行 Needs Fix 路由”会直接提交后台 run。"
                    : "当前没有 needs fix step。";
                  renderChatHistory();
                  const needsFixBusy = isGlobalBusy();
                  const needsFixDisabledAttrs = needsFixBusy ? ` disabled title="有任务正在执行，请等待当前任务执行完毕。"` : "";
                  $("iterationPlanGoals").innerHTML = goals.map(goal => `
                    <div class="card">
                      <strong>step ${escapeHtml(String(goal.goalIndex))} · ${escapeHtml(goal.status || "pending")}</strong>
                      ${["needs_fix", "failed"].includes(String(goal.status || "").trim().toLowerCase())
                        ? `<div class="v2-action-row"><button type="button" class="secondary" data-needs-fix-goal="${escapeHtml(String(goal.goalIndex || ""))}" onclick="event.stopPropagation(); runNeedsFixIterationGoal('${escapeHtml(String(goal.goalIndex || ""))}'); return false;"${needsFixDisabledAttrs}>运行 Needs Fix 路由</button></div>`
                        : ""}
                      <p>${escapeHtml(goal.title || "")}</p>
                      <p class="muted">${escapeHtml(goal.description || "")}</p>
                      ${goal.acceptanceHint ? `<p class="muted">完成判断：${escapeHtml(goal.acceptanceHint)}</p>` : ""}
                      ${goal.resultSummary ? `<p class="muted">结果：${escapeHtml(publicIterationGoalResultSummary(goal))}</p>` : ""}
                    </div>`).join("");
                }

                function publicIterationGoalResultSummary(goal) {
                  const status = String(goal?.status || "").trim().toLowerCase();
                  if (["needs_fix", "failed"].includes(status)) {
                    const details = sanitizePublicFailureContent(goal?.resultSummary || "");
                    return details
                      ? `该 step 未通过。失败详情：${details}（路径和文件名已隐藏。）请点击 Needs Fix 路由继续修复。`
                      : "该 step 未通过。失败详情不可展示，请点击 Needs Fix 路由继续修复，后台记录会保留完整证据。";
                  }
                  return sanitizePublicIterationPlanText(goal?.resultSummary || "");
                }

                function iterationPlanGoals() {
                  return Array.isArray(state.iterationPlan?.goals) ? state.iterationPlan.goals : [];
                }

                function hasAnyIterationPlan() {
                  return !!(state.iterationPlan?.session && iterationPlanGoals().length);
                }

                function hasOpenIterationPlan() {
                  return iterationPlanGoals().some(goal => ["pending", "needs_fix", "failed", "running"].includes(String(goal.status || "").trim().toLowerCase()));
                }

                function isIterationPlanComplete() {
                  const goals = iterationPlanGoals();
                  return goals.length > 0 && goals.every(goal => ["completed", "succeeded"].includes(String(goal.status || "").trim().toLowerCase()));
                }

                function isIterationPlanStarted() {
                  const goals = iterationPlanGoals();
                  const hasGoalRun = Array.isArray(state.iterationPlan?.goalRuns) && state.iterationPlan.goalRuns.length > 0;
                  const currentIndex = Number(state.iterationPlan?.session?.currentGoalIndex || 0);
                  return hasGoalRun || currentIndex > 0 || goals.some(goal => String(goal.status || "").trim().toLowerCase() !== "pending");
                }

                function currentNeedsFixRouteGoal() {
                  const goals = iterationPlanGoals();
                  if (!goals.length) return null;
                  const byStatus = status => goals.find(goal => String(goal.status || "").trim().toLowerCase() === status);
                  const currentIndex = Number(state.iterationPlan?.session?.currentGoalIndex || 0);
                  const currentGoal = currentIndex > 0 ? goals.find(goal => Number(goal.goalIndex || 0) === currentIndex) : null;
                  const currentStatus = String(currentGoal?.status || "").trim().toLowerCase();
                  return byStatus("needs_fix")
                    || byStatus("failed")
                    || byStatus("running")
                    || (currentGoal && currentStatus !== "pending" && currentStatus !== "succeeded" ? currentGoal : null)
                    || null;
                }

                function buildNeedsFixFeedbackForUserReport(goal, userFeedback) {
                  const lines = [
                    goal
                      ? `用户提交了当前目标的报错/修复反馈，请通过 needs-fix 顶层路由处理 step ${String(goal.goalIndex || "").trim()}：${String(goal.title || "").trim()}`
                      : "用户提交了报错/修复反馈，请通过 needs-fix 顶层路由处理。如果当前项目还没有可修复目标，请返回明确的前置条件提示，不要生成游戏模块。",
                    "",
                    "用户反馈：",
                    String(userFeedback || "").trim()
                  ];
                  if (goal?.resultSummary) {
                    lines.push("", "当前目标最近结果：", String(goal.resultSummary).trim());
                  }
                  return lines.join("\n").trim();
                }

                function renderIterationPlanEvaluation() {
                  if (state.iterationPlanEvaluationRunning) {
                    $("iterationPlanEvaluation").className = "card";
                    $("iterationPlanEvaluation").innerHTML = `
                      <strong>正在评估当前游戏模块</strong>
                      <p class="muted">系统正在判断当前计划是否可以直接执行，完成后结果会保留在这里。</p>
                    `;
                    return;
                  }
                  const evaluation = state.iterationPlanEvaluation;
                  if (!evaluation) {
                    $("iterationPlanEvaluation").className = "card muted";
                    $("iterationPlanEvaluation").textContent = "尚未评估当前游戏模块。";
                    return;
                  }
                  const decision = String(evaluation.decision || "").trim().toLowerCase();
                  const actionHint = decision === "llm_failed"
                    ? "LLM 调用失败，需先修复 LLM 后再继续；系统不会用本地规则替代评估。"
                    : decision === "should_refine_plan"
                    ? "推荐先点击“重新生成游戏模块”，不要直接执行下一目标。"
                    : decision === "ready_to_execute"
                      ? "推荐直接执行下一目标；如果目标变化较大，再重新生成计划。"
                      : "推荐先处理当前阻塞项，再决定是否继续。";
                  $("iterationPlanEvaluation").className = "card";
                  const safeSummary = sanitizePublicIterationPlanText(evaluation.summary || "");
                  const safeSuggestedAction = sanitizePublicIterationPlanText(evaluation.suggestedAction || "");
                  const safeRegenerationPrompt = sanitizePublicIterationPlanText(evaluation.suggestedPromptForRegeneration || "");
                  $("iterationPlanEvaluation").innerHTML = `
                    <strong>${escapeHtml(evaluation.decision || "pending")}</strong>
                    ${safeSummary ? `<p>${escapeHtml(safeSummary)}</p>` : ""}
                    ${safeSuggestedAction ? `<p class="muted">建议动作：${escapeHtml(safeSuggestedAction)}</p>` : ""}
                    <p class="muted">页面建议：${escapeHtml(actionHint)}</p>
                    ${safeRegenerationPrompt ? `<p class="muted">建议重拆提示词：${escapeHtml(safeRegenerationPrompt)}</p>` : ""}
                  `;
                }

                function autoGrowTextarea(textarea) {
                  if (!textarea) return;
                  textarea.style.height = "auto";
                  textarea.style.height = `${Math.min(Math.max(textarea.scrollHeight, 44), 220)}px`;
                }

                function openIterationPlanUpdateModal(mode, initialValue = "") {
                  state.iterationPlanUpdateMode = mode;
                  const isNewPlan = mode === "new";
                  $("iterationPlanUpdateTitle").textContent = isNewPlan ? "创建新的游戏模块" : "重新生成游戏模块";
                  $("iterationPlanUpdateEvaluation").className = isNewPlan ? "card muted hidden" : "card";
                  $("iterationPlanUpdateEvaluation").innerHTML = isNewPlan
                    ? ""
                    : iterationPlanEvaluationHtml(state.iterationPlanEvaluation);
                  $("iterationPlanUpdateInput").value = initialValue || "";
                  $("iterationPlanUpdateInput").placeholder = isNewPlan
                    ? "输入第二轮或新一轮迭代目标。"
                    : "输入本次更新计划的补充要求；留空时会优先使用评估结果中的重拆建议。";
                  $("confirmIterationPlanUpdate").textContent = isNewPlan ? "创建新的游戏模块" : "更新游戏模块";
                  $("iterationPlanUpdateHint").textContent = isNewPlan
                    ? "当前游戏模块已完成，将基于这里输入的新目标创建下一轮计划。"
                    : "更新时会优先参考输入框信息，其次参考当前评估结果。";
                  setModalVisible("iterationPlanUpdateModal", true);
                  autoGrowTextarea($("iterationPlanUpdateInput"));
                  $("iterationPlanUpdateInput").focus();
                }

                function iterationPlanEvaluationHtml(evaluation) {
                  if (!evaluation) return "<p class='muted'>尚未评估当前游戏模块。可以先关闭弹窗并点击“评估当前游戏模块”。</p>";
                  const safeSummary = sanitizePublicIterationPlanText(evaluation.summary || "");
                  const safeSuggestedAction = sanitizePublicIterationPlanText(evaluation.suggestedAction || "");
                  const safeRegenerationPrompt = sanitizePublicIterationPlanText(evaluation.suggestedPromptForRegeneration || "");
                  return `
                    <strong>${escapeHtml(evaluation.decision || "unknown")}</strong>
                    ${safeSummary ? `<p>${escapeHtml(safeSummary)}</p>` : ""}
                    ${safeSuggestedAction ? `<p class="muted">${escapeHtml(safeSuggestedAction)}</p>` : ""}
                    ${safeRegenerationPrompt ? `<p class="muted">建议：${escapeHtml(safeRegenerationPrompt)}</p>` : ""}
                  `;
                }

                async function confirmIterationPlanUpdate() {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("请先选择一个项目。");
                  const mode = state.iterationPlanUpdateMode || "update";
                  if (mode !== "new" && isIterationPlanStarted()) {
                    out("当前游戏模块已经开始执行，不允许更新游戏模块。");
                    return;
                  }
                  const typedMessage = $("iterationPlanUpdateInput").value.trim();
                  if (mode === "new" && !typedMessage) {
                    $("iterationPlanUpdateHint").textContent = "请输入第二轮游戏模块目标。";
                    $("iterationPlanUpdateInput").classList.add("field-invalid");
                    $("iterationPlanUpdateInput").focus();
                    return;
                  }
                  const evaluationMessage = currentIterationPlanRegenerationPrompt()
                    || state.iterationPlanEvaluation?.suggestedAction
                    || state.iterationPlanEvaluation?.reason
                    || "";
                  const message = typedMessage || evaluationMessage || state.nextSuggestedFeedback || defaultNextSuggestedFeedback();
                  const sourceKind = mode === "new" ? "new_iteration_plan" : typedMessage ? "iteration_plan_update" : "completion_suggestion";
                  setModalVisible("iterationPlanUpdateModal", false);
                  await submitIterationPlanFromFeedback(message, mode === "new" ? "正在创建新的游戏模块..." : "正在更新游戏模块...", sourceKind);
                }

                async function createIterationPlan() {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("请先选择一个项目。");
                  if (hasAnyIterationPlan()) {
                    if (isIterationPlanComplete()) {
                      openIterationPlanUpdateModal("new");
                      return;
                    }
                    if (isIterationPlanStarted()) {
                      out("当前游戏模块已经开始执行，不允许更新游戏模块。");
                      return;
                    }
                    openIterationPlanUpdateModal("update");
                    return;
                  }
                  const typedMessage = $("chatMessage").value.trim();
                  const message = typedMessage || currentIterationPlanRegenerationPrompt() || state.nextSuggestedFeedback || defaultNextSuggestedFeedback();
                  const sourceKind = typedMessage ? "manual_feedback" : "completion_suggestion";
                  if (!typedMessage) {
                    out("未输入优化目标，已使用当前下一步建议生成游戏模块。");
                  }
                  await submitIterationPlanFromFeedback(message, "正在生成游戏模块...", sourceKind);
                }

                async function evaluateIterationPlan(announceInChat = false) {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("请先选择一个项目。");
                  if (!state.iterationPlan?.session) return out("请先生成游戏模块。");
                  state.iterationPlanEvaluationRunning = true;
                  renderIterationPlan();
                  try {
                    const response = await api(`/api/projects/${state.projectId}/iteration-plan/evaluate`, {
                      method: "POST",
                      timeoutMs: longLlmTimeoutMs,
                      body: JSON.stringify({ model: $("globalModel").value || "gpt-5.5" })
                    });
                    state.iterationPlanEvaluation = response?.evaluation || response;
                    if (state.iterationPlan) {
                      state.iterationPlan.latestEvaluation = state.iterationPlanEvaluation;
                    }
                    syncIterationPlanRegenerationSuggestion();
                    renderIterationPlanEvaluation();
                    renderIterationPlan();
                    if (!announceInChat) {
                      out({
                        action: "iteration_plan_evaluated",
                        decision: state.iterationPlanEvaluation?.decision || "",
                        summary: state.iterationPlanEvaluation?.summary || "",
                        suggestedAction: state.iterationPlanEvaluation?.suggestedAction || ""
                      });
                    }
                    out({
                      action: "iteration_plan_evaluated",
                      decision: state.iterationPlanEvaluation?.decision || "",
                      summary: sanitizePublicIterationPlanText(state.iterationPlanEvaluation?.summary || ""),
                      suggestedAction: sanitizePublicIterationPlanText(state.iterationPlanEvaluation?.suggestedAction || "")
                    });
                  } catch (error) {
                    const payload = error?.payload;
                    if (payload?.status && payload?.summary) {
                      out({
                        status: error.status,
                        summary: "游戏模块评估失败。失败详情已隐藏，请稍后重试或联系管理员查看后台记录。"
                      });
                    } else {
                    showError(error);
                    }
                  } finally {
                    state.iterationPlanEvaluationRunning = false;
                    renderIterationPlan();
                    await refreshActiveRun();
                  }
                }

                async function submitIterationPlanFromFeedback(message, busyText, sourceKind = "manual_feedback") {
                  setLocalBusy(true, "正在生成游戏模块，请等待当前任务执行完毕。");
                  let shouldReloadIterationPlan = true;
                  try {
                    $("chatMessage").value = "";
                    const result = await api(`/api/projects/${state.projectId}/iteration-plan`, {
                      method: "POST",
                      timeoutMs: longLlmTimeoutMs,
                      body: JSON.stringify({ message, sourceKind, attachments: currentChatAttachmentsForRun(), model: $("globalModel").value || "gpt-5.5" })
                    });
                    const summary = result.goals?.length
                      ? `${result.summary}\n\n本次目标拆分：\n${result.goals.map(goal => `${goal.goalIndex}. ${goal.title}`).join("\n")}`
                      : result.summary;
                    if (result.status !== "ready") {
                      state.iterationPlanEvaluation = null;
                      state.iterationPlanFailure = publicIterationPlanFailureMessage(summary);
                      renderIterationPlan();
                      out({ status: result.status || "failed", summary: state.iterationPlanFailure });
                      shouldReloadIterationPlan = false;
                      return result;
                    }
                    state.iterationPlan = {
                      roundIndex: (Array.isArray(state.iterationPlans) ? state.iterationPlans.length : 0) + 1,
                      session: {
                        sessionId: result.sessionId,
                        status: result.status,
                        overallGoal: message,
                        currentGoalIndex: 0,
                        latestSummary: result.summary
                      },
                      goals: result.goals || [],
                      goalRuns: [],
                      latestEvaluation: result.latestEvaluation || null
                    };
                    state.iterationPlans = [...(Array.isArray(state.iterationPlans) ? state.iterationPlans.filter(plan => plan?.session?.sessionId !== result.sessionId) : []), state.iterationPlan];
                    state.selectedIterationSessionId = result.sessionId;
                    state.iterationPlanEvaluation = result.latestEvaluation || null;
                    state.iterationPlanFailure = "";
                    renderIterationPlan();
                    out(result);
                    return result;
                  } catch (error) {
                    showError(error);
                    shouldReloadIterationPlan = false;
                    return null;
                  } finally {
                    clearChatAttachments();
                    setLocalBusy(false);
                    if (shouldReloadIterationPlan) {
                      await loadIterationPlan();
                    } else {
                      renderIterationPlan();
                    }
                    await loadProjectPackages();
                    await refreshActiveRun();
                  }
                }

                async function deleteIterationPlan() {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("请先选择一个项目。");
                  if (!hasAnyIterationPlan()) return out("当前没有可删除的游戏模块。");
                  if (isIterationPlanComplete()) return out("游戏模块已经全部完成，不可以删除。");
                  const sessionId = state.iterationPlan?.session?.sessionId || state.selectedIterationSessionId || "";
                  const roundIndex = state.iterationPlan?.roundIndex || "";
                  if (!sessionId) return out("当前没有选中的游戏模块轮次。");
                  const roundLabel = roundIndex ? `第 ${roundIndex} 轮` : "当前轮";
                  if (!confirm(`确定要删除${roundLabel}游戏模块吗？该操作不会删除其他轮次。`)) return;
                  setLocalBusy(true, `正在删除${roundLabel}游戏模块...`);
                  try {
                    const result = await api(`/api/projects/${state.projectId}/iteration-plans/${encodeURIComponent(sessionId)}`, { method: "DELETE" });
                    state.iterationPlan = null;
                    state.selectedIterationSessionId = "";
                    state.iterationPlanEvaluation = null;
                    state.iterationPlanFailure = "";
                    renderIterationPlan();
                    out(result.summary || `${roundLabel}游戏模块已删除。`);
                    await loadIterationPlan();
                  } catch (error) {
                    showError(error);
                  } finally {
                    setLocalBusy(false);
                    await loadProjectPackages();
                    await refreshActiveRun();
                  }
                }

                async function executeIterationGoal() {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("请先选择一个项目。");
                  if (!state.iterationPlan?.session) return out("请先生成游戏模块。");
                  const needsFixGoal = currentNeedsFixRouteGoal();
                  if (needsFixGoal) {
                    await runNeedsFixIterationGoal(needsFixGoal.goalIndex);
                    return;
                  }
                  const evaluationDecision = currentIterationPlanDecision();
                  if (evaluationDecision === "should_refine_plan") return out("当前评估建议先重拆游戏模块，已停止执行旧目标。");
                  if (evaluationDecision === "llm_failed") return out("当前游戏模块评估失败，请先修复评估调用并重新评估计划。");
                  if (evaluationDecision === "blocked_by_current_goal") return out("当前评估显示已有目标阻塞，请先处理当前阻塞项。");
                  setLocalBusy(true, "正在执行下一目标，请等待当前任务执行完毕。");
                  try {
                    const result = await api(`/api/projects/${state.projectId}/iteration-plan/execute-next`, {
                      method: "POST"
                    });
                    await loadServerChatHistoryForProject(state.projectId);
                    out(result);
                  } catch (error) {
                    await loadServerChatHistoryForProject(state.projectId);
                    showError(error);
                  } finally {
                    setLocalBusy(false);
                    await loadIterationPlan();
                    await loadRuns();
                    await loadProjectPackages();
                    await refreshActiveRun();
                  }
                }

                async function runUiOptimization() {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("请先选择一个项目。");
                  if (!callV2("v2HasPrototypeSkeleton")) return out("请先完成原型骨架创建，再运行游戏界面优化。");
                  const goals = Array.isArray(state.iterationPlan?.goals) ? state.iterationPlan.goals : [];
                  if (!goals.length || !goals.every(goal => ["succeeded", "completed"].includes(String(goal.status || "").trim().toLowerCase()))) {
                    return out("请先完成游戏模块，再运行游戏界面优化。");
                  }
                  $("uiOptimizationStatus").textContent = "正在运行游戏界面优化，请等待后台任务完成。";
                  setLocalBusy(true, "正在运行游戏界面优化，请等待当前任务执行完毕。");
                  try {
                    const result = await api(`/api/projects/${state.projectId}/ui-optimization`, {
                      method: "POST",
                      body: JSON.stringify({ model: $("globalModel").value || "gpt-5.5" })
                    });
                    $("uiOptimizationStatus").textContent = result.summary || "游戏界面优化已完成。";
                    if (String(result.status || "").toLowerCase() === "succeeded") callV2("v2SetPrototypeValidationInvalidated", true);
                    out(result);
                  } catch (error) {
                    $("uiOptimizationStatus").textContent = `游戏界面优化失败：${error.message || error}`;
                    showError(error);
                  } finally {
                    setLocalBusy(false);
                    await loadRuns();
                    await refreshActiveRun();
                    callV2("v2RenderProgress");
                  }
                }

                async function createRepairPlan() {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("请先选择一个项目。");
                  setLocalBusy(true, "正在生成修复计划，请等待当前任务执行完毕。");
                  try {
                    const result = await api(`/api/projects/${state.projectId}/repair-plan`, { method: "POST" });
                    state.repairPlan = result;
                    renderRepairPlan();
                    focusRepairPlanPanel();
                    out(result);
                  } catch (error) {
                    showError(error);
                  } finally {
                    setLocalBusy(false);
                    await loadRepairPlan();
                    await refreshActiveRun();
                  }
                }

                async function executeRepairStep() {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("请先选择一个项目。");
                  if (!state.repairPlan?.sessionId) return out("请先生成修复计划。");
                  setLocalBusy(true, "正在执行下一项修复，请等待当前任务执行完毕。");
                  try {
                    const result = await api(`/api/projects/${state.projectId}/repair-plan/execute-next`, {
                      method: "POST",
                      body: JSON.stringify({ model: $("globalModel").value })
                    });
                    await loadServerChatHistoryForProject(state.projectId);
                    out(result);
                  } catch (error) {
                    await loadServerChatHistoryForProject(state.projectId);
                    showError(error);
                  } finally {
                    setLocalBusy(false);
                    await loadRepairPlan();
                    await loadRuns();
                    await refreshActiveRun();
                  }
                }

                function renderChatAttachments() {
                  const status = $("chatAttachmentStatus");
                  if (!status) return;
                  const files = state.chatAttachments || [];
                  if (!files.length) {
                    status.className = "v2-attachment-list muted";
                    status.textContent = "未导入 TXT 参考文件，只支持 TXT 文件导入。";
                    return;
                  }
                  status.className = "v2-attachment-list";
                  status.innerHTML = `
                    ${files.map((file, index) => `
                      <span class="v2-attachment-chip">
                        <span class="v2-attachment-name">${escapeHtml(file.fileName)}</span>
                        <span class="v2-attachment-meta">${escapeHtml(String(file.content?.length || 0))} 字符</span>
                        <button class="ghost v2-attachment-remove removeChatAttachment" type="button" title="移除 ${escapeHtml(file.fileName)}" data-index="${index}">×</button>
                      </span>
                    `).join("")}`;
                  document.querySelectorAll(".removeChatAttachment").forEach(button => {
                    button.onclick = () => removeChatAttachment(Number(button.dataset.index));
                  });
                }

                async function loadChatAttachmentFiles() {
                  const input = $("chatAttachmentFiles");
                  const files = Array.from(input?.files || []);
                  const existing = state.chatAttachments || [];
                  if (existing.length + files.length > 5) {
                    input.value = "";
                    renderChatAttachments();
                    return out("最多只能导入 5 个 TXT 参考文件。");
                  }
                  const attachments = [];
                  for (const file of files) {
                    const isTxt = file.type === "text/plain" || file.name.toLowerCase().endsWith(".txt");
                    if (!isTxt) {
                      input.value = "";
                      renderChatAttachments();
                      return out("只能导入 TXT 参考文件。");
                    }
                    attachments.push({ fileName: file.name, content: await file.text() });
                  }
                  state.chatAttachments = existing.concat(attachments);
                  input.value = "";
                  renderChatAttachments();
                }

                function removeChatAttachment(index) {
                  const files = state.chatAttachments || [];
                  if (index < 0 || index >= files.length) return;
                  state.chatAttachments = files.filter((_, currentIndex) => currentIndex !== index);
                  if ($("chatAttachmentFiles")) $("chatAttachmentFiles").value = "";
                  renderChatAttachments();
                }

                function clearChatAttachments() {
                  state.chatAttachments = [];
                  if ($("chatAttachmentFiles")) $("chatAttachmentFiles").value = "";
                  renderChatAttachments();
                }

                function currentChatAttachmentsForRun() {
                  return (state.chatAttachments || []).map(file => ({ fileName: file.fileName, content: file.content }));
                }

                function saveChatHistoryForProject() {
                  if (!state.projectId) return;
                  const compact = state.chatHistory.filter(isStoredChatMessage).slice(-maxStoredChatMessages).map(normalizeStoredChatMessage);
                  state.chatHistory = compact;
                  try {
                    localStorage.setItem(chatStorageKey(), JSON.stringify(compact));
                  } catch {
                    // Chat persistence is best-effort; it must not turn a successful workflow scan into a failed user action.
                  }
                }

                function chatMessageKey(message) {
                  return `${message?.role || ""}|${message?.kind || ""}|${sanitizePublicChatContent(message?.content || "")}`;
                }

                function previousStoredMessageKey(index) {
                  for (let current = index - 1; current >= 0; current--) {
                    const message = state.chatHistory[current];
                    if (isStoredChatMessage(message) && message?.kind !== "workflow-route") return chatMessageKey(message);
                  }
                  return "";
                }

                function nextStoredMessageKey(index) {
                  for (let current = index + 1; current < state.chatHistory.length; current++) {
                    const message = state.chatHistory[current];
                    if (isStoredChatMessage(message) && message?.kind !== "workflow-route") return chatMessageKey(message);
                  }
                  return "";
                }

                function mergeLocalWorkflowRouteMessages(serverMessages, localWorkflowRouteEntries) {
                  const merged = [...serverMessages];
                  for (const entry of localWorkflowRouteEntries) {
                    if (!isStoredChatMessage(entry.message)) continue;
                    if (merged.some(message => chatMessageKey(message) === chatMessageKey(entry.message))) continue;
                    let inserted = false;
                    if (entry.previousKey) {
                      const previousIndex = merged.findIndex(message => chatMessageKey(message) === entry.previousKey);
                      if (previousIndex >= 0) {
                        merged.splice(previousIndex + 1, 0, entry.message);
                        inserted = true;
                      }
                    }
                    if (!inserted && entry.nextKey) {
                      const nextIndex = merged.findIndex(message => chatMessageKey(message) === entry.nextKey);
                      if (nextIndex >= 0) {
                        merged.splice(nextIndex, 0, entry.message);
                        inserted = true;
                      }
                    }
                    if (!inserted) merged.push(entry.message);
                  }
                  return merged.filter(isStoredChatMessage);
                }

                function isStoredChatMessage(message) {
                  return message &&
                    !message.pending &&
                    message.kind !== "prototype-seed" &&
                    (message.role === "user" || message.role === "assistant") &&
                    typeof message.content === "string" &&
                    message.content.trim().length > 0;
                }

                function isLlmChatHistoryMessage(message) {
                  return isStoredChatMessage(message) && message.kind !== "workflow-route";
                }

                function recentChatHistoryForLlm() {
                  return state.chatHistory
                    .filter(isLlmChatHistoryMessage)
                    .slice(-3)
                    .map(message => ({ role: message.role, content: message.content }));
                }

                function normalizeStoredChatMessage(message) {
                  const stored = {
                    role: message.role,
                    content: sanitizePublicChatContent(message.content),
                    kind: message.kind || null,
                    continueConsumed: !!message.continueConsumed,
                    suggestedFeedback: sanitizePublicChatContent(message.suggestedFeedback || "")
                  };
                  if (message.workflowAction) stored.workflowAction = message.workflowAction;
                  if (message.workflowActions) stored.workflowActions = message.workflowActions;
                  if (message.workflowActionToken) stored.workflowActionToken = message.workflowActionToken;
                  if (message.workflowActionConsumed) stored.workflowActionConsumed = true;
                  if (message.workflowRoute) stored.workflowRoute = message.workflowRoute;
                  if (message.workflowIntent) stored.workflowIntent = message.workflowIntent;
                  if (message.gddOutlineUrl) stored.gddOutlineUrl = message.gddOutlineUrl;
                  return stored;
                }

                function restoreWorkflowRouteActionFromHistory() {
                  state.workflowRouteActionToken = "";
                  state.workflowRouteActionConsumed = false;
                  const latest = [...(state.chatHistory || [])].reverse().find(message =>
                    message.workflowActionToken &&
                    workflowMessageActions(message).length &&
                    !message.workflowActionConsumed);
                  if (!latest) return;
                  state.workflowRouteActionToken = latest.workflowActionToken;
                }

                function isVisibleChatMessage(message) {
                  return message?.kind !== "prototype-seed";
                }

                function sanitizePublicChatContent(value) {
                  const gddLinks = [];
                  return String(value || "")
                    .replace(/\/projects\/[^\s`'"，。；：、）)<]+\/gdd\/GDD\.md\?ticket=[^\s`'"，。；：、）)<]+/g, match => {
                      const token = `__PHASEA_GDD_LINK_${gddLinks.length}__`;
                      gddLinks.push(match);
                      return token;
                    })
                    .replace(/(?:本轮目标：|Direction lock:|Project README:|Recovery source consumed:|Current goal:|Scope rule:)[\s\S]*$/gi, "")
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

                function sanitizePublicFailureContent(value) {
                  return sanitizePublicChatContent(value || "")
                    .replace(/\[(?:路径已隐藏|文件已隐藏|模块已隐藏)\](?:\s*[:：]\s*)?/g, "[详情已隐藏]")
                    .replace(/(?:\[详情已隐藏\]\s*){2,}/g, "[详情已隐藏] ")
                    .replace(/[ \t]{2,}/g, " ")
                    .replace(/\n{3,}/g, "\n\n")
                    .trim();
                }

                function sanitizePublicIterationPlanText(value) {
                  return sanitizePublicChatContent(value || "");
                }

                function publicIterationPlanFailureMessage(value) {
                  const raw = String(value || "");
                  if (raw.includes("联系管理员创建定制游戏类型路线")) {
                    return "当前项目需要联系管理员创建定制游戏类型路线。";
                  }
                  const details = sanitizePublicFailureContent(raw);
                  return details
                    ? `游戏模块生成失败。失败详情：${details}（路径和文件名已隐藏。）`
                    : "游戏模块生成失败。失败详情不可展示，请稍后重试或联系管理员查看后台记录。";
                }

                function startChatThinkingMessage(initialContent = null) {
                  const id = `pending-${Date.now()}-${Math.random().toString(16).slice(2)}`;
                  let index = 0;
                  const message = { role: "assistant", content: initialContent || chatThinkingPrompts[index], pending: true, pendingId: id };
                  state.chatHistory.push(message);
                  renderChatHistory();
                  const timer = setInterval(() => {
                    const pending = state.chatHistory.find(item => item.pendingId === id);
                    if (!pending) {
                      clearInterval(timer);
                      return;
                    }
                    index = (index + 1) % chatThinkingPrompts.length;
                    pending.content = initialContent || chatThinkingPrompts[index];
                    renderChatHistory();
                  }, 5000);
                  return {
                    complete(content, failed = false, kind = null, extra = null) {
                      clearInterval(timer);
                      const pending = state.chatHistory.find(item => item.pendingId === id);
                      if (pending) {
                        pending.content = content;
                        pending.pending = false;
                        delete pending.pendingId;
                        if (kind) pending.kind = kind;
                        if (failed) pending.failed = true;
                        if (extra) Object.assign(pending, extra);
                      } else {
                        state.chatHistory.push({ role: "assistant", content, failed, kind, ...(extra || {}) });
                      }
                      renderChatHistory();
                      saveChatHistoryForProject();
                    }
                  };
                }

                function showLoggedOut() {
                  document.title = "Game Ren";
                  state.authenticated = false;
                  state.activeRun = null;
                  state.localBusy = false;
                  state.iterationPlan = null;
                  closeUserModals();
                  setUserTopActionsVisible(false);
                  $("sessionPanel").classList.remove("hidden");
                  hideCreateProjectPage();
                  $("adminPanel").classList.add("hidden");
                  $("accountAdminPanel").classList.add("hidden");
                  $("prototypeCommandPanel").classList.add("hidden");
                  $("chatPanel").classList.add("hidden");
                  state.nextSuggestedFeedback = "";
                  applyGlobalBusyState();
                  $("sessionStatus").textContent = token()
                    ? "Token 已保留。连接失败或认证未通过时，请点击验证并进入重试。"
                    : "Please paste an access token to sign in.";
                }

                function showAdminShell(role = state.role || "user") {
                  state.authenticated = true;
                  state.role = role;
                  const isAdmin = role === "admin";
                  document.title = isAdmin ? "Game Ren Admin" : "Game Ren";
                  $("sessionPanel").classList.add("hidden");
                  hideCreateProjectPage();
                  $("adminPanel").classList.remove("hidden");
                  setUserTopActionsVisible(true, isAdmin);
                  if (isAdmin) closeUserModals();
                  $("loadRuns").classList.toggle("hidden", !isAdmin);
                  $("runsPanel").classList.toggle("hidden", !isAdmin);
                  $("outputPanel").classList.toggle("hidden", !isAdmin);
                  $("accountAdminPanel").classList.toggle("hidden", !isAdmin);
                  $("prototypeCommandPanel").classList.toggle("hidden", !isAdmin);
                  $("chatPanel").classList.add("hidden");
                  $("projectDetailPanel").classList.add("hidden");
                  $("initStatusPanel").classList.add("hidden");
                  loadSkillActions();
                  if (isAdmin) {
                    loadUserAccounts();
                    loadAiCodeMirrorKeys();
                    loadAdminLlmUsage();
                    loadAdminLlmRuns();
                    loadAccountAudit();
                  }
                  refreshActiveRun();
                }

                function showInitialization(status, error) {
                  showAdminShell();
                  closeUserModals();
                  $("projectDetailPanel").classList.add("hidden");
                  $("initStatusPanel").classList.remove("hidden");
                  if (status === "failed") {
                    showCreateProjectPage();
                    $("adminPanel").classList.remove("hidden");
                    $("projectDetailPanel").classList.add("hidden");
                    $("chatPanel").classList.add("hidden");
                    $("initStatusText").innerHTML = `<strong class="danger">创建失败。</strong><br>${escapeHtml(sanitizePublicFailureContent(error || "初始化失败，请查看运行记录。"))}`;
                    return;
                  }
                  $("initStatusText").textContent = "项目初始化配置中...请稍等 2-5 分钟后刷新页面。";
                }

                function showProjectDetail() {
                  showAdminShell();
                  $("initStatusPanel").classList.add("hidden");
                  $("projectDetailPanel").classList.remove("hidden");
                }

                function projectStateCacheKey(projectId = state.projectId) {
                  return `phaseA.projectStateCache.v${projectStateCacheVersion}.${projectId || "none"}`;
                }

                function selectedProjectIdKey() {
                  return "phaseA.selectedProjectId";
                }

                function readSelectedProjectId() {
                  try {
                    return localStorage.getItem(selectedProjectIdKey()) || "";
                  } catch {
                    return "";
                  }
                }

                function writeSelectedProjectId(projectId) {
                  try {
                    if (projectId) localStorage.setItem(selectedProjectIdKey(), projectId);
                    else localStorage.removeItem(selectedProjectIdKey());
                  } catch {}
                }

                function readProjectStateCache(projectId = state.projectId) {
                  if (!projectId) return null;
                  try {
                    const cached = JSON.parse(localStorage.getItem(projectStateCacheKey(projectId)) || "null");
                    return cached && cached.projectId === projectId ? cached : null;
                  } catch {
                    return null;
                  }
                }

                function writeProjectStateCache(patch = {}) {
                  if (!state.projectId) return;
                  const previous = readProjectStateCache(state.projectId) || { projectId: state.projectId };
                  const next = { ...previous, ...patch, projectId: state.projectId, updatedAt: new Date().toISOString() };
                  try { localStorage.setItem(projectStateCacheKey(state.projectId), JSON.stringify(next)); } catch {}
                }

                function applyProjectStateCache(projectId) {
                  const cached = readProjectStateCache(projectId);
                  if (!cached) return;
                  if (Array.isArray(cached.runs)) {
                    state.runs = cached.runs;
                    renderRunsListFromState(cached.projectHealth || null);
                    renderFeedbackRecords();
                  }
                  if (cached.latestPrototypeDraft) {
                    applyDraftToForm(cached.latestPrototypeDraft);
                    renderDraftImportStatus(cached.latestPrototypeDraft);
                  }
                  if (cached.prototypeProgress) {
                    const progress = cached.prototypeProgress;
                    const acceptanceStatus = String(progress?.acceptanceStatus || progress?.status || "").trim().toLowerCase();
                    state.prototypeFailure = acceptanceStatus === "failed" ? (progress.acceptanceFailure || progress.failure || "") : "";
                    renderPrototypeProgress(progress);
                    renderPrototypeAcceptanceSummary(progress);
                    setPrototypeFormLocked(isPrototypeCreationLocked(progress));
                    updateChatPanelVisibility(progress);
                  }
                  if (cached.packageList) {
                    state.packageList = cached.packageList;
                    renderProjectPackages(cached.packageList);
                  }
                  if (cached.assetInventory) {
                    state.assetInventory = cached.assetInventory;
                    renderAssetInventory(cached.assetInventory, state.assetInventoryExpanded);
                  }
                  if (cached.iterationPlan !== undefined) {
                    state.iterationPlans = normalizeIterationPlanRounds(Array.isArray(cached.iterationPlans) ? cached.iterationPlans : []);
                    state.selectedIterationSessionId = cached.selectedIterationSessionId || "";
                    state.iterationPlan = cached.iterationPlan;
                    if (state.iterationPlans.length) {
                      state.iterationPlan = selectIterationPlanForDisplay(state.iterationPlans);
                    }
                    state.iterationPlanEvaluation = cached.iterationPlan?.latestEvaluation || cached.iterationPlanEvaluation || null;
                    state.iterationPlanFailure = cached.iterationPlanFailure || "";
                    renderIterationPlan();
                  }
                  if (cached.repairPlan !== undefined) {
                    state.repairPlan = cached.repairPlan;
                    renderRepairPlan();
                  }
                  if (cached.gddOutlineReady !== undefined && $("createGddDocument")) {
                    state.gddOutlineReady = !!cached.gddOutlineReady;
                    $("createGddDocument").textContent = state.gddOutlineReady ? "\u67e5\u9605\u7b56\u5212\u5927\u7eb2" : "\u521b\u5efa\u7b56\u5212\u5927\u7eb2";
                  }
                  callV2("v2RenderProgress");
                }

                function hasInitializingProject(projects) {
                  return projects.some(p => p.bootstrapStatus === "running");
                }

                function failedProject(projects) {
                  return projects.find(p => p.bootstrapStatus === "failed");
                }

                function isProjectReady(project) {
                  return String(project?.bootstrapStatus || "").toLowerCase() === "succeeded";
                }

                function isProjectPendingInitialization(project) {
                  const status = String(project?.bootstrapStatus || "").toLowerCase();
                  return status === "initial" || status === "running";
                }

                function listableProjects(projects) {
                  return projects.filter(isProjectReady);
                }

                function showCreationFailure(error) {
                  showCreateProjectPage();
                  state.projectId = "";
                  writeSelectedProjectId("");
                  $("adminPanel").classList.remove("hidden");
                  $("projectDetailPanel").classList.add("hidden");
                  $("chatPanel").classList.add("hidden");
                  $("initStatusPanel").classList.remove("hidden");
                  $("initStatusText").innerHTML = `<strong class="danger">创建失败。</strong><br>${escapeHtml(sanitizePublicFailureContent(error || "初始化失败，失败项目已自动清理。"))}`;
                  callV2("v2RenderLeftProjectList");
                }



                async function sendChat() {
                  if (!state.projectId) return out("请先选择一个项目。");
                  const message = $("chatMessage").value.trim();
                  if (!message) return out("请输入消息。");
                  $("sendChat").disabled = true;
                  $("sendChat").textContent = "发送中...";
                  let shouldClearChatAttachments = false;
                  try {
                    let routeIntent = null;
                    if (state.projectAnalysisMode) {
                      try {
                        routeIntent = await api(`/api/projects/${state.projectId}/workflow-route/intent`, {
                          method: "POST",
                          timeoutMs: 90 * 1000,
                          body: JSON.stringify({ message, model: $("globalModel").value || null })
                        });
                      } catch {
                        routeIntent = null;
                      }
                    }
                    if (routeIntent?.shouldRoute) {
                      state.chatHistory.push({ role: "user", content: message });
                      renderChatHistory();
                      saveChatHistoryForProject();
                      $("chatMessage").value = "";
                      await queryWorkflowRoute(routeIntent);
                      return;
                    }
                    invalidateWorkflowRouteAction();
                    shouldClearChatAttachments = true;
                    const payload = {
                      message,
                      model: $("globalModel").value || null,
                      skillActionId: $("chatSkillMode").value || "normal",
                      attachments: currentChatAttachmentsForRun(),
                      history: recentChatHistoryForLlm()
                    };
                    state.chatHistory.push({ role: "user", content: message });
                    renderChatHistory();
                    saveChatHistoryForProject();
                    $("chatMessage").value = "";
                    const thinking = startChatThinkingMessage();
                    const result = await api(`/api/projects/${state.projectId}/chat`, { method: "POST", body: JSON.stringify(payload) });
                    if (result.assistantMessage) {
                      thinking.complete(result.assistantMessage);
                    } else {
                      thinking.complete("本次没有生成回复。");
                    }
                    await loadServerChatHistoryForProject(state.projectId);
                    out(result);
                    await loadRuns();
                  } catch (error) {
                    const message = error?.payload?.failureCode || error?.payload?.error || "unknown_error";
                    const pending = state.chatHistory.find(item => item.pending);
                    if (pending) {
                      pending.content = `本次回复失败：${message}。可以稍后重试。`;
                      pending.pending = false;
                      delete pending.pendingId;
                      renderChatHistory();
                      saveChatHistoryForProject();
                    }
                    showError(error);
                  }
                  finally {
                    if (shouldClearChatAttachments) clearChatAttachments();
                    $("sendChat").disabled = false;
                    $("sendChat").textContent = "发送";
                    await refreshActiveRun();
                  }
                }

                async function refreshGddOutlineStatus() {
                  if (!state.projectId || !$("createGddDocument")) return;
                  try {
                    const outlineStatus = await api(`/api/projects/${state.projectId}/gdd/outline`);
                    state.gddOutlineReady = Array.isArray(outlineStatus?.sections) && outlineStatus.sections.length > 0;
                  } catch {
                    state.gddOutlineReady = false;
                  }
                  writeProjectStateCache({ gddOutlineReady: state.gddOutlineReady });
                  $("createGddDocument").textContent = state.gddOutlineReady ? "\u67e5\u9605\u7b56\u5212\u5927\u7eb2" : "\u521b\u5efa\u7b56\u5212\u5927\u7eb2";
                }


                function v2OpenGddOutlineTab() {
                  if (!state.projectId) return out("请先选择一个项目。");
                  if (typeof v2OpenEmbeddedTab === "function") {
                    v2OpenEmbeddedTab(
                      "gdd-outline",
                      "查阅策划大纲",
                      "v2GddOutlineFramePanel",
                      "v2GddOutlineFrame",
                      `/gdd-outline?projectId=${encodeURIComponent(state.projectId)}&embedded=1`);
                  } else {
                    window.open(`/gdd-outline?projectId=${encodeURIComponent(state.projectId)}`, "_blank", "noreferrer");
                  }
                }

                async function createGddDocument() {
                  if (!state.projectId) return out("请先选择一个项目。");
                  if (state.gddOutlineReady) {
                    callV2("v2OpenGddOutlineTab");
                    return;
                  }
                  if (!guardGlobalAction()) return;
                  const message = $("chatMessage").value.trim();
                  const button = $("createGddDocument");
                  setLocalBusy(true, "\u6b63\u5728\u521b\u5efa\u7b56\u5212\u5927\u7eb2\uff0c\u8bf7\u7b49\u5f85\u5f53\u524d\u4efb\u52a1\u6267\u884c\u5b8c\u6bd5\u3002");
                  button.disabled = true;
                  button.textContent = "创建中...";
                  try {
                    const payload = {
                      message,
                      model: $("globalModel").value || null,
                      attachments: currentChatAttachmentsForRun()
                    };
                    const result = await api(`/api/projects/${state.projectId}/gdd`, { method: "POST", body: JSON.stringify(payload) });
                    await loadServerChatHistoryForProject(state.projectId);
                    state.chatHistory.push({
                      role: "assistant",
                      kind: "gdd-result",
                      content: result.summary || "\u7b56\u5212\u5927\u7eb2\u5df2\u521b\u5efa\u3002",
                      gddOutlineUrl: result.downloadUrl || ""
                    });
                    renderChatHistory();
                    saveChatHistoryForProject();
                    state.gddOutlineReady = true;
                    button.textContent = "\u67e5\u9605\u7b56\u5212\u5927\u7eb2";
                    out(result.summary || "\u7b56\u5212\u5927\u7eb2\u5df2\u521b\u5efa\u3002");
                    await loadRuns();
                    await loadProjectPackages();
                  } catch (error) {
                    const failureMessage = sanitizePublicChatContent(error?.payload?.summary || error?.payload?.error || error?.payload?.failureCode || "\u521b\u5efa\u7b56\u5212\u5927\u7eb2\u5931\u8d25\u3002");
                    state.chatHistory.push({
                      role: "assistant",
                      kind: "gdd-result",
                      content: failureMessage
                    });
                    renderChatHistory();
                    saveChatHistoryForProject();
                    out(failureMessage);
                    await loadServerChatHistoryForProject(state.projectId).catch(() => {});
                    showError(error);
                  } finally {
                    clearChatAttachments();
                    setLocalBusy(false);
                    button.disabled = false;
                    button.textContent = state.gddOutlineReady ? "\u67e5\u9605\u7b56\u5212\u5927\u7eb2" : "\u521b\u5efa\u7b56\u5212\u5927\u7eb2";
                    await refreshActiveRun();
                  }
                }

                function chatHistoryDownloadFileName() {
                  const project = state.projects.find(item => item.projectId === state.projectId);
                  const base = (project?.name || project?.gameName || state.projectId || "chat-history")
                    .replace(/[^\p{L}\p{N}._-]+/gu, "-")
                    .replace(/^-+|-+$/g, "") || "chat-history";
                  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
                  return `${base}-chat-history-${stamp}.json`;
                }

                async function downloadChatHistory() {
                  if (!state.projectId) return out("请先选择一个项目。");
                  const button = $("downloadChatHistory");
                  const originalText = button.textContent;
                  button.disabled = true;
                  button.textContent = "下载中...";
                  try {
                    const result = await api(`/api/projects/${state.projectId}/chat-history`);
                    const messages = (result.messages || [])
                      .map(message => ({
                        role: message.role,
                        content: sanitizePublicChatContent(message.content),
                        kind: message.kind || null,
                        createdUtc: message.createdUtc || null,
                        continueConsumed: !!message.continueConsumed,
                        suggestedFeedback: sanitizePublicChatContent(message.suggestedFeedback || "")
                      }))
                      .filter(isStoredChatMessage);
                    const payload = {
                      projectId: state.projectId,
                      exportedAt: new Date().toISOString(),
                      messageCount: messages.length,
                      messages
                    };
                    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json;charset=utf-8" });
                    const url = URL.createObjectURL(blob);
                    const anchor = document.createElement("a");
                    anchor.href = url;
                    anchor.download = chatHistoryDownloadFileName();
                    document.body.appendChild(anchor);
                    anchor.click();
                    anchor.remove();
                    URL.revokeObjectURL(url);
                    out("记录已下载。");
                  } catch (error) {
                    showError(error);
                  } finally {
                    button.disabled = false;
                    button.textContent = originalText;
                  }
                }

                async function syncChatHistory() {
                  if (!state.projectId) return out("请先选择一个项目。");
                  const button = $("syncChatHistory");
                  const originalText = button.textContent;
                  button.disabled = true;
                  button.textContent = "同步中...";
                  try {
                    await loadServerChatHistoryForProject(state.projectId);
                    out("服务器聊天记录已同步。");
                  } catch (error) {
                    showError(error);
                  } finally {
                    button.disabled = false;
                    button.textContent = originalText;
                  }
                }

                async function createUserAccount() {
                  if (!guardGlobalAction()) return;
                  const username = $("newUsername").value.trim();
                  const projectLimit = Number($("newUserProjectLimit").value || "2");
                  const validDaysRaw = $("newUserValidDays").value.trim();
                  const spendLimitRaw = $("newUserSpendLimitCny").value.trim();
                  const validDays = validDaysRaw ? Number(validDaysRaw) : null;
                  const spendLimitCny = spendLimitRaw ? Number(spendLimitRaw) : null;
                  if (!username) return out("Username is required.");
                  if (!Number.isFinite(projectLimit) || projectLimit < 1) return out("Project limit must be greater than zero.");
                  if (validDays !== null && (!Number.isFinite(validDays) || validDays < 1)) return out("User valid days must be blank or greater than zero.");
                  if (spendLimitCny !== null && (!Number.isFinite(spendLimitCny) || spendLimitCny < 0)) return out("User spend limit must be blank or non-negative.");
                  setLocalBusy(true);
                  $("createUserAccount").disabled = true;
                  $("createUserAccount").textContent = "Creating...";
                  try {
                    const result = await api("/api/admin/users", {
                      method: "POST",
                      body: JSON.stringify({ username, projectLimit, validDays, spendLimitCny })
                    });
                    $("createUserAccountResult").className = "card";
                    $("createUserAccountResult").innerHTML = `
                      <strong>User created</strong>
                      <p>username: ${escapeHtml(result.username)}</p>
                      <p>accountId: ${escapeHtml(result.accountId)}</p>
                      <p>projectLimit: ${escapeHtml(result.projectLimit)}</p>
                      <p>validUntilUtc: ${escapeHtml(result.validUntilUtc || "no expiry")}</p>
                      <p>spendLimitCny: ${escapeHtml(result.spendLimitCny ?? "no limit")}</p>
                      <p>assignedAiCodeMirrorKey: ${escapeHtml(result.aiCodeMirrorKeyName || "")}</p>
                      <p>token: <code>${escapeHtml(result.token)}</code></p>
                    `;
                    showOneTimeTokenDialog("User token created", result);
                    out(result);
                    await loadUserAccounts();
                  } catch (error) {
                    $("createUserAccountResult").className = "card danger";
                    $("createUserAccountResult").textContent = error?.payload?.error || "create_user_failed";
                    showError(error);
                  } finally {
                    setLocalBusy(false);
                    $("createUserAccount").disabled = false;
                    $("createUserAccount").textContent = "Create user token";
                    await refreshActiveRun();
                  }
                }

                async function loadUserAccounts() {
                  if (state.role !== "admin") return;
                  try {
                    const [result, usage] = await Promise.all([
                      api("/api/admin/users"),
                      api("/api/admin/llm-usage").catch(() => ({ accounts: [] }))
                    ]);
                    const users = result.users || [];
                    const usageByAccount = new Map((usage.accounts || []).map(item => [item.accountId, item]));
                    const runMetricUsers = users.filter(user => !user.isAdmin);
                    $("adminRunMetricsAccount").innerHTML = `<option value="">All users</option>${runMetricUsers.map(user => `<option value="${escapeHtml(user.accountId)}">${escapeHtml(user.username)}</option>`).join("")}`;
                    $("userAccounts").innerHTML = users.map(user => `
                      <div class="card">
                        <strong>${escapeHtml(user.username)}${user.isAdmin ? " · admin" : ""}${user.isDisabled ? " · disabled" : ""}</strong>
                        <p class="muted">accountId: ${escapeHtml(user.accountId)}</p>
                        <p class="muted">projects: ${escapeHtml(user.projectCount)} / ${escapeHtml(user.projectLimit)}</p>
                        <p class="muted">validUntilUtc: ${escapeHtml(user.validUntilUtc || "no expiry")} · spendLimitCny: ${escapeHtml(user.spendLimitCny ?? "no limit")}</p>
                        ${renderUserLlmUsage(user, usageByAccount.get(user.accountId))}
                        <p class="muted">AiCodeMirror key: ${escapeHtml(user.aiCodeMirrorKeyName || "not assigned")}</p>
                        <p class="muted">created: ${escapeHtml(user.createdUtc)}</p>
                        ${user.isAdmin ? "" : `
                          <div class="split-actions">
                            <input data-user-valid-days="${escapeHtml(user.accountId)}" type="number" min="1" placeholder="valid days">
                            <input data-user-spend-limit="${escapeHtml(user.accountId)}" type="number" min="0" step="0.01" placeholder="spend CNY">
                            <button class="ghost" data-user-limits="${escapeHtml(user.accountId)}">Update limits</button>
                          </div>
                          <div class="split-actions">
                            <button class="ghost" data-user-status="${escapeHtml(user.accountId)}" data-disabled="${user.isDisabled ? "false" : "true"}">${user.isDisabled ? "Enable user" : "Disable user"}</button>
                            <button class="secondary" data-user-rotate="${escapeHtml(user.accountId)}">Rotate token</button>
                          </div>
                        `}
                      </div>
                    `).join("") || "<p class='muted'>No users.</p>";
                    document.querySelectorAll("[data-user-status]").forEach(button => {
                      button.onclick = () => updateUserStatus(button.dataset.userStatus, button.dataset.disabled === "true");
                    });
                    document.querySelectorAll("[data-user-rotate]").forEach(button => {
                      button.onclick = () => rotateUserToken(button.dataset.userRotate);
                    });
                    document.querySelectorAll("[data-user-limits]").forEach(button => {
                      button.onclick = () => updateUserLimits(button.dataset.userLimits);
                    });
                  } catch (error) {
                    $("userAccounts").innerHTML = "<p class='danger'>Failed to load users.</p>";
                  }
                }

                function renderUserLlmUsage(user, usage) {
                  const callCount = Number(usage?.callCount || 0);
                  const cost = Number(usage?.estimatedCostCny || 0);
                  const limitRaw = user.spendLimitCny;
                  const hasLimit = limitRaw !== null && limitRaw !== undefined && limitRaw !== "";
                  const limit = hasLimit ? Number(limitRaw) : null;
                  const remaining = hasLimit && Number.isFinite(limit) ? Math.max(0, limit - cost) : null;
                  const overLimit = hasLimit && Number.isFinite(limit) && cost >= limit;
                  return `
                    <p class="${overLimit ? "danger" : "muted"}">today LLM: ${escapeHtml(callCount)} calls / CNY ${escapeHtml(cost.toFixed(4))}</p>
                    <p class="muted">today remaining: ${escapeHtml(remaining === null ? "no limit" : `CNY ${remaining.toFixed(4)}`)}</p>
                  `;
                }

                async function loadLlmBinding() {
                  if (!state.authenticated) return;
                  try {
                    const binding = await api("/api/account/llm-binding");
                    $("llmGatewayBaseUrl").value = binding.gatewayBaseUrl || "";
                    $("llmExternalAccountRef").value = binding.externalAccountRef || "";
                    $("llmTokenRef").value = binding.tokenRef || "";
                    $("llmBindingStatus").className = "card";
                    $("llmBindingStatus").innerHTML = `
                      <strong>Account LLM binding loaded</strong>
                      <p>provider: ${escapeHtml(binding.gatewayProvider || "")}</p>
                      <p>baseUrl: ${escapeHtml(binding.gatewayBaseUrl || "")}</p>
                      <p>externalAccountRef: ${escapeHtml(binding.externalAccountRef || "")}</p>
                      <p>tokenRef: ${escapeHtml(binding.tokenRef || "")}</p>
                    `;
                  } catch (error) {
                    $("llmBindingStatus").className = "card muted";
                    $("llmBindingStatus").textContent = "No account LLM binding configured.";
                  }
                }

                async function saveLlmBinding() {
                  if (!guardGlobalAction()) return;
                  setLocalBusy(true);
                  $("saveLlmBinding").disabled = true;
                  $("saveLlmBinding").textContent = "Saving...";
                  try {
                    const result = await api("/api/account/llm-binding", {
                      method: "POST",
                      body: JSON.stringify({
                        gatewayProvider: "new-api",
                        gatewayBaseUrl: $("llmGatewayBaseUrl").value.trim(),
                        externalAccountRef: $("llmExternalAccountRef").value.trim(),
                        tokenRef: $("llmTokenRef").value.trim()
                      })
                    });
                    $("llmBindingStatus").className = "card";
                    $("llmBindingStatus").textContent = "Account LLM binding saved.";
                    out(result);
                    await loadLlmBinding();
                  } catch (error) {
                    $("llmBindingStatus").className = "card danger";
                    $("llmBindingStatus").textContent = error?.payload?.failureCode || error?.payload?.error || "llm_binding_failed";
                    showError(error);
                  } finally {
                    setLocalBusy(false);
                    $("saveLlmBinding").disabled = false;
                    $("saveLlmBinding").textContent = "Save account LLM binding";
                  }
                }

                async function loadLlmUsage() {
                  if (!state.authenticated) return;
                  try {
                    const usage = await api("/api/account/llm-usage");
                    const runs = usage.recentRuns || [];
                    $("llmUsageStatus").className = "card";
                    $("llmUsageStatus").innerHTML = `
                      <strong>Today: ${escapeHtml(usage.callCount)} LLM calls · CNY ${escapeHtml(usage.estimatedCostCny)}</strong>
                      <p class="muted">UTC day: ${escapeHtml(usage.utcDay)}</p>
                      <div class="card-list">
                        ${runs.slice(0, 5).map(run => `
                          <div class="card">
                            <strong>${escapeHtml(run.runType)} · ${escapeHtml(run.status)}</strong>
                            <p class="muted">model: ${escapeHtml(run.llmModel || "")}</p>
                            <p class="muted">gateway: ${escapeHtml(run.llmGateway || "")}</p>
                            <p class="muted">${escapeHtml(run.llmCostJson || "")}</p>
                          </div>
                        `).join("") || "<p class='muted'>No LLM runs today.</p>"}
                      </div>
                    `;
                  } catch (error) {
                    $("llmUsageStatus").className = "card danger";
                    $("llmUsageStatus").textContent = error?.payload?.error || "llm_usage_load_failed";
                  }
                }

                async function loadAdminLlmUsage() {
                  if (state.role !== "admin") return;
                  try {
                    const usage = await api("/api/admin/llm-usage");
                    const accounts = usage.accounts || [];
                    $("adminLlmUsageStatus").className = "card";
                    $("adminLlmUsageStatus").innerHTML = `
                      <strong>All accounts today: ${escapeHtml(usage.callCount)} LLM calls · CNY ${escapeHtml(usage.estimatedCostCny)}</strong>
                      <p class="muted">accounts: ${escapeHtml(usage.accountCount)} · UTC day: ${escapeHtml(usage.utcDay)}</p>
                      <div class="card-list">
                        ${accounts.map(account => `
                          <div class="card">
                            <strong>${escapeHtml(account.username)}${account.isAdmin ? " · admin" : ""}${account.isDisabled ? " · disabled" : ""}</strong>
                            <p class="muted">projects: ${escapeHtml(account.projectCount)}</p>
                            <p class="muted">calls: ${escapeHtml(account.callCount)} · CNY ${escapeHtml(account.estimatedCostCny)}</p>
                          </div>
                        `).join("") || "<p class='muted'>No accounts.</p>"}
                      </div>
                    `;
                  } catch (error) {
                    $("adminLlmUsageStatus").className = "card danger";
                    $("adminLlmUsageStatus").textContent = error?.payload?.error || "admin_llm_usage_load_failed";
                  }
                }

                async function loadAdminLlmUsageAggregate() {
                  if (state.role !== "admin") return;
                  const grain = $("adminLlmUsageGrain").value || "day";
                  const split = $("adminLlmUsageSplit").value || "account";
                  window.open(`/admin/llm-usage?grain=${encodeURIComponent(grain)}&split=${encodeURIComponent(split)}`, "_blank", "noreferrer");
                }

                function openAdminRunDurationMetrics() {
                  if (state.role !== "admin") return;
                  location.href = "/admin/run-duration-metrics";
                }

                function openAdminChatAverageMetrics() {
                  if (state.role !== "admin") return;
                  location.href = "/admin/chat-average-metrics";
                }

                async function downloadAdminLlmUsageCsv() {
                  if (state.role !== "admin") return;
                  try {
                    const response = await fetch("/api/admin/llm-usage.csv", {
                      headers: { "Authorization": `Bearer ${token()}` },
                      cache: "no-store"
                    });
                    if (!response.ok) {
                      throw { status: response.status, payload: { error: "admin_llm_usage_csv_failed" } };
                    }

                    const blob = await response.blob();
                    const url = URL.createObjectURL(blob);
                    const anchor = document.createElement("a");
                    anchor.href = url;
                    anchor.download = "admin-llm-usage.csv";
                    document.body.appendChild(anchor);
                    anchor.click();
                    anchor.remove();
                    URL.revokeObjectURL(url);
                  } catch (error) {
                    showError(error);
                  }
                }

                async function loadAdminLlmRuns() {
                  if (state.role !== "admin") return;
                  try {
                    const audit = await api("/api/admin/llm-runs?limit=50");
                    const runs = audit.runs || [];
                    $("adminLlmRunsStatus").className = "card";
                    $("adminLlmRunsStatus").innerHTML = `
                      <strong>Recent LLM runs: ${escapeHtml(audit.count)}</strong>
                      <div class="card-list">
                        ${runs.map(run => `
                          <div class="card">
                            <strong>${escapeHtml(run.username)} · ${escapeHtml(run.runType)} · ${escapeHtml(run.status)}</strong>
                            <p class="muted">projectId: ${escapeHtml(run.projectId)}</p>
                            <p class="muted">runId: ${escapeHtml(run.runId)}</p>
                            <p class="muted">model: ${escapeHtml(run.llmModel || "")} · gateway: ${escapeHtml(run.llmGateway || "")}</p>
                            <p class="muted">requestId: ${escapeHtml(run.llmRequestId || "")}</p>
                            <p class="muted">${escapeHtml(run.llmCostJson || "")}</p>
                          </div>
                        `).join("") || "<p class='muted'>No LLM runs.</p>"}
                      </div>
                    `;
                  } catch (error) {
                    $("adminLlmRunsStatus").className = "card danger";
                    $("adminLlmRunsStatus").textContent = error?.payload?.error || "admin_llm_runs_load_failed";
                  }
                }

                function formatMetricSeconds(value) {
                  if (value === null || value === undefined || value === "") return "-";
                  const number = Number(value);
                  if (!Number.isFinite(number)) return "-";
                  return `${number.toFixed(number >= 10 ? 1 : 3)}s`;
                }

                async function loadAdminRunMetrics(view = "runs") {
                  if (state.role !== "admin") return;
                  try {
                    const query = new URLSearchParams();
                    const accountId = $("adminRunMetricsAccount").value || "";
                    const runType = view === "chat" ? "prototype-chat" : $("adminRunMetricsType").value.trim();
                    if (accountId) query.set("accountId", accountId);
                    if (runType) query.set("runType", runType);
                    query.set("limit", "500");
                    const metrics = await api(`/api/admin/run-metrics?${query}`);
                    const runs = metrics.runs || [];
                    const chats = metrics.chatAverages || [];
                    const chatRuns = metrics.chatRuns || [];
                    const assetRuns = metrics.assetRuns || [];
                    const isChatView = view === "chat";
                    $("adminRunMetricsStatus").className = "card";
                    $("adminRunMetricsStatus").innerHTML = isChatView ? `
                      <strong>每个普通用户的聊天平均响应时长</strong>
                      <p class="muted">最近聊天记录：${escapeHtml(chatRuns.length)} 条</p>
                      <div class="card-list">
                        ${chats.map(item => `
                          <div class="card">
                            <strong>${escapeHtml(item.username)} · ${escapeHtml(item.runCount)} chat runs</strong>
                            <p class="muted">平均排队: ${escapeHtml(formatMetricSeconds(item.averageQueueSeconds))} · 平均响应: ${escapeHtml(formatMetricSeconds(item.averageRuntimeSeconds))}</p>
                          </div>
                        `).join("") || "<p class='muted'>没有匹配的聊天 run。</p>"}
                      </div>
                    ` : `
                      <strong>普通用户 run 花费时间记录：${escapeHtml(metrics.count || 0)} 条普通 run · ${escapeHtml(assetRuns.length)} 条素材生成 run</strong>
                      <div class="card-list">
                        ${[...runs, ...assetRuns].map(run => `
                          <div class="card">
                            <strong>${escapeHtml(run.username)} · ${escapeHtml(run.runType)} · ${escapeHtml(run.status)}</strong>
                            <p class="muted">project: ${escapeHtml(run.projectName || run.projectId)} · ${escapeHtml(run.gameName || "")}</p>
                            <p class="muted">runId: ${escapeHtml(run.runId)}</p>
                            <p class="muted">排队: ${escapeHtml(formatMetricSeconds(run.queueSeconds))} · 运行: ${escapeHtml(formatMetricSeconds(run.runtimeSeconds))} · 启动时队列序号: ${escapeHtml(run.queuePositionAtStart ?? "-")}</p>
                            <p class="muted">created: ${escapeHtml(run.createdUtc)} · started: ${escapeHtml(run.startedUtc || "")} · finished: ${escapeHtml(run.finishedUtc || "")}</p>
                          </div>
                        `).join("") || "<p class='muted'>没有匹配的非聊天 run。</p>"}
                      </div>
                    `;
                  } catch (error) {
                    $("adminRunMetricsStatus").className = "card danger";
                    $("adminRunMetricsStatus").textContent = error?.payload?.error || "admin_run_metrics_load_failed";
                  }
                }

                async function loadAccountAudit() {
                  if (state.role !== "admin") return;
                  try {
                    const result = await api("/api/admin/account-audit?limit=50&offset=0");
                    const events = result.events || [];
                    $("accountAuditStatus").className = "card";
                    $("accountAuditStatus").innerHTML = `
                      <strong>Recent account audit events: ${escapeHtml(events.length)}</strong>
                      <div class="card-list">
                        ${events.map(event => `
                          <div class="card">
                            <strong>${escapeHtml(event.action)} · ${escapeHtml(event.createdUtc)}</strong>
                            <p class="muted">actor: ${escapeHtml(event.actorAccountId)}</p>
                            <p class="muted">target: ${escapeHtml(event.targetAccountId || "")}</p>
                            <p class="muted">${escapeHtml(event.metadataJson || "{}")}</p>
                          </div>
                        `).join("") || "<p class='muted'>No account audit events.</p>"}
                      </div>
                    `;
                  } catch (error) {
                    $("accountAuditStatus").className = "card danger";
                    $("accountAuditStatus").textContent = error?.payload?.error || "account_audit_load_failed";
                  }
                }

                async function downloadAccountAuditCsv() {
                  if (state.role !== "admin") return;
                  try {
                    const response = await fetch("/api/admin/account-audit.csv?limit=500&offset=0", {
                      headers: { "Authorization": `Bearer ${token()}` },
                      cache: "no-store"
                    });
                    if (!response.ok) {
                      throw { status: response.status, payload: { error: "account_audit_csv_failed" } };
                    }

                    const blob = await response.blob();
                    const url = URL.createObjectURL(blob);
                    const anchor = document.createElement("a");
                    anchor.href = url;
                    anchor.download = "admin-account-audit.csv";
                    document.body.appendChild(anchor);
                    anchor.click();
                    anchor.remove();
                    URL.revokeObjectURL(url);
                  } catch (error) {
                    showError(error);
                  }
                }

                async function updateUserStatus(accountId, disabled) {
                  if (!guardGlobalAction()) return;
                  setLocalBusy(true);
                  try {
                    const result = await api(`/api/admin/users/${encodeURIComponent(accountId)}/status`, {
                      method: "POST",
                      body: JSON.stringify({ disabled })
                    });
                    $("createUserAccountResult").className = "card";
                    $("createUserAccountResult").textContent = disabled ? "User disabled." : "User enabled.";
                    out(result);
                    await loadUserAccounts();
                  } catch (error) {
                    showError(error);
                  } finally {
                    setLocalBusy(false);
                  }
                }

                async function rotateUserToken(accountId) {
                  if (!guardGlobalAction()) return;
                  setLocalBusy(true);
                  try {
                    const result = await api(`/api/admin/users/${encodeURIComponent(accountId)}/rotate-token`, { method: "POST" });
                    $("createUserAccountResult").className = "card";
                    $("createUserAccountResult").innerHTML = `
                      <strong>User token rotated</strong>
                      <p>username: ${escapeHtml(result.username)}</p>
                      <p>accountId: ${escapeHtml(result.accountId)}</p>
                      <p>token: <code>${escapeHtml(result.token)}</code></p>
                    `;
                    showOneTimeTokenDialog("User token rotated", result);
                    out(result);
                    await loadUserAccounts();
                  } catch (error) {
                    showError(error);
                  } finally {
                    setLocalBusy(false);
                  }
                }

                function showOneTimeTokenDialog(title, result) {
                  $("oneTimeTokenTitle").textContent = title || "One-time token";
                  $("oneTimeTokenMeta").textContent = `username: ${result.username || ""} | accountId: ${result.accountId || ""} | plaintext is shown once`;
                  $("oneTimeTokenValue").value = result.token || "";
                  $("oneTimeTokenCopyStatus").textContent = "Save this token now. After closing, the system cannot recover plaintext token from the database.";
                  $("oneTimeTokenModal").classList.remove("hidden");
                  $("oneTimeTokenValue").focus();
                  $("oneTimeTokenValue").select();
                }

                async function updateUserLimits(accountId) {
                  if (!guardGlobalAction()) return;
                  const validInput = document.querySelector(`[data-user-valid-days="${CSS.escape(accountId)}"]`);
                  const spendInput = document.querySelector(`[data-user-spend-limit="${CSS.escape(accountId)}"]`);
                  const validDaysRaw = validInput?.value?.trim() || "";
                  const spendLimitRaw = spendInput?.value?.trim() || "";
                  const validDays = validDaysRaw ? Number(validDaysRaw) : null;
                  const spendLimitCny = spendLimitRaw ? Number(spendLimitRaw) : null;
                  if (validDays !== null && (!Number.isFinite(validDays) || validDays < 1)) return out("Valid days must be blank or greater than zero.");
                  if (spendLimitCny !== null && (!Number.isFinite(spendLimitCny) || spendLimitCny < 0)) return out("Spend limit must be blank or non-negative.");
                  setLocalBusy(true);
                  try {
                    const result = await api(`/api/admin/users/${encodeURIComponent(accountId)}/limits`, {
                      method: "POST",
                      body: JSON.stringify({ validDays, spendLimitCny })
                    });
                    $("createUserAccountResult").className = "card";
                    $("createUserAccountResult").textContent = "User limits updated.";
                    out(result);
                    await loadUserAccounts();
                  } catch (error) {
                    showError(error);
                  } finally {
                    setLocalBusy(false);
                  }
                }

                async function loadAiCodeMirrorKeys() {
                  if (state.role !== "admin") return;
                  try {
                    const result = await api("/api/admin/aicodemirror-keys");
                    const keys = result.keys || [];
                    $("aicodemirrorKeyPool").innerHTML = keys.map(key => `
                      <div class="card">
                        <strong>${escapeHtml(key.keyName)} · ${escapeHtml(key.status)}</strong>
                        <p class="muted">accountId: ${escapeHtml(key.accountId || "unassigned")}</p>
                        <p class="muted">validDays: ${escapeHtml(key.validDays ?? "unlimited")} · expiresUtc: ${escapeHtml(key.expiresUtc || "no expiry")}</p>
                        <p class="muted">credentialImported: ${escapeHtml(key.credentialImported ? "yes" : "no")}</p>
                        <p>${escapeHtml(key.notes || "")}</p>
                      </div>
                    `).join("") || "<p class='muted'>No AiCodeMirror keys imported.</p>";
                  } catch (error) {
                    $("aicodemirrorKeyPool").innerHTML = "<p class='danger'>Failed to load AiCodeMirror keys.</p>";
                  }
                }

                async function importAiCodeMirrorKeyCsv() {
                  if (!guardGlobalAction()) return;
                  const file = $("aicodemirrorKeyCsv").files?.[0];
                  if (!file) return out("Please choose a CSV file first.");
                  setLocalBusy(true);
                  $("importAiCodeMirrorKeyCsv").disabled = true;
                  $("importAiCodeMirrorKeyCsv").textContent = "Importing...";
                  try {
                    const csv = await file.text();
                    const response = await fetch("/api/admin/aicodemirror-keys/import-csv", {
                      method: "POST",
                      headers: { "Authorization": `Bearer ${token()}`, "Content-Type": "text/csv; charset=utf-8" },
                      body: csv,
                      cache: "no-store"
                    });
                    const result = await response.json();
                    if (!response.ok && response.status !== 207) throw { status: response.status, payload: result };
                    $("aicodemirrorKeyImportResult").className = result.errors?.length ? "card danger" : "card";
                    $("aicodemirrorKeyImportResult").innerHTML = `<strong>Imported: ${escapeHtml(result.imported || 0)}</strong><p>${escapeHtml((result.errors || []).join("; ") || "ok")}</p>`;
                    out(result);
                    await loadAiCodeMirrorKeys();
                  } catch (error) {
                    $("aicodemirrorKeyImportResult").className = "card danger";
                    $("aicodemirrorKeyImportResult").textContent = error?.payload?.error || "aicodemirror_key_csv_import_failed";
                    showError(error);
                  } finally {
                    setLocalBusy(false);
                    $("importAiCodeMirrorKeyCsv").disabled = false;
                    $("importAiCodeMirrorKeyCsv").textContent = "Import key CSV";
                  }
                }

                async function downloadAiCodeMirrorKeyTemplate() {
                  const response = await fetch("/api/admin/aicodemirror-keys/template.csv", {
                    headers: { "Authorization": `Bearer ${token()}` },
                    cache: "no-store"
                  });
                  if (!response.ok) return out("Failed to download key CSV template.");
                  const blob = await response.blob();
                  const url = URL.createObjectURL(blob);
                  const anchor = document.createElement("a");
                  anchor.href = url;
                  anchor.download = "aicodemirror-key-template.csv";
                  document.body.appendChild(anchor);
                  anchor.click();
                  anchor.remove();
                  URL.revokeObjectURL(url);
                }

                async function submitFormalFeedback() {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("\u8bf7\u5148\u9009\u62e9\u4e00\u4e2a\u9879\u76ee\u3002");
                  if (!callV2("v2HasPrototypeSkeleton")) return out("请先运行并完成原型骨架创建，再提交正式反馈。自由对话仍可使用。");
                  const feedback = $("chatMessage").value.trim();
                  const goal = currentNeedsFixRouteGoal();
                  if (!feedback && !goal) return out("\u8bf7\u8f93\u5165\u8981\u6b63\u5f0f\u63d0\u4ea4\u7684\u53cd\u9988\u3002");
                  await submitNeedsFixRouteRequest({
                    feedback: feedback ? buildNeedsFixFeedbackForUserReport(goal, feedback) : buildNeedsFixFeedbackForGoal(goal),
                    goalId: goal?.goalId || null,
                    goalIndex: goal?.goalIndex || null
                  }, goal ? `Needs Fix 路由执行中 step ${String(goal.goalIndex || "")}...` : "Needs Fix 路由执行中...");
                }

                async function continueSuggestedFeedback(messageIndex) {
                  const message = state.chatHistory[messageIndex];
                  const suggestion = message?.suggestedFeedback || state.nextSuggestedFeedback;
                  if (isGlobalBusy()) return out("当前有任务正在执行，请等待完成后再试。");
                  if (!suggestion) return out("当前没有可继续执行的建议。");
                  if (message) {
                    message.continueConsumed = true;
                    renderChatHistory();
                    saveChatHistoryForProject();
                  }
                  const hasPendingPlan = state.iterationPlan?.session && Array.isArray(state.iterationPlan?.goals) && state.iterationPlan.goals.some(goal => goal.status === "pending");
                  if (suggestion === "__iteration_plan_evaluate__") {
                    await evaluateIterationPlan(true);
                    return;
                  }
                  if (suggestion === "__iteration_plan_execute_next__") {
                    if (!hasPendingPlan) return out("当前没有可继续执行的目标。");
                    await executeIterationGoal();
                    return;
                  }
                  if (hasPendingPlan && currentIterationPlanDecision() === "should_refine_plan") {
                    if (isIterationPlanStarted()) return out("当前游戏模块已经开始执行，不允许更新游戏模块。");
                    openIterationPlanUpdateModal("update", suggestion);
                    return;
                  }
                  if (hasPendingPlan) {
                    await executeIterationGoal();
                    return;
                  }
                  await submitIterationPlanFromFeedback(suggestion, "正在生成游戏模块...", "completion_suggestion");
                }

                async function submitFormalFeedbackText(feedback, busyText) {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("\u8bf7\u5148\u9009\u62e9\u4e00\u4e2a\u9879\u76ee\u3002");
                  if (!state.prototypeReadyForFeedback) return out("请先运行并完成原型骨架创建，再提交正式反馈。自由对话仍可使用。");
                  setLocalBusy(true);
                  $("submitFormalFeedback").disabled = true;
                  $("submitFormalFeedback").textContent = busyText || "\u6b63\u5f0f\u63d0\u4ea4\u4e2d...";
                  try {
                    $("chatMessage").value = "";
                    const result = await api(`/api/projects/${state.projectId}/prototype-feedback-iterations`, {
                      method: "POST",
                      body: JSON.stringify({ feedback, model: $("globalModel").value, skillActionId: $("chatSkillMode").value || "normal" })
                    });
                    out(result);
                    await loadRuns();
                    updateContinueSuggestionFromText(result.assistantMessage);
                  } catch (error) {
                    const message = sanitizePublicChatContent(error?.payload?.assistantMessage || error?.payload?.error || "本轮正式反馈处理失败。");
                    out(message);
                    showError(error);
                  }
                  finally {
                    setLocalBusy(false);
                    setFormalFeedbackAvailability(state.prototypeReadyForFeedback);
                    await loadProjectPackages();
                    await refreshActiveRun();
                  }
                }

                function buildNeedsFixFeedbackForGoal(goal) {
                  if (!goal) return "";
                  const parts = [
                    `请通过 needs-fix 路由处理当前迭代目标 step ${String(goal.goalIndex || "").trim()}：${String(goal.title || "").trim()}`,
                    String(goal.description || "").trim(),
                    goal.acceptanceHint ? `本步验收提示：${String(goal.acceptanceHint || "").trim()}` : "",
                    "要求：由系统判断当前目标是否适合短修；只围绕当前 step 本身处理，不要推进后续目标。"
                  ].filter(Boolean);
                  return parts.join("\n");
                }

                async function runNeedsFixIterationGoal(goalIndex) {
                  $("iterationNeedsFixStatus").className = "card muted";
                  $("iterationNeedsFixStatus").textContent = `正在准备提交 step ${String(goalIndex || "").trim()} 的 Needs Fix 路由...`;
                  await refreshActiveRun();
                  if (isGlobalBusy()) {
                    $("iterationNeedsFixStatus").className = "card muted";
                    $("iterationNeedsFixStatus").textContent = "当前有任务正在执行，请等待当前 run 完成后再启动 Needs Fix 路由。";
                    return out("当前有任务正在执行，请等待当前 run 完成后再启动 Needs Fix 路由。");
                  }
                  const goals = Array.isArray(state.iterationPlan?.goals) ? state.iterationPlan.goals : [];
                  const goal = goals.find(item => String(item.goalIndex) === String(goalIndex));
                  if (!goal) {
                    $("iterationNeedsFixStatus").className = "card";
                    $("iterationNeedsFixStatus").textContent = "未找到需要 needs-fix 处理的目标，请刷新游戏模块后再试。";
                    return out("未找到需要 needs-fix 处理的目标。");
                  }
                  const feedback = buildNeedsFixFeedbackForGoal(goal);
                  if (!feedback) {
                    $("iterationNeedsFixStatus").className = "card";
                    $("iterationNeedsFixStatus").textContent = "当前目标缺少可用于 needs-fix 路由的内容。";
                    return out("当前目标缺少可用于 needs-fix 路由的内容。");
                  }
                  await submitNeedsFixRouteRequest({
                    feedback,
                    goalId: goal.goalId || "",
                    goalIndex: Number(goal.goalIndex || 0)
                  }, `Needs Fix 路由执行中 step ${String(goal.goalIndex)}...`);
                }

                async function submitNeedsFixRouteRequest(payload, busyText) {
                  if (!state.projectId) return out("\u8bf7\u5148\u9009\u62e9\u4e00\u4e2a\u9879\u76ee\u3002");
                  if (isGlobalBusy()) {
                    $("iterationNeedsFixStatus").className = "card muted";
                    $("iterationNeedsFixStatus").textContent = "当前有任务正在执行，请等待当前 run 完成后再启动 Needs Fix 路由。";
                    return out("当前有任务正在执行，请等待当前 run 完成后再启动 Needs Fix 路由。");
                  }
                  setLocalBusy(true);
                  $("iterationNeedsFixStatus").className = "card muted";
                  $("iterationNeedsFixStatus").textContent = busyText || "Needs Fix 路由已提交，正在等待后台 run 创建。";
                  $("submitFormalFeedback").disabled = true;
                  try {
                    const feedback = String(payload?.feedback || "").trim();
                    $("chatMessage").value = "";
                    const result = await api(`/api/projects/${state.projectId}/needs-fix-route`, {
                      method: "POST",
                      body: JSON.stringify({
                        feedback,
                        model: $("globalModel").value,
                        skillActionId: $("chatSkillMode").value || "normal",
                        goalId: payload?.goalId || null,
                        goalIndex: payload?.goalIndex || null
                      })
                    });
                    const routeStatus = String(result.status || "").trim().toLowerCase();
                    const goalStatus = String(result.iterationGoalStatus || "").trim().toLowerCase();
                    const needsMoreFix = goalStatus === "needs_fix" || goalStatus === "failed" || routeStatus === "needs_fix" || routeStatus === "failed";
                    out(result);
                    $("iterationNeedsFixStatus").className = needsMoreFix ? "card" : "card muted";
                    $("iterationNeedsFixStatus").textContent = result.summary || (needsMoreFix ? "Needs Fix 路由已执行，但当前 step 仍需继续修复。" : "Needs Fix 路由已完成。");
                    await loadRuns();
                    await loadIterationPlan();
                  } catch (error) {
                    const message = sanitizePublicChatContent(error?.payload?.summary || error?.payload?.error || "Needs fix route failed.");
                    $("iterationNeedsFixStatus").className = "card";
                    $("iterationNeedsFixStatus").textContent = message;
                    out(message);
                    showError(error);
                  }
                  finally {
                    setLocalBusy(false);
                    setFormalFeedbackAvailability(state.prototypeReadyForFeedback);
                    await refreshActiveRun();
                  }
                }

                async function loadSkillActions() {
                  if (!state.authenticated) return;
                  try {
                    const result = await api("/api/skill-actions");
                    state.skillActions = result.actions || [];
                    renderSkillActions();
                  } catch (error) {
                    state.skillActions = [];
                    renderSkillActions();
                  }
                }

                function renderSkillActions() {
                  const select = $("chatSkillMode");
                  const previous = select.value || "normal";
                  select.innerHTML = `<option value="normal">普通模式</option>` +
                    state.skillActions.map(action => `<option value="${escapeHtml(action.actionId)}">${escapeHtml(action.label)}</option>`).join("");
                  if (v2PendingProjectUiSkillMode && Array.from(select.options).some(option => option.value === v2PendingProjectUiSkillMode)) {
                    select.value = v2PendingProjectUiSkillMode;
                    v2PendingProjectUiSkillMode = "";
                  } else if (Array.from(select.options).some(option => option.value === previous)) {
                    select.value = previous;
                  }
                  renderSelectedSkillAction();
                }

                function renderSelectedSkillAction() {
                  const selected = $("chatSkillMode").value || "normal";
                  if (selected === "normal") {
                    $("chatSkillDescription").textContent = "不激活 skills，按通用 Phase A 原型顾问方式回答。";
                    callV2("v2RenderAdvancedPlanningMode");
                    return;
                  }
                  const action = state.skillActions.find(item => item.actionId === selected);
                  if (!action) {
                    $("chatSkillMode").value = "normal";
                    $("chatSkillDescription").textContent = "当前能力不可用，已回退为普通模式。";
                    callV2("v2RenderAdvancedPlanningMode");
                    return;
                  }
                  $("chatSkillDescription").textContent = action.description || "当前能力暂无说明。";
                  callV2("v2RenderAdvancedPlanningMode");
                }

                const longLlmTimeoutMs = 1200 * 1000;

                async function api(path, options = {}) {
                  const { timeoutMs, ...fetchOptions } = options;
                  const controller = timeoutMs ? new AbortController() : null;
                  const timeoutHandle = timeoutMs ? setTimeout(() => controller.abort(), timeoutMs) : null;
                  let response;
                  try {
                    response = await fetch(path, {
                      ...fetchOptions,
                      signal: controller?.signal,
                      headers: { ...headers(), ...(options.headers || {}) }
                    });
                  } catch (error) {
                    if (error?.name === "AbortError") {
                      throw { status: 408, payload: { status: "client_timeout", failureCode: "client_timeout", timeoutMs } };
                    }
                    throw error;
                  } finally {
                    if (timeoutHandle) clearTimeout(timeoutHandle);
                  }
                  const text = await response.text();
                  let payload = {};
                  try { payload = text ? JSON.parse(text) : {}; } catch { payload = { raw: text }; }
                  if (!response.ok) throw { status: response.status, payload };
                  return payload;
                }

                async function refreshProjects(options = {}) {
                  const autoSelect = options.autoSelect !== false;
                  let sessionValidated = false;
                  try {
                    const session = await api("/api/session");
                    sessionValidated = true;
                    showAdminShell(session.role || "user");
                    if ((session.role || "user") === "admin") {
                      state.projects = [];
                      closeUserModals();
                      out("Admin project creation and project list are disabled. Use Account Admin on the right.");
                      return;
                    }

                    const projects = await api("/api/projects");
                    state.projects = projects;
                    const initializing = hasInitializingProject(projects);
                    $("initStatusPanel").classList.toggle("hidden", !initializing);
                    if (initializing) {
                      $("initStatusText").textContent = "\u9879\u76ee\u521d\u59cb\u5316\u914d\u7f6e\u4e2d...\u521d\u59cb\u5316\u5b8c\u6210\u540e\u4f1a\u81ea\u52a8\u8fdb\u5165\u9879\u76ee\u8be6\u60c5\u9875\u3002";
                    }

                    const visibleProjects = listableProjects(projects);
                    const latestFailure = visibleProjects.length === 0 && !initializing ? await loadLatestProjectCreationFailure() : null;
                    const health = await loadProjectHealthSummary();
                    const sortedVisibleProjects = visibleProjects
                      .slice()
                      .sort((a, b) => (projectTimestamp(b) || 0) - (projectTimestamp(a) || 0) || String(b.projectId || "").localeCompare(String(a.projectId || "")));
                    $("projects").innerHTML = sortedVisibleProjects.map(p => `
                      <div class="card">
                        <button class="ghost ${p.projectId === state.projectId ? "current" : ""}" data-project="${p.projectId}">
                        <strong>${escapeHtml(p.name)}</strong>
                        <span class="muted">${escapeHtml(p.gameName)} · ${escapeHtml(p.templateRuleId)} · ${escapeHtml(p.bootstrapStatus)}</span>
                        ${p.bootstrapStatus === "failed" ? `<span class="danger">初始化失败：${escapeHtml(sanitizePublicFailureContent(p.bootstrapError || "未知错误"))}</span>` : ""}
                        ${renderProjectHealthInline(health)}
                        </button>
                        <div class="grid">
                          <label>删除确认 1 <input data-delete-one="${p.projectId}" placeholder="输入 delete"></label>
                          <label>删除确认 2 <input data-delete-two="${p.projectId}" placeholder="再次输入 delete"></label>
                        </div>
                        <button class="danger-button" data-delete-project="${p.projectId}" data-global-action="true">删除项目</button>
                      </div>
                    `).join("");
                    document.querySelectorAll("[data-project]").forEach(button => button.onclick = () => selectProject(button.dataset.project));
                    document.querySelectorAll("[data-delete-project]").forEach(button => button.onclick = () => deleteProject(button.dataset.deleteProject));
                    callV2("v2RenderLeftProjectList");
                    const currentProjectVisible = !state.projectId || visibleProjects.some(project => project.projectId === state.projectId);
                    if (visibleProjects.length === 0 && latestFailure) {
                      showCreationFailure(latestFailure.failureError);
                    } else if (initializing && !state.projectId) {
                      showInitialization("running", "");
                    } else if (visibleProjects.length === 0) {
                      state.projectId = "";
                      writeSelectedProjectId("");
                      showCreateProjectPage();
                    } else if (!currentProjectVisible) {
                      state.projectId = "";
                      writeSelectedProjectId("");
                      selectDefaultProject(visibleProjects);
                    } else if (autoSelect || !state.projectId) {
                      selectDefaultProject(visibleProjects);
                    }
                    out(projects);
                  } catch (error) {
                    if (!sessionValidated) {
                      if (error?.status === 401 || error?.status === 403) {
                        localStorage.removeItem("phaseAAccessToken");
                        localStorage.removeItem("phaseAAdminToken");
                        clearBrowserCookie("phaseAAccessToken");
                      }
                      showLoggedOut();
                    } else {
                      $("sessionStatus").textContent = "Token 已验证。项目状态刷新失败，请稍后重试。";
                    }
                    showError(error);
                  }
                }

                function selectDefaultProject(projects) {
                  if (!Array.isArray(projects) || projects.length === 0) return;
                  const current = state.projectId ? projects.find(project => project.projectId === state.projectId) : null;
                  if (current?.projectId) {
                    selectProject(current.projectId);
                    return;
                  }
                  const remembered = readSelectedProjectId();
                  if (remembered && projects.some(project => project.projectId === remembered)) {
                    selectProject(remembered);
                    return;
                  }
                  const latest = latestProject(projects);
                  if (latest?.projectId) selectProject(latest.projectId);
                }

                function latestProject(projects) {
                  const datedProjects = projects
                    .map((project, index) => ({ project, index, timestamp: projectTimestamp(project) }))
                    .filter(item => Number.isFinite(item.timestamp));
                  if (datedProjects.length > 0) {
                    return datedProjects.sort((a, b) => b.timestamp - a.timestamp || b.index - a.index)[0].project;
                  }
                  return projects[projects.length - 1];
                }

                function projectTimestamp(project) {
                  const value = project.lastActivityUtc || project.updatedUtc || project.updatedAtUtc || project.lastUpdatedUtc || project.modifiedUtc || project.createdUtc || project.createdAtUtc;
                  if (!value) return Number.NaN;
                  const timestamp = Date.parse(value);
                  return Number.isFinite(timestamp) ? timestamp : Number.NaN;
                }

                async function loadLatestProjectCreationFailure() {
                  try {
                    const response = await fetch("/api/project-creation-failures/latest", { headers: { "Authorization": `Bearer ${token()}` } });
                    if (!response.ok) return null;
                    return await response.json();
                  } catch {
                    return null;
                  }
                }

                async function loadProjectHealthSummary() {
                  try {
                    const response = await fetch("/project-health/latest.json", { headers: { "Authorization": `Bearer ${token()}` } });
                    if (!response.ok) return null;
                    const payload = await response.json();
                    return {
                      status: payload.status || "未知",
                      generatedAt: payload.generated_at || "",
                      stage: (payload.records || []).find(r => r.kind === "detect-project-stage")?.stage || "",
                      summary: (payload.records || []).find(r => r.kind === "detect-project-stage")?.summary || ""
                    };
                  } catch {
                    return null;
                  }
                }

                function renderProjectHealthInline(summary) {
                  if (!summary) return "<span class='muted'>项目健康摘要暂不可用</span>";
                  return `<span class="muted">健康：${escapeHtml(summary.status)} · 阶段：${escapeHtml(summary.stage || "未识别")}</span><span>${escapeHtml(summary.summary || "")}</span>`;
                }

                function selectProject(projectId) {
                  state.projectId = projectId;
                  writeSelectedProjectId(projectId);
                  state.assetInventory = null;
                  state.assetInventoryExpanded = false;
                  state.packageList = null;
                  state.runs = [];
                  state.prototypeFailure = "";
                  state.v2PrototypeStatus = "";
                  state.v2PrototypeCreationStatus = "";
                  state.iterationPlan = null;
                  state.iterationPlans = [];
                  state.selectedIterationSessionId = "";
                  state.iterationPlanEvaluation = null;
                  state.iterationPlanFailure = "";
                  state.repairPlan = null;
                  v2ActiveTabId = "chat";
                  setModalVisible("projectListModal", false);
                  hideCreateProjectPage();
                  loadChatHistoryForProject(projectId);
                  const project = state.projects.find(p => p.projectId === projectId);
                  $("selectedProject").textContent = project ? `${project.name} (${project.projectId})` : projectId;
                  showProjectDetail();
                  callV2("v2RenderLeftProjectList");
                  applyProjectStateCache(projectId);
                  loadProjectRuntimeState();
                  loadServerChatHistoryForProject(projectId);
                  loadIterationPlan();
                  loadRepairPlan();
                  refreshGddOutlineStatus();
                }

                async function loadProjectRuntimeState() {
                  await loadRuns();
                  await loadLatestPrototypeDraft();
                  await loadPrototypeProgress();
                  await loadProjectPackages();
                  await refreshAssetInventoryAvailability();
                }

                async function loadLatestPrototypeDraft(forceVisibleNotice = false) {
                  if (!state.projectId) return;
                  try {
                    const draft = await api(`/api/projects/${state.projectId}/prototype-drafts/latest`);
                    applyDraftToForm(draft);
                    renderDraftImportStatus(draft);
                    writeProjectStateCache({ latestPrototypeDraft: draft });
                    if (forceVisibleNotice && draft.status === "succeeded") {
                      showPrototypeNotice("已同步最近一次草稿分析结果，表单已自动补全到最新状态。", "info");
                    }
                    return draft;
                  } catch {
                    $("draftImportStatus").className = "card muted";
                    $("draftImportStatus").textContent = "";
                    $("draftImportStatus").classList.add("hidden");
                    return null;
                  }
                }

                function renderProjectHealth(summary) {
                  if (!summary) {
                    $("projectHealthSummary").className = "card muted";
                    $("projectHealthSummary").textContent = "还没有 project-health 摘要。运行 Chapter 2 初始化后会生成。";
                    return;
                  }
                  const statusClass = summary.status === "ok" ? "status-ok" : summary.status === "fail" ? "status-fail" : "status-warn";
                  $("projectHealthSummary").className = "card";
                  $("projectHealthSummary").innerHTML = `
                    <strong class="${statusClass}">项目健康：${escapeHtml(summary.status)}</strong>
                    <p class="muted">更新时间：${escapeHtml(summary.generatedAt || "未知")} · 阶段：${escapeHtml(summary.stage || "未识别")}</p>
                    <p>${escapeHtml(summary.stageSummary || "暂无阶段摘要。")}</p>
                    <div class="health-grid">
                      <div class="metric"><span class="muted">Doctor</span><strong>${escapeHtml(summary.doctorStatus)}</strong><span>${summary.doctorFailCount} fail / ${summary.doctorWarnCount} warn / ${summary.doctorOkCount} ok</span></div>
                      <div class="metric"><span class="muted">目录边界</span><strong>${escapeHtml(summary.boundaryStatus)}</strong><span>${summary.boundaryFailCount} fail / ${summary.boundaryWarnCount} warn</span></div>
                      <div class="metric"><span class="muted">代码资产</span><strong>${summary.unitTestFileCount}</strong><span>${summary.contractFileCount} contracts / ${summary.overlayIndexCount} overlays</span></div>
                      <div class="metric"><span class="muted">报告索引</span><strong>${summary.jsonReportTotal}</strong><span>${summary.invalidJsonReportTotal} invalid / ${summary.activeTaskTotal} active tasks</span></div>
                    </div>
                    ${summary.topRecommendation ? `<p><strong>建议：</strong>${escapeHtml(summary.topRecommendation)}</p>` : ""}
                  `;
                }

                function setCreateProjectFieldError(fieldId, errorId, message) {
                  const field = $(fieldId);
                  const error = $(errorId);
                  if (!field || !error) return;
                  field.classList.toggle("field-invalid", !!message);
                  error.classList.toggle("hidden", !message);
                  error.textContent = message || "";
                }

                function validateCreateProjectForm(showSummary = true) {
                  const fields = [
                    { inputId: "projectName", fieldId: "projectNameField", errorId: "projectNameError", required: false, requiredMessage: "" },
                    { inputId: "gameName", fieldId: "gameNameField", errorId: "gameNameError", required: true, requiredMessage: "请输入游戏名称" },
                    { inputId: "gameTypeSource", fieldId: "gameTypeSourceField", errorId: "gameTypeSourceError", required: true, requiredMessage: "请输入参考游戏类型或游戏名称" }
                  ];
                  const messages = [];
                  for (const field of fields) {
                    const value = String($(field.inputId)?.value || "").trim();
                    let message = "";
                    if (field.required && !value) {
                      message = field.requiredMessage;
                    } else if (value && Array.from(value).length < 3) {
                      message = "输入信息过少";
                    }
                    setCreateProjectFieldError(field.fieldId, field.errorId, message);
                    if (message) messages.push(message);
                  }
                  const uniqueMessages = [...new Set(messages)];
                  const summary = $("createProjectValidation");
                  if (summary) {
                    summary.classList.toggle("hidden", !showSummary || uniqueMessages.length === 0);
                    summary.textContent = uniqueMessages.join("；");
                  }
                  return uniqueMessages.length === 0;
                }

                function isProjectCreationFailureForAttempt(failure, createdProjectId, attemptStartedAt) {
                  if (!failure?.failureError) return false;
                  if (createdProjectId && failure.projectId && failure.projectId === createdProjectId) return true;
                  const failureTime = Date.parse(failure.createdUtc || failure.CreatedUtc || "");
                  return Number.isFinite(failureTime) && Number.isFinite(attemptStartedAt) && failureTime >= attemptStartedAt - 5000;
                }

                async function createProject() {
                  if (!validateCreateProjectForm(true)) return;
                  if (!guardGlobalAction()) return;
                  setLocalBusy(true, "创建项目中，请等待当前任务执行完毕。");
                  $("createProject").disabled = true;
                  $("createProject").textContent = "创建中...";
                  const creationAttemptStartedAt = Date.now();
                  try {
                    const payload = {
                      projectName: $("projectName").value.trim() || null,
                      gameName: $("gameName").value.trim(),
                      gameTypeSource: $("gameTypeSource").value.trim()
                    };
                    const result = await api("/api/projects", { method: "POST", body: JSON.stringify(payload) });
                    const createdProjectId = result.projectId || result.ProjectId || "";
                    out(result);
                    if (createdProjectId) {
                      await refreshProjects({ autoSelect: false });
                    }
                    showInitialization("running", "");
                    await pollProjectInitializationResult(createdProjectId, creationAttemptStartedAt);
                  } catch (error) {
                    showCreationFailure(projectCreationErrorMessage(error));
                    showError(error);
                  } finally {
                    setLocalBusy(false);
                    $("createProject").disabled = false;
                    $("createProject").textContent = "创建项目";
                    await refreshActiveRun();
                  }
                }

                async function pollProjectInitializationResult(createdProjectId = "", attemptStartedAt = Date.now(), maxAttempts = 24, delayMs = 5000) {
                  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
                    await new Promise(resolve => setTimeout(resolve, delayMs));
                    try {
                      const projects = await api("/api/projects");
                      state.projects = projects;
                      const createdProject = projects.find(project => project.projectId === createdProjectId);
                      if (createdProject?.bootstrapStatus === "failed") {
                        showCreationFailure(createdProject.bootstrapError || "初始化失败，请查看运行记录。");
                        return;
                      }
                      if (isProjectReady(createdProject)) {
                        $("initStatusPanel").classList.add("hidden");
                        await refreshProjects({ autoSelect: false });
                        selectProject(createdProject.projectId);
                        return;
                      }
                      if (createdProjectId && isProjectPendingInitialization(createdProject)) {
                        showInitialization("running", "");
                        callV2("v2RenderLeftProjectList");
                        continue;
                      }
                      if (hasInitializingProject(projects)) {
                        showInitialization("running", "");
                        callV2("v2RenderLeftProjectList");
                        continue;
                      }
                      const visibleProjects = listableProjects(projects);
                      const latestFailure = await loadLatestProjectCreationFailure();
                      if (isProjectCreationFailureForAttempt(latestFailure, createdProjectId, attemptStartedAt)) {
                        showCreationFailure(latestFailure.failureError);
                        return;
                      }
                      if (visibleProjects.length > 0) {
                        await refreshProjects({ autoSelect: false });
                        if (!createdProjectId) {
                          selectDefaultProject(visibleProjects);
                          return;
                        }
                        showCreationFailure("项目初始化未成功完成，请稍后重试。");
                        return;
                      }
                      if (latestFailure?.failureError) {
                        showCreationFailure(latestFailure.failureError);
                        return;
                      }
                    } catch {
                      await refreshProjects({ autoSelect: false });
                      return;
                    }
                  }
                  const latestFailure = await loadLatestProjectCreationFailure();
                  if (isProjectCreationFailureForAttempt(latestFailure, createdProjectId, attemptStartedAt)) {
                    showCreationFailure(latestFailure.failureError);
                    return;
                  }
                  await refreshProjects({ autoSelect: false });
                  showInitialization("running", "");
                }

                function projectCreationErrorMessage(error) {
                  const payload = error?.payload || {};
                  const code = payload.failureCode || payload.error || error?.status || "unknown_error";
                  if (code === "project_initialization_in_progress") {
                    return "已有项目仍在初始化中，暂时不能创建新项目。系统会自动清理中断的初始化；如果页面一直停留在这里，请刷新后重试。";
                  }
                  if (code === "project_creation_concurrency_limit_exceeded" || code === "user_project_creation_concurrency_limit_exceeded") {
                    return "当前已有项目正在创建中，请等待创建完成后再提交新的项目创建请求。";
                  }
                  if (code === "project_quota_exceeded") {
                    return `项目数量已达到上限${payload.projectLimit ? `（${payload.projectLimit} 个）` : ""}，请先删除旧项目后再创建。`;
                  }
                  if (code === "game_name_required") {
                    return "请输入游戏名称";
                  }
                  if (code === "game_type_source_required") {
                    return "请输入参考游戏类型或游戏名称";
                  }
                  if (code === "git_url_not_allowed") {
                    return "当前入口不允许从浏览器提交 Git URL。";
                  }
                  if (code === "project_creation_failed") {
                    return payload.detail ? `项目工作区初始化失败：${payload.detail}` : "项目工作区初始化失败，请查看最新失败详情后重试。";
                  }
                  return `创建请求失败：${code}`;
                }

                async function deleteProject(projectId) {
                  if (!guardGlobalAction()) return;
                  const confirmOne = document.querySelector(`[data-delete-one="${projectId}"]`)?.value.trim() || "";
                  const confirmTwo = document.querySelector(`[data-delete-two="${projectId}"]`)?.value.trim() || "";
                  if (confirmOne !== "delete" || confirmTwo !== "delete") {
                    out("删除项目需要在两个确认框都输入 delete。");
                    return;
                  }
                  const deleteButton = document.querySelector(`[data-delete-project="${projectId}"]`);
                  setLocalBusy(true, "删除项目中，请等待当前任务执行完毕。");
                  if (deleteButton) {
                    deleteButton.disabled = true;
                    deleteButton.textContent = "删除中...";
                  }
                  try {
                    const result = await api(`/api/projects/${projectId}`, {
                      method: "DELETE",
                      body: JSON.stringify({ confirmOne, confirmTwo })
                    });
                    if (state.projectId === projectId) {
                      state.projectId = "";
                      writeSelectedProjectId("");
                      $("projectDetailPanel").classList.add("hidden");
                    }
                    out(result);
                    await refreshProjects();
                  } catch (error) { showError(error); }
                  finally {
                    if (deleteButton) {
                      deleteButton.disabled = false;
                      deleteButton.textContent = "删除项目";
                    }
                    setLocalBusy(false);
                    await refreshActiveRun();
                  }
                }

                async function loadRuns() {
                  if (!state.projectId) return out("请先选择一个项目。");
                  try {
                    const result = await api(`/api/projects/${state.projectId}/runs`);
                    state.runs = result.runs || [];
                    renderProjectHealth(result.projectHealth);
                    renderRunsListFromState(result.projectHealth);
                    writeProjectStateCache({ runs: state.runs, projectHealth: result.projectHealth || null });
                    renderFeedbackRecords();
                    callV2("v2RenderProgress");
                    out(result);
                  } catch (error) { showError(error); }
                }

                function renderRunsListFromState(projectHealth = null) {
                  if (projectHealth) renderProjectHealth(projectHealth);
                  $("runs").innerHTML = (state.runs || []).map(r => `
                    <button class="card ghost" data-run="${r.runId}">
                      <strong>${escapeHtml(r.runType)} · ${escapeHtml(r.status)}</strong>
                      <span class="muted">${escapeHtml(r.runId)}</span>
                    </button>
                  `).join("") || "<p class='muted'>还没有运行记录。</p>";
                  document.querySelectorAll("[data-run]").forEach(button => button.onclick = () => loadRun(button.dataset.run));
                }

                function renderFeedbackRecords() {
                  const goalRecords = iterationGoalRecords();
                  if (goalRecords.length > 0) {
                    renderFeedbackSummary();
                    const markers = iterationGoalMarkers();
                    $("feedbackRecords").innerHTML = goalRecords.map(record => {
                      const run = record.run;
                      const isCurrent = markers.currentGoalId === record.goal.goalId;
                      const isNext = markers.nextGoalId === record.goal.goalId;
                      const cardClass = isCurrent ? "card goal-card-current" : isNext ? "card goal-card-next" : "card";
                      const downloads = feedbackArtifacts(run).map(a => `<a href="/artifacts/${escapeHtml(a.artifactId)}" target="_blank" rel="noreferrer">${escapeHtml(a.artifactType)}</a>`).join(" · ");
                      return `
                        <div class="${cardClass}">
                          <strong>目标 ${escapeHtml(String(record.goal.goalIndex))} · ${escapeHtml(record.goal.title || "")}</strong>
                          <div class="goal-badges">
                            ${goalBadge(statusLabel(record.goal.status), `goal-badge-${normalizeGoalStatus(record.goal.status)}`)}
                            ${isCurrent ? goalBadge("当前目标", "goal-badge-current") : ""}
                            ${isNext ? goalBadge("下一目标", "goal-badge-next") : ""}
                          </div>
                          <span class="muted">${escapeHtml(run?.status || "未执行")}</span>
                          ${record.goal.resultSummary ? `<p>${escapeHtml(publicIterationGoalResultSummary(record.goal))}</p>` : "<p class='muted'>该目标尚未产出结果摘要。</p>"}
                          ${run ? `<p class="muted">Run: ${escapeHtml(run.runId)}</p>` : "<p class='muted'>该目标尚未关联执行记录。</p>"}
                          <p>${downloads || "暂无可下载日志"}</p>
                        </div>
                      `;
                    }).join("");
                    return;
                  }

                  const feedbackRuns = state.runs.filter(r => r.runType === "prototype-feedback-iteration");
                  renderFeedbackSummary(feedbackRuns);
                  $("feedbackRecords").innerHTML = feedbackRuns.map((run, index) => {
                    const downloads = feedbackArtifacts(run).map(a => `<a href="/artifacts/${escapeHtml(a.artifactId)}" target="_blank" rel="noreferrer">${escapeHtml(a.artifactType)}</a>`).join(" · ");
                    return `
                      <div class="card">
                        <strong>第 ${feedbackRuns.length - index} 次正式反馈 · ${escapeHtml(run.status)}</strong>
                        <span class="muted">${escapeHtml(run.runId)}</span>
                        <p>${downloads || "暂无可下载日志"}</p>
                      </div>
                    `;
                  }).join("") || "<p class='muted'>还没有流程记录。</p>";
                }

                function renderFeedbackSummary(legacyFeedbackRuns = []) {
                  const goals = Array.isArray(state.iterationPlan?.goals) ? state.iterationPlan.goals : [];
                  if (goals.length > 0) {
                    const completedGoals = goals.filter(goal => goal.status === "succeeded").length;
                    const runningGoal = goals.find(goal => goal.status === "running");
                    const needsFixGoal = goals.find(goal => goal.status === "needs_fix");
                    const pendingGoal = goals.find(goal => goal.status === "pending");
                    const failedGoal = goals.find(goal => goal.status === "failed");
                    const currentGoal = needsFixGoal || failedGoal || runningGoal || pendingGoal || goals[goals.length - 1];
                    const nextGoal = needsFixGoal || failedGoal ? null : pendingGoal;
                    $("feedbackSummary").className = "card";
                    $("feedbackSummary").innerHTML = `
                      <strong>计划摘要</strong>
                      <p class="muted">总目标数：${escapeHtml(String(goals.length))} · 已完成：${escapeHtml(String(completedGoals))}</p>
                      <p class="muted">当前目标：${currentGoal ? escapeHtml(`step ${currentGoal.goalIndex} · ${currentGoal.title || ""}`) : "暂无"}</p>
                      <p class="muted">下一目标：${needsFixGoal ? "请先修复当前目标" : nextGoal ? escapeHtml(`step ${nextGoal.goalIndex} · ${nextGoal.title || ""}`) : "全部完成"}</p>
                      ${renderFeedbackPrimaryAction()}
                    `;
                    const primaryActionButton = $("feedbackPrimaryAction");
                    if (primaryActionButton) {
                      primaryActionButton.onclick = () => runFeedbackPrimaryAction();
                    }
                    callV2("v2HideLegacyChatFeedback");
                    return;
                  }

                  if (legacyFeedbackRuns.length > 0) {
                    $("feedbackSummary").className = "card";
                    $("feedbackSummary").innerHTML = `
                      <strong>流程摘要</strong>
                      <p class="muted">当前项目还没有游戏模块，以下仅展示旧正式反馈记录。</p>
                      <p class="muted">正式反馈次数：${escapeHtml(String(legacyFeedbackRuns.length))}</p>
                    `;
                    callV2("v2HideLegacyChatFeedback");
                    return;
                  }

                  $("feedbackSummary").className = "card muted";
                  $("feedbackSummary").textContent = "尚未生成游戏模块。";
                  callV2("v2HideLegacyChatFeedback");
                }

                function feedbackPrimaryActionState() {
                  const goals = Array.isArray(state.iterationPlan?.goals) ? state.iterationPlan.goals : [];
                  if (!goals.length || !state.prototypeReadyForFeedback) {
                    return { label: "", action: "", source: "", disabled: true };
                  }
                  const decision = currentIterationPlanDecision();
                  const hasNeedsFix = goals.some(goal => goal.status === "needs_fix" || goal.status === "failed");
                  const hasPending = goals.some(goal => goal.status === "pending");
                  if (decision === "llm_failed") {
                    return { label: "LLM 调用失败，先修复", action: "", source: "当前计划评估", disabled: true };
                  }
                  if (decision === "should_refine_plan") {
                    return { label: "重新生成游戏模块", action: "refine", source: "当前计划评估", disabled: isGlobalBusy() || isIterationPlanStarted() };
                  }
                  if (hasNeedsFix || hasPending) {
                    return { label: "继续评估当前计划", action: "evaluate", source: "目标执行结果", disabled: isGlobalBusy() };
                  }
                  if (decision === "ready_to_execute") {
                    return { label: "继续当前迭代目标", action: "execute", source: "当前计划评估", disabled: isGlobalBusy() };
                  }
                  return { label: "", action: "", source: "", disabled: true };
                }

                function renderFeedbackPrimaryAction() {
                  const state = feedbackPrimaryActionState();
                  if (!state.label || !state.action) return "";
                  return `
                    <div class="card">
                      <strong>当前推荐动作</strong>
                      ${state.source ? `<p class="muted">来源：${escapeHtml(state.source)}</p>` : ""}
                      <button id="feedbackPrimaryAction" class="secondary" data-global-action="true" data-feedback-primary-action="${escapeHtml(state.action)}" ${state.disabled ? "disabled" : ""}>${escapeHtml(state.label)}</button>
                    </div>
                  `;
                }

                async function runFeedbackPrimaryAction() {
                  const state = feedbackPrimaryActionState();
                  if (!state.action) return out("当前没有可执行的推荐动作。");
                  if (state.action === "refine") {
                    if (isIterationPlanStarted()) return out("当前游戏模块已经开始执行，不允许更新游戏模块。");
                    const evaluationSuggestion = currentIterationPlanRegenerationPrompt();
                    if (evaluationSuggestion) {
                      openIterationPlanUpdateModal("update", evaluationSuggestion);
                      return;
                    }
                    if (!state.nextSuggestedFeedback) return out("当前没有可用于重拆计划的建议。");
                    openIterationPlanUpdateModal("update", state.nextSuggestedFeedback);
                    return;
                  }
                  if (state.action === "execute") {
                    await executeIterationGoal();
                    return;
                  }
                  await evaluateIterationPlan(true);
                }

                function iterationGoalRecords() {
                  const goals = Array.isArray(state.iterationPlan?.goals) ? state.iterationPlan.goals : [];
                  const goalRuns = Array.isArray(state.iterationPlan?.goalRuns) ? state.iterationPlan.goalRuns : [];
                  if (!goals.length) return [];
                  const runMap = new Map(state.runs.map(run => [run.runId, run]));
                  const latestGoalRunByGoalId = new Map();
                  goalRuns.forEach(goalRun => {
                    if (!goalRun?.goalId || !goalRun?.runId) return;
                    latestGoalRunByGoalId.set(goalRun.goalId, goalRun);
                  });
                  return goals
                    .map(goal => {
                      const goalRun = latestGoalRunByGoalId.get(goal.goalId);
                      const matchedRun = goalRun ? (runMap.get(goalRun.runId) || null) : null;
                      return { goal, run: matchedRun };
                    })
                    .filter(record => record.goal.status !== "pending" || record.run);
                }

                function iterationGoalMarkers() {
                  const goals = Array.isArray(state.iterationPlan?.goals) ? state.iterationPlan.goals : [];
                  const runningGoal = goals.find(goal => goal.status === "running");
                  const needsFixGoal = goals.find(goal => goal.status === "needs_fix");
                  const failedGoal = goals.find(goal => goal.status === "failed");
                  const pendingGoal = goals.find(goal => goal.status === "pending");
                  const currentGoal = needsFixGoal || failedGoal || runningGoal || pendingGoal || goals[goals.length - 1] || null;
                  const nextGoal = needsFixGoal || failedGoal ? null : pendingGoal || null;
                  return {
                    currentGoalId: currentGoal?.goalId || "",
                    nextGoalId: nextGoal?.goalId || ""
                  };
                }

                function normalizeGoalStatus(value) {
                  const normalized = String(value || "pending").trim().toLowerCase();
                  if (normalized === "succeeded") return "succeeded";
                  if (normalized === "running") return "running";
                  if (normalized === "failed") return "failed";
                  if (normalized === "needs_fix") return "needs-fix";
                  return "pending";
                }

                function statusLabel(value) {
                  const normalized = normalizeGoalStatus(value);
                  if (normalized === "succeeded") return "已完成";
                  if (normalized === "running") return "进行中";
                  if (normalized === "failed") return "失败";
                  if (normalized === "needs-fix") return "需修复";
                  return "待执行";
                }

                function goalBadge(text, className) {
                  return `<span class="goal-badge ${className}">${escapeHtml(text)}</span>`;
                }

                function feedbackArtifacts(run) {
                  try {
                    const evidence = JSON.parse(run.evidenceJson || "{}");
                    const paths = [evidence.submitted_feedback, evidence.result_log].filter(Boolean);
                    return paths.map(path => (run.artifacts || []).find(a => a.relativePath === path)).filter(Boolean);
                  } catch {
                    return [];
                  }
                }

                async function loadRun(runId) {
                  try {
                    const result = await api(`/api/runs/${runId}`);
                    const links = (result.artifacts || []).map(a => `产物: ${a.artifactType} ${location.origin}/artifacts/${a.artifactId}`).join("\n");
                    out(`${JSON.stringify(result.run, null, 2)}\n\n${links}`);
                  } catch (error) { showError(error); }
                }

                function isGlobalBusy() {
                  return state.localBusy || (!!state.activeRun?.busy && !isInlineOnlyRun(state.activeRun));
                }

                function isInlineOnlyRun(run) {
                  const runType = String(run?.runType || "").trim().toLowerCase();
                  return runType === "prototype-iteration-plan-evaluation";
                }

                function activeRunText(run) {
                  if (!run?.busy) return "";
                  if (run.heavyRunnerQueuePosition) {
                    const waitSeconds = Math.max(0, run.heavyRunnerEstimatedWaitSeconds || 0);
                    const waitMinutes = Math.max(1, Math.ceil(waitSeconds / 60));
                    return `\u4f60\u5df2\u8fdb\u5165\u91cd\u4efb\u52a1\u961f\u5217\uff1a\u7b2c ${run.heavyRunnerQueuePosition} \u4f4d\uff0c\u5f53\u524d\u7b49\u5f85 ${run.heavyRunnerQueuedCount || 0} \u4e2a\uff0c\u9884\u8ba1\u7b49\u5f85\u7ea6 ${waitMinutes} \u5206\u949f\u3002`;
                  }
                  const label = run.progressLabel || run.progressStep || run.status || "";
                  return `当前任务执行中：${run.runType || "未知"} · ${run.status || "running"} · ${run.runId || ""}${label ? " · " + label : ""}`;
                }

                function canCancelActiveRun(run) {
                  const runType = String(run?.runType || "").trim().toLowerCase();
                  return !!run?.runId && !["chapter2-bootstrap", "project-creation", "project-asset-generation", "asset-generation"].includes(runType);
                }

                function setLocalBusy(busy, message = "有任务正在执行，请等待当前任务执行完毕。") {
                  if (busy) invalidateWorkflowRouteAction();
                  state.localBusy = busy;
                  applyGlobalBusyState(message);
                }

                function renderActiveRunBanner(message) {
                  const banner = $("activeRunBanner");
                  banner.replaceChildren();
                  const text = document.createElement("span");
                  text.textContent = message;
                  banner.appendChild(text);
                  if (canCancelActiveRun(state.activeRun)) {
                    const cancelButton = document.createElement("button");
                    cancelButton.type = "button";
                    cancelButton.className = "ghost danger";
                    cancelButton.textContent = "\u53d6\u6d88";
                    cancelButton.onclick = cancelActiveRun;
                    banner.appendChild(cancelButton);
                  }
                }

                function applyGlobalBusyState(message = "有任务正在执行，请等待当前任务执行完毕。") {
                  const busy = isGlobalBusy();
                  document.querySelectorAll("[data-global-action]").forEach(button => {
                    button.disabled = busy;
                    if (busy) button.title = message;
                    else button.removeAttribute("title");
                  });
                  document.querySelectorAll("[data-needs-fix-goal]").forEach(button => {
                    button.disabled = busy;
                    if (busy) button.title = message;
                    else button.removeAttribute("title");
                  });
                  if (!busy && state.packageList) {
                    renderProjectPackages(state.packageList);
                  }
                  if (!busy && state.assetInventory) {
                    renderAssetInventory(state.assetInventory, state.assetInventoryExpanded);
                  }
                  updateDraftImportButtonState();
                  if (busy) {
                    $("activeRunBanner").classList.remove("hidden");
                    renderActiveRunBanner(state.activeRun?.busy ? activeRunText(state.activeRun) : message);
                  } else {
                    $("activeRunBanner").classList.add("hidden");
                    $("activeRunBanner").replaceChildren();
                  }
                }

                async function cancelActiveRun() {
                  const runId = state.activeRun?.runId;
                  if (!runId) return;
                  if (!confirm("\u786e\u5b9a\u8981\u53d6\u6d88\u5f53\u524d run \u5417\uff1f")) return;
                  try {
                    await api(`/api/runs/${encodeURIComponent(runId)}/cancel`, { method: "POST", body: "{}" });
                    state.activeRun = null;
                    out("\u5f53\u524d run \u5df2\u53d6\u6d88\u3002");
                    await refreshActiveRun();
                    if (state.projectId) {
                      await Promise.allSettled([
                        loadRuns(),
                        loadPrototypeProgress(),
                        refreshAssetInventoryAvailability(),
                        refreshGddOutlineStatus()
                      ]);
                    }
                  } catch (error) {
                    showError(error);
                    await refreshActiveRun();
                  }
                }

                async function refreshActiveRun() {
                  if (!state.authenticated) return;
                  try {
                    const wasBusy = isGlobalBusy();
                    state.activeRun = await api("/api/account/active-run");
                    applyGlobalBusyState();
                    if (state.projectId && shouldAutoRefreshIterationPlan(state.activeRun)) {
                      await loadIterationPlan();
                      await loadRuns();
                    }
                    if (wasBusy && !state.activeRun?.busy && state.projectId) {
                      await loadPrototypeProgress();
                      await loadProjectPackages();
                      await refreshAssetInventoryAvailability();
                    }
                  } catch {
                    state.activeRun = null;
                    applyGlobalBusyState();
                  }
                }

                function shouldAutoRefreshIterationPlan(activeRun) {
                  return !!(
                    state.projectId &&
                    activeRun?.busy &&
                    activeRun?.projectId === state.projectId &&
                    activeRun?.runType === "prototype-iteration-goal"
                  );
                }

                function guardGlobalAction() {
                  if (!isGlobalBusy()) return true;
                  out("有任务正在执行，请等待当前任务执行完毕。");
                  applyGlobalBusyState();
                  return false;
                }

                function applyDraftToForm(draft) {
                  if (draft.prototypeSlug) $("protoSlug").value = draft.prototypeSlug;
                  if (draft.hypothesis) $("hypothesis").value = draft.hypothesis;
                  if (draft.corePlayerFantasy) $("corePlayerFantasy").value = draft.corePlayerFantasy;
                  if (draft.minimumPlayableLoop) $("minimumPlayableLoop").value = draft.minimumPlayableLoop;
                  if (draft.successCriteria?.length) $("successCriteria").value = draft.successCriteria.join("\n");
                  if (draft.gameFeature) $("gameFeature").value = draft.gameFeature;
                  if (draft.coreGameplayLoop) $("coreGameplayLoop").value = draft.coreGameplayLoop;
                  if (draft.winFailConditions) $("winFailConditions").value = draft.winFailConditions;
                }

                function renderDraftImportStatus(draft) {
                  if (!draft || draft.status === "failed") {
                    $("draftImportStatus").className = "card muted";
                    $("draftImportStatus").textContent = draft?.failureCode ? `草稿分析失败：${draft.failureCode}` : "";
                    $("draftImportStatus").classList.toggle("hidden", !draft?.failureCode);
                    return;
                  }
                  if (draft.status === "running") {
                    state.draftAnalysisRunning = true;
                    $("draftImportStatus").className = "card muted";
                    $("draftImportStatus").textContent = "草稿分析中...完成前不能启动原型创建，刷新页面后会自动恢复状态。";
                    $("draftImportStatus").classList.remove("hidden");
                    setPrototypeFormLocked(true);
                    return;
                  }
                  state.draftAnalysisRunning = false;
                  $("draftImportStatus").className = "card";
                  $("draftImportStatus").innerHTML = `
                    <strong>草稿已分析并回填</strong>
                    <p class="muted">${escapeHtml(draft.fileName || "")} · ${draft.lineCount || 0} 行 · ${draft.byteCount || 0} bytes</p>
                    <p class="muted">草稿覆盖率：${escapeHtml(String(draft.coveragePercent ?? 0))}%${draft.coverageSummary ? ` · ${escapeHtml(draft.coverageSummary)}` : ""}</p>
                    <p class="muted">命中字段：${escapeHtml((draft.matchedFields || []).join(" · ") || "无")}</p>
                    <p class="muted">覆盖缺口：${escapeHtml((draft.coverageMissingTopics || []).join(" · ") || "无")}</p>
                    <p class="muted">警告：${escapeHtml((draft.warnings || []).join(" · ") || "无")}</p>
                  `;
                  $("draftImportStatus").classList.remove("hidden");
                }

                async function importDraft() {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("请先创建并选择项目。");
                  const file = $("draftFile").files?.[0];
                  if (!file) return out("请先选择一个 txt 文件。");
                  setLocalBusy(true, "草稿分析中，请等待当前任务执行完毕。");
                  $("importDraft").textContent = "模型分析中...";
                  $("runPrototype").textContent = "草稿分析中..暂不可启动原型.";
                  $("draftImportStatus").className = "card muted";
                  $("draftImportStatus").textContent = "后端正在调用模型分析 txt 草稿，完成前不能启动原型创建。";
                  $("draftImportStatus").classList.remove("hidden");
                  try {
                    const form = new FormData();
                    form.append("draftFile", file);
                    form.append("model", $("globalModel").value || "gpt-5.5");
                    const response = await fetch(`/api/projects/${state.projectId}/prototype-drafts/analyze`, { method: "POST", body: form, headers: { "Authorization": `Bearer ${token()}` } });
                    const payload = await response.json();
                    if (!response.ok) throw payload;
                    applyDraftToForm(payload);
                    renderDraftImportStatus(payload);
                    out(payload);
                    await loadRuns();
                  } catch (error) {
                    $("draftImportStatus").className = "card muted";
                    $("draftImportStatus").textContent = `草稿分析失败：${error?.error || error?.failureCode || "unknown_error"}`;
                    $("draftImportStatus").classList.remove("hidden");
                    showError(error);
                  } finally {
                    setLocalBusy(false);
                    $("importDraft").disabled = false;
                    $("importDraft").textContent = "分析草稿并回填";
                    updateDraftImportButtonState();
                    await refreshActiveRun();
                  }
                }

                function updateDraftImportButtonState() {
                  const file = $("draftFile")?.files?.[0];
                  const button = $("importDraft");
                  if (!button) return;
                  const canImport = !!state.projectId && !!file && !isGlobalBusy();
                  button.disabled = !canImport;
                  button.title = canImport ? "" : "请选择一个 txt 文件后再分析草稿并回填。";
                }

                async function createProjectPackage() {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("请先选择一个项目。");
                  setLocalBusy(true, "打包项目文件中，请等待当前任务执行完毕。");
                  $("createProjectPackage").disabled = true;
                  $("createProjectPackage").textContent = "打包中...";
                  $("projectPackageStatus").className = "card muted";
                  $("projectPackageStatus").textContent = "正在生成只包含项目相关文件的压缩包。";
                  try {
                    const result = await api(`/api/projects/${state.projectId}/packages`, { method: "POST" });
                    out(result);
                    await loadRuns();
                    await loadProjectPackages();
                  } catch (error) {
                    const reason = error?.payload?.failureCode || error?.payload?.disabledReason || error?.payload?.error || error?.payload?.status || error?.message || "unknown_error";
                    $("projectPackageStatus").className = "card";
                    $("projectPackageStatus").textContent = `打包失败：${projectPackageDisabledText(reason)} (${reason})`;
                    showError(error);
                  }
                  finally {
                    setLocalBusy(false);
                    $("createProjectPackage").textContent = "打包项目文件";
                    await loadProjectPackages();
                    await refreshActiveRun();
                  }
                }

                async function loadProjectPackages() {
                  if (!state.projectId) {
                    renderProjectPackages({ canCreatePackage: false, disabledReason: "project_not_selected", packages: [] });
                    return;
                  }
                  try {
                    const result = await api(`/api/projects/${state.projectId}/packages`);
                    state.packageList = result;
                    renderProjectPackages(result);
                    writeProjectStateCache({ packageList: result });
                  } catch (error) {
                    $("projectPackageStatus").className = "card muted";
                    $("projectPackageStatus").textContent = "项目文件包列表暂不可用。";
                  }
                }

                function renderProjectPackages(result) {
                  const packages = result?.packages || [];
                  const canCreate = !!result?.canCreatePackage && !isGlobalBusy();
                  $("createProjectPackage").disabled = !canCreate;
                  $("createProjectPackage").title = canCreate ? "" : projectPackageDisabledText(result?.disabledReason);
                  $("openProjectDownloads").disabled = !state.projectId;
                  $("openProjectDownloads").onclick = () => {
                    if (!state.projectId) return;
                    if (typeof v2OpenStepTab === "function") {
                      callV2("v2OpenStepTab", "download-project");
                    } else {
                      window.open(`/downloads?projectId=${encodeURIComponent(state.projectId)}`, "_blank", "noreferrer");
                    }
                  };
                  if (!state.projectId) {
                    $("projectPackageStatus").className = "card muted";
                    $("projectPackageStatus").textContent = "选择项目后显示项目文件包。";
                    return;
                  }
                  if (!result?.canCreatePackage && isProjectPackagePrerequisiteReason(result?.disabledReason)) {
                    $("projectPackageStatus").className = "card muted";
                    $("projectPackageStatus").textContent = projectPackageDisabledText(result.disabledReason);
                    return;
                  }
                  $("projectPackageStatus").className = "card";
                  $("projectPackageStatus").innerHTML = packages.length
                    ? `<strong>已生成 ${packages.length} 个项目文件包</strong><p class="muted">请进入下载页按版本号/时间戳下载。</p>${packages.slice(0, 3).map(renderPackageSummary).join("")}`
                    : "<strong>还没有项目文件包。</strong><p class=\"muted\">点击“打包项目文件”后会生成一个版本化 zip。</p>";
                }

                function renderPackageSummary(item) {
                  return `<p class="muted">${escapeHtml(item.version)} · ${escapeHtml(item.createdUtc || "")} · ${escapeHtml(item.fileName)}</p>`;
                }

                function projectPackageDisabledText(reason) {
                  if (reason === "prototype_not_created") {
                    return state.prototypeFailure === "没有创建有效的godot场景文件"
                      ? "没有创建有效的godot场景文件，成功修复后才可以打包项目文件。"
                      : "成功运行原型创建后才可以打包项目文件。";
                  }
                  if (reason === "project_busy") return "项目有后台任务正在执行，请等待完成。";
                  if (reason === "iteration_plan_not_completed") return "游戏模块完成后才可以打包项目文件。";
                  if (reason === "prototype_acceptance_not_passed") return "游戏模块完成后，需要重新进行原型验收并通过，才可以打包项目文件。";
                  if (reason === "project_not_selected") return "请先选择一个项目。";
                  return "暂不可打包项目文件。";
                }

                function isProjectPackagePrerequisiteReason(reason) {
                  return reason === "prototype_not_created" ||
                    reason === "iteration_plan_not_completed" ||
                    reason === "prototype_acceptance_not_passed";
                }

                async function refreshAssetInventoryAvailability() {
                  if (!state.projectId) {
                    state.assetInventory = null;
                    state.assetInventoryExpanded = false;
                    renderAssetInventory({ canReadInventory: false, disabledReason: "project_not_selected", usedAssets: [], generationCandidates: [] }, false);
                    return;
                  }
                  try {
                    const result = await api(`/api/projects/${state.projectId}/asset-inventory?judge=false`);
                    state.assetInventory = result;
                    renderAssetInventory(result, state.assetInventoryExpanded);
                    writeProjectStateCache({ assetInventory: result });
                  } catch {
                    $("loadAssetInventory").disabled = true;
                    $("assetInventoryStatus").className = "card muted";
                    $("assetInventoryStatus").textContent = "素材清单暂不可用。";
                  }
                }

                async function loadAssetInventory() {
                  if (!state.projectId) return out("请先选择一个项目。");
                  if (typeof v2OpenStepTab === "function") {
                    callV2("v2OpenStepTab", "asset-inventory");
                  } else {
                    window.open(`/assets?projectId=${encodeURIComponent(state.projectId)}&model=${encodeURIComponent($("globalModel").value || "gpt-5.5")}`, "_blank", "noreferrer");
                  }
                }

                function renderAssetInventory(result, expanded) {
                  const canRead = !!result?.canReadInventory && !isGlobalBusy();
                  $("loadAssetInventory").disabled = !canRead;
                  $("loadAssetInventory").title = canRead ? "" : assetInventoryDisabledText(result?.disabledReason);
                  if (!state.projectId) {
                    $("assetInventoryStatus").className = "card muted";
                    $("assetInventoryStatus").textContent = "选择项目后显示素材清单入口。";
                    return;
                  }
                  if (!result?.canReadInventory) {
                    $("assetInventoryStatus").className = "card muted";
                    $("assetInventoryStatus").textContent = assetInventoryDisabledText(result?.disabledReason);
                    return;
                  }
                  const usedAssets = result.usedAssets || [];
                  const candidates = result.generationCandidates || [];
                  if (!expanded) {
                    $("assetInventoryStatus").className = "card";
                    $("assetInventoryStatus").innerHTML = `<strong>素材清单可用</strong><p class="muted">已识别 ${escapeHtml(String(usedAssets.length))} 个素材实例，${escapeHtml(String(candidates.length))} 个可生成素材候选。点击“查看素材清单”展开。</p>`;
                    return;
                  }
                  $("assetInventoryStatus").className = "card";
                  $("assetInventoryStatus").innerHTML = `
                    <strong>项目素材清单</strong>
                    <p class="muted">已使用素材实例：${escapeHtml(String(usedAssets.length))} 个；可生成素材候选：${escapeHtml(String(candidates.length))} 个。</p>
                    <h2>已使用素材</h2>
                    <div class="asset-grid">${usedAssets.length ? usedAssets.map(renderUsedAssetItem).join("") : "<p class='muted'>未识别到可预览素材引用。</p>"}</div>
                    <h2>可生成素材候选</h2>
                    <div class="card-list">${candidates.length ? candidates.map(renderAssetCandidateItem).join("") : "<p class='muted'>暂未识别到明显的素材生成候选。</p>"}</div>
                  `;
                }

                function renderUsedAssetItem(item) {
                  return `
                    <div class="card">
                      <img class="asset-preview" src="${escapeHtml(item.previewUrl || "")}" alt="${escapeHtml(item.instanceName || "asset")}">
                      <strong>${escapeHtml(item.instanceName || "")}</strong>
                      <p class="muted">${escapeHtml(item.nodeType || "")}</p>
                      <p class="muted">场景：${escapeHtml(item.scenePath || "")}</p>
                      <p class="muted">用途：${escapeHtml(item.intendedUse || "")}</p>
                      <p class="muted">像素尺寸：${escapeHtml(assetPixelSize(item))}</p>
                      <p class="muted">素材：${escapeHtml(item.resourcePath || "")}</p>
                    </div>
                  `;
                }

                function renderAssetCandidateItem(item) {
                  return `
                    <div class="card">
                      <strong>${escapeHtml(item.instanceName || "")}</strong>
                      <p class="muted">${escapeHtml(item.nodeType || "")} · ${escapeHtml(item.suggestedAssetKind || "")}</p>
                      <p class="muted">场景：${escapeHtml(item.scenePath || "")}</p>
                      <p class="muted">用途：${escapeHtml(item.intendedUse || "")}</p>
                      <p>${escapeHtml(item.reason || "")}</p>
                      <p class="muted">判断状态：${escapeHtml(item.llmJudgementStatus || "")}</p>
                    </div>
                  `;
                }

                function assetInventoryDisabledText(reason) {
                  if (reason === "final_step_not_completed") return "final step 完成后才可以查看素材清单。";
                  if (reason === "project_not_selected") return "请先选择一个项目。";
                  return "素材清单暂不可用。";
                }

                async function runPrototype() {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) {
                    showPrototypeNotice("请先选择一个项目。", "warn");
                    return out("请先选择一个项目。");
                  }
                  await loadLatestPrototypeDraft(true);
                  if (state.draftAnalysisRunning) {
                    showPrototypeNotice("草稿分析仍在进行中，完成前不能启动原型创建。", "warn");
                    return out("草稿分析仍在进行中。");
                  }
                  const payload = buildPrototypePayload();
                  const missing = missingPrototypeFields(payload);
                  if (missing.length) {
                    showPrototypeNotice(`当前还不能启动：缺少必填项 ${missing.map(prototypeFieldLabel).join("、")}。如果你刚分析过 txt 草稿，请先刷新或等待草稿回填完成。`, "warn");
                    return out({ status: "missing_required_fields", missingRequiredFields: missing });
                  }
                  showPrototypeNotice("正在提交原型创建请求，请不要重复点击。", "info");
                  setLocalBusy(true, "原型骨架创建中，请等待当前任务执行完毕。");
                  setPrototypeFormLocked(true);
                  try {
                    const result = await api(`/api/projects/${state.projectId}/prototype-7day-playable`, { method: "POST", body: JSON.stringify(payload) });
                    out(result);
                    showPrototypeNotice(`原型创建请求已提交，状态：${result.status || "queued"}。刷新页面可继续查看创建进度。`, "info");
                    await loadRuns();
                    await loadPrototypeProgress();
                    await loadServerChatHistoryForProject(state.projectId);
                    setLocalBusy(false);
                    await refreshActiveRun();
                  } catch (error) {
                    setLocalBusy(false);
                    setPrototypeFormLocked(false);
                    showPrototypeError(error);
                    showError(error);
                  }
                }

                function buildPrototypePayload() {
                  return {
                    slug: $("protoSlug").value.trim(),
                    hypothesis: $("hypothesis").value.trim(),
                    corePlayerFantasy: $("corePlayerFantasy").value.trim(),
                    minimumPlayableLoop: $("minimumPlayableLoop").value.trim(),
                    successCriteria: $("successCriteria").value.split("\n").map(x => x.trim()).filter(Boolean),
                    gameFeature: $("gameFeature").value.trim(),
                    coreGameplayLoop: $("coreGameplayLoop").value.trim(),
                    winFailConditions: $("winFailConditions").value.trim(),
                    confirm: true,
                    scoreEngine: "deterministic",
                    model: $("globalModel").value
                  };
                }

                function missingPrototypeFields(payload) {
                  const missing = [];
                  if (!payload.slug) missing.push("slug");
                  if (!payload.hypothesis) missing.push("hypothesis");
                  if (!payload.corePlayerFantasy) missing.push("core_player_fantasy");
                  if (!payload.minimumPlayableLoop) missing.push("minimum_playable_loop");
                  if (!payload.successCriteria?.length) missing.push("success_criteria");
                  if (!payload.gameFeature) missing.push("game_feature");
                  if (!payload.coreGameplayLoop) missing.push("core_gameplay_loop");
                  if (!payload.winFailConditions) missing.push("win_fail_conditions");
                  return missing;
                }

                function prototypeFieldLabel(field) {
                  return ({
                    slug: "原型标识",
                    hypothesis: "原型假设",
                    core_player_fantasy: "核心玩家幻想",
                    minimum_playable_loop: "最小可玩循环",
                    success_criteria: "成功标准",
                    game_feature: "游戏功能",
                    core_gameplay_loop: "核心玩法循环",
                    win_fail_conditions: "胜利/失败条件"
                  })[field] || field;
                }

                function showPrototypeNotice(message, level = "info") {
                  $("prototypeProgress").className = level === "warn" ? "card muted" : "card";
                  $("prototypeProgress").innerHTML = `<strong>${escapeHtml(message)}</strong>`;
                }

                function showPrototypeError(error) {
                  const payload = error?.payload || {};
                  const missing = payload.missingRequiredFields || payload.MissingRequiredFields || [];
                  const message = missing.length
                    ? `缺少必填项：${missing.map(prototypeFieldLabel).join("、")}。请补全后再运行原型骨架创建。`
                    : payload.status === "project_busy"
                      ? "当前项目已有后台任务在执行，请等待顶部状态条消失后再启动原型骨架创建。"
                    : payload.failureCode === "prototype_valid_godot_scene_missing"
                      ? "没有创建有效的godot场景文件"
                      : `原型创建请求失败：${payload.status || payload.error || payload.failureCode || error?.status || "unknown_error"}`;
                  showPrototypeNotice(message, "warn");
                }


                async function repairPrototype() {
                  await createRepairPlan();
                }

                async function validatePrototype() {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("请先选择一个项目。");
                  setLocalBusy(true, "原型重新验收中，请等待当前任务执行完毕。");
                  $("validatePrototype").textContent = "验收中...";
                  showPrototypeNotice("正在重新验收当前原型；该操作会运行平台验收、Godot smoke 和项目专属行为验收，不会调用 Codex。", "info");
                  try {
                    const result = await api(`/api/projects/${state.projectId}/prototype-7day-playable/validate`, { method: "POST" });
                    out(result);
                    await loadRuns();
                    await loadPrototypeProgress();
                    await loadProjectPackages();
                    await refreshAssetInventoryAvailability();
                    if (result.status === "failed") {
                      const label = result.progress?.label || result.stderr || "原型验收失败，请查看运行记录并生成修复计划。";
                      showPrototypeNotice(label, "warn");
                    }
                  } catch (error) {
                    showError(error);
                    await loadPrototypeProgress();
                  } finally {
                    setLocalBusy(false);
                    $("validatePrototype").textContent = "重新验收原型";
                    await refreshActiveRun();
                  }
                }

                async function loadPrototypeProgress() {
                  if (!state.projectId) {
                    state.prototypeFailure = "";
                    $("validatePrototype").disabled = true;
                    $("prototypeProgress").className = "card muted";
                    $("prototypeProgress").textContent = "尚未选择项目。";
                    $("prototypeAcceptanceSummary").className = "card muted";
                    $("prototypeAcceptanceSummary").textContent = "尚未选择项目。";
                    $("chatPanel").classList.add("hidden");
                    setFormalFeedbackAvailability(false);
                    return;
                  }
                  try {
                    $("validatePrototype").disabled = isGlobalBusy();
                    const progress = await api(`/api/projects/${state.projectId}/prototype-7day-playable/progress`);
                    const acceptanceStatus = String(progress?.acceptanceStatus || progress?.status || "").trim().toLowerCase();
                    state.prototypeFailure = acceptanceStatus === "failed" ? (progress.acceptanceFailure || progress.failure || "") : "";
                    if (acceptanceStatus === "succeeded") {
                      callV2("v2SetPrototypeValidationInvalidated", false);
                    }
                    renderPrototypeProgress(progress);
                    renderPrototypeAcceptanceSummary(progress);
                    setPrototypeFormLocked(isPrototypeCreationLocked(progress));
                    updateChatPanelVisibility(progress);
                    writeProjectStateCache({ prototypeProgress: progress });
                  } catch (error) { showError(error); }
                }

                function renderPrototypeProgress(progress) {
                  const status = progress.status || "idle";
                  const statusClass = status === "succeeded" ? "status-ok" : status === "failed" ? "status-fail" : "status-warn";
                  $("prototypeProgress").className = "card";
                  $("prototypeProgress").innerHTML = `
                    <strong class="${statusClass}">${escapeHtml(status)}</strong>
                    <p>${escapeHtml(progress.label || "")}</p>
                    <p class="muted">step：${escapeHtml(progress.step || "-")} · substep：${escapeHtml(progress.substep || "-")}</p>
                    ${progress.updatedUtc ? `<p class="muted">更新时间：${escapeHtml(progress.updatedUtc)}</p>` : ""}
                    ${progress.failure ? `<p class="danger">${escapeHtml(sanitizePublicFailureContent(progress.failure))}</p><p class="danger">可以点击“生成修复计划”把失败拆成小步骤，再逐项执行修复。</p>` : ""}
                  `;
                  $("repairPrototype")?.classList.toggle("hidden", true);
                }

                function renderPrototypeAcceptanceSummary(progress) {
                  const status = progress?.status || "idle";
                  if (status === "failed") {
                    const failure = sanitizePublicFailureContent(progress?.failure || "原型验收未通过。");
                    $("prototypeAcceptanceSummary").className = "card";
                    $("prototypeAcceptanceSummary").innerHTML = `
                      <strong>原型验收摘要</strong>
                      <p class="danger">${escapeHtml(failure)}</p>
                      <p class="muted">当前项目尚未满足原型成功标准，暂不展示默认场景、验证摘要和试玩重点。</p>
                    `;
                    return;
                  }
                  if (status !== "succeeded") {
                    $("prototypeAcceptanceSummary").className = "card muted";
                    $("prototypeAcceptanceSummary").textContent = "原型完成后，这里会显示默认场景、验证摘要数量和建议试玩重点。";
                    return;
                  }
                  const defaultScene = progress?.defaultSceneLabel || progress?.defaultScene || "未识别";
                  const tddSummaryCount = Number(progress?.tddSummaryCount || 0);
                  const redCount = Number(progress?.tddRedCount || 0);
                  const greenCount = Number(progress?.tddGreenCount || 0);
                  const refactorCount = Number(progress?.tddRefactorCount || 0);
                  const nextStepSource = formatNextStepSource(progress?.nextStepSource);
                  const nextStepEvaluation = formatNextStepEvaluation(progress?.nextStepEvaluation);
                  const nextStepEvaluationReason = String(progress?.nextStepEvaluationReason || "").trim();
                  const focusPoints = Array.isArray(progress?.playtestFocusPoints) ? progress.playtestFocusPoints.filter(Boolean) : [];
                  $("prototypeAcceptanceSummary").className = "card";
                  $("prototypeAcceptanceSummary").innerHTML = `
                    <strong>原型验收摘要</strong>
                    <p class="muted">默认场景：${escapeHtml(defaultScene)}</p>
                    <p class="muted">验证摘要：共 ${escapeHtml(String(tddSummaryCount))} 份 · 红灯 ${escapeHtml(String(redCount))} · 绿灯 ${escapeHtml(String(greenCount))} · 重构 ${escapeHtml(String(refactorCount))}</p>
                    <p class="muted">下一步建议来源：${escapeHtml(nextStepSource)}</p>
                    <p class="muted">继续优化评估：${escapeHtml(nextStepEvaluation)}</p>
                    ${nextStepEvaluationReason ? `<p class="muted">${escapeHtml(nextStepEvaluationReason)}</p>` : ""}
                    ${focusPoints.length ? `<div><strong>建议试玩重点</strong><ul>${focusPoints.map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul></div>` : "<p class='muted'>暂无试玩重点建议。</p>"}
                  `;
                }

                function updateChatPanelVisibility(progress) {
                  const status = progress?.acceptanceStatus || progress?.status || "idle";
                  $("prototypeWorkflowPanel").classList.toggle("hidden", status === "succeeded");
                  $("chatPanel").classList.remove("hidden");
                  setFormalFeedbackAvailability(status === "succeeded");
                  if (status === "succeeded") {
                    seedChatFromPrototypeProgress(progress);
                  }
                }

                function setFormalFeedbackAvailability(canSubmit) {
                  state.prototypeReadyForFeedback = canSubmit;
                  const routeGoal = currentNeedsFixRouteGoal();
                  $("submitFormalFeedback").disabled = !canSubmit;
                  $("submitFormalFeedback").textContent = !canSubmit
                    ? "需先完成原型骨架创建后才能提交反馈"
                    : routeGoal
                      ? `提交到 Needs Fix 路由 step ${String(routeGoal.goalIndex || "")}`
                      : "提交反馈到 Needs Fix 路由";
                  renderChatHistory();
                }

                function seedChatFromPrototypeProgress(progress) {
                  if (state.chatHistory.some(message => message.role === "assistant" && message.kind === "prototype-seed")) return;
                  const seedContent = prototypeSeedMessage(progress);
                  state.chatHistory.unshift({
                    role: "assistant",
                    kind: "prototype-seed",
                    content: seedContent,
                    suggestedFeedback: state.nextSuggestedFeedback || defaultNextSuggestedFeedback()
                  });
                  renderChatHistory();
                  saveChatHistoryForProject();
                }

                function prototypeSeedMessage(progress) {
                  const status = progress?.status || "succeeded";
                  if (status === "succeeded") {
                    const realSummary = sanitizePublicChatContent(progress?.completionSummary || "");
                    if (realSummary) {
                      updateContinueSuggestionFromText(realSummary);
                      setFormalFeedbackAvailability(true);
                      return `下一步建议来源：${formatNextStepSource(progress?.nextStepSource)}\n继续优化评估：${formatNextStepEvaluation(progress?.nextStepEvaluation)}\n${String(progress?.nextStepEvaluationReason || "").trim()}\n\n${realSummary}`.trim();
                    }
                    const suggestion = defaultNextSuggestedFeedback();
                    state.nextSuggestedFeedback = suggestion;
                    setFormalFeedbackAvailability(true);
                    return `下一步建议来源：${formatNextStepSource(progress?.nextStepSource)}\n继续优化评估：${formatNextStepEvaluation(progress?.nextStepEvaluation)}\n${String(progress?.nextStepEvaluationReason || "").trim()}\n\n原型创建完成。\n\n本次完成：\n1. 已生成可玩的原型基础版本。\n2. 已完成基础启动检查。\n3. 已进入可继续优化状态。\n\n下一步建议：\n${suggestion}\n\n如需执行，请使用游戏模块或 Needs Fix 的固定功能按钮。`.trim();
                  }
                  if (status === "failed") {
                    return "原型创建未完成。你可以描述看到的问题，我可以帮你整理修复思路；需要执行修复时，请使用固定的修复按钮。";
                  }
                  return "原型流程已有进度。你可以继续说明目标或补充需求，我会按当前项目上下文协助梳理。";
                }

                function formatNextStepSource(value) {
                  const normalized = String(value || "").trim().toLowerCase();
                  if (normalized === "codex") return "Codex 输出";
                  if (normalized === "record") return "原型记录";
                  return "系统生成";
                }

                function formatNextStepEvaluation(value) {
                  const normalized = String(value || "").trim().toLowerCase();
                  if (normalized === "recommended") return "建议继续";
                  if (normalized === "caution") return "建议谨慎";
                  if (normalized === "not_recommended") return "暂不建议";
                  return "待判断";
                }

                function defaultNextSuggestedFeedback() {
                  return "请继续优化这个半成品原型：优先检查首分钟体验、操作反馈、目标提示、胜负条件和基础手感；如果发现明显短板，请直接改进并在完成后给出新的下一步建议。";
                }

                function currentIterationPlanDecision() {
                  return String(state.iterationPlanEvaluation?.decision || "").trim().toLowerCase();
                }

                function currentIterationPlanRegenerationPrompt() {
                  const decision = currentIterationPlanDecision();
                  if (decision !== "should_refine_plan") return "";
                  return String(state.iterationPlanEvaluation?.suggestedPromptForRegeneration || "").trim();
                }

                function syncIterationPlanRegenerationSuggestion() {
                  const suggestion = currentIterationPlanRegenerationPrompt();
                  if (suggestion) {
                    state.nextSuggestedFeedback = suggestion;
                  }
                }

                function updateContinueSuggestionFromText(text) {
                  const sanitized = sanitizePublicChatContent(text || "");
                  const match = sanitized.match(/下一步建议[：:]\s*([\s\S]{1,800}?)(?:\n\s*\n(?:如果你同意|如你同意|若你同意)|$)/);
                  state.nextSuggestedFeedback = match ? match[1].trim() : defaultNextSuggestedFeedback();
                  const lastAssistant = state.chatHistory.filter(message => message.role === "assistant" && !message.pending).slice(-1)[0];
                  if (lastAssistant && !lastAssistant.continueConsumed && !lastAssistant.suggestedFeedback) {
                    lastAssistant.suggestedFeedback = state.nextSuggestedFeedback;
                  }
                  setFormalFeedbackAvailability(state.prototypeReadyForFeedback);
                }

                function isPrototypeCreationLocked(progress) {
                  const status = progress?.prototypeCreationStatus || progress?.status || "idle";
                  return !["idle", "failed"].includes(status);
                }

                function setPrototypeFormLocked(locked) {
                  prototypeInputIds.forEach(id => $(id).disabled = locked);
                  $("runPrototype").disabled = locked || isGlobalBusy();
                  $("runPrototype").textContent = locked ? "原型骨架创建中..刷新页面查阅创建进度." : "运行原型骨架创建";
                  if ($("repairPrototype")) {
                    $("repairPrototype").disabled = locked || isGlobalBusy();
                    $("repairPrototype").textContent = locked ? "修复计划处理中..刷新页面查阅进度." : "生成修复计划";
                  }
                }

                async function runTdd(stage) {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("请先选择一个项目。");
                  setLocalBusy(true, "TDD 命令执行中，请等待当前任务执行完毕。");
                  try {
                    const payload = {
                      slug: $("tddSlug").value.trim(),
                      stage,
                      expect: "auto",
                      filter: $("testFilter").value.trim() || null,
                      timeoutSec: 300,
                      dotnetTarget: $("dotnetTarget").value.split("\n").map(x => x.trim()).filter(Boolean)
                    };
                    const result = await api(`/api/projects/${state.projectId}/prototype-tdd`, { method: "POST", body: JSON.stringify(payload) });
                    out(result);
                    await loadRuns();
                  } catch (error) { showError(error); }
                  finally {
                    setLocalBusy(false);
                    await refreshActiveRun();
                  }
                }

                async function createScene() {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("请先选择一个项目。");
                  setLocalBusy(true, "原型场景创建中，请等待当前任务执行完毕。");
                  try {
                    const payload = { slug: $("tddSlug").value.trim(), sceneRoot: $("sceneRoot").value.trim() || "Node2D" };
                    const result = await api(`/api/projects/${state.projectId}/prototype-scene`, { method: "POST", body: JSON.stringify(payload) });
                    out(result);
                    await loadRuns();
                  } catch (error) { showError(error); }
                  finally {
                    setLocalBusy(false);
                    await refreshActiveRun();
                  }
                }

                function showError(error) {
                  out(error && error.payload ? { status: error.status, ...error.payload } : String(error));
                }

                function escapeHtml(value) {
                  return String(value || "").replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#039;" }[ch]));
                }

                $("saveToken").onclick = () => {
                  persistAccessTokenFromInput();
                  $("sessionStatus").textContent = token() ? "Token 验证中..." : "Token 已清空。";
                  if (token()) refreshProjects(); else showLoggedOut();
                };
                $("token").addEventListener("input", persistAccessTokenFromInput);
                $("token").addEventListener("change", persistAccessTokenFromInput);
                $("logout").onclick = () => {
                  localStorage.removeItem("phaseAAdminToken");
                  localStorage.removeItem("phaseAAccessToken");
                  clearBrowserCookie("phaseAAccessToken");
                  $("token").value = "";
                  state.projectId = "";
                  writeSelectedProjectId("");
                  state.projects = [];
                  showLoggedOut();
                };
                $("openCreateProjectPage").onclick = () => showCreateProjectPage();
                $("openProjectListModal").onclick = async () => {
                  setModalVisible("projectListModal", true);
                  await refreshProjects({ autoSelect: false });
                };
                $("closeProjectListModal").onclick = () => setModalVisible("projectListModal", false);
                $("refreshProjects").onclick = () => refreshProjects({ autoSelect: false });
                $("createProject").onclick = createProject;
                ["projectName", "gameName", "gameTypeSource"].forEach(id => {
                  $(id)?.addEventListener("input", () => validateCreateProjectForm(false));
                });
                $("createUserAccount").onclick = createUserAccount;
                $("copyOneTimeToken").onclick = async () => {
                  const value = $("oneTimeTokenValue").value || "";
                  try {
                    await navigator.clipboard.writeText(value);
                    $("oneTimeTokenCopyStatus").textContent = "Token copied.";
                  } catch {
                    $("oneTimeTokenValue").focus();
                    $("oneTimeTokenValue").select();
                    $("oneTimeTokenCopyStatus").textContent = "Copy failed. The token is selected; press Ctrl+C.";
                  }
                };
                $("closeOneTimeToken").onclick = () => {
                  $("oneTimeTokenValue").value = "";
                  $("oneTimeTokenModal").classList.add("hidden");
                };
                $("downloadAiCodeMirrorKeyTemplate").onclick = downloadAiCodeMirrorKeyTemplate;
                $("importAiCodeMirrorKeyCsv").onclick = importAiCodeMirrorKeyCsv;
                $("refreshAiCodeMirrorKeys").onclick = loadAiCodeMirrorKeys;
                $("refreshUserAccounts").onclick = loadUserAccounts;
                $("loadAdminLlmUsage").onclick = loadAdminLlmUsage;
                $("loadAdminLlmUsageAggregate").onclick = loadAdminLlmUsageAggregate;
                $("downloadAdminLlmUsageCsv").onclick = downloadAdminLlmUsageCsv;
                $("loadAdminLlmRuns").onclick = loadAdminLlmRuns;
                $("loadAdminRunMetrics").onclick = loadAdminRunMetrics;
                $("openAdminRunDurationMetrics").onclick = openAdminRunDurationMetrics;
                $("openAdminChatAverageMetrics").onclick = openAdminChatAverageMetrics;
                $("loadAccountAudit").onclick = loadAccountAudit;
                $("downloadAccountAuditCsv").onclick = downloadAccountAuditCsv;
                $("importDraft").onclick = importDraft;
                $("draftFile").onchange = updateDraftImportButtonState;
                $("sendChat").onclick = sendChat;
                $("createGddDocument").onclick = createGddDocument;
                $("syncChatHistory").onclick = syncChatHistory;
                $("downloadChatHistory").onclick = downloadChatHistory;
                $("chatAttachmentFiles").onchange = loadChatAttachmentFiles;
                $("clearChatAttachments").onclick = clearChatAttachments;
                renderChatAttachments();
                $("evaluateIterationPlanFromChat").onclick = () => evaluateIterationPlan(true);
                $("submitFormalFeedback").onclick = submitFormalFeedback;
                $("createIterationPlan").onclick = createIterationPlan;
                $("deleteIterationPlan").onclick = deleteIterationPlan;
                $("evaluateIterationPlan").onclick = () => evaluateIterationPlan(false);
                $("executeIterationGoal").onclick = executeIterationGoal;
                $("confirmIterationPlanUpdate").onclick = confirmIterationPlanUpdate;
                $("closeIterationPlanUpdateModal").onclick = () => setModalVisible("iterationPlanUpdateModal", false);
                $("iterationPlanUpdateInput").addEventListener("input", event => autoGrowTextarea(event.target));
                $("createRepairPlan").onclick = createRepairPlan;
                $("executeRepairStep").onclick = executeRepairStep;
                $("chatSkillMode").onchange = () => {
                  renderSelectedSkillAction();
                  callV2("v2WriteProjectUiState");
                };
                window.addEventListener("beforeunload", () => {
                  callV2("v2WriteProjectUiState");
                });
                window.addEventListener("message", event => {
                  if (event.origin !== location.origin) return;
                  if (event.data?.type !== "phasea:gdd-outline-deleted") return;
                  if (event.data?.projectId && event.data.projectId !== state.projectId) return;
                  state.gddOutlineReady = false;
                  if ($("createGddDocument")) $("createGddDocument").textContent = "\u521b\u5efa\u7b56\u5212\u5927\u7eb2";
                  refreshGddOutlineStatus();
                });
                renderChatHistory();
                $("loadRuns").onclick = loadRuns;
                $("createProjectPackage").onclick = createProjectPackage;
                $("loadAssetInventory").onclick = loadAssetInventory;
                $("runPrototype").onclick = runPrototype;
                if ($("repairPrototype")) $("repairPrototype").onclick = repairPrototype;
                $("refreshPrototypeProgress").onclick = loadPrototypeProgress;
                $("validatePrototype").onclick = validatePrototype;
                $("createScene").onclick = createScene;
                document.querySelectorAll(".runTdd").forEach(button => button.onclick = () => runTdd(button.dataset.stage));
                document.addEventListener("click", event => {
                  const button = event.target?.closest?.("[data-needs-fix-goal]");
                  if (!button) return;
                  event.preventDefault();
                  runNeedsFixIterationGoal(button.dataset.needsFixGoal);
                });
                setTokenFromStorage();
                if (token()) refreshProjects(); else showLoggedOut();
                setTimeout(() => {
                  const currentToken = token();
                  if (currentToken) {
                    persistAccessTokenFromInput();
                    if (!state.authenticated) refreshProjects();
                  }
                }, 250);
                setInterval(refreshActiveRun, 5000);
              </script>
            </body>
            </html>
            """;
    }

    public string RenderProject(ProjectSnapshot project, IReadOnlyList<RunReadbackItem> runs)
    {
        var steps = BuildProjectDetailSteps(project, runs);
        var progressItems = string.Join("", steps.Select(step => $"""
            <a class="detail-step {step.Status}" href="{step.Href}">
              <span class="detail-step-number">{step.Number}</span>
              <span class="detail-step-icon" aria-hidden="true"></span>
              <span class="detail-step-label">{Encode(step.Label)}</span>
              <span class="detail-step-mark">{Encode(step.Mark)}</span>
            </a>
            """));
        var runItems = string.Join("", runs.Select(run =>
            $"<li><a href=\"/runs/{Encode(run.RunId)}\">{Encode(run.RunType)}</a> - {Encode(run.Status)}</li>"));
        var body = $$"""
            <style>
              :root { --ink: #17211b; --muted: #66736b; --paper: #fbf7ef; --panel: #fffdf8; --line: #ded4c4; --accent: #15905f; --danger: #b73732; --pending: #a8afad; }
              * { box-sizing: border-box; }
              body { margin: 0; font-family: Georgia, "Times New Roman", serif; color: var(--ink); background: linear-gradient(135deg, #fbf7ef, #efe5d3); }
              main { max-width: 96rem; margin: 0 auto; padding: 1.5rem 1rem 3rem; display: grid; gap: 1rem; }
              h1 { margin: 0; font-size: clamp(1.8rem, 4vw, 3.2rem); letter-spacing: 0; }
              p { color: var(--muted); }
              .card { background: var(--panel); border: 1px solid var(--line); border-radius: 0.75rem; padding: 1rem; box-shadow: 0 1rem 2.4rem rgba(57, 43, 24, 0.1); }
              .detail-progress { display: grid; grid-template-columns: repeat(9, minmax(5.6rem, 1fr)); gap: 0.5rem; overflow-x: auto; padding-bottom: 0.2rem; }
              .detail-step { min-width: 5.6rem; display: grid; justify-items: center; gap: 0.25rem; padding: 0.35rem 0.3rem 0.62rem; color: var(--muted); text-decoration: none; background: #fffdf8; border: 1px solid var(--line); border-radius: 0.75rem; }
              .detail-step-number { color: var(--accent); font-size: 0.82rem; line-height: 1; font-weight: 800; }
              .detail-step-icon { width: 2rem; height: 2rem; border-radius: 999px; background: #eef0ec; border: 2px solid var(--pending); }
              .detail-step-label { min-height: 2.2rem; display: grid; place-items: center; text-align: center; font-size: 0.86rem; line-height: 1.2; }
              .detail-step-mark { width: 1.15rem; height: 1.15rem; border-radius: 999px; display: grid; place-items: center; color: #fff; font-size: 0.8rem; font-weight: 800; background: var(--pending); }
              .detail-step.done { color: var(--ink); }
              .detail-step.done .detail-step-icon { border-color: var(--accent); background: #e6f4ef; }
              .detail-step.done .detail-step-mark { background: var(--accent); }
              .detail-step.fix { color: var(--ink); }
              .detail-step.fix .detail-step-icon { border-color: var(--danger); background: #fae9e6; }
              .detail-step.fix .detail-step-mark { background: var(--danger); }
              .detail-meta { display: grid; grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr)); gap: 0.75rem; }
              .detail-meta div { display: grid; gap: 0.15rem; }
              .detail-meta strong { color: var(--muted); font-size: 0.82rem; }
              ul { margin: 0; padding-left: 1.2rem; }
            </style>
            <main>
              <header>
                <h1>{{Encode(project.Name)}}</h1>
                <p>{{Encode(project.GameName)}}</p>
              </header>
              <section class="card detail-progress" aria-label="项目进度">
                {{progressItems}}
              </section>
              <section class="card detail-meta">
                <div><strong>项目类型</strong><span>{{Encode(project.GameTypeSource)}}</span></div>
                <div><strong>初始化状态</strong><span>{{Encode(project.BootstrapStatus)}}</span></div>
                <div><strong>项目 ID</strong><span>{{Encode(project.ProjectId)}}</span></div>
              </section>
              <section class="card">
                <h2>执行记录</h2>
                <ul>{{runItems}}</ul>
              </section>
            </main>
            """;
        return WrapSimplePage(Encode(project.Name), body);
    }

    private static IReadOnlyList<ProjectDetailStep> BuildProjectDetailSteps(ProjectSnapshot project, IReadOnlyList<RunReadbackItem> runs)
    {
        var latestPrototype = LatestRun(runs, "prototype-7day-playable");
        var latestRepair = LatestRun(runs, "prototype-repair-step", "prototype-quick-fix");
        var latestIteration = LatestRun(runs, "prototype-iteration-goal", "prototype-feedback-iteration");
        var latestUiOptimization = LatestRun(runs, "prototype-ui-optimization");
        var latestAssetInventory = LatestRun(runs, "project-asset-inventory");
        var latestPackage = LatestRun(runs, "project-package");
        var prototypeFailed = latestPrototype?.Status == "failed";
        var prototypeSucceeded = latestPrototype?.Status == "succeeded";

        return
        [
            new ProjectDetailStep(1, "游戏项目详情", "done", "/", "✓"),
            CreateRunStep(2, "原型骨架创建", latestPrototype, "/#prototypeWorkflowPanel"),
            prototypeFailed && latestRepair is null
                ? new ProjectDetailStep(3, "骨架验收修复", "fix", "/#v2RepairPanel", "×")
                : latestRepair is not null
                    ? CreateRunStep(3, "骨架验收修复", latestRepair, "/#v2RepairPanel")
                    : prototypeSucceeded
                        ? new ProjectDetailStep(3, "骨架验收修复", "done", "/#v2RepairPanel", "✓")
                        : CreateRunStep(3, "骨架验收修复", latestRepair, "/#v2RepairPanel"),
            CreateRunStep(4, "完成游戏模块", latestIteration, "/#v2IterationPanel"),
            CreateUiOptimizationStep(5, latestUiOptimization, "/#v2UiOptimizationPanel"),
            CreateAcceptanceStep(6, runs, latestIteration, "/#v2AcceptancePanel"),
            CreateRunStep(7, "确认素材清单", latestAssetInventory, $"/assets?projectId={Uri.EscapeDataString(project.ProjectId)}"),
            CreateRunStep(8, "打包下载项目", latestPackage, $"/downloads?projectId={Uri.EscapeDataString(project.ProjectId)}")
        ];
    }

    private static ProjectDetailStep CreateAcceptanceStep(int number, IReadOnlyList<RunReadbackItem> runs, RunReadbackItem? latestIterationRun, string href)
    {
        var latestValidation = runs
            .Where(run => string.Equals(run.RunType, "prototype-7day-playable", StringComparison.OrdinalIgnoreCase) &&
                          IsValidationOnlyRun(run))
            .OrderByDescending(RunSortTimeUtc)
            .ThenByDescending(run => run.RunId, StringComparer.Ordinal)
            .FirstOrDefault();
        if (latestValidation is null ||
            latestIterationRun is null ||
            !string.Equals(latestIterationRun.Status, "succeeded", StringComparison.OrdinalIgnoreCase) ||
            RunSortTimeUtc(latestValidation) < RunSortTimeUtc(latestIterationRun))
        {
            return new ProjectDetailStep(number, "原型验收", "pending", href, "");
        }

        return latestValidation.Status switch
        {
            "succeeded" => new ProjectDetailStep(number, "原型验收", "done", href, "✓"),
            "failed" => new ProjectDetailStep(number, "原型验收", "fix", href, "×"),
            _ => new ProjectDetailStep(number, "原型验收", "pending", href, "")
        };
    }

    private static ProjectDetailStep CreateRunStep(int number, string label, RunReadbackItem? run, string href)
    {
        if (run is null)
        {
            return new ProjectDetailStep(number, label, "pending", href, "");
        }

        return run.Status switch
        {
            "succeeded" => new ProjectDetailStep(number, label, "done", href, "✓"),
            "failed" => new ProjectDetailStep(number, label, "fix", href, "×"),
            _ => new ProjectDetailStep(number, label, "pending", href, "")
        };
    }

    private static ProjectDetailStep CreateUiOptimizationStep(int number, RunReadbackItem? run, string href)
    {
        if (run is null)
        {
            return new ProjectDetailStep(number, "游戏界面优化", "pending", href, "");
        }

        if (string.Equals(run.ProgressSubstep, "validation_skipped", StringComparison.OrdinalIgnoreCase))
        {
            return new ProjectDetailStep(number, "游戏界面优化", "pending", href, "");
        }

        if (string.Equals(run.ProgressSubstep, "validation_failed", StringComparison.OrdinalIgnoreCase))
        {
            return new ProjectDetailStep(number, "游戏界面优化", "fix", href, "×");
        }

        return CreateRunStep(number, "游戏界面优化", run, href);
    }

    private static RunReadbackItem? LatestRun(IReadOnlyList<RunReadbackItem> runs, params string[] runTypes)
    {
        return runs.FirstOrDefault(run => runTypes.Contains(run.RunType, StringComparer.OrdinalIgnoreCase));
    }

    private static DateTimeOffset RunSortTimeUtc(RunReadbackItem run)
    {
        return ParseUtc(run.ProgressUpdatedUtc) ?? DateTimeOffset.MinValue;
    }

    private static DateTimeOffset? ParseUtc(string? value)
    {
        return DateTimeOffset.TryParse(value, out var parsed) ? parsed : null;
    }

    private static bool IsValidationOnlyRun(RunReadbackItem run)
    {
        if (string.IsNullOrWhiteSpace(run.EvidenceJson))
        {
            return false;
        }

        try
        {
            using var document = System.Text.Json.JsonDocument.Parse(run.EvidenceJson);
            return document.RootElement.TryGetProperty("validation_only", out var value) &&
                   value.ValueKind == System.Text.Json.JsonValueKind.True;
        }
        catch (System.Text.Json.JsonException)
        {
            return false;
        }
    }

    private sealed record ProjectDetailStep(int Number, string Label, string Status, string Href, string Mark);

    public string RenderRun(RunSnapshot run, IReadOnlyList<ArtifactSnapshot> artifacts)
    {
        var artifactLinks = string.Join("", artifacts.Select(artifact =>
            $"<li><a href=\"/artifacts/{Encode(artifact.ArtifactId)}\">{Encode(artifact.ArtifactType)}</a> - {Encode(artifact.RelativePath)}</li>"));
        var body = $"""
            <h1>Run {Encode(run.RunId)}</h1>
            <p>Status: {Encode(run.Status)}</p>
            <p>Type: {Encode(run.RunType)}</p>
            <h2>Stdout</h2>
            <pre>{Encode(run.StdoutText ?? "")}</pre>
            <h2>Stderr</h2>
            <pre>{Encode(run.StderrText ?? "")}</pre>
            <ul>{artifactLinks}</ul>
            """;
        return WrapSimplePage($"Run {Encode(run.RunId)}", body);
    }

    public string RenderGddOutline()
    {
        return """
            <!doctype html>
            <html lang="zh-CN">
            <head>
              <meta charset="utf-8">
              <meta name="viewport" content="width=device-width, initial-scale=1">
              <title>&#31574;&#21010;&#22823;&#32434;</title>
              <style>
                :root { --ink:#17211b; --muted:#66736b; --paper:#fbf7ef; --panel:#fffdf8; --line:#ded4c4; --accent:#0f6b57; --accent2:#c65f2d; --danger:#a2342f; }
                * { box-sizing: border-box; }
                body { margin:0; font-family: Georgia,"Times New Roman",serif; color:var(--ink); background:linear-gradient(135deg,#fbf7ef,#efe5d3); }
                main { max-width: 1180px; margin: 0 auto; padding: 1.2rem; display:grid; gap:1rem; }
                header, section, article, dialog { background:rgba(255,252,245,.92); border:1px solid var(--line); border-radius:1rem; padding:1rem; }
                header { display:flex; justify-content:space-between; gap:1rem; align-items:start; }
                h1,h2,h3 { margin:.1rem 0 .6rem; }
                p { color:var(--muted); white-space:pre-wrap; }
                button { border:0; border-radius:.75rem; background:var(--accent); color:white; font-weight:700; padding:.65rem .9rem; cursor:pointer; }
                button.secondary { background:var(--accent2); }
                button.ghost { background:transparent; color:var(--accent); border:1px solid var(--accent); }
                button:disabled { opacity:.5; cursor:not-allowed; }
                textarea { width:100%; min-height:8rem; resize:vertical; border:1px solid var(--line); border-radius:.75rem; padding:.75rem; background:#fffdf8; color:var(--ink); font:inherit; }
                .muted { color:var(--muted); }
                .danger { color:var(--danger); }
                .grid { display:grid; grid-template-columns: minmax(0,1fr); gap:.8rem; }
                .section-card { display:grid; gap:.55rem; align-content:start; }
                .section-content { color:var(--ink); white-space:pre-wrap; }
                .section-header { display:flex; align-items:flex-start; justify-content:space-between; gap:.75rem; }
                .section-header h3 { margin:0; }
                .section-header button { width:auto; min-width:4.5rem; white-space:nowrap; }
                dialog { width:min(840px, calc(100vw - 2rem)); max-height:90vh; overflow:auto; box-shadow:0 2rem 5rem rgba(23,33,27,.28); }
                dialog::backdrop { background:rgba(23,33,27,.45); }
                .row { display:flex; flex-wrap:wrap; gap:.5rem; align-items:center; }
                .row button:last-child { margin-left:auto; }
                .outline-toolbar { justify-content:flex-end; margin-bottom:.8rem; }
                .outline-toolbar button:last-child { margin-left:0; }
                body.embedded { background:#fffdf8; }
                body.embedded main { max-width:none; padding:0; }
                body.embedded main > header { display:none; }
                body.embedded .outline-toolbar { padding:.25rem 0 .75rem; }
                body.embedded section, body.embedded article, body.embedded dialog { box-shadow:none; }
              </style>
            </head>
            <body>
              <main>
                <header>
                  <div>
                    <h1>&#31574;&#21010;&#22823;&#32434;</h1>
                    <p id="meta" class="muted">&#27491;&#22312;&#35835;&#21462;&#31574;&#21010;&#22823;&#32434;...</p>
                  </div>
                </header>
                <div class="row outline-toolbar" aria-label="GDD outline actions">
                  <button id="deleteGddOutline" class="ghost" type="button">&#21024;&#38500;&#31574;&#21010;&#22823;&#32434;</button>
                  <button id="exportGddMarkdown" class="secondary" type="button">&#23548;&#20986;&#20026; GDD.md</button>
                </div>
                <section>
                  <h2 id="title">-</h2>
                  <p id="summary"></p>
                </section>
                <section class="grid" id="sections"></section>
              </main>
              <dialog id="editor">
                <h2 id="editorTitle"></h2>
                <label><strong>&#39592;&#26550;&#20449;&#24687;</strong><textarea id="editorSkeleton" readonly></textarea></label>
                <label><strong>&#20855;&#20307;&#20869;&#23481;</strong><textarea id="editorContent" readonly></textarea></label>
                <label><strong>&#36755;&#20837;&#20449;&#24687;</strong><textarea id="editorMessage" placeholder="&#36755;&#20837;&#26412;&#26465;&#30446;&#30340;&#34917;&#20805;&#35201;&#27714;"></textarea></label>
                <div class="row">
                  <button id="generateSection" class="secondary">&#29983;&#25104;&#20855;&#20307;&#20869;&#23481;</button>
                  <button id="closeEditor" class="ghost">&#20851;&#38381;</button>
                </div>
              </dialog>
              <script>
                const params = new URLSearchParams(location.search);
                const projectId = params.get("projectId") || "";
                if (params.get("embedded") === "1") document.body.classList.add("embedded");
                const readBrowserCookie = name => {
                  const prefix = `${encodeURIComponent(name)}=`;
                  return document.cookie.split(";").map(part => part.trim()).find(part => part.startsWith(prefix))?.slice(prefix.length) || "";
                };
                const token = () => localStorage.getItem("phaseAAccessToken")
                  || decodeURIComponent(readBrowserCookie("phaseAAccessToken") || "")
                  || localStorage.getItem("phaseAAdminToken")
                  || window.parent?.document?.getElementById?.("token")?.value?.trim?.()
                  || "";
                const $ = id => document.getElementById(id);
                const escapeHtml = value => String(value || "").replace(/[&<>"']/g, ch => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", "\"":"&quot;", "'":"&#039;" }[ch]));
                let outline = null;
                let selectedSection = null;
                async function api(path, options = {}) {
                  const response = await fetch(path, { ...options, headers: { "Authorization": `Bearer ${token()}`, "Content-Type": "application/json", ...(options.headers || {}) }, cache: "no-store" });
                  const text = await response.text();
                  let payload = {};
                  try { payload = text ? JSON.parse(text) : {}; } catch { payload = { raw: text }; }
                  if (!response.ok) throw { status: response.status, payload };
                  return payload;
                }
                async function loadOutline() {
                  if (!projectId) { $("meta").innerHTML = "<span class='danger'>&#32570;&#23569; projectId&#12290;</span>"; return; }
                  if (!token()) { $("meta").innerHTML = "<span class='danger'>&#35831;&#20808;&#30331;&#24405;&#25511;&#21046;&#21488;&#12290;</span>"; return; }
                  try {
                    outline = await api(`/api/projects/${projectId}/gdd/outline`);
                    renderOutline();
                  } catch (error) {
                    $("meta").innerHTML = `<span class="danger">&#35835;&#21462;&#22833;&#36133;&#65306;${escapeHtml(error?.payload?.error || "gdd_outline_not_found")}</span>`;
                  }
                }
                function renderOutline() {
                  const hasSections = Array.isArray(outline.sections) && outline.sections.length > 0;
                  $("meta").textContent = hasSections
                    ? `已载入策划大纲${outline.lastUpdatedUtc ? ` · ${outline.lastUpdatedUtc}` : ""}`
                    : "当前策划大纲不可用，请删除后重新创建。";
                  $("deleteGddOutline").disabled = false;
                  $("exportGddMarkdown").disabled = !hasSections;
                  $("title").textContent = outline.title || "\u7b56\u5212\u5927\u7eb2";
                  $("summary").textContent = outline.summary || "";
                  $("sections").innerHTML = (outline.sections || []).map(section => `
                    <article class="section-card" data-section-id="${escapeHtml(section.id)}">
                      <div class="section-header">
                        <h3>${escapeHtml(section.title)}</h3>
                        <button type="button" data-edit-section="${escapeHtml(section.id)}">&#32534;&#36753;</button>
                      </div>
                      <p><strong>&#39592;&#26550;</strong><br>${escapeHtml(section.skeleton)}</p>
                      <div class="section-content">${section.content ? escapeHtml(section.content) : "<span class='muted'>&#20855;&#20307;&#20869;&#23481;&#24453;&#29983;&#25104;&#12290;</span>"}</div>
                    </article>
                  `).join("") || "<p class='muted'>&#27809;&#26377;&#22823;&#32434;&#26465;&#30446;&#12290;</p>";
                  document.querySelectorAll("[data-edit-section]").forEach(button => button.onclick = () => openEditor(button.dataset.editSection));
                }
                function openEditor(sectionId) {
                  selectedSection = (outline.sections || []).find(item => item.id === sectionId);
                  if (!selectedSection) return;
                  $("editorTitle").textContent = selectedSection.title;
                  $("editorSkeleton").value = selectedSection.skeleton || "";
                  $("editorContent").value = selectedSection.content || "";
                  $("editorMessage").value = "";
                  $("editor").showModal();
                }
                async function generateSection() {
                  if (!selectedSection) return;
                  const button = $("generateSection");
                  button.disabled = true;
                  button.textContent = "\u751f\u6210\u4e2d...";
                  try {
                    await api(`/api/projects/${projectId}/gdd/outline/sections/${encodeURIComponent(selectedSection.id)}`, { method:"POST", body: JSON.stringify({ message: $("editorMessage").value, model: localStorage.getItem("phaseASelectedModel") || null }) });
                    outline = await api(`/api/projects/${projectId}/gdd/outline`);
                    selectedSection = (outline.sections || []).find(item => item.id === selectedSection.id);
                    $("editorContent").value = selectedSection?.content || "";
                    renderOutline();
                  } catch (error) {
                    alert(error?.payload?.summary || error?.payload?.error || "generate_failed");
                  } finally {
                    button.disabled = false;
                    button.textContent = "\u751f\u6210\u5177\u4f53\u5185\u5bb9";
                  }
                }
                async function exportGddMarkdown() {
                  const button = $("exportGddMarkdown");
                  button.disabled = true;
                  button.textContent = "\u5bfc\u51fa\u4e2d...";
                  try {
                    const result = await api(`/api/projects/${projectId}/gdd/outline/export`, { method:"POST", body:"{}" });
                    window.open(result.downloadPageUrl || `/downloads?projectId=${encodeURIComponent(projectId)}`, "_blank", "noreferrer");
                  } catch (error) {
                    alert(error?.payload?.error || "export_failed");
                  } finally {
                    button.disabled = false;
                    button.textContent = "\u5bfc\u51fa\u4e3a GDD.md";
                  }
                }
                function notifyOutlineDeleted() {
                  try {
                    window.parent?.postMessage?.({ type: "phasea:gdd-outline-deleted", projectId }, location.origin);
                    const parentButton = window.parent?.document?.getElementById?.("createGddDocument");
                    if (parentButton) parentButton.textContent = "\u521b\u5efa\u7b56\u5212\u5927\u7eb2";
                  } catch {}
                }
                async function deleteGddOutline() {
                  if (!confirm("\u786e\u5b9a\u8981\u5220\u9664\u73b0\u6709\u7b56\u5212\u5927\u7eb2\u6846\u67b6\u5417\uff1f")) return;
                  const button = $("deleteGddOutline");
                  button.disabled = true;
                  button.textContent = "\u5220\u9664\u4e2d...";
                  try {
                    await api(`/api/projects/${projectId}/gdd/outline`, { method:"DELETE" });
                    outline = null;
                    $("meta").textContent = "\u7b56\u5212\u5927\u7eb2\u5df2\u5220\u9664\uff0c\u53ef\u56de\u5230\u804a\u5929\u754c\u9762\u91cd\u65b0\u521b\u5efa\u3002";
                    $("title").textContent = "\u5c1a\u672a\u521b\u5efa\u7b56\u5212\u5927\u7eb2";
                    $("summary").textContent = "";
                    $("sections").innerHTML = "<p class='muted'>\u7b56\u5212\u5927\u7eb2\u5df2\u5220\u9664\u3002</p>";
                    $("exportGddMarkdown").disabled = true;
                    notifyOutlineDeleted();
                  } catch (error) {
                    alert(error?.payload?.error || "delete_failed");
                    button.disabled = false;
                  } finally {
                    button.textContent = "\u5220\u9664\u7b56\u5212\u5927\u7eb2";
                  }
                }
                $("closeEditor").onclick = () => $("editor").close();
                $("generateSection").onclick = generateSection;
                $("exportGddMarkdown").onclick = exportGddMarkdown;
                $("deleteGddOutline").onclick = deleteGddOutline;
                loadOutline();
              </script>
            </body>
            </html>
            """;
    }

    public string RenderDownloads()
    {
        return """
            <!doctype html>
            <html lang="zh-CN">
            <head>
              <meta charset="utf-8">
              <meta name="viewport" content="width=device-width, initial-scale=1">
              <title>项目文件下载</title>
              <style>
                :root { --ink: #17211b; --muted: #66736b; --paper: #fbf7ef; --panel: #fffdf8; --line: #ded4c4; --accent: #0f6b57; --danger: #a2342f; }
                body { margin: 0; font-family: Georgia, "Times New Roman", serif; color: var(--ink); background: linear-gradient(135deg, #fbf7ef, #efe5d3); }
                main { max-width: 64rem; margin: 0 auto; padding: 2rem 1rem 4rem; display: grid; gap: 1rem; }
                h1 { margin: 0; font-size: clamp(2rem, 5vw, 4rem); letter-spacing: -0.06em; }
                p { color: var(--muted); }
                .card { background: var(--panel); border: 1px solid var(--line); border-radius: 1rem; padding: 1rem; box-shadow: 0 1rem 2.4rem rgba(57, 43, 24, 0.1); }
                .package { display: grid; gap: 0.45rem; }
                .downloads-grid { display: grid; gap: 1rem; }
                button { border: 0; border-radius: 0.75rem; padding: 0.75rem 1rem; background: var(--accent); color: white; font: inherit; font-weight: 700; cursor: pointer; }
                button:disabled { cursor: not-allowed; opacity: 0.45; }
                .toolbar { display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: center; }
                .danger { color: var(--danger); }
                .muted { color: var(--muted); }
                body.embedded main { max-width: none; padding: 0; }
                body.embedded main > header { display: none; }
              </style>
            </head>
            <body>
              <main>
                <header>
                  <h1>项目文件下载</h1>
                  <p>按版本号/时间戳从近到远列出所有已打包的项目文件。压缩包只包含项目相关文件，不包含平台工程代码。</p>
                </header>
                <section id="status" class="card muted">正在读取项目文件包列表...</section>
                <section class="card toolbar">
                  <button id="createPackage" disabled>打包项目文件</button>
                  <span id="createPackageHint" class="muted">正在检查是否可以打包。</span>
                </section>
                <section class="downloads-grid">
                  <section id="gddDownload" class="card"></section>
                  <section id="packages" class="card"></section>
                </section>
              </main>
              <script>
                const params = new URLSearchParams(location.search);
                const projectId = params.get("projectId") || "";
                if (params.get("embedded") === "1") document.body.classList.add("embedded");
                const readBrowserCookie = name => {
                  const prefix = `${encodeURIComponent(name)}=`;
                  return document.cookie.split(";").map(part => part.trim()).find(part => part.startsWith(prefix))?.slice(prefix.length) || "";
                };
                const token = () => localStorage.getItem("phaseAAccessToken") || decodeURIComponent(readBrowserCookie("phaseAAccessToken") || "") || localStorage.getItem("phaseAAdminToken") || window.parent?.document?.getElementById?.("token")?.value?.trim?.() || "";
                const $ = id => document.getElementById(id);
                const escapeHtml = value => String(value || "").replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#039;" }[ch]));
                async function loadPackages() {
                  if (!projectId) {
                    $("status").textContent = "缺少 projectId。请从控制台打开下载页。";
                    return;
                  }
                  if (!token()) {
                    $("status").textContent = "当前浏览器没有 token。请先在控制台登录。";
                    return;
                  }
                  const response = await fetch(`/api/projects/${projectId}/packages`, { headers: { "Authorization": `Bearer ${token()}` } });
                  const payload = await response.json();
                  if (!response.ok) {
                    $("status").innerHTML = `<span class="danger">读取失败：${escapeHtml(payload.error || "unknown_error")}</span>`;
                    return;
                  }
                  renderCreatePackageAction(payload);
                  $("status").textContent = payload.canCreatePackage ? "可以继续生成新的项目文件包。" : disabledText(payload.disabledReason);
                  $("packages").innerHTML = (payload.packages || []).map(item => `
                    <article class="package card">
                      <strong>${escapeHtml(item.version)}</strong>
                      <span class="muted">${escapeHtml(item.createdUtc || "未知时间")} · ${escapeHtml(item.fileName)} · ${item.sizeBytes} bytes</span>
                      <button data-download-url="${escapeHtml(item.downloadUrl)}" data-file-name="${escapeHtml(item.fileName)}">下载此版本</button>
                    </article>
                  `).join("") || "<p class='muted'>还没有已打包的项目文件。</p>";
                  document.querySelectorAll("[data-download-url]").forEach(button => {
                    button.onclick = () => downloadPackage(button, button.dataset.downloadUrl, button.dataset.fileName);
                  });
                  await loadGddDownload();
                }
                function renderCreatePackageAction(payload) {
                  const button = $("createPackage");
                  const hint = $("createPackageHint");
                  if (!button || !hint) return;
                  const canCreate = !!payload?.canCreatePackage;
                  button.disabled = !canCreate;
                  button.title = canCreate ? "" : disabledText(payload?.disabledReason);
                  hint.textContent = canCreate ? "点击后生成新的项目压缩包。" : disabledText(payload?.disabledReason);
                }
                async function createPackage() {
                  const button = $("createPackage");
                  if (!projectId || !button || button.disabled) return;
                  const originalText = button.textContent;
                  button.disabled = true;
                  button.textContent = "打包中...";
                  $("status").textContent = "正在生成项目压缩包，请等待当前任务完成。";
                  try {
                    const response = await fetch(`/api/projects/${projectId}/packages`, { method: "POST", headers: { "Authorization": `Bearer ${token()}`, "Content-Type": "application/json" }, cache: "no-store" });
                    let payload = {};
                    try { payload = await response.json(); } catch {}
                    if (!response.ok) {
                      const reason = payload.failureCode || payload.disabledReason || payload.error || payload.status || "unknown_error";
                      $("status").innerHTML = `<span class="danger">打包失败：${escapeHtml(disabledText(reason))} (${escapeHtml(reason)})</span>`;
                      return;
                    }
                    $("status").textContent = "项目压缩包已生成，正在刷新下载列表。";
                  } catch {
                    $("status").innerHTML = "<span class='danger'>打包失败：浏览器未能发起项目文件打包。</span>";
                  } finally {
                    button.textContent = originalText;
                    await loadPackages();
                  }
                }
                async function loadGddDownload() {
                  const response = await fetch(`/api/projects/${projectId}/gdd`, { headers: { "Authorization": `Bearer ${token()}` }, cache: "no-store" });
                  if (!response.ok) {
                    $("gddDownload").innerHTML = "<strong>&#31574;&#21010;&#22823;&#32434;&#25991;&#26723;</strong><p class='muted'>&#36824;&#27809;&#26377;&#21019;&#24314;&#31574;&#21010;&#22823;&#32434;&#12290;</p>";
                    return;
                  }

                  const payload = await response.json();
                  $("gddDownload").innerHTML = `
                    <article class="package">
                      <strong>&#31574;&#21010;&#22823;&#32434;&#25991;&#26723;</strong>
                      <span class="muted">${escapeHtml(payload.lastUpdatedUtc || "未知时间")} · ${escapeHtml(payload.relativePath || "docs/gdd/GDD.md")} · ${payload.sizeBytes || 0} bytes</span>
                      <button id="downloadGddDocument">下载 GDD.md</button>
                    </article>
                  `;
                  $("downloadGddDocument").onclick = () => downloadGddDocument($("downloadGddDocument"));
                }
                function disabledText(reason) {
                  if (reason === "prototype_not_created") return "尚未成功运行原型创建，或没有创建有效的godot场景文件，暂不能打包项目文件。";
                  if (reason === "project_busy") return "项目有后台任务正在执行。";
                  if (reason === "iteration_plan_not_completed") return "游戏模块完成后才可以打包项目文件。";
                  if (reason === "prototype_acceptance_not_passed") return "游戏模块完成后，需要重新进行原型验收并通过，才可以打包项目文件。";
                  return "当前暂不能生成新的项目文件包。";
                }
                async function downloadPackage(button, downloadUrl, fileName) {
                  const originalText = button.textContent;
                  button.disabled = true;
                  button.textContent = "下载准备中...";
                  $("status").textContent = "正在准备项目文件下载，请稍等。";
                  try {
                    const ticketUrl = `/api/projects/${encodeURIComponent(projectId)}/packages/${encodeURIComponent(fileName)}/download-ticket`;
                    const response = await fetch(ticketUrl, { method: "POST", headers: { "Authorization": `Bearer ${token()}`, "Content-Type": "application/json" }, cache: "no-store" });
                    if (!response.ok) {
                      let detail = "unknown_error";
                      try {
                        const payload = await response.json();
                        detail = payload.error || payload.status || detail;
                      } catch {}
                      $("status").innerHTML = `<span class="danger">下载失败：${escapeHtml(detail)}</span>`;
                      return;
                    }
                    const payload = await response.json();
                    if (!payload.downloadUrl) {
                      $("status").innerHTML = "<span class='danger'>下载失败：没有获得下载链接。</span>";
                      return;
                    }
                    const anchor = document.createElement("a");
                    anchor.href = payload.downloadUrl;
                    anchor.download = fileName || "project-package.zip";
                    anchor.style.display = "none";
                    document.body.appendChild(anchor);
                    anchor.click();
                    anchor.remove();
                    $("status").textContent = "下载已提交给浏览器。如果没有看到下载，请检查浏览器下载拦截或下载目录。";
                  } catch {
                    $("status").innerHTML = "<span class='danger'>下载失败：浏览器未能读取项目文件。</span>";
                  } finally {
                    button.disabled = false;
                    button.textContent = originalText;
                  }
                }
                async function downloadGddDocument(button) {
                  const originalText = button.textContent;
                  button.disabled = true;
                  button.textContent = "下载准备中...";
                  $("status").textContent = "\u6b63\u5728\u51c6\u5907\u7b56\u5212\u5927\u7eb2\u6587\u6863\u4e0b\u8f7d\u3002";
                  try {
                    const response = await fetch(`/api/projects/${projectId}/gdd/download-ticket`, { method: "POST", headers: { "Authorization": `Bearer ${token()}`, "Content-Type": "application/json" }, cache: "no-store" });
                    if (!response.ok) {
                      $("status").innerHTML = "<span class='danger'>下载失败：还没有可下载的 GDD.md。</span>";
                      return;
                    }

                    const payload = await response.json();
                    if (!payload.downloadUrl) {
                      $("status").innerHTML = "<span class='danger'>下载失败：没有获得下载链接。</span>";
                      return;
                    }
                    const anchor = document.createElement("a");
                    anchor.href = payload.downloadUrl;
                    anchor.download = "GDD.md";
                    anchor.style.display = "none";
                    document.body.appendChild(anchor);
                    anchor.click();
                    anchor.remove();
                    $("status").textContent = "GDD.md 已提交给浏览器下载。";
                  } catch {
                    $("status").innerHTML = "<span class='danger'>下载失败：浏览器未能读取 GDD.md。</span>";
                  } finally {
                    button.disabled = false;
                    button.textContent = originalText;
                  }
                }
                $("createPackage").onclick = createPackage;
                loadPackages();
              </script>
            </body>
            </html>
            """;
    }

    public string RenderAssets()
    {
        return """
            <!doctype html>
            <html lang="zh-CN">
            <head>
              <meta charset="utf-8">
              <meta name="viewport" content="width=device-width, initial-scale=1">
              <title>项目素材库</title>
              <!-- Project Asset Library -->
              <style>
                :root { --ink: #17211b; --muted: #66736b; --paper: #fbf7ef; --panel: #fffdf8; --line: #ded4c4; --accent: #0f6b57; --accent-2: #244c9a; --danger: #a2342f; }
                * { box-sizing: border-box; }
                body { margin: 0; font-family: Georgia, "Times New Roman", serif; color: var(--ink); background: linear-gradient(135deg, #fbf7ef, #efe5d3); }
                main { max-width: 78rem; margin: 0 auto; padding: 2rem 1rem; display: grid; gap: 1rem; }
                h1 { margin: 0; font-size: clamp(2rem, 5vw, 4rem); letter-spacing: 0; }
                h2 { margin: 0 0 0.75rem; }
                p { color: var(--muted); }
                .page-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; }
                .page-header-actions { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; justify-content: flex-end; }
                .card { background: var(--panel); border: 1px solid var(--line); border-radius: 0.5rem; padding: 1rem; box-shadow: 0 1rem 2.4rem rgba(57, 43, 24, 0.1); overflow-wrap: anywhere; }
                .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(17rem, 1fr)); gap: 0.75rem; }
                .list { display: grid; gap: 0.75rem; }
                .asset-preview { width: 100%; height: 10rem; object-fit: contain; border: 1px solid var(--line); border-radius: 0.5rem; background: #f3ead9; display: grid; place-items: center; cursor: pointer; }
                .asset-card { display: grid; gap: 0.65rem; align-content: start; }
                .asset-unit-name { margin: 0; color: var(--ink); font-size: 0.95rem; line-height: 1.3; font-weight: 800; }
                .asset-role { min-height: 2.2rem; margin: 0; color: var(--ink); font-size: 0.92rem; line-height: 1.3; }
                .asset-card-actions { display: grid; grid-template-columns: minmax(9.5rem, 1fr) minmax(4rem, 0.5fr); gap: 0.5rem; align-items: center; }
                .asset-card-actions button { min-width: 0; white-space: nowrap; }
                button { border: 0; border-radius: 0.4rem; padding: 0.65rem 0.9rem; background: var(--accent); color: white; font: inherit; font-weight: 700; cursor: pointer; }
                button.secondary { background: var(--accent-2); }
                button.ghost { background: transparent; border: 1px solid var(--line); color: var(--ink); }
                button:disabled { cursor: not-allowed; opacity: 0.45; }
                .muted { color: var(--muted); }
                .badge { display: inline-flex; border-radius: 999px; padding: 0.2rem 0.55rem; background: #e6f4ef; color: var(--accent); font-weight: 700; font-size: 0.85rem; }
                .row { display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem; }
                .asset-action-row { flex-wrap: nowrap; }
                .asset-action-row button { white-space: nowrap; flex: 0 0 auto; }
                .history-modal { position: fixed; inset: 0; display: none; align-items: center; justify-content: center; padding: 1rem; background: rgba(23, 33, 27, 0.36); z-index: 40; }
                .history-modal.open { display: flex; }
                .history-dialog { width: min(62rem, 100%); max-height: min(44rem, calc(100vh - 2rem)); overflow: hidden; background: var(--panel); border: 1px solid var(--line); border-radius: 0.5rem; padding: 1rem; box-shadow: 0 1.4rem 4rem rgba(23, 33, 27, 0.28); display: grid; gap: 0.8rem; }
                .history-dialog-header { display: flex; align-items: center; justify-content: space-between; gap: 1rem; margin-bottom: 0.75rem; }
                .asset-detail-grid { display: grid; grid-template-columns: minmax(14rem, 0.9fr) minmax(18rem, 1.1fr); gap: 0.8rem; min-height: 0; }
                .asset-detail-panel { border: 1px solid var(--line); border-radius: 0.5rem; padding: 0.75rem; background: #fbf7ef; min-height: 0; }
                .history-list { display: grid; gap: 0.5rem; max-height: 22rem; overflow-y: auto; padding-right: 0.25rem; }
                .history-row { display: grid; grid-template-columns: 4rem 90px minmax(8rem, 1fr) auto; align-items: center; gap: 0.65rem; border: 1px solid var(--line); border-radius: 0.5rem; padding: 0.5rem; background: #fbf7ef; }
                .history-row.selected { border-color: var(--accent); background: #edf8f3; }
                .history-row-number { font-weight: 800; }
                .history-row-time { color: var(--muted); font-size: 0.85rem; }
                .asset-create-panel { border-top: 1px solid var(--line); padding-top: 0.8rem; display: grid; grid-template-columns: auto auto minmax(12rem, 1fr) auto auto; align-items: center; gap: 0.55rem; }
                .asset-create-panel input[type="text"] { min-width: 0; border: 1px solid var(--line); border-radius: 0.4rem; padding: 0.65rem; font: inherit; background: #fffdf8; }
                .asset-create-panel select { border: 1px solid var(--line); border-radius: 0.4rem; padding: 0.65rem; font: inherit; background: #fffdf8; }
                .reference-file { display: none; }
                .reference-file.open { display: inline-flex; align-items: center; gap: 0.35rem; }
                .asset-original-preview-overlay {
                  position: fixed;
                  inset: 0;
                  display: none;
                  align-items: center;
                  justify-content: center;
                  overflow: auto;
                  padding: 1rem;
                  background: rgba(23, 33, 27, 0.22);
                  z-index: 60;
                }
                .asset-original-preview-overlay.open { display: flex; }
                .asset-original-preview-layer {
                  width: max-content;
                  height: max-content;
                  display: grid;
                  gap: 0.35rem;
                  background: var(--panel);
                  border: 1px solid var(--line);
                  border-radius: 0.5rem;
                  padding: 0.75rem;
                  box-shadow: 0 1.4rem 4rem rgba(23, 33, 27, 0.28);
                  position: relative;
                }
                .asset-original-preview-close {
                  position: absolute;
                  top: 0.35rem;
                  right: 0.35rem;
                  width: 2rem;
                  height: 2rem;
                  padding: 0;
                  display: inline-grid;
                  place-items: center;
                  border-radius: 999px;
                  background: rgba(255, 253, 248, 0.92);
                  border: 1px solid var(--line);
                  color: var(--ink);
                  font-size: 1.2rem;
                  line-height: 1;
                }
                .asset-original-preview-layer img {
                  display: block;
                  max-width: none;
                  max-height: none;
                  width: auto;
                  height: auto;
                  border: 0;
                  border-radius: 0.25rem;
                  background: transparent;
                }
                .asset-original-preview-meta { color: var(--muted); font-size: 0.85rem; }
                body.embedded main { max-width: none; padding: 0; }
                body.embedded main > header { display: none; }
                @media (max-width: 820px) {
                  .asset-detail-grid { grid-template-columns: 1fr; }
                  .asset-create-panel { grid-template-columns: 1fr; }
                }
              </style>
            </head>
            <body>
              <main>
                <header class="page-header">
                  <div>
                    <h1>项目素材库</h1>
                    <p>查看当前项目已使用的素材、可生成的素材候选和每个素材单位的生成历史。</p>
                  </div>
                  <div class="page-header-actions">
                    <button id="refreshAssetLibraryButton" class="ghost" type="button">刷新素材库</button>
                  </div>
                </header>
                <section id="status" class="card muted">正在读取素材清单...</section>
                <section class="card">
                  <h2>已使用素材</h2>
                  <div id="usedAssets" class="grid"></div>
                </section>
                <section class="card">
                  <h2>可生成素材候选</h2>
                  <div id="candidates" class="list"></div>
                </section>
              </main>
              <div id="assetHistoryModal" class="history-modal" aria-hidden="true">
                <div class="history-dialog">
                  <div class="history-dialog-header">
                    <strong id="assetHistoryTitle">素材详情及替换</strong>
                    <button id="closeAssetHistoryButton" class="ghost" type="button">关闭</button>
                  </div>
                  <div class="asset-detail-grid">
                    <section id="assetDetailInfo" class="asset-detail-panel"></section>
                    <section class="asset-detail-panel">
                      <strong>素材列表</strong>
                      <div id="assetHistoryList" class="history-list"></div>
                    </section>
                  </div>
                  <div class="asset-create-panel">
                    <label><input type="radio" name="assetGenerationMode" value="text-to-image" checked> 文生图</label>
                    <label><input type="radio" name="assetGenerationMode" value="image-to-image"> 图生图</label>
                    <label id="referenceImageLabel" class="reference-file">导入 <input id="referenceImageFile" type="file" accept=".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp"></label>
                    <input id="floatingPrompt" type="text" maxlength="2000" placeholder="输入本次素材生成方向，例如：蓝色史莱姆、俯视城镇地图、透明背景道具...">
                    <select id="assetGenerationCount"><option value="1" selected>1</option><option value="2">2</option><option value="3">3</option><option value="4">4</option></select>
                    <button id="modalGenerateAsset" class="secondary" type="button">创建素材</button>
                  </div>
                </div>
              </div>
              <div id="assetOriginalPreviewOverlay" class="asset-original-preview-overlay" aria-hidden="true">
                <div id="assetOriginalPreviewLayer" class="asset-original-preview-layer">
                  <button id="closeAssetOriginalPreviewButton" class="asset-original-preview-close" type="button" aria-label="关闭原图预览">×</button>
                  <strong id="assetOriginalPreviewTitle">原图预览</strong>
                  <div id="assetOriginalPreviewMeta" class="asset-original-preview-meta"></div>
                  <img id="assetOriginalPreviewImage" alt="素材原图预览">
                </div>
              </div>
              <script>
                const params = new URLSearchParams(location.search);
                const projectId = params.get("projectId") || "";
                const model = params.get("model") || "gpt-5.5";
                if (params.get("embedded") === "1") document.body.classList.add("embedded");
                const readBrowserCookie = name => {
                  const prefix = `${encodeURIComponent(name)}=`;
                  return document.cookie.split(";").map(part => part.trim()).find(part => part.startsWith(prefix))?.slice(prefix.length) || "";
                };
                const token = () => localStorage.getItem("phaseAAccessToken") || decodeURIComponent(readBrowserCookie("phaseAAccessToken") || "") || localStorage.getItem("phaseAAdminToken") || window.parent?.document?.getElementById?.("token")?.value?.trim?.() || "";
                const $ = id => document.getElementById(id);
                const escapeHtml = value => String(value || "").replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#039;" }[ch]));
                const state = { assetUnits: {}, library: { units: [] }, usedAssets: [], candidates: [], activeAsset: null };
                const cacheKey = () => `phaseA.assetLibrary.${projectId}.${model}`;

                function readAssetCache() {
                  try {
                    const cached = JSON.parse(localStorage.getItem(cacheKey()) || "null");
                    return cached && Array.isArray(cached.usedAssets) && Array.isArray(cached.candidates) ? cached : null;
                  } catch { return null; }
                }

                function writeAssetCache() {
                  const cleanLibrary = JSON.parse(JSON.stringify(state.library || { units: [] }));
                  for (const unit of cleanLibrary.units || []) for (const entry of unit.entries || []) delete entry.previewUrl;
                  localStorage.setItem(cacheKey(), JSON.stringify({
                    cachedAt: new Date().toISOString(),
                    usedAssets: state.usedAssets || [],
                    candidates: state.candidates || [],
                    library: cleanLibrary
                  }));
                }

                async function loadAssets(force = false) {
                  if (!projectId) { $("status").textContent = "缺少 projectId。"; return; }
                  if (!token()) { $("status").textContent = "浏览器 token 不存在，请先登录。"; return; }
                  const refreshButton = $("refreshAssetLibraryButton");
                  if (!force) {
                    const cached = readAssetCache();
                    if (cached) {
                      state.usedAssets = cached.usedAssets || [];
                      state.candidates = cached.candidates || [];
                      state.library = cached.library || { units: [] };
                      await hydrateLibraryPreviewUrls();
                      await renderAssetData(`已载入缓存素材库：已使用 ${state.usedAssets.length} 个，可生成候选 ${state.candidates.length} 个。`);
                      return;
                    }
                  }

                  if (refreshButton) {
                    refreshButton.disabled = true;
                    refreshButton.textContent = force ? "刷新中..." : "读取中...";
                  }
                  $("status").textContent = "正在刷新素材库...";
                  try {
                    const [inventoryResponse, libraryResponse] = await Promise.all([
                      fetch(`/api/projects/${encodeURIComponent(projectId)}/asset-inventory?judge=true&force=${force ? "true" : "false"}&model=${encodeURIComponent(model)}`, { headers: { "Authorization": `Bearer ${token()}` }, cache: "no-store" }),
                      fetch(`/api/projects/${encodeURIComponent(projectId)}/asset-library`, { headers: { "Authorization": `Bearer ${token()}` }, cache: "no-store" })
                    ]);
                    const payload = await inventoryResponse.json();
                    state.library = libraryResponse.ok ? await libraryResponse.json() : { units: [] };
                    await hydrateLibraryPreviewUrls();
                    if (!inventoryResponse.ok || !payload.canReadInventory) {
                      const reason = payload.disabledReason || payload.error || "unknown_error";
                      $("status").className = "card muted";
                      $("status").textContent = assetInventoryDisabledText(reason);
                      return;
                    }
                    state.usedAssets = payload.usedAssets || [];
                    state.candidates = payload.generationCandidates || [];
                    writeAssetCache();
                    await renderAssetData(`已刷新素材库：已使用 ${state.usedAssets.length} 个，可生成候选 ${state.candidates.length} 个。`);
                  } finally {
                    if (refreshButton) {
                      refreshButton.disabled = false;
                      refreshButton.textContent = "刷新素材库";
                    }
                  }
                }

                async function renderAssetData(statusText) {
                  $("status").className = "card muted";
                  $("status").textContent = statusText;
                  state.assetUnits = {};
                  await renderUsedAssets(state.usedAssets || []);
                  renderCandidates(state.candidates || []);
                }

                async function renderUsedAssets(items) {
                  const enriched = [];
                  for (const item of items) enriched.push({ ...item, previewUrl: await createPreviewUrl(item.resourcePath) });
                  $("usedAssets").innerHTML = enriched.length ? enriched.map(item => renderUsedAsset(registerUnit(item, "used_asset"))).join("") : "<p class='muted'>未识别到可预览的素材引用。</p>";
                }

                async function createPreviewUrl(resourcePath) {
                  if (!resourcePath) return "";
                  try {
                    const response = await fetch(`/api/projects/${encodeURIComponent(projectId)}/asset-preview-ticket`, {
                      method: "POST",
                      headers: { "Authorization": `Bearer ${token()}`, "Content-Type": "application/json" },
                      body: JSON.stringify({ resourcePath }),
                      cache: "no-store"
                    });
                    if (!response.ok) return "";
                    const payload = await response.json();
                    return payload.previewUrl || "";
                  } catch { return ""; }
                }

                async function hydrateLibraryPreviewUrls() {
                  const units = state.library?.units || [];
                  for (const unit of units) {
                    for (const entry of unit.entries || []) {
                      if (entry.previewResourcePath && !entry.previewUrl) {
                        entry.previewUrl = await createPreviewUrl(entry.previewResourcePath);
                      }
                    }
                  }
                }

                function registerUnit(item, kind) {
                  const key = `${kind}-${Object.keys(state.assetUnits).length + 1}`;
                  const libraryUnit = findLibraryUnit(item, kind);
                  const unit = {
                    clientKey: key,
                    unitKey: libraryUnit?.key || "",
                    instanceName: item.instanceName || "",
                    nodeType: item.nodeType || "",
                    scenePath: item.scenePath || "",
                    resourcePath: item.resourcePath || "",
                    kind: item.suggestedAssetKind || kind,
                    intendedUse: item.intendedUse || "",
                    reason: item.reason || "",
                    pixelSize: assetPixelSize(item)
                  };
                  state.assetUnits[key] = unit;
                  return { item, unit, libraryUnit };
                }

                function findLibraryUnit(item, fallbackKind) {
                  const units = state.library?.units || [];
                  return units.find(unit => String(unit.scenePath || "").toLowerCase() === String(item.scenePath || "").toLowerCase() && String(unit.instanceName || "").toLowerCase() === String(item.instanceName || "").toLowerCase() && String(unit.resourcePath || "").toLowerCase() === String(item.resourcePath || "").toLowerCase())
                    || units.find(unit => String(unit.scenePath || "").toLowerCase() === String(item.scenePath || "").toLowerCase() && String(unit.instanceName || "").toLowerCase() === String(item.instanceName || "").toLowerCase() && String(unit.kind || "").toLowerCase() === String(item.suggestedAssetKind || fallbackKind || "").toLowerCase());
                }

                function selectedLibraryEntry(libraryUnit) {
                  const entries = libraryUnit?.entries || [];
                  const selectedEntryId = libraryUnit?.selectedEntryId || "";
                  return entries.find(entry => entry.selected || entry.entryId === selectedEntryId) || null;
                }

                function renderUsedAsset(model) {
                  const item = model.item;
                  const selected = selectedLibraryEntry(model.libraryUnit);
                  const previewUrl = selected?.previewUrl || item.previewUrl || "";
                  const downloadUrl = previewUrl || "";
                  const downloadName = assetDownloadName(model, previewUrl);
                  const image = previewUrl ? `<img class="asset-preview" src="${escapeHtml(previewUrl)}" alt="${escapeHtml(item.instanceName || "asset")}" data-asset-detail-key="${escapeHtml(model.unit.clientKey)}">` : `<div class='asset-preview muted' data-asset-detail-key="${escapeHtml(model.unit.clientKey)}">预览不可用</div>`;
                  return `<article class="card asset-card"><p class="asset-unit-name">使用单位：${escapeHtml(assetUnitName(model.unit))}</p><p class="asset-role">${escapeHtml(assetRoleText(model.unit))}</p>${image}<div class="asset-card-actions"><button class="secondary asset-detail-button" type="button" data-asset-detail-key="${escapeHtml(model.unit.clientKey)}">素材详情及替换</button><button class="ghost" type="button" data-asset-download-url="${escapeHtml(downloadUrl)}" data-asset-download-name="${escapeHtml(downloadName)}" ${downloadUrl ? "" : "disabled"}>下载</button></div></article>`;
                }

                function assetUnitName(unit) {
                  const name = String(unit?.instanceName || "").trim();
                  if (name) return name;
                  const kind = String(unit?.kind || "").trim();
                  if (kind.includes("map")) return "地图场景";
                  if (kind.includes("sprite")) return "角色或物件";
                  return "未命名单位";
                }

                function assetRoleText(unit) {
                  const kind = String(unit?.kind || "").trim();
                  const use = String(unit?.intendedUse || unit?.reason || "").trim();
                  if (use) return use;
                  if (kind.includes("map")) return "地图或场景背景素材。";
                  if (kind.includes("sprite")) return "角色、敌人、道具或效果精灵素材。";
                  return "用于替换当前素材单位的默认显示。";
                }

                function assetPixelSize(item) {
                  const width = Number(item?.pixelWidth || 0);
                  const height = Number(item?.pixelHeight || 0);
                  return width > 0 && height > 0 ? `${width} x ${height}` : "未知";
                }

                function assetInventoryDisabledText(reason) {
                  if (reason === "final_step_not_completed") return "final step 完成后才可以查看素材清单。";
                  if (reason === "project_busy") return "项目正在运行，请稍后再试。";
                  if (reason === "project_not_selected") return "请先选择项目。";
                  return "素材清单暂不可用。";
                }

                function renderCandidates(items) {
                  $("candidates").innerHTML = items.length ? items.map(item => renderCandidate(registerUnit(item, "candidate_asset"))).join("") : "<p class='muted'>暂未识别到明显的素材生成候选。</p>";
                }

                function renderCandidate(model) {
                  const item = model.item;
                  const selected = selectedLibraryEntry(model.libraryUnit);
                  const preview = selected?.previewUrl || "";
                  const downloadName = assetDownloadName(model, preview);
                  const image = preview ? `<img class="asset-preview" src="${escapeHtml(preview)}" alt="${escapeHtml(item.instanceName || "asset")}" data-asset-detail-key="${escapeHtml(model.unit.clientKey)}">` : `<div class='asset-preview muted' data-asset-detail-key="${escapeHtml(model.unit.clientKey)}">待生成</div>`;
                  return `<article class="card asset-card"><p class="asset-unit-name">使用单位：${escapeHtml(assetUnitName(model.unit))}</p><p class="asset-role">${escapeHtml(assetRoleText(model.unit))}</p>${image}<div class="asset-card-actions"><button class="secondary asset-detail-button" type="button" data-asset-detail-key="${escapeHtml(model.unit.clientKey)}">素材详情及替换</button><button class="ghost" type="button" data-asset-download-url="${escapeHtml(preview)}" data-asset-download-name="${escapeHtml(downloadName)}" ${preview ? "" : "disabled"}>下载</button></div></article>`;
                }

                function showAssetHistory(unitKey) {
                  const active = state.activeAsset || Object.values(state.assetUnits).find(unit => unit.unitKey === unitKey);
                  if (active) {
                    state.activeAsset = active;
                  }
                  renderAssetDetail();
                }

                function openAssetDetail(clientKey) {
                  const unit = state.assetUnits[clientKey];
                  if (!unit) return;
                  state.activeAsset = unit;
                  renderAssetDetail();
                }

                function renderAssetDetail() {
                  const active = state.activeAsset;
                  if (!active) return;
                  const libraryUnit = (state.library?.units || []).find(unit => unit.key === active.unitKey)
                    || findLibraryUnit(active, active.kind);
                  const entries = libraryUnit?.entries || [];
                  const selectedEntryId = libraryUnit?.selectedEntryId || "";
                  $("assetHistoryTitle").textContent = `${active.instanceName || "素材"} 的素材详情及替换`;
                  $("assetDetailInfo").innerHTML = `
                    <p><strong>素材名字</strong><br>${escapeHtml(active.instanceName || "未命名素材")}</p>
                    <p><strong>素材场景</strong><br>${escapeHtml(active.scenePath || "未知")}</p>
                    <p><strong>用途</strong><br>${escapeHtml(active.intendedUse || "用于替换当前占位节点，提升可读性。")}</p>
                    <p><strong>像素尺寸</strong><br>${escapeHtml(active.pixelSize || "未知")}</p>
                  `;
                  $("assetHistoryList").innerHTML = entries.map((entry, index) => {
                    const selected = entry.selected || entry.entryId === selectedEntryId;
                    const preview = entry.previewUrl
                      ? `<img class="history-thumb" src="${escapeHtml(entry.previewUrl)}" alt="${escapeHtml("素材 " + (index + 1))}">`
                      : "<div class='history-thumb muted'>无图</div>";
                    return `<div class="history-row ${selected ? "selected" : ""}"><span class="history-row-number">#${index + 1}</span>${preview}<span class="history-row-time">${escapeHtml(formatTime(entry.createdUtc))}</span><button class="ghost" type="button" data-select-unit-key="${escapeHtml(libraryUnit.key)}" data-entry-id="${escapeHtml(entry.entryId)}">替换默认素材</button></div>`;
                  }).join("") || "<p class='muted'>暂无历史素材。可以在下方创建。</p>";
                  renderGenerationMode();
                  $("assetHistoryModal").classList.add("open");
                  $("assetHistoryModal").setAttribute("aria-hidden", "false");
                }

                function assetDownloadName(model, previewUrl) {
                  const baseName = sanitizeFileName(model?.unit?.instanceName || model?.item?.instanceName || model?.unit?.kind || "asset");
                  const extension = extensionFromPath(model?.item?.resourcePath || model?.unit?.resourcePath || previewUrl || "") || "png";
                  return `${baseName}.${extension}`;
                }

                function sanitizeFileName(name) {
                  return String(name || "asset").replace(/[\\/:*?"<>|]+/g, "_").replace(/\s+/g, " ").trim() || "asset";
                }

                function extensionFromPath(value) {
                  const base = String(value || "").split("?")[0].split("#")[0];
                  const match = base.match(/\.([a-zA-Z0-9]+)$/);
                  return match ? match[1] : "";
                }

                function downloadAsset(url, fileName) {
                  if (!url) return;
                  const link = document.createElement("a");
                  link.href = url;
                  link.download = fileName || "asset.png";
                  link.rel = "noopener";
                  document.body.appendChild(link);
                  link.click();
                  link.remove();
                }

                function assetPreviewOverlay() {
                  return {
                    overlay: $("assetOriginalPreviewOverlay"),
                    layer: $("assetOriginalPreviewLayer"),
                    title: $("assetOriginalPreviewTitle"),
                    meta: $("assetOriginalPreviewMeta"),
                    image: $("assetOriginalPreviewImage")
                  };
                }

                function hideAssetOriginalPreview() {
                  const { overlay, image } = assetPreviewOverlay();
                  if (!overlay || !image) return;
                  overlay.classList.remove("open");
                  overlay.setAttribute("aria-hidden", "true");
                  image.removeAttribute("src");
                  image.alt = "素材原图预览";
                }

                function showAssetOriginalPreview(source) {
                  const previewUrl = source?.getAttribute?.("src") || "";
                  if (!previewUrl) return;
                  const { overlay, title, meta, image } = assetPreviewOverlay();
                  if (!overlay || !title || !meta || !image) return;
                  const altText = source.getAttribute("alt") || "素材原图";
                  title.textContent = altText;
                  meta.textContent = "原始尺寸加载中...";
                  image.alt = altText;
                  image.onload = () => {
                    meta.textContent = `${image.naturalWidth} × ${image.naturalHeight}`;
                  };
                  image.src = previewUrl;
                  if (image.complete && image.naturalWidth > 0) {
                    meta.textContent = `${image.naturalWidth} × ${image.naturalHeight}`;
                  }
                  overlay.classList.add("open");
                  overlay.setAttribute("aria-hidden", "false");
                }

                function closeAssetHistory() {
                  hideAssetOriginalPreview();
                  $("assetHistoryModal").classList.remove("open");
                  $("assetHistoryModal").setAttribute("aria-hidden", "true");
                }

                function renderGenerationMode() {
                  const mode = document.querySelector("input[name='assetGenerationMode']:checked")?.value || "text-to-image";
                  $("referenceImageLabel").classList.toggle("open", mode === "image-to-image");
                }

                function cloneLibrary() {
                  return JSON.parse(JSON.stringify(state.library || { units: [] }));
                }

                async function applySelectionLocal(unitKey, entryId, statusText) {
                  const units = state.library?.units || [];
                  const libraryUnit = units.find(unit => unit.key === unitKey);
                  if (!libraryUnit) return false;
                  libraryUnit.selectedEntryId = entryId;
                  for (const entry of libraryUnit.entries || []) {
                    entry.selected = entry.entryId === entryId;
                  }
                  writeAssetCache();
                  await renderAssetData(statusText);
                  showAssetHistory(unitKey);
                  return true;
                }

                function trimMessage(value) {
                  const text = String(value || "").trim();
                  return text.length > 900 ? `${text.slice(0, 900)}...` : text;
                }

                function formatTime(value) {
                  const date = new Date(value);
                  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
                }

                async function readReferenceImagePayload() {
                  const mode = document.querySelector("input[name='assetGenerationMode']:checked")?.value || "text-to-image";
                  if (mode !== "image-to-image") return {};
                  const file = $("referenceImageFile")?.files?.[0];
                  if (!file) throw new Error("请选择一张参考图片。");
                  const allowed = ["image/png", "image/jpeg", "image/webp"];
                  if (!allowed.includes(file.type)) throw new Error("参考图片只支持 png、jpg、jpeg、webp。");
                  if (file.size > 10 * 1024 * 1024) throw new Error("参考图片不能超过 10M。");
                  const dataUrl = await new Promise((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onload = () => resolve(String(reader.result || ""));
                    reader.onerror = () => reject(new Error("参考图片读取失败。"));
                    reader.readAsDataURL(file);
                  });
                  return {
                    generationMode: "image-to-image",
                    referenceImageFileName: file.name,
                    referenceImageContentType: file.type,
                    referenceImageBase64: dataUrl
                  };
                }

                async function generateActiveAsset(button) {
                  if (!state.activeAsset) return;
                  await generateAsset(state.activeAsset.clientKey, button);
                }

                async function generateAsset(clientKey, button) {
                  const unit = state.assetUnits[clientKey];
                  if (!unit) return;
                  const originalText = button.textContent;
                  button.disabled = true;
                  button.textContent = "生成中...";
                  try {
                    const referencePayload = await readReferenceImagePayload();
                    const count = Number($("assetGenerationCount")?.value || 1);
                    const response = await fetch(`/api/projects/${encodeURIComponent(projectId)}/asset-library/generate`, {
                      method: "POST",
                      headers: { "Authorization": `Bearer ${token()}`, "Content-Type": "application/json" },
                      body: JSON.stringify({
                        floatingPrompt: $("floatingPrompt").value || "",
                        unit,
                        generationMode: referencePayload.generationMode || "text-to-image",
                        count,
                        ...referencePayload
                      }),
                      cache: "no-store"
                    });
                    const payload = await response.json();
                    if (!response.ok) throw new Error(payload.error || payload.failureCode || "generate_failed");
                    state.library = payload.library || state.library;
                    await hydrateLibraryPreviewUrls();
                    writeAssetCache();
                    if ($("referenceImageFile")) $("referenceImageFile").value = "";
                    if (payload.status !== "succeeded") {
                      $("status").textContent = `素材生成未完成，调用：${payload.actionId || "skill"}，状态：${payload.status || "unknown"}。`;
                      await renderAssetData($("status").textContent);
                      return;
                    }
                    $("status").textContent = `素材生成已完成，调用：${payload.actionId || "skill"}，状态：${payload.status || "unknown"}。`;
                    await renderAssetData($("status").textContent);
                    showAssetHistory(unit.unitKey);
                  } catch (error) {
                    $("status").textContent = `素材生成失败：${error.message || error}`;
                  } finally {
                    button.disabled = false;
                    button.textContent = originalText;
                  }
                }

                async function selectEntry(unitKey, entryId, button) {
                  const originalText = button.textContent;
                  const previousLibrary = cloneLibrary();
                  button.disabled = true;
                  button.textContent = "保存中...";
                  try {
                    const applied = await applySelectionLocal(unitKey, entryId, "默认素材已替换，正在后台保存...");
                    if (!applied) throw new Error("entry_not_found");
                    const response = await fetch(`/api/projects/${encodeURIComponent(projectId)}/asset-library/select`, { method: "POST", headers: { "Authorization": `Bearer ${token()}`, "Content-Type": "application/json" }, body: JSON.stringify({ unitKey, entryId }), cache: "no-store" });
                    const payload = await response.json();
                    if (!response.ok) throw new Error(payload.error || "select_failed");
                    const currentUnits = state.library?.units || [];
                    state.library = payload;
                    for (const unit of state.library?.units || []) {
                      const current = currentUnits.find(item => item.key === unit.key);
                      for (const entry of unit.entries || []) {
                        const currentEntry = (current?.entries || []).find(item => item.entryId === entry.entryId);
                        if (currentEntry?.previewUrl) entry.previewUrl = currentEntry.previewUrl;
                      }
                    }
                    writeAssetCache();
                    $("status").textContent = "默认素材已替换。";
                  } catch (error) {
                    state.library = previousLibrary;
                    await renderAssetData(`选择失败，已恢复原默认素材：${error.message || error}`);
                    showAssetHistory(unitKey);
                    $("status").textContent = `选择失败: ${error.message || error}`;
                  } finally {
                    const activeButton = $("assetHistoryList").querySelector(`button[data-entry-id="${CSS.escape(entryId)}"]`);
                    if (activeButton) {
                      activeButton.disabled = false;
                      activeButton.textContent = originalText;
                    }
                  }
                }

                document.addEventListener("click", event => {
                  const previewImage = event.target?.closest?.("img.asset-preview, img.history-thumb");
                  if (previewImage) {
                    showAssetOriginalPreview(previewImage);
                    return;
                  }
                  const detailTarget = event.target?.closest?.("[data-asset-detail-key]");
                  if (detailTarget) {
                    openAssetDetail(detailTarget.dataset.assetDetailKey || "");
                    return;
                  }
                  const downloadButton = event.target?.closest?.("[data-asset-download-url]");
                  if (downloadButton) {
                    downloadAsset(downloadButton.dataset.assetDownloadUrl || "", downloadButton.dataset.assetDownloadName || "asset.png");
                    return;
                  }
                  const selectButton = event.target?.closest?.("[data-select-unit-key][data-entry-id]");
                  if (selectButton) {
                    selectEntry(selectButton.dataset.selectUnitKey || "", selectButton.dataset.entryId || "", selectButton);
                  }
                });
                $("assetOriginalPreviewOverlay").addEventListener("click", event => {
                  if (event.target === $("assetOriginalPreviewOverlay")) {
                    hideAssetOriginalPreview();
                  }
                });
                $("closeAssetOriginalPreviewButton").addEventListener("click", hideAssetOriginalPreview);
                $("closeAssetHistoryButton").addEventListener("click", closeAssetHistory);
                $("modalGenerateAsset").addEventListener("click", event => generateActiveAsset(event.currentTarget));
                $("refreshAssetLibraryButton").addEventListener("click", () => loadAssets(true));
                document.querySelectorAll("input[name='assetGenerationMode']").forEach(input => input.addEventListener("change", renderGenerationMode));
                loadAssets();
              </script>
            </body>
            </html>
            """;
    }

    public string RenderAdminLlmUsage()
    {
        return """
            <!doctype html>
            <html lang="zh-CN">
            <head>
              <meta charset="utf-8">
              <meta name="viewport" content="width=device-width, initial-scale=1">
              <title>LLM 费用汇总</title>
              <style>
                :root { --ink: #17211b; --muted: #66736b; --paper: #f7f2e8; --panel: #fffdf8; --line: #ded4c4; --accent: #0f6b57; --danger: #a2342f; }
                body { margin: 0; font-family: Georgia, "Times New Roman", serif; color: var(--ink); background: linear-gradient(135deg, #fbf7ef, #efe5d3); }
                main { max-width: 78rem; margin: 0 auto; padding: 2rem 1rem 4rem; display: grid; gap: 1rem; }
                h1 { margin: 0; font-size: clamp(2rem, 5vw, 4rem); letter-spacing: -0.06em; }
                .card { background: var(--panel); border: 1px solid var(--line); border-radius: 1rem; padding: 1rem; box-shadow: 0 1rem 2.4rem rgba(57, 43, 24, 0.1); }
                .filters { display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: end; }
                label { display: grid; gap: 0.3rem; font-weight: 700; }
                select, input { border: 1px solid var(--line); border-radius: 0.75rem; padding: 0.65rem 0.75rem; font: inherit; background: white; }
                button { border: 0; border-radius: 0.75rem; padding: 0.75rem 1rem; background: var(--accent); color: white; font: inherit; font-weight: 700; cursor: pointer; }
                table { width: 100%; border-collapse: collapse; background: var(--panel); border-radius: 1rem; overflow: hidden; }
                th, td { text-align: left; padding: 0.7rem; border-bottom: 1px solid var(--line); vertical-align: top; }
                th { background: #efe5d3; }
                .muted { color: var(--muted); }
                .danger { color: var(--danger); }
                .summary { display: flex; flex-wrap: wrap; gap: 1rem; }
                .summary strong { font-size: 1.4rem; }
              </style>
            </head>
            <body>
              <main>
                <header>
                  <h1>LLM 费用汇总</h1>
                  <p class="muted">按用户、项目、小时、天、月汇总 PhaseA 记录到的 LLM 费用。</p>
                </header>
                <section class="card filters">
                  <label>粒度
                    <select id="grain"><option value="day">天</option><option value="month">月</option><option value="hour">小时</option></select>
                  </label>
                  <label>拆分
                    <select id="split"><option value="account">用户</option><option value="project">项目</option><option value="account-project">用户 + 项目</option></select>
                  </label>
                  <label>开始 UTC
                    <input id="fromUtc" placeholder="可空，例 2026-05-01T00:00:00Z">
                  </label>
                  <label>结束 UTC
                    <input id="toUtc" placeholder="可空，默认当前时间">
                  </label>
                  <button id="load">加载汇总</button>
                </section>
                <section id="summary" class="card muted">尚未加载。</section>
                <section class="card">
                  <table>
                    <thead><tr><th>时间桶 UTC</th><th>用户</th><th>项目</th><th>调用</th><th>费用 CNY</th></tr></thead>
                    <tbody id="rows"><tr><td colspan="5" class="muted">暂无数据。</td></tr></tbody>
                  </table>
                </section>
              </main>
                <script>
                const $ = id => document.getElementById(id);
                const params = new URLSearchParams(location.search);
                const readBrowserCookie = name => {
                  const prefix = `${encodeURIComponent(name)}=`;
                  return document.cookie.split(";").map(part => part.trim()).find(part => part.startsWith(prefix))?.slice(prefix.length) || "";
                };
                const token = () => localStorage.getItem("phaseAAccessToken") || decodeURIComponent(readBrowserCookie("phaseAAccessToken") || "") || localStorage.getItem("phaseAAdminToken") || window.parent?.document?.getElementById?.("token")?.value?.trim?.() || "";
                const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#039;" }[ch]));
                $("grain").value = params.get("grain") || "day";
                $("split").value = params.get("split") || "account";

                async function loadUsage() {
                  if (!token()) {
                    $("summary").className = "card danger";
                    $("summary").textContent = "当前浏览器没有 token，请先回控制台登录。";
                    return;
                  }
                  const query = new URLSearchParams();
                  query.set("grain", $("grain").value || "day");
                  query.set("split", $("split").value || "account");
                  if ($("fromUtc").value.trim()) query.set("fromUtc", $("fromUtc").value.trim());
                  if ($("toUtc").value.trim()) query.set("toUtc", $("toUtc").value.trim());
                  const response = await fetch(`/api/admin/llm-usage/aggregate?${query}`, {
                    headers: { "Authorization": `Bearer ${token()}` },
                    cache: "no-store"
                  });
                  const payload = await response.json();
                  if (!response.ok) {
                    $("summary").className = "card danger";
                    $("summary").textContent = payload.error || "费用汇总加载失败。";
                    return;
                  }
                  $("summary").className = "card";
                  $("summary").innerHTML = `
                    <div class="summary">
                      <span><strong>${escapeHtml(payload.callCount)}</strong><br><span class="muted">调用次数</span></span>
                      <span><strong>CNY ${escapeHtml(Number(payload.estimatedCostCny || 0).toFixed(4))}</strong><br><span class="muted">费用</span></span>
                      <span><strong>${escapeHtml(payload.bucketCount)}</strong><br><span class="muted">时间桶</span></span>
                    </div>
                    <p class="muted">范围：${escapeHtml(payload.fromUtc)} 到 ${escapeHtml(payload.toUtc)}</p>
                  `;
                  const items = payload.items || [];
                  $("rows").innerHTML = items.map(item => `
                    <tr>
                      <td>${escapeHtml(item.bucketUtc)}</td>
                      <td>${escapeHtml(item.username)}<br><span class="muted">${escapeHtml(item.accountId)}</span></td>
                      <td>${item.projectId ? `${escapeHtml(item.projectName || item.projectId)}<br><span class="muted">${escapeHtml(item.gameName || "")}</span>` : "<span class='muted'>未按项目拆分</span>"}</td>
                      <td>${escapeHtml(item.callCount)}</td>
                      <td>CNY ${escapeHtml(Number(item.estimatedCostCny || 0).toFixed(4))}</td>
                    </tr>
                  `).join("") || `<tr><td colspan="5" class="muted">暂无数据。</td></tr>`;
                }

                $("load").onclick = loadUsage;
                loadUsage();
              </script>
            </body>
            </html>
            """;
    }

    public string RenderAdminRunDurationMetrics()
    {
        return RenderAdminRunMetricsPage(
            "runs",
            "普通用户 run 花费时间记录",
            "查看每个普通用户非聊天 run 的排队时长、运行时长和启动时队列序号。");
    }

    public string RenderAdminChatAverageMetrics()
    {
        return RenderAdminRunMetricsPage(
            "chat",
            "普通用户聊天平均响应时长",
            "按普通用户聚合聊天 run，查看平均排队时长和平均响应时长。");
    }

    private static string RenderAdminRunMetricsPage(string mode, string title, string description)
    {
        return """
            <!doctype html>
            <html lang="zh-CN">
            <head>
              <meta charset="utf-8">
              <meta name="viewport" content="width=device-width, initial-scale=1">
              <title>__TITLE__</title>
              <style>
                :root { --ink: #17211b; --muted: #66736b; --paper: #f7f2e8; --panel: #fffdf8; --line: #ded4c4; --accent: #0f6b57; --danger: #a2342f; }
                body { margin: 0; font-family: Georgia, "Times New Roman", serif; color: var(--ink); background: linear-gradient(135deg, #fbf7ef, #efe5d3); }
                main { max-width: 86rem; margin: 0 auto; padding: 2rem 1rem 4rem; display: grid; gap: 1rem; }
                h1 { margin: 0; font-size: clamp(2rem, 5vw, 4rem); letter-spacing: -0.06em; }
                .card { background: var(--panel); border: 1px solid var(--line); border-radius: 1rem; padding: 1rem; box-shadow: 0 1rem 2.4rem rgba(57, 43, 24, 0.1); }
                .filters { display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: end; }
                label { display: grid; gap: 0.3rem; font-weight: 700; }
                select, input { border: 1px solid var(--line); border-radius: 0.75rem; padding: 0.65rem 0.75rem; font: inherit; background: white; min-width: 12rem; }
                button { border: 0; border-radius: 0.75rem; padding: 0.75rem 1rem; background: var(--accent); color: white; font: inherit; font-weight: 700; cursor: pointer; }
                table { width: 100%; border-collapse: collapse; background: var(--panel); border-radius: 1rem; overflow: hidden; }
                th, td { text-align: left; padding: 0.7rem; border-bottom: 1px solid var(--line); vertical-align: top; }
                th { background: #efe5d3; white-space: nowrap; }
                td { overflow-wrap: anywhere; }
                .muted { color: var(--muted); }
                .danger { color: var(--danger); }
                .summary { display: flex; flex-wrap: wrap; gap: 1rem; }
                .summary strong { font-size: 1.4rem; }
              </style>
            </head>
            <body>
              <main>
                <header>
                  <h1>__TITLE__</h1>
                  <p class="muted">__DESCRIPTION__</p>
                </header>
                <section class="card filters">
                  <label>普通用户
                    <select id="account"><option value="">全部普通用户</option></select>
                  </label>
                  <label id="runTypeLabel">Run 类型
                    <input id="runType" placeholder="可空，例 prototype-workflow">
                  </label>
                  <button id="load">加载</button>
                  <button id="back" type="button">返回控制台</button>
                </section>
                <section id="summary" class="card muted">尚未加载。</section>
                <section class="card">
                  <table>
                    <thead id="head"></thead>
                    <tbody id="rows"><tr><td class="muted">暂无数据。</td></tr></tbody>
                  </table>
                </section>
                <section id="recentRunsSection" class="card hidden">
                  <h2 id="recentRunsTitle">最近聊天 run 明细</h2>
                  <table>
                    <thead id="recentHead"></thead>
                    <tbody id="recentRows"><tr><td class="muted">暂无数据。</td></tr></tbody>
                  </table>
                </section>
              </main>
                <script>
                const mode = "__MODE__";
                const $ = id => document.getElementById(id);
                const readBrowserCookie = name => {
                  const prefix = `${encodeURIComponent(name)}=`;
                  return document.cookie.split(";").map(part => part.trim()).find(part => part.startsWith(prefix))?.slice(prefix.length) || "";
                };
                const token = () => localStorage.getItem("phaseAAccessToken") || decodeURIComponent(readBrowserCookie("phaseAAccessToken") || "") || localStorage.getItem("phaseAAdminToken") || window.parent?.document?.getElementById?.("token")?.value?.trim?.() || "";
                const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#039;" }[ch]));
                const formatSeconds = value => {
                  if (value === null || value === undefined || value === "") return "-";
                  const number = Number(value);
                  if (!Number.isFinite(number)) return "-";
                  return `${number.toFixed(number >= 10 ? 1 : 3)}s`;
                };
                async function api(path) {
                  if (!token()) throw new Error("missing_token");
                  const response = await fetch(path, {
                    headers: { "Authorization": `Bearer ${token()}` },
                    cache: "no-store"
                  });
                  const payload = await response.json();
                  if (!response.ok) throw new Error(payload.error || "request_failed");
                  return payload;
                }
                async function loadUsers() {
                  const result = await api("/api/admin/users");
                  const users = (result.users || []).filter(user => !user.isAdmin);
                  $("account").innerHTML = `<option value="">全部普通用户</option>${users.map(user => `<option value="${escapeHtml(user.accountId)}">${escapeHtml(user.username)}</option>`).join("")}`;
                }
                async function loadMetrics() {
                  try {
                    $("summary").className = "card muted";
                    $("summary").textContent = "加载中...";
                    const query = new URLSearchParams();
                    if ($("account").value) query.set("accountId", $("account").value);
                    if (mode === "chat") {
                      query.set("runType", "prototype-chat");
                    } else if ($("runType").value.trim()) {
                      query.set("runType", $("runType").value.trim());
                    }
                    query.set("limit", "500");
                    const result = await api(`/api/admin/run-metrics?${query}`);
                    if (mode === "chat") {
                      renderChatAverages(result.chatAverages || [], result.chatRuns || []);
                    } else {
                      renderRunDurations(result.runs || [], result.count || 0, result.assetRuns || []);
                    }
                  } catch (error) {
                    $("summary").className = "card danger";
                    $("summary").textContent = error.message === "missing_token" ? "当前浏览器没有 token，请先回控制台登录。" : error.message;
                  }
                }
                function renderRunDurations(runs, count, assetRuns) {
                  $("recentRunsSection").classList.add("hidden");
                  $("head").innerHTML = "<tr><th>用户</th><th>项目</th><th>Run</th><th>状态</th><th>排队</th><th>运行</th><th>启动序号</th><th>时间</th></tr>";
                  $("summary").className = "card";
                  $("summary").innerHTML = `<div class="summary"><span><strong>${escapeHtml(count)}</strong><br><span class="muted">普通 run</span></span><span><strong>${escapeHtml(assetRuns.length)}</strong><br><span class="muted">素材生成 run</span></span></div>`;
                  const allRuns = [...runs, ...assetRuns];
                  $("rows").innerHTML = allRuns.map(run => `
                    <tr>
                      <td>${escapeHtml(run.username)}</td>
                      <td>${escapeHtml(run.projectName || run.projectId)}<br><span class="muted">${escapeHtml(run.gameName || "")}</span></td>
                      <td>${escapeHtml(run.runType)}<br><span class="muted">${escapeHtml(run.runId)}</span></td>
                      <td>${escapeHtml(run.status)}</td>
                      <td>${escapeHtml(formatSeconds(run.queueSeconds))}</td>
                      <td>${escapeHtml(formatSeconds(run.runtimeSeconds))}</td>
                      <td>${escapeHtml(run.queuePositionAtStart ?? "-")}</td>
                      <td><span class="muted">created</span> ${escapeHtml(run.createdUtc)}<br><span class="muted">started</span> ${escapeHtml(run.startedUtc || "")}<br><span class="muted">finished</span> ${escapeHtml(run.finishedUtc || "")}</td>
                    </tr>
                  `).join("") || `<tr><td colspan="8" class="muted">没有匹配的 run。</td></tr>`;
                }
                function renderChatAverages(items, chatRuns) {
                  $("head").innerHTML = "<tr><th>用户</th><th>聊天 run 数</th><th>平均排队</th><th>平均响应</th></tr>";
                  const totalRuns = items.reduce((sum, item) => sum + Number(item.runCount || 0), 0);
                  $("summary").className = "card";
                  $("summary").innerHTML = `<div class="summary"><span><strong>${escapeHtml(items.length)}</strong><br><span class="muted">普通用户</span></span><span><strong>${escapeHtml(totalRuns)}</strong><br><span class="muted">聊天 run</span></span><span><strong>${escapeHtml(chatRuns.length)}</strong><br><span class="muted">最近聊天记录</span></span></div>`;
                  $("rows").innerHTML = items.map(item => `
                    <tr>
                      <td>${escapeHtml(item.username)}<br><span class="muted">${escapeHtml(item.accountId)}</span></td>
                      <td>${escapeHtml(item.runCount)}</td>
                      <td>${escapeHtml(formatSeconds(item.averageQueueSeconds))}</td>
                      <td>${escapeHtml(formatSeconds(item.averageRuntimeSeconds))}</td>
                    </tr>
                  `).join("") || `<tr><td colspan="4" class="muted">没有匹配的聊天平均数据。</td></tr>`;
                  $("recentRunsSection").classList.remove("hidden");
                  $("recentRunsTitle").textContent = "最近聊天 run 明细";
                  $("recentHead").innerHTML = "<tr><th>用户</th><th>Run</th><th>排队</th><th>状态 / 响应</th></tr>";
                  $("recentRows").innerHTML = chatRuns.map(run => `
                    <tr>
                      <td>${escapeHtml(run.username)}<br><span class="muted">${escapeHtml(run.accountId)}</span></td>
                      <td>${escapeHtml(run.runId)}</td>
                      <td>${escapeHtml(formatSeconds(run.queueSeconds))}</td>
                      <td>${escapeHtml(run.status)} · ${escapeHtml(formatSeconds(run.runtimeSeconds))}<br><span class="muted">${escapeHtml(run.createdUtc)}</span></td>
                    </tr>
                  `).join("") || `<tr><td colspan="4" class="muted">没有最近聊天 run 明细。</td></tr>`;
                }
                $("load").onclick = loadMetrics;
                $("back").onclick = () => { location.href = "/"; };
                if (mode === "chat") $("runTypeLabel").style.display = "none";
                loadUsers().then(loadMetrics).catch(error => {
                  $("summary").className = "card danger";
                  $("summary").textContent = error.message === "missing_token" ? "当前浏览器没有 token，请先回控制台登录。" : error.message;
                });
              </script>
            </body>
            </html>
            """
            .Replace("__MODE__", mode, StringComparison.Ordinal)
            .Replace("__TITLE__", WebUtility.HtmlEncode(title), StringComparison.Ordinal)
            .Replace("__DESCRIPTION__", WebUtility.HtmlEncode(description), StringComparison.Ordinal);
    }

    private static string WrapSimplePage(string title, string body)
    {
        return $"""
            <!doctype html>
            <html lang="zh-CN">
            <head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}</title></head>
            <body>{body}</body>
            </html>
            """;
    }

    private static string Encode(string value)
    {
        return WebUtility.HtmlEncode(value);
    }
}
