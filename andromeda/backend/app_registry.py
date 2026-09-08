"""
App Registry for Jimmy and Andromeda
Defines Top 10 applications across 6 categories:
1. Social Media
2. Streaming Sites
3. IDEs
4. CAD Systems
5. Graphic Systems
6. Music Apps & Websites
"""

import urllib.parse
from typing import Dict, Any, List, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Categories & App Definitions
# ─────────────────────────────────────────────────────────────────────────────

APP_REGISTRY: Dict[str, Dict[str, Any]] = {
    # =========================================================================
    # 1. SOCIAL MEDIA
    # =========================================================================
    "twitter": {
        "id": "twitter",
        "name": "X / Twitter",
        "category": "social",
        "aliases": ["twitter", "x", "tweet", "x.com"],
        "desktop_binaries": [],
        "flatpak_id": None,
        "web_base": "https://x.com",
        "actions": {
            "open": lambda p: "https://x.com",
            "search": lambda p: f"https://x.com/search?q={urllib.parse.quote(p.get('query', ''))}",
            "user": lambda p: f"https://x.com/{p.get('user', '').lstrip('@')}",
            "compose": lambda p: f"https://x.com/intent/tweet?text={urllib.parse.quote(p.get('text', ''))}",
            "hashtag": lambda p: f"https://x.com/hashtag/{p.get('tag', '').lstrip('#')}",
        }
    },
    "reddit": {
        "id": "reddit",
        "name": "Reddit",
        "category": "social",
        "aliases": ["reddit", "r/"],
        "desktop_binaries": [],
        "flatpak_id": None,
        "web_base": "https://www.reddit.com",
        "actions": {
            "open": lambda p: "https://www.reddit.com",
            "search": lambda p: f"https://www.reddit.com/search/?q={urllib.parse.quote(p.get('query', ''))}",
            "subreddit": lambda p: f"https://www.reddit.com/r/{p.get('subreddit', '').replace('r/', '')}",
            "user": lambda p: f"https://www.reddit.com/user/{p.get('user', '').replace('u/', '')}",
        }
    },
    "linkedin": {
        "id": "linkedin",
        "name": "LinkedIn",
        "category": "social",
        "aliases": ["linkedin", "in"],
        "desktop_binaries": [],
        "flatpak_id": None,
        "web_base": "https://www.linkedin.com",
        "actions": {
            "open": lambda p: "https://www.linkedin.com/feed/",
            "search": lambda p: f"https://www.linkedin.com/search/results/all/?keywords={urllib.parse.quote(p.get('query', ''))}",
            "jobs": lambda p: f"https://www.linkedin.com/jobs/search/?keywords={urllib.parse.quote(p.get('query', ''))}",
            "user": lambda p: f"https://www.linkedin.com/in/{p.get('user', '')}",
        }
    },
    "instagram": {
        "id": "instagram",
        "name": "Instagram",
        "category": "social",
        "aliases": ["instagram", "ig", "insta"],
        "desktop_binaries": [],
        "flatpak_id": None,
        "web_base": "https://www.instagram.com",
        "actions": {
            "open": lambda p: "https://www.instagram.com",
            "user": lambda p: f"https://www.instagram.com/{p.get('user', '').lstrip('@')}/",
            "explore": lambda p: "https://www.instagram.com/explore/",
            "direct": lambda p: "https://www.instagram.com/direct/inbox/",
        }
    },
    "tiktok": {
        "id": "tiktok",
        "name": "TikTok",
        "category": "social",
        "aliases": ["tiktok", "tt"],
        "desktop_binaries": [],
        "flatpak_id": None,
        "web_base": "https://www.tiktok.com",
        "actions": {
            "open": lambda p: "https://www.tiktok.com",
            "search": lambda p: f"https://www.tiktok.com/search?q={urllib.parse.quote(p.get('query', ''))}",
            "user": lambda p: f"https://www.tiktok.com/@{p.get('user', '').lstrip('@')}",
            "tag": lambda p: f"https://www.tiktok.com/tag/{p.get('tag', '').lstrip('#')}",
        }
    },
    "discord": {
        "id": "discord",
        "name": "Discord",
        "category": "social",
        "aliases": ["discord"],
        "desktop_binaries": ["discord", "Discord"],
        "flatpak_id": "com.discordapp.Discord",
        "web_base": "https://discord.com/app",
        "actions": {
            "open": lambda p: "https://discord.com/app",
            "channel": lambda p: f"https://discord.com/channels/{p.get('guild_id', '')}/{p.get('channel_id', '')}",
        }
    },
    "slack": {
        "id": "slack",
        "name": "Slack",
        "category": "social",
        "aliases": ["slack"],
        "desktop_binaries": ["slack"],
        "flatpak_id": "com.slack.Slack",
        "web_base": "https://app.slack.com",
        "actions": {
            "open": lambda p: p.get("url") or "https://app.slack.com",
            "search": lambda p: f"https://app.slack.com/client/search?query={urllib.parse.quote(p.get('query', ''))}",
        }
    },
    "telegram": {
        "id": "telegram",
        "name": "Telegram",
        "category": "social",
        "aliases": ["telegram", "tg"],
        "desktop_binaries": ["telegram-desktop", "Telegram"],
        "flatpak_id": "org.telegram.desktop",
        "web_base": "https://web.telegram.org",
        "actions": {
            "open": lambda p: "https://web.telegram.org",
            "user": lambda p: f"https://t.me/{p.get('user', '').lstrip('@')}",
            "join": lambda p: f"https://t.me/{p.get('channel', '').lstrip('@')}",
        }
    },
    "whatsapp": {
        "id": "whatsapp",
        "name": "WhatsApp",
        "category": "social",
        "aliases": ["whatsapp", "wa"],
        "desktop_binaries": ["whatsapp-for-linux"],
        "flatpak_id": "com.github.eneshecan.WhatsAppForLinux",
        "web_base": "https://web.whatsapp.com",
        "actions": {
            "open": lambda p: "https://web.whatsapp.com",
            "chat": lambda p: f"https://wa.me/{p.get('phone', '')}?text={urllib.parse.quote(p.get('text', ''))}",
        }
    },
    "facebook": {
        "id": "facebook",
        "name": "Facebook",
        "category": "social",
        "aliases": ["facebook", "fb"],
        "desktop_binaries": [],
        "flatpak_id": None,
        "web_base": "https://www.facebook.com",
        "actions": {
            "open": lambda p: "https://www.facebook.com",
            "search": lambda p: f"https://www.facebook.com/search/top/?q={urllib.parse.quote(p.get('query', ''))}",
            "user": lambda p: f"https://www.facebook.com/{p.get('user', '')}",
            "group": lambda p: f"https://www.facebook.com/groups/{p.get('group', '')}",
        }
    },

    # =========================================================================
    # 2. STREAMING SITES
    # =========================================================================
    "youtube": {
        "id": "youtube",
        "name": "YouTube",
        "category": "streaming",
        "aliases": ["youtube", "yt"],
        "desktop_binaries": [],
        "flatpak_id": None,
        "web_base": "https://www.youtube.com",
        "actions": {
            "open": lambda p: "https://www.youtube.com",
            "search": lambda p: f"https://www.youtube.com/results?search_query={urllib.parse.quote(p.get('query', ''))}",
            "play": lambda p: f"https://www.youtube.com/watch?v={p.get('video_id', '')}&autoplay=1" if p.get('video_id') else f"https://www.youtube.com/results?search_query={urllib.parse.quote(p.get('query', ''))}",
            "channel": lambda p: f"https://www.youtube.com/@{p.get('channel', '').lstrip('@')}",
            "trending": lambda p: "https://www.youtube.com/feed/trending",
        }
    },
    "twitch": {
        "id": "twitch",
        "name": "Twitch",
        "category": "streaming",
        "aliases": ["twitch", "stream"],
        "desktop_binaries": [],
        "flatpak_id": None,
        "web_base": "https://www.twitch.tv",
        "actions": {
            "open": lambda p: "https://www.twitch.tv",
            "channel": lambda p: f"https://www.twitch.tv/{p.get('channel', '')}",
            "search": lambda p: f"https://www.twitch.tv/search?term={urllib.parse.quote(p.get('query', ''))}",
            "directory": lambda p: f"https://www.twitch.tv/directory/category/{p.get('game', '')}",
        }
    },
    "netflix": {
        "id": "netflix",
        "name": "Netflix",
        "category": "streaming",
        "aliases": ["netflix"],
        "desktop_binaries": [],
        "flatpak_id": None,
        "web_base": "https://www.netflix.com",
        "actions": {
            "open": lambda p: "https://www.netflix.com/browse",
            "search": lambda p: f"https://www.netflix.com/search?q={urllib.parse.quote(p.get('query', ''))}",
            "watch": lambda p: f"https://www.netflix.com/watch/{p.get('title_id', '')}",
        }
    },
    "primevideo": {
        "id": "primevideo",
        "name": "Prime Video",
        "category": "streaming",
        "aliases": ["primevideo", "prime video", "amazon prime"],
        "desktop_binaries": [],
        "flatpak_id": None,
        "web_base": "https://www.primevideo.com",
        "actions": {
            "open": lambda p: "https://www.primevideo.com",
            "search": lambda p: f"https://www.primevideo.com/search/ref=atv_nb_sr?phrase={urllib.parse.quote(p.get('query', ''))}",
        }
    },
    "disneyplus": {
        "id": "disneyplus",
        "name": "Disney+",
        "category": "streaming",
        "aliases": ["disneyplus", "disney+", "disney"],
        "desktop_binaries": [],
        "flatpak_id": None,
        "web_base": "https://www.disneyplus.com",
        "actions": {
            "open": lambda p: "https://www.disneyplus.com/home",
            "search": lambda p: f"https://www.disneyplus.com/search?q={urllib.parse.quote(p.get('query', ''))}",
        }
    },
    "hulu": {
        "id": "hulu",
        "name": "Hulu",
        "category": "streaming",
        "aliases": ["hulu"],
        "desktop_binaries": [],
        "flatpak_id": None,
        "web_base": "https://www.hulu.com",
        "actions": {
            "open": lambda p: "https://www.hulu.com/hub/home",
            "search": lambda p: f"https://www.hulu.com/search?q={urllib.parse.quote(p.get('query', ''))}",
        }
    },
    "kick": {
        "id": "kick",
        "name": "Kick",
        "category": "streaming",
        "aliases": ["kick", "kick.com"],
        "desktop_binaries": [],
        "flatpak_id": None,
        "web_base": "https://kick.com",
        "actions": {
            "open": lambda p: "https://kick.com",
            "channel": lambda p: f"https://kick.com/{p.get('channel', '')}",
            "search": lambda p: f"https://kick.com/search?query={urllib.parse.quote(p.get('query', ''))}",
        }
    },
    "vimeo": {
        "id": "vimeo",
        "name": "Vimeo",
        "category": "streaming",
        "aliases": ["vimeo"],
        "desktop_binaries": [],
        "flatpak_id": None,
        "web_base": "https://vimeo.com",
        "actions": {
            "open": lambda p: "https://vimeo.com/watch",
            "search": lambda p: f"https://vimeo.com/search?q={urllib.parse.quote(p.get('query', ''))}",
        }
    },
    "dailymotion": {
        "id": "dailymotion",
        "name": "Dailymotion",
        "category": "streaming",
        "aliases": ["dailymotion"],
        "desktop_binaries": [],
        "flatpak_id": None,
        "web_base": "https://www.dailymotion.com",
        "actions": {
            "open": lambda p: "https://www.dailymotion.com",
            "search": lambda p: f"https://www.dailymotion.com/search/{urllib.parse.quote(p.get('query', ''))}",
        }
    },
    "crunchyroll": {
        "id": "crunchyroll",
        "name": "Crunchyroll",
        "category": "streaming",
        "aliases": ["crunchyroll", "anime"],
        "desktop_binaries": [],
        "flatpak_id": None,
        "web_base": "https://www.crunchyroll.com",
        "actions": {
            "open": lambda p: "https://www.crunchyroll.com",
            "search": lambda p: f"https://www.crunchyroll.com/search?q={urllib.parse.quote(p.get('query', ''))}",
        }
    },

    # =========================================================================
    # 3. IDEs (Integrated Development Environments)
    # =========================================================================
    "vscode": {
        "id": "vscode",
        "name": "Visual Studio Code",
        "category": "ide",
        "aliases": ["vscode", "code", "vs code"],
        "desktop_binaries": ["code", "codium", "code-oss"],
        "flatpak_id": "com.visualstudio.code",
        "web_base": "https://vscode.dev",
        "cli_builder": lambda p: ["code", "--goto", f"{p.get('file', '')}:{p.get('line', '1')}"] if p.get('line') else (["code", p.get('path', '.')] if p.get('path') else ["code"]),
        "actions": {
            "open": lambda p: f"https://vscode.dev/{p.get('path', '')}" if not p.get('path', '').startswith('/') else f"https://vscode.dev",
            "goto": lambda p: f"https://vscode.dev/{p.get('file', '')}",
        }
    },
    "cursor": {
        "id": "cursor",
        "name": "Cursor / Antigravity IDE",
        "category": "ide",
        "aliases": ["cursor", "antigravity", "cursor-ai"],
        "desktop_binaries": ["cursor"],
        "flatpak_id": None,
        "cli_builder": lambda p: ["cursor", p.get('path', '.')] if p.get('path') else ["cursor"],
        "actions": {
            "open": lambda p: "https://cursor.com",
        }
    },
    "neovim": {
        "id": "neovim",
        "name": "Neovim / Vim",
        "category": "ide",
        "aliases": ["neovim", "nvim", "vim", "vi"],
        "desktop_binaries": ["nvim", "vim"],
        "flatpak_id": "io.neovim.nvim",
        "cli_builder": lambda p: ["nvim", f"+{p.get('line', '1')}", p.get('file', '')] if p.get('file') else ["nvim"],
        "actions": {
            "open": lambda p: "https://neovim.io",
        }
    },
    "pycharm": {
        "id": "pycharm",
        "name": "PyCharm",
        "category": "ide",
        "aliases": ["pycharm", "pycharm-community"],
        "desktop_binaries": ["pycharm-community", "pycharm"],
        "flatpak_id": "com.jetbrains.PyCharm-Community",
        "cli_builder": lambda p: ["pycharm", p.get('path', '.')],
        "actions": {
            "open": lambda p: "https://www.jetbrains.com/pycharm/",
        }
    },
    "intellij": {
        "id": "intellij",
        "name": "IntelliJ IDEA",
        "category": "ide",
        "aliases": ["intellij", "idea"],
        "desktop_binaries": ["idea", "intellij-idea-community"],
        "flatpak_id": "com.jetbrains.IntelliJ-IDEA-Community",
        "cli_builder": lambda p: ["idea", p.get('path', '.')],
        "actions": {
            "open": lambda p: "https://www.jetbrains.com/idea/",
        }
    },
    "sublime": {
        "id": "sublime",
        "name": "Sublime Text",
        "category": "ide",
        "aliases": ["sublime", "subl", "sublime-text"],
        "desktop_binaries": ["subl", "sublime_text"],
        "flatpak_id": "com.sublimetext.three",
        "cli_builder": lambda p: ["subl", f"{p.get('file', '')}:{p.get('line', '1')}"] if p.get('line') else ["subl", p.get('path', '.')],
        "actions": {
            "open": lambda p: "https://www.sublimetext.com",
        }
    },
    "replit": {
        "id": "replit",
        "name": "Replit",
        "category": "ide",
        "aliases": ["replit"],
        "desktop_binaries": [],
        "flatpak_id": None,
        "web_base": "https://replit.com",
        "actions": {
            "open": lambda p: f"https://replit.com/@{p.get('user', '')}/{p.get('repl', '')}" if p.get('repl') else "https://replit.com/~",
            "new": lambda p: f"https://replit.com/new/{p.get('language', 'python3')}",
        }
    },
    "codespaces": {
        "id": "codespaces",
        "name": "GitHub Codespaces",
        "category": "ide",
        "aliases": ["codespaces", "github-codespaces", "github.dev"],
        "desktop_binaries": [],
        "flatpak_id": None,
        "web_base": "https://github.dev",
        "actions": {
            "open": lambda p: f"https://github.dev/{p.get('repo', '')}" if p.get('repo') else "https://github.com/codespaces",
        }
    },
    "stackblitz": {
        "id": "stackblitz",
        "name": "StackBlitz",
        "category": "ide",
        "aliases": ["stackblitz"],
        "desktop_binaries": [],
        "flatpak_id": None,
        "web_base": "https://stackblitz.com",
        "actions": {
            "open": lambda p: f"https://stackblitz.com/edit/{p.get('project', '')}" if p.get('project') else "https://stackblitz.com",
            "new": lambda p: f"https://stackblitz.com/fork/{p.get('template', 'node')}",
        }
    },
    "jupyter": {
        "id": "jupyter",
        "name": "JupyterLab / Notebook",
        "category": "ide",
        "aliases": ["jupyter", "jupyterlab", "jupyter-notebook"],
        "desktop_binaries": ["jupyter-lab", "jupyter"],
        "flatpak_id": None,
        "cli_builder": lambda p: ["jupyter-lab", p.get('notebook', '.')] if p.get('notebook') else ["jupyter-lab"],
        "actions": {
            "open": lambda p: "http://localhost:8888/lab",
        }
    },

    # =========================================================================
    # 4. CAD SYSTEMS
    # =========================================================================
    "freecad": {
        "id": "freecad",
        "name": "FreeCAD",
        "category": "cad",
        "aliases": ["freecad", "cad"],
        "desktop_binaries": ["freecad", "FreeCAD"],
        "flatpak_id": "org.freecad.FreeCAD",
        "cli_builder": lambda p: ["freecad", p.get('file', '')] if p.get('file') else ["freecad"],
        "actions": {
            "open": lambda p: "https://www.freecad.org",
        }
    },
    "blender": {
        "id": "blender",
        "name": "Blender 3D",
        "category": "cad",
        "aliases": ["blender", "blender3d"],
        "desktop_binaries": ["blender"],
        "flatpak_id": "org.blender.Blender",
        "cli_builder": lambda p: (["blender", "-b", p.get('file', ''), "-P", p.get('script', '')] if p.get('script') else ["blender", p.get('file', '')]) if p.get('file') else ["blender"],
        "actions": {
            "open": lambda p: "https://www.blender.org",
        }
    },
    "openscad": {
        "id": "openscad",
        "name": "OpenSCAD",
        "category": "cad",
        "aliases": ["openscad", "scad"],
        "desktop_binaries": ["openscad"],
        "flatpak_id": "org.openscad.OpenSCAD",
        "cli_builder": lambda p: (["openscad", "-o", p.get('output', 'model.stl'), p.get('file', '')] if p.get('output') else ["openscad", p.get('file', '')]) if p.get('file') else ["openscad"],
        "actions": {
            "open": lambda p: "https://openscad.org",
        }
    },
    "onshape": {
        "id": "onshape",
        "name": "Onshape",
        "category": "cad",
        "aliases": ["onshape"],
        "desktop_binaries": [],
        "flatpak_id": None,
        "web_base": "https://cad.onshape.com",
        "actions": {
            "open": lambda p: f"https://cad.onshape.com/documents/{p.get('doc_id', '')}" if p.get('doc_id') else "https://cad.onshape.com",
        }
    },
    "tinkercad": {
        "id": "tinkercad",
        "name": "Tinkercad",
        "category": "cad",
        "aliases": ["tinkercad"],
        "desktop_binaries": [],
        "flatpak_id": None,
        "web_base": "https://www.tinkercad.com",
        "actions": {
            "open": lambda p: "https://www.tinkercad.com/dashboard",
            "new": lambda p: "https://www.tinkercad.com/things/new",
        }
    },
    "sketchup": {
        "id": "sketchup",
        "name": "SketchUp for Web",
        "category": "cad",
        "aliases": ["sketchup", "sketchup-web"],
        "desktop_binaries": [],
        "flatpak_id": None,
        "web_base": "https://app.sketchup.com/app",
        "actions": {
            "open": lambda p: "https://app.sketchup.com/app",
        }
    },
    "spline": {
        "id": "spline",
        "name": "Spline 3D",
        "category": "cad",
        "aliases": ["spline", "spline3d"],
        "desktop_binaries": [],
        "flatpak_id": None,
        "web_base": "https://app.spline.design",
        "actions": {
            "open": lambda p: "https://app.spline.design",
        }
    },
    "librecad": {
        "id": "librecad",
        "name": "LibreCAD",
        "category": "cad",
        "aliases": ["librecad"],
        "desktop_binaries": ["librecad"],
        "flatpak_id": "org.librecad.librecad",
        "cli_builder": lambda p: ["librecad", p.get('file', '')] if p.get('file') else ["librecad"],
        "actions": {
            "open": lambda p: "https://librecad.org",
        }
    },
    "solvespace": {
        "id": "solvespace",
        "name": "SolveSpace",
        "category": "cad",
        "aliases": ["solvespace"],
        "desktop_binaries": ["solvespace"],
        "flatpak_id": "com.solvespace.SolveSpace",
        "cli_builder": lambda p: ["solvespace", p.get('file', '')] if p.get('file') else ["solvespace"],
        "actions": {
            "open": lambda p: "https://solvespace.com",
        }
    },
    "womp": {
        "id": "womp",
        "name": "Womp 3D",
        "category": "cad",
        "aliases": ["womp", "womp3d"],
        "desktop_binaries": [],
        "flatpak_id": None,
        "web_base": "https://womp.com",
        "actions": {
            "open": lambda p: "https://womp.com",
        }
    },

    # =========================================================================
    # 5. GRAPHIC SYSTEMS
    # =========================================================================
    "figma": {
        "id": "figma",
        "name": "Figma",
        "category": "graphics",
        "aliases": ["figma"],
        "desktop_binaries": ["figma-linux"],
        "flatpak_id": "io.github.Figma_Linux.figma_linux",
        "web_base": "https://www.figma.com",
        "actions": {
            "open": lambda p: f"https://www.figma.com/file/{p.get('file_id', '')}" if p.get('file_id') else "https://www.figma.com/files/recent",
            "prototype": lambda p: f"https://www.figma.com/proto/{p.get('file_id', '')}",
        }
    },
    "canva": {
        "id": "canva",
        "name": "Canva",
        "category": "graphics",
        "aliases": ["canva"],
        "desktop_binaries": [],
        "flatpak_id": None,
        "web_base": "https://www.canva.com",
        "actions": {
            "open": lambda p: f"https://www.canva.com/design/{p.get('design_id', '')}" if p.get('design_id') else "https://www.canva.com",
            "create": lambda p: f"https://www.canva.com/create/{p.get('template', 'posters')}/",
        }
    },
    "photopea": {
        "id": "photopea",
        "name": "Photopea",
        "category": "graphics",
        "aliases": ["photopea", "online-photoshop"],
        "desktop_binaries": [],
        "flatpak_id": None,
        "web_base": "https://www.photopea.com",
        "actions": {
            "open": lambda p: f"https://www.photopea.com#{urllib.parse.quote(p.get('file_url', ''))}" if p.get('file_url') else "https://www.photopea.com",
        }
    },
    "gimp": {
        "id": "gimp",
        "name": "GIMP",
        "category": "graphics",
        "aliases": ["gimp", "gnu-image-manipulation-program"],
        "desktop_binaries": ["gimp"],
        "flatpak_id": "org.gimp.GIMP",
        "cli_builder": lambda p: ["gimp", p.get('file', '')] if p.get('file') else ["gimp"],
        "actions": {
            "open": lambda p: "https://www.gimp.org",
        }
    },
    "inkscape": {
        "id": "inkscape",
        "name": "Inkscape",
        "category": "graphics",
        "aliases": ["inkscape", "vector"],
        "desktop_binaries": ["inkscape"],
        "flatpak_id": "org.inkscape.Inkscape",
        "cli_builder": lambda p: (["inkscape", p.get('file', ''), "-o", p.get('output', '')] if p.get('output') else ["inkscape", p.get('file', '')]) if p.get('file') else ["inkscape"],
        "actions": {
            "open": lambda p: "https://inkscape.org",
        }
    },
    "krita": {
        "id": "krita",
        "name": "Krita",
        "category": "graphics",
        "aliases": ["krita"],
        "desktop_binaries": ["krita"],
        "flatpak_id": "org.kde.krita",
        "cli_builder": lambda p: ["krita", p.get('file', '')] if p.get('file') else ["krita"],
        "actions": {
            "open": lambda p: "https://krita.org",
        }
    },
    "imagemagick": {
        "id": "imagemagick",
        "name": "ImageMagick",
        "category": "graphics",
        "aliases": ["imagemagick", "convert", "magick"],
        "desktop_binaries": ["magick", "convert"],
        "flatpak_id": None,
        "cli_builder": lambda p: ["convert", p.get('input', ''), p.get('output', 'out.png')] if p.get('input') else ["convert", "-version"],
        "actions": {
            "open": lambda p: "https://imagemagick.org",
        }
    },
    "pixlr": {
        "id": "pixlr",
        "name": "Pixlr",
        "category": "graphics",
        "aliases": ["pixlr"],
        "desktop_binaries": [],
        "flatpak_id": None,
        "web_base": "https://pixlr.com",
        "actions": {
            "open": lambda p: "https://pixlr.com/editor/",
        }
    },
    "darktable": {
        "id": "darktable",
        "name": "Darktable",
        "category": "graphics",
        "aliases": ["darktable"],
        "desktop_binaries": ["darktable"],
        "flatpak_id": "org.darktable.Darktable",
        "cli_builder": lambda p: ["darktable", p.get('file', '')] if p.get('file') else ["darktable"],
        "actions": {
            "open": lambda p: "https://www.darktable.org",
        }
    },
    "rawtherapee": {
        "id": "rawtherapee",
        "name": "RawTherapee",
        "category": "graphics",
        "aliases": ["rawtherapee"],
        "desktop_binaries": ["rawtherapee"],
        "flatpak_id": "com.rawtherapee.RawTherapee",
        "cli_builder": lambda p: ["rawtherapee", p.get('file', '')] if p.get('file') else ["rawtherapee"],
        "actions": {
            "open": lambda p: "https://rawtherapee.com",
        }
    },

    # =========================================================================
    # 6. MUSIC APPS & WEBSITES
    # =========================================================================
    "spotify": {
        "id": "spotify",
        "name": "Spotify",
        "category": "music",
        "aliases": ["spotify"],
        "desktop_binaries": ["spotify"],
        "flatpak_id": "com.spotify.Client",
        "web_base": "https://open.spotify.com",
        "cli_builder": lambda p: ["spotify", f"--uri={p.get('uri', '')}"] if p.get('uri') else ["spotify"],
        "actions": {
            "open": lambda p: "https://open.spotify.com",
            "search": lambda p: f"https://open.spotify.com/search/{urllib.parse.quote(p.get('query', ''))}",
            "play": lambda p: f"https://open.spotify.com/search/{urllib.parse.quote(p.get('query', ''))}",
            "track": lambda p: f"https://open.spotify.com/track/{p.get('track_id', '')}",
            "playlist": lambda p: f"https://open.spotify.com/playlist/{p.get('playlist_id', '')}",
        }
    },
    "youtubemusic": {
        "id": "youtubemusic",
        "name": "YouTube Music",
        "category": "music",
        "aliases": ["youtubemusic", "yt music", "youtube-music"],
        "desktop_binaries": ["youtube-music"],
        "flatpak_id": "com.github.th_ch.youtube_music",
        "web_base": "https://music.youtube.com",
        "actions": {
            "open": lambda p: "https://music.youtube.com",
            "search": lambda p: f"https://music.youtube.com/search?q={urllib.parse.quote(p.get('query', ''))}",
            "play": lambda p: f"https://music.youtube.com/search?q={urllib.parse.quote(p.get('query', ''))}",
        }
    },
    "soundcloud": {
        "id": "soundcloud",
        "name": "SoundCloud",
        "category": "music",
        "aliases": ["soundcloud"],
        "desktop_binaries": [],
        "flatpak_id": None,
        "web_base": "https://soundcloud.com",
        "actions": {
            "open": lambda p: "https://soundcloud.com/discover",
            "search": lambda p: f"https://soundcloud.com/search?q={urllib.parse.quote(p.get('query', ''))}",
            "user": lambda p: f"https://soundcloud.com/{p.get('user', '')}",
        }
    },
    "applemusic": {
        "id": "applemusic",
        "name": "Apple Music",
        "category": "music",
        "aliases": ["applemusic", "apple music"],
        "desktop_binaries": [],
        "flatpak_id": None,
        "web_base": "https://music.apple.com",
        "actions": {
            "open": lambda p: "https://music.apple.com",
            "search": lambda p: f"https://music.apple.com/search?term={urllib.parse.quote(p.get('query', ''))}",
        }
    },
    "tidal": {
        "id": "tidal",
        "name": "Tidal",
        "category": "music",
        "aliases": ["tidal"],
        "desktop_binaries": ["tidal-hifi"],
        "flatpak_id": "com.mastermindzh.tidal-hifi",
        "web_base": "https://listen.tidal.com",
        "actions": {
            "open": lambda p: "https://listen.tidal.com",
            "search": lambda p: f"https://listen.tidal.com/search?q={urllib.parse.quote(p.get('query', ''))}",
        }
    },
    "deezer": {
        "id": "deezer",
        "name": "Deezer",
        "category": "music",
        "aliases": ["deezer"],
        "desktop_binaries": ["deezer"],
        "flatpak_id": "dev.aunetx.deezer",
        "web_base": "https://www.deezer.com",
        "actions": {
            "open": lambda p: "https://www.deezer.com",
            "search": lambda p: f"https://www.deezer.com/search/{urllib.parse.quote(p.get('query', ''))}",
        }
    },
    "bandcamp": {
        "id": "bandcamp",
        "name": "Bandcamp",
        "category": "music",
        "aliases": ["bandcamp"],
        "desktop_binaries": [],
        "flatpak_id": None,
        "web_base": "https://bandcamp.com",
        "actions": {
            "open": lambda p: "https://bandcamp.com",
            "search": lambda p: f"https://bandcamp.com/search?q={urllib.parse.quote(p.get('query', ''))}",
        }
    },
    "vlc": {
        "id": "vlc",
        "name": "VLC Media Player",
        "category": "music",
        "aliases": ["vlc", "vlc-player"],
        "desktop_binaries": ["vlc"],
        "flatpak_id": "org.videolan.VLC",
        "cli_builder": lambda p: ["vlc", p.get('file', '')] if p.get('file') else ["vlc"],
        "actions": {
            "open": lambda p: "https://www.videolan.org/vlc/",
        }
    },
    "audacity": {
        "id": "audacity",
        "name": "Audacity",
        "category": "music",
        "aliases": ["audacity"],
        "desktop_binaries": ["audacity"],
        "flatpak_id": "org.audacityteam.Audacity",
        "cli_builder": lambda p: ["audacity", p.get('file', '')] if p.get('file') else ["audacity"],
        "actions": {
            "open": lambda p: "https://www.audacityteam.org",
        }
    },
    "rhythmbox": {
        "id": "rhythmbox",
        "name": "Rhythmbox",
        "category": "music",
        "aliases": ["rhythmbox"],
        "desktop_binaries": ["rhythmbox", "rhythmbox-client"],
        "flatpak_id": "org.gnome.Rhythmbox3",
        "cli_builder": lambda p: ["rhythmbox-client", f"--play-uri={p.get('file', '')}"] if p.get('file') else ["rhythmbox"],
        "actions": {
            "open": lambda p: "https://wiki.gnome.org/Apps/Rhythmbox",
        }
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────────────────────

CATEGORIES = ["social", "streaming", "ide", "cad", "graphics", "music"]

def get_apps_by_category(category: str) -> List[Dict[str, Any]]:
    """Return all registered apps under a specific category."""
    cat_lower = category.lower().strip()
    return [app for app in APP_REGISTRY.values() if app["category"] == cat_lower]

def find_app_entry(app_name: str) -> Optional[Dict[str, Any]]:
    """Lookup app by exact key, name, or aliases."""
    normalized = app_name.lower().strip()
    if normalized in APP_REGISTRY:
        return APP_REGISTRY[normalized]
    for app in APP_REGISTRY.values():
        if normalized == app["name"].lower() or normalized in app.get("aliases", []):
            return app
        for alias in app.get("aliases", []):
            if alias in normalized or normalized in alias:
                return app
    return None
