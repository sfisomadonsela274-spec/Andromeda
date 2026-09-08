#!/usr/bin/env python3
"""
=============================================================================
             🌌 ANDROMEDA CORE: COUNCIL OF AIS ENGINE 🌌
=============================================================================
Orchestrates adaptive, deterministic multi-model reasoning and inference across
local Ollama SLMs, enforcing strict memory-aware VRAM optimization and seat routing:

  1. The Scribe (Default)
     - Model: qwen2.5-coder:1.5b
     - Keep-Alive: -1 (Always warm in VRAM)
     - Role: Standard conversation, fast intent extraction, quick tools, latency-sensitive dispatch.

  2. The Architect (Deep Coder)
     - Model: qwen2.5-coder:7b
     - Keep-Alive: 0 (Evicted immediately post-task to free 4.7GB VRAM)
     - Role: Heavy multi-file code, refactors, syntax-dense tasks, algorithms, architectural logic.

  3. The Logician (Deep Thinker)
     - Model: llama3.2
     - Keep-Alive: 5m (5-minute VRAM window for multi-turn inquiry)
     - Role: Deep research, systematic analysis, trade-off evaluation, Socrates critique loops.

  4. The Sentinel (Vision / Pixel-Spicer)
     - Model: moondream
     - Keep-Alive: 2m (2-minute VRAM window for consecutive screenshot checks)
     - Role: Pixel-spacing, layout critique, design aesthetics, OCR, image analysis.
=============================================================================
"""

import os
import re
import sys
import json
import time
import asyncio
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union, Tuple

# Optional ollama python SDK integration
try:
    import ollama as ollama_sdk
except ImportError:
    ollama_sdk = None


# =============================================================================
# 🏛️ COUNCIL SEAT ARCHETYPES & VRAM PROFILES
# =============================================================================

@dataclass(frozen=True)
class CouncilSeat:
    id: str
    title: str
    model: str
    keep_alive: Union[int, str]
    role: str
    vram_profile: str
    description: str
    system_prompt: str
    tags: List[str] = field(default_factory=list)


SEAT_SCRIBE = CouncilSeat(
    id="scribe",
    title="The Scribe",
    model="qwen2.5-coder:1.5b",
    keep_alive=-1,  # Always warm in VRAM
    role="Fast Intent Extraction, Quick Tools & Standard Conversation",
    vram_profile="~1.0GB VRAM (Resident / Always Warm)",
    description="Primary rapid-response coordinator for conversational queries, shell commands, and quick dispatch.",
    system_prompt=(
        "You are The Scribe, the rapid coordinator of the Andromeda Council of AIs. "
        "Your duty is crisp, precise communication, fast intent extraction, and immediate utility."
    ),
    tags=["conversation", "intent", "tools", "quick", "shell", "fast"]
)

SEAT_ARCHITECT = CouncilSeat(
    id="architect",
    title="The Architect",
    model="qwen2.5-coder:7b",
    keep_alive=0,  # Evicted immediately post-task to reclaim 4.7GB VRAM
    role="Deep Coder, Multi-File Engineering & Complex Syntax",
    vram_profile="~4.7GB VRAM (Transient / Evicted Post-Task)",
    description="Master software engineer tasked with syntax-dense code generation, algorithmic optimization, and refactoring.",
    system_prompt=(
        "You are The Architect, master software architect of the Andromeda Council. "
        "You design robust, production-grade, bug-free implementations with impeccable type safety and architecture."
    ),
    tags=["code", "refactor", "algorithm", "architecture", "multi-file", "syntax", "debug"]
)

SEAT_LOGICIAN = CouncilSeat(
    id="logician",
    title="The Logician",
    model="llama3.2",
    keep_alive="5m",  # 5-minute memory persistence for iterative reasoning
    role="Deep Thinker, Systematic Analysis & Socrates Critique Loops",
    vram_profile="~2.0GB VRAM (Cached 5m Idle Window)",
    description="Philosopher-critic specialized in deep research, trade-off evaluation, and multi-perspective critique.",
    system_prompt=(
        "You are The Logician, philosophical reasoning engine of the Andromeda Council. "
        "You dissect problems systematically, applying Socratic questioning, first-principles deduction, and root-cause analysis."
    ),
    tags=["analysis", "logic", "critique", "socrates", "research", "trade-offs", "philosophy"]
)

