import re
from pathlib import Path

content = Path("/home/sfiso/ai-agent/jimmy.py").read_text()

# 1. Replace Prompts
old_prompts = r'''GATE_SYSTEM = """\\
Classify the user's latest message. Reply with exactly one word:
  TOOL  — if answering requires running a command, reading/writing files,
          fetching a URL, opening apps, IDEs, or any system action.
  CHAT  — if it's a question, explanation, or code generation with no
          system action needed.
One word only. No punctuation."""

AGENT_SYSTEM = """\\
You are Jimmy, an elite Linux AI assistant embedded in an agentic workflow.
Current directory: {cwd}
Rules:
1. ALWAYS wrap your reasoning in a <thought>...</thought> block BEFORE calling any tools. Explain what you are trying to do and why.
2. NEVER guess terminal output — always call execute_bash.
3. NEVER hallucinate file contents — always call read_file.
4. After tool results arrive, narrate what happened clearly and concisely.
5. If multiple steps are needed, call tools one at a time.
6. You MUST emit a valid JSON tool call object to use a tool. Do NOT write 'execute_bash' as plain text.
7. ARCHITECTURE: Write modular, DRY code. Never use global state spaghetti. Split logic into reusable functions/classes."""

CHAT_SYSTEM = """\\
You are Jimmy, an elite Linux AI assistant.
Current directory: {cwd}
You are currently in CHAT MODE. You do NOT have access to tools right now.
Do NOT attempt to call tools, write 'execute_bash', or format JSON tool calls.
Simply answer the user's question, provide explanations, or write code for them to copy."""'''

new_prompts = '''ARCHITECT_SYSTEM = """\\
You are the Architect. Your ONLY job is to analyze the user's goal and output a structured markdown checklist of discrete tasks. 
Do NOT execute tools or write the final code. Just plan.

Current directory: {cwd}"""

EXECUTOR_SYSTEM = """\\
You are the Executor. You receive a task checklist. Take the next incomplete item and use your available tools to accomplish it.
Current directory: {cwd}
Rules:
1. ALWAYS wrap your reasoning in a <thought>...</thought> block BEFORE calling any tools. Explain what you are trying to do and why.
2. NEVER guess terminal output — always call execute_bash.
3. NEVER hallucinate file contents — always call read_file.
4. You MUST emit a valid JSON tool call object to use a tool.
5. You must return raw tool responses."""

CRITIC_SYSTEM = """\\
You are the Critic. Review the Executor's tool outputs against the Architect's plan. 
If there are compilation bugs or logic gaps, reply 'REJECTED: [reason]'. 
If perfect, reply 'APPROVED'.
Current directory: {cwd}"""'''

content = content.replace(old_prompts, new_prompts)

# 2. Replace qwen_step and needs_tool with agent_step and momentum_engine
old_qwen = r'''def needs_tool(messages: list) -> bool:
    """
    Cheap binary gate via smollm2.
    Only asks TOOL vs CHAT — never asks it to format JSON.
    Falls back to True (optimistic) on any failure.
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
        return True  # fail open — let qwen decide


def qwen_step(messages: list, cwd: str, with_tools: bool = True) -> dict:
    """
    One qwen inference step.
    Returns the raw message dict so the caller can inspect tool_calls.
    """
    sys_prompt = AGENT_SYSTEM if with_tools else CHAT_SYSTEM
    sys_msg = {"role": "system", "content": sys_prompt.format(cwd=cwd)}
    brain_msgs = [sys_msg, *messages[-CONTEXT_KEEP:]]
    tools = JIMMY_TOOLS if with_tools else None
    resp  = _call(BRAIN_MODEL, brain_msgs, tools=tools, max_tokens=2048, ctx=8192)
    msg   = resp["message"]
    # Sanitise leaked control tokens from content
    if msg.get("content"):
        msg["content"] = re.sub(
            r"<\|im_start\|>|<\|im_end\|>|</?tool_response>", "", msg["content"]
        ).strip()
    return msg'''

