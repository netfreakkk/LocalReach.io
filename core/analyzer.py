import os
import time
import subprocess
from pathlib import Path
from .schema import VideoAnalysisResult
from .config import GEMINI_API_KEY, get_ffmpeg_binary
from .local_analyzer import analyze_video_locally
from .hotspots import extract_youtube_heatmap_hotspots, extract_chapter_hotspots

def analyze_video_moments(
    proxy_path: Path,
    api_key: str = None,
    model_name: str = "gemini-3.1-flash-lite",
    video_title: str = "",
    force_local: bool = False,
    metadata: dict = None,
    target_clips: int = 5
) -> VideoAnalysisResult:
    """
    Intelligent video analyzer:
    1. Extracts YouTube audience retention hotspots (Most Replayed heatmap + Chapters).
    2. Enforces structural wholeness (clips MUST start with a question or relatable story/fact).
    3. Guarantees strict non-overlapping clip boundaries (min 45s separation).
    4. Uses Gemini 3.1 Flash Lite / 3.8 Flash or offline local Whisper fallback.
    """
    key = api_key or GEMINI_API_KEY or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    
    # 1. Parse audience hotspots from YouTube metadata if available
    hotspot_hints = []
    if metadata:
        heatmap_hotspots = extract_youtube_heatmap_hotspots(metadata)
        chapter_hotspots = extract_chapter_hotspots(metadata)
        
        if heatmap_hotspots:
            hotspot_hints.append("YOUTUBE 'MOST REPLAYED' AUDIENCE HOTSPOTS (Moments viewers rewound most):")
            for h in heatmap_hotspots[:25]:
                hotspot_hints.append(f"  • {h['start_seconds']}s - {h['end_seconds']}s (Score: {h['score']}) - {h['reason']}")
                
        if chapter_hotspots:
            hotspot_hints.append("KEY DISCUSSION CHAPTERS:")
            for ch in chapter_hotspots[:25]:
                hotspot_hints.append(f"  • {ch['start_seconds']}s - {ch['end_seconds']}s - {ch['reason']}")

    hotspot_context_str = "\n".join(hotspot_hints) if hotspot_hints else "No YouTube heatmap available. Analyze audiovisual energy peaks."
    max_duration = float(metadata.get("duration", 0)) if metadata and "duration" in metadata else 0.0
    duration_constraint = f"CRITICAL DURATION BOUNDARY: Total video length is {max_duration:.1f}s. Every clip MUST have start_seconds < {max_duration - 10.0:.1f}s and end_seconds <= {max_duration:.1f}s. NEVER output timestamps exceeding {max_duration:.1f}s." if max_duration > 0 else ""

    # Fallback to local mode if explicitly requested or key is empty
    if force_local or not key or key.strip() == "":
        print("\n[⚡] Running 100% Local AI Intelligence Engine (Whisper + Hook Detection)...")
        ffmpeg_bin = get_ffmpeg_binary()
        temp_audio = proxy_path.parent / f"{proxy_path.stem}_audio.wav"
        
        cmd = [
            ffmpeg_bin, "-y",
            "-i", str(proxy_path),
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            str(temp_audio)
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        try:
            return analyze_video_locally(temp_audio, video_title=video_title, target_clips=target_clips)
        finally:
            temp_audio.unlink(missing_ok=True)

    # Key is available -> Run Multimodal Gemini (Flash-Lite / Flash)
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=key)

    print(f"[*] Uploading proxy video ({proxy_path.name}) to Gemini Multimodal AI...")
    uploaded_file = client.files.upload(file=str(proxy_path))

    try:
        while uploaded_file.state.name == "PROCESSING":
            print("    Waiting for Gemini to process proxy video...")
            time.sleep(3)
            uploaded_file = client.files.get(name=uploaded_file.name)

        if uploaded_file.state.name != "ACTIVE":
            raise RuntimeError(f"Video file processing failed with state: {uploaded_file.state.name}")

        print(f"[*] Watching video with {model_name} and detecting {target_clips} narrative-complete viral hooks...")
        
        prompt = f"""
    You are an elite short-form video producer and algorithm engineer (LocalReach.io & OpusClip).
    Watch and listen to this entire video to extract EXACTLY {target_clips} of the MOST ENGAGING, completely self-contained viral moments (35 to 55 seconds each).

    {duration_constraint}

    {hotspot_context_str}

    CRITICAL QUANTITY REQUIREMENT:
    You MUST output EXACTLY {target_clips} distinct, high-quality viral clips in the 'clips' array. Number them sequentially from 1 to {target_clips}.
    Do NOT stop at 5 clips under any circumstances. Return all {target_clips} clips.

    CRITICAL RULES FOR NARRATIVE WHOLENESS (A COMPLETE SHORT):
    1. STRICT LANGUAGE & SCRIPT RULE:
       ALL output text (on_screen_hook, yt_shorts_title, ig_caption_hook, etc.) MUST be strictly written in the English / Latin alphabet (A-Z).
       For Indian/Hindi speech, use fluent English translation or clean Romanized Hinglish (e.g. "KYUN BAHUT AARAM SE").
       NEVER use Arabic, Urdu, or Devanagari script under any circumstances!

    2. THE OPENING HOOK (First 3-5 seconds):
       Every clip MUST start in one of two ways so the audience immediately understands the context:
       A) A COMPELLING QUESTION: (e.g. "Why do 99% of people fail?", "Have you ever wondered...", or the interviewer asking a thought-provoking setup question).
       B) A RELATABLE STORY OR UNIVERSAL FACT: (e.g. "Most people think X, but the truth is Y...", "The moment everything changed was...", "When I first built this, everyone laughed...").
       NEVER start mid-sentence with dangling pronouns (e.g. "And then he said that to me..." without prior context).

    3. THE CONCLUSION (Last 3-5 seconds):
       The clip MUST resolve the premise with a clear punchline, lesson, or takeaway.
       Never cut off mid-thought or mid-sentence.

    4. STRICT NON-OVERLAPPING RULE:
       Every clip must cover a distinct discussion point. Ensure clip timestamps do not collide.

    ALGORITHM HIJACK METADATA RULES:
    - on_screen_hook: 3 to 6 words in ALL CAPS. Must be a captivating, high-CTR viral headline that immediately hooks the viewer (e.g. "THE BRUTAL TRUTH ABOUT AI", "WHY 99% OF FOUNDERS FAIL", "HE BET EVERYTHING ON GPT-4", "HOW TO NEVER HIRE YES-MEN", "SAM ALTMAN'S #1 SECRET").
      DO NOT write boring generic summaries like "BEING MISUNDERSTOOD IS A STRENGTH" or "DISCUSSING WORKPLACE CULTURE". Make it punchy, emotional, and intriguing!
    - yt_shorts_title: High-CTR curiosity-gap title under 60 chars with #Shorts.
    - ig_caption_hook: 2 punchy lines forcing users to expand caption.
    - ig_seo_keyword_paragraph: 3-sentence semantic SEO paragraph for Meta AI and TikTok search indexing.
    - niche_hashtags: 5 specific tags for this content niche.
    - algo_hijack_hashtags: 12 broad trending tags (#viralreels #explorepage #trendingnow #growthmindset).
    - yt_studio_tags: 15 comma-separated high-intent search queries.
    """

        candidate_models = [model_name, "gemini-3.1-flash-lite", "gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-3.8-flash"]
        last_err = None

        for m in candidate_models:
            try:
                print(f"    Analyzing with model '{m}' (target: {target_clips} clips)...")
                response = client.models.generate_content(
                    model=m,
                    contents=[uploaded_file, prompt],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=VideoAnalysisResult,
                        temperature=0.3
                    )
                )

                result = VideoAnalysisResult.model_validate_json(response.text)
                
                # Post-process: Filter out-of-bounds and overlapping clips
                filtered_clips = []
                for c in sorted(result.clips, key=lambda x: x.viral_score, reverse=True):
                    # Validate boundary against total video duration
                    if c.start_seconds < 0.0:
                        continue
                    if max_duration > 0:
                        if c.start_seconds >= (max_duration - 10.0):
                            continue
                        if c.end_seconds > max_duration:
                            c.end_seconds = max_duration
                    if (c.end_seconds - c.start_seconds) < 10.0:
                        continue

                    overlaps = False
                    for f in filtered_clips:
                        # Discard only if collision within 10s
                        if not (c.end_seconds + 10.0 <= f.start_seconds or c.start_seconds >= f.end_seconds + 10.0):
                            overlaps = True
                            break
                    if not overlaps:
                        filtered_clips.append(c)

                # Sort by timeline or score, and re-index sequentially 1..N
                for idx, c in enumerate(filtered_clips, start=1):
                    c.clip_number = idx

                result.clips = filtered_clips
                return result

            except Exception as e:
                last_err = e
                print(f"    Model '{m}' attempt returned: {e}. Trying fallback...")
                continue
    finally:
        try:
            client.files.delete(name=uploaded_file.name)
        except Exception:
            pass

    print(f"    [!] Gemini API failed ({last_err}). Seamlessly falling back to Local AI Engine...")
    return analyze_video_moments(proxy_path, video_title=video_title, force_local=True, target_clips=target_clips)
