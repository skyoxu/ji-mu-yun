#!/usr/bin/env python3
"""Top-level router for the prototype 7-day playable Godot workflow."""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

PLACEHOLDER_NEXT_STEPS = {
    "Proceed to the next prototype workflow confirmation step.",
    "Stay in prototype lane until explicitly promoted later.",
}


def configure_stdio_utf8() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except ValueError:
                continue


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def baseline_repo_root() -> Path:
    configured = str(os.environ.get("PHASEA_REPOSITORY_ROOT") or "").strip()
    if configured:
        candidate = Path(configured)
        if candidate.is_absolute() and path_exists(candidate):
            return candidate
    return repo_root()


def today_str() -> str:
    return dt.date.today().isoformat()


def to_windows_extended_path(path: Path) -> str:
    raw = str(path)
    if os.name != "nt":
        return raw
    if raw.startswith("\\\\?\\"):
        return raw
    if raw.startswith("\\\\"):
        return "\\\\?\\UNC\\" + raw[2:]
    return "\\\\?\\" + raw


def path_exists(path: Path) -> bool:
    try:
        return os.path.exists(to_windows_extended_path(path.resolve()))
    except OSError:
        return False


def ensure_dir(path: Path) -> None:
    os.makedirs(to_windows_extended_path(path.resolve()), exist_ok=True)


