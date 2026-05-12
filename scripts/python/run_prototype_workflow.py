#!/usr/bin/env python3
"""Top-level router for the prototype 7-day playable Godot workflow."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def today_str() -> str:
    return dt.date.today().isoformat()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, content: str) -> None:
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8", newline="\n")


def write_json(path: Path, payload: object) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
        stripped = line.strip()
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
        "evidence": list(raw.get("evidence") or ["TBD"]),
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
    return normalized


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
            if "round 1" in heading or "gameplay flow" in heading or "玩法" in heading:
                current_round = "gameplay_flow"
            elif "round 2" in heading or "scene ui" in heading or "场景 ui" in heading:
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
    merged.extend(by_id.values())
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
    updated["prototype_type_kit"] = type_kit
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
    return updated


def _repo_relative_posix(root: Path, path: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


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


def _day_steps(payload: dict[str, Any]) -> list[dict[str, Any]]:
    slug = str(payload["slug"])
    filter_expr = str(payload.get("test_filter") or slug.replace("-", "").replace("_", ""))
    gdunit_path = str(payload.get("gdunit_path") or f"tests/Prototype/{''.join(part.title() for part in slug.split('-'))}")
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
            "title": "执行 prototype green",
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
            ],
        },
        {
            "day": 5,
            "title": "执行 Godot 侧原型验证",
            "cmd": [
                "py",
                "-3",
                "scripts/python/dev_cli.py",
                "run-prototype-tdd",
                "--slug",
                slug,
                "--stage",
                "green",
                "--gdunit-path",
                gdunit_path,
            ],
        },
    ]


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
    ap.add_argument("--stop-after-day", type=int, default=5, choices=[1, 2, 3, 4, 5], help="在指定天数后停止。")
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
            "planned_days": [step["day"] for step in _day_steps(payload) if int(step["day"]) <= int(args.stop_after_day)],
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
    for step in _day_steps(payload):
        day = int(step["day"])
        if day == 1:
            steps_run.append({"day": day, "title": step["title"], "status": "ok", "record": record_file, "prototype_spec": prototype_spec})
        else:
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
            steps_run.append({"day": day, "title": step["title"], "status": "ok" if rc == 0 else "fail", "cmd": cmd})
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
    path = write_active_state(repo_root=root, slug=str(payload["slug"]), payload=state)
    print(f"PROTOTYPE_WORKFLOW 状态=完成 day={args.stop_after_day} 活动状态={path.relative_to(root).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
