#!/usr/bin/env python3
"""
Jimmy v7.0 — Split-Brain Agent
Router : smollm2:1.7b  (tool dispatch, always warm)
Brain  : qwen2.5-coder:7b Q4_K_M  (reasoning, evicted after each use)
Target : < 6 GB VRAM total
"""

import ollama
import subprocess
import os
import sys
import json
import re
import shlex
import urllib.request
import tempfile
import logging
import time
from pathlib import Path
from datetime import datetime
import math
import glob
import threading
import sys
import os
from pathlib import Path

try:
    import docker
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False

try:
    import tree_sitter_python as tspython
    import tree_sitter_javascript as tsjs
    from tree_sitter import Language, Parser
    AST_AVAILABLE = True
except ImportError:
    AST_AVAILABLE = False

try:
    import puppeteer_bridge
    PUPPETEER_AVAILABLE = puppeteer_bridge.is_puppeteer_available()
except Exception:
    PUPPETEER_AVAILABLE = False

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

try:
    from media_controller import media_ctrl
    MEDIA_AVAILABLE = True
except Exception:
    MEDIA_AVAILABLE = False

try:
    from macro_runner import runner as macro_runner
    MACROS_AVAILABLE = True
except Exception:
    MACROS_AVAILABLE = False

# Robustly ensure user site-packages is included to prevent ModuleNotFoundError when run globally
local_packages = os.path.expanduser("~/.local/lib/python3.12/site-packages")
if local_packages not in sys.path:
    sys.path.append(local_packages)

try:
    import chromadb
    from chromadb.utils import embedding_functions
except ImportError:
    print("Error: chromadb is not installed. Please run: pip3 install chromadb --break-system-packages")
    sys.exit(1)

try:
    import questionary
except ImportError:
    print("Error: questionary is not installed. Please run: pip3 install questionary --break-system-packages")
    sys.exit(1)

try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    console = Console()
    
    TUI_MODE = "--tui" in sys.argv
    if TUI_MODE:
        sys.argv.remove("--tui")
        
    tui_log = None
    tui_app = None
    import queue
    tui_input_queue = queue.Queue()
    
    _orig_print = console.print
    _orig_input = console.input
    
    def dual_print(*args, **kwargs):
        if tui_log is not None and tui_app is not None:
            tui_app.call_from_thread(tui_log.write, *args, **kwargs)
        if not TUI_MODE:
            _orig_print(*args, **kwargs)
            
    def dual_input(*args, **kwargs):
        if TUI_MODE:
            dual_print(*args, **kwargs)
            return tui_input_queue.get()
        return _orig_input(*args, **kwargs)
        
    console.print = dual_print
    console.input = dual_input
    
    class DummyStatus:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): pass
        def __exit__(self, *args, **kwargs): pass
        def update(self, *args, **kwargs): pass

    if TUI_MODE:
        console.status = lambda *args, **kwargs: DummyStatus()

except ImportError:
    print("Please install the 'rich' library: pip install rich")
    sys.exit(1)

try:
    import phoenix as px
    from phoenix.otel import register
    from opentelemetry import trace
    from openinference.semconv.trace import SpanAttributes, OpenInferenceSpanKindValues
except ImportError:
    print("Please install tracing dependencies: pip install arize-phoenix opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp openinference-semantic-conventions")
    sys.exit(1)

# ─────────────────────────────────────────────
# Config & Tracing Setup
# ─────────────────────────────────────────────
ROUTER_MODEL      = "smollm2:1.7b"
BRAIN_MODEL       = "qwen2.5-coder:7b"
HOME              = Path.home()
MEMORY_PATH       = HOME / "jimmy_brain.json"
CHROMA_PATH       = HOME / "jimmy_vector_brain"
LOG_DIR           = HOME / ".jimmy_logs"

chroma_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
emb_fn = embedding_functions.DefaultEmbeddingFunction()
chroma_collection = chroma_client.get_or_create_collection(name="jimmy_memory", embedding_function=emb_fn)
codebase_collection = chroma_client.get_or_create_collection(name="jimmy_codebase", embedding_function=emb_fn)

import contextlib
import io

try:
    os.environ["PHOENIX_TELEMETRY_ENABLED"] = "false"
    # Check if Phoenix is already running (e.g. in Docker)
    import urllib.request
    already_running = False
    try:
        urllib.request.urlopen("http://localhost:6006/", timeout=1)
        already_running = True
    except Exception:
        pass

    if already_running:
        register(endpoint="http://localhost:4317", set_global_tracer_provider=True)
        tracer = trace.get_tracer("jimmy-agent")
        class DockerPhoenixSession:
            url = "http://localhost:6006"
        px_session = DockerPhoenixSession()
    else:
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            px_session = px.launch_app()
        if px_session is None:
            raise RuntimeError("Phoenix failed to start and returned None")
        register(endpoint="http://localhost:4317", set_global_tracer_provider=True)
        tracer = trace.get_tracer("jimmy-agent")
except Exception as e:
    tracer = trace.get_tracer("jimmy-agent")
    class DummySession:
        url = "Tracing Disabled"
    px_session = DummySession()

MAX_TOOL_LOOPS    = 30         # allow deep multi-step execution
CONTEXT_KEEP      = 12         # messages to keep after trim (must be even)
BASH_TIMEOUT      = 60
OUTPUT_LIMIT      = 3000
BASH_OUTPUT_LIMIT = 1500       # max chars from bash output fed to context
FILE_PAGE_LIMIT   = 500        # max lines per read_file call

LOG_DIR.mkdir(exist_ok=True)
session_log = LOG_DIR / f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)

# ─────────────────────────────────────────────
# Session logger  (JSONL replay-friendly)
# ─────────────────────────────────────────────
def log_event(kind: str, data: dict):
    entry = {"ts": time.time(), "kind": kind, **data}
    with open(session_log, "a") as f:
        f.write(json.dumps(entry) + "\n")

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def safe_home_path(raw_path: str) -> Path | None:
    """Return resolved Path only if it stays inside HOME, else None."""
    try:
        p = Path(raw_path).expanduser().resolve()
        p.relative_to(HOME)          # raises ValueError if outside
        return p
    except ValueError:
        return None

def truncate(text: str, limit: int = OUTPUT_LIMIT) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n\n[⚠ OUTPUT TRUNCATED at {limit} chars]"

def evict(model: str):
    """Ask Ollama to unload a model from VRAM."""
    try:
        ollama.generate(model=model, prompt="", keep_alive=0)
    except Exception:
        pass

# ─────────────────────────────────────────────
# Tools
# ─────────────────────────────────────────────
# Trust levels:  read-only commands skip approval in AUTO_APPROVE mode
READ_ONLY_PREFIXES = ("ls", "cat", "echo", "pwd", "which", "df", "du",
                      "find", "grep", "head", "tail", "wc", "stat", "file")

AUTO_APPROVE: bool = False      # set True for fully autonomous workflows
DAEMONS: dict = {}
DAEMON_ALERTS: list = []


def _approve_bash(command: str) -> bool:
    global AUTO_APPROVE
    if AUTO_APPROVE:
        return True
        
    # Check for shell operators that could bypass simple prefix checks
    unsafe_chars = ["|", ";", "&&", "||", ">", "<", "$", "`"]
    is_unsafe = any(op in command for op in unsafe_chars)
    
    cmd_stripped = command.strip().lstrip("(").split()[0] if command.strip() else ""
    if not is_unsafe and cmd_stripped in READ_ONLY_PREFIXES:
        return True          # read-only always allowed if no operators
    console.print(f"\n[bold yellow][⚠  JIMMY WANTS TO RUN]:[/bold yellow] {command}")
    reply = console.input("[bold cyan]ENTER[/bold cyan] to approve, [bold red]'n'[/bold red] to cancel, [bold magenta]'auto'[/bold magenta] to trust all: ").strip().lower()
    if reply == "auto":
        AUTO_APPROVE = True
        return True
    return reply != "n"


def execute_bash(command: str, sandbox: bool = False) -> str:
    log_event("tool_call", {"tool": "execute_bash", "command": command, "sandbox": sandbox})
    if not _approve_bash(command):
        return "Command cancelled by user."
        
    if sandbox:
        if not DOCKER_AVAILABLE:
            return "[ERROR] Docker SDK is not installed. Cannot use sandbox."
        try:
            client = docker.from_env()
            console.print(f"\n[bold blue][🐳 DOCKER SANDBOX]:[/bold blue] {command}")
            cwd = os.getcwd()
            container = client.containers.run(
                "python:3.12-slim",
                f"bash -c {shlex.quote(command)}",
                volumes={cwd: {'bind': '/workspace', 'mode': 'rw'}},
                working_dir='/workspace',
                detach=False,
                remove=True
            )
            output = container.decode('utf-8')
            return f"[ok]\n{truncate(output, BASH_OUTPUT_LIMIT)}"
        except docker.errors.ContainerError as e:
            return f"[exit_code={e.exit_status}]\n{truncate(e.stderr.decode('utf-8'), BASH_OUTPUT_LIMIT)}"
        except Exception as e:
            return f"[ERROR] Docker failed: {e}"

    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=BASH_TIMEOUT
        )
        output = (result.stdout or result.stderr or "").strip()
        status = "ok" if result.returncode == 0 else f"exit_code={result.returncode}"
        if not output:
            payload = "[Command completed with no output.]"
        elif len(output) > BASH_OUTPUT_LIMIT:
            # Keep the tail — that's where success/error messages live
            payload = f"[...output truncated, showing last {BASH_OUTPUT_LIMIT} chars...]\n" + output[-BASH_OUTPUT_LIMIT:]
        else:
            payload = output
            
        error_keywords = ["error", "exception", "panicked", "failed"]
        if result.returncode != 0 and any(kw in payload.lower() for kw in error_keywords):
            # Trigger Momentum Engine
            payload = f"[MOMENTUM_TRIGGER] {payload}"
            
        log_event("tool_result", {"tool": "execute_bash", "status": status})
        return f"[{status}]\n{payload}"
    except subprocess.TimeoutExpired:
        return f"[TIMEOUT] Command exceeded {BASH_TIMEOUT}s."
    except Exception as e:
        return f"[ERROR] {e}"


