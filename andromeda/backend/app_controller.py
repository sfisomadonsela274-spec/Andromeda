"""
Unified App Controller for Jimmy and Andromeda
Handles dual-mode command execution across the Top 60 apps in 6 major domains:
Social Media, Streaming Sites, IDEs, CADs, Graphic Systems, and Music.
"""

import os
import shutil
import subprocess
import json
import logging
import re
import urllib.request
import urllib.parse
from typing import Dict, Any, Optional, Tuple, List

from app_registry import APP_REGISTRY, find_app_entry, get_apps_by_category
import puppeteer_bridge

def resolve_youtube_top_video(query: str) -> Dict[str, Optional[str]]:
    """Fast synchronous resolver extracting exact top videoId, title, and direct watch URL from YouTube."""
    try:
        clean_q = re.sub(r"\b(on|in|from)\s+youtube\b", "", query, flags=re.IGNORECASE).strip()
        clean_q = re.sub(r"^(play|watch|listen to)\s+", "", clean_q, flags=re.IGNORECASE).strip()
        if not clean_q:
            clean_q = query
        search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(clean_q)}"
        req = urllib.request.Request(
            search_url,
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        )
        html = urllib.request.urlopen(req, timeout=4).read().decode("utf-8")
        ids = re.findall(r"\"videoId\":\"([a-zA-Z0-9_-]{11})\"", html)
        titles = re.findall(r"\"title\":\{\"runs\":\[\{\"text\":\"([^\"]+)\"\}\]", html)
        vid = ids[0] if ids else None
        title = titles[0] if titles else clean_q
        return {
            "videoId": vid,
            "title": title,
            "url": f"https://www.youtube.com/watch?v={vid}&autoplay=1" if vid else f"https://www.youtube.com/results?search_query={urllib.parse.quote(clean_q)}"
        }
    except Exception as e:
        logging.warning(f"[YouTube Resolver] Error for '{query}': {e}")
        return {"videoId": None, "title": query, "url": None}

def detect_native_binary(app_entry: Dict[str, Any]) -> Optional[str]:
    """Check if desktop binary or Flatpak is available on the system."""
    for binary in app_entry.get("desktop_binaries", []):
        if shutil.which(binary):
            return binary
            
    flatpak_id = app_entry.get("flatpak_id")
    if flatpak_id and shutil.which("flatpak"):
        try:
            installed = subprocess.check_output(["flatpak", "list", "--app", "--columns=application"], text=True, timeout=3)
            if flatpak_id in installed:
                return f"flatpak run {flatpak_id}"
        except Exception:
            pass
            
    return None

def execute_app_command(
    app_identifier: str, 
    action: str = "open", 
    params: Optional[Dict[str, Any]] = None, 
    mode: str = "auto"
) -> Dict[str, Any]:
    """
    Execute a command on any registered application.
    
    Parameters:
      app_identifier: Name, key, or alias of the app (e.g. 'vscode', 'twitter', 'blender', 'youtube', 'figma', 'spotify')
      action: Target operation ('open', 'search', 'play', 'goto', 'user', 'channel', etc.)
      params: Dict of arguments (e.g. {'query': 'odeal', 'file': 'main.py', 'line': 42})
      mode: 'auto' (native if available, else web), 'desktop' (enforce native), 'web' (open in browser), 'headless' (scrape/interact via Puppeteer)
    """
    params = params or {}
    app = find_app_entry(app_identifier)
    
    if not app:
        return {
            "status": "error",
            "message": f"Application '{app_identifier}' is not registered in the Top 60 App Registry.",
            "supported_apps_count": len(APP_REGISTRY)
        }
        
    app_id = app["id"]
    app_name = app["name"]
    category = app["category"]
    actions = app.get("actions", {})
    
    # Check action support
    action_key = action.lower().strip()
    if action_key == "install":
        return install_app(app_identifier, method=params.get("method", "flatpak"))
    if action_key not in actions and "open" in actions:
        action_key = "open"
        
    # Determine target URL if applicable
    target_url = None
    if action_key in actions:
        url_builder = actions[action_key]
        try:
            target_url = url_builder(params)
        except Exception as e:
            target_url = app.get("web_base", "")
    elif app.get("web_base"):
        target_url = app["web_base"]

    # 1. Headless Execution Mode (Puppeteer Automation)
    if mode == "headless":
        if not target_url:
            return {"status": "error", "message": f"App '{app_name}' does not have a web interface for headless automation."}
            
        if category == "streaming" and app_id == "youtube" and action_key in ["play", "search"]:
            query = params.get("query", "")
            res = puppeteer_bridge.puppeteer_resolve_youtube(query)
            return {
                "status": "success",
                "app": app_name,
                "category": category,
                "action": action_key,
                "mode": "headless",
                "result": res
            }
        else:
            res = puppeteer_bridge.puppeteer_navigate(target_url)
            return {
                "status": "success",
                "app": app_name,
                "category": category,
                "action": action_key,
                "mode": "headless",
                "url": target_url,
                "page_title": res.get("title"),
                "summary": res.get("pageData", {}).get("text", "")[:500]
            }

    # 2. Native Desktop CLI Mode
    native_bin = detect_native_binary(app)
    use_desktop = (mode == "desktop") or (mode == "auto" and native_bin is not None)
    
    if use_desktop and native_bin:
        try:
            cli_builder = app.get("cli_builder")
            if cli_builder:
                cmd = cli_builder(params)
            else:
                base_args = native_bin.split()
                if params.get("file"):
                    base_args.append(params["file"])
                elif params.get("path"):
                    base_args.append(params["path"])
                cmd = base_args

            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=os.environ.copy())
            return {
                "status": "success",
                "app": app_name,
                "category": category,
                "action": action_key,
                "mode": "desktop",
                "binary": native_bin,
                "command": " ".join(cmd),
                "pid": proc.pid,
                "message": f"Launched native {app_name} on desktop (PID {proc.pid})"
            }
        except Exception as e:
            logging.warning(f"Failed to launch native {app_name}: {e}. Falling back to web.")
            if mode == "desktop":
                return {"status": "error", "message": f"Failed to launch desktop binary '{native_bin}': {e}"}

    # 3. Web Desktop Browser Mode
    if target_url:
        try:
            # Check if YouTube autoplay or specific media
            if category == "streaming" and app_id == "youtube" and action_key in ["play", "search"]:
                query = params.get("query", "")
                yt_info = resolve_youtube_top_video(query)
                if yt_info.get("url"):
                    target_url = yt_info["url"]
                else:
                    res = puppeteer_bridge.puppeteer_resolve_youtube(query)
                    if res.get("status") == "success" and res.get("url"):
                        target_url = res["url"] + ("&autoplay=1" if "?" in res["url"] else "?autoplay=1")

            browser_cmd = ["firefox", target_url]
            proc = subprocess.Popen(browser_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=os.environ.copy())
            return {
                "status": "success",
                "app": app_name,
                "category": category,
                "action": action_key,
                "mode": "web",
                "url": target_url,
                "pid": proc.pid,
                "message": f"Opened {app_name} in browser: {target_url}"
            }
        except Exception as e:
            return {"status": "error", "message": f"Failed to open browser URL for '{app_name}': {e}"}

    return {
        "status": "error",
        "message": f"No native binary or web action available for '{app_name}' (action: {action_key})"
    }

