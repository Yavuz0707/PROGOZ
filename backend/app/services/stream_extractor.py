import logging
import re
import threading
from pathlib import Path

logger = logging.getLogger("progoz.stream_extractor")

_FORMAT = (
    "best[height<=480][protocol=m3u8_native]"
    "/best[height<=480]"
    "/best[protocol=m3u8_native]"
    "/best"
)

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_COOKIES_FILE = Path(__file__).parent.parent.parent / "cookies.txt"

# Hard wall-clock limit for the entire extraction (seconds)
_TIMEOUT = 25


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _do_extract(page_url: str) -> str:
    """Blocking yt-dlp extraction — always called via _extract_timeout."""
    import yt_dlp

    opts: dict = {
        "format": _FORMAT,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 10,
    }
    if _COOKIES_FILE.exists():
        opts["cookiefile"] = str(_COOKIES_FILE)
        logger.info("cookies.txt kullaniliyor")

    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            info = ydl.extract_info(page_url, download=False)
        except yt_dlp.utils.DownloadError as exc:
            raise ValueError(_strip_ansi(str(exc))) from exc

    if info is None:
        raise ValueError("Sayfa analiz edilemedi.")
    if "entries" in info:
        entry = next(iter(info["entries"]), None)
        if entry is None:
            raise ValueError("Playlist bos.")
        info = entry

    url = info.get("url")
    if not url:
        raise ValueError("Stream URL bulunamadi.")

    logger.info("Stream alindi → %sp %s %s…", info.get("height", "?"), info.get("protocol", "?"), url[:60])
    return url


def extract_stream_url(page_url: str) -> str:
    """
    Return a playable stream URL with a hard 25-second timeout.
    If yt-dlp hangs (unsupported site, bot protection, etc.) the call
    returns an error instead of blocking the API forever.
    """
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        raise RuntimeError("yt-dlp yuklu degil. 'pip install yt-dlp' calistirin.")

    result: list = [None]
    error: list = [None]

    def _worker():
        try:
            result[0] = _do_extract(page_url)
        except Exception as exc:  # noqa: BLE001
            error[0] = exc

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join(timeout=_TIMEOUT)

    if t.is_alive():
        # Thread still running → yt-dlp is stuck
        raise ValueError(
            f"Stream alinamadi: {_TIMEOUT} saniye icinde yanit gelmedi.\n"
            "Bu site desteklenmiyor veya bot koruması aktif olabilir.\n"
            "Dogrudan HLS/RTSP/m3u8 adresi deneyin."
        )

    if error[0] is not None:
        exc = error[0]
        raw = _strip_ansi(str(exc))
        is_yt = "youtube" in page_url.lower() or "youtu.be" in page_url.lower()
        if is_yt and any(k in raw.lower() for k in ("bot", "sign in", "login", "cookie")):
            raise ValueError(
                "YouTube bot koruması aktif.\n\n"
                "Çözüm: Chrome'a 'Get cookies.txt LOCALLY' eklentisini kur, "
                "youtube.com'a giriş yap, cookies.txt indir ve şuraya koy:\n"
                f"{_COOKIES_FILE}\n\nSonra tekrar dene."
            ) from exc
        raise ValueError(raw) from exc

    return result[0]
