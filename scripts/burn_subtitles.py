#!/usr/bin/env python3
"""
烧录字幕到视频
处理 FFmpeg libass 支持和路径空格问题
"""

import sys
import os
import shutil
import subprocess
import tempfile
import platform
from pathlib import Path
from typing import Dict, Optional, Tuple

from utils import format_file_size


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


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "y", "on")


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    return value.strip() if value else default


def ass_time(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours}:{minutes:02d}:{secs:05.2f}"


def to_ass_color(hex_color: str, fallback_hex: str) -> str:
    def normalize(value: str) -> Optional[str]:
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


def build_ass_from_srt_bilingual(
    srt_path: str,
    ass_path: str,
    font_name: str,
    font_size: int,
    margin_v: int,
    outline: int,
    shadow: int,
    alignment: int,
    en_color: str,
    zh_color: str,
    bilingual_order: str,
    play_res: Tuple[int, int]
) -> None:
    try:
        import pysrt
    except ImportError:
        raise RuntimeError("pysrt not installed. Please install: pip install pysrt")

    subs = pysrt.open(srt_path)
    play_res_x, play_res_y = play_res

    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {play_res_x}\n"
        f"PlayResY: {play_res_y}\n"
        "ScaledBorderAndShadow: yes\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Default,"
        f"{font_name},{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,"
        f"0,0,0,0,100,100,0,0,1,{outline},{shadow},{alignment},20,20,{margin_v},1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(header)

        for sub in subs:
            start = sub.start.hours * 3600 + sub.start.minutes * 60 + sub.start.seconds + sub.start.milliseconds / 1000
            end = sub.end.hours * 3600 + sub.end.minutes * 60 + sub.end.seconds + sub.end.milliseconds / 1000

            lines = [line.strip() for line in sub.text.splitlines() if line.strip()]
            if not lines:
                continue

            order = bilingual_order.upper()
            if len(lines) >= 2:
                if order == "ZH_FIRST":
                    zh_lines = [lines[0]]
                    en_lines = lines[1:]
                else:
                    en_lines = [lines[0]]
                    zh_lines = lines[1:]

                en_text = "\\N".join(en_lines)
                zh_text = "\\N".join(zh_lines)

                text = f"{{\\c{en_color}}}{en_text}"
                if zh_text:
                    text += f"\\N{{\\c{zh_color}}}{zh_text}"
            else:
                text = f"{{\\c{en_color}}}{lines[0]}"

            f.write(
                f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Default,,0,0,0,,{text}\n"
            )

def detect_ffmpeg_variant() -> Dict:
    """
    检测 FFmpeg 版本和 libass 支持

    Returns:
        Dict: {
            'type': 'full' | 'standard' | 'none',
            'path': FFmpeg 可执行文件路径,
            'has_libass': 是否支持 libass
        }
    """
    print("🔍 检测 FFmpeg 环境...")

    # 优先检查 ffmpeg-full（macOS）
    if platform.system() == 'Darwin':
        # Apple Silicon
        full_path_arm = '/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg'
        # Intel
        full_path_intel = '/usr/local/opt/ffmpeg-full/bin/ffmpeg'

        for full_path in [full_path_arm, full_path_intel]:
            if Path(full_path).exists():
                has_libass = check_libass_support(full_path)
                print(f"   找到 ffmpeg-full: {full_path}")
                print(f"   libass 支持: {'✅ 是' if has_libass else '❌ 否'}")
                return {
                    'type': 'full',
                    'path': full_path,
                    'has_libass': has_libass
                }

    # 检查标准 FFmpeg
    standard_path = shutil.which('ffmpeg')
    if standard_path:
        has_libass = check_libass_support(standard_path)
        variant_type = 'full' if has_libass else 'standard'
        print(f"   找到 FFmpeg: {standard_path}")
        print(f"   类型: {variant_type}")
        print(f"   libass 支持: {'✅ 是' if has_libass else '❌ 否'}")
        return {
            'type': variant_type,
            'path': standard_path,
            'has_libass': has_libass
        }

    # 未找到 FFmpeg
    print("   ❌ 未找到 FFmpeg")
    return {
        'type': 'none',
        'path': None,
        'has_libass': False
    }