SEAT_SENTINEL = CouncilSeat(
    id="sentinel",
    title="The Sentinel",
    model="moondream",
    keep_alive="2m",  # 2-minute memory persistence for visual inspect cycles
    role="Vision, Pixel-Spacing, Layout Critique & Image Inspection",
    vram_profile="~1.7GB VRAM (Cached 2m Idle Window)",
    description="Vision specialist scrutinizing pixel alignment, neumorphic soft UI depth, spatial aesthetics, and diagrams.",
    system_prompt=(
        "You are The Sentinel, visual aesthetics and layout inspection engine of the Andromeda Council. "
        "You analyze spatial arrangements, pixel spacing, contrast ratios, and imagery with exacting precision."
    ),
    tags=["vision", "image", "screenshot", "layout", "spacing", "pixel", "ui", "design"]
)

COUNCIL_SEATS: Dict[str, CouncilSeat] = {
    SEAT_SCRIBE.id: SEAT_SCRIBE,
    SEAT_ARCHITECT.id: SEAT_ARCHITECT,
    SEAT_LOGICIAN.id: SEAT_LOGICIAN,
    SEAT_SENTINEL.id: SEAT_SENTINEL,
}


# =============================================================================
# 🔍 DETERMINISTIC ADJUDICATION & CODE DENSITY HEURISTICS
# =============================================================================

ARCHITECT_KEYWORDS = {
    "refactor", "architect", "architecture", "algorithm", "data structure",
    "regex", "regular expression", "sql", "sqlite3", "database schema",
    "foreign key", "deadlock", "race condition", "memory leak", "stack trace",
    "traceback", "dockerfile", "caddyfile", "nginx.conf", "fastapi", "uvicorn",
    "endpoint", "asyncio", "multithreading", "concurrency", "pull request",
    "class hierarchy", "dependency injection", "type hint", "interface",
    "syntax error", "compiler error", "reimplement", "unit test", "benchmark",
    "complexity", "o(n)", "big-o", "binary tree", "pointer", "segfault"
}

LOGICIAN_KEYWORDS = {
    "think deeply", "socrates", "socratic", "critique", "critique loop",
    "systematic", "pros and cons", "trade-off", "tradeoffs", "evaluate",
    "deep research", "philosophical", "philosophy", "first principles",
    "why is it that", "deduce", "deduction", "implications", "hypothesis",
    "counter-argument", "counterargument", "fallacy", "causality",
    "epistemology", "ethics", "deliberate", "root cause analysis", "underlying reason"
}

SENTINEL_KEYWORDS = {
    "pixel", "pixel-spacing", "pixels", "layout", "padding", "margin",
    "spacing", "alignment", "align", "css", "visual", "look at this",
    "inspect design", "font size", "color contrast", "color palette",
    "wireframe", "screenshot", "image", "picture", "photo", "diagram",
    "neumorphic", "glassmorphism", "ui design", "ux critique", "visual bug",
    "aspect ratio", "resolution", "moondream"
}

CODE_SYNTAX_TOKENS = [
    r"```[a-zA-Z0-9_\-]*\n[\s\S]*?\n```",  # Fenced code blocks
    r"\bdef\s+[a-zA-Z_]\w*\s*\(",          # Python def
    r"\bclass\s+[a-zA-Z_]\w*[:\(]",        # Class definition
    r"\bfunction\s+[a-zA-Z_]\w*\s*\(",     # JS function
    r"\b(?:const|let|var)\s+[a-zA-Z_]",    # JS declarations
    r"\bimport\s+[a-zA-Z_]",               # Import
    r"\bfrom\s+[a-zA-Z_\.]+\s+import",     # Python from import
    r"\b(?:public|private|protected)\s+",  # OOP modifiers
    r"\b(?:SELECT|INSERT|UPDATE|DELETE)\s+.*?\bFROM\b", # SQL
    r"[{}\[\];]{2,}",                      # Dense structural punctuation
    r"(?:->|=>|::|:=)",                    # Arrow / Scope / Walrus operators
    r"\b(?:if|elif|else|for|while|try|catch|except|finally)\s*[:\(]" # Control flow
]