def read_file(file_path: str, start_line: int | None = None, end_line: int | None = None) -> str:
    """Explicit read — model calls this instead of `cat` for clarity."""
    log_event("tool_call", {"tool": "read_file", "path": file_path})
    p = safe_home_path(file_path)
    if p is None:
        return "[SECURITY] Path is outside home directory."
    if not p.exists():
        return f"[ERROR] File not found: {file_path}"
    try:
        content = p.read_text(errors="replace")
        lines = content.split("\n")
        total = len(lines)

        # Pagination guard — force Jimmy to read in chunks
        if start_line is None and end_line is None:
            if total > FILE_PAGE_LIMIT:
                return (
                    f"[PAGINATION REQUIRED] File '{file_path}' has {total} lines — too large to read at once.\n"
                    f"Please call read_file again with start_line and end_line (max {FILE_PAGE_LIMIT} lines per call).\n"
                    f"Example: read_file('{file_path}', start_line=1, end_line={FILE_PAGE_LIMIT})"
                )

        s_idx = max(0, (start_line - 1) if start_line is not None else 0)
        e_idx = min(total, (end_line if end_line is not None else total))

        # Enforce page size even when explicit line numbers are given
        if (e_idx - s_idx) > FILE_PAGE_LIMIT:
            e_idx = s_idx + FILE_PAGE_LIMIT
            console.print(f"[dim yellow][read_file] Page clamped to lines {s_idx+1}-{e_idx} ({FILE_PAGE_LIMIT}-line limit)[/dim yellow]")

        if s_idx >= e_idx or s_idx >= total:
            return f"[ERROR] Invalid line range ({start_line}-{end_line}). File has {total} lines."

        lines_to_show = lines[s_idx:e_idx]
        numbered_lines = [f"{s_idx+i+1:4} | {line}" for i, line in enumerate(lines_to_show)]
        suffix = f"\n[Showing lines {s_idx+1}-{e_idx} of {total}. Use start_line/end_line to read more.]"
        return "\n".join(numbered_lines) + (suffix if total > FILE_PAGE_LIMIT else "")
    except Exception as e:
        return f"[ERROR] {e}"


def write_to_file(file_path: str, content: str) -> str:
    log_event("tool_call", {"tool": "write_to_file", "path": file_path})
    p = safe_home_path(file_path)
    if p is None:
        return "[SECURITY] Path is outside home directory."
    console.print(f"\n[bold yellow][✏  WRITE]:[/bold yellow] {file_path}  ([cyan]{len(content)}[/cyan] chars)")
    if not AUTO_APPROVE:
        if console.input("[bold cyan]ENTER[/bold cyan] to approve, [bold red]'n'[/bold red] to cancel: ").strip().lower() == "n":
            return "Write cancelled by user."
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"[ok] Wrote {len(content)} chars to {file_path}"
    except Exception as e:
        return f"[ERROR] {e}"


def patch_file(file_path: str, start_line: int, end_line: int, replacement_code: str) -> str:
    log_event("tool_call", {"tool": "patch_file", "path": file_path})
    p = safe_home_path(file_path)
    if p is None:
        return "[SECURITY] Path is outside home directory."
    if not p.exists():
        return f"[ERROR] File not found: {file_path}"
    console.print(f"\n[bold yellow][🔧 PATCH]:[/bold yellow] {file_path}  (lines [cyan]{start_line}-{end_line}[/cyan])")
    if not AUTO_APPROVE:
        if console.input("[bold cyan]ENTER[/bold cyan] to approve, [bold red]'n'[/bold red] to cancel: ").strip().lower() == "n":
            return "Patch cancelled by user."
            
    try:
        lines = p.read_text(errors="replace").split("\n")
        
        start_line = max(1, start_line)
        if len(lines) > 0 and end_line > len(lines):
            end_line = len(lines)
            
        if start_line > end_line or start_line > len(lines):
            return f"[ERROR] Invalid start_line ({start_line}). File only has {len(lines)} lines."
            
        start_idx = start_line - 1
        end_idx = end_line
        
        new_content = "\n".join(lines[:start_idx]) + ("\n" if start_idx > 0 else "") + \
                      replacement_code + \
                      ("\n" if end_idx < len(lines) else "") + "\n".join(lines[end_idx:])
                      
        p.write_text(new_content)
        
        # Generate diff preview
        new_lines = new_content.split("\n")
        inserted_count = len(replacement_code.split("\n"))
        
        preview_start = max(0, start_line - 4)
        preview_end = min(len(new_lines), start_line - 1 + inserted_count + 3)
        
        snippet = []
        for i in range(preview_start, preview_end):
            marker = ">> " if (start_line - 1 <= i < start_line - 1 + inserted_count) else "   "
            snippet.append(f"{i+1:4} {marker}| {new_lines[i]}")
            
        preview = "\n".join(snippet)
        return f"[ok] Patched {file_path} (lines {start_line}-{end_line})\nPreview:\n{preview}"
    except Exception as e:
        return f"[ERROR] {e}"


def fetch_webpage(url: str) -> str:
    log_event("tool_call", {"tool": "fetch_webpage", "url": url})
    console.print(f"\n[bold green][🌐 FETCH]:[/bold green] {url}")
    # Prioritize Puppeteer for full client-side JS rendering and local intranet endpoints
    if PUPPETEER_AVAILABLE:
        try:
            res = puppeteer_bridge.puppeteer_navigate(url, timeout=20)
            if res.get("status") == "success":
                data = res.get("pageData", {})
                title = res.get("title", "")
                text = data.get("text", "")
                buttons = ", ".join(data.get("buttons", [])[:10])
                headings = ", ".join(data.get("headings", [])[:10])
                output = f"Title: {title}\nHeadings: {headings}\nButtons: {buttons}\n\nRendered Content:\n{text}"
                return truncate(output, limit=OUTPUT_LIMIT * 2)
        except Exception as e:
            console.print(f"[dim yellow]Puppeteer fallback to HTTP fetch: {e}[/dim yellow]")
    try:
        # Fallback to Jina Reader API for static/public markdown
        req = urllib.request.Request(f"https://r.jina.ai/{url}", headers={"User-Agent": "Mozilla/5.0 (Jimmy AI Agent)"})
        text = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", errors="replace")
        return truncate(text, limit=OUTPUT_LIMIT * 2)
    except Exception as e:
        return f"[ERROR] {e}"


def look_at_screen(query: str = "Describe what is on the screen.", mode: str = "general") -> str:
    log_event("tool_call", {"tool": "look_at_screen", "mode": mode})
    console.print(f"\n[bold magenta][👀 SCREEN CAPTURE ({mode})][/bold magenta]")
    subprocess.run("scrot /tmp/jimmy_eyes.png", shell=True, capture_output=True)
    try:
        img_bytes = Path("/tmp/jimmy_eyes.png").read_bytes()
        prompt = f"Critique this UI design. Point out alignment errors, bad contrast, or spacing issues. Provide actionable CSS/Tailwind feedback to make it look premium. Specific query: {query}" if mode == "ui_critique" else query
        response = ollama.chat(
            model="moondream",
            messages=[{"role": "user", "content": prompt, "images": [img_bytes]}]
        )
        return f"Screen: {response['message']['content']}"
    except Exception as e:
        return f"[ERROR] {e}"


def scaffold_project(file_tree_json: str) -> str:
    log_event("tool_call", {"tool": "scaffold_project"})
    console.print("\n[bold blue][🏗  SCAFFOLD][/bold blue]")
    try:
        file_tree = json.loads(file_tree_json) if isinstance(file_tree_json, str) else file_tree_json
        created = []
        for raw_path, content in file_tree.items():
            p = safe_home_path(raw_path)
            if p is None:
                return f"[SECURITY] Path '{raw_path}' escapes home — scaffold aborted."
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            created.append(str(p))
        return f"[ok] Scaffolded {len(created)} files:\n" + "\n".join(created)
    except Exception as e:
        return f"[ERROR] {e}"


def edit_code_block(file_path: str, target_name: str, new_code: str) -> str:
    log_event("tool_call", {"tool": "edit_code_block", "file": file_path, "target": target_name})
    console.print(f"\n[bold yellow][📝 AST EDIT]:[/bold yellow] {file_path} -> {target_name}")
    if not AST_AVAILABLE:
        return "[ERROR] AST modules not installed. Cannot use edit_code_block."
        
    p = safe_home_path(file_path)
    if not p or not p.exists():
        return f"[ERROR] File not found: {file_path}"
        
    code = p.read_bytes()
    ext = p.suffix.lower()
    
    if ext == ".py":
        lang = Language(tspython.language())
        valid_nodes = ('function_definition', 'class_definition', 'async_function_definition')
    elif ext in (".js", ".ts", ".jsx", ".tsx"):
        lang = Language(tsjs.language())
        valid_nodes = ('function_declaration', 'class_declaration', 'method_definition', 'arrow_function')
    else:
        return f"[ERROR] AST edit not supported for extension {ext}"
        
    parser = Parser(lang)
    tree = parser.parse(code)
    
    def find_node(node, name):
        if node.type in valid_nodes:
            for child in node.children:
                if child.type == 'identifier' and code[child.start_byte:child.end_byte].decode('utf-8', 'ignore') == name:
                    return node
        for child in node.children:
            res = find_node(child, name)
            if res: return res
        return None

    target_node = find_node(tree.root_node, target_name)
    if not target_node:
        return f"[ERROR] Could not find '{target_name}' in {file_path}."
        
    start = target_node.start_byte
    end = target_node.end_byte
    
    new_content = code[:start] + new_code.encode('utf-8') + code[end:]
    p.write_bytes(new_content)
    
    if ext == ".py":
        try:
            res = subprocess.run(["pyright", str(p)], capture_output=True, text=True)
            if res.returncode != 0:
                return f"[ok] Replaced '{target_name}', BUT pyright found errors:\n{truncate(res.stdout, 500)}"
        except FileNotFoundError:
            pass
            
    return f"[ok] Successfully replaced '{target_name}' in {file_path}"


def test_ui_flow(url: str, actions_json: str) -> str:
    log_event("tool_call", {"tool": "test_ui_flow", "url": url})
    console.print(f"\n[bold magenta][🎭 UI TEST]:[/bold magenta] Testing {url}")
    
    action_list = json.loads(actions_json) if isinstance(actions_json, str) else actions_json

    if PUPPETEER_AVAILABLE:
        res = puppeteer_bridge.puppeteer_test_flow(url, action_list)
        if res.get("status") == "success":
            logs = [f"Step {a['step']}: {a['action']} {a.get('selector', '')} -> {a.get('status', 'ok')}" for a in res.get("actions", [])]
            return "[TEST PASSED]\n" + "\n".join(logs)
        else:
            err = res.get("error") or res.get("message", "Unknown failure")
            failed_step = res.get("failedStep", "?")
            return f"[TEST FAILED at step {failed_step}]: {err}"

    if not PLAYWRIGHT_AVAILABLE:
        return "[ERROR] Neither Puppeteer nor Playwright available. Cannot run UI tests."
        
    try:
        results = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=10000)
            
            for act in action_list:
                a_type = act.get("action")
                sel = act.get("selector")
                val = act.get("value")
                
                try:
                    if a_type == "click":
                        page.locator(sel).click(timeout=3000)
                        results.append(f"Clicked {sel}")
                    elif a_type == "fill":
                        page.locator(sel).fill(val, timeout=3000)
                        results.append(f"Filled {sel} with '{val}'")
                    elif a_type == "assert_text":
                        text = page.locator(sel).inner_text(timeout=3000)
                        if val not in text:
                            browser.close()
                            return f"[TEST FAILED] Expected '{val}' in {sel}, but found '{text}'"
                        results.append(f"Asserted '{val}' in {sel}")
                    else:
                        results.append(f"Unknown action {a_type}")
                except Exception as step_e:
                    browser.close()
                    return f"[TEST FAILED at '{a_type}' on '{sel}']: {step_e}"
                    
            browser.close()
        return "[TEST PASSED]\n" + "\n".join(results)
    except Exception as e:
        return f"[TEST FAILED] {e}"


