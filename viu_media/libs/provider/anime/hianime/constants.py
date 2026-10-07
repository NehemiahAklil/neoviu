from ..types import ProviderServer

HIANIME_BASE = "https://hianime.at"
REQUEST_HEADERS = {
    "Referer": HIANIME_BASE + "/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}
AJAX_HEADERS = {"X-Requested-With": "XMLHttpRequest"}
EMBED_SERVERS = {
    "zokoanime": ProviderServer.ZOKOANIME,
    "hd-1": ProviderServer.MEGAPLAY,
}