def calculate_code_density(prompt: str) -> float:
    """
    Computes a normalized code density score from 0.0 (pure natural text)
    to 1.0 (dense programming code).

    Evaluation dimensions:
      1. Presence and size of markdown fenced code blocks (```...```).
      2. Frequency of structural symbols (brackets, semicolons, arrows).
      3. Prevalence of programming language keywords and syntax constructs.
      4. Indentation patterns typical of code.
    """
    if not prompt or not prompt.strip():
        return 0.0

    text = prompt.strip()
    lines = [line for line in text.split("\n") if line.strip()]
    total_lines = max(len(lines), 1)
    total_chars = max(len(text), 1)

    # 1. Fenced code block check
    fenced_matches = re.findall(r"```[\s\S]*?```", text)
    fenced_char_count = sum(len(m) for m in fenced_matches)
    fenced_ratio = fenced_char_count / total_chars

    # 2. Syntax token check
    syntax_matches = 0
    for pattern in CODE_SYNTAX_TOKENS:
        syntax_matches += len(re.findall(pattern, text, flags=re.IGNORECASE | re.MULTILINE))

    # 3. Symbol punctuation density
    code_punct = sum(1 for c in text if c in "{}[]();<>=!&|:/*+$%^~`\\")
    punct_ratio = min(code_punct / total_chars, 0.4) * 2.5  # Scale up

    # 4. Indented lines check (typical of code snippets)
    indented_lines = sum(1 for line in lines if line.startswith("    ") or line.startswith("\t"))
    indent_ratio = indented_lines / total_lines

    # Weighted composite score
    composite_score = (
        (fenced_ratio * 0.45) +
        (min(syntax_matches / 4.0, 1.0) * 0.30) +
        (punct_ratio * 0.15) +
        (indent_ratio * 0.10)
    )

    return round(min(max(composite_score, 0.0), 1.0), 3)


def adjudicate_seat(
    prompt: str,
    has_image: bool = False,
    seat_override: Optional[str] = None
) -> Tuple[CouncilSeat, Dict[str, Any]]:
    """
    Deterministically routes a prompt to the appropriate Council Seat.

    Decision Hierarchy:
      1. Explicit Seat Override (if requested and valid)
      2. The Sentinel: has_image is True, or prompt embeds base64/image paths
      3. The Architect: Code density >= 0.22, fenced multi-line code, or Architect keywords
      4. The Logician: Deep analysis, philosophical inquiry, or Socrates critique loops
      5. The Sentinel (Text Mode): Explicit pixel spacing or layout review requests
      6. The Scribe: Standard default for swift, warm, general interactions
    """
    # 1. Manual Override
    if seat_override:
        clean_override = seat_override.strip().lower().replace("the ", "")
        if clean_override in COUNCIL_SEATS:
            seat = COUNCIL_SEATS[clean_override]
            return seat, {
                "seat_id": seat.id,
                "reason": f"Manual override explicitly requested seat: {seat.title}",
                "code_density": calculate_code_density(prompt),
                "has_image": has_image,
                "rule": "manual_override"
            }

    prompt_lower = prompt.lower()
    code_density = calculate_code_density(prompt)

    # 2. Image / Vision check -> The Sentinel
    has_image_embed = bool(
        re.search(r"data:image\/[a-zA-Z]+;base64,", prompt) or
        re.search(r"\bhttps?:\/\/\S+\.(?:png|jpe?g|webp|gif|svg)\b", prompt_lower) or
        re.search(r"\b\/?[\w\-\.\/]+\.(?:png|jpe?g|webp|svg)\b", prompt_lower)
    )

    if has_image or has_image_embed:
        return SEAT_SENTINEL, {
            "seat_id": SEAT_SENTINEL.id,
            "reason": "Visual inspection active (image attachment or media URI detected).",
            "code_density": code_density,
            "has_image": True,
            "rule": "vision_payload"
        }

    # 3. High Code Density or Architect Keywords -> The Architect
    has_fenced_code = "```" in prompt
    architect_matches = [kw for kw in ARCHITECT_KEYWORDS if re.search(r"\b" + re.escape(kw) + r"\b", prompt_lower)]

    if code_density >= 0.18 or has_fenced_code or len(architect_matches) >= 2 or (architect_matches and code_density >= 0.08):
        matched_str = ", ".join(architect_matches[:3]) if architect_matches else "structural syntax density"
        return SEAT_ARCHITECT, {
            "seat_id": SEAT_ARCHITECT.id,
            "reason": f"Deep coding task detected (code density: {code_density:.2f}, markers: {matched_str}).",
            "code_density": code_density,
            "has_image": False,
            "rule": "code_density_and_architecture"
        }

    # 4. Visual / Pixel-Spacing / Layout Critique (Text Mode) -> The Sentinel
    sentinel_matches = [kw for kw in SENTINEL_KEYWORDS if re.search(r"\b" + re.escape(kw) + r"\b", prompt_lower)]
    has_layout_marker = any(k in prompt_lower for k in ["pixel", "spacing", "padding", "margin", "layout", "neumorphic", "css"])
    if (len(sentinel_matches) >= 2 or (sentinel_matches and has_layout_marker)) and code_density < 0.25:
        return SEAT_SENTINEL, {
            "seat_id": SEAT_SENTINEL.id,
            "reason": f"Pixel-spacing and layout critique requested (keywords: {', '.join(sentinel_matches[:3])}).",
            "code_density": code_density,
            "has_image": False,
            "rule": "layout_critique_text"
        }

    # 5. Deep Reasoning & Socratic Critique -> The Logician
    logician_matches = [kw for kw in LOGICIAN_KEYWORDS if re.search(r"\b" + re.escape(kw) + r"\b", prompt_lower)]
    if len(logician_matches) >= 1 and code_density < 0.25:
        return SEAT_LOGICIAN, {
            "seat_id": SEAT_LOGICIAN.id,
            "reason": f"Systematic reasoning requested (keywords: {', '.join(logician_matches[:3])}).",
            "code_density": code_density,
            "has_image": False,
            "rule": "socratic_logic_and_analysis"
        }

    # 6. Default Fallback -> The Scribe
    return SEAT_SCRIBE, {
        "seat_id": SEAT_SCRIBE.id,
        "reason": f"Standard conversational query, fast intent or tool dispatch (code density: {code_density:.2f}).",
        "code_density": code_density,
        "has_image": False,
        "rule": "default_scribe_warm"
    }


