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

def extract_url():
    try:
        res = subprocess.run(
            ["docker", "logs", "cloudflared"],
            capture_output=True,
            text=True,
            timeout=5
        )
        combined = res.stdout + res.stderr
        matches = re.findall(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", combined)
        if matches:
            return matches[-1]
    except Exception as e:
        print(f"[URL Fetcher Error]: {e}", file=sys.stderr)
    return None

def save_url(url):
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
    try:
        deploy_script = os.path.join(RUNTIME_DIR, "deploy-gh-pages.sh")
        if os.path.exists(deploy_script):
            subprocess.Popen(
                [deploy_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
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

    print("🌌 Andromeda Automated URL Fetcher Daemon started.")
    last_url = None
    while True:
        url = extract_url()
        if url and url != last_url:
            last_url = url
            save_url(url)
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 🟢 New Public URL: {url}", flush=True)
            deploy_github_pages()
        time.sleep(5)

if __name__ == "__main__":
    main()
