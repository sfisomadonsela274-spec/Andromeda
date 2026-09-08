#!/usr/bin/env python3
"""
=============================================================================
             🌌 ANDROMEDA SPICE DAEMON: WATCHDOG PROCESSOR 🌌
=============================================================================
Continuous file system daemon monitoring /home/sfiso/photos_incoming for
new photos, processing them via pixel_spicer.py (CLAHE LAB + Real-ESRGAN
Vulkan + Moondream The Sentinel), and saving enhanced assets into
/home/sfiso/photos_enhanced.
=============================================================================
"""

import os
import sys
import time
import shutil
import signal
import hashlib
import argparse
from pathlib import Path
from typing import Optional, Set

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileMovedEvent

# Import the core enhancement pipeline
try:
    from pixel_spicer import spice_image, SUPPORTED_EXTENSIONS
except ImportError:
    # Ensure current directory is on sys.path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from pixel_spicer import spice_image, SUPPORTED_EXTENSIONS


DEFAULT_INCOMING = os.path.expanduser("/home/sfiso/photos_incoming")
DEFAULT_ENHANCED = os.path.expanduser("/home/sfiso/photos_enhanced")


def compute_file_hash(filepath: Path) -> str:
    """Computes quick SHA256 of first 64KB + file size for duplicate suppression."""
    try:
        hasher = hashlib.sha256()
        hasher.update(str(filepath.stat().st_size).encode())
        with open(filepath, "rb") as f:
            chunk = f.read(65536)
            hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return str(filepath)


def wait_for_file_settled(filepath: Path, timeout: float = 10.0, check_interval: float = 0.5) -> bool:
    """
    Waits until a newly created or copied file stops growing in size,
    preventing race conditions where enhancement starts before file write finishes.
    """
    start_time = time.time()
    last_size = -1

    while time.time() - start_time < timeout:
        try:
            if not filepath.exists():
                return False
            current_size = filepath.stat().st_size
            if current_size > 0 and current_size == last_size:
                return True
            last_size = current_size
        except Exception:
            pass
        time.sleep(check_interval)

    return filepath.exists() and filepath.stat().st_size > 0


class SpiceDropHandler(FileSystemEventHandler):
    """
    Watchdog handler that listens for image files dropped into the incoming folder,
    dispatches them through Pixel Spicer, and stores the enhanced image and critique.
    """

    def __init__(
        self,
        incoming_dir: Path,
        enhanced_dir: Path,
        scale: int = 4,
        model: str = "realesrgan-x4plus",
        clip_limit: float = 2.0,
        archive_processed: bool = False
    ):
        super().__init__()
        self.incoming_dir = incoming_dir
        self.enhanced_dir = enhanced_dir
        self.scale = scale
        self.model = model
        self.clip_limit = clip_limit
        self.archive_processed = archive_processed
        self.processed_hashes: Set[str] = set()

        if self.archive_processed:
            self.archive_dir = self.incoming_dir / ".processed"
            self.archive_dir.mkdir(parents=True, exist_ok=True)

    def is_valid_image_file(self, filepath: Path) -> bool:
        """Checks if file is a non-hidden, supported image."""
        if filepath.name.startswith(".") or filepath.name.startswith("~"):
            return False
        return filepath.suffix.lower() in SUPPORTED_EXTENSIONS

    def on_created(self, event: FileCreatedEvent):
        if event.is_directory:
            return
        filepath = Path(event.src_path)
        self.handle_incoming_file(filepath)

    def on_moved(self, event: FileMovedEvent):
        if event.is_directory:
            return
        filepath = Path(event.dest_path)
        self.handle_incoming_file(filepath)

    def handle_incoming_file(self, filepath: Path):
        """Processes a single incoming image file."""
        if not self.is_valid_image_file(filepath):
            return

        print(f"\n📥 [Spice Daemon] Detected incoming image: {filepath.name}")

        # Wait for copy / download to finish
        if not wait_for_file_settled(filepath):
            print(f"⚠️ [Spice Daemon] File did not settle or was removed: {filepath.name}", file=sys.stderr)
            return

        file_hash = compute_file_hash(filepath)
        if file_hash in self.processed_hashes:
            print(f"ℹ️ [Spice Daemon] Skipping already processed image: {filepath.name}")
            return

        self.processed_hashes.add(file_hash)

        # Destination paths
        enhanced_filename = f"{filepath.stem}_spiced{filepath.suffix}"
        destination_image = self.enhanced_dir / enhanced_filename

        print(f"🚀 [Spice Daemon] Enhancing {filepath.name} -> {enhanced_filename} (Scale: {self.scale}x, Model: {self.model})...")

        try:
            res = spice_image(
                input_path=str(filepath),
                output_path=str(destination_image),
                scale=self.scale,
                model_name=self.model,
                clip_limit=self.clip_limit
            )

            print("=" * 65)
            print(f"✅ [Spice Daemon] Finished {filepath.name} in {res['total_duration_ms']} ms")
            print(f"✨ Enhanced output: {destination_image}")
            print(f"📋 Metadata saved:  {destination_image.with_suffix('.json')}")
            if res.get("sentinel_critique", {}).get("critique"):
                critique_preview = res["sentinel_critique"]["critique"].replace("\n", " ")[:120]
                print(f"👁️ The Sentinel:    {critique_preview}...")
            print("=" * 65)

            # Move to archive folder if requested
            if self.archive_processed:
                target_archive = self.archive_dir / filepath.name
                shutil.move(str(filepath), str(target_archive))
                print(f"📦 [Spice Daemon] Archived source to {target_archive}")

        except Exception as e:
            print(f"❌ [Spice Daemon] Error enhancing {filepath.name}: {e}", file=sys.stderr)


