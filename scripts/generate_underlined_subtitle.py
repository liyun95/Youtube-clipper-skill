#!/usr/bin/env python3
"""
生成带下划线标注的双语 ASS 字幕
用于第二遍视频，对关键表达添加下划线高亮
"""

import sys
import json
import re
import os
import traceback
from pathlib import Path
from typing import List, Dict, Tuple, Optional

try:
    import pysrt
except ImportError:
    print("❌ Error: pysrt not installed")
    print("Please install: pip install pysrt")
    sys.exit(1)


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


def load_phrases(phrases_path: str) -> List[str]:
    """加载关键表达列表"""
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

    unique = []
    seen = set()
    for p in phrases:
        key = p.lower()
        if key not in seen:
            unique.append(p)
            seen.add(key)

    unique.sort(key=len, reverse=True)
    return unique


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


def build_underline_pattern(phrase: str) -> re.Pattern:
    """构建关键表达匹配正则（单词边界，大小写不敏感）"""
    escaped = re.escape(phrase)
    pattern = rf"(?i)(?<!\w)({escaped})(?!\w)"
    return re.compile(pattern)


def add_underline_to_text(text: str, patterns: List[Tuple[str, re.Pattern]]) -> str:
    """
    在文本中对匹配的关键表达添加 ASS 下划线标记

    Args:
        text: 原始文本
        patterns: [(phrase, compiled_pattern), ...]

    Returns:
        带 ASS 下划线标记的文本
    """
    result = text
    for phrase, pattern in patterns:
        def replacer(match):
            matched = match.group(1)
            return f"{{\\u1}}{matched}{{\\u0}}"
        result = pattern.sub(replacer, result)
    return result


def generate_underlined_subtitle(
    srt_path: str,
    phrases_path: str,
    output_path: str,
    translations: List[Dict] = None,
    font_name: str = None,
    font_size: int = None,
    margin_v: int = None,
    outline: int = None,
    shadow: int = None,
    alignment: int = None,
    en_color: str = None,
    zh_color: str = None,
    bilingual_order: str = None,
    play_res: Tuple[int, int] = None
) -> str:
    """
    生成带下划线标注的双语 ASS 字幕

    Args:
        srt_path: 英文 SRT 字幕路径
        phrases_path: 关键表达 JSON 路径
        output_path: 输出 ASS 路径
        translations: 翻译列表 [{start, end, text, translation}, ...]
        font_name: 字体名称
        font_size: 字体大小
        margin_v: 底部边距
        outline: 描边宽度
        shadow: 阴影
        alignment: 对齐方式
        en_color: 英文颜色（ASS 格式）
        zh_color: 中文颜色（ASS 格式）
        bilingual_order: 双语顺序 (EN_FIRST / ZH_FIRST)
        play_res: 分辨率 (width, height)

    Returns:
        str: 输出 ASS 路径
    """
    srt_path = Path(srt_path)
    if not srt_path.exists():
        raise FileNotFoundError(f"SRT file not found: {srt_path}")

    phrases = load_phrases(phrases_path)
    if not phrases:
        print("⚠️  未找到关键表达，将生成普通双语字幕")

    patterns = [(p, build_underline_pattern(p)) for p in phrases]

    font_name = font_name or env_str("SUBTITLE_FONT_NAME", "PingFang SC")
    # ASS 字体大小需要比 SRT force_style 更大才能视觉匹配
    font_size = font_size or env_int("SUBTITLE_FONT_SIZE_ASS", env_int("SUBTITLE_FONT_SIZE", 28))
    margin_v = margin_v or env_int("SUBTITLE_MARGIN_V", 30)
    outline = outline or env_int("SUBTITLE_OUTLINE", 2)
    shadow = shadow or env_int("SUBTITLE_SHADOW", 1)
    alignment = alignment or env_int("SUBTITLE_ALIGNMENT", 2)

    # 英文白色，中文浅蓝色（与 tellmemore 样式一致）
    en_hex = env_str("SUBTITLE_EN_COLOR", "#FFFFFF")
    zh_hex = env_str("SUBTITLE_ZH_COLOR", "#7AD7FF")
    en_color = en_color or to_ass_color(en_hex, "#FFFFFF")
    zh_color = zh_color or to_ass_color(zh_hex, "#7AD7FF")

    bilingual_order = bilingual_order or env_str("BILINGUAL_ORDER", "EN_FIRST")
    play_res_x = play_res[0] if play_res else env_int("SUBTITLE_PLAYRESX", 1920)
    play_res_y = play_res[1] if play_res else env_int("SUBTITLE_PLAYRESY", 1080)

    print(f"🖊️  生成带下划线的双语字幕...")
    print(f"   输入字幕: {srt_path}")
    print(f"   关键表达: {len(phrases)} 个")
    print(f"   输出: {output_path}")

    subs = pysrt.open(str(srt_path))

    translation_map = {}
    if translations:
        for t in translations:
            key = (round(t['start'], 2), round(t['end'], 2))
            translation_map[key] = t.get('translation', '')

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

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    underline_count = 0

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header)

        for sub in subs:
            start = (
                sub.start.hours * 3600 +
                sub.start.minutes * 60 +
                sub.start.seconds +
                sub.start.milliseconds / 1000
            )
            end = (
                sub.end.hours * 3600 +
                sub.end.minutes * 60 +
                sub.end.seconds +
                sub.end.milliseconds / 1000
            )

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

                en_text = " ".join(en_lines)
                zh_text = " ".join(zh_lines)
            else:
                en_text = lines[0]
                key = (round(start, 2), round(end, 2))
                zh_text = translation_map.get(key, "")

            original_en = en_text
            en_text_with_underline = add_underline_to_text(en_text, patterns)

            if en_text_with_underline != original_en:
                underline_count += 1

            text = f"{{\\c{en_color}}}{en_text_with_underline}"
            if zh_text:
                text += f"\\N{{\\c{zh_color}}}{zh_text}"

            f.write(
                f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Default,,0,0,0,,{text}\n"
            )

    print(f"✅ 下划线字幕生成完成")
    print(f"   添加下划线: {underline_count} 处")

    return str(output_path)


def main():
    if len(sys.argv) < 4:
        print("Usage: python generate_underlined_subtitle.py <subtitle.srt> <phrases.json> <output.ass>")
        print("Example:")
        print("  python generate_underlined_subtitle.py clip.srt key_phrases.json underlined.ass")
        sys.exit(1)

    srt_path = sys.argv[1]
    phrases_path = sys.argv[2]
    output_path = sys.argv[3]

    try:
        generate_underlined_subtitle(srt_path, phrases_path, output_path)
    except Exception as e:
        print(f"\n❌ 错误: {str(e)}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
