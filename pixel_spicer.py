#!/usr/bin/env python3
"""
=============================================================================
             🌌 ANDROMEDA PIXEL SPICER: ENHANCEMENT PIPELINE 🌌
=============================================================================
Combines three synergistic image processing stages:
  1. Dynamic Range Balance: OpenCV CLAHE in LAB Color Space (L-channel equalization).
  2. Neural Super-Resolution: Real-ESRGAN NCNN Vulkan binary acceleration.
  3. Visual Critique: Moondream (The Sentinel) evaluation via Ollama (keep_alive: 2m).
=============================================================================
"""

import os
import sys
import json
import time
import base64
import shutil
import argparse
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

import cv2
import numpy as np

# Path configurations
DEFAULT_BINARY_PATH = os.path.expanduser("/home/sfiso/ai-agent/bin/realesrgan/realesrgan-ncnn-vulkan")
DEFAULT_MODELS_DIR = os.path.expanduser("/home/sfiso/ai-agent/bin/realesrgan/models")
DEFAULT_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}


# =============================================================================
# 🎨 STEP 1: OPENCV CLAHE IN LAB COLOR SPACE
# =============================================================================

def apply_clahe_lab(
    image: np.ndarray,
    clip_limit: float = 2.0,
    tile_grid_size: Tuple[int, int] = (8, 8)
) -> np.ndarray:
    """
    Applies Contrast Limited Adaptive Histogram Equalization (CLAHE)
    to the Lightness (L) channel in LAB color space.

    Why LAB Color Space?
      - Preserves pure color chroma (A and B channels) completely untouched.
      - Boosts shadowed dynamic range and tones down harsh highlights exclusively
        on the L channel without inducing artificial color tinting or oversaturation.
    """
    if image is None or image.size == 0:
        raise ValueError("Invalid or empty image array passed to apply_clahe_lab.")

    # 1. Convert BGR to LAB
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)

    # 2. Split into L, A, B channels
    l_channel, a_channel, b_channel = cv2.split(lab)

    # 3. Create CLAHE operator and apply to Lightness
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    cl = clahe.apply(l_channel)

    # 4. Merge back with original chrominance channels
    balanced_lab = cv2.merge((cl, a_channel, b_channel))

    # 5. Convert back to BGR color space
    balanced_bgr = cv2.cvtColor(balanced_lab, cv2.COLOR_LAB2BGR)
    return balanced_bgr


# =============================================================================
# 🚀 STEP 2: REAL-ESRGAN NCNN VULKAN SUPER-RESOLUTION
# =============================================================================

def run_realesrgan(
    input_path: str,
    output_path: str,
    scale: int = 4,
    model_name: str = "realesrgan-x4plus",
    binary_path: str = DEFAULT_BINARY_PATH,
    models_dir: str = DEFAULT_MODELS_DIR
) -> Dict[str, Any]:
    """
    Executes the Real-ESRGAN NCNN Vulkan binary on GPU for super-resolution upscaling.
    """
    binary_path = os.path.expanduser(binary_path)
    models_dir = os.path.expanduser(models_dir)

    if not os.path.exists(binary_path):
        raise FileNotFoundError(f"Real-ESRGAN Vulkan binary not found at: {binary_path}")

    if not os.path.exists(models_dir):
        raise FileNotFoundError(f"Real-ESRGAN models folder not found at: {models_dir}")

    cmd = [
        binary_path,
        "-i", str(input_path),
        "-o", str(output_path),
        "-s", str(scale),
        "-m", str(models_dir),
        "-n", str(model_name)
    ]

    start_t = time.time()
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    elapsed_ms = round((time.time() - start_t) * 1000, 2)

    if result.returncode != 0:
        raise RuntimeError(
            f"Real-ESRGAN failed with return code {result.returncode}.\n"
            f"Error details:\n{result.stderr.strip()}"
        )

    if not os.path.exists(output_path):
        raise FileNotFoundError(f"Real-ESRGAN finished but output file missing: {output_path}")

    return {
        "status": "success",
        "scale": scale,
        "model": model_name,
        "elapsed_ms": elapsed_ms,
        "output_path": output_path
    }


# =============================================================================
# 👁️ STEP 3: MOONDREAM (THE SENTINEL) VISUAL CRITIQUE
# =============================================================================

