#!/usr/bin/env python3
"""
Run GdUnit4 tests headless and archive reports to logs/e2e/<date>/.

Usage:
  py -3 scripts/python/run_gdunit.py \
    --godot-bin "C:\\Godot\\Godot_v4.5.1-stable_mono_win64_console.exe" \
    --project Tests.Godot \
    --add tests/Adapters --add tests/OtherSuite \
    --timeout-sec 300
"""
import argparse
import datetime as dt
import os
import shutil
import subprocess
import json
import sys
import threading
import time
import xml.etree.ElementTree as ET

from ci_process import run_logged_command

GODOT_LOG_LIMIT_BYTES = 32 * 1024 * 1024
GODOT_LOG_GROWTH_LIMIT_BYTES = 16 * 1024 * 1024


def _candidate_dotnet_paths(root: str) -> list[str]:
    exe_name = "dotnet.exe" if os.name == "nt" else "dotnet"
    candidates: list[str] = []

    which_dotnet = shutil.which("dotnet")
    if which_dotnet:
        candidates.append(which_dotnet)

    for env_key in ("DOTNET_ROOT", "DOTNET_HOME"):
        env_val = os.environ.get(env_key)
        if env_val:
            candidates.append(os.path.join(env_val, exe_name))

    candidates.append(os.path.join(root, ".dotnet", exe_name))
    candidates.append(os.path.join(os.path.expanduser("~"), ".dotnet", exe_name))

    if os.name == "nt":
        candidates.append(r"C:\Program Files\dotnet\dotnet.exe")
        candidates.append(r"C:\Program Files (x86)\dotnet\dotnet.exe")

    unique: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = os.path.normcase(os.path.normpath(candidate))
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def _resolve_dotnet(root: str) -> str:
    for candidate in _candidate_dotnet_paths(root):
        if os.path.isfile(candidate):
            return candidate
    return "dotnet"


def _build_process_env(root: str, dotnet_bin: str) -> dict[str, str]:
    env = os.environ.copy()
    if os.path.isfile(dotnet_bin):
        dotnet_root = os.path.dirname(dotnet_bin)
        env["DOTNET_ROOT"] = dotnet_root
        env["DOTNET_HOME"] = dotnet_root
        current_path = env.get("PATH", "")
        path_parts = current_path.split(os.pathsep) if current_path else []
        if dotnet_root not in path_parts:
            env["PATH"] = dotnet_root + (os.pathsep + current_path if current_path else "")
    return env


def _godot_isolation_base(root: str, date: str) -> str:
    base = os.environ.get("PHASEA_GODOT_USER_DATA_ROOT", "").strip()
    if not base:
        validation_root = os.environ.get("PHASEA_VALIDATION_BUILD_ROOT", "").strip()
        base = validation_root if validation_root else os.path.join(root, "logs", "e2e", date)
    return base


def _isolated_godot_runtime_env(root: str, date: str) -> dict[str, str]:
    run_id = f"gdunit-appdata-{os.getpid()}-{int(time.time() * 1000)}"
    base = _godot_isolation_base(root, date)
    appdata_root = os.path.join(base, run_id)
    roaming = os.path.join(appdata_root, "Roaming")
    local = os.path.join(appdata_root, "Local")
    os.makedirs(os.path.join(roaming, "Godot"), exist_ok=True)
    os.makedirs(os.path.join(local, "Godot"), exist_ok=True)
    return {
        "APPDATA": roaming,
        "LOCALAPPDATA": local,
    }


def _msbuild_isolation_args(scope: str) -> list[str]:
    build_root = os.environ.get("PHASEA_VALIDATION_BUILD_ROOT", "").strip()
    if not build_root:
        return []
    safe_scope = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in scope).strip("_") or "validation"
    obj_root = os.path.join(build_root, safe_scope, "obj", "$(MSBuildProjectName)")
    bin_root = os.path.join(build_root, safe_scope, "bin", "$(MSBuildProjectName)")
    return [
        f"-p:BaseIntermediateOutputPath={obj_root}{os.sep}",
        f"-p:IntermediateOutputPath={obj_root}{os.sep}Debug{os.sep}",
        f"-p:BaseOutputPath={bin_root}{os.sep}",
        f"-p:OutputPath={bin_root}{os.sep}Debug{os.sep}",
        "-p:UseSharedCompilation=false",
        "-p:NodeReuse=false",
        "-m:1",
        "-p:BuildInParallel=false",
    ]


