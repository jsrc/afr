# AFR Pusher

把 AFR 新闻标题抓下来，翻译后合并成一条消息，发送到 Telegram。

默认行为：
1. 每次抓最新 1 条文章
2. 翻译方向 `EN -> ZH`
3. 默认发送“标题 + 正文翻译”
4. 当 `--max-articles` 或 `AFR_MAX_ARTICLES` 大于 1 时，发送“标题列表汇总”
5. 支持并列推送 `main` 和 `Street Talk` 两个来源

Telegram 消息默认按 `HTML` 富文本发送：
1. 批量模式：标题列表带编号和原文链接
2. 单篇模式：标题加粗，正文按段落/要点分块排版
3. 如需回退纯文本，可将 `TELEGRAM_PARSE_MODE=` 留空

支持发送通道：
1. Telegram Bot API

## 首图摘要卡片（最小版）

开启后会先生成一张竖版摘要图片（默认 `1080x1620`），再继续发送文本消息：

```ini
PREVIEW_ENABLED=false
PREVIEW_OUTPUT_DIR=./data/previews
PREVIEW_MAX_TITLES=3
```

说明：
1. 图片会落地到 `PREVIEW_OUTPUT_DIR`
2. 发送顺序是“先图片，后文本”
3. 若当前发送通道不支持图片，会记录日志但不影响文本发送

## 运行前准备

1. Python 3.9+
2. DeepL API Key
3. Telegram Bot Token

## 1. 下载和安装

```bash
git clone <your-repo-url>
cd afr
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

## 2. 配置

复制配置文件：

```bash
cp config.ini.example config.ini
cp .env.example .env
```

默认 `.gitignore` 已忽略 `config.ini` 和 `.env`。

配置分层：
1. `config.ini`：业务参数（抓取、翻译方向、路由、运行参数等）
2. `.env`：敏感信息（例如 `DEEPL_API_KEY`、`TELEGRAM_BOT_TOKEN`、`MINIAPP_API_KEY`），并覆盖 `config.ini` 同名项
3. 建议不要重复配置同名键，避免来源混淆

Telegram 推荐放法：
1. `TELEGRAM_BOT_TOKEN` 放 `.env`
2. `TELEGRAM_CHAT_ID` 放 `config.ini`
3. 只有在你需要临时覆盖目标频道时，才把 `TELEGRAM_CHAT_ID` 也写进 `.env`

优先级（高 -> 低）：
1. 命令行参数
2. 进程环境变量
3. `.env`
4. `config.ini`
5. 代码默认值

先在 `.env` 至少填写：

```env
DEEPL_API_KEY=your_deepl_key
TELEGRAM_BOT_TOKEN=your_telegram_token
MINIAPP_API_KEY=replace_with_a_long_random_secret
```

### 常见配置示例

抓 AFR 首页（默认）：

```ini
AFR_HOMEPAGE_URL=https://www.afr.com
AFR_ARTICLE_PATH_PREFIX=
```

抓 Markets Live 列表（推荐）：

```ini
AFR_HOMEPAGE_URL=https://www.afr.com/topic/markets-live-1po
AFR_ARTICLE_PATH_PREFIX=/markets/equity-markets/
```

来源选择：

```ini
AFR_SOURCE=
AFR_STREET_TALK_HOMEPAGE_URL=https://www.afr.com/street-talk
AFR_STREET_TALK_ARTICLE_PATH_PREFIX=/street-talk
```

说明：
1. `AFR_SOURCE=` 留空时，同时推送 `main` 和 `Street Talk`
2. `AFR_SOURCE=main` 时，只推送主来源
3. `AFR_SOURCE=street-talk` 时，只推送 `Street Talk`
4. 当 `AFR_MAX_ARTICLES=1` 时，各来源分别发送最新单篇正文
5. 当 `AFR_MAX_ARTICLES>1` 时，各来源分别发送标题列表
6. 也可以临时用命令行覆盖：`--source main` 或 `--source street-talk`

发送通道配置：
1. 配置 Telegram 后直接发送到 Telegram
2. 不再包含桌面微信发送

```ini
# 推荐写在 config.ini
TELEGRAM_CHAT_ID=@your_channel
```

```env
# 推荐写在 .env
TELEGRAM_BOT_TOKEN=your_telegram_token