def puppeteer_browser(action: str, url: str, payload: str = "") -> str:
    log_event("tool_call", {"tool": "puppeteer_browser", "action": action, "url": url})
    console.print(f"\n[bold cyan][🌐 PUPPETEER ({action})]:[/bold cyan] {url}")
    if not PUPPETEER_AVAILABLE:
        return "[ERROR] Puppeteer is not available on this system."

    try:
        if action == "navigate":
            res = puppeteer_bridge.puppeteer_navigate(url)
            if res.get("status") == "success":
                data = res.get("pageData", {})
                title = res.get("title", "")
                text = data.get("text", "")
                buttons = ", ".join(data.get("buttons", [])[:12])
                headings = ", ".join(data.get("headings", [])[:8])
                links = [f"[{l['text']}]({l['href']})" for l in data.get("links", [])[:10] if l.get("text")]
                links_str = "\n".join(links)
                return f"Page Title: {title}\nStatus: {res.get('httpStatus')}\nHeadings: {headings}\nButtons: {buttons}\n\nLinks:\n{links_str}\n\nContent:\n{truncate(text, 2500)}"
            return f"[ERROR] {res.get('message', 'Navigation failed')}"

        elif action == "screenshot":
            out_file = payload.strip() if payload.strip() else f"/tmp/puppeteer_{int(time.time())}.png"
            res = puppeteer_bridge.puppeteer_screenshot(url, output_path=out_file, full_page=True)
            if res.get("status") == "success":
                return f"[ok] Screenshot captured successfully to: {res.get('screenshot')}"
            return f"[ERROR] {res.get('message', 'Screenshot failed')}"

        elif action == "critique":
            out_file = f"/tmp/puppeteer_critique_{int(time.time())}.png"
            res = puppeteer_bridge.puppeteer_screenshot(url, output_path=out_file, full_page=False)
            if res.get("status") != "success":
                return f"[ERROR] Could not capture screenshot: {res.get('message')}"
            
            img_bytes = Path(out_file).read_bytes()
            query = payload.strip() if payload.strip() else "Critique this web UI. Point out alignment, typography, visual hierarchy, and color issues with actionable advice."
            response = ollama.chat(
                model="moondream",
                messages=[{"role": "user", "content": query, "images": [img_bytes]}]
            )
            return f"[UI Critique for {url}]:\n{response['message']['content']}\nScreenshot saved to: {out_file}"

        elif action == "pdf":
            out_file = payload.strip() if payload.strip() else f"/tmp/puppeteer_{int(time.time())}.pdf"
            res = puppeteer_bridge.puppeteer_pdf(url, output_path=out_file)
            if res.get("status") == "success":
                return f"[ok] PDF rendered successfully to: {res.get('pdf')}"
            return f"[ERROR] {res.get('message', 'PDF generation failed')}"

        elif action == "eval":
            res = puppeteer_bridge.puppeteer_eval(url, script=payload)
            if res.get("status") == "success":
                return f"[ok] Result: {json.dumps(res.get('evalResult'), indent=2)}"
            return f"[ERROR] {res.get('message', 'Evaluation failed')}"

        elif action == "test_flow":
            actions = json.loads(payload) if isinstance(payload, str) else payload
            res = puppeteer_bridge.puppeteer_test_flow(url, actions)
            if res.get("status") == "success":
                logs = [f"Step {a['step']}: {a['action']} {a.get('selector', '')} -> {a.get('status', 'ok')}" for a in res.get("actions", [])]
                return "[TEST PASSED]\n" + "\n".join(logs)
            return f"[TEST FAILED]: {res.get('error') or res.get('message')}"

        else:
            return f"[ERROR] Unknown puppeteer action '{action}'. Valid actions: navigate, screenshot, critique, pdf, eval, test_flow."
    except Exception as e:
        return f"[ERROR] {e}"


