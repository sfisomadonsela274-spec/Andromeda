#!/usr/bin/env python3
"""
=============================================================================
             🌌 ANDROMEDA MACRO RUNNER: WORKFLOW ORCHESTRATION 🌌
=============================================================================
Executes multi-step, multi-app workflows defined in macros.yaml:
  - Intertwines shell commands, App Controller actions, Media Controller calls,
    and daemon background tasks.
  - Formats dynamic parameter interpolations across sequential steps.
  - Automatically intercepts any step failure or exception and emits
    [MOMENTUM_TRIGGER] for autonomous recovery loops.
=============================================================================
"""

import os
import sys
import json
import yaml
import logging
import argparse
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Union

# Integration imports
from app_controller import execute_app_action
from media_controller import media_ctrl

logger = logging.getLogger("macro_runner")
MACROS_FILE = Path(__file__).parent / "macros.yaml"


class MacroRunner:
    """Orchestrates multi-step sequential automation workflows from YAML configs."""

    def __init__(self, config_path: Path = MACROS_FILE):
        self.config_path = Path(config_path)
        self.macros = self._load_macros()

    def _load_macros(self) -> Dict[str, Any]:
        """Loads and parses macro definitions from YAML config file."""
        if not self.config_path.exists():
            logger.warning(f"Macro config not found at: {self.config_path}")
            return {}
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                return data.get("macros", {})
        except Exception as e:
            logger.error(f"Failed to parse {self.config_path}: {e}")
            return {}

    def list_macros(self) -> Dict[str, str]:
        """Returns mapping of macro names to their descriptions."""
        self.macros = self._load_macros()
        return {k: v.get("description", "") for k, v in self.macros.items()}

    def get_macro(self, macro_name: str) -> Optional[Dict[str, Any]]:
        """Returns raw specification for target macro."""
        self.macros = self._load_macros()
        return self.macros.get(macro_name)

    @staticmethod
    def _interpolate(val: Any, inputs: Dict[str, Any]) -> Any:
        """Recursively formats string templates with input parameters."""
        if isinstance(val, str):
            try:
                return val.format(**inputs)
            except KeyError as e:
                logger.warning(f"Missing parameter during interpolation: {e}")
                return val
        elif isinstance(val, dict):
            return {k: MacroRunner._interpolate(v, inputs) for k, v in val.items()}
        elif isinstance(val, list):
            return [MacroRunner._interpolate(x, inputs) for x in val]
        return val

    def run(self, macro_name: str, overrides: Optional[Union[Dict[str, Any], str]] = None) -> str:
        """
        Executes a defined workflow macro step-by-step.
        Returns full execution trace. On any failure, emits [MOMENTUM_TRIGGER].
        """
        # Reload macros to reflect any on-disk edits
        self.macros = self._load_macros()

        if macro_name not in self.macros:
            avail = ", ".join(f"'{m}'" for m in self.macros.keys())
            return (
                f"[ERROR] [MOMENTUM_TRIGGER] Macro '{macro_name}' not found. "
                f"Available macros: [{avail}]"
            )

        # Parse overrides if passed as JSON string
        if isinstance(overrides, str) and overrides.strip():
            try:
                overrides = json.loads(overrides)
            except Exception as e:
                return (
                    f"[ERROR] [MOMENTUM_TRIGGER] Failed to parse macro overrides JSON: {e}"
                )
        elif not isinstance(overrides, dict):
            overrides = {}

        macro = self.macros[macro_name]
        steps = macro.get("steps", [])

        # Build combined inputs from defaults + overrides
        inputs: Dict[str, Any] = {}
        for inp in macro.get("inputs", []):
            name = inp.get("name")
            if name:
                inputs[name] = inp.get("default", "")
        inputs.update(overrides)

        logs = [f"🚀 Starting Macro: '{macro_name}'", f"Params: {json.dumps(inputs)}"]

        for idx, step in enumerate(steps, 1):
            step_id = step.get("id", f"step_{idx}")
            step_type = (step.get("type") or "bash").lower().strip()
            logs.append(f"\n--- [Step {idx}/{len(steps)}: {step_id}] ({step_type}) ---")

            try:
                # ── TYPE 1: BASH COMMAND ──
                if step_type == "bash":
                    cmd_template = step.get("command", "")
                    cmd = self._interpolate(cmd_template, inputs)
                    logs.append(f"$ {cmd}")
                    timeout = step.get("timeout", 180)
                    res = subprocess.run(
                        cmd,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=timeout
                    )
                    if res.returncode != 0:
                        err_out = res.stderr.strip() or res.stdout.strip() or f"Process exited with code {res.returncode}"
                        err_msg = (
                            f"[MOMENTUM_TRIGGER] Macro '{macro_name}' failed at step '{step_id}' (bash):\n"
                            f"Command: {cmd}\n"
                            f"Error: {err_out}"
                        )
                        logs.append(err_msg)
                        return "\n".join(logs)
                    out_snippet = res.stdout.strip()
                    if out_snippet:
                        logs.append(f"[ok] {out_snippet[:400]}")
                    else:
                        logs.append("[ok] Command executed cleanly.")

                # ── TYPE 2: APP CONTROLLER ACTION ──
                elif step_type == "app_control":
                    app = step.get("app", "")
                    action = step.get("action", "open")
                    raw_params = step.get("params", {})
                    formatted_params = self._interpolate(raw_params, inputs)
                    mode = step.get("mode", "auto")

                    logs.append(f"App: {app} | Action: {action} | Params: {formatted_params} | Mode: {mode}")
                    res = execute_app_action(app, action, formatted_params, mode=mode)

                    if isinstance(res, str) and res.strip().startswith("[ERROR]"):
                        err_msg = (
                            f"[MOMENTUM_TRIGGER] Macro '{macro_name}' app_control failed at step '{step_id}':\n"
                            f"App: {app} | Action: {action}\n"
                            f"{res.strip()}"
                        )
                        logs.append(err_msg)
                        return "\n".join(logs)
                    logs.append(res)

                # ── TYPE 3: MEDIA CONTROLLER ACTION ──
                elif step_type in ("media_control", "media"):
                    action = step.get("action", "status")
                    params = self._interpolate(step.get("params", {}), inputs)
                    val = params.get("value") if isinstance(params, dict) else step.get("value")
                    player = params.get("player") if isinstance(params, dict) else step.get("player")

                    logs.append(f"Media Action: {action} | Value: {val} | Player: {player}")
                    res = media_ctrl.execute(action=action, value=val, player=player)

                    if isinstance(res, str) and res.strip().startswith("[ERROR]"):
                        err_msg = (
                            f"[MOMENTUM_TRIGGER] Macro '{macro_name}' media_control failed at step '{step_id}':\n"
                            f"{res.strip()}"
                        )
                        logs.append(err_msg)
                        return "\n".join(logs)
                    logs.append(f"[ok] {res}")

                # ── TYPE 4: BACKGROUND DAEMON ──
                elif step_type == "daemon":
                    cmd_template = step.get("command", "")
                    cmd = self._interpolate(cmd_template, inputs)
                    logs.append(f"Starting background daemon: {cmd}")
                    proc = subprocess.Popen(
                        cmd,
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    logs.append(f"[ok] Daemon dispatched in background (PID: {proc.pid}).")

                else:
                    err_msg = f"[MOMENTUM_TRIGGER] Unknown step type '{step_type}' at step '{step_id}'"
                    logs.append(err_msg)
                    return "\n".join(logs)

            except Exception as e:
                err_msg = (
                    f"[MOMENTUM_TRIGGER] Macro '{macro_name}' runtime exception at step '{step_id}': {str(e)}"
                )
                logs.append(err_msg)
                return "\n".join(logs)

        logs.append(f"\n✅ Macro '{macro_name}' completed successfully.")
        return "\n".join(logs)


# Singleton instance for direct import across modules
runner = MacroRunner()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Andromeda Macro Runner CLI")
    parser.add_argument("macro_name", nargs="?", default=None, help="Name of macro to execute")
    parser.add_argument("-l", "--list", action="store_true", help="List all available macros")
    parser.add_argument("-o", "--overrides", type=str, default="{}", help="JSON string of parameter overrides")
    args = parser.parse_args()

    if args.list or not args.macro_name:
        macros = runner.list_macros()
        print("Available Macros:")
        for name, desc in macros.items():
            print(f"  • {name}: {desc}")
        sys.exit(0)

    output = runner.run(args.macro_name, overrides=args.overrides)
    print(output)

    if "[MOMENTUM_TRIGGER]" in output or "[ERROR]" in output:
        sys.exit(1)
    sys.exit(0)
