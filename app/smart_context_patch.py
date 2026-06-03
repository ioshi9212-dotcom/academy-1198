from __future__ import annotations

from typing import Any, Dict

from app.context_planner import (
    build_context_plan,
    focused_knowledge,
    focused_relationships,
    make_context_load_chain,
)


def patch_main_context(ns: Dict[str, Any]) -> None:
    """Patch main.build_turn_context without rewriting the whole API file."""

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

        files = plan["files"]
        contents: Dict[str, Any] = {}
        if req.include_file_contents:
            for path in files:
                contents[path] = ns["trimmed"](ns["read_project_file"](path, session_id))

        scene = state.get("scene") if isinstance(state.get("scene"), dict) else {}
        start_commands = {cmd.replace("ё", "е") for cmd in ns["START_COMMANDS"]}

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
                "character_ids": plan["character_ids"],
                "character_files": plan["character_files"],
                "profile_files": plan["profile_files"],
            },
            "context_load_chain": make_context_load_chain(plan),
            "focused_knowledge": focused_knowledge(runtime_json_file, session_id, plan["character_ids"]),
            "focused_relationships": focused_relationships(runtime_json_file, session_id, plan["character_ids"]),
            "required_files": files,
            "required_file_contents": contents,
            "turn_counter": ns["story_lines"](session_id).get("turn_counter", {}),
            "actions_contract": {
                "default_context": "POST /api/v1/turn/context",
                "session_turn_contract": "POST /api/v1/sessions/{session_id}/turn-contract",
                "submit_result": "POST /api/v1/sessions/{session_id}/turn-result",
                "apply_turn_result": "POST /api/v1/sessions/{session_id}/apply-turn-result",
                "note": "If this response is returned, Action API is available.",
            },
            "checks": [
                "Read gpt/scene_format.md before scene output.",
                "Use scene_roster for active and nearby characters.",
                "Use context_load_chain and required_files; do not load everything.",
                "Use focused_knowledge before NPC claims.",
                "Use focused_relationships before relationship tension or open threads.",
                "Do not write player decisions, emotions, or replies for Akira.",
                "After scene output, call submitTurnResult or applyTurnResult to persist state.",
            ],
        }

    ns["build_turn_context"] = smart_build_turn_context