def play_media(query: str, platform: str = "youtube", browser: str = "firefox") -> str:
    log_event("tool_call", {"tool": "play_media", "query": query, "platform": platform, "browser": browser})
    console.print(f"\n[bold red][▶ PLAY MEDIA ({platform})]:[/bold red] {query} on {browser}")
    try:
        import app_controller
        yt_info = app_controller.resolve_youtube_top_video(query)
        if yt_info.get("videoId"):
            play_url = yt_info["url"]
            title = yt_info.get("title", query)
            subprocess.Popen([browser, play_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"[ok] Resolved exact video '{title}' (ID: {yt_info['videoId']}) and launched playback on {browser}: {play_url}"
    except Exception as e:
        logging.warning(f"Fast resolver failed: {e}")

    if PUPPETEER_AVAILABLE:
        try:
            res = puppeteer_bridge.puppeteer_play_media(query, browser=browser)
            if res.get("status") == "success":
                title = res.get("title", query)
                play_url = res.get("playUrl", "")
                return f"[ok] Successfully resolved '{title}' and launched playback on {browser}: {play_url}"
        except Exception:
            pass

    target_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
    subprocess.Popen([browser, target_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return f"[FALLBACK] Launched YouTube search for '{query}' on {browser}: {target_url}"


def install_app(app: str, method: str = "flatpak") -> str:
    log_event("tool_call", {"tool": "install_app", "app": app, "method": method})
    console.print(f"\n[bold green][📦 INSTALL APP]:[/bold green] {app} via {method}")
    try:
        import app_controller
        res = app_controller.install_app(app_identifier=app, method=method)
        if res.get("status") == "success":
            return f"[ok] {res.get('message')}\nCommand: {res.get('command')}"
        return f"[ERROR] {res.get('message', 'Installation failed')}"
    except Exception as e:
        return f"[ERROR] {e}"


def app_control(app: str, action: str = "open", params_json: str = "{}", mode: str = "auto") -> str:
    log_event("tool_call", {"tool": "app_control", "app": app, "action": action, "mode": mode})
    console.print(f"\n[bold green][🚀 APP CONTROL]:[/bold green] {app} → {action} (mode: {mode})")
    try:
        import app_controller
        params = json.loads(params_json) if isinstance(params_json, str) and params_json.strip() else (params_json if isinstance(params_json, dict) else {})
        res = app_controller.execute_app_command(app_identifier=app, action=action, params=params, mode=mode)
        if res.get("status") == "success":
            msg = res.get("message") or f"Executed '{action}' on {res.get('app')}"
            url = res.get("url")
            url_str = f"\nURL: {url}" if url else ""
            cmd = res.get("command")
            cmd_str = f"\nCommand: {cmd}" if cmd else ""
            return f"[ok] {msg}{url_str}{cmd_str}"
        return f"[ERROR] {res.get('message', 'Execution failed')}"
    except Exception as e:
        return f"[ERROR] {e}"


def media_control(action: str, value: float = None, player: str = None) -> str:
    log_event("tool_call", {"tool": "media_control", "action": action, "value": value})
    console.print(f"\n[bold magenta][🎵 MEDIA]:[/bold magenta] {action} (value={value}, player={player})")
    if not MEDIA_AVAILABLE:
        return "[ERROR] media_controller module is not available"
    res = media_ctrl.execute(action=action, value=value, player=player)
    console.print(f"[bold magenta][🎵 MEDIA RESULT]:[/bold magenta] {res}")
    return res


def run_macro(macro_name: str, overrides_json: str = "{}") -> str:
    log_event("tool_call", {"tool": "run_macro", "macro": macro_name})
    console.print(f"\n[bold blue][⚡ MACRO]:[/bold blue] Launching macro '{macro_name}'...")
    if not MACROS_AVAILABLE:
        return "[ERROR] macro_runner module is not available"
    try:
        overrides = json.loads(overrides_json) if isinstance(overrides_json, str) and overrides_json.strip() else (overrides_json if isinstance(overrides_json, dict) else {})
    except Exception:
        overrides = {}
    res = macro_runner.run(macro_name, overrides)
    return res


def ide_interact(action: str, payload: str = "") -> str:
    log_event("tool_call", {"tool": "ide_interact", "action": action})
    console.print(f"\n[bold cyan][💻 IDE]:[/bold cyan] {action} → {payload[:60]}")
    brain: dict = json.loads(MEMORY_PATH.read_text()) if MEMORY_PATH.exists() else {}
    ide_cmd = brain.get("IDE_CMD")
    
    try:
        import shutil
        
        # Auto-detect IDE if not set or missing
        if not ide_cmd or not (shutil.which(ide_cmd.split()[0]) if ide_cmd else False):
            common_ides = [
                "code", "zed", "cursor", "subl", "pycharm", "idea", "webstorm", 
                "atom", "nvim", "vim", "emacs", "nano", "gedit", "kate", "geany"
            ]
            
            flatpak_map = {
                "zed": "dev.zed.Zed",
                "code": "com.visualstudio.code",
                "subl": "com.sublimetext.three",
                "pycharm": "com.jetbrains.PyCharm-Community",
                "idea": "com.jetbrains.IntelliJ-IDEA-Community"
            }
            
            installed_flatpaks = ""
            if shutil.which("flatpak"):
                try:
                    installed_flatpaks = subprocess.check_output(["flatpak", "list", "--app", "--columns=application"], text=True)
                except Exception:
                    pass

            for ide in common_ides:
                if shutil.which(ide):
                    ide_cmd = ide
                    break
                if ide in flatpak_map and flatpak_map[ide] in installed_flatpaks:
                    ide_cmd = f"flatpak run {flatpak_map[ide]}"
                    break
            
            if not ide_cmd:
                return "[ERROR] No common IDE found in PATH or Flatpak. Please install one."

        # Handle commands with spaces (like "flatpak run ...")
        base_cmd = ide_cmd.split()

        if action == "open":
            cmd_args = base_cmd + [payload] if payload else base_cmd
            subprocess.Popen(cmd_args)
            return f"[ok] Opened {payload or 'IDE'} using {ide_cmd}"
        elif action == "goto":
            # Basic goto support for known IDEs
            if "code" in ide_cmd or "cursor" in ide_cmd:
                cmd_args = base_cmd + ["--goto", payload]
            else:
                cmd_args = base_cmd + [payload]
                
            subprocess.Popen(cmd_args)
            return f"[ok] Navigated to {payload} using {ide_cmd}"
        return "[ERROR] Unknown action. Use open/goto."
    except Exception as e:
        return f"[ERROR] {e}"


# ─────────────────────────────────────────────
# Advanced Features
# ─────────────────────────────────────────────
def chunk_text(text: str, size: int = 1000, overlap: int = 200) -> list[str]:
    chunks = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return chunks

def ast_chunk_text(file_path: str, content: str) -> list[str]:
    ext = Path(file_path).suffix.lower()
    if not AST_AVAILABLE or ext not in (".py", ".js", ".ts", ".jsx", ".tsx"):
        return chunk_text(content)
        
    try:
        code = content.encode('utf-8', 'ignore')
        if ext == ".py":
            lang = Language(tspython.language())
            valid_nodes = ('function_definition', 'class_definition', 'async_function_definition')
        else:
            lang = Language(tsjs.language())
            valid_nodes = ('function_declaration', 'class_declaration', 'method_definition', 'arrow_function')
            
        parser = Parser(lang)
        tree = parser.parse(code)
        
        chunks = []
        def traverse(node):
            if node.type in valid_nodes:
                chunk = code[node.start_byte:node.end_byte].decode('utf-8', 'ignore')
                chunks.append(f"File: {file_path}\n{chunk}")
                return # Do not traverse inner functions to avoid duplicates
            for child in node.children:
                traverse(child)
                
        traverse(tree.root_node)
        return chunks if chunks else chunk_text(content)
    except Exception:
        return chunk_text(content)

def search_codebase(query: str) -> str:
    log_event("tool_call", {"tool": "search_codebase", "query": query})
    console.print(f"\n[bold blue][🔍 RAG SEARCH]:[/bold blue] {query}")
    try:
        files = []
        for ext in ("*.py", "*.js", "*.ts", "*.md", "*.json", "*.html", "*.css"):
            files.extend(glob.glob(f"**/{ext}", recursive=True))
        files = [f for f in files if not any(d in f for d in ["node_modules", ".git", "venv", "__pycache__", "jimmy_env"])]
        
        with console.status("[dim]Indexing codebase for search (this may take a moment)...[/dim]", spinner="dots"):
            for f in files[:200]: # Limit to 200 files for safety
                try:
                    content = Path(f).read_text(errors="ignore")
                    if not content.strip():
                        continue
                        
                    chunks = ast_chunk_text(f, content)
                    docs = []
                    ids = []
                    for i, chunk in enumerate(chunks):
                        if not chunk.strip(): continue
                        docs.append(chunk)
                        ids.append(f"{f}_{i}")
                    if docs:
                        codebase_collection.upsert(documents=docs, ids=ids)
                except Exception:
                    pass
        
        results = codebase_collection.query(query_texts=[query], n_results=5)
        
        out = []
        if results and results['documents'] and results['documents'][0]:
            for doc, id_ in zip(results['documents'][0], results['ids'][0]):
                preview = doc[:300] + "..." if len(doc) > 300 else doc
                out.append(f"--- Document ID: {id_} ---\n{preview}\n")
            
        return "\n".join(out) if out else "[No results found]"
    except Exception as e:
        return f"[ERROR] {e}"

def generate_repo_map(target_dir: str = ".") -> str:
    log_event("tool_call", {"tool": "generate_repo_map", "dir": target_dir})
    console.print(f"\n[bold green][🗺️ REPO MAP]:[/bold green] {target_dir}")
    if not AST_AVAILABLE:
        return "[ERROR] AST modules not installed. Cannot generate repo map."
        
    files = []
    for ext in ("*.py", "*.js", "*.ts", "*.jsx", "*.tsx"):
        files.extend(glob.glob(f"{target_dir}/**/{ext}", recursive=True))
    files = [f for f in files if not any(d in f for d in ["node_modules", ".git", "venv", "__pycache__", "jimmy_env"])]
    
    map_lines = []
    for f_path in files[:100]: # limit to 100 files to prevent token explosion
        try:
            content = Path(f_path).read_bytes()
            ext = Path(f_path).suffix.lower()
            if ext == ".py":
                lang = Language(tspython.language())
                valid_nodes = ('class_definition', 'function_definition', 'async_function_definition')
            else:
                lang = Language(tsjs.language())
                valid_nodes = ('class_declaration', 'function_declaration', 'method_definition', 'arrow_function')
            
            parser = Parser(lang)
            tree = parser.parse(content)
            
            sigs = []
            def traverse(node, indent="  "):
                if node.type in valid_nodes:
                    sig_line = content[node.start_byte:node.end_byte].split(b'\n')[0].decode('utf-8', 'ignore').strip()
                    sigs.append(indent + sig_line)
                    indent += "  "
                for child in node.children:
                    traverse(child, indent)
                    
            traverse(tree.root_node)
            
            if sigs:
                map_lines.append(f_path + ":")
                map_lines.extend(sigs)
            else:
                map_lines.append(f_path)
        except Exception:
            pass
            
    res = "\n".join(map_lines)
    return truncate(res, limit=OUTPUT_LIMIT * 4) if res else "[No AST maps generated]"

def delegate_task(task_description: str) -> str:
    log_event("tool_call", {"tool": "delegate_task", "task": task_description})
    console.print(f"\n[bold magenta][🤖 DELEGATE]:[/bold magenta] {task_description[:60]}...")
    
    scratch_dir = tempfile.mkdtemp(prefix="jimmy_scratch_")
    scratch_result = os.path.join(scratch_dir, "result.json")
    
    sub_system = (
        f"You are a Sub-Agent of Jimmy. Task: {task_description}\n"
        f"Do NOT ask for user approval. Execute tools.\n"
        f"A shared scratchpad directory has been created at: {scratch_dir}\n"
        f"If you need to return structured data to the main agent, write it as a JSON file to: {scratch_result}\n"
        f"Return a FINAL summary when finished."
    )
    sub_msgs = []
    cwd = os.getcwd()
    
    try:
        loops = 0
        seen_sigs = set()
        while loops < 8:
            with console.status(f"[bold magenta]Sub-Agent working...[/bold magenta] [dim](Loop {loops+1}/8)[/dim]", spinner="dots"):
                try:
                    msg = agent_step(sub_system, sub_msgs, cwd, with_tools=True)
                except Exception as e:
                    return f"[ERROR] Sub-agent inference failed: {e}"
                
            raw_calls = msg.get("tool_calls") or []
            if not raw_calls and msg.get("content"):
                rescued = rescue_tool_calls(msg["content"])
                if rescued:
                    raw_calls = [{"function": {"name": t["name"], "arguments": t["arguments"]}} for t in rescued]
                    
            if raw_calls:
                sub_msgs.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": raw_calls})
                for tc in raw_calls:
                    name, args = tc["function"]["name"], tc["function"].get("arguments", {})
                    sig = (name, json.dumps(args, sort_keys=True))
                    
                    if name == "delegate_task":
                        res = "[ERROR] Sub-agents cannot delegate."
                    elif sig in seen_sigs:
                        res = "[ERROR] Loop intercepted. You repeated the exact same tool call."
                    elif name in AVAILABLE_TOOLS:
                        seen_sigs.add(sig)
                        console.print(f"[dim magenta]\\[Sub-Agent → {name}][/dim magenta]")
                        res = AVAILABLE_TOOLS[name](**args)
                    else:
                        res = f"[ERROR] Unknown tool: {name}"
                    sub_msgs.append({"role": "tool", "content": res, "name": name})
                loops += 1
            else:
                summary = (msg.get('content') or '').strip()
                structured_data = ""
                if os.path.exists(scratch_result):
                    try:
                        data = Path(scratch_result).read_text(errors="ignore")
                        structured_data = f"\n\n[Structured Result from {scratch_result}]:\n{data}"
                    except Exception:
                        pass
                return f"[Sub-Agent Completed] {summary}{structured_data}"
        return "[ERROR] Sub-agent hit loop limit (8)."
    except Exception as e:
        return f"[ERROR] {e}"

def _monitor_daemon(cmd_id: str, proc: subprocess.Popen, command: str):
    proc.wait()
    if proc.returncode != 0:
        stderr = proc.stderr.read().decode('utf-8', errors='ignore') if proc.stderr else ""
        DAEMON_ALERTS.append(f"[BACKGROUND CRASH] '{command}' exited with code {proc.returncode}.\nOutput: {stderr[-1000:]}")
        console.print(f"\n[bold red]\\[⚠ DAEMON CRASH][/bold red] {command} exited with code {proc.returncode}!")

def run_daemon(command: str) -> str:
    log_event("tool_call", {"tool": "run_daemon", "command": command})
    console.print(f"\n[bold blue][🚀 DAEMON]:[/bold blue] {command}")
    if not _approve_bash(command):
        return "Daemon cancelled by user."
    try:
        proc = subprocess.Popen(command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        cmd_id = f"daemon_{time.time()}"
        DAEMONS[cmd_id] = proc
        t = threading.Thread(target=_monitor_daemon, args=(cmd_id, proc, command), daemon=True)
        t.start()
        return f"[ok] Daemon started (PID {proc.pid}). It is being monitored in the background."
    except Exception as e:
        return f"[ERROR] {e}"

def consult_designer(query: str) -> str:
    log_event("tool_call", {"tool": "consult_designer", "query": query})
    console.print(f"\n[bold magenta][🎨 DESIGN LOBE]:[/bold magenta] {query[:60]}...")
    design_system = """You are a master UI/UX Frontend Architect (Apple-tier).
Your job is to provide highly specific, actionable design blueprints.
Always prioritize: Glassmorphism, Tailwind CSS, slate/zinc scales, rounded-2xl, flexbox/grid alignments, smooth micro-animations (transition-all duration-300), and generous padding/whitespace.
Return exact Tailwind classes, hex codes, and structural advice. Do not write backend logic."""
    try:
        with console.status("[bold magenta]Consulting Design Lobe...[/bold magenta]", spinner="dots"):
            resp = _call(BRAIN_MODEL, [{"role": "system", "content": design_system}, {"role": "user", "content": query}], max_tokens=1024, ctx=2048)
        return f"[Design Blueprint]\n{(resp['message'].get('content') or '').strip()}"
    except Exception as e:
        return f"[ERROR] {e}"

UI_KIT_DIR = HOME / ".jimmy_ui_kit"
def _init_ui_kit():
    if not UI_KIT_DIR.exists():
        UI_KIT_DIR.mkdir()
        glass_card = """<div class="relative overflow-hidden rounded-2xl border border-white/20 bg-white/10 px-6 py-8 shadow-2xl backdrop-blur-md transition-all duration-300 hover:bg-white/20 hover:-translate-y-1">\n  <h3 class="mb-2 text-xl font-semibold text-slate-100">Premium Glass Card</h3>\n  <p class="text-slate-300 text-sm">Perfect for modern dashboards.</p>\n</div>"""
        hero_section = """<section class="relative flex min-h-[70vh] flex-col items-center justify-center overflow-hidden bg-slate-900 px-6 py-24 text-center">\n  <div class="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 mix-blend-overlay"></div>\n  <div class="absolute -top-40 -left-40 h-96 w-96 rounded-full bg-indigo-500 blur-[128px] opacity-50"></div>\n  <div class="absolute -bottom-40 -right-40 h-96 w-96 rounded-full bg-rose-500 blur-[128px] opacity-50"></div>\n  <div class="z-10 max-w-3xl">\n    <h1 class="mb-6 text-5xl font-extrabold tracking-tight text-white sm:text-7xl">Build the Future.</h1>\n    <p class="mb-8 text-lg text-slate-300 sm:text-xl">A stunning, modern hero section with ambient glows and noise overlays.</p>\n    <button class="rounded-full bg-white px-8 py-3.5 text-sm font-semibold text-slate-900 shadow-sm transition-all duration-300 hover:scale-105 hover:bg-slate-200">Get Started</button>\n  </div>\n</section>"""
        modern_navbar = """<nav class="fixed top-0 left-0 right-0 z-50 flex items-center justify-between border-b border-white/10 bg-slate-900/50 px-8 py-4 backdrop-blur-lg">\n  <div class="text-xl font-bold text-white tracking-wide">Brand.</div>\n  <ul class="flex space-x-8 text-sm font-medium text-slate-300">\n    <li class="hover:text-white transition-colors cursor-pointer">Home</li>\n    <li class="hover:text-white transition-colors cursor-pointer">Features</li>\n    <li class="hover:text-white transition-colors cursor-pointer">Pricing</li>\n  </ul>\n  <button class="rounded-lg bg-indigo-500 px-4 py-2 text-sm font-semibold text-white shadow-md transition-all hover:bg-indigo-600">Login</button>\n</nav>"""
        (UI_KIT_DIR / "glass_card.html").write_text(glass_card)
        (UI_KIT_DIR / "hero_section.html").write_text(hero_section)
        (UI_KIT_DIR / "modern_navbar.html").write_text(modern_navbar)

def import_ui_component(component_name: str) -> str:
    log_event("tool_call", {"tool": "import_ui_component", "component": component_name})
    console.print(f"\n[bold blue][🎨 UI KIT]:[/bold blue] Fetching {component_name}")
    _init_ui_kit()
    if component_name.lower() == "list":
        comps = [f.stem for f in UI_KIT_DIR.glob("*.html")]
        return f"[UI Kit Components Available]\n" + "\n".join(comps)
    p = UI_KIT_DIR / f"{component_name}.html"
    if not p.exists():
        return f"[ERROR] Component '{component_name}' not found. Use component_name='list' to see available templates."
    return f"[UI Component: {component_name}]\n{p.read_text()}"

def init_framework(framework_type: str, project_name: str) -> str:
    log_event("tool_call", {"tool": "init_framework", "type": framework_type, "name": project_name})
    console.print(f"\n[bold green][📦 INIT FRAMEWORK]:[/bold green] {framework_type} → {project_name}")
    if not _approve_bash(f"init_framework {framework_type}"):
        return "Initialization cancelled by user."

    import shutil as _shutil
    # ── Dependency preflight check ──
    DEPS = {
        "vite-react":  [("node", "Node.js"), ("npx", "npx (npm)")],
        "nextjs":      [("node", "Node.js"), ("npx", "npx (npm)")],
        "express-api": [("node", "Node.js"), ("npm", "npm")],
        "flask-api":   [("python3", "Python 3")],
    }
    missing = [label for (bin_, label) in DEPS.get(framework_type, []) if not _shutil.which(bin_)]
    if missing:
        return f"[ERROR] Missing required dependencies: {', '.join(missing)}. Please install them and try again."

    try:
        if framework_type == "vite-react":
            cmd = f"npx -y create-vite@latest {project_name} --template react && cd {project_name} && npm install"
        elif framework_type == "flask-api":
            cmd = f"mkdir -p {project_name} && cd {project_name} && python3 -m venv venv && venv/bin/pip install flask flask-cors"
        elif framework_type == "express-api":
            cmd = f"mkdir -p {project_name} && cd {project_name} && npm init -y && npm install express cors dotenv"
        elif framework_type == "nextjs":
            cmd = f"npx -y create-next-app@latest {project_name} --use-npm --eslint --tailwind --app --src-dir --import-alias '@/*' --yes"
        else:
            return f"[ERROR] Unknown framework type. Supported: vite-react, flask-api, express-api, nextjs"

        with console.status(f"[dim]Running {framework_type} boilerplate setup...[/dim]", spinner="dots"):
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=180)

        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "")[-BASH_OUTPUT_LIMIT:]
            return f"[ERROR] Initialization failed:\n{tail}"
        return f"[ok] Successfully initialized {framework_type} project at ./{project_name}"
    except Exception as e:
        return f"[ERROR] {e}"

AVAILABLE_TOOLS = {
    "execute_bash":   execute_bash,
    "read_file":      read_file,
    "write_to_file":  write_to_file,
    "patch_file":     patch_file,
    "edit_code_block": edit_code_block,
    "fetch_webpage":  fetch_webpage,
    "test_ui_flow":   test_ui_flow,
    "puppeteer_browser": puppeteer_browser,
    "play_media":     play_media,
    "app_control":    app_control,
    "look_at_screen": look_at_screen,
    "scaffold_project": scaffold_project,
    "ide_interact":   ide_interact,
    "search_codebase": search_codebase,
    "generate_repo_map": generate_repo_map,
    "delegate_task":  delegate_task,
    "run_daemon":     run_daemon,
    "consult_designer": consult_designer,
    "import_ui_component": import_ui_component,
    "init_framework": init_framework,
    "media_control": media_control,
    "run_macro": run_macro,
    "install_app": install_app,
}

JIMMY_TOOLS = [
    {"type": "function", "function": {
        "name": "install_app",
        "description": "Install an application using Flatpak on the host (e.g. spotify, vscode, discord, vlc, blender).",
        "parameters": {"type": "object", "properties": {
            "app": {"type": "string", "description": "The app name to install (e.g. 'spotify', 'vscode', 'discord')"},
            "method": {"type": "string", "description": "Installation method, default 'flatpak'"}
        }, "required": ["app"]}
    }},
    {"type": "function", "function": {
        "name": "execute_bash",
        "description": "Run a bash command. Use for installs, git, builds, listing dirs (ls -la), etc.",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string", "description": "The full shell command to run."}
        }, "required": ["command"]}
    }},
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Read a file's contents. Optional start_line and end_line for pagination.",
        "parameters": {"type": "object", "properties": {
            "file_path": {"type": "string"},
            "start_line": {"type": "integer"},
            "end_line": {"type": "integer"}
        }, "required": ["file_path"]}
    }},
    {"type": "function", "function": {
        "name": "write_to_file",
        "description": "Create or fully overwrite a file.",
        "parameters": {"type": "object", "properties": {
            "file_path": {"type": "string"},
            "content": {"type": "string"}
        }, "required": ["file_path", "content"]}
    }},
    {"type": "function", "function": {
        "name": "patch_file",
        "description": "Surgical in-place replacement using line numbers. start_line and end_line are inclusive.",
        "parameters": {"type": "object", "properties": {
            "file_path": {"type": "string"},
            "start_line": {"type": "integer", "description": "1-based starting line number to replace"},
            "end_line": {"type": "integer", "description": "1-based ending line number to replace (inclusive)"},
            "replacement_code": {"type": "string", "description": "The exact code to insert in place of the removed lines"}
        }, "required": ["file_path", "start_line", "end_line", "replacement_code"]}
    }},
    {"type": "function", "function": {
        "name": "fetch_webpage",
        "description": "Fetch and strip a webpage to readable text.",
        "parameters": {"type": "object", "properties": {
            "url": {"type": "string"}
        }, "required": ["url"]}
    }},
    {"type": "function", "function": {
        "name": "test_ui_flow",
        "description": "Run an automated UI test on a webpage using headless Chrome. Use this to verify web apps work correctly.",
        "parameters": {"type": "object", "properties": {
            "url": {"type": "string"},
            "actions_json": {"type": "string", "description": "JSON list of actions: [{'action': 'click'|'fill'|'assert_text'|'screenshot'|'wait', 'selector': 'css', 'value': 'optional'}]"}
        }, "required": ["url", "actions_json"]}
    }},
    {"type": "function", "function": {
        "name": "puppeteer_browser",
        "description": "Automate headless Chrome via Puppeteer. Use to inspect dynamic SPAs, capture screenshots, run visual design critiques with AI vision, evaluate JavaScript, or export PDFs.",
        "parameters": {"type": "object", "properties": {
            "action": {"type": "string", "enum": ["navigate", "screenshot", "critique", "pdf", "eval", "test_flow"], "description": "Action to execute in Chrome."},
            "url": {"type": "string", "description": "The URL to navigate to (e.g. http://localhost:5173)."},
            "payload": {"type": "string", "description": "Extra argument: output file path for screenshot/pdf, JavaScript string for eval, or JSON action array for test_flow."}
        }, "required": ["action", "url"]}
    }},
    {"type": "function", "function": {
        "name": "play_media",
        "description": "Automatically search for a song, music, or video on YouTube, resolve the top video, and immediately start playback on the user's desktop browser (Firefox or Chrome).",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "The song title, artist, or video to play (e.g. 'odeal', 'neo soul jazz')."},
            "platform": {"type": "string", "enum": ["youtube", "spotify"], "description": "Streaming platform. Default is youtube."},
            "browser": {"type": "string", "enum": ["firefox", "chrome"], "description": "Desktop browser to launch. Default is firefox."}
        }, "required": ["query"]}
    }},
    {"type": "function", "function": {
        "name": "app_control",
        "description": "Execute commands on the top 10 apps across Social Media (Twitter, Reddit, LinkedIn, Instagram, TikTok, Discord, Slack, Telegram, WhatsApp, Facebook), Streaming (YouTube, Twitch, Netflix, Prime Video, Disney+, Hulu, Kick, Vimeo, Dailymotion, Crunchyroll), IDEs (VS Code, Cursor, Neovim, PyCharm, IntelliJ, Sublime, Replit, Codespaces, StackBlitz, Jupyter), CADs (FreeCAD, Blender, OpenSCAD, Onshape, Tinkercad, SketchUp, Spline, LibreCAD, SolveSpace, Womp), Graphics (Figma, Canva, Photopea, GIMP, Inkscape, Krita, ImageMagick, Pixlr, Darktable, RawTherapee), and Music (Spotify, YouTube Music, SoundCloud, Apple Music, Tidal, Deezer, Bandcamp, VLC, Audacity, Rhythmbox).",
        "parameters": {"type": "object", "properties": {
            "app": {"type": "string", "description": "Name or key of the application (e.g. 'twitter', 'reddit', 'youtube', 'vscode', 'blender', 'figma', 'spotify', etc.)."},
            "action": {"type": "string", "description": "Action to perform: 'open', 'search', 'play', 'goto', 'user', 'channel', 'compose', 'render', etc. Default is 'open'."},
            "params_json": {"type": "string", "description": "Optional JSON dictionary of parameters (e.g. '{\"query\": \"...\"}', '{\"file\": \"...\", \"line\": 50}', '{\"user\": \"...\"}')."},
            "mode": {"type": "string", "enum": ["auto", "desktop", "web", "headless"], "description": "Execution mode: 'auto' (native if available, else web), 'desktop' (native CLI/window), 'web' (browser), 'headless' (scrape/interact via Puppeteer). Default is 'auto'."}
        }, "required": ["app"]}
    }},
    {"type": "function", "function": {
        "name": "media_control",
        "description": "Control desktop playback and volume (play_pause, next, previous, stop, volume_up, volume_down, set_volume, status) for Spotify, browser audio, and system media players.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["play_pause", "next", "previous", "stop", "volume_up", "volume_down", "set_volume", "status"],
                    "description": "The playback or volume action to perform."
                },
                "value": {
                    "type": "number",
                    "description": "Volume scalar (0.0 to 1.0 for set_volume, or 0.05 for increments)."
                },
                "player": {
                    "type": "string",
                    "description": "Specific player name (e.g., 'spotify', 'firefox', 'vlc'). Defaults to active player."
                }
            },
            "required": ["action"]
        }
    }},
    {"type": "function", "function": {
        "name": "run_macro",
        "description": "Execute multi-step sequential automation macros across shell, apps, and background daemons. Available: 'code_review', 'asset_pipeline_3d', 'deep_work_session', 'photo_restoration'.",
        "parameters": {
            "type": "object",
            "properties": {
                "macro_name": {
                    "type": "string",
                    "description": "Name of the macro to run ('code_review', 'asset_pipeline_3d', 'deep_work_session', 'photo_restoration')."
                },
                "overrides_json": {
                    "type": "string",
                    "description": "Optional JSON dictionary of input parameters to override macro defaults."
                }
            },
            "required": ["macro_name"]
        }
    }},
    {"type": "function", "function": {
        "name": "look_at_screen",
        "description": "ONLY when explicitly asked. Takes a screenshot and describes it. Use mode='ui_critique' for strict aesthetic/CSS feedback.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"},
            "mode": {"type": "string", "enum": ["general", "ui_critique"]}
        }, "required": ["query"]}
    }},
    {"type": "function", "function": {
        "name": "edit_code_block",
        "description": "AST-aware semantic code editing. Replaces a specific function or class by name without relying on line numbers. Use this instead of patch_file for code.",
        "parameters": {"type": "object", "properties": {
            "file_path": {"type": "string"},
            "target_name": {"type": "string", "description": "The exact name of the function or class to replace."},
            "new_code": {"type": "string", "description": "The complete replacement code for the function/class."}
        }, "required": ["file_path", "target_name", "new_code"]}
    }},
    {"type": "function", "function": {
        "name": "scaffold_project",
        "description": "Create many files at once from a JSON dict of {path: content}.",
        "parameters": {"type": "object", "properties": {
            "file_tree_json": {"type": "object", "additionalProperties": {"type": "string"}, "description": "A dictionary mapping file paths to their string content."}
        }, "required": ["file_tree_json"]}
    }},
    {"type": "function", "function": {
        "name": "ide_interact",
        "description": "Launch an IDE, open files, or jump to lines.",
        "parameters": {"type": "object", "properties": {
            "action":  {"type": "string", "enum": ["open", "goto"]},
            "payload": {"type": "string", "description": "File or folder to open. Leave empty to just launch the IDE empty."}
        }, "required": ["action"]}
    }},
    {"type": "function", "function": {
        "name": "search_codebase",
        "description": "Semantic RAG search using embeddings to find relevant code snippets in the workspace.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Natural language query, e.g. 'where is the auth logic'"}
        }, "required": ["query"]}
    }},
    {"type": "function", "function": {
        "name": "generate_repo_map",
        "description": "Generates a compressed AST map of the entire codebase showing all files, classes, and function signatures. Use this to get an architectural overview.",
        "parameters": {"type": "object", "properties": {
            "target_dir": {"type": "string", "description": "The directory to map. Default is '.'"}
        }}
    }},
    {"type": "function", "function": {
        "name": "delegate_task",
        "description": "Spawn a sub-agent to handle a complex, multi-step subtask in the background without user approval.",
        "parameters": {"type": "object", "properties": {
            "task_description": {"type": "string", "description": "Clear instructions for the sub-agent."}
        }, "required": ["task_description"]}
    }},
    {"type": "function", "function": {
        "name": "run_daemon",
        "description": "Launch a long-running background server/process and monitor it for crashes.",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string", "description": "The command to run in the background."}
        }, "required": ["command"]}
    }},
    {"type": "function", "function": {
        "name": "consult_designer",
        "description": "Consult the Design Lobe (an expert UI/UX sub-agent) for structural UI advice, color hexes, and Tailwind class blueprints.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "What component or layout do you need a design blueprint for?"}
        }, "required": ["query"]}
    }},
    {"type": "function", "function": {
        "name": "import_ui_component",
        "description": "Import pre-built, ultra-premium Tailwind UI components. Call with 'list' to see what is available.",
        "parameters": {"type": "object", "properties": {
            "component_name": {"type": "string"}
        }, "required": ["component_name"]}
    }},
    {"type": "function", "function": {
        "name": "init_framework",
        "description": "Initialize a modern framework boilerplate (e.g. vite-react, nextjs, flask-api, express-api) in a new directory.",
        "parameters": {"type": "object", "properties": {
            "framework_type": {"type": "string", "enum": ["vite-react", "nextjs", "flask-api", "express-api"]},
            "project_name": {"type": "string", "description": "The name of the new folder to create."}
        }, "required": ["framework_type", "project_name"]}
    }},
]

