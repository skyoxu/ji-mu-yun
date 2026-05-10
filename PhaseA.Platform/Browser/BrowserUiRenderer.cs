using System.Net;
using PhaseA.Platform.Data;

namespace PhaseA.Platform.Browser;

public sealed class BrowserUiRenderer
{
    public string RenderShell()
    {
        return """
            <!doctype html>
            <html lang="en">
            <head>
              <meta charset="utf-8">
              <meta name="viewport" content="width=device-width, initial-scale=1">
              <title>Phase A Prototype Console</title>
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
                @media (max-width: 920px) {
                  main, .grid { grid-template-columns: 1fr; }
                }
              </style>
            </head>
            <body>
              <header>
                <h1>Phase A Prototype Console</h1>
                <p>Single-admin browser console for project creation, hosted prototype routes, run logs, and artifacts.</p>
              </header>
              <main>
                <aside class="stack">
                  <section class="stack">
                    <h2>Session</h2>
                    <label>Admin token <input id="token" type="password" autocomplete="off" placeholder="Bearer token"></label>
                    <button id="saveToken">Save token locally</button>
                    <button id="refreshProjects" class="ghost">Refresh projects</button>
                    <p id="sessionStatus" class="muted">Token is stored only in this browser localStorage.</p>
                  </section>
                  <section class="stack">
                    <h2>Create Project</h2>
                    <label>Project name <input id="projectName" placeholder="optional"></label>
                    <label>Game name <input id="gameName" placeholder="Demo Game"></label>
                    <label>Game type source <input id="gameTypeSource" value="manual"></label>
                    <button id="createProject">Create project</button>
                  </section>
                  <section>
                    <h2>Projects</h2>
                    <div id="projects" class="card-list"></div>
                  </section>
                </aside>
                <div class="stack">
                  <section class="stack">
                    <h2>Selected Project</h2>
                    <p id="selectedProject" class="muted">No project selected.</p>
                    <div class="grid">
                      <button id="chapter2" class="secondary">Run Chapter 2 Bootstrap</button>
                      <button id="loadRuns" class="ghost">Load Runs</button>
                    </div>
                  </section>
                  <section class="stack">
                    <h2>Prototype 7-Day Playable</h2>
                    <div class="grid">
                      <label>Slug <input id="protoSlug" placeholder="demo-prototype"></label>
                      <label>Stop after day <select id="stopAfterDay"><option>5</option><option>1</option><option>2</option><option>3</option><option>4</option></select></label>
                    </div>
                    <label>Hypothesis <textarea id="hypothesis"></textarea></label>
                    <label>Core player fantasy <textarea id="corePlayerFantasy"></textarea></label>
                    <label>Minimum playable loop <textarea id="minimumPlayableLoop"></textarea></label>
                    <label>Success criteria, one per line <textarea id="successCriteria"></textarea></label>
                    <label>Game feature <textarea id="gameFeature"></textarea></label>
                    <label>Core gameplay loop <textarea id="coreGameplayLoop"></textarea></label>
                    <label>Win/fail conditions <textarea id="winFailConditions"></textarea></label>
                    <button id="runPrototype" class="secondary">Run Prototype Route</button>
                  </section>
                  <section class="stack">
                    <h2>Prototype Commands</h2>
                    <div class="grid">
                      <label>TDD slug <input id="tddSlug" placeholder="demo-prototype"></label>
                      <label>Scene root <input id="sceneRoot" value="Node2D"></label>
                    </div>
                    <div class="split-actions">
                      <button data-stage="red" class="runTdd">TDD Red</button>
                      <button data-stage="green" class="runTdd">TDD Green</button>
                      <button data-stage="refactor" class="runTdd">TDD Refactor</button>
                    </div>
                    <button id="createScene" class="ghost">Create Prototype Scene</button>
                  </section>
                  <section>
                    <h2>Runs</h2>
                    <div id="runs" class="card-list"></div>
                  </section>
                  <section>
                    <h2>Output</h2>
                    <pre id="output">Ready.</pre>
                  </section>
                </div>
              </main>
              <script>
                const state = { projectId: "", projects: [] };
                const $ = id => document.getElementById(id);
                const out = value => $("output").textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
                const token = () => $("token").value.trim();
                const headers = () => ({ "Authorization": `Bearer ${token()}`, "Content-Type": "application/json" });

                function setTokenFromStorage() {
                  $("token").value = localStorage.getItem("phaseAAdminToken") || "";
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
                    const projects = await api("/api/projects");
                    state.projects = projects;
                    $("projects").innerHTML = projects.map(p => `
                      <button class="card ghost" data-project="${p.projectId}">
                        <strong>${escapeHtml(p.name)}</strong>
                        <span class="muted">${escapeHtml(p.gameName)} · ${escapeHtml(p.templateRuleId)}</span>
                      </button>
                    `).join("") || "<p class='muted'>No projects yet.</p>";
                    document.querySelectorAll("[data-project]").forEach(button => button.onclick = () => selectProject(button.dataset.project));
                    out(projects);
                  } catch (error) { showError(error); }
                }

                function selectProject(projectId) {
                  state.projectId = projectId;
                  const project = state.projects.find(p => p.projectId === projectId);
                  $("selectedProject").textContent = project ? `${project.name} (${project.projectId})` : projectId;
                  loadRuns();
                }

                async function createProject() {
                  try {
                    const payload = {
                      projectName: $("projectName").value.trim() || null,
                      gameName: $("gameName").value.trim(),
                      gameTypeSource: $("gameTypeSource").value.trim() || "manual"
                    };
                    const result = await api("/api/projects", { method: "POST", body: JSON.stringify(payload) });
                    out(result);
                    await refreshProjects();
                    if (result.projectId) selectProject(result.projectId);
                  } catch (error) { showError(error); }
                }

                async function loadRuns() {
                  if (!state.projectId) return out("Select a project first.");
                  try {
                    const result = await api(`/api/projects/${state.projectId}/runs`);
                    $("runs").innerHTML = result.runs.map(r => `
                      <button class="card ghost" data-run="${r.runId}">
                        <strong>${escapeHtml(r.runType)} · ${escapeHtml(r.status)}</strong>
                        <span class="muted">${escapeHtml(r.runId)}</span>
                      </button>
                    `).join("") || "<p class='muted'>No runs yet.</p>";
                    document.querySelectorAll("[data-run]").forEach(button => button.onclick = () => loadRun(button.dataset.run));
                    out(result);
                  } catch (error) { showError(error); }
                }

                async function loadRun(runId) {
                  try {
                    const result = await api(`/api/runs/${runId}`);
                    const links = (result.artifacts || []).map(a => `Artifact: ${a.artifactType} ${location.origin}/artifacts/${a.artifactId}`).join("\n");
                    out(`${JSON.stringify(result.run, null, 2)}\n\n${links}`);
                  } catch (error) { showError(error); }
                }

                async function runChapter2() {
                  if (!state.projectId) return out("Select a project first.");
                  try {
                    const result = await api(`/api/projects/${state.projectId}/chapter2-bootstrap`, { method: "POST", body: "{}" });
                    out(result);
                    await loadRuns();
                  } catch (error) { showError(error); }
                }

                async function runPrototype() {
                  if (!state.projectId) return out("Select a project first.");
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
                      stopAfterDay: Number($("stopAfterDay").value),
                      scoreEngine: "deterministic"
                    };
                    const result = await api(`/api/projects/${state.projectId}/prototype-7day-playable`, { method: "POST", body: JSON.stringify(payload) });
                    out(result);
                    await loadRuns();
                  } catch (error) { showError(error); }
                }

                async function runTdd(stage) {
                  if (!state.projectId) return out("Select a project first.");
                  try {
                    const payload = { slug: $("tddSlug").value.trim(), stage, expect: "auto", timeoutSec: 300 };
                    const result = await api(`/api/projects/${state.projectId}/prototype-tdd`, { method: "POST", body: JSON.stringify(payload) });
                    out(result);
                    await loadRuns();
                  } catch (error) { showError(error); }
                }

                async function createScene() {
                  if (!state.projectId) return out("Select a project first.");
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
                  $("sessionStatus").textContent = token() ? "Token saved locally." : "Token cleared.";
                };
                $("refreshProjects").onclick = refreshProjects;
                $("createProject").onclick = createProject;
                $("chapter2").onclick = runChapter2;
                $("loadRuns").onclick = loadRuns;
                $("runPrototype").onclick = runPrototype;
                $("createScene").onclick = createScene;
                document.querySelectorAll(".runTdd").forEach(button => button.onclick = () => runTdd(button.dataset.stage));
                setTokenFromStorage();
                if (token()) refreshProjects();
              </script>
            </body>
            </html>
            """;
    }

    public string RenderProject(ProjectSnapshot project, IReadOnlyList<RunSnapshot> runs)
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
            <html lang="en">
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
