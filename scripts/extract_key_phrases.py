#!/usr/bin/env python3
"""
提取关键表达（单词/短语）
用于学习型短片的字幕挖空和 summary 卡片
"""

import sys
import json
from pathlib import Path
from typing import List, Dict

try:
    import pysrt
except ImportError:
    print("❌ Error: pysrt not installed")
    print("Please install: pip install pysrt")
    sys.exit(1)


def load_srt_text(srt_path: str) -> List[str]:
    srt_path = Path(srt_path)
    if not srt_path.exists():
        raise FileNotFoundError(f"SRT file not found: {srt_path}")

    subs = pysrt.open(srt_path)
    lines = []
    for sub in subs:
        text = sub.text.replace("\n", " ").strip()
        if text:
            lines.append(text)
    return lines


def extract_key_phrases(
    srt_path: str,
    max_phrases: int = 6
) -> List[Dict]:
    """
    提取关键表达（占位）
    在 Skill 环境中由 Claude 自动填充
    """
    print(f"🔎 提取关键表达...")
    print(f"   输入字幕: {srt_path}")
    print(f"   期望数量: {max_phrases}")

    lines = load_srt_text(srt_path)

    print("\n" + "=" * 60)
    print("字幕文本（供 Claude 提取关键表达）:")
    print("=" * 60)
    preview = lines[:50]
    for line in preview:
        print(line)
    if len(lines) > 50:
        print(f"... （还有 {len(lines) - 50} 行）")

    print("\n" + "=" * 60)
    print("提取要求:")
    print("=" * 60)
    print(f"""
请从上述字幕中提取 {max_phrases} 个关键表达（单词或短语）。

输出格式（JSON）：
[
  {{"phrase": "key phrase 1", "translation": "中文释义1"}},
  {{"phrase": "key phrase 2", "translation": "中文释义2"}},
  ...
]
""")

    # 占位输出（由 Claude 在 Skill 执行时替换）
    placeholders = []
    for _ in range(max_phrases):
        placeholders.append({
            "phrase": "[待提取]",
            "translation": "[待翻译]"
        })

    return placeholders


def save_phrases(phrases: List[Dict], output_path: str) -> str:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(phrases, f, indent=2, ensure_ascii=False)

    print(f"✅ 关键表达已保存: {output_path}")
    return str(output_path)


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_key_phrases.py <subtitle.srt> [output_json] [max_phrases]")
        print("Example:")
        print("  python extract_key_phrases.py clip.srt key_phrases.json 6")
        sys.exit(1)

    srt_path = sys.argv[1]
    output_json = sys.argv[2] if len(sys.argv) > 2 else "key_phrases.json"
    max_phrases = int(sys.argv[3]) if len(sys.argv) > 3 else 6

    try:
        phrases = extract_key_phrases(srt_path, max_phrases=max_phrases)
        save_phrases(phrases, output_json)
    except Exception as e:
        print(f"\n❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