def sweep_existing_images(handler: SpiceDropHandler):
    """Processes any existing supported images found in incoming folder on startup."""
    incoming_dir = handler.incoming_dir
    existing = sorted([
        p for p in incoming_dir.iterdir()
        if p.is_file() and handler.is_valid_image_file(p)
    ])

    if existing:
        print(f"\n🔍 [Spice Daemon] Found {len(existing)} existing image(s) in {incoming_dir}. Processing sweep...")
        for img_path in existing:
            handler.handle_incoming_file(img_path)
    else:
        print(f"ℹ️ [Spice Daemon] No pending images found in {incoming_dir}.")


def run_daemon(
    incoming_dir: str = DEFAULT_INCOMING,
    enhanced_dir: str = DEFAULT_ENHANCED,
    scale: int = 4,
    model: str = "realesrgan-x4plus",
    clip_limit: float = 2.0,
    archive: bool = False,
    once: bool = False
):
    """Main daemon runner with directory watchdog and graceful shutdown."""
    in_path = Path(incoming_dir).resolve()
    out_path = Path(enhanced_dir).resolve()

    in_path.mkdir(parents=True, exist_ok=True)
    out_path.mkdir(parents=True, exist_ok=True)

    print("""
=============================================================================
             🌌 ANDROMEDA SPICE DAEMON INITIALIZED 🌌
=============================================================================""")
    print(f"  📥 Incoming Watch Directory: {in_path}")
    print(f"  ✨ Enhanced Output Directory: {out_path}")
    print(f"  🚀 Pipeline:                 OpenCV CLAHE (LAB) + Real-ESRGAN ({scale}x, {model})")
    print(f"  👁️ Council Oversight:        Moondream (The Sentinel - keep_alive: 2m)")
    print(f"  📦 Auto-Archive:             {'Enabled (.processed/)' if archive else 'Disabled'}")
    print("=============================================================================")

    handler = SpiceDropHandler(
        incoming_dir=in_path,
        enhanced_dir=out_path,
        scale=scale,
        model=model,
        clip_limit=clip_limit,
        archive_processed=archive
    )

    # 1. Sweep existing backlog
    sweep_existing_images(handler)

    if once:
        print("🏁 [Spice Daemon] Batch sweep completed (--once requested). Exiting.")
        return

    # 2. Start Watchdog Observer
    observer = Observer()
    observer.schedule(handler, str(in_path), recursive=False)
    observer.start()
    print(f"\n👀 [Spice Daemon] Watching {in_path} for new incoming photos... (Press Ctrl+C to stop)")

    stop_flag = False

    def handle_sig(sig, frame):
        nonlocal stop_flag
        print("\n🛑 [Spice Daemon] Received shutdown signal. Stopping observer...")
        stop_flag = True

    signal.signal(signal.SIGINT, handle_sig)
    signal.signal(signal.SIGTERM, handle_sig)

    try:
        while not stop_flag:
            time.sleep(1.0)
    finally:
        observer.stop()
        observer.join()
        print("👋 [Spice Daemon] Observer stopped cleanly.")


def main():
    parser = argparse.ArgumentParser(description="Andromeda Spice Daemon: Watchdog photo enhancer")
    parser.add_argument("--incoming", default=DEFAULT_INCOMING, help=f"Directory to watch for incoming images (default: {DEFAULT_INCOMING})")
    parser.add_argument("--enhanced", default=DEFAULT_ENHANCED, help=f"Directory to save enhanced images (default: {DEFAULT_ENHANCED})")
    parser.add_argument("-s", "--scale", type=int, default=4, choices=[2, 3, 4], help="Super-resolution upscale factor (default: 4)")
    parser.add_argument("-m", "--model", default="realesrgan-x4plus", help="Real-ESRGAN model (default: realesrgan-x4plus)")
    parser.add_argument("--clip-limit", type=float, default=2.0, help="CLAHE clip limit (default: 2.0)")
    parser.add_argument("--archive", action="store_true", help="Move processed incoming images to .processed/ archive")
    parser.add_argument("--once", action="store_true", help="Process existing files in incoming directory and exit immediately")

    args = parser.parse_args()

    run_daemon(
        incoming_dir=args.incoming,
        enhanced_dir=args.enhanced,
        scale=args.scale,
        model=args.model,
        clip_limit=args.clip_limit,
        archive=args.archive,
        once=args.once
    )


if __name__ == "__main__":
    main()
