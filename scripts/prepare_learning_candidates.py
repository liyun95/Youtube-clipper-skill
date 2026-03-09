#!/usr/bin/env python3
"""
Prepare analysis and ranked candidate windows for learning clips.

This script writes all artifacts into the target run directory to avoid
scattering files in the project root.
"""

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

from analyze_subtitles import parse_vtt, prepare_analysis_data, save_analysis_data


STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "but", "by",
    "can", "could", "did", "do", "does", "doing", "for", "from", "had",
    "has", "have", "having", "he", "her", "here", "him", "his", "i", "if",
    "in", "into", "is", "it", "its", "may", "me", "might", "must", "my",
    "of", "on", "or", "our", "out", "over", "she", "so", "than", "that",
    "the", "their", "them", "then", "there", "these", "they", "this", "those",
    "to", "under", "up", "us", "was", "we", "were", "will", "with", "within",
    "without", "would", "you", "your",
}


def derive_video_id(subtitle_path: Path) -> str:
    stem = subtitle_path.stem
    if stem.endswith(".en"):
        stem = stem[:-3]
    return stem


def seconds_to_label(seconds: float) -> str:
    total = max(0, int(seconds))
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def sentence_boundary(text: str) -> bool:
    return bool(re.search(r"[.!?][\"']?\s*$", text.strip()))


def tokenize_words(text: str) -> List[str]:
    return [word.lower() for word in re.findall(r"[A-Za-z']+", text)]


def iou(range_a: Tuple[float, float], range_b: Tuple[float, float]) -> float:
    start_a, end_a = range_a
    start_b, end_b = range_b
    overlap = max(0.0, min(end_a, end_b) - max(start_a, start_b))
    union = max(end_a, end_b) - min(start_a, start_b)
    if union <= 0:
        return 0.0
    return overlap / union


def build_window_candidates(
    subtitles: List[Dict],
    total_duration: float,
    window_sec: float,
    max_gap_sec: float,
    min_lines: int,
    max_lines: int,
) -> List[Dict]:
    candidates = []
    for index, subtitle in enumerate(subtitles):
        start = float(subtitle["start"])
        end = start + window_sec
        if end > total_duration:
            continue

        segment = [
            item for item in subtitles
            if float(item["end"]) > start and float(item["start"]) < end
        ]
        line_count = len(segment)
        if line_count < min_lines or line_count > max_lines:
            continue

        gaps = []
        for i in range(len(segment) - 1):
            raw_gap = float(segment[i + 1]["start"]) - float(segment[i]["end"])
            gaps.append(max(0.0, raw_gap))

        max_gap = max(gaps) if gaps else 0.0
        if max_gap > max_gap_sec:
            continue

        text = " ".join(item["text"].strip() for item in segment)
        tokens = tokenize_words(text)
        content_tokens = [token for token in tokens if token not in STOPWORDS]
        unique_tokens = set(content_tokens)

        lexical_diversity = len(unique_tokens) / max(1, len(content_tokens))
        rich_token_count = sum(1 for token in unique_tokens if len(token) >= 6)
        phrase_richness = min(
            1.0,
            (rich_token_count / 16.0) * 0.7 + lexical_diversity * 0.3,
        )

        start_boundary = True
        if index > 0:
            start_boundary = sentence_boundary(subtitles[index - 1]["text"])
        end_boundary = sentence_boundary(segment[-1]["text"])
        boundary_score = (0.5 if start_boundary else 0.0) + (0.5 if end_boundary else 0.0)

        sentence_like_count = sum(1 for item in segment if sentence_boundary(item["text"]))
        sentence_density = min(1.0, sentence_like_count / max(1, line_count * 0.55))
        clarity_score = 0.6 * boundary_score + 0.4 * sentence_density

        avg_gap = (sum(gaps) / len(gaps)) if gaps else 0.0
        continuity = max(
            0.0,
            1.0 - (max_gap / max_gap_sec) * 0.7 - (avg_gap / max_gap_sec) * 0.3,
        )
        coherence_score = min(1.0, 0.7 * continuity + 0.3 * boundary_score)

        overall = 0.35 * phrase_richness + 0.35 * clarity_score + 0.30 * coherence_score

        preview = " ".join(item["text"].strip() for item in segment[:3])
        candidates.append(
            {
                "start": round(start, 3),
                "end": round(end, 3),
                "duration": round(window_sec, 3),
                "line_count": line_count,
                "max_gap": round(max_gap, 3),
                "scores": {
                    "phrase_richness": round(phrase_richness, 4),
                    "clarity": round(clarity_score, 4),
                    "coherence": round(coherence_score, 4),
                    "overall": round(overall, 4),
                },
                "start_time": seconds_to_label(start),
                "end_time": seconds_to_label(end),
                "preview": preview[:240],
            }
        )

    return candidates


