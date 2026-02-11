from __future__ import annotations

import argparse
import logging
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Optional
from urllib.parse import unquote

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .store import SQLiteStore

DEFAULT_LIMIT = 20
MAX_LIMIT = 100
VALID_STATUS = {"pending", "sent", "failed"}
DEFAULT_DB_PATH = Path("./data/afr_pusher.db")
DB_PATH_ENV = "AFR_MINIAPP_DB_PATH"
API_KEY_ENV = "MINIAPP_API_KEY"
CORS_ORIGINS_ENV = "MINIAPP_API_CORS_ORIGINS"
API_KEY_HEADER = "X-API-Key"


class MiniAppArticleStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _row_to_article(row: sqlite3.Row) -> dict[str, object]:
        return {
            "record_key": str(row["record_key"]),
            "article_id": str(row["article_id"]),
            "url": str(row["url"]),
            "title": str(row["title"]),
            "summary": str(row["summary"]),
            "translated_title": str(row["translated_title"]),
            "translated_summary": str(row["translated_summary"]),
            "status": str(row["status"]),
            "sent_channel": row["sent_channel"],
            "published_at": row["published_at"],
            "updated_at": row["updated_at"],
            "created_at": str(row["created_at"]),
            "last_attempt_at": row["last_attempt_at"],
            "sent_at": row["sent_at"],
            "last_error": row["last_error"],
        }

    def list_articles(self, *, limit: int = DEFAULT_LIMIT, status: Optional[str] = None) -> list[dict[str, object]]:
        safe_limit = max(1, min(int(limit), MAX_LIMIT))
        where_sql = ""
        params: list[object] = []

        if status:
            where_sql = "WHERE status = ?"
            params.append(status)

        params.append(safe_limit)

        query = f"""
            SELECT
                record_key,
                article_id,
                url,
                title,
                summary,
                translated_title,
                translated_summary,
                status,
                sent_channel,
                published_at,
                updated_at,
                created_at,
                last_attempt_at,
                sent_at,
                last_error
            FROM article_events
            {where_sql}
            ORDER BY COALESCE(sent_at, last_attempt_at, created_at) DESC, created_at DESC
            LIMIT ?
        """

        with closing(self._connect()) as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
            return [self._row_to_article(row) for row in rows]

    def get_article(self, record_key: str) -> Optional[dict[str, object]]:
        with closing(self._connect()) as conn:
            article_row = conn.execute(
                """
                SELECT
                    record_key,
                    article_id,
                    url,
                    title,
                    summary,
                    translated_title,
                    translated_summary,
                    status,
                    sent_channel,
                    published_at,
                    updated_at,
                    created_at,
                    last_attempt_at,
                    sent_at,
                    last_error
                FROM article_events
                WHERE record_key = ?
                LIMIT 1
                """,
                (record_key,),
            ).fetchone()

            if article_row is None:
                return None

            deliveries = conn.execute(
                """
                SELECT
                    channel,
                    target,
                    success,
                    error_message,
                    response_excerpt,
                    created_at
                FROM deliveries
                WHERE record_key = ?
                ORDER BY id DESC
                LIMIT 10
                """,
                (record_key,),
            ).fetchall()

        article = self._row_to_article(article_row)
        article["deliveries"] = [
            {
                "channel": str(row["channel"]),
                "target": str(row["target"]),
                "success": bool(row["success"]),
                "error_message": row["error_message"],
                "response_excerpt": row["response_excerpt"],
                "created_at": str(row["created_at"]),
            }
            for row in deliveries
        ]
        return article


