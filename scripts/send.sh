#!/bin/bash

# WeChat Send Script
# Usage:
#   ./send.sh <contact_name> <message_text>
#   echo "message" | ./send.sh <contact_name>
#   ./send.sh <contact_name> --image /path/to/image.png

set -euo pipefail

usage() {
  echo "Usage:"
  echo "  $0 <contact_name> <message_text>"
  echo "  echo \"message\" | $0 <contact_name>"
  echo "  $0 <contact_name> --image /path/to/image.png"
}

CONTACT_NAME="${1:-}"
shift || true

if [[ -z "$CONTACT_NAME" ]]; then
  usage
  exit 1
fi

IMAGE_PATH=""
MESSAGE_TEXT=""
if [[ "${1:-}" == "--image" ]]; then
  shift || true
  IMAGE_PATH="${1:-}"
  shift || true
  if [[ -z "$IMAGE_PATH" ]]; then
    echo "Error: image path is required after --image"
    exit 1
  fi
  if [[ "$#" -gt 0 ]]; then
    echo "Error: unexpected extra arguments after image path"
    exit 1
  fi
else
  if [[ "$#" -gt 0 ]]; then
    MESSAGE_TEXT="$*"
  elif [[ ! -t 0 ]]; then
    MESSAGE_TEXT="$(cat)"
  fi
  if [[ -z "$MESSAGE_TEXT" ]]; then
    echo "Error: message text is empty"
    exit 1
  fi
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
if [[ -z "$PID" ]]; then
  PID="$(pgrep -x 微信 | head -n 1 || true)"
fi

if [[ -z "$PID" ]]; then
  echo "Error: unable to resolve WeChat PID."
  exit 1
fi

RESULT_COORDS="${WECHAT_RESULT_COORDS:-250,230}"
INPUT_COORDS="${WECHAT_INPUT_COORDS:-600,800}"

focus_input_box() {
  # Explicitly click the first search result.
  "$PEEKABOO" click --coords "$RESULT_COORDS"
  sleep 0.6

  # Explicitly focus the message input textbox.
  "$PEEKABOO" click --coords "$INPUT_COORDS"
  sleep 0.3
}

copy_image_to_clipboard() {
  local image_path="$1"
  if [[ ! -f "$image_path" ]]; then
    echo "Error: image file not found: $image_path"
    return 1
  fi
  if ! command -v sips >/dev/null; then
    echo "Error: sips command is required for image conversion."
    return 1
  fi

  local tiff_path
  tiff_path="$(mktemp /tmp/wechat-send-image.XXXXXX.tiff)"

  if ! sips -s format tiff "$image_path" --out "$tiff_path" >/dev/null 2>&1; then
    rm -f "$tiff_path"
    echo "Error: failed to convert image to TIFF."
    return 1
  fi

  if ! osascript - "$tiff_path" <<'OSA'
on run argv
  set imagePath to POSIX file (item 1 of argv)
  set the clipboard to (read imagePath as TIFF picture)
end run
OSA
  then
    rm -f "$tiff_path"
    echo "Error: failed to copy image into clipboard."
    return 1
  fi

  rm -f "$tiff_path"
}

echo "Targeting WeChat PID: $PID"
if [[ -n "$IMAGE_PATH" ]]; then
  echo "Sending image to '$CONTACT_NAME'..."
else
  echo "Sending message to '$CONTACT_NAME'..."
fi

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

focus_input_box

if [[ -n "$IMAGE_PATH" ]]; then
  copy_image_to_clipboard "$IMAGE_PATH"
  sleep 0.2
  "$PEEKABOO" hotkey --keys "cmd,v" --pid "$PID"
  sleep 0.4
  "$PEEKABOO" press return --pid "$PID"
else
  "$PEEKABOO" paste "$MESSAGE_TEXT" --pid "$PID"
  sleep 0.3
  "$PEEKABOO" press return --pid "$PID"
fi

echo "Done."