new_agent_step = '''def agent_step(system_prompt: str, messages: list, cwd: str, with_tools: bool = False) -> dict:
    sys_msg = {"role": "system", "content": system_prompt.format(cwd=cwd)}
    brain_msgs = [sys_msg, *messages[-CONTEXT_KEEP:]]
    tools = JIMMY_TOOLS if with_tools else None
    resp  = _call(BRAIN_MODEL, brain_msgs, tools=tools, max_tokens=2048, ctx=8192)
    msg   = resp["message"]
    if msg.get("content"):
        msg["content"] = re.sub(r"<\|im_start\|>|<\|im_end\|>|</?tool_response>", "", msg["content"]).strip()
    return msg

def momentum_engine(error_text: str, cwd: str, messages: list) -> str:
    console.print(f"\\n[bold red]⚡ MOMENTUM ENGINE TRIGGERED[/bold red] - Semantic Prefetching...")
    
    query_results = chroma_collection.query(query_texts=[error_text], n_results=2)
    code_results = codebase_collection.query(query_texts=[error_text], n_results=2)
    
    context = []
    if query_results and query_results['documents'] and query_results['documents'][0]:
        context.append("Historical memory:\\n" + "\\n".join(query_results['documents'][0]))
    if code_results and code_results['documents'] and code_results['documents'][0]:
        context.append("Codebase matches:\\n" + "\\n".join(code_results['documents'][0]))
        
    prefetch_context = "\\n".join(context)
    
    console.print("[dim]Generating Tree of Thoughts solutions...[/dim]")
    solutions = []
    for i in range(3):
        prompt = f"Error occurred: {error_text}\\nContext:\\n{prefetch_context}\\nProvide Solution {i+1} as a brief plan."
        resp = _call(BRAIN_MODEL, [{"role": "user", "content": prompt}], max_tokens=300)
        solutions.append(resp["message"].get("content", f"Solution {i+1} fallback"))
        
    best_solution = solutions[0]
    best_score = -1
    
    console.print("[dim]Critic evaluating solutions...[/dim]")
    for idx, sol in enumerate(solutions):
        critique_prompt = f"Evaluate this solution for structural risk and feasibility (1-10 scale). Reply with ONLY the integer score.\\nSolution: {sol}"
        resp = _call(BRAIN_MODEL, [{"role": "system", "content": CRITIC_SYSTEM.format(cwd=cwd)}, {"role": "user", "content": critique_prompt}], max_tokens=10)
        try:
            score = int(re.search(r'\d+', resp["message"].get("content", "0")).group())
        except:
            score = 0
        if score > best_score:
            best_score = score
            best_solution = sol
            
    console.print(f"[bold green]Best solution selected (Score: {best_score})[/bold green]")
    return f"[MOMENTUM ENGINE RECOVERY PLAN]\\n{best_solution}"'''

content = content.replace(old_qwen, new_agent_step)

# 3. Replace memory load and compression bugs
content = re.sub(r'sys_msg = \{"role": "system", "content": AGENT_SYSTEM\.format\(cwd=cwd\)\}', 
                 r'sys_msg = {"role": "system", "content": f"Compression Context in {cwd}"}', content)

old_mem_load = r'''    if not DB_PATH.exists():
        return
        
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute("SELECT key, value FROM memory WHERE key IN ({seq})".format(
            seq=','.join(['?']*len(CORE_MEMORY_KEYS))), list(CORE_MEMORY_KEYS))
        core_rows = c.fetchall()
        core = {k: v for k, v in core_rows}

        injected_parts = []
        if core:
            injected_parts.append("[CORE LAWS]\n" + json.dumps(core, indent=2))

        c.execute("SELECT key, value, embedding FROM memory WHERE key NOT IN ({seq})".format(
            seq=','.join(['?']*len(CORE_MEMORY_KEYS))), list(CORE_MEMORY_KEYS))
        dynamic_rows = c.fetchall()
        
        if dynamic_rows:
            try:
                q_emb = ollama.embeddings(model="nomic-embed-text", prompt=query)["embedding"]
                scored = []
                for k, v, emb_str in dynamic_rows:
                    if not emb_str or emb_str == "[]":
                        continue
                    try:
                        v_emb = json.loads(emb_str)
                        mag1 = math.sqrt(sum(a*a for a in q_emb))
                        mag2 = math.sqrt(sum(b*b for b in v_emb))
                        sim = sum(a*b for a, b in zip(q_emb, v_emb)) / (mag1 * mag2) if mag1 and mag2 else 0
                        scored.append((sim, k, v))
                    except Exception:
                        pass
                scored.sort(reverse=True, key=lambda x: x[0])
                top3 = {k: v for _, k, v in scored[:3]}
                if top3:
                    injected_parts.append("[RELEVANT MEMORIES]\n" + json.dumps(top3, indent=2))
            except Exception:
                # nomic-embed-text not available — fall back to loading all dynamic facts
                dynamic = {k: v for k, v, _ in dynamic_rows}
                if dynamic:
                    injected_parts.append("[MEMORY]\n" + json.dumps(dynamic, indent=2))
        
        conn.close()
        
        if injected_parts:
            messages.append({"role": "system", "content": "\n\n".join(injected_parts)})
    except Exception as e:
        logging.warning(f"Memory load error: {e}")'''