# =============================================================================
# ⚡ OLLAMA INFERENCE & MEMORY-AWARE VRAM CONTROLLER
# =============================================================================

def get_ollama_host() -> str:
    """Resolves the active Ollama host from environment or standard fallbacks."""
    env_host = os.environ.get("OLLAMA_HOST", "").strip()
    if env_host:
        if not env_host.startswith("http://") and not env_host.startswith("https://"):
            env_host = f"http://{env_host}"
        return env_host.rstrip("/")

    # Check container network
    try:
        urllib.request.urlopen("http://ollama:11434/api/tags", timeout=0.5)
        return "http://ollama:11434"
    except Exception:
        pass

    return "http://localhost:11434"


def unload_model(model: str, ollama_host: Optional[str] = None) -> bool:
    """
    Explicitly evicts a model from VRAM by issuing keep_alive=0 to Ollama.
    Critical for The Architect (qwen2.5-coder:7b) to immediately release 4.7GB VRAM.
    """
    host = (ollama_host or get_ollama_host()).rstrip("/")
    url = f"{host}/api/generate"
    payload = {
        "model": model,
        "prompt": "",
        "keep_alive": 0
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            return resp.status == 200
    except Exception as e:
        if ollama_sdk:
            try:
                client = ollama_sdk.Client(host=host)
                client.generate(model=model, prompt="", keep_alive=0)
                return True
            except Exception:
                pass
        print(f"[Council VRAM Warning] Failed to explicitly evict {model}: {e}", file=sys.stderr)
        return False


def warm_the_scribe(ollama_host: Optional[str] = None) -> bool:
    """Pre-warms The Scribe (qwen2.5-coder:1.5b) into VRAM with keep_alive=-1."""
    host = (ollama_host or get_ollama_host()).rstrip("/")
    url = f"{host}/api/generate"
    payload = {
        "model": SEAT_SCRIBE.model,
        "prompt": "ping",
        "keep_alive": -1
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15.0) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"[Council Scribe Warning] Pre-warming failed: {e}", file=sys.stderr)
        return False


