# YouTube Clipper Skill

> AI-powered YouTube video clipper for Claude Code. Download videos, generate semantic chapters, clip segments, translate subtitles to bilingual format, and burn subtitles into videos.

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

English | [简体中文](README.zh-CN.md)

[Features](#features) • [Installation](#installation) • [Usage](#usage) • [Requirements](#requirements) • [Configuration](#configuration) • [Troubleshooting](#troubleshooting)

---

## Features

- **AI Semantic Analysis** - Generate fine-grained chapters (2-5 minutes each) by understanding video content, not just mechanical time splitting
- **Precise Clipping** - Use FFmpeg to extract video segments with frame-accurate timing
- **Bilingual Subtitles** - Batch translate subtitles to Chinese/English with 95% API call reduction
- **Subtitle Burning** - Hardcode bilingual subtitles into videos with customizable styling
- **Content Summarization** - Auto-generate social media content (Xiaohongshu, Douyin, WeChat)
- **Learning Clip Mode** - Create dual-pass learning clips: masked English first pass + full bilingual second pass + summary card

---

## Installation

### Option 1: npx skills (Recommended)

```bash
npx skills add https://github.com/op7418/Youtube-clipper-skill
```

This command will automatically install the skill to `~/.claude/skills/youtube-clipper/`.

### Option 2: Manual Installation

```bash
git clone https://github.com/op7418/Youtube-clipper-skill.git
cd Youtube-clipper-skill
bash install_as_skill.sh
```

The install script will:
- Copy files to `~/.claude/skills/youtube-clipper/`
- Install Python dependencies (yt-dlp, pysrt, python-dotenv)
- Check system dependencies (Python, yt-dlp, FFmpeg)
- Create `.env` configuration file

---

## Requirements

### System Dependencies

| Dependency | Version | Purpose | Installation |
|------------|---------|---------|--------------|
| **Python** | 3.8+ | Script execution | [python.org](https://www.python.org/downloads/) |
| **yt-dlp** | Latest | YouTube download | `brew install yt-dlp` (macOS)<br>`sudo apt install yt-dlp` (Ubuntu)<br>`pip install yt-dlp` (pip) |
| **FFmpeg with libass** | Latest | Video processing & subtitle burning | `brew install ffmpeg-full` (macOS)<br>`sudo apt install ffmpeg libass-dev` (Ubuntu) |

### Python Packages

These are automatically installed by the install script (see [requirements.txt](requirements.txt)):

| Package | Version | Purpose |
|---------|---------|---------|
| `yt-dlp` | >=2024.0.0 | YouTube video/subtitle download |
| `pysrt` | >=1.1.2 | SRT subtitle parsing and manipulation |
| `python-dotenv` | >=1.0.0 | Environment variable management |
| `chardet` | >=5.0.0 | Character encoding detection |

Install manually if needed:
```bash
pip install -r requirements.txt
```

### Important: FFmpeg libass Support

**macOS users**: The standard `ffmpeg` package from Homebrew does NOT include libass support (required for subtitle burning). You must install `ffmpeg-full`:

```bash
# Remove standard ffmpeg (if installed)
brew uninstall ffmpeg

# Install ffmpeg-full (includes libass)
brew install ffmpeg-full
```

**Verify libass support**:
```bash
ffmpeg -filters 2>&1 | grep subtitles
# Should output: subtitles    V->V  (...)
```

---

## Usage

### In Claude Code

Simply tell Claude to clip a YouTube video:

```
Clip this YouTube video: https://youtube.com/watch?v=VIDEO_ID
```

or

```
剪辑这个 YouTube 视频：https://youtube.com/watch?v=VIDEO_ID
```

### Workflow

1. **Environment Check** - Verifies yt-dlp, FFmpeg, and Python dependencies
2. **Video Download** - Downloads video (up to 1080p) and English subtitles
3. **AI Chapter Analysis** - Claude analyzes subtitles to generate semantic chapters (2-5 min each)
4. **User Selection** - Choose which chapters to clip and processing options
5. **Processing** - Clips video, translates subtitles, burns subtitles (if requested)
6. **Output** - Organized files in `./youtube-clips/<timestamp>/`

### Output Files

For each clipped chapter:

```
./youtube-clips/20260122_143022/
└── Chapter_Title/
    ├── Chapter_Title_clip.mp4              # Original clip (no subtitles)
    ├── Chapter_Title_with_subtitles.mp4    # With burned subtitles
    ├── Chapter_Title_bilingual.srt         # Bilingual subtitle file
    └── Chapter_Title_summary.md            # Social media content
```

### Learning Clip Mode (5-Segment Structure)

Create a 30-60s learning clip with a structured 5-segment format designed for language learning:

```
┌─────────┐   ┌─────────┐   ┌────────────┐   ┌─────────────────┐   ┌─────────┐
│  Intro  │ → │ Masked  │ → │ Transition │ → │ Full + Underline│ → │ Summary │
│  Card   │   │  Video  │   │    Card    │   │     Video       │   │  Card   │
│  (4s)   │   │ (30-60s)│   │    (3s)    │   │    (30-60s)     │   │  (4s)   │
└─────────┘   └─────────┘   └────────────┘   └─────────────────┘   └─────────┘
```

**Segment Details:**
1. **Intro Card** - Shows blank placeholders for key expressions, prompts user to listen and fill
2. **Masked Video** - First pass with key expressions blanked out (`____`)
3. **Transition Card** - Announces the answer reveal with underlined key expressions
4. **Full Video** - Second pass with complete bilingual subtitles, key expressions underlined
5. **Summary Card** - Lists all key expressions with translations

```bash
python scripts/learning_clip.py video.mp4 video.en.vtt 00:05:00 00:05:45 --output ./youtube-clips --name demo_clip
```

Output files:
```
./youtube-clips/demo_clip/
├── demo_clip_clip.mp4           # Original clip
├── demo_clip_clip.srt           # Original subtitles
├── demo_clip_key_phrases.json   # Extracted key expressions
├── demo_clip_masked.srt         # Masked subtitles (with ____)
├── demo_clip_bilingual.srt      # Bilingual subtitles
├── demo_clip_underlined.ass     # ASS subtitles with underlines
├── demo_clip_intro.mp4          # Intro guidance card
├── demo_clip_masked.mp4         # First pass video
├── demo_clip_transition.mp4     # Transition card
├── demo_clip_full.mp4           # Second pass video (underlined)
├── demo_clip_summary.mp4        # Summary card
└── demo_clip_learning.mp4       # Final concatenated output
```

**Underline Format (ASS):**
Key expressions in the second pass are underlined using ASS tags:
```
She had a {\u1}black belt{\u0} in small talk.
```


### Codex Workflow (No API)

**Limit:** Semantic analysis is not automated without an API key. Codex can analyze in-chat, but it is a manual step.

**Why Codex asks for a URL or subtitle file:** it needs timestamps to propose 3–5 candidate 30–60s ranges for learning clips.

**Option A: YouTube URL**
1. Provide the URL and your learning goal (e.g., “listening cloze”).
2. Codex downloads MP4/VTT.
3. Codex generates candidate artifacts directly in the run directory:
   `python scripts/prepare_learning_candidates.py <subtitle.vtt> --output ./youtube-clips --name <base>`
4. Codex proposes 3–5 ranked 30–60s ranges from `<output>/<base>/<video_id>_candidate_report.md`.
5. You pick one range (or auto-pick rank #1).
6. Codex runs:
   `~/.codex/skills/learning-video-maker/scripts/learning_clip_guided.py <video.mp4> <subtitle.vtt|srt> <start> <end> --output <dir> --name <base>`

**Option B: Local MP4 + VTT**
1. Provide local `video.mp4` and `subtitle.vtt|srt` paths plus your learning goal.
2. Codex runs:
   `python scripts/prepare_learning_candidates.py <subtitle.vtt> --output ./youtube-clips --name <base>`
3. Codex proposes 3–5 ranked 30–60s ranges from the generated report.
4. You pick one range (or auto-pick rank #1).
5. Codex runs the same guided script above.

All candidate artifacts are kept under `<output>/<base>/` (no project-root spill):
- `<video_id>_analysis.json`
- `<video_id>_candidates.json`
- `<video_id>_candidate_report.md`

---

## Configuration

The skill uses environment variables for customization. Edit `~/.claude/skills/youtube-clipper/.env`:

### Key Settings

```bash
# FFmpeg path (auto-detected if empty)
FFMPEG_PATH=

# Output directory (default: current working directory)
OUTPUT_DIR=./youtube-clips

# Video quality limit (720, 1080, 1440, 2160)
MAX_VIDEO_HEIGHT=1080

# Translation batch size (20-25 recommended)
TRANSLATION_BATCH_SIZE=20

# Target language for translation
TARGET_LANGUAGE=中文

# Target chapter duration in seconds (180-300 recommended)
TARGET_CHAPTER_DURATION=180
```

### Learning Clip Settings

```bash
# Learning clip duration (seconds)
LEARNING_CLIP_MIN_SEC=30
LEARNING_CLIP_MAX_SEC=60
LEARNING_CLIP_TARGET_SEC=45

# Mask token for cloze subtitles
MASK_TOKEN=____

# Intro card (guidance before first pass)
INTRO_DURATION_SEC=4
INTRO_TITLE_COLOR=#7AD7FF
INTRO_SUBTITLE_COLOR=#FFFFFF
INTRO_BLANK_COLOR=#FFD54F

# Transition card (between first and second pass)
TRANSITION_DURATION_SEC=3
TRANSITION_TITLE_COLOR=#7AD7FF
TRANSITION_SUBTITLE_COLOR=#FFFFFF

# Summary card (key expressions list)
SUMMARY_DURATION_SEC=4
SUMMARY_TITLE_COLOR=#7AD7FF
SUMMARY_EN_COLOR=#FFD54F
SUMMARY_ZH_COLOR=#FFFFFF
SUMMARY_INCLUDE_TRANSLATION=true
```

### Subtitle Styling

```bash
# Font settings
SUBTITLE_FONT_NAME=PingFang SC
SUBTITLE_FONT_SIZE=24
SUBTITLE_MARGIN_V=30
SUBTITLE_OUTLINE=2
SUBTITLE_SHADOW=1

# Bilingual subtitle colors
BILINGUAL_COLOR=true
BILINGUAL_ORDER=EN_FIRST
SUBTITLE_EN_COLOR=#FFD54F
SUBTITLE_ZH_COLOR=#FFFFFF
```

For full configuration options, see [.env.example](.env.example).

---

## Examples

### Example 1: Extract highlights from a tech interview

**Input**:
```
Clip this video: https://youtube.com/watch?v=Ckt1cj0xjRM
```

**Output** (AI-generated chapters):
```
1. [00:00 - 03:15] AGI as an exponential curve, not a point in time
2. [03:15 - 06:30] China's gap in AI development
3. [06:30 - 09:45] The impact of chip bans
...
```

**Result**: Select chapters → Get clipped videos with bilingual subtitles + social media content

### Example 2: Create short clips from a course

**Input**:
```
Clip this lecture video and create bilingual subtitles: https://youtube.com/watch?v=LECTURE_ID
```

**Options**:
- Generate bilingual subtitles: Yes
- Burn subtitles into video: Yes
- Generate summary: Yes

**Result**: High-quality clips ready for sharing on social media platforms

### Example 3: Create a dual-pass learning clip (30-60s)

**Input**:
```
~/.codex/skills/learning-video-maker/scripts/learning_clip_guided.py video.mp4 video.en.vtt 00:12:10 00:12:55 --name vocab_boost
```

**Result**: Masked English pass + full bilingual pass + summary card, concatenated into a final video

---

## Key Differentiators

### AI Semantic Chapter Analysis

Unlike mechanical time-based splitting, this skill uses Claude's AI to:
- Understand content semantics
- Identify natural topic transitions
- Generate meaningful chapter titles and summaries
- Ensure complete coverage with no gaps

**Example**:
```
❌ Mechanical splitting: [0:00-30:00], [30:00-60:00]
✅ AI semantic analysis:
   - [00:00-03:15] AGI definition
   - [03:15-07:30] China's AI landscape
   - [07:30-12:00] Chip ban impacts
```

### Batch Translation Optimization

Translates 20 subtitles at once instead of one-by-one:
- 95% reduction in API calls
- 10x faster translation
- Better translation consistency

### Bilingual Subtitle Format

Generated subtitle files contain both English and Chinese:

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

## Troubleshooting

### FFmpeg subtitle burning fails

**Error**: `Option not found: subtitles` or `filter not found`

**Solution**: Install `ffmpeg-full` (macOS) or ensure `libass-dev` is installed (Ubuntu):
```bash
# macOS
brew uninstall ffmpeg
brew install ffmpeg-full

# Ubuntu
sudo apt install ffmpeg libass-dev
```

### Video download is slow

**Solution**: Set a proxy in `.env`:
```bash
YT_DLP_PROXY=http://proxy-server:port
# or
YT_DLP_PROXY=socks5://proxy-server:port
```

### Subtitle translation fails

**Cause**: API rate limiting or network issues

**Solution**: The skill automatically retries up to 3 times. If persistent, check:
- Network connectivity
- Claude API status
- Reduce `TRANSLATION_BATCH_SIZE` in `.env`

### Special characters in filenames

**Issue**: Filenames with `:`, `/`, `?`, etc. may cause errors

**Solution**: The skill automatically sanitizes filenames by:
- Removing special characters: `/ \ : * ? " < > |`
- Replacing spaces with underscores
- Limiting length to 100 characters

---

## Documentation

- **[SKILL.md](SKILL.md)** - Complete workflow and technical details
- **[TECHNICAL_NOTES.md](TECHNICAL_NOTES.md)** - Implementation notes and design decisions
- **[FIXES_AND_IMPROVEMENTS.md](FIXES_AND_IMPROVEMENTS.md)** - Changelog and bug fixes
- **[references/](references/)** - FFmpeg, yt-dlp, and subtitle formatting guides

---

## Contributing

Contributions are welcome! Please:
- Report bugs via [GitHub Issues](https://github.com/op7418/Youtube-clipper-skill/issues)
- Submit feature requests
- Open pull requests for improvements

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Acknowledgements

- **[Claude Code](https://claude.ai/claude-code)** - The AI-powered CLI tool
- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** - YouTube download engine
- **[FFmpeg](https://ffmpeg.org/)** - Video processing powerhouse

---

<div align="center">

**Made with ❤️ by [op7418](https://github.com/op7418)**

If this skill helps you, please give it a ⭐️

</div>