# ─────────────────────────────────────────────
# JSON extraction fallback (rescue engine)
# ─────────────────────────────────────────────
def _safe_json(s: str) -> dict | None:
    for candidate in (s, s.replace("\\", "\\\\")):
        try:
            return json.loads(candidate, strict=False)
        except Exception:
            pass
    return None


def rescue_tool_calls(text: str) -> list[dict]:
    """Extract tool-call objects from model text when native tool_calls is empty."""
    found = []
    seen  = set()

    patterns = [
        r'```(?:json|bash|sh|text)?\s*(\{[\s\S]*?\})\s*```',  # fenced object
        r'```(?:json|bash|sh|text)?\s*(\[[\s\S]*?\])\s*```',  # fenced array
        r'<tool[^>]*>\s*(\{[\s\S]*?\})\s*</tool[^>]*>',        # xml-ish object
    ]
    for pat in patterns:
        for m in re.finditer(pat, text, re.DOTALL):
            obj = _safe_json(m.group(1))
            items = obj if isinstance(obj, list) else [obj]
            for item in items:
                if isinstance(item, dict) and "name" in item and "arguments" in item:
                    key = (item["name"], json.dumps(item["arguments"], sort_keys=True))
                    if key not in seen:
                        found.append(item)
                        seen.add(key)

    # Brace-depth scanner as last resort
    if not found:
        depth = start = 0
        for i, ch in enumerate(text):
            if ch in "{[":
                if depth == 0:
                    start = i
                depth += 1
            elif ch in "}]":
                depth -= 1
                if depth == 0 and start != -1:
                    obj = _safe_json(text[start : i + 1])
                    items = obj if isinstance(obj, list) else [obj]
                    for item in items:
                        if isinstance(item, dict) and "name" in item and "arguments" in item:
                            key = (item["name"], json.dumps(item["arguments"], sort_keys=True))
                            if key not in seen:
                                found.append(item)
                                seen.add(key)
    return found


