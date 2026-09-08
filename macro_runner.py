#!/usr/bin/env python3
"""
macro_runner.py — Orchestrates multi-step, multi-app workflows.
Intertwines shell tasks, app controller invocations, and daemon executions.
"""

import os
import yaml
import json
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from app_controller import execute_app_action

logger = logging.getLogger("macro_runner")
MACROS_FILE = Path(__file__).parent / "macros.yaml"

class MacroRunner:
    def __init__(self, config_path: Path = MACROS_FILE):
        self.config_path = config_path
        self.macros = self._load_macros()

    def _load_macros(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            return {}
        with open(self.config_path, "r") as f:
            data = yaml.safe_load(f) or {}
            return data.get("macros", {})

    def list_macros(self) -> Dict[str, str]:
        return {k: v.get("description", "") for k, v in self.macros.items()}

    def run(self, macro_name: str, overrides: Optional[Dict[str, Any]] = None) -> str:
        # Reload macros in case configuration was modified
        self.macros = self._load_macros()
        
        if macro_name not in self.macros:
            return f"[ERROR] Macro '{macro_name}' not found. Available: {list(self.macros.keys())}"

        macro = self.macros[macro_name]
        steps = macro.get("steps", [])
        inputs = {i["name"]: i.get("default", "") for i in macro.get("inputs", [])}
        if overrides:
            inputs.update(overrides)

        logs = [f"🚀 Starting Macro: {macro_name}"]

        for idx, step in enumerate(steps, 1):
            step_id = step.get("id", f"step_{idx}")
            step_type = step.get("type")
            logs.append(f"\n--- [Step {idx}/{len(steps)}: {step_id}] ({step_type}) ---")

            try:
                if step_type == "bash":
                    cmd = step["command"].format(**inputs)
                    logs.append(f"$ {cmd}")
                    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
                    if res.returncode != 0:
                        err_msg = f"[MOMENTUM_TRIGGER] Macro failed at step '{step_id}': {res.stderr.strip()}"
                        logs.append(err_msg)
                        return "\n".join(logs)
                    logs.append(f"[ok] {res.stdout.strip()[:300]}")

                elif step_type == "app_control":
                    app = step["app"]
                    action = step["action"]
                    raw_params = step.get("params", {})
                    # Interpolate parameters
                    formatted_params = {
                        k: (v.format(**inputs) if isinstance(v, str) else v)
                        for k, v in raw_params.items()
                    }
                    mode = step.get("mode", "auto")
                    logs.append(f"App: {app} | Action: {action} | Params: {formatted_params} | Mode: {mode}")
                    res = execute_app_action(app, action, formatted_params, mode=mode)
                    logs.append(res)

                elif step_type == "daemon":
                    cmd = step["command"].format(**inputs)
                    logs.append(f"Starting background daemon: {cmd}")
                    subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    logs.append("[ok] Daemon dispatched in background.")

                else:
                    logs.append(f"[WARN] Unknown step type: {step_type}")

            except Exception as e:
                err_msg = f"[MOMENTUM_TRIGGER] Macro runtime exception at step '{step_id}': {str(e)}"
                logs.append(err_msg)
                return "\n".join(logs)

        logs.append(f"\n✅ Macro '{macro_name}' completed successfully.")
        return "\n".join(logs)

runner = MacroRunner()

if __name__ == "__main__":
    print("Available macros:", runner.list_macros())
