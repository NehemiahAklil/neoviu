"""Downloads and caches cover art for the grid TUI."""

import hashlib
import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional
from urllib.parse import urlparse

import httpx

from ...core.constants import APP_CACHE_DIR
from ...libs.media_api.types import MediaItem

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage

logger = logging.getLogger(__name__)

COVERS_DIR = APP_CACHE_DIR / "covers"
# Largest decoded cover kept in memory; bigger art only slows down rendering.
MAX_COVER_PIXELS = (460, 650)

_slots = threading.BoundedSemaphore(6)
_client_lock = threading.Lock()
_client: Optional[httpx.Client] = None
_image_widget: Optional[Any] = None


def prepare_images(enabled: bool = True) -> bool:
    """Loads the image widget; returns False when covers fall back to text.

    textual-image probes the terminal when it is imported, which is only
    possible before Textual takes over the screen, so call this first.
    """
    global _image_widget
    _image_widget = None
    if not enabled:
        return False
    try:
        from textual_image.widget import Image
    except Exception as e:  # missing extra or an unsupported terminal
        logger.info(f"Cover images disabled: {e}")
        return False
    _image_widget = Image
    return True


def image_widget() -> Optional[Any]:
    return _image_widget


def cover_url(item: MediaItem, large: bool = False) -> Optional[str]:
    image = item.cover_image
    if image is None:
        return None
    if large:
        return image.extra_large or image.large or image.medium
    return image.large or image.medium or image.extra_large


def cover_path(url: str, cache_dir: Path = COVERS_DIR) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        suffix = ".img"
    return cache_dir / f"{digest}{suffix}"


def _http() -> httpx.Client:
    global _client
    with _client_lock:
        if _client is None:
            _client = httpx.Client(timeout=15, follow_redirects=True)
        return _client


def fetch_cover(url: str, cache_dir: Path = COVERS_DIR) -> Optional[Path]:
    """Returns the cached cover for ``url``, downloading it on first use."""
    path = cover_path(url, cache_dir)
    if path.is_file() and path.stat().st_size:
        return path
    with _slots:
        if path.is_file() and path.stat().st_size:
            return path
        try:
            response = _http().get(url)
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.debug(f"Cover download failed for {url}: {e}")
            return None
    tmp = path.with_name(f"{path.name}.{threading.get_ident()}.part")
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(response.content)
        tmp.replace(path)
    except OSError as e:
        logger.debug(f"Could not cache cover {url}: {e}")
        tmp.unlink(missing_ok=True)
        return None
    return path


def load_cover(url: str) -> Optional["PILImage"]:
    """Downloads and decodes a cover, shrunk for terminal rendering."""
    path = fetch_cover(url)
    if path is None:
        return None
    try:
        from PIL import Image

        image = Image.open(path)
        image.draft("RGB", MAX_COVER_PIXELS)
        image = image.convert("RGB")
        image.thumbnail(MAX_COVER_PIXELS)
        return image
    except Exception as e:
        logger.debug(f"Could not decode cover {path}: {e}")
        path.unlink(missing_ok=True)
        return None


def close() -> None:
    global _client
    with _client_lock:
        if _client is not None:
            _client.close()
            _client = None
