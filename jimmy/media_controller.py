#!/usr/bin/env python3
"""
=============================================================================
             🌌 ANDROMEDA MEDIA CONTROLLER: LINUX MPRIS INTERFACE 🌌
=============================================================================
Exposes DesktopMediaController communicating with Linux MPRIS via playerctl:
  - Playback Control: play, pause, play_pause / toggle, next, previous, stop
  - Volume Control: set_volume (0.0 - 1.0), volume_up, volume_down, get_volume
  - Metadata & Status: active status, title, artist, album, duration, position
  - Player Querying: multi-player detection across Spotify, VLC, browsers, etc.
=============================================================================
"""

import os
import sys
import json
import shutil
import logging
import subprocess
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger("media_controller")

# Predefined search paths for playerctl binary
PLAYERCTL_CANDIDATE_PATHS = [
    shutil.which("playerctl"),
    "/home/sfiso/.gemini/antigravity-ide/bin/playerctl",
    "/home/sfiso/.local/bin/playerctl",
    "/usr/bin/playerctl",
    "/usr/local/bin/playerctl",
]


class DesktopMediaController:
    """Interfaces with Linux MPRIS D-Bus media players via playerctl."""

    def __init__(self, binary_path: Optional[str] = None):
        self._binary_path = binary_path or self._resolve_binary()

    @staticmethod
    def _resolve_binary() -> str:
        """Resolves the best available path to playerctl."""
        for path in PLAYERCTL_CANDIDATE_PATHS:
            if path and os.path.isfile(path) and os.access(path, os.X_OK):
                return path
        # Fallback to system name
        return "playerctl"

    def _build_env(self) -> Dict[str, str]:
        """Prepares the host environment with required library and bin paths."""
        env = os.environ.copy()
        extra_paths = ["/home/sfiso/.gemini/antigravity-ide/bin", "/home/sfiso/.local/bin"]
        current_path = env.get("PATH", "")
        for p in extra_paths:
            if p not in current_path:
                current_path = f"{p}:{current_path}"
        env["PATH"] = current_path.strip(":")

        extra_libs = ["/home/sfiso/.local/lib/x86_64-linux-gnu"]
        current_lib = env.get("LD_LIBRARY_PATH", "")
        for lib in extra_libs:
            if lib not in current_lib and os.path.exists(lib):
                current_lib = f"{lib}:{current_lib}"
        if current_lib:
            env["LD_LIBRARY_PATH"] = current_lib.strip(":")

        return env

    def _run_cmd(self, args: List[str]) -> Tuple[int, str, str]:
        """Executes playerctl with isolated command args and error interception."""
        cmd = [self._binary_path] + args
        env = self._build_env()

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5, env=env)
            return res.returncode, res.stdout.strip(), res.stderr.strip()
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out after 5 seconds"
        except FileNotFoundError:
            return -1, "", f"playerctl binary not found at '{self._binary_path}'"
        except Exception as e:
            return -1, "", str(e)

    def list_players(self) -> List[str]:
        """Returns a list of all active MPRIS media player identifiers."""
        code, out, _ = self._run_cmd(["-l"])
        if code != 0 or not out:
            return []
        return [p.strip() for p in out.split("\n") if p.strip()]

    def is_active(self) -> bool:
        """Returns True if at least one MPRIS player is detected."""
        return len(self.list_players()) > 0

    def get_status(self, player: Optional[str] = None) -> Dict[str, Any]:
        """
        Queries playback status and rich track metadata across active players.
        Returns a structured dictionary representation.
        """
        players = self.list_players()
        if not players:
            return {
                "active": False,
                "playback_status": "Stopped",
                "player": None,
                "title": "",
                "artist": "",
                "album": "",
                "volume": 0.0,
                "available_players": [],
                "message": "No active MPRIS media players detected."
            }

        prefix = ["-p", player] if player else []

        # Request structured JSON format from playerctl metadata
        fmt = (
            '{"player":"{{playerName}}","status":"{{status}}",'
            '"title":"{{markup_escape(title)}}","artist":"{{markup_escape(artist)}}",'
            '"album":"{{markup_escape(album)}}","volume":{{volume}},'
            '"position":{{position}},"length":{{mpris:length}}}'
        )

        code, meta_raw, _ = self._run_cmd(prefix + ["metadata", "--format", fmt])
        if code == 0 and meta_raw:
            try:
                first_line = meta_raw.split("\n")[0]
                data = json.loads(first_line)
                data["active"] = True
                data["available_players"] = players
                if "volume" in data and isinstance(data["volume"], (int, float)):
                    data["volume"] = round(float(data["volume"]), 2)
                return data
            except (json.JSONDecodeError, ValueError):
                pass

        # Fallback to simple status query if rich metadata is not fully populated
        code_status, status_out, _ = self._run_cmd(prefix + ["status"])
        playback_status = status_out if code_status == 0 and status_out else "Unknown"

        return {
            "active": True,
            "playback_status": playback_status,
            "player": player or (players[0] if players else None),
            "title": "",
            "artist": "",
            "album": "",
            "volume": 0.0,
            "available_players": players
        }

    def get_metadata(self, player: Optional[str] = None) -> Dict[str, Any]:
        """Alias for get_status returning comprehensive track metadata."""
        return self.get_status(player=player)

    def play(self, player: Optional[str] = None) -> str:
        """Starts playback on the target or default media player."""
        prefix = ["-p", player] if player else []
        code, _, err = self._run_cmd(prefix + ["play"])
        if code != 0:
            return f"[ERROR] Failed to start playback: {err or 'No active player responded'}"
        return "[ok] Playback started."

    def pause(self, player: Optional[str] = None) -> str:
        """Pauses playback on the target or default media player."""
        prefix = ["-p", player] if player else []
        code, _, err = self._run_cmd(prefix + ["pause"])
        if code != 0:
            return f"[ERROR] Failed to pause playback: {err or 'No active player responded'}"
        return "[ok] Playback paused."

    def play_pause(self, player: Optional[str] = None) -> str:
        """Toggles play/pause on the target or default media player."""
        prefix = ["-p", player] if player else []
        code, _, err = self._run_cmd(prefix + ["play-pause"])
        if code != 0:
            return f"[ERROR] Failed to toggle play/pause: {err or 'No active player responded'}"
        return "[ok] Play/pause toggled."

    def next_track(self, player: Optional[str] = None) -> str:
        """Skips to the next track."""
        prefix = ["-p", player] if player else []
        code, _, err = self._run_cmd(prefix + ["next"])
        if code != 0:
            return f"[ERROR] Failed to skip to next track: {err or 'No active player responded'}"
        return "[ok] Skipped to next track."

    def previous_track(self, player: Optional[str] = None) -> str:
        """Returns to the previous track."""
        prefix = ["-p", player] if player else []
        code, _, err = self._run_cmd(prefix + ["previous"])
        if code != 0:
            return f"[ERROR] Failed to return to previous track: {err or 'No active player responded'}"
        return "[ok] Returned to previous track."

    def stop(self, player: Optional[str] = None) -> str:
        """Stops playback."""
        prefix = ["-p", player] if player else []
        code, _, err = self._run_cmd(prefix + ["stop"])
        if code != 0:
            return f"[ERROR] Failed to stop playback: {err or 'No active player responded'}"
        return "[ok] Playback stopped."

    def set_volume(self, value: float, player: Optional[str] = None) -> str:
        """
        Sets the player volume level.
        Accepts float in range 0.0 to 1.0 (or percentage 0 to 100).
        """
        try:
            val = float(value)
        except (ValueError, TypeError):
            return f"[ERROR] 'set_volume' requires a numeric value, got: '{value}'"

        # Normalize percentage (e.g., 75 -> 0.75) if > 1.0
        if val > 1.0:
            val = val / 100.0

        val = max(0.0, min(1.0, val))
        prefix = ["-p", player] if player else []
        code, _, err = self._run_cmd(prefix + ["volume", f"{val:.2f}"])
        if code != 0:
            return f"[ERROR] Failed to set volume: {err or 'No active player responded'}"
        return f"[ok] Volume set to {int(val * 100)}% ({val:.2f})."

    def volume_up(self, step: float = 0.05, player: Optional[str] = None) -> str:
        """Increments volume by step (default: 0.05 / 5%)."""
        try:
            step_val = float(step)
            if step_val > 1.0:
                step_val = step_val / 100.0
        except (ValueError, TypeError):
            step_val = 0.05

        prefix = ["-p", player] if player else []
        code, _, err = self._run_cmd(prefix + ["volume", f"{step_val:.2f}+"])
        if code != 0:
            return f"[ERROR] Failed to increase volume: {err or 'No active player responded'}"
        return f"[ok] Volume increased by +{int(step_val * 100)}%."

    def volume_down(self, step: float = 0.05, player: Optional[str] = None) -> str:
        """Decrements volume by step (default: 0.05 / 5%)."""
        try:
            step_val = float(step)
            if step_val > 1.0:
                step_val = step_val / 100.0
        except (ValueError, TypeError):
            step_val = 0.05

        prefix = ["-p", player] if player else []
        code, _, err = self._run_cmd(prefix + ["volume", f"{step_val:.2f}-"])
        if code != 0:
            return f"[ERROR] Failed to decrease volume: {err or 'No active player responded'}"
        return f"[ok] Volume decreased by -{int(step_val * 100)}%."

    def execute(self, action: str, value: Optional[float] = None, player: Optional[str] = None) -> str:
        """
        Unified action dispatcher for tool invocations and CLI commands.
        Maintains full compatibility with Jimmy and Andromeda tool calling.
        """
        action_clean = (action or "").lower().strip()

        if action_clean in ("play_pause", "toggle"):
            return self.play_pause(player=player)
        elif action_clean == "play":
            return self.play(player=player)
        elif action_clean == "pause":
            return self.pause(player=player)
        elif action_clean in ("next", "skip"):
            return self.next_track(player=player)
        elif action_clean in ("prev", "previous"):
            return self.previous_track(player=player)
        elif action_clean == "stop":
            return self.stop(player=player)
        elif action_clean == "volume_up":
            step = value if value is not None else 0.05
            return self.volume_up(step=step, player=player)
        elif action_clean == "volume_down":
            step = value if value is not None else 0.05
            return self.volume_down(step=step, player=player)
        elif action_clean in ("set_volume", "volume"):
            if value is None:
                return "[ERROR] 'set_volume' requires a numeric value between 0.0 and 1.0"
            return self.set_volume(value=value, player=player)
        elif action_clean in ("status", "info", "get_status"):
            return json.dumps(self.get_status(player=player), indent=2)
        elif action_clean in ("metadata", "get_metadata"):
            return json.dumps(self.get_metadata(player=player), indent=2)
        elif action_clean in ("list", "players", "list_players"):
            players = self.list_players()
            if not players:
                return "No active MPRIS media players found."
            return f"Active MPRIS players ({len(players)}):\n" + "\n".join(f"  • {p}" for p in players)
        else:
            return f"[ERROR] Unsupported media action: '{action}'. Supported: play_pause, play, pause, next, previous, stop, volume_up, volume_down, set_volume, status, metadata, list."


# Singleton instance for direct import across modules
media_ctrl = DesktopMediaController()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="DesktopMediaController MPRIS playerctl CLI")
    parser.add_argument("action", nargs="?", default="status", help="Media action to perform")
    parser.add_argument("value", nargs="?", type=float, default=None, help="Optional numeric value (volume)")
    parser.add_argument("-p", "--player", default=None, help="Target player identifier")
    args = parser.parse_args()

    result = media_ctrl.execute(action=args.action, value=args.value, player=args.player)
    print(result)
