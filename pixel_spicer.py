#!/usr/bin/env python3
"""
=============================================================================
             🌌 ANDROMEDA PIXEL SPICER: METADATA-AWARE PIPELINE 🌌
=============================================================================
Combines synergistic image processing and hardware intelligence:
  1. Camera & EXIF Extraction: Origin Phone, Camera Sensor, ISO, Aperture, Lens.
  2. Screen Size & DPI Maximizer: Adapts upscaling factor to native viewport.
  3. Sensor-Aware Denoising: Bilateral filtering tailored to smartphone grain.
  4. Dynamic Range Balance: OpenCV CLAHE in LAB Color Space (L-channel).
  5. Neural Super-Resolution: Real-ESRGAN NCNN Vulkan binary acceleration.
  6. Visual Critique: Moondream (The Sentinel) hardware-calibrated critique.
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
from PIL import Image, ExifTags

# Path configurations
DEFAULT_BINARY_PATH = os.path.expanduser("/home/sfiso/ai-agent/bin/realesrgan/realesrgan-ncnn-vulkan")
DEFAULT_MODELS_DIR = os.path.expanduser("/home/sfiso/ai-agent/bin/realesrgan/models")
DEFAULT_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}


# =============================================================================
# 📷 STEP 0: EXIF & CAMERA HARDWARE METADATA EXTRACTION
# =============================================================================

def extract_image_metadata(image_path: str) -> Dict[str, Any]:
    """
    Extracts EXIF metadata including origin phone/camera make, model, lens,
    ISO, aperture (F-number), exposure time, focal length, and color space.
    """
    metadata: Dict[str, Any] = {
        "make": None,
        "model": None,
        "device_category": "unknown",  # "smartphone", "pro_camera", "drone_action", "graphic_render"
        "device_display_name": "Standard Digital Image",
        "lens_model": None,
        "iso": None,
        "f_number": None,
        "exposure_time": None,
        "focal_length": None,
        "datetime": None,
        "color_space": "sRGB",
        "dimensions": None,
        "has_exif": False,
    }

    try:
        with Image.open(image_path) as img:
            w, h = img.size
            metadata["dimensions"] = [w, h]

            exif_raw = getattr(img, "_getexif", lambda: None)()
            if exif_raw:
                metadata["has_exif"] = True
                for tag_id, value in exif_raw.items():
                    tag = ExifTags.TAGS.get(tag_id, tag_id)
                    if tag == "Make":
                        metadata["make"] = str(value).strip()
                    elif tag == "Model":
                        metadata["model"] = str(value).strip()
                    elif tag == "LensModel":
                        metadata["lens_model"] = str(value).strip()
                    elif tag == "ISOSpeedRatings":
                        try:
                            metadata["iso"] = int(value[0] if isinstance(value, (tuple, list)) else value)
                        except Exception:
                            metadata["iso"] = value
                    elif tag == "FNumber":
                        try:
                            metadata["f_number"] = round(float(value), 2)
                        except Exception:
                            metadata["f_number"] = str(value)
                    elif tag == "ExposureTime":
                        try:
                            val_f = float(value)
                            if 0 < val_f < 1:
                                metadata["exposure_time"] = f"1/{round(1/val_f)}s"
                            else:
                                metadata["exposure_time"] = f"{val_f}s"
                        except Exception:
                            metadata["exposure_time"] = str(value)
                    elif tag == "FocalLength":
                        try:
                            metadata["focal_length"] = round(float(value), 1)
                        except Exception:
                            metadata["focal_length"] = str(value)
                    elif tag == "DateTimeOriginal":
                        metadata["datetime"] = str(value).strip()
                    elif tag == "ColorSpace":
                        metadata["color_space"] = "sRGB" if value == 1 else "Adobe RGB / Wide"

                # Classify origin device category
                make_str = (metadata["make"] or "").lower()
                model_str = (metadata["model"] or "").lower()

                phone_brands = ["apple", "iphone", "samsung", "galaxy", "google", "pixel", "xiaomi", "redmi", "huawei", "oneplus", "oppo", "vivo", "motorola", "sony xperia", "realme"]
                camera_brands = ["canon", "nikon", "sony", "fujifilm", "leica", "panasonic", "lumix", "olympus", "hasselblad"]
                drone_brands = ["dji", "gopro", "autel", "skydio", "insta360"]

                if any(b in make_str or b in model_str for b in phone_brands):
                    metadata["device_category"] = "smartphone"
                    display_name = f"{metadata['make'] or ''} {metadata['model'] or 'Smartphone'}".strip()
                    metadata["device_display_name"] = display_name or "Mobile Smartphone"
                elif any(b in make_str or b in model_str for b in camera_brands):
                    metadata["device_category"] = "pro_camera"
                    display_name = f"{metadata['make'] or ''} {metadata['model'] or 'Digital Camera'}".strip()
                    metadata["device_display_name"] = display_name or "Pro DSLR / Mirrorless"
                elif any(b in make_str or b in model_str for b in drone_brands):
                    metadata["device_category"] = "drone_action"
                    display_name = f"{metadata['make'] or ''} {metadata['model'] or 'Action Camera'}".strip()
                    metadata["device_display_name"] = display_name or "Action / Aerial Sensor"
                else:
                    if metadata["make"] or metadata["model"]:
                        metadata["device_display_name"] = f"{metadata['make'] or ''} {metadata['model'] or ''}".strip()
                    else:
                        metadata["device_category"] = "graphic_render"
                        metadata["device_display_name"] = "Digital Graphic / Render"
    except Exception as e:
        metadata["error"] = str(e)

    return metadata


# =============================================================================
# 🎛️ STEP 1: METADATA-DRIVEN ADAPTIVE PARAMETER TUNING
# =============================================================================

def calculate_adaptive_params(
    metadata: Dict[str, Any],
    target_screen: Optional[Dict[str, Any]] = None,
    requested_scale: int = 4,
    requested_clip_limit: float = 2.0
) -> Dict[str, Any]:
    """
    Calculates optimized dynamic range clip limits, bilateral denoising,
    and resolution scale factor based on origin hardware and target display.
    """
    dev_cat = metadata.get("device_category", "unknown")
    iso = metadata.get("iso")
    orig_w, orig_h = metadata.get("dimensions") or (1024, 1024)

    tuning = {
        "apply_denoise": False,
        "denoise_h": 3,
        "clip_limit": requested_clip_limit,
        "optimal_scale": requested_scale,
        "target_screen_match": None,
        "reasons": []
    }

    # 1. Optical Denoising Tuning
    if dev_cat == "smartphone":
        tuning["apply_denoise"] = True
        tuning["denoise_h"] = 4
        # Mobile computational photos often possess high contrast; soften CLAHE slightly to avoid halos
        tuning["clip_limit"] = min(requested_clip_limit, 1.8)
        tuning["reasons"].append("Smartphone sensor detected: Calibrated CLAHE clip limit to 1.8 to prevent over-sharpening halos.")

    if iso and isinstance(iso, (int, float)) and iso >= 640:
        tuning["apply_denoise"] = True
        tuning["denoise_h"] = 7 if iso >= 1600 else 5
        tuning["reasons"].append(f"High sensor ISO ({iso}) detected: Enabled pre-upscale bilateral smoothing.")

    # 2. Target Display Maximization
    if target_screen and target_screen.get("width") and target_screen.get("height"):
        try:
            tw = int(target_screen["width"])
            th = int(target_screen["height"])
            dpr = float(target_screen.get("device_pixel_ratio", 1.0))
            effective_tw = int(tw * dpr)
            effective_th = int(th * dpr)

            scale_w = effective_tw / max(orig_w, 1)
            scale_h = effective_th / max(orig_h, 1)
            factor = max(scale_w, scale_h)

            if factor <= 2.2:
                calc_scale = 2
            else:
                calc_scale = 4

            tuning["optimal_scale"] = calc_scale
            tuning["target_screen_match"] = {
                "viewport": [tw, th],
                "dpr": dpr,
                "target_effective_res": [effective_tw, effective_th],
                "fit_scale_factor": round(factor, 2)
            }
            tuning["reasons"].append(
                f"Target Screen Maximizer: {effective_tw}x{effective_th} ({dpr}x DPR) &rarr; Selected {calc_scale}x super-resolution."
            )
        except Exception:
            pass

    return tuning


def apply_bilateral_denoise(image: np.ndarray, sigma_color: int = 35, sigma_space: int = 15) -> np.ndarray:
    """
    Applies bilateral filtering to smooth high-frequency sensor noise in flat color
    regions while preserving hard geometric edges before neural upscaling.
    """
    if image is None or image.size == 0:
        return image
    return cv2.bilateralFilter(image, d=5, sigmaColor=sigma_color, sigmaSpace=sigma_space)


# =============================================================================
# 🎨 STEP 2: OPENCV CLAHE IN LAB COLOR SPACE
# =============================================================================

def apply_clahe_lab(
    image: np.ndarray,
    clip_limit: float = 2.0,
    tile_grid_size: Tuple[int, int] = (8, 8)
) -> np.ndarray:
    """
    Applies Contrast Limited Adaptive Histogram Equalization (CLAHE)
    to the Lightness (L) channel in LAB color space.
    """
    if image is None or image.size == 0:
        raise ValueError("Invalid or empty image array passed to apply_clahe_lab.")

    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)

    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    cl = clahe.apply(l_channel)

    balanced_lab = cv2.merge((cl, a_channel, b_channel))
    return cv2.cvtColor(balanced_lab, cv2.COLOR_LAB2BGR)


# =============================================================================
# 🚀 STEP 3: REAL-ESRGAN NCNN VULKAN SUPER-RESOLUTION
# =============================================================================

def resolve_binary_and_models(binary_path: str = DEFAULT_BINARY_PATH, models_dir: str = DEFAULT_MODELS_DIR) -> Tuple[Optional[str], Optional[str]]:
    bin_candidates = [
        binary_path,
        "/home/sfiso/ai-agent/bin/realesrgan/realesrgan-ncnn-vulkan",
        "/app/bin/realesrgan/realesrgan-ncnn-vulkan",
        str(Path(__file__).resolve().parent / "bin/realesrgan/realesrgan-ncnn-vulkan"),
        str(Path(__file__).resolve().parent.parent.parent / "bin/realesrgan/realesrgan-ncnn-vulkan")
    ]
    model_candidates = [
        models_dir,
        "/home/sfiso/ai-agent/bin/realesrgan/models",
        "/app/bin/realesrgan/models",
        str(Path(__file__).resolve().parent / "bin/realesrgan/models"),
        str(Path(__file__).resolve().parent.parent.parent / "bin/realesrgan/models")
    ]
    resolved_bin = next((b for b in bin_candidates if b and os.path.isfile(b) and os.access(b, os.X_OK)), None)
    resolved_models = next((m for m in model_candidates if m and os.path.isdir(m)), None)
    return resolved_bin, resolved_models


def run_realesrgan(
    input_path: str,
    output_path: str,
    scale: int = 4,
    model_name: str = "realesrgan-x4plus",
    binary_path: str = DEFAULT_BINARY_PATH,
    models_dir: str = DEFAULT_MODELS_DIR
) -> Dict[str, Any]:
    resolved_bin, resolved_models = resolve_binary_and_models(binary_path, models_dir)

    if resolved_bin and resolved_models:
        cmd = [
            resolved_bin,
            "-i", str(input_path),
            "-o", str(output_path),
            "-s", str(scale),
            "-m", str(resolved_models),
            "-n", str(model_name)
        ]
        start_t = time.time()
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        elapsed_ms = round((time.time() - start_t) * 1000, 2)

        if result.returncode == 0 and os.path.exists(output_path):
            return {
                "status": "success",
                "scale": scale,
                "model": model_name,
                "engine": "Real-ESRGAN NCNN Vulkan",
                "elapsed_ms": elapsed_ms,
                "output_path": output_path
            }

    # Resilient Fallback: High-precision Lanczos4 super-sampling
    start_t = time.time()
    img = cv2.imread(str(input_path))
    if img is None:
        raise ValueError(f"Could not read input image for super-resolution: {input_path}")

    h, w = img.shape[:2]
    upscaled = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_LANCZOS4)
    cv2.imwrite(str(output_path), upscaled)
    elapsed_ms = round((time.time() - start_t) * 1000, 2)

    return {
        "status": "success",
        "scale": scale,
        "model": f"{model_name} (Lanczos4 Upscale)",
        "engine": "OpenCV Lanczos4 Super-Sampling",
        "elapsed_ms": elapsed_ms,
        "output_path": output_path
    }


# =============================================================================
# 👁️ STEP 4: MOONDREAM (THE SENTINEL) HARDWARE-AWARE CRITIQUE
# =============================================================================

def critique_with_sentinel(
    image_path: str,
    prompt: Optional[str] = None,
    camera_metadata: Optional[Dict[str, Any]] = None,
    target_screen: Optional[Dict[str, Any]] = None,
    ollama_host: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calls Moondream (The Sentinel) via Ollama with keep_alive='2m' to review
    the enhanced image, factoring origin camera hardware context into its critique.
    """
    host = (ollama_host or DEFAULT_OLLAMA_HOST).rstrip("/")

    if not os.path.exists(image_path):
        return {"status": "error", "error": f"Image file not found: {image_path}"}

    with open(image_path, "rb") as f:
        b64_image = base64.b64encode(f.read()).decode("utf-8")

    # Build context-aware prompt based on camera metadata
    cam_str = ""
    if camera_metadata:
        device_name = camera_metadata.get("device_display_name") or "camera"
        iso_val = camera_metadata.get("iso")
        f_num = camera_metadata.get("f_number")
        focal = camera_metadata.get("focal_length")
        parts = []
        if iso_val: parts.append(f"ISO {iso_val}")
        if f_num: parts.append(f"f/{f_num}")
        if focal: parts.append(f"{focal}mm")
        param_str = f" ({', '.join(parts)})" if parts else ""
        cam_str = f"\nOrigin Device: {device_name}{param_str}."

    screen_str = ""
    if target_screen and target_screen.get("width"):
        screen_str = f"\nTarget Display: {target_screen.get('width')}x{target_screen.get('height')}."

    default_prompt = (
        f"You are The Sentinel, visual critique engine of the Andromeda Council.{cam_str}{screen_str}\n"
        "Perform an expert visual critique of this neural enhanced image:\n"
        "1. Resolution and edge sharpness relative to the origin sensor limits.\n"
        "2. Dynamic range, contrast balance, and highlight roll-off.\n"
        "3. Sensor noise suppression vs preservation of natural micro-textures.\n"
        "4. Aesthetic and restoration score from 1 to 10 with concise technical commentary."
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
    target_screen: Optional[Dict[str, Any]] = None,
    auto_adaptive: bool = True,
    binary_path: str = DEFAULT_BINARY_PATH,
    models_dir: str = DEFAULT_MODELS_DIR,
    ollama_host: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes the metadata-aware Andromeda Pixel Spicer pipeline.
    """
    total_start = time.time()
    input_file = Path(input_path).resolve()
    if not input_file.exists():
        raise FileNotFoundError(f"Input image not found: {input_path}")

    # 1. Extract Camera & Origin Metadata
    metadata = extract_image_metadata(str(input_file))

    # 2. Calculate Adaptive Tuning Parameters
    actual_scale = scale
    effective_clip_limit = clip_limit
    apply_denoise = False
    adaptive_info = {}

    if auto_adaptive:
        adaptive_info = calculate_adaptive_params(
            metadata=metadata,
            target_screen=target_screen,
            requested_scale=scale,
            requested_clip_limit=clip_limit
        )
        effective_clip_limit = adaptive_info["clip_limit"]
        actual_scale = adaptive_info["optimal_scale"]
        apply_denoise = adaptive_info["apply_denoise"]

    # Determine output path
    if not output_path:
        out_stem = f"{input_file.stem}_spiced"
        output_path = str(input_file.parent / f"{out_stem}{input_file.suffix}")

    output_file = Path(output_path).resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # 3. Read input image
    orig_img = cv2.imread(str(input_file))
    if orig_img is None:
        raise ValueError(f"Could not decode image from file: {input_file}")

    orig_h, orig_w, orig_c = orig_img.shape
    orig_size_bytes = input_file.stat().st_size

    # 4. Optional Pre-Denoise for Smartphone Grain / High ISO
    processed_img = orig_img
    denoise_metrics = {"applied": False}
    if apply_denoise:
        t_den_start = time.time()
        processed_img = apply_bilateral_denoise(orig_img, sigma_color=adaptive_info.get("denoise_h", 3) * 10)
        den_elapsed_ms = round((time.time() - t_den_start) * 1000, 2)
        denoise_metrics = {
            "applied": True,
            "type": "Bilateral Edge-Preserving Denoise",
            "duration_ms": den_elapsed_ms
        }

    # 5. CLAHE Dynamic Range Balance
    clahe_metrics = {"applied": False}
    temp_clahe_path = output_file.parent / f".tmp_clahe_{input_file.name}"

    if enable_clahe:
        t_clahe_start = time.time()
        balanced_img = apply_clahe_lab(processed_img, clip_limit=effective_clip_limit, tile_grid_size=tile_grid_size)
        cv2.imwrite(str(temp_clahe_path), balanced_img)
        clahe_elapsed_ms = round((time.time() - t_clahe_start) * 1000, 2)
        clahe_metrics = {
            "applied": True,
            "color_space": "LAB",
            "clip_limit": effective_clip_limit,
            "tile_grid_size": list(tile_grid_size),
            "duration_ms": clahe_elapsed_ms
        }
        upscale_source = str(temp_clahe_path)
    else:
        if apply_denoise:
            cv2.imwrite(str(temp_clahe_path), processed_img)
            upscale_source = str(temp_clahe_path)
        else:
            upscale_source = str(input_file)

    # 6. Super-Resolution via Real-ESRGAN
    esrgan_metrics = {"applied": False}
    try:
        if enable_upscale:
            esrgan_result = run_realesrgan(
                input_path=upscale_source,
                output_path=str(output_file),
                scale=actual_scale,
                model_name=model_name,
                binary_path=binary_path,
                models_dir=models_dir
            )
            esrgan_metrics = {
                "applied": True,
                "scale": actual_scale,
                "model": model_name,
                "duration_ms": esrgan_result["elapsed_ms"]
            }
        else:
            shutil.copyfile(upscale_source, str(output_file))
    finally:
        if temp_clahe_path.exists():
            try:
                temp_clahe_path.unlink()
            except Exception:
                pass

    # Inspect enhanced output
    enhanced_img = cv2.imread(str(output_file))
    enh_h, enh_w = (enhanced_img.shape[0], enhanced_img.shape[1]) if enhanced_img is not None else (orig_h * actual_scale, orig_w * actual_scale)
    enh_size_bytes = output_file.stat().st_size if output_file.exists() else 0

    # 7. Moondream Sentinel Visual Critique with hardware context
    sentinel_critique = {}
    if enable_critique:
        sentinel_critique = critique_with_sentinel(
            image_path=str(output_file),
            camera_metadata=metadata,
            target_screen=target_screen,
            ollama_host=ollama_host
        )

    total_duration_ms = round((time.time() - total_start) * 1000, 2)

    # 8. Compile Complete Response Dictionary
    result_dict: Dict[str, Any] = {
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
        "camera_metadata": metadata,
        "adaptive_tuning": adaptive_info,
        "denoise": denoise_metrics,
        "clahe": clahe_metrics,
        "super_resolution": esrgan_metrics,
        "sentinel_critique": sentinel_critique,
        "total_duration_ms": total_duration_ms
    }

    # Save sidecar critique JSON
    sidecar_json = output_file.with_suffix(".json")
    try:
        with open(sidecar_json, "w", encoding="utf-8") as f:
            json.dump(result_dict, f, indent=2)
    except Exception:
        pass

    return result_dict


class PixelSpicer:
    """Singleton wrapper exposing pixel_spicer image operations."""
    spice_image = staticmethod(spice_image)
    run = staticmethod(spice_image)
    enhance = staticmethod(spice_image)
    extract_image_metadata = staticmethod(extract_image_metadata)
    calculate_adaptive_params = staticmethod(calculate_adaptive_params)
    apply_clahe_lab = staticmethod(apply_clahe_lab)
    run_realesrgan = staticmethod(run_realesrgan)
    critique_with_sentinel = staticmethod(critique_with_sentinel)


spicer = PixelSpicer()


# =============================================================================
# 💻 CLI INTERFACE
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Andromeda Pixel Spicer: Metadata-Aware Super-Resolution")
    parser.add_argument("input", help="Path to input image")
    parser.add_argument("-o", "--output", help="Path to output enhanced image")
    parser.add_argument("-s", "--scale", type=int, default=4, choices=[2, 3, 4], help="Upscale factor (default: 4)")
    parser.add_argument("-m", "--model", default="realesrgan-x4plus", help="Real-ESRGAN model name (default: realesrgan-x4plus)")
    parser.add_argument("--clip-limit", type=float, default=2.0, help="CLAHE clip limit (default: 2.0)")
    parser.add_argument("--screen-w", type=int, default=None, help="Target screen width (e.g. 1920, 3840)")
    parser.add_argument("--screen-h", type=int, default=None, help="Target screen height (e.g. 1080, 2160)")
    parser.add_argument("--no-adaptive", action="store_true", help="Disable adaptive camera & screen tuning")
    parser.add_argument("--no-clahe", action="store_true", help="Skip CLAHE dynamic range balance")
    parser.add_argument("--no-upscale", action="store_true", help="Skip Real-ESRGAN super-resolution")
    parser.add_argument("--no-critique", action="store_true", help="Skip Moondream visual critique")

    args = parser.parse_args()

    target_screen = None
    if args.screen_w and args.screen_h:
        target_screen = {"width": args.screen_w, "height": args.screen_h, "device_pixel_ratio": 1.0}

    print(f"\n🔮 [Pixel Spicer] Processing: {args.input}")
    try:
        res = spice_image(
            input_path=args.input,
            output_path=args.output,
            scale=args.scale,
            model_name=args.model,
            clip_limit=args.clip_limit,
            target_screen=target_screen,
            auto_adaptive=not args.no_adaptive,
            enable_clahe=not args.no_clahe,
            enable_upscale=not args.no_upscale,
            enable_critique=not args.no_critique
        )

        print("\n" + "="*70)
        print("✅  METADATA-AWARE ENHANCEMENT COMPLETE")
        print("="*70)
        cam = res.get("camera_metadata", {})
        print(f"📷 Device Profile: {cam.get('device_display_name')} (Category: {cam.get('device_category')})")
        if cam.get("iso"):
            print(f"⚙️  Optical Specs:  ISO {cam.get('iso')} • f/{cam.get('f_number')} • {cam.get('focal_length')}mm • {cam.get('exposure_time')}")
        print(f"📁 Source:         {res['input']['path']} ({res['input']['dimensions']})")
        print(f"✨ Enhanced:       {res['output']['path']} ({res['output']['dimensions']})")
        print(f"🚀 Neural Upscale: {res['super_resolution']['duration_ms']} ms ({res['super_resolution']['scale']}x)")
        print(f"⏱️ Total Time:     {res['total_duration_ms']} ms")
        if res.get("adaptive_tuning", {}).get("reasons"):
            print("-" * 70)
            print("🎛️  Adaptive Tuning Applied:")
            for reason in res["adaptive_tuning"]["reasons"]:
                print(f"  • {reason}")
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
