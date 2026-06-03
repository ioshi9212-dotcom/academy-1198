from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

APP_ROOT = Path(__file__).resolve().parents[1]
PROJECT_SLUG = os.getenv("PROJECT_SLUG", "academy-1198")
DEFAULT_SESSION_ID = os.getenv("DEFAULT_SESSION_ID", "academy_1198_start")
DEFAULT_PUBLIC_BASE_URL = "https://academy-1198-production.up.railway.app"
MAX_FILE_CHARS = int(os.getenv("MAX_FILE_CHARS", "18000"))

STATE_FILES = [
    "current_state.json",
    "story_lines.json",
    "relationships.json",
    "knowledge_state.json",
    "reputation_state.json",
    "power_state.json",
    "rumors_state.json",
    "inventory_state.json",
    "future_locks_progress.json",
]

CHARACTER_PATHS = {
    "akira": "characters/main/akira.md",
    "livia_cross": "characters/main/livia_cross.md",
    "kir_knox": "characters/main/kir_knox.md",
    "raiden_sterling": "characters/main/raiden_sterling.md",
    "haru_foster": "characters/main/haru_foster.md",
    "jun_carter": "characters/main/jun_carter.md",
    "ray_carter": "characters/main/ray_carter.md",
    "samuel_sterling": "characters/main/samuel_sterling.md",
    "kiara_volt": "characters/main/kiara_volt.md",
    "noa_rian": "characters/main/noa_rian.md",
    "veronica_ellard": "characters/main/veronica_ellard.md",
    "daniel_dante_weiss": "characters/main/daniel_dante_weiss.md",
    "elias_aster": "characters/main/elias_seline_aster.md",
    "seline_aster": "characters/main/elias_seline_aster.md",
}

BASE_CONTEXT_FILES = [
    "gpt/engine_prompt.md",
    "canon/source_usage_rules.md",
    "canon/calendar_1198.md",
    "canon/timeline_1198_1206.md",
    "canon/story_chain_1198.md",
    "state/current_state.json",
    "state/story_lines.json",
    "state/story_lines_extensions.md",
    "state/relationships.json",
    "state/knowledge_state.json",
    "state/reputation_state.json",
    "state/power_state.json",
    "state/rumors_state.json",
    "state/inventory_state.json",
    "state/future_locks_progress.json",
    "characters/character_id_index.md",
]

