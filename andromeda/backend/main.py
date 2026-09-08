import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, APIRouter
from fastapi.middleware.cors import CORSMiddleware
import asyncio

from .lobes import telephony
from .lobes import memory
from .lobes import vision
from .engine import run_agent_step
from . import engine
from .db import save_message, get_session_history, get_all_sessions, delete_session

app = FastAPI(title="Andromeda Spatial OS Backend")

# Allow CORS for the Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from pydantic import BaseModel
try:
    from media_controller import media_ctrl
except ImportError:
    try:
        from .media_controller import media_ctrl
    except ImportError:
        media_ctrl = None

media_router = APIRouter(prefix="/api/media", tags=["media"])

class MediaCommand(BaseModel):
    action: str
    value: float | None = None
    player: str | None = None

@media_router.get("/status")
async def get_media_status():
    if not media_ctrl:
        return {"active": False, "message": "media_controller module not loaded"}
    return media_ctrl.get_status()

@media_router.post("/execute")
async def execute_media(cmd: MediaCommand):
    if not media_ctrl:
        return {"status": "error", "detail": "media_controller module not loaded"}
    result = media_ctrl.execute(action=cmd.action, value=cmd.value, player=cmd.player)
    return {"status": "ok", "detail": result}

@media_router.get("/resolve_youtube")
async def resolve_youtube_endpoint(query: str):
    from .engine import resolve_youtube_top_video
    result = await asyncio.to_thread(resolve_youtube_top_video, query)
    return result

app.include_router(media_router)

apps_router = APIRouter(prefix="/api/apps", tags=["apps"])

class AppInstallPayload(BaseModel):
    app: str
    method: str = "flatpak"

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

app.include_router(apps_router)

# Include Lobe Routers
app.include_router(telephony.router, tags=["telephony"])
app.include_router(memory.router, tags=["memory"])
app.include_router(vision.router, tags=["vision"])

sessions_router = APIRouter(prefix="/api/sessions", tags=["sessions"])

@sessions_router.get("")
async def list_sessions_endpoint():
    return {"sessions": get_all_sessions()}

@sessions_router.delete("/{session_id}")
async def delete_session_endpoint(session_id: str):
    success = delete_session(session_id)
    return {"status": "ok", "deleted": success, "session_id": session_id}

app.include_router(sessions_router)

@app.get("/")
def read_root():
    return {"status": "Andromeda Core Online"}

@app.websocket("/ws/core")
async def core_endpoint(websocket: WebSocket):
    await websocket.accept()
    # Jimmy expects a stateful message array for the conversation
    conversation_history = []
    session_id = None
    active_telemetry = None
    
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
                    if cloud_url and isinstance(cloud_url, str) and cloud_url.strip():
                        engine.CLOUD_NODE_URL = cloud_url.strip()
                    else:
                        engine.CLOUD_NODE_URL = ""
                    if requested_model:
                        engine.scaffolding.model_name = requested_model
                        
                    if session_id:
                        history = get_session_history(session_id)
                        conversation_history = history.copy()
                        await websocket.send_json({"type": "history", "messages": history})
                    continue
                    
                if payload_type == "telemetry":
                    active_telemetry = payload.get("data", {})
                    continue
                    
                if payload_type == "get_sessions":
                    sessions = get_all_sessions()
                    await websocket.send_json({"type": "sessions_list", "sessions": sessions})
                    continue

                if payload_type == "delete_session":
                    target_id = payload.get("session_id")
                    if target_id:
                        delete_session(target_id)
                        sessions = get_all_sessions()
                        await websocket.send_json({"type": "sessions_list", "sessions": sessions})
                        await websocket.send_json({"type": "session_deleted", "session_id": target_id})
                    continue
                
                if payload_type == "prompt":
                    prompt = payload.get("prompt") or payload.get("text", "")
                    cwd = payload.get("cwd", "/home/sfiso/ai-agent")
                    with_tools = payload.get("with_tools", True)
                    
                    if not session_id:
                        session_id = "default_session"
                        
                    # Save user prompt
                    save_message(session_id, "user", prompt)
                    
                    # Append user prompt
                    conversation_history.append({"role": "user", "content": prompt})
                    
                    # Send a progress event back
                    async def stream_status(msg: str):
                        try:
                            await websocket.send_json({"type": "status", "message": msg})
                        except Exception:
                            pass
                        
                    await stream_status("Thinking...")
                    
                    try:
                        response_dict = await run_agent_step(
                            user_prompt=prompt, 
                            messages=conversation_history, 
                            cwd=cwd, 
                            with_tools=with_tools,
                            telemetry_data=active_telemetry,
                            stream_callback=stream_status
                        )
                        
                        # Append assistant response
                        if response_dict and response_dict.get("content"):
                            conversation_history.append(response_dict)
                            save_message(session_id, "assistant", response_dict["content"])
                            await websocket.send_json({"type": "response", "message": response_dict["content"]})
                        else:
                            fallback_msg = json.dumps({"action": "chat", "message": "Command executed successfully."})
                            await websocket.send_json({"type": "response", "message": fallback_msg})
                    except Exception as e:
                        print(f"[Core Agent Step Error]: {e}")
                        err_payload = json.dumps({"action": "chat", "message": f"[Engine Notice]: Could not complete prompt. Error: {e}"})
                        await websocket.send_json({"type": "response", "message": err_payload})
                    
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON payload."})
                
    except WebSocketDisconnect:
        print("[Core] Client disconnected.")
