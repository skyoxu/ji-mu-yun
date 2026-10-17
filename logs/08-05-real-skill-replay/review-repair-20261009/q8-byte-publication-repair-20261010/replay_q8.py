"""Invoke the native ADR-0058 Q8 predicate in read-only mode."""
import contextlib
import io
import json
from pathlib import Path
import sys
import time
import traceback

WS = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
Q8 = WS / "logs/08-05-real-skill-replay/review-repair-20261009/current-run-q8-recovery-r4"
sys.path.insert(0, str(WS / ".agents/skills/quick-dev-tdd-adapter/tools"))
from coverage_predicates import publish_implementation_complete


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    command = load(Q8 / "q8-command/command-result.json")["argv"]
    options = {command[i]: command[i + 1] for i in range(len(command) - 1) if command[i].startswith("--")}
    native_input = load(Q8 / "terminal-input.v2.json")
    stdout, stderr = io.StringIO(), io.StringIO()
    start = time.monotonic()
    report = {"authorizes": [], "tests_executed": False, "mode": "native-Q8-verify-existing",
              "q8_result_ref": str((Q8 / "implementation-complete-result.v2.json").relative_to(WS)),
              "predecessor_count": len(native_input["predecessors"])}
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            result = publish_implementation_complete(
                workspace=WS,
                semantic_plan=WS / options["--plan"] / "semantic-plan-bundle.v1.json",
                predecessors=native_input["predecessors"],
                snapshot_roots=load(WS / options["--snapshot-roots"]),
                source_commit=options["--source-commit"],
                base_commit=options["--base-commit"],
                out=Q8 / "implementation-complete-result.v2.json",
                profile=native_input["profile"],
                detached_promotion_binding=native_input["detached_promotion_binding"],
                verify_existing=True,
            )
            report.update(status="pass", predicate=result["predicate"],
                          runtime_closure_sha256=result["runtime_closure_sha256"],
                          runtime_closure_tuple_count=len(result["runtime_closure_tuples"]),
                          terminal_input_sha256=result["terminal_input_sha256"])
            print(json.dumps(report))
        except Exception as error:
            traceback.print_exc()
            report.update(status="fail", error=str(error))
    report["elapsed_seconds"] = time.monotonic() - start
    (OUT / "q8-readonly-stdout.txt").write_text(stdout.getvalue(), encoding="utf-8", newline="\n")
    (OUT / "q8-readonly-stderr.txt").write_text(stderr.getvalue(), encoding="utf-8", newline="\n")
    (OUT / "q8-readonly-result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report))
    sys.exit(0 if report["status"] == "pass" else 1)
