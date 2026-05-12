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
                  grid-template-columns: minmax(18rem, 24rem) 1fr;
                  gap: 1rem;
                  padding: 1rem clamp(1rem, 4vw, 4rem) 4rem;
                }
                section, aside {
                  background: var(--panel);
                  border: 1px solid var(--line);
                  border-radius: 1.2rem;
                  box-shadow: 0 1.2rem 3rem rgba(57, 43, 24, 0.11);
                  padding: 1rem;
                }
                .stack { display: grid; gap: 1rem; align-content: start; }
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
                .grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; }
                .card-list { display: grid; gap: 0.6rem; }
                .card {
                  border: 1px solid var(--line);
                  border-radius: 0.9rem;
                  background: #fffdf8;
                  padding: 0.8rem;
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
                .split-actions { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem; }
                .health-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.6rem; }
                .metric { border: 1px solid var(--line); border-radius: 0.8rem; background: #fffdf8; padding: 0.7rem; }
                .metric strong { display: block; font-size: 1.15rem; }
                .chat-frame { max-height: 34rem; overflow: hidden; }
                .chat-scroll { max-height: 18rem; overflow-y: auto; padding-right: 0.25rem; }
                .status-ok { color: var(--accent); }
                .status-warn { color: var(--accent-2); }
                .status-fail { color: var(--danger); }
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
                    <button id="createProject">创建项目</button>
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
                    <button id="createProjectPackage" class="secondary">打包下载项目文件</button>
                    <div id="prototypeProgress" class="card muted">尚未开始 7 步可玩原型。</div>
                    <div id="projectHealthSummary" class="card muted">选择项目后显示项目健康摘要。</div>
                    <div id="projectPackageStatus" class="card muted">尚未生成项目压缩包。</div>
                  </section>
                  <section class="stack">
                    <h2>7 步可玩原型</h2>
                    <label>原型标识 Slug <input id="protoSlug" placeholder="demo-prototype"></label>
                    <label>原型假设 <textarea id="hypothesis" placeholder="这个原型要验证什么？"></textarea></label>
                    <label>核心玩家幻想 <textarea id="corePlayerFantasy" placeholder="玩家应该感受到什么？"></textarea></label>
                    <label>最小可玩循环 <textarea id="minimumPlayableLoop" placeholder="玩家反复执行的最小闭环是什么？"></textarea></label>
                    <label>成功标准，每行一条 <textarea id="successCriteria" placeholder="例如：30 秒内能理解目标"></textarea></label>
                    <label>游戏功能 <textarea id="gameFeature" placeholder="本次要实现或验证的核心功能"></textarea></label>
                    <label>核心玩法循环 <textarea id="coreGameplayLoop" placeholder="输入、反馈、奖励、升级或失败的循环"></textarea></label>
                    <label>胜利/失败条件 <textarea id="winFailConditions" placeholder="如何判定玩家成功或失败"></textarea></label>
                    <button id="repairPrototype" class="ghost hidden">修复原型</button>
                    <button id="runPrototype" class="secondary">运行原型路线</button>
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
                      <button data-stage="red" class="runTdd">TDD 红灯</button>
                      <button data-stage="green" class="runTdd">TDD 绿灯</button>
                      <button data-stage="refactor" class="runTdd">TDD 重构</button>
                    </div>
                    <button id="createScene" class="ghost">创建原型场景</button>
                  </section>
                  <section id="chatPanel" class="stack hidden chat-frame">
                    <h2>自由对话</h2>
                    <p class="muted">选择项目后即可聊天。后端会映射到服务器本机 Codex CLI 配置；需要执行工作流时仍使用上方固定按钮。</p>
                    <label>能力模式 <select id="chatSkillMode"><option value="normal">普通模式</option></select></label>
                    <div id="chatSkillDescription" class="card muted">普通模式：不激活 skills。</div>
                    <label>消息 <textarea id="chatMessage" placeholder="例如：帮我把这个原型想法拆成最小可玩循环"></textarea></label>
                    <button id="sendChat" class="secondary">发送消息</button>
                    <button id="submitFormalFeedback" class="ghost">提交反馈并继续优化原型</button>
                    <div id="chatHistory" class="card-list chat-scroll"></div>
                    <h2>正式反馈记录</h2>
                    <div id="feedbackRecords" class="card-list chat-scroll"></div>
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
                const state = { projectId: "", projects: [], runs: [], chatHistory: [], skillActions: [], authenticated: false, prototypeReadyForFeedback: false };
                const prototypeInputIds = ["protoSlug", "hypothesis", "corePlayerFantasy", "minimumPlayableLoop", "successCriteria", "gameFeature", "coreGameplayLoop", "winFailConditions"];
                const $ = id => document.getElementById(id);
                const out = value => $("output").textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
                const token = () => $("token").value.trim();
                const headers = () => ({ "Authorization": `Bearer ${token()}`, "Content-Type": "application/json" });

                function setTokenFromStorage() {
                  $("token").value = localStorage.getItem("phaseAAdminToken") || "";
                }

                function renderChatHistory() {
                  $("chatHistory").innerHTML = state.chatHistory.map(message => `
                    <div class="card">
                      <strong>${message.role === "assistant" ? "助手" : "我"}</strong>
                      <span>${escapeHtml(message.content)}</span>
                    </div>
                  `).join("") || "<p class='muted'>还没有对话。</p>";
                }

                function showLoggedOut() {
                  state.authenticated = false;
                  $("stepsPanel").classList.remove("hidden");
                  $("sessionPanel").classList.remove("hidden");
                  $("adminPanel").classList.add("hidden");
                  $("globalModelPanel").classList.add("hidden");
                  $("createProjectPanel").classList.add("hidden");
                  $("codexConfigPanel").classList.add("hidden");
                  $("prototypeCommandPanel").classList.add("hidden");
                  $("chatPanel").classList.add("hidden");
                  $("projectListPanel").classList.add("hidden");
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
                      history: state.chatHistory.slice(-10)
                    };
                    state.chatHistory.push({ role: "user", content: message });
                    renderChatHistory();
                    $("chatMessage").value = "";
                    const result = await api(`/api/projects/${state.projectId}/chat`, { method: "POST", body: JSON.stringify(payload) });
                    if (result.assistantMessage) {
                      state.chatHistory.push({ role: "assistant", content: result.assistantMessage });
                      renderChatHistory();
                    }
                    out(result);
                    await loadRuns();
                  } catch (error) { showError(error); }
                  finally {
                    $("sendChat").disabled = false;
                    $("sendChat").textContent = "发送消息";
                  }
                }

                async function submitFormalFeedback() {
                  if (!state.projectId) return out("\u8bf7\u5148\u9009\u62e9\u4e00\u4e2a\u9879\u76ee\u3002");
                  if (!state.prototypeReadyForFeedback) return out("\u8bf7\u5148\u8fd0\u884c\u5e76\u5b8c\u6210 7 \u6b65\u53ef\u73a9\u539f\u578b\uff0c\u518d\u63d0\u4ea4\u6b63\u5f0f\u53cd\u9988\u3002\u81ea\u7531\u5bf9\u8bdd\u4ecd\u53ef\u4f7f\u7528\u3002");
                  const feedback = $("chatMessage").value.trim();
                  if (!feedback) return out("\u8bf7\u8f93\u5165\u8981\u6b63\u5f0f\u63d0\u4ea4\u7684\u53cd\u9988\u3002");
                  $("submitFormalFeedback").disabled = true;
                  $("submitFormalFeedback").textContent = "\u6b63\u5f0f\u63d0\u4ea4\u4e2d...";
                  try {
                    state.chatHistory.push({ role: "user", content: feedback });
                    renderChatHistory();
                    $("chatMessage").value = "";
                    const result = await api(`/api/projects/${state.projectId}/prototype-feedback-iterations`, {
                      method: "POST",
                      body: JSON.stringify({ feedback, model: $("globalModel").value, skillActionId: $("chatSkillMode").value || "normal" })
                    });
                    state.chatHistory.push({ role: "assistant", content: result.assistantMessage || "\u672c\u8f6e\u6b63\u5f0f\u53cd\u9988\u5df2\u5b8c\u6210\u3002" });
                    renderChatHistory();
                    out(result);
                    await loadRuns();
                  } catch (error) { showError(error); }
                  finally {
                    setFormalFeedbackAvailability(state.prototypeReadyForFeedback);
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
                    const latestFailure = await loadLatestProjectCreationFailure();
                    const visibleProjects = listableProjects(projects);
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
                        <button class="danger-button" data-delete-project="${p.projectId}">删除项目</button>
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
                  const project = state.projects.find(p => p.projectId === projectId);
                  $("selectedProject").textContent = project ? `${project.name} (${project.projectId})` : projectId;
                  showProjectDetail();
                  loadProjectRuntimeState();
                }

                async function loadProjectRuntimeState() {
                  await loadRuns();
                  await loadPrototypeProgress();
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
                  } catch (error) {
                    showError(error);
                  } finally {
                    $("createProject").disabled = false;
                    $("createProject").textContent = "创建项目";
                  }
                }

                async function deleteProject(projectId) {
                  const confirmOne = document.querySelector(`[data-delete-one="${projectId}"]`)?.value.trim() || "";
                  const confirmTwo = document.querySelector(`[data-delete-two="${projectId}"]`)?.value.trim() || "";
                  if (confirmOne !== "delete" || confirmTwo !== "delete") {
                    out("删除项目需要在两个确认框都输入 delete。");
                    return;
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
                  const feedbackRuns = state.runs.filter(r => r.runType === "prototype-feedback-iteration");
                  $("feedbackRecords").innerHTML = feedbackRuns.map((run, index) => {
                    const downloads = feedbackArtifacts(run).map(a => `<a href="/artifacts/${escapeHtml(a.artifactId)}" target="_blank" rel="noreferrer">${escapeHtml(a.artifactType)}</a>`).join(" · ");
                    return `
                      <div class="card">
                        <strong>第 ${feedbackRuns.length - index} 次正式反馈 · ${escapeHtml(run.status)}</strong>
                        <span class="muted">${escapeHtml(run.runId)}</span>
                        <p>${downloads || "暂无可下载日志"}</p>
                      </div>
                    `;
                  }).join("") || "<p class='muted'>还没有正式反馈记录。</p>";
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

                async function createProjectPackage() {
                  if (!state.projectId) return out("请先选择一个项目。");
                  $("createProjectPackage").disabled = true;
                  $("createProjectPackage").textContent = "打包中...";
                  $("projectPackageStatus").className = "card muted";
                  $("projectPackageStatus").textContent = "正在生成只包含项目相关文件的压缩包。";
                  try {
                    const result = await api(`/api/projects/${state.projectId}/packages`, { method: "POST" });
                    $("projectPackageStatus").className = "card";
                    $("projectPackageStatus").innerHTML = `
                      <strong>项目包已生成：${escapeHtml(result.version)}</strong>
                      <p class="muted">${escapeHtml(result.fileName)} · ${result.includedFileCount} files · ${result.sizeBytes} bytes</p>
                      <button class="ghost" id="downloadLatestProjectPackage">下载压缩包</button>
                    `;
                    $("downloadLatestProjectPackage").onclick = () => downloadProjectPackage(result.downloadUrl, result.fileName);
                    out(result);
                    await downloadProjectPackage(result.downloadUrl, result.fileName);
                    await loadRuns();
                  } catch (error) { showError(error); }
                  finally {
                    $("createProjectPackage").disabled = false;
                    $("createProjectPackage").textContent = "打包下载项目文件";
                  }
                }

                async function downloadProjectPackage(downloadUrl, fileName) {
                  const response = await fetch(downloadUrl, { headers: { "Authorization": `Bearer ${token()}` } });
                  if (!response.ok) throw { status: response.status, payload: { error: "project_package_download_failed" } };
                  const blob = await response.blob();
                  const url = URL.createObjectURL(blob);
                  const anchor = document.createElement("a");
                  anchor.href = url;
                  anchor.download = fileName;
                  document.body.appendChild(anchor);
                  anchor.click();
                  anchor.remove();
                  URL.revokeObjectURL(url);
                }

                async function runPrototype() {
                  if (!state.projectId) return out("请先选择一个项目。");
                  setPrototypeFormLocked(true);
                  try {
                    const payload = {
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
                    const result = await api(`/api/projects/${state.projectId}/prototype-7day-playable`, { method: "POST", body: JSON.stringify(payload) });
                    out(result);
                    await loadRuns();
                    await loadPrototypeProgress();
                  } catch (error) {
                    setPrototypeFormLocked(false);
                    showError(error);
                  }
                }


                async function repairPrototype() {
                  if (!state.projectId) return out("请先选择一个项目。");
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
                  } catch (error) {
                    setPrototypeFormLocked(false);
                    showError(error);
                  }
                }

                async function loadPrototypeProgress() {
                  if (!state.projectId) {
                    $("prototypeProgress").className = "card muted";
                    $("prototypeProgress").textContent = "尚未选择项目。";
                    $("chatPanel").classList.add("hidden");
                    setFormalFeedbackAvailability(false);
                    return;
                  }
                  try {
                    const progress = await api(`/api/projects/${state.projectId}/prototype-7day-playable/progress`);
                    renderPrototypeProgress(progress);
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

                function updateChatPanelVisibility(progress) {
                  const status = progress?.status || "idle";
                  $("chatPanel").classList.remove("hidden");
                  setFormalFeedbackAvailability(status === "succeeded");
                  if (status === "succeeded") {
                    seedChatFromPrototypeProgress(progress);
                  }
                }

                function setFormalFeedbackAvailability(canSubmit) {
                  state.prototypeReadyForFeedback = canSubmit;
                  $("submitFormalFeedback").disabled = !canSubmit;
                  $("submitFormalFeedback").textContent = canSubmit ? "\u63d0\u4ea4\u53cd\u9988\u5e76\u7ee7\u7eed\u4f18\u5316\u539f\u578b" : "\u9700\u5148\u5b8c\u6210 7 \u6b65\u539f\u578b\u540e\u624d\u80fd\u63d0\u4ea4\u53cd\u9988";
                }

                function seedChatFromPrototypeProgress(progress) {
                  if (state.chatHistory.some(message => message.role === "assistant" && message.kind === "prototype-seed")) return;
                  const terminalOutput = latestPrototypeTerminalOutput(progress?.runId);
                  state.chatHistory.unshift({
                    role: "assistant",
                    kind: "prototype-seed",
                    content: terminalOutput || `7 步可玩原型已完成。当前 runId：${progress.runId || "未知"}。`
                  });
                  renderChatHistory();
                }

                function latestPrototypeTerminalOutput(runId) {
                  const run = state.runs.find(item => item.runId === runId) ||
                    state.runs.find(item => item.runType === "prototype-7day-playable" && item.status === "succeeded");
                  if (!run) return "";
                  const text = String(run.stdoutText || run.stderrText || "").trim();
                  if (!text) return "";
                  return tailText(text, 6000);
                }

                function tailText(text, maxLength) {
                  return text.length <= maxLength ? text : text.slice(text.length - maxLength);
                }

                function isPrototypeCreationLocked(progress) {
                  const status = progress?.status || "idle";
                  return !["idle", "failed"].includes(status);
                }

                function setPrototypeFormLocked(locked) {
                  prototypeInputIds.forEach(id => $(id).disabled = locked);
                  $("runPrototype").disabled = locked;
                  $("runPrototype").textContent = locked ? "原型创建中..刷新页面查阅创建进度." : "运行原型路线";
                  $("repairPrototype").disabled = locked;
                  $("repairPrototype").textContent = locked ? "原型修复中..刷新页面查阅修复进度." : "修复原型";
                }

                async function runTdd(stage) {
                  if (!state.projectId) return out("请先选择一个项目。");
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
                }

                async function createScene() {
                  if (!state.projectId) return out("请先选择一个项目。");
                  try {
                    const payload = { slug: $("tddSlug").value.trim(), sceneRoot: $("sceneRoot").value.trim() || "Node2D" };
                    const result = await api(`/api/projects/${state.projectId}/prototype-scene`, { method: "POST", body: JSON.stringify(payload) });
                    out(result);
                    await loadRuns();
                  } catch (error) { showError(error); }
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
                $("sendChat").onclick = sendChat;
                $("submitFormalFeedback").onclick = submitFormalFeedback;
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
