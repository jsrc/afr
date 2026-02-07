from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence


def _clean_titles(titles: Sequence[str], max_titles: int) -> list[str]:
    cleaned: list[str] = []
    for title in titles:
        text = (title or "").strip()
        if text:
            cleaned.append(text)
        if len(cleaned) >= max_titles:
            break
    return cleaned


class SummaryCardRenderer:
    def __init__(
        self,
        output_dir: Path,
        max_titles: int = 3,
        width: int = 1080,
        height: int = 1620,
        logger: Optional[logging.Logger] = None,
    ):
        self.output_dir = Path(output_dir)
        self.max_titles = max(1, max_titles)
        self.width = width
        self.height = height
        self.logger = logger or logging.getLogger(__name__)

    def render(self, translated_titles: Sequence[str]) -> Optional[Path]:
        titles = _clean_titles(translated_titles, self.max_titles)
        if not titles:
            return None

        try:
            from PIL import Image, ImageDraw, ImageFont
        except Exception as exc:
            self.logger.warning("preview disabled: Pillow unavailable (%s)", exc)
            return None

        self.output_dir.mkdir(parents=True, exist_ok=True)

        image = Image.new("RGB", (self.width, self.height), "#EEF2FD")
        draw = ImageDraw.Draw(image)
        now = datetime.now()

        brand_font = self._load_font(ImageFont, 86)
        subtitle_font = self._load_font(ImageFont, 50)
        time_font = self._load_font(ImageFont, 54)
        headline_font = self._load_font(ImageFont, 72)
        body_font = self._load_font(ImageFont, 56)
        card_meta_font = self._load_font(ImageFont, 42)
        footer_font = self._load_font(ImageFont, 58)

        self._draw_background(image, draw, Image, ImageDraw)
        self._draw_header(draw, brand_font, subtitle_font)
        self._draw_content_card(
            draw=draw,
            now=now,
            titles=titles,
            time_font=time_font,
            headline_font=headline_font,
            body_font=body_font,
            card_meta_font=card_meta_font,
        )
        self._draw_footer_bar(draw, footer_font)

        output_path = self.output_dir / f"preview-{datetime.now().strftime('%Y%m%d-%H%M%S')}.png"
        image.save(output_path, format="PNG")
        return output_path

    def _draw_background(self, image, draw, image_module, image_draw_module) -> None:
        top = (228, 234, 248)
        bottom = (245, 247, 253)
        for y in range(self.height):
            ratio = y / max(1, self.height - 1)
            color = (
                int(top[0] + (bottom[0] - top[0]) * ratio),
                int(top[1] + (bottom[1] - top[1]) * ratio),
                int(top[2] + (bottom[2] - top[2]) * ratio),
            )
            draw.line((0, y, self.width, y), fill=color)

        overlay = image_module.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        overlay_draw = image_draw_module.Draw(overlay)
        overlay_draw.polygon(
            [(0, 0), (220, 0), (520, 980), (280, 980)],
            fill=(255, 255, 255, 75),
        )
        overlay_draw.polygon(
            [(830, 0), (1080, 0), (1080, 1020), (620, 560)],
            fill=(255, 255, 255, 60),
        )
        overlay_draw.polygon(
            [(550, 0), (760, 0), (1020, 980), (780, 980)],
            fill=(255, 255, 255, 40),
        )
        image.paste(overlay, (0, 0), overlay)

    def _draw_header(self, draw, brand_font, subtitle_font) -> None:
        icon_size = 94
        icon_radius = 20
        gap = 26
        top = 120

        segments = [
            ("AFR", "#1B3D8C"),
            (" · ", "#1B3D8C"),
            ("电报", "#2B6FE4"),
        ]
        text_width = sum(self._text_width(draw, text, brand_font) for text, _ in segments)
        total_width = icon_size + gap + text_width
        start_x = (self.width - total_width) // 2

        icon_left = start_x
        icon_top = top
        icon_right = icon_left + icon_size
        icon_bottom = icon_top + icon_size
        draw.rounded_rectangle(
            (icon_left, icon_top, icon_right, icon_bottom),
            radius=icon_radius,
            fill="#1B3D8C",
        )
        draw.rounded_rectangle(
            (icon_left + 18, icon_top + 18, icon_right - 18, icon_bottom - 18),
            radius=10,
            outline="#FFFFFF",
            width=7,
        )
        draw.polygon(
            [
                (icon_left + 48, icon_top + 48),
                (icon_right - 14, icon_top + 34),
                (icon_right - 34, icon_bottom - 14),
            ],
            fill="#FFFFFF",
        )

        text_x = icon_right + gap
        for text, color in segments:
            draw.text((text_x, top - 2), text, fill=color, font=brand_font)
            text_x += self._text_width(draw, text, brand_font)

        subtitle = "比新闻更快的财经资讯"
        sub_y = top + icon_size + 56
        sub_w = self._text_width(draw, subtitle, subtitle_font)
        sub_left = (self.width - sub_w) // 2 - 24
        sub_right = sub_left + sub_w + 48
        draw.rounded_rectangle(
            (sub_left, sub_y - 8, sub_right, sub_y + 64),
            radius=10,
            fill="#F8FAFF",
        )
        draw.text((sub_left + 24, sub_y), subtitle, fill="#6E768A", font=subtitle_font)

    def _draw_content_card(self, draw, now: datetime, titles: list[str], time_font, headline_font, body_font, card_meta_font):
        card_left = 34
        card_top = 380
        card_right = self.width - 34
        card_bottom = self.height - 170
        radius = 56
        draw.rounded_rectangle(
            (card_left, card_top, card_right, card_bottom),
            radius=radius,
            fill="#FFFFFF",
            outline="#E5EAF4",
            width=2,
        )

        inner_left = card_left + 52
        inner_top = card_top + 64
        inner_right = card_right - 52
        inner_bottom = card_bottom - 52
        inner_width = inner_right - inner_left

        time_text = self._format_cn_datetime(now)
        time_w = self._text_width(draw, time_text, time_font)
        draw.text(
            (inner_left + (inner_width - time_w) // 2, inner_top),
            time_text,
            fill="#1F2330",
            font=time_font,
        )

        divider_y = inner_top + 86
        center_x = inner_left + inner_width // 2
        draw.line((inner_left + 30, divider_y, center_x - 28, divider_y), fill="#DADFEA", width=3)
        draw.line((center_x + 28, divider_y, inner_right - 30, divider_y), fill="#DADFEA", width=3)
        draw.polygon(
            [
                (center_x, divider_y + 12),
                (center_x - 16, divider_y),
                (center_x, divider_y - 12),
                (center_x + 16, divider_y),
            ],
            fill="#E4E8F2",
        )

        headline = titles[0]
        body_parts = titles[1:] if len(titles) > 1 else []
        body_text = "；".join(body_parts) if body_parts else "暂无更多要点，稍后将持续更新。"

        content_left = inner_left
        content_right = inner_right
        content_width = content_right - content_left
        headline_y = divider_y + 50

        headline_lines = self._wrap_lines(
            draw=draw,
            text=headline,
            font=headline_font,
            max_width=content_width,
            max_lines=2,
        )
        headline_line_height = self._line_height(draw, headline_font)
        draw.multiline_text(
            (content_left, headline_y),
            "\n".join(headline_lines),
            fill="#B00F1E",
            font=headline_font,
            spacing=16,
        )

        body_y = headline_y + len(headline_lines) * headline_line_height + max(0, len(headline_lines) - 1) * 16 + 42

        qr_size = 178
        qr_left = inner_right - qr_size
        qr_top = inner_bottom - qr_size - 24
        footer_top = qr_top + 10

        body_line_height = self._line_height(draw, body_font) + 14
        body_available = max(120, footer_top - body_y - 16)
        max_body_lines = max(2, min(6, body_available // max(1, body_line_height)))
        body_lines = self._wrap_lines(
            draw=draw,
            text=body_text,
            font=body_font,
            max_width=content_width,
            max_lines=max_body_lines,
        )
        draw.multiline_text(
            (content_left, body_y),
            "\n".join(body_lines),
            fill="#B11E2A",
            font=body_font,
            spacing=14,
        )

        meta_left = content_left
        meta_right = qr_left - 36
        draw.line((meta_left, qr_top + 8, meta_right, qr_top + 8), fill="#E1E6EF", width=2)
        draw.text(
            (meta_left, qr_top + 32),
            "研究 · 电报 · 路演 · 行情 · 社区",
            fill="#8A8E98",
            font=card_meta_font,
        )
        draw.line((meta_left, qr_top + 98, meta_right, qr_top + 98), fill="#E1E6EF", width=2)
        draw.text(
            (meta_left, qr_top + 120),
            "自动摘要识别，快读 AFR 要闻",
            fill="#9CA1AC",
            font=card_meta_font,
        )

        draw.rounded_rectangle(
            (qr_left, qr_top, qr_left + qr_size, qr_top + qr_size),
            radius=12,
            fill="#FFFFFF",
            outline="#D5DBE8",
            width=2,
        )
        self._draw_qr_placeholder(
            draw=draw,
            left=qr_left + 10,
            top=qr_top + 10,
            size=qr_size - 20,
            seed=f"{headline}-{now.isoformat()}",
        )

    def _draw_footer_bar(self, draw, footer_font) -> None:
        footer_h = 126
        top = self.height - footer_h
        draw.rectangle((0, top, self.width, self.height), fill="#3C67DB")

        text = "AFR Pusher    全球视野 · 快速资讯"
        text_w = self._text_width(draw, text, footer_font)
        draw.text(
            ((self.width - text_w) // 2, top + 32),
            text,
            fill="#F3F6FF",
            font=footer_font,
        )

    def _draw_qr_placeholder(self, draw, left: int, top: int, size: int, seed: str) -> None:
        module_count = 29
        cell = max(3, size // module_count)
        grid_size = cell * module_count
        offset_x = left + (size - grid_size) // 2
        offset_y = top + (size - grid_size) // 2

        draw.rectangle((offset_x, offset_y, offset_x + grid_size, offset_y + grid_size), fill="#FFFFFF")

        def in_finder(i: int, j: int) -> bool:
            return (
                (i < 7 and j < 7)
                or (i < 7 and j >= module_count - 7)
                or (i >= module_count - 7 and j < 7)
            )

        def draw_finder(fi: int, fj: int) -> None:
            x = offset_x + fi * cell
            y = offset_y + fj * cell
            s = 7 * cell
            draw.rectangle((x, y, x + s, y + s), fill="#101217")
            draw.rectangle((x + cell, y + cell, x + s - cell, y + s - cell), fill="#FFFFFF")
            draw.rectangle((x + 2 * cell, y + 2 * cell, x + s - 2 * cell, y + s - 2 * cell), fill="#101217")

        draw_finder(0, 0)
        draw_finder(0, module_count - 7)
        draw_finder(module_count - 7, 0)

        for i in range(module_count):
            for j in range(module_count):
                if in_finder(i, j):
                    continue
                token = hashlib.sha256(f"{seed}:{i}:{j}".encode("utf-8")).digest()[0]
                if token % 3 == 0:
                    x = offset_x + i * cell
                    y = offset_y + j * cell
                    draw.rectangle((x, y, x + cell, y + cell), fill="#101217")

        logo_size = max(24, cell * 5)
        logo_left = offset_x + (grid_size - logo_size) // 2
        logo_top = offset_y + (grid_size - logo_size) // 2
        draw.rounded_rectangle(
            (logo_left, logo_top, logo_left + logo_size, logo_top + logo_size),
            radius=8,
            fill="#2B6FE4",
        )
        draw.rounded_rectangle(
            (
                logo_left + logo_size // 4,
                logo_top + logo_size // 4,
                logo_left + logo_size * 3 // 4,
                logo_top + logo_size * 3 // 4,
            ),
            radius=4,
            fill="#FFFFFF",
        )
        draw.polygon(
            [
                (logo_left + logo_size // 2, logo_top + logo_size // 2 - 8),
                (logo_left + logo_size // 2 + 10, logo_top + logo_size // 2 + 10),
                (logo_left + logo_size // 2 - 10, logo_top + logo_size // 2 + 10),
            ],
            fill="#2B6FE4",
        )

    @staticmethod
    def _format_cn_datetime(now: datetime) -> str:
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        return f"{now.strftime('%Y-%m-%d %H:%M')} {weekdays[now.weekday()]}"

    def _load_font(self, image_font_module, size: int):
        font_candidates = [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
        ]
        for font_path in font_candidates:
            path = Path(font_path)
            if path.exists():
                try:
                    return image_font_module.truetype(str(path), size=size)
                except Exception:
                    continue
        return image_font_module.load_default()

    @staticmethod
    def _text_width(draw, text: str, font) -> int:
        if not text:
            return 0
        left, _, right, _ = draw.textbbox((0, 0), text, font=font)
        return right - left

    @staticmethod
    def _line_height(draw, font) -> int:
        _, top, _, bottom = draw.textbbox((0, 0), "国A", font=font)
        return bottom - top

    def _fit_prefix(self, draw, text: str, font, max_width: int) -> int:
        if max_width <= 0:
            return 0
        index = 0
        for index in range(1, len(text) + 1):
            if self._text_width(draw, text[:index], font) > max_width:
                return max(0, index - 1)
        return len(text)

    def _wrap_lines(self, draw, text: str, font, max_width: int, max_lines: int) -> list[str]:
        content = text.strip()
        if not content:
            return []

        lines: list[str] = []
        cursor = 0
        truncated = False
        while cursor < len(content) and len(lines) < max_lines:
            consumed = self._fit_prefix(draw, content[cursor:], font, max_width)
            if consumed <= 0:
                break
            next_line = content[cursor : cursor + consumed].strip()
            lines.append(next_line)
            cursor += consumed
        if cursor < len(content):
            truncated = True

        if truncated and lines:
            ellipsis = "..."
            last = lines[-1].rstrip()
            while last and self._text_width(draw, last + ellipsis, font) > max_width:
                last = last[:-1]
            lines[-1] = (last.rstrip() + ellipsis) if last else ellipsis
        return lines