def _isolated_godot_user_data_dir(root: str, date: str) -> str:
    base = _godot_isolation_base(root, date)
    run_id = f"gdunit-user-{os.getpid()}-{int(time.time() * 1000)}"
    user_dir = os.path.join(base, run_id)
    os.makedirs(user_dir, exist_ok=True)
    os.makedirs(os.path.join(user_dir, "logs"), exist_ok=True)
    return user_dir


def _isolated_godot_user_data_args(root: str, date: str) -> list[str]:
    user_dir = _isolated_godot_user_data_dir(root, date)
    return ["--user-data-dir", user_dir]


def _copy_reports_best_effort(src_root: str, dest_root: str) -> list[tuple[str, str, str]]:
    failures: list[tuple[str, str, str]] = []
    if not os.path.isdir(src_root):
        return failures

    for current_root, dir_names, file_names in os.walk(src_root):
        rel_root = os.path.relpath(current_root, src_root)
        dest_dir = dest_root if rel_root in (".", "") else os.path.join(dest_root, rel_root)
        try:
            os.makedirs(dest_dir, exist_ok=True)
        except OSError as ex:
            failures.append((current_root, dest_dir, str(ex)))
            dir_names[:] = []
            continue

        for name in file_names:
            src = os.path.join(current_root, name)
            dst = os.path.join(dest_dir, name)
            try:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
            except OSError as ex:
                failures.append((src, dst, str(ex)))
    return failures


def _find_latest_results_xml(reports_dir: str, *, not_before_ns: int | None = None):
    try:
        if not os.path.isdir(reports_dir):
            return None
        best_path = None
        best_mtime = -1.0
        for name in os.listdir(reports_dir):
            if not name.startswith("report_"):
                continue
            cand = os.path.join(reports_dir, name, "results.xml")
            if not os.path.isfile(cand):
                continue
            stat = os.stat(cand)
            if not_before_ns is not None and stat.st_mtime_ns < not_before_ns:
                continue
            mtime = stat.st_mtime_ns
            if mtime > best_mtime:
                best_mtime = mtime
                best_path = cand
        return best_path
    except Exception:
        return None


def _parse_results_xml(path: str):
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        failures = int(root.attrib.get("failures", "0"))
        tests = int(root.attrib.get("tests", "0"))
        errors = 0
        for ts in root.findall("testsuite"):
            errors += int(ts.attrib.get("errors", "0"))
        return {"path": path, "tests": tests, "failures": failures, "errors": errors, "skipped": int(root.attrib.get("skipped", "0"))}
    except Exception as ex:
        return {"path": path, "error": f"parse_failed:{type(ex).__name__}"}


def _result_exit_code(rc: int, parsed: dict, *, strict: bool) -> int:
    # ADR-0025: current positive case counts and complete results are mandatory.
    complete = (
        parsed and not parsed.get("error") and parsed.get("tests", 0) > parsed.get("skipped", 0)
        and parsed.get("failures") == 0 and parsed.get("errors") == 0
    )
    if not complete:
        return rc if rc != 0 else 1
    if not strict and rc != 124:
        return 0
    return rc


def run_cmd(args, cwd=None, timeout=600_000, env=None, log_root=None):
    # ADR-0005: compiler descendants may retain inherited stdout after Godot exits.
    rc, output, _ = run_logged_command(
        args, cwd=cwd, timeout=timeout, env=env, log_root=log_root
    )
    return rc, output


def _godot_log_files(env: dict[str, str] | None, user_data_dir: str | None = None) -> list[str]:
    roots: list[str] = []
    if user_data_dir:
        roots.append(user_data_dir)
    if env:
        appdata = env.get("APPDATA")
        localappdata = env.get("LOCALAPPDATA")
        if appdata:
            roots.append(os.path.join(appdata, "Godot"))
        if localappdata:
            roots.append(os.path.join(localappdata, "Godot"))

    files: list[str] = []
    seen: set[str] = set()
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for current_root, _, names in os.walk(root):
            for name in names:
                if name.lower() != "godot.log":
                    continue
                path = os.path.join(current_root, name)
                key = os.path.normcase(os.path.normpath(path))
                if key not in seen:
                    seen.add(key)
                    files.append(path)
    return files


def _godot_log_growth_failure(
    env: dict[str, str] | None,
    user_data_dir: str | None,
    baseline_sizes: dict[str, int],
    max_total_bytes: int | None = None,
    max_growth_bytes: int | None = None,
) -> str | None:
    max_total_bytes = GODOT_LOG_LIMIT_BYTES if max_total_bytes is None else max_total_bytes
    max_growth_bytes = GODOT_LOG_GROWTH_LIMIT_BYTES if max_growth_bytes is None else max_growth_bytes
    for path in _godot_log_files(env, user_data_dir):
        try:
            size = os.path.getsize(path)
        except OSError:
            continue
        baseline = baseline_sizes.setdefault(path, size)
        if size > max_total_bytes:
            return f"godot_log_size_limit_exceeded:{path}:{size}"
        if size - baseline > max_growth_bytes:
            return f"godot_log_growth_limit_exceeded:{path}:{size - baseline}"
    return None