# 可选：只有需要覆盖 config.ini 目标频道时才写
# TELEGRAM_CHAT_ID=@another_channel
```

MiniApp API 安全配置：

```ini
MINIAPP_API_CORS_ORIGINS=https://mini.example.com
```

```env
MINIAPP_API_KEY=replace_with_a_long_random_secret
```

### 获取 `TELEGRAM_CHAT_ID`（一条命令）

先做前置动作：
1. 私聊：在 Telegram 里打开你的 bot，发送 `/start` 或任意消息
2. 群聊：把 bot 拉进群后，在群里发一条消息（群 `chat_id` 一般是负数）

然后执行这条命令（把 `xxx` 换成你的 bot token）：

```bash
TELEGRAM_BOT_TOKEN=xxx; curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getUpdates" | python3 -c 'import sys,json; d=json.load(sys.stdin); rows={}; [rows.__setitem__(c.get("id"), (c.get("type",""), c.get("title") or c.get("username") or c.get("first_name") or "")) for u in d.get("result",[]) for c in [((u.get("message") or u.get("edited_message") or u.get("channel_post") or {}).get("chat") or {})] if c.get("id") is not None]; print("\\n".join(f"{cid}\\t{t}\\t{name}" for cid,(t,name) in rows.items()) or "No chat found. Send a message to the bot first, then rerun.")'
```

输出第一列就是 `chat_id`，默认填入 `config.ini`：

```ini
TELEGRAM_CHAT_ID=你找到的数字ID
```

## 3. 运行

先做不发消息测试：

```bash
python3 -m afr_pusher --dry-run --log-level INFO
```

真实发送一次：

```bash
python3 -m afr_pusher --log-level INFO
```

定时循环运行（每 10 分钟）：

```bash
python3 -m afr_pusher --loop --interval-sec 600 --log-level INFO
```

每天固定时间运行（例如每天下午 4:30）：

```bash
python3 -m afr_pusher --daily-at 16:30 --log-level INFO
```

说明：`--daily-at` 使用本机本地时间（24 小时制 `HH:MM`）。如果同时传了 `--loop` 或 `--interval-sec`，会被忽略。

### macOS 定时（launchd）

安装每天 16:30 自动运行（终端关闭也会执行）：

```bash
python3 -m afr_pusher --install-launchd --daily-at 16:30 --log-level INFO
```

卸载该定时任务：

```bash
python3 -m afr_pusher --uninstall-launchd
```

可选：自定义任务名（label）：

```bash
python3 -m afr_pusher --install-launchd --daily-at 16:30 --launchd-label com.yourname.afr
```

launchd 日志文件（默认）：
1. `./logs/launchd.out.log`
2. `./logs/launchd.err.log`

## 4. 微信小程序 API

仓库包含原生微信小程序前端：`./miniapp`。

### 启动 JSON API

标准 FastAPI 启动（开发调试）：

```bash
AFR_MINIAPP_DB_PATH=./data/afr_pusher.db \
MINIAPP_API_KEY=your_secret \
MINIAPP_API_CORS_ORIGINS=https://mini.example.com \
python3 -m uvicorn afr_pusher.miniapp_api:create_app --factory --host 127.0.0.1 --port 8000 --reload
```

项目封装命令（生产也可用）：

```bash
python3 -m afr_pusher --serve-api --api-host 127.0.0.1 --api-port 8000
```

或入口命令：

```bash
afr-miniapi --db-path ./data/afr_pusher.db --host 127.0.0.1 --port 8000 --api-key your_secret --cors-origins https://mini.example.com
```

接口：
1. `GET /health`（无需鉴权）
2. `GET /api/articles?limit=20&status=sent`（需 `X-API-Key`）
3. `GET /api/articles/{record_key}`（需 `X-API-Key`）

### 小程序侧配置

编辑 `miniapp/config.js`：
1. `API_BASE_URL` 改为你的 HTTPS 域名
2. `API_KEY` 填入与后端一致的 key

真机调试必须使用 HTTPS，并在小程序后台配置业务域名。

## 5. Linux 生产部署（systemd + Nginx）

仓库提供模板：
1. `deploy/systemd/afr-miniapi.service`
2. `deploy/systemd/afr-pusher.service`
3. `deploy/systemd/afr-pusher.timer`
4. `deploy/nginx/afr-miniapi.conf`
### 5.1 安装 systemd 服务

```bash
sudo cp deploy/systemd/afr-miniapi.service /etc/systemd/system/
sudo cp deploy/systemd/afr-pusher.service /etc/systemd/system/
sudo cp deploy/systemd/afr-pusher.timer /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable --now afr-miniapi.service
sudo systemctl enable --now afr-pusher.timer
```

检查状态：

```bash
sudo systemctl status afr-miniapi.service
sudo systemctl status afr-pusher.timer
```

`deploy/systemd/afr-pusher.timer` 默认使用系统级固定时间调度：

```ini
OnCalendar=*-*-* 16:30:00
```

### 5.2 配置 Nginx 反向代理

```bash
sudo cp deploy/nginx/afr-miniapi.conf /etc/nginx/conf.d/afr-miniapi.conf
sudo nginx -t
sudo systemctl reload nginx
```

模板默认先安装 HTTP 反向代理，确保首次上线和 `certbot` 引导不互相卡住。
然后再用 Let’s Encrypt 申请证书（示例域名替换为你的真实域名）：

```bash
sudo certbot --nginx -d api.example.com
```

## 6. 怎么判断是否成功

看日志里这两行：
1. `sending message: mode=batch-titles items=10 ...` 或 `mode=single-with-content`
2. `run complete: fetched=10 sent=10 failed=0 skipped=0`

API 健康检查：

```bash
curl -sS https://api.example.com/health
```

API 鉴权检查：

```bash
curl -sS -H 'X-API-Key: your_secret' 'https://api.example.com/api/articles?limit=1'
```

## 7. 常见问题

只收到 1 条标题：
1. 检查是否用了 `--max-articles 1`
2. 检查来源页是否只有 1 条符合过滤条件
3. 查看日志 `sending message: ... items=...`
