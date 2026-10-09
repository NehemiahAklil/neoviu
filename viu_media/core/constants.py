import os
import sys
from importlib import metadata, resources
from pathlib import Path

PLATFORM = sys.platform
CLI_NAME = "NVIU"
CLI_NAME_LOWER = "nviu"
PROJECT_NAME = "nviu"
# Name used for the config, data, and cache directories before the rename to nviu.
LEGACY_APP_NAME = "viu"
APP_NAME = os.environ.get(f"{CLI_NAME}_APP_NAME", CLI_NAME_LOWER)

USER_NAME = os.environ.get("USERNAME", os.environ.get("USER", "User"))


__version__ = metadata.version(PROJECT_NAME)

AUTHOR = "NehemiahAklil"
REPO_NAME = "neoviu"
GIT_REPO = "github.com"
GIT_PROTOCOL = "https://"
REPO_HOME = f"https://{GIT_REPO}/{AUTHOR}/{REPO_NAME}"
REPO_GIT_URL = f"{REPO_HOME}.git"

DISCORD_INVITE = "https://discord.gg/C4rhMA4mmK"

ANILIST_AUTH = (
    "https://anilist.co/api/v2/oauth/authorize?client_id=20148&response_type=token"
)

try:
    APP_DIR = Path(str(resources.files("viu_media")))

except ModuleNotFoundError:
    from pathlib import Path

    APP_DIR = Path(__file__).resolve().parent.parent

ASSETS_DIR = APP_DIR / "assets"
DEFAULTS_DIR = ASSETS_DIR / "defaults"
SCRIPTS_DIR = ASSETS_DIR / "scripts"
GRAPHQL_DIR = ASSETS_DIR / "graphql"
ICONS_DIR = ASSETS_DIR / "icons"

ICON_PATH = ICONS_DIR / ("logo.ico" if PLATFORM == "Win32" else "logo.png")
APP_ASCII_ART = DEFAULTS_DIR / "ascii-art"


def _app_data_dir(app_name: str) -> Path:
    try:
        import click

        return Path(click.get_app_dir(app_name, roaming=False))
    except ModuleNotFoundError:
        if PLATFORM == "win32":
            return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / app_name
        if PLATFORM == "darwin":
            return Path.home() / "Library" / "Application Support" / app_name
        return (
            Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / app_name
        )


APP_DATA_DIR = _app_data_dir(APP_NAME)

# Carry config, logins, and history over from a pre-rename install. The old
# directory is copied, not moved, so an upstream Viu install keeps working.
if APP_NAME == CLI_NAME_LOWER and not APP_DATA_DIR.exists():
    _legacy_data_dir = _app_data_dir(LEGACY_APP_NAME)
    if _legacy_data_dir.is_dir():
        import shutil

        try:
            shutil.copytree(_legacy_data_dir, APP_DATA_DIR)
        except OSError:
            pass

if PLATFORM == "win32":
    APP_CACHE_DIR = APP_DATA_DIR / "cache"
    USER_VIDEOS_DIR = Path.home() / "Videos" / APP_NAME

elif PLATFORM == "darwin":
    APP_CACHE_DIR = Path.home() / "Library" / "Caches" / APP_NAME
    USER_VIDEOS_DIR = Path.home() / "Movies" / APP_NAME

else:
    xdg_cache_home = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    APP_CACHE_DIR = xdg_cache_home / APP_NAME

    xdg_videos_dir = Path(os.environ.get("XDG_VIDEOS_DIR", Path.home() / "Videos"))
    USER_VIDEOS_DIR = xdg_videos_dir / APP_NAME

USER_APPLICATIONS = Path.home() / ".local" / "share" / "applications"
LOG_FOLDER = APP_CACHE_DIR / "logs"

# USER_APPLICATIONS.mkdir(parents=True,exist_ok=True)
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
APP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
LOG_FOLDER.mkdir(parents=True, exist_ok=True)
USER_VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

USER_CONFIG = APP_DATA_DIR / "config.toml"

LOG_FILE = LOG_FOLDER / "app.log"
SUPPORT_PROJECT_URL = REPO_HOME
