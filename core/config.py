import os
import shutil
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

TEMP_DIR = BASE_DIR / "temp"
EXPORTS_DIR = BASE_DIR / "exports"
DOWNLOADS_DIR = BASE_DIR / "downloads"

TEMP_DIR.mkdir(parents=True, exist_ok=True)
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""

def get_ffmpeg_binary() -> str:
    """Finds ffmpeg binary in PATH or Windows winget install directory."""
    which_ffmpeg = shutil.which("ffmpeg")
    if which_ffmpeg:
        return which_ffmpeg
    
    # Check standard Gyan.FFmpeg installation locations
    possible_paths = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages" / "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe",
        Path("C:/Program Files/FFmpeg/bin/ffmpeg.exe"),
        Path("C:/ffmpeg/bin/ffmpeg.exe")
    ]
    for p in possible_paths:
        if p.is_dir():
            matches = list(p.glob("**/ffmpeg.exe"))
            if matches:
                return str(matches[0])
        elif p.is_file():
            return str(p)
            
    return "ffmpeg"

def get_ffprobe_binary() -> str:
    """Finds ffprobe binary corresponding to ffmpeg binary or in PATH."""
    ffmpeg_bin = get_ffmpeg_binary()
    ffprobe_candidate = Path(ffmpeg_bin).parent / "ffprobe.exe"
    if ffprobe_candidate.exists():
        return str(ffprobe_candidate)
    which_ffprobe = shutil.which("ffprobe")
    if which_ffprobe:
        return which_ffprobe
    return "ffprobe"

def check_nvenc_support() -> bool:
    """Determines if NVIDIA NVENC hardware acceleration is usable."""
    ffmpeg_bin = get_ffmpeg_binary()
    try:
        res = subprocess.run([ffmpeg_bin, "-encoders"], capture_output=True, text=True, timeout=5)
        return "h264_nvenc" in res.stdout
    except Exception:
        return False

HAS_NVENC = check_nvenc_support()
