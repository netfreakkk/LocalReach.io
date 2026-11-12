import os
import re
import json
import shutil
import hashlib
import subprocess
from pathlib import Path
from typing import Callable, Optional
import yt_dlp
import cv2
from .config import get_ffmpeg_binary, HAS_NVENC, DOWNLOADS_DIR

def extract_cache_id(source: str) -> str:
    """Extracts YouTube ID or creates clean hash for caching."""
    # YouTube ID extraction patterns
    yt_patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",
        r"youtu\.be\/([0-9A-Za-z_-]{11})"
    ]
    for p in yt_patterns:
        m = re.search(p, source)
        if m:
            return m.group(1)
            
    # For local files or other URLs, hash the path/URL
    return hashlib.md5(source.encode("utf-8")).hexdigest()[:12]

def download_video(
    source: str,
    work_dir: Path,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> tuple[Path, Path, dict]:
    """
    Ingests source video with PERSISTENT DISK CACHING.
    If a video has been downloaded previously, it is instantly loaded from downloads/<id>/,
    completely skipping re-downloading from YouTube!
    """
    ffmpeg_bin = get_ffmpeg_binary()
    cache_id = extract_cache_id(source)
    cache_folder = DOWNLOADS_DIR / cache_id
    cache_folder.mkdir(parents=True, exist_ok=True)

    cached_master = cache_folder / "master.mp4"
    cached_proxy = cache_folder / "proxy_360p.mp4"
    cached_meta_file = cache_folder / "meta.json"

    master_dest = work_dir / "master.mp4"
    proxy_dest = work_dir / "proxy_360p.mp4"

    # ==========================================
    # 1. CHECK CACHE (INSTANT RE-USE)
    # ==========================================
    if cached_master.exists() and cached_master.stat().st_size > 1024 * 1024:
        if progress_callback:
            progress_callback(50.0, f"Found cached video on disk ({cache_id})! Loading instantly...")

        metadata = {}
        if cached_meta_file.exists():
            try:
                metadata = json.loads(cached_meta_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        if not metadata:
            cap = cv2.VideoCapture(str(cached_master))
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
            duration = int(frame_count / fps) if fps > 0 else 0
            cap.release()
            metadata = {
                "title": f"Cached Video ({cache_id})",
                "channel": "YouTube (Cached)",
                "duration": duration,
                "id": cache_id
            }

        # Ensure proxy exists
        if not cached_proxy.exists() or cached_proxy.stat().st_size == 0:
            if progress_callback:
                progress_callback(80.0, "Generating analysis proxy for cached video...")
            vcodec = ["-c:v", "h264_nvenc", "-preset", "p1", "-cq", "32"] if HAS_NVENC else ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "32"]
            cmd = [
                ffmpeg_bin, "-y", "-i", str(cached_master),
                "-vf", "scale=-2:360",
                *vcodec,
                "-c:a", "aac", "-b:a", "64k",
                str(cached_proxy)
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Copy or hardlink to working directory
        shutil.copy2(cached_master, master_dest)
        shutil.copy2(cached_proxy, proxy_dest)

        if progress_callback:
            progress_callback(100.0, f"Loaded from cache: '{metadata['title']}' (Download skipped!)")

        return master_dest, proxy_dest, metadata

    # ==========================================
    # 2. SOURCE IS LOCAL FILE
    # ==========================================
    source_path = Path(source)
    if source_path.is_file() and source_path.exists():
        if progress_callback:
            progress_callback(30.0, f"Caching local video: {source_path.name}...")

        shutil.copy2(source_path, cached_master)
        cap = cv2.VideoCapture(str(cached_master))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        duration = int(frame_count / fps) if fps > 0 else 0
        cap.release()

        metadata = {
            "title": source_path.stem.replace("_", " ").title(),
            "channel": "Local Upload",
            "duration": duration,
            "id": cache_id
        }
    else:
        # ==========================================
        # 3. DOWNLOAD FROM YOUTUBE & PERSIST TO CACHE
        # ==========================================
        locked_total_bytes = None
        def ytdl_hook(d):
            nonlocal locked_total_bytes
            if d.get('status') == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes') or 0
                if total > 0:
                    if locked_total_bytes is None or abs(locked_total_bytes - total) > (100 * 1024 * 1024):
                        locked_total_bytes = total
                    use_total = max(locked_total_bytes, downloaded)
                    pct = min(99.9, round((downloaded / use_total) * 100, 1))
                    mb_dl = downloaded / (1024 * 1024)
                    mb_total = use_total / (1024 * 1024)
                    if mb_total >= 1000:
                        msg = f"Downloading 1080p: {pct}% ({mb_dl/1024:.2f}GB / ~{mb_total/1024:.2f}GB)"
                    else:
                        msg = f"Downloading 1080p: {pct}% ({mb_dl:.1f}MB / ~{mb_total:.0f}MB)"
                    if progress_callback:
                        progress_callback(pct, msg)
            elif d.get('status') == 'finished':
                if progress_callback:
                    progress_callback(100.0, "Merging streams & saving to permanent downloads cache...")

        temp_download_pattern = str(cache_folder / "temp_master.%(ext)s")
        ydl_opts = {
            'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': temp_download_pattern,
            'merge_output_format': 'mp4',
            'ffmpeg_location': ffmpeg_bin,
            'quiet': True,
            'no_warnings': True,
            'progress_hooks': [ytdl_hook]
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(source, download=True)
            temp_file = cache_folder / f"temp_master.{info.get('ext', 'mp4')}"
            if temp_file.exists():
                if cached_master.exists():
                    cached_master.unlink()
                temp_file.rename(cached_master)

        metadata = {
            "title": info.get("title", "Unknown Title"),
            "channel": info.get("uploader", "Unknown Channel"),
            "duration": info.get("duration", 0),
            "id": cache_id,
            "heatmap": info.get("heatmap"),
            "chapters": info.get("chapters", [])
        }

    # Save metadata JSON to cache
    cached_meta_file.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    # Generate 360p analysis proxy in cache folder
    if progress_callback:
        progress_callback(90.0, "Generating 360p analysis proxy...")

    vcodec = ["-c:v", "h264_nvenc", "-preset", "p1", "-cq", "32"] if HAS_NVENC else ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "32"]
    cmd = [
        ffmpeg_bin, "-y", "-i", str(cached_master),
        "-vf", "scale=-2:360",
        *vcodec,
        "-c:a", "aac", "-b:a", "64k",
        str(cached_proxy)
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Copy cached master and proxy into work directory
    shutil.copy2(cached_master, master_dest)
    shutil.copy2(cached_proxy, proxy_dest)

    if progress_callback:
        progress_callback(100.0, f"Video ready & saved to disk: '{metadata['title']}'")

    return master_dest, proxy_dest, metadata
