# AFR WeChat Mini Program

This folder contains a native WeChat Mini Program frontend for the AFR pipeline.

## 1. Start backend JSON API

Recommended FastAPI command (from project root):

```bash
AFR_MINIAPP_DB_PATH=./data/afr_pusher.db \
MINIAPP_API_KEY=your_secret \
MINIAPP_API_CORS_ORIGINS=https://mini.example.com \
python3 -m uvicorn afr_pusher.miniapp_api:create_app --factory --host 127.0.0.1 --port 8000 --reload
```

Or use project CLI wrapper:

```bash
python3 -m afr_pusher --serve-api --api-host 127.0.0.1 --api-port 8000
```

FastAPI docs:

```text
http://127.0.0.1:8000/docs
```

Available endpoints:

1. `GET /health`
2. `GET /api/articles?limit=20&status=sent` (requires header `X-API-Key`)
3. `GET /api/articles/{record_key}` (requires header `X-API-Key`)

## 2. Open this project in WeChat DevTools

1. Open WeChat DevTools
2. Import this folder: `miniapp/`
3. Keep AppID as `touristappid` for local preview (or replace with your real AppID)
4. Ensure `config.js` points to your API URL
5. Set `API_KEY` in `config.js` to match backend `MINIAPP_API_KEY`

## 3. Domain notes for real device testing

1. Real device requests must use HTTPS and a whitelisted domain in mini-program settings.
2. `http://127.0.0.1:8000` is for local simulator/dev workflow only.