def run_cmd_failfast(
    args,
    cwd=None,
    timeout=600_000,
    break_markers=None,
    env=None,
    godot_user_data_dir=None,
    godot_log_poll_interval=1.0,
):
    """Run a process and stream stdout; if any line contains a break marker, kill early and return rc=1.
    This avoids long timeouts when Godot enters Debugger Break state.
    """
    break_markers = break_markers or [
        'Debugger Break',
        'Parser Error',
        'SCRIPT ERROR',
    ]
    p = subprocess.Popen(args, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, encoding='utf-8', errors='ignore')
    buf_lines = []
    hit_break = False
    log_failure_reason: list[str] = []
    log_monitor_stop = threading.Event()
    godot_log_baseline_sizes: dict[str, int] = {}

    def monitor_godot_logs() -> None:
        while not log_monitor_stop.wait(godot_log_poll_interval):
            if p.poll() is not None:
                return
            log_failure = _godot_log_growth_failure(env, godot_user_data_dir, godot_log_baseline_sizes)
            if log_failure:
                log_failure_reason.append(log_failure)
                _terminate_process_tree(p)
                return

    log_monitor = threading.Thread(target=monitor_godot_logs, daemon=True)
    log_monitor.start()
    try:
        # Poll line-by-line up to timeout
        end_ts = dt.datetime.now().timestamp() + (timeout/1000.0)
        while True:
            line = p.stdout.readline()
            if line:
                buf_lines.append(line)
                low = line.lower()
                if any(m.lower() in low for m in break_markers):
                    hit_break = True
                    _terminate_process_tree(p)
                    break
            else:
                if p.poll() is not None:
                    break
                if log_failure_reason:
                    hit_break = True
                    break
            if dt.datetime.now().timestamp() > end_ts:
                _terminate_process_tree(p)
                return 124, ''.join(buf_lines)
        out = ''.join(buf_lines)
        if log_failure_reason:
            out += f"\nGDUNIT_FAILFAST {log_failure_reason[0]}\n"
            hit_break = True
        if hit_break:
            return 1, out
        return (p.returncode or 0), out
    except Exception:
        _terminate_process_tree(p)
        return 1, ''.join(buf_lines)
    finally:
        log_monitor_stop.set()
        log_monitor.join(timeout=2.0)
        if p.poll() is None:
            _terminate_process_tree(p)
        try:
            p.wait(timeout=5)
        except Exception:
            _terminate_process_tree(p)
        try:
            if p.stdout:
                p.stdout.close()
        except Exception:
            pass


def _terminate_process_tree(process) -> None:
    try:
        pid = getattr(process, "pid", None)
        if pid and os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=20,
            )
            return
    except Exception:
        pass
    try:
        process.kill()
    except Exception:
        pass


