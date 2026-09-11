#!/usr/bin/env python3
import subprocess
import time
import re
import os
import sys

RUNTIME_DIR = "/home/sfiso/andromeda-runtime"
TUNNEL_FILE = os.path.join(RUNTIME_DIR, "public_url.txt")
USB_FILE = "/media/sfiso/USB STICK/Projects/ai-agent/public_url.txt"
DATA_TUNNEL_FILE = os.path.join(RUNTIME_DIR, "data", "tunnel", "public_url.txt")

deploy_process = None

def extract_url():
    """Extract active Cloudflare Tunnel URL progressively without timeouts."""
    for tail_count in ["100", "500", "2000"]:
        try:
            res = subprocess.run(
                ["docker", "logs", "--tail", tail_count, "cloudflared"],
                capture_output=True,
                text=True,
                timeout=4
            )
            combined = res.stdout + res.stderr
            matches = re.findall(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", combined)
            if matches:
                return matches[-1]
        except Exception as e:
            pass
    return None

def save_url(url):
    """Save active URL across runtime, data, and USB targets."""
    targets = [
        TUNNEL_FILE,
        DATA_TUNNEL_FILE,
        USB_FILE,
        os.path.join(RUNTIME_DIR, "andromeda", "public", "public_url.txt"),
        os.path.join(RUNTIME_DIR, "andromeda", "dist", "public_url.txt"),
        "/media/sfiso/USB STICK/Projects/ai-agent/andromeda/public/public_url.txt",
        "/media/sfiso/USB STICK/Projects/ai-agent/andromeda/dist/public_url.txt"
    ]
    for target in targets:
        try:
            parent = os.path.dirname(target)
            if os.path.isdir(parent):
                with open(target, "w") as f:
                    f.write(url + "\n")
        except Exception:
            pass

def deploy_github_pages():
    """Trigger background GitHub Pages edge deployment with concurrency guard."""
    global deploy_process
    try:
        if deploy_process and deploy_process.poll() is None:
            print("[URL Fetcher]: GitHub Pages deploy already running, skipping overlapping run.", file=sys.stderr)
            return

        deploy_script = os.path.join(RUNTIME_DIR, "deploy-gh-pages.sh")
        if os.path.exists(deploy_script):
            log_dir = os.path.join(RUNTIME_DIR, "logs")
            os.makedirs(log_dir, exist_ok=True)
            log_file = open(os.path.join(log_dir, "deploy-gh-pages.log"), "a")
            deploy_process = subprocess.Popen(
                ["/usr/bin/env", "bash", deploy_script],
                stdout=log_file,
                stderr=log_file,
                cwd=RUNTIME_DIR
            )
    except Exception as e:
        print(f"[Deploy Error]: {e}", file=sys.stderr)

def main():
    if "--once" in sys.argv:
        url = extract_url()
        if url:
            save_url(url)
            print(url)
            sys.exit(0)
        else:
            print("URL not found yet", file=sys.stderr)
            sys.exit(1)

    print("🌌 Andromeda Automated URL Fetcher Daemon active.")
    last_url = None
    while True:
        url = extract_url()
        if url:
            if url != last_url:
                last_url = url
                save_url(url)
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 🟢 New Public URL: {url}", flush=True)
                deploy_github_pages()
            else:
                # Also ensure USB target stays synced if USB drive was plugged in later
                if os.path.exists(os.path.dirname(USB_FILE)):
                    try:
                        if not os.path.exists(USB_FILE) or open(USB_FILE).read().strip() != url:
                            save_url(url)
                    except Exception:
                        pass
        time.sleep(5)

if __name__ == "__main__":
    main()
