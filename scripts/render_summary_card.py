#!/usr/bin/env python3
"""
生成 summary 卡片视频（纯色背景 + 关键表达列表）
"""

import sys
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict


def load_env():
    """加载 .env（如果存在）"""
    try:
        from dotenv import load_dotenv
    except Exception:
        return

    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)


load_env()


def env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    return value.strip() if value else default


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "y", "on")


def load_phrases(phrases_path: str) -> List[Dict]:
    phrases_path = Path(phrases_path)
    if not phrases_path.exists():
        raise FileNotFoundError(f"Phrases file not found: {phrases_path}")
    with open(phrases_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Invalid phrases JSON: expected list")
    return data


def ass_escape(text: str) -> str:
    # Escape ASS override braces and newlines
    text = text.replace("{", r"\{").replace("}", r"\}")
    text = text.replace("\n", r"\N")
    return text


def to_ass_color(hex_color: str, fallback_hex: str) -> str:
    def normalize(value: str):
        if not value:
            return None
        value = value.strip()
        if value.startswith("#"):
            value = value[1:]
        if len(value) != 6:
            return None
        if any(c not in "0123456789abcdefABCDEF" for c in value):
            return None
        r, g, b = value[0:2], value[2:4], value[4:6]
        return f"&H00{b}{g}{r}"

    return normalize(hex_color) or normalize(fallback_hex) or "&H00FFFFFF"


def colorize(text: str, ass_color: str) -> str:
    return f"{{\\c{ass_color}}}{ass_escape(text)}"


def build_ass_text(
    phrases: List[Dict],
    include_translation: bool,
    title: str = "Key Expressions",
    max_items: int = 8,
    title_color: str = "&H00FFFFFF",
    en_color: str = "&H00FFD54F",
    zh_color: str = "&H00FFFFFF"
) -> str:
    items = []
    count = 0
    for item in phrases:
        if count >= max_items:
            break
        phrase = str(item.get("phrase", "")).strip()
        translation = str(item.get("translation", "")).strip()
        if not phrase:
            continue
        if include_translation and translation and translation != "[待翻译]":
            line = (
                f"{colorize('• ', zh_color)}"
                f"{colorize(phrase, en_color)}"
                f"{colorize(' - ' + translation, zh_color)}"
            )
            items.append(line)
        else:
            line = f"{colorize('• ', zh_color)}{colorize(phrase, en_color)}"
            items.append(line)
        count += 1

    if not items:
        items = [colorize("• (no key phrases)", zh_color)]

    title_line = colorize(title, title_color)
    text = r"{\fs54}" + title_line + r"{\fs40}\N" + r"\N".join(items)
    return text


def render_summary_card(
    phrases_path: str,
    output_path: str,
    width: int = 1920,
    height: int = 1080,
    duration: int = 4,
    fps: float = 30.0,
    include_translation: bool = None,
    title: str = "Key Expressions",
    max_items: int = 8,
    bg_color: str = "black",
    font_name: str = None
) -> str:
    phrases = load_phrases(phrases_path)

    font_name = font_name or env_str("SUBTITLE_FONT_NAME", "Arial")
    if include_translation is None:
        include_translation = env_bool("SUMMARY_INCLUDE_TRANSLATION", True)

    title_hex = env_str("SUMMARY_TITLE_COLOR", "#7AD7FF")
    en_hex = env_str("SUMMARY_EN_COLOR", env_str("SUBTITLE_EN_COLOR", "#FFD54F"))
    zh_hex = env_str("SUMMARY_ZH_COLOR", "#FFFFFF")
    title_color = to_ass_color(title_hex, "#7AD7FF")
    en_color = to_ass_color(en_hex, "#FFD54F")
    zh_color = to_ass_color(zh_hex, "#FFFFFF")

    ass_text = build_ass_text(
        phrases=phrases,
        include_translation=include_translation,
        title=title,
        max_items=max_items,
        title_color=title_color,
        en_color=en_color,
        zh_color=zh_color
    )

    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {width}\n"
        f"PlayResY: {height}\n"
        "ScaledBorderAndShadow: yes\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{font_name},40,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,"
        "0,0,0,0,100,100,0,0,1,2,1,5,60,60,80,1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    ass_content = header + f"Dialogue: 0,0:00:00.00,0:00:{duration:02d}.00,Default,,0,0,0,,{ass_text}\n"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"🧾 生成 summary 卡片...")
    print(f"   输出: {output_path}")
    print(f"   分辨率: {width}x{height}")
    print(f"   时长: {duration}s")
    print(f"   帧率: {fps}")

    temp_dir = tempfile.mkdtemp(prefix="youtube_clipper_summary_")
    try:
        ass_path = Path(temp_dir) / "summary.ass"
        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(ass_content)

        cmd = [
            "ffmpeg",
            "-f", "lavfi",
            "-i", f"color=c={bg_color}:s={width}x{height}:d={duration}:r={fps}",
            "-f", "lavfi",
            "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-shortest",
            "-vf", f"ass={ass_path}",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-y",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(result.stderr)
            raise RuntimeError("FFmpeg failed to render summary card")

        print("✅ summary 卡片生成完成")
        return str(output_path)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    if len(sys.argv) < 3:
        print("Usage: python render_summary_card.py <phrases.json> <output.mp4> [width] [height] [duration] [fps]")
        print("Example:")
        print("  python render_summary_card.py key_phrases.json summary.mp4 1920 1080 4 30")
        sys.exit(1)

    phrases_path = sys.argv[1]
    output_path = sys.argv[2]
    width = int(sys.argv[3]) if len(sys.argv) > 3 else 1920
    height = int(sys.argv[4]) if len(sys.argv) > 4 else 1080
    duration = int(sys.argv[5]) if len(sys.argv) > 5 else env_int("SUMMARY_DURATION_SEC", 4)
    fps = float(sys.argv[6]) if len(sys.argv) > 6 else 30.0

    include_translation = env_bool("SUMMARY_INCLUDE_TRANSLATION", True)

    try:
        render_summary_card(
            phrases_path=phrases_path,
            output_path=output_path,
            width=width,
            height=height,
            duration=duration,
            fps=fps,
            include_translation=include_translation
        )
    except Exception as e:
        print(f"\n❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
