import os
import re
import json
import time
import asyncio
import logging
from typing import List, Dict, Tuple, Optional, Callable

CLOUD_NODE_URL = ""

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

try:
    from pydantic import BaseModel, Field
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False

from .lobes.memory import get_memory_collection, CHROMA_AVAILABLE

import urllib.request
import urllib.parse

# Pydantic Structured Output definition
if PYDANTIC_AVAILABLE:
    class ActionResponse(BaseModel):
        action: str = Field(description="The action to execute: 'chat', 'youtube', 'browser', 'spotify', 'mailto', 'scroll', 'app_control', 'app_install', 'media_control'")
        message: Optional[str] = Field(None, description="Conversational text or status explanation for the user")
        app: Optional[str] = Field(None, description="App name ('spotify', 'twitter', 'figma', 'blender', 'vscode', 'twitch', 'soundcloud', etc.)")
        category: Optional[str] = Field(None, description="Category: 'social', 'streaming', 'ide', 'cad', 'graphics', 'music'")
        sub_action: Optional[str] = Field(None, description="Sub-action: 'open', 'search', 'play', 'install', 'goto', 'user', 'create', 'play_pause', 'next', 'previous', 'stop', 'volume_up', 'volume_down'")
        query: Optional[str] = Field(None, description="Search query if action is youtube, spotify, or app_control")
        value: Optional[float] = Field(None, description="Volume scalar or increment for media_control")
        player: Optional[str] = Field(None, description="Specific media player name for media_control")
        url: Optional[str] = Field(None, description="URL if action is browser, youtube, or app_control")
        browser: Optional[str] = Field(None, description="Browser preference ('firefox', 'chrome') if specified")
        videoId: Optional[str] = Field(None, description="Direct YouTube video ID if resolved")
        trackTitle: Optional[str] = Field(None, description="Resolved track or media title")
        package_id: Optional[str] = Field(None, description="Package identifier (e.g. com.spotify.Client)")
        method: Optional[str] = Field(None, description="Installation method ('flatpak', 'native')")
        command: Optional[str] = Field(None, description="Shell command for installation or launch")
        recipient: Optional[str] = Field(None, description="Email address recipient if action is mailto")
        subject: Optional[str] = Field(None, description="Email subject if action is mailto")
        body: Optional[str] = Field(None, description="Email body if action is mailto")
        direction: Optional[str] = Field(None, description="Scroll direction (up/down) if action is scroll")
else:
    ActionResponse = None

SYSTEM_PROMPT = """You are Andromeda, an intelligent, sleek, and high-performance AI workspace companion and agent.
You are sharp, poised, polite, and exceptionally capable. You execute user commands smoothly, with zero unnecessary friction, complaints, or delays.
You never insult the user, tell them to shut up, or complain about work. When the user asks you to relax, do a task, install software, or play music, you cheerfully and precisely fulfill their request.
Your primary function is to interpret user commands and execute actions by returning STRICT JSON.
You must always reply with a single JSON object. Do not include markdown code blocks (e.g. ```json) around the JSON itself. Do not include any conversational text outside the JSON.

Available actions:
1. "youtube": Play music or video on YouTube. Requires fields: "action": "youtube", "query": "search query or artist", "message": "conversational reply"
2. "app_control": Launch, search, or control applications. Requires fields: "action": "app_control", "app": "app_name", "sub_action": "open|search|play|install", "message": "conversational reply"
3. "app_install": Install an application or flatpak. Requires fields: "action": "app_install", "app": "spotify|vscode|vlc|etc", "method": "flatpak", "message": "conversational reply"
4. "media_control": Control desktop MPRIS media (play/pause, next, volume). Requires fields: "action": "media_control", "sub_action": "play_pause|next|previous|volume_up|volume_down|set_volume", "message": "conversational reply"
5. "spotify": Control or search Spotify. Requires fields: "action": "spotify", "query": "search query", "message": "conversational reply"
6. "browser": Open a website or URL in browser. Requires fields: "action": "browser", "url": "https://...", "message": "conversational reply"
7. "scroll": Scroll the screen up or down. Requires fields: "action": "scroll", "direction": "up|down", "message": "conversational reply"
8. "mailto": Draft an email. Requires fields: "action": "mailto", "recipient": "email@address.com", "subject": "...", "body": "...", "message": "conversational reply"
9. "chat": Standard conversational, educational, or code response. Requires fields: "action": "chat", "message": "<full response, explanations, and code examples>"

CRITICAL RULE FOR PROGRAMMING, EXPLANATIONS, AND GENERAL QUESTIONS:
- For code requests, programming questions (such as Python inheritance, algorithms, debugging, syntax, etc.), explanations, or conversations, ALWAYS use action "chat".
- Place the complete explanation, including all code blocks and examples, directly within the "message" field.
- NEVER invent arbitrary custom JSON keys or schemas (e.g., do NOT output schemas like {"Superclass": ..., "Methods": ...}).

Example responses:
{"action": "youtube", "query": "tame impala loser", "message": "Playing Tame Impala - Loser on YouTube for you."}
{"action": "app_install", "app": "spotify", "method": "flatpak", "message": "Installing Spotify via Flatpak for you."}
{"action": "app_control", "app": "spotify", "sub_action": "open", "message": "Opening Spotify."}
{"action": "chat", "message": "Here is an example of Python inheritance:\\n\\n```python\\nclass Parent:\\n    def greet(self):\\n        return 'Hello'\\n\\nclass Child(Parent):\\n    pass\\n```\\n\\nUse `super()` to invoke the parent initializer."}
{"action": "chat", "message": "I'm right here. How can I help you today?"}
"""