new_mem_load = '''    try:
        injected_parts = []
        core = {}
        for key in CORE_MEMORY_KEYS:
            res = chroma_collection.get(ids=[key])
            if res and res["documents"] and res["documents"][0]:
                core[key] = res["documents"][0]
                
        if core:
            injected_parts.append("[CORE LAWS]\\n" + json.dumps(core, indent=2))

        results = chroma_collection.query(query_texts=[query], n_results=3)
        if results and results['documents'] and results['documents'][0]:
            top_memories = {idx: doc for idx, doc in zip(results['ids'][0], results['documents'][0]) if idx not in CORE_MEMORY_KEYS}
            if top_memories:
                injected_parts.append("[RELEVANT MEMORIES]\\n" + json.dumps(top_memories, indent=2))
                
        if injected_parts:
            messages.append({"role": "system", "content": "\\n\\n".join(injected_parts)})
    except Exception as e:
        logging.warning(f"Memory load error: {e}")'''

content = content.replace(old_mem_load, new_mem_load)

# 4. Replace Boot aesthetic laws
old_boot = r'''    # Boot aesthetic and architecture memory laws
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    injected = False
    
    c.execute("SELECT key FROM memory WHERE key='UX_LAWS'")
    if not c.fetchone():
        val = "Always use modern aesthetics. Use glassmorphism (backdrop-blur). Avoid pure black/white; use slate/zinc scales. Use subtle micro-animations (transition-all duration-300). Prioritize whitespace, rounded-2xl corners, and elegant typography."
        try:
            emb = json.dumps(ollama.embeddings(model="nomic-embed-text", prompt=val)["embedding"])
        except:
            emb = "[]"
        c.execute("INSERT INTO memory (key, namespace, value, embedding) VALUES (?, ?, ?, ?)", 
                 ('UX_LAWS', 'global', val, emb))
        injected = True
        
    c.execute("SELECT key FROM memory WHERE key='ARCHITECTURE_LAWS'")
    if not c.fetchone():
        val = "Always structure code professionally. Use MVC patterns or strict component separation. Never dump all logic into a single file. Export/Import modules. Write modular, object-oriented or functional code. No global variable spaghetti."
        try:
            emb = json.dumps(ollama.embeddings(model="nomic-embed-text", prompt=val)["embedding"])
        except:
            emb = "[]"
        c.execute("INSERT INTO memory (key, namespace, value, embedding) VALUES (?, ?, ?, ?)", 
                 ('ARCHITECTURE_LAWS', 'global', val, emb))
        injected = True
        
    if injected:
        conn.commit()
        console.print("[dim italic]\\[Injected strict UX and Architecture Laws into memory][/dim italic]")
        
    conn.close()'''

new_boot = '''    # Boot aesthetic and architecture memory laws
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
        console.print("[dim italic]\\\\[Injected strict UX and Architecture Laws into memory][/dim italic]")'''

content = content.replace(old_boot, new_boot)