def write_text(path: Path, content: str) -> None:
    ensure_dir(path.parent)
    with open(to_windows_extended_path(path.resolve()), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def read_text(path: Path, *, errors: str = "strict") -> str:
    with open(to_windows_extended_path(path.resolve()), "r", encoding="utf-8", errors=errors) as handle:
        return handle.read()


def write_json(path: Path, payload: object) -> None:
    ensure_dir(path.parent)
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def sanitize_slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", str(value or "").strip())
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-_")
    return cleaned or "prototype"


def section_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", str(value or "").strip().lower())
    cleaned = re.sub(r"_{2,}", "_", cleaned).strip("_")
    return cleaned or "section"


_LIST_FIELD_ALIASES: dict[str, list[str]] = {
    "status": ["status", "状态"],
    "owner": ["owner", "负责人"],
    "date": ["date", "日期"],
    "related_formal_task_ids": ["related formal task ids", "关联正式任务 id"],
    "game_name": ["game name", "游戏名称"],
    "game_type": ["game type", "游戏类型"],
    "hypothesis": ["hypothesis", "假设"],
    "core_player_fantasy": ["core player fantasy", "核心玩家幻想"],
    "minimum_playable_loop": ["minimum playable loop", "最小可玩循环"],
    "game_feature": ["game feature", "游戏特色"],
    "core_gameplay_loop": ["core gameplay loop", "核心游戏循环"],
    "win_fail_conditions": ["win / fail conditions", "win fail conditions", "victory / failure conditions", "胜利/失败条件", "胜利 / 失败条件"],
    "success_criteria": ["success criteria", "成功标准"],
    "promote_signals": ["promote signals", "进入 promote 的信号"],
    "archive_signals": ["archive signals", "进入 archive 的信号"],
    "discard_signals": ["discard signals", "进入 discard 的信号"],
    "decision": ["decision", "结论"],
    "next_step": ["next step", "下一步"],
}


def _normalize_heading(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().strip(":：")).lower()


def _normalize_evidence_list(values: list[Any] | None) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    heading_markers = {
        "code paths",
        "代码路径",
        "logs / media / notes",
        "日志 / 媒体 / 备注",
    }
    for raw in list(values or []):
        text = str(raw or "").strip()
        if not text:
            continue
        lowered = _normalize_heading(text)
        if lowered in heading_markers:
            continue
        if text.upper() == "TBD":
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
    return cleaned or ["TBD"]


def parse_template_content(content: str) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    lines = content.splitlines()
    current_section: str | None = None
    scope_mode: str | None = None
    evidence_mode: str | None = None
    prototype_type_kit_subsection: str | None = None
    section_values: dict[str, list[str]] = {}
    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip().lstrip("\ufeff")
        if not stripped:
            continue
        if stripped.startswith("# "):
            title = stripped[2:].strip()
            if title.startswith("Prototype:"):
                payload["slug"] = sanitize_slug(title.split(":", 1)[1].strip())
            elif title.startswith("原型："):
                payload["slug"] = sanitize_slug(title.split("：", 1)[1].strip())
            continue
        if stripped.startswith("- "):
            entry = stripped[2:].strip()
            if current_section == "game_type_specifics":
                if ":" in entry or "：" in entry:
                    key, value = re.split(r"[:：]", entry, maxsplit=1)
                    normalized_key = _normalize_heading(key)
                    if normalized_key in {"game type", "游戏类型"}:
                        section_values.setdefault("game_type", []).append(value.strip())
                    elif normalized_key in {"guide path", "game type guide path", "类型模板路径", "游戏类型模板路径"}:
                        section_values.setdefault("game_type_guide_path", []).append(value.strip())
                    else:
                        section_values.setdefault("game_type_specific_lines", []).append(f"{key.strip()}: {value.strip()}")
                continue
            if current_section == "prototype_type_kit":
                if ":" in entry or "：" in entry:
                    key, value = re.split(r"[:：]", entry, maxsplit=1)
                    normalized_key = _normalize_heading(key)
                    if normalized_key in {"game type", "游戏类型"}:
                        section_values.setdefault("prototype_type_kit_game_type", []).append(value.strip())
                    elif normalized_key in {"kit path", "prototype type kit path", "模板路径", "原型类型模板路径"}:
                        section_values.setdefault("prototype_type_kit_path", []).append(value.strip())
                    elif normalized_key in {"manifest path", "template manifest", "manifest"}:
                        section_values.setdefault("prototype_type_kit_manifest_path", []).append(value.strip())
                continue
            if current_section == "scope":
                lowered_entry = _normalize_heading(entry)
                if lowered_entry in {"in", "纳入"}:
                    scope_mode = "in"
                elif lowered_entry in {"out", "排除"}:
                    scope_mode = "out"
                elif scope_mode == "in":
                    section_values.setdefault("scope_in", []).append(entry)
                elif scope_mode == "out":
                    section_values.setdefault("scope_out", []).append(entry)
                continue
            if current_section == "evidence":
                lowered_entry = _normalize_heading(entry)
                if lowered_entry in {"code paths", "代码路径"}:
                    evidence_mode = "code"
                elif lowered_entry in {"logs / media / notes", "日志 / 媒体 / 备注"}:
                    evidence_mode = "notes"
                elif evidence_mode:
                    section_values.setdefault("evidence", []).append(entry)
                continue
            matched_meta = False
            for canonical, aliases in _LIST_FIELD_ALIASES.items():
                for alias in aliases:
                    if entry.lower().startswith(alias.lower() + ":") or entry.lower().startswith(alias.lower() + "："):
                        _, value = re.split(r"[:：]", entry, maxsplit=1)
                        section_values.setdefault(canonical, []).append(value.strip())
                        matched_meta = True
                        break
                if matched_meta:
                    break
            if matched_meta and current_section is None:
                continue
            if current_section:
                section_values.setdefault(current_section, []).append(entry)
            continue
        if stripped.startswith("### ") and current_section == "prototype_type_kit":
            heading = _normalize_heading(stripped[4:])
            if heading in {"gameplay flow / gdd route", "gameplay flow", "gdd route", "玩法动线", "玩法动线"}:
                prototype_type_kit_subsection = "gameplay_flow"
            elif heading in {"prototype scene ui", "scene ui", "原型场景 ui", "场景 ui"}:
                prototype_type_kit_subsection = "prototype_scene_ui"
            else:
                prototype_type_kit_subsection = None
            continue
        if stripped.startswith("## "):
            heading = _normalize_heading(stripped[3:])
            current_section = None
            scope_mode = None
            evidence_mode = None
            prototype_type_kit_subsection = None
            for canonical, aliases in _LIST_FIELD_ALIASES.items():
                if heading in [_normalize_heading(item) for item in aliases]:
                    current_section = canonical
                    break
            if heading == "范围" or heading == "scope":
                current_section = "scope"
            elif heading == "证据" or heading == "evidence":
                current_section = "evidence"
            elif heading in {"game type specifics", "游戏类型细节", "游戏类型特定设计"}:
                current_section = "game_type_specifics"
            elif heading in {"prototype type kit", "原型类型模板", "prototype 类型模板"}:
                current_section = "prototype_type_kit"
            continue
        if current_section == "scope":
            lowered = _normalize_heading(stripped)
            if lowered in {"in", "纳入"}:
                scope_mode = "in"
            elif lowered in {"out", "排除"}:
                scope_mode = "out"
            continue
        if current_section == "evidence":
            lowered = _normalize_heading(stripped)
            if lowered in {"code paths", "代码路径"}:
                evidence_mode = "code"
            elif lowered in {"logs / media / notes", "日志 / 媒体 / 备注"}:
                evidence_mode = "notes"
            elif evidence_mode:
                section_values.setdefault("evidence", []).append(stripped)
            continue
    for key, values in section_values.items():
        if key == "slug":
            payload["slug"] = sanitize_slug(values[0]) if values else ""
        elif key in {"status", "owner", "date", "decision", "next_step"}:
            payload[key] = values[0] if values else ""
        elif key == "game_type_specific_lines":
            sections = []
            for item in values:
                title, answer = item.split(":", 1)
                title = title.strip()
                sections.append({"id": section_id(title), "title": title, "answer": answer.strip()})
            payload["game_type_specifics"] = {"selected_sections": sections}
        elif key == "prototype_type_kit_game_type":
            payload.setdefault("prototype_type_kit", {})
            payload["prototype_type_kit"]["game_type"] = values[0] if values else ""
        elif key == "prototype_type_kit_path":
            payload.setdefault("prototype_type_kit", {})
            payload["prototype_type_kit"]["kit_path"] = values[0] if values else ""
        elif key == "prototype_type_kit_manifest_path":
            payload.setdefault("prototype_type_kit", {})
            payload["prototype_type_kit"]["manifest_path"] = values[0] if values else ""
        elif key in {"prototype_type_kit_gameplay_flow", "prototype_type_kit_prototype_scene_ui"}:
            payload.setdefault("prototype_type_kit", {})
            target_key = key.replace("prototype_type_kit_", "")
            payload["prototype_type_kit"][target_key] = [
                {"id": section_id(_split_question_answer_for_router(item)[0]), "question": _split_question_answer_for_router(item)[0], "answer": _split_question_answer_for_router(item)[1]}
                for item in values
                if str(item).strip()
            ]
        else:
            payload[key] = [item for item in values if item]
    return payload


def normalize_prototype_payload(raw: dict[str, Any], *, today: str | None = None) -> dict[str, Any]:
    current_day = today or today_str()
    normalized: dict[str, Any] = {
        "slug": sanitize_slug(raw.get("slug") or "") if str(raw.get("slug") or "").strip() else "",
        "status": str(raw.get("status") or "active").strip() or "active",
        "owner": str(raw.get("owner") or "operator").strip() or "operator",
        "date": str(raw.get("date") or current_day).strip() or current_day,
        "related_formal_task_ids": list(raw.get("related_formal_task_ids") or ["none yet"]),
        "game_name": _first(raw.get("game_name")) or "",
        "game_type": _first(raw.get("game_type")) or "",
        "hypothesis": _first(raw.get("hypothesis")) or "",
        "core_player_fantasy": _first(raw.get("core_player_fantasy")) or "",
        "minimum_playable_loop": _first(raw.get("minimum_playable_loop")) or "",
        "game_feature": _first(raw.get("game_feature")) or "",
        "core_gameplay_loop": _first(raw.get("core_gameplay_loop")) or "",
        "win_fail_conditions": _first(raw.get("win_fail_conditions")) or "",
        "scope_in": list(raw.get("scope_in") or ["TBD"]),
        "scope_out": list(raw.get("scope_out") or ["TBD"]),
        "success_criteria": list(raw.get("success_criteria") or []),
        "promote_signals": list(raw.get("promote_signals") or ["TBD"]),
        "archive_signals": list(raw.get("archive_signals") or ["TBD"]),
        "discard_signals": list(raw.get("discard_signals") or ["TBD"]),
        "evidence": _normalize_evidence_list(list(raw.get("evidence") or [])),
        "decision": str(raw.get("decision") or "pending").strip() or "pending",
        "next_step": str(raw.get("next_step") or "Proceed to the next prototype workflow confirmation step.").strip()
        or "Proceed to the next prototype workflow confirmation step.",
    }
    if raw.get("game_type_guide_path"):
        normalized["game_type_guide_path"] = _first(raw.get("game_type_guide_path"))
    if raw.get("game_type_guide_content"):
        normalized["game_type_guide_content"] = str(raw.get("game_type_guide_content") or "")
    if isinstance(raw.get("game_type_specifics"), dict):
        normalized["game_type_specifics"] = dict(raw.get("game_type_specifics") or {})
    if isinstance(raw.get("prototype_type_kit"), dict):
        normalized["prototype_type_kit"] = dict(raw.get("prototype_type_kit") or {})
    if isinstance(raw.get("implementation_skill"), dict):
        normalized["implementation_skill"] = dict(raw.get("implementation_skill") or {})
    if normalized.get("game_type_guide_content") or normalized.get("game_type_specifics"):
        normalized["game_type_specifics"] = normalize_game_type_specifics(normalized)
    if not str(normalized.get("game_type") or "").strip():
        inferred = _infer_game_type_from_raw_payload(raw)
        if inferred:
            normalized["game_type"] = inferred
    return normalized


def _infer_game_type_from_raw_payload(raw: dict[str, Any]) -> str:
    haystacks: list[str] = []
    for value in raw.values():
        if isinstance(value, str):
            haystacks.append(value)
        elif isinstance(value, list):
            haystacks.extend(str(item) for item in value if str(item).strip())
        elif isinstance(value, dict):
            haystacks.append(json.dumps(value, ensure_ascii=False))
    joined = "\n".join(haystacks).lower()
    if any(token in joined for token in ("rpg", "jrpg", "角色扮演")):
        return "rpg"
    return ""


def enrich_payload_with_prototype_manifest(*, root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    updated = dict(payload)
    type_kit = dict(updated.get("prototype_type_kit") or {}) if isinstance(updated.get("prototype_type_kit"), dict) else {}
    manifest_path = str(type_kit.get("manifest_path") or "").strip()
    if not manifest_path and sanitize_slug(str(updated.get("game_type") or "")) == "rpg":
        default_manifest = root / "docs" / "prototype-type-kits" / "default-rpg-template.manifest.json"
        if default_manifest.exists():
            manifest_path = str(default_manifest.relative_to(root)).replace("\\", "/")
    if not manifest_path:
        if type_kit:
            updated["prototype_type_kit"] = type_kit
        return updated
    resolved = (root / manifest_path).resolve()
    if not resolved.exists():
        type_kit["manifest_path"] = manifest_path
        updated["prototype_type_kit"] = type_kit
        return updated
    try:
        manifest_payload = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        manifest_payload = {}
    type_kit["manifest_path"] = manifest_path
    if isinstance(manifest_payload, dict):
        type_kit["manifest"] = manifest_payload
    updated["prototype_type_kit"] = type_kit
    return updated


def parse_prototype_type_kit(content: str, *, game_type: str, path: str) -> dict[str, Any]:
    gameplay_questions: list[dict[str, str]] = []
    ui_questions: list[dict[str, str]] = []
    default_route: list[str] = []
    default_ui: list[str] = []
    current_section = ""
    current_round = ""
    for raw_line in str(content or "").splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("## "):
            heading = _normalize_heading(stripped[3:])
            current_section = heading
            current_round = ""
            continue
        if stripped.startswith("### "):
            heading = _normalize_heading(stripped[4:])
            if "round 1" in heading or "第一轮" in heading:
                current_round = "gameplay_flow"
            elif "round 2" in heading or "第二轮" in heading:
                current_round = "prototype_scene_ui"
            else:
                current_round = ""
            continue
        numbered = re.match(r"^\d+[\.?]\s*(.+)$", stripped)
        if numbered and current_round in {"gameplay_flow", "prototype_scene_ui"}:
            question = numbered.group(1).strip()
            if current_round == "gameplay_flow":
                item = {"id": f"gameplay_flow_{len(gameplay_questions) + 1}", "question": question, "answer": ""}
                gameplay_questions.append(item)
            else:
                item = {"id": f"prototype_scene_ui_{len(ui_questions) + 1}", "question": question, "answer": ""}
                ui_questions.append(item)
            continue
        if stripped.startswith("- "):
            bullet = stripped[2:].strip()
            if current_round in {"gameplay_flow", "prototype_scene_ui"}:
                if current_round == "gameplay_flow":
                    item = {"id": f"gameplay_flow_{len(gameplay_questions) + 1}", "question": bullet, "answer": ""}
                    gameplay_questions.append(item)
                else:
                    item = {"id": f"prototype_scene_ui_{len(ui_questions) + 1}", "question": bullet, "answer": ""}
                    ui_questions.append(item)
                continue
            if current_section in {"gameplay flow / gdd route", "gameplay flow", "玩法动线"}:
                default_route.append(bullet)
            elif current_section in {"prototype scene ui", "scene ui", "原型场景 ui"}:
                default_ui.append(bullet)
    return {
        "game_type": sanitize_slug(game_type),
        "kit_path": path,
        "gameplay_flow": gameplay_questions,
        "prototype_scene_ui": ui_questions,
        "default_route": default_route[:12],
        "default_ui": default_ui[:16],
    }


def _merge_type_kit_items(defaults: list[dict[str, str]], existing: list[Any]) -> list[dict[str, str]]:
    by_id: dict[str, dict[str, str]] = {}
    for item in existing:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question") or item.get("title") or item.get("id") or "").strip()
        item_id = str(item.get("id") or section_id(question)).strip()
        if item_id:
            by_id[item_id] = {
                "id": item_id,
                "question": question or item_id,
                "answer": str(item.get("answer") or "").strip(),
            }
    merged: list[dict[str, str]] = []
    for item in defaults:
        item_id = str(item.get("id") or "").strip()
        prior = by_id.pop(item_id, {})
        merged.append(
            {
                "id": item_id,
                "question": str(item.get("question") or prior.get("question") or item_id),
                "answer": str(prior.get("answer") or item.get("answer") or "").strip(),
            }
        )
    return merged


def enrich_payload_with_prototype_type_kit(*, root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    updated = dict(payload)
    game_type = sanitize_slug(str(updated.get("game_type") or ""))
    existing = updated.get("prototype_type_kit") if isinstance(updated.get("prototype_type_kit"), dict) else {}
    if not game_type:
        game_type = sanitize_slug(str(existing.get("game_type") or ""))
    if not game_type:
        return updated
    kit_path = str(existing.get("kit_path") or f"docs/prototype-type-kits/{game_type}.md").strip()
    kit_file = (root / kit_path).resolve()
    type_kit = dict(existing)
    type_kit["game_type"] = game_type
    type_kit["kit_path"] = kit_path
    if kit_file.exists():
        parsed = parse_prototype_type_kit(kit_file.read_text(encoding="utf-8"), game_type=game_type, path=kit_path)
        type_kit["gameplay_flow"] = _merge_type_kit_items(list(parsed.get("gameplay_flow") or []), list(existing.get("gameplay_flow") or []))
        type_kit["prototype_scene_ui"] = _merge_type_kit_items(list(parsed.get("prototype_scene_ui") or []), list(existing.get("prototype_scene_ui") or []))
        type_kit["default_route"] = list(parsed.get("default_route") or [])
        type_kit["default_ui"] = list(parsed.get("default_ui") or [])
    type_kit = _fill_legacy_prototype_type_kit_answers(type_kit)
    updated["prototype_type_kit"] = type_kit
    return updated


def _fill_legacy_prototype_type_kit_answers(type_kit: dict[str, Any]) -> dict[str, Any]:
    updated = dict(type_kit)

    gameplay_items = [dict(item) for item in list(updated.get("gameplay_flow") or []) if isinstance(item, dict)]
    if gameplay_items and not any(str(item.get("answer") or "").strip() for item in gameplay_items):
        gameplay_defaults = [
            "Support both map collision encounter and light random encounter hints, with map collision as the main visible trigger.",
            "Use a simple turn-based combat command flow with at least Attack as the primary action.",
            "After victory, return to the map so the player can immediately feel the loop is connected.",
            "After failure, allow retry so the prototype can be validated quickly without restarting the whole project.",
            "Skip post-battle roguelike reward for the minimum version unless later iteration specifically asks for it.",
        ]
        for item, answer in zip(gameplay_items, gameplay_defaults):
            item["answer"] = answer
        updated["gameplay_flow"] = gameplay_items

    ui_items = [dict(item) for item in list(updated.get("prototype_scene_ui") or []) if isinstance(item, dict)]
    if ui_items and not any(str(item.get("answer") or "").strip() for item in ui_items):
        ui_defaults = [
            "Battle scene should show player HP, enemy HP, one Attack action, and a short battle log.",
            "Map scene should show player HP, movement hint, and a clear encounter or objective hint.",
            "Failure should offer Retry directly.",
            "Result UI should provide Continue or Back to Map, plus Retry on failure.",
            "Keep a small debug text area visible if it helps verify encounter and battle state quickly.",
        ]
        for item, answer in zip(ui_items, ui_defaults):
            item["answer"] = answer
        updated["prototype_scene_ui"] = ui_items

    return updated


def missing_prototype_type_kit_question_names(payload: dict[str, Any]) -> list[str]:
    type_kit = payload.get("prototype_type_kit") if isinstance(payload.get("prototype_type_kit"), dict) else {}
    missing: list[str] = []
    for section_name in ("gameplay_flow", "prototype_scene_ui"):
        for item in list(type_kit.get(section_name) or []):
            if isinstance(item, dict) and str(item.get("question") or "").strip() and not str(item.get("answer") or "").strip():
                missing.append(f"prototype_type_kit.{section_name}.{item.get('id')}")
    return missing


def prototype_spec_path(*, root: Path, slug: str) -> Path:
    return root / "docs" / "prototypes" / f"{sanitize_slug(slug)}.prototype.json"


def build_prototype_spec_sidecar(*, root: Path, payload: dict[str, Any], prototype_file: str = "", tdd: dict[str, Any] | None = None) -> dict[str, Any]:
    type_kit = payload.get("prototype_type_kit") if isinstance(payload.get("prototype_type_kit"), dict) else {}
    specifics = payload.get("game_type_specifics") if isinstance(payload.get("game_type_specifics"), dict) else {}
    implementation_skill = payload.get("implementation_skill") if isinstance(payload.get("implementation_skill"), dict) else {}
    spec_path = prototype_spec_path(root=root, slug=str(payload.get("slug") or "prototype"))
    existing_tdd: dict[str, Any] = {"red": "pending", "green": "pending", "refactor": "pending"}
    if spec_path.exists():
        try:
            existing_payload = json.loads(spec_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing_payload = {}
        if isinstance(existing_payload, dict) and isinstance(existing_payload.get("tdd"), dict):
            existing_tdd.update(dict(existing_payload.get("tdd") or {}))
    if tdd:
        existing_tdd.update(tdd)
    return {
        "schema_version": 1,
        "kind": "prototype-spec",
        "slug": str(payload.get("slug") or ""),
        "status": str(payload.get("status") or "active"),
        "date": str(payload.get("date") or today_str()),
        "game_name": str(payload.get("game_name") or ""),
        "game_type": str(payload.get("game_type") or type_kit.get("game_type") or specifics.get("game_type") or ""),
        "game_type_source": str(payload.get("game_type_source") or ""),
        "game_type_guide": str(specifics.get("guide_path") or payload.get("game_type_guide_path") or ""),
        "game_type_specifics": specifics,
        "prototype_file": prototype_file,
        "prototype_spec": str(spec_path.relative_to(root)).replace("\\", "/") if spec_path.is_relative_to(root) else str(spec_path),
        "prototype_type_kit": type_kit,
        "implementation_skill": implementation_skill,
        "prototype_core": {
            "hypothesis": str(payload.get("hypothesis") or ""),
            "core_player_fantasy": str(payload.get("core_player_fantasy") or ""),
            "minimum_playable_loop": str(payload.get("minimum_playable_loop") or ""),
            "game_feature": str(payload.get("game_feature") or ""),
            "core_gameplay_loop": str(payload.get("core_gameplay_loop") or ""),
            "win_fail_conditions": str(payload.get("win_fail_conditions") or ""),
            "success_criteria": list(payload.get("success_criteria") or []),
        },
        "tdd": existing_tdd,
    }


def write_prototype_spec_sidecar(*, root: Path, payload: dict[str, Any], prototype_file: str = "", tdd: dict[str, Any] | None = None) -> str:
    path = prototype_spec_path(root=root, slug=str(payload.get("slug") or "prototype"))
    spec = build_prototype_spec_sidecar(root=root, payload=payload, prototype_file=prototype_file, tdd=tdd)
    write_json(path, spec)
    return str(path.relative_to(root)).replace("\\", "/") if path.is_relative_to(root) else str(path)


def _first(value: Any) -> str:
    if isinstance(value, list):
        return str(value[0]).strip() if value else ""
    return str(value or "").strip()


def required_field_names(payload: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    required_scalars = [
        "slug",
        "hypothesis",
        "core_player_fantasy",
        "minimum_playable_loop",
        "game_feature",
        "core_gameplay_loop",
        "win_fail_conditions",
    ]
    for key in required_scalars:
        if not str(payload.get(key) or "").strip():
            missing.append(key)
    if not payload.get("success_criteria"):
        missing.append("success_criteria")
    return missing


def parse_game_type_guide(content: str, *, game_type: str, path: str) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    body: list[str] = []

    def flush() -> None:
        nonlocal current, body
        if current is None:
            return
        text = "\n".join(body).strip()
        placeholders = re.findall(r"\{\{\s*([A-Za-z0-9_ -]+)\s*\}\}", text)
        bullets = [line.strip()[2:].strip() for line in text.splitlines() if line.strip().startswith("- ")]
        prompt_source = "; ".join(bullets[:4]) or current["title"]
        sections.append(
            {
                "id": section_id(str(current["title"])),
                "title": str(current["title"]),
                "placeholders": [section_id(item) for item in placeholders],
                "prompt": prompt_source,
                "body": text,
                "optional": "optional" in text.lower(),
                "narrative": "narrative" in text.lower(),
            }
        )
        current = None
        body = []

    for line in str(content or "").splitlines():
        if line.startswith("### "):
            flush()
            current = {"title": line[4:].strip()}
            body = []
        elif current is not None:
            body.append(line)
    flush()
    return {
        "game_type": sanitize_slug(game_type),
        "guide_path": str(path or ""),
        "sections": sections,
        "needs_narrative": any(bool(item.get("narrative")) for item in sections),
    }


def select_prototype_relevant_sections(parsed: dict[str, Any], *, limit: int = 3) -> list[dict[str, Any]]:
    priority_terms = (
        "core",
        "mechanic",
        "loop",
        "progression",
        "level",
        "structure",
        "control",
        "combat",
        "system",
        "objective",
    )
    scored: list[tuple[int, int, dict[str, Any]]] = []
    for index, section in enumerate(list(parsed.get("sections") or [])):
        if not isinstance(section, dict):
            continue
        haystack = f"{section.get('id', '')} {section.get('title', '')} {section.get('prompt', '')}".lower()
        score = sum(3 for term in priority_terms if term in haystack)
        if "replay" in haystack or "monet" in haystack or "meta" in haystack:
            score -= 2
        scored.append((score, -index, section))
    selected = [item[2] for item in sorted(scored, reverse=True)[: max(1, int(limit))]]
    return sorted(selected, key=lambda section: [item.get("id") for item in list(parsed.get("sections") or [])].index(section.get("id")))


def _guide_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    content = str(payload.get("game_type_guide_content") or "")
    if not content:
        return {}
    return parse_game_type_guide(
        content,
        game_type=str(payload.get("game_type") or ""),
        path=str(payload.get("game_type_guide_path") or ""),
    )


def normalize_game_type_specifics(payload: dict[str, Any], *, guide: dict[str, Any] | None = None) -> dict[str, Any]:
    existing = payload.get("game_type_specifics") if isinstance(payload.get("game_type_specifics"), dict) else {}
    parsed = guide or _guide_from_payload(payload)
    selected = select_prototype_relevant_sections(parsed, limit=3) if parsed else list(existing.get("selected_sections") or [])
    existing_by_id = {
        str(item.get("id") or "").strip(): item
        for item in list(existing.get("selected_sections") or [])
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    }
    normalized_sections: list[dict[str, Any]] = []
    for section in selected:
        section_id_value = str(section.get("id") or section_id(str(section.get("title") or "")))
        prior = existing_by_id.get(section_id_value) or {}
        normalized_sections.append(
            {
                "id": section_id_value,
                "title": str(section.get("title") or prior.get("title") or section_id_value),
                "prompt": str(section.get("prompt") or prior.get("prompt") or ""),
                "answer": str(prior.get("answer") or section.get("answer") or "").strip(),
            }
        )
    return {
        "game_type": sanitize_slug(str(payload.get("game_type") or existing.get("game_type") or (parsed or {}).get("game_type") or "")),
        "guide_path": str(payload.get("game_type_guide_path") or existing.get("guide_path") or (parsed or {}).get("guide_path") or ""),
        "selected_sections": normalized_sections,
        "needs_narrative": bool(existing.get("needs_narrative") or (parsed or {}).get("needs_narrative")),
    }


def enrich_legacy_game_type_specific_answers(payload: dict[str, Any]) -> dict[str, Any]:
    updated = dict(payload)
    game_type = sanitize_slug(str(updated.get("game_type") or ""))
    specifics = updated.get("game_type_specifics") if isinstance(updated.get("game_type_specifics"), dict) else {}
    sections = [dict(item) for item in list(specifics.get("selected_sections") or []) if isinstance(item, dict)]
    if game_type != "rpg" or not sections:
        return updated
    if any(str(item.get("answer") or "").strip() for item in sections):
        return updated

    defaults = {
        "character_system": "Single playable hero with only core combat stats for the prototype: HP and attack. No class split, no leveling tree, no long-term progression.",
        "world_and_exploration": "One compact map scene for short exploration with movement, encounter trigger, and clear return flow after battle.",
        "combat_system": "Small-scale RPG combat loop with direct damage exchange, visible HP changes, and explicit win or fail resolution.",
    }
    changed = False
    for section in sections:
        section_id_value = str(section.get("id") or "").strip()
        if section_id_value in defaults and not str(section.get("answer") or "").strip():
            section["answer"] = defaults[section_id_value]
            changed = True
    if not changed:
        return updated

    specifics["selected_sections"] = sections
    updated["game_type_specifics"] = specifics
    return updated


def enrich_payload_with_game_type_guide(*, root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    updated = dict(payload)
    guide = load_game_type_guide(root=root, payload=updated)
    if guide.get("path"):
        updated["game_type_guide_path"] = guide["path"]
        updated["game_type_guide_content"] = guide["content"]
        parsed = parse_game_type_guide(guide["content"], game_type=guide["game_type"], path=guide["path"])
        updated["game_type_specifics"] = normalize_game_type_specifics(updated, guide=parsed)
    elif updated.get("game_type_specifics"):
        updated["game_type_specifics"] = normalize_game_type_specifics(updated)
    updated = enrich_legacy_game_type_specific_answers(updated)
    return updated


def _repo_relative_posix(root: Path, path: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def _slug_to_pascal(slug: str) -> str:
    parts = [part for part in re.split(r"[-_]+", sanitize_slug(slug)) if part]
    return "".join(part[:1].upper() + part[1:] for part in parts) or "Prototype"


def _resolve_runtime_default_scene(*, root: Path, payload: dict[str, Any]) -> str:
    slug = str(payload.get("slug") or "prototype")
    candidate = _resolve_default_scene(
        {
            **payload,
            "prototype_type_kit": {
                **(payload.get("prototype_type_kit") if isinstance(payload.get("prototype_type_kit"), dict) else {}),
                "paths": {
                    **(((payload.get("prototype_type_kit") or {}).get("paths")) if isinstance((payload.get("prototype_type_kit") or {}).get("paths"), dict) else {}),
                    "default_scene": f"res://Game.Godot/Prototypes/{sanitize_slug(slug)}/{_slug_to_pascal(slug)}Prototype.tscn",
                },
            },
        }
    )
    if candidate.startswith("res://"):
        candidate_file = root / candidate.replace("res://", "").replace("/", os.sep)
        if candidate_file.exists():
            return candidate
    return _resolve_default_scene(payload)


def _prototype_class_name(slug: str) -> str:
    return f"{_slug_to_pascal(slug)}Prototype"


def _prototype_loop_test_filter(slug: str) -> str:
    return f"{_prototype_class_name(slug)}LoopTests"


def _prototype_gdunit_dir(slug: str) -> str:
    return f"tests/Prototype/{_prototype_class_name(slug)}"


def _prototype_dotnet_test_path(slug: str) -> str:
    return f"Game.Core.Tests/Prototypes/{_prototype_class_name(slug)}LoopTests.cs"


def _prototype_godot_test_path(slug: str) -> str:
    return f"Tests.Godot/tests/Prototype/{_prototype_class_name(slug)}/test_{sanitize_slug(slug).replace('-', '_')}_prototype_scene.gd"


def enrich_payload_with_repo_local_skill(*, root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    updated = dict(payload)
    game_type = sanitize_slug(str(updated.get("game_type") or ""))
    if game_type != "rpg":
        updated.pop("implementation_skill", None)
        return updated

    skill_file = root / ".agents" / "skills" / "prototype-rpg-godot-zh" / "SKILL.md"
    if not skill_file.exists():
        updated.pop("implementation_skill", None)
        return updated

    metadata: dict[str, Any] = {
        "name": "prototype-rpg-godot-zh",
        "path": _repo_relative_posix(root, skill_file),
    }
    contract_file = skill_file.parent / "references" / "rpg-prototype-contract.md"
    if contract_file.exists():
        metadata["contract_path"] = _repo_relative_posix(root, contract_file)
    updated["implementation_skill"] = metadata
    return updated


def missing_game_type_specific_question_names(payload: dict[str, Any]) -> list[str]:
    specifics = payload.get("game_type_specifics") if isinstance(payload.get("game_type_specifics"), dict) else {}
    missing = []
    for section in list(specifics.get("selected_sections") or []):
        if isinstance(section, dict) and not str(section.get("answer") or "").strip():
            missing.append(f"game_type_specifics.{section.get('id')}")
    return missing


def required_questions_for_missing_payload(payload: dict[str, Any]) -> list[dict[str, str]]:
    normalized = normalize_prototype_payload(payload)
    prompts = {
        "slug": "原型标识 slug",
        "hypothesis": "原型假设",
        "core_player_fantasy": "核心玩家幻想",
        "minimum_playable_loop": "最小可玩循环",
        "game_feature": "游戏特色 / 玩法独特性",
        "core_gameplay_loop": "核心游戏循环",
        "win_fail_conditions": "胜利 / 失败条件",
        "success_criteria": "成功标准（多个用逗号分隔）",
    }
    questions = [{"id": key, "prompt": prompts[key]} for key in required_field_names(normalized)]
    if not questions:
        specifics = normalized.get("game_type_specifics") if isinstance(normalized.get("game_type_specifics"), dict) else {}
        by_id = {
            str(section.get("id") or ""): section
            for section in list(specifics.get("selected_sections") or [])
            if isinstance(section, dict)
        }
        for key in missing_game_type_specific_question_names(normalized):
            section = by_id.get(key.split(".", 1)[1]) or {}
            title = str(section.get("title") or key)
            prompt = str(section.get("prompt") or "请描述与该原型最相关的游戏类型细节。")
            questions.append({"id": key, "prompt": f"{title}: {prompt}"})
    return questions


def active_state_path(*, repo_root: Path, slug: str) -> Path:
    return repo_root / "logs" / "ci" / "active-prototypes" / f"{sanitize_slug(slug)}.active.json"


def write_active_state(*, repo_root: Path, slug: str, payload: dict[str, Any]) -> Path:
    path = active_state_path(repo_root=repo_root, slug=slug)
    write_json(path, payload)
    return path


def load_game_type_guide(*, root: Path, payload: dict[str, Any]) -> dict[str, str]:
    game_type = sanitize_slug(str(payload.get("game_type") or ""))
    if not game_type:
        return {"game_type": "", "path": "", "content": ""}
    guide = root / "docs" / "game-type-guides" / f"{game_type}.md"
    if not guide.exists():
        return {"game_type": game_type, "path": "", "content": ""}
    return {
        "game_type": game_type,
        "path": str(guide.relative_to(root)).replace("\\", "/"),
        "content": guide.read_text(encoding="utf-8"),
    }


def _score_text(value: Any) -> str:
    if isinstance(value, list):
        text = " ".join(str(item).strip() for item in value if str(item).strip())
        return text.strip()
    return str(value or "").strip()


def _has_meaningful_items(items: list[Any]) -> bool:
    meaningful = [item for item in items if _score_text(item) and _score_text(item).upper() != "TBD"]
    return bool(meaningful)


def build_prototype_intake_score(payload: dict[str, Any]) -> dict[str, Any]:
    hypothesis_text = _score_text(payload.get("hypothesis"))
    fantasy_text = _score_text(payload.get("core_player_fantasy"))
    loop_text = _score_text(payload.get("minimum_playable_loop"))
    next_step_text = _score_text(payload.get("next_step"))
    success_items = [item for item in payload.get("success_criteria") or [] if _score_text(item)]
    scope_in_items = [item for item in payload.get("scope_in") or [] if _score_text(item) and _score_text(item).upper() != "TBD"]
    scope_out_items = [item for item in payload.get("scope_out") or [] if _score_text(item) and _score_text(item).upper() != "TBD"]
    evidence_items = [item for item in payload.get("evidence") or [] if _score_text(item) and _score_text(item).upper() != "TBD"]
    promote_items = [item for item in payload.get("promote_signals") or [] if _score_text(item) and _score_text(item).upper() != "TBD"]
    archive_items = [item for item in payload.get("archive_signals") or [] if _score_text(item) and _score_text(item).upper() != "TBD"]
    discard_items = [item for item in payload.get("discard_signals") or [] if _score_text(item) and _score_text(item).upper() != "TBD"]

    feasibility_score = 0
    if len(hypothesis_text) >= 20 and len(loop_text) >= 40:
        feasibility_score += 8
    elif len(hypothesis_text) >= 10 and len(loop_text) >= 20:
        feasibility_score += 4
    if len(success_items) >= 2:
        feasibility_score += 6
    elif len(success_items) == 1:
        feasibility_score += 3
    if len(scope_in_items) >= 2 and len(scope_out_items) >= 2:
        feasibility_score += 6
    elif len(scope_in_items) >= 1 and len(scope_out_items) >= 1:
        feasibility_score += 3
    if next_step_text and next_step_text != "Proceed to the next prototype workflow confirmation step.":
        feasibility_score += 5 if len(next_step_text) >= 12 else 2
    feasibility_score = min(feasibility_score, 25)

    completeness_score = 0
    if len(hypothesis_text) >= 20:
        completeness_score += 5
    elif hypothesis_text:
        completeness_score += 2
    if len(fantasy_text) >= 30:
        completeness_score += 5
    elif fantasy_text:
        completeness_score += 2
    if len(loop_text) >= 40:
        completeness_score += 5
    elif loop_text:
        completeness_score += 2
    if len(success_items) >= 2:
        completeness_score += 4
    elif len(success_items) == 1:
        completeness_score += 2
    if len(promote_items) >= 1 and len(archive_items) >= 1 and len(discard_items) >= 1:
        completeness_score += 3
    elif len(promote_items) >= 1:
        completeness_score += 1
    if len(evidence_items) >= 1:
        completeness_score += 3
    completeness_score = min(completeness_score, 25)

    dimensions = [
        {
            "id": "prototype_feasibility",
            "label": "Prototype feasibility",
            "score": feasibility_score,
            "max_score": 25,
            "focus": "The file is concrete enough for the top-level prototype router to drive Day 1 to Day 5 with low ambiguity.",
        },
        {
            "id": "content_completeness",
            "label": "Content completeness",
            "score": completeness_score,
            "max_score": 25,
            "focus": "The prototype file contains enough structured information to avoid relying on hidden assumptions.",
        },
    ]
    total_score = sum(int(item["score"]) for item in dimensions)
    recommendation = (
        "ready-for-tdd"
        if total_score >= 36 and feasibility_score >= 18 and completeness_score >= 14
        else "refine-before-tdd"
    )
    return {
        "total_score": total_score,
        "max_score": 50,
        "recommendation": recommendation,
        "dimensions": dimensions,
    }


def _json_block(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = str(text or "").strip()
    if not stripped:
        return {}
    try:
        parsed = json.loads(stripped)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        parsed = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _build_llm_review_prompt(payload: dict[str, Any]) -> str:
    return (
        "You are reviewing an indie game prototype intake, not a full PRD/GDD.\n"
        "Score only the market and commercialization aspects that cannot be hard-scored reliably with deterministic rules.\n"
        "Use exactly two dimensions, 25 points each: market_potential, commercialization_cost.\n"
        "Be conservative. Do not hand out high scores just because required fields are filled.\n"
        "Market potential and commercialization cost must be judged only from statements present in the file, not from outside knowledge.\n"
        "Do not require a complete PRD, GDD, lore bible, production roadmap, economy design, or full architecture.\n"
        "Return JSON only with keys: total_score, max_score, recommendation, dimensions, top_gaps.\n"
        "recommendation must be one of: market-strong, market-cautious, commercialization-risky.\n\n"
        f"Prototype intake:\n{_json_block(payload)}\n"
    )


def _resolve_codex_command() -> str:
    if sys.platform.startswith("win"):
        return shutil.which("codex.cmd") or shutil.which("codex") or "codex"
    return shutil.which("codex") or "codex"


def _codex_model_args() -> list[str]:
    args: list[str] = []
    model = str(os.environ.get("PHASEA_CODEX_DEFAULT_MODEL") or "").strip()
    reasoning_effort = str(os.environ.get("PHASEA_CODEX_REASONING_EFFORT") or "").strip()
    if model:
        args.extend(["-m", model])
    if reasoning_effort:
        args.extend(["-c", f'model_reasoning_effort="{reasoning_effort}"'])
    return args


def build_prototype_intake_llm_review(
    payload: dict[str, Any],
    *,
    root: Path,
    score_engine: str,
    timeout_sec: int,
) -> dict[str, Any]:
    engine = str(score_engine or "deterministic").strip().lower()
    if engine == "deterministic":
        return {"engine": engine, "status": "skipped", "reason": "deterministic score engine only"}
    if engine not in {"codex", "hybrid"}:
        return {"engine": engine, "status": "skipped", "reason": f"unsupported score engine: {engine}"}

    out_path = root / "logs" / "ci" / "active-prototypes" / f"{sanitize_slug(payload.get('slug') or 'prototype')}.llm-intake-review.md"
    prompt = _build_llm_review_prompt(payload)
    cmd = [
        _resolve_codex_command(),
        "exec",
        *_codex_model_args(),
        "-s",
        "read-only",
        "--skip-git-repo-check",
        "-C",
        str(root),
        "--output-last-message",
        str(out_path),
        "-",
    ]
    rc, trace = _run_with_input(cmd, cwd=root, input_text=prompt, timeout_sec=timeout_sec)
    if rc != 0:
        return {"engine": engine, "status": "failed", "rc": rc, "trace": trace[-2000:]}
    review_text = out_path.read_text(encoding="utf-8") if out_path.exists() else trace
    review = _extract_json_object(review_text)
    if not review:
        return {"engine": engine, "status": "failed", "rc": rc, "trace": trace[-2000:], "error": "missing-json-review"}
    return {"engine": engine, "status": "ok", "review": review}


def _build_confirmation_message(
    payload: dict[str, Any],
    *,
    file_path: str,
    intake_score: dict[str, Any],
    llm_review: dict[str, Any] | None = None,
) -> str:
    lines = [
        "原型工作流已暂停，等待确认。",
        f"原型文件：{file_path or '未提供'}",
        f"Slug：{payload.get('slug') or '（缺失）'}",
        f"假设：{payload.get('hypothesis') or '（缺失）'}",
        f"核心玩家幻想：{payload.get('core_player_fantasy') or '（缺失）'}",
        f"最小可玩循环：{payload.get('minimum_playable_loop') or '（缺失）'}",
        f"游戏特色：{payload.get('game_feature') or '（缺失）'}",
        f"核心游戏循环：{payload.get('core_gameplay_loop') or '（缺失）'}",
        f"胜利 / 失败条件：{payload.get('win_fail_conditions') or '（缺失）'}",
        f"成功标准：{', '.join(payload.get('success_criteria') or []) or '（缺失）'}",
        f"硬评分：{intake_score['total_score']}/{intake_score['max_score']}",
        f"硬评分建议：{intake_score['recommendation']}",
    ]
    specifics = payload.get("game_type_specifics") if isinstance(payload.get("game_type_specifics"), dict) else {}
    selected_sections = [item for item in list(specifics.get("selected_sections") or []) if isinstance(item, dict)]
    if selected_sections:
        lines.append(f"游戏类型指南：{specifics.get('guide_path') or '（缺失）'}")
        for section in selected_sections:
            title = str(section.get("title") or section.get("id") or "Game type section")
            answer = str(section.get("answer") or "(missing)")
            lines.append(f"{title}: {answer}")
    type_kit = payload.get("prototype_type_kit") if isinstance(payload.get("prototype_type_kit"), dict) else {}
    if type_kit:
        lines.append(f"Prototype type kit: {type_kit.get('kit_path') or 'missing'}")
        for section_name, label in (("gameplay_flow", "Gameplay Flow / GDD Route"), ("prototype_scene_ui", "Prototype Scene UI")):
            answered = [str(item.get("answer") or "").strip() for item in list(type_kit.get(section_name) or []) if isinstance(item, dict) and str(item.get("answer") or "").strip()]
            if answered:
                lines.append(f"{label}: {'; '.join(answered[:3])}")
    implementation_skill = payload.get("implementation_skill") if isinstance(payload.get("implementation_skill"), dict) else {}
    if implementation_skill:
        lines.append(f"Prototype implementation skill: {implementation_skill.get('name') or 'unknown'}")
        lines.append(f"Prototype implementation skill path: {implementation_skill.get('path') or 'missing'}")
    for item in intake_score["dimensions"]:
        lines.append(f"{item['label']}: {item['score']}/{item['max_score']}")
    if llm_review and llm_review.get("status") == "ok":
        review = dict(llm_review.get("review") or {})
        lines.append(f"AI market/commercial score: {review.get('total_score', 'unknown')}/{review.get('max_score', 50)}")
        lines.append(f"AI market/commercial recommendation: {review.get('recommendation', 'unknown')}")
        for item in list(review.get("dimensions") or []):
            if isinstance(item, dict):
                label = str(item.get("label") or item.get("id") or "AI dimension")
                score = item.get("score", "unknown")
                max_score = item.get("max_score", 25)
                lines.append(f"{label}: {score}/{max_score}")
            else:
                text = str(item).strip()
                if text:
                    lines.append(text)
        top_gaps = [str(item) for item in list(review.get("top_gaps") or []) if str(item).strip()]
        if top_gaps:
            lines.append(f"AI top gaps: {'; '.join(top_gaps[:3])}")
    elif llm_review and llm_review.get("status") == "skipped":
        lines.append("AI 市场/商业化评估：未运行")
    elif llm_review and llm_review.get("status") not in {"skipped", ""}:
        lines.append(f"AI market/commercial review: {llm_review.get('status')} ({llm_review.get('reason') or llm_review.get('error') or 'see active state'})")
    return "\n".join(lines)


def _run(cmd: list[str], *, cwd: Path) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="ignore",
        check=False,
    )
    return proc.returncode or 0, proc.stdout or ""


def _run_with_input(cmd: list[str], *, cwd: Path, input_text: str, timeout_sec: int) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd,
            input=input_text,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=False,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired:
        return 124, "codex exec timeout\n"
    except Exception as exc:  # noqa: BLE001
        return 1, f"codex exec failed to start: {exc}\n"
    return proc.returncode or 0, proc.stdout or ""


def _resolve_codex_command() -> str:
    if sys.platform.startswith("win"):
        return shutil.which("codex.cmd") or shutil.which("codex") or "codex"
    return shutil.which("codex") or "codex"


def _codex_model_args() -> list[str]:
    args: list[str] = []
    model = str(os.environ.get("PHASEA_CODEX_DEFAULT_MODEL") or "").strip()
    reasoning_effort = str(os.environ.get("PHASEA_CODEX_REASONING_EFFORT") or "").strip()
    if model:
        args.extend(["-m", model])
    if reasoning_effort:
        args.extend(["-c", f'model_reasoning_effort="{reasoning_effort}"'])
    return args


def _prototype_record_path(*, root: Path, slug: str) -> Path:
    return root / "docs" / "prototypes" / f"{today_str()}-{slug}.md"


def _ensure_prototype_record(root: Path, payload: dict[str, Any]) -> tuple[int, str]:
    cmd = [
        "py",
        "-3",
        "scripts/python/run_prototype_tdd.py",
        "--slug",
        str(payload["slug"]),
        "--create-record-only",
        "--owner",
        str(payload["owner"]),
        "--hypothesis",
        str(payload["hypothesis"]),
        "--core-player-fantasy",
        str(payload["core_player_fantasy"]),
        "--minimum-playable-loop",
        str(payload["minimum_playable_loop"]),
        "--game-feature",
        str(payload["game_feature"]),
        "--core-gameplay-loop",
        str(payload["core_gameplay_loop"]),
        "--win-fail-conditions",
        str(payload["win_fail_conditions"]),
        "--decision",
        str(payload["decision"]),
        "--next-step",
        str(payload["next_step"]),
    ]
    for item in payload.get("related_formal_task_ids") or []:
        cmd += ["--related-task-id", str(item)]
    for item in payload.get("scope_in") or []:
        cmd += ["--scope-in", str(item)]
    for item in payload.get("scope_out") or []:
        cmd += ["--scope-out", str(item)]
    for item in payload.get("success_criteria") or []:
        cmd += ["--success-criteria", str(item)]
    for item in payload.get("promote_signals") or []:
        cmd += ["--promote-signal", str(item)]
    for item in payload.get("archive_signals") or []:
        cmd += ["--archive-signal", str(item)]
    for item in payload.get("discard_signals") or []:
        cmd += ["--discard-signal", str(item)]
    for item in payload.get("evidence") or []:
        cmd += ["--evidence", str(item)]
    specifics = payload.get("game_type_specifics") if isinstance(payload.get("game_type_specifics"), dict) else {}
    if specifics.get("game_type"):
        cmd += ["--game-type-specific-game-type", str(specifics.get("game_type"))]
    if specifics.get("guide_path"):
        cmd += ["--game-type-specific-guide-path", str(specifics.get("guide_path"))]
    for section in list(specifics.get("selected_sections") or []):
        if isinstance(section, dict):
            title = str(section.get("title") or section.get("id") or "").strip()
            answer = str(section.get("answer") or "").strip()
            if title or answer:
                cmd += ["--game-type-specific-section", f"{title}: {answer}"]
    type_kit = payload.get("prototype_type_kit") if isinstance(payload.get("prototype_type_kit"), dict) else {}
    if type_kit.get("game_type"):
        cmd += ["--prototype-type-kit-game-type", str(type_kit.get("game_type"))]
    if type_kit.get("kit_path"):
        cmd += ["--prototype-type-kit-path", str(type_kit.get("kit_path"))]
    if type_kit.get("manifest_path"):
        cmd += ["--prototype-type-kit-manifest-path", str(type_kit.get("manifest_path"))]
    for item in list(type_kit.get("gameplay_flow") or []):
        if isinstance(item, dict):
            cmd += ["--prototype-type-kit-gameplay-flow", f"{item.get('question') or item.get('id') or ''} {item.get('answer') or ''}".strip()]
    for item in list(type_kit.get("prototype_scene_ui") or []):
        if isinstance(item, dict):
            cmd += ["--prototype-type-kit-scene-ui", f"{item.get('question') or item.get('id') or ''} {item.get('answer') or ''}".strip()]
    implementation_skill = payload.get("implementation_skill") if isinstance(payload.get("implementation_skill"), dict) else {}
    if implementation_skill.get("name"):
        cmd += ["--implementation-skill-name", str(implementation_skill.get("name"))]
    if implementation_skill.get("path"):
        cmd += ["--implementation-skill-path", str(implementation_skill.get("path"))]
    if implementation_skill.get("contract_path"):
        cmd += ["--implementation-skill-contract-path", str(implementation_skill.get("contract_path"))]
    return _run(cmd, cwd=root)


def _build_implementation_prompt(*, payload: dict[str, Any], record_file: str, default_scene: str) -> str:
    implementation_skill = payload.get("implementation_skill") if isinstance(payload.get("implementation_skill"), dict) else {}
    skill_name = str(implementation_skill.get("name") or "normal")
    contract_path = str(implementation_skill.get("contract_path") or "").strip()
    success_criteria = [str(item).strip() for item in list(payload.get("success_criteria") or []) if str(item).strip()]
    slug = sanitize_slug(payload.get("slug") or "prototype")
    class_name = _prototype_class_name(slug)
    scene_path = f"Game.Godot/Prototypes/{slug}/{class_name}.tscn"
    script_path = f"Game.Godot/Prototypes/{slug}/Scripts/{class_name}.cs"
    core_loop_path = f"Game.Core/Prototypes/{class_name}Loop.cs"
    dotnet_test_path = _prototype_dotnet_test_path(slug)
    gdunit_test_path = _prototype_godot_test_path(slug)
    return (
        "你正在执行 prototype lane 的 Day 4 最小实现步骤。\n"
        "目标：基于当前原型记录，把 Day 3 红灯测试修到最小可通过，并保持范围严格受控。\n"
        "要求：\n"
        "- 只修改当前仓库内与该 prototype 直接相关的代码、场景、测试和文档。\n"
        "- 不进入 Chapter 3-7 正式交付流程。\n"
        "- 不做破坏性 git 操作。\n"
        "- 当前 workspace 不是独立 git 仓库，不要执行 git status、git config safe.directory 或任何 git 探测命令。\n"
        "- 如果 rg 不可用，必须改用 Python、Get-ChildItem 或 Select-String 等回退方式继续，不要因为工具缺失中止。\n"
        "- 优先保证：项目专属 red 测试可以转为 green，Godot 场景可实例化，默认场景路径有效。\n"
        "- 如果你新增了实现，请同步让项目专属测试不再依赖模板 DefaultRpgPrototype。\n"
        "- 必须保留并使用当前 slug 对应的项目专属路径，不得回退到模板场景或模板测试。\n"
        "- 必须保证从 Game.Godot/Scenes/Main.tscn 进入后，主菜单里的“原型 / Prototype”按钮能够通过现有 MainMenu + PrototypeCatalog + ScreenNavigator 链路跳转到本次 prototype 的 default_scene。\n"
        "- 不允许只生成 prototype 场景文件而不接通 Main.tscn 的主菜单原型入口；如果入口无法跳到项目专属场景，这次实现视为不完整。\n"
        "- 如果当前原型是 RPG，不得仅通过加载 DefaultRpgTemplate 或复用 DefaultRpgPrototypeLoop 来包装出一个表面可运行的壳。\n"
        "- 如果当前原型是 RPG，项目专属实现必须自己维护地图移动、遇敌、战斗、奖励三选一，以及打赢目标或失败重试的最小状态流转。\n"
        "- 必须落地并维护以下文件：\n"
        f"  1. {scene_path}\n"
        f"  2. {script_path}\n"
        f"  3. {core_loop_path}\n"
        f"  4. {dotnet_test_path}\n"
        f"  5. {gdunit_test_path}\n"
        "- 场景根下必须存在名为 PrototypeLoop 的节点，供项目专属 GdUnit 测试读取。\n"
        "- scene 脚手架默认提示文字不能作为最终实现结果；必须完全替换脚手架 _Ready 实现，不能只保留一条 GD.Print 提示。\n"
        "- Godot 脚本必须在运行时提供一个最小可交互循环，至少让玩家看到当前状态、推进一次循环，并拿到完成或重试反馈。\n"
        "- 目标循环必须覆盖当前记录里的地图移动、遇敌、战斗、奖励或结算反馈，不要只停留在空壳 UI。\n"
        "- 完成实现时，请一并检查主菜单原型入口是否仍指向 default_scene，而不是模板 DefaultRpgPrototype。\n"
        "- 完成后输出简短总结，说明主要改动和验证结果。\n\n"
        f"Prototype slug: {payload.get('slug')}\n"
        f"Prototype record: {record_file}\n"
        f"Default scene target: {default_scene}\n"
        f"Implementation skill: {skill_name}\n"
        f"Contract path: {contract_path or 'none'}\n"
        f"Hypothesis: {payload.get('hypothesis')}\n"
        f"Core player fantasy: {payload.get('core_player_fantasy')}\n"
        f"Minimum playable loop: {payload.get('minimum_playable_loop')}\n"
        f"Game feature: {payload.get('game_feature')}\n"
        f"Core gameplay loop: {payload.get('core_gameplay_loop')}\n"
        f"Win/fail conditions: {payload.get('win_fail_conditions')}\n"
        f"Success criteria: {'; '.join(success_criteria) if success_criteria else 'none'}\n"
    )


@contextlib.contextmanager
def _temporary_env(overrides: dict[str, str]):
    previous = {key: os.environ.get(key) for key in overrides}
    try:
        for key, value in overrides.items():
            os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _prototype_scene_file(*, root: Path, slug: str) -> Path:
    class_name = _prototype_class_name(slug)
    return root / "Game.Godot" / "Prototypes" / sanitize_slug(slug) / f"{class_name}.tscn"


def _prototype_script_file(*, root: Path, slug: str) -> Path:
    class_name = _prototype_class_name(slug)
    return root / "Game.Godot" / "Prototypes" / sanitize_slug(slug) / "Scripts" / f"{class_name}.cs"


def _prototype_core_loop_file(*, root: Path, slug: str) -> Path:
    class_name = _prototype_class_name(slug)
    return root / "Game.Core" / "Prototypes" / f"{class_name}Loop.cs"


def _prototype_state_type_name(slug: str) -> str:
    return f"{_prototype_class_name(slug)}State"


def _prototype_encounter_type_name(slug: str) -> str:
    return f"{_prototype_class_name(slug)}Encounter"


def _prototype_reward_option_type_name(slug: str) -> str:
    return f"{_prototype_class_name(slug)}RewardOption"


def _prototype_battle_result_type_name(slug: str) -> str:
    return f"{_prototype_class_name(slug)}BattleResult"


def _is_rpg_payload(payload: dict[str, Any]) -> bool:
    game_type = sanitize_slug(str(payload.get("game_type") or ""))
    if game_type == "rpg":
        return True
    implementation_skill = payload.get("implementation_skill") if isinstance(payload.get("implementation_skill"), dict) else {}
    return str(implementation_skill.get("name") or "").strip() == "prototype-rpg-godot-zh"


def _render_day4_fallback_script(*, slug: str) -> str:
    class_name = _prototype_class_name(slug)
    loop_class_name = f"{class_name}Loop"
    return "\n".join(
        [
            "using Game.Core.Prototypes;",
            "using Godot;",
            "",
            "namespace Game.Godot.Prototypes;",
            "",
            f"public partial class {class_name} : Node2D",
            "{",
            f"    private readonly {loop_class_name} _loop = new();",
            "    private Label? _statusLabel;",
            "    private Label? _logLabel;",
            "    private Button? _actionButton;",
            "    private Button? _retryButton;",
            "    private int _stepIndex;",
            "    private bool _finished;",
            "",
            "    public override void _Ready()",
            "    {",
            "        EnsureRuntimeUi();",
            "        ResetLoop();",
            "    }",
            "",
            "    private void EnsureRuntimeUi()",
            "    {",
            '        var loopNode = GetNodeOrNull<Node2D>("PrototypeLoop");',
            "        if (loopNode is null)",
            "        {",
            '            loopNode = new Node2D { Name = \"PrototypeLoop\" };',
            "            AddChild(loopNode);",
            "        }",
            "",
            '        var canvas = GetNodeOrNull<CanvasLayer>("CanvasLayer");',
            "        if (canvas is null)",
            "        {",
            '            canvas = new CanvasLayer { Name = \"CanvasLayer\" };',
            "            AddChild(canvas);",
            "        }",
            "",
            '        var ui = canvas.GetNodeOrNull<Control>("UI");',
            "        if (ui is null)",
            "        {",
            '            ui = new Control { Name = \"UI\" };',
            "            ui.SetAnchorsPreset(Control.LayoutPreset.FullRect);",
            "            canvas.AddChild(ui);",
            "        }",
            "",
            '        var panel = ui.GetNodeOrNull<PanelContainer>("Panel");',
            "        if (panel is null)",
            "        {",
            '            panel = new PanelContainer { Name = \"Panel\" };',
            "            panel.SetAnchorsPreset(Control.LayoutPreset.TopLeft);",
            "            panel.OffsetLeft = 24;",
            "            panel.OffsetTop = 24;",
            "            panel.OffsetRight = 500;",
            "            panel.OffsetBottom = 280;",
            "            ui.AddChild(panel);",
            "        }",
            "",
            '        var vbox = panel.GetNodeOrNull<VBoxContainer>("VBox");',
            "        if (vbox is null)",
            "        {",
            '            vbox = new VBoxContainer { Name = \"VBox\" };',
            "            vbox.SetAnchorsPreset(Control.LayoutPreset.FullRect);",
            "            vbox.OffsetLeft = 12;",
            "            vbox.OffsetTop = 12;",
            "            vbox.OffsetRight = -12;",
            "            vbox.OffsetBottom = -12;",
            "            panel.AddChild(vbox);",
            "        }",
            "",
            '        _statusLabel = vbox.GetNodeOrNull<Label>("StatusLabel");',
            "        if (_statusLabel is null)",
            "        {",
            '            _statusLabel = new Label { Name = \"StatusLabel\" };',
            "            vbox.AddChild(_statusLabel);",
            "        }",
            "",
            '        _logLabel = vbox.GetNodeOrNull<Label>("LogLabel");',
            "        if (_logLabel is null)",
            "        {",
            '            _logLabel = new Label { Name = \"LogLabel\" };',
            "            _logLabel.AutowrapMode = TextServer.AutowrapMode.WordSmart;",
            "            vbox.AddChild(_logLabel);",
            "        }",
            "",
            '        var buttons = vbox.GetNodeOrNull<HBoxContainer>("Buttons");',
            "        if (buttons is null)",
            "        {",
            '            buttons = new HBoxContainer { Name = \"Buttons\" };',
            "            vbox.AddChild(buttons);",
            "        }",
            "",
            '        _actionButton = buttons.GetNodeOrNull<Button>("ActionButton");',
            "        if (_actionButton is null)",
            "        {",
            '            _actionButton = new Button { Name = \"ActionButton\" };',
            "            buttons.AddChild(_actionButton);",
            "        }",
            "",
            '        _retryButton = buttons.GetNodeOrNull<Button>("RetryButton");',
            "        if (_retryButton is null)",
            "        {",
            '            _retryButton = new Button { Name = \"RetryButton\" };',
            "            buttons.AddChild(_retryButton);",
            "        }",
            "",
            "        _actionButton.Pressed -= AdvanceLoop;",
            "        _actionButton.Pressed += AdvanceLoop;",
            "        _retryButton.Pressed -= ResetLoop;",
            "        _retryButton.Pressed += ResetLoop;",
            "    }",
            "",
            "    private void AdvanceLoop()",
            "    {",
            "        if (_finished)",
            "        {",
            "            return;",
            "        }",
            "",
            "        _stepIndex += 1;",
            "        if (_stepIndex >= 3)",
            "        {",
            "            _finished = true;",
            '            SetStatus(\"Prototype complete\");',
            '            SetLog(_loop.DescribePlayableLoop() + \"\\nOutcome: win feedback reached. Press Retry to loop again.\");',
            "            if (_actionButton is not null)",
            "            {",
            "                _actionButton.Disabled = true;",
            '                _actionButton.Text = \"Completed\";',
            "            }",
            "            if (_retryButton is not null)",
            "            {",
            "                _retryButton.Disabled = false;",
            "            }",
            "            return;",
            "        }",
            "",
            "        if (_stepIndex == 1)",
            "        {",
            '            SetStatus(\"Encounter\");',
            '            SetLog(\"The player moves forward, finds a target, and enters the first readable encounter.\");',
            "            return;",
            "        }",
            "",
            '        SetStatus(\"Battle resolved\");',
            '        SetLog(\"One readable action resolves the encounter and the prototype shows a reward/result transition.\");',
            "    }",
            "",
            "    private void ResetLoop()",
            "    {",
            "        _stepIndex = 0;",
            "        _finished = false;",
            '        SetStatus(\"Ready\");',
            "        SetLog(_loop.DescribePlayableLoop());",
            "        if (_actionButton is not null)",
            "        {",
            "            _actionButton.Disabled = false;",
            '            _actionButton.Text = \"Advance Loop\";',
            "        }",
            "        if (_retryButton is not null)",
            "        {",
            "            _retryButton.Disabled = true;",
            "        }",
            "    }",
            "",
            "    private void SetStatus(string value)",
            "    {",
            "        if (_statusLabel is not null)",
            "        {",
            '            _statusLabel.Text = $\"Status: {value}\";',
            "        }",
            "    }",
            "",
            "    private void SetLog(string value)",
            "    {",
            "        if (_logLabel is not null)",
            "        {",
            "            _logLabel.Text = value;",
            "        }",
            "    }",
            "}",
            "",
        ]
    )


def _render_rpg_project_specific_scene(*, slug: str) -> str:
    source = baseline_repo_root() / "Game.Godot" / "Prototypes" / "dq-rpg" / "DqRpgPrototype.tscn"
    if source.exists() and sanitize_slug(slug) == "dq-rpg":
        return read_text(source, errors="ignore")

    class_name = _prototype_class_name(slug)
    return "\n".join(
        [
            "[gd_scene load_steps=2 format=3]",
            "",
            f'[ext_resource type="Script" path="res://Game.Godot/Prototypes/{sanitize_slug(slug)}/Scripts/{class_name}.cs" id="1"]',
            "",
            f'[node name="{class_name}" type="Node2D"]',
            'script = ExtResource("1")',
            "",
            '[node name="PrototypeLoop" type="Node2D" parent="."]',
            "",
        ]
    )


def _render_rpg_project_specific_core_loop(*, slug: str) -> str:
    source = baseline_repo_root() / "Game.Core" / "Prototypes" / "DqRpgPrototypeLoop.cs"
    if source.exists() and sanitize_slug(slug) == "dq-rpg":
        return read_text(source, errors="ignore")

    class_name = _prototype_class_name(slug)
    state_type = _prototype_state_type_name(slug)
    encounter_type = _prototype_encounter_type_name(slug)
    reward_option_type = _prototype_reward_option_type_name(slug)
    battle_result_type = _prototype_battle_result_type_name(slug)
    return "\n".join(
        [
            "using System;",
            "using System.Collections.Generic;",
            "using System.Linq;",
            "",
            "namespace Game.Core.Prototypes;",
            "",
            f"public sealed class {class_name}Loop",
            "{",
            "    public const int VictoryBattleCount = 15;",
            "    public const int WinBattleTarget = VictoryBattleCount;",
            "",
            f"    public {state_type} CreateInitialState()",
            "    {",
            f"        return new {state_type}(28, 6, 0, 0, \"map\", false, false, \"Explore the map and collide with the monster to start the next battle.\", []);",
            "    }",
            "",
            "    public string DescribePlayableLoop()",
            "    {",
            '        return "Move on the map, collide with a visible monster, resolve a player-first battle, pick one of three growth rewards, return to the map, and survive 15 wins before a single defeat ends the run.";',
            "    }",
            "",
            f"    public {encounter_type} CreateEncounter({state_type} state)",
            "    {",
            "        var nextBattleIndex = state.BattlesWon + 1;",
            "        if (nextBattleIndex >= VictoryBattleCount)",
            "        {",
            f'            return new {encounter_type}("boss", "Boss Herald", 24, 5, 2);',
            "        }",
            "        if (nextBattleIndex % 5 == 0)",
            "        {",
            f'            return new {encounter_type}("elite", $\"Elite Slime {nextBattleIndex}\", 16 + nextBattleIndex, 4, 1);',
            "        }",
            f'        return new {encounter_type}("normal", $\"Wild Slime {nextBattleIndex}\", 9 + nextBattleIndex, 3 + Math.Min(2, nextBattleIndex / 6), 0);',
            "    }",
            "",
            f"    public {state_type} EnterBattle({state_type} state, {encounter_type} encounter)",
            "    {",
            "        return state with { Phase = \"battle\", LastEvent = $\"Encountered {encounter.Name}. Press Attack to resolve the turn-based exchange.\" };",
            "    }",
            "",
            f"    public {state_type} EnterChestReward({state_type} state)",
            "    {",
            "        return state with { Phase = \"reward\", LastEvent = \"Opened a chest. Pick one of three rewards.\" };",
            "    }",
            "",
            f"    public {battle_result_type} ResolveBattle({state_type} state, {encounter_type} encounter)",
            "    {",
            "        var battleLog = new List<string> { $\"Battle {state.BattlesWon + 1}: {encounter.Name}\" };",
            "        var playerHp = state.PlayerHp;",
            "        var enemyHp = encounter.Hp;",
            "        var round = 1;",
            "        while (playerHp > 0 && enemyHp > 0)",
            "        {",
            "            var playerDamage = Math.Max(1, state.PlayerAttack - encounter.Defense);",
            "            enemyHp = Math.Max(0, enemyHp - playerDamage);",
            "            battleLog.Add($\"Round {round}: player deals {playerDamage} damage.\");",
            "            if (enemyHp <= 0)",
            "            {",
            "                break;",
            "            }",
            "            var enemyDamage = Math.Max(1, encounter.Attack);",
            "            playerHp = Math.Max(0, playerHp - enemyDamage);",
            "            battleLog.Add($\"Round {round}: enemy deals {enemyDamage} damage.\");",
            "            round++;",
            "        }",
            "        if (playerHp <= 0)",
            "        {",
            "            var failedState = state with { PlayerHp = 0, Phase = \"complete\", IsGameOver = true, IsVictory = false, LastEvent = \"The run failed. Retry to restart the prototype.\" };",
            "            battleLog.Add(\"Defeat. The prototype run is over.\");",
            f"            return new {battle_result_type}(encounter, failedState, [], battleLog);",
            "        }",
            "        var nextWins = state.BattlesWon + 1;",
            "        var isVictory = nextWins >= VictoryBattleCount;",
            "        var nextState = state with",
            "        {",
            "            PlayerHp = playerHp,",
            "            BattlesWon = nextWins,",
            "            Phase = isVictory ? \"complete\" : \"reward\",",
            "            IsGameOver = false,",
            "            IsVictory = isVictory,",
            "            LastEvent = isVictory ? \"Victory. The boss is down and the prototype loop is complete.\" : \"Victory. Pick one reward and return to the map.\"",
            "        };",
            "        battleLog.Add(isVictory ? \"Boss defeated. Prototype objective cleared.\" : \"Enemy defeated. Reward selection unlocked.\");",
            "        var rewardOptions = isVictory ? [] : CreateRewardOptions(nextState, fromChest: false);",
            f"        return new {battle_result_type}(encounter, nextState, rewardOptions, battleLog);",
            "    }",
            "",
            f"    public IReadOnlyList<{reward_option_type}> CreateRewardOptions({state_type} state, bool fromChest)",
            "    {",
            "        var tier = Math.Max(1, state.BattlesWon);",
            "        var hpBoost = fromChest ? 4 : 3 + (tier / 5);",
            "        var attackBoost = fromChest ? 1 : 1 + (tier / 7);",
            "        return",
            "        [",
            f'            new {reward_option_type}("Vital Draft", $"+{hpBoost} HP to survive the next encounter.", hpBoost, 0),',
            f'            new {reward_option_type}("Iron Edge", $"+{attackBoost} ATK for faster battles.", 0, attackBoost),',
            f'            new {reward_option_type}("Balanced Crest", "+2 HP and +1 ATK for a safer all-round route.", 2, 1)',
            "        ];",
            "    }",
            "",
            f"    public {state_type} ApplyReward({state_type} state, int rewardIndex, bool fromChest)",
            "    {",
            "        var options = CreateRewardOptions(state, fromChest);",
            "        var selectedIndex = Math.Clamp(rewardIndex, 0, options.Count - 1);",
            "        var reward = options[selectedIndex];",
            "        var rewardHistory = state.RewardHistory.ToList();",
            "        rewardHistory.Add(reward.Title);",
            "        return state with",
            "        {",
            "            PlayerHp = state.PlayerHp + reward.HpDelta,",
            "            PlayerAttack = state.PlayerAttack + reward.AttackDelta,",
            "            ChestsOpened = state.ChestsOpened + (fromChest ? 1 : 0),",
            "            Phase = \"map\",",
            "            LastEvent = fromChest ? $\"Chest reward selected: {reward.Title}. Continue exploring.\" : $\"Battle reward selected: {reward.Title}. Return to the map for the next fight.\",",
            "            RewardHistory = rewardHistory",
            "        };",
            "    }",
            "}",
            "",
            f"public sealed record {state_type}(int PlayerHp, int PlayerAttack, int BattlesWon, int ChestsOpened, string Phase, bool IsGameOver, bool IsVictory, string LastEvent, IReadOnlyList<string> RewardHistory);",
            f"public sealed record {encounter_type}(string Kind, string Name, int Hp, int Attack, int Defense);",
            f"public sealed record {reward_option_type}(string Title, string Description, int HpDelta, int AttackDelta);",
            f"public sealed record {battle_result_type}({encounter_type} Encounter, {state_type} NextState, IReadOnlyList<{reward_option_type}> RewardOptions, IReadOnlyList<string> BattleLog);",
            "",
        ]
    )


def _render_rpg_project_specific_script(*, slug: str) -> str:
    source = baseline_repo_root() / "Game.Godot" / "Prototypes" / "dq-rpg" / "Scripts" / "DqRpgPrototype.cs"
    if source.exists() and sanitize_slug(slug) == "dq-rpg":
        return read_text(source, errors="ignore")

    class_name = _prototype_class_name(slug)
    return "\n".join(
        [
            "using Game.Core.Prototypes;",
            "using Godot;",
            "",
            "namespace Game.Godot.Prototypes;",
            "",
            f"public partial class {class_name} : Node2D",
            "{",
            "    public override void _Ready()",
            "    {",
            '        var loopNode = GetNodeOrNull<Node2D>("PrototypeLoop");',
            "        if (loopNode is null)",
            "        {",
            '            loopNode = new Node2D { Name = "PrototypeLoop" };',
            "            AddChild(loopNode);",
            "        }",
            "",
            '        var label = new Label();',
            '        label.Text = "RPG fallback ready. Replace with a richer project-specific prototype if needed.";',
            "        loopNode.AddChild(label);",
            "    }",
            "}",
            "",
        ]
    )


def _write_rpg_project_specific_fallback(*, root: Path, payload: dict[str, Any]) -> None:
    slug = sanitize_slug(payload.get("slug") or "prototype")
    scene_path = _prototype_scene_file(root=root, slug=slug)
    script_path = _prototype_script_file(root=root, slug=slug)
    core_loop_path = _prototype_core_loop_file(root=root, slug=slug)
    write_text(scene_path, _render_rpg_project_specific_scene(slug=slug))
    write_text(script_path, _render_rpg_project_specific_script(slug=slug))
    write_text(core_loop_path, _render_rpg_project_specific_core_loop(slug=slug))


def _apply_day4_fallback_if_needed(*, root: Path, payload: dict[str, Any], issues: list[str]) -> bool:
    slug = sanitize_slug(payload.get("slug") or "prototype")
    if _is_rpg_payload(payload):
        rpg_issue_prefixes = (
            "missing_files=",
            "scaffold_script_not_replaced=",
            "template_scene_dependency=",
            "template_core_loop_dependency=",
            "rpg_runtime_loop_ui_missing=",
            "rpg_reward_flow_missing=",
            "rpg_win_target_missing=",
        )
        if any(issue.startswith(rpg_issue_prefixes) for issue in issues):
            _write_rpg_project_specific_fallback(root=root, payload=payload)
            return True

    script_path = _prototype_script_file(root=root, slug=slug)
    class_name = _prototype_class_name(slug)
    scaffold_issue = f"scaffold_script_not_replaced={_repo_relative_posix(root, script_path)}"
    if scaffold_issue not in issues:
        return False
    if not path_exists(script_path):
        return False

    script_text = read_text(script_path, errors="ignore")
    if "private Label? _statusLabel;" in script_text and "AdvanceLoop();" in script_text:
        return False

    scene_path = _prototype_scene_file(root=root, slug=slug)
    if not path_exists(scene_path):
        return False

    scene_text = read_text(scene_path, errors="ignore")
    if f'path="res://Game.Godot/Prototypes/{slug}/Scripts/{class_name}.cs"' not in scene_text:
        return False

    write_text(script_path, _render_day4_fallback_script(slug=slug))
    return True


def _validate_day4_implementation_outputs(*, root: Path, payload: dict[str, Any]) -> tuple[bool, list[str]]:
    slug = sanitize_slug(payload.get("slug") or "prototype")
    scene_path = _prototype_scene_file(root=root, slug=slug)
    script_path = _prototype_script_file(root=root, slug=slug)
    core_loop_path = _prototype_core_loop_file(root=root, slug=slug)
    dotnet_test_path = root / _prototype_dotnet_test_path(slug).replace("/", os.sep)
    gdunit_test_path = root / _prototype_godot_test_path(slug).replace("/", os.sep)
    missing: list[str] = []
    for path in (scene_path, script_path, core_loop_path, dotnet_test_path, gdunit_test_path):
        if not path_exists(path):
            missing.append(_repo_relative_posix(root, path))

    issues: list[str] = []
    if missing:
        issues.append("missing_files=" + ",".join(missing))

    if path_exists(scene_path):
        scene_text = read_text(scene_path, errors="ignore")
        if '[node name="PrototypeLoop"' not in scene_text:
            issues.append(f"missing_prototype_loop_node={_repo_relative_posix(root, scene_path)}")
    if path_exists(script_path):
        script_text = read_text(script_path, errors="ignore")
        if "Prototype scaffold ready: replace this scene with the minimum playable loop." in script_text:
            issues.append(f"scaffold_script_not_replaced={_repo_relative_posix(root, script_path)}")
        if _is_rpg_payload(payload):
            if "DefaultRpgTemplate/DefaultRpgPrototype.tscn" in script_text or "DefaultPrototypeScenePath" in script_text:
                issues.append(f"template_scene_dependency={_repo_relative_posix(root, script_path)}")
            runtime_marker_groups = [
                ("reward", ("RewardOption", "Reward Choice", "reward")),
                ("movement", ("WASD", "W/A/S/D", "Move", "ReadMovementInput")),
                ("battle", ("Attack", "battle", "StartEncounter")),
                ("retry", ("Retry", "_retryButton", "Restart")),
            ]
            for _, marker_group in runtime_marker_groups:
                if not any(marker in script_text for marker in marker_group):
                    issues.append(f"rpg_runtime_loop_ui_missing={_repo_relative_posix(root, script_path)}")
                    break
    if path_exists(core_loop_path) and _is_rpg_payload(payload):
        core_loop_text = read_text(core_loop_path, errors="ignore")
        if "DefaultRpgPrototypeLoop" in core_loop_text:
            issues.append(f"template_core_loop_dependency={_repo_relative_posix(root, core_loop_path)}")
        if "WinBattleTarget" not in core_loop_text and "VictoryBattleCount" not in core_loop_text and "VictoryTarget" not in core_loop_text:
            issues.append(f"rpg_win_target_missing={_repo_relative_posix(root, core_loop_path)}")
        if "CreateRewardOptions" not in core_loop_text and "BuildRewardOptions" not in core_loop_text and "RewardOptions" not in core_loop_text:
            issues.append(f"rpg_reward_flow_missing={_repo_relative_posix(root, core_loop_path)}")
    return len(issues) == 0, issues


def _run_day4_codex_implementation(*, root: Path, payload: dict[str, Any], record_file: str) -> tuple[int, str]:
    default_scene = _resolve_runtime_default_scene(root=root, payload=payload)
    out_path = root / "logs" / "ci" / today_str() / f"prototype-implementation-{sanitize_slug(payload.get('slug') or 'prototype')}" / "codex-output.txt"
    ensure_dir(out_path.parent)
    prompt = _build_implementation_prompt(payload=payload, record_file=record_file, default_scene=default_scene)
    cmd = [
        _resolve_codex_command(),
        "exec",
        *_codex_model_args(),
        "--sandbox",
        "workspace-write",
        "--skip-git-repo-check",
        "-c",
        'approval_policy="never"',
        "--cd",
        str(root),
        "-o",
        str(out_path),
        prompt,
    ]
    env_overrides = {
        "GIT_CEILING_DIRECTORIES": str(root),
        "GIT_DISCOVERY_ACROSS_FILESYSTEM": "1",
    }
    with _temporary_env(env_overrides):
        rc, trace = _run(cmd, cwd=root)
    output = ""
    if path_exists(out_path):
        output = read_text(out_path, errors="ignore")
    merged = output.strip() or trace.strip()
    valid, issues = _validate_day4_implementation_outputs(root=root, payload=payload)
    fallback_applied = False
    if not valid:
        fallback_applied = _apply_day4_fallback_if_needed(root=root, payload=payload, issues=issues)
        if fallback_applied:
            valid, issues = _validate_day4_implementation_outputs(root=root, payload=payload)
    if not valid:
        validation_text = "DAY4_IMPLEMENTATION_VALIDATION failed " + " ".join(issues)
        merged = "\n".join(part for part in [merged.strip(), validation_text, trace.strip() if rc != 0 else ""] if part.strip())
        return 1, merged + ("\n" if merged and not merged.endswith("\n") else "")
    if fallback_applied:
        merged = "\n".join(
            part
            for part in [
                merged.strip(),
                "DAY4_IMPLEMENTATION_FALLBACK applied=minimal_runtime_script",
            ]
            if part.strip()
        )
    if rc != 0:
        merged = "\n".join(
            part
            for part in [
                merged.strip(),
                f"DAY4_IMPLEMENTATION_RECOVERED codex_exit_code={rc}",
            ]
            if part.strip()
        )
        return 0, merged + ("\n" if merged and not merged.endswith("\n") else "")
    return rc, merged + ("\n" if merged and not merged.endswith("\n") else "")


def _day_steps(payload: dict[str, Any], *, root: Path, record_file: str) -> list[dict[str, Any]]:
    slug = str(payload["slug"])
    default_scene = _resolve_runtime_default_scene(root=root, payload=payload)
    filter_expr = str(payload.get("test_filter") or "").strip() or _prototype_loop_test_filter(slug)
    gdunit_path = str(payload.get("gdunit_path") or "").strip() or _prototype_gdunit_dir(slug)
    return [
        {
            "day": 1,
            "title": "创建原型记录",
            "cmd": None,
        },
        {
            "day": 2,
            "title": "创建最小原型场景脚手架",
            "cmd": ["py", "-3", "scripts/python/dev_cli.py", "create-prototype-scene", "--slug", slug],
        },
        {
            "day": 3,
            "title": "执行 prototype red",
            "cmd": [
                "py",
                "-3",
                "scripts/python/dev_cli.py",
                "run-prototype-tdd",
                "--slug",
                slug,
                "--stage",
                "red",
                "--dotnet-target",
                "Game.Core.Tests/Game.Core.Tests.csproj",
                "--filter",
                filter_expr,
            ],
        },
        {
            "day": 4,
            "title": "执行最小实现并准备 prototype green",
            "cmd": None,
            "internal_action": "codex_implementation",
        },
        {
            "day": 5,
            "title": "执行 prototype green 与 Godot 侧原型验证",
            "cmd": [
                "py",
                "-3",
                "scripts/python/dev_cli.py",
                "run-prototype-tdd",
                "--slug",
                slug,
                "--stage",
                "green",
                "--dotnet-target",
                "Game.Core.Tests/Game.Core.Tests.csproj",
                "--filter",
                filter_expr,
                "--gdunit-path",
                gdunit_path,
            ],
            "default_scene": default_scene,
        },
        {
            "day": 6,
            "title": "整理原型产物与验证摘要",
            "cmd": None,
            "internal_action": "packaging_summary",
        },
        {
            "day": 7,
            "title": "生成完成报告与下一步建议",
            "cmd": None,
            "internal_action": "completion_report",
        },
    ]


def _resolve_default_scene(payload: dict[str, Any]) -> str:
    slug = str(payload.get("slug") or "prototype")
    type_kit = payload.get("prototype_type_kit") if isinstance(payload.get("prototype_type_kit"), dict) else {}
    type_kit_paths = type_kit.get("paths") if isinstance(type_kit.get("paths"), dict) else {}
    for candidate in (
        str(type_kit_paths.get("default_scene") or "").strip(),
        str(type_kit_paths.get("prototype_scene") or "").strip(),
    ):
        if candidate:
            return candidate
    manifest = type_kit.get("manifest") if isinstance(type_kit.get("manifest"), dict) else {}
    manifest_paths = manifest.get("paths") if isinstance(manifest.get("paths"), dict) else {}
    default_scene = str(manifest.get("default_scene") or manifest_paths.get("default_scene") or "").strip()
    if default_scene:
        return default_scene
    pascal = _slug_to_pascal(slug)
    return f"res://Game.Godot/Prototypes/{sanitize_slug(slug)}/{pascal}Prototype.tscn"

def _collect_prototype_tdd_summary_paths(*, steps_run: list[dict[str, Any]]) -> list[str]:
    candidates: list[str] = []
    for step in steps_run:
        summary_path = str(step.get("summary_path") or "").strip()
        if summary_path:
            candidates.append(summary_path)
    return list(dict.fromkeys(candidates))


def _collect_latest_prototype_tdd_summary_paths(*, root: Path, slug: str) -> list[str]:
    logs_root = root / "logs" / "ci"
    if not logs_root.exists():
        return []

    slug_lower = sanitize_slug(slug).lower()
    by_stage: dict[str, tuple[float, str]] = {}
    for summary_path in logs_root.rglob("summary.json"):
        normalized = str(summary_path.relative_to(root)).replace("\\", "/")
        lower = normalized.lower()
        if slug_lower not in lower or "prototype-tdd" not in lower:
            continue
        payload = _read_json_file(summary_path)
        stage = str(payload.get("stage") or "").strip().lower()
        if not stage:
            if "-red/" in lower or "-red\\" in lower:
                stage = "red"
            elif "-green/" in lower or "-green\\" in lower:
                stage = "green"
            elif "-refactor/" in lower or "-refactor\\" in lower:
                stage = "refactor"
        if not stage:
            continue
        score = summary_path.stat().st_mtime
        current = by_stage.get(stage)
        if current is None or score >= current[0]:
            by_stage[stage] = (score, normalized)
    ordered = [by_stage[key][1] for key in ("red", "green", "refactor") if key in by_stage]
    return ordered


def _read_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_tdd_summaries(*, root: Path, relative_paths: list[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for relative_path in relative_paths:
        path = root / relative_path.replace("/", os.sep)
        payload = _read_json_file(path)
        if not payload:
            continue
        results.append(
            {
                "path": relative_path,
                "stage": str(payload.get("stage") or ""),
                "status": str(payload.get("status") or ""),
                "message": str(payload.get("message") or ""),
                "step_count": len(payload.get("steps") or []) if isinstance(payload.get("steps"), list) else 0,
            }
        )
    return results


def _playtest_focus_points(payload: dict[str, Any]) -> list[str]:
    defaults = [
        "首分钟是否知道目标，以及是否能快速进入最小可玩循环。",
        "操作反馈是否直接、清楚，是否能理解每次行动带来的结果。",
        "胜利 / 失败条件是否明确，失败后是否知道如何重试。",
        "地图、战斗或主场景之间的切换是否顺畅，没有明显断裂感。",
    ]
    success_criteria = [str(item).strip() for item in list(payload.get("success_criteria") or []) if str(item).strip()]
    if success_criteria:
        defaults[0] = f"优先验证成功标准是否成立：{success_criteria[0]}"
        if len(success_criteria) > 1:
            defaults[1] = f"继续验证：{success_criteria[1]}"
    return defaults


def _is_placeholder_next_step(value: Any) -> bool:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    return text in PLACEHOLDER_NEXT_STEPS


def _compact_advice_text(value: Any, *, limit: int = 48) -> str:
    text = str(value or "").strip()
    text = text.strip("()（）[]【】")
    text = re.sub(r"\s+", " ", text)
    return text[:limit].rstrip("，、；;,.。 ") if len(text) > limit else text


def _build_actionable_next_step(payload: dict[str, Any]) -> str:
    game_type = str(payload.get("game_type") or "").strip().lower()
    success_criteria = [str(item).strip() for item in list(payload.get("success_criteria") or []) if str(item).strip()]
    loop_text = _compact_advice_text(payload.get("core_gameplay_loop") or payload.get("minimum_playable_loop"), limit=72)
    feature_text = _compact_advice_text(payload.get("game_feature"), limit=72)
    win_fail_text = _compact_advice_text(payload.get("win_fail_conditions"), limit=56)

    if game_type == "rpg":
        parts = [
            "请继续把当前 RPG 原型补成一个完整首轮闭环：优先让玩家能稳定移动、触发遇敌、完成一场战斗，并在胜利后完成一次奖励 3 选 1 再返回地图。"
        ]
        if success_criteria:
            parts.append(f"完成后先重点验证“{_compact_advice_text(success_criteria[0], limit=40)}”是否真的成立。")
        if win_fail_text:
            parts.append(f"同时把“{win_fail_text}”做成玩家一眼能看懂的明确提示。")
        return " ".join(parts)

    if loop_text:
        suggestion = f"请继续把当前原型补成一个可反复试玩的最小闭环：围绕“{loop_text}”补齐关键反馈、状态切换和完成判定。"
    elif feature_text:
        suggestion = f"请继续把当前原型的核心玩法做实：围绕“{feature_text}”补齐玩家输入、结果反馈和完成判定。"
    else:
        suggestion = "请继续优化这个半成品原型：优先补齐首分钟目标提示、核心交互反馈、状态切换和明确的完成/失败判定。"

    if success_criteria:
        suggestion += f" 完成后先验证“{_compact_advice_text(success_criteria[0], limit=40)}”是否真正成立。"
    elif win_fail_text:
        suggestion += f" 同时把“{win_fail_text}”做成玩家容易理解的明确提示。"
    return suggestion


def _strip_public_markdown_noise(text: str) -> str:
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    value = value.replace("`", "")
    value = re.sub(r"[A-Za-z]:\\[^\s)>\]]+", "", value)
    value = re.sub(r"res://[^\s)>\]]+", "", value)
    value = re.sub(r"\b[\w.-]+[/\\][\w./\\-]+\b", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" -\t\r\n")


def _normalize_suggestion_sentence(text: str) -> str:
    value = _strip_public_markdown_noise(text)
    value = re.sub(r"^(?:如果你(?:要|愿意|需要)[，,]?\s*(?:我)?下一步可以|下一步(?:建议)?[：:]?|可以直接|可以继续)\s*", "", value)
    value = value.strip("，,：:;； ")
    if not value:
        return ""
    if value[-1] not in "。！？!?":
        value += "。"
    return value


def _extract_next_step_from_codex_output(text: str) -> str:
    value = str(text or "").strip()
    if not value:
        return ""

    patterns = [
        r"下一步建议[：:]\s*(.+?)(?:\n\s*\n|$)",
        r"如果你(?:要|愿意|需要)[，,]?\s*(?:我)?下一步可以(.+?)(?:\n\s*\n|$)",
        r"接下来可以(.+?)(?:\n\s*\n|$)",
    ]
    for pattern in patterns:
        matches = re.findall(pattern, value, flags=re.IGNORECASE | re.DOTALL)
        for candidate in reversed(matches):
            normalized = _normalize_suggestion_sentence(candidate)
            if normalized:
                return normalized

    paragraphs = [item.strip() for item in re.split(r"\n\s*\n", value) if item.strip()]
    for paragraph in reversed(paragraphs):
        if "下一步" not in paragraph and "如果你要" not in paragraph and "如果你愿意" not in paragraph and "接下来" not in paragraph:
            continue
        normalized = _normalize_suggestion_sentence(paragraph)
        if normalized:
            return normalized
    return ""


def _find_latest_codex_output_path(*, root: Path, slug: str) -> Path | None:
    logs_root = root / "logs" / "ci"
    if not path_exists(logs_root):
        return None
    prefix = f"prototype-implementation-{sanitize_slug(slug)}"
    candidates = [path for path in logs_root.rglob("codex-output.txt") if path.parent.name == prefix]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_mtime)


def _resolve_completion_next_step(*, root: Path, payload: dict[str, Any]) -> str:
    current = str(payload.get("next_step") or "").strip()
    if current and not _is_placeholder_next_step(current):
        return current

    slug = str(payload.get("slug") or "prototype")
    codex_output_path = _find_latest_codex_output_path(root=root, slug=slug)
    if codex_output_path and path_exists(codex_output_path):
        candidate = _extract_next_step_from_codex_output(read_text(codex_output_path, errors="ignore"))
        if candidate:
            return candidate
    return _build_actionable_next_step(payload)


def _friendly_scene_label(scene_path: str) -> str:
    value = str(scene_path or "").strip()
    if not value:
        return "未识别"
    if "DefaultRpgPrototype" in value:
        return "默认 RPG 原型主场景"
    if value.startswith("res://"):
        scene_name = Path(value.replace("res://", "")).stem
        if scene_name:
            return f"{scene_name} 场景"
    return value


def _build_tdd_stage_counts(tdd_summaries: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"red": 0, "green": 0, "refactor": 0}
    for item in tdd_summaries:
        stage = str(item.get("stage") or "").strip().lower()
        if stage in counts:
            counts[stage] += 1
    return counts


def _build_completion_summary(
    *,
    payload: dict[str, Any],
    steps_run: list[dict[str, Any]],
    tdd_summary_paths: list[str],
    prototype_spec: str,
    next_step: str,
) -> str:
    success_criteria = [str(item).strip() for item in list(payload.get("success_criteria") or []) if str(item).strip()]
    completed_steps = [step for step in steps_run if str(step.get("status") or "").strip().lower() == "ok"]
    completed_titles = [f"Step {int(step['day']):02d}：{str(step.get('title') or '').strip()}" for step in completed_steps if step.get("day")]

    lines = [
        "原型创建完成。",
        "",
        "本次完成：",
    ]
    if completed_titles:
        lines.extend(f"{index}. {title}" for index, title in enumerate(completed_titles, start=1))
    else:
        lines.append("1. 已完成当前原型路线。")

    if success_criteria:
        lines.extend([
            "",
            "成功标准回顾：",
            *[f"- {item}" for item in success_criteria[:5]],
        ])

    lines.extend([
        "",
        "验证结果：",
        f"- 已生成原型规格摘要。",
        f"- 已完成当前基线的原型验证步骤。",
    ])
    if tdd_summary_paths:
        lines.append(f"- 已整理 {len(tdd_summary_paths)} 份验证摘要。")

    lines.extend([
        "",
        "下一步建议：",
        next_step,
        "",
        "如果你同意，可以点击这条消息下方的“同意继续优化”，系统会把这条建议作为正式反馈继续提交。",
    ])
    return "\n".join(lines)


def _packaging_summary_path(*, root: Path, slug: str) -> Path:
    return root / "logs" / "ci" / "active-prototypes" / f"{sanitize_slug(slug)}.packaging.json"


def _completion_report_path(*, root: Path, slug: str) -> Path:
    return root / "logs" / "ci" / "active-prototypes" / f"{sanitize_slug(slug)}.completion.md"


def _write_packaging_summary(
    *,
    root: Path,
    payload: dict[str, Any],
    record_file: str,
    prototype_spec: str,
    steps_run: list[dict[str, Any]],
) -> tuple[str, list[str]]:
    slug = str(payload.get("slug") or "prototype")
    tdd_summary_paths = _collect_prototype_tdd_summary_paths(steps_run=steps_run)
    if not tdd_summary_paths:
        tdd_summary_paths = _collect_latest_prototype_tdd_summary_paths(root=root, slug=slug)
    tdd_summaries = _load_tdd_summaries(root=root, relative_paths=tdd_summary_paths)
    default_scene = _resolve_runtime_default_scene(root=root, payload=payload)
    prototype_artifacts = [
        record_file,
        prototype_spec,
        default_scene,
        *tdd_summary_paths,
    ]
    summary = {
        "schema_version": 1,
        "kind": "prototype-packaging-summary",
        "generated_at_utc": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "slug": sanitize_slug(slug),
        "prototype_record": record_file,
        "prototype_spec": prototype_spec,
        "default_scene": default_scene,
        "default_scene_label": _friendly_scene_label(default_scene),
        "tdd_summary_paths": tdd_summary_paths,
        "tdd_summaries": tdd_summaries,
        "tdd_stage_counts": _build_tdd_stage_counts(tdd_summaries),
        "prototype_artifacts": prototype_artifacts,
        "playtest_focus_points": _playtest_focus_points(payload),
        "steps_completed": [
            {
                "day": int(step.get("day") or 0),
                "title": str(step.get("title") or ""),
                "status": str(step.get("status") or ""),
            }
            for step in steps_run
        ],
    }
    path = _packaging_summary_path(root=root, slug=slug)
    write_json(path, summary)
    return _repo_relative_posix(root, path), tdd_summary_paths


def _write_completion_report(
    *,
    root: Path,
    payload: dict[str, Any],
    record_file: str,
    prototype_spec: str,
    packaging_summary_path: str,
    tdd_summary_paths: list[str],
    steps_run: list[dict[str, Any]],
) -> tuple[str, str]:
    slug = str(payload.get("slug") or "prototype")
    resolved_next_step = _resolve_completion_next_step(root=root, payload=payload)
    payload["next_step"] = resolved_next_step
    packaging_payload = _read_json_file(root / packaging_summary_path.replace("/", os.sep))
    report_default_scene = (
        str(packaging_payload.get("default_scene") or "").strip()
        or _resolve_runtime_default_scene(root=root, payload=payload)
        or _resolve_default_scene(payload)
    )
    summary = _build_completion_summary(
        payload=payload,
        steps_run=steps_run,
        tdd_summary_paths=tdd_summary_paths,
        prototype_spec=prototype_spec,
        next_step=resolved_next_step,
    )
    lines = [
        "# Prototype Completion Report",
        "",
        f"Slug: {sanitize_slug(slug)}",
        f"Prototype Record: {record_file}",
        f"Prototype Spec: {prototype_spec}",
        f"Packaging Summary: {packaging_summary_path}",
        f"Default Scene: {report_default_scene}",
        "",
        "## Final Summary",
        "",
        summary,
    ]
    if packaging_payload:
        lines.extend([
            "",
            "## Acceptance Snapshot",
            "",
            f"- Default Scene: {report_default_scene}",
            f"- Prototype Record: {packaging_payload.get('prototype_record') or record_file}",
            f"- Prototype Spec: {packaging_payload.get('prototype_spec') or prototype_spec}",
        ])
        focus_points = [str(item).strip() for item in list(packaging_payload.get("playtest_focus_points") or []) if str(item).strip()]
        if focus_points:
            lines.extend([
                "",
                "## Suggested Playtest Focus",
                "",
                *[f"- {item}" for item in focus_points],
            ])
    if tdd_summary_paths:
        lines.extend([
            "",
            "## Verification Summaries",
            "",
            *[f"- {item}" for item in tdd_summary_paths],
        ])
    tdd_summaries = [item for item in list(packaging_payload.get("tdd_summaries") or []) if isinstance(item, dict)]
    if tdd_summaries:
        lines.extend([
            "",
            "## Verification Snapshot",
            "",
            *[
                f"- {str(item.get('stage') or 'unknown')} · {str(item.get('status') or 'unknown')} · {str(item.get('message') or '').strip()}"
                for item in tdd_summaries
            ],
        ])
    path = _completion_report_path(root=root, slug=slug)
    write_text(path, "\n".join(lines) + "\n")
    return _repo_relative_posix(root, path), summary


def _is_existing_scaffold_rerun(day: int, output: str) -> bool:
    if int(day) != 2:
        return False
    text = str(output or "")
    return (
        "PROTOTYPE_SCENE ERROR:" in text
        and "scaffold already exists for slug=" in text
        and "pass --force to overwrite" in text
    )


def _extract_summary_path_from_output(output: str) -> str:
    text = str(output or "")
    match = re.search(r"(?:^|\s)out=([^\s]+summary\.json)", text)
    if not match:
        return ""
    return match.group(1).strip().replace("\\", "/")


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _apply_answers(payload: dict[str, Any], answers: dict[str, str]) -> dict[str, Any]:
    updated = dict(payload)
    for key, value in answers.items():
        if key.startswith("game_type_specifics."):
            specifics = updated.get("game_type_specifics") if isinstance(updated.get("game_type_specifics"), dict) else {}
            sections = [dict(item) for item in list(specifics.get("selected_sections") or []) if isinstance(item, dict)]
            target_id = key.split(".", 1)[1].strip()
            found = False
            for section in sections:
                if str(section.get("id") or "") == target_id:
                    section["answer"] = value.strip()
                    found = True
                    break
            if not found:
                sections.append({"id": target_id, "title": target_id.replace("_", " ").title(), "prompt": "", "answer": value.strip()})
            specifics["selected_sections"] = sections
            updated["game_type_specifics"] = specifics
        elif key.startswith("prototype_type_kit."):
            parts = key.split(".")
            if len(parts) >= 3:
                section_name = parts[1]
                target_id = parts[2]
                type_kit = updated.get("prototype_type_kit") if isinstance(updated.get("prototype_type_kit"), dict) else {}
                items = [dict(item) for item in list(type_kit.get(section_name) or []) if isinstance(item, dict)]
                found = False
                for item in items:
                    if str(item.get("id") or "") == target_id:
                        item["answer"] = value.strip()
                        found = True
                        break
                if not found:
                    items.append({"id": target_id, "question": target_id.replace("_", " "), "answer": value.strip()})
                type_kit[section_name] = items
                updated["prototype_type_kit"] = type_kit
        elif key == "slug":
            updated[key] = sanitize_slug(value)
        elif key == "success_criteria":
            updated[key] = _split_csv(value)
        elif key in {"scope_in", "scope_out", "related_formal_task_ids", "promote_signals", "archive_signals", "discard_signals", "evidence"}:
            updated[key] = _split_csv(value)
        else:
            updated[key] = value.strip()
    return updated


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="运行 prototype 7 天顶层编排路由（默认到 Day 5）。")
    ap.add_argument("--prototype-file", default="", help="按 TEMPLATE.md / TEMPLATE.zh-CN.md 填写后的原型记录文件路径。")
    ap.add_argument("--confirm", action="store_true", help="阅读并确认原型摘要后继续执行。")
    ap.add_argument("--set", action="append", default=[], help="当路由器提示缺失字段时，用 key=value 提供答案（可重复）。")
    ap.add_argument("--godot-bin", default="", help="进入 Day 5 的 Godot 侧验证前必填。")
    ap.add_argument("--stop-after-day", type=int, default=7, choices=[1, 2, 3, 4, 5, 6, 7], help="在指定天数后停止。")
    ap.add_argument("--resume-active", default="", help="当未重新提供文件时，从活动原型 slug 恢复。")
    ap.add_argument("--score-engine", default="deterministic", choices=["deterministic", "codex", "hybrid"], help="可选原型 intake 评分引擎。Codex 仅作软建议，不替代硬门禁。")
    ap.add_argument("--score-timeout-sec", type=int, default=180, help="可选 codex intake 评估的超时秒数。")
    ap.add_argument("--self-check", action="store_true", help="只打印计划行为，不实际执行步骤。")
    return ap


def _parse_set_args(values: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in values:
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def _resolve_file(root: Path, path_str: str) -> Path | None:
    if not str(path_str or "").strip():
        return None
    candidate = Path(path_str)
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve()


def _load_existing_active_state(root: Path, slug: str) -> dict[str, Any] | None:
    path = active_state_path(repo_root=root, slug=slug)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    configure_stdio_utf8()
    args = build_parser().parse_args(argv)
    root = repo_root()
    answers = _parse_set_args(list(args.set or []))
    prototype_file = _resolve_file(root, args.prototype_file)
    active_payload: dict[str, Any] | None = None
    if not prototype_file and args.resume_active:
        active_payload = _load_existing_active_state(root, sanitize_slug(args.resume_active))

    payload: dict[str, Any]
    file_label = ""
    if prototype_file:
        if not prototype_file.exists():
            print(f"PROTOTYPE_WORKFLOW ERROR: prototype file not found: {prototype_file}", file=sys.stderr)
            return 2
        file_label = str(prototype_file.relative_to(root)).replace("\\", "/") if prototype_file.is_relative_to(root) else str(prototype_file)
        payload = normalize_prototype_payload(parse_template_content(prototype_file.read_text(encoding="utf-8")))
    elif active_payload:
        payload = normalize_prototype_payload(active_payload.get("prototype") or {})
        file_label = active_payload.get("prototype_file") or ""
    else:
        payload = normalize_prototype_payload({})

    if answers:
        payload = normalize_prototype_payload(_apply_answers(payload, answers))
    payload = enrich_payload_with_game_type_guide(root=root, payload=payload)
    payload = enrich_payload_with_prototype_type_kit(root=root, payload=payload)
    payload = enrich_payload_with_prototype_manifest(root=root, payload=payload)
    payload = enrich_payload_with_repo_local_skill(root=root, payload=payload)
    if answers:
        payload = normalize_prototype_payload(_apply_answers(payload, answers))
        payload = enrich_payload_with_game_type_guide(root=root, payload=payload)
        payload = enrich_payload_with_prototype_type_kit(root=root, payload=payload)
        payload = enrich_payload_with_prototype_manifest(root=root, payload=payload)
        payload = enrich_payload_with_repo_local_skill(root=root, payload=payload)

    core_missing = required_field_names(payload)
    missing = core_missing + ([] if core_missing else missing_game_type_specific_question_names(payload))
    if not missing and not core_missing:
        missing = missing_prototype_type_kit_question_names(payload)
    if not prototype_file and not active_payload and not answers:
        questions = required_questions_for_missing_payload(payload)
        state = {
            "status": "awaiting-required-fields",
            "prototype_file": "",
            "prototype": payload,
            "missing_required_fields": missing,
            "questions": questions,
            "resume_hint": f"py -3 scripts/python/dev_cli.py run-prototype-workflow --set slug=<slug> --set hypothesis=<...> --set core_player_fantasy=<...> --set minimum_playable_loop=<...> --set success_criteria=<item1,item2>",
        }
        slug = payload.get("slug") or "prototype"
        path = write_active_state(repo_root=root, slug=str(slug), payload=state)
        print("PROTOTYPE_WORKFLOW 状态=需要输入")
        print(f"活动状态文件：{path.relative_to(root).as_posix()}")
        for item in questions:
            print(f" - 必填 {item['id']}：{item['prompt']}")
        return 0

    if missing:
        state = {
            "status": "awaiting-required-fields",
            "prototype_file": file_label,
            "prototype": payload,
            "missing_required_fields": missing,
            "questions": required_questions_for_missing_payload(payload),
            "resume_hint": "请使用 --set key=value 补全每个缺失必填项后重新运行。",
        }
        path = write_active_state(repo_root=root, slug=str(payload.get("slug") or "prototype"), payload=state)
        print("PROTOTYPE_WORKFLOW 状态=需要输入")
        print(f"活动状态文件：{path.relative_to(root).as_posix()}")
        print(f"缺失必填字段：{', '.join(missing)}")
        return 0

    intake_score = build_prototype_intake_score(payload)
    llm_review = build_prototype_intake_llm_review(
        payload,
        root=root,
        score_engine=str(args.score_engine),
        timeout_sec=int(args.score_timeout_sec),
    )
    if not args.confirm:
        prototype_spec = write_prototype_spec_sidecar(root=root, payload=payload, prototype_file=file_label)
        state = {
            "status": "needs-confirmation",
            "prototype_file": file_label,
            "prototype": payload,
            "missing_required_fields": [],
            "prototype_intake_score": intake_score,
            "prototype_intake_llm_review": llm_review,
            "prototype_spec": prototype_spec,
            "confirmation_summary": _build_confirmation_message(
                payload,
                file_path=file_label,
                intake_score=intake_score,
                llm_review=llm_review,
            ),
            "resume_hint": f"py -3 scripts/python/dev_cli.py run-prototype-workflow {'--prototype-file ' + file_label if file_label else '--resume-active ' + str(payload['slug'])} --confirm",
        }
        path = write_active_state(repo_root=root, slug=str(payload["slug"]), payload=state)
        print("PROTOTYPE_WORKFLOW 状态=需要确认")
        print(f"活动状态文件：{path.relative_to(root).as_posix()}")
        print(state["confirmation_summary"])
        return 0

    if args.self_check:
        guide = load_game_type_guide(root=root, payload=payload)
        state = {
            "status": "自检",
            "prototype_file": file_label,
            "prototype": payload,
            "game_type_guide": guide,
            "prototype_intake_score": intake_score,
            "prototype_intake_llm_review": llm_review,
            "planned_days": [step["day"] for step in _day_steps(payload, root=root, record_file=file_label) if int(step["day"]) <= int(args.stop_after_day)],
        }
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0

    guide = load_game_type_guide(root=root, payload=payload)
    if guide.get("path"):
        payload["game_type_guide_path"] = guide["path"]
    record_rc, record_output = _ensure_prototype_record(root, payload)
    if record_rc != 0:
        print(record_output, end="")
        return record_rc

    record_file = str(_prototype_record_path(root=root, slug=str(payload["slug"])).relative_to(root)).replace("\\", "/")
    prototype_spec = write_prototype_spec_sidecar(root=root, payload=payload, prototype_file=record_file)

    steps_run: list[dict[str, Any]] = []
    tdd_summary_paths: list[str] = []
    packaging_summary_path = ""
    completion_summary = ""
    completion_report_path = ""
    for step in _day_steps(payload, root=root, record_file=record_file):
        day = int(step["day"])
        if day == 1:
            steps_run.append({"day": day, "title": step["title"], "status": "ok", "record": record_file, "prototype_spec": prototype_spec})
        else:
            internal_action = str(step.get("internal_action") or "").strip()
            if internal_action == "packaging_summary":
                packaging_summary_path, tdd_summary_paths = _write_packaging_summary(
                    root=root,
                    payload=payload,
                    record_file=record_file,
                    prototype_spec=prototype_spec,
                    steps_run=steps_run,
                )
                steps_run.append(
                    {
                        "day": day,
                        "title": step["title"],
                        "status": "ok",
                        "packaging_summary": packaging_summary_path,
                        "tdd_summary_paths": tdd_summary_paths,
                    }
                )
                if day >= int(args.stop_after_day):
                    break
                continue
            if internal_action == "completion_report":
                if not packaging_summary_path:
                    packaging_summary_path, tdd_summary_paths = _write_packaging_summary(
                        root=root,
                        payload=payload,
                        record_file=record_file,
                        prototype_spec=prototype_spec,
                        steps_run=steps_run,
                    )
                completion_report_path, completion_summary = _write_completion_report(
                    root=root,
                    payload=payload,
                    record_file=record_file,
                    prototype_spec=prototype_spec,
                    packaging_summary_path=packaging_summary_path,
                    tdd_summary_paths=tdd_summary_paths,
                    steps_run=steps_run,
                )
                steps_run.append(
                    {
                        "day": day,
                        "title": step["title"],
                        "status": "ok",
                        "completion_report": completion_report_path,
                    }
                )
                if day >= int(args.stop_after_day):
                    break
                continue
            if internal_action == "codex_implementation":
                rc, output = _run_day4_codex_implementation(root=root, payload=payload, record_file=record_file)
                step_result = {"day": day, "title": step["title"], "status": "ok" if rc == 0 else "fail"}
                steps_run.append(step_result)
                if rc != 0:
                    print(output, end="")
                    return rc
                continue
            cmd = [str(item) for item in (step["cmd"] or [])]
            if day == 5:
                if not str(args.godot_bin or "").strip():
                    state = {
                        "status": "awaiting-required-fields",
                        "prototype_file": file_label,
                        "prototype": payload,
                        "missing_required_fields": ["godot_bin"],
                        "questions": [{"id": "godot_bin", "prompt": "进入第 5 天前需要提供 Godot 可执行文件路径"}],
                        "steps_run": steps_run,
                    }
                    path = write_active_state(repo_root=root, slug=str(payload["slug"]), payload=state)
                    print("PROTOTYPE_WORKFLOW 状态=需要输入")
                    print(f"活动状态文件：{path.relative_to(root).as_posix()}")
                    print("缺失必填字段：godot_bin")
                    return 0
                cmd += ["--godot-bin", str(args.godot_bin)]
            rc, output = _run(cmd, cwd=root)
            if rc != 0 and _is_existing_scaffold_rerun(day, output):
                steps_run.append(
                    {
                        "day": day,
                        "title": step["title"],
                        "status": "skipped",
                        "reason": "prototype_scaffold_already_exists",
                        "cmd": cmd,
                    }
                )
                continue
            step_result = {"day": day, "title": step["title"], "status": "ok" if rc == 0 else "fail", "cmd": cmd}
            if day in {3, 4, 5}:
                summary_path = _extract_summary_path_from_output(output)
                if summary_path:
                    step_result["summary_path"] = summary_path
            steps_run.append(step_result)
            if rc != 0:
                print(output, end="")
                return rc
        if day >= int(args.stop_after_day):
            break

    state = {
        "status": "completed-through-day",
        "prototype_file": file_label,
        "prototype": payload,
        "prototype_intake_score": intake_score,
        "prototype_intake_llm_review": llm_review,
        "prototype_spec": prototype_spec,
        "completed_through_day": int(args.stop_after_day),
        "steps_run": steps_run,
    }
    if int(args.stop_after_day) >= 6:
        state["tdd_summary_paths"] = tdd_summary_paths
        state["packaging_summary"] = packaging_summary_path
    if int(args.stop_after_day) >= 7:
        state["completion_summary"] = completion_summary
        state["completion_report"] = completion_report_path
    path = write_active_state(repo_root=root, slug=str(payload["slug"]), payload=state)
    print(f"PROTOTYPE_WORKFLOW 状态=完成 day={args.stop_after_day} 活动状态={path.relative_to(root).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
