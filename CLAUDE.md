# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A Claude Code skill for AI-powered YouTube video clipping. It downloads videos, uses Claude to semantically analyze subtitles into chapters, lets users select segments to clip, translates subtitles to bilingual format, burns subtitles into video, and generates social media summaries. There's also a "Learning Clip" mode that creates a 5-segment structure for language learning.

The skill is installed to `~/.claude/skills/youtube-clipper/` and invoked via SKILL.md.

## System Dependencies

```bash
pip install -r requirements.txt          # Python packages: yt-dlp, pysrt, python-dotenv, chardet
brew install yt-dlp                       # YouTube downloader
brew install ffmpeg-full                  # FFmpeg with libass (required for subtitle burning)
```

**Critical**: macOS standard `brew install ffmpeg` does NOT include libass. Must use `ffmpeg-full`.
- Apple Silicon path: `/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg`
- Intel path: `/usr/local/opt/ffmpeg-full/bin/ffmpeg`

Verify libass: `ffmpeg -filters 2>&1 | grep subtitles`

## Running Scripts Directly

All scripts live in `scripts/` and must be run from that directory (they use relative imports):

```bash
cd ~/.claude/skills/youtube-clipper

# Download video and subtitles
python3 scripts/download_video.py <youtube_url>

# Clip a video segment
python3 scripts/clip_video.py <video> <start_time> <end_time> <output>
# Example: python3 scripts/clip_video.py input.mp4 00:01:30 00:04:45 output.mp4

# Burn subtitles
python3 scripts/burn_subtitles.py <video> <subtitle.srt> <output.mp4>

# Translate subtitles (batch, outputs bilingual SRT)
python3 scripts/translate_subtitles.py <subtitle_path>

# Full learning clip pipeline
python3 scripts/learning_clip.py <video.mp4> <subtitle.vtt|srt> <start> <end> --output <dir> --name <base_name>

# Prepare learning clip candidates from subtitles
python3 scripts/prepare_learning_candidates.py <subtitle.vtt> --output ./youtube-clips --name <base>

# Run utils tests
python3 scripts/utils.py
```

## Architecture

The skill executes a 6-phase pipeline orchestrated by Claude following SKILL.md:

1. **Environment check** → verify yt-dlp, ffmpeg+libass, Python deps
2. **Download** (`scripts/download_video.py`) → `<video_id>.mp4` + `<video_id>.en.vtt`
3. **AI chapter analysis** (`scripts/analyze_subtitles.py`) → Claude reads subtitles and generates semantic chapters (2–5 min each)
4. **User selection** → AskUserQuestion to pick chapters and options
5. **Processing pipeline** per chapter:
   - `clip_video.py` — FFmpeg clip (default: re-encode with libx264/crf18; set `CLIP_MODE=fast-copy` for stream copy)
   - `extract_subtitle_clip.py` — VTT→SRT extraction with timestamp adjustment
   - `translate_subtitles.py` — batched translation (20 subtitles/batch, ~95% API call reduction)
   - `merge_bilingual_subtitles.py` — combine EN+ZH into bilingual SRT
   - `burn_subtitles.py` — hardcode subtitles via FFmpeg subtitles filter; uses temp dir to avoid space-in-path bugs; can auto-convert SRT→ASS for per-language coloring when `BILINGUAL_COLOR=true`
   - `generate_summary.py` — social media content
6. **Output** → `./youtube-clips/<timestamp>/<chapter_title>/`

### Learning Clip Mode (5-segment structure)

`learning_clip.py` orchestrates these sub-scripts:
- `extract_key_phrases.py` — Claude extracts key expressions → JSON
- `mask_subtitles.py` — replace key expressions with `MASK_TOKEN` (default `____`)
- `generate_underlined_subtitle.py` — ASS format with `{\u1}word{\u0}` underline tags
- `render_intro_card.py`, `render_transition_card.py`, `render_summary_card.py` — generate static video cards via FFmpeg `lavfi`/`drawtext`
- Final FFmpeg concat: intro → masked video → transition → full+underlined video → summary card

### Shared Utilities (`scripts/utils.py`)

- `time_to_seconds` / `seconds_to_time` — supports HH:MM:SS.mmm, MM:SS.mmm, SS.mmm
- `sanitize_filename` — strips `<>:"/\|?*`, replaces spaces with `_`, max 100 chars
- `create_output_dir` — timestamped `youtube-clips/<YYYYMMDD_HHMMSS>/`
- `parse_time_range` — parses `"MM:SS - MM:SS"` format
- `validate_url` — YouTube URL pattern matching

## Configuration

Copy `.env.example` to `.env` in the skill directory. Key variables:

| Variable | Default | Notes |
|---|---|---|
| `FFMPEG_PATH` | auto-detect | Override if ffmpeg-full not on PATH |
| `CLIP_MODE` | `accurate` | Set to `fast-copy` for stream copy (faster, less precise) |
| `BILINGUAL_COLOR` | `false` | `true` = auto-generate ASS with separate EN/ZH colors |
| `BILINGUAL_ORDER` | `EN_FIRST` | `ZH_FIRST` puts Chinese on top |
| `SUBTITLE_EN_COLOR` / `SUBTITLE_ZH_COLOR` | `#FFD54F` / `#FFFFFF` | Hex colors for bilingual ASS |
| `TRANSLATION_BATCH_SIZE` | `20` | Subtitles per translation API call |
| `TARGET_LANGUAGE` | `中文` | Translation target |
| `YT_DLP_PROXY` | empty | `http://...` or `socks5://...` for slow downloads |
| `MASK_TOKEN` | `____` | Placeholder for masked subtitles in learning mode |

## Key Technical Constraints

- **Path spaces**: FFmpeg `subtitles` filter cannot handle paths with spaces. `burn_subtitles.py` copies files to a temp dir, runs FFmpeg there, then moves output back.
- **libass requirement**: subtitle burning requires `ffmpeg-full` on macOS; standard `ffmpeg` lacks this filter.
- **VTT quirks**: YouTube VTT files contain word-level timing tags and duplicate incremental cues. `extract_subtitle_clip.py` strips these tags and deduplicates.
- **Video naming**: videos are downloaded as `<video_id>.mp4` (not title) to avoid special characters in filenames.
