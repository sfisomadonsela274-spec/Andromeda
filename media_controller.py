#!/usr/bin/env python3
"""
media_controller.py — Unified MPRIS D-Bus media controller via playerctl.
Controls desktop audio/video players (Spotify, Firefox, Chrome, VLC, Rhythmbox).
"""

import os
import shutil
import subprocess
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("media_controller")

class DesktopMediaController:
    """Interfaces with Linux MPRIS via playerctl."""

    @staticmethod
    def _run_cmd(args: list[str]) -> tuple[int, str, str]:
        cmd_name = shutil.which("playerctl") or "/home/sfiso/.local/bin/playerctl"
        cmd = [cmd_name] + args
        env = os.environ.copy()
        if "/home/sfiso/.local/lib/x86_64-linux-gnu" not in env.get("LD_LIBRARY_PATH", ""):
            env["LD_LIBRARY_PATH"] = f"/home/sfiso/.local/lib/x86_64-linux-gnu:{env.get('LD_LIBRARY_PATH', '')}".strip(":")
        if "/home/sfiso/.local/bin" not in env.get("PATH", ""):
            env["PATH"] = f"/home/sfiso/.local/bin:{env.get('PATH', '')}"
            
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5, env=env)
            return res.returncode, res.stdout.strip(), res.stderr.strip()
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out"
        except FileNotFoundError:
            return -1, "", "playerctl is not installed on host"

    def get_status(self) -> Dict[str, Any]:
        """Returns metadata and status across active desktop players."""
        code, players_raw, _ = self._run_cmd(["-l"])
        if code != 0 or not players_raw:
            return {
                "active": False,
                "playback_status": "Stopped",
                "message": "No active MPRIS media players detected."
            }

        players = [p for p in players_raw.split("\n") if p]
        
        # Query active player metadata as JSON
        fmt = '{"player":"{{playerName}}","status":"{{status}}","title":"{{markup_escape(title)}}","artist":"{{markup_escape(artist)}}","album":"{{markup_escape(album)}}","volume":{{volume}}}'
        code, meta_raw, _ = self._run_cmd(["metadata", "--format", fmt])

        if code == 0 and meta_raw:
            try:
                # Handle possible multiline output if multiple players are active
                first_line = meta_raw.split("\n")[0]
                data = json.loads(first_line)
                data["active"] = True
                data["available_players"] = players
                return data
            except json.JSONDecodeError:
                pass

        return {
            "active": True,
            "playback_status": "Unknown",
            "available_players": players
        }

    def execute(self, action: str, value: Optional[float] = None, player: Optional[str] = None) -> str:
        """Executes a playback or volume action."""
        prefix = ["-p", player] if player else []
        
        action = action.lower().strip()
        if action in ("play", "pause", "play_pause", "toggle"):
            code, out, err = self._run_cmd(prefix + ["play-pause"])
        elif action in ("next", "skip"):
            code, out, err = self._run_cmd(prefix + ["next"])
        elif action in ("prev", "previous"):
            code, out, err = self._run_cmd(prefix + ["previous"])
        elif action == "stop":
            code, out, err = self._run_cmd(prefix + ["stop"])
        elif action == "volume_up":
            step = value if value is not None else 0.05
            code, out, err = self._run_cmd(prefix + ["volume", f"{step}+"])
        elif action == "volume_down":
            step = value if value is not None else 0.05
            code, out, err = self._run_cmd(prefix + ["volume", f"{step}-"])
        elif action == "set_volume":
            if value is None or not (0.0 <= value <= 1.0):
                return "[ERROR] 'set_volume' requires a float value between 0.0 and 1.0"
            code, out, err = self._run_cmd(prefix + ["volume", str(value)])
        elif action == "status":
            return json.dumps(self.get_status(), indent=2)
        else:
            return f"[ERROR] Unsupported media action: '{action}'"

        if code != 0:
            return f"[ERROR] Action '{action}' failed: {err or 'No active player responded'}"
        return f"[ok] Media action '{action}' executed successfully."

media_ctrl = DesktopMediaController()

if __name__ == "__main__":
    import sys
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    print(media_ctrl.execute(action))
