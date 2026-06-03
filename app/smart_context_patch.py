from __future__ import annotations

import re
from typing import Any, Dict, List

from app.context_planner import (
    build_context_plan,
    focused_knowledge,
    focused_relationships,
    make_context_load_chain,
)

CALENDAR_FILE = "canon/calendar_1198.md"
MONTHS_RU = {
    "01": "января",
    "02": "февраля",
    "03": "марта",
    "04": "апреля",
    "05": "мая",
    "06": "июня",
    "07": "июля",
    "08": "августа",
    "09": "сентября",
    "10": "октября",
    "11": "ноября",
    "12": "декабря",
}


def is_hidden_file(path: str) -> bool:
    lower = path.lower()
    return "/hidden/" in lower or "hidden" in lower


def filter_hidden_without_raiden(plan: Dict[str, Any]) -> Dict[str, Any]:
    character_ids = plan.get("character_ids", []) or []
    if "raiden_sterling" in character_ids:
        return plan

    clean = dict(plan)
    for key in ["files", "linked_files", "topic_files", "skipped_linked_files"]:
        values = clean.get(key, []) or []
        clean[key] = [path for path in values if not is_hidden_file(str(path))]
    return clean


def filter_calendar_file(plan: Dict[str, Any]) -> Dict[str, Any]:
    clean = dict(plan)
    for key in ["files", "linked_files", "topic_files", "skipped_linked_files"]:
        values = clean.get(key, []) or []
        clean[key] = [path for path in values if path != CALENDAR_FILE]
    return clean


def clean_context_chain(chain: Dict[str, Any], has_raiden: bool) -> Dict[str, Any]:
    clean = dict(chain)
    for key in ["base_files", "linked_files_from_cards", "topic_files", "skipped_linked_files"]:
        values = clean.get(key, []) or []
        values = [path for path in values if path != CALENDAR_FILE]
        if not has_raiden:
            values = [path for path in values if not is_hidden_file(str(path))]
        clean[key] = values
    clean["calendar_rule"] = "Full calendar file is not loaded. Use focused_calendar for the current date only."
    clean["hidden_rule"] = "Hidden files are included only when raiden_sterling is present in scene_roster."
    return clean


def clean_focused_knowledge(data: Dict[str, Any], has_raiden: bool) -> Dict[str, Any]:
    if has_raiden:
        return data
    clean = dict(data)
    clean["scene_hidden_boundaries"] = {}
    return clean


def clean_focused_relationships(data: Dict[str, Any], has_raiden: bool) -> Dict[str, Any]:
    if has_raiden:
        return data
    clean = dict(data)
    relationships = clean.get("relationships", {}) or {}
    filtered: Dict[str, Any] = {}
    for rel_id, rel in relationships.items():
        if not isinstance(rel, dict):
            continue
        marker = " ".join([
            str(rel_id),
            str(rel.get("type", "")),
            str(rel.get("hidden_status", "")),
            str(rel.get("source_ref", "")),
        ]).lower()
        if "hidden" in marker:
            continue
        filtered[rel_id] = rel
    clean["relationships"] = filtered
    return clean


def focused_calendar(current_date: str | None, calendar_text: str) -> Dict[str, Any]:
    if not current_date:
        return {"date": None, "source": CALENDAR_FILE, "entry": None}

    parts = str(current_date).split("-")
    if len(parts) < 3:
        return {"date": current_date, "source": CALENDAR_FILE, "entry": None}

    month = MONTHS_RU.get(parts[1])
    day = str(int(parts[2])) if parts[2].isdigit() else parts[2]
    if not month or not calendar_text:
        return {"date": current_date, "source": CALENDAR_FILE, "entry": None}

    pattern = re.compile(rf"^###\s+{re.escape(day)}\s+{re.escape(month)}\b.*$", re.MULTILINE | re.IGNORECASE)
    match = pattern.search(calendar_text)
    if not match:
        return {"date": current_date, "source": CALENDAR_FILE, "entry": None}

    next_match = re.search(r"^###\s+", calendar_text[match.end():], re.MULTILINE)
    end = match.end() + next_match.start() if next_match else len(calendar_text)
    entry = calendar_text[match.start():end].strip()
    return {"date": current_date, "source": CALENDAR_FILE, "entry": entry[:5000]}


