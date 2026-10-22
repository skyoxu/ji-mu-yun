"""ADR-0041/ADR-0062: explicit offline installation, never workflow preflight."""
import json
from pathlib import Path
import shutil
import uuid

from . import (NativeError, RECEIPT, SUPPORTED, contained, digest, load_lock,
               verify, write_config)


def install(root, source, replace=False):
    root, source = Path(root).absolute(), Path(source).absolute()
    lock = load_lock()
    try:
        package = json.loads(contained(source, "package.json").read_text(encoding="utf-8"))
        if package.get("name") != "bmad-method" or package.get("version") != SUPPORTED:
            raise NativeError("NATIVE_SOURCE_MISMATCH")
        copies = {}
        for relative, sha in {**lock["files"], **lock["runtime"]}.items():
            if relative.startswith(".agents/"):
                name = relative.split("/")[2]
                origin = lock["trees"][name]["source"] + "/" + "/".join(relative.split("/")[3:])
            else:
                origin = "src/scripts/" + Path(relative).name
            path = contained(source, origin)
            if not path.is_file() or digest(path) != sha:
                raise NativeError("NATIVE_SOURCE_MISMATCH")
            copies[relative] = path
        for name, info in lock["trees"].items():
            tree = contained(source, info["source"])
            actual = {".agents/skills/" + name + "/" + p.relative_to(tree).as_posix()
                      for p in tree.rglob("*") if p.is_file()}
            if actual != {p for p in lock["files"] if p.startswith(".agents/skills/" + name + "/")}:
                raise NativeError("NATIVE_SOURCE_MISMATCH")
    except (OSError, json.JSONDecodeError, KeyError):
        raise NativeError("NATIVE_SOURCE_MISMATCH") from None

    # A general installer manifest must not silently disagree with this scoped install.
    manifest = contained(root, "_bmad/_config/manifest.yaml")
    if manifest.exists():
        from . import installed_version
        if installed_version(root) != SUPPORTED:
            raise NativeError("NATIVE_VERSION_CONFLICT")
    targets = [".agents/skills/bmad-spec", ".agents/skills/bmad-architecture",
               "_bmad/scripts", RECEIPT]
    existing = [relative for relative in targets if contained(root, relative).exists()]
    if existing and not replace:
        raise NativeError("NATIVE_INSTALL_CONFLICT")
    # Validate every target before any move. No business artifacts are installed.
    for relative in [*copies, "_bmad/config.toml"]:
        contained(root, relative)
    backup = None
    if existing:
        backup = contained(root, "logs/bmad-native-install/" + uuid.uuid4().hex)
        for relative in existing:
            saved = contained(backup, relative)
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(contained(root, relative)), str(saved))
    for relative, path in copies.items():
        target = contained(root, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    contained(root, RECEIPT).write_text(json.dumps({
        "version": SUPPORTED, "commit": lock["commit"], "source": lock["source"],
        "scope": list(lock["trees"]), "installed_from": str(source),
    }, indent=2) + "\n", encoding="utf-8")
    if not contained(root, "_bmad/config.toml").exists():
        write_config(root)
    verify(root)
    return {"ok": True, "version": SUPPORTED, "source_commit": lock["commit"],
            "backup": str(backup) if backup else None, "authorizes": []}
