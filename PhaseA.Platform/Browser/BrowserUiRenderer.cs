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
            .Replace("</style>", """
                body.v2-detail #projectDetailPanel {
                  display: grid;
                  gap: 0.9rem;
                  align-items: start;
                }
                body.v2-detail #v2ProgressShell { grid-column: 1; }
                body.v2-detail #v2ContentGrid {
                  display: grid;
                  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
                  gap: 0.9rem;
                  align-items: start;
                }
                body.v2-detail #chatPanel { grid-column: 1; grid-row: 1; align-self: start; }
                body.v2-detail #v2IterationPanel { grid-column: 2; grid-row: 1; align-self: start; }
                body.v2-detail #v2RepairPanel { grid-column: 2; grid-row: 1; align-self: start; }
                body.v2-detail #v2AcceptancePanel { grid-column: 2; grid-row: 1; align-self: start; }
                body.v2-detail #currentProjectPanel,
                body.v2-detail #prototypeWorkflowPanel,
                body.v2-detail #prototypeCommandPanel,
                body.v2-detail #runsPanel { grid-column: 2; grid-row: 1; align-self: start; }
                body.v2-detail #outputPanel { grid-column: 1 / -1; }
                body.v2-detail .v2-progress-row { display: grid; grid-template-columns: repeat(8, minmax(5.6rem, 1fr)); gap: 0.45rem; overflow-x: auto; padding-bottom: 0.1rem; }
                body.v2-detail .v2-step-button { position: relative; min-width: 5.6rem; display: grid; justify-items: center; gap: 0.25rem; padding: 0.35rem 0.3rem 0.62rem; color: var(--ink); background: #fffdf8; border: 1px solid var(--line); border-radius: 0.75rem; }
                body.v2-detail .v2-step-button.active { outline: 2px solid var(--accent-2); border-color: var(--accent-2); }
                body.v2-detail .v2-step-number { color: #15905f; font-size: 0.82rem; line-height: 1; font-weight: 800; }
                body.v2-detail .v2-step-icon { width: 3.25rem; height: 3.25rem; background-image: var(--icon-sheet); background-size: 900% 100%; background-position: calc(var(--step-index) * -100%) 0; background-repeat: no-repeat; }
                body.v2-detail .v2-step-button.pending,
                body.v2-detail .v2-step-button.action { --icon-sheet: url('/ui-v2/icons/workflow-icons-gray.png'); color: var(--muted); }
                body.v2-detail .v2-step-button.done,
                body.v2-detail .v2-step-button.fix,
                body.v2-detail .v2-step-button.continue { --icon-sheet: url('/ui-v2/icons/workflow-icons-color.png'); }
                body.v2-detail .v2-step-label { font-size: 0.78rem; line-height: 1.15; text-align: center; white-space: nowrap; }
                body.v2-detail .v2-step-mark { position: absolute; left: 50%; bottom: 0.12rem; transform: translateX(-50%); width: 1.05rem; height: 1.05rem; border-radius: 999px; color: white; font-size: 0.75rem; display: grid; place-items: center; font-family: Arial, sans-serif; font-weight: 800; }
                body.v2-detail .v2-step-button.pending .v2-step-mark,
                body.v2-detail .v2-step-button.action .v2-step-mark { background: #a8afad; }
                body.v2-detail .v2-step-button.done .v2-step-mark { background: #15905f; }
                body.v2-detail .v2-step-button.fix .v2-step-mark { background: #b73732; }
                body.v2-detail .v2-step-button.continue .v2-step-mark { width: auto; height: auto; background: transparent; color: #15905f; font-size: 1.2rem; letter-spacing: 0.08rem; line-height: 1; }
                body.v2-detail .v2-summary-grid { display: grid; grid-template-columns: 2fr 1fr 1fr; gap: 0.7rem; }
                body.v2-detail .v2-next { margin-top: 0.7rem; }
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
                body.v2-detail .v2-skill-row { display: grid; grid-template-columns: minmax(9rem, 13rem) minmax(0, 1fr); gap: 0.6rem; align-items: stretch; }
                body.v2-detail .v2-skill-row #chatSkillDescription { margin: 0; }
                body.v2-detail #currentProjectPanel > button { display: none; }
                body.v2-detail #prototypeWorkflowPanel.v2-prototype-locked input,
                body.v2-detail #prototypeWorkflowPanel.v2-prototype-locked textarea,
                body.v2-detail #prototypeWorkflowPanel.v2-prototype-locked select,
                body.v2-detail #prototypeWorkflowPanel.v2-prototype-locked button { opacity: 0.55; }
                body.v2-detail .v2-action-row button,
                body.v2-detail .v2-chat-controls button,
                body.v2-detail .v2-chat-controls label,
                body.v2-detail .v2-chat-controls select { width: auto; min-height: 2.35rem; padding: 0.5rem 0.72rem; border-radius: 999px; font-size: 0.88rem; }
                body.v2-detail .v2-chat-controls .v2-attach-button { display: inline-flex; align-items: center; justify-content: center; min-width: 2.35rem; cursor: pointer; color: var(--danger); border: 0; background: transparent; font-weight: 900; font-size: 1.65rem; line-height: 1; padding: 0.25rem 0.45rem; }
                body.v2-detail .v2-chat-controls .v2-attach-button input { display: none; }
                body.v2-detail .v2-chat-controls #sendChat { margin-left: auto; min-width: 4.2rem; background: var(--accent-2); }
                @media (max-width: 1000px) {
                  body.v2-detail #v2ContentGrid,
                  body.v2-detail .v2-summary-grid,
                  body.v2-detail .v2-skill-row { grid-template-columns: 1fr; }
                  body.v2-detail #chatPanel,
                  body.v2-detail #v2IterationPanel,
                  body.v2-detail #v2RepairPanel,
                  body.v2-detail #v2AcceptancePanel,
                  body.v2-detail #currentProjectPanel,
                  body.v2-detail #prototypeWorkflowPanel,
                  body.v2-detail #prototypeCommandPanel,
                  body.v2-detail #runsPanel,
                  body.v2-detail #outputPanel { grid-column: 1; grid-row: auto; }
                  body.v2-detail .v2-chat-controls #sendChat { margin-left: 0; }
                }
              </style>
              """)
            .Replace("<section id=\"currentProjectPanel\" class=\"stack\">", """
                  <section id="v2ProgressShell" class="stack">
                    <div id="v2ProgressSteps" class="v2-progress-row"></div>
                    <div class="card v2-next"><strong>下一步建议</strong><p id="v2NextSuggestion" class="muted">点击按钮后扫描项目进度并给出下一步建议。</p><button id="v2JudgeNextStep" class="ghost" type="button">扫描项目判断下一步建议</button></div>
                  </section>
                  <section id="currentProjectPanel" class="stack">
                  """)
            .Replace("</body>", """
              <script>
                document.body.classList.add("v2-detail");
                const v2Steps = [
                  ["new-project", "游戏项目详情", 0],
                  ["create-prototype", "原型骨架创建", 1],
                  ["prototype-acceptance", "原型验收", 2],
                  ["execute-or-repair", "原型验收修复", 4],
                  ["iteration-plan", "完成迭代计划", 3],
                  ["asset-inventory", "确认素材清单", 6],
                  ["package-project", "打包项目文件", 7],
                  ["download-project", "下载项目文件", 8]
                ];
                let v2SelectedStep = "new-project";
                function v2HasPackages() {
                  if (Array.isArray(state.packageList)) return state.packageList.length > 0;
                  return Array.isArray(state.packageList?.packages) && state.packageList.packages.length > 0;
                }
                function v2AssetInventoryConfirmed() {
                  return !!state.assetInventory?.canReadInventory;
                }
                function v2StepStatus(stepId) {
                  const progressStatus = state?.prototypeFailure ? "failed" : "";
                  const progressText = $("prototypeProgress")?.textContent || "";
                  const prototypeStatus = String(state?.v2PrototypeStatus || "").trim().toLowerCase();
                  const succeeded = prototypeStatus === "succeeded";
                  const failed = prototypeStatus === "failed" || progressStatus === "failed" || !!state?.prototypeFailure;
                  if (stepId === "new-project") return state.projectId ? "done" : "pending";
                  if (stepId === "create-prototype") {
                    if (!state.projectId || progressText.includes("idle") || !prototypeStatus) return "pending";
                    return failed ? "fix" : succeeded ? "done" : "pending";
                  }
                  if (stepId === "prototype-acceptance") return succeeded ? "done" : failed ? "fix" : "pending";
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
                    return "pending";
                  }
                  if (stepId === "asset-inventory") return v2AssetInventoryConfirmed() ? "done" : "pending";
                  if (stepId === "package-project") return v2HasPackages() ? "done" : "pending";
                  if (stepId === "download-project") return v2HasPackages() ? "action" : "pending";
                  return "pending";
                }
                function v2ShowStep(stepId) {
                  v2SelectedStep = stepId;
                  const show = id => $(id)?.classList.remove("hidden");
                  const hide = id => $(id)?.classList.add("hidden");
                  ["v2IterationPanel", "v2RepairPanel", "v2AcceptancePanel", "currentProjectPanel", "prototypeWorkflowPanel", "prototypeCommandPanel", "runsPanel", "outputPanel"].forEach(hide);
                  show("chatPanel");
                  if (stepId === "new-project") show("currentProjectPanel");
                  if (stepId === "create-prototype") show("prototypeWorkflowPanel");
                  if (stepId === "prototype-acceptance") show("v2AcceptancePanel");
                  if (stepId === "asset-inventory" || stepId === "package-project" || stepId === "download-project") show("currentProjectPanel");
                  if (stepId === "iteration-plan") show("v2IterationPanel");
                  if (stepId === "execute-or-repair") show("v2RepairPanel");
                  v2ApplyPrototypeFormLock();
                  v2RunStepAction(stepId);
                  v2RenderProgress();
                }
                function v2RunStepAction(stepId) {
                  if (!state.projectId) return;
                  if (stepId === "asset-inventory") {
                    $("loadAssetInventory")?.click();
                    return;
                  }
                  if (stepId === "package-project") {
                    $("createProjectPackage")?.click();
                    return;
                  }
                  if (stepId === "download-project") {
                    $("openProjectDownloads")?.click();
                  }
                }
                function v2CreateIterationPanel() {
                  if ($("v2IterationPanel")) return;
                  const chatPanel = $("chatPanel");
                  if (!chatPanel) return;
                  const panel = document.createElement("section");
                  panel.id = "v2IterationPanel";
                  panel.className = "stack hidden";
                  panel.setAttribute("aria-label", "迭代计划");
                  chatPanel.insertAdjacentElement("afterend", panel);
                  const firstChatRecordHeading = Array.from(chatPanel.querySelectorAll("h2")).find(heading => heading.textContent.trim() === "聊天记录");
                  const iterationStart = Array.from(chatPanel.querySelectorAll("h2")).find(heading => heading.textContent.trim() === "主流程：迭代计划");
                  if (!iterationStart || !firstChatRecordHeading) return;
                  let current = iterationStart;
                  while (current && current !== firstChatRecordHeading) {
                    const next = current.nextElementSibling;
                    panel.appendChild(current);
                    current = next;
                  }
                  v2ArrangeIterationPanel();
                }
                function v2EnsureContentGrid() {
                  if ($("v2ContentGrid")) return;
                  const detailPanel = $("projectDetailPanel");
                  const progressShell = $("v2ProgressShell");
                  if (!detailPanel || !progressShell) return;
                  const grid = document.createElement("div");
                  grid.id = "v2ContentGrid";
                  grid.className = "v2-content-grid";
                  progressShell.insertAdjacentElement("afterend", grid);
                  v2CreateAcceptancePanel();
                  ["chatPanel", "v2IterationPanel", "v2RepairPanel", "v2AcceptancePanel", "currentProjectPanel", "prototypeWorkflowPanel", "prototypeCommandPanel", "runsPanel"].forEach(id => {
                    const element = $(id);
                    if (element) grid.appendChild(element);
                  });
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
                }
                function v2IterationPlanAllowsAcceptance() {
                  const goals = state.iterationPlan?.goals;
                  if (!Array.isArray(goals) || goals.length === 0) return true;
                  return goals.every(goal => ["succeeded", "completed"].includes(String(goal.status || "").trim().toLowerCase()));
                }
                function v2ValidatePrototypeIfAllowed() {
                  if (!v2IterationPlanAllowsAcceptance()) {
                    $("v2NextSuggestion").textContent = "请先完成当前迭代计划，所有目标完成后再进行原型验收。";
                    out("请先完成迭代计划，再进行原型验收。");
                    return;
                  }
                  $("validatePrototype")?.click();
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
                  createPlan?.insertAdjacentElement("beforebegin", mainActions);
                  [createPlan, evaluatePlan, executeGoal].filter(Boolean).forEach(button => mainActions.appendChild(button));

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
                  const repairHeading = Array.from($("v2IterationPanel").querySelectorAll("h2")).find(heading => heading.textContent.trim() === "异常修复计划");
                  let current = repairHeading;
                  while (current) {
                    const next = current.nextElementSibling;
                    panel.appendChild(current);
                    if (current.id === "repairPlanGoals") break;
                    current = next;
                  }
                  const actions = document.createElement("div");
                  actions.id = "v2RepairActions";
                  actions.className = "v2-action-row";
                  createRepair?.insertAdjacentElement("beforebegin", actions);
                  [createRepair, $("executeRepairStep")].filter(Boolean).forEach(button => actions.appendChild(button));
                }
                function resizeChatComposer() {
                  const textarea = $("chatMessage");
                  if (!textarea) return;
                  textarea.style.height = "auto";
                  textarea.style.height = `${Math.min(textarea.scrollHeight, 176)}px`;
                }
                function v2ArrangeChatPanel() {
                  const chatPanel = $("chatPanel");
                  if (!chatPanel) return;
                  const title = Array.from(chatPanel.querySelectorAll("h2")).find(heading => heading.textContent.trim() === "自由聊天");
                  title?.classList.add("hidden");
                  if (title?.nextElementSibling?.tagName === "P") title.nextElementSibling.classList.add("hidden");
                  const flowTitle = Array.from(chatPanel.querySelectorAll("h2")).find(heading => heading.textContent.trim() === "流程记录");
                  flowTitle?.classList.add("hidden");
                  $("feedbackSummary")?.classList.add("hidden");
                  $("feedbackRecords")?.classList.add("hidden");
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
                    attachLabel.className = "v2-attach-button";
                    if (attachLabel.childNodes?.[0]?.nodeType === Node.TEXT_NODE) attachLabel.childNodes[0].textContent = "+";
                    attachLabel.title = "导入 TXT 参考文件";
                  }
                  if ($("clearChatAttachments")) $("clearChatAttachments").textContent = "清空";
                  if (!$("v2CreateIterationPlanFromChat")) {
                    const createPlanButton = document.createElement("button");
                    createPlanButton.id = "v2CreateIterationPlanFromChat";
                    createPlanButton.className = "ghost";
                    createPlanButton.type = "button";
                    createPlanButton.textContent = "创建新迭代计划";
                    createPlanButton.onclick = v2CreateIterationPlanFromChat;
                    controls.appendChild(createPlanButton);
                  }
                  [$("chatAttachmentFiles")?.closest("label"), $("clearChatAttachments"), $("syncChatHistory"), $("downloadChatHistory"), $("v2CreateIterationPlanFromChat"), $("createGddDocument"), $("sendChat")].filter(Boolean).forEach(element => controls.appendChild(element));
                  $("chatMessage").addEventListener("input", v2RenderChatIterationPlanButtonState);
                  $("chatMessage").addEventListener("input", resizeChatComposer);
                  resizeChatComposer();
                  v2RenderChatIterationPlanButtonState();
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
                  const button = $("v2CreateIterationPlanFromChat");
                  if (!button) return;
                  button.disabled = !v2CanCreateIterationPlanFromChat();
                  button.title = !v2IterationPlanExists()
                    ? "当前还没有迭代计划。"
                    : !v2IterationPlanCompleted()
                      ? "请先完成当前迭代计划。"
                      : !v2PrototypeValidationPassedForPlanning()
                        ? "请先完成原型验收。"
                        : "";
                }
                async function v2CreateIterationPlanFromChat() {
                  if (!guardGlobalAction()) return;
                  if (!v2CanCreateIterationPlanFromChat()) {
                    out("需要满足：已有迭代计划、当前迭代计划已完成、原型验收通过。");
                    return;
                  }
                  const message = $("chatMessage").value.trim();
                  if (!message) return out("请先在聊天输入框填写新的迭代目标。");
                  await submitIterationPlanFromFeedback(message, "正在根据聊天内容创建新的迭代计划...", "manual_feedback");
                  v2RenderChatIterationPlanButtonState();
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
                  const status = v2PrototypeStatus();
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
                  if (form.sourcePath) {
                    $("draftImportStatus").className = "card muted";
                    $("draftImportStatus").textContent = `已载入原型记录：${form.sourcePath}`;
                  }
                }
                function v2CompletedIterationStatus(status) {
                  return ["succeeded", "completed", "done"].includes(String(status || "").trim().toLowerCase());
                }
                function v2CurrentPrototypeStatus() {
                  return String(state?.v2PrototypeStatus || "").trim().toLowerCase();
                }
                function v2HasPrototypeSkeleton() {
                  const status = v2CurrentPrototypeStatus();
                  return !!status && status !== "idle";
                }
                function v2HasFailedPrototypeAcceptance() {
                  return v2CurrentPrototypeStatus() === "failed" || !!state.prototypeFailure;
                }
                function v2BuildLocalNextStepSuggestion() {
                  const goals = Array.isArray(state.iterationPlan?.goals) ? state.iterationPlan.goals : [];
                  const hasPlan = !!state.iterationPlan?.session && goals.length > 0;
                  const allGoalsCompleted = hasPlan && goals.every(goal => v2CompletedIterationStatus(goal.status));
                  const hasOpenGoal = hasPlan && goals.some(goal => !v2CompletedIterationStatus(goal.status));
                  const validationPassed = v2PrototypeValidationPassedForPlanning();
                  if (!v2HasPrototypeSkeleton()) {
                    return "建议：请先进行 2. 原型骨架创建。\n\n如果你还没有整理清楚游戏设定，也可以先在自由聊天的能力模式中激活“游戏策划大师”，让它协助你梳理并创建策划文档，再回到 2. 原型骨架创建填写表单。";
                  }
                  if (v2HasFailedPrototypeAcceptance()) {
                    return "建议：请先进行 4. 原型验收修复。\n\n当前原型验收没有通过，需要先生成或执行修复计划，把失败项修到可验收状态，再继续后续流程。";
                  }
                  if (validationPassed && !hasPlan) {
                    return "建议：请先进行 5. 生成迭代计划。\n\n原型验收已经通过，但还没有生成迭代计划。下一步应该把游戏原型需要补齐的功能拆成可执行 step，逐项完成游戏功能。";
                  }
                  if (hasOpenGoal) {
                    return "建议：请先完成当前迭代计划的执行或修复。\n\n当前迭代计划中仍有至少一个 step 不是完成状态。请继续执行下一目标；如果某个 step 进入 needs fix 或失败状态，请先完成对应修复。";
                  }
                  if (allGoalsCompleted && !validationPassed) {
                    return "建议：请重新进行原型验收。\n\n当前迭代计划已经全部完成，但本轮迭代后的原型验收还没有重新通过。请回到 3. 原型验收，确认迭代后的项目仍然可以正常运行。";
                  }
                  if (allGoalsCompleted && validationPassed) {
                    return "建议：可以确认素材清单后打包项目文件。\n\n请依次进行 6. 确认素材清单、7. 打包项目文件、8. 下载项目文件；在下载列表中下载游戏项目压缩包，并在本地 Godot 里试玩和验证。试玩后把结果发到聊天界面，我们再准备第二轮迭代计划。";
                  }
                  return "建议：请先刷新项目状态或重新选择项目。\n\n当前页面没有读取到足够的项目状态，无法判断下一步。";
                }
                async function v2JudgeNextStepLocally() {
                  if (!state.projectId) return out("请先选择一个项目。");
                  const button = $("v2JudgeNextStep");
                  button.disabled = true;
                  button.textContent = "扫描中...";
                  $("v2NextSuggestion").textContent = "正在扫描项目状态...";
                  try {
                    await loadProjectRuntimeState();
                    await loadIterationPlan();
                    await loadRepairPlan();
                    $("v2NextSuggestion").textContent = v2BuildLocalNextStepSuggestion();
                  } catch (error) {
                    $("v2NextSuggestion").textContent = "项目状态扫描失败，请稍后重试或先刷新页面。";
                    showError(error);
                  } finally {
                    button.disabled = false;
                    button.textContent = "扫描项目判断下一步建议";
                  }
                }
                function v2RenderProgress() {
                  const shell = $("v2ProgressSteps");
                  if (!shell) return;
                  shell.innerHTML = v2Steps.map(([id, label, iconIndex], index) => {
                    const status = v2StepStatus(id);
                    const mark = status === "done" ? "✓" : status === "fix" ? "×" : status === "continue" ? "•••" : "";
                    return `<button class="v2-step-button ${status} ${v2SelectedStep === id ? "active" : ""}" data-v2-step="${id}" style="--step-index:${iconIndex ?? index}"><span class="v2-step-number">${index + 1}</span><span class="v2-step-icon"></span><span class="v2-step-label">${label}</span><span class="v2-step-mark">${mark}</span></button>`;
                  }).join("");
                  document.querySelectorAll("[data-v2-step]").forEach(button => button.onclick = () => v2ShowStep(button.dataset.v2Step));
                  v2RenderChatIterationPlanButtonState();
                }
                const v2OriginalShowProjectDetail = showProjectDetail;
                showProjectDetail = function() {
                  v2CreateIterationPanel();
                  v2ArrangeChatPanel();
                  v2EnsureContentGrid();
                  v2OriginalShowProjectDetail();
                  v2LoadPrototypeValidationInvalidation();
                  v2EnsureContentGrid();
                  $("chatPanel")?.classList.remove("hidden");
                  v2ShowStep(v2SelectedStep);
                  v2ApplyPrototypeFormLock();
                };
                const v2OriginalUpdateChatPanelVisibility = updateChatPanelVisibility;
                updateChatPanelVisibility = function(progress) {
                  state.v2PrototypeStatus = progress?.status || "";
                  v2CreateIterationPanel();
                  v2ArrangeChatPanel();
                  v2EnsureContentGrid();
                  v2OriginalUpdateChatPanelVisibility(progress);
                  v2EnsureContentGrid();
                  $("chatPanel")?.classList.remove("hidden");
                  if (v2SelectedStep === "create-prototype") $("prototypeWorkflowPanel")?.classList.remove("hidden");
                  v2ApplyPrototypeFormSnapshot(progress);
                  v2ApplyPrototypeFormLock();
                  v2RenderProgress();
                };
                const v2OriginalSubmitIterationPlanFromFeedback = submitIterationPlanFromFeedback;
                submitIterationPlanFromFeedback = async function(message, busyText, sourceKind = "manual_feedback") {
                  await v2OriginalSubmitIterationPlanFromFeedback(message, busyText, sourceKind);
                  if (state.iterationPlan?.session) {
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
                $("v2JudgeNextStep").onclick = v2JudgeNextStepLocally;
                setInterval(v2RenderProgress, 2000);
              </script>
            </body>
            """);
    }

    public string RenderShell()
    {
        return """
            <!doctype html>
            <html lang="zh-CN">
            <head>
              <meta charset="utf-8">
              <meta name="viewport" content="width=device-width, initial-scale=1">
              <title>积木云 Phase A 原型控制台</title>
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
                  padding: 2.2rem clamp(1rem, 4vw, 4rem) 1rem;
                  display: grid;
                  gap: 0.8rem;
                }
                .header-row {
                  display: grid;
                  grid-template-columns: minmax(0, 1fr) auto;
                  gap: 1rem;
                  align-items: start;
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
                h1 { margin: 0; font-size: clamp(2rem, 5vw, 4.5rem); letter-spacing: -0.06em; }
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
                .busy-banner { margin-top: 0.75rem; border: 1px solid var(--accent-2); background: #fff8e6; border-radius: 0.9rem; padding: 0.85rem; }
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
                  background: #fffdf8;
                  border: 1px solid var(--line);
                  border-radius: 1.2rem;
                  box-shadow: 0 2rem 5rem rgba(23, 33, 27, 0.28);
                  padding: 1rem;
                  display: grid;
                  gap: 0.8rem;
                }
                .modal-card.modal-card-large { width: min(58rem, 100%); }
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
                    <h1>积木云 Phase A 原型控制台</h1>
                    <p>Phase A Prototype Console: account-scoped console for creating projects, running cloud prototype routes, reviewing logs, and downloading artifacts.</p>
                  </div>
                  <div id="userTopActions" class="top-actions hidden">
                    <label class="user-only-action">模型选择 <select id="globalModel"><option value="gpt-5.5" selected>5.5</option><option value="gpt-5.4">5.4</option></select></label>
                    <button id="openCreateProjectPage" class="secondary user-only-action" data-global-action="true">创建项目</button>
                    <button id="openProjectListModal" class="ghost user-only-action">项目列表</button>
                    <button id="logout" class="danger-button">退出登录</button>
                  </div>
                </div>
                <div id="activeRunBanner" class="busy-banner hidden"></div>
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
              <main>
                <section id="sessionPanel" class="stack login-shell">
                  <h2>会话</h2>
                  <label>Access token <input id="token" type="password" autocomplete="off" placeholder="Paste the server-issued token"></label>
                  <button id="saveToken">验证并进入</button>
                  <p id="sessionStatus" class="muted">Token 只保存在当前浏览器 localStorage，不会写入仓库。</p>
                </section>
                <section id="createProjectPanel" class="stack hidden">
                  <h2 id="createProjectTitle">创建项目</h2>
                  <label>项目名 <input id="projectName" placeholder="可选，不填会自动生成"></label>
                  <label>游戏名 <input id="gameName" placeholder="例如：Demo Game"></label>
                  <label>游戏类型/玩法方向 <input id="gameTypeSource" placeholder="例如：RPG、塔防、Roguelike、平台跳跃、解谜冒险"></label>
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
                    <button id="loadAccountAudit" class="ghost">Load account audit</button>
                    <button id="downloadAccountAuditCsv" class="ghost">Download account audit CSV</button>
                    <div id="createUserAccountResult" class="card muted">Admin only. The token is shown once after creation.</div>
                    <div id="userAccounts" class="card-list"></div>
                    <div id="adminLlmUsageStatus" class="card muted">No admin LLM usage loaded.</div>
                    <div id="adminLlmRunsStatus" class="card muted">No admin LLM run audit loaded.</div>
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
                    <label>导入原型草稿 TXT <input id="draftFile" type="file" accept=".txt,text/plain"></label>
                    <button id="importDraft" class="ghost" data-global-action="true">分析草稿并回填</button>
                    <div id="draftImportStatus" class="card muted">可选：创建项目后上传 txt 草稿，由后端模型分析后回填原型表单。</div>
                    <label>原型标识 Slug <input id="protoSlug" placeholder="demo-prototype"></label>
                    <label>原型假设 <textarea id="hypothesis" placeholder="这个原型要验证什么？"></textarea></label>
                    <label>核心玩家幻想 <textarea id="corePlayerFantasy" placeholder="玩家应该感受到什么？"></textarea></label>
                    <label>最小可玩循环 <textarea id="minimumPlayableLoop" placeholder="玩家反复执行的最小闭环是什么？"></textarea></label>
                    <label>成功标准，每行一条 <textarea id="successCriteria" placeholder="例如：30 秒内能理解目标"></textarea></label>
                    <label>游戏功能 <textarea id="gameFeature" placeholder="本次要实现或验证的核心功能"></textarea></label>
                    <label>核心玩法循环 <textarea id="coreGameplayLoop" placeholder="输入、反馈、奖励、升级或失败的循环"></textarea></label>
                    <label>胜利/失败条件 <textarea id="winFailConditions" placeholder="如何判定玩家成功或失败"></textarea></label>
                    <button id="repairPrototype" class="ghost hidden" data-global-action="true">生成修复计划</button>
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
                    <h2>主流程：迭代计划</h2>
                    <p class="muted">推荐流程：先把较大的优化目标拆成 3-7 个小目标，再逐个执行。每次只推进一个目标，完成后停下，由你决定是否继续。</p>
                    <button id="createIterationPlan" class="ghost" data-global-action="true">生成迭代计划</button>
                    <button id="evaluateIterationPlan" class="ghost" data-global-action="true">评估当前迭代计划</button>
                    <button id="executeIterationGoal" class="secondary" data-global-action="true">执行下一目标</button>
                    <p id="iterationAutoRefreshHint" class="muted">执行中会自动刷新进度，你可以停留在当前页面直接查看状态变化。</p>
                    <div id="iterationPlanStatus" class="card muted">尚未生成迭代计划。</div>
                    <div id="iterationPlanEvaluation" class="card muted">尚未评估当前迭代计划。</div>
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
                    <button id="createGddDocument" class="ghost" data-global-action="true">创建策划文档</button>
                    <button id="sendChat" class="secondary">发送</button>
                    <button id="evaluateIterationPlanFromChat" class="ghost" data-global-action="true">评估当前计划是否值得继续</button>
                    <button id="submitFormalFeedback" class="ghost" data-global-action="true">提交反馈到 Needs Fix 路由</button>
                    <h2>流程记录</h2>
                    <div id="feedbackSummary" class="card muted">尚未生成迭代计划。</div>
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
                const state = { projectId: "", projects: [], runs: [], packageList: null, assetInventory: null, assetInventoryExpanded: false, chatHistory: [], chatAttachments: [], skillActions: [], authenticated: false, prototypeReadyForFeedback: false, activeRun: null, localBusy: false, nextSuggestedFeedback: "", draftAnalysisRunning: false, prototypeFailure: "", iterationPlan: null, iterationPlanEvaluation: null };
                const prototypeInputIds = ["protoSlug", "hypothesis", "corePlayerFantasy", "minimumPlayableLoop", "successCriteria", "gameFeature", "coreGameplayLoop", "winFailConditions"];
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
                const token = () => $("token").value.trim();
                const headers = () => ({ "Authorization": `Bearer ${token()}`, "Content-Type": "application/json" });

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
                }

                function showCreateProjectPage() {
                  closeUserModals();
                  $("sessionPanel").classList.add("hidden");
                  $("adminPanel").classList.add("hidden");
                  $("createProjectPanel").classList.remove("hidden");
                }

                function hideCreateProjectPage() {
                  $("createProjectPanel").classList.add("hidden");
                }

                function setTokenFromStorage() {
                  $("token").value = localStorage.getItem("phaseAAccessToken") || localStorage.getItem("phaseAAdminToken") || "";
                }

                function renderChatHistory() {
                  applyChatWorkflowActions();
                  state.chatHistory.forEach(message => {
                    if (typeof message.content === "string") message.content = sanitizePublicChatContent(message.content);
                  });
                  $("chatHistory").innerHTML = state.chatHistory.map((message, index) => {
                    const roleClass = message.role === "user" ? "v2-chat-message-user" : "v2-chat-message-assistant";
                    const pendingClass = message.pending ? " v2-chat-message-pending" : "";
                    const pendingLabel = message.pending ? "<span class=\"v2-chat-pending-label\">生成中</span>" : "";
                    const contentHtml = message.role === "user"
                      ? `<span>${escapeHtml(message.content)}</span>`
                      : renderAssistantChatContent(message.content);
                    return `
                      <div class="v2-chat-message ${roleClass}${pendingClass}">
                        ${pendingLabel}
                        ${contentHtml}
                      </div>
                    `;
                  }).join("") || "<p class='muted'>还没有对话。</p>";
                }

                function renderAssistantChatContent(content) {
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
                  return parts.join("") || "<p></p>";
                }

                function renderInlineMarkdown(value) {
                  let html = escapeHtml(value || "");
                  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
                  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
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
                  renderChatHistory();
                }

                async function loadServerChatHistoryForProject(projectId) {
                  if (!projectId) return;
                  try {
                    const result = await api(`/api/projects/${projectId}/chat-history`);
                    state.chatHistory = (result.messages || [])
                      .map(message => ({
                        role: message.role,
                        content: sanitizePublicChatContent(message.content),
                        kind: message.kind || null,
                        continueConsumed: !!message.continueConsumed,
                        suggestedFeedback: sanitizePublicChatContent(message.suggestedFeedback || "")
                      }))
                      .filter(isStoredChatMessage)
                      .slice(-maxStoredChatMessages);
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
                    state.iterationPlanEvaluation = null;
                    renderIterationPlan();
                    return;
                  }
                  try {
                    state.iterationPlan = await api(`/api/projects/${state.projectId}/iteration-plan/latest`);
                    state.iterationPlanEvaluation = state.iterationPlan?.latestEvaluation || null;
                  } catch (error) {
                    if (error?.status === 404) {
                      state.iterationPlan = null;
                      state.iterationPlanEvaluation = null;
                    } else {
                      showError(error);
                    }
                  }
                  renderIterationPlan();
                }

                async function loadRepairPlan() {
                  if (!state.projectId) {
                    state.repairPlan = null;
                    renderRepairPlan();
                    return;
                  }
                  try {
                    state.repairPlan = await api(`/api/projects/${state.projectId}/repair-plan/latest`);
                  } catch (error) {
                    if (error?.status === 404) {
                      state.repairPlan = null;
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
                  $("repairPlanGoals").innerHTML = goals.map(goal => `
                    <div class="card">
                      <strong>repair-step${String(goal.goalIndex || 0).padStart(2, "0")} · ${escapeHtml(goal.status || "pending")}</strong>
                      <p>${escapeHtml(goal.title || "")}</p>
                      <p class="muted">${escapeHtml(repairGoalDisplayText(goal.description || ""))}</p>
                      ${goal.acceptanceHint ? `<p class="muted">验收：${escapeHtml(goal.acceptanceHint)}</p>` : ""}
                      ${goal.resultSummary ? `<p class="muted">结果：${escapeHtml(goal.resultSummary)}</p>` : ""}
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

                function repairPlanChatSummary(result) {
                  const goals = Array.isArray(result?.goals) ? result.goals : [];
                  const lines = [
                    result?.summary || "修复计划已生成。",
                    "",
                    "下一步：点击“执行下一项修复”，系统会只处理第一项未完成修复步骤。"
                  ];
                  if (goals.length) {
                    lines.push("", "修复步骤：");
                    goals.forEach(goal => lines.push(`${goal.goalIndex}. ${goal.title}`));
                  }
                  return lines.join("\n").trim();
                }

                function renderIterationPlan() {
                  const plan = state.iterationPlan;
                  if (!plan || !plan.session) {
                    $("iterationPlanStatus").className = "card muted";
                    $("iterationPlanStatus").textContent = "尚未生成迭代计划。";
                    $("iterationPlanEvaluation").className = "card muted";
                    $("iterationPlanEvaluation").textContent = "尚未评估当前迭代计划。";
                    $("iterationPlanGoals").innerHTML = "";
                    $("createIterationPlan").disabled = isGlobalBusy();
                    $("createIterationPlan").textContent = "生成新的迭代计划";
                    $("evaluateIterationPlan").disabled = true;
                    $("evaluateIterationPlan").textContent = "请先生成迭代计划";
                    $("evaluateIterationPlanFromChat").disabled = true;
                    $("evaluateIterationPlanFromChat").textContent = "请先生成迭代计划";
                    $("executeIterationGoal").disabled = true;
                    $("executeIterationGoal").textContent = "请先生成迭代计划";
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
                  const canCreateNewPlan = (!hasPending && !hasNeedsFix) || shouldRefinePlan;
                  $("iterationPlanStatus").className = "card";
                  $("iterationPlanStatus").innerHTML = `
                    <strong>${escapeHtml(session.status || "ready")}</strong>
                    <p>${escapeHtml(session.overallGoal || "")}</p>
                    ${session.latestSummary ? `<p class="muted">${escapeHtml(session.latestSummary)}</p>` : ""}
                    <p class="muted">当前目标序号：${escapeHtml(String(session.currentGoalIndex || 0))}</p>
                    ${planningAnalysis ? `<p class="muted">生成依据：${escapeHtml(planningAnalysis.analysisSummary || "")}</p>` : ""}
                    ${planningAnalysis ? `<p class="muted">原型状态：${escapeHtml(planningAnalysis.latestPrototypeStatus || "unknown")} · 草稿覆盖率：${escapeHtml(String(planningAnalysis.draftCoveragePercent ?? 0))}%${planningAnalysis.templateId ? ` · 模板：${escapeHtml(planningAnalysis.templateId)}` : ""}</p>` : ""}
                    ${planningAnalysis && Array.isArray(planningAnalysis.fieldCoverage) && planningAnalysis.fieldCoverage.length
                      ? `<p class="muted">字段判断：${escapeHtml(planningAnalysis.fieldCoverage.map(item => `${item.field}:${item.status}${item.missingReason ? `(${item.missingReason})` : item.evidence ? `(${item.evidence})` : ""}`).join(" · "))}</p>`
                      : ""}
                  `;
                  $("createIterationPlan").disabled = !canCreateNewPlan || blockedByCurrentGoal || isGlobalBusy();
                  $("createIterationPlan").textContent = "根据评估更新迭代计划";
                  $("evaluateIterationPlan").disabled = isGlobalBusy();
                  $("evaluateIterationPlan").textContent = "评估当前迭代计划";
                  $("evaluateIterationPlanFromChat").disabled = isGlobalBusy();
                  $("evaluateIterationPlanFromChat").textContent = "评估当前计划是否值得继续";
                  $("executeIterationGoal").disabled = !hasPending || hasNeedsFix || shouldRefinePlan || blockedByCurrentGoal || isGlobalBusy();
                  $("executeIterationGoal").textContent = hasNeedsFix
                    ? "请先修复当前目标"
                    : shouldRefinePlan
                      ? "建议先重拆迭代计划"
                      : hasPending
                        ? "执行下一目标"
                        : "当前没有待执行目标";
                  renderIterationPlanEvaluation();
                  renderChatHistory();
                  $("iterationPlanGoals").innerHTML = goals.map(goal => `
                    <div class="card">
                      <strong>step ${escapeHtml(String(goal.goalIndex))} · ${escapeHtml(goal.status || "pending")}</strong>
                      <p>${escapeHtml(goal.title || "")}</p>
                      <p class="muted">${escapeHtml(goal.description || "")}</p>
                      ${goal.acceptanceHint ? `<p class="muted">完成判断：${escapeHtml(goal.acceptanceHint)}</p>` : ""}
                      ${goal.resultSummary ? `<p class="muted">结果：${escapeHtml(goal.resultSummary)}</p>` : ""}
                      ${["needs_fix", "failed"].includes(String(goal.status || "").trim().toLowerCase())
                        ? `<button class="secondary" data-global-action="true" data-needs-fix-goal="${escapeHtml(String(goal.goalIndex || ""))}">运行 Needs Fix 路由</button>`
                        : ""}
                    </div>`).join("");
                  document.querySelectorAll("[data-needs-fix-goal]").forEach(button => button.onclick = () => runNeedsFixIterationGoal(button.dataset.needsFixGoal));
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
                      : "用户提交了报错/修复反馈，请通过 needs-fix 顶层路由处理。如果当前项目还没有可修复目标，请返回明确的前置条件提示，不要生成迭代计划。",
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
                  const evaluation = state.iterationPlanEvaluation;
                  if (!evaluation) {
                    $("iterationPlanEvaluation").className = "card muted";
                    $("iterationPlanEvaluation").textContent = "尚未评估当前迭代计划。";
                    return;
                  }
                  const decision = String(evaluation.decision || "").trim().toLowerCase();
                  const actionHint = decision === "llm_failed"
                    ? "LLM 调用失败，需先修复 LLM 后再继续；系统不会用本地规则替代评估。"
                    : decision === "should_refine_plan"
                    ? "推荐先点击“按评估重拆迭代计划”，不要直接执行下一目标。"
                    : decision === "ready_to_execute"
                      ? "推荐直接执行下一目标；如果目标变化较大，再重新生成计划。"
                      : "推荐先处理当前阻塞项，再决定是否继续。";
                  $("iterationPlanEvaluation").className = "card";
                  $("iterationPlanEvaluation").innerHTML = `
                    <strong>${escapeHtml(evaluation.decision || "pending")}</strong>
                    <p>${escapeHtml(evaluation.summary || "")}</p>
                    ${evaluation.reason ? `<p class="muted">${escapeHtml(evaluation.reason)}</p>` : ""}
                    ${evaluation.suggestedAction ? `<p class="muted">建议动作：${escapeHtml(evaluation.suggestedAction)}</p>` : ""}
                    <p class="muted">页面建议：${escapeHtml(actionHint)}</p>
                    ${evaluation.suggestedPromptForRegeneration ? `<p class="muted">建议重拆提示词：${escapeHtml(evaluation.suggestedPromptForRegeneration)}</p>` : ""}
                  `;
                }

                async function createIterationPlan() {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("请先选择一个项目。");
                  const typedMessage = $("chatMessage").value.trim();
                  const message = typedMessage || state.nextSuggestedFeedback || defaultNextSuggestedFeedback();
                  const sourceKind = typedMessage ? "manual_feedback" : "completion_suggestion";
                  if (!typedMessage) {
                    out("未输入优化目标，已使用当前下一步建议生成迭代计划。");
                  }
                  await submitIterationPlanFromFeedback(message, "正在生成迭代计划...", sourceKind);
                }

                function buildIterationPlanEvaluationChatMessage(evaluation) {
                  if (!evaluation) return "当前没有可用的迭代计划评估结果。";
                  const lines = [
                    "迭代计划继续评估结果：",
                    `decision: ${String(evaluation.decision || "pending").trim()}`,
                    String(evaluation.summary || "").trim()
                  ].filter(Boolean);
                  if (evaluation.reason) lines.push(`原因：${String(evaluation.reason).trim()}`);
                  if (evaluation.suggestedAction) lines.push(`建议动作：${String(evaluation.suggestedAction).trim()}`);
                  if (evaluation.suggestedPromptForRegeneration) lines.push(`建议重拆提示词：${String(evaluation.suggestedPromptForRegeneration).trim()}`);
                  return lines.join("\n");
                }

                function resolveIterationPlanEvaluationSuggestedFeedback(evaluation) {
                  const decision = String(evaluation?.decision || "").trim().toLowerCase();
                  if (decision === "llm_failed") {
                    return "";
                  }
                  if (decision === "should_refine_plan") {
                    return String(evaluation?.suggestedPromptForRegeneration || state.nextSuggestedFeedback || defaultNextSuggestedFeedback()).trim();
                  }
                  if (decision === "ready_to_execute") {
                    return "__iteration_plan_execute_next__";
                  }
                  return "";
                }

                async function evaluateIterationPlan(announceInChat = false) {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("请先选择一个项目。");
                  if (!state.iterationPlan?.session) return out("请先生成迭代计划。");
                  setLocalBusy(true, "正在评估当前迭代计划，请等待当前任务执行完毕。");
                  try {
                    state.iterationPlanEvaluation = await api(`/api/projects/${state.projectId}/iteration-plan/evaluate`, {
                      method: "POST",
                      body: JSON.stringify({})
                    });
                    if (state.iterationPlan) {
                      state.iterationPlan.latestEvaluation = state.iterationPlanEvaluation;
                    }
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
                    if (announceInChat) {
                      state.chatHistory.push({
                        role: "assistant",
                        content: buildIterationPlanEvaluationChatMessage(state.iterationPlanEvaluation),
                        kind: "iteration-plan-evaluation",
                        evaluationDecision: state.iterationPlanEvaluation?.decision || "",
                        suggestedFeedback: resolveIterationPlanEvaluationSuggestedFeedback(state.iterationPlanEvaluation)
                      });
                      renderChatHistory();
                      saveChatHistoryForProject();
                    }
                    out(state.iterationPlanEvaluation);
                  } catch (error) {
                    showError(error);
                  } finally {
                    setLocalBusy(false);
                    await refreshActiveRun();
                  }
                }

                async function submitIterationPlanFromFeedback(message, busyText, sourceKind = "manual_feedback") {
                  setLocalBusy(true, "正在生成迭代计划，请等待当前任务执行完毕。");
                  try {
                    state.chatHistory.push({ role: "user", content: message, kind: "iteration-plan-request" });
                    renderChatHistory();
                    saveChatHistoryForProject();
                    $("chatMessage").value = "";
                    const result = await api(`/api/projects/${state.projectId}/iteration-plan`, {
                      method: "POST",
                      body: JSON.stringify({ message, sourceKind, attachments: currentChatAttachmentsForRun() })
                    });
                    state.iterationPlan = {
                      session: {
                        sessionId: result.sessionId,
                        status: result.status,
                        overallGoal: message,
                        currentGoalIndex: 0,
                        latestSummary: result.summary
                      },
                      goals: result.goals || [],
                      goalRuns: [],
                      latestEvaluation: null
                    };
                    state.iterationPlanEvaluation = null;
                    const summary = result.goals?.length
                      ? `${result.summary}\n\n本次目标拆分：\n${result.goals.map(goal => `${goal.goalIndex}. ${goal.title}`).join("\n")}`
                      : result.summary;
                    state.chatHistory.push({ role: "assistant", content: summary, kind: "iteration-plan-result" });
                    renderIterationPlan();
                    renderChatHistory();
                    saveChatHistoryForProject();
                    out(result);
                  } catch (error) {
                    showError(error);
                  } finally {
                    clearChatAttachments();
                    setLocalBusy(false);
                    await loadIterationPlan();
                    await refreshActiveRun();
                  }
                }

                async function executeIterationGoal() {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("请先选择一个项目。");
                  if (!state.iterationPlan?.session) return out("请先生成迭代计划。");
                  const evaluationDecision = currentIterationPlanDecision();
                  if (evaluationDecision === "should_refine_plan") return out("当前评估建议先重拆迭代计划，已停止执行旧目标。");
                  if (evaluationDecision === "llm_failed") return out("当前迭代计划评估失败，请先修复评估调用并重新评估计划。");
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
                    await refreshActiveRun();
                  }
                }

                async function createRepairPlan() {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("请先选择一个项目。");
                  setLocalBusy(true, "正在生成修复计划，请等待当前任务执行完毕。");
                  try {
                    const result = await api(`/api/projects/${state.projectId}/repair-plan`, { method: "POST" });
                    state.repairPlan = result;
                    await loadServerChatHistoryForProject(state.projectId);
                    renderRepairPlan();
                    state.chatHistory.push({ role: "assistant", content: repairPlanChatSummary(result), kind: "repair-plan-visible-summary" });
                    renderChatHistory();
                    saveChatHistoryForProject();
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
                  const compact = state.chatHistory.filter(isStoredChatMessage).slice(-maxStoredChatMessages);
                  compact.forEach(message => message.content = sanitizePublicChatContent(message.content));
                  compact.forEach(message => {
                    if (message.suggestedFeedback) message.suggestedFeedback = sanitizePublicChatContent(message.suggestedFeedback);
                  });
                  state.chatHistory = compact;
                  localStorage.setItem(chatStorageKey(), JSON.stringify(compact));
                }

                function chatMessageKey(message) {
                  return `${message?.role || ""}|${message?.kind || ""}|${sanitizePublicChatContent(message?.content || "")}`;
                }

                function isStoredChatMessage(message) {
                  return message &&
                    !message.pending &&
                    (message.role === "user" || message.role === "assistant") &&
                    typeof message.content === "string" &&
                    message.content.trim().length > 0;
                }

                function sanitizePublicChatContent(value) {
                  return String(value || "")
                    .replace(/(?:本轮目标：|Direction lock:|Project README:|Recovery source consumed:|Current goal:|Scope rule:)[\s\S]*$/gi, "")
                    .replace(/[A-Za-z]:[\\/][^\s`'"，。；：、）)]+/g, "")
                    .replace(/(?<![\w.])\/(?:[A-Za-z0-9._-]+\/)+[A-Za-z0-9._-]+/g, "")
                    .replace(/(?<![\w.-])[\w.-]+\.(?:ps1|cmd|bat|sh|py|csproj|sln|json|toml|yaml|yml|md|log)(?![\w.-])/gi, "")
                    .replace(/^\s*(?:&\s*)?(?:(?:dotnet\s+(?:test|run|build|publish|restore))|(?:py(?:thon)?\s+[-\w.\/\\])|(?:powershell(?:\.exe)?\s+[-/]\w+)|(?:cmd(?:\.exe)?\s+\/[ck])|(?:codex(?:\.cmd)?\s+(?:exec|run|review|--|-))|(?:caddy(?:\.exe)?\s+(?:run|reload|fmt|--|-))|(?:git\s+\w+)|(?:rg\s+.+)|(?:node\s+.+)|(?:npm\s+\w+))[^\r\n]*/gim, "")
                    .replace(/\b(?:logs\/ci|logs\\ci|active-prototypes|workspaces|GODOT_BIN|PHASEA_[A-Z0-9_]+)\b[^\r\n，。；]*/gi, "")
                    .replace(/[ \t]{2,}/g, " ")
                    .replace(/\n{3,}/g, "\n\n")
                    .trim();
                }

                function startChatThinkingMessage() {
                  const id = `pending-${Date.now()}-${Math.random().toString(16).slice(2)}`;
                  let index = 0;
                  const message = { role: "assistant", content: chatThinkingPrompts[index], pending: true, pendingId: id };
                  state.chatHistory.push(message);
                  renderChatHistory();
                  const timer = setInterval(() => {
                    const pending = state.chatHistory.find(item => item.pendingId === id);
                    if (!pending) {
                      clearInterval(timer);
                      return;
                    }
                    index = (index + 1) % chatThinkingPrompts.length;
                    pending.content = chatThinkingPrompts[index];
                    renderChatHistory();
                  }, 5000);
                  return {
                    complete(content, failed = false) {
                      clearInterval(timer);
                      const pending = state.chatHistory.find(item => item.pendingId === id);
                      if (pending) {
                        pending.content = content;
                        pending.pending = false;
                        delete pending.pendingId;
                        if (failed) pending.failed = true;
                      } else {
                        state.chatHistory.push({ role: "assistant", content, failed });
                      }
                      renderChatHistory();
                      saveChatHistoryForProject();
                    }
                  };
                }

                function showLoggedOut() {
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
                  $("sessionStatus").textContent = "Please paste an access token to sign in.";
                }

                function showAdminShell(role = state.role || "user") {
                  state.authenticated = true;
                  state.role = role;
                  const isAdmin = role === "admin";
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
                    $("initStatusText").innerHTML = `<strong class="danger">创建失败。</strong><br>${escapeHtml(error || "初始化失败，请查看运行记录。")}`;
                    return;
                  }
                  $("initStatusText").textContent = "项目初始化配置中...请稍等 2-5 分钟后刷新页面。";
                }

                function showProjectDetail() {
                  showAdminShell();
                  $("initStatusPanel").classList.add("hidden");
                  $("projectDetailPanel").classList.remove("hidden");
                }

                function hasInitializingProject(projects) {
                  return projects.some(p => p.bootstrapStatus === "running");
                }

                function failedProject(projects) {
                  return projects.find(p => p.bootstrapStatus === "failed");
                }

                function listableProjects(projects) {
                  return projects.filter(p => p.bootstrapStatus !== "running");
                }

                function showCreationFailure(error) {
                  showCreateProjectPage();
                  $("adminPanel").classList.remove("hidden");
                  $("initStatusPanel").classList.remove("hidden");
                  $("initStatusText").innerHTML = `<strong class="danger">创建失败。</strong><br>${escapeHtml(error || "初始化失败，失败项目已自动清理。")}`;
                }



                async function sendChat() {
                  if (!state.projectId) return out("请先选择一个项目。");
                  const message = $("chatMessage").value.trim();
                  if (!message) return out("请输入消息。");
                  $("sendChat").disabled = true;
                  $("sendChat").textContent = "发送中...";
                  try {
                    const payload = {
                      message,
                      model: $("globalModel").value || null,
                      skillActionId: $("chatSkillMode").value || "normal",
                      attachments: currentChatAttachmentsForRun(),
                      history: state.chatHistory.slice(-3)
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
                    clearChatAttachments();
                    $("sendChat").disabled = false;
                    $("sendChat").textContent = "发送";
                    await refreshActiveRun();
                  }
                }

                async function createGddDocument() {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("请先选择一个项目。");
                  const message = $("chatMessage").value.trim();
                  const button = $("createGddDocument");
                  setLocalBusy(true, "正在创建策划 GDD 文档，请等待当前任务执行完毕。");
                  button.disabled = true;
                  button.textContent = "创建中...";
                  try {
                    const payload = {
                      message,
                      model: $("globalModel").value || null,
                      attachments: currentChatAttachmentsForRun()
                    };
                    const result = await api(`/api/projects/${state.projectId}/gdd`, { method: "POST", body: JSON.stringify(payload) });
                    out(result.summary || "策划 GDD 文档已创建。");
                    await loadServerChatHistoryForProject(state.projectId);
                    await loadRuns();
                    await loadProjectPackages();
                  } catch (error) {
                    showError(error);
                  } finally {
                    clearChatAttachments();
                    setLocalBusy(false);
                    button.disabled = false;
                    button.textContent = "创建策划文档";
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
                  if (!state.prototypeReadyForFeedback) return out("请先运行并完成原型骨架创建，再提交正式反馈。自由对话仍可使用。");
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
                    await submitIterationPlanFromFeedback(suggestion, "正在按评估重拆迭代计划...", "completion_suggestion");
                    return;
                  }
                  if (hasPendingPlan) {
                    await executeIterationGoal();
                    return;
                  }
                  await submitIterationPlanFromFeedback(suggestion, "正在生成迭代计划...", "completion_suggestion");
                }

                async function submitFormalFeedbackText(feedback, busyText) {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("\u8bf7\u5148\u9009\u62e9\u4e00\u4e2a\u9879\u76ee\u3002");
                  if (!state.prototypeReadyForFeedback) return out("请先运行并完成原型骨架创建，再提交正式反馈。自由对话仍可使用。");
                  setLocalBusy(true);
                  $("submitFormalFeedback").disabled = true;
                  $("submitFormalFeedback").textContent = busyText || "\u6b63\u5f0f\u63d0\u4ea4\u4e2d...";
                  try {
                    state.chatHistory.push({ role: "user", content: feedback });
                    renderChatHistory();
                    saveChatHistoryForProject();
                    $("chatMessage").value = "";
                    const result = await api(`/api/projects/${state.projectId}/prototype-feedback-iterations`, {
                      method: "POST",
                      body: JSON.stringify({ feedback, model: $("globalModel").value, skillActionId: $("chatSkillMode").value || "normal" })
                    });
                    state.chatHistory.push({ role: "assistant", content: result.assistantMessage || "\u672c\u8f6e\u6b63\u5f0f\u53cd\u9988\u5df2\u5b8c\u6210\u3002" });
                    renderChatHistory();
                    saveChatHistoryForProject();
                    await loadServerChatHistoryForProject(state.projectId);
                    out(result);
                    await loadRuns();
                    updateContinueSuggestionFromText(result.assistantMessage);
                  } catch (error) {
                    const message = sanitizePublicChatContent(error?.payload?.assistantMessage || error?.payload?.error || "本轮正式反馈处理失败。");
                    if (message) {
                      state.chatHistory.push({ role: "assistant", content: message, kind: "formal-feedback-failed" });
                      renderChatHistory();
                      saveChatHistoryForProject();
                    }
                    showError(error);
                    await loadServerChatHistoryForProject(state.projectId);
                  }
                  finally {
                    setLocalBusy(false);
                    setFormalFeedbackAvailability(state.prototypeReadyForFeedback);
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
                  const goals = Array.isArray(state.iterationPlan?.goals) ? state.iterationPlan.goals : [];
                  const goal = goals.find(item => String(item.goalIndex) === String(goalIndex));
                  if (!goal) return out("未找到需要 needs-fix 处理的目标。");
                  const feedback = buildNeedsFixFeedbackForGoal(goal);
                  if (!feedback) return out("当前目标缺少可用于 needs-fix 路由的内容。");
                  await submitNeedsFixRouteRequest({
                    feedback,
                    goalId: goal.goalId || "",
                    goalIndex: Number(goal.goalIndex || 0)
                  }, `Needs Fix 路由执行中 step ${String(goal.goalIndex)}...`);
                }

                async function submitNeedsFixRouteRequest(payload, busyText) {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("\u8bf7\u5148\u9009\u62e9\u4e00\u4e2a\u9879\u76ee\u3002");
                  if (!state.prototypeReadyForFeedback) return out("请先完成原型骨架创建，再使用 needs-fix 路由。");
                  setLocalBusy(true);
                  $("submitFormalFeedback").disabled = true;
                  try {
                    const feedback = String(payload?.feedback || "").trim();
                    state.chatHistory.push({ role: "user", content: feedback, kind: "needs-fix-route" });
                    renderChatHistory();
                    saveChatHistoryForProject();
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
                    state.chatHistory.push({
                      role: "assistant",
                      content: result.summary || (needsMoreFix ? "本轮 needs-fix 路由已执行，但当前目标仍需继续修复。" : "本轮 needs-fix 路由已完成。"),
                      kind: needsMoreFix ? "needs-fix-route-failed" : "needs-fix-route-result"
                    });
                    renderChatHistory();
                    saveChatHistoryForProject();
                    await loadServerChatHistoryForProject(state.projectId);
                    out(result);
                    await loadRuns();
                    await loadIterationPlan();
                  } catch (error) {
                    const message = sanitizePublicChatContent(error?.payload?.summary || error?.payload?.error || "Needs fix route failed.");
                    if (message) {
                      state.chatHistory.push({ role: "assistant", content: message, kind: "needs-fix-route-failed" });
                      renderChatHistory();
                      saveChatHistoryForProject();
                    }
                    showError(error);
                    await loadServerChatHistoryForProject(state.projectId);
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
                  select.innerHTML = `<option value="normal">普通模式</option>` +
                    state.skillActions.map(action => `<option value="${escapeHtml(action.actionId)}">${escapeHtml(action.label)}</option>`).join("");
                  renderSelectedSkillAction();
                }

                function renderSelectedSkillAction() {
                  const selected = $("chatSkillMode").value || "normal";
                  if (selected === "normal") {
                    $("chatSkillDescription").textContent = "不激活 skills，按通用 Phase A 原型顾问方式回答。";
                    return;
                  }
                  const action = state.skillActions.find(item => item.actionId === selected);
                  if (!action) {
                    $("chatSkillDescription").textContent = "当前能力不可用，已回退为普通模式。";
                    return;
                  }
                  $("chatSkillDescription").textContent = action.description || "当前能力暂无说明。";
                }

                async function api(path, options = {}) {
                  const response = await fetch(path, { ...options, headers: { ...headers(), ...(options.headers || {}) } });
                  const text = await response.text();
                  let payload = {};
                  try { payload = text ? JSON.parse(text) : {}; } catch { payload = { raw: text }; }
                  if (!response.ok) throw { status: response.status, payload };
                  return payload;
                }

                async function refreshProjects(options = {}) {
                  const autoSelect = options.autoSelect !== false;
                  try {
                    const session = await api("/api/session");
                    showAdminShell(session.role || "user");
                    if ((session.role || "user") === "admin") {
                      state.projects = [];
                      closeUserModals();
                      out("Admin project creation and project list are disabled. Use Account Admin on the right.");
                      return;
                    }

                    const projects = await api("/api/projects");
                    state.projects = projects;
                    if (hasInitializingProject(projects)) {
                      showInitialization("running", "");
                      out(projects);
                      return;
                    }

                    // Once no project is still bootstrapping, always clear the
                    // initialization overlay before rendering the steady-state UI.
                    $("initStatusPanel").classList.add("hidden");

                    const visibleProjects = listableProjects(projects);
                    const latestFailure = visibleProjects.length === 0 ? await loadLatestProjectCreationFailure() : null;
                    const health = await loadProjectHealthSummary();
                    $("projects").innerHTML = visibleProjects.map(p => `
                      <div class="card">
                        <button class="ghost" data-project="${p.projectId}">
                        <strong>${escapeHtml(p.name)}</strong>
                        <span class="muted">${escapeHtml(p.gameName)} · ${escapeHtml(p.templateRuleId)} · ${escapeHtml(p.bootstrapStatus)}</span>
                        ${p.bootstrapStatus === "failed" ? `<span class="danger">初始化失败：${escapeHtml(p.bootstrapError || "未知错误")}</span>` : ""}
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
                    if (visibleProjects.length === 0 && latestFailure) {
                      showCreationFailure(latestFailure.failureError);
                    } else if (visibleProjects.length === 0) {
                      showCreateProjectPage();
                    } else if (autoSelect) {
                      selectDefaultProject(visibleProjects);
                    }
                    out(projects);
                  } catch (error) {
                    localStorage.removeItem("phaseAAccessToken");
                    localStorage.removeItem("phaseAAdminToken");
                    showLoggedOut();
                    showError(error);
                  }
                }

                function selectDefaultProject(projects) {
                  if (!Array.isArray(projects) || projects.length === 0) return;
                  if (state.projectId && projects.some(project => project.projectId === state.projectId)) return;
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
                  const value = project.updatedUtc || project.updatedAtUtc || project.lastUpdatedUtc || project.modifiedUtc || project.createdUtc || project.createdAtUtc;
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
                      status: payload.status || "unknown",
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
                  state.assetInventory = null;
                  state.assetInventoryExpanded = false;
                  setModalVisible("projectListModal", false);
                  hideCreateProjectPage();
                  loadChatHistoryForProject(projectId);
                  const project = state.projects.find(p => p.projectId === projectId);
                  $("selectedProject").textContent = project ? `${project.name} (${project.projectId})` : projectId;
                  showProjectDetail();
                  loadProjectRuntimeState();
                  loadServerChatHistoryForProject(projectId);
                  loadIterationPlan();
                  loadRepairPlan();
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
                    if (forceVisibleNotice && draft.status === "succeeded") {
                      showPrototypeNotice("已同步最近一次草稿分析结果，表单已自动补全到最新状态。", "info");
                    }
                    return draft;
                  } catch {
                    $("draftImportStatus").className = "card muted";
                    $("draftImportStatus").textContent = "可选：创建项目后上传 txt 草稿，由后端模型分析后回填原型表单。";
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

                async function createProject() {
                  if (!guardGlobalAction()) return;
                  setLocalBusy(true, "创建项目中，请等待当前任务执行完毕。");
                  $("createProject").disabled = true;
                  $("createProject").textContent = "创建中...";
                  try {
                    const payload = {
                      projectName: $("projectName").value.trim() || null,
                      gameName: $("gameName").value.trim(),
                      gameTypeSource: $("gameTypeSource").value.trim()
                    };
                    const result = await api("/api/projects", { method: "POST", body: JSON.stringify(payload) });
                    out(result);
                    showInitialization("running", "");
                    await pollProjectInitializationResult();
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

                async function pollProjectInitializationResult(maxAttempts = 24, delayMs = 5000) {
                  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
                    await new Promise(resolve => setTimeout(resolve, delayMs));
                    try {
                      const projects = await api("/api/projects");
                      state.projects = projects;
                      if (hasInitializingProject(projects)) {
                        continue;
                      }
                      const visibleProjects = listableProjects(projects);
                      const latestFailure = await loadLatestProjectCreationFailure();
                      if (visibleProjects.length > 0) {
                        $("initStatusPanel").classList.add("hidden");
                        await refreshProjects();
                        return;
                      }
                      if (latestFailure?.failureError) {
                        showCreationFailure(latestFailure.failureError);
                        return;
                      }
                    } catch {
                      return;
                    }
                  }
                }

                function projectCreationErrorMessage(error) {
                  const payload = error?.payload || {};
                  const code = payload.failureCode || payload.error || error?.status || "unknown_error";
                  if (code === "project_initialization_in_progress") {
                    return "已有项目仍在初始化中，暂时不能创建新项目。系统会自动清理中断的初始化；如果页面一直停留在这里，请刷新后重试。";
                  }
                  if (code === "project_quota_exceeded") {
                    return `项目数量已达到上限${payload.projectLimit ? `（${payload.projectLimit} 个）` : ""}，请先删除旧项目后再创建。`;
                  }
                  if (code === "game_name_required") {
                    return "请填写游戏名称。";
                  }
                  if (code === "game_type_source_required") {
                    return "请填写游戏类型/玩法方向。";
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
                    $("runs").innerHTML = result.runs.map(r => `
                      <button class="card ghost" data-run="${r.runId}">
                        <strong>${escapeHtml(r.runType)} · ${escapeHtml(r.status)}</strong>
                        <span class="muted">${escapeHtml(r.runId)}</span>
                      </button>
                    `).join("") || "<p class='muted'>还没有运行记录。</p>";
                    document.querySelectorAll("[data-run]").forEach(button => button.onclick = () => loadRun(button.dataset.run));
                    renderFeedbackRecords();
                    out(result);
                  } catch (error) { showError(error); }
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
                          ${record.goal.resultSummary ? `<p>${escapeHtml(record.goal.resultSummary)}</p>` : "<p class='muted'>该目标尚未产出结果摘要。</p>"}
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
                    return;
                  }

                  if (legacyFeedbackRuns.length > 0) {
                    $("feedbackSummary").className = "card";
                    $("feedbackSummary").innerHTML = `
                      <strong>流程摘要</strong>
                      <p class="muted">当前项目还没有迭代计划，以下仅展示旧正式反馈记录。</p>
                      <p class="muted">正式反馈次数：${escapeHtml(String(legacyFeedbackRuns.length))}</p>
                    `;
                    return;
                  }

                  $("feedbackSummary").className = "card muted";
                  $("feedbackSummary").textContent = "尚未生成迭代计划。";
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
                    return { label: "按评估重拆迭代计划", action: "refine", source: "当前计划评估", disabled: isGlobalBusy() };
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
                    const evaluationMessage = state.chatHistory.filter(message => message.role === "assistant" && message.kind === "iteration-plan-evaluation" && !message.continueConsumed).slice(-1)[0];
                    if (evaluationMessage) {
                      await continueSuggestedFeedback(state.chatHistory.indexOf(evaluationMessage));
                      return;
                    }
                    if (!state.nextSuggestedFeedback) return out("当前没有可用于重拆计划的建议。");
                    await submitIterationPlanFromFeedback(state.nextSuggestedFeedback, "正在按评估重拆迭代计划...", "completion_suggestion");
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
                  return state.localBusy || !!state.activeRun?.busy;
                }

                function activeRunText(run) {
                  if (!run?.busy) return "";
                  if (run.heavyRunnerQueuePosition) {
                    const waitSeconds = Math.max(0, run.heavyRunnerEstimatedWaitSeconds || 0);
                    const waitMinutes = Math.max(1, Math.ceil(waitSeconds / 60));
                    return `\u4f60\u5df2\u8fdb\u5165\u91cd\u4efb\u52a1\u961f\u5217\uff1a\u7b2c ${run.heavyRunnerQueuePosition} \u4f4d\uff0c\u5f53\u524d\u7b49\u5f85 ${run.heavyRunnerQueuedCount || 0} \u4e2a\uff0c\u9884\u8ba1\u7b49\u5f85\u7ea6 ${waitMinutes} \u5206\u949f\u3002`;
                  }
                  const label = run.progressLabel || run.progressStep || run.status || "";
                  return `当前任务执行中：${run.runType || "unknown"} · ${run.status || "running"} · ${run.runId || ""}${label ? " · " + label : ""}`;
                }

                function setLocalBusy(busy, message = "有任务正在执行，请等待当前任务执行完毕。") {
                  state.localBusy = busy;
                  applyGlobalBusyState(message);
                }

                function applyGlobalBusyState(message = "有任务正在执行，请等待当前任务执行完毕。") {
                  const busy = isGlobalBusy();
                  document.querySelectorAll("[data-global-action]").forEach(button => {
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
                  if (busy) {
                    $("activeRunBanner").classList.remove("hidden");
                    $("activeRunBanner").textContent = state.activeRun?.busy ? activeRunText(state.activeRun) : message;
                  } else {
                    $("activeRunBanner").classList.add("hidden");
                    $("activeRunBanner").textContent = "";
                  }
                }

                async function refreshActiveRun() {
                  if (!state.authenticated) return;
                  try {
                    state.activeRun = await api("/api/account/active-run");
                    applyGlobalBusyState();
                    if (state.projectId && shouldAutoRefreshIterationPlan(state.activeRun)) {
                      await loadIterationPlan();
                      await loadRuns();
                    }
                    if (!state.activeRun?.busy && state.projectId) {
                      await loadPrototypeProgress();
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
                    $("draftImportStatus").textContent = draft?.failureCode ? `草稿分析失败：${draft.failureCode}` : "尚未分析草稿。";
                    return;
                  }
                  if (draft.status === "running") {
                    state.draftAnalysisRunning = true;
                    $("draftImportStatus").className = "card muted";
                    $("draftImportStatus").textContent = "草稿分析中...完成前不能启动原型创建，刷新页面后会自动恢复状态。";
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
                    showError(error);
                  } finally {
                    setLocalBusy(false);
                    $("importDraft").disabled = false;
                    $("importDraft").textContent = "分析草稿并回填";
                    await refreshActiveRun();
                  }
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
                  } catch (error) { showError(error); }
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
                    if (state.projectId) window.open(`/downloads?projectId=${encodeURIComponent(state.projectId)}`, "_blank", "noreferrer");
                  };
                  if (!state.projectId) {
                    $("projectPackageStatus").className = "card muted";
                    $("projectPackageStatus").textContent = "选择项目后显示项目文件包。";
                    return;
                  }
                  if (!result?.canCreatePackage && result?.disabledReason === "prototype_not_created") {
                    $("projectPackageStatus").className = "card muted";
                    $("projectPackageStatus").textContent = state.prototypeFailure === "没有创建有效的godot场景文件"
                      ? "没有创建有效的godot场景文件，暂不能打包项目文件。"
                      : "尚未成功运行原型创建，暂不能打包项目文件。";
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
                  if (reason === "project_not_selected") return "请先选择一个项目。";
                  return "暂不可打包项目文件。";
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
                  } catch {
                    $("loadAssetInventory").disabled = true;
                    $("assetInventoryStatus").className = "card muted";
                    $("assetInventoryStatus").textContent = "素材清单暂不可用。";
                  }
                }

                async function loadAssetInventory() {
                  if (!state.projectId) return out("请先选择一个项目。");
                  window.open(`/assets?projectId=${encodeURIComponent(state.projectId)}&model=${encodeURIComponent($("globalModel").value || "gpt-5.5")}`, "_blank", "noreferrer");
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
                    state.prototypeFailure = progress?.status === "failed" ? (progress.failure || "") : "";
                    renderPrototypeProgress(progress);
                    renderPrototypeAcceptanceSummary(progress);
                    setPrototypeFormLocked(isPrototypeCreationLocked(progress));
                    updateChatPanelVisibility(progress);
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
                    ${progress.failure ? `<p class="danger">${escapeHtml(progress.failure)}</p><p class="danger">可以点击“生成修复计划”把失败拆成小步骤，再逐项执行修复。</p>` : ""}
                  `;
                  $("repairPrototype").classList.toggle("hidden", status !== "failed");
                }

                function renderPrototypeAcceptanceSummary(progress) {
                  const status = progress?.status || "idle";
                  if (status === "failed") {
                    const failure = progress?.failure || "原型验收未通过。";
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
                  const status = progress?.status || "idle";
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
                    return `下一步建议来源：${formatNextStepSource(progress?.nextStepSource)}\n继续优化评估：${formatNextStepEvaluation(progress?.nextStepEvaluation)}\n${String(progress?.nextStepEvaluationReason || "").trim()}\n\n原型创建完成。\n\n本次完成：\n1. 已生成可玩的原型基础版本。\n2. 已完成基础启动检查。\n3. 已进入可继续优化状态。\n\n下一步建议：\n${suggestion}\n\n如需执行，请使用迭代计划或 Needs Fix 的固定功能按钮。`.trim();
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
                  const status = progress?.status || "idle";
                  return !["idle", "failed"].includes(status);
                }

                function setPrototypeFormLocked(locked) {
                  prototypeInputIds.forEach(id => $(id).disabled = locked);
                  $("runPrototype").disabled = locked || isGlobalBusy();
                  $("runPrototype").textContent = locked ? "原型骨架创建中..刷新页面查阅创建进度." : "运行原型骨架创建";
                  $("repairPrototype").disabled = locked || isGlobalBusy();
                  $("repairPrototype").textContent = locked ? "修复计划处理中..刷新页面查阅进度." : "生成修复计划";
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
                  localStorage.setItem("phaseAAccessToken", token());
                  localStorage.removeItem("phaseAAdminToken");
                  $("sessionStatus").textContent = token() ? "Token 验证中..." : "Token 已清空。";
                  if (token()) refreshProjects(); else showLoggedOut();
                };
                $("logout").onclick = () => {
                  localStorage.removeItem("phaseAAdminToken");
                  localStorage.removeItem("phaseAAccessToken");
                  $("token").value = "";
                  state.projectId = "";
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
                $("loadAccountAudit").onclick = loadAccountAudit;
                $("downloadAccountAuditCsv").onclick = downloadAccountAuditCsv;
                $("importDraft").onclick = importDraft;
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
                $("evaluateIterationPlan").onclick = () => evaluateIterationPlan(false);
                $("executeIterationGoal").onclick = executeIterationGoal;
                $("createRepairPlan").onclick = createRepairPlan;
                $("executeRepairStep").onclick = executeRepairStep;
                $("chatSkillMode").onchange = renderSelectedSkillAction;
                renderChatHistory();
                $("loadRuns").onclick = loadRuns;
                $("createProjectPackage").onclick = createProjectPackage;
                $("loadAssetInventory").onclick = loadAssetInventory;
                $("runPrototype").onclick = runPrototype;
                $("repairPrototype").onclick = repairPrototype;
                $("refreshPrototypeProgress").onclick = loadPrototypeProgress;
                $("validatePrototype").onclick = validatePrototype;
                $("createScene").onclick = createScene;
                document.querySelectorAll(".runTdd").forEach(button => button.onclick = () => runTdd(button.dataset.stage));
                setTokenFromStorage();
                if (token()) refreshProjects(); else showLoggedOut();
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
              .detail-progress { display: grid; grid-template-columns: repeat(8, minmax(5.6rem, 1fr)); gap: 0.5rem; overflow-x: auto; padding-bottom: 0.2rem; }
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
        var latestAssetInventory = LatestRun(runs, "project-asset-inventory");
        var latestPackage = LatestRun(runs, "project-package");
        var prototypeFailed = latestPrototype?.Status == "failed";

        return
        [
            new ProjectDetailStep(1, "游戏项目详情", "done", "/", "✓"),
            CreateRunStep(2, "原型骨架创建", latestPrototype, "/#prototypeWorkflowPanel"),
            CreateAcceptanceStep(latestPrototype, "/#prototypeWorkflowPanel"),
            prototypeFailed && latestRepair is null
                ? new ProjectDetailStep(4, "原型验收修复", "fix", "/#v2RepairPanel", "×")
                : CreateRunStep(4, "原型验收修复", latestRepair, "/#v2RepairPanel"),
            CreateRunStep(5, "完成迭代计划", latestIteration, "/#v2IterationPanel"),
            CreateRunStep(6, "确认素材清单", latestAssetInventory, $"/assets?projectId={Uri.EscapeDataString(project.ProjectId)}"),
            CreateRunStep(7, "打包项目文件", latestPackage, "/#createProjectPackage"),
            new ProjectDetailStep(8, "下载项目文件", "pending", $"/downloads?projectId={Uri.EscapeDataString(project.ProjectId)}", "")
        ];
    }

    private static ProjectDetailStep CreateAcceptanceStep(RunReadbackItem? prototypeRun, string href)
    {
        if (prototypeRun is null || string.IsNullOrWhiteSpace(prototypeRun.ProgressStep))
        {
            return new ProjectDetailStep(3, "原型验收", "pending", href, "");
        }

        return prototypeRun.Status switch
        {
            "succeeded" => new ProjectDetailStep(3, "原型验收", "done", href, "✓"),
            "failed" => new ProjectDetailStep(3, "原型验收", "fix", href, "×"),
            _ => new ProjectDetailStep(3, "原型验收", "pending", href, "")
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

    private static RunReadbackItem? LatestRun(IReadOnlyList<RunReadbackItem> runs, params string[] runTypes)
    {
        return runs.FirstOrDefault(run => runTypes.Contains(run.RunType, StringComparer.OrdinalIgnoreCase));
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
                .danger { color: var(--danger); }
                .muted { color: var(--muted); }
              </style>
            </head>
            <body>
              <main>
                <header>
                  <h1>项目文件下载</h1>
                  <p>按版本号/时间戳从近到远列出所有已打包的项目文件。压缩包只包含项目相关文件，不包含平台工程代码。</p>
                </header>
                <section id="status" class="card muted">正在读取项目文件包列表...</section>
                <section class="downloads-grid">
                  <section id="gddDownload" class="card"></section>
                  <section id="packages" class="card"></section>
                </section>
              </main>
              <script>
                const params = new URLSearchParams(location.search);
                const projectId = params.get("projectId") || "";
                const token = () => localStorage.getItem("phaseAAccessToken") || localStorage.getItem("phaseAAdminToken") || "";
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
                async function loadGddDownload() {
                  const response = await fetch(`/api/projects/${projectId}/gdd`, { headers: { "Authorization": `Bearer ${token()}` }, cache: "no-store" });
                  if (!response.ok) {
                    $("gddDownload").innerHTML = "<strong>策划 GDD 文档</strong><p class='muted'>还没有创建 GDD.md。</p>";
                    return;
                  }

                  const payload = await response.json();
                  $("gddDownload").innerHTML = `
                    <article class="package">
                      <strong>策划 GDD 文档</strong>
                      <span class="muted">${escapeHtml(payload.lastUpdatedUtc || "未知时间")} · ${escapeHtml(payload.relativePath || "docs/gdd/GDD.md")} · ${payload.sizeBytes || 0} bytes</span>
                      <button id="downloadGddDocument">下载 GDD.md</button>
                    </article>
                  `;
                  $("downloadGddDocument").onclick = () => downloadGddDocument($("downloadGddDocument"));
                }
                function disabledText(reason) {
                  if (reason === "prototype_not_created") return "尚未成功运行原型创建，或没有创建有效的godot场景文件，暂不能打包项目文件。";
                  if (reason === "project_busy") return "项目有后台任务正在执行。";
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
                  $("status").textContent = "正在准备策划 GDD 文档下载。";
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
              <title>项目素材清单</title>
              <style>
                :root { --ink: #17211b; --muted: #66736b; --paper: #fbf7ef; --panel: #fffdf8; --line: #ded4c4; --accent: #0f6b57; --danger: #a2342f; }
                * { box-sizing: border-box; }
                body { margin: 0; font-family: Georgia, "Times New Roman", serif; color: var(--ink); background: linear-gradient(135deg, #fbf7ef, #efe5d3); }
                main { max-width: 78rem; margin: 0 auto; padding: 2rem 1rem 4rem; display: grid; gap: 1rem; }
                h1 { margin: 0; font-size: clamp(2rem, 5vw, 4rem); letter-spacing: -0.06em; }
                h2 { margin: 0 0 0.75rem; }
                p { color: var(--muted); }
                .card { background: var(--panel); border: 1px solid var(--line); border-radius: 1rem; padding: 1rem; box-shadow: 0 1rem 2.4rem rgba(57, 43, 24, 0.1); overflow-wrap: anywhere; }
                .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr)); gap: 0.75rem; }
                .list { display: grid; gap: 0.75rem; }
                .asset-preview { width: 100%; height: 10rem; object-fit: contain; border: 1px solid var(--line); border-radius: 0.75rem; background: #f3ead9; }
                button { border: 0; border-radius: 0.75rem; padding: 0.75rem 1rem; background: var(--accent); color: white; font: inherit; font-weight: 700; cursor: pointer; }
                button:disabled { cursor: not-allowed; opacity: 0.45; }
                .danger { color: var(--danger); }
                .muted { color: var(--muted); }
                .badge { display: inline-flex; border-radius: 999px; padding: 0.2rem 0.55rem; background: #e6f4ef; color: var(--accent); font-weight: 700; font-size: 0.85rem; }
              </style>
            </head>
            <body>
              <main>
                <header>
                  <h1>项目素材清单</h1>
                  <p>列出当前项目实际使用的素材实例、素材预览，以及未使用素材但适合生成素材的候选实例。候选项会说明它在游戏或界面中做什么用。</p>
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
              <script>
                const params = new URLSearchParams(location.search);
                const projectId = params.get("projectId") || "";
                const model = params.get("model") || "gpt-5.5";
                const token = () => localStorage.getItem("phaseAAccessToken") || localStorage.getItem("phaseAAdminToken") || "";
                const $ = id => document.getElementById(id);
                const escapeHtml = value => String(value || "").replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#039;" }[ch]));

                async function loadAssets() {
                  if (!projectId) {
                    $("status").textContent = "缺少 projectId。请从控制台打开素材清单页。";
                    return;
                  }
                  if (!token()) {
                    $("status").textContent = "当前浏览器没有 token。请先在控制台登录。";
                    return;
                  }
                  $("status").textContent = "正在识别素材实例和可生成素材候选...";
                  const response = await fetch(`/api/projects/${encodeURIComponent(projectId)}/asset-inventory?judge=true&model=${encodeURIComponent(model)}`, {
                    headers: { "Authorization": `Bearer ${token()}` },
                    cache: "no-store"
                  });
                  const payload = await response.json();
                  if (!response.ok || !payload.canReadInventory) {
                    $("status").innerHTML = `<span class="danger">读取失败：${escapeHtml(payload.error || payload.disabledReason || "unknown_error")}</span>`;
                    return;
                  }
                  const usedAssets = payload.usedAssets || [];
                  const candidates = payload.generationCandidates || [];
                  $("status").textContent = `已识别 ${usedAssets.length} 个已使用素材实例，${candidates.length} 个可生成素材候选。`;
                  await renderUsedAssets(usedAssets);
                  renderCandidates(candidates);
                }

                async function renderUsedAssets(items) {
                  const enriched = [];
                  for (const item of items) {
                    enriched.push({ ...item, previewUrl: await createPreviewUrl(item.resourcePath) });
                  }
                  $("usedAssets").innerHTML = enriched.length
                    ? enriched.map(renderUsedAsset).join("")
                    : "<p class='muted'>未识别到可预览素材引用。</p>";
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
                  } catch {
                    return "";
                  }
                }

                function renderUsedAsset(item) {
                  const image = item.previewUrl
                    ? `<img class="asset-preview" src="${escapeHtml(item.previewUrl)}" alt="${escapeHtml(item.instanceName || "asset")}">`
                    : "<div class='asset-preview muted'>预览不可用</div>";
                  return `
                    <article class="card">
                      ${image}
                      <strong>${escapeHtml(item.instanceName || "")}</strong>
                      <p class="muted">${escapeHtml(item.nodeType || "")}</p>
                      <p class="muted">场景：${escapeHtml(item.scenePath || "")}</p>
                      <p class="muted">用途：${escapeHtml(item.intendedUse || "")}</p>
                      <p class="muted">像素尺寸：${escapeHtml(assetPixelSize(item))}</p>
                      <p class="muted">素材：${escapeHtml(item.resourcePath || "")}</p>
                    </article>
                  `;
                }

                function assetPixelSize(item) {
                  const width = Number(item?.pixelWidth || 0);
                  const height = Number(item?.pixelHeight || 0);
                  return width > 0 && height > 0 ? `${width} x ${height}` : "未知";
                }

                function renderCandidates(items) {
                  $("candidates").innerHTML = items.length
                    ? items.map(renderCandidate).join("")
                    : "<p class='muted'>暂未识别到明显的素材生成候选。</p>";
                }

                function renderCandidate(item) {
                  return `
                    <article class="card">
                      <strong>${escapeHtml(item.instanceName || "")}</strong>
                      <p><span class="badge">${escapeHtml(item.suggestedAssetKind || "visual_asset")}</span></p>
                      <p class="muted">节点类型：${escapeHtml(item.nodeType || "")}</p>
                      <p class="muted">场景：${escapeHtml(item.scenePath || "")}</p>
                      <p><strong>用途</strong>：${escapeHtml(item.intendedUse || "用于替换当前占位节点，提升可读性。")}</p>
                      <p><strong>建议原因</strong>：${escapeHtml(item.reason || "")}</p>
                      <p class="muted">判断状态：${escapeHtml(item.llmJudgementStatus || "")}</p>
                    </article>
                  `;
                }

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
                const token = () => localStorage.getItem("phaseAAccessToken") || localStorage.getItem("phaseAAdminToken") || "";
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