# 5. Replace chat_loop core
old_chat_loop = r'''        # ── Step 1: cheap gate — does this need tools at all? ──
        with console.status("[dim]Gate is analyzing intent...[/dim]", spinner="dots"):
            tool_turn = needs_tool(messages)
            
        gate_status = "[bold yellow]TOOL[/bold yellow]" if tool_turn else "[bold blue]CHAT[/bold blue]"
        console.print(f"[dim]\\[Gate: {gate_status}][/dim]")

        # ── Step 2: qwen agentic loop ──
        # qwen owns ALL tool call formatting. We just feed results back.
        tool_loops = 0
        executed_tool_signatures = set()
        try:
            while tool_loops < MAX_TOOL_LOOPS:
                with console.status(f"[bold green]Jimmy is thinking...[/bold green] [dim](Loop {tool_loops+1}/{MAX_TOOL_LOOPS})[/dim]", spinner="bouncingBar"):
                    msg = qwen_step(messages, cwd, with_tools=tool_turn)

                # ── Has qwen decided to call a tool? ──
                raw_tool_calls = msg.get("tool_calls") or []

                # Rescue leaked JSON if native tool_calls is empty
                if not raw_tool_calls and msg.get("content"):
                    rescued = rescue_tool_calls(msg["content"])
                    if rescued:
                        console.print(f"[bold yellow]\\[Rescued {len(rescued)} leaked tool call(s)][/bold yellow]")
                        raw_tool_calls = [
                            {"function": {"name": t["name"], "arguments": t["arguments"]}}
                            for t in rescued
                        ]
                        # Strip the JSON from the displayed content
                        msg["content"] = re.sub(
                            r"```(?:json|bash|sh|text)?\s*\{[\s\S]*?\}\s*```", "", msg["content"]
                        ).strip()

                if raw_tool_calls:
                    # Append qwen's assistant turn (may have partial narration)
                    messages.append({
                        "role": "assistant",
                        "content": msg.get("content") or "",
                        "tool_calls": raw_tool_calls,
                    })

                    # Execute each tool and append results
                    for tc in raw_tool_calls:
                        fn   = tc["function"]
                        name = fn["name"]
                        args = fn.get("arguments") or {}

                        sig = (name, json.dumps(args, sort_keys=True))
                        
                        if sig in executed_tool_signatures:
                            console.print(f"[bold red]\\[Loop Intercepted][/bold red] Blocked duplicate call to {name}")
                            result = "[SYSTEM INTERCEPT] You are stuck in a loop. You just executed this exact tool call and it failed or didn't advance the task. Stop and rethink your approach, or ask the user for help. DO NOT repeat this call."
                        elif name not in AVAILABLE_TOOLS:
                            result = f"[ERROR] Unknown tool: {name}"
                            executed_tool_signatures.add(sig)
                        else:
                            executed_tool_signatures.add(sig)
                            console.print(f"[bold yellow]\\[→ {name}({', '.join(f'{k}={str(v)[:40]}' for k,v in args.items())})][/bold yellow]")
                            log_event("tool_dispatch", {"tool": name, "args": args})
                            result = AVAILABLE_TOOLS[name](**args)
                            log_event("tool_result", {"tool": name, "result": result[:200]})

                        messages.append({
                            "role": "tool",
                            "content": result,
                            "name": name,
                        })

                    tool_loops += 1
                    # Loop — qwen will now see results and decide next action
                    continue

                else:
                    # No tool call — qwen is done, print final response
                    final = (msg.get("content") or "").strip()
                    if final:
                        messages.append({"role": "assistant", "content": final})
                        log_event("assistant", {"content": final})
                        console.print("\n[bold magenta]Jimmy:[/bold magenta]")
                        console.print(Markdown(final))
                        console.print()
                    else:
                        console.print("[dim italic]\\[Jimmy returned an empty response — try rephrasing][/dim italic]\n")
                    break

        except Exception as e:
            console.print(f"\n[bold red]\\[Error: {e}][/bold red]\n")
            log_event("error", {"msg": str(e)})

        if tool_loops >= MAX_TOOL_LOOPS:
            console.print(f"[bold red]\\[⚠ Tool loop limit ({MAX_TOOL_LOOPS}) hit][/bold red]\n")'''

