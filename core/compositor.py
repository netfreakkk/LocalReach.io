import subprocess
from pathlib import Path
from typing import Callable, Optional
from .schema import ViralClipSpec
from .config import get_ffmpeg_binary, HAS_NVENC
from .subtitles import extract_word_timestamps, generate_ass_script, snap_speech_boundaries
from .smart_crop import analyze_faces_in_video, build_reframing_filter

def render_vertical_clip(
    master_video_path: Path,
    clip: ViralClipSpec,
    output_dir: Path,
    reframing_style: str = "smart", # "smart", "split", "blur", "center"
    highlight_color: str = "&H0000FFFF&", # Yellow
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> Path:
    """
    Slices raw master video, extracts word timestamps for karaoke subtitles,
    performs smart speech boundary snapping (zero trailing awkward silence),
    applies face tracking reframing, and renders final 1080x1920 9:16 MP4 using NVENC.
    """
    ffmpeg_bin = get_ffmpeg_binary()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    clip_base_name = f"clip_{clip.clip_number}_score{clip.viral_score}"
    temp_slice = output_dir / f"{clip_base_name}_temp.mp4"
    temp_audio = output_dir / f"{clip_base_name}_audio.wav"
    ass_path = output_dir / f"{clip_base_name}.ass"
    final_mp4 = output_dir / f"{clip_base_name}.mp4"

    raw_duration = max(1.0, clip.end_seconds - clip.start_seconds)

    if progress_callback:
        progress_callback(20.0, f"Extracting candidate audio segment #{clip.clip_number}...")

    # Extract clean audio segment first to inspect speech boundaries
    raw_audio_cmd = [
        ffmpeg_bin, "-y",
        "-ss", str(clip.start_seconds),
        "-t", str(raw_duration),
        "-i", str(master_video_path),
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        str(temp_audio)
    ]
    subprocess.run(raw_audio_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    if progress_callback:
        progress_callback(40.0, f"Aligning speech boundaries (eliminating dead silence)...")

    # Word-level alignment and natural speech boundary snapping
    words = extract_word_timestamps(temp_audio)
    start_offset, effective_duration = snap_speech_boundaries(words, raw_duration)

    # Actual cut timestamps aligned with speech
    actual_start = clip.start_seconds + start_offset
    actual_duration = max(5.0, effective_duration - start_offset)

    # Adjust word timestamps relative to the trimmed start without dropping opening words
    aligned_words = []
    for w in words:
        if w["end"] > start_offset and w["start"] < (start_offset + actual_duration):
            aligned_words.append({
                "word": w["word"],
                "start": max(0.0, round(w["start"] - start_offset, 3)),
                "end": min(actual_duration, round(w["end"] - start_offset, 3))
            })

    # Slice exact speech-bounded video segment
    slice_cmd = [
        ffmpeg_bin, "-y",
        "-ss", str(actual_start),
        "-t", str(actual_duration),
        "-i", str(master_video_path),
        "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac",
        str(temp_slice)
    ]
    subprocess.run(slice_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    if progress_callback:
        progress_callback(60.0, f"Generating modern top hook pill & karaoke subtitles...")

    generate_ass_script(
        words=aligned_words,
        ass_path=ass_path,
        hook_banner=clip.on_screen_hook,
        highlight_color=highlight_color
    )

    if progress_callback:
        progress_callback(75.0, f"Tracking speaker face coordinates with OpenCV...")

    face_meta = analyze_faces_in_video(temp_slice)
    vf_filter = build_reframing_filter(face_meta, ass_path, style=reframing_style)

    if progress_callback:
        progress_callback(85.0, f"Encoding 1080x1920 with RTX 4050 NVENC...")

    # Audio fade out filter (0.25s) to ensure a complete, smooth natural finish
    fade_start = max(0.1, actual_duration - 0.25)
    af_filter = f"afade=t=out:st={fade_start:.2f}:d=0.25"

    vcodec_args = ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "21"] if HAS_NVENC else ["-c:v", "libx264", "-preset", "fast", "-crf", "21"]

    render_cmd = [
        ffmpeg_bin, "-y",
        "-i", temp_slice.name,
        "-vf", vf_filter,
        "-af", af_filter,
        *vcodec_args,
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart",
        final_mp4.name
    ]

    try:
        subprocess.run(
            render_cmd,
            cwd=str(output_dir),
            check=True,
            capture_output=True,
            text=True
        )
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr[:200] if e.stderr else "unknown error"
        print(f"  [!] NVENC render hit an issue ({err_msg}), falling back to CPU libx264...")
        cpu_render_cmd = [
            ffmpeg_bin, "-y",
            "-i", temp_slice.name,
            "-vf", vf_filter,
            "-af", af_filter,
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart",
            final_mp4.name
        ]
        subprocess.run(
            cpu_render_cmd,
            cwd=str(output_dir),
            check=True,
            capture_output=True,
            text=True
        )

    # Cleanup temp intermediates
    temp_slice.unlink(missing_ok=True)
    temp_audio.unlink(missing_ok=True)

    if progress_callback:
        progress_callback(100.0, f"Clip #{clip.clip_number} rendered with speech-snapped boundaries!")

    return final_mp4
