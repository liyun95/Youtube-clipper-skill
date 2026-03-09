#!/usr/bin/env python3
"""
学习型短片流程：
引导卡片 -> 挖空版视频 -> 过渡卡片 -> 完整版视频(下划线标注) -> summary 卡片 -> 拼接输出
"""

import sys
import os
import json
import shutil
import subprocess
import tempfile
import traceback
from pathlib import Path
from typing import Tuple, List

from utils import (
    time_to_seconds,
    seconds_to_time,
    sanitize_filename,
    create_output_dir,
    ensure_directory
)

from clip_video import clip_video, extract_subtitle_segment, save_subtitles_as_srt
from extract_subtitle_clip import extract_subtitle_clip
from translate_subtitles import (
    load_subtitles_from_srt,
    translate_subtitles_batch,
    create_bilingual_subtitles
)
from burn_subtitles import burn_subtitles
from extract_key_phrases import extract_key_phrases, save_phrases
from mask_subtitles import mask_subtitles
from render_summary_card import render_summary_card
from render_intro_card import render_intro_card
from render_transition_card import render_transition_card
from generate_underlined_subtitle import generate_underlined_subtitle


def _derive_video_id_from_subtitle(subtitle_path: str) -> str:
    stem = Path(subtitle_path).stem
    # 兼容 4uzGDAoNOZc.en.vtt / 4uzGDAoNOZc.vtt / 4uzGDAoNOZc.srt
    if stem.endswith(".en"):
        stem = stem[:-3]
    return stem


def mirror_analysis_artifacts(subtitle_path: str, base_dir: Path, output_dir: Path) -> None:
    """
    将语义分析产物镜像到当前 clip 输出目录，便于单目录归档。
    """
    video_id = _derive_video_id_from_subtitle(subtitle_path)
    suffixes = [
        "_analysis.json",
        "_candidates.json",
        "_candidate_report.md",
    ]
    source_roots = [
        Path(base_dir),
        Path(subtitle_path).resolve().parent,
        Path.cwd(),
    ]

    copied = 0
    for suffix in suffixes:
        target = Path(output_dir) / f"{video_id}{suffix}"
        if target.exists():
            continue

        source = None
        for root in source_roots:
            candidate = root / f"{video_id}{suffix}"
            if candidate.exists():
                source = candidate
                break

        if source:
            shutil.copy2(source, target)
            copied += 1

    if copied:
        print(f"📎 已复制 {copied} 个分析文件到输出目录")


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


def parse_time_arg(value: str) -> float:
    if ":" in value or "." in value:
        return time_to_seconds(value)
    return float(value)


