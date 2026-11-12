import re
from pathlib import Path
from faster_whisper import WhisperModel

def clean_to_latin(text: str) -> str:
    """
    Strictly enforces English and Romanized Hinglish (Latin alphabet only).
    Transliterates Devanagari to Romanized Hinglish, and removes any Arabic/Urdu/Persian characters.
    """
    if not text:
        return ""
    
    # If Devanagari characters are present, transliterate to Latin Hinglish
    if re.search(r'[\u0900-\u097F]', text):
        try:
            from indic_transliteration import sanscript
            text = sanscript.transliterate(text, sanscript.DEVANAGARI, sanscript.ITRANS)
        except Exception:
            pass
            
    # Remove any Arabic/Urdu/Persian characters
    text = re.sub(r'[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]', '', text).strip()
    return text

def format_ass_time(seconds: float) -> str:
    """Converts seconds float to standard ASS timestamp format H:MM:SS.cc"""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int(round((seconds - int(seconds)) * 100))
    if centis >= 100:
        centis = 99
    return f"{hrs}:{mins:02d}:{secs:02d}.{centis:02d}"

def extract_word_timestamps(audio_path: Path, model_size: str = "base", task: str = "translate") -> list[dict]:
    """
    Transcribes audio using faster-whisper with millisecond word timestamps and punctuation.
    Uses task="translate" so that any non-English speech (Hindi, Hinglish, etc.) is strictly
    translated into fluent English in the Latin alphabet, eliminating any Arabic/Urdu script.
    """
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(
        str(audio_path),
        task=task,
        word_timestamps=True,
        vad_filter=True,
        beam_size=1
    )
    
    words = []
    for seg in segments:
        if seg.words:
            for w in seg.words:
                raw_w = w.word.strip()
                cleaned = clean_to_latin(raw_w).upper()
                if cleaned:
                    words.append({
                        "word": cleaned,
                        "raw": clean_to_latin(raw_w),
                        "start": max(0.0, float(w.start)),
                        "end": max(float(w.start) + 0.1, float(w.end))
                    })
    return words

def snap_speech_boundaries(words: list[dict], max_duration: float) -> tuple[float, float]:
    """
    Ensures complete narrative wholeness and eliminates awkward trailing silence or cuts:
    1. Trims dangling fragments of earlier sentences (e.g. bleeding from prior topic).
    2. Starts cleanly on the opening hook / sentence.
    3. Snaps clip ending to the final completed statement / punchline.
    4. Trims out trailing interviewer questions with no answer and dead silence.
    """
    if not words:
        return 0.0, max_duration

    # 1. Start boundary: skip any dangling tail fragment of a previous sentence
    start_offset = 0.0
    for i in range(min(5, len(words) - 1)):
        w = words[i]
        raw = w.get("raw", w.get("word", ""))
        # If a sentence ended very early (in first 3.5s)
        if raw.endswith((".", "!", "?")) and w["end"] <= 3.5:
            next_w = words[i + 1]
            pause = next_w["start"] - w["end"]
            # If there is a noticeable pause or only 1-3 words before the period
            if pause >= 0.3 or i <= 2:
                start_offset = max(0.0, next_w["start"] - 0.1)
                break

    # If no dangling fragment was skipped, start at the very first word
    if start_offset == 0.0:
        start_offset = max(0.0, words[0]["start"] - 0.1)

    # 2. End boundary: find natural conclusion and cut trailing dead air
    last_word_end = words[-1]["end"]
    effective_end = min(max_duration, last_word_end + 0.25)

    # Check for unanswered questions or dangling incomplete sentences at the end
    last_punct_idx = -1
    for i in range(len(words) - 1, -1, -1):
        raw = words[i].get("raw", words[i].get("word", ""))
        if raw.endswith(("?", ".", "!")):
            last_punct_idx = i
            break

    if last_punct_idx >= 0:
        last_w = words[last_punct_idx]
        raw_last = last_w.get("raw", last_w.get("word", ""))
        
        # A) Unanswered question cutoff: if clip ends with a question in the final 8 seconds
        if raw_last.endswith("?"):
            prev_term_idx = -1
            for k in range(last_punct_idx - 1, -1, -1):
                prev_raw = words[k].get("raw", words[k].get("word", ""))
                if prev_raw.endswith((".", "!", "?")):
                    prev_term_idx = k
                    break
            if prev_term_idx >= 0:
                prev_end = words[prev_term_idx]["end"] + 0.25
                if prev_end - start_offset >= 18.0:
                    effective_end = prev_end
        
        # B) Mid-sentence cutoff: if words after last_punct_idx exist and have no terminator
        elif last_punct_idx < len(words) - 1:
            words_after = len(words) - 1 - last_punct_idx
            if words_after >= 3:
                prev_end = last_w["end"] + 0.25
                if prev_end - start_offset >= 18.0:
                    effective_end = prev_end

    # Ensure minimum reasonable duration (at least 15s)
    if effective_end - start_offset < 15.0:
        effective_end = max(start_offset + 15.0, min(max_duration, words[-1]["end"] + 0.25))

    return round(start_offset, 2), round(effective_end, 2)

def generate_ass_script(
    words: list[dict],
    ass_path: Path,
    hook_banner: str = "",
    highlight_color: str = "&H0000FFFF&", # Bright Yellow in BGR hex
    font_name: str = "Impact",
    chunk_size: int = 3
) -> Path:
    """
    Builds a professional Hormozi/ScaleReach style .ass subtitle script
    with a sleek modern Top Hook Pill and word-by-word karaoke pop effects.
    """
    # Modern Top Hook Pill: Sleek translucent dark glass pill with accent badge & crisp typography
    ass_header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: PopCaption,Arial Black,76,&H00FFFFFF,{highlight_color},&H00000000,&H80000000,-1,0,0,0,100,100,2,0,1,8,4,2,60,60,420,1
Style: TopHookPill,{font_name},50,&H00FFFFFF,&H0000FFFF,&H00000000,&HC0111115,-1,0,0,0,100,100,2,0,3,16,0,8,60,60,195,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [ass_header]

    # Persistent Top Hook Pill for the duration of the clip
    if hook_banner:
        clean_hook = hook_banner.replace("{", "").replace("}", "").upper().strip()
        # Display the sleek top banner with vibrant bullet accent
        lines.append(f"Dialogue: 0,0:00:00.00,0:01:10.00,TopHookPill,,0,0,0,,  {{\\c{highlight_color}}}● {{\\c&H00FFFFFF&}}{clean_hook}  ")

    # Generate 3-word chunked karaoke subtitles
    for i in range(0, len(words), chunk_size):
        chunk = words[i:i + chunk_size]
        if not chunk:
            continue

        for active_idx, active_word in enumerate(chunk):
            start_t = format_ass_time(active_word["start"])
            end_t = format_ass_time(active_word["end"])
            
            formatted_words = []
            for idx, w in enumerate(chunk):
                raw_w = w["word"].replace("{", "").replace("}", "")
                if idx == active_idx:
                    # Highlight active word with scale pop
                    formatted_words.append(f"{{\\c{highlight_color}\\fscx114\\fscy114}}{raw_w}{{\\c&H00FFFFFF&\\fscx100\\fscy100}}")
                else:
                    formatted_words.append(raw_w)
            
            line_text = " ".join(formatted_words)
            lines.append(f"Dialogue: 1,{start_t},{end_t},PopCaption,,0,0,0,,{line_text}")

    ass_path.write_text("\n".join(lines), encoding="utf-8")
    return ass_path
