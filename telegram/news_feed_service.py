"""
Сервис парсинга и кэширования ленты новостей официального Telegram-канала (@itheprison)
с безопасной санитизацией HTML и дисковым прокси-кэшем медиа (фото + GIF/MP4 с поддержкой Range).
"""

from __future__ import annotations

import asyncio
import hashlib
import html as html_lib
import json
import logging
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

_ALLOWED_TAGS = {"b", "strong", "i", "em", "u", "s", "code", "pre", "blockquote", "br", "a"}
_ALLOWED_MEDIA_HOST_SUFFIXES = ("telesco.pe", "telegram.org", "cdn-telegram.org", "t.me")


def is_allowed_telegram_media_url(url: str) -> bool:
    """SSRF-проверка: разрешены только официальные HTTPS-хосты Telegram CDN."""
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return False
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    host = parsed.hostname.lower().strip(".")
    return any(host == suf or host.endswith(f".{suf}") for suf in _ALLOWED_MEDIA_HOST_SUFFIXES)


class _TelegramHtmlSanitizer(HTMLParser):
    """Строгий allowlist-санитайзер HTML для безопасного рендера постов Telegram."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._out: List[str] = []
        self._skip_depth: int = 0

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        t = tag.lower()
        if t in ("script", "style", "iframe", "object", "embed", "svg"):
            self._skip_depth += 1
            return
        if self._skip_depth > 0:
            return
        if t == "br":
            self._out.append("<br>")
            return
        if t not in _ALLOWED_TAGS:
            return
        if t == "a":
            href = ""
            for k, v in attrs:
                if k.lower() == "href" and v:
                    cand = v.strip()
                    if cand.startswith("https://") or cand.startswith("http://"):
                        href = html_lib.escape(cand, quote=True)
                    break
            if href:
                self._out.append(f'<a href="{href}" target="_blank" rel="noopener noreferrer">')
            else:
                self._out.append("<a>")
        else:
            self._out.append(f"<{t}>")

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in ("script", "style", "iframe", "object", "embed", "svg"):
            if self._skip_depth > 0:
                self._skip_depth -= 1
            return
        if self._skip_depth > 0 or t == "br" or t not in _ALLOWED_TAGS:
            return
        self._out.append(f"</{t}>")

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        self._out.append(html_lib.escape(data))

    def get_html(self) -> str:
        return "".join(self._out).strip()


def sanitize_telegram_html(raw_html: str) -> str:
    if not raw_html:
        return ""
    s = _TelegramHtmlSanitizer()
    s.feed(raw_html)
    s.close()
    return s.get_html()


def _extract_balanced_div(html_text: str, start_pos: int) -> Tuple[str, int]:
    """Извлекает содержимое <div ...>...</div> с учетом вложенных div."""
    tag_end = html_text.find(">", start_pos)
    if tag_end == -1:
        return "", start_pos + 1
    depth = 1
    pos = tag_end + 1
    pattern = re.compile(r"<(/?)div\b", re.IGNORECASE)
    for m in pattern.finditer(html_text, pos):
        if m.group(1) == "/":
            depth -= 1
            if depth == 0:
                close_end = html_text.find(">", m.start())
                return html_text[tag_end + 1 : m.start()], (close_end + 1 if close_end != -1 else m.end())
        else:
            depth += 1
    return html_text[tag_end + 1 : min(len(html_text), tag_end + 8000)], len(html_text)


def _media_id_for_url(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]


_NEWS_DENY_PATTERNS = (
    r"итог[иа]\s+активност",
    r"самыми\s+активными",
    r"самыми\s+уважаемыми",
    r"\bрозыгрыш\w*",
    r"\bконкурс\w*",
    r"\bпобедител\w*",
    r"\bпризер\w*",
    r"\bпризёр\w*",
    r"список\s+победителей",
    r"раздача\s+приз",
)

_NEWS_ALLOW_PATTERNS = (
    r"дорожн\w+\s+карт",
    r"тех(?:ническ\w+)?\s+работ",
    r"профилактик\w*",
    r"серверн\w+\s+работ",
    r"\bобновлен\w*",
    r"\bпатч\w*",
    r"\bфикс\w*",
    r"исправлен\w*",
    r"\bбаланс\w*",
    r"нов\w+\s+(?:босс|талант|событ|рейд|тюрьм|акци|механик)",
    r"\bменял\w*",
    r"\bзаруб\w*",
    r"\bрейд\w*",
    r"\bбосс\w*",
    r"\bакци\w*",
    r"\bсобыт\w*",
    r"\bталант\w*",
    r"\bтюрьм\w*",
    r"\bпосылк\w*",
    r"\bурон\w*",
    r"\bделюг\w*",
    r"\bконтрабанд\w*",
    r"\bсходняк\w*",
    r"\bкореш\w*",
)


def is_game_news_post(post: Dict[str, Any]) -> bool:
    """
    Умный фильтр ленты @itheprison:
    пропускает только игровые новости (обновления, дорожные карты, техработы, фиксы,
    боссы, события, акции, меняла, зарубы, баланс) и отсеивает итоги активности
    сообщества, розыгрыши, конкурсы и списки призеров с @username.
    """
    if not isinstance(post, dict):
        return False
    text = str(post.get("text") or "").strip()
    if not text and post.get("html"):
        text = html_lib.unescape(re.sub(r"<[^>]+>", " ", str(post.get("html") or ""))).strip()
    low = re.sub(r"\s+", " ", text).lower()

    # 1. Явные deny-правила (итоги активности, розыгрыши, списки призеров)
    for pat in _NEWS_DENY_PATTERNS:
        if re.search(pat, low, re.IGNORECASE):
            return False

    # 2. Массовые упоминания @username / нумерованный рейтинг призеров
    mentions = re.findall(r"@[a-z0-9_]{3,}", low)
    if len(mentions) >= 2:
        return False
    if re.search(r"(?:^|\s)(?:1[\.\)]|🥇|🥈|🥉)\s*@", low):
        return False

    # 3. Allow-правила: игровая тематика
    for pat in _NEWS_ALLOW_PATTERNS:
        if re.search(pat, low, re.IGNORECASE):
            return True

    # Если есть медиа (например картинка дорожной карты с коротким текстом),
    # но без deny-признаков и без спама — разрешаем только при наличии минимального игрового контекста
    # либо если текста нет совсем (чистый анонс-баннер), но не оффтоп-реклама.
    if not low and post.get("media"):
        return True
    return False


def _news_content_hash(post: Dict[str, Any]) -> str:
    norm_text = re.sub(r"\s+", " ", str(post.get("text") or "").strip().lower())
    media_ids = ",".join(
        str(m.get("id") or m.get("url") or "")
        for m in (post.get("media") or [])
        if isinstance(m, dict)
    )
    payload = f"{norm_text}|{media_ids}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def deduplicate_news_posts(posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Дедуплицирует посты по post_id и по нормализованному контент-хэшу текста + медиа."""
    seen_ids: set[str] = set()
    seen_hashes: set[str] = set()
    out: List[Dict[str, Any]] = []
    for p in posts or []:
        if not isinstance(p, dict):
            continue
        pid = str(p.get("post_id") or "")
        if pid and pid in seen_ids:
            continue
        chash = _news_content_hash(p)
        if chash in seen_hashes:
            continue
        if pid:
            seen_ids.add(pid)
        seen_hashes.add(chash)
        out.append(p)
    return out