START_COMMANDS = {"начнем", "начнём", "начинай", "старт", "start", "begin"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def running_on_railway() -> bool:
    return any(os.getenv(key) for key in ("RAILWAY_ENVIRONMENT", "RAILWAY_PROJECT_ID", "RAILWAY_SERVICE_ID"))


def resolve_data_dir() -> Path:
    default_dir = "/data" if running_on_railway() else "./data"
    return Path(os.getenv("RAILWAY_VOLUME_MOUNT_PATH") or os.getenv("DATA_DIR") or default_dir)


def normalize_base_url(value: Optional[str]) -> str:
    if not value:
        return ""
    value = value.strip().rstrip("/")
    if not value:
        return ""
    if value.startswith(("http://", "https://")):
        return value
    return f"https://{value}"


def resolve_public_base_url() -> str:
    return (
        normalize_base_url(os.getenv("PUBLIC_BASE_URL"))
        or normalize_base_url(os.getenv("RAILWAY_PUBLIC_DOMAIN"))
        or DEFAULT_PUBLIC_BASE_URL
    )


DATA_DIR = resolve_data_dir()
SESSIONS_DIR = DATA_DIR / "sessions"
PUBLIC_BASE_URL = resolve_public_base_url()

app = FastAPI(
    title=f"{PROJECT_SLUG} API",
    version="1.2.0",
    description="Railway API for Academy 1198 state, repository context, volume persistence, and GPT Actions.",
)


class CreateSessionRequest(BaseModel):
    session_id: Optional[str] = Field(default=None, description="Optional session id. If omitted, default session is used.")
    reset: bool = False


class TurnContextRequest(BaseModel):
    user_input: str = Field(..., description="User message or technical request.")
    mode: Literal["play", "technical", "audit", "transfer"] = "play"
    include_file_contents: bool = True
    client_context: Optional[Dict[str, Any]] = None


class TurnResultRequest(BaseModel):
    scene_id: str = "scene"
    scene_text: str = ""
    technical: bool = False
    state_patches: Dict[str, Any] = Field(default_factory=dict)


class ApplyTurnResultRequest(BaseModel):
    scene_id: Optional[str] = None
    scene_text: Optional[str] = None
    technical: bool = False
    state_patches: Dict[str, Any] = Field(default_factory=dict)
    current_state_changes: Dict[str, Any] = Field(default_factory=dict)
    story_lines_changes: Dict[str, Any] = Field(default_factory=dict)
    relationship_changes: Dict[str, Any] = Field(default_factory=dict)
    knowledge_changes: Dict[str, Any] = Field(default_factory=dict)
    reputation_changes: Dict[str, Any] = Field(default_factory=dict)
    rumor_changes: Dict[str, Any] = Field(default_factory=dict)
    inventory_changes: Dict[str, Any] = Field(default_factory=dict)
    power_changes: Dict[str, Any] = Field(default_factory=dict)
    future_locks_changes: Dict[str, Any] = Field(default_factory=dict)


def safe_session_id(session_id: str) -> str:
    safe = "".join(ch for ch in session_id if ch.isalnum() or ch in "-_")
    return safe or DEFAULT_SESSION_ID


def safe_repo_path(path: str) -> str:
    normalized = path.replace("\\", "/").strip().lstrip("/")
    parts = [part for part in normalized.split("/") if part]
    if not parts or any(part == ".." for part in parts):
        raise HTTPException(status_code=400, detail="Unsafe or empty path")
    return "/".join(parts)


def session_dir(session_id: str = DEFAULT_SESSION_ID) -> Path:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = SESSIONS_DIR / safe_session_id(session_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_text(path: Path, default: str = "") -> str:
    if not path.exists():
        return default
    return path.read_text(encoding="utf-8")


def read_json(path: Path, default: Any) -> Any:
    text = read_text(path)
    if not text:
        return default
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return default


def write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp") as tmp:
        json.dump(data, tmp, ensure_ascii=False, indent=2)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def append_jsonl(path: Path, item: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")


def deep_merge(base: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def repo_path(path: str) -> Path:
    return APP_ROOT / safe_repo_path(path)


def runtime_state_path(session_id: str, filename: str) -> Path:
    return session_dir(session_id) / filename


def ensure_session_state(session_id: str = DEFAULT_SESSION_ID, reset: bool = False) -> Path:
    sdir = session_dir(session_id)
    for filename in STATE_FILES:
        dst = sdir / filename
        src = APP_ROOT / "state" / filename
        if src.exists() and (reset or not dst.exists()):
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return sdir


def read_project_file(path: str, session_id: str = DEFAULT_SESSION_ID) -> str:
    safe = safe_repo_path(path)
    if safe.startswith("state/"):
        runtime = runtime_state_path(session_id, Path(safe).name)
        if runtime.exists():
            return read_text(runtime)
    return read_text(repo_path(safe))


def file_exists_for_context(path: str, session_id: str = DEFAULT_SESSION_ID) -> bool:
    safe = safe_repo_path(path)
    if safe.startswith("state/") and runtime_state_path(session_id, Path(safe).name).exists():
        return True
    return repo_path(safe).exists()


def trimmed(text: str) -> Dict[str, Any]:
    if len(text) <= MAX_FILE_CHARS:
        return {"content": text, "truncated": False, "chars": len(text)}
    return {"content": text[:MAX_FILE_CHARS], "truncated": True, "chars": len(text)}


def current_state(session_id: str = DEFAULT_SESSION_ID) -> Dict[str, Any]:
    ensure_session_state(session_id)
    state = read_json(runtime_state_path(session_id, "current_state.json"), None)
    if isinstance(state, dict):
        return state
    return {"schema": "current_state_v1", "project": PROJECT_SLUG, "session_id": safe_session_id(session_id)}


def story_lines(session_id: str = DEFAULT_SESSION_ID) -> Dict[str, Any]:
    ensure_session_state(session_id)
    data = read_json(runtime_state_path(session_id, "story_lines.json"), {})
    return data if isinstance(data, dict) else {}


def normalized_text(text: str) -> str:
    return " ".join(text.strip().lower().replace("ё", "е").split())


def classify_mode(req: TurnContextRequest) -> str:
    if req.mode != "play":
        return req.mode
    text = normalized_text(req.user_input)
    markers = [
        "github", "railway", "volume", "волум", "api", "openapi", "deploy", "деплой",
        "schema", "схема", "техничес", "не продолжай сцену", "репозитор", "почини",
    ]
    return "technical" if any(marker in text for marker in markers) else "play"


def build_file_list(state: Dict[str, Any], mode: str, session_id: str) -> List[str]:
    files: List[str] = []
    files.extend(BASE_CONTEXT_FILES)

    loading = state.get("loading_policy") if isinstance(state.get("loading_policy"), dict) else {}
    before = loading.get("before_scene_load") if isinstance(loading, dict) else []
    if isinstance(before, list):
        files.extend(str(item) for item in before if isinstance(item, str) and "." in item)

    active = state.get("active_characters") or []
    nearby = state.get("nearby_or_possible") or []
    if mode == "play":
        for character_id in list(dict.fromkeys(list(active) + list(nearby))):
            path = CHARACTER_PATHS.get(str(character_id))
            if path:
                files.append(path)

    player = state.get("player_character") if isinstance(state.get("player_character"), dict) else {}
    profile = player.get("current_behavior_profile") if isinstance(player, dict) else None
    if isinstance(profile, str):
        files.append(profile)

    return [path for path in dict.fromkeys(files) if file_exists_for_context(path, session_id)]


def build_turn_context(session_id: str, req: TurnContextRequest) -> Dict[str, Any]:
    ensure_session_state(session_id)
    mode = classify_mode(req)
    state = current_state(session_id)
    state.setdefault("session_id", safe_session_id(session_id))
    files = build_file_list(state, mode, session_id)
    contents: Dict[str, Any] = {}
    if req.include_file_contents:
        for path in files:
            contents[path] = trimmed(read_project_file(path, session_id))

    scene = state.get("scene") if isinstance(state.get("scene"), dict) else {}
    return {
        "success": True,
        "project": PROJECT_SLUG,
        "session_id": safe_session_id(session_id),
        "mode": mode,
        "is_game_turn": mode == "play",
        "can_generate_scene": mode == "play",
        "response_mode": "play_scene" if mode == "play" else "technical_response",
        "start_requested": normalized_text(req.user_input) in {cmd.replace("ё", "е") for cmd in START_COMMANDS},
        "current_scene_anchor": {
            "date": state.get("date"),
            "time_of_day": state.get("time_of_day"),
            "scene_id": scene.get("scene_id"),
            "phase": scene.get("phase"),
            "location": state.get("location"),
            "active_characters": state.get("active_characters", []),
            "nearby_or_possible": state.get("nearby_or_possible", []),
        },
        "required_files": files,
        "required_file_contents": contents,
        "turn_counter": story_lines(session_id).get("turn_counter", {}),
        "actions_contract": {
            "default_context": "POST /api/v1/turn/context",
            "session_turn_contract": "POST /api/v1/sessions/{session_id}/turn-contract",
            "submit_result": "POST /api/v1/sessions/{session_id}/turn-result",
            "apply_turn_result": "POST /api/v1/sessions/{session_id}/apply-turn-result",
            "note": "If this response is returned, Action API is available. Do not say API/context is unavailable.",
        },
        "checks": [
            "Do not write player decisions, emotions, or replies for Akira.",
            "Use repository canon first, then runtime state from Railway volume.",
            "Required state files are included in required_file_contents when they exist.",
            "If a direct answer from Akira is needed, stop at the NPC line instead of continuing.",
            "After scene output, call submitTurnResult or applyTurnResult to persist state.",
        ],
    }


def normalize_state_patches(req: TurnResultRequest | ApplyTurnResultRequest) -> Dict[str, Any]:
    patches = dict(getattr(req, "state_patches", {}) or {})
    pairs = {
        "current_state_patch": getattr(req, "current_state_changes", None),
        "story_line_patches": getattr(req, "story_lines_changes", None),
        "relationship_patches": getattr(req, "relationship_changes", None),
        "knowledge_patches": getattr(req, "knowledge_changes", None),
        "reputation_patches": getattr(req, "reputation_changes", None),
        "rumor_patches": getattr(req, "rumor_changes", None),
        "inventory_patches": getattr(req, "inventory_changes", None),
        "power_state_patches": getattr(req, "power_changes", None),
        "future_locks_patches": getattr(req, "future_locks_changes", None),
    }
    for key, value in pairs.items():
        if isinstance(value, dict) and value:
            patches[key] = value
    return patches


def save_turn_result(session_id: str, req: TurnResultRequest | ApplyTurnResultRequest) -> Dict[str, Any]:
    ensure_session_state(session_id)
    sdir = session_dir(session_id)
    safe_id = safe_session_id(session_id)
    scene_id = getattr(req, "scene_id", None) or "scene"
    scene_text = getattr(req, "scene_text", None) or ""
    technical = bool(getattr(req, "technical", False))
    patches = normalize_state_patches(req)

    if technical:
        append_jsonl(sdir / "technical_history.jsonl", {"time": utc_now(), "scene_id": scene_id, "text": scene_text})
        return {"success": True, "status": "technical_saved", "session_id": safe_id, "updated_files": ["technical_history.jsonl"]}

    append_jsonl(sdir / "scene_history.jsonl", {"time": utc_now(), "scene_id": scene_id, "scene_text": scene_text, "state_patches": patches})

    state = current_state(session_id)
    current_patch = patches.get("current_state_patch") if isinstance(patches, dict) else None
    if isinstance(current_patch, dict):
        deep_merge(state, current_patch)
    state["updated_at"] = utc_now()
    write_json_atomic(sdir / "current_state.json", state)

    lines = story_lines(session_id)
    counter = lines.setdefault("turn_counter", {})
    counter["total_game_turns"] = int(counter.get("total_game_turns", 0) or 0) + 1
    counter["last_scene_id"] = scene_id
    counter["updated_at"] = utc_now()
    story_patch = patches.get("story_line_patches") if isinstance(patches, dict) else None
    if isinstance(story_patch, dict):
        deep_merge(lines, story_patch)
    write_json_atomic(sdir / "story_lines.json", lines)

    write_json_atomic(sdir / "last_turn_result.json", {"scene_id": scene_id, "scene_text": scene_text, "technical": technical, "state_patches": patches})
    return {
        "success": True,
        "status": "turn_result_saved",
        "session_id": safe_id,
        "updated_files": ["scene_history.jsonl", "current_state.json", "story_lines.json", "last_turn_result.json"],
    }


def object_schema(properties: Dict[str, Any], required: Optional[List[str]] = None) -> Dict[str, Any]:
    schema: Dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def turn_context_request_schema() -> Dict[str, Any]:
    return object_schema({
        "user_input": {"type": "string"},
        "mode": {"type": "string", "enum": ["play", "technical", "audit", "transfer"], "default": "play"},
        "include_file_contents": {"type": "boolean", "default": True},
        "client_context": {"type": "object"},
    }, ["user_input"])


def turn_result_request_schema() -> Dict[str, Any]:
    return object_schema({
        "scene_id": {"type": "string", "default": "scene"},
        "scene_text": {"type": "string"},
        "technical": {"type": "boolean", "default": False},
        "state_patches": {"type": "object"},
        "current_state_changes": {"type": "object"},
        "story_lines_changes": {"type": "object"},
        "relationship_changes": {"type": "object"},
        "knowledge_changes": {"type": "object"},
        "reputation_changes": {"type": "object"},
        "rumor_changes": {"type": "object"},
        "inventory_changes": {"type": "object"},
        "power_changes": {"type": "object"},
        "future_locks_changes": {"type": "object"},
    }, ["scene_text"])


def json_request_body(schema: Dict[str, Any], required: bool = True) -> Dict[str, Any]:
    return {"required": required, "content": {"application/json": {"schema": schema}}}


def session_parameter() -> Dict[str, Any]:
    return {"name": "session_id", "in": "path", "required": True, "schema": {"type": "string"}}


def actions_schema_json() -> Dict[str, Any]:
    return {
        "openapi": "3.1.0",
        "info": {"title": f"{PROJECT_SLUG} GPT Actions API", "version": "1.2.0"},
        "servers": [{"url": PUBLIC_BASE_URL}],
        "paths": {
            "/health": {"get": {"operationId": "healthCheck", "summary": "Check API health", "responses": {"200": {"description": "API is running"}}}},
            "/debug/volume": {"get": {"operationId": "debugVolume", "summary": "Check Railway volume persistence", "responses": {"200": {"description": "Volume status"}}}},
            "/api/v1/sessions": {"post": {"operationId": "createSession", "summary": "Create or initialize a runtime session in Railway volume", "requestBody": json_request_body(object_schema({"session_id": {"type": "string"}, "reset": {"type": "boolean", "default": False}}), required=False), "responses": {"200": {"description": "Session initialized"}}}},
            "/api/v1/turn/context": {"post": {"operationId": "getTurnContext", "summary": "Get default session context and repository file contents", "requestBody": json_request_body(turn_context_request_schema()), "responses": {"200": {"description": "Turn context"}}}},
            "/api/v1/sessions/{session_id}/turn-contract": {"post": {"operationId": "getSessionTurnContract", "summary": "Get turn contract and context for a specific session", "parameters": [session_parameter()], "requestBody": json_request_body(turn_context_request_schema()), "responses": {"200": {"description": "Turn contract and context"}}}},
            "/api/v1/sessions/{session_id}/turn-result": {"post": {"operationId": "submitTurnResult", "summary": "Persist generated scene and state patches", "parameters": [session_parameter()], "requestBody": json_request_body(turn_result_request_schema()), "responses": {"200": {"description": "Turn result saved"}}}},
            "/api/v1/sessions/{session_id}/apply-turn-result": {"post": {"operationId": "applyTurnResult", "summary": "Compatibility alias for saving generated scene and state changes", "parameters": [session_parameter()], "requestBody": json_request_body(turn_result_request_schema()), "responses": {"200": {"description": "Turn result saved"}}}},
            "/api/v1/files/{file_path}": {"get": {"operationId": "readProjectFile", "summary": "Read a repository or runtime state file by path", "parameters": [{"name": "file_path", "in": "path", "required": True, "schema": {"type": "string"}}], "responses": {"200": {"description": "File content"}}}},
        },
    }


@app.get("/")
def root() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": PROJECT_SLUG,
        "version": "1.2.0",
        "public_base_url": PUBLIC_BASE_URL,
        "data_dir": str(DATA_DIR),
        "health": "/health",
        "debug_volume": "/debug/volume",
        "gpt_actions_schema": "/openapi-actions.json",
        "default_context_endpoint": "/api/v1/turn/context",
        "session_turn_contract_endpoint": "/api/v1/sessions/{session_id}/turn-contract",
    }


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"success": True, "status": "ok", "project": PROJECT_SLUG, "time": utc_now()}


@app.get("/debug/volume")
def debug_volume() -> Dict[str, Any]:
    try:
        ensure_session_state(DEFAULT_SESSION_ID)
        test_file = DATA_DIR / "volume_test.txt"
        test_file.write_text(f"volume works {utc_now()}\n", encoding="utf-8")
        return {
            "success": True,
            "mount": str(DATA_DIR),
            "exists": DATA_DIR.exists(),
            "sessions_dir": str(SESSIONS_DIR),
            "default_session_dir": str(session_dir(DEFAULT_SESSION_ID)),
            "test_file": str(test_file),
            "test_file_exists": test_file.exists(),
            "session_files": sorted(p.name for p in session_dir(DEFAULT_SESSION_ID).iterdir()),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/v1/sessions")
def create_session(req: CreateSessionRequest = CreateSessionRequest()) -> Dict[str, Any]:
    sid = safe_session_id(req.session_id or DEFAULT_SESSION_ID)
    sdir = ensure_session_state(sid, reset=req.reset)
    return {
        "success": True,
        "project": PROJECT_SLUG,
        "session_id": sid,
        "session_dir": str(sdir),
        "reset": req.reset,
        "files": sorted(p.name for p in sdir.iterdir()),
        "next": {"turn_contract": f"/api/v1/sessions/{sid}/turn-contract", "turn_result": f"/api/v1/sessions/{sid}/turn-result"},
    }


@app.post("/api/v1/turn/context")
def turn_context(req: TurnContextRequest) -> Dict[str, Any]:
    return build_turn_context(DEFAULT_SESSION_ID, req)


@app.post("/api/v1/sessions/{session_id}/turn-contract")
def turn_contract(session_id: str, req: TurnContextRequest) -> Dict[str, Any]:
    return build_turn_context(session_id, req)


@app.post("/api/v1/sessions/{session_id}/turn-result")
def turn_result(session_id: str, req: TurnResultRequest) -> Dict[str, Any]:
    return save_turn_result(session_id, req)


@app.post("/api/v1/sessions/{session_id}/apply-turn-result")
def apply_turn_result(session_id: str, req: ApplyTurnResultRequest) -> Dict[str, Any]:
    return save_turn_result(session_id, req)


@app.get("/api/v1/files/{file_path:path}")
def read_file_endpoint(file_path: str, session_id: str = DEFAULT_SESSION_ID) -> Dict[str, Any]:
    path = safe_repo_path(file_path)
    text = read_project_file(path, session_id)
    if not text:
        raise HTTPException(status_code=404, detail="File not found or empty")
    return {"path": path, **trimmed(text)}


@app.get("/openapi-actions.json")
def openapi_actions_json() -> Dict[str, Any]:
    return actions_schema_json()


@app.get("/openapi-actions.yaml", response_class=PlainTextResponse)
def openapi_actions_yaml() -> str:
    return json.dumps(actions_schema_json(), ensure_ascii=False, indent=2) + "\n"
