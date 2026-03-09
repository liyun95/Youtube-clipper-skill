#!/usr/bin/env python3
"""
提取字幕片段并转换为 SRT 格式
修复点：
1) 保留与片段边界重叠的字幕（避免开头/结尾丢字）
2) 清理 YouTube VTT 词级时间标签，恢复单词间空格
3) 过滤极短增量字幕，减少抖动与“看起来不同步”的现象
"""

import html
import sys
import re
from datetime import timedelta
from typing import List, Dict

def parse_vtt_time(time_str):
    """解析 VTT 时间格式为秒"""
    parts = time_str.strip().split(':')
    if len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        return hours * 3600 + minutes * 60 + seconds
    elif len(parts) == 2:
        minutes = int(parts[0])
        seconds = float(parts[1])
        return minutes * 60 + seconds
    return 0

def format_srt_time(seconds):
    """格式化为 SRT 时间格式"""
    td = timedelta(seconds=seconds)
    hours = int(td.total_seconds() // 3600)
    minutes = int((td.total_seconds() % 3600) // 60)
    secs = int(td.total_seconds() % 60)
    millis = int((td.total_seconds() % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def normalize_vtt_text(text_lines: List[str]) -> str:
    """将 VTT cue 文本规范化为可读句子。"""
    text = " ".join(line.strip() for line in text_lines if line.strip())
    text = html.unescape(text)

    # YouTube 词级标签: <00:11:17.920><c> I</c>
    text = re.sub(r"<\d{2}:\d{2}:\d{2}\.\d{3}><c>", " ", text)
    text = text.replace("</c>", " ")
    text = re.sub(r"</?c[^>]*>", " ", text)
    text = re.sub(r"<\d{2}:\d{2}:\d{2}\.\d{3}>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)

    # 移除说话人标记样式 >> / > >
    text = text.replace(">>", " ")

    # 标点前空格清理 + 多空格折叠
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def compact_incremental_cues(subtitles: List[Dict], tiny_threshold: float = 0.12) -> List[Dict]:
    """
    去除自动字幕中的极短增量片段（如 10ms 的中间态），保留可读 cue。
    """
    if not subtitles:
        return subtitles

    subtitles = sorted(subtitles, key=lambda x: (x["start"], x["end"]))

    # 先合并完全重复文本的相邻 cue
    merged: List[Dict] = []
    for sub in subtitles:
        if merged:
            prev = merged[-1]
            if (
                sub["text"] == prev["text"]
                and sub["start"] - prev["end"] <= 0.05
            ):
                prev["end"] = max(prev["end"], sub["end"])
                continue
        merged.append(sub)

    cleaned: List[Dict] = []
    for idx, sub in enumerate(merged):
        dur = sub["end"] - sub["start"]
        nxt = merged[idx + 1] if idx + 1 < len(merged) else None

        # 极短且与下一条存在“前缀/后缀增量关系”时，判定为中间态字幕，跳过
        if nxt and dur < tiny_threshold:
            a = sub["text"]
            b = nxt["text"]
            if b.startswith(a) or a.startswith(b):
                continue

        cleaned.append(sub)

    return cleaned

def extract_subtitle_clip(vtt_file, start_time, end_time, output_file):
    """提取字幕片段"""
    # 解析时间
    start_seconds = parse_vtt_time(start_time)
    end_seconds = parse_vtt_time(end_time)

    print(f"📝 提取字幕片段...")
    print(f"   输入: {vtt_file}")
    print(f"   时间范围: {start_time} - {end_time}")
    print(f"   时间范围（秒）: {start_seconds:.1f}s - {end_seconds:.1f}s")

    # 读取 VTT 文件
    with open(vtt_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # 解析字幕
    subtitles = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # 查找时间戳行
        if '-->' in line:
            # 解析时间戳
            time_parts = line.split('-->')
            sub_start_str = time_parts[0].strip().split()[0]
            sub_end_str = time_parts[1].strip().split()[0]

            sub_start = parse_vtt_time(sub_start_str)
            sub_end = parse_vtt_time(sub_end_str)

            # 检查与目标时间范围是否有重叠（不再只保留“完全包含”）
            if sub_start < end_seconds and sub_end > start_seconds:
                # 收集字幕文本
                i += 1
                text_lines = []
                while i < len(lines) and lines[i].strip() != '':
                    text_lines.append(lines[i].strip())
                    i += 1

                text = normalize_vtt_text(text_lines)
                if not text:
                    continue

                # 调整时间戳并裁剪到片段边界
                adjusted_start = max(0.0, sub_start - start_seconds)
                adjusted_end = min(end_seconds - start_seconds, sub_end - start_seconds)
                if adjusted_end <= adjusted_start:
                    continue

                subtitles.append({
                    'start': adjusted_start,
                    'end': adjusted_end,
                    'text': text
                })

        i += 1

    subtitles = compact_incremental_cues(subtitles)

    print(f"   找到 {len(subtitles)} 条字幕")

    # 写入 SRT 格式
    with open(output_file, 'w', encoding='utf-8') as f:
        for idx, sub in enumerate(subtitles, 1):
            f.write(f"{idx}\n")
            f.write(f"{format_srt_time(sub['start'])} --> {format_srt_time(sub['end'])}\n")
            f.write(f"{sub['text']}\n")
            f.write("\n")

    print(f"✅ 字幕提取完成")
    print(f"   输出文件: {output_file}")
    print(f"   字幕条数: {len(subtitles)}")

    return subtitles

if __name__ == '__main__':
    if len(sys.argv) != 5:
        print("用法: python extract_subtitle_clip.py <vtt_file> <start_time> <end_time> <output_file>")
        print("示例: python extract_subtitle_clip.py input.vtt 00:05:47 00:09:19 output.srt")
        sys.exit(1)

    vtt_file = sys.argv[1]
    start_time = sys.argv[2]
    end_time = sys.argv[3]
    output_file = sys.argv[4]

    extract_subtitle_clip(vtt_file, start_time, end_time, output_file)