def build_app(
    *,
    db_path: Path,
    api_key: str,
    cors_origins: tuple[str, ...] = (),
    logger: Optional[logging.Logger] = None,
) -> FastAPI:
    normalized_api_key = (api_key or "").strip()
    if not normalized_api_key:
        raise ValueError("MINIAPP_API_KEY is required")

    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    # Ensure DB schema exists before serving queries.
    SQLiteStore(db_file)

    app_logger = logger or logging.getLogger("afr_pusher.miniapp_api")
    normalized_origins = tuple(origin.strip() for origin in cors_origins if origin.strip())
    store = MiniAppArticleStore(db_file)

    app = FastAPI(
        title="AFR MiniApp API",
        description="JSON API for WeChat Mini Program article browsing",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(normalized_origins),
        allow_methods=["GET", "OPTIONS"],
        allow_headers=[API_KEY_HEADER, "Content-Type"],
    )
    if not normalized_origins:
        app_logger.warning("CORS whitelist is empty; browser cross-origin requests will be rejected")

    @app.middleware("http")
    async def api_key_guard(request: Request, call_next):
        if request.url.path.startswith("/api/"):
            provided = (request.headers.get(API_KEY_HEADER) or "").strip()
            if provided != normalized_api_key:
                return JSONResponse(status_code=401, content={"ok": False, "error": "unauthorized"})
        return await call_next(request)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        error_message = exc.detail if isinstance(exc.detail, str) else "request_error"
        return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": error_message})

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        message = str(exc.errors()[0].get("msg", "validation_error")) if exc.errors() else "validation_error"
        return JSONResponse(status_code=422, content={"ok": False, "error": message})

    @app.exception_handler(sqlite3.Error)
    async def sqlite_exception_handler(_: Request, exc: sqlite3.Error) -> JSONResponse:
        app_logger.exception("api sqlite error")
        return JSONResponse(status_code=500, content={"ok": False, "error": "internal_error"})

    @app.get("/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/articles")
    def list_articles(
        limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
        status: Optional[str] = Query(default=None),
    ) -> dict[str, object]:
        normalized_status = (status or "").strip().lower() or None
        if normalized_status is not None and normalized_status not in VALID_STATUS:
            raise HTTPException(status_code=400, detail="status must be pending, sent, or failed")

        items = store.list_articles(limit=limit, status=normalized_status)
        return {
            "ok": True,
            "items": items,
            "count": len(items),
            "limit": limit,
            "status": normalized_status,
        }

    @app.get("/api/articles/{record_key:path}")
    def get_article(record_key: str) -> dict[str, object]:
        normalized_key = unquote(record_key).strip()
        if not normalized_key:
            raise HTTPException(status_code=400, detail="record_key required")

        item = store.get_article(normalized_key)
        if item is None:
            raise HTTPException(status_code=404, detail="not_found")

        return {"ok": True, "item": item}

    return app


def _resolve_db_path(db_path: Optional[Path] = None) -> Path:
    if db_path is not None:
        return Path(db_path)
    env_value = (os.getenv(DB_PATH_ENV) or "").strip()
    if env_value:
        return Path(env_value).expanduser()
    return DEFAULT_DB_PATH


def _parse_cors_origins(raw: str) -> tuple[str, ...]:
    text = raw.strip()
    if not text:
        return ()
    return tuple(part.strip() for part in text.split(",") if part.strip())


def _resolve_api_key(api_key: Optional[str] = None) -> str:
    if api_key is not None and api_key.strip():
        return api_key.strip()
    env_value = (os.getenv(API_KEY_ENV) or "").strip()
    if env_value:
        return env_value
    raise ValueError("MINIAPP_API_KEY is required")


def _resolve_cors_origins(cors_origins: Optional[str] = None) -> tuple[str, ...]:
    if cors_origins is not None:
        return _parse_cors_origins(cors_origins)
    return _parse_cors_origins(os.getenv(CORS_ORIGINS_ENV, ""))


def create_app() -> FastAPI:
    """
    Uvicorn factory entrypoint.
    Example:
      AFR_MINIAPP_DB_PATH=./data/afr_pusher.db \
      MINIAPP_API_KEY=your_secret \
      python3 -m uvicorn afr_pusher.miniapp_api:create_app --factory --host 127.0.0.1 --port 8000 --reload
    """
    return build_app(
        db_path=_resolve_db_path(),
        api_key=_resolve_api_key(),
        cors_origins=_resolve_cors_origins(),
        logger=logging.getLogger("afr_pusher.miniapp_api"),
    )


def run_miniapp_api_server(
    *,
    db_path: Path,
    api_key: str,
    cors_origins: tuple[str, ...] = (),
    host: str = "127.0.0.1",
    port: int = 8000,
    logger: Optional[logging.Logger] = None,
) -> None:
    if port < 1 or port > 65535:
        raise ValueError("port must be in [1, 65535]")

    db_file = _resolve_db_path(db_path)
    app_logger = logger or logging.getLogger("afr_pusher.miniapp_api")
    app = build_app(
        db_path=db_file,
        api_key=_resolve_api_key(api_key),
        cors_origins=cors_origins,
        logger=app_logger,
    )
    app_logger.info("miniapp api started: http://%s:%s (db=%s)", host, port, db_file)

    uvicorn.run(app, host=host, port=port, log_level="info")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve AFR data as JSON for WeChat Mini Program")
    parser.add_argument("--db-path", default="./data/afr_pusher.db", help="SQLite file path")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=8000, help="Bind port")
    parser.add_argument("--api-key", default=None, help=f"API key (or set {API_KEY_ENV})")
    parser.add_argument(
        "--cors-origins",
        default=None,
        help=f"Comma-separated CORS origins whitelist (or set {CORS_ORIGINS_ENV})",
    )
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    run_miniapp_api_server(
        db_path=Path(args.db_path),
        api_key=_resolve_api_key(args.api_key),
        cors_origins=_resolve_cors_origins(args.cors_origins),
        host=args.host,
        port=args.port,
        logger=logging.getLogger("afr_pusher.miniapp_api"),
    )


if __name__ == "__main__":
    main()
