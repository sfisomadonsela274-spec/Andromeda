"""
Puppeteer Bridge for Jimmy and Andromeda
Executes headless browser automation, UI testing, text scraping, and visual capture via Puppeteer.
"""

import json
import subprocess
import os
from pathlib import Path
from typing import Dict, Any, List, Optional

RUNNER_PATH = Path(__file__).parent / "puppeteer_runner.js"

def is_puppeteer_available() -> bool:
    """Check if node and puppeteer runner are available."""
    try:
        res = subprocess.run(["node", "-v"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        return res.returncode == 0 and RUNNER_PATH.exists()
    except Exception:
        return False

def run_puppeteer(payload: Dict[str, Any], timeout: int = 45) -> Dict[str, Any]:
    """
    Run a command payload against the Puppeteer runner script.
    """
    if not RUNNER_PATH.exists():
        return {"status": "error", "message": f"Puppeteer runner script not found at {RUNNER_PATH}"}

    try:
        proc = subprocess.run(
            ["node", str(RUNNER_PATH), "--input", json.dumps(payload)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout
        )

        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()

        if stdout:
            try:
                return json.loads(stdout)
            except json.JSONDecodeError:
                return {"status": "error", "raw_output": stdout, "stderr": stderr}

        if proc.returncode != 0:
            return {"status": "error", "message": stderr or f"Process exited with code {proc.returncode}"}

        return {"status": "success"}
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": f"Puppeteer execution timed out after {timeout} seconds"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def puppeteer_navigate(url: str, screenshot_path: Optional[str] = None, timeout: int = 30) -> Dict[str, Any]:
    """Navigate to a URL and extract text, structure, links, and optional screenshot."""
    payload = {
        "command": "navigate",
        "url": url,
        "screenshot_path": screenshot_path,
        "timeout": timeout * 1000
    }
    return run_puppeteer(payload, timeout=timeout + 15)

def puppeteer_test_flow(url: str, actions: List[Dict[str, Any]], timeout: int = 30) -> Dict[str, Any]:
    """Execute multi-step UI actions and assertions."""
    payload = {
        "command": "test_flow",
        "url": url,
        "actions": actions,
        "timeout": timeout * 1000
    }
    return run_puppeteer(payload, timeout=timeout + 15)

def puppeteer_screenshot(url: str, output_path: Optional[str] = None, selector: Optional[str] = None, full_page: bool = False, timeout: int = 30) -> Dict[str, Any]:
    """Capture a screenshot of a page or element."""
    payload = {
        "command": "screenshot",
        "url": url,
        "output_path": output_path,
        "selector": selector,
        "fullPage": full_page,
        "timeout": timeout * 1000
    }
    return run_puppeteer(payload, timeout=timeout + 15)

def puppeteer_pdf(url: str, output_path: Optional[str] = None, timeout: int = 30) -> Dict[str, Any]:
    """Generate a PDF of the webpage."""
    payload = {
        "command": "pdf",
        "url": url,
        "output_path": output_path,
        "timeout": timeout * 1000
    }
    return run_puppeteer(payload, timeout=timeout + 15)

def puppeteer_eval(url: str, script: str, timeout: int = 30) -> Dict[str, Any]:
    """Evaluate arbitrary JavaScript on a webpage."""
    payload = {
        "command": "eval",
        "url": url,
        "script": script,
        "timeout": timeout * 1000
    }
    return run_puppeteer(payload, timeout=timeout + 15)

def puppeteer_resolve_youtube(query: str, timeout: int = 20) -> Dict[str, Any]:
    """Headlessly search YouTube and extract the top video ID and direct watch URL."""
    payload = {
        "command": "youtube_search",
        "query": query,
        "timeout": timeout * 1000
    }
    return run_puppeteer(payload, timeout=timeout + 15)

def puppeteer_play_media(query: str, browser: str = "firefox", timeout: int = 20) -> Dict[str, Any]:
    """Search YouTube and automatically launch desktop browser to play the top video."""
    payload = {
        "command": "play_media",
        "query": query,
        "browser": browser,
        "timeout": timeout * 1000
    }
    return run_puppeteer(payload, timeout=timeout + 15)

