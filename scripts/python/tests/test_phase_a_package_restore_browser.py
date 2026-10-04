"""ADR-0038/0061: execute the real downloads-page restore caller in Node."""
from pathlib import Path
import shutil
import subprocess
import unittest


class PackageRestoreBrowserTests(unittest.TestCase):
    def test_restore_resume_and_activation_confirmation(self):
        source = (Path(__file__).resolve().parents[3] / "PhaseA.Platform/Browser/BrowserUiRenderer.cs").read_text(encoding="utf-8")
        start = source.index("                const restoreStorageKey =")
        end = source.index("                function renderWebPreviewAction(", start)
        caller = source[start:end]
        node = shutil.which("node")
        self.assertIsNotNone(node, "Node is required for the browser caller regression.")
        harness = r"""
const vm = require("node:vm");
const assert = require("node:assert/strict");
const source = JSON.parse(process.argv[1]);
async function exercise(mode) {
  const saved = new Map(); const calls = []; const messages = []; let confirmation = mode !== "declined";
  let auth = "fixture-token"; let polls = 0; let refreshes = 0;
  const status = { textContent: "", hidden: true };
  const ctx = { projectId: "project-a", token: () => auth,
    confirm: () => confirmation, crypto: { randomUUID: () => "same-operation" },
    location: { origin: "https://fixture.invalid" },
    window: { parent: { postMessage: message => messages.push(message) } },
    document: { querySelectorAll: () => [{ disabled: false }] },
    $: () => status, disabledText: code => code, loadPackages: async () => { refreshes++; },
    sessionStorage: { getItem: key => saved.get(key) || null, setItem: (key, value) => saved.set(key, value), removeItem: key => saved.delete(key) },
    setTimeout: callback => { callback(); },
    fetch: async (url, options) => {
      calls.push({ url, options });
      assert.equal(options.cache, "no-store");
      assert.equal(options.headers.Authorization, "Bearer fixture-token");
      if (options.method === "POST") {
        assert.equal(JSON.parse(options.body).operationKey, "same-operation");
        assert.ok(url.includes("version%20one.zip/restore"));
        if (mode === "lost-response" && calls.length === 1) throw new Error("connection lost");
        if (mode === "auth-changed") auth = "different-account";
        return { ok: true, json: async () => ({ operationId: "run-one" }) };
      }
      assert.equal(url, "/api/runs/run-one");
      polls++;
      if (polls === 1) return { ok: true, json: async () => ({ run: { status: "queued" } }) };
      return { ok: true, json: async () => ({ run: { status: mode === "failed" ? "failed" : "succeeded",
        evidenceJson: JSON.stringify({ activated: mode !== "no-activation" }) } }) };
    }
  };
  vm.createContext(ctx);
  vm.runInContext(source + ";globalThis.restore = restorePackage; globalThis.resume = resumePackageRestore;", ctx);
  if (mode === "resume") saved.set("phasePackageRestore:project-a", JSON.stringify({ operationId: "run-one", fileName: "version one.zip", version: "v1" }));
  if (mode === "resume") await ctx.resume(); else await ctx.restore("version one.zip", "v1");
  if (mode === "lost-response") {
    assert.equal(JSON.parse(saved.get("phasePackageRestore:project-a")).operationKey, "same-operation");
    await ctx.resume();
    assert.equal(calls.filter(call => call.options.method === "POST").length, 2);
  }
  if (["success", "resume", "lost-response"].includes(mode)) {
    assert.equal(saved.size, 0); assert.equal(messages.length, 1);
    assert.equal(messages[0].projectId, "project-a"); assert.ok(status.textContent.includes("v1"));
  } else { assert.equal(messages.length, 0); }
  if (mode === "resume") assert.equal(calls.filter(call => call.options.method === "POST").length, 0);
  if (mode === "declined") { assert.equal(calls.length, 0); assert.equal(saved.size, 0); }
  if (mode === "auth-changed") { assert.equal(polls, 0); assert.equal(saved.size, 1); }
  if (mode === "failed") assert.equal(saved.size, 0);
  if (mode === "no-activation") assert.equal(saved.size, 1);
}
(async () => { for (const mode of ["success", "failed", "declined", "resume", "lost-response", "auth-changed", "no-activation"]) await exercise(mode);
  console.log("7 browser restore scenarios passed"); })().catch(error => { console.error(error); process.exit(1); });
"""
        import json
        result = subprocess.run([node, "-e", harness, json.dumps(caller)], capture_output=True, text=True, encoding="utf-8", timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("7 browser restore scenarios passed", result.stdout)