def deliberate(
    prompt: str,
    has_image: bool = False,
    images: Optional[List[str]] = None,
    seat_override: Optional[str] = None,
    system_prompt: Optional[str] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    options: Optional[Dict[str, Any]] = None,
    ollama_host: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes Council deliberation with strict memory-aware VRAM keep_alive enforcement.

    Steps:
      1. Adjudicates the optimal Council Seat based on prompt characteristics.
      2. Configures messages (system prompt + history + current user input + images).
      3. Dispatches inference to Ollama with the seat's specific keep_alive setting.
      4. Post-Task Eviction: If The Architect was summoned, executes explicit VRAM
         eviction (`keep_alive: 0`) to immediately return 4.7GB VRAM to the system.
      5. Returns a rich, telemetry-ready CouncilVerdict dict.
    """
    start_time = time.time()
    host = (ollama_host or get_ollama_host()).rstrip("/")

    # 1. Adjudicate Seat
    seat, adjudication = adjudicate_seat(
        prompt=prompt,
        has_image=has_image or bool(images),
        seat_override=seat_override
    )

    # 2. Build Messages Array
    messages: List[Dict[str, Any]] = []

    # System instruction
    effective_system = system_prompt or seat.system_prompt
    if effective_system:
        messages.append({"role": "system", "content": effective_system})

    # Prior conversation context
    if conversation_history:
        for msg in conversation_history:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            })

    # Current user turn
    user_turn: Dict[str, Any] = {"role": "user", "content": prompt}
    if images and seat.id == SEAT_SENTINEL.id:
        user_turn["images"] = images
    messages.append(user_turn)

    # 3. Assemble Inference Payload
    payload: Dict[str, Any] = {
        "model": seat.model,
        "messages": messages,
        "stream": False,
        "keep_alive": seat.keep_alive,
    }
    if options:
        payload["options"] = options

    chat_url = f"{host}/api/chat"
    response_data: Dict[str, Any] = {}
    content = ""
    error_msg = None

    try:
        req = urllib.request.Request(
            chat_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=120.0) as resp:
            raw_body = resp.read().decode("utf-8")
            response_data = json.loads(raw_body)
            msg_obj = response_data.get("message", {})
            content = msg_obj.get("content", "")

    except urllib.error.HTTPError as http_err:
        if ollama_sdk:
            try:
                client = ollama_sdk.Client(host=host)
                sdk_resp = client.chat(
                    model=seat.model,
                    messages=messages,
                    keep_alive=seat.keep_alive,
                    options=options
                )
                content = sdk_resp.get("message", {}).get("content", "")
                response_data = dict(sdk_resp)
            except Exception as inner_e:
                error_msg = f"HTTP Error {http_err.code}: {http_err.reason}. Fallback failed: {inner_e}"
        else:
            error_msg = f"HTTP Error {http_err.code}: {http_err.reason}"

    except Exception as e:
        error_msg = f"Inference dispatch error: {e}"

    duration_ms = round((time.time() - start_time) * 1000, 2)

    # 4. Post-Task Eviction for The Architect
    vram_action = f"Kept in VRAM with keep_alive={seat.keep_alive}"
    if seat.id == SEAT_ARCHITECT.id:
        evicted = unload_model(seat.model, ollama_host=host)
        vram_action = "Evicted post-task: 4.7GB VRAM freed" if evicted else "Eviction signal dispatched"

    # 5. Return Council Verdict
    return {
        "status": "success" if not error_msg else "error",
        "error": error_msg,
        "seat": seat.title,
        "seat_id": seat.id,
        "model": seat.model,
        "keep_alive": seat.keep_alive,
        "vram_profile": seat.vram_profile,
        "vram_action": vram_action,
        "adjudication": adjudication,
        "content": content,
        "duration_ms": duration_ms,
        "eval_count": response_data.get("eval_count", 0),
        "prompt_eval_count": response_data.get("prompt_eval_count", 0),
        "eval_duration_ms": round(response_data.get("eval_duration", 0) / 1e6, 2),
        "host": host
    }


async def deliberate_async(
    prompt: str,
    has_image: bool = False,
    images: Optional[List[str]] = None,
    seat_override: Optional[str] = None,
    system_prompt: Optional[str] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    options: Optional[Dict[str, Any]] = None,
    ollama_host: Optional[str] = None
) -> Dict[str, Any]:
    """Asynchronous wrapper around deliberate() executing in an async executor thread."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: deliberate(
            prompt=prompt,
            has_image=has_image,
            images=images,
            seat_override=seat_override,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
            options=options,
            ollama_host=ollama_host
        )
    )


