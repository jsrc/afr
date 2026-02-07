# AFR Pusher

把 AFR 新闻标题抓下来，翻译后合并成一条消息，发送到微信。

默认行为：
1. 每次抓最新 10 条标题
2. 翻译方向 `EN -> ZH`
3. 10 条标题合并成 1 条消息发送

支持两种发送通道：
1. 企业微信 Webhook（官方）
2. 桌面微信自动化脚本（仓库内置 `./scripts/send.sh`）

## 运行前准备

1. Python 3.9+
2. DeepL API Key
3. 如果用桌面微信发送：
- macOS 已安装并登录微信
- 已安装 `peekaboo`
- 给运行终端授予“辅助功能”权限（Accessibility）

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
cp .env.example .env
```

打开 `.env`，至少改这几个：

```env
DEEPL_API_KEY=你的_deepl_key
WECHAT_TARGET=你的微信联系人名
```

### 常见配置示例

抓 AFR 首页（默认）：

```env
AFR_HOMEPAGE_URL=https://www.afr.com
AFR_ARTICLE_PATH_PREFIX=
```

抓 Markets Live 列表（推荐这样配）：

```env
AFR_HOMEPAGE_URL=https://www.afr.com/topic/markets-live-1po
AFR_ARTICLE_PATH_PREFIX=/markets/equity-markets/
```

发送通道二选一（可同时配，失败自动降级）：

```env
# 官方通道（可选）
WECOM_WEBHOOK_URL=

# 桌面微信脚本通道（默认已指向仓库内脚本）
DESKTOP_SEND_SCRIPT=./scripts/send.sh
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

定时循环运行（每 10 分钟）：

```bash
python3 -m afr_pusher --loop --interval-sec 600 --log-level INFO
```

## 4. 怎么判断是否成功

看日志里这两行：

1. `sending batch message: items=10 ...`（表示本轮合并了 10 条）
2. `run complete: fetched=10 sent=10 failed=0 skipped=0`（表示流程成功）

## 5. 常见问题

桌面发送失败，提示脚本错误：
1. 确认微信客户端正在运行
2. 确认 `peekaboo` 可用（`which peekaboo`）
3. 给终端开辅助功能权限（System Settings -> Privacy & Security -> Accessibility）

只收到 1 条标题：
1. 检查命令是否用了 `--max-articles 1`
2. 检查来源页是否确实只有 1 条符合过滤条件
3. 查看日志里 `sending batch message: items=...` 的实际值