class VectorGateEngine:
    def __init__(self):
        self.enabled = CHROMA_AVAILABLE
        self.threshold = 0.65 # Cosine distance threshold (lower is more similar)
        
        # Hardcoded intent mapping for fallback and fast detection
        self.intent_patterns = {
            "youtube": [
                r"\b(youtube|yt)\b",
                r"\b(play|watch|listen)\b.*\b(on|in)\s+youtube\b",
                r"\b(watch|play)\s+(video|clip|trailer)\b"
            ],
            "browser": [
                r"\b(open|launch|use|goto|go to|browse)\s+(firefox|chrome|browser|site|website|web|internet|link|url)\b",
                r"\b(https?://[^\s]+)\b",
                r"\b(firefox|chrome)\b"
            ],
            "spotify": [
                r"\b(play|start|resume)\s+(music|spotify|playlist|song)\b",
                r"\b(next|skip|pause|stop)\s+track\b",
                r"\bspotify\b"
            ],
            "mailto": [
                r"\b(write|send|draft)\s+(an\s+)?(email|mail|message)\b",
                r"\bmailto\b"
            ],
            "scroll": [
                r"\b(scroll|swipe)\s+(up|down)\b"
            ],
            "app_control": [
                r"\b(figma|canva|photopea|gimp|inkscape|krita|darktable|rawtherapee|imagemagick)\b",
                r"\b(freecad|blender|openscad|onshape|tinkercad|sketchup|spline|solvespace|womp|librecad)\b",
                r"\b(vscode|cursor|neovim|nvim|pycharm|intellij|sublime|replit|codespaces|stackblitz|jupyter)\b",
                r"\b(twitter|reddit|linkedin|instagram|tiktok|discord|slack|telegram|whatsapp|facebook)\b",
                r"\b(twitch|netflix|primevideo|disneyplus|hulu|kick|vimeo|dailymotion|crunchyroll)\b",
                r"\b(soundcloud|applemusic|tidal|deezer|bandcamp|vlc|audacity|rhythmbox)\b"
            ],
            "media_control": [
                r"\b(pause|resume|unpause)\s+(music|song|playback|audio|track)\b",
                r"\b(next|skip|prev|previous)\s+(song|track)\b",
                r"\b(volume\s+(up|down)|turn\s+(up|down)\s+(the\s+)?(music|volume|sound)|mute\s+audio|set\s+volume)\b"
            ],
            "app_install": [
                r"\b(install|setup|get)\s+([a-zA-Z0-9_-]+)\b",
                r"\b(flatpak\s+install|install\s+via\s+flatpak|do\s+it\s+via\s+flatpak)\b",
                r"\binstall\s+(spotify|vscode|discord|vlc|gimp|blender|obs|slack)\b"
            ]
        }
        
        if self.enabled:
            import chromadb
            from chromadb.utils import embedding_functions
            self.client = chromadb.EphemeralClient()
            self.embed_fn = embedding_functions.DefaultEmbeddingFunction()
            self.collection = self.client.get_or_create_collection("intent_gate", embedding_function=self.embed_fn)
            
            # Embed intent prototypes
            documents = []
            metadatas = []
            ids = []
            i = 0
            
            prototypes = {
                "youtube": ["play music on youtube", "play odeal on youtube", "open youtube", "search youtube", "watch on youtube", "play video on youtube", "youtube video", "play loser by tame impala on youtube"],
                "browser": ["use youtube on firefox", "open firefox", "open browser", "browse web", "open website", "open in browser", "launch firefox", "use browser"],
                "spotify": ["play music", "start spotify", "play a song", "next track", "pause music", "put on some tracks", "play jazz"],
                "mailto": ["send an email", "draft a message", "write an email to", "email boss"],
                "scroll": ["scroll down", "scroll up", "swipe down the screen"],
                "app_control": ["open figma", "launch blender", "open vscode", "open twitter", "search on reddit", "open freecad", "open canva", "open onshape", "play on soundcloud", "watch twitch", "open pycharm", "open neovim", "open discord", "open slack", "check linkedin", "open gimp", "open inkscape", "open photopea", "open netflix"],
                "media_control": ["pause music", "resume music", "next song", "skip song", "previous song", "volume up", "volume down", "turn down the music", "turn up the music", "mute audio", "pause playback"],
                "app_install": ["install spotify", "install spotify via flatpak", "do it via flatpak", "install app via flatpak", "setup flatpak", "get spotify", "install vlc"]
            }
            
            for intent, phrases in prototypes.items():
                for phrase in phrases:
                    documents.append(phrase)
                    metadatas.append({"intent": intent})
                    ids.append(f"gate_{i}")
                    i += 1
                    
            self.collection.upsert(documents=documents, metadatas=metadatas, ids=ids)

    def classify_intent(self, prompt: str) -> Tuple[str, bool]:
        """
        Vector-based pre-routing logic. Uses ephemeral Chroma collection.
        Falls back to regex if Chroma isn't available.
        """
        normalized = prompt.lower().strip()
        
        if self.enabled:
            results = self.collection.query(query_texts=[normalized], n_results=1)
            if results and results['distances'] and len(results['distances'][0]) > 0:
                dist = results['distances'][0][0]
                if dist < self.threshold:
                    matched_intent = results['metadatas'][0][0]['intent']
                    logging.info(f"[Gate] Vector Match: '{normalized}' -> {matched_intent} (dist={dist:.2f})")
                    return matched_intent, True
                    
        # Fallback to Regex
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, normalized):
                    logging.info(f"[Gate] Regex Match: '{normalized}' -> {intent}")
                    return intent, True
        
        return "chat", False

