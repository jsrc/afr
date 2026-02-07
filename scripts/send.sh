#!/bin/bash

# WeChat Send Script
# Usage:
#   ./send.sh <contact_name> <message_text>
#   echo "message" | ./send.sh <contact_name>

set -euo pipefail

CONTACT_NAME="${1:-}"
shift || true

if [[ -z "$CONTACT_NAME" ]]; then
  echo "Usage: $0 <contact_name> [message_text]"
  exit 1
fi

MESSAGE_TEXT=""
if [[ "$#" -gt 0 ]]; then
  MESSAGE_TEXT="$*"
elif [[ ! -t 0 ]]; then
  MESSAGE_TEXT="$(cat)"
fi

if [[ -z "$MESSAGE_TEXT" ]]; then
  echo "Error: message text is empty"
  exit 1
fi

if ! pgrep -x "WeChat" >/dev/null && ! pgrep -x "微信" >/dev/null; then
  echo "Error: WeChat is not running."
  exit 1
fi

PEEKABOO="/opt/homebrew/bin/peekaboo"
if [[ ! -x "$PEEKABOO" ]]; then
  PEEKABOO="$(command -v peekaboo || true)"
fi

if [[ -z "$PEEKABOO" ]]; then
  echo "Error: peekaboo not found."
  exit 1
fi

PID="$(pgrep -x WeChat | head -n 1)"
RESULT_COORDS="${WECHAT_RESULT_COORDS:-250,230}"
INPUT_COORDS="${WECHAT_INPUT_COORDS:-600,800}"

echo "Targeting WeChat PID: $PID"
echo "Sending message to '$CONTACT_NAME'..."

open -a WeChat
sleep 1

"$PEEKABOO" window set-bounds --pid "$PID" --x 100 --y 100 --width 1000 --height 800
sleep 0.5

"$PEEKABOO" hotkey --keys "cmd,f" --pid "$PID"
sleep 0.3
"$PEEKABOO" hotkey --keys "cmd,a" --pid "$PID"
sleep 0.1
"$PEEKABOO" press delete --pid "$PID"
sleep 0.1
"$PEEKABOO" paste "$CONTACT_NAME" --pid "$PID"
sleep 1.2

# Explicitly click the first search result.
"$PEEKABOO" click --coords "$RESULT_COORDS"
sleep 0.6

# Explicitly focus the message input textbox.
"$PEEKABOO" click --coords "$INPUT_COORDS"
sleep 0.3

"$PEEKABOO" paste "$MESSAGE_TEXT" --pid "$PID"
sleep 0.3
"$PEEKABOO" press return --pid "$PID"

echo "Done."