new_chat_loop = '''        # ── Step 1: The Architect (Plan Generation) ──
        with console.status("[bold cyan]The Architect is planning...[/bold cyan]", spinner="dots"):
            architect_msg = agent_step(ARCHITECT_SYSTEM, messages, cwd, with_tools=False)
            plan = (architect_msg.get("content") or "").strip()
            
        console.print(Panel(Markdown(plan), title="[bold cyan]Architect Plan[/bold cyan]", border_style="cyan"))
        messages.append({"role": "assistant", "content": f"[ARCHITECT PLAN]\\n{plan}"})

        # ── Step 2: The Executor (Tool Execution) ──
        tool_loops = 0
        executed_tool_signatures = set()
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
                        console.print(f"[bold yellow]\\\\[Rescued {len(rescued)} leaked tool call(s)][/bold yellow]")
                        raw_tool_calls = [{"function": {"name": t["name"], "arguments": t["arguments"]}} for t in rescued]
                        msg["content"] = re.sub(r"```(?:json|bash|sh|text)?\s*\\{[\\s\\S]*?\\}\\s*```", "", msg["content"]).strip()

                if raw_tool_calls:
                    messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": raw_tool_calls})

                    for tc in raw_tool_calls:
                        fn = tc["function"]
                        name = fn["name"]
                        args = fn.get("arguments") or {}
                        sig = (name, json.dumps(args, sort_keys=True))
                        
                        if sig in executed_tool_signatures:
                            console.print(f"[bold red]\\\\[Loop Intercepted][/bold red] Blocked duplicate call to {name}")
                            result = "[SYSTEM INTERCEPT] You are stuck in a loop. Stop and rethink your approach."
                        elif name not in AVAILABLE_TOOLS:
                            result = f"[ERROR] Unknown tool: {name}"
                            executed_tool_signatures.add(sig)
                        else:
                            executed_tool_signatures.add(sig)
                            console.print(f"[bold yellow]\\\\[→ {name}({', '.join(f'{k}={str(v)[:40]}' for k,v in args.items())})][/bold yellow]")
                            log_event("tool_dispatch", {"tool": name, "args": args})
                            result = AVAILABLE_TOOLS[name](**args)
                            log_event("tool_result", {"tool": name, "result": result[:200]})
                            
                            # MOMENTUM ENGINE INTERCEPT
                            if "[MOMENTUM_TRIGGER]" in result:
                                error_text = result.split("[MOMENTUM_TRIGGER]")[1].strip()
                                recovery_plan = momentum_engine(error_text, cwd, messages)
                                result = result + "\\n\\n" + recovery_plan

                        messages.append({"role": "tool", "content": result, "name": name})

                    tool_loops += 1
                    continue
                else:
                    final_executor_msg = (msg.get("content") or "").strip()
                    executor_done = True
                    if final_executor_msg:
                        messages.append({"role": "assistant", "content": final_executor_msg})
                        console.print("\\n[bold green]Executor:[/bold green]")
                        console.print(Markdown(final_executor_msg))
                    
            if tool_loops >= MAX_TOOL_LOOPS:
                console.print(f"[bold red]\\\\[⚠ Executor tool loop limit ({MAX_TOOL_LOOPS}) hit][/bold red]\\n")

            # ── Step 3: The Critic (Evaluation) ──
            if executor_done or tool_loops > 0:
                with console.status("[bold magenta]The Critic is evaluating...[/bold magenta]", spinner="dots"):
                    critic_msg = agent_step(CRITIC_SYSTEM, messages, cwd, with_tools=False)
                    critique = (critic_msg.get("content") or "").strip()
                
                console.print(Panel(Markdown(critique), title="[bold magenta]Critic Evaluation[/bold magenta]", border_style="magenta"))
                messages.append({"role": "assistant", "content": f"[CRITIC EVALUATION]\\n{critique}"})
                
                if "REJECTED" in critique.upper():
                    console.print("[bold red]Critic REJECTED the outcome. Please ask the user for further instructions or automatically retry.[/bold red]")

        except Exception as e:
            console.print(f"\\n[bold red]\\\\[Error: {e}][/bold red]\\n")
            log_event("error", {"msg": str(e)})'''

content = content.replace(old_chat_loop, new_chat_loop)

# Fix missing import if needed (chromadb already added)
Path("/home/sfiso/ai-agent/jimmy.py").write_text(content)
print("Patch applied successfully.")
