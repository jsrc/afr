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

from ..models import Article

ARTICLE_PATH_RE = re.compile(r"/[^\s\"'#?]*-\d{8}-p[0-9a-z]+/?$", re.IGNORECASE)
ARTICLE_ID_RE = re.compile(r"-(p[0-9a-z]+)$", re.IGNORECASE)
HREF_RE = re.compile(
    r"href=[\"'](?P<href>(?:https?://www\.afr\.com)?/[^\"'#? ]*-\d{8}-p[0-9a-z]+(?:/)?)[\"']",
    re.IGNORECASE,
)
ARTICLE_BODY_MIN_LEN = 80
ARTICLE_CONTENT_MAX_CHARS = 3500


class AFRFetcher:
    def __init__(
        self,
        homepage_url: str,
        timeout_sec: float,
        user_agent: str,
        article_path_prefix: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ):
        self.homepage_url = homepage_url
        self.timeout_sec = timeout_sec
        self.user_agent = user_agent
        self.article_path_prefix = article_path_prefix.rstrip("/") if article_path_prefix else None
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})

    def fetch_recent(self, limit: int = 10) -> list[Article]:
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

        content = self._extract_article_content(soup, ld_json)

        if not title:
            return None
        if not summary:
            summary = "(No summary extracted)"

        article_id = self._extract_article_id(url)
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
        chunks: list[str] = []

        chunks.extend(self._extract_ld_article_bodies(ld_json))
        if not chunks:
            chunks.extend(self._extract_dom_paragraphs(soup, min_len=ARTICLE_BODY_MIN_LEN))
        if not chunks:
            chunks.extend(self._extract_dom_paragraphs(soup, min_len=40))

        merged = self._merge_chunks(chunks, max_chars=ARTICLE_CONTENT_MAX_CHARS)
        return merged or None

    def _extract_ld_article_bodies(self, ld_json: dict) -> list[str]:
        if not isinstance(ld_json, dict):
            return []

        chunks: list[str] = []
        direct = self._clean_text(ld_json.get("articleBody"))
        if direct:
            chunks.append(direct)

        updates = ld_json.get("liveBlogUpdate")
        if isinstance(updates, list):
            for item in updates:
                if not isinstance(item, dict):
                    continue
                body = self._clean_text(item.get("articleBody"))
                if body and len(body) >= 40:
                    chunks.append(body)

        return chunks

    def _extract_dom_paragraphs(self, soup: BeautifulSoup, min_len: int) -> list[str]:
        article = soup.find("article")
        root = article if article else soup

        chunks: list[str] = []
        for p in root.find_all("p"):
            text = self._clean_text(p.get_text(" ", strip=True))
            if not text:
                continue
            if len(text) < min_len:
                continue
            chunks.append(text)
        return chunks

    def _merge_chunks(self, chunks: list[str], max_chars: int) -> str:
        seen: set[str] = set()
        cleaned: list[str] = []
        total = 0
        sep = "\n\n"

        for chunk in chunks:
            item = self._clean_text(chunk)
            if not item or item in seen:
                continue
            seen.add(item)

            extra = len(item) if not cleaned else len(sep) + len(item)
            if total + extra > max_chars:
                break

            cleaned.append(item)
            total += extra

        return sep.join(cleaned)

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
