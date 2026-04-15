from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
LANDING_DIR = ROOT / "landing_site"
GAME_DIR = ROOT / "web"
DIST_DIR = ROOT / "site_dist"
PLAY_DIR = DIST_DIR / "play"

GAME_FILES = (
    "index.html",
    "app.js",
    "styles.css",
    "main_music.ogg",
    "favicon.svg",
)
def rebuild_dist() -> None:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copytree(LANDING_DIR, DIST_DIR, dirs_exist_ok=True)
    PLAY_DIR.mkdir(parents=True, exist_ok=True)

    for filename in GAME_FILES:
        shutil.copy2(GAME_DIR / filename, PLAY_DIR / filename)


if __name__ == "__main__":
    rebuild_dist()
    print(f"Built Netlify site into: {DIST_DIR}")