def get_video_resolution(video_path: str) -> Tuple[int, int, float]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return 1920, 1080, 30.0

    cmd = [
        ffprobe,
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate",
        "-of", "json",
        video_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return 1920, 1080, 30.0
        data = json.loads(result.stdout)
        stream = data.get("streams", [{}])[0]
        width = int(stream.get("width", 1920))
        height = int(stream.get("height", 1080))
        rate = stream.get("r_frame_rate", "30/1")
        if "/" in rate:
            num, den = rate.split("/", 1)
            fps = float(num) / float(den) if float(den) != 0 else 30.0
        else:
            fps = float(rate)
        return width, height, fps
    except Exception:
        return 1920, 1080, 30.0


def clip_srt_segment(srt_path: str, start_sec: float, end_sec: float, output_path: str) -> str:
    subtitles = load_subtitles_from_srt(srt_path)
    segment = extract_subtitle_segment(subtitles, start_sec, end_sec, adjust_timestamps=True)
    save_subtitles_as_srt(segment, output_path)
    return output_path


def concat_videos(segments: List[str], output_path: str) -> str:
    temp_dir = tempfile.mkdtemp(prefix="youtube_clipper_concat_")
    list_path = Path(temp_dir) / "list.txt"
    try:
        with open(list_path, "w", encoding="utf-8") as f:
            for seg in segments:
                f.write(f"file '{seg}'\n")

        cmd = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_path),
            "-c", "copy",
            "-y",
            str(output_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return str(output_path)

        # fallback: re-encode concat
        print("⚠️  无法无损拼接，尝试重新编码拼接...")
        inputs = []
        filter_inputs = []
        for i, seg in enumerate(segments):
            inputs.extend(["-i", seg])
            filter_inputs.append(f"[{i}:v][{i}:a]")
        filter_complex = "".join(filter_inputs) + f"concat=n={len(segments)}:v=1:a=1[outv][outa]"
        cmd = [
            "ffmpeg",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[outv]",
            "-map", "[outa]",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-y",
            str(output_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(result.stderr)
            raise RuntimeError("Failed to concat videos")
        return str(output_path)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    if len(sys.argv) < 5:
        print("Usage: python learning_clip.py <video.mp4> <subtitle.vtt|srt> <start_time> <end_time> [output_dir]")
        print("Optional flags: --output <dir> --name <base_name>")
        print("Example:")
        print("  python learning_clip.py video.mp4 video.en.vtt 00:05:00 00:05:45 --output ./youtube-clips")
        sys.exit(1)

    args = sys.argv[1:]
    video_path = args[0]
    subtitle_path = args[1]
    start_time = args[2]
    end_time = args[3]
    rest = args[4:]

    output_dir = None
    base_name = None
    i = 0
    while i < len(rest):
        if rest[i] in ("-o", "--output") and i + 1 < len(rest):
            output_dir = rest[i + 1]
            i += 2
        elif rest[i] in ("-n", "--name") and i + 1 < len(rest):
            base_name = rest[i + 1]
            i += 2
        else:
            output_dir = rest[i]
            i += 1

    start_sec = parse_time_arg(start_time)
    end_sec = parse_time_arg(end_time)
    duration = end_sec - start_sec

    min_sec = env_int("LEARNING_CLIP_MIN_SEC", 30)
    max_sec = env_int("LEARNING_CLIP_MAX_SEC", 60)
    if duration < min_sec or duration > max_sec:
        print(f"⚠️  提示：片段时长 {duration:.1f}s 不在推荐范围 {min_sec}-{max_sec}s")

    if not base_name:
        base_name = f"learning_{int(start_sec)}_{int(end_sec)}"
    base_name = sanitize_filename(base_name)

    # 确定输出目录：始终在基础目录下创建以 base_name 命名的子目录
    if output_dir:
        base_dir = Path(output_dir)
    else:
        base_output = env_str("OUTPUT_DIR", "")
        base_dir = Path(base_output) if base_output else Path.cwd() / "youtube-clips"

    output_dir = ensure_directory(base_dir / base_name)

    output_dir = Path(output_dir)

    # 文件名不再需要前缀，因为目录已经用 base_name 命名
    clip_mp4 = output_dir / "clip.mp4"
    clip_srt = output_dir / "clip.srt"
    key_phrases_json = output_dir / "key_phrases.json"
    masked_srt = output_dir / "masked.srt"
    bilingual_srt = output_dir / "bilingual.srt"
    underlined_ass = output_dir / "underlined.ass"
    intro_mp4 = output_dir / "intro.mp4"
    masked_mp4 = output_dir / "masked.mp4"
    transition_mp4 = output_dir / "transition.mp4"
    full_mp4 = output_dir / "full.mp4"
    summary_mp4 = output_dir / "summary.mp4"
    final_mp4 = output_dir / "learning.mp4"

    print(f"🎬 学习型短片流程开始")
    print(f"   输出目录: {output_dir}")

    mirror_analysis_artifacts(subtitle_path, base_dir, output_dir)

    # 1) 剪辑视频片段
    clip_video(video_path, start_sec, end_sec, str(clip_mp4))

    # 2) 提取字幕片段（VTT 或 SRT）
    if subtitle_path.lower().endswith(".vtt"):
        extract_subtitle_clip(subtitle_path, seconds_to_time(start_sec), seconds_to_time(end_sec), str(clip_srt))
    elif subtitle_path.lower().endswith(".srt"):
        clip_srt_segment(subtitle_path, start_sec, end_sec, str(clip_srt))
    else:
        raise ValueError("Unsupported subtitle format. Use .vtt or .srt")

    # 3) 关键表达提取
    phrases = extract_key_phrases(str(clip_srt), max_phrases=6)
    save_phrases(phrases, str(key_phrases_json))

    # 4) 字幕挖空（第一遍）
    mask_subtitles(str(clip_srt), str(key_phrases_json), str(masked_srt))

    # 5) 完整双语字幕（第二遍）
    subtitles = load_subtitles_from_srt(str(clip_srt))
    target_lang = env_str("TARGET_LANGUAGE", "中文")
    translated = translate_subtitles_batch(
        subtitles,
        batch_size=env_int("TRANSLATION_BATCH_SIZE", 20),
        target_lang=target_lang
    )
    has_translation = any(
        sub.get("translation") and sub.get("translation") != "[待翻译]" for sub in translated
    )
    if has_translation:
        create_bilingual_subtitles(translated, str(bilingual_srt), english_first=True)
    else:
        shutil.copy(str(clip_srt), str(bilingual_srt))
        print("⚠️  翻译不可用，第二遍将使用英文完整字幕")

    # 6) 生成带下划线的完整字幕（ASS 格式）
    generate_underlined_subtitle(
        srt_path=str(bilingual_srt),
        phrases_path=str(key_phrases_json),
        output_path=str(underlined_ass),
        translations=translated if has_translation else None
    )

    # 7) 获取视频分辨率信息
    width, height, fps = get_video_resolution(str(clip_mp4))

    # 8) 生成引导卡片
    intro_duration = env_int("INTRO_DURATION_SEC", 4)
    render_intro_card(
        phrases_path=str(key_phrases_json),
        output_path=str(intro_mp4),
        width=width,
        height=height,
        duration=intro_duration,
        fps=fps
    )

    # 9) 烧录挖空字幕（第一遍视频）
    burn_subtitles(str(clip_mp4), str(masked_srt), str(masked_mp4))

    # 10) 生成过渡卡片
    transition_duration = env_int("TRANSITION_DURATION_SEC", 3)
    render_transition_card(
        output_path=str(transition_mp4),
        width=width,
        height=height,
        duration=transition_duration,
        fps=fps
    )

    # 11) 烧录带下划线的完整字幕（第二遍视频）
    burn_subtitles(str(clip_mp4), str(underlined_ass), str(full_mp4))

    # 12) 生成 summary 卡片
    summary_duration = env_int("SUMMARY_DURATION_SEC", 4)
    render_summary_card(
        phrases_path=str(key_phrases_json),
        output_path=str(summary_mp4),
        width=width,
        height=height,
        duration=summary_duration,
        fps=fps
    )

    # 13) 拼接导出（5 段视频）
    concat_videos([
        str(intro_mp4),
        str(masked_mp4),
        str(transition_mp4),
        str(full_mp4),
        str(summary_mp4)
    ], str(final_mp4))

    print("\n✨ 完成！输出文件:")
    print(f"   片段: {clip_mp4}")
    print(f"   挖空字幕: {masked_srt}")
    print(f"   下划线字幕: {underlined_ass}")
    print(f"   引导卡片: {intro_mp4}")
    print(f"   第一遍视频: {masked_mp4}")
    print(f"   过渡卡片: {transition_mp4}")
    print(f"   第二遍视频: {full_mp4}")
    print(f"   Summary 卡片: {summary_mp4}")
    print(f"   最终输出: {final_mp4}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ 错误: {str(e)}")
        traceback.print_exc()
        sys.exit(1)
