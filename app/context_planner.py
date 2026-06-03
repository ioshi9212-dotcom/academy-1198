from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, List

ReadText = Callable[[str, str], str]
FileExists = Callable[[str, str], bool]
ReadRuntimeJson = Callable[[str, str, Any], Any]

MAX_REQUIRED_FILES = 45

CHARACTER_ALIASES = {
    "акира": "akira",
    "ливия": "livia_cross",
    "кир": "kir_knox",
    "райден": "raiden_sterling",
    "рейден": "raiden_sterling",
    "хару": "haru_foster",
    "джун": "jun_carter",
    "рэй": "ray_carter",
    "рей": "ray_carter",
    "самуэль": "samuel_sterling",
    "киара": "kiara_volt",
    "ноа": "noa_rian",
    "вероника": "veronica_ellard",
    "дэниел": "daniel_dante_weiss",
    "данте": "daniel_dante_weiss",
    "элиас": "elias_aster",
    "селин": "seline_aster",
}

BASE_CONTEXT_FILES = [
    "gpt/engine_prompt.md",
    "gpt/scene_format.md",
    "canon/source_usage_rules.md",
    "canon/novella_goal.md",
    "canon/calendar_1198.md",
    "canon/story_chain_1198.md",
    "state/current_state.json",
    "state/story_lines.json",
    "state/knowledge_state.json",
    "state/relationships.json",
    "characters/character_id_index.md",
]

OPTIONAL_STATE_FILES = {
    "reputation": "state/reputation_state.json",
    "power": "state/power_state.json",
    "rumors": "state/rumors_state.json",
    "inventory": "state/inventory_state.json",
    "future": "state/future_locks_progress.json",
    "story_extensions": "state/story_lines_extensions.md",
}

TOPIC_FILES = {
    "academy": ["canon/academy_rules_index.md", "canon/academy_discipline_ratings_admissions.md"],
    "combat": ["canon/academy_combat_and_weapon_rules.md", "canon/academy_energy_application_rules.md"],
    "energy": ["canon/academy_energy_application_rules.md"],
    "bond": ["canon/hidden/akira_raiden_reincarnation_link.md"],
    "timeline": ["canon/timeline_1198_1206.md"],
}

REPO_PATH_RE = re.compile(r"`?((?:gpt|canon|characters|state|templates)/[A-Za-z0-9_./\-]+\.(?:md|json|txt))`?")