# ─────────────────────────────────────────────
# Split-Brain inference
#
# Roles:
#   smollm2  — cheap intent gate: "needs tool?" yes/no (no JSON generation)
#   qwen     — owns ALL tool call formatting + reasoning + narration
#
# Why: smollm2 can't reliably emit structured JSON for tool args.
# Letting it try causes the "tools not used" bug. We only ask it
# a binary question; qwen does the real work.
# ─────────────────────────────────────────────

GATE_SYSTEM = """\
Classify the user's latest message. Reply with exactly one word:
  TOOL  — if answering requires running a command, reading/writing files,
          fetching a URL, opening apps, IDEs, or any system action.
  CHAT  — if it's a question, explanation, or code generation with no
          system action needed.
One word only. No punctuation."""

CHAT_SYSTEM = """\
You are Jimmy, an elite Linux AI assistant.
Current directory: {cwd}
You are currently in CHAT MODE. You do NOT have access to tools right now.
Do NOT attempt to call tools, write 'execute_bash', or format JSON tool calls.
Simply answer the user's question, provide explanations, or write code for them to copy."""

IDEATOR_SYSTEM = """\
You are the Ideator. Your job is to read the user's prompt and brainstorm exactly 3 distinct, high-level scaffolding/execution strategies to accomplish their goal.
Present your ideas strictly as a numbered list (1., 2., 3.). Each item should be a concise but highly technical summary of the strategy.
Do NOT execute tools or write code.
Current directory: {cwd}"""

ARCHITECT_SYSTEM = """\
You are the Architect. Your ONLY job is to analyze the user's goal and output a structured markdown checklist of discrete tasks. 
Do NOT execute tools or write the final code. Just plan.

Current directory: {cwd}"""

EXECUTOR_SYSTEM = """\
You are the Executor. You receive a task checklist. Take the next incomplete item and use your available tools to accomplish it.
Current directory: {cwd}
Rules:
1. ALWAYS wrap your reasoning in a <thought>...</thought> block BEFORE calling any tools. Explain what you are trying to do and why.
2. NEVER guess terminal output — always call execute_bash.
3. NEVER hallucinate file contents — always call read_file.
4. To call a tool, you MUST emit a valid JSON tool call object exactly matching the schema.
5. You must return raw tool responses."""

CRITIC_SYSTEM = """\
You are the Critic. Review the Executor's tool outputs against the Architect's plan. 
If there are compilation bugs or logic gaps, reply 'REJECTED: [reason]'. 
If perfect, reply 'APPROVED'.
Current directory: {cwd}"""


@tracer.start_as_current_span("ollama_chat")
def _call(model: str, messages: list, tools: list | None = None,
          max_tokens: int = 1024, ctx: int = 4096) -> dict:
    span = trace.get_current_span()
    span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, OpenInferenceSpanKindValues.LLM.value)
    span.set_attribute(SpanAttributes.LLM_MODEL_NAME, model)
    span.set_attribute(SpanAttributes.INPUT_VALUE, json.dumps(messages))
    if tools:
        span.set_attribute("llm.tools", json.dumps(tools))

    opts = {"num_ctx": ctx, "num_predict": max_tokens}
    kwargs: dict = dict(model=model, messages=messages, options=opts)
    if tools:
        kwargs["tools"] = tools
        
    resp_obj = ollama.chat(**kwargs)
    resp = resp_obj.model_dump() if hasattr(resp_obj, "model_dump") else dict(resp_obj)
    span.set_attribute(SpanAttributes.OUTPUT_VALUE, json.dumps(resp))
    return resp


