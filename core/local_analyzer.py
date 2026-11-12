import re
import math
from pathlib import Path
from collections import Counter
from faster_whisper import WhisperModel
from .schema import ViralClipSpec, VideoAnalysisResult

# High-velocity viral trigger phrases used by top creators (Hormozi, MrBeast, Huberman, etc.)
HOOK_TRIGGERS = [
    r"\b(stop|never|don't|mistake|worst|danger|warning|avoid)\b",
    r"\b(secret|nobody tells you|the truth|the real reason|the lie|exposed)\b",
    r"\b(why|how to|what happens|did you know|have you ever|what if)\b",
    r"\b(insane|crazy|game changer|unbelievable|huge|biggest|shocking)\b",
    r"\b(rule number|step one|here is how|formula|three things|number one)\b",
    r"\b(if you want|if you're trying|most people|everyone thinks)\b"
]

ALGO_FEEDER_TAGS = [
    "#explorepage", "#viralreels", "#trendingnow", "#reelsindia", 
    "#foryoupage", "#fyp", "#growthmindset", "#learnontiktok", 
    "#viralpost", "#dailycontent", "#contentcreator", "#reelsvideo"
]

def extract_transcript_and_segments(audio_path: Path, model_size: str = "base") -> tuple[list[dict], str]:
    """
    Transcribes audio using faster-whisper with millisecond timestamps completely offline.
    Uses CPU with int8 quantization to prevent any cuBLAS CUDA DLL dependency errors.
    """
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    segments, _ = model.transcribe(str(audio_path), task="translate", word_timestamps=True, vad_filter=True, beam_size=1)
    
    clean_segments = []
    full_text_parts = []
    for s in segments:
        text = s.text.strip()
        if text:
            clean_segments.append({
                "start": s.start,
                "end": s.end,
                "text": text,
                "words": len(text.split())
            })
            full_text_parts.append(text)

    return clean_segments, " ".join(full_text_parts)

