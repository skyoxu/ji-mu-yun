using System.Net;
using PhaseA.Platform.Data;
using PhaseA.Platform.Readback;

namespace PhaseA.Platform.Browser;

public sealed class BrowserUiRenderer
{
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
                  gap: 0.6rem;
                }
                h1 { margin: 0; font-size: clamp(2rem, 5vw, 4.5rem); letter-spacing: -0.06em; }
                h2 { margin: 0 0 1rem; font-size: 1.15rem; }
                p { color: var(--muted); }
                main {
                  display: grid;
                  grid-template-columns: minmax(15rem, 22rem) minmax(0, 1fr);
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
                .chat-scroll { min-height: 16rem; max-height: 24rem; overflow-y: auto; padding-right: 0.25rem; }
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
                .busy-banner { margin-top: 0.75rem; border: 1px solid var(--accent-2); background: #fff8e6; border-radius: 0.9rem; padding: 0.85rem; }
                .hidden { display: none !important; }
                @media (max-width: 920px) {
                  main, .grid, .health-grid { grid-template-columns: 1fr; }
                }
              </style>
            </head>
            <body>
              <header>
                <h1>积木云 Phase A 原型控制台</h1>
                <p>Phase A Prototype Console：用于创建项目、运行云端原型路线、查看运行日志和产物的单管理员控制台。</p>
                <div id="activeRunBanner" class="busy-banner hidden"></div>
              </header>
              <main>
                <aside class="stack">
                  <section id="globalModelPanel" class="stack hidden">
                    <h2>全局模型</h2>
                    <label>模型选择 <select id="globalModel"><option value="gpt-5.4" selected>gpt-5.4</option><option value="gpt-5.5">gpt-5.5</option></select></label>
                    <p class="muted">该模型同时用于 7 步可玩原型、自由对话和正式反馈提交。</p>
                  </section>
                  <section id="stepsPanel" class="stack">
                    <h2>使用步骤</h2>
                    <p>1. 粘贴 Admin token 并保存。2. 创建或选择项目。3. 先运行 Chapter 2 初始化。4. 填写 7 步可玩原型表单并运行。5. 在 Runs 和 Output 查看结果与产物链接。</p>
                    <p class="muted">当前 Phase A 只提供固定工作流按钮，不是 Codex CLI 式自由对话窗口。</p>
                  </section>
                  <section id="sessionPanel" class="stack">
                    <h2>会话</h2>
                    <label>Admin token <input id="token" type="password" autocomplete="off" placeholder="粘贴服务器生成的 token"></label>
                    <button id="saveToken">验证并进入</button>
                    <p id="sessionStatus" class="muted">Token 只保存在当前浏览器 localStorage，不会写入仓库。</p>
                  </section>
                  <section id="createProjectPanel" class="stack hidden">
                    <h2>创建项目</h2>
                    <label>项目名 <input id="projectName" placeholder="可选，不填会自动生成"></label>
                    <label>游戏名 <input id="gameName" placeholder="例如：Demo Game"></label>
                    <label>游戏类型/玩法方向 <input id="gameTypeSource" placeholder="例如：RPG、塔防、Roguelike、平台跳跃、解谜冒险"></label>
                    <button id="createProject" data-global-action="true">创建项目</button>
                  </section>
                  <section id="codexConfigPanel" class="stack hidden">
                    <h2>Codex 配置</h2>
                    <p class="muted">自由对话复用服务器本机 Codex CLI 的登录态、provider 和配置；浏览器用户只能从服务器允许的模型列表中选择。</p>
                    <p class="muted">当前后端以只读方式调用 codex exec。聊天不会直接修改文件；需要执行工作流时仍使用页面上的固定按钮。</p>
                    <button id="logout" class="danger-button">退出登录</button>
                  </section>
                  <section id="projectListPanel" class="hidden">
                    <h2>项目列表</h2>
                    <button id="refreshProjects" class="ghost">刷新项目列表</button>
                    <div id="projects" class="card-list"></div>
                  </section>
                </aside>
                <div id="adminPanel" class="stack hidden">
                  <section id="initStatusPanel" class="stack hidden">
                    <h2>项目初始化</h2>
                    <p id="initStatusText" class="muted">项目初始化配置中...请稍等 2-5 分钟后刷新页面。</p>
                  </section>
                  <section id="projectDetailPanel" class="stack hidden">
                  <section id="currentProjectPanel" class="stack">
                    <h2>当前项目</h2>
                    <p id="selectedProject" class="muted">尚未选择项目。</p>
                    <button id="loadRuns" class="ghost">加载运行记录</button>
                    <button id="refreshPrototypeProgress" class="ghost">刷新原型进度</button>
                    <button id="createProjectPackage" class="secondary" data-global-action="true" disabled>打包项目文件</button>
                    <button id="openProjectDownloads" class="ghost" disabled>打开项目文件下载页</button>
                    <div id="prototypeProgress" class="card muted">尚未开始 7 步可玩原型。</div>
                    <div id="prototypeAcceptanceSummary" class="card muted">原型完成后，这里会显示默认场景、验证摘要数量和建议试玩重点。</div>
                    <div id="projectHealthSummary" class="card muted">选择项目后显示项目健康摘要。</div>
                    <div id="projectPackageStatus" class="card muted">尚未生成项目压缩包。</div>
                  </section>
                  <section id="prototypeWorkflowPanel" class="stack">
                    <h2>7 步可玩原型</h2>
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
                    <button id="repairPrototype" class="ghost hidden" data-global-action="true">修复原型</button>
                    <button id="runPrototype" class="secondary" data-global-action="true">运行原型路线</button>
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
                    <details id="quickFixPanel">
                      <summary>兼容入口：快速修复</summary>
                      <p class="muted">仅适合接线、文案、状态显示等单点小修。若需求涉及玩法增强、结构调整或多个连续目标，请优先使用上方迭代计划主流程。</p>
                      <button id="submitQuickFix" class="secondary" data-global-action="true">快速修复</button>
                    </details>
                    <h2>聊天记录</h2>
                    <div id="chatHistory" class="card-list chat-scroll"></div>
                    <label>消息 <textarea id="chatMessage" placeholder="例如：帮我把这个原型想法拆成最小可玩循环"></textarea></label>
                    <button id="sendChat" class="secondary" data-global-action="true">发送消息</button>
                    <button id="evaluateIterationPlanFromChat" class="ghost" data-global-action="true">评估当前计划是否值得继续</button>
                    <button id="submitFormalFeedback" class="ghost" data-global-action="true">提交反馈并生成迭代计划</button>
                    <h2>流程记录</h2>
                    <div id="feedbackSummary" class="card muted">尚未生成迭代计划。</div>
                    <div id="feedbackRecords" class="card-list feedback-scroll"></div>
                  </section>
                  <section>
                    <h2>运行记录</h2>
                    <div id="runs" class="card-list"></div>
                  </section>
                  <section>
                    <h2>输出</h2>
                    <pre id="output">就绪。</pre>
                  </section>
                  </section>
                </div>
              </main>
              <script>
                const state = { projectId: "", projects: [], runs: [], packageList: null, chatHistory: [], skillActions: [], authenticated: false, prototypeReadyForFeedback: false, activeRun: null, localBusy: false, nextSuggestedFeedback: "", draftAnalysisRunning: false, prototypeFailure: "", iterationPlan: null, iterationPlanEvaluation: null };
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

                function setTokenFromStorage() {
                  $("token").value = localStorage.getItem("phaseAAdminToken") || "";
                }

                function renderChatHistory() {
                  applyChatWorkflowActions();
                  state.chatHistory.forEach(message => {
                    if (typeof message.content === "string") message.content = sanitizePublicChatContent(message.content);
                  });
                  $("chatHistory").innerHTML = state.chatHistory.map((message, index) => `
                    <div class="card">
                      <strong>${message.role === "assistant" ? "助手" : "我"}${message.pending ? " · 生成中" : ""}</strong>
                      <span>${escapeHtml(message.content)}</span>
                      ${renderInlineContinueAction(message, index)}
                    </div>
                  `).join("") || "<p class='muted'>还没有对话。</p>";
                  document.querySelectorAll("[data-continue-suggestion]").forEach(button => {
                    button.onclick = () => continueSuggestedFeedback(Number(button.dataset.continueSuggestion));
                  });
                }

                function renderInlineContinueAction(message, index) {
                  if (message.role !== "assistant" || message.pending || message.continueConsumed) return "";
                  if (!state.prototypeReadyForFeedback) return "";
                  const label = inlineContinueActionLabelForMessage(message);
                  if (!label) return "";
                  return `<button class="secondary" data-global-action="true" data-continue-suggestion="${index}">${escapeHtml(label)}</button>`;
                }

                function inlineContinueActionLabelForMessage(message) {
                  const hasPendingPlan = !!(state.iterationPlan?.session && Array.isArray(state.iterationPlan?.goals) && state.iterationPlan.goals.some(goal => goal.status === "pending"));
                  if ((message?.kind === "iteration-goal-result" || message?.kind === "iteration-goal-failed") &&
                      message?.suggestedFeedback === "__iteration_plan_evaluate__") {
                    return "继续评估当前计划";
                  }
                  if (message?.kind === "iteration-plan-evaluation") {
                    const decision = String(message.evaluationDecision || currentIterationPlanDecision()).trim().toLowerCase();
                    if (decision === "should_refine_plan") return "按评估重拆迭代计划";
                    if (decision === "ready_to_execute" && hasPendingPlan) return "继续当前迭代目标";
                    return "";
                  }
                  if (!message?.suggestedFeedback) return "";
                  return continueActionLabel();
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
                  } catch (error) {
                    if (error?.status === 404) {
                      state.iterationPlan = null;
                    } else {
                      showError(error);
                    }
                  }
                  renderIterationPlan();
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
                    $("createIterationPlan").textContent = "生成迭代计划";
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
                  const hasNeedsFix = goals.some(goal => goal.status === "needs_fix");
                  const hasPending = goals.some(goal => goal.status === "pending");
                  const evaluationDecision = currentIterationPlanDecision();
                  const shouldRefinePlan = evaluationDecision === "should_refine_plan";
                  const blockedByCurrentGoal = evaluationDecision === "blocked_by_current_goal";
                  const canCreateNewPlan = (!hasPending && !hasNeedsFix) || shouldRefinePlan;
                  $("iterationPlanStatus").className = "card";
                  $("iterationPlanStatus").innerHTML = `
                    <strong>${escapeHtml(session.status || "ready")}</strong>
                    <p>${escapeHtml(session.overallGoal || "")}</p>
                    ${session.latestSummary ? `<p class="muted">${escapeHtml(session.latestSummary)}</p>` : ""}
                    <p class="muted">当前目标序号：${escapeHtml(String(session.currentGoalIndex || 0))}</p>
                  `;
                  $("createIterationPlan").disabled = !canCreateNewPlan || blockedByCurrentGoal || isGlobalBusy();
                  $("createIterationPlan").textContent = shouldRefinePlan
                    ? "按评估重拆迭代计划"
                    : canCreateNewPlan
                      ? "生成新的迭代计划"
                      : hasNeedsFix
                        ? "当前计划需先修复"
                        : "当前已有未完成计划";
                  $("evaluateIterationPlan").disabled = isGlobalBusy();
                  $("evaluateIterationPlan").textContent = "评估当前迭代计划";
                  $("evaluateIterationPlanFromChat").disabled = isGlobalBusy();
                  $("evaluateIterationPlanFromChat").textContent = "评估当前计划是否值得继续";
                  $("executeIterationGoal").disabled = !hasPending || hasNeedsFix || shouldRefinePlan || isGlobalBusy();
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
                    </div>`).join("");
                }

                function renderIterationPlanEvaluation() {
                  const evaluation = state.iterationPlanEvaluation;
                  if (!evaluation) {
                    $("iterationPlanEvaluation").className = "card muted";
                    $("iterationPlanEvaluation").textContent = "尚未评估当前迭代计划。";
                    return;
                  }
                  const decision = String(evaluation.decision || "").trim().toLowerCase();
                  const actionHint = decision === "should_refine_plan"
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
                  const message = $("chatMessage").value.trim();
                  if (!message) return out("请先输入要拆解的优化目标。");
                  await submitIterationPlanFromFeedback(message, "正在生成迭代计划...");
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
                    renderIterationPlanEvaluation();
                    renderIterationPlan();
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
                      body: JSON.stringify({ message, sourceKind })
                    });
                    state.iterationPlan = {
                      session: {
                        sessionId: result.sessionId,
                        status: result.status,
                        overallGoal: message,
                        currentGoalIndex: 0,
                        latestSummary: result.summary
                      },
                      goals: result.goals || []
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
                    setLocalBusy(false);
                    await loadIterationPlan();
                    await refreshActiveRun();
                  }
                }

                async function executeIterationGoal() {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("请先选择一个项目。");
                  if (!state.iterationPlan?.session) return out("请先生成迭代计划。");
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
                  $("stepsPanel").classList.remove("hidden");
                  $("sessionPanel").classList.remove("hidden");
                  $("adminPanel").classList.add("hidden");
                  $("globalModelPanel").classList.add("hidden");
                  $("createProjectPanel").classList.add("hidden");
                  $("codexConfigPanel").classList.add("hidden");
                  $("prototypeCommandPanel").classList.add("hidden");
                  $("chatPanel").classList.add("hidden");
                  state.nextSuggestedFeedback = "";
                  $("projectListPanel").classList.add("hidden");
                  applyGlobalBusyState();
                  $("sessionStatus").textContent = "请粘贴 Admin token 后验证。";
                }

                function showAdminShell(role = state.role || "user") {
                  state.authenticated = true;
                  state.role = role;
                  $("stepsPanel").classList.add("hidden");
                  $("sessionPanel").classList.add("hidden");
                  $("adminPanel").classList.remove("hidden");
                  $("globalModelPanel").classList.remove("hidden");
                  $("createProjectPanel").classList.remove("hidden");
                  $("codexConfigPanel").classList.remove("hidden");
                  $("prototypeCommandPanel").classList.toggle("hidden", role !== "admin");
                  $("chatPanel").classList.add("hidden");
                  $("projectDetailPanel").classList.add("hidden");
                  $("initStatusPanel").classList.add("hidden");
                  loadSkillActions();
                  refreshActiveRun();
                }

                function showInitialization(status, error) {
                  showAdminShell();
                  $("createProjectPanel").classList.add("hidden");
                  $("projectListPanel").classList.add("hidden");
                  $("projectDetailPanel").classList.add("hidden");
                  $("initStatusPanel").classList.remove("hidden");
                  if (status === "failed") {
                    $("createProjectPanel").classList.remove("hidden");
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
                  $("initStatusPanel").classList.remove("hidden");
                  $("createProjectPanel").classList.remove("hidden");
                  $("initStatusText").innerHTML = `<strong class="danger">创建失败。</strong><br>${escapeHtml(error || "初始化失败，失败项目已自动清理。")}`;
                }



                async function sendChat() {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("请先选择一个项目。");
                  const message = $("chatMessage").value.trim();
                  if (!message) return out("请输入消息。");
                  setLocalBusy(true);
                  $("sendChat").disabled = true;
                  $("sendChat").textContent = "发送中...";
                  try {
                    const payload = {
                      message,
                      model: $("globalModel").value || null,
                      skillActionId: $("chatSkillMode").value || "normal",
                      history: state.chatHistory.slice(-10)
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
                    setLocalBusy(false);
                    $("sendChat").disabled = false;
                    $("sendChat").textContent = "发送消息";
                    await refreshActiveRun();
                  }
                }

                async function submitFormalFeedback() {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("\u8bf7\u5148\u9009\u62e9\u4e00\u4e2a\u9879\u76ee\u3002");
                  if (!state.prototypeReadyForFeedback) return out("\u8bf7\u5148\u8fd0\u884c\u5e76\u5b8c\u6210 7 \u6b65\u53ef\u73a9\u539f\u578b\uff0c\u518d\u63d0\u4ea4\u6b63\u5f0f\u53cd\u9988\u3002\u81ea\u7531\u5bf9\u8bdd\u4ecd\u53ef\u4f7f\u7528\u3002");
                  const feedback = $("chatMessage").value.trim();
                  if (!feedback) return out("\u8bf7\u8f93\u5165\u8981\u6b63\u5f0f\u63d0\u4ea4\u7684\u53cd\u9988\u3002");
                  await submitIterationPlanFromFeedback(feedback, "正在生成迭代计划...");
                }

                async function submitQuickFix() {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("\u8bf7\u5148\u9009\u62e9\u4e00\u4e2a\u9879\u76ee\u3002");
                  if (!state.prototypeReadyForFeedback) return out("\u8bf7\u5148\u5b8c\u6210 7 \u6b65\u539f\u578b\uff0c\u518d\u4f7f\u7528\u5feb\u901f\u4fee\u590d\u3002");
                  const feedback = $("chatMessage").value.trim();
                  if (!feedback) return out("\u8bf7\u8f93\u5165\u8981\u5feb\u901f\u4fee\u590d\u7684\u95ee\u9898\u3002");
                  await submitQuickFixText(feedback, "快速修复中...");
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
                  if (!state.prototypeReadyForFeedback) return out("\u8bf7\u5148\u8fd0\u884c\u5e76\u5b8c\u6210 7 \u6b65\u53ef\u73a9\u539f\u578b\uff0c\u518d\u63d0\u4ea4\u6b63\u5f0f\u53cd\u9988\u3002\u81ea\u7531\u5bf9\u8bdd\u4ecd\u53ef\u4f7f\u7528\u3002");
                  setLocalBusy(true);
                  $("submitQuickFix").disabled = true;
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

                async function submitQuickFixText(feedback, busyText) {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("\u8bf7\u5148\u9009\u62e9\u4e00\u4e2a\u9879\u76ee\u3002");
                  if (!state.prototypeReadyForFeedback) return out("\u8bf7\u5148\u5b8c\u6210 7 \u6b65\u539f\u578b\uff0c\u518d\u4f7f\u7528\u5feb\u901f\u4fee\u590d\u3002");
                  setLocalBusy(true);
                  $("submitQuickFix").disabled = true;
                  $("submitFormalFeedback").disabled = true;
                  $("submitQuickFix").textContent = busyText || "快速修复中...";
                  try {
                    state.chatHistory.push({ role: "user", content: feedback, kind: "quick-fix" });
                    renderChatHistory();
                    saveChatHistoryForProject();
                    $("chatMessage").value = "";
                    const result = await api(`/api/projects/${state.projectId}/prototype-quick-fixes`, {
                      method: "POST",
                      body: JSON.stringify({ feedback, model: $("globalModel").value, skillActionId: $("chatSkillMode").value || "normal" })
                    });
                    state.chatHistory.push({ role: "assistant", content: result.assistantMessage || "本轮快速修复已完成。", kind: "quick-fix-result" });
                    renderChatHistory();
                    saveChatHistoryForProject();
                    await loadServerChatHistoryForProject(state.projectId);
                    out(result);
                    await loadRuns();
                  } catch (error) {
                    const message = sanitizePublicChatContent(error?.payload?.assistantMessage || error?.payload?.error || "本轮快速修复失败。");
                    if (message) {
                      state.chatHistory.push({ role: "assistant", content: message, kind: "quick-fix-failed" });
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
                    $("chatSkillDescription").textContent = "普通模式：不激活 skills，按通用 Phase A 原型顾问方式回答。";
                    return;
                  }
                  const action = state.skillActions.find(item => item.actionId === selected);
                  if (!action) {
                    $("chatSkillDescription").textContent = "当前能力不可用，已回退为普通模式。";
                    return;
                  }
                  const adminLine = state.role === "admin" ? `<p class="muted">actionId: ${escapeHtml(action.actionId)} · skill: ${escapeHtml(action.skillName)} · mode: ${escapeHtml(action.executionMode)}</p>` : "";
                  $("chatSkillDescription").innerHTML = `<strong>${escapeHtml(action.label)}</strong><p>${escapeHtml(action.description)}</p>${adminLine}`;
                }

                async function api(path, options = {}) {
                  const response = await fetch(path, { ...options, headers: { ...headers(), ...(options.headers || {}) } });
                  const text = await response.text();
                  let payload = {};
                  try { payload = text ? JSON.parse(text) : {}; } catch { payload = { raw: text }; }
                  if (!response.ok) throw { status: response.status, payload };
                  return payload;
                }

                async function refreshProjects() {
                  try {
                    const session = await api("/api/session");
                    const projects = await api("/api/projects");
                    state.projects = projects;
                    showAdminShell(session.role || "user");
                    if (hasInitializingProject(projects)) {
                      showInitialization("running", "");
                      out(projects);
                      return;
                    }
                    const failed = failedProject(projects);
                    const visibleProjects = listableProjects(projects);
                    const latestFailure = failed || visibleProjects.length === 0 ? await loadLatestProjectCreationFailure() : null;
                    $("projectListPanel").classList.toggle("hidden", visibleProjects.length === 0);
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
                    if (failed || latestFailure) {
                      showCreationFailure(failed?.bootstrapError || latestFailure?.failureError);
                    }
                    out(projects);
                  } catch (error) {
                    localStorage.removeItem("phaseAAdminToken");
                    showLoggedOut();
                    showError(error);
                  }
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
                  loadChatHistoryForProject(projectId);
                  const project = state.projects.find(p => p.projectId === projectId);
                  $("selectedProject").textContent = project ? `${project.name} (${project.projectId})` : projectId;
                  showProjectDetail();
                  loadProjectRuntimeState();
                  loadServerChatHistoryForProject(projectId);
                  loadIterationPlan();
                }

                async function loadProjectRuntimeState() {
                  await loadRuns();
                  await loadLatestPrototypeDraft();
                  await loadPrototypeProgress();
                  await loadProjectPackages();
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
                    `;
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
                    <p class="muted">命中字段：${escapeHtml((draft.matchedFields || []).join(" · ") || "无")}</p>
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
                    form.append("model", $("globalModel").value || "gpt-5.4");
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
                  setLocalBusy(true, "原型创建中，请等待当前任务执行完毕。");
                  setPrototypeFormLocked(true);
                  try {
                    const result = await api(`/api/projects/${state.projectId}/prototype-7day-playable`, { method: "POST", body: JSON.stringify(payload) });
                    out(result);
                    showPrototypeNotice(`原型创建请求已提交，状态：${result.status || "queued"}。刷新页面可继续查看创建进度。`, "info");
                    await loadRuns();
                    await loadPrototypeProgress();
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
                    ? `缺少必填项：${missing.map(prototypeFieldLabel).join("、")}。请补全后再运行原型路线。`
                    : payload.status === "project_busy"
                      ? "当前项目已有后台任务在执行，请等待顶部状态条消失后再启动原型路线。"
                    : payload.failureCode === "prototype_valid_godot_scene_missing"
                      ? "没有创建有效的godot场景文件"
                      : `原型创建请求失败：${payload.status || payload.error || payload.failureCode || error?.status || "unknown_error"}`;
                  showPrototypeNotice(message, "warn");
                }


                async function repairPrototype() {
                  if (!guardGlobalAction()) return;
                  if (!state.projectId) return out("请先选择一个项目。");
                  setLocalBusy(true, "原型修复中，请等待当前任务执行完毕。");
                  setPrototypeFormLocked(true);
                  $("repairPrototype").classList.add("hidden");
                  try {
                    const result = await api(`/api/projects/${state.projectId}/prototype-7day-playable/repair`, {
                      method: "POST",
                      body: JSON.stringify({ model: $("globalModel").value })
                    });
                    out(result);
                    await loadRuns();
                    await loadPrototypeProgress();
                    setLocalBusy(false);
                    await refreshActiveRun();
                  } catch (error) {
                    setLocalBusy(false);
                    setPrototypeFormLocked(false);
                    showError(error);
                  }
                }

                async function loadPrototypeProgress() {
                  if (!state.projectId) {
                    state.prototypeFailure = "";
                    $("prototypeProgress").className = "card muted";
                    $("prototypeProgress").textContent = "尚未选择项目。";
                    $("prototypeAcceptanceSummary").className = "card muted";
                    $("prototypeAcceptanceSummary").textContent = "尚未选择项目。";
                    $("chatPanel").classList.add("hidden");
                    setFormalFeedbackAvailability(false);
                    return;
                  }
                  try {
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
                    ${progress.failure ? `<p class="danger">${escapeHtml(progress.failure)}</p><p class="danger">可以点击“修复原型”继续修复；修复期间页面会锁定，刷新后查看最终成功或新的失败原因。</p>` : ""}
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
                  $("submitQuickFix").disabled = !canSubmit;
                  $("submitQuickFix").textContent = canSubmit ? "快速修复" : "需先完成 7 步原型后才能快速修复";
                  const hasPendingPlan = !!(state.iterationPlan?.session && Array.isArray(state.iterationPlan?.goals) && state.iterationPlan.goals.some(goal => goal.status === "pending"));
                  $("submitFormalFeedback").disabled = !canSubmit || hasPendingPlan;
                  $("submitFormalFeedback").textContent = !canSubmit
                    ? "\u9700\u5148\u5b8c\u6210 7 \u6b65\u539f\u578b\u540e\u624d\u80fd\u63d0\u4ea4\u53cd\u9988"
                    : hasPendingPlan
                      ? "当前已有未完成计划，请先执行下一目标"
                      : "提交反馈并生成迭代计划";
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
                    return `下一步建议来源：${formatNextStepSource(progress?.nextStepSource)}\n继续优化评估：${formatNextStepEvaluation(progress?.nextStepEvaluation)}\n${String(progress?.nextStepEvaluationReason || "").trim()}\n\n原型创建完成。\n\n本次完成：\n1. 已生成可玩的原型基础版本。\n2. 已完成基础启动检查。\n3. 已进入可继续优化状态。\n\n下一步建议：\n${suggestion}\n\n如果你同意，可以点击这条消息下方的“${continueActionLabel()}”。系统会根据当前状态执行更明确的动作：没有计划时生成计划；已有计划且评估认为过大时重拆计划；已有计划且边界清晰时继续执行下一目标。`.trim();
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

                function continueActionLabel() {
                  const hasPendingPlan = !!(state.iterationPlan?.session && Array.isArray(state.iterationPlan?.goals) && state.iterationPlan.goals.some(goal => goal.status === "pending"));
                  const decision = currentIterationPlanDecision();
                  if (hasPendingPlan && decision === "should_refine_plan") return "按建议重拆迭代计划";
                  if (hasPendingPlan) return "继续当前迭代目标";
                  return "按建议生成迭代计划";
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
                  $("runPrototype").textContent = locked ? "原型创建中..刷新页面查阅创建进度." : "运行原型路线";
                  $("repairPrototype").disabled = locked || isGlobalBusy();
                  $("repairPrototype").textContent = locked ? "原型修复中..刷新页面查阅修复进度." : "修复原型";
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
                  localStorage.setItem("phaseAAdminToken", token());
                  $("sessionStatus").textContent = token() ? "Token 验证中..." : "Token 已清空。";
                  if (token()) refreshProjects(); else showLoggedOut();
                };
                $("logout").onclick = () => {
                  localStorage.removeItem("phaseAAdminToken");
                  $("token").value = "";
                  state.projectId = "";
                  state.projects = [];
                  showLoggedOut();
                };
                $("refreshProjects").onclick = refreshProjects;
                $("createProject").onclick = createProject;
                $("importDraft").onclick = importDraft;
                $("sendChat").onclick = sendChat;
                $("evaluateIterationPlanFromChat").onclick = () => evaluateIterationPlan(true);
                $("submitQuickFix").onclick = submitQuickFix;
                $("submitFormalFeedback").onclick = submitFormalFeedback;
                $("createIterationPlan").onclick = createIterationPlan;
                $("evaluateIterationPlan").onclick = evaluateIterationPlan;
                $("executeIterationGoal").onclick = executeIterationGoal;
                $("chatSkillMode").onchange = renderSelectedSkillAction;
                renderChatHistory();
                $("loadRuns").onclick = loadRuns;
                $("createProjectPackage").onclick = createProjectPackage;
                $("runPrototype").onclick = runPrototype;
                $("repairPrototype").onclick = repairPrototype;
                $("refreshPrototypeProgress").onclick = loadPrototypeProgress;
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
        var runItems = string.Join("", runs.Select(run =>
            $"<li><a href=\"/runs/{Encode(run.RunId)}\">{Encode(run.RunType)}</a> - {Encode(run.Status)}</li>"));
        return WrapSimplePage(Encode(project.Name), $"<h1>{Encode(project.Name)}</h1><p>{Encode(project.GameName)}</p><ul>{runItems}</ul>");
    }

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
                <section id="packages" class="card"></section>
              </main>
              <script>
                const params = new URLSearchParams(location.search);
                const projectId = params.get("projectId") || "";
                const token = () => localStorage.getItem("phaseAAdminToken") || "";
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
                loadPackages();
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