def check_libass_support(ffmpeg_path: str) -> bool:
    """
    检查 FFmpeg 是否支持 libass（字幕烧录必需）

    Args:
        ffmpeg_path: FFmpeg 可执行文件路径

    Returns:
        bool: 是否支持 libass
    """
    try:
        # 检查是否有 subtitles 滤镜
        result = subprocess.run(
            [ffmpeg_path, '-filters'],
            capture_output=True,
            text=True,
            timeout=5
        )

        # 查找 subtitles 滤镜
        return 'subtitles' in result.stdout.lower()

    except Exception:
        return False


def install_ffmpeg_full_guide():
    """
    显示安装 ffmpeg-full 的指南
    """
    print("\n" + "="*60)
    print("⚠️  需要安装 ffmpeg-full 才能烧录字幕")
    print("="*60)

    if platform.system() == 'Darwin':
        print("\nmacOS 安装方法:")
        print("  brew install ffmpeg-full")
        print("\n安装后，FFmpeg 路径:")
        print("  /opt/homebrew/opt/ffmpeg-full/bin/ffmpeg  (Apple Silicon)")
        print("  /usr/local/opt/ffmpeg-full/bin/ffmpeg     (Intel)")
    else:
        print("\n其他系统:")
        print("  请从源码编译 FFmpeg，确保包含 libass 支持")
        print("  参考: https://trac.ffmpeg.org/wiki/CompilationGuide")

    print("\n验证安装:")
    print("  ffmpeg -filters 2>&1 | grep subtitles")
    print("="*60)