def write_text(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
    except PermissionError:
        base, ext = os.path.splitext(path)
        fallback = f"{base}-{os.getpid()}-{int(time.time() * 1000)}{ext or '.txt'}"
        with open(fallback, 'w', encoding='utf-8') as f:
            f.write(content)


def ensure_runtime_logs_godot_ignored(repo_root: str) -> None:
    logs_root = os.path.join(repo_root, "logs")
    os.makedirs(logs_root, exist_ok=True)
    gdignore = os.path.join(logs_root, ".gdignore")
    if not os.path.exists(gdignore):
        with open(gdignore, "w", encoding="utf-8") as f:
            f.write("")


def _cleanup_godot_processes(godot_bin: str) -> None:
    exe_name = os.path.basename(godot_bin).strip()
    if not exe_name:
        return
    exe_names = [exe_name]
    if exe_name.endswith("_console.exe"):
        exe_names.append(exe_name.replace("_console.exe", ".exe"))
    try:
        for name in dict.fromkeys(exe_names):
            subprocess.run(
                ["taskkill", "/F", "/IM", name, "/T"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=20,
            )
    except Exception:
        pass


def ensure_tests_project_junction(repo_root: str, project_abs: str, out_dir: str) -> None:
    """
    Hard gate: ensure Tests.Godot/Game.Godot is a Junction to the real Game.Godot.

    This prevents drift between test resources and the actual game project.
    """
    try:
        proj_name = os.path.basename(os.path.normpath(project_abs))
        if proj_name != "Tests.Godot":
            return

        # Only enforce when the project is within repo root.
        try:
            common = os.path.commonpath([os.path.abspath(repo_root), os.path.abspath(project_abs)])
        except ValueError:
            return
        if os.path.abspath(common) != os.path.abspath(repo_root):
            return

        ensure_script = os.path.join(repo_root, "scripts", "python", "ensure_tests_godot_junction.py")
        if not os.path.isfile(ensure_script):
            raise RuntimeError("ensure_tests_godot_junction_script_missing")

        rel_project = os.path.relpath(project_abs, repo_root)
        cmd = [
            sys.executable,
            ensure_script,
            "--root",
            repo_root,
            "--tests-project",
            rel_project,
            "--link-name",
            "Game.Godot",
            "--target-rel",
            "Game.Godot",
            "--create-if-missing",
            "--fix-wrong-target",
        ]
        rc, out = run_cmd(cmd, cwd=repo_root, timeout=60_000)
        try:
            write_text(os.path.join(out_dir, "ensure-tests-godot-junction.txt"), out)
        except Exception:
            pass
        if rc != 0:
            raise RuntimeError("ensure_tests_godot_junction_failed")
    except Exception:
        raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--godot-bin', required=True)
    ap.add_argument('--project', default='Tests.Godot')
    ap.add_argument('--add', action='append', default=[], help='Add directory or suite path(s). E.g., tests/Adapters or res://tests/Adapters')
    ap.add_argument('--timeout-sec', type=int, default=600, help='Timeout seconds for test run (default 600)')
    ap.add_argument('--prewarm', action='store_true', help='Prewarm: build solutions before running tests')
    ap.add_argument('--rd', dest='report_dir', default=None, help='Custom destination to copy reports into (defaults to logs/e2e/<date>/gdunit-reports)')
    args = ap.parse_args()

    root = os.getcwd()
    dotnet_bin = _resolve_dotnet(root)
    process_env = _build_process_env(root, dotnet_bin)
    proj = os.path.abspath(args.project)
    date = dt.date.today().strftime('%Y-%m-%d')
    out_dir = os.path.join(root, 'logs', 'e2e', date)
    os.makedirs(out_dir, exist_ok=True)
    godot_user_data_dir = _isolated_godot_user_data_dir(root, date)
    godot_user_data_args = ["--user-data-dir", godot_user_data_dir]
    process_env.update(_isolated_godot_runtime_env(root, date))

    ensure_runtime_logs_godot_ignored(root)
    _cleanup_godot_processes(args.godot_bin)

    # Hard gate before any Godot invocation.
    ensure_tests_project_junction(repo_root=root, project_abs=proj, out_dir=out_dir)

    # Optional prewarm with fallback
    prewarm_rc = None
    prewarm_note = None
    if args.prewarm:
        pre_cmd = [args.godot_bin, '--headless', *godot_user_data_args, '--path', proj, '--build-solutions', '--quit']
        _rcp, _outp = run_cmd(pre_cmd, cwd=proj, timeout=300_000, env=process_env, log_root=root)
        prewarm_attempts = 1
        prewarm_rc = _rcp
        # Write first attempt
        write_text(os.path.join(out_dir, 'prewarm-godot.txt'), _outp)
        if _rcp != 0:
            # Wait and retry once to mitigate transient C# load issues
            time.sleep(3)
            _rcp2, _outp2 = run_cmd(pre_cmd, cwd=proj, timeout=360_000, env=process_env, log_root=root)
            prewarm_attempts = 2
            prewarm_rc = _rcp2
            # Append retry log to same file
            try:
                with open(os.path.join(out_dir, 'prewarm-godot.txt'), 'a', encoding='utf-8') as f:
                    f.write("\n=== retry rc=%d ===\n" % _rcp2)
                    f.write(_outp2)
            except Exception:
                pass
            if _rcp2 == 0:
                prewarm_note = 'retry-ok'
            else:
                # Fallback to dotnet build to avoid editor plugin failures
                dotnet_projects = []
                tests_csproj = os.path.join(proj, 'Tests.Godot.csproj')
                if os.path.isfile(tests_csproj):
                    dotnet_projects.append(tests_csproj)
                # Also try solution at repo root if present
                sln = os.path.join(root, 'GodotGame.sln')
                # Prefer project build; if solution exists, add as secondary
                build_logs = []
                for item in (dotnet_projects or [sln] if os.path.isfile(sln) else []):
                    rc_b, out_b = run_cmd([dotnet_bin, 'build', item, '-c', 'Debug', '-v', 'minimal', *_msbuild_isolation_args('gdunit-fallback')], cwd=root, timeout=600_000, env=process_env)
                    build_logs.append((item, rc_b, out_b))
                # Persist build logs
                agg = []
                for item, rc_b, out_b in build_logs:
                    agg.append(f'=== {item} rc={rc_b} ===\n{out_b}\n')
                write_text(os.path.join(out_dir, 'prewarm-dotnet.txt'), '\n'.join(agg) if agg else 'NO_DOTNET_BUILD_TARGETS')
                prewarm_note = 'fallback-dotnet'

    # Run tests (Debugger break, fail-fast).
    # Build command with optional -a filters
    cmd = [args.godot_bin, '--headless', *godot_user_data_args, '--path', proj, '-s', '-d', 'res://addons/gdUnit4/bin/GdUnitCmdTool.gd', '--ignoreHeadlessMode']
    for a in args.add:
        apath = a
        if not apath.startswith('res://'):
            # normalize relative tests path to res://
            apath = 'res://' + apath.replace('\\', '/').lstrip('/')
        cmd += ['-a', apath]
    invocation_started_ns = time.time_ns()
    try:
        rc, out = run_cmd_failfast(cmd, cwd=proj, timeout=args.timeout_sec*1000, env=process_env, godot_user_data_dir=godot_user_data_dir)
    finally:
        _cleanup_godot_processes(args.godot_bin)
    console_path = os.path.join(out_dir, 'gdunit-console.txt')
    with open(console_path, 'w', encoding='utf-8') as f:
        f.write(out)

    # Generate HTML log frame only after a clean GdUnit process exit. When the
    # runner fail-fast kills a debugger break, starting Godot again can recreate
    # the same log storm.
    copy_log_rc = None
    if rc == 0:
        copy_log_rc, _out2 = run_cmd([args.godot_bin, '--headless', *godot_user_data_args, '--path', proj, '--quiet', '-s', 'res://addons/gdUnit4/bin/GdUnitCopyLog.gd'], cwd=proj, env=process_env, log_root=root)

    # Archive reports
    reports_dir = os.path.join(proj, 'reports')
    dest = args.report_dir if args.report_dir else os.path.join(out_dir, 'gdunit-reports')
    # Always create a destination folder with at least the console log and a summary
    if os.path.isdir(dest):
        shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest, exist_ok=True)
    # Copy console log for diagnosis
    try:
        shutil.copy2(console_path, os.path.join(dest, 'gdunit-console.txt'))
    except Exception:
        pass
    report_copy_failures = []
    # Copy reports if they exist
    if os.path.isdir(reports_dir):
        for name in os.listdir(reports_dir):
            src = os.path.join(reports_dir, name)
            dst = os.path.join(dest, name)
            if os.path.isdir(src):
                report_copy_failures.extend(_copy_reports_best_effort(src, dst))
            else:
                try:
                    shutil.copy2(src, dst)
                except OSError as ex:
                    report_copy_failures.append((src, dst, str(ex)))

    parsed = {}
    latest_results = _find_latest_results_xml(reports_dir, not_before_ns=invocation_started_ns)
    if latest_results:
        parsed = _parse_results_xml(latest_results)

    strict_exit = (os.environ.get("GDUNIT_STRICT_EXIT_CODE") or "0").strip() == "1"
    normalized_rc = _result_exit_code(rc, parsed, strict=strict_exit)

    # Write a small summary json for CI
    summary = {
        'rc': rc,
        'normalized_rc': normalized_rc,
        'strict_exit_code': strict_exit,
        'dotnet_bin': dotnet_bin,
        'project': proj,
        'godot_user_data_args': godot_user_data_args,
        'added': args.add,
        'timeout_sec': args.timeout_sec,
        'results': parsed,
        'copy_log_rc': copy_log_rc,
    }
    if report_copy_failures:
        summary['report_copy_failures'] = report_copy_failures
    if prewarm_rc is not None:
        summary['prewarm_rc'] = prewarm_rc
        if prewarm_note:
            summary['prewarm_note'] = prewarm_note
        try:
            summary['prewarm_attempts'] = prewarm_attempts
        except NameError:
            pass
    try:
        with open(os.path.join(dest, 'run-summary.json'), 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False)
    except Exception:
        pass
    print(f'GDUNIT_DONE rc={rc} out={out_dir}')
    return 0 if normalized_rc == 0 else normalized_rc


if __name__ == '__main__':
    raise SystemExit(main())