def unique(values: List[str]) -> List[str]:
    result: List[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def normalized_text(text: str) -> str:
    return " ".join(str(text or "").strip().lower().replace("ё", "е").split())


def text_has(text: str, words: List[str]) -> bool:
    lowered = normalized_text(text)
    return any(word in lowered for word in words)


def scene_character_ids(state: Dict[str, Any], user_input: str, character_paths: Dict[str, str]) -> List[str]:
    player = state.get("player_character") if isinstance(state.get("player_character"), dict) else {}
    ids: List[str] = [str(player.get("id") or "akira")]
    ids.extend(str(item) for item in state.get("active_characters", []) or [])
    ids.extend(str(item) for item in state.get("nearby_or_possible", []) or [])
    lowered = normalized_text(user_input)
    for alias, cid in CHARACTER_ALIASES.items():
        if alias in lowered:
            ids.append(cid)
    return [cid for cid in unique(ids) if cid in character_paths or cid == "akira"]


def optional_files_for_turn(state: Dict[str, Any], user_input: str, character_ids: List[str]) -> Dict[str, Any]:
    scene = state.get("scene") if isinstance(state.get("scene"), dict) else {}
    location = state.get("location") if isinstance(state.get("location"), dict) else {}
    text = normalized_text("\n".join([user_input, str(scene), str(location), " ".join(character_ids)]))
    topic_files: List[str] = []
    state_files: Dict[str, str] = {}

    if text_has(text, ["академ", "регистрац", "инструктаж", "общежит", "комнат", "рейтинг", "мед", "корпус", "двор"]):
        topic_files.extend(TOPIC_FILES["academy"])
    if text_has(text, ["бой", "спарр", "оруж", "стрель", "трениров", "баскет", "полоса", "физ"]):
        topic_files.extend(TOPIC_FILES["combat"])
        state_files["power"] = OPTIONAL_STATE_FILES["power"]
    if text_has(text, ["энерг", "сила", "простран", "эхо", "кайрос", "барьер", "синхрон", "датчик"]):
        topic_files.extend(TOPIC_FILES["energy"])
        state_files["power"] = OPTIONAL_STATE_FILES["power"]
    if "akira" in character_ids and "raiden_sterling" in character_ids:
        topic_files.extend(TOPIC_FILES["bond"])
    if text_has(text, ["слух", "толпа", "смотр", "репутац", "социал"]):
        state_files["reputation"] = OPTIONAL_STATE_FILES["reputation"]
        state_files["rumors"] = OPTIONAL_STATE_FILES["rumors"]
    if text_has(text, ["предмет", "вещ", "карман", "сумк", "нож", "телефон", "браслет", "форма"]):
        state_files["inventory"] = OPTIONAL_STATE_FILES["inventory"]
    if text_has(text, ["дата", "день", "завтра", "вчера", "август", "сентябр", "пропустить", "расписан"]):
        topic_files.extend(TOPIC_FILES["timeline"])
        state_files["story_extensions"] = OPTIONAL_STATE_FILES["story_extensions"]
    if text_has(text, ["будущ", "нить", "обещ", "вызов", "долж"]):
        state_files["future"] = OPTIONAL_STATE_FILES["future"]
    return {"topic_files": unique(topic_files), "state_files": state_files}


def extract_repo_paths(text: str) -> List[str]:
    paths = [match.group(1).rstrip(".,);]") for match in REPO_PATH_RE.finditer(text or "")]
    return unique(paths)


def should_follow_link(path: str, user_input: str, character_ids: List[str]) -> bool:
    lower = path.lower()
    text = normalized_text(user_input + " " + " ".join(character_ids) + " " + lower)
    if lower.startswith("state/"):
        return False
    if "/hidden/" in lower or "hidden" in lower:
        return ("akira" in character_ids and "raiden_sterling" in character_ids) or text_has(text, ["связ", "райден", "эхо", "кайрос"])
    if "/powers/" in lower or "power" in lower or "energy" in lower:
        return text_has(text, ["энерг", "сила", "бой", "спарр", "трениров", "простран", "эхо", "датчик"])
    if "/past/" in lower:
        return text_has(text, ["прошл", "школ", "стар", "кир", "ливи", "ашер", "кай"])
    if "/social/" in lower:
        return text_has(text, ["социал", "слух", "волос", "толпа", "смотр", "репутац"])
    if "/habits/" in lower or "/knowledge/" in lower or "/locks/" in lower or "/variants/" in lower:
        return True
    return False


def expand_from_links(
    files: List[str],
    user_input: str,
    character_ids: List[str],
    session_id: str,
    file_exists: FileExists,
    read_file: ReadText,
) -> Dict[str, List[str]]:
    required = unique(files)
    linked: List[str] = []
    skipped: List[str] = []
    for path in list(required):
        if not file_exists(path, session_id):
            continue
        for ref in extract_repo_paths(read_file(path, session_id)):
            if ref in required:
                continue
            if not file_exists(ref, session_id):
                skipped.append(ref)
                continue
            if should_follow_link(ref, user_input, character_ids):
                linked.append(ref)
                required.append(ref)
            else:
                skipped.append(ref)
            if len(required) >= MAX_REQUIRED_FILES:
                break
        if len(required) >= MAX_REQUIRED_FILES:
            break
    return {"files": unique(required)[:MAX_REQUIRED_FILES], "linked_files": unique(linked), "skipped_linked_files": unique(skipped)}


def focused_knowledge(read_runtime_json: ReadRuntimeJson, session_id: str, character_ids: List[str]) -> Dict[str, Any]:
    data = read_runtime_json("knowledge_state.json", session_id, {}) or {}
    chars = data.get("character_knowledge") if isinstance(data.get("character_knowledge"), dict) else {}
    hidden = data.get("hidden_truths") if isinstance(data.get("hidden_truths"), dict) else {}
    scene_set = set(character_ids)
    relevant_hidden: Dict[str, Any] = {}
    for item_id, item in hidden.items():
        if not isinstance(item, dict):
            continue
        linked_people = set(item.get("known_by", []) or []) | set(item.get("partly_known_by", []) or []) | set(item.get("unknown_to", []) or [])
        if linked_people & scene_set:
            relevant_hidden[item_id] = item
    return {
        "rules": data.get("rules", {}),
        "global_public_knowledge": data.get("global_public_knowledge", {}),
        "character_knowledge": {cid: chars.get(cid, {}) for cid in character_ids},
        "scene_hidden_boundaries": relevant_hidden,
    }


def focused_relationships(read_runtime_json: ReadRuntimeJson, session_id: str, character_ids: List[str]) -> Dict[str, Any]:
    data = read_runtime_json("relationships.json", session_id, {}) or {}
    rels = data.get("relationships") if isinstance(data.get("relationships"), dict) else {}
    scene_set = set(character_ids)
    focused: Dict[str, Any] = {}
    for rel_id, rel in rels.items():
        if not isinstance(rel, dict):
            continue
        ids = set(rel.get("ids", []) or [])
        known_by = set(rel.get("known_by", []) or [])
        if ids & scene_set or known_by & scene_set:
            focused[rel_id] = rel
    return {"rules": data.get("rules", {}), "relationships": focused}


def build_context_plan(
    state: Dict[str, Any],
    mode: str,
    user_input: str,
    session_id: str,
    character_paths: Dict[str, str],
    file_exists: FileExists,
    read_file: ReadText,
) -> Dict[str, Any]:
    character_ids = scene_character_ids(state, user_input, character_paths)
    character_files = [character_paths[cid] for cid in character_ids if cid in character_paths]
    player = state.get("player_character") if isinstance(state.get("player_character"), dict) else {}
    profile = player.get("current_behavior_profile") if isinstance(player, dict) else None
    profile_files = [profile] if isinstance(profile, str) else []
    optional = optional_files_for_turn(state, user_input, character_ids) if mode == "play" else {"topic_files": [], "state_files": {}}

    files = unique(BASE_CONTEXT_FILES + character_files + profile_files + list(optional["topic_files"]) + list(optional["state_files"].values()))
    files = [path for path in files if file_exists(path, session_id)]
    expanded = expand_from_links(files, user_input, character_ids, session_id, file_exists, read_file) if mode == "play" else {"files": files, "linked_files": [], "skipped_linked_files": []}

    return {
        "files": expanded["files"],
        "character_ids": character_ids,
        "character_files": [path for path in character_files if file_exists(path, session_id)],
        "profile_files": [path for path in profile_files if file_exists(path, session_id)],
        "topic_files": [path for path in optional["topic_files"] if file_exists(path, session_id)],
        "conditional_state_files": optional["state_files"],
        "linked_files": expanded["linked_files"],
        "skipped_linked_files": expanded["skipped_linked_files"],
    }


def make_context_load_chain(plan: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "base_files": BASE_CONTEXT_FILES,
        "character_files": plan["character_files"],
        "profile_files": plan["profile_files"],
        "linked_files_from_cards": plan["linked_files"],
        "topic_files": plan["topic_files"],
        "conditional_state_files": plan["conditional_state_files"],
        "skipped_linked_files": plan["skipped_linked_files"],
        "rule": "Use required_files in order. Do not load the whole repository. Follow only linked files included here.",
    }
