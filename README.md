# AFR Pusher

把 AFR 新闻标题抓下来，翻译后合并成一条消息，发送到微信或 Telegram。

默认行为：
1. 每次抓最新 10 条标题
2. 翻译方向 `EN -> ZH`
3. 10 条标题合并成 1 条消息发送
4. 当 `--max-articles 1`（或 `AFR_MAX_ARTICLES=1`）时，发送“标题 + 正文翻译”

支持三种发送通道：
1. Telegram Bot API
2. 企业微信 Webhook（官方）
3. 桌面微信自动化脚本（仓库内置 `./scripts/send.sh`）

## 首图摘要卡片（最小版）

开启后会先生成一张竖版摘要图片（默认 `1080x1620`），再继续发送文本消息：

```ini
PREVIEW_ENABLED=true
PREVIEW_OUTPUT_DIR=./data/previews
PREVIEW_MAX_TITLES=3
```

说明：
1. 图片会落地到 `PREVIEW_OUTPUT_DIR`
2. 发送顺序是“先图片，后文本”
3. 企业微信 Webhook 支持图片消息；如果当前发送通道不支持图片，会记录日志，但不影响文本发送

## 运行前准备

1. Python 3.9+
2. DeepL API Key
3. 如果用桌面微信发送：
- macOS 已安装并登录微信
- 已安装 `peekaboo`
- 给运行终端授予“辅助功能”权限（Accessibility）
- 若要发送图片，`osascript` 和 `sips` 需可用（macOS 默认自带）

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
2. `.env`：敏感信息（例如 `DEEPL_API_KEY`、`TELEGRAM_BOT_TOKEN`），并覆盖 `config.ini` 同名项

优先级（高 -> 低）：
1. 命令行参数
2. 进程环境变量
3. `.env`
4. `config.ini`
5. 代码默认值

先在 `.env` 至少填写 DeepL Key：

```env
DEEPL_API_KEY=你的_deepl_key
```

### 常见配置示例

抓 AFR 首页（默认）：

```ini
AFR_HOMEPAGE_URL=https://www.afr.com
AFR_ARTICLE_PATH_PREFIX=
```

抓 Markets Live 列表（推荐这样配）：

```ini
AFR_HOMEPAGE_URL=https://www.afr.com/topic/markets-live-1po
AFR_ARTICLE_PATH_PREFIX=/markets/equity-markets/
```

发送通道配置（可同时配，当前为“主通道 + 一级降级”）：
1. 配了 Telegram 时：主通道是 Telegram，降级到 WeCom（若未配 WeCom，则降级到桌面脚本）
2. 未配 Telegram 时：主通道是 WeCom，降级到桌面脚本
3. 可用命令参数 `--send-channel telegram|wecom|desktop` 显式指定通道（指定后只发该通道）

```ini
# Telegram chat_id（可配在 config.ini）
TELEGRAM_CHAT_ID=

# 官方通道（可选）
WECOM_WEBHOOK_URL=

# 桌面微信脚本通道（默认已指向仓库内脚本）
WECHAT_TARGET=你的微信联系人名
DESKTOP_SEND_SCRIPT=./scripts/send.sh
```

```env
# Telegram token 建议放 .env（敏感）
TELEGRAM_BOT_TOKEN=
```

### 获取 `TELEGRAM_CHAT_ID`（一条命令）

先做前置动作：
1. 私聊：在 Telegram 里打开你的 bot，发送 `/start` 或任意消息
2. 群聊：把 bot 拉进群后，在群里发一条消息（群 `chat_id` 一般是负数）

然后执行这条命令（把 `xxx` 换成你的 bot token）：

```bash
TELEGRAM_BOT_TOKEN=xxx; curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getUpdates" | python3 -c 'import sys,json; d=json.load(sys.stdin); rows={}; [rows.__setitem__(c.get("id"), (c.get("type",""), c.get("title") or c.get("username") or c.get("first_name") or "")) for u in d.get("result",[]) for c in [((u.get("message") or u.get("edited_message") or u.get("channel_post") or {}).get("chat") or {})] if c.get("id") is not None]; print("\\n".join(f"{cid}\\t{t}\\t{name}" for cid,(t,name) in rows.items()) or "No chat found. Send a message to the bot first, then rerun.")'
```

输出第一列就是 `chat_id`，填入 `config.ini`（或放 `.env` 覆盖同名项）：

```ini
TELEGRAM_CHAT_ID=你找到的数字ID
```

## 3. 运行

先做不发消息测试：

```bash
python3 -m afr_pusher --dry-run --max-articles 10 --log-level INFO
```

真实发送一次：

```bash
python3 -m afr_pusher --max-articles 10 --log-level INFO
```

显式指定发送通道（示例：只发企业微信）：

```bash
python3 -m afr_pusher --max-articles 10 --send-channel wecom --log-level INFO
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
这个模式需要你保持程序一直运行（关终端就会停止）。

### 推荐：安装为系统级定时任务（macOS launchd）

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

## 4. 怎么判断是否成功

看日志里这两行：

1. `sending message: mode=batch-titles items=10 ...`（表示本轮合并了 10 条标题）
   或 `sending message: mode=single-with-content items=1 ...`（表示发送 1 条“标题+正文”）
2. `run complete: fetched=10 sent=10 failed=0 skipped=0`（表示流程成功）

## 5. 常见问题

桌面发送失败，提示脚本错误：
1. 确认微信客户端正在运行
2. 确认 `peekaboo` 可用（`which peekaboo`）
3. 给终端开辅助功能权限（System Settings -> Privacy & Security -> Accessibility）

只收到 1 条标题：
1. 检查命令是否用了 `--max-articles 1`
2. 检查来源页是否确实只有 1 条符合过滤条件
3. 查看日志里 `sending message: ... items=...` 的实际值

测试桌面脚本图片发送：
1. `./scripts/send.sh 你的联系人 --image /绝对路径/preview.png`