def get_category_summary() -> Dict[str, List[Dict[str, Any]]]:
    """Returns a list of top 10 apps categorized with their native availability status."""
    summary = {}
    for cat in ["social", "streaming", "ide", "cad", "graphics", "music"]:
        apps = get_apps_by_category(cat)
        cat_apps = []
        for a in apps:
            bin_installed = detect_native_binary(a) is not None
            cat_apps.append({
                "id": a["id"],
                "name": a["name"],
                "native_available": bin_installed,
                "web_url": a.get("web_base", "")
            })
        summary[cat] = cat_apps
    return summary

def install_app(app_identifier: str, method: str = "flatpak") -> Dict[str, Any]:
    """Install an application using Flatpak on the host."""
    app = find_app_entry(app_identifier)
    pkg_id = None
    app_name = app_identifier
    if app:
        pkg_id = app.get("flatpak_id")
        app_name = app.get("name", app_identifier)
        
    if not pkg_id:
        flatpak_ids = {
            "spotify": "com.spotify.Client",
            "vscode": "com.visualstudio.code",
            "discord": "com.discordapp.Discord",
            "vlc": "org.videolan.VLC",
            "gimp": "org.gimp.GIMP",
            "blender": "org.blender.Blender",
            "slack": "com.slack.Slack",
            "obs": "com.obsproject.Studio",
        }
        pkg_id = flatpak_ids.get(app_identifier.lower().strip(), f"com.{app_identifier.lower().strip()}.App")

    cmd = ["flatpak", "install", "--user", "-y", "flathub", pkg_id]
    if shutil.which("flatpak"):
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {
                "status": "success",
                "app": app_name,
                "package_id": pkg_id,
                "method": method,
                "command": " ".join(cmd),
                "pid": proc.pid,
                "message": f"Flatpak installation started for {app_name} ({pkg_id}) [PID: {proc.pid}]"
            }
        except Exception as e:
            return {
                "status": "error",
                "app": app_name,
                "package_id": pkg_id,
                "command": " ".join(cmd),
                "message": f"Failed to run flatpak install: {e}"
            }
    else:
        return {
            "status": "error",
            "app": app_name,
            "package_id": pkg_id,
            "command": " ".join(cmd),
            "message": "Flatpak is not installed on this host."
        }

def execute_app_action(app: str, action: str = "open", params: Any = None, mode: str = "auto") -> str:
    """Convenience string-formatted interface for macros and agents."""
    if isinstance(params, str) and params.strip():
        try:
            params = json.loads(params)
        except Exception:
            params = {}
    elif not isinstance(params, dict):
        params = {}
    res = execute_app_command(app_identifier=app, action=action, params=params, mode=mode)
    if res.get("status") == "success":
        msg = res.get("message") or f"Executed '{action}' on {res.get('app')}"
        url = res.get("url")
        url_str = f" | URL: {url}" if url else ""
        cmd = res.get("command")
        cmd_str = f" | Command: {cmd}" if cmd else ""
        return f"[ok] {msg}{url_str}{cmd_str}"
    return f"[ERROR] {res.get('message', 'Execution failed')}"
