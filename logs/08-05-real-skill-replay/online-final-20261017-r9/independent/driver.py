"""Three isolated forward checks; never an Acceptance/Q8 validation."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

BASE = Path(__file__).resolve().parent
SOURCE = BASE.parent / "repair-08-05-final-20261017/.agents/skills/run-refactor-implementation-acceptance/scripts"
PYTHON = BASE.parent / "acceptance-final-env-20261017/bin/python"
CLI = SOURCE / "acceptance_cli.py"
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
sys.path.insert(0, str(SOURCE))
from execution_control import create_persisted_run

HASH = "sha256:" + "a" * 64
CONTRACT = "sha256:" + "b" * 64
commands = []


def run(argv, cwd=BASE):
    process = subprocess.run([str(x) for x in argv], cwd=cwd, env=ENV,
                             text=True, capture_output=True, timeout=60)
    item = {"command": [str(x) for x in argv], "cwd": str(cwd),
            "environmentOverrides": {"PYTHONDONTWRITEBYTECODE": "1"},
            "stdout": process.stdout, "stderr": process.stderr,
            "exitCode": process.returncode}
    commands.append(item)
    (BASE / "results.json").write_text(json.dumps({"status": "running", "commands": commands}, indent=2) + "\n")
    return item


def dump(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def digest(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def make_case(name, scripts):
    fixture = BASE / name
    fixture.mkdir()
    (fixture / "seed.txt").write_text("original\n")
    (fixture / ".gitignore").write_text("logs/\n")
    assert run(["git", "init", "--quiet"], fixture)["exitCode"] == 0
    assert run(["git", "add", "--", "seed.txt", ".gitignore"], fixture)["exitCode"] == 0
    run_root = fixture / "logs"
    run_root.mkdir()
    run_dir = create_persisted_run(run_root, "run-001", HASH, CONTRACT)
    actions = [{"actionId": "action-" + str(i + 1), "commandId": "command-" + str(i + 1),
                "dependsOn": [] if i == 0 else ["action-" + str(i)],
                "activation": True, "order": i} for i in range(len(scripts))]
    descriptors = [{"id": "command-" + str(i + 1), "executable": str(PYTHON),
                    "argv": ["-B", "-c", code], "cwd": ".", "timeout_seconds": 20,
                    "shell": False, "allowed_write_roots": [], "forbidden_write_roots": [],
                    "environment_allowlist": ["PATH", "PYTHONDONTWRITEBYTECODE"],
                    "typed_placeholders": {}, "placeholder_values": {}}
                   for i, code in enumerate(scripts)]
    material = {"schemaVersion": "acceptance-command-registry.v1", "commands": descriptors}
    registry_hash = "sha256:" + hashlib.sha256(json.dumps(material, ensure_ascii=False,
                                  sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    registry = {"schemaVersion": material["schemaVersion"], "registryHash": registry_hash,
                "commands": [dict(d, registry_hash=registry_hash) for d in descriptors]}
    action_path, registry_path = BASE / (name + "-actions.json"), BASE / (name + "-registry.json")
    dump(action_path, actions)
    dump(registry_path, registry)

    def invoke(operation):
        argv = [PYTHON, "-B", CLI, operation, "--run-dir", run_dir,
                "--actions", action_path, "--run-input-hash", HASH, "--contract-hash", CONTRACT]
        if operation == "resume-persisted-run":
            argv += ["--repository-root", fixture, "--command-registry", registry_path]
        return run(argv)

    return fixture, run_dir, invoke


observations = []
try:
    fixture, persisted, invoke = make_case("read-only", [
        "from pathlib import Path; print('first:' + Path('seed.txt').read_text().strip())",
        "from pathlib import Path; print('second:' + Path('seed.txt').read_text().strip())",
    ])
    first = invoke("resume-persisted-run")
    assert first["exitCode"] == 0
    first_value = json.loads(first["stdout"])
    assert first_value["actionId"] == "action-1"
    receipt = persisted / first_value["resultReceipt"]["path"]
    first_receipt_hash = digest(receipt)
    middle = invoke("inspect-persisted-run")
    middle_value = json.loads(middle["stdout"])
    assert middle["exitCode"] == 0 and middle_value["actionStates"] == {"action-1": "completed", "action-2": "ready"}
    second = invoke("resume-persisted-run")
    second_value = json.loads(second["stdout"])
    assert second["exitCode"] == 0 and second_value["actionId"] == "action-2"
    final = invoke("inspect-persisted-run")
    final_value = json.loads(final["stdout"])
    assert final["exitCode"] == 0 and final_value["actionStates"] == {"action-1": "completed", "action-2": "completed"}
    assert digest(receipt) == first_receipt_hash
    events = [json.loads(line) for line in (persisted / "acceptance-events.jsonl").read_text().splitlines()]
    assert sum(e["eventType"] == "action-started" for e in events) == 2
    assert (fixture / "seed.txt").read_text() == "original\n"
    observations.append({"scenario": "split-read-only-persistence", "status": "pass",
                         "firstReceiptPreserved": True, "startedActions": 2,
                         "middleStates": middle_value["actionStates"], "finalStates": final_value["actionStates"]})

    fixture, persisted, invoke = make_case("tracked-write", [
        "from pathlib import Path; Path('seed.txt').write_text('changed\\n')",
    ])
    rejected = invoke("resume-persisted-run")
    assert rejected["exitCode"] != 0 and "read-only command changed repository bytes" in rejected["stderr"]
    assert (fixture / "seed.txt").read_text() == "changed\n"
    polluted = json.loads((persisted / "run-polluted.v1.json").read_text())
    assert polluted["reason"] == "read-only command changed repository bytes"
    observations.append({"scenario": "real-tracked-write-rejected", "status": "pass",
                         "trackedFileActuallyChanged": True, "pollutionReason": polluted["reason"],
                         "limitation": "Guard detects and rejects after execution; it does not roll back the fixture file."})

    fixture, persisted, invoke = make_case("failed-action", [
        "import sys; print('intentional failure'); print('fixture stderr', file=sys.stderr); sys.exit(7)",
    ])
    failed = invoke("resume-persisted-run")
    value = json.loads(failed["stdout"])
    assert failed["exitCode"] == 1 and value["receipt"]["exitCode"] == 7
    assert value["receipt"]["processResult"]["stdout"] == "intentional failure\n"
    assert value["receipt"]["processResult"]["stderr"] == "fixture stderr\n"
    inspection = invoke("inspect-persisted-run")
    assert inspection["exitCode"] == 0 and json.loads(inspection["stdout"])["actionStates"] == {"action-1": "failed"}
    events_before = (persisted / "acceptance-events.jsonl").read_bytes()
    retry = invoke("resume-persisted-run")
    assert retry["exitCode"] != 0 and "persisted action failed; explicit recovery is required" in retry["stderr"]
    assert (persisted / "acceptance-events.jsonl").read_bytes() == events_before
    assert not (persisted / "actions/action-1/attempt-002").exists()
    observations.append({"scenario": "failed-action-is-terminal", "status": "pass",
                         "realChildExitCode": 7, "inspectionState": "failed", "retryExecuted": False,
                         "lifecycleLogUnchangedAfterRetry": True})
    status = "pass"
    failure = None
except Exception as exc:
    status = "fail"
    failure = type(exc).__name__ + ": " + str(exc)

result = {"status": status, "scope": "Function-level persisted-run creation plus real Acceptance CLI resume/inspect in index-only temporary Git fixtures.",
          "notProven": ["Real Acceptance", "Q8", "real 08-05", "Windows behavior", "model launch"],
          "authorizes": [], "driverCommand": [str(PYTHON), "-B", str(Path(__file__).resolve())],
          "environmentOverrides": {"PYTHONDONTWRITEBYTECODE": "1"},
          "sourceHashes": {str(CLI): digest(CLI), str(SOURCE / "execution_control.py"): digest(SOURCE / "execution_control.py")},
          "observations": observations, "commands": commands, "failure": failure}
dump(BASE / "results.json", result)
(BASE / "report.md").write_text(
    "# Minimal independent forward validation\n\n"
    + "Result: " + status.upper() + ".\n\n"
    + "Scope: native `create_persisted_run` plus real `acceptance_cli.py` resume/inspect commands, each in a fresh Python process. Three minimal index-only Git fixtures; no commits, pushes, real plan execution, network calls, or model launches.\n\n"
    + "1. Two dependent read-only actions execute in separate CLI calls. Fresh-process inspection replays the first completion and exposes the second as ready. The original receipt remains unchanged.\n"
    + "2. A real child changes a tracked fixture file. The read-only guard rejects the execution and marks its run polluted. Detection is post-execution and does not roll back the file.\n"
    + "3. A real child exits 7 with recorded stdout/stderr. Inspection preserves failed state; identical retry is rejected without a second attempt or lifecycle mutation.\n\n"
    + "`results.json` contains actual invoked commands, working directories, stdout, stderr, exit codes, observations, and source hashes. The tracked-write child has no published process receipt because the guard raises; its real file change and CLI rejection are preserved.\n\n"
    + "This is function-level persistence and real CLI validation. It is not real Acceptance or Q8 evidence and grants no authority.\n"
    + ("\nFailure: " + failure + "\n" if failure else ""))
print(json.dumps({"status": status, "scenarios": observations, "failure": failure}, indent=2))
raise SystemExit(0 if status == "pass" else 1)