def parse_telegram_channel_html(html_text: str, channel: str = "itheprison") -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, str]]]:
    """
    Парсит публичную HTML-страницу `https://t.me/s/<channel>`.
    Возвращает (posts, media_registry).
    """
    posts: List[Dict[str, Any]] = []
    media_reg: Dict[str, Dict[str, str]] = {}

    msg_pattern = re.compile(
        r'<div[^>]+class="[^"]*tgme_widget_message\b[^"]*"[^>]+data-post="([^"]+)"[^>]*>',
        re.IGNORECASE,
    )
    for m in msg_pattern.finditer(html_text):
        data_post = m.group(1)
        block_html, _ = _extract_balanced_div(html_text, m.start())
        if not block_html:
            continue

        post_id_str = data_post.rsplit("/", 1)[-1]
        if not post_id_str.isdigit():
            continue
        post_id = int(post_id_str)

        # Текст поста (tgme_widget_message_text)
        raw_text_html = ""
        txt_m = re.search(r'<div[^>]+class="[^"]*tgme_widget_message_text[^"]*"[^>]*>', block_html, re.IGNORECASE)
        if txt_m:
            raw_text_html, _ = _extract_balanced_div(block_html, txt_m.start())
        safe_html = sanitize_telegram_html(raw_text_html)
        plain_text = html_lib.unescape(re.sub(r"<[^>]+>", " ", safe_html)).strip()
        plain_text = re.sub(r"\s+", " ", plain_text)

        # Дата и просмотры
        dt_m = re.search(r'<time[^>]+datetime="([^"]+)"', block_html, re.IGNORECASE)
        published_at = dt_m.group(1) if dt_m else ""
        vw_m = re.search(r'<span[^>]+class="[^"]*tgme_widget_message_views[^"]*"[^>]*>(.*?)</span>', block_html, re.IGNORECASE | re.S)
        views = html_lib.unescape(vw_m.group(1)).strip() if vw_m else ""

        media_list: List[Dict[str, Any]] = []
        seen_urls: set[str] = set()

        # GIF / MP4 видео + постер
        for vid_m in re.finditer(r'<video[^>]+src="([^"]+)"[^>]*>', block_html, re.IGNORECASE):
            v_url = html_lib.unescape(vid_m.group(1)).strip()
            if not is_allowed_telegram_media_url(v_url) or v_url in seen_urls:
                continue
            seen_urls.add(v_url)
            mid = _media_id_for_url(v_url)
            media_reg[mid] = {"url": v_url, "kind": "gif"}

            poster_proxy = None
            thumb_m = re.search(
                r'tgme_widget_message_video_thumb[^>]+background-image:url\([\'"]?([^\'"\)]+)[\'"]?\)',
                block_html,
                re.IGNORECASE,
            )
            if thumb_m:
                p_url = html_lib.unescape(thumb_m.group(1)).strip()
                if is_allowed_telegram_media_url(p_url):
                    pid = _media_id_for_url(p_url)
                    media_reg[pid] = {"url": p_url, "kind": "photo"}
                    poster_proxy = f"/api/v1/news/media/{pid}"

            media_list.append({
                "id": mid,
                "type": "gif",
                "url": f"/api/v1/news/media/{mid}",
                "poster_url": poster_proxy,
            })

        # Фотографии (tgme_widget_message_photo_wrap)
        for ph_m in re.finditer(
            r'tgme_widget_message_photo_wrap[^>]+background-image:url\([\'"]?([^\'"\)]+)[\'"]?\)',
            block_html,
            re.IGNORECASE,
        ):
            ph_url = html_lib.unescape(ph_m.group(1)).strip()
            if not is_allowed_telegram_media_url(ph_url) or ph_url in seen_urls:
                continue
            seen_urls.add(ph_url)
            mid = _media_id_for_url(ph_url)
            media_reg[mid] = {"url": ph_url, "kind": "photo"}
            media_list.append({
                "id": mid,
                "type": "photo",
                "url": f"/api/v1/news/media/{mid}",
            })

        if not safe_html and not media_list:
            continue

        posts.append({
            "post_id": post_id,
            "channel": channel,
            "url": f"https://t.me/{channel}/{post_id}",
            "published_at": published_at,
            "views": views,
            "html": safe_html,
            "text": plain_text,
            "media": media_list,
        })

    posts.sort(key=lambda p: p["post_id"], reverse=True)
    return posts, media_reg