class SocratesScaffoldingAsync:
    def __init__(self):
        self.model_name = os.getenv("ANDROMEDA_MODEL", "llama3.2:latest")
        self.client = ollama.AsyncClient() if OLLAMA_AVAILABLE else None

    async def get_working_model(self, requested_model: Optional[str] = None) -> str:
        """
        Verifies if target model exists in Ollama, otherwise returns first available installed model.
        """
        target = requested_model or self.model_name
        if not OLLAMA_AVAILABLE or not self.client:
            return target
        try:
            models_res = await self.client.list()
            installed = [m.get('name', '') or m.get('model', '') for m in models_res.get('models', [])]
            if any(target in m for m in installed):
                return target
            prefix = target.split(":")[0]
            matched = [m for m in installed if prefix in m]
            if matched:
                return matched[0]
            if installed:
                logging.info(f"[Engine] Configured model '{target}' not found. Falling back to '{installed[0]}'")
                return installed[0]
        except Exception as e:
            logging.warning(f"[Engine] Could not query Ollama models: {e}")
        return target

    async def query_model(self, full_messages: List[Dict], enforce_json: bool = False, model: Optional[str] = None) -> str:
        """
        Sends payload to the local Ollama environment or Cloud Node asynchronously.
        """
        if CLOUD_NODE_URL and AIOHTTP_AVAILABLE:
            prompt_str = ""
            for msg in full_messages:
                prompt_str += f"<|im_start|>{msg['role']}\n{msg['content']}<|im_end|>\n"
            prompt_str += "<|im_start|>assistant\n"
            
            try:
                from urllib.parse import urlparse
                import aiohttp
                parsed = urlparse(CLOUD_NODE_URL)
                base_url = f"{parsed.scheme}://{parsed.netloc}"
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{base_url}/v1/chat/completions",
                        json={"prompt": prompt_str, "max_tokens": 512, "temperature": 0.1},
                        timeout=aiohttp.ClientTimeout(total=6)
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            return data.get("choices", [{}])[0].get("message", {}).get("content", '{"action": "chat", "message": "No response."}')
                        else:
                            logging.warning(f"[Cloud Engine HTTP {resp.status}], falling back to local Ollama")
            except Exception as e:
                logging.warning(f"[Cloud Engine Failed: {e}], falling back to local Ollama")

        if not OLLAMA_AVAILABLE:
            return '{"action": "chat", "message": "Ollama is missing. Mock response."}'

        try:
            active_model = await self.get_working_model(requested_model=model)
            kwargs = {
                "model": active_model,
                "messages": full_messages
            }
            if enforce_json and PYDANTIC_AVAILABLE and ActionResponse:
                kwargs["format"] = ActionResponse.model_json_schema()

            response = await self.client.chat(**kwargs)
            return response.get('message', {}).get('content', '{"action": "chat", "message": "No response."}')
        except Exception as e:
            return '{"action": "chat", "message": "[Local Engine Error]: ' + str(e) + '"}'

    async def execute_fast_chat(self, user_prompt: str, messages: List[Dict], context_memory: str = "", stream_callback=None, model: Optional[str] = None) -> str:
        if stream_callback:
            await stream_callback("Synthesizing response...")
            
        base_history = messages[-6:] if len(messages) > 6 else messages
        system = f"""{SYSTEM_PROMPT}
You are Andromeda. Respond directly to the user query following your personality rules.
You must output strictly valid JSON conforming to the ActionResponse schema."""
        
        full_messages = [{"role": "system", "content": system + context_memory}] + base_history
        return await self.query_model(full_messages, enforce_json=True, model=model)

    async def execute_fast_extract(self, intent: str, user_prompt: str, context_memory: str = "", stream_callback=None, model: Optional[str] = None) -> str:
        if stream_callback:
            await stream_callback(f"[Gate] Fast Extraction for: {intent}")
            
        system = f"""You are Andromeda. The user intent is '{intent}'.
Extract parameters from the user's prompt and output ONLY a valid JSON object representing the action.
Do not output markdown code blocks. Always include a polite, helpful 'message' explaining what you're doing.
For 'youtube': {{"action": "youtube", "query": "search term or artist", "browser": "firefox|chrome|none", "message": "conversational reply"}}
For 'app_install': {{"action": "app_install", "app": "spotify|vscode|etc", "method": "flatpak", "message": "conversational reply"}}
For 'app_control': {{"action": "app_control", "app": "app_name", "category": "social|streaming|ide|cad|graphics|music", "sub_action": "open|search|play|install", "query": "optional", "url": "https://...", "message": "conversational reply"}}
For 'browser': {{"action": "browser", "url": "https://...", "message": "conversational reply"}}
For 'spotify': {{"action": "spotify", "query": "search term", "message": "conversational reply"}}
For 'media_control': {{"action": "media_control", "sub_action": "play_pause|next|previous|stop|volume_up|volume_down|set_volume", "value": 0.05, "message": "conversational reply"}}
For 'scroll': {{"action": "scroll", "direction": "up|down", "message": "conversational reply"}}
For 'mailto': {{"action": "mailto", "recipient": "email@address.com", "subject": "...", "body": "...", "message": "conversational reply"}}
For 'chat': {{"action": "chat", "message": "conversational reply"}}"""
        
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"{context_memory}\nQuery: {user_prompt}"}
        ]
        
        return await self.query_model(messages, enforce_json=True, model=model)

    async def execute_socrates_loop(self, user_prompt: str, messages: List[Dict], context_memory: str = "", stream_callback=None, model: Optional[str] = None) -> str:
        # Context Compression: Keep only the last 6 messages to avoid quadratic scaling
        base_history = messages[-6:] if len(messages) > 6 else messages
        
        # --- STAGE 1: THE DRAFT ---
        if stream_callback:
            await stream_callback("[Socrates] Thinking: Formulating draft...")
            
        stage_1_system = f"{SYSTEM_PROMPT}\nYou are Andromeda's Executor node. Draft an initial response to the query."
        stage_1_messages = [{"role": "system", "content": stage_1_system + context_memory}] + base_history
        initial_draft = await self.query_model(stage_1_messages, model=model)

        # --- STAGE 2: THE CRITIC ---
        if stream_callback:
            await stream_callback("[Socrates] Thinking: Critiquing logic...")
            
        stage_2_system = """You are Andromeda's Socrates Critic. Analyze the provided draft JSON response.
Verify that the response is helpful, precise, polite, and that the intent is handled correctly.
Since JSON syntax is strictly enforced, focus on logical flow and task completion.
Output your critique explicitly."""
        stage_2_messages = [
            {"role": "system", "content": stage_2_system},
            {"role": "user", "content": f"Original Query: {user_prompt}\nInitial Draft: {initial_draft}"}
        ]
        critique = await self.query_model(stage_2_messages, model=model)

        # --- STAGE 3: THE REFINE ---
        if stream_callback:
            await stream_callback("[Socrates] Thinking: Synthesizing final output...")
            
        stage_3_system = f"""{SYSTEM_PROMPT}
You are Andromeda's Synthesis node. Combine the initial draft and the critique to output a perfect, verified JSON response.
You MUST output strictly valid JSON."""
        stage_3_messages = [
            {"role": "system", "content": stage_3_system},
            {"role": "user", "content": f"Original Query: {user_prompt}\nDraft: {initial_draft}\nCritique: {critique}"}
        ]
        
        refined_output = await self.query_model(stage_3_messages, enforce_json=True, model=model)
        return refined_output