def needs_tool(messages: list) -> bool:
    """
    Cheap binary gate via smollm2.
    Only asks TOOL vs CHAT.
    """
    if messages and messages[-1]["role"] == "user":
        content = messages[-1]["content"].strip().lower()
        fast_verbs = ("open", "run", "do ", "use ", "read ", "write ", "fetch", "scaffold", "patch", "edit", "create", "make", "build", "let's", "lets", "fix", "update", "change")
        if content.startswith(fast_verbs) or "create" in content or "build" in content or "fix" in content:
            return True  # Fast-path bypass for obvious action verbs

    recent = [m for m in messages[-4:] if m["role"] in ("user", "assistant")]
    gate_msgs = [
        {"role": "system", "content": GATE_SYSTEM},
        *recent,
    ]
    try:
        resp = _call(ROUTER_MODEL, gate_msgs, max_tokens=5, ctx=512)
        verdict = (resp["message"].get("content") or "").strip().upper()
        logging.debug(f"Gate verdict: {verdict!r}")
        return "CHAT" not in verdict   # if uncertain, assume tool needed
    except Exception as e:
        logging.warning(f"Gate error: {e}")
        return True  # fail open


def agent_step(system_prompt: str, messages: list, cwd: str, with_tools: bool = False) -> dict:
    sys_msg = {"role": "system", "content": system_prompt.replace("{cwd}", cwd)}
    brain_msgs = [sys_msg, *messages[-CONTEXT_KEEP:]]
    tools = JIMMY_TOOLS if with_tools else None
    resp  = _call(BRAIN_MODEL, brain_msgs, tools=tools, max_tokens=2048, ctx=8192)
    msg   = resp["message"]
    if msg.get("content"):
        msg["content"] = re.sub(r"<\|im_start\|>|<\|im_end\|>|</?tool_response>", "", msg["content"]).strip()
    return msg

def momentum_engine(error_text: str, cwd: str, messages: list) -> str:
    console.print(f"\n[bold red]⚡ MOMENTUM ENGINE TRIGGERED[/bold red] - Semantic Prefetching...")
    
    query_results = chroma_collection.query(query_texts=[error_text], n_results=2)
    code_results = codebase_collection.query(query_texts=[error_text], n_results=2)
    
    context = []
    if query_results and query_results['documents'] and query_results['documents'][0]:
        context.append("Historical memory:\n" + "\n".join(query_results['documents'][0]))
    if code_results and code_results['documents'] and code_results['documents'][0]:
        context.append("Codebase matches:\n" + "\n".join(code_results['documents'][0]))
        
    prefetch_context = "\n".join(context)
    
    console.print("[dim]Generating Tree of Thoughts solutions...[/dim]")
    solutions = []
    for i in range(3):
        prompt = f"Error occurred: {error_text}\nContext:\n{prefetch_context}\nProvide Solution {i+1} as a brief plan."
        resp = _call(BRAIN_MODEL, [{"role": "user", "content": prompt}], max_tokens=300)
        solutions.append(resp["message"].get("content", f"Solution {i+1} fallback"))
        
    best_solution = solutions[0]
    best_score = -1
    
    console.print("[dim]Critic evaluating solutions...[/dim]")
    for idx, sol in enumerate(solutions):
        critique_prompt = f"Evaluate this solution for structural risk and feasibility (1-10 scale). Reply with ONLY the integer score.\nSolution: {sol}"
        resp = _call(BRAIN_MODEL, [{"role": "system", "content": CRITIC_SYSTEM.format(cwd=cwd)}, {"role": "user", "content": critique_prompt}], max_tokens=10)
        try:
            score = int(re.search(r'\d+', resp["message"].get("content", "0")).group())
        except:
            score = 0
        if score > best_score:
            best_score = score
            best_solution = sol
            
    console.print(f"[bold green]Best solution selected (Score: {best_score})[/bold green]")
    return f"[MOMENTUM ENGINE RECOVERY PLAN]\n{best_solution}"


# ─────────────────────────────────────────────
# Semantic Memory Loader
# ─────────────────────────────────────────────
CORE_MEMORY_KEYS = {"UX_LAWS", "ARCHITECTURE_LAWS", "IDE_CMD"}

def _semantic_mem_load(messages: list, query: str = "general context") -> None:
    """
    Load CORE_MEMORY_KEYS unconditionally.
    For all other keys, load their pre-computed embeddings from SQLite,
    and inject only the top-3 most relevant facts.
    """
    try:
        injected_parts = []
        core = {}
        for key in CORE_MEMORY_KEYS:
            res = chroma_collection.get(ids=[key])
            if res and res["documents"] and res["documents"][0]:
                core[key] = res["documents"][0]
                
        if core:
            injected_parts.append("[CORE LAWS]\n" + json.dumps(core, indent=2))

        results = chroma_collection.query(query_texts=[query], n_results=3)
        if results and results['documents'] and results['documents'][0]:
            top_memories = {idx: doc for idx, doc in zip(results['ids'][0], results['documents'][0]) if idx not in CORE_MEMORY_KEYS}
            if top_memories:
                injected_parts.append("[RELEVANT MEMORIES]\n" + json.dumps(top_memories, indent=2))
                
        if injected_parts:
            messages.append({"role": "system", "content": "\n\n".join(injected_parts)})
    except Exception as e:
        logging.warning(f"Memory load error: {e}")

# ─────────────────────────────────────────────
# Context compression
# ─────────────────────────────────────────────
def compress_context(messages: list, cwd: str) -> list:
    """Summarise old history, rebuild tight context."""
    console.print("\n[dim italic]System: Compressing context to save VRAM...[/dim italic]")
    sys_msg = {"role": "system", "content": f"Compression Context in {cwd}"}
    summary_prompt = (
        "Summarize the key facts, file paths, decisions, and task state "
        "from this conversation in ≤120 words. Be terse and factual."
    )
    try:
        resp = _call(
            BRAIN_MODEL,
            [sys_msg, *messages, {"role": "user", "content": summary_prompt}],
            max_tokens=200, ctx=8192,
        )
        summary = (resp["message"].get("content") or "").strip()
    except Exception:
        summary = "(summary unavailable)"

    summary_msg = {"role": "system", "content": f"[CONTEXT SUMMARY]\n{summary}"}
    
    # Pin recent important tool outputs that would otherwise be discarded
    dropped_messages = messages[:-CONTEXT_KEEP]
    pinned_messages = []
    for m in reversed(dropped_messages):
        if m.get("role") == "tool" and m.get("name") in ("read_file", "execute_bash"):
            pinned_messages.append(m)
            if len(pinned_messages) >= 2:
                break
    pinned_messages.reverse()
    
    if pinned_messages:
        pinned_notice = {"role": "system", "content": "[PINNED RECENT TOOL OUTPUTS TO PREVENT AMNESIA]"}
        return [sys_msg, summary_msg, pinned_notice, *pinned_messages, *messages[-CONTEXT_KEEP:]]
        
    return [sys_msg, summary_msg, *messages[-CONTEXT_KEEP:]]


