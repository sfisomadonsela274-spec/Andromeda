import base64
import requests
from fastapi import APIRouter
from pydantic import BaseModel
import logging
from .. import engine

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    logging.warning("Ollama is not installed. Vision tasks will be mocked.")

router = APIRouter()

class VisionRequest(BaseModel):
    image_base64: str
    prompt: str = "Describe what is in this image. Extract any text visible."
    model: str = "moondream" # Future expansion to llava or gemini

@router.post("/analyze")
async def analyze_image(req: VisionRequest):
    """Passes an image to Moondream (or other VLMs) for OCR and scene understanding."""
    if engine.CLOUD_NODE_URL:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(engine.CLOUD_NODE_URL)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            resp = requests.post(
                f"{base_url}/analyze",
                json={"image": req.image_base64, "query": req.prompt},
                timeout=60
            )
            if resp.status_code == 200:
                data = resp.json()
                return {"response": data.get("response", "No text found.")}
            else:
                return {"error": f"Cloud Engine Error HTTP {resp.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    if not OLLAMA_AVAILABLE:
        return {"response": "Mock OCR Response: No text found. (Ollama not available)"}
        
    try:
        # Decode base64 to bytes
        img_bytes = base64.b64decode(req.image_base64)
        
        # Route to specified model
        if req.model in ["moondream", "llava"]:
            response = ollama.chat(
                model=req.model,
                messages=[{"role": "user", "content": req.prompt, "images": [img_bytes]}]
            )
            return {"response": response['message']['content']}
        elif req.model == "gemini":
            return {"response": "Gemini fallback is currently disabled based on engine configuration."}
        else:
            return {"error": f"Unsupported model: {req.model}"}
            
    except Exception as e:
        return {"error": str(e)}
