# YouTube Clipper Skill

> Claude Code 的 AI 智能视频剪辑工具。下载视频、生成语义章节、剪辑片段、翻译双语字幕并烧录字幕到视频。

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

[English](README.md) | 简体中文

[功能特性](#功能特性) • [安装](#安装) • [使用方法](#使用方法) • [系统要求](#系统要求) • [配置](#配置) • [常见问题](#常见问题)

---

## 功能特性

- **AI 语义分析** - 通过理解视频内容生成精细章节（每个 2-5 分钟），而非机械按时间切分
- **精确剪辑** - 使用 FFmpeg 以帧精度提取视频片段
- **双语字幕** - 批量翻译字幕为中英双语，减少 95% 的 API 调用
- **字幕烧录** - 将双语字幕硬编码到视频中，支持自定义样式
- **内容总结** - 自动生成适合社交媒体的文案（小红书、抖音、微信公众号）
- **学习型短片** - 双遍学习模式：英文挖空首遍 + 完整双语次遍 + summary 卡片

---

## 安装

### 方式 1: npx skills（推荐）

```bash
npx skills add https://github.com/op7418/Youtube-clipper-skill
```

该命令会自动将 skill 安装到 `~/.claude/skills/youtube-clipper/` 目录。

### 方式 2: 手动安装

```bash
git clone https://github.com/op7418/Youtube-clipper-skill.git
cd Youtube-clipper-skill
bash install_as_skill.sh
```

安装脚本会：
- 复制文件到 `~/.claude/skills/youtube-clipper/`
- 安装 Python 依赖（yt-dlp、pysrt、python-dotenv）
- 检查系统依赖（Python、yt-dlp、FFmpeg）
- 创建 `.env` 配置文件

---

## 系统要求

### 系统依赖

| 依赖项 | 版本 | 用途 | 安装方法 |
|--------|------|------|----------|
| **Python** | 3.8+ | 脚本执行 | [python.org](https://www.python.org/downloads/) |
| **yt-dlp** | 最新版 | YouTube 视频下载 | `brew install yt-dlp` (macOS)<br>`sudo apt install yt-dlp` (Ubuntu)<br>`pip install yt-dlp` (pip) |
| **FFmpeg with libass** | 最新版 | 视频处理和字幕烧录 | `brew install ffmpeg-full` (macOS)<br>`sudo apt install ffmpeg libass-dev` (Ubuntu) |

### Python 包

安装脚本会自动安装以下包（详见 [requirements.txt](requirements.txt)）：

| 包名 | 版本 | 用途 |
|------|------|------|
| `yt-dlp` | >=2024.0.0 | YouTube 视频/字幕下载 |
| `pysrt` | >=1.1.2 | SRT 字幕解析和处理 |
| `python-dotenv` | >=1.0.0 | 环境变量管理 |
| `chardet` | >=5.0.0 | 字符编码检测 |

手动安装命令：
```bash
pip install -r requirements.txt
```

### 重要：FFmpeg libass 支持

**macOS 用户注意**：Homebrew 的标准 `ffmpeg` 包不包含 libass 支持（字幕烧录必需）。你必须安装 `ffmpeg-full`：

```bash
# 卸载标准 ffmpeg（如果已安装）
brew uninstall ffmpeg

# 安装 ffmpeg-full（包含 libass）
brew install ffmpeg-full
```

**验证 libass 支持**：
```bash
ffmpeg -filters 2>&1 | grep subtitles
# 应该输出：subtitles    V->V  (...)
```

---

## 使用方法

### 在 Claude Code 中使用

只需告诉 Claude 剪辑一个 YouTube 视频：

```
Clip this YouTube video: https://youtube.com/watch?v=VIDEO_ID
```

或者

```
剪辑这个 YouTube 视频：https://youtube.com/watch?v=VIDEO_ID
```

### 工作流程

1. **环境检测** - 验证 yt-dlp、FFmpeg 和 Python 依赖
2. **视频下载** - 下载视频（最高 1080p）和英文字幕
3. **AI 章节分析** - Claude 分析字幕生成语义章节（每个 2-5 分钟）
4. **用户选择** - 选择要剪辑的章节和处理选项
5. **处理** - 剪辑视频、翻译字幕、烧录字幕（如果需要）
6. **输出** - 组织文件到 `./youtube-clips/<时间戳>/`

### 输出文件

每个剪辑的章节包含：

```
./youtube-clips/20260122_143022/
└── 章节标题/
    ├── 章节标题_clip.mp4              # 原始剪辑（无字幕）
    ├── 章节标题_with_subtitles.mp4   # 带烧录字幕的视频
    ├── 章节标题_bilingual.srt        # 双语字幕文件
    └── 章节标题_summary.md           # 社交媒体文案
```

### 学习型短片模式（5 段结构）

生成 30-60s 学习短片，采用专为语言学习设计的 5 段结构：

```
┌─────────┐   ┌─────────┐   ┌────────────┐   ┌─────────────────┐   ┌─────────┐
│  引导   │ → │  挖空   │ → │    过渡    │ → │  完整+下划线    │ → │ Summary │
│  卡片   │   │  视频   │   │    卡片    │   │     视频        │   │  卡片   │
│  (4秒)  │   │(30-60秒)│   │   (3秒)    │   │   (30-60秒)     │   │  (4秒)  │
└─────────┘   └─────────┘   └────────────┘   └─────────────────┘   └─────────┘
```

**各段说明：**
1. **引导卡片** - 显示关键表达的空白占位符，提示用户仔细听
2. **挖空视频** - 第一遍，关键表达被替换为 `____`
3. **过渡卡片** - 提示即将揭晓答案，关键表达将带下划线
4. **完整视频** - 第二遍，完整双语字幕，关键表达带下划线标注
5. **Summary 卡片** - 列出所有关键表达及其翻译

```bash
python scripts/learning_clip.py video.mp4 video.en.vtt 00:05:00 00:05:45 --output ./youtube-clips --name demo_clip
```

输出文件：
```
./youtube-clips/demo_clip/
├── demo_clip_clip.mp4           # 原始片段
├── demo_clip_clip.srt           # 原始字幕
├── demo_clip_key_phrases.json   # 提取的关键表达
├── demo_clip_masked.srt         # 挖空字幕（带 ____）
├── demo_clip_bilingual.srt      # 双语字幕
├── demo_clip_underlined.ass     # 带下划线的 ASS 字幕
├── demo_clip_intro.mp4          # 引导卡片
├── demo_clip_masked.mp4         # 第一遍视频
├── demo_clip_transition.mp4     # 过渡卡片
├── demo_clip_full.mp4           # 第二遍视频（下划线标注）
├── demo_clip_summary.mp4        # Summary 卡片
└── demo_clip_learning.mp4       # 最终拼接输出
```

**下划线格式（ASS）：**
第二遍视频中的关键表达使用 ASS 下划线标签标注：
```
She had a {\u1}black belt{\u0} in small talk.
```


### Codex 工作流（无 API）

**限制说明：** 没有 API key 时无法自动化语义分析。Codex 可以在对话中做语义分析，但这一步是人工流程。

**为什么要提供 URL 或字幕文件：** Codex 需要时间戳来提出 3–5 个 30–60s 的候选片段。

**选项 A：YouTube URL**
1. 提供 URL 和学习目标（例如“听力填空”）。
2. Codex 下载 MP4/VTT。
3. Codex 先在本次输出目录下生成候选产物：
   `python scripts/prepare_learning_candidates.py <subtitle.vtt> --output ./youtube-clips --name <base>`
4. Codex 基于 `<output>/<base>/<video_id>_candidate_report.md` 给出 3–5 个候选片段（带排序）。
5. 你选择其中一个片段（或自动选第 1 名）。
6. Codex 运行：
   `~/.codex/skills/learning-video-maker/scripts/learning_clip_guided.py <video.mp4> <subtitle.vtt|srt> <start> <end> --output <dir> --name <base>`

**选项 B：本地 MP4 + VTT**
1. 提供本地 `video.mp4` 和 `subtitle.vtt|srt` 路径，并说明学习目标。
2. Codex 运行：
   `python scripts/prepare_learning_candidates.py <subtitle.vtt> --output ./youtube-clips --name <base>`
3. Codex 基于生成报告给出 3–5 个候选片段（带排序）。
4. 你选择其中一个片段（或自动选第 1 名）。
5. Codex 运行同一条引导脚本。

候选产物统一保存在 `<output>/<base>/` 下（不会散落到项目根目录）：
- `<video_id>_analysis.json`
- `<video_id>_candidates.json`
- `<video_id>_candidate_report.md`

---

## 配置

本 skill 使用环境变量进行自定义配置。编辑 `~/.claude/skills/youtube-clipper/.env`：

### 主要设置

```bash
# FFmpeg 路径（留空则自动检测）
FFMPEG_PATH=

# 输出目录（默认：当前工作目录）
OUTPUT_DIR=./youtube-clips

# 视频质量限制（720、1080、1440、2160）
MAX_VIDEO_HEIGHT=1080

# 翻译批次大小（推荐 20-25）
TRANSLATION_BATCH_SIZE=20

# 目标翻译语言
TARGET_LANGUAGE=中文

# 目标章节时长（秒，推荐 180-300）
TARGET_CHAPTER_DURATION=180
```

### 学习型短片设置

```bash
# 学习型短片时长（秒）
LEARNING_CLIP_MIN_SEC=30
LEARNING_CLIP_MAX_SEC=60
LEARNING_CLIP_TARGET_SEC=45

# 字幕挖空占位符
MASK_TOKEN=____

# 引导卡片（第一遍前的提示）
INTRO_DURATION_SEC=4
INTRO_TITLE_COLOR=#7AD7FF
INTRO_SUBTITLE_COLOR=#FFFFFF
INTRO_BLANK_COLOR=#FFD54F

# 过渡卡片（第一遍和第二遍之间）
TRANSITION_DURATION_SEC=3
TRANSITION_TITLE_COLOR=#7AD7FF
TRANSITION_SUBTITLE_COLOR=#FFFFFF

# Summary 卡片（关键表达列表）
SUMMARY_DURATION_SEC=4
SUMMARY_TITLE_COLOR=#7AD7FF
SUMMARY_EN_COLOR=#FFD54F
SUMMARY_ZH_COLOR=#FFFFFF
SUMMARY_INCLUDE_TRANSLATION=true
```

### 字幕样式

```bash
# 字体设置
SUBTITLE_FONT_NAME=PingFang SC
SUBTITLE_FONT_SIZE=24
SUBTITLE_MARGIN_V=30
SUBTITLE_OUTLINE=2
SUBTITLE_SHADOW=1

# 双语字幕配色
BILINGUAL_COLOR=true
BILINGUAL_ORDER=EN_FIRST
SUBTITLE_EN_COLOR=#FFD54F
SUBTITLE_ZH_COLOR=#FFFFFF
```

完整配置选项请参见 [.env.example](.env.example)。

---

## 使用示例

### 示例 1：从技术访谈中提取精华

**输入**：
```
剪辑这个视频：https://youtube.com/watch?v=Ckt1cj0xjRM
```

**输出**（AI 生成的章节）：
```
1. [00:00 - 03:15] AGI 是指数曲线而非时间点
2. [03:15 - 06:30] 中国在 AI 领域的差距
3. [06:30 - 09:45] 芯片禁令的影响
...
```

**结果**：选择章节 → 获得带双语字幕的剪辑视频 + 社交媒体文案

### 示例 2：从课程视频创建短片

**输入**：
```
剪辑这个讲座视频并创建双语字幕：https://youtube.com/watch?v=LECTURE_ID
```

**选项**：
- 生成双语字幕：是
- 烧录字幕到视频：是
- 生成总结：是

**结果**：可直接在社交媒体平台分享的高质量剪辑视频

### 示例 3：制作双遍学习短片（30-60s）

**输入**：
```
~/.codex/skills/learning-video-maker/scripts/learning_clip_guided.py video.mp4 video.en.vtt 00:12:10 00:12:55 --name vocab_boost
```

**结果**：英文挖空首遍 + 完整双语次遍 + summary 卡片，拼接成最终视频

---

## 核心差异化功能

### AI 语义章节分析

与机械按时间切分不同，本 skill 使用 Claude AI 来：
- 理解内容语义
- 识别自然的主题转换点
- 生成有意义的章节标题和摘要
- 确保完整覆盖，无遗漏

**示例**：
```
❌ 机械切分：[0:00-30:00]、[30:00-60:00]
✅ AI 语义分析：
   - [00:00-03:15] AGI 定义
   - [03:15-07:30] 中国的 AI 格局
   - [07:30-12:00] 芯片禁令影响
```

### 批量翻译优化

一次翻译 20 条字幕，而非逐条翻译：
- 减少 95% 的 API 调用
- 速度提升 10 倍
- 更好的翻译一致性

### 双语字幕格式

生成的字幕文件同时包含英文和中文：

```srt
1
00:00:00,000 --> 00:00:03,500
This is the English subtitle
这是中文字幕

2
00:00:03,500 --> 00:00:07,000
Another English line
另一行中文
```

---

## 常见问题

### FFmpeg 字幕烧录失败

**错误**：`Option not found: subtitles` 或 `filter not found`

**解决方案**：安装 `ffmpeg-full`（macOS）或确保安装了 `libass-dev`（Ubuntu）：
```bash
# macOS
brew uninstall ffmpeg
brew install ffmpeg-full

# Ubuntu
sudo apt install ffmpeg libass-dev
```

### 视频下载速度慢

**解决方案**：在 `.env` 中设置代理：
```bash
YT_DLP_PROXY=http://proxy-server:port
# 或
YT_DLP_PROXY=socks5://proxy-server:port
```

### 字幕翻译失败

**原因**：API 限流或网络问题

**解决方案**：skill 会自动重试最多 3 次。如果持续失败，请检查：
- 网络连接
- Claude API 状态
- 减少 `.env` 中的 `TRANSLATION_BATCH_SIZE`

### 文件名包含特殊字符

**问题**：文件名中的 `:`、`/`、`?` 等可能导致错误

**解决方案**：skill 会自动清理文件名：
- 移除特殊字符：`/ \ : * ? " < > |`
- 将空格替换为下划线
- 限制长度为 100 字符

---

## 文档

- **[SKILL.md](SKILL.md)** - 完整工作流程和技术细节
- **[TECHNICAL_NOTES.md](TECHNICAL_NOTES.md)** - 实现笔记和设计决策
- **[FIXES_AND_IMPROVEMENTS.md](FIXES_AND_IMPROVEMENTS.md)** - 更新日志和 Bug 修复
- **[references/](references/)** - FFmpeg、yt-dlp 和字幕格式指南

---

## 贡献

欢迎贡献！请：
- 通过 [GitHub Issues](https://github.com/op7418/Youtube-clipper-skill/issues) 报告 Bug
- 提交功能请求
- 为改进提交 Pull Request

---

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

---

## 致谢

- **[Claude Code](https://claude.ai/claude-code)** - AI 驱动的 CLI 工具
- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** - YouTube 下载引擎
- **[FFmpeg](https://ffmpeg.org/)** - 视频处理利器

---

<div align="center">

**Made with ❤️ by [op7418](https://github.com/op7418)**

如果这个 skill 对你有帮助，请给个 ⭐️

</div>
