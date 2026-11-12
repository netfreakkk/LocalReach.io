import re
import numpy as np
from pathlib import Path
from typing import Optional

def extract_youtube_heatmap_hotspots(
    info_dict: dict,
    target_duration: float = 45.0,
    min_duration: float = 35.0,
    max_duration: float = 55.0
) -> list[dict]:
    """
    Parses YouTube's native 'Most Replayed' heatmap data (100 normalized intensity points)
    to discover the exact timeline moments where global audiences rewound and rewatched most.
    """
    heatmap = info_dict.get("heatmap")
    if not heatmap:
        return []

    # heatmap is a list of {"start_time": float, "end_time": float, "value": float}
    points = sorted(heatmap, key=lambda x: x["start_time"])
    if not points:
        return []

    # Rolling window scoring: find windows of 35-55s with the highest average retention
    hotspots = []
    step_size = max(1, len(points) // 60) # sample windows across timeline

    for i in range(0, len(points), step_size):
        start_t = points[i]["start_time"]
        for j in range(i + 1, len(points)):
            end_t = points[j]["end_time"]
            dur = end_t - start_t
            if min_duration <= dur <= max_duration:
                # Average intensity in this window
                window_vals = [p["value"] for p in points[i:j + 1]]
                avg_intensity = float(np.mean(window_vals))
                peak_intensity = float(np.max(window_vals))
                
                # Composite retention score (0 - 100)
                score = int(round((avg_intensity * 0.6 + peak_intensity * 0.4) * 100))

                hotspots.append({
                    "start_seconds": round(start_t, 1),
                    "end_seconds": round(end_t, 1),
                    "score": score,
                    "reason": f"YouTube Most Replayed Peak (Avg Retention: {avg_intensity:.2f}, Peak: {peak_intensity:.2f})"
                })
            elif dur > max_duration:
                break

    # Sort descending by score
    hotspots.sort(key=lambda x: x["score"], reverse=True)

    # Greedily filter non-overlapping windows with at least 45s separation
    selected = []
    for h in hotspots:
        overlaps = False
        for s in selected:
            # Enforce strict 40s separation between clips
            if not (h["end_seconds"] + 40 <= s["start_seconds"] or h["start_seconds"] >= s["end_seconds"] + 40):
                overlaps = True
                break
        if not overlaps:
            selected.append(h)
            if len(selected) >= 15:
                break

    return selected

def extract_chapter_hotspots(info_dict: dict) -> list[dict]:
    """
    Extracts high-intent chapters from YouTube metadata.
    """
    chapters = info_dict.get("chapters") or []
    results = []
    
    # Priority keywords that indicate viral/intriguing topics
    viral_chapter_keywords = [
        "secret", "truth", "future", "bet", "mistake", "how", "why", 
        "failure", "success", "money", "revolution", "danger", "rule",
        "growth", "advice", "career", "leadership", "founder", "ai", 
        "openai", "contrarian", "mindset", "extraordinary", "price"
    ]

    for idx, ch in enumerate(chapters):
        title = ch.get("title", "")
        start_t = float(ch.get("start_time", 0))
        end_t = float(ch.get("end_time", 0))
        dur = end_t - start_t
        
        # Check title affinity
        matches = [kw for kw in viral_chapter_keywords if kw in title.lower()]
        score = 80 + min(18, len(matches) * 5)

        if dur >= 35:
            # We can take the initial 45s hook of the chapter
            clip_end = min(start_t + 48.0, end_t)
            results.append({
                "start_seconds": round(start_t, 1),
                "end_seconds": round(clip_end, 1),
                "score": score,
                "reason": f"YouTube Chapter: '{title}'"
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results