def score_segment_window(segments: list[dict], start_idx: int, end_idx: int) -> tuple[float, str]:
    """
    Evaluates a candidate 35-55 second window for viral potential based on speech cadence,
    verbal hooks, emotional polarity, and question density.
    """
    first_seg = segments[start_idx]
    window_segs = segments[start_idx:end_idx + 1]
    
    total_words = sum(s["words"] for s in window_segs)
    duration = window_segs[-1]["end"] - first_seg["start"]
    if duration <= 0:
        return 0.0, "Invalid duration"

    speech_rate = total_words / duration # Target: 2.2 to 3.8 words/sec

    # 1. Opening verbal hook score (Max 40 pts)
    hook_score = 0
    first_text = first_seg["text"].lower()
    matched_hooks = []
    for pattern in HOOK_TRIGGERS:
        m = re.findall(pattern, first_text)
        if m:
            hook_score += 15
            matched_hooks.extend(m)
    if "?" in first_text:
        hook_score += 15
        matched_hooks.append("question")

    hook_score = min(40, hook_score)

    # 2. Speech cadence & pace (Max 30 pts)
    # Penalize speech that is too slow (<1.8 wps) or too frantic (>4.5 wps)
    if 2.2 <= speech_rate <= 3.8:
        cadence_score = 30
    elif 1.8 <= speech_rate <= 4.2:
        cadence_score = 20
    else:
        cadence_score = 10

    # 3. Content density & energy (Max 30 pts)
    all_text = " ".join(s["text"] for s in window_segs)
    questions_count = all_text.count("?")
    exclamation_count = all_text.count("!")
    density_score = min(30, (questions_count * 8) + (exclamation_count * 6) + (len(all_text.split()) // 8))

    total_score = hook_score + cadence_score + density_score
    # Normalize to 65 - 98 range
    final_score = int(65 + (total_score / 100.0) * 33)
    final_score = max(65, min(98, final_score))

    reason = f"Starts with verbal hook ({', '.join(matched_hooks) or 'high vocal inflection'}), pace {speech_rate:.1f} w/s"
    return final_score, reason

def extract_keywords_from_text(text: str, top_k: int = 15) -> list[str]:
    """Extracts high-frequency content keywords excluding common stopwords."""
    stopwords = {
        "the", "and", "that", "this", "with", "from", "your", "have", "more", 
        "will", "about", "what", "when", "there", "they", "just", "like", "know", 
        "think", "really", "because", "their", "people", "would", "could", "these"
    }
    words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
    filtered = [w for w in words if w not in stopwords]
    counts = Counter(filtered)
    return [w for w, _ in counts.most_common(top_k)]

def analyze_video_locally(
    audio_path: Path,
    video_title: str = "",
    min_duration: float = 35.0,
    max_duration: float = 55.0,
    target_clips: int = 5
) -> VideoAnalysisResult:
    """
    100% LOCAL & FREE Viral Moment Detector.
    Runs faster-whisper to transcribe audio and applies algorithmic hook detection
    to find the top 5 high-retention 35-55s segments without needing ANY API key.
    """
    print(f"[*] Running 100% Local AI Analysis (Zero API key required)...")
    segments, full_text = extract_transcript_and_segments(audio_path)
    
    if not segments:
        raise ValueError("Could not extract any speech segments from video.")

    print(f"    Transcribed {len(segments)} spoken segments across the video.")

    # Search for all candidate 35-55s windows
    candidates = []
    n = len(segments)
    for i in range(n):
        for j in range(i, n):
            dur = segments[j]["end"] - segments[i]["start"]
            if min_duration <= dur <= max_duration:
                score, reason = score_segment_window(segments, i, j)
                candidates.append({
                    "start_idx": i,
                    "end_idx": j,
                    "start_seconds": round(segments[i]["start"], 2),
                    "end_seconds": round(segments[j]["end"], 2),
                    "viral_score": score,
                    "reason": reason,
                    "text": " ".join(segments[k]["text"] for k in range(i, j + 1))
                })
            elif dur > max_duration:
                break

    if not candidates:
        # Fallback to fixed chunks if video is short
        first_end = min(segments[-1]["end"], 45.0)
        candidates.append({
            "start_idx": 0,
            "end_idx": n - 1,
            "start_seconds": 0.0,
            "end_seconds": first_end,
            "viral_score": 85,
            "reason": "Primary content window",
            "text": " ".join(s["text"] for s in segments)
        })

    # Sort candidates by viral score descending
    candidates.sort(key=lambda x: x["viral_score"], reverse=True)

    # Greedily select non-overlapping top clips
    chosen = []
    for cand in candidates:
        # Check overlap with strict 45-second separation
        overlaps = False
        for c in chosen:
            if not (cand["end_seconds"] + 45.0 <= c["start_seconds"] or cand["start_seconds"] >= c["end_seconds"] + 45.0):
                overlaps = True
                break
        if not overlaps:
            chosen.append(cand)
            if len(chosen) >= target_clips:
                break

    # If fewer than target_clips, fill with remaining non-colliding candidates (relaxed 10s gap)
    if len(chosen) < target_clips and candidates:
        for cand in candidates:
            if cand in chosen:
                continue
            overlaps = False
            for c in chosen:
                if not (cand["end_seconds"] + 10.0 <= c["start_seconds"] or cand["start_seconds"] >= c["end_seconds"] + 10.0):
                    overlaps = True
                    break
            if not overlaps:
                chosen.append(cand)
                if len(chosen) >= target_clips:
                    break

    # Format into Pydantic models
    video_keywords = extract_keywords_from_text(full_text, top_k=20)
    top_theme = (video_keywords[0] if video_keywords else "Insights").capitalize()

    viral_clips = []
    for idx, c in enumerate(chosen):
        clip_keywords = extract_keywords_from_text(c["text"], top_k=10)
        first_sentence = c["text"].split(".")[0].strip()
        kw1 = clip_keywords[0].upper() if clip_keywords else top_theme.upper()
        kw2 = clip_keywords[1].upper() if len(clip_keywords) > 1 else "SUCCESS"
        
        # High-CTR hook headline synthesis
        if "?" in first_sentence:
            q_part = first_sentence.split("?")[0].strip()
            banner_hook = " ".join(q_part.split()[:5]).upper() + "?"
        else:
            hook_templates = [
                f"THE BRUTAL TRUTH ABOUT {kw1}",
                f"WHY 99% FAIL AT {kw1}",
                f"THE SECRET TO {kw1}",
                f"HOW TO MASTER {kw1} FAST",
                f"THE BIGGEST {kw1} MISTAKE"
            ]
            banner_hook = hook_templates[idx % len(hook_templates)]

        title = f"{first_sentence[:50]}... #Shorts"
        ig_hook = f"{first_sentence}.\nWatch until the end for the key takeaway."
        seo_paragraph = (
            f"Discover essential insights about {', '.join(clip_keywords[:3])}. "
            f"Learn how to master {top_theme.lower()} with proven techniques that actually work. "
            f"Save and implement these actionable tips for better results."
        )

        niche_tags = [f"#{kw}" for kw in clip_keywords[:5]]
        yt_tags = clip_keywords[:8] + [video_title[:30], f"{top_theme} tips", "shorts algorithm"]

        viral_clips.append(ViralClipSpec(
            clip_number=idx + 1,
            start_seconds=c["start_seconds"],
            end_seconds=c["end_seconds"],
            on_screen_hook=banner_hook[:40],
            viral_score=c["viral_score"],
            hook_rationale=c["reason"],
            yt_shorts_title=title,
            ig_caption_hook=ig_hook,
            ig_seo_keyword_paragraph=seo_paragraph,
            niche_hashtags=niche_tags,
            algo_hijack_hashtags=ALGO_FEEDER_TAGS,
            yt_studio_tags=[t for t in yt_tags if t]
        ))

    return VideoAnalysisResult(
        video_summary=f"Analysis of '{video_title or 'Input Video'}' covering key themes in {top_theme}.",
        dominant_theme=top_theme,
        clips=viral_clips
    )
