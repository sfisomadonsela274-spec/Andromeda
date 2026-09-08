import os
import sys
import json
import time
import base64
import re
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List

# Ensure site-packages and local modules are resolvable
local_packages = os.path.expanduser("~/.local/lib/python3.12/site-packages")
if os.path.exists(local_packages) and local_packages not in sys.path:
    sys.path.insert(0, local_packages)

current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent
for candidate in ["/app", "/home/sfiso/ai-agent", str(project_root), str(current_dir)]:
    if os.path.exists(candidate) and candidate not in sys.path:
        sys.path.insert(0, candidate)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, APIRouter, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .lobes import telephony
from .lobes import memory
from .lobes import vision
from .engine import run_agent_step
from . import engine
from .db import (
    save_message,
    get_session_history,
    get_all_sessions,
    delete_session,
    delete_all_sessions,
    get_user_by_token,
)
from .auth import router as auth_router, get_current_user_optional

# Singletons from core modules
try:
    from media_controller import media_ctrl
except ImportError:
    try:
        from .media_controller import media_ctrl
    except ImportError:
        media_ctrl = None

try:
    from pixel_spicer import spicer, spice_image
except ImportError:
    try:
        from .pixel_spicer import spicer, spice_image
    except ImportError:
        spicer = None
        spice_image = None

try:
    from council_engine import council, adjudicate_seat, unload_model
except ImportError:
    try:
        from .council_engine import council, adjudicate_seat, unload_model
    except ImportError:
        council = None
        adjudicate_seat = None
        unload_model = None


app = FastAPI(title="Andromeda Spatial OS Backend")

# Allow CORS for the Vite dev server and external clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# 🎵 MEDIA CONTROLLER ENDPOINTS
# =============================================================================

media_router = APIRouter(prefix="/api/media", tags=["media"])

class MediaCommand(BaseModel):
    action: str
    value: Optional[float] = None
    player: Optional[str] = None


@media_router.get("/status")
async def get_media_status(player: Optional[str] = None):
    """Returns playback status and active track metadata from Linux MPRIS via playerctl."""
    if not media_ctrl:
        return {
            "active": False,
            "status": "error",
            "playback_status": "Stopped",
            "message": "media_controller module not loaded on host"
        }
    try:
        return media_ctrl.get_status(player=player)
    except Exception as e:
        return {
            "active": False,
            "status": "error",
            "playback_status": "Stopped",
            "message": str(e)
        }


