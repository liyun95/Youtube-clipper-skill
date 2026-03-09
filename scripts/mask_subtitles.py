#!/usr/bin/env python3
"""
字幕挖空：按关键词列表将字幕中的关键表达替换为占位符
"""

import sys
import json
import re
import os
from pathlib import Path
from typing import List, Dict, Tuple

try:
    import pysrt
except ImportError:
    print("❌ Error: pysrt not installed")
    print("Please install: pip install pysrt")
    sys.exit(1)


def env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    return value.strip() if value else default


def load_phrases(phrases_path: str) -> List[str]:
    phrases_path = Path(phrases_path)
    if not phrases_path.exists():
        raise FileNotFoundError(f"Phrases file not found: {phrases_path}")

    with open(phrases_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    phrases = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, str):
                if item.strip():
                    phrases.append(item.strip())
            elif isinstance(item, dict):
                phrase = item.get("phrase") or item.get("text")
                if phrase and str(phrase).strip():
                    phrases.append(str(phrase).strip())
    else:
        raise ValueError("Invalid phrases JSON: expected list")

    # 去重并按长度降序（优先匹配长短语）
    unique = []
    seen = set()
    for p in phrases:
        key = p.lower()
        if key not in seen:
            unique.append(p)
            seen.add(key)

    unique.sort(key=len, reverse=True)
    return unique


def build_pattern(phrase: str) -> re.Pattern:
    escaped = re.escape(phrase)
    # 使用单词边界避免误伤子串
    pattern = rf"(?i)(?<!\w){escaped}(?!\w)"
    return re.compile(pattern)


def mask_text(text: str, patterns: List[Tuple[str, re.Pattern]], mask_token: str) -> Tuple[str, int]:
    replaced = 0
    new_text = text
    for phrase, pattern in patterns:
        new_text, count = pattern.subn(mask_token, new_text)
        replaced += count
    return new_text, replaced


def mask_subtitles(
    srt_path: str,
    phrases_path: str,
    output_path: str,
    mask_token: str = None
) -> str:
    srt_path = Path(srt_path)
    if not srt_path.exists():
        raise FileNotFoundError(f"SRT file not found: {srt_path}")

    phrases = load_phrases(phrases_path)
    if not phrases:
        raise ValueError("No phrases found for masking")

    mask_token = mask_token or env_str("MASK_TOKEN", "____")

    patterns = [(p, build_pattern(p)) for p in phrases]

    print(f"🕳️  字幕挖空处理中...")
    print(f"   输入字幕: {srt_path}")
    print(f"   关键词数: {len(phrases)}")
    print(f"   占位符: {mask_token}")

    subs = pysrt.open(str(srt_path))

    total_replaced = 0
    for sub in subs:
        original = sub.text
        masked, count = mask_text(original, patterns, mask_token)
        if count > 0:
            sub.text = masked
            total_replaced += count

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    subs.save(str(output_path), encoding="utf-8")

    print(f"✅ 挖空完成: {output_path}")
    print(f"   替换次数: {total_replaced}")

    return str(output_path)


def main():
    if len(sys.argv) < 3:
        print("Usage: python mask_subtitles.py <subtitle.srt> <phrases.json> [output.srt] [mask_token]")
        print("Example:")
        print("  python mask_subtitles.py clip.srt key_phrases.json masked.srt ____")
        sys.exit(1)

    srt_path = sys.argv[1]
    phrases_path = sys.argv[2]
    output_path = sys.argv[3] if len(sys.argv) > 3 else "masked.srt"
    mask_token = sys.argv[4] if len(sys.argv) > 4 else None

    try:
        mask_subtitles(srt_path, phrases_path, output_path, mask_token)
    except Exception as e:
        print(f"\n❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