def resolve_youtube_top_video(query: str) -> Dict[str, Optional[str]]:
    """Fast synchronous resolver extracting exact top videoId, title, and watch URL from YouTube."""
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
            "url": f"https://www.youtube.com/watch?v={vid}" if vid else f"https://www.youtube.com/results?search_query={urllib.parse.quote(clean_q)}"
        }
    except Exception as e:
        logging.warning(f"[YouTube Resolver] Failed for '{query}': {e}")
        return {"videoId": None, "title": query, "url": None}

gate_engine = VectorGateEngine()
scaffolding = SocratesScaffoldingAsync()

async def run_agent_step(user_prompt: str, messages: List[Dict], cwd: str, with_tools: bool = False, telemetry_data: dict = None, stream_callback: Callable = None, model: Optional[str] = None) -> dict:
    """
    Fully Async Unified Orchestrator: Executes a reasoning step using Gate Engine and Fast Chat / Socrates Loop.
    Honors dynamic Council of AIs model adjudication.
    """
    # Mock fallback
    if not OLLAMA_AVAILABLE and not CLOUD_NODE_URL:
        if stream_callback:
            await stream_callback("[Warning] Ollama unavailable. Using mock response.")
        mock_response = '{"action": "chat", "message": "Ollama is missing. Mock response."}'
        if "email" in user_prompt.lower():
            mock_response = '{"action": "mailto", "recipient": "test@test.com", "subject": "Test", "body": "Mock email"}'
        elif "music" in user_prompt.lower() or "spotify" in user_prompt.lower():
            mock_response = '{"action": "spotify", "query": "mock music"}'
        elif "battery" in user_prompt.lower():
            mock_response = f'{{"action": "chat", "message": "Your battery is at {telemetry_data.get("battery", "unknown")}%"}}' if telemetry_data else '{"action": "chat", "message": "I cannot see your battery."}'
        return {"role": "assistant", "content": mock_response}

    # Context Loading
    context_text = ""
    if CHROMA_AVAILABLE:
        try:
            coll = get_memory_collection()
            if coll:
                results = await asyncio.to_thread(coll.query, query_texts=[user_prompt], n_results=2)
                if results and results.get("documents") and len(results["documents"][0]) > 0:
                    context_text = "\n\n[Local Memory Context]:\n" + "\n".join(results["documents"][0])
        except Exception:
            pass
            
    if telemetry_data:
        context_text += "\\n\\n[Device Hardware State]:\\n" + json.dumps(telemetry_data)

    # Intent Routing
    intent, is_tool = gate_engine.classify_intent(user_prompt)
    
    # Check if deep multi-stage Socrates reasoning is explicitly requested
    deep_reasoning = any(k in user_prompt.lower() for k in ["think deeply", "reason through", "socrates", "plan out", "deliberate"])

    if is_tool:
        final_completion = await scaffolding.execute_fast_extract(intent, user_prompt, context_text, stream_callback, model=model)
    elif deep_reasoning:
        final_completion = await scaffolding.execute_socrates_loop(user_prompt, messages, context_text, stream_callback, model=model)
    else:
        final_completion = await scaffolding.execute_fast_chat(user_prompt, messages, context_text, stream_callback, model=model)

    raw = (final_completion or "").strip()
    
    # Clean surrounding markdown code fences
    fence_json = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
    if fence_json:
        candidate_raw = fence_json.group(1).strip()
        if candidate_raw.startswith("{") and candidate_raw.endswith("}"):
            raw = candidate_raw
    else:
        if raw.startswith("```json"):
            raw = raw[7:]
        if raw.startswith("```"):
            raw = raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

    parsed = None
    # 1. Direct JSON parse
    try:
        parsed = json.loads(raw)
    except Exception:
        # 2. Extract outermost braces
        b_start = raw.find("{")
        b_end = raw.rfind("}")
        if b_start != -1 and b_end != -1 and b_end > b_start:
            try:
                parsed = json.loads(raw[b_start:b_end + 1])
            except Exception:
                pass

    # 3. Resilient recovery for incomplete or raw natural language output
    if not parsed or not isinstance(parsed, dict):
        if raw == "{" or (raw.startswith("{") and len(raw) < 10):
            parsed = {
                "action": "chat",
                "message": "I apologize, the response stream was interrupted. Please ask again and I will give you the complete response."
            }
        else:
            parsed = {
                "action": "chat",
                "message": raw or "Command executed."
            }

    # 4. Normalize unexpected schema (e.g. {"Superclass": "ParentClass", ...})
    valid_actions = {"chat", "youtube", "browser", "spotify", "mailto", "scroll", "app_control", "app_install", "media_control"}
    act = parsed.get("action", "")
    if act not in valid_actions:
        if "message" in parsed and isinstance(parsed["message"], str):
            parsed["action"] = "chat"
        else:
            # Transform raw dictionary into readable markdown bullet points
            lines = []
            for k, v in parsed.items():
                if isinstance(v, list):
                    lines.append(f"• **{k}**: {', '.join(str(i) for i in v)}")
                elif isinstance(v, dict):
                    lines.append(f"• **{k}**:\n```json\n{json.dumps(v, indent=2)}\n```")
                else:
                    lines.append(f"• **{k}**: {v}")
            parsed = {
                "action": "chat",
                "message": "\n".join(lines) if lines else raw
            }

    # Post-process and enrich parsed JSON for tools
    try:
        act = parsed.get("action", "chat")
        
        # 1. Resolve YouTube video ID & direct URL
        if act == "youtube":
            yt_query = parsed.get("query") or user_prompt
            yt_res = await asyncio.to_thread(resolve_youtube_top_video, yt_query)
            if yt_res.get("videoId"):
                parsed["videoId"] = yt_res["videoId"]
                parsed["url"] = yt_res["url"]
                parsed["trackTitle"] = yt_res["title"]
                parsed["message"] = f"Playing \"{yt_res['title']}\" on YouTube"
            final_completion = json.dumps(parsed)
            
        # 2. Enrich app_install & flatpak requests
        elif act in ["app_install", "flatpak"] or (act == "app_control" and parsed.get("sub_action") == "install"):
            app_raw = parsed.get("app") or ("spotify" if "spotify" in user_prompt.lower() else "app")
            parsed["action"] = "app_install"
            parsed["app"] = app_raw.lower()
            parsed["method"] = "flatpak"
            flatpak_ids = {
                "spotify": "com.spotify.Client",
                "vscode": "com.visualstudio.code",
                "discord": "com.discordapp.Discord",
                "vlc": "org.videolan.VLC",
                "gimp": "org.gimp.GIMP",
                "blender": "org.blender.Blender",
                "slack": "com.slack.Slack",
                "obs": "com.obsproject.Studio"
            }
            pkg_id = flatpak_ids.get(app_raw.lower(), f"com.{app_raw.lower()}.App")
            parsed["package_id"] = pkg_id
            parsed["command"] = f"flatpak install --user -y flathub {pkg_id}"
            parsed["message"] = f"Ready to install {app_raw.capitalize()} via Flatpak ({pkg_id})."
            final_completion = json.dumps(parsed)
        else:
            final_completion = json.dumps(parsed)

    except Exception as parse_err:
        logging.warning(f"[Agent Step Post-Process] JSON parse error: {parse_err}")
        final_completion = json.dumps(parsed)

    return {"role": "assistant", "content": final_completion}