# ─────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────
def chat_loop():
    welcome_msg = f"""[bold cyan]Gate[/bold cyan]   : [green]{ROUTER_MODEL:<30}[/green]
[bold cyan]Brain[/bold cyan]  : [green]{BRAIN_MODEL:<30}[/green]
[bold cyan]Log[/bold cyan]    : [dim]{str(session_log)[-30:]:<30}[/dim]
[bold cyan]Trace[/bold cyan]  : [dim]{px_session.url:<30}[/dim]
[dim]Type 'exit' to quit | 'auto' to enable autonomous mode[/dim]"""
    console.print(Panel(welcome_msg, title="[bold magenta]Jimmy v7.2 — Split-Brain Agent[/bold magenta]", border_style="magenta"))

    cwd = os.getcwd()
    messages: list[dict] = []

    # Boot aesthetic and architecture memory laws
    injected = False
    if not chroma_collection.get(ids=["UX_LAWS"])["documents"]:
        val = "Always use modern aesthetics. Use glassmorphism (backdrop-blur). Avoid pure black/white; use slate/zinc scales. Use subtle micro-animations (transition-all duration-300). Prioritize whitespace, rounded-2xl corners, and elegant typography."
        chroma_collection.upsert(documents=[val], ids=["UX_LAWS"])
        injected = True
        
    if not chroma_collection.get(ids=["ARCHITECTURE_LAWS"])["documents"]:
        val = "Always structure code professionally. Use MVC patterns or strict component separation. Never dump all logic into a single file. Export/Import modules. Write modular, object-oriented or functional code. No global variable spaghetti."
        chroma_collection.upsert(documents=[val], ids=["ARCHITECTURE_LAWS"])
        injected = True
        
    if injected:
        console.print("[dim italic]\\[Injected strict UX and Architecture Laws into memory][/dim italic]")

    # Boot memory — always load core laws; semantically filter the rest
    _semantic_mem_load(messages)

    while True:
        try:
            user_input = console.input("[bold cyan]You:[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim italic]Goodbye[/dim italic]")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            break
        if user_input.lower() == "auto":
            global AUTO_APPROVE
            AUTO_APPROVE = True
            console.print("[dim italic]Auto-approve enabled for this session[/dim italic]")
            continue

        log_event("user", {"content": user_input})
        messages.append({"role": "user", "content": user_input})

        # Inject daemon alerts
        if DAEMON_ALERTS:
            for alert in DAEMON_ALERTS:
                messages.append({"role": "system", "content": alert})
            DAEMON_ALERTS.clear()

        # Compress if needed
        if len(messages) > CONTEXT_KEEP + 4:
            messages = compress_context(messages, cwd)

        # ── Step 0: Gate (TOOL vs CHAT) ──
        with console.status("[dim]Gate is analyzing intent...[/dim]", spinner="dots"):
            tool_turn = needs_tool(messages)
            
        if not tool_turn:
            console.print("[dim]\\[Gate: CHAT mode][/dim]")
            with console.status("[bold green]Jimmy is thinking...[/bold green]", spinner="dots"):
                chat_msg = agent_step(CHAT_SYSTEM, messages, cwd, with_tools=False)
                final_chat = (chat_msg.get("content") or "").strip()
            if final_chat:
                messages.append({"role": "assistant", "content": final_chat})
                console.print("\n[bold magenta]Jimmy:[/bold magenta]")
                console.print(Markdown(final_chat))
            continue

        # ── Step 1a: The Ideator (Scaffolding Options) ──
        with console.status("[bold cyan]The Ideator is brainstorming approaches...[/bold cyan]", spinner="dots"):
            ideator_msg = agent_step(IDEATOR_SYSTEM, messages, cwd, with_tools=False)
            ideas = (ideator_msg.get("content") or "").strip()
            
        console.print(Panel(Markdown(ideas), title="[bold cyan]Execution Options[/bold cyan]", border_style="cyan"))
        
        # Parse ideas heuristically into choices
        choices = []
        for line in ideas.split('\n'):
            line_stripped = line.strip()
            if re.match(r'^(\d+\.|-|\*)\s+', line_stripped):
                # truncate long lines for the menu display to prevent terminal breakage
                display_line = line_stripped if len(line_stripped) < 100 else line_stripped[:97] + "..."
                choices.append(display_line)
        
        if not choices:
            choices = ["Proceed with the default plan", "I will provide my own plan"]
            
        choices.append("Custom... (Type your own instruction)")
        
        if not TUI_MODE:
            selected_option = questionary.select(
                "Pick a scaffolding strategy:",
                choices=choices
            ).ask()
        else:
            choices_text = "\n".join([f"{i+1}. {c}" for i, c in enumerate(choices)])
            console.print(Panel(f"Pick a scaffolding strategy:\n{choices_text}", title="Ideator", border_style="cyan"))
            idx_str = console.input("[bold cyan]Enter choice number (or type custom text):[/bold cyan] ").strip()
            if idx_str.isdigit() and 1 <= int(idx_str) <= len(choices):
                selected_option = choices[int(idx_str)-1]
            else:
                selected_option = idx_str
        
        if not selected_option:
            continue # cancelled via ctrl-c
            
        if selected_option == "Custom... (Type your own instruction)":
            selected_option = console.input("[bold cyan]Your custom instruction:[/bold cyan] ").strip()
            
        messages.append({"role": "system", "content": f"[IDEATOR OPTIONS]\n{ideas}"})
        messages.append({"role": "user", "content": f"I have selected this approach: {selected_option}. Proceed with the plan."})

        # ── Step 1b: The Architect (Plan Generation) ──
        with console.status("[bold cyan]The Architect is planning...[/bold cyan]", spinner="dots"):
            architect_msg = agent_step(ARCHITECT_SYSTEM, messages, cwd, with_tools=False)
            plan = (architect_msg.get("content") or "").strip()
            
        console.print(Panel(Markdown(plan), title="[bold cyan]Architect Plan[/bold cyan]", border_style="cyan"))
        messages.append({"role": "system", "content": f"[ARCHITECT PLAN]\n{plan}"})

        # ── Step 2: The Executor (Tool Execution) ──
        tool_loops = 0
        executor_done = False
        final_executor_msg = ""
        
        try:
            while tool_loops < MAX_TOOL_LOOPS and not executor_done:
                with console.status(f"[bold green]The Executor is working...[/bold green] [dim](Loop {tool_loops+1}/{MAX_TOOL_LOOPS})[/dim]", spinner="bouncingBar"):
                    msg = agent_step(EXECUTOR_SYSTEM, messages, cwd, with_tools=True)

                raw_tool_calls = msg.get("tool_calls") or []

                if not raw_tool_calls and msg.get("content"):
                    rescued = rescue_tool_calls(msg["content"])
                    if rescued:
                        console.print(f"[bold yellow]\\[Rescued {len(rescued)} leaked tool call(s)][/bold yellow]")
                        raw_tool_calls = [{"function": {"name": t["name"], "arguments": t["arguments"]}} for t in rescued]
                        msg["content"] = re.sub(r"```(?:json|bash|sh|text)?\s*\{[\s\S]*?\}\s*```", "", msg["content"]).strip()

                if raw_tool_calls:
                    messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": raw_tool_calls})

                    for tc in raw_tool_calls:
                        fn = tc["function"]
                        name = fn["name"]
                        args = fn.get("arguments") or {}
                        sig = (name, json.dumps(args, sort_keys=True))
                        if name not in AVAILABLE_TOOLS:
                            result = f"[ERROR] Unknown tool: {name}"
                        else:
                            console.print(f"[bold yellow]\\[→ {name}({', '.join(f'{k}={str(v)[:40]}' for k,v in args.items())})][/bold yellow]")
                            log_event("tool_dispatch", {"tool": name, "args": args})
                            result = AVAILABLE_TOOLS[name](**args)
                            log_event("tool_result", {"tool": name, "result": result[:200]})
                            
                            # MOMENTUM ENGINE INTERCEPT
                            if "[MOMENTUM_TRIGGER]" in result:
                                error_text = result.split("[MOMENTUM_TRIGGER]")[1].strip()
                                recovery_plan = momentum_engine(error_text, cwd, messages)
                                result = result + "\n\n" + recovery_plan

                        messages.append({"role": "tool", "content": result, "name": name})

                    tool_loops += 1
                    continue
                else:
                    final_executor_msg = (msg.get("content") or "").strip()
                    executor_done = True
                    if final_executor_msg:
                        messages.append({"role": "assistant", "content": final_executor_msg})
                        console.print("\n[bold green]Executor:[/bold green]")
                        console.print(Markdown(final_executor_msg))
                    
            if tool_loops >= MAX_TOOL_LOOPS:
                console.print(f"[bold red]\\[⚠ Executor tool loop limit ({MAX_TOOL_LOOPS}) hit][/bold red]\n")

            # ── Step 3: The Critic (Evaluation) ──
            if executor_done or tool_loops > 0:
                with console.status("[bold magenta]The Critic is evaluating...[/bold magenta]", spinner="dots"):
                    critic_msgs = messages + [{"role": "user", "content": "Review the execution. Reply ONLY with 'APPROVED' or 'REJECTED: [reason]'."}]
                    critic_msg = agent_step(CRITIC_SYSTEM, critic_msgs, cwd, with_tools=False)
                    critique = (critic_msg.get("content") or "").strip()
                
                console.print(Panel(Markdown(critique), title="[bold magenta]Critic Evaluation[/bold magenta]", border_style="magenta"))
                messages.append({"role": "system", "content": f"[CRITIC EVALUATION]\n{critique}"})
                
                if "REJECTED" in critique.upper():
                    console.print("[bold red]Critic REJECTED the outcome. Please ask the user for further instructions or automatically retry.[/bold red]")

        except Exception as e:
            console.print(f"\n[bold red]\\[Error: {e}][/bold red]\n")
            log_event("error", {"msg": str(e)})

        # Auto-Reflection
        if tool_loops > 0:
            with console.status("[dim]Reflecting on new knowledge...[/dim]", spinner="dots"):
                try:
                    refl_msg = "Did you learn any PERMANENT facts about the workspace/user in this task? If YES, output ONLY a JSON dict. If NO, output 'NO'."
                    resp = _call(ROUTER_MODEL, [*messages[-CONTEXT_KEEP:], {"role": "user", "content": refl_msg}], max_tokens=100, ctx=4096)
                    content = (resp["message"].get("content") or "").strip()
                    if content and "NO" not in content[:10]:
                        facts = _safe_json(content)
                        if not facts:
                            m = re.search(r'\{[\s\S]*?\}', content)
                            if m: facts = _safe_json(m.group(0))
                        
                        if facts and isinstance(facts, dict):
                            added = False
                            for k, v in facts.items():
                                if str(v).strip().upper() not in ["NO", "NONE", "FALSE", ""]:
                                    chroma_collection.upsert(documents=[str(v)], ids=[k])
                                    console.print(f"[dim italic]\\[Learned new fact: {k}][/dim italic]")
                                    added = True
                except Exception:
                    pass

if TUI_MODE:
    from textual.app import App, ComposeResult
    from textual.containers import Horizontal, Vertical, Grid
    from textual.widgets import Header, Footer, Static, Input, Button, RichLog, ProgressBar
    from textual import work

    class JimmyApp(App):
        CSS = """
        Screen {
            background: #e0e5ec;
            color: #64748b;
        }
        #sidebar {
            width: 30%;
            height: 100%;
            background: #e0e5ec;
            padding: 1 2;
            border-right: vkey #a3b1c6;
        }
        #main {
            width: 70%;
            height: 100%;
            background: #e0e5ec;
        }
        .brand-panel {
            background: #e0e5ec;
            border: panel #a3b1c6;
            content-align: center middle;
            height: 5;
            margin-bottom: 2;
        }
        .telemetry-title {
            text-style: bold;
            color: #64748b;
            margin-top: 1;
        }
        #btn-grid {
            layout: grid;
            grid-size: 2 2;
            grid-columns: 1fr 1fr;
            grid-gutter: 1 2;
            height: auto;
            margin-top: 1;
        }
        Button {
            width: 100%;
            height: 3;
            background: #e0e5ec;
            color: #64748b;
            border: panel #a3b1c6;
        }
        Button:hover {
            color: #3b82f6;
            border: panel #3b82f6;
        }
        RichLog {
            height: 1fr;
            margin: 1 2;
            background: #0f172a;
            color: #38bdf8;
            border: round #a3b1c6;
            padding: 1 2;
        }
        #cmd-input {
            dock: bottom;
            margin: 0 2 1 2;
            background: #e0e5ec;
            color: #334155;
            border: panel #a3b1c6;
        }
        """

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            with Horizontal():
                with Vertical(id="sidebar"):
                    yield Static("[bold slate_blue]JIMMY[/bold slate_blue][dim]v7[/dim]", classes="brand-panel")
                    yield Static("[bold green]● System Online[/bold green]\n", classes="telemetry-title")
                    
                    yield Static("VRAM Allocation (4.2/6 GB)", classes="telemetry-title")
                    yield ProgressBar(total=100, progress=70, show_eta=False)
                    
                    yield Static("Context Buffer (4096 tokens)", classes="telemetry-title")
                    yield ProgressBar(total=100, progress=35, show_eta=False)
                    
                    yield Static("System Overrides", classes="telemetry-title")
                    with Grid(id="btn-grid"):
                        yield Button("Vision", id="macro_vision")
                        yield Button("Repo Map", id="macro_repomap")
                        yield Button("IDE Link", id="macro_ide")
                        yield Button("Flush DB", id="macro_flush")
                with Vertical(id="main"):
                    yield RichLog(id="tui_log", markup=True, auto_scroll=True)
                    yield Input(placeholder="❯ Transmit instruction to Jimmy...", id="cmd-input")
            yield Footer()

        def on_mount(self) -> None:
            global tui_log, tui_app
            tui_log = self.query_one("#tui_log", RichLog)
            tui_app = self
            self.run_jimmy()

        @work(thread=True)
        def run_jimmy(self):
            chat_loop()
            
        def on_input_submitted(self, event: Input.Submitted) -> None:
            text = event.value.strip()
            if text:
                tui_input_queue.put(text)
                event.input.value = ""

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "macro_vision":
                tui_input_queue.put("Execute visual inspection routine: look_at_screen")
            elif event.button.id == "macro_repomap":
                tui_input_queue.put("Generate a repository map")
            elif event.button.id == "macro_ide":
                tui_input_queue.put("Open IDE link")
            elif event.button.id == "macro_flush":
                tui_input_queue.put("Flush memory DB")

    if __name__ == "__main__":
        app = JimmyApp()
        app.run()
else:
    if __name__ == "__main__":
        chat_loop()