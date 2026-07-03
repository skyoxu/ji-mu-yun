using System.Net;
using System.Reflection;
using System.Text;
using System.Text.Json;
using PhaseA.Platform.Data;
using PhaseA.Platform.Readback;

namespace PhaseA.Platform.Browser;

public sealed class BrowserUiRenderer
{
    private static readonly string[] PrototypeSkeletonRunNotes = LoadPrototypeSkeletonRunNotes();

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
                body.v2-detail .prototype-draft-row .import-draft-button.import-draft-ready:not(:disabled) { background: #d92d20; border-color: #d92d20; color: #fff; font-weight: 800; box-shadow: 0 8px 18px rgba(217, 45, 32, 0.18); }
                body.v2-detail .prototype-draft-row .import-draft-button.import-draft-ready:not(:disabled):hover { background: #b42318; border-color: #b42318; }
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
                body.v2-detail .v2-tabs { position: sticky; top: 0; z-index: 1301; display: flex; align-items: end; gap: 0.12rem; overflow-x: auto; padding: 0 0.45rem; margin-bottom: -1px; border-bottom: 0; background: transparent; }
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
                body.v2-detail .legacy-iteration-plan-ui,
                body.v2-detail #iterationPlanEvaluation,
                body.v2-detail #v2IterationSummary,
                body.v2-detail #iterationNeedsFixStatus,
                body.v2-detail #iterationPlanStatus { display: none !important; }
                body.v2-detail .milestone-progress-shell { display: grid; gap: 0.65rem; }
                body.v2-detail .milestone-progress-header { display: flex; align-items: baseline; justify-content: space-between; gap: 0.75rem; flex-wrap: wrap; }
                body.v2-detail .milestone-progress-actions { display: flex; align-items: center; justify-content: flex-end; gap: 0.5rem; flex-wrap: wrap; }
                body.v2-detail .milestone-progress-actions button { width: auto; }
                body.v2-detail .milestone-progress-track { display: grid; grid-template-columns: repeat(auto-fit, minmax(4.8rem, 1fr)); gap: 0.45rem; }
                body.v2-detail .milestone-progress-button { min-height: 3.25rem; display: grid; grid-template-rows: auto auto; gap: 0.32rem; align-items: center; justify-items: center; border: 1px solid var(--line); border-radius: 0.55rem; background: #fffdf8; color: var(--ink); padding: 0.48rem; }
                body.v2-detail .milestone-progress-button.active { outline: 2px solid var(--accent-2); border-color: var(--accent-2); }
                body.v2-detail .milestone-progress-button .milestone-progress-label { font-size: 0.83rem; font-weight: 800; white-space: nowrap; }
                body.v2-detail .milestone-status-square { width: 1rem; height: 1rem; border-radius: 0.2rem; background: #a8afad; }
                body.v2-detail .milestone-progress-button.done .milestone-status-square { background: #15905f; }
                body.v2-detail .milestone-progress-button.running .milestone-status-square { background: #d7a924; }
                body.v2-detail .milestone-progress-button.pending .milestone-status-square,
                body.v2-detail .milestone-progress-button.locked .milestone-status-square { background: #a8afad; }
                body.v2-detail .milestone-evidence-list { margin: 0.35rem 0 0; padding-left: 1.1rem; }
                body.v2-detail .milestone-evidence-list li { margin: 0.15rem 0; }
                body.v2-detail .milestone-result-panel { border: 1px solid var(--line); border-radius: 0.45rem; padding: 0.65rem; margin: 0.65rem 0; background: #fffdf8; }
                body.v2-detail .milestone-playtest-panel { border: 1px solid #c9dbff; border-radius: 0.45rem; padding: 0.65rem; margin: 0.65rem 0; background: #f8fbff; }
                body.v2-detail .milestone-playtest-panel p { margin: 0.35rem 0 0; }
                body.v2-detail .milestone-result-panel ul { margin: 0.35rem 0 0; padding-left: 1.1rem; }
                body.v2-detail .milestone-result-panel li { margin: 0.2rem 0; }
                body.v2-detail .milestone-detail-nav { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; flex-wrap: wrap; margin-top: 0.65rem; }
                body.v2-detail .milestone-detail-nav button { width: auto; }
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
        const string notesPlaceholder = "__PROTOTYPE_SKELETON_RUN_NOTES__";
        return """
              <script>
                document.body.classList.add("v2-detail");
                const PrototypeSkeletonRunNotes = __PROTOTYPE_SKELETON_RUN_NOTES__;
                const v2Steps = [
                  ["new-project", "游戏项目概述", "panel"],
                  ["create-prototype", "游戏场景创建", "spark"],
                  ["execute-or-repair", "场景验收修复", "wrench"],
                  ["iteration-plan", "完成游戏模块", "list"],
                  ["prototype-acceptance", "原型项目验收", "check"],
                  ["asset-inventory", "项目素材库", "image"],
                  ["download-project", "打包下载项目", "download"]
                ];
                let v2SelectedStep = "new-project";
                let v2UserSelectedStep = false;
                let v2CurrentProjectId = "";
                let v2ActiveTabId = "chat";
                let v2RestoredProjectUiStateId = "";
                let v2PendingProjectUiSkillMode = "";
                const v2ProjectUiStateVersion = 2;
                const v2OpenTabs = new Map([["chat", { id: "chat", label: "游戏策划创作", panelId: "chatPanel", closable: false }]]);
                function v2ProjectUiStateKey(projectId = state.projectId) {
                  return `phaseA.projectUiState.v${v2ProjectUiStateVersion}.${projectId || "none"}`;
                }
                function v2LegacyProjectUiStateKey(projectId = state.projectId) {
                  return `phaseA.projectUiState.v1.${projectId || "none"}`;
                }
                function v2NormalizeProjectUiState(cached) {
                  if (!cached || !cached.projectId) return null;
                  const stateJson = cached.stateJson && typeof cached.stateJson === "string" ? cached.stateJson : null;
                  const rawState = stateJson ? (() => { try { return JSON.parse(stateJson); } catch { return null; } })() : cached;
                  if (!rawState || typeof rawState !== "object") return null;
                  return {
                    ...rawState,
                    schemaVersion: v2ProjectUiStateVersion,
                    projectId: String(rawState.projectId || cached.projectId || "")
                  };
                }
                function v2ReadProjectUiState(projectId = state.projectId) {
                  if (!projectId) return null;
                  try {
                    const currentCached = JSON.parse(localStorage.getItem(v2ProjectUiStateKey(projectId)) || "null");
                    const normalizedCurrent = v2NormalizeProjectUiState(currentCached);
                    if (normalizedCurrent && Number(currentCached?.schemaVersion || v2ProjectUiStateVersion) === v2ProjectUiStateVersion) {
                      return normalizedCurrent;
                    }
                    const legacyCached = JSON.parse(localStorage.getItem(v2LegacyProjectUiStateKey(projectId)) || "null");
                    const normalizedLegacy = v2NormalizeProjectUiState(legacyCached);
                    if (!normalizedLegacy) return null;
                    try { localStorage.setItem(v2ProjectUiStateKey(projectId), JSON.stringify(normalizedLegacy)); } catch {}
                    return normalizedLegacy;
                  } catch {
                    return null;
                  }
                }
                async function v2FetchProjectUiState(projectId = state.projectId) {
                  if (!projectId) return null;
                  try {
                    const cached = await api(`/api/projects/${encodeURIComponent(projectId)}/ui-state`);
                    const normalized = v2NormalizeProjectUiState(cached);
                    if (!normalized) return null;
                    try { localStorage.setItem(v2ProjectUiStateKey(projectId), JSON.stringify(normalized)); } catch {}
                    return normalized;
                  } catch {
                    return null;
                  }
                }
                function v2ProjectUiStateUpdatedAt(source) {
                  const value = String(source?.updatedAt || source?.updatedUtc || source?.updated_utc || "").trim();
                  const time = Date.parse(value);
                  return Number.isFinite(time) ? time : 0;
                }
                function v2ChooseProjectUiStateSource(...sources) {
                  return sources
                    .filter(source => source && typeof source === "object")
                    .sort((left, right) => v2ProjectUiStateUpdatedAt(right) - v2ProjectUiStateUpdatedAt(left))[0] || null;
                }
                function v2BuildProjectUiStateSeed(projectId = state.projectId) {
                  return {
                    projectId,
                    schemaVersion: v2ProjectUiStateVersion,
                    activeTabId: "chat",
                    selectedStep: "new-project",
                    userSelectedStep: false,
                    tabs: [],
                    settings: {
                      advancedPlanningMode: ($("chatSkillMode")?.value || "normal") === "game-design-master",
                      chatSkillMode: $("chatSkillMode")?.value || "normal",
                      projectAnalysisMode: !!state.projectAnalysisMode
                    },
                    updatedAt: new Date().toISOString()
                  };
                }
                function v2EnsureProjectUiStateSeed(projectId = state.projectId) {
                  if (!projectId) return null;
                  const cached = v2ReadProjectUiState(projectId);
                  if (cached) return cached;
                  const seed = v2BuildProjectUiStateSeed(projectId);
                  try { localStorage.setItem(v2ProjectUiStateKey(projectId), JSON.stringify(seed)); } catch {}
                  return seed;
                }
                function v2BuildProjectUiStatePayload() {
                  if (!state.projectId) return null;
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
                  return {
                    projectId: state.projectId,
                    schemaVersion: v2ProjectUiStateVersion,
                    activeTabId: v2ActiveTabId,
                    selectedStep: v2SelectedStep,
                    userSelectedStep: !!v2UserSelectedStep,
                    tabs,
                    settings,
                    updatedAt: new Date().toISOString()
                  };
                }
                async function v2WriteProjectUiState() {
                  const payload = v2BuildProjectUiStatePayload();
                  if (!payload) return;
                  const projectId = payload.projectId || state.projectId;
                  try { localStorage.setItem(v2ProjectUiStateKey(projectId), JSON.stringify(payload)); } catch {}
                  try {
                    await api(`/api/projects/${encodeURIComponent(projectId)}/ui-state`, {
                      method: "POST",
                      body: JSON.stringify(payload)
                    });
                  } catch {}
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
                async function v2RestoreProjectUiState(projectId = state.projectId) {
                  if (!projectId) return;
                  const requestAuthEpoch = authEpoch;
                  if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
                  if (v2RestoredProjectUiStateId === projectId) {
                    v2LoadProjectUiStateTabState();
                    return;
                  }
                  v2RestoredProjectUiStateId = projectId;
                  const cached = v2ReadProjectUiState(projectId);
                  const remote = await v2FetchProjectUiState(projectId);
                  if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
                  const source = v2ChooseProjectUiStateSource(remote, cached) || v2BuildProjectUiStateSeed(projectId);
                  if (!cached) {
                    try { localStorage.setItem(v2ProjectUiStateKey(projectId), JSON.stringify(source)); } catch {}
                  }
                  if (!source) {
                    if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
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
                  for (const tab of Array.isArray(source.tabs) ? source.tabs : []) {
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
                  const activeTabId = String(source.activeTabId || "chat");
                  v2ActiveTabId = v2OpenTabs.has(activeTabId) ? activeTabId : "chat";
                  if (typeof source.selectedStep === "string" && source.selectedStep) {
                    v2SelectedStep = source.selectedStep;
                  }
                  v2UserSelectedStep = !!source.userSelectedStep;
                  const activeTab = v2OpenTabs.get(v2ActiveTabId);
                  if (activeTab?.stepId) {
                    v2SelectedStep = activeTab.stepId;
                    v2UserSelectedStep = true;
                  }
                  state.projectAnalysisMode = !!source.settings?.projectAnalysisMode;
                  const skillMode = source.settings?.advancedPlanningMode ? "game-design-master" : String(source.settings?.chatSkillMode || "");
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
                  if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
                  v2LoadProjectUiStateTabState(source);
                }
                function v2LoadProjectUiStateTabState(source = null) {
                  const cached = source || v2ReadProjectUiState(state.projectId);
                  if (!cached) return;
                  if (Array.isArray(cached.tabs) && cached.tabs.length) {
                    v2OpenTabs.forEach((tab, tabId) => {
                      if (tabId !== "chat") v2OpenTabs.delete(tabId);
                    });
                    for (const tab of cached.tabs) {
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
                  }
                  const activeTabId = String(cached.activeTabId || "chat");
                  v2ActiveTabId = v2OpenTabs.has(activeTabId) ? activeTabId : "chat";
                  const activeTab = v2OpenTabs.get(v2ActiveTabId);
                  if (activeTab?.stepId) {
                    v2SelectedStep = activeTab.stepId;
                    v2UserSelectedStep = true;
                  }
                  v2RenderTabs();
                  v2ApplySelectedStepVisibility();
                  v2RenderProgress();
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
                  v2LoadEmbeddedFrame(frameId, url, true);
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
                  updateProjectSwitchAvailability();
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
                  return evidence?.validation_only === true && evidence?.skeleton_validation_only !== true;
                }
                function v2IsSkeletonValidationRun(run) {
                  const evidence = v2RunEvidence(run);
                  return evidence?.validation_only === true && evidence?.skeleton_validation_only === true;
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
                function v2LatestSkeletonValidationRun() {
                  return (state.runs || [])
                    .filter(run => String(run.runType || "").toLowerCase() === "prototype-7day-playable" && v2IsSkeletonValidationRun(run))
                    .sort((a, b) => v2RunTimestamp(b) - v2RunTimestamp(a) || String(b.runId || "").localeCompare(String(a.runId || "")))[0] || null;
                }
                function v2IsoTime(value) {
                  const time = Date.parse(value || "");
                  return Number.isFinite(time) ? time : 0;
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
                function v2GlobalIterationGoals() {
                  const plan = v2LatestIterationPlanForGlobalState();
                  return Array.isArray(plan?.goals) ? plan.goals : [];
                }
                function v2IsRepairGoalStatus(status) {
                  return ["needs_fix", "failed"].includes(String(status || "").trim().toLowerCase());
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
                  if (stepId === "new-project") return state.projectId ? "done" : "pending";
                  if (stepId === "create-prototype") {
                    if (prototypeSkeletonM1Completed()) return "done";
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
                  if (stepId === "iteration-plan") {
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
                  if (stepId === "execute-or-repair") {
                    if (prototypeSkeletonM1Completed()) return "done";
                    const goals = state.repairPlan?.goals || [];
                    const skeletonValidation = v2LatestSkeletonValidationRun();
                    const skeletonValidationStatus = String(skeletonValidation?.status || "").trim().toLowerCase();
                    if (skeletonValidationStatus === "succeeded") return "done";
                    if (skeletonValidationStatus === "failed") return "fix";
                    if (failed && !v2HasPrototypeSkeleton()) return "fix";
                    if (goals.some(goal => goal.status === "needs_fix" || goal.status === "failed")) return "fix";
                    if (goals.length && goals.every(goal => goal.status === "succeeded" || goal.status === "completed")) return "done";
                    if (!goals.length && v2HasPrototypeSkeleton()) return "done";
                    return "pending";
                  }
                  if (stepId === "asset-inventory") return v2AssetInventoryConfirmed() ? "done" : "pending";
                  if (stepId === "download-project") return v2HasPackages() ? "done" : "pending";
                  return "pending";
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
                function v2LoadEmbeddedFrame(frameId, url, forceReload = false) {
                  const frame = $(frameId);
                  if (!frame) return;
                  if (forceReload || frame.dataset.src !== url) {
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
                    "iterationPlanGoals",
                    "gddMilestoneStepStatus",
                    "gddMilestoneStepActions"
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
                  panel.innerHTML = "<h2>原型项目验收结果</h2>";
                  summary.insertAdjacentElement("beforebegin", panel);
                  panel.appendChild(summary);
                  const actions = document.createElement("div");
                  actions.className = "v2-action-row";
                  const rerun = document.createElement("button");
                  rerun.id = "v2RevalidatePrototype";
                  rerun.className = "secondary";
                  rerun.type = "button";
                  rerun.textContent = "重新触发原型项目验收";
                  rerun.onclick = v2ValidatePrototypeIfAllowed;
                  actions.appendChild(rerun);
                  panel.appendChild(actions);
                  const status = document.createElement("div");
                  status.id = "v2AcceptanceActionStatus";
                  status.className = "card muted";
                  status.textContent = "原型项目验收入口会在游戏模块完成后启用。";
                  panel.appendChild(status);
                }
                function v2IterationPlanAllowsAcceptance() {
                  const goals = v2GlobalIterationGoals();
                  if (!Array.isArray(goals) || goals.length === 0) return false;
                  return goals.every(goal => ["succeeded", "completed"].includes(String(goal.status || "").trim().toLowerCase()));
                }
                function v2PrototypeAcceptanceBlockReason() {
                  const goals = v2GlobalIterationGoals();
                  if (!Array.isArray(goals) || goals.length === 0) {
                    return "请先生成并完成当前游戏模块，所有任务完成后再进行原型项目验收。";
                  }
                  if (!v2IterationPlanAllowsAcceptance()) {
                    return "请先完成当前游戏模块，所有任务完成后再进行原型项目验收。";
                  }
                  if (isGlobalBusy()) {
                    return "当前有任务正在执行，请等待当前 run 完成后再进行原型项目验收。";
                  }
                  return "";
                }
                function v2RefreshAcceptanceActionState() {
                  const rerun = $("v2RevalidatePrototype");
                  const legacyRerun = $("validatePrototype");
                  const status = $("v2AcceptanceActionStatus");
                  const reason = v2PrototypeAcceptanceBlockReason();
                  if (rerun) setButtonDisabledState(rerun, !!reason, reason || "");
                  if (legacyRerun) setButtonDisabledState(legacyRerun, !!reason, reason || "");
                  if (status) {
                    status.className = reason ? "card muted" : "card";
                    status.textContent = reason || "当前已满足原型项目验收条件，点击按钮会创建一条原型项目验收 run。";
                  }
                }
                async function validatePrototypeSkeleton(autoTriggered = false) {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("请先选择一个项目。");
                  const context = projectRequestContext();
                  const projectId = context.projectId;
                  setLocalBusy(true, autoTriggered ? "场景创建完成，正在自动执行场景验收。" : "场景验收中，请等待当前任务执行完毕。");
                  const skeletonButton = $("v2SkeletonAcceptance");
                  if (skeletonButton) skeletonButton.textContent = autoTriggered ? "场景验收中..." : "验收中...";
                  if (autoTriggered) {
                    showPrototypeNotice("游戏场景创建完成，正在自动执行一次场景验收；该操作只验证场景可运行，不等同于最终原型项目验收。", "info");
                  } else {
                    showPrototypeNotice("正在执行场景验收；该操作只验证场景可运行，不要求游戏模块已完成。", "info");
                  }
                  try {
                    const result = await api(`/api/projects/${projectId}/prototype-7day-playable/validate-skeleton`, { method: "POST" });
                    if (!isCurrentProjectContext(context)) return null;
                    out(result);
                    await trackProjectRunFromResult(result, projectId, context.authEpoch);
                    await loadRuns();
                    await loadPrototypeProgress();
                    if (result.status === "failed") {
                      const label = result.progress?.label || result.stderr || "场景验收失败，请查看运行记录并生成修复计划。";
                      showPrototypeNotice(label, "warn");
                    }
                    return result;
                  } catch (error) {
                    if (!isCurrentProjectContext(context)) return null;
                    if (!autoTriggered) showError(error);
                    await loadPrototypeProgress();
                    return null;
                  } finally {
                    if (!isCurrentProjectContext(context)) return null;
                    try {
                      await refreshActiveRun();
                    } finally {
                      setLocalBusy(false);
                      if (skeletonButton) skeletonButton.textContent = "场景验收";
                    }
                  }
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
                async function v2ValidateSkeletonIfAllowed() {
                  await validatePrototypeSkeleton(false);
                }
                function v2ArrangeIterationPanel() {
                  const panel = $("v2IterationPanel");
                  if (!panel || $("v2IterationMainActions")) return;
                  const mainActions = document.createElement("div");
                  mainActions.id = "v2IterationMainActions";
                  mainActions.className = "v2-action-row legacy-iteration-plan-ui";
                  const createPlan = $("createIterationPlan");
                  const evaluatePlan = $("evaluateIterationPlan");
                  const executeGoal = $("executeIterationGoal");
                  const deletePlan = $("deleteIterationPlan");
                  createPlan?.insertAdjacentElement("beforebegin", mainActions);
                  const roundTabs = document.createElement("div");
                  roundTabs.id = "v2IterationRoundTabs";
                  roundTabs.className = "v2-round-tabs hidden legacy-iteration-plan-ui";
                  mainActions.insertAdjacentElement("beforebegin", roundTabs);
                  [createPlan, evaluatePlan, executeGoal, deletePlan].filter(Boolean).forEach(button => mainActions.appendChild(button));
                  [
                    "v2IterationSummary",
                    "iterationAutoRefreshHint",
                    "iterationPlanStatus",
                    "iterationPlanEvaluation",
                    "iterationNeedsFixStatus",
                    "iterationPlanGoals"
                  ].map($).filter(Boolean).forEach(element => element.classList.add("legacy-iteration-plan-ui"));

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
                  skeletonAcceptance.textContent = "场景验收";
                  skeletonAcceptance.onclick = v2ValidateSkeletonIfAllowed;
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
                  return v2GlobalIterationGoals().length > 0;
                }
                function v2IterationPlanCompleted() {
                  const goals = v2GlobalIterationGoals();
                  return goals.length > 0 && goals.every(goal => ["succeeded", "completed"].includes(String(goal.status || "").trim().toLowerCase()));
                }
                function v2PrototypeValidationPassedForPlanning() {
                  return state.prototypeReadyForFeedback && !state.v2PrototypeValidationInvalidatedByIteration;
                }
                function v2SkeletonValidationSucceeded() {
                  const skeletonValidation = v2LatestSkeletonValidationRun();
                  return String(skeletonValidation?.status || "").trim().toLowerCase() === "succeeded";
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
                  const currentProjectCancelled = !!state.cancelledActiveRunId && state.cancelledActiveRunProjectId === state.projectId;
                  if (currentProjectCancelled || readCancelledPrototypeMarker(state.projectId)) return false;
                  const acceptanceStatus = String(state.prototypeReadyForFeedback ? "succeeded" : state?.v2PrototypeAcceptanceStatus || "").trim().toLowerCase();
                  const status = String(state?.v2PrototypeCreationStatus || v2PrototypeStatus() || "").trim().toLowerCase();
                  return !!state.projectId && (acceptanceStatus === "succeeded" || v2HasPrototypeSkeleton() || v2SkeletonValidationSucceeded() || (status !== "" && !["idle", "failed"].includes(status)));
                }
                function v2ApplyPrototypeFormLock() {
                  const locked = v2ShouldLockPrototypeForm();
                  $("prototypeWorkflowPanel")?.classList.toggle("v2-prototype-locked", locked);
                  prototypeInputIds.forEach(id => { if ($(id)) $(id).disabled = locked; });
                  setPrototypeDraftFileLocked(locked);
                  if ($("importDraft")) setButtonDisabledState($("importDraft"), locked, "游戏场景已验收通过，不能重复创建。");
                  if (!locked && typeof resetPrototypeActionButtonsVisualState === "function") {
                    resetPrototypeActionButtonsVisualState();
                    updateDraftImportButtonState();
                  }
                  if ($("runPrototype")) {
                    setButtonDisabledState($("runPrototype"), locked || isGlobalBusy(), locked ? "游戏场景已验收通过，不能重复创建。" : "");
                    $("runPrototype").textContent = locked ? "M1 游戏场景已完成" : "确认 GDD 无误，执行 M1 游戏场景";
                  }
                  if (typeof updatePrototypeSkeletonPackageButton === "function") updatePrototypeSkeletonPackageButton();
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
                  const plan = v2LatestIterationPlanForGlobalState();
                  const goals = Array.isArray(plan?.goals) ? plan.goals : [];
                  const hasPlan = !!plan?.session && goals.length > 0;
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
                  const projectId = state.projectId;
                  if (!projectId) return out("请先选择一个项目。");
                  const requestAuthEpoch = authEpoch;
                  const message = state.chatHistory.find(item => item.workflowActionToken === token);
                  const action = workflowMessageActions(message).find(item => item.actionId === actionId) || workflowMessageActions(message)[0];
                  if (!message || !action || message.workflowActionConsumed || state.workflowRouteActionToken !== token) return;
                  let currentRoute = null;
                  try {
                    currentRoute = await fetchWorkflowRoute(message.workflowIntent, projectId);
                    if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
                  } catch (error) {
                    if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
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
                      return out("游戏界面优化当前未作为主流程开放，请继续进行原型项目验收或打包试玩。");
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

                async function queryWorkflowRoute(intent = null, projectId = state.projectId, allowCurrentBusy = false, requestAuthEpoch = authEpoch) {
                  if (!projectId) return out("请先选择一个项目。");
                  if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
                  if (!allowCurrentBusy && isGlobalBusy()) return out("当前有任务正在执行，请等待当前任务完成后再扫描项目状态。");
                  if (state.workflowRouteBusy) return out("项目状态扫描中，请等待当前扫描完成。");
                  state.workflowRouteBusy = true;
                  applyGlobalBusyState("正在扫描项目状态，请等待当前扫描完成。");
                  const button = $("v2JudgeNextStep");
                  if (button) {
                    button.disabled = true;
                    button.textContent = "扫描中...";
                  }
                  v2ShowChatTab();
                  const thinking = startChatThinkingMessage("正在扫描项目状态...");
                  try {
                    const route = await fetchWorkflowRoute(intent, projectId);
                    if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
                    thinking.complete(buildWorkflowRouteChatContent(route, intent), false, "workflow-route", buildWorkflowRouteMessageExtra(route, intent));
                  } catch (error) {
                    if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
                    const failure = workflowRouteFailureMessage(error);
                    thinking.complete(failure, true, "workflow-route");
                    showError(error);
                  } finally {
                    if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
                    state.workflowRouteBusy = false;
                    applyGlobalBusyState();
                    if (button) {
                      button.disabled = false;
                      button.textContent = "下一步建议";
                    }
                  }
                }
                function workflowRouteFailureMessage(error) {
                  const code = publicErrorCode(error?.payload?.failureCode || error?.payload?.error || error?.payload?.status || error?.status || "unknown_error");
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
                async function fetchWorkflowRoute(intent = null, projectId = state.projectId) {
                  return await api(`/api/projects/${projectId}/workflow-route${workflowRouteQueryForIntent(intent)}`);
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
                  v2RestoreProjectUiState(state.projectId);
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
                  state.v2PrototypeAcceptanceStatus = progress?.acceptanceStatus || "";
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
            """
            .Replace(notesPlaceholder, JsonSerializer.Serialize(PrototypeSkeletonRunNotes), StringComparison.Ordinal);
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
                button.button-state-enabled { cursor: pointer; opacity: 1; }
                button.button-state-disabled {
                  cursor: not-allowed;
                  opacity: 0.45;
                  filter: grayscale(0.25);
                }
                button:disabled,
                button[disabled],
                button.button-state-disabled {
                  cursor: not-allowed;
                  opacity: 0.45 !important;
                  filter: grayscale(0.25);
                  background-color: #9ca3af !important;
                  border-color: #9ca3af !important;
                  color: #f8fafc !important;
                }
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
                  z-index: 1200;
                  width: min(calc(100vw - 2rem), 72rem);
                  min-height: 2.75rem;
                  display: flex;
                  align-items: center;
                  justify-content: space-between;
                  gap: 0.75rem;
                  border: 1px solid var(--accent-2);
                  background: #fff8e6;
                  border-top: 0;
                  border-radius: 0 0 0.9rem 0.9rem;
                  box-shadow: 0 0.85rem 2.5rem rgba(57, 43, 24, 0.2);
                  padding: 0.7rem 1rem;
                  color: var(--ink);
                  font-weight: 700;
                  line-height: 1.35;
                  text-align: center;
                  max-height: 100px;
                  overflow-y: auto;
                  overflow-wrap: break-word;
                  word-break: normal;
                  pointer-events: none;
                }
                .busy-banner.busy-banner-prototype-skeleton {
                  display: grid;
                  gap: 0.35rem;
                  grid-template-columns: minmax(0, 1fr) auto;
                  justify-items: stretch;
                  align-items: start;
                  text-align: left;
                  height: 100px;
                  min-height: 100px;
                  max-height: 100px;
                  overflow: hidden;
                }
                #activeRunBanner {
                  position: absolute;
                  top: 0;
                  left: 50%;
                  transform: translateX(-50%);
                }
                #activeRunBanner.busy-banner-prototype-skeleton {
                  position: absolute;
                }
                .busy-banner > span,
                .busy-banner .busy-banner-lines,
                .busy-banner .busy-banner-actions,
                .busy-banner .busy-banner-note-window,
                .busy-banner .busy-banner-line {
                  pointer-events: auto;
                  user-select: text;
                }
                .busy-banner.busy-banner-prototype-skeleton.is-expanded {
                  height: min(27rem, calc(100vh - 6rem));
                  min-height: min(27rem, calc(100vh - 6rem));
                  max-height: calc(100vh - 6rem);
                }
                .busy-banner-prototype-skeleton .busy-banner-lines {
                  display: grid;
                  gap: 0.2rem;
                  width: 100%;
                  min-height: 0;
                  overflow: hidden;
                  grid-column: 1;
                }
                .busy-banner-prototype-skeleton .busy-banner-line {
                  min-height: 1.35rem;
                  line-height: 1.35;
                  white-space: normal;
                }
                .busy-banner-prototype-skeleton .busy-banner-line.is-muted {
                  color: var(--muted);
                  font-weight: 600;
                }
                .busy-banner-prototype-skeleton .busy-banner-details {
                  display: grid;
                  align-content: start;
                  gap: 0.2rem;
                  width: 100%;
                  min-height: 0;
                  max-height: 15rem;
                  overflow-y: auto;
                  overscroll-behavior: contain;
                  pointer-events: auto;
                  padding-right: 0.15rem;
                  grid-column: 1;
                }
                .busy-banner-prototype-skeleton .busy-banner-note-window {
                  display: grid;
                  align-content: start;
                  gap: 0.2rem;
                  min-height: 0;
                  overflow: hidden;
                }
                .busy-banner-prototype-skeleton.is-expanded .busy-banner-note-window {
                  max-height: 15rem;
                  overflow-y: auto;
                  overscroll-behavior: contain;
                  pointer-events: auto;
                  padding-right: 0.15rem;
                }
                .busy-banner-prototype-skeleton .busy-banner-actions {
                  display: grid;
                  gap: 0.35rem;
                  align-content: start;
                  justify-items: stretch;
                  grid-column: 2;
                  grid-row: 1 / span 2;
                  min-width: 6rem;
                }
                .busy-banner > span { flex: 1 1 auto; min-width: 0; text-align: left; }
                .busy-banner button {
                  flex: 0 0 auto;
                  width: auto;
                  min-width: 4.5rem;
                  max-width: 8rem;
                  padding: 0.45rem 0.8rem;
                  white-space: nowrap;
                  pointer-events: auto;
                  user-select: none;
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
                .gdd-question-loading { display: grid; gap: 0.55rem; align-content: start; }
                .gdd-question-progress {
                  position: relative;
                  width: 100%;
                  height: 0.7rem;
                  border: 1px solid var(--line);
                  border-radius: 999px;
                  background: #f3ead9;
                  overflow: hidden;
                }
                .gdd-question-progress-bar {
                  width: 0%;
                  height: 100%;
                  border-radius: inherit;
                  background: var(--accent);
                  transition: width 120ms linear;
                }
                .gdd-question-progress-value {
                  font-size: 0.9rem;
                  font-weight: 800;
                  color: var(--accent);
                  text-align: right;
                }
                .login-shell { max-width: 34rem; justify-self: center; width: 100%; }
                .token-box {
                  min-height: 7rem;
                  font-family: Consolas, "Courier New", monospace;
                  overflow-wrap: anywhere;
                  word-break: break-all;
                }
                .hidden { display: none !important; }
                .header-low {
                  position: relative;
                  z-index: 30;
                }
                @media (max-width: 920px) {
                  .header-row, main, .grid, .health-grid { grid-template-columns: 1fr; }
                  .top-actions { justify-content: stretch; }
                  .top-actions button, .top-actions label, .top-actions select { width: 100%; }
                }
              </style>
            </head>
            <body>
              <div id="activeRunBanner" class="busy-banner hidden" role="status" aria-live="polite"></div>
              <header>
                <div class="header-row header-low">
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
              <div id="milestoneFeedbackModal" class="modal-backdrop hidden" role="dialog" aria-modal="true" aria-labelledby="milestoneFeedbackTitle">
                <div class="modal-card modal-card-large">
                  <section class="stack">
                    <h2 id="milestoneFeedbackTitle">提交反馈并修正模块</h2>
                    <div id="milestoneFeedbackMeta" class="card muted">请选择当前激活模块。</div>
                    <label>试玩反馈或修改意见
                      <textarea id="milestoneFeedbackInput" rows="6" placeholder="描述你在当前模块试玩中发现的问题、希望调整的玩法、UI、手感或验证结果。"></textarea>
                    </label>
                    <div class="split-actions">
                      <button id="confirmMilestoneFeedback" class="secondary" data-global-action="true">提交反馈并修正模块</button>
                      <button id="closeMilestoneFeedbackModal" class="ghost" type="button">关闭</button>
                    </div>
                    <p id="milestoneFeedbackHint" class="muted"></p>
                  </section>
                </div>
              </div>
              <div id="gddQuestionFormModal" class="modal-backdrop hidden" role="dialog" aria-modal="true" aria-labelledby="gddQuestionFormTitle">
                <div class="modal-card modal-card-large">
                  <section class="stack">
                    <h2 id="gddQuestionFormTitle">创建策划大纲</h2>
                    <div id="gddQuestionFormMeta" class="card muted"></div>
                    <form id="gddQuestionForm" class="stack modal-scroll"></form>
                    <div class="split-actions">
                      <button id="confirmGddQuestionForm" class="secondary" type="button" data-global-action="true">确认并创建策划大纲</button>
                      <button id="cancelGddQuestionForm" class="ghost" type="button">取消</button>
                    </div>
                    <p id="gddQuestionFormHint" class="muted"></p>
                  </section>
                </div>
              </div>
              <main>
                <section id="sessionPanel" class="stack login-shell">
                  <h2>会话</h2>
                  <label>Access token <input id="token" type="password" autocomplete="off" placeholder="Paste the server-issued token"></label>
                  <button id="saveToken">验证并进入</button>
                  <p id="sessionStatus" class="muted">Token 只保存在当前浏览器 localStorage，不会写入仓库。</p>
                  <p id="sessionDiagnostics" class="muted"></p>
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
                    <p class="muted">CSV columns: key_name, api_key, description, valid_days. The api_key column is required for real per-user execution.</p>
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
                    <button id="validatePrototype" class="ghost" data-global-action="true">重新触发原型项目验收</button>
                    <button id="createProjectPackage" class="secondary" data-global-action="true" disabled>打包项目文件</button>
                    <button id="openProjectDownloads" class="ghost" disabled>打开项目文件下载页</button>
                    <button id="loadAssetInventory" class="ghost" disabled>查看项目素材库</button>
                    <div id="prototypeProgress" class="card muted">尚未开始游戏场景创建。</div>
                    <div id="prototypeAcceptanceSummary" class="card muted">原型完成后，这里会显示默认场景、验证摘要数量和建议试玩重点。</div>
                    <div id="projectHealthSummary" class="card muted">选择项目后显示项目健康摘要。</div>
                    <div id="projectPackageStatus" class="card muted">尚未生成项目压缩包。</div>
                    <div id="assetInventoryStatus" class="card muted">原型素材库会在项目可检查时显示。</div>
                  </section>
                  <section id="prototypeWorkflowPanel" class="stack">
                    <h2>游戏场景创建</h2>
                    <div id="prototypeGddStatus" class="card muted">正在读取当前项目 GDD。</div>
                    <div class="prototype-draft-row hidden">
                      <input id="draftFile" type="file" accept=".txt,text/plain" disabled>
                      <button id="importDraft" class="secondary import-draft-button" data-global-action="true" disabled></button>
                    </div>
                    <div id="draftImportStatus" class="card muted hidden"></div>
                    <div id="prototypeM1SpecStatus" class="card muted">创建策划大纲后显示 M1 游戏场景目标。</div>
                    <div class="hidden">
                      <label>游戏原型ID <input id="protoSlug" placeholder="demo-prototype"></label>
                      <label>原型假设 <textarea id="hypothesis" placeholder="这个原型要验证什么？"></textarea></label>
                      <label>核心玩家幻想 <textarea id="corePlayerFantasy" placeholder="玩家应该感受到什么？"></textarea></label>
                      <label>最小可玩循环 <textarea id="minimumPlayableLoop" placeholder="玩家反复执行的最小闭环是什么？"></textarea></label>
                      <label>成功标准，每行一条 <textarea id="successCriteria" placeholder="例如：30 秒内能理解目标"></textarea></label>
                      <label>游戏功能 <textarea id="gameFeature" placeholder="本次要实现或验证的核心功能"></textarea></label>
                      <label>核心玩法循环 <textarea id="coreGameplayLoop" placeholder="输入、反馈、奖励、升级或失败的循环"></textarea></label>
                      <label>胜利/失败条件 <textarea id="winFailConditions" placeholder="如何判定玩家成功或失败"></textarea></label>
                    </div>
                    <div class="split-actions">
                      <button id="runPrototype" class="secondary" data-global-action="true" disabled>确认 GDD 无误，执行 M1 游戏场景</button>
                      <button id="packagePrototypeSkeleton" class="ghost" data-global-action="true" disabled>打包下载项目</button>
                    </div>
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
                    <p class="muted">选择项目后即可聊天。后端会映射到服务器本机运行配置；需要执行工作流时仍使用上方固定按钮。</p>
                    <label>能力模式 <select id="chatSkillMode"><option value="normal">普通模式</option></select></label>
                    <div id="chatSkillDescription" class="card muted">普通模式：不激活 skills。</div>
                    <h2>主流程：游戏模块</h2>
                    <button id="createIterationPlan" class="ghost" data-global-action="true">生成游戏模块</button>
                    <button id="evaluateIterationPlan" class="ghost" data-global-action="true">评估当前游戏模块</button>
                    <button id="deleteIterationPlan" class="ghost" data-global-action="true">删除当前轮游戏模块</button>
                    <button id="executeIterationGoal" class="secondary" data-global-action="true">执行下一任务</button>
                    <p id="iterationAutoRefreshHint" class="muted">执行中会自动刷新进度，你可以停留在当前页面直接查看状态变化。</p>
                    <div id="iterationPlanStatus" class="card muted">尚未生成游戏模块。</div>
                    <div id="iterationPlanEvaluation" class="card muted">尚未评估当前游戏模块。</div>
                    <div id="iterationNeedsFixStatus" class="card muted">任务进入“需要修复”后，可在对应任务卡片里启动需要修复路由。</div>
                    <div id="iterationPlanGoals" class="card-list"></div>
                    <div id="gddMilestoneStepStatus" class="card muted">创建策划大纲后显示游戏模块。</div>
                    <div id="gddMilestoneStepActions" class="split-actions">
                      <button id="executeCurrentMilestoneStep" class="secondary" data-global-action="true" disabled>执行当前模块</button>
                      <button id="quickRepairCurrentMilestoneStep" class="ghost" data-global-action="true" disabled>快速修复</button>
                      <button id="confirmCurrentMilestoneStep" class="ghost" data-global-action="true" disabled>完成当前模块并激活下一模块</button>
                      <button id="submitCurrentMilestoneFeedback" class="ghost" data-global-action="true" disabled>提交反馈并修正模块</button>
                    </div>
                    <h2>异常修复计划</h2>
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
                    <button id="submitFormalFeedback" class="ghost" data-global-action="true">提交反馈到需要修复路由</button>
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
                const state = { projectId: "", projects: [], runs: [], packageList: null, assetInventory: null, assetInventoryExpanded: false, gddMilestoneSteps: null, gddMilestoneEvidence: {}, selectedGddMilestoneStepId: "", gddMilestoneManualSelection: false, chatHistory: [], chatAttachments: [], skillActions: [], authenticated: false, prototypeReadyForFeedback: false, activeRun: null, localBusy: false, chatBusy: false, workflowRouteBusy: false, nextSuggestedFeedback: "", draftAnalysisRunning: false, prototypeFailure: "", v2PrototypeStatus: "", v2PrototypeAcceptanceStatus: "", v2PrototypeCreationStatus: "", iterationPlan: null, iterationPlans: [], selectedIterationSessionId: "", iterationPlanEvaluation: null, iterationPlanFailure: "", iterationPlanUpdateMode: "update", iterationPlanEvaluationRunning: false, gddQuestionFormFields: [], gddQuestionFormSource: "", gddQuestionFormRequestToken: 0, gddQuestionFormAbortController: null, gddQuestionFormProgressTimer: null, gddQuestionFormProgressStartedAtMs: 0, gddQuestionFormCurrentSchemaSignature: "", gddQuestionFormDraftCache: new Map(), gddQuestionFormSchemaCache: new Map(), gddOutlineReady: false, workflowRouteActionToken: "", workflowRouteActionConsumed: false, projectAnalysisMode: false, prototypeSkeletonBannerExpanded: false, prototypeSkeletonBannerIndex: 0, prototypeSkeletonBannerTick: 0, prototypeSkeletonBannerRunId: "", prototypeSkeletonBannerDisplayedCount: 0, prototypeSkeletonBannerStartedAtMs: 0, pendingPrototypeSkeletonRun: null, prototypeSkeletonBannerStickyUntil: 0, cancelledActiveRunId: "", cancelledActiveRunProjectId: "" };
                let authEpoch = 0;
                let clientErrorRecoveryInstalled = false;
                let clientErrorRecoveryRefreshing = false;
                let startupSessionRestoreStarted = false;
                const prototypeInputIds = ["protoSlug", "hypothesis", "corePlayerFantasy", "minimumPlayableLoop", "successCriteria", "gameFeature", "coreGameplayLoop", "winFailConditions"];
                const projectStateCacheVersion = 2;
                const chatStorageVersion = "v2";
                const maxStoredChatMessages = 30;
                const gddQuestionFormMessageBudget = 5500;
                const gddQuestionFormSchemaCacheTtlMs = 24 * 60 * 60 * 1000;
                const gddQuestionFormFallbackCacheTtlMs = 5 * 60 * 1000;
                const gddQuestionFormSchemaTimeoutMs = 90 * 1000;
                const gddQuestionFormProgressDurationMs = 20 * 1000;
                const chatThinkingPrompts = [
                  "正在理解你的问题...",
                  "正在结合当前项目上下文...",
                  "正在生成回复...",
                  "正在整理可读答案...",
                  "还在处理中，请稍等..."
                ];
                const $ = id => document.getElementById(id);
                const out = value => $("output").textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
                function bumpAuthEpoch() {
                  authEpoch += 1;
                  return authEpoch;
                }
                function isCurrentAuthRequest(requestAuthEpoch) {
                  return requestAuthEpoch === authEpoch;
                }
                function projectRequestContext(projectId = state.projectId) {
                  return { projectId, authEpoch };
                }
                function isCurrentProjectContext(context) {
                  return !!context?.projectId && state.projectId === context.projectId && context.authEpoch === authEpoch;
                }
                function storedAccessToken() {
                  return localStorage.getItem("phaseAAccessToken") || readBrowserCookie("phaseAAccessToken") || localStorage.getItem("phaseAAdminToken") || "";
                }
                function rawTokenInput() {
                  return $("token").value.trim();
                }
                function token() {
                  const inputValue = rawTokenInput();
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
                  setModalVisible("gddQuestionFormModal", false);
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

                function showUserLoadingFallback(message = "正在读取项目列表...") {
                  $("sessionPanel").classList.add("hidden");
                  hideCreateProjectPage();
                  $("adminPanel").classList.remove("hidden");
                  $("accountAdminPanel").classList.add("hidden");
                  $("prototypeCommandPanel").classList.add("hidden");
                  $("runsPanel").classList.add("hidden");
                  $("outputPanel").classList.add("hidden");
                  $("projectDetailPanel").classList.add("hidden");
                  $("chatPanel").classList.add("hidden");
                  $("initStatusPanel").classList.remove("hidden");
                  $("initStatusText").textContent = message;
                }

                function recoverVisiblePageFromClientError(error) {
                  try {
                    console.error("Phase A UI error", error);
                  } catch {}
                  try {
                    const authenticated = !!state.authenticated || !!token();
                    if (!authenticated) {
                      showLoggedOut();
                      return;
                    }

                    const visibleProjects = listableProjects(Array.isArray(state.projects) ? state.projects : []);
                    const hasVisibleMainPanel = ["sessionPanel", "createProjectPanel", "adminPanel", "projectDetailPanel", "chatPanel"]
                      .some(id => {
                        const element = $(id);
                        return element && !element.classList.contains("hidden");
                      });
                    if (!hasVisibleMainPanel) {
                      if (visibleProjects.length > 0) {
                        showUserLoadingFallback("页面状态恢复中，请稍候...");
                        ensureProjectPageFallback(visibleProjects, false);
                      } else if (!clientErrorRecoveryRefreshing) {
                        clientErrorRecoveryRefreshing = true;
                        showUserLoadingFallback("页面状态恢复中，正在重新读取项目列表...");
                        void refreshProjects({ autoSelect: true })
                          .catch(() => showCreateProjectPage())
                          .finally(() => { clientErrorRecoveryRefreshing = false; });
                      } else {
                        showCreateProjectPage();
                      }
                    }
                  } catch {}
                }

                function installClientErrorRecovery() {
                  if (clientErrorRecoveryInstalled) return;
                  clientErrorRecoveryInstalled = true;
                  window.addEventListener("error", event => {
                    recordSessionProbe("window_error", {
                      message: String(event.message || "").slice(0, 500),
                      source: String(event.filename || "").slice(0, 300),
                      line: event.lineno || 0,
                      column: event.colno || 0,
                      error: sanitizeSessionProbeError(event.error)
                    });
                    recoverVisiblePageFromClientError(event.error || event.message);
                  });
                  window.addEventListener("unhandledrejection", event => {
                    recordSessionProbe("unhandled_rejection", { error: sanitizeSessionProbeError(event.reason) });
                    recoverVisiblePageFromClientError(event.reason);
                  });
                }

                function installSessionProbeEventListeners() {
                  window.phaseASessionProbeDump = () => sessionProbeDump("console_dump");
                  window.addEventListener("pageshow", event => {
                    recordSessionProbe("pageshow", { persisted: !!event.persisted });
                  });
                  document.addEventListener("visibilitychange", () => {
                    recordSessionProbe("visibilitychange", { visibilityState: document.visibilityState });
                  });
                  window.addEventListener("storage", event => {
                    if (event.key === "phaseAAccessToken" || event.key === "phaseAAdminToken") {
                      recordSessionProbe("storage_token_changed", { key: event.key, newLength: String(event.newValue || "").length });
                    }
                  });
                }

                installClientErrorRecovery();

                function ensureProjectPageFallback(projects, preferRemembered = true) {
                  const visibleProjects = listableProjects(Array.isArray(projects) ? projects : []);
                  if (visibleProjects.length > 0) {
                    selectDefaultProject(visibleProjects, preferRemembered);
                    return;
                  }
                  state.projectId = "";
                  writeSelectedProjectId("");
                  showCreateProjectPage();
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
                function clearAccessTokenStorage() {
                  localStorage.removeItem("phaseAAdminToken");
                  localStorage.removeItem("phaseAAccessToken");
                  clearBrowserCookie("phaseAAccessToken");
                }
                function persistAccessToken(value) {
                  if (!value) return false;
                  localStorage.setItem("phaseAAccessToken", value);
                  localStorage.removeItem("phaseAAdminToken");
                  writeBrowserCookie("phaseAAccessToken", value, 60 * 60 * 24 * 30);
                  return true;
                }
                function persistAccessTokenFromInput() {
                  return persistAccessToken(rawTokenInput());
                }
                function sessionProbeStorageKey() {
                  return "phaseASessionProbeLog";
                }
                function sanitizeSessionProbeError(error) {
                  if (!error) return null;
                  if (typeof error === "string") return { message: error.slice(0, 500) };
                  const payload = error.payload || {};
                  return {
                    name: String(error.name || "").slice(0, 120),
                    message: String(error.message || payload.message || payload.error || payload.status || "").slice(0, 500),
                    status: error.status || payload.statusCode || payload.status || null,
                    failureCode: payload.failureCode || payload.failure_code || payload.errorCode || "",
                    stack: String(error.stack || "").split("\n").slice(0, 4).join("\n")
                  };
                }
                function buildSessionProbeSnapshot(reason = "manual", extra = {}) {
                  const visiblePanels = ["sessionPanel", "createProjectPanel", "adminPanel", "projectDetailPanel", "chatPanel", "initStatusPanel"]
                    .filter(id => {
                      const element = $(id);
                      return element && !element.classList.contains("hidden");
                    });
                  const input = rawTokenInput();
                  const stored = localStorage.getItem("phaseAAccessToken") || "";
                  const cookie = readBrowserCookie("phaseAAccessToken") || "";
                  const legacy = localStorage.getItem("phaseAAdminToken") || "";
                  return {
                    timestamp: new Date().toISOString(),
                    reason,
                    href: location.href,
                    origin: location.origin,
                    visibilityState: document.visibilityState,
                    online: navigator.onLine,
                    authEpoch,
                    authenticated: !!state.authenticated,
                    role: state.role || "",
                    projectId: state.projectId || "",
                    activeRunId: state.activeRun?.runId || "",
                    tokenLengths: {
                      input: input.length,
                      stored: stored.length,
                      cookie: cookie.length,
                      legacy: legacy.length,
                      effective: Math.max(input.length, stored.length, cookie.length, legacy.length)
                    },
                    sessionStatus: $("sessionStatus")?.textContent || "",
                    visiblePanels,
                    extra
                  };
                }
                function recordSessionProbe(reason = "manual", extra = {}) {
                  try {
                    const entry = buildSessionProbeSnapshot(reason, extra);
                    const existing = JSON.parse(localStorage.getItem(sessionProbeStorageKey()) || "[]");
                    const entries = Array.isArray(existing) ? existing : [];
                    entries.push(entry);
                    localStorage.setItem(sessionProbeStorageKey(), JSON.stringify(entries.slice(-80)));
                    console.info("[phasea-session-probe]", entry);
                    return entry;
                  } catch (error) {
                    try { console.warn("[phasea-session-probe-failed]", error); } catch {}
                    return null;
                  }
                }
                function sessionProbeDump(reason = "manual_copy") {
                  let entries = [];
                  try {
                    const parsed = JSON.parse(localStorage.getItem(sessionProbeStorageKey()) || "[]");
                    entries = Array.isArray(parsed) ? parsed : [];
                  } catch {}
                  return {
                    copiedAt: new Date().toISOString(),
                    latest: buildSessionProbeSnapshot(reason),
                    entries
                  };
                }
                window.phaseASessionProbeDump = () => sessionProbeDump("console_dump");
                function updateSessionDiagnostics(reason = "") {
                  const element = $("sessionDiagnostics");
                  if (!element) return;
                  const stored = localStorage.getItem("phaseAAccessToken") || "";
                  const cookie = readBrowserCookie("phaseAAccessToken") || "";
                  const legacy = localStorage.getItem("phaseAAdminToken") || "";
                  const input = rawTokenInput();
                  element.textContent = `登录诊断：${location.origin} · ${reason || "ready"} · input=${input.length} · stored=${stored.length} · cookie=${cookie.length} · legacy=${legacy.length}`;
                  recordSessionProbe(reason || "session_diagnostics");
                }
                function persistTokenInputFromBrowser(reason = "input") {
                  const persisted = persistAccessTokenFromInput();
                  updateSessionDiagnostics(reason);
                  if (persisted && !state.authenticated) {
                    $("sessionStatus").textContent = "Token 已保留。点击验证并进入，或等待页面自动恢复登录。";
                  }
                }
                function scheduleAutofillTokenRecovery() {
                  [250, 1000, 2500].forEach(delayMs => {
                    window.setTimeout(() => {
                      const before = storedAccessToken();
                      if (rawTokenInput()) persistAccessTokenFromInput();
                      updateSessionDiagnostics(before ? `autofill_check_${delayMs}` : `autofill_empty_${delayMs}`);
                      if (!state.authenticated && token()) {
                        void refreshProjects({ autoSelect: true });
                      }
                    }, delayMs);
                  });
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
                  const goals = latestIterationPlanGoalsForAction();
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

                async function loadServerChatHistoryForProject(projectId, requestAuthEpoch = authEpoch) {
                  if (!projectId) return;
                  try {
                    const localWorkflowRouteEntries = state.chatHistory
                      .map((message, index) => ({ message, previousKey: previousStoredMessageKey(index), nextKey: nextStoredMessageKey(index) }))
                      .filter(entry => entry.message?.kind === "workflow-route");
                    const result = await api(`/api/projects/${projectId}/chat-history`);
                    if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
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
                    if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
                    renderChatHistory();
                  }
                }

                async function loadIterationPlan() {
                  const projectId = state.projectId;
                  const requestAuthEpoch = authEpoch;
                  if (!projectId) {
                    state.iterationPlan = null;
                    state.iterationPlans = [];
                    state.selectedIterationSessionId = "";
                    state.iterationPlanEvaluation = null;
                    renderIterationPlan();
                    return;
                  }
                  try {
                    const result = await api(`/api/projects/${projectId}/iteration-plans`);
                    if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
                    state.iterationPlans = normalizeIterationPlanRounds(Array.isArray(result?.rounds) ? result.rounds : []);
                    state.iterationPlan = selectIterationPlanForDisplay(state.iterationPlans);
                    state.iterationPlanEvaluation = state.iterationPlan?.latestEvaluation || null;
                    state.iterationPlanFailure = "";
                    syncIterationPlanRegenerationSuggestion();
                    writeProjectStateCache({ iterationPlan: state.iterationPlan, iterationPlans: state.iterationPlans, selectedIterationSessionId: state.selectedIterationSessionId, iterationPlanEvaluation: state.iterationPlanEvaluation, iterationPlanFailure: "" }, projectId);
                  } catch (error) {
                    if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
                    if (error?.status === 404) {
                      state.iterationPlan = null;
                      state.iterationPlans = [];
                      state.selectedIterationSessionId = "";
                      state.iterationPlanEvaluation = null;
                      state.iterationPlanFailure = "";
                      writeProjectStateCache({ iterationPlan: null, iterationPlans: [], selectedIterationSessionId: "", iterationPlanEvaluation: null, iterationPlanFailure: "" }, projectId);
                    } else {
                      showError(error);
                    }
                  }
                  renderIterationPlan();
                  if (isCurrentProjectRequest(projectId, requestAuthEpoch)) await loadProjectPackages();
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
                  const projectId = state.projectId;
                  const requestAuthEpoch = authEpoch;
                  if (!projectId) {
                    state.repairPlan = null;
                    renderRepairPlan();
                    return;
                  }
                  try {
                    const repairPlan = await api(`/api/projects/${projectId}/repair-plan/latest`);
                    if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
                    state.repairPlan = repairPlan;
                    writeProjectStateCache({ repairPlan: state.repairPlan }, projectId);
                  } catch (error) {
                    if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
                    if (error?.status === 404) {
                      state.repairPlan = null;
                      writeProjectStateCache({ repairPlan: null }, projectId);
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
                    <strong>${escapeHtml(publicStatusLabel(plan.status || "ready"))}</strong>
                    <p>${escapeHtml(plan.summary || "")}</p>
                    <p class="muted">修复计划 ID：${escapeHtml(plan.sessionId || "")}</p>
                  `;
                  $("createRepairPlan").disabled = isGlobalBusy();
                  $("executeRepairStep").disabled = !hasRunnable || isGlobalBusy();
                  $("executeRepairStep").textContent = hasRunnable ? "执行下一项修复" : "修复计划已无待执行步骤";
                  $("v2SkeletonAcceptance")?.classList.toggle("hidden", hasRunnable);
                  $("repairPlanGoals").innerHTML = goals.map(goal => `
                    <div class="card">
                      <strong>修复任务 ${String(goal.goalIndex || 0).padStart(2, "0")} · ${escapeHtml(publicGoalStatusLabel(goal.status))}</strong>
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
                  $("iterationNeedsFixStatus").textContent = "任务进入“需要修复”后，可在对应任务卡片里启动需要修复路由。";
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
                  const hasNeedsFix = goals.some(goal => v2IsRepairGoalStatus(goal.status));
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
                    <strong>${escapeHtml(publicStatusLabel(session.status || "ready"))}</strong>
                    ${state.iterationPlanFailure ? `<p class="danger">${escapeHtml(state.iterationPlanFailure)}</p>` : ""}
                    <p>${escapeHtml(session.overallGoal || "")}</p>
                    ${session.latestSummary ? `<p class="muted">${escapeHtml(session.latestSummary)}</p>` : ""}
                    <p class="muted">当前任务序号：${escapeHtml(String(session.currentGoalIndex || 0))}</p>
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
                    ? "运行需要修复路由"
                    : shouldRefinePlan
                      ? "建议先重拆游戏模块"
                      : hasPending
                        ? "执行下一任务"
                        : "当前没有待执行任务";
                  renderIterationPlanEvaluation();
                  $("iterationNeedsFixStatus").className = hasNeedsFix ? "card" : "card muted";
                  $("iterationNeedsFixStatus").textContent = hasNeedsFix
                    ? "当前有任务需要修复。点击对应任务卡片里的“运行需要修复路由”会直接提交后台 run。"
                    : "当前没有需要修复的任务。";
                  renderChatHistory();
                  const needsFixDisabled = !isLatestPlan || isGlobalBusy();
                  const needsFixTitle = !isLatestPlan
                    ? "只能修复最新一轮游戏模块。请切回最新轮次后再运行需要修复路由。"
                    : isGlobalBusy()
                      ? "有任务正在执行，请等待当前任务执行完毕。"
                      : "";
                  const needsFixDisabledAttrs = needsFixDisabled ? ` disabled title="${escapeHtml(needsFixTitle)}"` : "";
                  $("iterationPlanGoals").innerHTML = goals.map(goal => `
                    <div class="card">
                      <strong>任务 ${escapeHtml(String(goal.goalIndex))} · ${escapeHtml(publicGoalStatusLabel(goal.status))}</strong>
                      ${v2IsRepairGoalStatus(goal.status)
                        ? `<div class="v2-action-row"><button type="button" class="secondary" data-needs-fix-goal="${escapeHtml(String(goal.goalIndex || ""))}" onclick="event.stopPropagation(); runNeedsFixIterationGoal('${escapeHtml(String(goal.goalIndex || ""))}'); return false;"${needsFixDisabledAttrs}>运行需要修复路由</button></div>`
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
                      ? `该任务未通过。失败详情：${details}（路径和文件名已隐藏。）请点击需要修复路由继续修复。`
                      : "该任务未通过。失败详情不可展示，请点击需要修复路由继续修复，后台记录会保留完整证据。";
                  }
                  return sanitizePublicIterationPlanText(goal?.resultSummary || "");
                }

                function iterationPlanGoals(plan = state.iterationPlan) {
                  return Array.isArray(plan?.goals) ? plan.goals : [];
                }

                function latestIterationPlanForAction() {
                  return v2LatestIterationPlanForGlobalState();
                }

                function latestIterationPlanGoalsForAction() {
                  return iterationPlanGoals(latestIterationPlanForAction());
                }

                function selectLatestIterationPlanForAction() {
                  const plan = latestIterationPlanForAction();
                  if (!plan?.session) return plan;
                  if (state.iterationPlan?.session?.sessionId !== plan.session.sessionId) {
                    state.iterationPlan = plan;
                    state.selectedIterationSessionId = plan.session.sessionId || "";
                    state.iterationPlanEvaluation = plan.latestEvaluation || null;
                    writeProjectStateCache({ iterationPlan: state.iterationPlan, iterationPlans: state.iterationPlans, selectedIterationSessionId: state.selectedIterationSessionId, iterationPlanEvaluation: state.iterationPlanEvaluation, iterationPlanFailure: state.iterationPlanFailure || "" });
                    renderIterationPlan();
                  }
                  return plan;
                }

                function latestIterationPlanEvaluationForAction() {
                  const plan = latestIterationPlanForAction();
                  if (!plan?.session) return null;
                  if (plan.latestEvaluation) return plan.latestEvaluation;
                  return state.iterationPlan?.session?.sessionId === plan.session.sessionId
                    ? state.iterationPlanEvaluation
                    : null;
                }

                function hasAnyIterationPlan(plan = state.iterationPlan) {
                  return !!(plan?.session && iterationPlanGoals(plan).length);
                }

                function hasOpenIterationPlan(plan = state.iterationPlan) {
                  return iterationPlanGoals(plan).some(goal => ["pending", "needs_fix", "failed", "running"].includes(String(goal.status || "").trim().toLowerCase()));
                }

                function isIterationPlanComplete(plan = state.iterationPlan) {
                  const goals = iterationPlanGoals(plan);
                  return goals.length > 0 && goals.every(goal => ["completed", "succeeded"].includes(String(goal.status || "").trim().toLowerCase()));
                }

                function isIterationPlanStarted(plan = state.iterationPlan) {
                  const goals = iterationPlanGoals(plan);
                  const hasGoalRun = Array.isArray(plan?.goalRuns) && plan.goalRuns.length > 0;
                  const currentIndex = Number(plan?.session?.currentGoalIndex || 0);
                  return hasGoalRun || currentIndex > 0 || goals.some(goal => String(goal.status || "").trim().toLowerCase() !== "pending");
                }

                function currentNeedsFixRouteGoal(plan = state.iterationPlan) {
                  const goals = iterationPlanGoals(plan);
                  if (!goals.length) return null;
                  const byStatus = status => goals.find(goal => String(goal.status || "").trim().toLowerCase() === status);
                  const currentIndex = Number(plan?.session?.currentGoalIndex || 0);
                  const currentGoal = currentIndex > 0 ? goals.find(goal => Number(goal.goalIndex || 0) === currentIndex) : null;
                  const currentStatus = String(currentGoal?.status || "").trim().toLowerCase();
                  return byStatus("needs_fix")
                    || byStatus("failed")
                    || byStatus("running")
                    || (currentGoal && currentStatus !== "pending" && currentStatus !== "succeeded" ? currentGoal : null)
                    || null;
                }

                function latestNeedsFixRouteGoalForAction() {
                  return currentNeedsFixRouteGoal(latestIterationPlanForAction());
                }

                function buildNeedsFixFeedbackForUserReport(goal, userFeedback) {
                  const lines = [
                    goal
                      ? `用户提交了当前任务的报错/修复反馈，请通过 needs-fix 顶层路由处理任务 ${String(goal.goalIndex || "").trim()}：${String(goal.title || "").trim()}`
                      : "用户提交了报错/修复反馈，请通过 needs-fix 顶层路由处理。如果当前项目还没有可修复目标，请返回明确的前置条件提示，不要生成游戏模块。",
                    "",
                    "用户反馈：",
                    String(userFeedback || "").trim()
                  ];
                  if (goal?.resultSummary) {
                    lines.push("", "当前任务最近结果：", String(goal.resultSummary).trim());
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
                    ? "推荐先点击“重新生成游戏模块”，不要直接执行下一任务。"
                    : decision === "ready_to_execute"
                      ? "推荐直接执行下一任务；如果任务变化较大，再重新生成计划。"
                      : "推荐先处理当前阻塞项，再决定是否继续。";
                  $("iterationPlanEvaluation").className = "card";
                  const safeSummary = sanitizePublicIterationPlanText(evaluation.summary || "");
                  const safeSuggestedAction = sanitizePublicIterationPlanText(evaluation.suggestedAction || "");
                  const safeRegenerationPrompt = sanitizePublicIterationPlanText(evaluation.suggestedPromptForRegeneration || "");
                  $("iterationPlanEvaluation").innerHTML = `
                    <strong>${escapeHtml(publicDecisionLabel(evaluation.decision || "pending"))}</strong>
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
                    ? "输入第二轮或新一轮游戏模块任务目标。"
                    : "输入本次更新计划的补充要求；留空时会优先使用评估结果中的重拆建议。";
                  $("confirmIterationPlanUpdate").textContent = isNewPlan ? "创建新的游戏模块" : "更新游戏模块";
                  $("iterationPlanUpdateHint").textContent = isNewPlan
                    ? "将基于这里输入的新目标创建独立的新一轮计划，不会更新当前轮游戏模块。"
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
                  const actionPlan = mode === "new" ? latestIterationPlanForAction() : selectLatestIterationPlanForAction();
                  if (mode !== "new" && isIterationPlanStarted(actionPlan)) {
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
                  const actionEvaluation = latestIterationPlanEvaluationForAction();
                  const evaluationMessage = latestIterationPlanRegenerationPrompt()
                    || actionEvaluation?.suggestedAction
                    || actionEvaluation?.reason
                    || "";
                  const message = typedMessage || evaluationMessage || state.nextSuggestedFeedback || defaultNextSuggestedFeedback();
                  const sourceKind = mode === "new" ? "new_iteration_plan" : typedMessage ? "iteration_plan_update" : "completion_suggestion";
                  setModalVisible("iterationPlanUpdateModal", false);
                  await submitIterationPlanFromFeedback(message, mode === "new" ? "正在创建新的游戏模块..." : "正在更新游戏模块...", sourceKind);
                }

                async function createIterationPlan() {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("请先选择一个项目。");
                  const actionPlan = latestIterationPlanForAction();
                  if (hasAnyIterationPlan(actionPlan)) {
                    selectLatestIterationPlanForAction();
                    if (isIterationPlanComplete(actionPlan)) {
                      openIterationPlanUpdateModal("new");
                      return;
                    }
                    if (isIterationPlanStarted(actionPlan)) {
                      out("当前游戏模块已经开始执行，不允许更新游戏模块。");
                      return;
                    }
                    openIterationPlanUpdateModal("update");
                    return;
                  }
                  const typedMessage = $("chatMessage").value.trim();
                  const message = typedMessage || latestIterationPlanRegenerationPrompt() || state.nextSuggestedFeedback || defaultNextSuggestedFeedback();
                  const sourceKind = typedMessage ? "manual_feedback" : "completion_suggestion";
                  if (!typedMessage) {
                    out("未输入优化目标，已使用当前下一步建议生成游戏模块。");
                  }
                  await submitIterationPlanFromFeedback(message, "正在生成游戏模块...", sourceKind);
                }

                async function evaluateIterationPlan(announceInChat = false) {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("请先选择一个项目。");
                  const projectId = state.projectId;
                  const requestAuthEpoch = authEpoch;
                  const actionPlan = selectLatestIterationPlanForAction();
                  if (!actionPlan?.session) return out("请先生成游戏模块。");
                  const actionSessionId = actionPlan.session.sessionId || "";
                  state.iterationPlanEvaluationRunning = true;
                  applyGlobalBusyState("正在评估当前游戏模块，请等待当前评估完成。");
                  renderIterationPlan();
                  try {
                    const response = await api(`/api/projects/${projectId}/iteration-plan/evaluate`, {
                      method: "POST",
                      timeoutMs: longLlmTimeoutMs,
                      body: JSON.stringify({ model: $("globalModel").value || "gpt-5.5" })
                    });
                    if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
                    const evaluation = response?.evaluation || response;
                    await trackProjectRunFromResult(response, projectId, requestAuthEpoch);
                    const latestPlan = latestIterationPlanForAction();
                    if (actionSessionId && latestPlan?.session?.sessionId !== actionSessionId) return out("游戏模块已变化，本次评估结果已丢弃。");
                    if (latestPlan) {
                      latestPlan.latestEvaluation = evaluation;
                    }
                    if (state.iterationPlan?.session?.sessionId === latestPlan?.session?.sessionId) {
                      state.iterationPlanEvaluation = evaluation;
                    }
                    syncIterationPlanRegenerationSuggestion(evaluation);
                    renderIterationPlanEvaluation();
                    renderIterationPlan();
                    if (!announceInChat) {
                      out({
                        action: "iteration_plan_evaluated",
                        decision: evaluation?.decision || "",
                        summary: evaluation?.summary || "",
                        suggestedAction: evaluation?.suggestedAction || ""
                      });
                    }
                    out({
                      action: "iteration_plan_evaluated",
                      decision: evaluation?.decision || "",
                      summary: sanitizePublicIterationPlanText(evaluation?.summary || ""),
                      suggestedAction: sanitizePublicIterationPlanText(evaluation?.suggestedAction || "")
                    });
                  } catch (error) {
                    if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
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
                    applyGlobalBusyState();
                    if (isCurrentProjectRequest(projectId, requestAuthEpoch)) renderIterationPlan();
                    await refreshActiveRun();
                  }
                }

                async function submitIterationPlanFromFeedback(message, busyText, sourceKind = "manual_feedback") {
                  const context = projectRequestContext();
                  const projectId = context.projectId;
                  setLocalBusy(true, "正在生成游戏模块，请等待当前任务执行完毕。");
                  let shouldReloadIterationPlan = true;
                  try {
                    $("chatMessage").value = "";
                    const result = await api(`/api/projects/${projectId}/iteration-plan`, {
                      method: "POST",
                      timeoutMs: longLlmTimeoutMs,
                      body: JSON.stringify({ message, sourceKind, attachments: currentChatAttachmentsForRun(), model: $("globalModel").value || "gpt-5.5" })
                    });
                    if (!isCurrentProjectContext(context)) return null;
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
                    await trackProjectRunFromResult(result, projectId, context.authEpoch);
                    return result;
                  } catch (error) {
                    if (!isCurrentProjectContext(context)) return null;
                    showError(error);
                    shouldReloadIterationPlan = false;
                    return null;
                  } finally {
                    if (!isCurrentProjectContext(context)) return null;
                    try {
                      clearChatAttachments();
                      if (shouldReloadIterationPlan) {
                        await loadIterationPlan();
                      } else {
                        renderIterationPlan();
                      }
                      await loadProjectPackages();
                      await refreshActiveRun();
                    } finally {
                      setLocalBusy(false);
                    }
                  }
                }

                async function deleteIterationPlan() {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("请先选择一个项目。");
                  const context = projectRequestContext();
                  const projectId = context.projectId;
                  if (!hasAnyIterationPlan()) return out("当前没有可删除的游戏模块。");
                  if (isIterationPlanComplete()) return out("游戏模块已经全部完成，不可以删除。");
                  const sessionId = state.iterationPlan?.session?.sessionId || state.selectedIterationSessionId || "";
                  const roundIndex = state.iterationPlan?.roundIndex || "";
                  if (!sessionId) return out("当前没有选中的游戏模块轮次。");
                  const roundLabel = roundIndex ? `第 ${roundIndex} 轮` : "当前轮";
                  if (!confirm(`确定要删除${roundLabel}游戏模块吗？该操作不会删除其他轮次。`)) return;
                  setLocalBusy(true, `正在删除${roundLabel}游戏模块...`);
                  try {
                    const result = await api(`/api/projects/${projectId}/iteration-plans/${encodeURIComponent(sessionId)}`, { method: "DELETE" });
                    if (!isCurrentProjectContext(context)) return;
                    state.iterationPlan = null;
                    state.selectedIterationSessionId = "";
                    state.iterationPlanEvaluation = null;
                    state.iterationPlanFailure = "";
                    renderIterationPlan();
                    out(result.summary || `${roundLabel}游戏模块已删除。`);
                    await loadIterationPlan();
                  } catch (error) {
                    if (!isCurrentProjectContext(context)) return;
                    showError(error);
                  } finally {
                    if (!isCurrentProjectContext(context)) return;
                    try {
                      await loadProjectPackages();
                      await refreshActiveRun();
                    } finally {
                      setLocalBusy(false);
                    }
                  }
                }

                async function executeIterationGoal() {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("请先选择一个项目。");
                  const context = projectRequestContext();
                  const projectId = context.projectId;
                  const actionPlan = selectLatestIterationPlanForAction();
                  if (!actionPlan?.session) return out("请先生成游戏模块。");
                  const needsFixGoal = currentNeedsFixRouteGoal(actionPlan);
                  if (needsFixGoal) {
                    await runNeedsFixIterationGoal(needsFixGoal.goalIndex);
                    return;
                  }
                  const evaluationDecision = latestIterationPlanDecision();
                  if (evaluationDecision === "should_refine_plan") return out("当前评估建议先重拆游戏模块，已停止执行旧目标。");
                  if (evaluationDecision === "llm_failed") return out("当前游戏模块评估失败，请先修复评估调用并重新评估计划。");
                  if (evaluationDecision === "blocked_by_current_goal") return out("当前评估显示已有任务阻塞，请先处理当前阻塞项。");
                  setLocalBusy(true, "正在执行下一任务，请等待当前任务执行完毕。");
                  try {
                    const result = await api(`/api/projects/${projectId}/iteration-plan/execute-next`, {
                      method: "POST"
                    });
                    if (!isCurrentProjectContext(context)) return;
                    await loadServerChatHistoryForProject(projectId, context.authEpoch);
                    if (!isCurrentProjectContext(context)) return;
                    out(result);
                    await trackProjectRunFromResult(result, projectId, context.authEpoch);
                  } catch (error) {
                    if (!isCurrentProjectContext(context)) return;
                    await loadServerChatHistoryForProject(projectId, context.authEpoch);
                    showError(error);
                  } finally {
                    if (!isCurrentProjectContext(context)) return;
                    try {
                      await loadIterationPlan();
                      await loadRuns();
                      await loadProjectPackages();
                      await refreshActiveRun();
                    } finally {
                      setLocalBusy(false);
                    }
                  }
                }

                async function createRepairPlan() {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("请先选择一个项目。");
                  const context = projectRequestContext();
                  const projectId = context.projectId;
                  setLocalBusy(true, "正在生成修复计划，请等待当前任务执行完毕。");
                  try {
                    const result = await api(`/api/projects/${projectId}/repair-plan`, { method: "POST" });
                    if (!isCurrentProjectContext(context)) return;
                    state.repairPlan = result;
                    renderRepairPlan();
                    focusRepairPlanPanel();
                    out(result);
                  } catch (error) {
                    if (!isCurrentProjectContext(context)) return;
                    showError(error);
                  } finally {
                    if (!isCurrentProjectContext(context)) return;
                    try {
                      await loadRepairPlan();
                      await refreshActiveRun();
                    } finally {
                      setLocalBusy(false);
                    }
                  }
                }

                async function executeRepairStep() {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("请先选择一个项目。");
                  if (!state.repairPlan?.sessionId) return out("请先生成修复计划。");
                  const context = projectRequestContext();
                  const projectId = context.projectId;
                  setLocalBusy(true, "正在执行下一项修复，请等待当前任务执行完毕。");
                  try {
                    const result = await api(`/api/projects/${projectId}/repair-plan/execute-next`, {
                      method: "POST",
                      body: JSON.stringify({ model: $("globalModel").value })
                    });
                    if (!isCurrentProjectContext(context)) return;
                    await loadServerChatHistoryForProject(projectId, context.authEpoch);
                    if (!isCurrentProjectContext(context)) return;
                    out(result);
                    await trackProjectRunFromResult(result, projectId, context.authEpoch);
                  } catch (error) {
                    if (!isCurrentProjectContext(context)) return;
                    await loadServerChatHistoryForProject(projectId, context.authEpoch);
                    showError(error);
                  } finally {
                    if (!isCurrentProjectContext(context)) return;
                    try {
                      await loadRepairPlan();
                      await loadRuns();
                      await refreshActiveRun();
                    } finally {
                      setLocalBusy(false);
                    }
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
                    .replace(/(?:本轮目标：|本轮任务：|Direction lock:|方向锁定：|Project README:|Project Execution Guide:|Recovery source consumed:|已读取恢复来源：|Current goal:|当前任务：|Previous platform rejection:|上一轮平台拒绝：|Task repair ledger:|任务修复台账：|User feedback:|用户反馈：|Scope rule:|范围规则：)[\s\S]*$/gi, "")
                    .replace(/(?<![\w])[A-Za-z]:[\\/][^\s`'"，。；：、）)]+/g, "[路径已隐藏]")
                    .replace(/\bres:\/\/[^\s`'"，。；：、）)<]+/gi, "[路径已隐藏]")
                    .replace(/\/(?:gdd-outline|assets|downloads|runs|projects|admin|api|account)(?:\/[^\s`'"，。；：、）)<]*)?(?:\?[^\s`'"，。；：、）)<]*)?/gi, "")
                    .replace(/\b(?:projectId|runId|accountId|ticket|embedded)=[^\s`'"，。；：、）)<]+/gi, "")
                    .replace(/(?<![\w.:/])\/(?:[A-Za-z0-9._-]+\/)+[A-Za-z0-9._-]+/g, "[路径已隐藏]")
                    .replace(/(?<![\w])(?:[A-Za-z0-9_.-]+[\\/]){1,}[A-Za-z0-9_.-]+/g, "[路径已隐藏]")
                    .replace(/(?<![\w.-])[\w.-]+\.(?:ps1|cmd|bat|sh|py|cs|csproj|sln|json|toml|yaml|yml|md|log|txt|tscn|tres|res|gd|png|jpg|jpeg|webp|svg|ogg|wav|mp3|ttf|otf|import|dll|exe|pdb|cache|sqlite|sqlite3|db|zip)(?::\d+(?::\d+)?)?(?![\w.-])/gi, "[文件已隐藏]")
                    .replace(/^\s*(?:&\s*)?(?:(?:dotnet\s+(?:test|run|build|publish|restore))|(?:py(?:thon)?\s+[-\w.\/\\])|(?:powershell(?:\.exe)?\s+[-/]\w+)|(?:cmd(?:\.exe)?\s+\/[ck])|(?:codex(?:\.cmd)?\s+(?:exec|run|review|--|-))|(?:caddy(?:\.exe)?\s+(?:run|reload|fmt|--|-))|(?:git\s+\w+)|(?:rg\s+.+)|(?:node\s+.+)|(?:npm\s+\w+))[^\r\n]*/gim, "")
                    .replace(/\bBMAD\b/gi, "")
                    .replace(/\bCodex(?:[\s_-]+CLI)?\b/gi, "生成流程")
                    .replace(/\bcodex[\s_-]*cli\b/gi, "generation")
                    .replace(/\bcodex\b/gi, "generation")
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

                function sanitizePublicRunContent(value) {
                  return sanitizePublicChatContent(value || "");
                }

                function publicArtifactLabel(value) {
                  const raw = String(value || "");
                  if (raw.includes("prompt")) return "输入记录";
                  if (raw.includes("result") || raw.includes("output") || raw.includes("codex")) return "生成结果";
                  if (raw.includes("gdd") || raw.includes("outline")) return "策划文档";
                  if (raw.includes("package") || raw.includes("zip")) return "项目文件包";
                  return sanitizePublicRunContent(raw) || "产物";
                }

                function publicErrorCode(value) {
                  const sanitized = sanitizePublicChatContent(value || "");
                  return sanitized || "unknown_error";
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
                  state.chatBusy = false;
                  state.workflowRouteBusy = false;
                  state.iterationPlan = null;
                  clearChatAttachments();
                  invalidateWorkflowRouteAction();
                  closeUserModals();
                  setUserTopActionsVisible(false);
                  $("sessionPanel").classList.remove("hidden");
                  hideCreateProjectPage();
                  $("adminPanel").classList.add("hidden");
                  $("accountAdminPanel").classList.add("hidden");
                  $("prototypeCommandPanel").classList.add("hidden");
                  $("chatPanel").classList.add("hidden");
                  state.nextSuggestedFeedback = "";
                  state.prototypeSkeletonBannerExpanded = false;
                  state.prototypeSkeletonBannerIndex = 0;
                  state.prototypeSkeletonBannerTick = 0;
                  applyGlobalBusyState();
                  updateSessionDiagnostics("logged_out");
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
                  updateSessionDiagnostics("authenticated");
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

                function isCurrentProjectRequest(projectId, requestAuthEpoch = authEpoch) {
                  return !!projectId && state.projectId === projectId && requestAuthEpoch === authEpoch;
                }

                function runProjectId(run) {
                  return String(run?.projectId || "").trim();
                }

                function runBelongsToCurrentProject(run) {
                  const projectId = runProjectId(run);
                  return !projectId || (!!state.projectId && projectId === state.projectId);
                }

                function currentProjectHasBusyRun() {
                  return runIsBusy(state.activeRun) && !isInlineOnlyRun(state.activeRun) && runBelongsToCurrentProject(state.activeRun);
                }

                function projectSwitchLocked() {
                  return !!state.localBusy ||
                    !!state.chatBusy ||
                    !!state.workflowRouteBusy ||
                    !!state.iterationPlanEvaluationRunning ||
                    currentProjectHasBusyRun() ||
                    hasPendingPrototypeSkeletonBannerRun();
                }

                function updateProjectSwitchAvailability() {
                  const locked = projectSwitchLocked();
                  document.querySelectorAll("[data-v2-left-project], [data-project]").forEach(button => {
                    button.disabled = locked && !!state.projectId;
                    button.title = button.disabled ? "当前操作完成前不能切换项目。" : "";
                  });
                  ["openProjectListModal", "refreshProjects"].forEach(id => {
                    const button = $(id);
                    if (!button) return;
                    setButtonDisabledState(button, locked && !!state.projectId, "当前操作完成前不能切换项目。");
                  });
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

                function writeProjectStateCache(patch = {}, projectId = state.projectId) {
                  if (!projectId) return;
                  const previous = readProjectStateCache(projectId) || { projectId };
                  const next = { ...previous, ...patch, projectId, updatedAt: new Date().toISOString() };
                  try { localStorage.setItem(projectStateCacheKey(projectId), JSON.stringify(next)); } catch {}
                }

                function applyProjectStateCache(projectId) {
                  let cached = null;
                  try {
                    cached = readProjectStateCache(projectId);
                  } catch {
                    cached = null;
                  }
                  if (!cached) return;
                  if (Array.isArray(cached.runs)) {
                    try {
                      state.runs = cached.runs;
                      renderRunsListFromState(cached.projectHealth || null);
                      renderFeedbackRecords();
                    } catch {}
                  }
                  if (cached.latestPrototypeDraft) {
                    try {
                      applyDraftToForm(cached.latestPrototypeDraft);
                      renderDraftImportStatus(cached.latestPrototypeDraft);
                    } catch {}
                  }
                  if (cached.prototypeProgress) {
                    try {
                      const progress = cached.prototypeProgress;
                      const acceptanceStatus = String(progress?.acceptanceStatus || progress?.status || "").trim().toLowerCase();
                      state.prototypeFailure = acceptanceStatus === "failed" ? (progress.acceptanceFailure || progress.failure || "") : "";
                      renderPrototypeProgress(progress);
                      renderPrototypeAcceptanceSummary(progress);
                      const creationStatus = String(progress?.prototypeCreationStatus || progress?.status || "").trim().toLowerCase();
                      const suppressLockedState = ((!!state.cancelledActiveRunId && state.cancelledActiveRunProjectId === projectId) || !!readCancelledPrototypeMarker(projectId)) && ["queued", "running"].includes(creationStatus);
                      setPrototypeFormLocked(suppressLockedState ? false : isPrototypeCreationLocked(progress));
                      if (creationStatus === "idle" && progress?.step === "cancelled" && $("draftFile")) {
                        $("draftFile").disabled = true;
                      }
                      updateChatPanelVisibility(progress);
                    } catch {}
                  }
                  if (cached.packageList) {
                    try {
                      state.packageList = cached.packageList;
                      renderProjectPackages(cached.packageList);
                    } catch {}
                  }
                  if (cached.assetInventory) {
                    try {
                      state.assetInventory = cached.assetInventory;
                      renderAssetInventory(cached.assetInventory, state.assetInventoryExpanded);
                    } catch {}
                  }
                  if (cached.iterationPlan !== undefined) {
                    try {
                      state.iterationPlans = normalizeIterationPlanRounds(Array.isArray(cached.iterationPlans) ? cached.iterationPlans : []);
                      state.selectedIterationSessionId = cached.selectedIterationSessionId || "";
                      state.iterationPlan = cached.iterationPlan;
                      if (state.iterationPlans.length) {
                        state.iterationPlan = selectIterationPlanForDisplay(state.iterationPlans);
                      }
                      state.iterationPlanEvaluation = cached.iterationPlan?.latestEvaluation || cached.iterationPlanEvaluation || null;
                      state.iterationPlanFailure = cached.iterationPlanFailure || "";
                      renderIterationPlan();
                    } catch {}
                  }
                  if (cached.repairPlan !== undefined) {
                    try {
                      state.repairPlan = cached.repairPlan;
                      renderRepairPlan();
                    } catch {}
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
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("请先选择一个项目。");
                  const context = projectRequestContext();
                  const projectId = context.projectId;
                  const message = $("chatMessage").value.trim();
                  if (!message) return out("请输入消息。");
                  state.chatBusy = true;
                  applyGlobalBusyState("正在等待聊天回复，请等待当前任务执行完毕。");
                  $("sendChat").disabled = true;
                  $("sendChat").textContent = "发送中...";
                  let shouldClearChatAttachments = false;
                  try {
                    let routeIntent = null;
                    if (state.projectAnalysisMode) {
                      try {
                        routeIntent = await api(`/api/projects/${projectId}/workflow-route/intent`, {
                          method: "POST",
                          timeoutMs: 90 * 1000,
                          body: JSON.stringify({ message, model: $("globalModel").value || null })
                        });
                        if (!isCurrentProjectContext(context)) return;
                      } catch {
                        routeIntent = null;
                      }
                    }
                    if (routeIntent?.shouldRoute) {
                      state.chatHistory.push({ role: "user", content: message });
                      renderChatHistory();
                      saveChatHistoryForProject();
                      $("chatMessage").value = "";
                      await queryWorkflowRoute(routeIntent, projectId, true, context.authEpoch);
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
                    const result = await api(`/api/projects/${projectId}/chat`, { method: "POST", body: JSON.stringify(payload) });
                    if (!isCurrentProjectContext(context)) return;
                    if (result.assistantMessage) {
                      thinking.complete(result.assistantMessage);
                    } else {
                      thinking.complete("本次没有生成回复。");
                    }
                    await loadServerChatHistoryForProject(projectId);
                    out(result);
                    await loadRuns();
                  } catch (error) {
                    if (!isCurrentProjectContext(context)) return;
                    const message = publicErrorCode(error?.payload?.failureCode || error?.payload?.error || "unknown_error");
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
                    if (!isCurrentProjectContext(context)) return;
                    state.chatBusy = false;
                    applyGlobalBusyState();
                    if (shouldClearChatAttachments) clearChatAttachments();
                    $("sendChat").disabled = false;
                    $("sendChat").textContent = "发送";
                    await refreshActiveRun();
                  }
                }

                async function refreshGddOutlineStatus() {
                  const projectId = state.projectId;
                  const requestAuthEpoch = authEpoch;
                  if (!projectId || !$("createGddDocument")) return;
                  try {
                    const outlineStatus = await api(`/api/projects/${projectId}/gdd/outline`);
                    if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
                    state.gddOutlineReady = Array.isArray(outlineStatus?.sections) && outlineStatus.sections.length > 0;
                  } catch {
                    if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
                    state.gddOutlineReady = false;
                  }
                  writeProjectStateCache({ gddOutlineReady: state.gddOutlineReady }, projectId);
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

                function currentProjectSnapshot(projectId = state.projectId) {
                  return (state.projects || []).find(project => project.projectId === projectId) || null;
                }

                function currentProjectGameTypeText() {
                  const project = currentProjectSnapshot();
                  return [
                    project?.gameTypeSource,
                    project?.templateRuleId,
                    project?.gameName,
                    project?.name
                  ].filter(Boolean).join(" ");
                }

                function fallbackGddQuestionFormFields() {
                  const project = currentProjectSnapshot();
                  const gameTypeText = currentProjectGameTypeText();
                  const normalized = gameTypeText.toLowerCase();
                  const isRpg = /rpg|role|jrpg|crpg|arpg|diablo|dungeon/.test(normalized);
                  const isDeckbuilder = /deck|card|牌|卡/.test(normalized);
                  const isSurvivorslike = /survivor|arena|吸血鬼|割草|幸存/.test(normalized);
                  const isTowerDefense = /tower|defen|塔防/.test(normalized);

                  const fields = [
                    { id: "reference_signal", label: "参考游戏或体验标杆", placeholder: "例如参考对象、想保留的体验、明确不想要的方向。", rows: 2, required: true },
                    { id: "player_fantasy", label: "玩家核心幻想", placeholder: "玩家在 1 分钟内应该感到自己在做什么、变强什么、承担什么风险。", rows: 3, required: true },
                    { id: "core_loop", label: "核心循环", placeholder: "进入场景、做选择、获得反馈、成长或失败、再次尝试的循环。", rows: 3, required: true },
                    { id: "first_scene", label: "首个可玩场景", placeholder: "首个场景里要出现的地图、对象、敌人、目标、交互或事件。", rows: 3, required: true },
                    { id: "controls_camera", label: "操作、视角与基础手感", placeholder: "移动、点击、键鼠输入、镜头、节奏、碰撞或命中反馈。", rows: 3 },
                    { id: "challenge_fail", label: "主要挑战与失败条件", placeholder: "玩家如何受压、如何犯错、失败或损失如何发生。", rows: 3 },
                    { id: "progression_reward", label: "成长、奖励与解锁", placeholder: "局内/局外成长、资源、装备、技能、卡牌、关卡或剧情推进。", rows: 3 },
                    { id: "ui_feedback", label: "UI/HUD 与玩家反馈", placeholder: "必须显示的状态、提示、数值、按钮、战斗/交互反馈。", rows: 3 },
                    { id: "scope_boundaries", label: "首版范围边界", placeholder: "本次 GDD 和首个原型必须做什么，明确不做什么。", rows: 3 },
                    { id: "acceptance", label: "验收标准", placeholder: "怎样判断 GDD 和第一个可玩版本是成功的。", rows: 3 }
                  ];

                  if (isRpg) {
                    fields[3] = { id: "rpg_scene", label: "首个可探索区域", placeholder: "区域布局、NPC/敌人、事件、入口出口、互动对象。", rows: 3, required: true };
                    fields[5] = { id: "rpg_conflict", label: "战斗/冲突/遭遇", placeholder: "遇敌方式、回合或即时规则、角色能力、胜负反馈。", rows: 3 };
                    fields[6] = { id: "rpg_growth", label: "角色成长与叙事推进", placeholder: "等级、装备、技能、任务、剧情或队伍状态如何推进。", rows: 3 };
                  } else if (isDeckbuilder) {
                    fields[2] = { id: "deck_loop", label: "牌局核心循环", placeholder: "抽牌、出牌、资源、敌方回合、结算、奖励和下一场。", rows: 3, required: true };
                    fields[5] = { id: "deck_pressure", label: "敌人压力与失败条件", placeholder: "敌人意图、伤害、状态、倒计时或资源枯竭。", rows: 3 };
                    fields[6] = { id: "deck_growth", label: "卡组构筑与奖励", placeholder: "新增卡、删卡、升级、遗物、货币、路线选择。", rows: 3 };
                  } else if (isSurvivorslike) {
                    fields[2] = { id: "survivors_loop", label: "单局战斗循环", placeholder: "移动、自动/手动攻击、拾取、升级、敌潮、坚持或撤离。", rows: 3, required: true };
                    fields[5] = { id: "survivors_pressure", label: "敌潮、精英与生存压力", placeholder: "敌人类型、刷怪节奏、危险升级、失败原因。", rows: 3 };
                    fields[6] = { id: "survivors_build", label: "升级、构筑与局外成长", placeholder: "局内升级选择、武器组合、被动、局外解锁。", rows: 3 };
                  } else if (isTowerDefense) {
                    fields[2] = { id: "tower_loop", label: "波次防守循环", placeholder: "布防、出怪、战斗、结算、升级、下一波。", rows: 3, required: true };
                    fields[3] = { id: "tower_map", label: "首张防守地图", placeholder: "路径、入口出口、建造点、阻挡、目标生命或基地。", rows: 3, required: true };
                    fields[6] = { id: "tower_economy", label: "塔、敌人与经济", placeholder: "塔类型、升级、费用、敌人护甲/速度/特殊能力、收益。", rows: 3 };
                  }

                  if (project?.gameName) {
                    fields[0].placeholder = `${project.gameName} 的参考对象、体验目标和禁忌方向。`;
                  }

                  return fields;
                }

                function normalizeGddQuestionFormFields(fields) {
                  if (!Array.isArray(fields)) return [];
                  const usedIds = new Set();
                  return fields.map(field => {
                    const label = String(field?.label || "").trim().slice(0, 32);
                    const id = String(field?.id || label || "")
                      .trim()
                      .toLowerCase()
                      .replace(/[^a-z0-9]+/g, "_")
                      .replace(/^_+|_+$/g, "");
                    if (!id || !label || usedIds.has(id)) return null;
                    usedIds.add(id);
                    const rawRows = Number(field?.rows || 3);
                    const rawMaxLength = Number(field?.maxLength || 500);
                    const rows = Math.min(4, Math.max(2, Number.isFinite(rawRows) ? rawRows : 3));
                    const maxLength = Math.min(700, Math.max(120, Number.isFinite(rawMaxLength) ? rawMaxLength : 500));
                    return {
                      id,
                      label,
                      placeholder: String(field?.placeholder || "").trim().slice(0, 120),
                      inputType: "textarea",
                      rows,
                      maxLength,
                      required: field?.required === true
                    };
                  }).filter(Boolean).slice(0, 12);
                }

                function setGddQuestionFormLoading() {
                  state.gddQuestionFormFields = [];
                  state.gddQuestionFormSource = "";
                  $("gddQuestionForm").dataset.schema = "question-form";
                  $("gddQuestionForm").innerHTML = `
                    <div class="gdd-question-loading">
                      <p class="muted">正在根据当前游戏类型规划问题，请稍候。</p>
                      <div class="gdd-question-progress" role="progressbar" aria-label="策划问题准备进度" aria-valuemin="0" aria-valuemax="99" aria-valuenow="0">
                        <div id="gddQuestionFormProgressBar" class="gdd-question-progress-bar"></div>
                      </div>
                      <div id="gddQuestionFormProgressValue" class="gdd-question-progress-value">0%</div>
                    </div>`;
                  $("gddQuestionFormMeta").textContent = "正在准备策划大纲问题";
                  $("gddQuestionFormHint").textContent = "";
                  $("confirmGddQuestionForm").disabled = true;
                  startGddQuestionFormProgress();
                }

                function updateGddQuestionFormProgress(percent) {
                  const safePercent = Math.min(99, Math.max(0, Math.floor(Number(percent) || 0)));
                  const progress = document.querySelector(".gdd-question-progress");
                  const bar = $("gddQuestionFormProgressBar");
                  const value = $("gddQuestionFormProgressValue");
                  if (progress) progress.setAttribute("aria-valuenow", String(safePercent));
                  if (bar) bar.style.width = `${safePercent}%`;
                  if (value) value.textContent = `${safePercent}%`;
                }

                function startGddQuestionFormProgress() {
                  stopGddQuestionFormProgress();
                  state.gddQuestionFormProgressStartedAtMs = Date.now();
                  updateGddQuestionFormProgress(0);
                  state.gddQuestionFormProgressTimer = setInterval(() => {
                    const elapsedMs = Date.now() - state.gddQuestionFormProgressStartedAtMs;
                    updateGddQuestionFormProgress((elapsedMs / gddQuestionFormProgressDurationMs) * 99);
                  }, 100);
                }

                function stopGddQuestionFormProgress() {
                  if (state.gddQuestionFormProgressTimer) {
                    clearInterval(state.gddQuestionFormProgressTimer);
                    state.gddQuestionFormProgressTimer = null;
                  }
                  state.gddQuestionFormProgressStartedAtMs = 0;
                }

                function gddQuestionFormCacheKey(projectId = state.projectId) {
                  const project = currentProjectSnapshot(projectId);
                  return [
                    projectId || "",
                    project?.gameTypeSource || "",
                    project?.templateRuleId || "",
                    project?.gameName || "",
                    $("globalModel")?.value || ""
                  ].join("|");
                }

                function readGddQuestionFormSchemaCache(cacheKey) {
                  const cached = state.gddQuestionFormSchemaCache.get(cacheKey);
                  if (!cached || cached.expiresAt <= Date.now()) {
                    state.gddQuestionFormSchemaCache.delete(cacheKey);
                    return null;
                  }
                  return cached.schema;
                }

                function writeGddQuestionFormSchemaCache(cacheKey, schema, ttlMs = gddQuestionFormSchemaCacheTtlMs) {
                  state.gddQuestionFormSchemaCache.set(cacheKey, {
                    schema,
                    expiresAt: Date.now() + ttlMs
                  });
                }

                function gddQuestionFormSchemaSignature(fields) {
                  return JSON.stringify((fields || []).map(field => [
                    field.id,
                    field.label,
                    field.placeholder || "",
                    field.rows || 3,
                    field.maxLength || 500,
                    !!field.required
                  ]));
                }

                function saveGddQuestionFormDraft() {
                  if (!state.gddQuestionFormFields.length || !state.gddQuestionFormCurrentSchemaSignature) return;
                  const values = {};
                  state.gddQuestionFormFields.forEach(field => {
                    values[field.id] = (document.querySelector(`[data-gdd-question-input="${field.id}"]`)?.value || "").trim();
                  });
                  state.gddQuestionFormDraftCache.set(gddQuestionFormCacheKey(), {
                    signature: state.gddQuestionFormCurrentSchemaSignature,
                    values
                  });
                }

                function readGddQuestionFormDraft(signature) {
                  const draft = state.gddQuestionFormDraftCache.get(gddQuestionFormCacheKey());
                  if (!draft || draft.signature !== signature) return null;
                  return draft.values || null;
                }

                function clearGddQuestionFormDraft() {
                  state.gddQuestionFormDraftCache.delete(gddQuestionFormCacheKey());
                  state.gddQuestionFormCurrentSchemaSignature = "";
                }

                function isGddQuestionFormModalOpen() {
                  return !$("gddQuestionFormModal").classList.contains("hidden");
                }

                function isCurrentGddQuestionFormRequest(requestToken, projectId) {
                  return requestToken === state.gddQuestionFormRequestToken &&
                    state.projectId === projectId &&
                    isGddQuestionFormModalOpen();
                }

                async function loadGddQuestionFormSchema(projectId, requestToken, signal) {
                  const cacheKey = gddQuestionFormCacheKey(projectId);
                  try {
                    const result = await api(`/api/projects/${projectId}/gdd/question-form`, {
                      method: "POST",
                      timeoutMs: gddQuestionFormSchemaTimeoutMs,
                      signal,
                      body: JSON.stringify({ model: $("globalModel").value || null })
                    });
                    if (!isCurrentGddQuestionFormRequest(requestToken, projectId)) return null;
                    const fields = normalizeGddQuestionFormFields(result?.fields);
                    const requiredFieldCount = fields.filter(field => field.required).length;
                    if (fields.length >= 8 && fields.length <= 12 && requiredFieldCount >= 4 && requiredFieldCount <= 6) {
                      const schema = { fields, source: result?.source || "agent", failureCode: result?.failureCode || "" };
                      writeGddQuestionFormSchemaCache(cacheKey, schema);
                      return schema;
                    }
                    const fallbackSchema = { fields: normalizeGddQuestionFormFields(fallbackGddQuestionFormFields()), source: "fallback", failureCode: "invalid_schema" };
                    writeGddQuestionFormSchemaCache(cacheKey, fallbackSchema, gddQuestionFormFallbackCacheTtlMs);
                    return fallbackSchema;
                  } catch (error) {
                    if (error?.status === 401 || error?.status === 403 || error?.status === 404) throw error;
                    if (!isCurrentGddQuestionFormRequest(requestToken, projectId)) return null;
                    const fallbackSchema = { fields: normalizeGddQuestionFormFields(fallbackGddQuestionFormFields()), source: "fallback", failureCode: error?.payload?.failureCode || error?.payload?.error || "schema_request_failed" };
                    writeGddQuestionFormSchemaCache(cacheKey, fallbackSchema, gddQuestionFormFallbackCacheTtlMs);
                    return fallbackSchema;
                  }
                }

                function renderGddQuestionForm(schema) {
                  stopGddQuestionFormProgress();
                  const project = currentProjectSnapshot();
                  const fields = normalizeGddQuestionFormFields(schema?.fields);
                  const gameType = currentProjectGameTypeText() || "未指定游戏类型";
                  const requiredFieldCount = fields.filter(field => field.required).length;
                  state.gddQuestionFormFields = fields.length >= 8 && fields.length <= 12 && requiredFieldCount >= 4 && requiredFieldCount <= 6 ? fields : normalizeGddQuestionFormFields(fallbackGddQuestionFormFields());
                  state.gddQuestionFormSource = schema?.source || "fallback";
                  state.gddQuestionFormCurrentSchemaSignature = gddQuestionFormSchemaSignature(state.gddQuestionFormFields);
                  const draftValues = readGddQuestionFormDraft(state.gddQuestionFormCurrentSchemaSignature);
                  $("gddQuestionForm").dataset.schema = "question-form";
                  $("gddQuestionForm").innerHTML = state.gddQuestionFormFields.map(field => `
                    <label data-gdd-question="${escapeHtml(field.id)}">${escapeHtml(field.label)}${field.required ? " *" : ""}
                      <textarea data-gdd-question-input="${escapeHtml(field.id)}" rows="${field.rows || 3}" maxlength="${field.maxLength || 500}" ${field.required ? "required aria-required=\"true\"" : ""}>${escapeHtml(draftValues?.[field.id] ?? field.placeholder ?? "")}</textarea>
                    </label>
                  `).join("");
                  $("gddQuestionFormMeta").textContent = `${project?.gameName || project?.name || "当前项目"} · ${gameType}`;
                  $("gddQuestionFormHint").textContent = state.gddQuestionFormSource === "agent"
                    ? "请补充关键原始资料。"
                    : "已使用保底问题，请补充关键原始资料。";
                  $("confirmGddQuestionForm").disabled = false;
                }

                async function openGddQuestionFormModal() {
                  if (!state.projectId) return out("请先选择一个项目。");
                  if (state.gddOutlineReady) {
                    callV2("v2OpenGddOutlineTab");
                    return;
                  }
                  if (!guardGlobalAction()) return;
                  const projectId = state.projectId;
                  state.gddQuestionFormRequestToken += 1;
                  const requestToken = state.gddQuestionFormRequestToken;
                  if (state.gddQuestionFormAbortController) state.gddQuestionFormAbortController.abort();
                  const abortController = new AbortController();
                  state.gddQuestionFormAbortController = abortController;
                  const button = $("createGddDocument");
                  const cacheKey = gddQuestionFormCacheKey(projectId);
                  const cachedSchema = readGddQuestionFormSchemaCache(cacheKey);
                  if (cachedSchema) {
                    renderGddQuestionForm(cachedSchema);
                    setModalVisible("gddQuestionFormModal", true);
                    state.gddQuestionFormAbortController = null;
                    return;
                  }
                  button.disabled = true;
                  button.textContent = "规划中...";
                  setGddQuestionFormLoading();
                  setModalVisible("gddQuestionFormModal", true);
                  try {
                    if (!currentProjectSnapshot()) {
                      await refreshProjects({ autoSelect: false }).catch(() => {});
                    }
                    if (!isCurrentGddQuestionFormRequest(requestToken, projectId)) return;
                    const schema = await loadGddQuestionFormSchema(projectId, requestToken, abortController.signal);
                    if (!schema || !isCurrentGddQuestionFormRequest(requestToken, projectId)) return;
                    renderGddQuestionForm(schema);
                  } catch (error) {
                    if (!isCurrentGddQuestionFormRequest(requestToken, projectId)) return;
                    closeGddQuestionFormModal({ preserveDraft: false });
                    out(error?.payload?.error || error?.payload?.failureCode || "策划大纲问题加载失败，请刷新项目后重试。");
                    showError(error);
                  } finally {
                    if (state.gddQuestionFormAbortController === abortController) {
                      state.gddQuestionFormAbortController = null;
                    }
                    if (requestToken === state.gddQuestionFormRequestToken && !state.localBusy) {
                      button.disabled = false;
                      button.textContent = state.gddOutlineReady ? "\u67e5\u9605\u7b56\u5212\u5927\u7eb2" : "\u521b\u5efa\u7b56\u5212\u5927\u7eb2";
                    }
                  }
                }

                function closeGddQuestionFormModal(options = {}) {
                  state.gddQuestionFormRequestToken += 1;
                  if (options?.preserveDraft !== false) {
                    saveGddQuestionFormDraft();
                  }
                  stopGddQuestionFormProgress();
                  if (state.gddQuestionFormAbortController) {
                    state.gddQuestionFormAbortController.abort();
                    state.gddQuestionFormAbortController = null;
                  }
                  setModalVisible("gddQuestionFormModal", false);
                  $("gddQuestionFormHint").textContent = "";
                  $("confirmGddQuestionForm").disabled = false;
                  if (!state.localBusy && $("createGddDocument")) {
                    $("createGddDocument").disabled = false;
                    $("createGddDocument").textContent = state.gddOutlineReady ? "\u67e5\u9605\u7b56\u5212\u5927\u7eb2" : "\u521b\u5efa\u7b56\u5212\u5927\u7eb2";
                  }
                }

                function collectGddQuestionFormAnswers() {
                  const fields = state.gddQuestionFormFields.length ? state.gddQuestionFormFields : normalizeGddQuestionFormFields(fallbackGddQuestionFormFields());
                  return fields.map(field => ({
                    id: field.id,
                    label: field.label,
                    required: !!field.required,
                    answer: (document.querySelector(`[data-gdd-question-input="${field.id}"]`)?.value || "").trim()
                  }));
                }

                function buildGddQuestionFormMessage(message, answers) {
                  const project = currentProjectSnapshot();
                  const lines = [
                    "GDD question-form raw material:",
                    `Project: ${project?.gameName || project?.name || state.projectId}`,
                    `Game type: ${currentProjectGameTypeText() || "unspecified"}`,
                    `Question form source: ${state.gddQuestionFormSource || "fallback"}`,
                    ""
                  ];
                  const trimmedMessage = (message || "").trim();
                  if (trimmedMessage) {
                    lines.push("User freeform note:", trimmedMessage, "");
                  }
                  lines.push("Question-form answers:");
                  answers.forEach((item, index) => {
                    lines.push(`${index + 1}. ${item.label}: ${item.answer || "未填写"}`);
                  });
                  lines.push("", "Use these answers as authoritative raw material for creating the GDD outline. Preserve the existing GDD route design and validation rules.");
                  return lines.join("\n");
                }

                async function confirmGddQuestionForm() {
                  const answers = collectGddQuestionFormAnswers();
                  const answeredCount = answers.filter(item => item.answer).length;
                  const missingRequired = answers.filter(item => item.required && !item.answer);
                  if (missingRequired.length > 0) {
                    $("gddQuestionFormHint").textContent = `请先填写必填问题：${missingRequired.slice(0, 3).map(item => item.label).join("、")}。`;
                    document.querySelector(`[data-gdd-question-input="${missingRequired[0].id}"]`)?.focus();
                    return;
                  }
                  if (answeredCount < 4) {
                    $("gddQuestionFormHint").textContent = "请至少填写 4 个关键问题。";
                    return;
                  }
                  const message = buildGddQuestionFormMessage($("chatMessage").value, answers);
                  if (message.length > gddQuestionFormMessageBudget) {
                    $("gddQuestionFormHint").textContent = `当前原始资料约 ${message.length} 字，超过 ${gddQuestionFormMessageBudget} 字预算，请缩短后再创建。`;
                    return;
                  }
                  const button = $("confirmGddQuestionForm");
                  button.disabled = true;
                  button.textContent = "创建中...";
                  try {
                    const succeeded = await startGddDocumentRoute(message);
                    if (succeeded) {
                      clearGddQuestionFormDraft();
                      closeGddQuestionFormModal({ preserveDraft: false });
                    }
                  } finally {
                    button.disabled = false;
                    button.textContent = "确认并创建策划大纲";
                  }
                }

                async function createGddDocument() {
                  await openGddQuestionFormModal();
                }

                function scheduleGddPostSuccessRefreshes(projectId, context) {
                  void (async () => {
                    try {
                      await loadServerChatHistoryForProject(projectId, context.authEpoch);
                      if (!isCurrentProjectContext(context)) return;
                      await Promise.allSettled([
                        loadRuns(),
                        loadProjectPackages()
                      ]);
                    } catch {
                      // Success cleanup must not depend on best-effort UI refreshes.
                    }
                  })();
                }

                function scheduleGddPostFailureRefresh(projectId, context) {
                  void (async () => {
                    try {
                      await loadServerChatHistoryForProject(projectId, context.authEpoch);
                    } catch {
                      // Failure cleanup must not depend on best-effort UI refreshes.
                    }
                  })();
                }

                async function startGddDocumentRoute(message) {
                  if (!state.projectId) {
                    out("请先选择一个项目。");
                    return false;
                  }
                  if (!guardGlobalAction()) return false;
                  const context = projectRequestContext();
                  const projectId = context.projectId;
                  const button = $("createGddDocument");
                  let succeeded = false;
                  setLocalBusy(true, "\u6b63\u5728\u521b\u5efa\u7b56\u5212\u5927\u7eb2\uff0c\u8bf7\u7b49\u5f85\u5f53\u524d\u4efb\u52a1\u6267\u884c\u5b8c\u6bd5\u3002");
                  button.disabled = true;
                  button.textContent = "创建中...";
                  try {
                    const payload = {
                      message,
                      model: $("globalModel").value || null,
                      attachments: currentChatAttachmentsForRun()
                    };
                    const result = await api(`/api/projects/${projectId}/gdd`, { method: "POST", body: JSON.stringify(payload) });
                    if (!isCurrentProjectContext(context)) return false;
                    succeeded = true;
                    state.gddOutlineReady = true;
                    button.textContent = "\u67e5\u9605\u7b56\u5212\u5927\u7eb2";
                    const resultSummary = result.summary || "\u7b56\u5212\u5927\u7eb2\u5df2\u521b\u5efa\u3002";
                    out(resultSummary);
                    state.chatHistory.push({
                      role: "assistant",
                      kind: "gdd-result",
                      content: resultSummary,
                      gddOutlineUrl: result.downloadUrl || ""
                    });
                    renderChatHistory();
                    saveChatHistoryForProject();
                    scheduleGddPostSuccessRefreshes(projectId, context);
                    return true;
                  } catch (error) {
                    if (!isCurrentProjectContext(context)) return false;
                    if ((error?.payload?.failureCode || error?.payload?.error) === "gdd_already_exists") {
                      state.gddOutlineReady = true;
                      button.textContent = "\u67e5\u9605\u7b56\u5212\u5927\u7eb2";
                      out(error?.payload?.summary || "\u7b56\u5212\u5927\u7eb2\u5df2\u5b58\u5728\u3002");
                      if (typeof closeGddQuestionFormModal === "function") closeGddQuestionFormModal();
                      callV2("v2OpenGddOutlineTab");
                      return false;
                    }
                    const failureMessage = sanitizePublicChatContent(error?.payload?.summary || error?.payload?.error || error?.payload?.failureCode || "\u521b\u5efa\u7b56\u5212\u5927\u7eb2\u5931\u8d25\u3002");
                    state.chatHistory.push({
                      role: "assistant",
                      kind: "gdd-result",
                      content: failureMessage
                    });
                    renderChatHistory();
                    saveChatHistoryForProject();
                    out(failureMessage);
                    scheduleGddPostFailureRefresh(projectId, context);
                    showError(error);
                    return false;
                  } finally {
                    if (!isCurrentProjectContext(context)) return;
                    if (succeeded) clearChatAttachments();
                    if (succeeded && $("chatMessage")) $("chatMessage").value = "";
                    void refreshActiveRun();
                    setLocalBusy(false);
                    button.disabled = false;
                    button.textContent = state.gddOutlineReady ? "\u67e5\u9605\u7b56\u5212\u5927\u7eb2" : "\u521b\u5efa\u7b56\u5212\u5927\u7eb2";
                  }
                }

                function chatHistoryDownloadFileName(projectId = state.projectId) {
                  const project = state.projects.find(item => item.projectId === projectId);
                  const base = (project?.name || project?.gameName || projectId || "chat-history")
                    .replace(/[^\p{L}\p{N}._-]+/gu, "-")
                    .replace(/^-+|-+$/g, "") || "chat-history";
                  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
                  return `${base}-chat-history-${stamp}.json`;
                }

                async function downloadChatHistory() {
                  if (!state.projectId) return out("请先选择一个项目。");
                  const projectId = state.projectId;
                  const requestAuthEpoch = authEpoch;
                  const button = $("downloadChatHistory");
                  const originalText = button.textContent;
                  button.disabled = true;
                  button.textContent = "下载中...";
                  try {
                    const result = await api(`/api/projects/${projectId}/chat-history`);
                    if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return out("项目或登录状态已切换，本次聊天记录下载已取消。");
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
                      projectId,
                      exportedAt: new Date().toISOString(),
                      messageCount: messages.length,
                      messages
                    };
                    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json;charset=utf-8" });
                    const url = URL.createObjectURL(blob);
                    const anchor = document.createElement("a");
                    anchor.href = url;
                    anchor.download = chatHistoryDownloadFileName(projectId);
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
                  const context = projectRequestContext();
                  const button = $("syncChatHistory");
                  const originalText = button.textContent;
                  button.disabled = true;
                  button.textContent = "同步中...";
                  try {
                    await loadServerChatHistoryForProject(context.projectId, context.authEpoch);
                    if (!isCurrentProjectContext(context)) return;
                    out("服务器聊天记录已同步。");
                  } catch (error) {
                    if (!isCurrentProjectContext(context)) return;
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
                    try {
                      await refreshActiveRun();
                    } finally {
                      setLocalBusy(false);
                      $("createUserAccount").disabled = false;
                      $("createUserAccount").textContent = "Create user token";
                    }
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
                  if (!$("llmGatewayBaseUrl") || !$("llmExternalAccountRef") || !$("llmTokenRef")) return;
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
                  if (!$("llmGatewayBaseUrl") || !$("llmExternalAccountRef") || !$("llmTokenRef") || !$("saveLlmBinding")) return;
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
                    $("llmBindingStatus").textContent = publicErrorCode(error?.payload?.failureCode || error?.payload?.error || "llm_binding_failed");
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
                  if (!callV2("v2HasPrototypeSkeleton")) return out("请先运行并完成游戏场景创建，再提交正式反馈。自由对话仍可使用。");
                  const feedback = $("chatMessage").value.trim();
                  const goal = latestNeedsFixRouteGoalForAction();
                  if (!feedback && !goal) return out("\u8bf7\u8f93\u5165\u8981\u6b63\u5f0f\u63d0\u4ea4\u7684\u53cd\u9988\u3002");
                  if (goal) selectLatestIterationPlanForAction();
                  await submitNeedsFixRouteRequest({
                    feedback: feedback ? buildNeedsFixFeedbackForUserReport(goal, feedback) : buildNeedsFixFeedbackForGoal(goal),
                    goalId: goal?.goalId || null,
                    goalIndex: goal?.goalIndex || null
                  }, goal ? `需要修复路由执行中，任务 ${String(goal.goalIndex || "")}...` : "需要修复路由执行中...");
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
                  const actionPlan = latestIterationPlanForAction();
                  const actionGoals = iterationPlanGoals(actionPlan);
                  const hasPendingPlan = !!actionPlan?.session && actionGoals.some(goal => goal.status === "pending");
                  if (suggestion === "__iteration_plan_evaluate__") {
                    await evaluateIterationPlan(true);
                    return;
                  }
                  if (suggestion === "__iteration_plan_execute_next__") {
                    if (!hasPendingPlan) return out("当前没有可继续执行的任务。");
                    await executeIterationGoal();
                    return;
                  }
                  if (hasPendingPlan && latestIterationPlanDecision() === "should_refine_plan") {
                    if (isIterationPlanStarted(actionPlan)) return out("当前游戏模块已经开始执行，不允许更新游戏模块。");
                    selectLatestIterationPlanForAction();
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
                  if (!state.prototypeReadyForFeedback) return out("请先运行并完成游戏场景创建，再提交正式反馈。自由对话仍可使用。");
                  const context = projectRequestContext();
                  const projectId = context.projectId;
                  setLocalBusy(true);
                  $("submitFormalFeedback").disabled = true;
                  $("submitFormalFeedback").textContent = busyText || "\u6b63\u5f0f\u63d0\u4ea4\u4e2d...";
                  try {
                    $("chatMessage").value = "";
                    const result = await api(`/api/projects/${projectId}/prototype-feedback-iterations`, {
                      method: "POST",
                      body: JSON.stringify({ feedback, model: $("globalModel").value, skillActionId: $("chatSkillMode").value || "normal" })
                    });
                    if (!isCurrentProjectContext(context)) return;
                    out(result);
                    await trackProjectRunFromResult(result, projectId, context.authEpoch);
                    await loadRuns();
                    updateContinueSuggestionFromText(result.assistantMessage);
                  } catch (error) {
                    if (!isCurrentProjectContext(context)) return;
                    const message = sanitizePublicChatContent(error?.payload?.assistantMessage || error?.payload?.error || "本轮正式反馈处理失败。");
                    out(message);
                    showError(error);
                  }
                  finally {
                    if (!isCurrentProjectContext(context)) return;
                    try {
                      await loadProjectPackages();
                      await refreshActiveRun();
                    } finally {
                      setLocalBusy(false);
                      setFormalFeedbackAvailability(state.prototypeReadyForFeedback);
                    }
                  }
                }

                function buildNeedsFixFeedbackForGoal(goal) {
                  if (!goal) return "";
                  const parts = [
                    `请通过需要修复路由处理当前迭代任务 ${String(goal.goalIndex || "").trim()}：${String(goal.title || "").trim()}`,
                    String(goal.description || "").trim(),
                    goal.acceptanceHint ? `本步验收提示：${String(goal.acceptanceHint || "").trim()}` : "",
                    "要求：由系统判断当前任务是否适合短修；只围绕当前任务本身处理，不要推进后续任务。"
                  ].filter(Boolean);
                  return parts.join("\n");
                }

                async function runNeedsFixIterationGoal(goalIndex) {
                  $("iterationNeedsFixStatus").className = "card muted";
                  $("iterationNeedsFixStatus").textContent = `正在准备提交任务 ${String(goalIndex || "").trim()} 的需要修复路由...`;
                  if (!isDisplayingLatestIterationPlan()) {
                    const message = "只能修复最新一轮游戏模块。请切回最新轮次后再运行需要修复路由。";
                    $("iterationNeedsFixStatus").className = "card muted";
                    $("iterationNeedsFixStatus").textContent = message;
                    return out(message);
                  }
                  await refreshActiveRun();
                  if (isGlobalBusy()) {
                    $("iterationNeedsFixStatus").className = "card muted";
                    $("iterationNeedsFixStatus").textContent = "当前有任务正在执行，请等待当前 run 完成后再启动需要修复路由。";
                    return out("当前有任务正在执行，请等待当前 run 完成后再启动需要修复路由。");
                  }
                  const goals = Array.isArray(state.iterationPlan?.goals) ? state.iterationPlan.goals : [];
                  const goal = goals.find(item => String(item.goalIndex) === String(goalIndex));
                  if (!goal) {
                    $("iterationNeedsFixStatus").className = "card";
                    $("iterationNeedsFixStatus").textContent = "未找到需要修复处理的任务，请刷新游戏模块后再试。";
                    return out("未找到需要修复处理的任务。");
                  }
                  const feedback = buildNeedsFixFeedbackForGoal(goal);
                  if (!feedback) {
                    $("iterationNeedsFixStatus").className = "card";
                    $("iterationNeedsFixStatus").textContent = "当前任务缺少可用于需要修复路由的内容。";
                    return out("当前任务缺少可用于需要修复路由的内容。");
                  }
                  await submitNeedsFixRouteRequest({
                    feedback,
                    goalId: goal.goalId || "",
                    goalIndex: Number(goal.goalIndex || 0)
                  }, `需要修复路由执行中，任务 ${String(goal.goalIndex)}...`);
                }

                async function submitNeedsFixRouteRequest(payload, busyText) {
                  if (!state.projectId) return out("\u8bf7\u5148\u9009\u62e9\u4e00\u4e2a\u9879\u76ee\u3002");
                  if (isGlobalBusy()) {
                    $("iterationNeedsFixStatus").className = "card muted";
                    $("iterationNeedsFixStatus").textContent = "当前有任务正在执行，请等待当前 run 完成后再启动需要修复路由。";
                    return out("当前有任务正在执行，请等待当前 run 完成后再启动需要修复路由。");
                  }
                  const context = projectRequestContext();
                  const projectId = context.projectId;
                  setLocalBusy(true);
                  $("iterationNeedsFixStatus").className = "card muted";
                  $("iterationNeedsFixStatus").textContent = busyText || "需要修复路由已提交，正在等待后台 run 创建。";
                  $("submitFormalFeedback").disabled = true;
                  try {
                    const feedback = String(payload?.feedback || "").trim();
                    $("chatMessage").value = "";
                    const result = await api(`/api/projects/${projectId}/needs-fix-route`, {
                      method: "POST",
                      body: JSON.stringify({
                        feedback,
                        model: $("globalModel").value,
                        skillActionId: $("chatSkillMode").value || "normal",
                        goalId: payload?.goalId || null,
                        goalIndex: payload?.goalIndex || null
                      })
                    });
                    if (!isCurrentProjectContext(context)) return;
                    const routeStatus = String(result.status || "").trim().toLowerCase();
                    const goalStatus = String(result.iterationGoalStatus || "").trim().toLowerCase();
                    const needsMoreFix = goalStatus === "needs_fix" || goalStatus === "failed" || routeStatus === "needs_fix" || routeStatus === "failed";
                    out(result);
                    await trackProjectRunFromResult(result, projectId, context.authEpoch);
                    $("iterationNeedsFixStatus").className = needsMoreFix ? "card" : "card muted";
                    $("iterationNeedsFixStatus").textContent = result.summary || (needsMoreFix ? "需要修复路由已执行，但当前任务仍需继续修复。" : "需要修复路由已完成。");
                    await loadRuns();
                    await loadIterationPlan();
                  } catch (error) {
                    if (!isCurrentProjectContext(context)) return;
                    const message = sanitizePublicChatContent(error?.payload?.summary || error?.payload?.error || "Needs fix route failed.");
                    $("iterationNeedsFixStatus").className = "card";
                    $("iterationNeedsFixStatus").textContent = message;
                    out(message);
                    showError(error);
                  }
                  finally {
                    if (!isCurrentProjectContext(context)) return;
                    try {
                      await refreshActiveRun();
                    } finally {
                      setLocalBusy(false);
                      setFormalFeedbackAvailability(state.prototypeReadyForFeedback);
                    }
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
                  const { timeoutMs, signal: externalSignal, ...fetchOptions } = options;
                  const shouldProbeApi = path === "/api/session" || path === "/api/projects";
                  if (shouldProbeApi) {
                    recordSessionProbe("api_start", { path, method: fetchOptions.method || "GET", timeoutMs: timeoutMs || 0 });
                  }
                  const controller = (timeoutMs || externalSignal) ? new AbortController() : null;
                  const timeoutHandle = timeoutMs ? setTimeout(() => controller.abort(), timeoutMs) : null;
                  let externalAbortHandler = null;
                  if (externalSignal && controller) {
                    if (externalSignal.aborted) {
                      controller.abort();
                    } else {
                      externalAbortHandler = () => controller.abort();
                      externalSignal.addEventListener("abort", externalAbortHandler, { once: true });
                    }
                  }
                  let response;
                  try {
                    response = await fetch(path, {
                      ...fetchOptions,
                      cache: fetchOptions.cache || "no-store",
                      signal: controller?.signal,
                      headers: { ...headers(), ...(options.headers || {}) }
                    });
                  } catch (error) {
                    if (shouldProbeApi) {
                      recordSessionProbe("api_fetch_error", { path, error: sanitizeSessionProbeError(error) });
                    }
                    if (error?.name === "AbortError") {
                      throw { status: 408, payload: { status: "client_timeout", failureCode: "client_timeout", timeoutMs } };
                    }
                    throw error;
                  } finally {
                    if (timeoutHandle) clearTimeout(timeoutHandle);
                    if (externalSignal && externalAbortHandler) externalSignal.removeEventListener("abort", externalAbortHandler);
                  }
                  const text = await response.text();
                  let payload = {};
                  try { payload = text ? JSON.parse(text) : {}; } catch { payload = { raw: text }; }
                  if (!response.ok) {
                    if (shouldProbeApi) {
                      recordSessionProbe("api_response_error", {
                        path,
                        status: response.status,
                        payloadStatus: payload.status || "",
                        failureCode: payload.failureCode || payload.failure_code || ""
                      });
                    }
                    throw { status: response.status, payload };
                  }
                  if (shouldProbeApi) {
                    recordSessionProbe("api_success", { path, status: response.status });
                  }
                  return payload;
                }

                async function refreshProjects(options = {}) {
                  const autoSelect = options.autoSelect !== false;
                  const requestAuthEpoch = authEpoch;
                  let sessionValidated = false;
                  recordSessionProbe("refreshProjects_start", {
                    autoSelect,
                    retryOnAuthFailure: options.retryOnAuthFailure !== false,
                    requestAuthEpoch
                  });
                  try {
                    const session = await api("/api/session");
                    if (!isCurrentAuthRequest(requestAuthEpoch)) return;
                    sessionValidated = true;
                    recordSessionProbe("refreshProjects_session_validated", { role: session.role || "user", requestAuthEpoch });
                    showAdminShell(session.role || "user");
                    if ((session.role || "user") === "admin") {
                      state.projects = [];
                      closeUserModals();
                      out("Admin project creation and project list are disabled. Use Account Admin on the right.");
                      return;
                    }
                    showUserLoadingFallback();

                    const projects = await api("/api/projects");
                    if (!isCurrentAuthRequest(requestAuthEpoch)) return;
                    state.projects = projects;
                    const initializing = hasInitializingProject(projects);
                    $("initStatusPanel").classList.toggle("hidden", !initializing);
                    if (initializing) {
                      $("initStatusText").textContent = "\u9879\u76ee\u521d\u59cb\u5316\u914d\u7f6e\u4e2d...\u521d\u59cb\u5316\u5b8c\u6210\u540e\u4f1a\u81ea\u52a8\u8fdb\u5165\u9879\u76ee\u8be6\u60c5\u9875\u3002";
                    }

                    const visibleProjects = listableProjects(projects);
                    const latestFailure = visibleProjects.length === 0 && !initializing ? await loadLatestProjectCreationFailure() : null;
                    if (!isCurrentAuthRequest(requestAuthEpoch)) return;
                    const sortedVisibleProjects = visibleProjects
                      .slice()
                      .sort((a, b) => (projectTimestamp(b) || 0) - (projectTimestamp(a) || 0) || String(b.projectId || "").localeCompare(String(a.projectId || "")));
                    $("projects").innerHTML = sortedVisibleProjects.map(p => `
                      <div class="card">
                        <button class="ghost ${p.projectId === state.projectId ? "current" : ""}" data-project="${p.projectId}">
                        <strong>${escapeHtml(p.name)}</strong>
                        <span class="muted">${escapeHtml(p.gameName)} · ${escapeHtml(p.templateRuleId)} · ${escapeHtml(p.bootstrapStatus)}</span>
                        ${p.bootstrapStatus === "failed" ? `<span class="danger">初始化失败：${escapeHtml(sanitizePublicFailureContent(p.bootstrapError || "未知错误"))}</span>` : ""}
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
                    updateProjectSwitchAvailability();
                    callV2("v2RenderLeftProjectList");
                    if (projectSwitchLocked() && state.projectId) {
                      out(projects);
                      return;
                    }
                    const currentProjectVisible = !!state.projectId && visibleProjects.some(project => project.projectId === state.projectId);
                    if (visibleProjects.length === 0 && latestFailure) {
                      showCreationFailure(latestFailure.failureError);
                    } else if (initializing && !state.projectId) {
                      showInitialization("running", "");
                    } else if (visibleProjects.length === 0) {
                      state.projectId = "";
                      writeSelectedProjectId("");
                      showCreateProjectPage();
                    } else if (state.projectId && !currentProjectVisible) {
                      state.projectId = "";
                      writeSelectedProjectId("");
                      selectDefaultProject(visibleProjects);
                    } else if (!state.projectId && autoSelect) {
                      selectDefaultProject(visibleProjects);
                    }
                    out(projects);
                    recordSessionProbe("refreshProjects_success", {
                      projectCount: Array.isArray(projects) ? projects.length : 0,
                      visibleProjectCount: visibleProjects.length,
                      initializing
                    });
                  } catch (error) {
                    if (!isCurrentAuthRequest(requestAuthEpoch)) return;
                    recordSessionProbe("refreshProjects_error", {
                      sessionValidated,
                      retryOnAuthFailure: options.retryOnAuthFailure !== false,
                      error: sanitizeSessionProbeError(error)
                    });
                    if (!sessionValidated) {
                      if (token() && options.retryOnAuthFailure !== false && (!error?.status || error.status >= 500)) {
                        $("sessionStatus").textContent = "Token 已保留。登录状态恢复失败，正在重试...";
                        showUserLoadingFallback("正在恢复登录状态，请稍候...");
                        window.setTimeout(() => {
                          if (!state.authenticated && token() && isCurrentAuthRequest(requestAuthEpoch)) {
                            void refreshProjects({ ...options, retryOnAuthFailure: false });
                          }
                        }, 1000);
                        return;
                      }
                      showLoggedOut();
                    } else {
                      $("sessionStatus").textContent = "Token 已验证。项目状态刷新失败，请稍后重试。";
                      ensureProjectPageFallback(state.projects, false);
                    }
                    showError(error);
                  }
                }

                function restoreSessionFromStoredToken() {
                  const currentToken = token();
                  recordSessionProbe("restoreSessionFromStoredToken_start", { hasToken: !!currentToken });
                  if (!currentToken) {
                    showLoggedOut();
                    return;
                  }

                  persistAccessToken(currentToken);
                  updateSessionDiagnostics("restore_stored_token");
                  $("sessionStatus").textContent = "Token 已读取，正在恢复登录...";
                  showUserLoadingFallback("正在恢复登录状态，请稍候...");
                  void refreshProjects({ autoSelect: true });
                }

                function runStartupSessionRestore() {
                  if (startupSessionRestoreStarted) return;
                  startupSessionRestoreStarted = true;
                  setTokenFromStorage();
                  installSessionProbeEventListeners();
                  recordSessionProbe("startup_before_restore");
                  restoreSessionFromStoredToken();
                  scheduleAutofillTokenRecovery();
                }

                function runStartupStep(name, action) {
                  recordSessionProbe(`startup_${name}_before`);
                  try {
                    const result = action();
                    recordSessionProbe(`startup_${name}_after`);
                    return result;
                  } catch (error) {
                    recordSessionProbe(`startup_${name}_error`, { error: sanitizeSessionProbeError(error) });
                    throw error;
                  }
                }

                function selectDefaultProject(projects, preferRemembered = true) {
                  if (!Array.isArray(projects) || projects.length === 0) return;
                  const current = state.projectId ? projects.find(project => project.projectId === state.projectId) : null;
                  if (current?.projectId) {
                    void selectProject(current.projectId);
                    return;
                  }
                  const remembered = preferRemembered ? readSelectedProjectId() : "";
                  if (remembered && projects.some(project => project.projectId === remembered)) {
                    void selectProject(remembered);
                    return;
                  }
                  const latest = latestProject(projects);
                  if (latest?.projectId) void selectProject(latest.projectId);
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

                async function selectProject(projectId) {
                  if (projectSwitchLocked() && state.projectId) {
                    out("当前操作完成前不能切换项目。");
                    updateProjectSwitchAvailability();
                    return;
                  }
                  const switchingProject = state.projectId !== projectId;
                  if (state.projectId && state.projectId !== projectId) {
                    try { await v2WriteProjectUiState(); } catch {}
                  }
                  if (switchingProject) clearChatAttachments();
                  state.pendingPrototypeSkeletonRun = null;
                  resetPrototypeSkeletonBannerState(false);
                  state.projectId = projectId;
                  v2RestoredProjectUiStateId = "";
                  writeSelectedProjectId(projectId);
                  state.assetInventory = null;
                  state.assetInventoryExpanded = false;
                  state.draftAnalysisRunning = false;
                  state.gddMilestoneSteps = null;
                  state.selectedGddMilestoneStepId = "";
                  state.gddMilestoneManualSelection = false;
                  state.packageList = null;
                  state.runs = [];
                  state.prototypeFailure = "";
                  state.prototypeReadyForFeedback = false;
                  state.v2PrototypeStatus = "";
                  state.v2PrototypeAcceptanceStatus = "";
                  state.v2PrototypeCreationStatus = "";
                  state.iterationPlan = null;
                  state.iterationPlans = [];
                  state.selectedIterationSessionId = "";
                  state.iterationPlanEvaluation = null;
                  state.iterationPlanFailure = "";
                  state.repairPlan = null;
                  Array.from(v2OpenTabs.keys()).forEach(tabId => {
                    if (tabId !== "chat") v2OpenTabs.delete(tabId);
                  });
                  v2ActiveTabId = "chat";
                  v2SelectedStep = "new-project";
                  v2UserSelectedStep = false;
                  setModalVisible("projectListModal", false);
                  hideCreateProjectPage();
                  const project = state.projects.find(p => p.projectId === projectId);
                  $("selectedProject").textContent = project ? `${project.name} (${project.projectId})` : projectId;
                  showProjectDetail();
                  try { loadChatHistoryForProject(projectId); } catch {}
                  try { callV2("v2RenderLeftProjectList"); } catch {}
                  try { v2RenderTabs(); } catch {}
                  try { v2ApplySelectedStepVisibility(); } catch {}
                  try { v2RenderProgress(); } catch {}
                  try { setFormalFeedbackAvailability(false); } catch {}
                  try { v2ApplyPrototypeFormLock(); } catch {}
                  try { applyProjectStateCache(projectId); } catch {}
                  void v2RestoreProjectUiState(projectId).catch(recoverVisiblePageFromClientError);
                  void loadProjectRuntimeState().catch(recoverVisiblePageFromClientError);
                  void loadServerChatHistoryForProject(projectId).catch(() => {});
                  void loadIterationPlan().catch(() => {});
                  void loadRepairPlan().catch(() => {});
                  void refreshGddOutlineStatus().catch(() => {});
                  void refreshPrototypeGddStatus().catch(() => {});
                }

                async function loadProjectRuntimeState() {
                  const projectId = state.projectId;
                  const requestAuthEpoch = authEpoch;
                  await Promise.allSettled([
                    loadRuns(),
                    loadPrototypeProgress(),
                    loadProjectPackages(),
                    refreshAssetInventoryAvailability(),
                    refreshPrototypeGddStatus(),
                    loadGddMilestoneSteps()
                  ]);
                  if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
                  try { v2RenderProgress(); } catch {}
                }

                async function loadLatestPrototypeDraft(forceVisibleNotice = false) {
                  const projectId = state.projectId;
                  const requestAuthEpoch = authEpoch;
                  if (!projectId) return;
                  try {
                    const draft = await api(`/api/projects/${projectId}/prototype-drafts/latest`);
                    if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return null;
                    applyDraftToForm(draft);
                    renderDraftImportStatus(draft);
                    writeProjectStateCache({ latestPrototypeDraft: draft }, projectId);
                    if (forceVisibleNotice && draft.status === "succeeded") {
                      showPrototypeNotice("已同步最近一次草稿分析结果，表单已自动补全到最新状态。", "info");
                    }
                    return draft;
                  } catch {
                    if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return null;
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
                    try {
                      await refreshActiveRun();
                    } finally {
                      setLocalBusy(false);
                      $("createProject").disabled = false;
                      $("createProject").textContent = "创建项目";
                    }
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
                        void selectProject(createdProject.projectId);
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
                  const code = publicErrorCode(payload.failureCode || payload.error || error?.status || "unknown_error");
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
                    try {
                      await refreshActiveRun();
                    } finally {
                      if (deleteButton) {
                        deleteButton.disabled = false;
                        deleteButton.textContent = "删除项目";
                      }
                      setLocalBusy(false);
                    }
                  }
                }

                async function loadRuns() {
                  const projectId = state.projectId;
                  const requestAuthEpoch = authEpoch;
                  if (!projectId) return out("请先选择一个项目。");
                  try {
                    const result = await api(`/api/projects/${projectId}/runs`);
                    if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
                    state.runs = result.runs || [];
                    renderProjectHealth(result.projectHealth);
                    renderRunsListFromState(result.projectHealth);
                    writeProjectStateCache({ runs: state.runs, projectHealth: result.projectHealth || null }, projectId);
                    renderFeedbackRecords();
                    callV2("v2RenderProgress");
                    out(result);
                  } catch (error) {
                    if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
                    showError(error);
                  }
                }

                function renderRunsListFromState(projectHealth = null) {
                  if (projectHealth) renderProjectHealth(projectHealth);
                  $("runs").innerHTML = (state.runs || []).map(r => `
                    <button class="card ghost" data-run="${r.runId}">
                      <strong>${escapeHtml(r.runType)} · ${escapeHtml(publicStatusLabel(r.status))}</strong>
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
                      const downloads = feedbackArtifacts(run).map(a => `<a href="/artifacts/${escapeHtml(a.artifactId)}" target="_blank" rel="noreferrer">${escapeHtml(publicArtifactLabel(a.artifactType))}</a>`).join(" · ");
                      return `
                        <div class="${cardClass}">
                          <strong>任务 ${escapeHtml(String(record.goal.goalIndex))} · ${escapeHtml(record.goal.title || "")}</strong>
                          <div class="goal-badges">
                            ${goalBadge(statusLabel(record.goal.status), `goal-badge-${normalizeGoalStatus(record.goal.status)}`)}
                            ${isCurrent ? goalBadge("当前任务", "goal-badge-current") : ""}
                            ${isNext ? goalBadge("下一任务", "goal-badge-next") : ""}
                          </div>
                          <span class="muted">${escapeHtml(publicStatusLabel(run?.status || "pending"))}</span>
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
                    const downloads = feedbackArtifacts(run).map(a => `<a href="/artifacts/${escapeHtml(a.artifactId)}" target="_blank" rel="noreferrer">${escapeHtml(publicArtifactLabel(a.artifactType))}</a>`).join(" · ");
                    return `
                      <div class="card">
                        <strong>第 ${feedbackRuns.length - index} 次正式反馈 · ${escapeHtml(publicStatusLabel(run.status))}</strong>
                        <span class="muted">${escapeHtml(run.runId)}</span>
                        <p>${downloads || "暂无可下载日志"}</p>
                      </div>
                    `;
                  }).join("") || "<p class='muted'>还没有流程记录。</p>";
                }

                function renderFeedbackSummary(legacyFeedbackRuns = []) {
                  const goals = latestIterationPlanGoalsForAction();
                  if (goals.length > 0) {
                    const completedGoals = goals.filter(goal => goal.status === "succeeded").length;
                    const runningGoal = goals.find(goal => goal.status === "running");
                    const needsFixGoal = goals.find(goal => goal.status === "needs_fix");
                    const pendingGoal = goals.find(goal => goal.status === "pending");
                    const failedGoal = goals.find(goal => goal.status === "failed");
                    const repairGoal = needsFixGoal || failedGoal;
                    const currentGoal = repairGoal || runningGoal || pendingGoal || goals[goals.length - 1];
                    const nextGoal = repairGoal ? null : pendingGoal;
                    $("feedbackSummary").className = "card";
                    $("feedbackSummary").innerHTML = `
                      <strong>计划摘要</strong>
                      <p class="muted">总任务数：${escapeHtml(String(goals.length))} · 完成：${escapeHtml(String(completedGoals))}</p>
                      <p class="muted">当前任务：${currentGoal ? escapeHtml(`任务 ${currentGoal.goalIndex} · ${currentGoal.title || ""}`) : "暂无"}</p>
                      <p class="muted">下一任务：${repairGoal ? "请先修复当前任务" : nextGoal ? escapeHtml(`任务 ${nextGoal.goalIndex} · ${nextGoal.title || ""}`) : "全部完成"}</p>
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
                  const actionPlan = latestIterationPlanForAction();
                  const goals = iterationPlanGoals(actionPlan);
                  if (!goals.length || !state.prototypeReadyForFeedback) {
                    return { label: "", action: "", source: "", disabled: true };
                  }
                  const decision = latestIterationPlanDecision();
                  const hasNeedsFix = goals.some(goal => goal.status === "needs_fix" || goal.status === "failed");
                  const hasPending = goals.some(goal => goal.status === "pending");
                  if (decision === "llm_failed") {
                    return { label: "LLM 调用失败，先修复", action: "", source: "当前计划评估", disabled: true };
                  }
                  if (decision === "should_refine_plan") {
                    return { label: "重新生成游戏模块", action: "refine", source: "当前计划评估", disabled: isGlobalBusy() || isIterationPlanStarted(actionPlan) };
                  }
                  if (hasNeedsFix || hasPending) {
                    return { label: "继续评估当前计划", action: "evaluate", source: "目标执行结果", disabled: isGlobalBusy() };
                  }
                  if (decision === "ready_to_execute") {
                    return { label: "继续当前任务", action: "execute", source: "当前计划评估", disabled: isGlobalBusy() };
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
                  const actionState = feedbackPrimaryActionState();
                  if (!actionState.action) return out("当前没有可执行的推荐动作。");
                  const actionPlan = latestIterationPlanForAction();
                  if (actionState.action === "refine") {
                    if (isIterationPlanStarted(actionPlan)) return out("当前游戏模块已经开始执行，不允许更新游戏模块。");
                    const evaluationSuggestion = latestIterationPlanRegenerationPrompt();
                    if (evaluationSuggestion) {
                      selectLatestIterationPlanForAction();
                      openIterationPlanUpdateModal("update", evaluationSuggestion);
                      return;
                    }
                    if (!state.nextSuggestedFeedback) return out("当前没有可用于重拆计划的建议。");
                    selectLatestIterationPlanForAction();
                    openIterationPlanUpdateModal("update", state.nextSuggestedFeedback);
                    return;
                  }
                  if (actionState.action === "execute") {
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

                function publicGoalStatusLabel(value) {
                  const normalized = normalizeGoalStatus(value);
                  if (normalized === "succeeded") return "完成";
                  if (normalized === "running") return "执行中";
                  if (normalized === "failed") return "需要修复";
                  if (normalized === "needs-fix") return "需要修复";
                  if (normalized === "timed-out") return "需要修复";
                  return "待执行";
                }

                function statusLabel(value) {
                  return publicGoalStatusLabel(value);
                }

                function publicStatusLabel(value) {
                  const normalized = String(value || "").trim().toLowerCase().replace(/_/g, "-");
                  if (normalized === "succeeded" || normalized === "completed" || normalized === "done") return "完成";
                  if (normalized === "needs-fix" || normalized === "failed" || normalized === "fix") return "需要修复";
                  if (normalized === "pending" || normalized === "queued" || normalized === "ready" || normalized === "idle") return "待执行";
                  if (normalized === "running" || normalized === "preparing" || normalized === "repairing") return "执行中";
                  if (normalized === "paused-for-review") return "等待确认";
                  if (normalized === "cancel") return "已取消";
                  return value || "待执行";
                }

                function publicDecisionLabel(value) {
                  const normalized = String(value || "").trim().toLowerCase();
                  if (normalized === "ready_to_execute") return "可以执行";
                  if (normalized === "should_refine_plan") return "建议重拆";
                  if (normalized === "blocked_by_current_goal") return "当前任务阻塞";
                  if (normalized === "llm_failed") return "模型调用失败";
                  return publicStatusLabel(value);
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
                    const links = (result.artifacts || []).map(a => `产物: ${publicArtifactLabel(a.artifactType)} ${location.origin}/artifacts/${a.artifactId}`).join("\n");
                    out(`${sanitizePublicRunContent(JSON.stringify(result.run, null, 2))}\n\n${links}`);
                  } catch (error) { showError(error); }
                }

                function isGlobalBusy() {
                  return state.localBusy ||
                    state.chatBusy ||
                    state.workflowRouteBusy ||
                    state.iterationPlanEvaluationRunning ||
                    (runIsBusy(state.activeRun) && !isInlineOnlyRun(state.activeRun)) ||
                    hasPendingPrototypeSkeletonBannerRun();
                }

                function runIsBusy(run) {
                  if (!run) return false;
                  if (!run.runId) return false;
                  if (run.busy === true) return true;
                  const status = String(run.status || "").trim().toLowerCase();
                  return status === "queued" || status === "running";
                }

                function isInlineOnlyRun(run) {
                  const runType = String(run?.runType || "").trim().toLowerCase();
                  return runType === "prototype-iteration-plan-evaluation";
                }

                function activeRunText(run) {
                  if (!runIsBusy(run)) return "";
                  const projectLabel = run.projectName || run.projectId || "";
                  const projectText = projectLabel ? `项目：${projectLabel} · ` : "";
                  if (run.heavyRunnerQueuePosition) {
                    const waitSeconds = Math.max(0, run.heavyRunnerEstimatedWaitSeconds || 0);
                    const waitMinutes = Math.max(1, Math.ceil(waitSeconds / 60));
                    return `${projectText}\u4f60\u5df2\u8fdb\u5165\u91cd\u4efb\u52a1\u961f\u5217\uff1a\u7b2c ${run.heavyRunnerQueuePosition} \u4f4d\uff0c\u5f53\u524d\u7b49\u5f85 ${run.heavyRunnerQueuedCount || 0} \u4e2a\uff0c\u9884\u8ba1\u7b49\u5f85\u7ea6 ${waitMinutes} \u5206\u949f\u3002`;
                  }
                  const label = run.progressLabel || run.progressStep || run.status || "";
                  if (String(run.runType || "").trim().toLowerCase() === "game-design-gdd-section-batch") {
                    return label ? `${projectText}\u7b56\u5212\u5927\u7eb2\u8865\u5168\u4e2d\uff1a${label}` : `${projectText}\u7b56\u5212\u5927\u7eb2\u8865\u5168\u4e2d\u3002`;
                  }
                  return `${projectText}当前任务执行中：${run.runType || "未知"} · ${publicStatusLabel(run.status || "running")} · ${run.runId || ""}${label ? " · " + label : ""}`;
                }

                function isPrototypeSkeletonRunType(run) {
                  const runType = String(run?.runType || "").trim().toLowerCase();
                  return runType === "prototype-7day-playable";
                }

                function isPrototypeSkeletonCreationRun(run) {
                  if (!isPrototypeSkeletonRunType(run)) return false;
                  const step = String(run?.progressStep || "").trim().toLowerCase();
                  const label = String(run?.progressLabel || "").trim();
                  return !step.includes("validation") && !label.includes("验收");
                }

                function hasPendingPrototypeSkeletonBannerRun() {
                  return !!state.pendingPrototypeSkeletonRun?.runId &&
                    runIsBusy(state.pendingPrototypeSkeletonRun) &&
                    isPrototypeSkeletonCreationRun(state.pendingPrototypeSkeletonRun) &&
                    runBelongsToCurrentProject(state.pendingPrototypeSkeletonRun);
                }

                function skeletonBannerRun() {
                  if (isPrototypeSkeletonCreationRun(state.activeRun) && runIsBusy(state.activeRun) && runBelongsToCurrentProject(state.activeRun)) return state.activeRun;
                  return hasPendingPrototypeSkeletonBannerRun() ? state.pendingPrototypeSkeletonRun : null;
                }

                function prototypeSkeletonBannerLine1() {
                  return "系统正在进行游戏场景创建工作，其中可能存在的信息延迟或显示遗漏但不影响实际进程；";
                }

                function prototypeSkeletonBannerStorageKey(runId = state.prototypeSkeletonBannerRunId, projectId = state.projectId) {
                  return `phaseA.prototypeSkeletonBanner.${projectId || "none"}.${runId || "none"}`;
                }

                function prototypeSkeletonBannerCurrentKey(projectId = state.projectId) {
                  return `phaseA.prototypeSkeletonBanner.current.${projectId || "none"}`;
                }

                function prototypeSkeletonBannerStoredRunId() {
                  try {
                    return localStorage.getItem(prototypeSkeletonBannerCurrentKey()) || "";
                  } catch {
                    return "";
                  }
                }

                function prototypeSkeletonNowMs() {
                  return Date.now ? Date.now() : new Date().getTime();
                }

                function prototypeSkeletonRunStartedAtMs(run) {
                  const value = run?.startedUtc || run?.createdUtc || run?.queuedUtc || run?.progressUpdatedUtc || "";
                  const time = Date.parse(value || "");
                  return Number.isFinite(time) ? time : 0;
                }

                function readPrototypeSkeletonBannerState(runId, projectId = state.projectId) {
                  if (!runId) return null;
                  try {
                    const cached = JSON.parse(localStorage.getItem(prototypeSkeletonBannerStorageKey(runId, projectId)) || "null");
                    return cached && cached.runId === runId && (!cached.projectId || cached.projectId === projectId) ? cached : null;
                  } catch {
                    return null;
                  }
                }

                function writePrototypeSkeletonBannerState() {
                  if (!state.prototypeSkeletonBannerRunId) return;
                  try {
                    localStorage.setItem(prototypeSkeletonBannerCurrentKey(), state.prototypeSkeletonBannerRunId);
                    localStorage.setItem(prototypeSkeletonBannerStorageKey(), JSON.stringify({
                      runId: state.prototypeSkeletonBannerRunId,
                      projectId: state.projectId || "",
                      expanded: !!state.prototypeSkeletonBannerExpanded,
                      displayedCount: Math.max(0, state.prototypeSkeletonBannerDisplayedCount || 0),
                      startedAtMs: Math.max(0, state.prototypeSkeletonBannerStartedAtMs || 0),
                      tick: Math.max(0, state.prototypeSkeletonBannerTick || 0),
                      runCreatedUtc: state.pendingPrototypeSkeletonRun?.createdUtc || state.activeRun?.createdUtc || "",
                      runStartedUtc: state.pendingPrototypeSkeletonRun?.startedUtc || state.activeRun?.startedUtc || "",
                      runProgressUpdatedUtc: state.pendingPrototypeSkeletonRun?.progressUpdatedUtc || state.activeRun?.progressUpdatedUtc || "",
                      updatedAt: new Date().toISOString()
                    }));
                  } catch {}
                }

                function clearPrototypeSkeletonBannerState(runId = state.prototypeSkeletonBannerRunId, projectId = state.projectId) {
                  if (!runId) return;
                  try {
                    localStorage.removeItem(prototypeSkeletonBannerStorageKey(runId, projectId));
                    if (localStorage.getItem(prototypeSkeletonBannerCurrentKey(projectId)) === runId) {
                      localStorage.removeItem(prototypeSkeletonBannerCurrentKey(projectId));
                    }
                  } catch {}
                }

                function resetPrototypeSkeletonBannerState(clearPersisted = false) {
                  const runId = state.prototypeSkeletonBannerRunId;
                  state.prototypeSkeletonBannerExpanded = false;
                  state.prototypeSkeletonBannerIndex = 0;
                  state.prototypeSkeletonBannerTick = 0;
                  state.prototypeSkeletonBannerRunId = "";
                  state.prototypeSkeletonBannerDisplayedCount = 0;
                  state.prototypeSkeletonBannerStartedAtMs = 0;
                  if (clearPersisted) clearPrototypeSkeletonBannerState(runId);
                }

                function prototypeSkeletonDisplayCountFromStartedAt(startedAtMs) {
                  if (!PrototypeSkeletonRunNotes.length) return 0;
                  const start = Math.max(0, startedAtMs || 0);
                  if (!start) return 1;
                  const elapsedMs = Math.max(0, prototypeSkeletonNowMs() - start);
                  return Math.min(PrototypeSkeletonRunNotes.length, Math.max(1, Math.floor(elapsedMs / 20000) + 1));
                }

                function syncPrototypeSkeletonBannerDisplayedCount() {
                  const targetCount = prototypeSkeletonDisplayCountFromStartedAt(state.prototypeSkeletonBannerStartedAtMs);
                  if (targetCount > state.prototypeSkeletonBannerDisplayedCount) {
                    state.prototypeSkeletonBannerDisplayedCount = targetCount;
                    writePrototypeSkeletonBannerState();
                    return true;
                  }
                  return false;
                }

                function restorePrototypeSkeletonBannerFromStorage() {
                  if (state.prototypeSkeletonBannerRunId) return;
                  const projectId = state.projectId;
                  if (!projectId) return;
                  try {
                    const runId = localStorage.getItem(prototypeSkeletonBannerCurrentKey(projectId)) || "";
                    const cached = readPrototypeSkeletonBannerState(runId, projectId);
                    if (!cached?.runId) return;
                    state.prototypeSkeletonBannerRunId = cached.runId;
                    state.prototypeSkeletonBannerExpanded = !!cached.expanded;
                    state.prototypeSkeletonBannerTick = Math.max(0, cached.tick || 0);
                    const cachedRunTime = prototypeSkeletonRunStartedAtMs({
                      startedUtc: cached.runStartedUtc,
                      createdUtc: cached.runCreatedUtc,
                      progressUpdatedUtc: cached.runProgressUpdatedUtc
                    });
                    state.prototypeSkeletonBannerStartedAtMs = Math.max(0, cached.startedAtMs || 0) || cachedRunTime || prototypeSkeletonNowMs();
                    state.prototypeSkeletonBannerDisplayedCount = Math.min(
                      PrototypeSkeletonRunNotes.length,
                      Math.max(1, cached.displayedCount || 1)
                    );
                    syncPrototypeSkeletonBannerDisplayedCount();
                    state.pendingPrototypeSkeletonRun = {
                      runId: cached.runId,
                      projectId,
                      busy: true,
                      runType: "prototype-7day-playable",
                      status: "running",
                      progressStep: "restored",
                      progressLabel: "正在同步任务状态。",
                      createdUtc: cached.runCreatedUtc || "",
                      startedUtc: cached.runStartedUtc || "",
                      progressUpdatedUtc: cached.updatedAt || new Date().toISOString()
                    };
                    applyGlobalBusyState();
                  } catch {}
                }

                function ensurePrototypeSkeletonBannerRun(run) {
                  if (!run?.runId) return;
                  if (!runBelongsToCurrentProject(run)) return;
                  if (state.prototypeSkeletonBannerRunId === run.runId) {
                    if (!state.prototypeSkeletonBannerStartedAtMs) {
                      const cached = readPrototypeSkeletonBannerState(run.runId, state.projectId);
                      state.prototypeSkeletonBannerStartedAtMs = Math.max(0, cached?.startedAtMs || 0) || prototypeSkeletonRunStartedAtMs(run) || prototypeSkeletonNowMs();
                    }
                    syncPrototypeSkeletonBannerDisplayedCount();
                    return;
                  }
                  const cached = readPrototypeSkeletonBannerState(run.runId, state.projectId);
                  state.prototypeSkeletonBannerRunId = run.runId;
                  state.prototypeSkeletonBannerExpanded = !!cached?.expanded;
                  state.prototypeSkeletonBannerIndex = 0;
                  state.prototypeSkeletonBannerTick = Math.max(0, cached?.tick || 0);
                  state.prototypeSkeletonBannerStartedAtMs = Math.max(0, cached?.startedAtMs || 0) || prototypeSkeletonRunStartedAtMs(run) || prototypeSkeletonNowMs();
                  state.prototypeSkeletonBannerDisplayedCount = Math.min(
                    PrototypeSkeletonRunNotes.length,
                    Math.max(1, cached?.displayedCount || 1)
                  );
                  syncPrototypeSkeletonBannerDisplayedCount();
                  writePrototypeSkeletonBannerState();
                }

                function prototypeSkeletonVisibleNotes() {
                  syncPrototypeSkeletonBannerDisplayedCount();
                  const displayed = Math.max(0, state.prototypeSkeletonBannerDisplayedCount || 0);
                  return PrototypeSkeletonRunNotes.slice(0, displayed);
                }

                function prototypeSkeletonBannerNotes() {
                  const notes = prototypeSkeletonVisibleNotes();
                  return state.prototypeSkeletonBannerExpanded ? notes : notes.slice(Math.max(0, notes.length - 2));
                }

                function scrollPrototypeSkeletonNotesToBottom(container) {
                  if (!container) return;
                  requestAnimationFrame(() => {
                    container.scrollTop = container.scrollHeight;
                  });
                }

                function prototypeSkeletonAdvanceTail() {
                  if (!PrototypeSkeletonRunNotes.length) return;
                  syncPrototypeSkeletonBannerDisplayedCount();
                }

                function renderPrototypeSkeletonBanner(run) {
                  const banner = $("activeRunBanner");
                  if (!run?.runId) {
                    banner.classList.add("hidden");
                    banner.replaceChildren();
                    return;
                  }
                  banner.classList.add("busy-banner-prototype-skeleton");
                  banner.classList.toggle("is-expanded", !!state.prototypeSkeletonBannerExpanded);
                  banner.replaceChildren();
                  ensurePrototypeSkeletonBannerRun(run);
                  const lines = document.createElement("div");
                  lines.className = "busy-banner-lines";
                  const headline = document.createElement("div");
                  headline.className = "busy-banner-line";
                  headline.textContent = prototypeSkeletonBannerLine1();
                  lines.appendChild(headline);
                  const noteWindow = document.createElement("div");
                  noteWindow.className = "busy-banner-note-window";
                  for (const text of prototypeSkeletonBannerNotes()) {
                    const line = document.createElement("div");
                    line.className = "busy-banner-line is-muted";
                    line.textContent = text;
                    noteWindow.appendChild(line);
                  }
                  lines.appendChild(noteWindow);
                  banner.appendChild(lines);
                  if (state.prototypeSkeletonBannerExpanded) {
                    noteWindow.classList.add("busy-banner-details");
                    scrollPrototypeSkeletonNotesToBottom(noteWindow);
                  }
                  const actions = document.createElement("div");
                  actions.className = "busy-banner-actions";
                  const toggleButton = document.createElement("button");
                  toggleButton.type = "button";
                  toggleButton.className = "ghost";
                  toggleButton.textContent = state.prototypeSkeletonBannerExpanded ? "关闭详细信息" : "展开详细信息";
                  toggleButton.onclick = () => {
                    state.prototypeSkeletonBannerExpanded = !state.prototypeSkeletonBannerExpanded;
                    writePrototypeSkeletonBannerState();
                    applyGlobalBusyState();
                  };
                  actions.appendChild(toggleButton);
                  if (canCancelActiveRun(state.activeRun)) {
                    const cancelButton = document.createElement("button");
                    cancelButton.type = "button";
                    cancelButton.className = "ghost danger";
                    cancelButton.textContent = "取消任务";
                    cancelButton.onclick = cancelActiveRun;
                    actions.appendChild(cancelButton);
                  }
                  banner.appendChild(actions);
                }

                function canCancelActiveRun(run) {
                  const runType = String(run?.runType || "").trim().toLowerCase();
                  return !!run?.runId &&
                    runBelongsToCurrentProject(run) &&
                    !["chapter2-bootstrap", "project-creation", "project-asset-generation", "asset-generation"].includes(runType);
                }

                function clearCancelledActiveRunState() {
                  state.cancelledActiveRunId = "";
                  state.cancelledActiveRunProjectId = "";
                }

                function cancelledPrototypeMarkerKey(projectId = state.projectId) {
                  return `phaseA.cancelledPrototypeRun.${projectId || "none"}`;
                }

                function writeCancelledPrototypeMarker(runId, projectId = state.projectId) {
                  if (!projectId || !runId) return;
                  try {
                    localStorage.setItem(cancelledPrototypeMarkerKey(projectId), JSON.stringify({
                      runId,
                      updatedAt: new Date().toISOString()
                    }));
                  } catch {}
                }

                function readCancelledPrototypeMarker(projectId = state.projectId) {
                  if (!projectId) return null;
                  try {
                    const marker = JSON.parse(localStorage.getItem(cancelledPrototypeMarkerKey(projectId)) || "null");
                    return marker?.runId ? marker : null;
                  } catch {
                    return null;
                  }
                }

                function clearCancelledPrototypeMarker(projectId = state.projectId) {
                  if (!projectId) return;
                  try { localStorage.removeItem(cancelledPrototypeMarkerKey(projectId)); } catch {}
                }

                function shouldSuppressPrototypeFormLockForProgress(progress) {
                  const creationStatus = String(progress?.prototypeCreationStatus || progress?.status || "").trim().toLowerCase();
                  const currentProjectCancelled = !!state.cancelledActiveRunId && state.cancelledActiveRunProjectId === state.projectId;
                  return (currentProjectCancelled || !!readCancelledPrototypeMarker(state.projectId)) && ["queued", "running"].includes(creationStatus);
                }

                function cancelledPrototypeProgressSnapshot() {
                  return {
                    status: "idle",
                    prototypeCreationStatus: "idle",
                    acceptanceStatus: "idle",
                    label: "任务已取消。",
                    step: "cancelled",
                    substep: "",
                    updatedUtc: new Date().toISOString()
                  };
                }

                function prototypeSkeletonLocked() {
                  return state.prototypeReadyForFeedback ||
                    String(state.v2PrototypeAcceptanceStatus || "").trim().toLowerCase() === "succeeded" ||
                    v2HasPrototypeSkeleton() ||
                    v2SkeletonValidationSucceeded();
                }

                function firstGddMilestoneStep() {
                  const steps = Array.isArray(state.gddMilestoneSteps?.steps) ? state.gddMilestoneSteps.steps : [];
                  return steps.find(step => String(step.stepId || "").trim().toUpperCase() === "M1") || steps[0] || null;
                }

                function prototypeSkeletonM1Completed() {
                  const m1 = firstGddMilestoneStep();
                  const status = String(m1?.status || "").trim().toLowerCase();
                  return prototypeSkeletonLocked() || !!m1?.confirmedUtc || ["executed", "feedback_submitted", "confirmed"].includes(status);
                }

                function updatePrototypeSkeletonPackageButton() {
                  const button = $("packagePrototypeSkeleton");
                  if (!button) return;
                  const enabled = !!state.projectId && prototypeSkeletonM1Completed() && !isGlobalBusy();
                  setButtonDisabledState(
                    button,
                    !enabled,
                    enabled ? "" : "M1 游戏场景完成后才可以在这里打包下载项目。");
                }

                function renderPrototypeM1SpecStatus() {
                  const panel = $("prototypeM1SpecStatus");
                  if (!panel) return;
                  const m1 = firstGddMilestoneStep();
                  if (!state.projectId) {
                    panel.className = "card muted";
                    panel.textContent = "选择项目后显示 M1 游戏场景目标。";
                    updatePrototypeSkeletonPackageButton();
                    return;
                  }

                  if (!m1) {
                    panel.className = "card muted";
                    panel.textContent = "创建策划大纲后显示 M1 游戏场景目标。";
                    updatePrototypeSkeletonPackageButton();
                    return;
                  }

                  panel.className = "card";
                  panel.innerHTML = `
                    <strong>M1 游戏场景目标：${escapeHtml(m1.title || "首个可玩模块")}</strong>
                    <p>${escapeHtml(m1.description || "完成首个可进入、可操作、可验证的可玩模块。")}</p>
                    ${renderStepSpecLine("验收", m1.acceptance)}
                    ${renderStepSpecLine("完成后试玩验证", m1.packagingValidation)}
                    ${m1.specRelativePath ? `<p class="muted"><strong>规格文件：</strong>${escapeHtml(m1.specRelativePath)}</p>` : ""}
                  `;
                  updatePrototypeSkeletonPackageButton();
                }

                function setLocalBusy(busy, message = "有任务正在执行，请等待当前任务执行完毕。") {
                  if (busy) invalidateWorkflowRouteAction();
                  if (busy) {
                    clearCancelledActiveRunState();
                    clearCancelledPrototypeMarker();
                  }
                  state.localBusy = busy;
                  applyGlobalBusyState(message);
                }

                function renderActiveRunBanner(message) {
                  const banner = $("activeRunBanner");
                  banner.classList.remove("busy-banner-prototype-skeleton", "is-expanded");
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

                function hideActiveRunBanner() {
                  const banner = $("activeRunBanner");
                  if (!banner) return;
                  banner.classList.add("hidden");
                  banner.classList.remove("busy-banner-prototype-skeleton", "is-expanded");
                  banner.replaceChildren();
                }

                function setButtonVisualState(button, enabled) {
                  if (!button) return;
                  button.classList.toggle("button-state-enabled", !!enabled);
                  button.classList.toggle("button-state-disabled", !enabled);
                }

                function setButtonBaseClass(button, baseClassName) {
                  if (!button) return;
                  button.classList.remove("button-state-enabled", "button-state-disabled", "import-draft-ready");
                  String(baseClassName || "")
                    .split(/\s+/)
                    .filter(Boolean)
                    .forEach(className => button.classList.add(className));
                }

                function setButtonDisabledState(button, disabled, title = "") {
                  if (!button) return;
                  button.disabled = !!disabled;
                  setButtonVisualState(button, !disabled);
                  if (disabled && title) button.title = title;
                  else button.removeAttribute("title");
                }

                function resetPrototypeActionButtonsVisualState() {
                  if ($("runPrototype")) {
                    const skeletonLocked = prototypeSkeletonLocked();
                    setButtonBaseClass($("runPrototype"), "secondary");
                    $("runPrototype").style.removeProperty("background");
                    $("runPrototype").style.removeProperty("border-color");
                    $("runPrototype").style.removeProperty("color");
                    $("runPrototype").style.removeProperty("box-shadow");
                    $("runPrototype").removeAttribute("title");
                    $("runPrototype").textContent = skeletonLocked ? "M1 游戏场景已完成" : "确认 GDD 无误，执行 M1 游戏场景";
                    setButtonDisabledState(
                      $("runPrototype"),
                      skeletonLocked,
                      skeletonLocked ? "游戏场景已验收通过，不能重复创建。" : "");
                  }
                  if ($("importDraft")) {
                    setButtonBaseClass($("importDraft"), "secondary import-draft-button");
                    $("importDraft").style.removeProperty("background");
                    $("importDraft").style.removeProperty("border-color");
                    $("importDraft").style.removeProperty("color");
                    $("importDraft").style.removeProperty("box-shadow");
                    $("importDraft").removeAttribute("title");
                    $("importDraft").textContent = "分析草稿并回填";
                    setButtonVisualState($("importDraft"), false);
                  }
                  if ($("repairPrototype")) {
                    $("repairPrototype").removeAttribute("title");
                  }
                }

                function unlockPrototypeFormAfterCancel() {
                  prototypeInputIds.forEach(id => { if ($(id)) $(id).disabled = false; });
                  if ($("draftFile")) $("draftFile").disabled = true;
                  resetPrototypeActionButtonsVisualState();
                  setButtonDisabledState($("runPrototype"), false);
                  setButtonDisabledState($("importDraft"), true, "游戏场景创建只读取当前项目 GDD。");
                  if ($("repairPrototype")) $("repairPrototype").textContent = "生成修复计划";
                  setButtonDisabledState($("repairPrototype"), false);
                }

                function setPrototypeDraftFileLocked(locked) {
                  if (!$("draftFile")) return;
                  $("draftFile").disabled = true;
                }

                function applyGlobalBusyState(message = "有任务正在执行，请等待当前任务执行完毕。") {
                  const busy = isGlobalBusy();
                  updateProjectSwitchAvailability();
                  document.querySelectorAll("[data-global-action]").forEach(button => {
                    if (button.id === "runPrototype" && prototypeSkeletonLocked()) {
                      setButtonDisabledState(button, true, "游戏场景已验收通过，不能重复创建。");
                      button.textContent = "M1 游戏场景已完成";
                      return;
                    }
                    if (button.id === "packagePrototypeSkeleton") {
                      updatePrototypeSkeletonPackageButton();
                      return;
                    }
                    if (button.id === "importDraft" && prototypeSkeletonLocked()) {
                      setButtonDisabledState(button, true, "游戏场景已验收通过，不能重新导入。");
                      return;
                    }
                    setButtonDisabledState(button, busy, message);
                  });
                  document.querySelectorAll("[data-needs-fix-goal]").forEach(button => {
                    setButtonDisabledState(button, busy, message);
                  });
                  if (!busy && state.packageList) {
                    renderProjectPackages(state.packageList);
                  }
                  if (!busy && state.assetInventory) {
                    renderAssetInventory(state.assetInventory, state.assetInventoryExpanded);
                  }
                  if (!busy) {
                    renderGddMilestoneSteps();
                    renderPrototypeM1SpecStatus();
                  }
                  if (!busy && !state.draftAnalysisRunning) {
                    resetPrototypeActionButtonsVisualState();
                  }
                  updateDraftImportButtonState();
                  updatePrototypeSkeletonPackageButton();
                  if (busy) {
                    $("activeRunBanner").classList.remove("hidden");
                    const skeletonRun = skeletonBannerRun();
                    if (skeletonRun) {
                      renderPrototypeSkeletonBanner(skeletonRun);
                    } else {
                      state.prototypeSkeletonBannerExpanded = false;
                      renderActiveRunBanner(runIsBusy(state.activeRun) ? activeRunText(state.activeRun) : message);
                    }
                  } else {
                    if (!state.pendingPrototypeSkeletonRun?.runId && !prototypeSkeletonBannerStoredRunId()) {
                      resetPrototypeSkeletonBannerState(true);
                    }
                    hideActiveRunBanner();
                  }
                }

                async function cancelActiveRun() {
                  const run = state.activeRun;
                  const runId = run?.runId;
                  if (!runId) return;
                  if (!confirm("确定要取消当前 run 吗？")) return;
                  try {
                    const runProjectId = String(run?.projectId || state.projectId || "");
                    const cancelledCurrentPrototypeRun = isPrototypeSkeletonCreationRun(run) && !!runProjectId && runProjectId === state.projectId;
                    await api(`/api/runs/${encodeURIComponent(runId)}/cancel`, { method: "POST", body: "{}" });
                    state.cancelledActiveRunId = runId;
                    state.cancelledActiveRunProjectId = runProjectId;
                    if (isPrototypeSkeletonCreationRun(run) && runProjectId) {
                      writeCancelledPrototypeMarker(runId, runProjectId);
                    }
                    state.activeRun = null;
                    state.localBusy = false;
                    state.draftAnalysisRunning = false;
                    state.pendingPrototypeSkeletonRun = null;
                    if (cancelledCurrentPrototypeRun) {
                      state.v2PrototypeCreationStatus = "idle";
                      writeProjectStateCache({ prototypeProgress: cancelledPrototypeProgressSnapshot() }, runProjectId);
                    }
                    resetPrototypeSkeletonBannerState(true);
                    if (cancelledCurrentPrototypeRun) unlockPrototypeFormAfterCancel();
                    out("当前 run 已取消。");
                    hideActiveRunBanner();
                    applyGlobalBusyState();
                    if (cancelledCurrentPrototypeRun) unlockPrototypeFormAfterCancel();
                    if (state.projectId) {
                      await Promise.allSettled([
                        loadRuns(),
                        refreshAssetInventoryAvailability(),
                        refreshGddOutlineStatus()
                      ]);
                    }
                    if (cancelledCurrentPrototypeRun) unlockPrototypeFormAfterCancel();
                  } catch (error) {
                    showError(error);
                    await refreshActiveRun();
                  }
                }

                async function refreshActiveRun() {
                  if (!state.authenticated) return;
                  try {
                    const wasBusy = isGlobalBusy();
                    const hadTrackedBusyRun = runIsBusy(state.activeRun) || hasPendingPrototypeSkeletonBannerRun();
                    const activeRun = await api("/api/account/active-run");
                    if (!activeRun?.runId) {
                      state.activeRun = null;
                      if (state.pendingPrototypeSkeletonRun?.runId) {
                        state.pendingPrototypeSkeletonRun = null;
                        resetPrototypeSkeletonBannerState(true);
                      }
                      if (hadTrackedBusyRun && state.localBusy) {
                        state.localBusy = false;
                      }
                      applyGlobalBusyState();
                      if (hadTrackedBusyRun && state.projectId) {
                        await refreshCurrentProjectAfterActiveRunSettled();
                      }
                      return;
                    }
                    if (state.cancelledActiveRunId && activeRun?.runId === state.cancelledActiveRunId) {
                      if (runIsBusy(activeRun)) {
                        state.activeRun = null;
                        state.pendingPrototypeSkeletonRun = null;
                        applyGlobalBusyState();
                        return;
                      }
                      clearCancelledActiveRunState();
                    } else if (state.cancelledActiveRunId && (!activeRun?.runId || activeRun.runId !== state.cancelledActiveRunId || !runIsBusy(activeRun))) {
                      clearCancelledActiveRunState();
                    }
                    if (activeRun?.runId && state.cancelledActiveRunId === activeRun.runId && runIsBusy(activeRun)) {
                      state.activeRun = null;
                    } else {
                      state.activeRun = activeRun;
                    }
                    if (isPrototypeSkeletonCreationRun(state.activeRun) && runIsBusy(state.activeRun) && runBelongsToCurrentProject(state.activeRun)) {
                      state.pendingPrototypeSkeletonRun = state.activeRun;
                      ensurePrototypeSkeletonBannerRun(state.activeRun);
                    } else if (hasPendingPrototypeSkeletonBannerRun()) {
                      const pendingRunId = state.pendingPrototypeSkeletonRun?.runId || "";
                      if (!activeRun?.runId || (pendingRunId && activeRun.runId !== pendingRunId) || !runIsBusy(activeRun)) {
                        state.pendingPrototypeSkeletonRun = null;
                        resetPrototypeSkeletonBannerState(true);
                      } else {
                        state.pendingPrototypeSkeletonRun.busy = true;
                        state.pendingPrototypeSkeletonRun.status = state.pendingPrototypeSkeletonRun.status || "running";
                        ensurePrototypeSkeletonBannerRun(state.pendingPrototypeSkeletonRun);
                      }
                    } else {
                      state.pendingPrototypeSkeletonRun = null;
                    }
                    if (runIsBusy(state.activeRun) && !isInlineOnlyRun(state.activeRun) && runBelongsToCurrentProject(state.activeRun)) {
                      const observedProjectId = runProjectId(state.activeRun) || state.projectId;
                      startProjectRunPolling(state.activeRun.runId, observedProjectId, authEpoch);
                    }
                    applyGlobalBusyState();
                    if (state.projectId && shouldAutoRefreshIterationPlan(activeRun)) {
                      await loadIterationPlan();
                      await loadRuns();
                    }
                    if (wasBusy && !runIsBusy(activeRun) && !hasPendingPrototypeSkeletonBannerRun() && state.projectId && runBelongsToCurrentProject(activeRun)) {
                      await refreshCurrentProjectAfterActiveRunSettled();
                    }
                  } catch {
                    state.activeRun = null;
                    if (hasPendingPrototypeSkeletonBannerRun()) {
                      state.pendingPrototypeSkeletonRun.busy = true;
                      ensurePrototypeSkeletonBannerRun(state.pendingPrototypeSkeletonRun);
                    }
                    applyGlobalBusyState();
                  }
                }

                async function refreshCurrentProjectAfterActiveRunSettled() {
                  if (!state.projectId) return;
                  await Promise.allSettled([
                    loadRuns(),
                    loadGddMilestoneSteps(),
                    loadIterationPlan(),
                    loadPrototypeProgress(),
                    loadProjectPackages(),
                    refreshAssetInventoryAvailability(),
                    refreshGddOutlineStatus()
                  ]);
                }

                function scheduleActiveRunRefresh(attempts = 8, delayMs = 750, requireLocalBusy = true) {
                  let remaining = Math.max(1, attempts);
                  const tick = async () => {
                    await refreshActiveRun();
                    remaining -= 1;
                    if (remaining > 0 && state.authenticated && (!requireLocalBusy || state.localBusy || runIsBusy(state.activeRun) || hasPendingPrototypeSkeletonBannerRun())) {
                      window.setTimeout(tick, delayMs);
                    }
                  };
                  window.setTimeout(tick, delayMs);
                }

                let projectRunPollTimer = null;
                let projectRunPollId = "";
                let projectRunPollProjectId = "";
                let projectRunPollAuthEpoch = 0;

                function resultRunId(result) {
                  return result?.runId ||
                    result?.run?.runId ||
                    result?.stepExecution?.runId ||
                    result?.needsFixRun?.runId ||
                    result?.feedbackRun?.runId ||
                    "";
                }

                function stopProjectRunPolling(runId = "") {
                  if (runId && projectRunPollId && runId !== projectRunPollId) return;
                  if (projectRunPollTimer) window.clearInterval(projectRunPollTimer);
                  projectRunPollTimer = null;
                  projectRunPollId = "";
                  projectRunPollProjectId = "";
                  projectRunPollAuthEpoch = 0;
                }

                async function refreshProjectRun(runId, projectId = state.projectId, requestAuthEpoch = authEpoch) {
                  if (!runId || !projectId) return null;
                  if (state.cancelledActiveRunId === runId) return null;
                  try {
                    const result = await api(`/api/runs/${encodeURIComponent(runId)}`);
                    const run = result?.run || null;
                    if (!run) return null;
                    const actualProjectId = runProjectId(run) || projectId;
                    if (actualProjectId !== projectId || !isCurrentProjectRequest(projectId, requestAuthEpoch)) return run;
                    state.activeRun = run;
                    if (isPrototypeSkeletonCreationRun(run) && runBelongsToCurrentProject(run)) {
                      state.pendingPrototypeSkeletonRun = {
                        runId: run.runId,
                        projectId: actualProjectId,
                        busy: runIsBusy(run),
                        runType: run.runType,
                        status: run.status,
                        progressStep: run.progressStep,
                        progressLabel: run.progressLabel,
                        progressUpdatedUtc: run.progressUpdatedUtc
                      };
                      ensurePrototypeSkeletonBannerRun(state.pendingPrototypeSkeletonRun);
                    }
                    applyGlobalBusyState();
                    if (shouldAutoRefreshIterationPlan(run)) {
                      await loadIterationPlan();
                      await loadRuns();
                    }
                    if (!runIsBusy(run)) {
                      stopProjectRunPolling(runId);
                      if (state.activeRun?.runId === runId) state.activeRun = null;
                      if (state.localBusy) state.localBusy = false;
                      if (isPrototypeSkeletonCreationRun(run)) {
                        state.pendingPrototypeSkeletonRun = null;
                        resetPrototypeSkeletonBannerState(true);
                      }
                      applyGlobalBusyState();
                      await refreshCurrentProjectAfterActiveRunSettled();
                    }
                    return run;
                  } catch {
                    return null;
                  }
                }

                function startProjectRunPolling(runId, projectId = state.projectId, requestAuthEpoch = authEpoch) {
                  if (!runId || !projectId) return;
                  if (projectRunPollId === runId && projectRunPollTimer) return;
                  stopProjectRunPolling();
                  projectRunPollId = runId;
                  projectRunPollProjectId = projectId;
                  projectRunPollAuthEpoch = requestAuthEpoch;
                  void refreshProjectRun(runId, projectId, requestAuthEpoch);
                  projectRunPollTimer = window.setInterval(() => {
                    void refreshProjectRun(runId, projectId, requestAuthEpoch);
                  }, 2000);
                }

                async function trackProjectRunFromResult(result, projectId = state.projectId, requestAuthEpoch = authEpoch) {
                  const runId = resultRunId(result);
                  if (!runId) return "";
                  const run = await refreshProjectRun(runId, projectId, requestAuthEpoch);
                  if (run && !runIsBusy(run)) return runId;
                  startProjectRunPolling(runId, projectId, requestAuthEpoch);
                  return runId;
                }

                function stopGddMilestoneRunPolling(runId = "") {
                  stopProjectRunPolling(runId);
                }

                async function refreshGddMilestoneRun(runId, projectId = state.projectId, requestAuthEpoch = authEpoch) {
                  return await refreshProjectRun(runId, projectId, requestAuthEpoch);
                }

                function startGddMilestoneRunPolling(runId, projectId = state.projectId, requestAuthEpoch = authEpoch) {
                  startProjectRunPolling(runId, projectId, requestAuthEpoch);
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
                    $("draftImportStatus").textContent = draft?.failureCode ? `草稿分析失败：${publicErrorCode(draft.failureCode)}` : "";
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
                  const context = projectRequestContext();
                  const projectId = context.projectId;
                  const file = $("draftFile").files?.[0];
                  if (!file) return out("请先选择一个 txt 文件。");
                  setLocalBusy(true, "草稿分析中，请等待当前任务执行完毕。");
                  $("importDraft").textContent = "模型分析中...";
                  $("runPrototype").textContent = "草稿分析中..暂不可启动 M1.";
                  setButtonDisabledState($("importDraft"), true, "草稿分析中，请等待当前任务执行完毕。");
                  setButtonDisabledState($("runPrototype"), true, "草稿分析中，请等待当前任务执行完毕。");
                  $("draftImportStatus").className = "card muted";
                  $("draftImportStatus").textContent = "后端正在调用模型分析 txt 草稿，完成前不能启动原型创建。";
                  $("draftImportStatus").classList.remove("hidden");
                  try {
                    const form = new FormData();
                    form.append("draftFile", file);
                    form.append("model", $("globalModel").value || "gpt-5.5");
                    const response = await fetch(`/api/projects/${projectId}/prototype-drafts/analyze`, { method: "POST", body: form, headers: { "Authorization": `Bearer ${token()}` } });
                    const payload = await response.json();
                    if (!response.ok) throw payload;
                    if (!isCurrentProjectContext(context)) return;
                    applyDraftToForm(payload);
                    renderDraftImportStatus(payload);
                    out(payload);
                    await loadRuns();
                  } catch (error) {
                    if (!isCurrentProjectContext(context)) return;
                    $("draftImportStatus").className = "card muted";
                    $("draftImportStatus").textContent = `草稿分析失败：${publicErrorCode(error?.error || error?.failureCode || "unknown_error")}`;
                    $("draftImportStatus").classList.remove("hidden");
                    showError(error);
                  } finally {
                    if (!isCurrentProjectContext(context)) return;
                    try {
                      await refreshActiveRun();
                    } finally {
                      setLocalBusy(false);
                      resetPrototypeActionButtonsVisualState();
                      setButtonDisabledState($("runPrototype"), isGlobalBusy());
                      setButtonDisabledState($("importDraft"), false);
                      updateDraftImportButtonState();
                      resetPrototypeActionButtonsVisualState();
                      setButtonDisabledState($("runPrototype"), isGlobalBusy());
                      updatePrototypeSkeletonPackageButton();
                    }
                  }
                }

                function updateDraftImportButtonState() {
                  const file = $("draftFile")?.files?.[0];
                  const button = $("importDraft");
                  if (!button) return;
                  const canImport = !!state.projectId && !!file && !isGlobalBusy();
                  setButtonDisabledState(button, !canImport, "请选择一个 txt 文件后再分析草稿并回填。");
                  button.classList.toggle("import-draft-ready", canImport);
                }

                async function createProjectPackage() {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("请先选择一个项目。");
                  const context = projectRequestContext();
                  const projectId = context.projectId;
                  setLocalBusy(true, "打包项目文件中，请等待当前任务执行完毕。");
                  $("createProjectPackage").disabled = true;
                  $("createProjectPackage").textContent = "打包中...";
                  $("projectPackageStatus").className = "card muted";
                  $("projectPackageStatus").textContent = "正在生成只包含项目相关文件的压缩包。";
                  try {
                    const result = await api(`/api/projects/${projectId}/packages`, { method: "POST" });
                    if (!isCurrentProjectContext(context)) return;
                    out(result);
                    await trackProjectRunFromResult(result, projectId, context.authEpoch);
                    await loadRuns();
                    await loadProjectPackages();
                  } catch (error) {
                    if (!isCurrentProjectContext(context)) return;
                    const reason = publicErrorCode(error?.payload?.failureCode || error?.payload?.disabledReason || error?.payload?.error || error?.payload?.status || error?.message || "unknown_error");
                    $("projectPackageStatus").className = "card";
                    $("projectPackageStatus").textContent = `打包失败：${projectPackageDisabledText(reason)} (${reason})`;
                    showError(error);
                  }
                  finally {
                    if (!isCurrentProjectContext(context)) return;
                    try {
                      await loadProjectPackages();
                      await refreshActiveRun();
                    } finally {
                      setLocalBusy(false);
                      $("createProjectPackage").textContent = "打包项目文件";
                    }
                  }
                }

                async function loadProjectPackages() {
                  const projectId = state.projectId;
                  const requestAuthEpoch = authEpoch;
                  if (!projectId) {
                    renderProjectPackages({ canCreatePackage: false, disabledReason: "project_not_selected", packages: [] });
                    return;
                  }
                  try {
                    const result = await api(`/api/projects/${projectId}/packages`);
                    if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
                    state.packageList = result;
                    renderProjectPackages(result);
                    writeProjectStateCache({ packageList: result }, projectId);
                  } catch (error) {
                    if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
                    $("projectPackageStatus").className = "card muted";
                    $("projectPackageStatus").textContent = "项目文件包列表暂不可用。";
                  }
                }

                async function refreshPrototypeGddStatus() {
                  if (!$("prototypeGddStatus")) return false;
                  const projectId = state.projectId;
                  const requestAuthEpoch = authEpoch;
                  if (!projectId) {
                    $("prototypeGddStatus").className = "card muted";
                    $("prototypeGddStatus").textContent = "请先选择项目。";
                    setButtonDisabledState($("runPrototype"), true, "请先选择项目。");
                    return false;
                  }

                  try {
                    const result = await api(`/api/projects/${projectId}/gdd`);
                    if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return false;
                    let modulePlan = state.gddMilestoneSteps;
                    try {
                      modulePlan = await api(`/api/projects/${projectId}/gdd-milestone-steps/latest`);
                      if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return false;
                      state.gddMilestoneSteps = modulePlan;
                      v2RenderProgress();
                      v2RenderLeftProjectList();
                    } catch {}
                    const outlineIncomplete = modulePlan?.outlineComplete === false;
                    const incompleteSections = Array.isArray(modulePlan?.incompleteOutlineSections) ? modulePlan.incompleteOutlineSections : [];
                    $("prototypeGddStatus").className = "card";
                    $("prototypeGddStatus").innerHTML = `
                      <strong>已载入当前项目 GDD</strong>
                      <p class="muted">${escapeHtml(result.relativePath || "docs/gdd/GDD.md")} · ${escapeHtml(result.lastUpdatedUtc || "")} · ${escapeHtml(String(result.sizeBytes || 0))} bytes</p>
                      <p class="muted">游戏场景将只根据当前 GDD 创建；如需补充设计，请先回到“创建策划大纲”更新 GDD。</p>
                      ${outlineIncomplete ? `<p class="muted"><strong>当前策划大纲尚未补全：</strong>${escapeHtml(incompleteSections.slice(0, 5).join("、") || "存在未补全章节")}。补全后才能执行 M1 游戏场景。</p>` : ""}
                    `;
                    setButtonDisabledState(
                      $("runPrototype"),
                      prototypeSkeletonLocked() || isGlobalBusy() || outlineIncomplete,
                      prototypeSkeletonLocked() ? "游戏场景已验收通过，不能重复创建。" : isGlobalBusy() ? "项目有后台任务正在执行。" : outlineIncomplete ? "请先补全所有策划大纲章节。" : "");
                    if (prototypeSkeletonLocked() && $("runPrototype")) $("runPrototype").textContent = "M1 游戏场景已完成";
                    renderPrototypeM1SpecStatus();
                    return true;
                  } catch (error) {
                    if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return false;
                    $("prototypeGddStatus").className = "card muted";
                    $("prototypeGddStatus").textContent = "当前项目还没有 GDD。请先创建策划大纲；创建策划大纲时仍可导入参考文件，并会优先参考导入内容。";
                    setButtonDisabledState($("runPrototype"), true, "请先创建策划大纲。");
                    renderPrototypeM1SpecStatus();
                    return false;
                  }
                }

                async function loadGddMilestoneSteps() {
                  const projectId = state.projectId;
                  const requestAuthEpoch = authEpoch;
                  if (!projectId) {
                    state.gddMilestoneSteps = null;
                    state.gddMilestoneEvidence = {};
                    renderGddMilestoneSteps();
                    return;
                  }

                  try {
                    const result = await api(`/api/projects/${projectId}/gdd-milestone-steps/latest`);
                    if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
                    state.gddMilestoneSteps = result;
                    await loadGddMilestoneEvidence(result, projectId, requestAuthEpoch);
                    if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
                    const active = activeGddMilestoneStep(Array.isArray(result?.steps) ? result.steps : [], result);
                    if (!state.gddMilestoneManualSelection && active) {
                      state.selectedGddMilestoneStepId = active.stepId || "";
                    }
                    writeProjectStateCache({ gddMilestoneSteps: result, selectedGddMilestoneStepId: state.selectedGddMilestoneStepId, gddMilestoneManualSelection: state.gddMilestoneManualSelection }, projectId);
                  } catch (error) {
                    if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
                    state.gddMilestoneSteps = { status: "gdd_not_found", summary: "创建策划大纲后显示游戏模块。", steps: [] };
                    state.gddMilestoneEvidence = {};
                  }
                  renderGddMilestoneSteps();
                  renderPrototypeM1SpecStatus();
                  v2RenderProgress();
                  v2RenderLeftProjectList();
                }

                async function loadGddMilestoneEvidence(plan, projectId = state.projectId, requestAuthEpoch = authEpoch) {
                  const steps = Array.isArray(plan?.steps) ? plan.steps : [];
                  const evidence = { ...(state.gddMilestoneEvidence || {}) };
                  await Promise.all(steps.map(async step => {
                    const path = step?.latestEvidenceRelativePath || "";
                    if (!path || evidence[path]?.loaded) return;
                    try {
                      evidence[path] = { loaded: true, data: await api(`/api/projects/${encodeURIComponent(projectId)}/prototype-evidence?path=${encodeURIComponent(path)}`) };
                    } catch (error) {
                      evidence[path] = { loaded: true, error: error?.payload?.error || "prototype_evidence_unavailable" };
                    }
                  }));
                  if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
                  state.gddMilestoneEvidence = evidence;
                }

                function renderGddMilestoneSteps() {
                  const panel = $("gddMilestoneStepStatus");
                  if (!panel) return;
                  const plan = state.gddMilestoneSteps;
                  const steps = Array.isArray(plan?.steps) ? plan.steps : [];
                  const active = activeGddMilestoneStep(steps, plan);
                  const selected = selectedGddMilestoneStep(steps, active);
                  applyGddMilestoneActionState(selected, active);
                  if (!state.projectId) {
                    panel.className = "card muted";
                    panel.textContent = "选择项目后显示游戏模块。";
                    return;
                  }

                  if (!steps.length) {
                    panel.className = "card muted";
                    panel.textContent = plan?.summary || "创建策划大纲后显示游戏模块。";
                    return;
                  }

                  panel.className = "card";
                  const completedCount = steps.filter(step => gddMilestoneVisualState(step, active) === "done").length;
                  const activeIndex = active ? Math.max(0, steps.findIndex(step => step.stepId === active.stepId)) : steps.length;
                  const selectedIndex = selected ? Math.max(0, steps.findIndex(step => step.stepId === selected.stepId)) : -1;
                  const incompleteSections = Array.isArray(plan?.incompleteOutlineSections) ? plan.incompleteOutlineSections : [];
                  const outlineWarning = plan?.outlineComplete === false
                    ? `<p class="muted"><strong>当前策划大纲尚未补全：</strong>${escapeHtml(incompleteSections.slice(0, 5).join("、") || "存在未补全章节")}。补全后才能执行游戏模块和 M1 游戏场景。</p>`
                    : "";
                  panel.innerHTML = `
                    <div class="milestone-progress-shell">
                      <div class="milestone-progress-header">
                        <strong>当前模块执行进度</strong>
                        <div class="milestone-progress-actions">
                          <span class="muted">共 ${escapeHtml(String(steps.length))} 个模块 · 完成 ${escapeHtml(String(completedCount))} 个 · 当前 ${escapeHtml(active ? `模块 ${activeIndex + 1}` : "全部完成")}</span>
                          <button id="refreshGddMilestoneSteps" type="button" class="ghost" data-global-action="true">更新游戏模块内容</button>
                          <button id="createNewGddMilestoneRound" type="button" class="secondary" data-global-action="true">创建新一轮游戏模块</button>
                        </div>
                      </div>
                      <div class="milestone-progress-track">
                        ${steps.map((step, index) => renderGddMilestoneProgressButton(step, index, selected, active)).join("")}
                      </div>
                    </div>
                    ${outlineWarning}
                    ${selected ? renderGddMilestoneStepItem(selected, selectedIndex, active) : "<p class='muted'>所有模块已确认完成，可以创建新一轮游戏模块。</p>"}
                  `;
                  panel.querySelectorAll("[data-gdd-milestone-step-id]").forEach(button => {
                    button.onclick = () => selectGddMilestoneStep(button.dataset.gddMilestoneStepId || "", true);
                  });
                  panel.querySelector("[data-gdd-milestone-nav='previous']")?.addEventListener("click", () => selectGddMilestoneByOffset(-1));
                  panel.querySelector("[data-gdd-milestone-nav='next']")?.addEventListener("click", () => selectGddMilestoneByOffset(1));
                  panel.querySelector("#refreshGddMilestoneSteps")?.addEventListener("click", refreshGddMilestoneSteps);
                  panel.querySelector("#createNewGddMilestoneRound")?.addEventListener("click", () => openIterationPlanUpdateModal("new"));
                  applyGddMilestoneActionState(selected, active);
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
                      <span class="milestone-progress-label">模块 ${escapeHtml(String(index + 1))}</span>
                      <span class="milestone-status-square" aria-hidden="true"></span>
                    </button>
                  `;
                }

                function renderGddMilestoneStepItem(step, index, active) {
                  const status = step.locked ? "locked" : step.status || "ready";
                  const isActive = !!active && active.stepId === step.stepId;
                  const steps = Array.isArray(state.gddMilestoneSteps?.steps) ? state.gddMilestoneSteps.steps : [];
                  return `
                    <div class="milestone-detail ${step.locked || !isActive ? "muted" : ""}">
                      <strong>模块 ${escapeHtml(String(index + 1))} · ${escapeHtml(step.title || step.stepId || "")}</strong>
                      <p class="muted">状态：${escapeHtml(gddMilestoneStatusLabel(status, isActive))}</p>
                      <p>${escapeHtml(step.description || "")}</p>
                      ${renderStepSpecLine("本模块范围", step.scopeIn)}
                      ${renderStepSpecLine("暂不包含", step.scopeOut)}
                      ${renderStepSpecLine("Godot/C# 实现切片", step.godotSlice)}
                      ${renderStepSpecLine("反馈改进", step.feedbackGuidance)}
                      ${renderStepSpecLine("下一模块调整检查", step.nextStepReview)}
                      ${step.reviewSummary ? `<p class="muted">解锁前检查：${escapeHtml(step.reviewSummary)}</p>` : ""}
                      ${renderGddMilestoneResultPanel(step)}
                      ${renderGddMilestonePlaytestPanel(step)}
                      ${renderGddMilestoneEvidence(step)}
                      <div class="milestone-detail-nav">
                        <button type="button" class="ghost" data-gdd-milestone-nav="previous" ${index <= 0 ? "disabled" : ""}>上一个模块</button>
                        <span class="muted">${isActive ? "当前激活模块" : "非激活模块，仅可查看"}</span>
                        <button type="button" class="ghost" data-gdd-milestone-nav="next" ${index >= steps.length - 1 ? "disabled" : ""}>下一个模块</button>
                      </div>
                    </div>
                  `;
                }

                function renderGddMilestonePlaytestPanel(step) {
                  const acceptance = String(step?.acceptance || "").trim();
                  const packagingValidation = String(step?.packagingValidation || "").trim();
                  const acceptanceHtml = acceptance
                    ? `<p><strong>试玩验收：</strong>${escapeHtml(acceptance)}</p>`
                    : `<p class="muted">暂无单独试玩验收说明，请先补全该模块的大纲内容。</p>`;
                  const packageHtml = packagingValidation
                    ? `<p><strong>打包试玩：</strong>${escapeHtml(packagingValidation)}</p>`
                    : "";
                  return `
                    <div class="milestone-playtest-panel">
                      <strong>玩家试玩验收内容</strong>
                      ${acceptanceHtml}
                      ${packageHtml}
                    </div>
                  `;
                }

                function renderGddMilestoneResultPanel(step) {
                  const executionRun = String(step?.executionRunId || "").trim();
                  const feedbackRun = String(step?.feedbackRunId || "").trim();
                  const executionSummary = sanitizePublicFailureContent(step?.executionSummary || "");
                  const feedbackSummary = sanitizePublicFailureContent(step?.feedbackSummary || "");
                  const latestRun = feedbackRun || executionRun;
                  const latestSummary = feedbackSummary || executionSummary;
                  const status = gddMilestoneStatusLabel(step?.status || "ready", false);
                  const latestEvidence = String(step?.latestEvidenceRelativePath || "").trim();
                  const rows = [
                    ["模块状态", status],
                    ["最近 run", latestRun || "尚未执行"],
                    ["最近结果", latestSummary || "暂无执行结果摘要"],
                    ["执行 run", executionRun || "尚未执行"],
                    ["执行结果", executionSummary || "暂无执行结果摘要"],
                    ["反馈修复 run", feedbackRun || "尚未提交反馈修复"],
                    ["反馈修复结果", feedbackSummary || "暂无反馈修复结果摘要"],
                    ["自动验收证据", latestEvidence || "尚未生成"]
                  ];
                  return `
                    <div class="milestone-result-panel">
                      <strong>模块执行结果</strong>
                      <ul>
                        ${rows.map(([label, value]) => `<li><strong>${escapeHtml(label)}：</strong>${escapeHtml(value)}</li>`).join("")}
                      </ul>
                    </div>
                  `;
                }

                function renderGddMilestoneEvidence(step) {
                  const evidencePath = step?.latestEvidenceRelativePath || "";
                  const evidenceState = evidencePath ? state.gddMilestoneEvidence?.[evidencePath] : null;
                  const evidence = evidenceState?.data || null;
                  const checks = evidence?.checks || {};
                  const rows = [
                    ["build", checks.dotnetBuild],
                    ["godot import", checks.godotImport],
                    ["scene load", checks.headlessLoad],
                    ["milestone smoke", checks.milestoneSmoke],
                    ["asset validation", checks.assetValidation],
                    ["frame check", checks.frameCheck]
                  ];
                  const rowHtml = evidence
                    ? rows.map(([label, check]) => `<li><strong>${escapeHtml(label)}:</strong> ${escapeHtml(check?.status || "skipped")}${check?.reason ? ` · ${escapeHtml(check.reason)}` : ""}</li>`).join("")
                    : "";
                  const meta = evidence
                    ? `<p class="muted">status: ${escapeHtml(evidence.status || "unknown")} · run: ${escapeHtml(evidence.runId || "")}</p><ul class="milestone-evidence-list">${rowHtml}</ul>`
                    : evidenceState?.error
                      ? `<p class="muted">证据读取失败：${escapeHtml(evidenceState.error)}</p>`
                      : `<p class="muted">尚未读取结构化证据。</p>`;
                  return `
                    <details class="milestone-evidence">
                      <summary>自动验收证据</summary>
                      ${meta}
                      <p class="muted">latest evidence path: ${escapeHtml(evidencePath || "尚未生成")}</p>
                    </details>
                  `;
                }

                function gddMilestoneStatusLabel(status, isActive) {
                  const normalized = String(status || "").trim().toLowerCase();
                  if (normalized === "confirmed") return "完成";
                  if (isActive) return normalized === "executed" || normalized === "feedback_submitted" ? "等待确认完成" : "当前激活模块";
                  if (normalized === "locked") return "待执行";
                  return statusLabel(status);
                }

                function applyGddMilestoneActionState(selected, active) {
                  const canUse = !!state.projectId && !!selected && !!active && selected.stepId === active.stepId && !selected.locked && !isGlobalBusy();
                  const canSubmitFeedback = !!selected?.canSubmitFeedback || !!selected?.canConfirm;
                  const canCreateNewRound = !!state.projectId && !isGlobalBusy();
                  setButtonDisabledState($("refreshGddMilestoneSteps"), !state.projectId || isGlobalBusy(), "选择项目后可以更新游戏模块内容。");
                  setButtonDisabledState($("createNewGddMilestoneRound"), !canCreateNewRound, state.projectId ? "有任务正在执行，请等待当前任务完成后再创建新一轮。" : "请先选择项目。");
                  setButtonDisabledState($("executeCurrentMilestoneStep"), !(canUse && selected.canExecute), selected ? "只有当前激活模块可以执行。" : "没有可执行的当前模块。");
                  setButtonDisabledState($("quickRepairCurrentMilestoneStep"), !(canUse && canQuickRepairGddMilestoneStep(selected)), selected ? "只有当前激活模块存在失败执行结果时可以快速修复。" : "没有可快速修复的当前模块。");
                  setButtonDisabledState($("confirmCurrentMilestoneStep"), !(canUse && selected.canConfirm), selected ? "只有当前激活模块完成执行后可以确认。" : "没有可确认的当前模块。");
                  setButtonDisabledState($("submitCurrentMilestoneFeedback"), !(canUse && canSubmitFeedback), selected ? "只有当前激活模块可以提交反馈。" : "没有可反馈的当前模块。");
                }

                function canQuickRepairGddMilestoneStep(step) {
                  const status = String(step?.status || "").trim().toLowerCase();
                  return !!step?.canSubmitFeedback && ["needs_fix", "execution_failed", "feedback_failed", "timed_out"].includes(status);
                }

                function renderStepSpecLine(label, value) {
                  if (!value) return "";
                  return `<p class="muted"><strong>${escapeHtml(label)}：</strong>${escapeHtml(value)}</p>`;
                }

                function currentGddMilestoneStep() {
                  const plan = state.gddMilestoneSteps;
                  const steps = Array.isArray(plan?.steps) ? plan.steps : [];
                  return activeGddMilestoneStep(steps, plan);
                }

                function gddMilestoneActionRunId(result, fallbackStep = null) {
                  const directRunId = result?.stepExecution?.runId || result?.needsFixRun?.runId || result?.feedbackRun?.runId || "";
                  if (directRunId) return directRunId;
                  const stepId = String(result?.stepId || fallbackStep?.stepId || "").trim();
                  const steps = Array.isArray(result?.plan?.steps) ? result.plan.steps : [];
                  const matched = steps.find(step => stepId && String(step?.stepId || "").trim() === stepId) ||
                    steps.find(step => step?.executionRunId || step?.feedbackRunId);
                  return matched?.executionRunId || matched?.feedbackRunId || "";
                }

                async function executeCurrentMilestoneStep() {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("请先选择一个项目。");
                  const context = projectRequestContext();
                  const projectId = context.projectId;
                  const step = currentGddMilestoneStep();
                  if (!step) return out("当前没有可执行的游戏模块。");
                  setLocalBusy(true, "正在执行当前游戏模块。");
                  scheduleActiveRunRefresh();
                  try {
                    const result = await api(`/api/projects/${projectId}/gdd-milestone-steps/current/execute`, {
                      method: "POST",
                      timeoutMs: longLlmTimeoutMs,
                      body: JSON.stringify({})
                    });
                    if (!isCurrentProjectContext(context)) return;
                    out(result);
                    const actionRunId = gddMilestoneActionRunId(result, step);
                    if (actionRunId) {
                      await trackProjectRunFromResult({ runId: actionRunId }, projectId, context.authEpoch);
                    }
                    if (result.stepExecution) {
                      await loadIterationPlan();
                    }
                    await loadGddMilestoneSteps();
                  } catch (error) {
                    if (!isCurrentProjectContext(context)) return;
                    showError(error);
                  } finally {
                    if (!isCurrentProjectContext(context)) return;
                    try {
                      await refreshActiveRun();
                    } finally {
                      setLocalBusy(false);
                    }
                  }
                }

                async function refreshGddMilestoneSteps() {
                  if (!state.projectId) return out("请先选择一个项目。");
                  $("refreshGddMilestoneSteps").disabled = true;
                  $("refreshGddMilestoneSteps").textContent = "刷新中...";
                  try {
                    await loadGddMilestoneSteps();
                    out("游戏模块内容已更新。");
                  } catch (error) {
                    showError(error);
                  } finally {
                    if ($("refreshGddMilestoneSteps")) $("refreshGddMilestoneSteps").textContent = "更新游戏模块内容";
                    applyGddMilestoneActionState(selectedGddMilestoneStep(Array.isArray(state.gddMilestoneSteps?.steps) ? state.gddMilestoneSteps.steps : [], activeGddMilestoneStep(Array.isArray(state.gddMilestoneSteps?.steps) ? state.gddMilestoneSteps.steps : [], state.gddMilestoneSteps)), activeGddMilestoneStep(Array.isArray(state.gddMilestoneSteps?.steps) ? state.gddMilestoneSteps.steps : [], state.gddMilestoneSteps));
                  }
                }

                function buildQuickRepairFeedbackForMilestoneStep(step) {
                  const executionSummary = String(step?.executionSummary || "").trim();
                  const feedbackSummary = String(step?.feedbackSummary || "").trim();
                  const latestSummary = feedbackSummary || executionSummary || "当前模块执行失败或需要修复，但没有结构化摘要，请查看运行记录和自动验收证据。";
                  const lines = [
                    `请根据当前模块 ${String(step?.stepId || "").trim()} 的最近执行结果直接修复，不需要等待玩家额外描述。`,
                    `模块标题：${String(step?.title || "").trim()}`,
                    `模块状态：${String(step?.status || "").trim()}`,
                    `执行 run：${String(step?.executionRunId || "").trim() || "无"}`,
                    `反馈修复 run：${String(step?.feedbackRunId || "").trim() || "无"}`,
                    `自动验收证据：${String(step?.latestEvidenceRelativePath || "").trim() || "无"}`,
                    "最近执行结果：",
                    latestSummary,
                    feedbackSummary && executionSummary && feedbackSummary !== executionSummary ? `原始执行结果：\n${executionSummary}` : ""
                  ];
                  return lines.filter(Boolean).join("\\n");
                }

                async function quickRepairCurrentMilestoneStep() {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("请先选择一个项目。");
                  const context = projectRequestContext();
                  const projectId = context.projectId;
                  const step = currentGddMilestoneStep();
                  if (!step) return out("当前没有可快速修复的游戏模块。");
                  if (!canQuickRepairGddMilestoneStep(step)) return out("当前模块没有失败执行结果，不能快速修复。");
                  setLocalBusy(true, "正在根据当前模块执行结果启动快速修复。");
                  scheduleActiveRunRefresh();
                  try {
                    const result = await api(`/api/projects/${projectId}/gdd-milestone-steps/${encodeURIComponent(step.stepId)}/feedback-run`, {
                      method: "POST",
                      timeoutMs: longLlmTimeoutMs,
                      body: JSON.stringify({ feedback: buildQuickRepairFeedbackForMilestoneStep(step), model: $("globalModel").value || "gpt-5.5", sourceKind: "quick_repair" })
                    });
                    if (!isCurrentProjectContext(context)) return;
                    out(result);
                    const actionRunId = gddMilestoneActionRunId(result, step);
                    if (actionRunId) {
                      await trackProjectRunFromResult({ runId: actionRunId }, projectId, context.authEpoch);
                    }
                    state.gddMilestoneSteps = result.plan || state.gddMilestoneSteps;
                    renderGddMilestoneSteps();
                    await loadGddMilestoneSteps();
                    await loadRuns();
                  } catch (error) {
                    if (!isCurrentProjectContext(context)) return;
                    showError(error);
                  } finally {
                    if (!isCurrentProjectContext(context)) return;
                    try {
                      await refreshActiveRun();
                    } finally {
                      setLocalBusy(false);
                    }
                  }
                }

                async function confirmCurrentMilestoneStep() {
                  if (!guardGlobalAction()) return;
                  const step = currentGddMilestoneStep();
                  if (!state.projectId || !step) return out("当前没有可确认的游戏模块。");
                  if (!confirm(`建议先打包下载试玩验证 ${step.stepId}，但不是必需。确认完成后会解锁下一个模块，并触发下一模块解锁前检查。`)) return;
                  const context = projectRequestContext();
                  const projectId = context.projectId;
                  setLocalBusy(true, "正在确认当前模块并执行下一模块解锁前检查。");
                  scheduleActiveRunRefresh();
                  try {
                    const result = await api(`/api/projects/${projectId}/gdd-milestone-steps/${encodeURIComponent(step.stepId)}/confirm`, {
                      method: "POST",
                      body: JSON.stringify({ notes: "confirmed from browser", model: $("globalModel").value || "gpt-5.5" })
                    });
                    if (!isCurrentProjectContext(context)) return;
                    out(result);
                    state.gddMilestoneSteps = result.plan || state.gddMilestoneSteps;
                    state.selectedGddMilestoneStepId = result.plan?.currentStepId || "";
                    state.gddMilestoneManualSelection = false;
                    renderGddMilestoneSteps();
                    await loadGddMilestoneSteps();
                  } catch (error) {
                    if (!isCurrentProjectContext(context)) return;
                    showError(error);
                  } finally {
                    if (!isCurrentProjectContext(context)) return;
                    try {
                      await refreshActiveRun();
                    } finally {
                      setLocalBusy(false);
                    }
                  }
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
                  const context = projectRequestContext();
                  const projectId = context.projectId;
                  const feedback = $("milestoneFeedbackInput").value || "";
                  if (!feedback?.trim()) return;
                  setLocalBusy(true, "正在提交当前模块的反馈修复。");
                  scheduleActiveRunRefresh();
                  $("confirmMilestoneFeedback").disabled = true;
                  $("confirmMilestoneFeedback").textContent = "提交中...";
                  $("milestoneFeedbackHint").textContent = "正在根据当前模块反馈启动修复。";
                  try {
                    const result = await api(`/api/projects/${projectId}/gdd-milestone-steps/${encodeURIComponent(step.stepId)}/feedback-run`, {
                      method: "POST",
                      timeoutMs: longLlmTimeoutMs,
                      body: JSON.stringify({ feedback, model: $("globalModel").value || "gpt-5.5", sourceKind: "manual_feedback" })
                    });
                    if (!isCurrentProjectContext(context)) return;
                    out(result);
                    const actionRunId = gddMilestoneActionRunId(result, step);
                    if (actionRunId) {
                      await trackProjectRunFromResult({ runId: actionRunId }, projectId, context.authEpoch);
                    }
                    state.gddMilestoneSteps = result.plan || state.gddMilestoneSteps;
                    setModalVisible("milestoneFeedbackModal", false);
                    renderGddMilestoneSteps();
                    await loadGddMilestoneSteps();
                    await loadRuns();
                  } catch (error) {
                    if (!isCurrentProjectContext(context)) return;
                    $("milestoneFeedbackHint").textContent = "提交失败，请检查反馈内容或稍后重试。";
                    showError(error);
                  } finally {
                    if (!isCurrentProjectContext(context)) return;
                    try {
                      await refreshActiveRun();
                    } finally {
                      $("confirmMilestoneFeedback").disabled = false;
                      $("confirmMilestoneFeedback").textContent = "提交反馈并修正模块";
                      setLocalBusy(false);
                    }
                  }
                }

                function renderProjectPackages(result) {
                  const packages = result?.packages || [];
                  const canCreate = !!result?.canCreatePackage && !isGlobalBusy();
                  $("createProjectPackage").disabled = !canCreate;
                  $("createProjectPackage").title = canCreate ? "" : projectPackageDisabledText(result?.disabledReason);
                  updatePrototypeSkeletonPackageButton();
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
                  if (reason === "m1_not_completed") return "M1 游戏场景完成后才可以打包项目文件。";
                  if (reason === "project_busy") return "项目有后台任务正在执行，请等待完成。";
                  if (reason === "project_not_selected") return "请先选择一个项目。";
                  return "暂不可打包项目文件。";
                }

                function isProjectPackagePrerequisiteReason(reason) {
                  return reason === "prototype_not_created" || reason === "m1_not_completed";
                }

                async function refreshAssetInventoryAvailability() {
                  const projectId = state.projectId;
                  const requestAuthEpoch = authEpoch;
                  if (!projectId) {
                    state.assetInventory = null;
                    state.assetInventoryExpanded = false;
                    renderAssetInventory({ canReadInventory: false, disabledReason: "project_not_selected", usedAssets: [], generationCandidates: [] }, false);
                    return;
                  }
                  try {
                    const result = await api(`/api/projects/${projectId}/asset-inventory?judge=false`);
                    if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
                    state.assetInventory = result;
                    renderAssetInventory(result, state.assetInventoryExpanded);
                    writeProjectStateCache({ assetInventory: result }, projectId);
                  } catch {
                    if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
                    $("loadAssetInventory").disabled = true;
                    $("assetInventoryStatus").className = "card muted";
                    $("assetInventoryStatus").textContent = "项目素材库暂不可用。";
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
                    $("assetInventoryStatus").textContent = "选择项目后显示项目素材库入口。";
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
                    $("assetInventoryStatus").innerHTML = `<strong>项目素材库可用</strong><p class="muted">已识别 ${escapeHtml(String(usedAssets.length))} 个素材实例，${escapeHtml(String(candidates.length))} 个可生成素材候选。点击“查看项目素材库”展开。</p>`;
                    return;
                  }
                  $("assetInventoryStatus").className = "card";
                  $("assetInventoryStatus").innerHTML = `
                    <strong>项目素材库</strong>
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
                  if (reason === "final_step_not_completed") return "当前项目素材库还没有足够的可检查内容。";
                  if (reason === "project_not_selected") return "请先选择一个项目。";
                  return "项目素材库暂不可用。";
                }

                async function runPrototype() {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) {
                    showPrototypeNotice("请先选择一个项目。", "warn");
                    return out("请先选择一个项目。");
                  }
                  const projectId = state.projectId;
                  const requestAuthEpoch = authEpoch;
                  if (prototypeSkeletonLocked()) {
                    showPrototypeNotice("游戏场景已验收通过，不能重复创建。", "info");
                    setPrototypeFormLocked(true);
                    return out("游戏场景已验收通过，不能重复创建。");
                  }
                  const hasGdd = await refreshPrototypeGddStatus();
                  if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
                  if (!hasGdd) {
                    showPrototypeNotice("请先创建策划大纲，确认 GDD 后再创建游戏场景。", "warn");
                    return out({ status: "gdd_not_found" });
                  }
                  showPrototypeNotice("正在提交原型创建请求，请不要重复点击。", "info");
                  setLocalBusy(true, "游戏场景创建中，请等待当前任务执行完毕。");
                  setPrototypeFormLocked(true);
                  try {
                    const payload = {
                      confirm: true,
                      scoreEngine: "deterministic",
                      model: $("globalModel").value
                    };
                    const result = await api(`/api/projects/${projectId}/prototype-7day-playable/from-gdd`, { method: "POST", body: JSON.stringify(payload) });
                    if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
                    out(result);
                    if (result?.runId) {
                      state.pendingPrototypeSkeletonRun = {
                        runId: result.runId,
                        projectId,
                        busy: true,
                        runType: "prototype-7day-playable",
                        progressStep: "queued",
                        progressLabel: "已提交，等待 runner。",
                        progressUpdatedUtc: new Date().toISOString()
                      };
                      ensurePrototypeSkeletonBannerRun(state.pendingPrototypeSkeletonRun);
                      writePrototypeSkeletonBannerState();
                      applyGlobalBusyState();
                      await refreshPrototypeSkeletonRun(result.runId, projectId, requestAuthEpoch);
                    }
                    if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
                    showPrototypeNotice(`原型创建请求已提交，状态：${result.status || "queued"}。刷新页面可继续查看创建进度。`, "info");
                    await loadRuns();
                    await loadPrototypeProgress();
                    await loadServerChatHistoryForProject(projectId, requestAuthEpoch);
                    try {
                      await refreshActiveRun();
                    } finally {
                      setLocalBusy(false);
                    }
                  } catch (error) {
                    if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
                    setLocalBusy(false);
                    setPrototypeFormLocked(false);
                    state.pendingPrototypeSkeletonRun = null;
                    showPrototypeError(error);
                    showError(error);
                  }
                }

                async function refreshPrototypeSkeletonRun(runId, projectId = state.projectId, requestAuthEpoch = authEpoch) {
                  if (!runId || !projectId) return;
                  if (state.cancelledActiveRunId === runId) return;
                  try {
                    const result = await api(`/api/runs/${encodeURIComponent(runId)}`);
                    const run = result?.run || null;
                    if (!run) return;
                    const actualProjectId = runProjectId(run) || projectId;
                    if (actualProjectId !== projectId || !isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
                    state.pendingPrototypeSkeletonRun = {
                      runId: run.runId,
                      projectId: actualProjectId,
                      busy: runIsBusy(run),
                      runType: run.runType,
                      status: run.status,
                      progressStep: run.progressStep,
                      progressLabel: run.progressLabel,
                      progressUpdatedUtc: run.progressUpdatedUtc
                    };
                    state.activeRun = run;
                    applyGlobalBusyState();
                    if (!runIsBusy(run)) {
                      if (state.activeRun?.runId === runId) state.activeRun = null;
                      state.pendingPrototypeSkeletonRun = null;
                      resetPrototypeSkeletonBannerState(true);
                      applyGlobalBusyState();
                      if (String(run.status || "").toLowerCase() === "succeeded" && isCurrentProjectRequest(projectId, requestAuthEpoch)) {
                        await validatePrototypeSkeleton(true);
                      }
                    }
                  } catch {
                    // keep last visible banner state if the polling fails
                  }
                }

                function buildPrototypePayload() {
                  return {
                    slug: $("protoSlug").value.trim(),
                    gameType: $("gameTypeSource").value.trim(),
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
                      ? `缺少必填项：${missing.map(prototypeFieldLabel).join("、")}。请先更新 GDD 后再创建游戏场景。`
                      : payload.status === "project_busy"
                        ? "当前项目已有后台任务在执行，请等待顶部状态条消失后再启动游戏场景创建。"
                    : payload.status === "gdd_not_found" || payload.failureCode === "gdd_not_found"
                      ? "请先创建策划大纲，确认 GDD 后再创建游戏场景。"
                    : payload.failureCode === "prototype_valid_godot_scene_missing"
                      ? "没有创建有效的godot场景文件"
                      : `原型创建请求失败：${publicErrorCode(payload.status || payload.error || payload.failureCode || error?.status || "unknown_error")}`;
                  showPrototypeNotice(message, "warn");
                }


                async function repairPrototype() {
                  await createRepairPlan();
                }

                async function validatePrototype() {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("请先选择一个项目。");
                  const context = projectRequestContext();
                  const projectId = context.projectId;
                  setLocalBusy(true, "原型重新验收中，请等待当前任务执行完毕。");
                  $("validatePrototype").textContent = "验收中...";
                  showPrototypeNotice("正在重新验收当前原型；该操作会运行平台验收、Godot smoke 和项目专属行为验收，不会触发生成流程。", "info");
                  try {
                    const result = await api(`/api/projects/${projectId}/prototype-7day-playable/validate`, { method: "POST" });
                    if (!isCurrentProjectContext(context)) return;
                    out(result);
                    await trackProjectRunFromResult(result, projectId, context.authEpoch);
                    await loadRuns();
                    await loadPrototypeProgress();
                    await loadProjectPackages();
                    await refreshAssetInventoryAvailability();
                    if (result.status === "failed") {
                      const label = result.progress?.label || result.stderr || "原型项目验收失败，请查看运行记录并生成修复计划。";
                      showPrototypeNotice(label, "warn");
                    }
                  } catch (error) {
                    if (!isCurrentProjectContext(context)) return;
                    showError(error);
                    await loadPrototypeProgress();
                  } finally {
                    if (!isCurrentProjectContext(context)) return;
                    try {
                      await refreshActiveRun();
                    } finally {
                      setLocalBusy(false);
                      $("validatePrototype").textContent = "重新触发原型项目验收";
                    }
                  }
                }

                async function loadPrototypeProgress() {
                  const projectId = state.projectId;
                  const requestAuthEpoch = authEpoch;
                  if (!projectId) {
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
                    const progress = await api(`/api/projects/${projectId}/prototype-7day-playable/progress`);
                    if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
                    const currentProjectCancelled = !!state.cancelledActiveRunId && state.cancelledActiveRunProjectId === projectId;
                    if (currentProjectCancelled || readCancelledPrototypeMarker(projectId)) {
                      const creationStatus = String(progress?.prototypeCreationStatus || progress?.status || "").trim().toLowerCase();
                      if (["queued", "running"].includes(creationStatus)) {
                        state.v2PrototypeCreationStatus = "idle";
                        state.prototypeFailure = "";
                        renderPrototypeProgress(cancelledPrototypeProgressSnapshot());
                        setPrototypeFormLocked(false);
                        if ($("draftFile")) $("draftFile").disabled = true;
                        writeProjectStateCache({ prototypeProgress: cancelledPrototypeProgressSnapshot() }, projectId);
                        return;
                      }
                      clearCancelledPrototypeMarker(projectId);
                    }
                    const acceptanceStatus = String(progress?.acceptanceStatus || progress?.status || "").trim().toLowerCase();
                    state.v2PrototypeStatus = progress?.status || "";
                    state.v2PrototypeCreationStatus = progress?.prototypeCreationStatus || progress?.status || "";
                    state.v2PrototypeAcceptanceStatus = progress?.acceptanceStatus || "";
                    state.prototypeFailure = acceptanceStatus === "failed" ? (progress.acceptanceFailure || progress.failure || "") : "";
                    if (acceptanceStatus === "succeeded") {
                      callV2("v2SetPrototypeValidationInvalidated", false);
                    }
                    renderPrototypeProgress(progress);
                    renderPrototypeAcceptanceSummary(progress);
                    setPrototypeFormLocked(isPrototypeCreationLocked(progress));
                    renderPrototypeM1SpecStatus();
                    updateChatPanelVisibility(progress);
                    writeProjectStateCache({ prototypeProgress: progress }, projectId);
                  } catch (error) {
                    if (!isCurrentProjectRequest(projectId, requestAuthEpoch)) return;
                    showError(error);
                  }
                }

                function renderPrototypeProgress(progress) {
                  const status = progress.status || "idle";
                  const statusClass = status === "succeeded" ? "status-ok" : status === "failed" ? "status-fail" : "status-warn";
                  $("prototypeProgress").className = "card";
                  $("prototypeProgress").innerHTML = `
                    <strong class="${statusClass}">${escapeHtml(publicStatusLabel(status))}</strong>
                    <p>${escapeHtml(progress.label || "")}</p>
                    <p class="muted">任务：${escapeHtml(progress.step || "-")} · 子任务：${escapeHtml(progress.substep || "-")}</p>
                    ${progress.updatedUtc ? `<p class="muted">更新时间：${escapeHtml(progress.updatedUtc)}</p>` : ""}
                    ${progress.failure ? `<p class="danger">${escapeHtml(sanitizePublicFailureContent(progress.failure))}</p><p class="danger">可以点击“生成修复计划”把失败拆成小步骤，再逐项执行修复。</p>` : ""}
                  `;
                  $("repairPrototype")?.classList.toggle("hidden", true);
                }

                function renderPrototypeAcceptanceSummary(progress) {
                  const status = progress?.status || "idle";
                  if (status === "failed") {
                    const failure = sanitizePublicFailureContent(progress?.failure || "原型项目验收未通过。");
                    $("prototypeAcceptanceSummary").className = "card";
                    $("prototypeAcceptanceSummary").innerHTML = `
                      <strong>原型项目验收摘要</strong>
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
                    <strong>原型项目验收摘要</strong>
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
                  const routeGoal = latestNeedsFixRouteGoalForAction();
                  $("submitFormalFeedback").disabled = !canSubmit;
                  $("submitFormalFeedback").textContent = !canSubmit
                    ? "需先完成游戏场景创建后才能提交反馈"
                    : routeGoal
                      ? `提交到需要修复路由任务 ${String(routeGoal.goalIndex || "")}`
                      : "提交反馈到需要修复路由";
                  if (typeof updatePrototypeSkeletonPackageButton === "function") updatePrototypeSkeletonPackageButton();
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
                    return `下一步建议来源：${formatNextStepSource(progress?.nextStepSource)}\n继续优化评估：${formatNextStepEvaluation(progress?.nextStepEvaluation)}\n${String(progress?.nextStepEvaluationReason || "").trim()}\n\n原型创建完成。\n\n本次完成：\n1. 已生成可玩的原型基础版本。\n2. 已完成基础启动检查。\n3. 已进入可继续优化状态。\n\n下一步建议：\n${suggestion}\n\n如需执行，请使用游戏模块或需要修复的固定功能按钮。`.trim();
                  }
                  if (status === "failed") {
                    return "原型创建未完成。你可以描述看到的问题，我可以帮你整理修复思路；需要执行修复时，请使用固定的修复按钮。";
                  }
                  return "原型流程已有进度。你可以继续说明目标或补充需求，我会按当前项目上下文协助梳理。";
                }

                function formatNextStepSource(value) {
                  const normalized = String(value || "").trim().toLowerCase();
                  if (normalized === "codex") return "生成结果";
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

                function iterationPlanDecision(evaluation = state.iterationPlanEvaluation) {
                  return String(evaluation?.decision || "").trim().toLowerCase();
                }

                function currentIterationPlanDecision() {
                  return iterationPlanDecision(state.iterationPlanEvaluation);
                }

                function latestIterationPlanDecision() {
                  return iterationPlanDecision(latestIterationPlanEvaluationForAction());
                }

                function iterationPlanRegenerationPrompt(evaluation = state.iterationPlanEvaluation) {
                  const decision = iterationPlanDecision(evaluation);
                  if (decision !== "should_refine_plan") return "";
                  return String(evaluation?.suggestedPromptForRegeneration || "").trim();
                }

                function currentIterationPlanRegenerationPrompt() {
                  return iterationPlanRegenerationPrompt(state.iterationPlanEvaluation);
                }

                function latestIterationPlanRegenerationPrompt() {
                  return iterationPlanRegenerationPrompt(latestIterationPlanEvaluationForAction());
                }

                function syncIterationPlanRegenerationSuggestion(evaluation = state.iterationPlanEvaluation) {
                  const suggestion = iterationPlanRegenerationPrompt(evaluation);
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
                  const acceptanceStatus = String(progress?.acceptanceStatus || progress?.status || "").trim().toLowerCase();
                  if (acceptanceStatus === "succeeded" || prototypeSkeletonLocked()) return true;
                  const status = String(progress?.prototypeCreationStatus || progress?.status || "idle").trim().toLowerCase();
                  return !["idle", "failed", "cancel"].includes(status);
                }

                function setPrototypeFormLocked(locked) {
                  prototypeInputIds.forEach(id => $(id).disabled = locked);
                  setPrototypeDraftFileLocked(locked);
                  if (!locked) {
                    resetPrototypeActionButtonsVisualState();
                  }
                  if ($("runPrototype")) {
                    const lockedReason = state.prototypeReadyForFeedback ? "游戏场景已验收通过，不能重复创建。" : "游戏场景创建中，请等待当前任务执行完毕。";
                    setButtonDisabledState($("runPrototype"), locked || isGlobalBusy(), locked ? lockedReason : "");
                    $("runPrototype").textContent = locked
                      ? state.prototypeReadyForFeedback ? "M1 游戏场景已完成" : "M1 游戏场景执行中..刷新页面查阅进度."
                      : "确认 GDD 无误，执行 M1 游戏场景";
                  }
                  updatePrototypeSkeletonPackageButton();
                  if ($("importDraft")) {
                    $("importDraft").textContent = locked ? "模型分析中..." : "分析草稿并回填";
                  }
                  if ($("repairPrototype")) {
                    setButtonDisabledState($("repairPrototype"), locked || isGlobalBusy(), locked ? "修复计划处理中，请等待当前任务执行完毕。" : "");
                    $("repairPrototype").textContent = locked ? "修复计划处理中..刷新页面查阅进度." : "生成修复计划";
                  }
                  updateDraftImportButtonState();
                }

                async function runTdd(stage) {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("请先选择一个项目。");
                  const context = projectRequestContext();
                  const projectId = context.projectId;
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
                    const result = await api(`/api/projects/${projectId}/prototype-tdd`, { method: "POST", body: JSON.stringify(payload) });
                    if (!isCurrentProjectContext(context)) return;
                    out(result);
                    await trackProjectRunFromResult(result, projectId, context.authEpoch);
                    await loadRuns();
                  } catch (error) {
                    if (!isCurrentProjectContext(context)) return;
                    showError(error);
                  }
                  finally {
                    if (!isCurrentProjectContext(context)) return;
                    try {
                      await refreshActiveRun();
                    } finally {
                      setLocalBusy(false);
                    }
                  }
                }

                async function createScene() {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("请先选择一个项目。");
                  const context = projectRequestContext();
                  const projectId = context.projectId;
                  setLocalBusy(true, "原型场景创建中，请等待当前任务执行完毕。");
                  try {
                    const sceneSlug = $("tddSlug").value.trim() || $("protoSlug").value.trim();
                    const prototypePayload = { ...buildPrototypePayload(), slug: sceneSlug };
                    const payload = {
                      slug: sceneSlug,
                      sceneRoot: $("sceneRoot").value.trim() || "Node2D",
                      gameType: prototypePayload.gameType,
                      hypothesis: prototypePayload.hypothesis,
                      corePlayerFantasy: prototypePayload.corePlayerFantasy,
                      minimumPlayableLoop: prototypePayload.minimumPlayableLoop,
                      gameFeature: prototypePayload.gameFeature,
                      coreGameplayLoop: prototypePayload.coreGameplayLoop,
                      winFailConditions: prototypePayload.winFailConditions
                    };
                    const result = await api(`/api/projects/${projectId}/prototype-scene`, { method: "POST", body: JSON.stringify(payload) });
                    if (!isCurrentProjectContext(context)) return;
                    out(result);
                    await trackProjectRunFromResult(result, projectId, context.authEpoch);
                    await loadRuns();
                  } catch (error) {
                    if (!isCurrentProjectContext(context)) return;
                    showError(error);
                  }
                  finally {
                    if (!isCurrentProjectContext(context)) return;
                    try {
                      await refreshActiveRun();
                    } finally {
                      setLocalBusy(false);
                    }
                  }
                }

                function showError(error) {
                  out(error && error.payload ? { status: error.status, ...error.payload } : String(error));
                }

                function escapeHtml(value) {
                  return String(value || "").replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#039;" }[ch]));
                }

                $("saveToken").onclick = () => {
                  const value = rawTokenInput();
                  bumpAuthEpoch();
                  recordSessionProbe("save_token_clicked", { hasValue: !!value });
                  if (!value) {
                    clearAccessTokenStorage();
                    $("sessionStatus").textContent = "Token 已清空。";
                    recordSessionProbe("token_cleared_from_empty_save");
                    showLoggedOut();
                    return;
                  }
                  persistAccessToken(value);
                  updateSessionDiagnostics("save_token");
                  $("sessionStatus").textContent = "Token 验证中...";
                  refreshProjects();
                };
                $("token").addEventListener("input", () => {
                  bumpAuthEpoch();
                  persistTokenInputFromBrowser("input");
                });
                $("token").addEventListener("change", () => {
                  bumpAuthEpoch();
                  persistTokenInputFromBrowser("change");
                });
                $("logout").onclick = () => {
                  bumpAuthEpoch();
                  recordSessionProbe("logout_clicked");
                  clearAccessTokenStorage();
                  $("token").value = "";
                  updateSessionDiagnostics("logout");
                  state.projectId = "";
                  writeSelectedProjectId("");
                  state.projects = [];
                  showLoggedOut();
                };
                runStartupSessionRestore();
                $("openCreateProjectPage").onclick = () => showCreateProjectPage();
                $("openProjectListModal").onclick = async () => {
                  if (projectSwitchLocked() && state.projectId) return out("当前操作完成前不能切换项目。");
                  setModalVisible("projectListModal", true);
                  await refreshProjects({ autoSelect: false });
                };
                $("closeProjectListModal").onclick = () => setModalVisible("projectListModal", false);
                $("refreshProjects").onclick = () => {
                  if (projectSwitchLocked() && state.projectId) return out("当前操作完成前不能切换项目。");
                  return refreshProjects({ autoSelect: false });
                };
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
                $("confirmGddQuestionForm").onclick = confirmGddQuestionForm;
                $("cancelGddQuestionForm").onclick = closeGddQuestionFormModal;
                $("syncChatHistory").onclick = syncChatHistory;
                $("downloadChatHistory").onclick = downloadChatHistory;
                $("chatAttachmentFiles").onchange = loadChatAttachmentFiles;
                $("clearChatAttachments").onclick = clearChatAttachments;
                runStartupStep("renderChatAttachments", renderChatAttachments);
                $("evaluateIterationPlanFromChat").onclick = () => evaluateIterationPlan(true);
                $("submitFormalFeedback").onclick = submitFormalFeedback;
                $("createIterationPlan").onclick = createIterationPlan;
                $("deleteIterationPlan").onclick = deleteIterationPlan;
                $("evaluateIterationPlan").onclick = () => evaluateIterationPlan(false);
                $("executeIterationGoal").onclick = executeIterationGoal;
                $("confirmIterationPlanUpdate").onclick = confirmIterationPlanUpdate;
                $("closeIterationPlanUpdateModal").onclick = () => setModalVisible("iterationPlanUpdateModal", false);
                $("iterationPlanUpdateInput").addEventListener("input", event => autoGrowTextarea(event.target));
                $("confirmMilestoneFeedback").onclick = submitCurrentMilestoneFeedback;
                $("closeMilestoneFeedbackModal").onclick = () => setModalVisible("milestoneFeedbackModal", false);
                $("milestoneFeedbackInput").addEventListener("input", event => autoGrowTextarea(event.target));
                $("createRepairPlan").onclick = createRepairPlan;
                $("executeRepairStep").onclick = executeRepairStep;
                $("executeCurrentMilestoneStep").onclick = executeCurrentMilestoneStep;
                $("quickRepairCurrentMilestoneStep").onclick = quickRepairCurrentMilestoneStep;
                $("confirmCurrentMilestoneStep").onclick = confirmCurrentMilestoneStep;
                $("submitCurrentMilestoneFeedback").onclick = openCurrentMilestoneFeedbackModal;
                $("chatSkillMode").onchange = () => {
                  renderSelectedSkillAction();
                  callV2("v2WriteProjectUiState");
                };
                window.addEventListener("beforeunload", () => {
                  callV2("v2WriteProjectUiState");
                });
                installClientErrorRecovery();
                window.addEventListener("message", event => {
                  if (event.origin !== location.origin) return;
                  if (event.data?.projectId && event.data.projectId !== state.projectId) return;
                  if (event.data?.type === "phasea:gdd-outline-deleted") {
                    state.gddOutlineReady = false;
                    if ($("createGddDocument")) $("createGddDocument").textContent = "\u521b\u5efa\u7b56\u5212\u5927\u7eb2";
                    refreshGddOutlineStatus();
                    return;
                  }
                  if (event.data?.type === "phasea:gdd-modules-refresh") {
                    loadGddMilestoneSteps();
                    return;
                  }
                  if (event.data?.type === "phasea:active-run-refresh") {
                    const eventRunId = String(event.data?.runId || "").trim();
                    const eventProjectId = String(event.data?.projectId || state.projectId || "").trim();
                    if (eventRunId && eventProjectId) {
                      startProjectRunPolling(eventRunId, eventProjectId, authEpoch);
                    }
                    void refreshActiveRun();
                    scheduleActiveRunRefresh(8, 750, false);
                  }
                });
                runStartupStep("renderChatHistory", renderChatHistory);
                runStartupStep("restorePrototypeSkeletonBannerFromStorage", restorePrototypeSkeletonBannerFromStorage);
                void refreshActiveRun();
                $("loadRuns").onclick = loadRuns;
                $("createProjectPackage").onclick = createProjectPackage;
                $("packagePrototypeSkeleton").onclick = createProjectPackage;
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
                runStartupSessionRestore();
                setInterval(refreshActiveRun, 5000);
                setInterval(() => {
                  const skeletonRun = skeletonBannerRun();
                  if (!skeletonRun?.runId) return;
                  ensurePrototypeSkeletonBannerRun(skeletonRun);
                  state.prototypeSkeletonBannerTick += 1;
                  const changed = syncPrototypeSkeletonBannerDisplayedCount();
                  writePrototypeSkeletonBannerState();
                  if (changed) applyGlobalBusyState();
                }, 5000);
                setInterval(() => {
                  const skeletonRun = skeletonBannerRun();
                  if (!skeletonRun?.runId) return;
                  refreshPrototypeSkeletonRun(skeletonRun.runId, runProjectId(skeletonRun) || state.projectId);
                }, 5000);
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
              .detail-progress { display: grid; grid-template-columns: repeat(7, minmax(5.6rem, 1fr)); gap: 0.5rem; overflow-x: auto; padding-bottom: 0.2rem; }
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
        var latestPrototype = runs
            .Where(run => string.Equals(run.RunType, "prototype-7day-playable", StringComparison.OrdinalIgnoreCase) &&
                          !IsAnyValidationOnlyRun(run))
            .OrderByDescending(RunSortTimeUtc)
            .ThenByDescending(run => run.RunId, StringComparer.Ordinal)
            .FirstOrDefault();
        var latestSkeletonValidation = runs
            .Where(run => string.Equals(run.RunType, "prototype-7day-playable", StringComparison.OrdinalIgnoreCase) &&
                          IsSkeletonValidationOnlyRun(run))
            .OrderByDescending(RunSortTimeUtc)
            .ThenByDescending(run => run.RunId, StringComparer.Ordinal)
            .FirstOrDefault();
        var latestRepair = LatestRun(runs, "prototype-repair-step", "prototype-quick-fix");
        var latestIteration = LatestRun(runs, "prototype-iteration-goal", "prototype-feedback-iteration");
        var latestGoalRepair = LatestGoalRepairRun(runs);
        var latestAssetInventory = LatestRun(runs, "project-asset-inventory");
        var latestPackage = LatestRun(runs, "project-package");
        var firstMilestoneCompleted = IsFirstGddMilestoneCompleted(project);
        var skeletonValidationSucceeded = string.Equals(latestSkeletonValidation?.Status, "succeeded", StringComparison.OrdinalIgnoreCase);
        var prototypeFailed = !firstMilestoneCompleted &&
                              !skeletonValidationSucceeded &&
                              (string.Equals(latestSkeletonValidation?.Status, "failed", StringComparison.OrdinalIgnoreCase) ||
                               string.Equals(latestPrototype?.Status, "failed", StringComparison.OrdinalIgnoreCase));
        var prototypeSucceeded = firstMilestoneCompleted ||
                                 skeletonValidationSucceeded ||
                                 string.Equals(latestPrototype?.Status, "succeeded", StringComparison.OrdinalIgnoreCase);
        var prototypeStepRun = skeletonValidationSucceeded
            ? latestSkeletonValidation
            : latestPrototype;

        return
        [
            new ProjectDetailStep(1, "游戏项目概述", "done", "/", "✓"),
            firstMilestoneCompleted
                ? new ProjectDetailStep(2, "游戏场景创建", "done", "/#prototypeWorkflowPanel", "✓")
                : CreateRunStep(2, "游戏场景创建", prototypeStepRun, "/#prototypeWorkflowPanel"),
            firstMilestoneCompleted
                ? new ProjectDetailStep(3, "场景验收修复", "done", "/#v2RepairPanel", "✓")
                : prototypeFailed && latestRepair is null
                ? new ProjectDetailStep(3, "场景验收修复", "fix", "/#v2RepairPanel", "×")
                : latestRepair is not null
                    ? CreateRunStep(3, "场景验收修复", latestRepair, "/#v2RepairPanel")
                    : prototypeSucceeded
                        ? new ProjectDetailStep(3, "场景验收修复", "done", "/#v2RepairPanel", "✓")
                        : CreateRunStep(3, "场景验收修复", latestRepair, "/#v2RepairPanel"),
            CreateIterationStep(4, latestIteration, latestGoalRepair, "/#v2IterationPanel"),
            CreateAcceptanceStep(5, runs, latestIteration, latestGoalRepair, "/#v2AcceptancePanel"),
            CreateRunStep(6, "项目素材库", latestAssetInventory, $"/assets?projectId={Uri.EscapeDataString(project.ProjectId)}"),
            CreateRunStep(7, "打包下载项目", latestPackage, $"/downloads?projectId={Uri.EscapeDataString(project.ProjectId)}")
        ];
    }

    private static bool IsFirstGddMilestoneCompleted(ProjectSnapshot project)
    {
        var path = Path.Combine(project.MetaPath, "routes", "gdd-milestones", "latest.json");
        if (!File.Exists(path))
        {
            return false;
        }

        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(path, Encoding.UTF8));
            if (!document.RootElement.TryGetProperty("steps", out var steps) ||
                steps.ValueKind != JsonValueKind.Array)
            {
                return false;
            }

            JsonElement? first = null;
            foreach (var step in steps.EnumerateArray())
            {
                var stepId = step.TryGetProperty("stepId", out var stepIdElement)
                    ? stepIdElement.GetString()
                    : null;
                if (string.Equals(stepId, "M1", StringComparison.OrdinalIgnoreCase))
                {
                    first = step;
                    break;
                }

                first ??= step;
            }

            if (first is null)
            {
                return false;
            }

            var status = first.Value.TryGetProperty("status", out var statusElement)
                ? statusElement.GetString()
                : "";
            var confirmedUtc = first.Value.TryGetProperty("confirmedUtc", out var confirmedUtcElement)
                ? confirmedUtcElement.GetString()
                : "";
            return !string.IsNullOrWhiteSpace(confirmedUtc) ||
                   IsCompletedMilestoneStatus(status);
        }
        catch (IOException)
        {
            return false;
        }
        catch (JsonException)
        {
            return false;
        }
    }

    private static bool IsCompletedMilestoneStatus(string? status)
    {
        return string.Equals(status, "confirmed", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(status, "completed", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(status, "succeeded", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(status, "executed", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(status, "feedback_submitted", StringComparison.OrdinalIgnoreCase);
    }

    private static ProjectDetailStep CreateAcceptanceStep(
        int number,
        IReadOnlyList<RunReadbackItem> runs,
        RunReadbackItem? latestIterationRun,
        RunReadbackItem? latestGoalRepair,
        string href)
    {
        var latestValidation = runs
            .Where(run => string.Equals(run.RunType, "prototype-7day-playable", StringComparison.OrdinalIgnoreCase) &&
                          IsValidationOnlyRun(run))
            .OrderByDescending(RunSortTimeUtc)
            .ThenByDescending(run => run.RunId, StringComparer.Ordinal)
            .FirstOrDefault();
        var effectiveIterationBoundary = EffectiveIterationAcceptanceBoundary(latestIterationRun, latestGoalRepair);
        if (latestValidation is null ||
            effectiveIterationBoundary is null ||
            RunSortTimeUtc(latestValidation) < RunSortTimeUtc(effectiveIterationBoundary))
        {
            return new ProjectDetailStep(number, "原型项目验收", "pending", href, "");
        }

        return latestValidation.Status switch
        {
            "succeeded" => new ProjectDetailStep(number, "原型项目验收", "done", href, "✓"),
            "failed" => new ProjectDetailStep(number, "原型项目验收", "fix", href, "×"),
            _ => new ProjectDetailStep(number, "原型项目验收", "pending", href, "")
        };
    }

    private static RunReadbackItem? EffectiveIterationAcceptanceBoundary(RunReadbackItem? latestIterationRun, RunReadbackItem? latestGoalRepair)
    {
        RunReadbackItem? boundary = null;
        if (string.Equals(latestIterationRun?.Status, "succeeded", StringComparison.OrdinalIgnoreCase))
        {
            boundary = latestIterationRun;
        }

        if (latestIterationRun is not null &&
            IsSucceededGoalRepair(latestGoalRepair) &&
            RunSortTimeUtc(latestGoalRepair!) >= RunSortTimeUtc(latestIterationRun))
        {
            boundary = latestGoalRepair;
        }

        return boundary;
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

    private static ProjectDetailStep CreateIterationStep(int number, RunReadbackItem? latestIteration, RunReadbackItem? latestGoalRepair, string href)
    {
        if (latestGoalRepair is not null &&
            (latestIteration is null || RunSortTimeUtc(latestGoalRepair) >= RunSortTimeUtc(latestIteration)))
        {
            var repairStatus = ReadStringFromEvidence(latestGoalRepair, "goal_repair_status");
            if (string.Equals(latestGoalRepair.Status, "failed", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(latestGoalRepair.ProgressSubstep, "validation_failed", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(repairStatus, "needs_fix", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(repairStatus, "failed", StringComparison.OrdinalIgnoreCase))
            {
                return new ProjectDetailStep(number, "完成游戏模块", "fix", href, "×");
            }

            if (string.Equals(latestGoalRepair.Status, "succeeded", StringComparison.OrdinalIgnoreCase) &&
                string.Equals(repairStatus, "succeeded", StringComparison.OrdinalIgnoreCase))
            {
                return new ProjectDetailStep(number, "完成游戏模块", "pending", href, "");
            }
        }

        return CreateRunStep(number, "完成游戏模块", latestIteration, href);
    }

    private static RunReadbackItem? LatestGoalRepairRun(IReadOnlyList<RunReadbackItem> runs)
    {
        return runs
            .Where(run => string.Equals(run.RunType, "prototype-quick-fix", StringComparison.OrdinalIgnoreCase) &&
                          IsGoalRepairRun(run))
            .OrderByDescending(RunSortTimeUtc)
            .ThenByDescending(run => run.RunId, StringComparer.Ordinal)
            .FirstOrDefault();
    }

    private static bool IsGoalRepairRun(RunReadbackItem run)
    {
        if (string.IsNullOrWhiteSpace(run.EvidenceJson))
        {
            return false;
        }

        try
        {
            using var document = JsonDocument.Parse(run.EvidenceJson);
            return document.RootElement.TryGetProperty("goal_repair", out var value) &&
                   value.ValueKind == JsonValueKind.True;
        }
        catch (JsonException)
        {
            return false;
        }
    }

    private static bool IsSucceededGoalRepair(RunReadbackItem? run)
    {
        return run is not null &&
               string.Equals(run.Status, "succeeded", StringComparison.OrdinalIgnoreCase) &&
               string.Equals(ReadStringFromEvidence(run, "goal_repair_status"), "succeeded", StringComparison.OrdinalIgnoreCase);
    }

    private static string? ReadStringFromEvidence(RunReadbackItem run, string propertyName)
    {
        if (string.IsNullOrWhiteSpace(run.EvidenceJson))
        {
            return null;
        }

        try
        {
            using var document = JsonDocument.Parse(run.EvidenceJson);
            return document.RootElement.TryGetProperty(propertyName, out var value) &&
                   value.ValueKind == JsonValueKind.String
                ? value.GetString()
                : null;
        }
        catch (JsonException)
        {
            return null;
        }
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
        if (IsSkeletonValidationOnlyRun(run))
        {
            return false;
        }

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

    private static bool IsAnyValidationOnlyRun(RunReadbackItem run)
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

    private static bool IsSkeletonValidationOnlyRun(RunReadbackItem run)
    {
        if (string.IsNullOrWhiteSpace(run.EvidenceJson))
        {
            return false;
        }

        try
        {
            using var document = System.Text.Json.JsonDocument.Parse(run.EvidenceJson);
            return document.RootElement.TryGetProperty("skeleton_validation_only", out var value) &&
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
            $"<li><a href=\"/artifacts/{Encode(artifact.ArtifactId)}\">{Encode(PublicArtifactLabel(artifact.ArtifactType))}</a> - {Encode(SanitizePublicRunContent(artifact.RelativePath))}</li>"));
        var body = $"""
            <h1>Run {Encode(run.RunId)}</h1>
            <p>Status: {Encode(run.Status)}</p>
            <p>Type: {Encode(run.RunType)}</p>
            <h2>Stdout</h2>
            <pre>{Encode(SanitizePublicRunContent(run.StdoutText ?? ""))}</pre>
            <h2>Stderr</h2>
            <pre>{Encode(SanitizePublicRunContent(run.StderrText ?? ""))}</pre>
            <ul>{artifactLinks}</ul>
            """;
        return WrapSimplePage($"Run {Encode(run.RunId)}", body);
    }

    private static string SanitizePublicRunContent(string value)
    {
        return value
            .Replace("BMAD", "", StringComparison.OrdinalIgnoreCase)
            .Replace("codex-cli", "generation", StringComparison.OrdinalIgnoreCase)
            .Replace("codex_cli", "generation", StringComparison.OrdinalIgnoreCase)
            .Replace("codex cli", "generation", StringComparison.OrdinalIgnoreCase)
            .Replace("Codex CLI", "generation", StringComparison.OrdinalIgnoreCase)
            .Replace("Codex", "generation", StringComparison.OrdinalIgnoreCase)
            .Replace("codex", "generation", StringComparison.OrdinalIgnoreCase);
    }

    private static string PublicArtifactLabel(string value)
    {
        if (value.Contains("prompt", StringComparison.OrdinalIgnoreCase))
        {
            return "Input record";
        }

        if (value.Contains("result", StringComparison.OrdinalIgnoreCase) ||
            value.Contains("output", StringComparison.OrdinalIgnoreCase) ||
            value.Contains("codex", StringComparison.OrdinalIgnoreCase))
        {
            return "Generation result";
        }

        if (value.Contains("gdd", StringComparison.OrdinalIgnoreCase) ||
            value.Contains("outline", StringComparison.OrdinalIgnoreCase))
        {
            return "Design document";
        }

        if (value.Contains("package", StringComparison.OrdinalIgnoreCase) ||
            value.Contains("zip", StringComparison.OrdinalIgnoreCase))
        {
            return "Project package";
        }

        var sanitized = SanitizePublicRunContent(value);
        return string.IsNullOrWhiteSpace(sanitized) ? "Artifact" : sanitized;
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
                .section-actions { display:flex; flex-wrap:wrap; gap:.45rem; justify-content:flex-end; }
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
                  <button id="completeAllSections" type="button">&#34917;&#20840;&#25152;&#26377;&#22823;&#32434;</button>
                  <button id="openAddSection" type="button">&#26032;&#22686;&#22823;&#32434;&#31456;&#33410;</button>
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
                <label><strong>&#39592;&#26550;&#20449;&#24687;</strong><textarea id="editorSkeleton"></textarea></label>
                <label><strong>&#20855;&#20307;&#20869;&#23481;</strong><textarea id="editorContent"></textarea></label>
                <label><strong>&#36755;&#20837;&#20449;&#24687;</strong><textarea id="editorMessage" placeholder="&#36755;&#20837;&#26412;&#26465;&#30446;&#30340;&#34917;&#20805;&#35201;&#27714;"></textarea></label>
                <div class="row">
                  <button id="saveSection" type="button">&#20445;&#23384;&#20462;&#25913;</button>
                  <button id="generateSection" class="secondary">&#29983;&#25104;&#20855;&#20307;&#20869;&#23481;</button>
                  <button id="closeEditor" class="ghost">&#20851;&#38381;</button>
                </div>
              </dialog>
              <dialog id="addSectionDialog">
                <h2>&#26032;&#22686;&#22823;&#32434;&#31456;&#33410;</h2>
                <p class="muted">&#21482;&#20250;&#22312;&#29616;&#26377;&#22823;&#32434;&#26411;&#23614;&#22686;&#37327;&#34917;&#20805;&#26032;&#31456;&#33410;&#65292;&#19981;&#20250;&#20462;&#25913;&#12289;&#37325;&#25490;&#25110;&#21024;&#38500;&#21407;&#26377;&#22823;&#32434;&#32467;&#26500;&#12290;</p>
                <label><strong>&#36755;&#20837;&#20449;&#24687;</strong><textarea id="addSectionMessage" placeholder="&#20363;&#22914;&#65306;&#26032;&#22686; M9 Boss &#19982;&#32467;&#31639;&#27169;&#22359;&#65292;&#35201;&#21253;&#21547;&#29609;&#23478;&#39564;&#25910;&#21644;&#25171;&#21253;&#39564;&#35777;&#12290;"></textarea></label>
                <div class="row">
                  <button id="confirmAddSection" type="button">&#30830;&#35748;&#26032;&#22686;</button>
                  <button id="closeAddSection" class="ghost" type="button">&#20851;&#38381;</button>
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
                let batchOutlinePollTimer = null;
                let batchOutlinePollRunId = "";
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
                    $("meta").innerHTML = `<span class="danger">&#35835;&#21462;&#22833;&#36133;&#65306;${escapeHtml(publicErrorCode(error?.payload?.error || "gdd_outline_not_found"))}</span>`;
                  }
                }
                function renderOutline() {
                  const hasSections = Array.isArray(outline.sections) && outline.sections.length > 0;
                  $("meta").textContent = hasSections
                    ? `已载入策划大纲${outline.lastUpdatedUtc ? ` · ${outline.lastUpdatedUtc}` : ""}`
                    : "当前策划大纲不可用，请删除后重新创建。";
                  $("deleteGddOutline").disabled = false;
                  $("completeAllSections").disabled = !hasSections;
                  $("openAddSection").disabled = !hasSections;
                  $("exportGddMarkdown").disabled = !hasSections;
                  $("title").textContent = outline.title || "\u7b56\u5212\u5927\u7eb2";
                  $("summary").textContent = outline.summary || "";
                  $("sections").innerHTML = (outline.sections || []).map(section => `
                    <article class="section-card" data-section-id="${escapeHtml(section.id)}">
                      <div class="section-header">
                        <h3>${escapeHtml(section.title)}</h3>
                        <div class="section-actions">
                          <button type="button" data-quick-complete-section="${escapeHtml(section.id)}">&#24555;&#36895;&#34917;&#20840;</button>
                          <button type="button" data-edit-section="${escapeHtml(section.id)}">&#32534;&#36753;</button>
                        </div>
                      </div>
                      <p><strong>&#39592;&#26550;</strong><br>${escapeHtml(section.skeleton)}</p>
                      <div class="section-content">${section.content ? escapeHtml(section.content) : "<span class='muted'>&#20855;&#20307;&#20869;&#23481;&#24453;&#29983;&#25104;&#12290;</span>"}</div>
                    </article>
                  `).join("") || "<p class='muted'>&#27809;&#26377;&#22823;&#32434;&#26465;&#30446;&#12290;</p>";
                  document.querySelectorAll("[data-edit-section]").forEach(button => button.onclick = () => openEditor(button.dataset.editSection));
                  document.querySelectorAll("[data-quick-complete-section]").forEach(button => button.onclick = () => quickCompleteSection(button.dataset.quickCompleteSection, button));
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
                    await generateSectionContent(selectedSection.id, $("editorMessage").value);
                    selectedSection = (outline.sections || []).find(item => item.id === selectedSection.id);
                    $("editorContent").value = selectedSection?.content || "";
                    renderOutline();
                  } catch (error) {
                    alert(error?.payload?.summary || publicErrorCode(error?.payload?.error || "generate_failed"));
                  } finally {
                    button.disabled = false;
                    button.textContent = "\u751f\u6210\u5177\u4f53\u5185\u5bb9";
                  }
                }
                async function generateSectionContent(sectionId, message = "") {
                  await api(`/api/projects/${projectId}/gdd/outline/sections/${encodeURIComponent(sectionId)}`, { method:"POST", body: JSON.stringify({ message, model: localStorage.getItem("phaseASelectedModel") || null }) });
                  outline = await api(`/api/projects/${projectId}/gdd/outline`);
                }
                async function saveSection() {
                  if (!selectedSection) return;
                  const button = $("saveSection");
                  button.disabled = true;
                  button.textContent = "\u4fdd\u5b58\u4e2d...";
                  try {
                    await api(`/api/projects/${projectId}/gdd/outline/sections/${encodeURIComponent(selectedSection.id)}`, {
                      method:"PATCH",
                      body: JSON.stringify({
                        skeleton: $("editorSkeleton").value,
                        content: $("editorContent").value
                      })
                    });
                    outline = await api(`/api/projects/${projectId}/gdd/outline`);
                    selectedSection = (outline.sections || []).find(item => item.id === selectedSection.id);
                    if (selectedSection) {
                      $("editorSkeleton").value = selectedSection.skeleton || "";
                      $("editorContent").value = selectedSection.content || "";
                    }
                    renderOutline();
                    $("meta").textContent = "\u7b56\u5212\u5927\u7eb2\u6761\u76ee\u5df2\u4fdd\u5b58\u3002";
                  } catch (error) {
                    alert(error?.payload?.summary || publicErrorCode(error?.payload?.error || "save_failed"));
                  } finally {
                    button.disabled = false;
                    button.textContent = "\u4fdd\u5b58\u4fee\u6539";
                  }
                }
                function notifyGameModulesRefresh() {
                  try {
                    window.parent?.postMessage?.({ type: "phasea:gdd-modules-refresh", projectId }, location.origin);
                  } catch {}
                }
                function notifyActiveRunRefresh(runId = "") {
                  try {
                    window.parent?.postMessage?.({ type: "phasea:active-run-refresh", projectId, runId }, location.origin);
                  } catch {}
                }
                function openAddSectionDialog() {
                  $("addSectionMessage").value = "";
                  $("addSectionDialog").showModal();
                  $("addSectionMessage").focus();
                }
                async function confirmAddSection() {
                  const message = $("addSectionMessage").value || "";
                  if (!message.trim()) {
                    alert("\u8bf7\u8f93\u5165\u65b0\u589e\u5927\u7eb2\u7ae0\u8282\u7684\u8981\u6c42\u3002");
                    return;
                  }
                  const button = $("confirmAddSection");
                  button.disabled = true;
                  button.textContent = "\u65b0\u589e\u4e2d...";
                  $("openAddSection").disabled = true;
                  $("completeAllSections").disabled = true;
                  try {
                    const result = await api(`/api/projects/${projectId}/gdd/outline/sections/add`, {
                      method:"POST",
                      body: JSON.stringify({ message, model: localStorage.getItem("phaseASelectedModel") || null })
                    });
                    outline = await api(`/api/projects/${projectId}/gdd/outline`);
                    renderOutline();
                    notifyGameModulesRefresh();
                    $("addSectionDialog").close();
                    $("meta").textContent = result.summary || "\u7b56\u5212\u5927\u7eb2\u65b0\u589e\u7ae0\u8282\u5df2\u521b\u5efa\u3002";
                  } catch (error) {
                    alert(error?.payload?.summary || publicErrorCode(error?.payload?.error || "add_section_failed"));
                  } finally {
                    button.disabled = false;
                    button.textContent = "\u786e\u8ba4\u65b0\u589e";
                    $("openAddSection").disabled = !Array.isArray(outline?.sections) || outline.sections.length === 0;
                    $("completeAllSections").disabled = !Array.isArray(outline?.sections) || outline.sections.length === 0;
                  }
                }
                function isTerminalRunStatus(status) {
                  return ["succeeded", "failed", "blocked", "cancel", "cancelled", "timeout"].includes(String(status || "").toLowerCase());
                }
                function formatBatchRunProgress(run, fallbackCount) {
                  const label = run?.progressLabel || run?.progressSubstep || run?.status || "";
                  return label
                    ? `\u7b56\u5212\u5927\u7eb2\u6279\u91cf\u8865\u5168\u4e2d\uff1a${label}`
                    : `\u7b56\u5212\u5927\u7eb2\u6279\u91cf\u8865\u5168\u4e2d\uff0c\u5171 ${fallbackCount || 0} \u4e2a\u6761\u76ee\u3002`;
                }
                function stopBatchOutlinePolling(runId = "") {
                  if (runId && batchOutlinePollRunId && runId !== batchOutlinePollRunId) return;
                  if (batchOutlinePollTimer) {
                    clearInterval(batchOutlinePollTimer);
                    batchOutlinePollTimer = null;
                  }
                  batchOutlinePollRunId = "";
                }
                async function refreshBatchOutlineRun(runId, fallbackCount = 0) {
                  if (!runId) return null;
                  const result = await api(`/api/runs/${encodeURIComponent(runId)}`);
                  const run = result.run || {};
                  $("meta").textContent = formatBatchRunProgress(run, fallbackCount);
                  notifyActiveRunRefresh(runId);
                  if (run.finishedUtc || isTerminalRunStatus(run.status)) {
                    stopBatchOutlinePolling(runId);
                    try {
                      outline = await api(`/api/projects/${projectId}/gdd/outline`);
                      renderOutline();
                    } catch {}
                  }
                  return run;
                }
                function startBatchOutlinePolling(runId, fallbackCount = 0) {
                  if (!runId) return;
                  if (batchOutlinePollRunId === runId && batchOutlinePollTimer) return;
                  stopBatchOutlinePolling();
                  batchOutlinePollRunId = runId;
                  void refreshBatchOutlineRun(runId, fallbackCount).catch(() => {});
                  batchOutlinePollTimer = setInterval(() => {
                    void refreshBatchOutlineRun(runId, fallbackCount).catch(() => {});
                  }, 2000);
                }
                async function attachActiveBatchOutlineRun() {
                  if (!projectId || !token()) return;
                  try {
                    const run = await api("/api/account/active-run");
                    const runType = String(run?.runType || "").trim().toLowerCase();
                    if (run?.busy && run?.runId && run?.projectId === projectId && runType === "game-design-gdd-section-batch") {
                      const fallbackCount = (outline?.sections || []).filter(section => !String(section.content || "").trim()).length;
                      startBatchOutlinePolling(run.runId, fallbackCount);
                    }
                  } catch {}
                }
                async function waitForBatchOutlineRun(runId, fallbackCount) {
                  if (!runId) return null;
                  for (let attempt = 0; attempt < 1800; attempt++) {
                    await new Promise(resolve => setTimeout(resolve, attempt === 0 ? 800 : 2000));
                    const run = await refreshBatchOutlineRun(runId, fallbackCount);
                    if (run.finishedUtc || isTerminalRunStatus(run.status)) return run;
                  }
                  return null;
                }
                async function quickCompleteSection(sectionId, button) {
                  if (!sectionId || !button) return;
                  button.disabled = true;
                  $("completeAllSections").disabled = true;
                  button.textContent = "生成中...";
                  try {
                    await generateSectionContent(sectionId, "");
                    if (selectedSection?.id === sectionId) {
                      selectedSection = (outline.sections || []).find(item => item.id === sectionId);
                      $("editorContent").value = selectedSection?.content || "";
                    }
                    renderOutline();
                  } catch (error) {
                    alert(error?.payload?.summary || publicErrorCode(error?.payload?.error || "generate_failed"));
                    button.disabled = false;
                  } finally {
                    button.textContent = "快速补全";
                    $("completeAllSections").disabled = !Array.isArray(outline?.sections) || outline.sections.length === 0;
                  }
                }
                async function completeAllSections() {
                  const button = $("completeAllSections");
                  const pendingSections = (outline?.sections || []).filter(section => !String(section.content || "").trim());
                  if (pendingSections.length === 0) {
                    alert("\u6240\u6709\u5927\u7eb2\u90fd\u5df2\u6709\u5177\u4f53\u5185\u5bb9\u3002");
                    return;
                  }
                  if (!confirm(`\u5c06\u987a\u5e8f\u8865\u5168 ${pendingSections.length} \u4e2a\u5927\u7eb2\u6761\u76ee\uff0c\u671f\u95f4\u4f1a\u9010\u6761\u8c03\u7528\u751f\u6210\u4efb\u52a1\u3002\u662f\u5426\u7ee7\u7eed\uff1f`)) return;

                  button.disabled = true;
                  $("deleteGddOutline").disabled = true;
                  $("generateSection").disabled = true;
                  $("exportGddMarkdown").disabled = true;
                  document.querySelectorAll("[data-quick-complete-section]").forEach(item => item.disabled = true);
                  button.textContent = "\u8865\u5168\u4e2d...";
                  $("meta").textContent = `\u6b63\u5728\u8865\u5168 ${pendingSections.length} \u4e2a\u5927\u7eb2\u6761\u76ee\u3002`;
                  try {
                    const result = await api(`/api/projects/${projectId}/gdd/outline/sections/complete-missing`, { method:"POST", body: JSON.stringify({ message: "", model: localStorage.getItem("phaseASelectedModel") || null }) });
                    if (result.runId && ["queued", "running"].includes(String(result.status || "").toLowerCase())) {
                      notifyActiveRunRefresh(result.runId);
                      startBatchOutlinePolling(result.runId, pendingSections.length);
                      const run = await waitForBatchOutlineRun(result.runId, pendingSections.length);
                      outline = await api(`/api/projects/${projectId}/gdd/outline`);
                      renderOutline();
                      if (!run) {
                        alert("\u6279\u91cf\u8865\u5168\u4ecd\u5728\u540e\u53f0\u6267\u884c\uff0c\u53ef\u7a0d\u540e\u91cd\u65b0\u6253\u5f00\u7b56\u5212\u5927\u7eb2\u67e5\u770b\u7ed3\u679c\u3002");
                        return;
                      }
                      if (String(run.status || "").toLowerCase() !== "succeeded") {
                        alert(run.progressLabel || "\u6279\u91cf\u8865\u5168\u672a\u5b8c\u6210\uff0c\u8bf7\u67e5\u770b\u8fd0\u884c\u8bb0\u5f55\u3002");
                        return;
                      }
                      alert(run.progressLabel || "\u7b56\u5212\u5927\u7eb2\u5df2\u6279\u91cf\u8865\u5168\u3002");
                      return;
                    }
                    outline = await api(`/api/projects/${projectId}/gdd/outline`);
                    renderOutline();
                    alert(result.summary || `\u5df2\u8865\u5168 ${result.completedCount || 0} \u4e2a\u5927\u7eb2\u6761\u76ee\u3002`);
                  } catch (error) {
                    alert(error?.payload?.summary || publicErrorCode(error?.payload?.error || "complete_all_failed"));
                    try { outline = await api(`/api/projects/${projectId}/gdd/outline`); renderOutline(); } catch {}
                  } finally {
                    button.disabled = false;
                    button.textContent = "\u8865\u5168\u6240\u6709\u5927\u7eb2";
                    $("deleteGddOutline").disabled = false;
                    $("generateSection").disabled = false;
                    $("openAddSection").disabled = !Array.isArray(outline?.sections) || outline.sections.length === 0;
                    $("exportGddMarkdown").disabled = !Array.isArray(outline?.sections) || outline.sections.length === 0;
                    document.querySelectorAll("[data-quick-complete-section]").forEach(item => item.disabled = false);
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
                    alert(publicErrorCode(error?.payload?.error || "export_failed"));
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
                    $("completeAllSections").disabled = true;
                    $("openAddSection").disabled = true;
                    $("exportGddMarkdown").disabled = true;
                    notifyOutlineDeleted();
                  } catch (error) {
                    alert(publicErrorCode(error?.payload?.error || "delete_failed"));
                    button.disabled = false;
                  } finally {
                    button.textContent = "\u5220\u9664\u7b56\u5212\u5927\u7eb2";
                  }
                }
                $("closeEditor").onclick = () => $("editor").close();
                $("openAddSection").onclick = openAddSectionDialog;
                $("closeAddSection").onclick = () => $("addSectionDialog").close();
                $("confirmAddSection").onclick = confirmAddSection;
                $("saveSection").onclick = saveSection;
                $("generateSection").onclick = generateSection;
                $("completeAllSections").onclick = completeAllSections;
                $("exportGddMarkdown").onclick = exportGddMarkdown;
                $("deleteGddOutline").onclick = deleteGddOutline;
                loadOutline().then(() => attachActiveBatchOutlineRun()).catch(() => {});
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
                .toolbar, .package-actions { display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: center; }
                .preview-button { background: #264a62; }
                .preview-button.ready { background: #7a4d11; }
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
                    $("status").innerHTML = `<span class="danger">读取失败：${escapeHtml(publicErrorCode(payload.error || "unknown_error"))}</span>`;
                    return;
                  }
                  renderCreatePackageAction(payload);
                  $("status").textContent = payload.canCreatePackage ? "可以继续生成新的项目文件包。" : disabledText(payload.disabledReason);
                  $("packages").innerHTML = (payload.packages || []).map(item => `
                    <article class="package card">
                      <strong>${escapeHtml(item.version)}</strong>
                      <span class="muted">${escapeHtml(item.createdUtc || "未知时间")} · ${escapeHtml(item.fileName)} · ${item.sizeBytes} bytes</span>
                      <div class="package-actions">
                        <button data-download-url="${escapeHtml(item.downloadUrl)}" data-file-name="${escapeHtml(item.fileName)}">下载此版本</button>
                      </div>
                      ${renderWebPreviewAction(item)}
                    </article>
                  `).join("") || "<p class='muted'>还没有已打包的项目文件。</p>";
                  document.querySelectorAll("[data-download-url]").forEach(button => {
                    button.onclick = () => downloadPackage(button, button.dataset.downloadUrl, button.dataset.fileName);
                  });
                  document.querySelectorAll("[data-web-preview-file]").forEach(button => {
                    button.onclick = () => handleWebPreviewBackground(button, button.dataset.webPreviewFile, button.dataset.webPreviewUrl);
                  });
                  await loadGddDownload();
                }
                function renderWebPreviewAction(item) {
                  const preview = item.webPreview || {};
                  const ready = preview.status === "ready" && preview.previewUrl;
                  const running = preview.status === "queued" || preview.status === "running";
                  const failed = preview.status === "failed";
                  const stale = preview.status === "stale";
                  const readyFailure = ready && preview.failureCode
                    ? ` · \u4e0a\u6b21\u91cd\u65b0\u751f\u6210\u5931\u8d25\uff1a${escapeHtml(disabledText(preview.failureCode))} (${escapeHtml(preview.failureCode)})`
                    : "";
                  const buttonText = ready
                    ? "\u6253\u5f00\u6d4f\u89c8\u5668\u8bd5\u73a9\u5730\u5740"
                      : running
                        ? "\u8f6c\u6362\u4e2d..."
                      : failed
                        ? "\u91cd\u65b0\u751f\u6210\u6d4f\u89c8\u5668\u8bd5\u73a9"
                        : stale
                          ? "\u91cd\u65b0\u751f\u6210\u6d4f\u89c8\u5668\u8bd5\u73a9"
                        : "\u751f\u6210\u6d4f\u89c8\u5668\u8bd5\u73a9";
                  const failureCode = preview.failureCode || "web_preview_failed";
                  const fidelity = preview.fidelityTier ? ` · ${escapeHtml(preview.fidelityTier)}` : "";
                  const surface = preview.playableSurface ? ` · ${escapeHtml(preview.playableSurface)}` : "";
                  const type = preview.gameTypeId ? ` · ${escapeHtml(preview.gameTypeId)}` : "";
                  const meta = ready
                    ? `${escapeHtml(preview.createdUtc || "\u672a\u77e5\u65f6\u95f4")} · ${escapeHtml(preview.mode || "preview")} · \u5305\u8f6c\u6362\u8bd5\u73a9\u7248${type}${fidelity}${surface}${readyFailure}`
                    : failed
                      ? `\u4e0a\u6b21\u751f\u6210\u5931\u8d25\uff1a${escapeHtml(disabledText(failureCode))} (${escapeHtml(failureCode)})`
                      : stale
                        ? "\u8f6c\u6362\u5668\u5df2\u5347\u7ea7\uff0c\u9700\u8981\u91cd\u65b0\u751f\u6210\u5305\u8f6c\u6362\u8bd5\u73a9\u7248\u3002"
                      : running
                        ? webPreviewQueueText(preview)
                        : "guest \u6743\u9650\u516c\u5f00\u8bbf\u95ee\uff0c\u751f\u6210\u7684\u94fe\u63a5\u662f\u5305\u8f6c\u6362\u8bd5\u73a9\u7248\u3002";
                  return `
                    <div class="package-actions">
                      <button class="preview-button ${ready ? "ready" : ""}" data-web-preview-file="${escapeHtml(item.fileName)}" data-web-preview-url="${escapeHtml(preview.previewUrl || "")}" ${running ? "disabled" : ""}>${buttonText}</button>
                      <span class="muted">${meta}</span>
                    </div>
                  `;
                }
                function webPreviewQueueText(preview) {
                  const seconds = Number(preview.estimatedWaitSeconds || 0);
                  const position = Number(preview.queuePosition || 0);
                  if (position > 0 && seconds > 0) {
                    return `Godot3 \u6b63\u5728\u6392\u961f\uff0c\u961f\u5217\u4f4d\u7f6e ${position}\uff0c\u9884\u8ba1\u7b49\u5f85 ${formatDuration(seconds)}\u3002`;
                  }
                  if (preview.status === "running") {
                    return "Godot3 \u6b63\u5728\u5bfc\u51fa\uff0c\u8bf7\u7a0d\u5019\u5237\u65b0\u6216\u7b49\u5f85\u81ea\u52a8\u6253\u5f00\u3002";
                  }
                  return "Godot3 \u6b63\u5728\u6392\u961f\uff0c\u8bf7\u7a0d\u5019\u5237\u65b0\u6216\u7b49\u5f85\u81ea\u52a8\u6253\u5f00\u3002";
                }
                function formatDuration(seconds) {
                  const value = Math.max(0, Math.floor(Number(seconds) || 0));
                  if (value < 60) return `${value}\u79d2`;
                  const minutes = Math.floor(value / 60);
                  const remainder = value % 60;
                  return remainder ? `${minutes}\u5206${remainder}\u79d2` : `${minutes}\u5206\u949f`;
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
                      const reason = publicErrorCode(payload.failureCode || payload.disabledReason || payload.error || payload.status || "unknown_error");
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
                  if (reason === "m1_not_completed") return "M1 游戏场景完成后才可以打包项目文件。";
                  if (reason === "project_busy") return "项目有后台任务正在执行。";
                  if (reason === "project_not_found") return "项目不存在或当前账号无权访问。";
                  if (reason === "package_not_found") return "没有找到这个项目文件包。";
                  if (reason === "user_web_preview_concurrency_limit_exceeded") return "\u5f53\u524d\u8d26\u53f7\u5df2\u6709\u4e00\u4e2a\u6d4f\u89c8\u5668\u8bd5\u73a9\u751f\u6210\u4efb\u52a1\u5728\u6267\u884c\u3002";
                  if (reason === "web_preview_signing_secret_missing") return "\u670d\u52a1\u5668\u672a\u914d\u7f6e\u6d4f\u89c8\u5668\u8bd5\u73a9\u7b7e\u540d\u5bc6\u94a5\u3002";
                  if (reason === "godot3_shell_patch_failed") return "Godot3 HTML5 \u8f7d\u5165\u58f3\u8865\u4e01\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5\u5bfc\u51fa\u6a21\u677f\u7248\u672c\u3002";
                  if (reason === "web_preview_background_failed") return "\u6d4f\u89c8\u5668\u8bd5\u73a9\u540e\u53f0\u4efb\u52a1\u5f02\u5e38\u4e2d\u65ad\u3002";
                  if (reason === "abandoned_run_recovered") return "\u6d4f\u89c8\u5668\u8bd5\u73a9\u751f\u6210\u4efb\u52a1\u5728\u670d\u52a1\u5668\u91cd\u542f\u6216\u8d85\u65f6\u6062\u590d\u540e\u4e2d\u65ad\uff0c\u8bf7\u91cd\u65b0\u751f\u6210\u3002";
                  if (reason === "godot3_bin_not_configured") return "服务器没有配置可用的 Godot3 执行文件。";
                  if (reason === "unsupported_package_template") return "当前项目文件包缺少可生成浏览器试玩的 Godot 主场景或场景清单。";
                  if (reason === "package_invalid_zip") return "\u9879\u76ee\u6587\u4ef6\u5305\u4e0d\u662f\u6709\u6548\u7684 zip \u6587\u4ef6\u3002";
                  if (reason === "package_scan_budget_exceeded") return "\u9879\u76ee\u6587\u4ef6\u5305\u8d85\u8fc7\u6d4f\u89c8\u5668\u8bd5\u73a9\u626b\u63cf\u4e0a\u9650\u3002";
                  if (reason === "web_preview_converter_fingerprint_mismatch") return "\u5f53\u524d\u9879\u76ee\u6587\u4ef6\u5305\u4e0e\u670d\u52a1\u5668\u7684\u4e13\u7528\u6d4f\u89c8\u5668\u8bd5\u73a9\u8f6c\u6362\u5668\u6307\u7eb9\u4e0d\u5339\u914d\uff0c\u5df2\u4fdd\u7559\u901a\u7528\u5305\u9884\u89c8\u515c\u5e95\u8def\u5f84\u3002";
                  if (reason === "converter_schema_outdated") return "\u8f6c\u6362\u5668\u5df2\u5347\u7ea7\uff0c\u9700\u8981\u91cd\u65b0\u751f\u6210\u8bd5\u73a9\u7248\u3002";
                  if (reason === "godot3_export_failed") return "Godot3 HTML5 导出失败，请查看后台运行记录。";
                  if (reason === "web_preview_failed") return "项目文件包未能生成浏览器试玩地址。";
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
                        detail = publicErrorCode(payload.error || payload.status || detail);
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
                async function handleWebPreviewBackground(button, fileName, previewUrl) {
                  if (previewUrl) {
                    window.open(previewUrl, "_blank", "noopener");
                    return;
                  }

                  const originalText = button.textContent;
                  button.disabled = true;
                  button.textContent = "\u751f\u6210\u4e2d...";
                  $("status").textContent = "\u5df2\u63d0\u4ea4\u6d4f\u89c8\u5668\u8bd5\u73a9\u751f\u6210\u4efb\u52a1\uff0c\u6b63\u5728\u7b49\u5f85 Godot3 \u5bfc\u51fa\u3002";
                  try {
                    const response = await fetch(`/api/projects/${encodeURIComponent(projectId)}/packages/${encodeURIComponent(fileName)}/web-preview`, { method: "POST", headers: { "Authorization": `Bearer ${token()}`, "Content-Type": "application/json" }, cache: "no-store" });
                    let payload = {};
                    try { payload = await response.json(); } catch {}
                    if (!response.ok && response.status !== 202) {
                      const reason = publicErrorCode(payload.failureCode || payload.status || payload.error || "unknown_error");
                      $("status").innerHTML = `<span class="danger">\u8bd5\u73a9\u5730\u5740\u751f\u6210\u5931\u8d25\uff1a${escapeHtml(disabledText(reason))} (${escapeHtml(reason)})</span>`;
                      return;
                    }

                    const previewResult = await waitForWebPreview(fileName, button, payload.runId || "");
                    if (previewResult.status === "failed") {
                      const reason = publicErrorCode(previewResult.failureCode || "web_preview_failed");
                      $("status").innerHTML = `<span class="danger">\u8bd5\u73a9\u5730\u5740\u751f\u6210\u5931\u8d25\uff1a${escapeHtml(disabledText(reason))} (${escapeHtml(reason)})</span>`;
                      await loadPackages();
                      return;
                    }
                    if (!previewResult.url) {
                      $("status").innerHTML = "<span class='danger'>\u8bd5\u73a9\u5730\u5740\u8fd8\u672a\u751f\u6210\u5b8c\u6210\uff0c\u8bf7\u7a0d\u540e\u5237\u65b0\u4e0b\u8f7d\u9875\u67e5\u770b\u72b6\u6001\u3002</span>";
                      return;
                    }

                    await loadPackages();
                    $("status").innerHTML = `\u6d4f\u89c8\u5668\u8bd5\u73a9\u5730\u5740\u5df2\u751f\u6210\uff0c\u8bf7\u70b9\u51fb\u65b0\u7684\u201c\u6253\u5f00\u6d4f\u89c8\u5668\u8bd5\u73a9\u5730\u5740\u201d\u6309\u94ae\uff0c\u6216 <a href="${escapeHtml(previewResult.url)}" target="_blank" rel="noopener">\u76f4\u63a5\u6253\u5f00</a>\u3002`;
                  } catch {
                    $("status").innerHTML = "<span class='danger'>\u8bd5\u73a9\u5730\u5740\u751f\u6210\u5931\u8d25\uff1a\u6d4f\u89c8\u5668\u672a\u80fd\u53d1\u8d77\u751f\u6210\u8bf7\u6c42\u3002</span>";
                  } finally {
                    button.disabled = false;
                    button.textContent = originalText;
                  }
                }

                function webPreviewFailureCodeFromRun(run) {
                  if (!run) return "web_preview_failed";
                  try {
                    const evidence = JSON.parse(run.evidenceJson || "{}");
                    return evidence.failure_code || "web_preview_failed";
                  } catch {
                    return "web_preview_failed";
                  }
                }

                async function waitForWebPreview(fileName, button, runId) {
                  const maxAttempts = 900;
                  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
                    button.textContent = `\u8f6c\u6362\u4e2d ${attempt}/${maxAttempts}`;
                    await new Promise(resolve => setTimeout(resolve, 2000));
                    if (runId) {
                      const runResponse = await fetch(`/api/runs/${encodeURIComponent(runId)}`, { headers: { "Authorization": `Bearer ${token()}` }, cache: "no-store" });
                      if (runResponse.ok) {
                        const runPayload = await runResponse.json();
                        const run = runPayload.run || {};
                        if (run.status === "failed" || run.status === "blocked" || run.status === "cancel") {
                          return { status: "failed", url: "", failureCode: webPreviewFailureCodeFromRun(run) };
                        }
                      }
                    }
                    const response = await fetch(`/api/projects/${encodeURIComponent(projectId)}/packages`, { headers: { "Authorization": `Bearer ${token()}` }, cache: "no-store" });
                    if (!response.ok) continue;
                    const payload = await response.json();
                    const item = (payload.packages || []).find(pkg => pkg.fileName === fileName);
                    const preview = item?.webPreview || {};
                    if (preview.status === "queued" && Number(preview.estimatedWaitSeconds || 0) > 0) {
                      const position = Number(preview.queuePosition || 0);
                      button.textContent = position > 0
                        ? `\u6392\u961f\u4e2d ${position} · ${formatDuration(preview.estimatedWaitSeconds)}`
                        : `\u6392\u961f\u4e2d · ${formatDuration(preview.estimatedWaitSeconds)}`;
                    }
                    if (preview.status === "ready" && preview.previewUrl) {
                      return { status: "ready", url: preview.previewUrl };
                    }
                    if (preview.status === "failed") {
                      return { status: "failed", url: "", failureCode: preview.failureCode || "web_preview_failed" };
                    }
                  }
                  return { status: "timeout", url: "" };
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
                <section id="status" class="card muted">正在读取项目素材库...</section>
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
                    <input id="assetImportQuery" type="text" maxlength="2000" placeholder="关键词或白名单 URL；非白名单 URL 只按关键词分析">
                    <button id="modalImportAsset" class="ghost" type="button">导入素材</button>
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
                      const reason = publicErrorCode(payload.disabledReason || payload.error || "unknown_error");
                      $("status").className = "card muted";
                      $("status").textContent = assetInventoryDisabledText(reason);
                      return;
                    }
                    state.usedAssets = payload.usedAssets || [];
                    state.candidates = payload.generationCandidates || [];
                    writeAssetCache();
                    const judgedCandidates = state.candidates.filter(item => item.llmJudgementStatus || item.llmJudgementReason).length;
                    const suffix = state.candidates.length && !judgedCandidates
                      ? " 本次没有启动素材判定 run，可能是没有需要判定的候选或已使用缓存。"
                      : "";
                    await renderAssetData(`已刷新素材库：已使用 ${state.usedAssets.length} 个，可生成候选 ${state.candidates.length} 个。${suffix}`);
                  } catch (error) {
                    $("status").className = "card muted";
                    $("status").textContent = `素材库刷新失败：${publicErrorCode(error?.message || error || "unknown_error")}。`;
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
                  if (reason === "final_step_not_completed") return "当前项目素材库还没有足够的可检查内容。";
                  if (reason === "project_busy") return "项目正在运行，请稍后再试。";
                  if (reason === "project_not_selected") return "请先选择项目。";
                  return "项目素材库暂不可用。";
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
                    const validation = entry.selectionValidation?.status ? `<span class="muted">${escapeHtml(publicStatusLabel(entry.selectionValidation.status))}</span>` : "";
                    const source = entry.sourceKind ? `<span class="muted">${escapeHtml(entry.sourceKind)}</span>` : "";
                    return `<div class="history-row ${selected ? "selected" : ""}"><span class="history-row-number">#${index + 1}</span>${preview}<span class="history-row-time">${escapeHtml(formatTime(entry.createdUtc))}</span>${source}${validation}<button class="ghost" type="button" data-select-unit-key="${escapeHtml(libraryUnit.key)}" data-entry-id="${escapeHtml(entry.entryId)}">替换默认素材</button></div>`;
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

                async function importActiveAsset(button) {
                  if (!state.activeAsset) return;
                  const unit = state.activeAsset;
                  const originalText = button.textContent;
                  button.disabled = true;
                  button.textContent = "导入中...";
                  try {
                    const queryOrUrl = $("assetImportQuery").value || "";
                    if (!queryOrUrl.trim()) throw new Error("请输入关键词或白名单 URL。");
                    const response = await fetch(`/api/projects/${encodeURIComponent(projectId)}/asset-library/import`, {
                      method: "POST",
                      headers: { "Authorization": `Bearer ${token()}`, "Content-Type": "application/json" },
                      body: JSON.stringify({ queryOrUrl, unit }),
                      cache: "no-store"
                    });
                    const payload = await response.json();
                    if (!response.ok) throw new Error(publicErrorCode(payload.error || payload.failureCode || "import_failed"));
                    state.library = payload.library || state.library;
                    await hydrateLibraryPreviewUrls();
                    writeAssetCache();
                    $("assetImportQuery").value = "";
                    const sourceText = payload.sourceUrlAllowed ? "白名单 URL 下载" : "关键词记录";
                    $("status").textContent = `素材导入已完成：${sourceText}，状态：${publicStatusLabel(payload.status || "unknown")}。`;
                    await renderAssetData($("status").textContent);
                    showAssetHistory(unit.unitKey);
                  } catch (error) {
                    $("status").textContent = `素材导入失败：${error.message || error}`;
                  } finally {
                    button.disabled = false;
                    button.textContent = originalText;
                  }
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
                    if (!response.ok) throw new Error(publicErrorCode(payload.error || payload.failureCode || "generate_failed"));
                    state.library = payload.library || state.library;
                    await hydrateLibraryPreviewUrls();
                    writeAssetCache();
                    if ($("referenceImageFile")) $("referenceImageFile").value = "";
                    if (payload.status !== "succeeded") {
                      $("status").textContent = `素材生成未完成，调用：${payload.actionId || "skill"}，状态：${publicStatusLabel(payload.status || "unknown")}。`;
                      await renderAssetData($("status").textContent);
                      return;
                    }
                    $("status").textContent = `素材生成已完成，调用：${payload.actionId || "skill"}，状态：${publicStatusLabel(payload.status || "unknown")}。`;
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
                    const response = await fetch(`/api/projects/${encodeURIComponent(projectId)}/asset-library/select`, { method: "POST", headers: { "Authorization": `Bearer ${token()}`, "Content-Type": "application/json" }, body: JSON.stringify({ unitKey, entryId, validateWithSmoke: true }), cache: "no-store" });
                    const payload = await response.json();
                    if (!response.ok) throw new Error(publicErrorCode(payload.error || "select_failed"));
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
                    const selectedUnit = (state.library?.units || []).find(unit => unit.key === unitKey);
                    const selectedEntry = (selectedUnit?.entries || []).find(entry => entry.entryId === entryId);
                    const validation = selectedEntry?.selectionValidation;
                    $("status").textContent = validation?.summary
                      ? `默认素材已替换。${validation.summary} 状态：${publicStatusLabel(validation.status || "unknown")}。${validation.selectionSmoke?.reason ? " Smoke：" + publicStatusLabel(validation.selectionSmoke.reason) + "。" : ""}`
                      : "默认素材已替换。";
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
                $("modalImportAsset").addEventListener("click", event => importActiveAsset(event.currentTarget));
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

    private static string[] LoadPrototypeSkeletonRunNotes()
    {
        var assembly = typeof(BrowserUiRenderer).Assembly;
        var resourceName = assembly.GetManifestResourceNames()
            .FirstOrDefault(name => name.EndsWith("Browser.Assets.PrototypeSkeletonRunNotes.txt", StringComparison.OrdinalIgnoreCase));
        if (resourceName is null)
        {
            return [];
        }

        using var stream = assembly.GetManifestResourceStream(resourceName);
        if (stream is null)
        {
            return [];
        }

        using var reader = new StreamReader(stream, Encoding.UTF8, detectEncodingFromByteOrderMarks: true);
        return reader.ReadToEnd()
            .Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
    }
}
