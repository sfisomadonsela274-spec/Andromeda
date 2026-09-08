import os
import tempfile
import base64
import requests
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import logging
from .. import engine

try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    logging.warning("faster-whisper not installed. Audio transcription will be mocked.")

router = APIRouter()

# Load model lazily or at startup. Using small/tiny for low latency.
# The user wants to run this locally.
whisper_model = None
def get_whisper_model():
    global whisper_model
    if WHISPER_AVAILABLE and whisper_model is None:
        whisper_model = WhisperModel("tiny.en", device="cpu", compute_type="int8")
    return whisper_model

@router.websocket("/ws/audio")
async def audio_endpoint(websocket: WebSocket):
    await websocket.accept()
    audio_buffer = bytearray()
    
    try:
        while True:
            data = await websocket.receive_bytes()
            audio_buffer.extend(data)
    except WebSocketDisconnect:
        # Stream ended. Process the audio buffer.
        if len(audio_buffer) == 0:
            return

        if engine.CLOUD_NODE_URL:
            try:
                from urllib.parse import urlparse
                parsed = urlparse(engine.CLOUD_NODE_URL)
                base_url = f"{parsed.scheme}://{parsed.netloc}"
                base64_audio = base64.b64encode(audio_buffer).decode("utf-8")
                resp = requests.post(
                    f"{base_url}/transcribe",
                    json={"audio": base64_audio},
                    timeout=60
                )
                if resp.status_code == 200:
                    transcript = resp.json().get("text", "")
                    print(f"[Cloud Telephony] Transcribed: {transcript}")
                else:
                    print(f"[Cloud Telephony Error] HTTP {resp.status_code}")
            except Exception as e:
                print(f"[Cloud Telephony Error] {e}")
            return

        if not WHISPER_AVAILABLE:
            print("[Telephony] Mocking transcription since faster-whisper is unavailable.")
            # We would normally send a REST callback or return text if connection wasn't closed.
            return
            
        model = get_whisper_model()
        if model is None:
            return
            
        # Write buffer to a temp file because faster_whisper expects a file path or a file-like object.
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
            tmp.write(audio_buffer)
            tmp_path = tmp.name
            
        try:
            segments, info = model.transcribe(tmp_path, beam_size=5)
            transcript = "".join([segment.text for segment in segments])
            print(f"[Telephony Lobe] Transcribed: {transcript}")
            
            # TODO: Here we would trigger Andromeda's intent engine based on the transcript.
            # In a real setup, the frontend would probably maintain a separate WebSocket 
            # for telemetry where we can push this transcript back.
        except Exception as e:
            print(f"[Telephony Error]: {e}")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