def _is_valid_media_bytes(data: bytes, ctype: str) -> bool:
    """Проверяет непустоту и magic bytes для JPEG/PNG/WebP/GIF/MP4 (отсекает HTML-заглушки CDN)."""
    if not data or len(data) < 12:
        return False
    if ctype.startswith("text/") or "html" in ctype or "json" in ctype:
        return False
    head = data[:16]
    if head.startswith(b"\xff\xd8\xff"):  # JPEG
        return True
    if head.startswith(b"\x89PNG\r\n\x1a\n"):  # PNG
        return True
    if head.startswith(b"GIF87a") or head.startswith(b"GIF89a"):  # GIF
        return True
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":  # WebP
        return True
    if b"ftyp" in head[:12]:  # MP4 / ISO BMFF
        return True
    return ctype.startswith("image/") or ctype.startswith("video/")


class NewsFeedService:
    """Сервис ленты новостей @itheprison с TTL-кэшем, stale-while-revalidate и LRU-кэшем медиа."""

    def __init__(self) -> None:
        self.media_dir = Path("storage") / "news_media"
        self.media_dir.mkdir(parents=True, exist_ok=True)
        self._posts_cache: List[Dict[str, Any]] = []
        self._media_registry: Dict[str, Dict[str, str]] = {}
        self._cache_ts: float = 0.0
        self._fetch_lock = asyncio.Lock()
        self._bg_task: Optional[asyncio.Task] = None

    def register_media(self, media_reg: Dict[str, Dict[str, str]]) -> None:
        self._media_registry.update(media_reg)

    async def _fetch_from_telegram(self, channel: str, before: Optional[int] = None) -> List[Dict[str, Any]]:
        url = f"https://t.me/s/{channel}"
        if before and int(before) > 0:
            url = f"{url}?before={int(before)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        }
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            posts, reg = parse_telegram_channel_html(resp.text, channel=channel)
            self.register_media(reg)
            return posts

    async def _fetch_filtered_batch(
        self,
        channel: str,
        *,
        limit: int,
        before: Optional[int] = None,
        max_pages: int = 3,
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """Загружает посты с t.me/s/<channel>, применяет фильтр и дедупликацию, дозагружая более ранние страницы при необходимости."""
        collected: List[Dict[str, Any]] = []
        cur_before = before
        has_more = False
        for _ in range(max_pages):
            raw_posts = await self._fetch_from_telegram(channel, before=cur_before)
            if not raw_posts:
                has_more = False
                break
            filtered = [p for p in raw_posts if is_game_news_post(p)]
            collected = deduplicate_news_posts(collected + filtered)
            min_id = min((int(p["post_id"]) for p in raw_posts if p.get("post_id") is not None), default=0)
            has_more = len(raw_posts) >= 5 and min_id > 1
            if len(collected) >= limit or not has_more:
                break
            cur_before = min_id
        return collected, has_more

    async def get_feed(
        self,
        *,
        limit: Optional[int] = None,
        before: Optional[int] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        channel = getattr(settings, "NEWS_CHANNEL_USERNAME", "itheprison") or "itheprison"
        ttl = int(getattr(settings, "NEWS_CACHE_TTL_SEC", 300) or 300)
        eff_limit = max(1, min(30, int(limit or getattr(settings, "NEWS_PAGE_LIMIT_DEFAULT", 12))))
        now = time.monotonic()

        if before:
            try:
                older, has_more = await self._fetch_filtered_batch(channel, limit=eff_limit, before=int(before))
                return {
                    "success": True,
                    "channel": channel,
                    "posts": older[:eff_limit],
                    "has_more": has_more or len(older) > eff_limit,
                    "cached_at": int(time.time()),
                }
            except Exception as e:
                logger.warning("NewsFeedService pagination fetch failed: %s", e)
                return {"success": True, "channel": channel, "posts": [], "has_more": False, "error": str(e)}

        is_fresh = bool(self._posts_cache and (now - self._cache_ts) < ttl and not force_refresh)
        if is_fresh:
            deduped = deduplicate_news_posts([p for p in self._posts_cache if is_game_news_post(p)])
            return {
                "success": True,
                "channel": channel,
                "posts": deduped[:eff_limit],
                "has_more": len(deduped) > eff_limit or len(deduped) >= 5,
                "cached_at": int(time.time()),
            }

        # Stale-while-revalidate: отдаем кэш мгновенно, обновляем в фоне
        if self._posts_cache and not force_refresh:
            if self._bg_task is None or self._bg_task.done():
                self._bg_task = asyncio.create_task(self._refresh_cache(channel, eff_limit))
            deduped = deduplicate_news_posts([p for p in self._posts_cache if is_game_news_post(p)])
            return {
                "success": True,
                "channel": channel,
                "posts": deduped[:eff_limit],
                "has_more": len(deduped) > eff_limit or len(deduped) >= 5,
                "cached_at": int(time.time()),
                "stale": True,
            }

        await self._refresh_cache(channel, eff_limit)
        deduped = deduplicate_news_posts([p for p in self._posts_cache if is_game_news_post(p)])
        return {
            "success": True,
            "channel": channel,
            "posts": deduped[:eff_limit],
            "has_more": len(deduped) > eff_limit or len(deduped) >= 5,
            "cached_at": int(time.time()),
        }

    async def _refresh_cache(self, channel: str, limit: int = 12) -> None:
        async with self._fetch_lock:
            try:
                posts, _ = await self._fetch_filtered_batch(channel, limit=max(limit, 12))
                if posts:
                    self._posts_cache = deduplicate_news_posts(posts)
                    self._cache_ts = time.monotonic()
            except Exception as e:
                logger.warning("NewsFeedService refresh failed for @%s: %s", channel, e)

    def _prune_media_lru(self) -> None:
        max_bytes = int(getattr(settings, "NEWS_MEDIA_CACHE_MAX_MB", 64) or 64) * 1024 * 1024
        files = [p for p in self.media_dir.iterdir() if p.is_file() and not p.name.endswith(".json")]
        total = sum(p.stat().st_size for p in files)
        if total <= max_bytes:
            return
        files.sort(key=lambda p: p.stat().st_mtime)
        for p in files:
            if total <= max_bytes:
                break
            sz = p.stat().st_size
            try:
                p.unlink()
                meta_p = p.with_suffix(".meta.json")
                if meta_p.exists():
                    meta_p.unlink()
                total -= sz
            except Exception:
                pass

    async def get_or_fetch_media(self, media_id: str) -> Tuple[Optional[Path], str]:
        """Возвращает (path_on_disk, content_type) для media_id или (None, '') при ошибке/недопустимом ID."""
        if not re.fullmatch(r"[a-f0-9]{24}", str(media_id)):
            return None, ""

        self.media_dir.mkdir(parents=True, exist_ok=True)
        for existing in self.media_dir.glob(f"{media_id}.*"):
            if existing.name.endswith(".meta.json"):
                continue
            meta_p = existing.with_suffix(".meta.json")
            ctype = "application/octet-stream"
            if meta_p.exists():
                try:
                    ctype = json.loads(meta_p.read_text(encoding="utf-8")).get("content_type", ctype)
                except Exception:
                    pass
            existing.touch()
            return existing, ctype

        info = self._media_registry.get(media_id)
        if not info or not is_allowed_telegram_media_url(info.get("url", "")):
            return None, ""

        target_url = html_lib.unescape(info["url"]).strip().strip('"').strip("'")
        if not is_allowed_telegram_media_url(target_url):
            return None, ""
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                resp = await client.get(target_url, headers={"User-Agent": "Mozilla/5.0"})
                resp.raise_for_status()
                ctype = (resp.headers.get("content-type") or "application/octet-stream").split(";")[0].strip().lower()
                if not _is_valid_media_bytes(resp.content, ctype):
                    logger.warning("NewsFeedService rejected invalid media (%s, ctype=%s, len=%s)", media_id, ctype, len(resp.content))
                    return None, ""
                ext = ".mp4" if "mp4" in ctype or info.get("kind") == "gif" else (".webp" if "webp" in ctype else (".png" if "png" in ctype else ".jpg"))
                out_path = self.media_dir / f"{media_id}{ext}"
                out_path.write_bytes(resp.content)
                out_path.with_suffix(".meta.json").write_text(
                    json.dumps({"content_type": ctype, "url": target_url}),
                    encoding="utf-8",
                )
                self._prune_media_lru()
                return out_path, ctype
        except Exception as e:
            logger.warning("NewsFeedService media download error (%s): %s", media_id, e)
            return None, ""


news_feed_service = NewsFeedService()
