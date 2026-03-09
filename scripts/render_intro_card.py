#!/usr/bin/env python3
"""
生成引导卡片视频（展示挖空的关键表达，提示用户注意听）
"""

import sys
import json
import os
import shutil
import subprocess
import tempfile
import traceback
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


def build_intro_ass_text(
    phrases: List[Dict],
    max_items: int = 6,
    title_color: str = "&H00FFFFFF",
    subtitle_color: str = "&H00FFFFFF",
    phrase_color: str = "&H00FFD54F",
    translation_color: str = "&H00FFFFFF"
) -> str:
    """
    构建引导卡片的 ASS 文本
    显示双语关键表达：phrase - 翻译
    """
    title = "Listen & Fill"
    subtitle = "Try to catch these expressions:"

    items = []
    count = 0
    for item in phrases:
        if count >= max_items:
            break
        phrase = str(item.get("phrase", "")).strip()
        translation = str(item.get("translation", "")).strip()
        if not phrase or phrase == "[待提取]":
            continue
        # 显示双语格式：phrase - 翻译
        if translation and translation != "[待翻译]":
            line = f"{colorize('• ', subtitle_color)}{colorize(phrase, phrase_color)}{colorize(' - ', subtitle_color)}{colorize(translation, translation_color)}"
        else:
            line = f"{colorize('• ', subtitle_color)}{colorize(phrase, phrase_color)}"
        items.append(line)
        count += 1

    if not items:
        for _ in range(3):
            items.append(f"{colorize('• ', subtitle_color)}{colorize('expression', phrase_color)}")

    title_line = colorize(title, title_color)
    subtitle_line = colorize(subtitle, subtitle_color)

    text = (
        r"{\fs60}" + title_line + r"{\fs40}\N\N" +
        subtitle_line + r"\N\N" +
        r"\N".join(items)
    )
    return text


def render_intro_card(
    phrases_path: str,
    output_path: str,
    width: int = 1920,
    height: int = 1080,
    duration: int = 4,
    fps: float = 30.0,
    max_items: int = 6,
    bg_color: str = "black",
    font_name: str = None
) -> str:
    """
    渲染引导卡片视频

    Args:
        phrases_path: 关键表达 JSON 文件路径
        output_path: 输出视频路径
        width: 视频宽度
        height: 视频高度
        duration: 视频时长（秒）
        fps: 帧率
        max_items: 最大显示条目数
        bg_color: 背景颜色
        font_name: 字体名称

    Returns:
        str: 输出视频路径
    """
    phrases = load_phrases(phrases_path)

    font_name = font_name or env_str("SUBTITLE_FONT_NAME", "Arial")

    title_hex = env_str("INTRO_TITLE_COLOR", "#7AD7FF")
    subtitle_hex = env_str("INTRO_SUBTITLE_COLOR", "#FFFFFF")
    phrase_hex = env_str("INTRO_PHRASE_COLOR", env_str("INTRO_BLANK_COLOR", "#FFD54F"))
    translation_hex = env_str("INTRO_TRANSLATION_COLOR", "#AAAAAA")

    title_color = to_ass_color(title_hex, "#7AD7FF")
    subtitle_color = to_ass_color(subtitle_hex, "#FFFFFF")
    phrase_color = to_ass_color(phrase_hex, "#FFD54F")
    translation_color = to_ass_color(translation_hex, "#AAAAAA")

    ass_text = build_intro_ass_text(
        phrases=phrases,
        max_items=max_items,
        title_color=title_color,
        subtitle_color=subtitle_color,
        phrase_color=phrase_color,
        translation_color=translation_color
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

    print(f"🎬 生成引导卡片...")
    print(f"   输出: {output_path}")
    print(f"   分辨率: {width}x{height}")
    print(f"   时长: {duration}s")
    print(f"   帧率: {fps}")

    temp_dir = tempfile.mkdtemp(prefix="youtube_clipper_intro_")
    try:
        ass_path = Path(temp_dir) / "intro.ass"
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
            raise RuntimeError("FFmpeg failed to render intro card")

        print("✅ 引导卡片生成完成")
        return str(output_path)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    if len(sys.argv) < 3:
        print("Usage: python render_intro_card.py <phrases.json> <output.mp4> [width] [height] [duration] [fps]")
        print("Example:")
        print("  python render_intro_card.py key_phrases.json intro.mp4 1920 1080 4 30")
        sys.exit(1)

    phrases_path = sys.argv[1]
    output_path = sys.argv[2]
    width = int(sys.argv[3]) if len(sys.argv) > 3 else 1920
    height = int(sys.argv[4]) if len(sys.argv) > 4 else 1080
    duration = int(sys.argv[5]) if len(sys.argv) > 5 else env_int("INTRO_DURATION_SEC", 4)
    fps = float(sys.argv[6]) if len(sys.argv) > 6 else 30.0

    try:
        render_intro_card(
            phrases_path=phrases_path,
            output_path=output_path,
            width=width,
            height=height,
            duration=duration,
            fps=fps
        )
    except Exception as e:
        print(f"\n❌ 错误: {str(e)}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