def critique_with_sentinel(
    image_path: str,
    prompt: Optional[str] = None,
    ollama_host: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calls Moondream (The Sentinel) via Ollama with keep_alive='2m' to review
    the enhanced image, evaluating resolution, balance, artifacts, and aesthetic score.
    """
    host = (ollama_host or DEFAULT_OLLAMA_HOST).rstrip("/")

    if not os.path.exists(image_path):
        return {"status": "error", "error": f"Image file not found: {image_path}"}

    with open(image_path, "rb") as f:
        b64_image = base64.b64encode(f.read()).decode("utf-8")

    default_prompt = (
        "You are The Sentinel, visual critique engine of the Andromeda Council. "
        "Perform an expert visual critique of this enhanced image. "
        "Provide a concise analysis addressing:\n"
        "1. Resolution and edge sharpness\n"
        "2. Dynamic range, contrast, and lighting balance\n"
        "3. Presence of upscaling artifacts, noise, or chromatic aberrations\n"
        "4. Aesthetic quality rating on a scale from 1 to 10 with brief justification."
    )
    query_prompt = prompt or default_prompt

    req_payload = {
        "model": "moondream",
        "prompt": query_prompt,
        "images": [b64_image],
        "stream": False,
        "keep_alive": "2m"
    }

    start_t = time.time()
    try:
        req = urllib.request.Request(
            f"{host}/api/generate",
            data=json.dumps(req_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=45.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            critique_text = data.get("response", "").strip()
            elapsed_ms = round((time.time() - start_t) * 1000, 2)
            return {
                "status": "success",
                "seat": "The Sentinel",
                "model": "moondream",
                "keep_alive": "2m",
                "critique": critique_text,
                "duration_ms": elapsed_ms
            }
    except Exception as e:
        return {
            "status": "warning",
            "seat": "The Sentinel",
            "model": "moondream",
            "error": f"Sentinel visual critique call failed: {e}",
            "critique": "Visual critique unavailable (Ollama Moondream offline or timed out)."
        }


# =============================================================================
# 🌟 COMPLETE PIPELINE: SPICE IMAGE
# =============================================================================

def spice_image(
    input_path: str,
    output_path: Optional[str] = None,
    scale: int = 4,
    model_name: str = "realesrgan-x4plus",
    clip_limit: float = 2.0,
    tile_grid_size: Tuple[int, int] = (8, 8),
    enable_clahe: bool = True,
    enable_upscale: bool = True,
    enable_critique: bool = True,
    binary_path: str = DEFAULT_BINARY_PATH,
    models_dir: str = DEFAULT_MODELS_DIR,
    ollama_host: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes the full Andromeda Pixel Spicer pipeline:
      1. Reads source image.
      2. Dynamic range balance via CLAHE in LAB color space.
      3. Real-ESRGAN NCNN Vulkan super-resolution upscaling.
      4. Visual critique by Moondream (The Sentinel).
      5. Outputs enhanced image and companion JSON metadata.
    """
    total_start = time.time()
    input_file = Path(input_path).resolve()
    if not input_file.exists():
        raise FileNotFoundError(f"Input image not found: {input_path}")

    # Determine output path if not specified
    if not output_path:
        out_stem = f"{input_file.stem}_spiced"
        output_path = str(input_file.parent / f"{out_stem}{input_file.suffix}")

    output_file = Path(output_path).resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # 1. Load image
    orig_img = cv2.imread(str(input_file))
    if orig_img is None:
        raise ValueError(f"Could not decode image from file: {input_file}")

    orig_h, orig_w, orig_c = orig_img.shape
    orig_size_bytes = input_file.stat().st_size

    # 2. CLAHE Dynamic Range Balance
    clahe_metrics = {"applied": False}
    temp_clahe_path = output_file.parent / f".tmp_clahe_{input_file.name}"

    if enable_clahe:
        t_clahe_start = time.time()
        balanced_img = apply_clahe_lab(orig_img, clip_limit=clip_limit, tile_grid_size=tile_grid_size)
        cv2.imwrite(str(temp_clahe_path), balanced_img)
        clahe_elapsed_ms = round((time.time() - t_clahe_start) * 1000, 2)
        clahe_metrics = {
            "applied": True,
            "color_space": "LAB",
            "clip_limit": clip_limit,
            "tile_grid_size": list(tile_grid_size),
            "duration_ms": clahe_elapsed_ms
        }
        upscale_source = str(temp_clahe_path)
    else:
        upscale_source = str(input_file)

    # 3. Super-Resolution via Real-ESRGAN
    esrgan_metrics = {"applied": False}
    try:
        if enable_upscale:
            esrgan_result = run_realesrgan(
                input_path=upscale_source,
                output_path=str(output_file),
                scale=scale,
                model_name=model_name,
                binary_path=binary_path,
                models_dir=models_dir
            )
            esrgan_metrics = {
                "applied": True,
                "scale": scale,
                "model": model_name,
                "duration_ms": esrgan_result["elapsed_ms"]
            }
        else:
            shutil.copyfile(upscale_source, str(output_file))
    finally:
        # Clean up temporary CLAHE intermediate
        if temp_clahe_path.exists():
            try:
                temp_clahe_path.unlink()
            except Exception:
                pass

    # Inspect enhanced output
    enhanced_img = cv2.imread(str(output_file))
    enh_h, enh_w = (enhanced_img.shape[0], enhanced_img.shape[1]) if enhanced_img is not None else (orig_h * scale, orig_w * scale)
    enh_size_bytes = output_file.stat().st_size if output_file.exists() else 0

    # 4. The Sentinel Visual Critique
    sentinel_critique = {}
    if enable_critique:
        sentinel_critique = critique_with_sentinel(str(output_file), ollama_host=ollama_host)

    total_duration_ms = round((time.time() - total_start) * 1000, 2)

    # 5. Compile Metadata
    metadata: Dict[str, Any] = {
        "status": "success",
        "input": {
            "path": str(input_file),
            "filename": input_file.name,
            "dimensions": f"{orig_w}x{orig_h}",
            "size_bytes": orig_size_bytes
        },
        "output": {
            "path": str(output_file),
            "filename": output_file.name,
            "dimensions": f"{enh_w}x{enh_h}",
            "size_bytes": enh_size_bytes
        },
        "clahe": clahe_metrics,
        "super_resolution": esrgan_metrics,
        "sentinel_critique": sentinel_critique,
        "total_duration_ms": total_duration_ms
    }

    # Save sidecar critique JSON
    sidecar_json = output_file.with_suffix(".json")
    with open(sidecar_json, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    return metadata


class PixelSpicer:
    """Singleton wrapper exposing pixel_spicer image operations."""
    spice_image = staticmethod(spice_image)
    run = staticmethod(spice_image)
    enhance = staticmethod(spice_image)
    apply_clahe_lab = staticmethod(apply_clahe_lab)
    run_realesrgan = staticmethod(run_realesrgan)
    critique_with_sentinel = staticmethod(critique_with_sentinel)


# Singleton instance for direct import across modules
spicer = PixelSpicer()


# =============================================================================
# 💻 CLI INTERFACE
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Andromeda Pixel Spicer: CLAHE + Real-ESRGAN + Moondream")
    parser.add_argument("input", help="Path to input image")
    parser.add_argument("-o", "--output", help="Path to output enhanced image")
    parser.add_argument("-s", "--scale", type=int, default=4, choices=[2, 3, 4], help="Upscale factor (default: 4)")
    parser.add_argument("-m", "--model", default="realesrgan-x4plus", help="Real-ESRGAN model name (default: realesrgan-x4plus)")
    parser.add_argument("--clip-limit", type=float, default=2.0, help="CLAHE clip limit (default: 2.0)")
    parser.add_argument("--no-clahe", action="store_true", help="Skip CLAHE dynamic range balance")
    parser.add_argument("--no-upscale", action="store_true", help="Skip Real-ESRGAN super-resolution")
    parser.add_argument("--no-critique", action="store_true", help="Skip Moondream visual critique")

    args = parser.parse_args()

    print(f"\n🔮 [Pixel Spicer] Processing: {args.input}")
    try:
        res = spice_image(
            input_path=args.input,
            output_path=args.output,
            scale=args.scale,
            model_name=args.model,
            clip_limit=args.clip_limit,
            enable_clahe=not args.no_clahe,
            enable_upscale=not args.no_upscale,
            enable_critique=not args.no_critique
        )

        print("\n" + "="*70)
        print("✅  ENHANCEMENT COMPLETE")
        print("="*70)
        print(f"📁 Source:      {res['input']['path']} ({res['input']['dimensions']})")
        print(f"✨ Enhanced:    {res['output']['path']} ({res['output']['dimensions']})")
        print(f"🎨 CLAHE:       {res['clahe']['duration_ms']} ms")
        print(f"🚀 Real-ESRGAN: {res['super_resolution']['duration_ms']} ms ({res['super_resolution']['scale']}x)")
        print(f"⏱️ Total Time:  {res['total_duration_ms']} ms")
        print("-" * 70)
        if res.get("sentinel_critique", {}).get("critique"):
            print("👁️  THE SENTINEL VISUAL CRITIQUE:")
            print(res["sentinel_critique"]["critique"])
        print("="*70 + "\n")

    except Exception as e:
        print(f"❌ Error during enhancement: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