@media_router.post("/execute")
async def execute_media(cmd: MediaCommand):
    """Executes a playback or volume action on desktop media players."""
    if not media_ctrl:
        return {"status": "error", "detail": "media_controller module not loaded on host"}
    try:
        result = media_ctrl.execute(action=cmd.action, value=cmd.value, player=cmd.player)
        is_error = isinstance(result, str) and result.startswith("[ERROR]")
        return {
            "status": "error" if is_error else "ok",
            "action": cmd.action,
            "result": result,
            "detail": result
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@media_router.get("/resolve_youtube")
async def resolve_youtube_endpoint(query: str):
    from .engine import resolve_youtube_top_video
    result = await asyncio.to_thread(resolve_youtube_top_video, query)
    return result

app.include_router(media_router)


# =============================================================================
# ✨ PIXEL SPICER ENDPOINTS
# =============================================================================

spice_router = APIRouter(prefix="/api/spice", tags=["spice"])

class SpiceEnhanceRequest(BaseModel):
    image_path: Optional[str] = None
    image_base64: Optional[str] = None
    filename: Optional[str] = None
    output_path: Optional[str] = None
    scale: int = 4
    model: str = "realesrgan-x4plus"
    clip_limit: float = 2.0
    no_clahe: bool = False
    no_upscale: bool = False
    no_critique: bool = False
    target_screen_width: Optional[int] = None
    target_screen_height: Optional[int] = None
    device_pixel_ratio: Optional[float] = 1.0
    auto_adaptive: bool = True


@spice_router.post("/enhance")
async def spice_enhance_endpoint(req: SpiceEnhanceRequest):
    """
    Applies the full Andromeda Pixel Spicer pipeline:
      1. Dynamic Range Balance: OpenCV CLAHE in LAB color space.
      2. Neural Super-Resolution: Real-ESRGAN NCNN Vulkan binary on host GPU.
      3. Visual Critique: Moondream (The Sentinel) inspection via Ollama.
    """
    if not spicer and not spice_image:
        raise HTTPException(status_code=500, detail="Pixel Spicer engine not loaded on host")

    spice_fn = spicer.spice_image if spicer else spice_image

    incoming_dir = Path("/home/sfiso/photos_incoming")
    enhanced_dir = Path("/home/sfiso/photos_enhanced")
    incoming_dir.mkdir(parents=True, exist_ok=True)
    enhanced_dir.mkdir(parents=True, exist_ok=True)

    input_file_path = None

    # Handle input path or base64 upload
    if req.image_path:
        p = Path(req.image_path)
        if not p.is_absolute():
            p = incoming_dir / p
        if not p.exists():
            raise HTTPException(status_code=404, detail=f"Source image not found: {req.image_path}")
        input_file_path = str(p)
    elif req.image_base64:
        raw_b64 = req.image_base64
        if "base64," in raw_b64:
            raw_b64 = raw_b64.split("base64,")[1]
        try:
            img_bytes = base64.b64decode(raw_b64)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid base64 payload: {e}")

        fname = req.filename or f"upload_{int(time.time())}.png"
        safe_name = os.path.basename(fname)
        target_in = incoming_dir / safe_name
        with open(target_in, "wb") as f:
            f.write(img_bytes)
        input_file_path = str(target_in)
    else:
        raise HTTPException(status_code=400, detail="image_path or image_base64 is required")

    # Determine destination output path
    dest_path = req.output_path
    if not dest_path:
        stem = Path(input_file_path).stem
        dest_path = str(enhanced_dir / f"{stem}_spiced.png")

    target_screen = None
    if req.target_screen_width and req.target_screen_height:
        target_screen = {
            "width": req.target_screen_width,
            "height": req.target_screen_height,
            "device_pixel_ratio": req.device_pixel_ratio or 1.0
        }

    try:
        loop = asyncio.get_running_loop()
        res = await loop.run_in_executor(
            None,
            lambda: spice_fn(
                input_path=input_file_path,
                output_path=dest_path,
                scale=req.scale,
                model_name=req.model,
                clip_limit=req.clip_limit,
                enable_clahe=not req.no_clahe,
                enable_upscale=not req.no_upscale,
                enable_critique=not req.no_critique,
                target_screen=target_screen,
                auto_adaptive=req.auto_adaptive
            )
        )

        out_img = res.get("output", {}).get("path") or res.get("output_image", dest_path)
        out_name = os.path.basename(out_img)
        critique_text = res.get("sentinel_critique")
        if isinstance(critique_text, dict):
            critique_text = critique_text.get("critique", "")

        # Read enhanced image to return base64 for instant zero-latency client rendering
        enhanced_b64 = None
        try:
            if os.path.exists(out_img):
                with open(out_img, "rb") as f:
                    ext = os.path.splitext(out_img)[1].lower().replace(".", "") or "png"
                    enhanced_b64 = f"data:image/{ext};base64,{base64.b64encode(f.read()).decode('utf-8')}"
        except Exception:
            pass

        return {
            "status": "success",
            "output_image": out_img,
            "filename": out_name,
            "download_url": f"/api/spice/download/{out_name}",
            "image_base64": enhanced_b64,
            "scale": res.get("super_resolution", {}).get("scale", req.scale),
            "model": res.get("super_resolution", {}).get("model", req.model),
            "camera_metadata": res.get("camera_metadata", {}),
            "adaptive_tuning": res.get("adaptive_tuning", {}),
            "denoise": res.get("denoise", {}),
            "original_resolution": res.get("input", {}).get("dimensions"),
            "enhanced_resolution": res.get("output", {}).get("dimensions"),
            "critique": critique_text or "Visual critique completed.",
            "duration_ms": res.get("total_duration_ms")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Enhancement error: {e}")


@spice_router.get("/download/{filename}")
async def spice_download_endpoint(filename: str):
    """Serves enhanced photos directly from the photos_enhanced storage directory."""
    safe_name = os.path.basename(filename)
    search_dirs = [
        Path("/home/sfiso/photos_enhanced"),
        Path("/home/sfiso/photos_incoming"),
        Path("/app/photos_enhanced")
    ]

    found_path = None
    for d in search_dirs:
        candidate = d / safe_name
        if candidate.exists() and candidate.is_file():
            found_path = candidate
            break

    if not found_path:
        raise HTTPException(status_code=404, detail=f"Enhanced image '{safe_name}' not found")

    ext = found_path.suffix.lower()
    media_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".json": "application/json"
    }
    media_type = media_types.get(ext, "application/octet-stream")

    return FileResponse(
        path=str(found_path),
        media_type=media_type,
        filename=safe_name
    )

app.include_router(spice_router)


# =============================================================================
# 🚀 APP CONTROLLER ENDPOINTS
# =============================================================================

apps_router = APIRouter(prefix="/api/apps", tags=["apps"])

class AppInstallPayload(BaseModel):
    app: str
    method: str = "flatpak"

class AppExecutePayload(BaseModel):
    app: str
    action: str = "launch"  # "launch" or "install"

@apps_router.get("")
async def list_apps_endpoint():
    """Lists registered desktop applications and their launch definitions."""
    apps_list = [
        {"id": "vscode", "name": "VS Code", "category": "development", "icon": "code", "package_id": "com.visualstudio.code", "flatpak": True},
        {"id": "spotify", "name": "Spotify", "category": "media", "icon": "music", "package_id": "com.spotify.Client", "flatpak": True},
        {"id": "discord", "name": "Discord", "category": "social", "icon": "message-circle", "package_id": "com.discordapp.Discord", "flatpak": True},
        {"id": "vlc", "name": "VLC Media Player", "category": "media", "icon": "video", "package_id": "org.videolan.VLC", "flatpak": True},
        {"id": "blender", "name": "Blender 3D", "category": "design", "icon": "box", "package_id": "org.blender.Blender", "flatpak": True},
        {"id": "gimp", "name": "GIMP Image Editor", "category": "design", "icon": "image", "package_id": "org.gimp.GIMP", "flatpak": True},
        {"id": "obs", "name": "OBS Studio", "category": "media", "icon": "radio", "package_id": "com.obsproject.Studio", "flatpak": True},
        {"id": "slack", "name": "Slack", "category": "communication", "icon": "hash", "package_id": "com.slack.Slack", "flatpak": True}
    ]
    return {"status": "ok", "apps": apps_list}

@apps_router.post("/install")
async def app_install_endpoint(req: AppInstallPayload):
    flatpak_ids = {
        "spotify": "com.spotify.Client",
        "vscode": "com.visualstudio.code",
        "discord": "com.discordapp.Discord",
        "vlc": "org.videolan.VLC",
        "gimp": "org.gimp.GIMP",
        "blender": "org.blender.Blender",
        "slack": "com.slack.Slack",
        "obs": "com.obsproject.Studio"
    }
    app_key = req.app.lower().strip()
    pkg_id = flatpak_ids.get(app_key, f"com.{app_key}.App")
    cmd = f"flatpak install --user -y flathub {pkg_id}"
    return {
        "status": "ready",
        "app": req.app,
        "package_id": pkg_id,
        "command": cmd,
        "message": f"Execute on terminal: {cmd}"
    }

@apps_router.post("/execute")
async def app_execute_endpoint(req: AppExecutePayload):
    app_key = req.app.lower().strip()
    if req.action == "install":
        cmd = f"flatpak install --user -y flathub {app_key}"
        return {"status": "staged", "action": "install", "command": cmd, "message": f"Staged Flatpak install: {cmd}"}
    else:
        cmd = f"gtk-launch {app_key} 2>/dev/null || flatpak run {app_key} 2>/dev/null || which {app_key}"
        import subprocess
        try:
            subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {"status": "launched", "action": "launch", "app": app_key, "message": f"Dispatched launch for {app_key}."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

app.include_router(apps_router)


# =============================================================================
# 📜 WORKFLOW MACROS ENDPOINTS
# =============================================================================

macro_router = APIRouter(prefix="/api/macros", tags=["macros"])

class MacroRunPayload(BaseModel):
    macro_name: str
    overrides: Optional[Dict[str, Any]] = None

@macro_router.get("")
async def list_macros_endpoint():
    """Lists available workflow macros from macros.yaml."""
    yaml_candidates = [
        Path("/app/macros.yaml"),
        Path("/home/sfiso/ai-agent/macros.yaml"),
        Path(__file__).resolve().parent / "macros.yaml"
    ]
    macros_data = {}
    for cand in yaml_candidates:
        if cand.exists():
            try:
                import yaml
                with open(cand, "r", encoding="utf-8") as f:
                    macros_data = yaml.safe_load(f).get("macros", {})
                break
            except Exception:
                pass

    result = []
    for mid, mdata in macros_data.items():
        result.append({
            "id": mid,
            "name": mdata.get("name", mid),
            "description": mdata.get("description", ""),
            "steps_count": len(mdata.get("steps", [])),
            "steps": mdata.get("steps", [])
        })
    return {"status": "ok", "macros": result}

@macro_router.post("/run")
async def run_macro_endpoint(payload: MacroRunPayload):
    """Executes a workflow macro via macro_runner asynchronously."""
    try:
        from macro_runner import runner as m_runner
    except ImportError:
        try:
            from .macro_runner import runner as m_runner
        except ImportError:
            m_runner = None

    if not m_runner:
        raise HTTPException(status_code=500, detail="Macro runner engine not available on host")

    loop = asyncio.get_running_loop()
    res = await loop.run_in_executor(
        None,
        lambda: m_runner.run_macro(payload.macro_name, payload.overrides or {})
    )
    return res

app.include_router(macro_router)


# =============================================================================
# 🧹 MEMORY & VRAM RECLAIM ENDPOINTS
# =============================================================================

memory_reclaim_router = APIRouter(prefix="/api/memory", tags=["memory"])

@memory_reclaim_router.post("/sweep")
async def memory_sweep_endpoint():
    """Unloads idle Ollama models from GPU VRAM and runs Python garbage collection."""
    import gc
    gc.collect()
    evictions = []

    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    for m in ["qwen2.5-coder:7b", "llama3.2"]:
        try:
            req = urllib.request.Request(
                f"{host}/api/generate",
                data=json.dumps({"model": m, "keep_alive": 0}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                evictions.append(m)
        except Exception:
            pass

    return {
        "status": "success",
        "message": f"VRAM sweep executed. Evicted: {', '.join(evictions) if evictions else 'Heavy models cleared'}.",
        "evicted_models": evictions,
        "gc_collected": True
    }

app.include_router(memory_reclaim_router)

# Include Auth Router
app.include_router(auth_router)

# Include Lobe Routers
app.include_router(telephony.router, tags=["telephony"])
app.include_router(memory.router, tags=["memory"])
app.include_router(vision.router, tags=["vision"])


# =============================================================================
# 💬 SESSIONS ENDPOINTS
# =============================================================================

sessions_router = APIRouter(prefix="/api/sessions", tags=["sessions"])

@sessions_router.get("")
async def list_sessions_endpoint(user: dict | None = Depends(get_current_user_optional)):
    user_id = user["id"] if user else "guest"
    return {"sessions": get_all_sessions(user_id=user_id)}

@sessions_router.delete("/{session_id}")
async def delete_session_endpoint(session_id: str, user: dict | None = Depends(get_current_user_optional)):
    user_id = user["id"] if user else "guest"
    success = delete_session(session_id, user_id=user_id)
    return {"status": "ok", "deleted": success, "session_id": session_id}

@sessions_router.delete("")
async def delete_all_sessions_endpoint(user: dict | None = Depends(get_current_user_optional)):
    user_id = user["id"] if user else "guest"
    deleted_count = delete_all_sessions(user_id=user_id)
    return {"status": "ok", "deleted_count": deleted_count}

app.include_router(sessions_router)


@app.get("/")
def read_root():
    return {"status": "Andromeda Core Online"}


# =============================================================================
# ⚡ WEBSOCKET CORE ENGINE (/ws/core) WITH COUNCIL INTEGRATION
# =============================================================================

@app.websocket("/ws/core")
async def core_endpoint(websocket: WebSocket):
    await websocket.accept()
    conversation_history = []
    session_id = None
    active_telemetry = None
    
    # Resolve user from query param ?token=...
    token = websocket.query_params.get("token")
    user = get_user_by_token(token) if token else None
    active_user_id = user["id"] if user else "guest"
    
    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                payload_type = payload.get("type", "prompt")
                
                if payload_type == "init":
                    session_id = payload.get("session_id")
                    cloud_url = payload.get("cloud_url")
                    requested_model = payload.get("model")
                    init_token = payload.get("token")
                    if init_token:
                        init_user = get_user_by_token(init_token)
                        if init_user:
                            active_user_id = init_user["id"]

                    if cloud_url and isinstance(cloud_url, str) and cloud_url.strip():
                        engine.CLOUD_NODE_URL = cloud_url.strip()
                    else:
                        engine.CLOUD_NODE_URL = ""
                    if requested_model:
                        engine.scaffolding.model_name = requested_model
                        
                    if session_id:
                        history = get_session_history(session_id, user_id=active_user_id)
                        conversation_history = history.copy()
                        await websocket.send_json({"type": "history", "messages": history, "user_id": active_user_id})
                    continue
                    
                if payload_type == "telemetry":
                    active_telemetry = payload.get("data", {})
                    continue
                    
                if payload_type == "get_sessions":
                    sessions = get_all_sessions(user_id=active_user_id)
                    await websocket.send_json({"type": "sessions_list", "sessions": sessions, "user_id": active_user_id})
                    continue

                if payload_type == "delete_session":
                    target_id = payload.get("session_id")
                    if target_id:
                        delete_session(target_id, user_id=active_user_id)
                        sessions = get_all_sessions(user_id=active_user_id)
                        await websocket.send_json({"type": "sessions_list", "sessions": sessions, "user_id": active_user_id})
                        await websocket.send_json({"type": "session_deleted", "session_id": target_id})
                    continue

                if payload_type == "clear_all_sessions":
                    delete_all_sessions(user_id=active_user_id)
                    await websocket.send_json({"type": "sessions_list", "sessions": [], "user_id": active_user_id})
                    await websocket.send_json({"type": "all_sessions_cleared"})
                    continue
                
                if payload_type == "prompt":
                    prompt = payload.get("prompt") or payload.get("text", "")
                    cwd = payload.get("cwd", "/home/sfiso/ai-agent")
                    with_tools = payload.get("with_tools", True)
                    
                    if not session_id:
                        session_id = "default_session"
                        
                    # Save user prompt to database
                    save_message(session_id, "user", prompt, user_id=active_user_id)
                    conversation_history.append({"role": "user", "content": prompt})
                    
                    # ── COUNCIL ADJUDICATION ──
                    seat_info = {
                        "title": "The Scribe",
                        "id": "scribe",
                        "model": "qwen2.5-coder:1.5b",
                        "vram_profile": "~1.0GB VRAM (Resident / Always Warm)",
                        "role": "Fast Intent Extraction, Quick Tools & Standard Conversation",
                        "reason": "Standard conversational query"
                    }

                    adjudicate_fn = (council.adjudicate_seat if council else adjudicate_seat)
                    if adjudicate_fn:
                        try:
                            has_image = bool(re.search(r"\.(?:png|jpe?g|webp|svg)\b", prompt.lower()))
                            seat_obj, adjudication = adjudicate_fn(prompt=prompt, has_image=has_image)
                            seat_info = {
                                "title": seat_obj.title,
                                "id": seat_obj.id,
                                "model": seat_obj.model,
                                "vram_profile": seat_obj.vram_profile,
                                "role": seat_obj.role,
                                "reason": adjudication.get("reason", "Council adjudication")
                            }
                        except Exception as e:
                            print(f"[Council Adjudication Error]: {e}")

                    # 1. Emit real-time Council Status packet before processing
                    await websocket.send_json({
                        "type": "council_status",
                        "presiding_seat": seat_info["title"],
                        "seat": seat_info["title"],
                        "seat_id": seat_info["id"],
                        "model": seat_info["model"],
                        "vram_profile": seat_info["vram_profile"],
                        "role": seat_info["role"],
                        "reason": seat_info["reason"],
                        "message": f"🏛️ {seat_info['title']} is presiding ({seat_info['model']})."
                    })

                    # Progress helper for thought trace in UI
                    async def stream_status(msg: str):
                        try:
                            await websocket.send_json({
                                "type": "status",
                                "message": msg,
                                "presiding_seat": seat_info["title"],
                                "model": seat_info["model"]
                            })
                        except Exception:
                            pass
                        
                    await stream_status(f"🏛️ {seat_info['title']} presiding ({seat_info['model']}) • {seat_info['reason']}")
                    
                    try:
                        response_dict = await run_agent_step(
                            user_prompt=prompt, 
                            messages=conversation_history, 
                            cwd=cwd, 
                            with_tools=with_tools,
                            telemetry_data=active_telemetry,
                            stream_callback=stream_status,
                            model=seat_info["model"]
                        )
                        
                        # Append and emit assistant response
                        if response_dict and response_dict.get("content"):
                            conversation_history.append(response_dict)
                            save_message(session_id, "assistant", response_dict["content"], user_id=active_user_id)
                            await websocket.send_json({
                                "type": "response",
                                "message": response_dict["content"],
                                "presiding_seat": seat_info["title"],
                                "model": seat_info["model"],
                                "seat_id": seat_info["id"]
                            })
                        else:
                            fallback_msg = json.dumps({"action": "chat", "message": "Command executed successfully."})
                            await websocket.send_json({
                                "type": "response",
                                "message": fallback_msg,
                                "presiding_seat": seat_info["title"],
                                "model": seat_info["model"],
                                "seat_id": seat_info["id"]
                            })
                    except Exception as e:
                        print(f"[Core Agent Step Error]: {e}")
                        err_payload = json.dumps({"action": "chat", "message": f"[Engine Notice]: Could not complete prompt. Error: {e}"})
                        await websocket.send_json({
                            "type": "response",
                            "message": err_payload,
                            "presiding_seat": seat_info["title"],
                            "model": seat_info["model"],
                            "seat_id": seat_info["id"]
                        })
                    finally:
                        # Reclaim 4.7GB VRAM if The Architect was presiding
                        if seat_info["id"] == "architect" and unload_model:
                            try:
                                asyncio.create_task(asyncio.to_thread(unload_model, seat_info["model"]))
                            except Exception:
                                pass
                    
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON payload."})
                
    except WebSocketDisconnect:
        print("[Core] Client disconnected.")
