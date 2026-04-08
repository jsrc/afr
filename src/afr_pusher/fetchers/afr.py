from __future__ import annotations

import html as html_lib
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Iterable, Optional
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from ..message import serialize_content_blocks
from ..models import Article, ArticleBlock

ARTICLE_PATH_RE = re.compile(r"/[^\s\"'#?]*-\d{8}-p[0-9a-z]+/?$", re.IGNORECASE)
ARTICLE_ID_RE = re.compile(r"-(p[0-9a-z]+)$", re.IGNORECASE)
HREF_RE = re.compile(
    r"href=[\"'](?P<href>(?:https?://www\.afr\.com)?/[^\"'#? ]*-\d{8}-p[0-9a-z]+(?:/)?)[\"']",
    re.IGNORECASE,
)
ARTICLE_BODY_MIN_LEN = 80
ARTICLE_CONTENT_MAX_CHARS = 3500
CONTENT_API_URL_TEMPLATE = "https://api.afr.com/api/content/v0/assets/{article_id}"
LIST_ITEM_PREFIX_RE = re.compile(r"^(?:[-*•]\s+)(.+)$")


class AFRFetcher:
    def __init__(
        self,
        homepage_url: str,
        timeout_sec: float,
        user_agent: str,
        article_path_prefix: Optional[str] = None,
        prefer_content_api: bool = False,
        session: Optional[requests.Session] = None,
    ):
        self.homepage_url = homepage_url
        self.timeout_sec = timeout_sec
        self.user_agent = user_agent
        self.article_path_prefix = article_path_prefix.rstrip("/") if article_path_prefix else None
        self.prefer_content_api = prefer_content_api
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})

    def fetch_recent(self, limit: int = 1) -> list[Article]:
        homepage_html = self._get_text(self.homepage_url)
        article_urls = self._extract_article_urls(homepage_html)

        articles: list[Article] = []
        scan_limit = max(limit * 4, limit, 20)
        for url in article_urls[:scan_limit]:
            try:
                article = self._fetch_article(url)
            except Exception:
                continue
            if article:
                articles.append(article)

        articles.sort(
            key=lambda item: (item.updated_at or item.published_at or ""),
            reverse=True,
        )
        return articles[: max(limit, 0)]

    def _get_text(self, url: str) -> str:
        response = self.session.get(url, timeout=self.timeout_sec)
        response.raise_for_status()
        return response.text

    def _get_json(self, url: str) -> dict:
        response = self.session.get(url, timeout=self.timeout_sec)
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}

    def _extract_article_urls(self, html: str) -> list[str]:
        raw_urls = [match.group("href") for match in HREF_RE.finditer(html)]
        normalized = []
        seen: set[str] = set()

        for raw in raw_urls:
            absolute = urljoin("https://www.afr.com", raw)
            parsed = urlparse(absolute)
            clean_path = parsed.path.rstrip("/")
            if not ARTICLE_PATH_RE.search(clean_path):
                continue
            if self.article_path_prefix and not clean_path.startswith(self.article_path_prefix):
                continue
            clean = urlunparse((parsed.scheme, parsed.netloc, clean_path, "", "", ""))
            if clean in seen:
                continue
            seen.add(clean)
            normalized.append(clean)

        return normalized

    def _fetch_article(self, url: str) -> Optional[Article]:
        html = self._get_text(url)
        soup = BeautifulSoup(html, "html.parser")
        ld_json = self._extract_ld_json(soup)

        title = self._meta_content(soup, "property", "og:title") or self._safe_title(soup)
        summary = self._meta_content(soup, "name", "description") or self._meta_content(
            soup, "property", "og:description"
        )

        published_at = self._extract_datetime(soup, "article:published_time")
        updated_at = self._extract_datetime(soup, "article:modified_time")

        if not title or not summary:
            title = title or ld_json.get("headline") or ld_json.get("name")
            summary = summary or ld_json.get("description")
            published_at = published_at or self._normalize_dt(ld_json.get("datePublished"))
            updated_at = updated_at or self._normalize_dt(ld_json.get("dateModified"))

        if not title:
            return None
        if not summary:
            summary = "(No summary extracted)"

        article_id = self._extract_article_id(url)
        content_blocks = self._extract_preferred_content_blocks(soup, ld_json, article_id)
        content = serialize_content_blocks(content_blocks) or None
        record_key = f"{article_id}:{updated_at or published_at or 'na'}"

        return Article(
            article_id=article_id,
            record_key=record_key,
            url=url,
            title=title.strip(),
            summary=summary.strip(),
            published_at=published_at,
            updated_at=updated_at,
            content=content,
            content_blocks=content_blocks,
        )

    def _safe_title(self, soup: BeautifulSoup) -> Optional[str]:
        if soup.title and soup.title.string:
            return soup.title.string.strip()
        return None

    def _meta_content(self, soup: BeautifulSoup, attr_key: str, attr_value: str) -> Optional[str]:
        tag = soup.find("meta", attrs={attr_key: attr_value})
        if tag and tag.get("content"):
            return str(tag.get("content")).strip()
        return None

    def _extract_datetime(self, soup: BeautifulSoup, meta_property: str) -> Optional[str]:
        value = self._meta_content(soup, "property", meta_property)
        return self._normalize_dt(value)

    def _extract_article_id(self, url: str) -> str:
        path = urlparse(url).path.rstrip("/")
        match = ARTICLE_ID_RE.search(path)
        if match:
            return match.group(1).lower()
        return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]

    def _extract_ld_json(self, soup: BeautifulSoup) -> dict:
        scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
        for script in scripts:
            text = script.string or script.text
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                continue

            for candidate in self._iter_candidates(payload):
                if not isinstance(candidate, dict):
                    continue
                typename = str(candidate.get("@type", "")).lower()
                if typename in {
                    "newsarticle",
                    "article",
                    "reportagearticle",
                    "analysisnewsarticle",
                    "liveblogposting",
                    "blogposting",
                }:
                    return candidate
        return {}

    def _extract_article_content(self, soup: BeautifulSoup, ld_json: dict) -> Optional[str]:
        content = serialize_content_blocks(self._extract_article_content_blocks(soup, ld_json))
        return content or None

    def _extract_preferred_content_blocks(
        self,
        soup: BeautifulSoup,
        ld_json: dict,
        article_id: str,
    ) -> tuple[ArticleBlock, ...]:
        if self.prefer_content_api:
            try:
                api_blocks = self._extract_content_api_blocks(article_id)
            except Exception:
                api_blocks = ()
            if api_blocks:
                return api_blocks
        return self._extract_article_content_blocks(soup, ld_json)

    def _extract_article_content_blocks(self, soup: BeautifulSoup, ld_json: dict) -> tuple[ArticleBlock, ...]:
        blocks: list[ArticleBlock] = []

        blocks.extend(self._extract_ld_article_blocks(ld_json))
        if not blocks:
            blocks.extend(self._extract_dom_blocks(soup, min_len=ARTICLE_BODY_MIN_LEN))
        if not blocks:
            blocks.extend(self._extract_dom_blocks(soup, min_len=40))

        return self._merge_blocks(blocks, max_chars=ARTICLE_CONTENT_MAX_CHARS)

    def _extract_content_api_blocks(self, article_id: str) -> tuple[ArticleBlock, ...]:
        if not article_id:
            return ()

        payload = self._get_json(CONTENT_API_URL_TEMPLATE.format(article_id=article_id))
        asset = payload.get("asset")
        if not isinstance(asset, dict):
            return ()

        body_html = asset.get("body")
        if not isinstance(body_html, str) or not body_html.strip():
            return ()

        blocks = self._extract_html_fragment_blocks(body_html, min_len=1)
        return self._merge_blocks(blocks, max_chars=ARTICLE_CONTENT_MAX_CHARS)

    def _extract_ld_article_blocks(self, ld_json: dict) -> list[ArticleBlock]:
        if not isinstance(ld_json, dict):
            return []

        blocks: list[ArticleBlock] = []
        blocks.extend(self._blocks_from_text(ld_json.get("articleBody"), min_len=1))

        updates = ld_json.get("liveBlogUpdate")
        if isinstance(updates, list):
            for item in updates:
                if not isinstance(item, dict):
                    continue
                body_blocks = self._blocks_from_text(item.get("articleBody"), min_len=40)
                blocks.extend(body_blocks)

        return blocks

    def _extract_dom_blocks(self, soup: BeautifulSoup, min_len: int) -> list[ArticleBlock]:
        article = soup.find("article")
        root = article if article else soup
        return self._extract_block_nodes(root.find_all(["p", "li"]), min_len=min_len)

    def _extract_html_fragment_blocks(self, html_fragment: str, min_len: int) -> list[ArticleBlock]:
        fragment = BeautifulSoup(html_fragment, "html.parser")
        return self._extract_block_nodes(fragment.find_all(["p", "li", "h2", "h3"]), min_len=min_len)

    def _extract_block_nodes(self, nodes: Iterable[object], min_len: int) -> list[ArticleBlock]:
        blocks: list[ArticleBlock] = []
        for node in nodes:
            text_getter = getattr(node, "get_text", None)
            if text_getter is None:
                continue
            text = self._clean_text(text_getter(" ", strip=True))
            if not text:
                continue
            if len(text) < min_len:
                continue
            kind = "list_item" if getattr(node, "name", "") == "li" else "paragraph"
            blocks.append(ArticleBlock(kind=kind, text=text))
        return blocks

    def _merge_blocks(self, blocks: list[ArticleBlock], max_chars: int) -> tuple[ArticleBlock, ...]:
        seen: set[tuple[str, str]] = set()
        cleaned: list[ArticleBlock] = []
        total = 0
        separator = 2

        for block in blocks:
            item = self._clean_text(block.text)
            dedupe_key = (block.kind, item)
            if not item or dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            extra = len(item) if not cleaned else separator + len(item)
            if total + extra > max_chars:
                break

            cleaned.append(ArticleBlock(kind=block.kind, text=item))
            total += extra

        return tuple(cleaned)

    def _blocks_from_text(self, value: object, min_len: int = ARTICLE_BODY_MIN_LEN) -> list[ArticleBlock]:
        if not isinstance(value, str):
            return []

        text = html_lib.unescape(value).replace("\r\n", "\n").replace("\r", "\n")
        pieces = [piece.strip() for piece in re.split(r"\n\s*\n+", text) if piece.strip()]
        if len(pieces) <= 1:
            pieces = [piece.strip() for piece in text.splitlines() if piece.strip()]
        if len(pieces) <= 1:
            pieces = [text.strip()]

        blocks: list[ArticleBlock] = []
        for piece in pieces:
            match = LIST_ITEM_PREFIX_RE.match(piece)
            kind = "list_item" if match else "paragraph"
            payload = match.group(1) if match else piece
            cleaned = self._clean_text(payload)
            if cleaned and len(cleaned) >= min_len:
                blocks.append(ArticleBlock(kind=kind, text=cleaned))
        return blocks

    def _clean_text(self, value: object) -> str:
        if not isinstance(value, str):
            return ""
        text = html_lib.unescape(value)
        text = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
        return " ".join(text.split())

    def _iter_candidates(self, payload: object) -> Iterable[object]:
        if isinstance(payload, list):
            for item in payload:
                yield item
            return

        if isinstance(payload, dict):
            if "@graph" in payload and isinstance(payload["@graph"], list):
                for item in payload["@graph"]:
                    yield item
                return
            yield payload

    def _normalize_dt(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None

        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