class CouncilEngine:
    """Council of AIs orchestration singleton."""
    deliberate = staticmethod(deliberate)
    deliberate_async = staticmethod(deliberate_async)
    adjudicate_seat = staticmethod(adjudicate_seat)
    unload_model = staticmethod(unload_model)
    warm_the_scribe = staticmethod(warm_the_scribe)
    calculate_code_density = staticmethod(calculate_code_density)


# Singleton instance for direct import across modules
council = CouncilEngine()



# =============================================================================
# 🖥️ COMMAND-LINE DEMONSTRATION & BENCHMARK SUITE
# =============================================================================

def print_council_sitemap():
    """Prints a styled overview of the Council of AIs."""
    print("""
=============================================================================
             🌌 ANDROMEDA CORE: COUNCIL OF AIS SITEMAP 🌌
=============================================================================""")
    for seat in COUNCIL_SEATS.values():
        print(f"  🏛️  {seat.title.upper()} ({seat.id})")
        print(f"     • Model:       {seat.model}")
        print(f"     • Keep-Alive:  {seat.keep_alive}")
        print(f"     • VRAM Policy: {seat.vram_profile}")
        print(f"     • Duty:        {seat.role}")
        print(f"     • Focus:       {', '.join(seat.tags)}")
        print()
    print("=============================================================================")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Andromeda Council of AIs Orchestrator")
    parser.add_argument("prompt", nargs="?", help="Input prompt to adjudicate and deliberate")
    parser.add_argument("--image", action="store_true", help="Flag indicating image attachment is present")
    parser.add_argument("--seat", choices=["scribe", "architect", "logician", "sentinel"], help="Force specific seat")
    parser.add_argument("--adjudicate-only", action="store_true", help="Only run seat adjudication without LLM call")
    parser.add_argument("--seats", action="store_true", help="Display Council seats sitemap")
    parser.add_argument("--warm", action="store_true", help="Pre-warm The Scribe (qwen2.5-coder:1.5b)")
    parser.add_argument("--evict", metavar="MODEL", help="Explicitly unload a model from VRAM")

    args = parser.parse_args()

    if args.seats:
        print_council_sitemap()
        return

    if args.warm:
        print("⚡ Pre-warming The Scribe (qwen2.5-coder:1.5b) in VRAM...")
        ok = warm_the_scribe()
        print(f"Result: {'SUCCESS (Resident in VRAM)' if ok else 'FAILED'}")
        return

    if args.evict:
        print(f"🧹 Evicting model {args.evict} from VRAM...")
        ok = unload_model(args.evict)
        print(f"Result: {'SUCCESS (VRAM Reclaimed)' if ok else 'FAILED'}")
        return

    if not args.prompt:
        parser.print_help()
        print("\nExample invocations:")
        print("  python council_engine.py \"Hello, what are your capabilities?\"")
        print("  python council_engine.py \"Refactor this SQL function with indexes: SELECT * FROM messages\"")
        print("  python council_engine.py \"Think deeply about why SQLite3 WAL mode prevents read/write locks\"")
        print("  python council_engine.py \"Critique the pixel spacing and padding of my navbar\" --image")
        return

    if args.adjudicate_only:
        seat, adj = adjudicate_seat(args.prompt, has_image=args.image, seat_override=args.seat)
        print(json.dumps({
            "adjudicated_seat": seat.title,
            "seat_id": seat.id,
            "model": seat.model,
            "keep_alive": seat.keep_alive,
            "adjudication_metadata": adj
        }, indent=2))
        return

    print(f"\n🔮 Convening the Council for prompt: \"{args.prompt[:60]}...\"")
    verdict = deliberate(
        prompt=args.prompt,
        has_image=args.image,
        seat_override=args.seat
    )

    print("\n" + "="*70)
    print(f"🏛️  SEAT APPOINTED:   {verdict['seat']} ({verdict['model']})")
    print(f"🧠  ADJUDICATION:     {verdict['adjudication']['reason']}")
    print(f"📊  CODE DENSITY:     {verdict['adjudication'].get('code_density', 0.0)}")
    print(f"💾  VRAM ACTION:      {verdict['vram_action']}")
    print(f"⏱️  LATENCY:          {verdict['duration_ms']} ms")
    print("="*70)
    print("\nRESPONSE:\n")
    print(verdict.get("content") or f"[Error]: {verdict.get('error')}")
    print("\n" + "="*70)


if __name__ == "__main__":
    main()
