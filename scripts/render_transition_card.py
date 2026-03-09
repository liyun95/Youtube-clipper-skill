#!/usr/bin/env python3
"""
生成过渡卡片视频（提示用户接下来是完整版，关键表达有下划线）
"""

import sys
import os
import shutil
import subprocess
import tempfile
import traceback
from pathlib import Path


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


def build_transition_ass_text(
    title_color: str = "&H00FFFFFF",
    subtitle_color: str = "&H00FFFFFF"
) -> str:
    """
    构建过渡卡片的 ASS 文本
    """
    title = "Now let's check!"
    subtitle = "Key expressions are underlined"

    title_line = colorize(title, title_color)
    subtitle_line = colorize(subtitle, subtitle_color)

    text = (
        r"{\fs60}" + title_line + r"{\fs36}\N\N" +
        subtitle_line
    )
    return text


def render_transition_card(
    output_path: str,
    width: int = 1920,
    height: int = 1080,
    duration: int = 3,
    fps: float = 30.0,
    bg_color: str = "black",
    font_name: str = None
) -> str:
    """
    渲染过渡卡片视频

    Args:
        output_path: 输出视频路径
        width: 视频宽度
        height: 视频高度
        duration: 视频时长（秒）
        fps: 帧率
        bg_color: 背景颜色
        font_name: 字体名称

    Returns:
        str: 输出视频路径
    """
    font_name = font_name or env_str("SUBTITLE_FONT_NAME", "Arial")

    title_hex = env_str("TRANSITION_TITLE_COLOR", "#7AD7FF")
    subtitle_hex = env_str("TRANSITION_SUBTITLE_COLOR", "#FFFFFF")

    title_color = to_ass_color(title_hex, "#7AD7FF")
    subtitle_color = to_ass_color(subtitle_hex, "#FFFFFF")

    ass_text = build_transition_ass_text(
        title_color=title_color,
        subtitle_color=subtitle_color
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

    print(f"🔄 生成过渡卡片...")
    print(f"   输出: {output_path}")
    print(f"   分辨率: {width}x{height}")
    print(f"   时长: {duration}s")
    print(f"   帧率: {fps}")

    temp_dir = tempfile.mkdtemp(prefix="youtube_clipper_transition_")
    try:
        ass_path = Path(temp_dir) / "transition.ass"
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
            raise RuntimeError("FFmpeg failed to render transition card")

        print("✅ 过渡卡片生成完成")
        return str(output_path)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    if len(sys.argv) < 2:
        print("Usage: python render_transition_card.py <output.mp4> [width] [height] [duration] [fps]")
        print("Example:")
        print("  python render_transition_card.py transition.mp4 1920 1080 3 30")
        sys.exit(1)

    output_path = sys.argv[1]
    width = int(sys.argv[2]) if len(sys.argv) > 2 else 1920
    height = int(sys.argv[3]) if len(sys.argv) > 3 else 1080
    duration = int(sys.argv[4]) if len(sys.argv) > 4 else env_int("TRANSITION_DURATION_SEC", 3)
    fps = float(sys.argv[5]) if len(sys.argv) > 5 else 30.0

    try:
        render_transition_card(
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