def patch_main_context(ns: Dict[str, Any]) -> None:
    """Patch runtime context to behave like the old academy: context first, no mandatory turn saving action."""

    original_actions_schema = ns.get("actions_schema_json")

    def context_only_actions_schema() -> Dict[str, Any]:
        schema = original_actions_schema() if callable(original_actions_schema) else {}
        paths = schema.get("paths") if isinstance(schema.get("paths"), dict) else {}
        paths.pop("/api/v1/sessions/{session_id}/turn-result", None)
        paths.pop("/api/v1/sessions/{session_id}/apply-turn-result", None)
        info = schema.get("info") if isinstance(schema.get("info"), dict) else {}
        info["version"] = "1.3.1-context-only"
        schema["info"] = info
        schema["paths"] = paths
        return schema

    def runtime_json_file(filename: str, session_id: str, default: Any) -> Any:
        return ns["read_json"](ns["runtime_state_path"](session_id, filename), default)

    def smart_build_turn_context(session_id: str, req: Any) -> Dict[str, Any]:
        ns["ensure_session_state"](session_id)
        mode = ns["classify_mode"](req)
        state = ns["current_state"](session_id)
        state.setdefault("session_id", ns["safe_session_id"](session_id))

        plan = build_context_plan(
            state=state,
            mode=mode,
            user_input=req.user_input,
            session_id=session_id,
            character_paths=ns["CHARACTER_PATHS"],
            file_exists=ns["file_exists_for_context"],
            read_file=ns["read_project_file"],
        )
        plan = filter_calendar_file(filter_hidden_without_raiden(plan))

        character_ids = plan["character_ids"]
        has_raiden = "raiden_sterling" in character_ids
        files = plan["files"]

        contents: Dict[str, Any] = {}
        if req.include_file_contents:
            for path in files:
                contents[path] = ns["trimmed"](ns["read_project_file"](path, session_id))

        scene = state.get("scene") if isinstance(state.get("scene"), dict) else {}
        start_commands = {cmd.replace("ё", "е") for cmd in ns["START_COMMANDS"]}
        calendar_text = ns["read_project_file"](CALENDAR_FILE, session_id) if ns["file_exists_for_context"](CALENDAR_FILE, session_id) else ""

        knowledge = focused_knowledge(runtime_json_file, session_id, character_ids)
        relationships = focused_relationships(runtime_json_file, session_id, character_ids)
        chain = clean_context_chain(make_context_load_chain(plan), has_raiden)

        return {
            "success": True,
            "project": ns["PROJECT_SLUG"],
            "session_id": ns["safe_session_id"](session_id),
            "mode": mode,
            "is_game_turn": mode == "play",
            "can_generate_scene": mode == "play",
            "response_mode": "play_scene" if mode == "play" else "technical_response",
            "start_requested": ns["normalized_text"](req.user_input) in start_commands,
            "current_scene_anchor": {
                "date": state.get("date"),
                "time_of_day": state.get("time_of_day"),
                "scene_id": scene.get("scene_id"),
                "phase": scene.get("phase"),
                "location": state.get("location"),
                "active_characters": state.get("active_characters", []),
                "nearby_or_possible": state.get("nearby_or_possible", []),
            },
            "scene_roster": {
                "character_ids": character_ids,
                "character_files": plan["character_files"],
                "profile_files": plan["profile_files"],
            },
            "context_load_chain": chain,
            "focused_calendar": focused_calendar(state.get("date"), calendar_text),
            "focused_knowledge": clean_focused_knowledge(knowledge, has_raiden),
            "focused_relationships": clean_focused_relationships(relationships, has_raiden),
            "required_files": files,
            "required_file_contents": contents,
            "turn_counter": ns["story_lines"](session_id).get("turn_counter", {}),
            "actions_contract": {
                "default_context": "POST /api/v1/turn/context",
                "read_file": "GET /api/v1/files/{file_path}",
                "save_turn_result": "not exposed in GPT Actions; scene output is the user-facing result",
                "note": "Generate the full scene after this context. Do not call a save action instead of answering.",
            },
            "checks": [
                "Read gpt/scene_format.md before scene output.",
                "Use focused_calendar for the current date only; do not load full calendar.",
                "Hidden files are available only when raiden_sterling is in scene_roster.",
                "Use scene_roster for active and nearby characters.",
                "Use context_load_chain and required_files; do not load everything.",
                "Use focused_knowledge before NPC claims.",
                "Use focused_relationships before relationship tension or open threads.",
                "Do not write player decisions, emotions, or replies for Akira.",
                "Return the full user-facing scene. Never replace it with a save summary.",
            ],
        }

    ns["actions_schema_json"] = context_only_actions_schema
    ns["build_turn_context"] = smart_build_turn_context