def burn_subtitles(
    video_path: str,
    subtitle_path: str,
    output_path: str,
    ffmpeg_path: str = None,
    font_size: Optional[int] = None,
    margin_v: Optional[int] = None
) -> str:
    """
    烧录字幕到视频（使用临时目录解决路径空格问题）

    Args:
        video_path: 输入视频路径
        subtitle_path: 字幕文件路径（SRT/ASS 格式）
        output_path: 输出视频路径
        ffmpeg_path: FFmpeg 可执行文件路径（可选）
        font_size: 字体大小（可选）
        margin_v: 底部边距（可选）

    Returns:
        str: 输出视频路径

    Raises:
        FileNotFoundError: 输入文件不存在
        RuntimeError: FFmpeg 执行失败
    """
    video_path = Path(video_path)
    subtitle_path = Path(subtitle_path)
    output_path = Path(output_path)

    # 验证输入文件
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")
    if not subtitle_path.exists():
        raise FileNotFoundError(f"Subtitle file not found: {subtitle_path}")

    # 检测 FFmpeg
    if ffmpeg_path is None:
        ffmpeg_info = detect_ffmpeg_variant()

        if ffmpeg_info['type'] == 'none':
            install_ffmpeg_full_guide()
            raise RuntimeError("FFmpeg not found")

        if not ffmpeg_info['has_libass']:
            install_ffmpeg_full_guide()
            raise RuntimeError("FFmpeg does not support libass (subtitles filter)")

        ffmpeg_path = ffmpeg_info['path']

    if font_size is None:
        font_size = env_int("SUBTITLE_FONT_SIZE", 24)
    if margin_v is None:
        margin_v = env_int("SUBTITLE_MARGIN_V", 30)

    print(f"\n🎬 烧录字幕到视频...")
    print(f"   视频: {video_path.name}")
    print(f"   字幕: {subtitle_path.name}")
    print(f"   输出: {output_path.name}")
    print(f"   FFmpeg: {ffmpeg_path}")

    # 创建临时目录（解决路径空格问题）
    temp_dir = tempfile.mkdtemp(prefix='youtube_clipper_')
    print(f"   使用临时目录: {temp_dir}")

    try:
        # 复制文件到临时目录（路径无空格）
        temp_video = os.path.join(temp_dir, 'video.mp4')
        subtitle_ext = subtitle_path.suffix.lower() or ".srt"
        temp_subtitle = os.path.join(temp_dir, f"subtitle{subtitle_ext}")
        temp_output = os.path.join(temp_dir, 'output.mp4')

        print(f"   复制文件到临时目录...")
        shutil.copy(video_path, temp_video)
        shutil.copy(subtitle_path, temp_subtitle)

        use_ass = subtitle_ext in (".ass", ".ssa")
        bilingual_color = env_bool("BILINGUAL_COLOR", False)

        if not use_ass and bilingual_color and subtitle_ext == ".srt":
            font_name = env_str("SUBTITLE_FONT_NAME", "PingFang SC")
            outline = env_int("SUBTITLE_OUTLINE", 2)
            shadow = env_int("SUBTITLE_SHADOW", 1)
            alignment = env_int("SUBTITLE_ALIGNMENT", 2)
            # 英文白色，中文浅蓝色（与 tellmemore 样式一致）
            en_color = to_ass_color(env_str("SUBTITLE_EN_COLOR", "#FFFFFF"), "#FFFFFF")
            zh_color = to_ass_color(env_str("SUBTITLE_ZH_COLOR", "#7AD7FF"), "#7AD7FF")
            bilingual_order = env_str("BILINGUAL_ORDER", "EN_FIRST")
            play_res_x = env_int("SUBTITLE_PLAYRESX", 1920)
            play_res_y = env_int("SUBTITLE_PLAYRESY", 1080)

            temp_ass = os.path.join(temp_dir, "subtitle.ass")
            print("   检测到双语配色配置，生成 ASS 字幕...")
            build_ass_from_srt_bilingual(
                temp_subtitle,
                temp_ass,
                font_name=font_name,
                font_size=font_size,
                margin_v=margin_v,
                outline=outline,
                shadow=shadow,
                alignment=alignment,
                en_color=en_color,
                zh_color=zh_color,
                bilingual_order=bilingual_order,
                play_res=(play_res_x, play_res_y)
            )
            temp_subtitle = temp_ass
            use_ass = True

        # 构建 FFmpeg 命令
        # 使用 subtitles 滤镜烧录字幕
        if use_ass:
            subtitle_filter = f"subtitles={temp_subtitle}"
        else:
            # 第一遍字幕样式：白色字幕，黑色描边，与 tellmemore 一致
            font_name = env_str("SUBTITLE_FONT_NAME", "PingFang SC")
            outline = env_int("SUBTITLE_OUTLINE", 2)
            shadow = env_int("SUBTITLE_SHADOW", 1)
            subtitle_filter = f"subtitles={temp_subtitle}:force_style='FontName={font_name},FontSize={font_size},MarginV={margin_v},Outline={outline},Shadow={shadow}'"

        cmd = [
            ffmpeg_path,
            '-i', temp_video,
            '-vf', subtitle_filter,
            '-c:a', 'copy',  # 音频直接复制，不重新编码
            '-y',  # 覆盖输出文件
            temp_output
        ]

        print(f"   执行 FFmpeg...")
        print(f"   命令: {' '.join(cmd)}")

        # 执行 FFmpeg
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print(f"\n❌ FFmpeg 执行失败:")
            print(result.stderr)
            raise RuntimeError(f"FFmpeg failed with return code {result.returncode}")

        # 验证输出文件
        if not Path(temp_output).exists():
            raise RuntimeError("Output file not created")

        # 移动输出文件到目标位置
        print(f"   移动输出文件...")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(temp_output, output_path)

        # 获取文件大小
        output_size = output_path.stat().st_size
        print(f"✅ 字幕烧录完成")
        print(f"   输出文件: {output_path}")
        print(f"   文件大小: {format_file_size(output_size)}")

        return str(output_path)

    finally:
        # 清理临时目录
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
            print(f"   清理临时目录")
        except Exception:
            pass


def main():
    """命令行入口"""
    if len(sys.argv) < 4:
        print("Usage: python burn_subtitles.py <video> <subtitle> <output> [font_size] [margin_v]")
        print("\nArguments:")
        print("  video      - 输入视频文件路径")
        print("  subtitle   - 字幕文件路径（SRT/ASS 格式）")
        print("  output     - 输出视频文件路径")
        print("  font_size  - 字体大小，默认 24")
        print("  margin_v   - 底部边距，默认 30")
        print("\nExample:")
        print("  python burn_subtitles.py input.mp4 subtitle.srt output.mp4")
        print("  python burn_subtitles.py input.mp4 subtitle.srt output.mp4 28 40")
        sys.exit(1)

    video_path = sys.argv[1]
    subtitle_path = sys.argv[2]
    output_path = sys.argv[3]
    font_size = int(sys.argv[4]) if len(sys.argv) > 4 else None
    margin_v = int(sys.argv[5]) if len(sys.argv) > 5 else None

    try:
        result_path = burn_subtitles(
            video_path,
            subtitle_path,
            output_path,
            font_size=font_size,
            margin_v=margin_v
        )

        print(f"\n✨ 完成！输出文件: {result_path}")

    except Exception as e:
        print(f"\n❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