def select_top_candidates(candidates: List[Dict], top_k: int, overlap_limit: float) -> List[Dict]:
    ordered = sorted(candidates, key=lambda item: item["scores"]["overall"], reverse=True)
    selected = []
    for candidate in ordered:
        overlaps = any(
            iou((candidate["start"], candidate["end"]), (picked["start"], picked["end"])) >= overlap_limit
            for picked in selected
        )
        if overlaps:
            continue
        selected.append(candidate)
        if len(selected) >= top_k:
            break

    for rank, candidate in enumerate(selected, start=1):
        candidate["rank"] = rank
        candidate["auto_selected"] = rank == 1

    return selected


def make_candidate_reason(candidate: Dict) -> str:
    reasons = []
    if candidate["scores"]["phrase_richness"] >= 0.60:
        reasons.append("high phrase richness")
    if candidate["scores"]["clarity"] >= 0.65:
        reasons.append("strong sentence boundaries")
    if candidate["scores"]["coherence"] >= 0.70:
        reasons.append("stable speech continuity")
    if not reasons:
        reasons.append("balanced overall learning quality")
    return ", ".join(reasons)


def main():
    parser = argparse.ArgumentParser(
        description="Generate analysis/candidate artifacts under a run output directory.",
    )
    parser.add_argument("subtitle_vtt", help="Path to source VTT subtitle file")
    parser.add_argument(
        "--output",
        required=True,
        help="Base output directory (for example: ./youtube-clips)",
    )
    parser.add_argument(
        "--name",
        required=True,
        help="Run directory name under output (for example: eIho2S0ZahI_learning)",
    )
    parser.add_argument("--window", type=float, default=45.0, help="Candidate window length in seconds")
    parser.add_argument("--top-k", type=int, default=5, help="Number of candidates to keep")
    parser.add_argument("--max-gap", type=float, default=3.5, help="Max allowed silence gap in seconds")
    parser.add_argument("--min-lines", type=int, default=8, help="Min subtitle line count in a window")
    parser.add_argument("--max-lines", type=int, default=18, help="Max subtitle line count in a window")
    parser.add_argument(
        "--target-duration",
        type=int,
        default=180,
        help="Target chapter duration for analysis metadata",
    )
    args = parser.parse_args()

    subtitle_path = Path(args.subtitle_vtt).resolve()
    if not subtitle_path.exists():
        raise FileNotFoundError(f"Subtitle file not found: {subtitle_path}")

    run_dir = Path(args.output).expanduser().resolve() / args.name
    run_dir.mkdir(parents=True, exist_ok=True)

    video_id = derive_video_id(subtitle_path)
    analysis_path = run_dir / f"{video_id}_analysis.json"
    candidates_path = run_dir / f"{video_id}_candidates.json"
    report_path = run_dir / f"{video_id}_candidate_report.md"

    subtitles = parse_vtt(str(subtitle_path))
    analysis = prepare_analysis_data(subtitles, args.target_duration)
    save_analysis_data(analysis, str(analysis_path))

    all_candidates = build_window_candidates(
        subtitles=analysis["subtitles_raw"],
        total_duration=float(analysis["total_duration"]),
        window_sec=float(args.window),
        max_gap_sec=float(args.max_gap),
        min_lines=int(args.min_lines),
        max_lines=int(args.max_lines),
    )
    selected = select_top_candidates(all_candidates, args.top_k, overlap_limit=0.55)

    for candidate in selected:
        candidate["selection_reason"] = make_candidate_reason(candidate)

    payload = {
        "video_id": video_id,
        "window_seconds": float(args.window),
        "constraints": {
            "max_silence_gap_seconds": float(args.max_gap),
            "line_count_range": [int(args.min_lines), int(args.max_lines)],
        },
        "total_candidates_scored": len(all_candidates),
        "selected_count": len(selected),
        "auto_selected_rank": 1 if selected else None,
        "auto_selected_start": selected[0]["start_time"] if selected else None,
        "auto_selected_end": selected[0]["end_time"] if selected else None,
        "candidates": selected,
    }
    candidates_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        f"# {video_id} Candidate Report",
        "",
        f"- Window: {args.window:.1f}s",
        f"- Constraints: max gap <= {args.max_gap:.1f}s, line count {args.min_lines}-{args.max_lines}",
        f"- Scored windows: {len(all_candidates)}",
        (
            f"- Auto-selected: Rank #1 "
            f"({payload['auto_selected_start']} - {payload['auto_selected_end']})"
            if selected
            else "- Auto-selected: none"
        ),
        "",
        "## Ranked Candidates",
        "",
    ]
    for candidate in selected:
        lines.extend(
            [
                f"### {candidate['rank']}. {candidate['start_time']} - {candidate['end_time']} "
                f"(score {candidate['scores']['overall']})",
                f"- Lines: {candidate['line_count']}",
                f"- Max silence gap: {candidate['max_gap']}s",
                f"- Reason: {candidate['selection_reason']}",
                f"- Preview: {candidate['preview']}",
                "",
            ]
        )
    report_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"Analysis: {analysis_path}")
    print(f"Candidates: {candidates_path}")
    print(f"Report: {report_path}")
    if selected:
        print(f"AUTO_SELECTED_START={selected[0]['start_time']}")
        print(f"AUTO_SELECTED_END={selected[0]['end_time']}")


if __name__ == "__main__":
    main()
