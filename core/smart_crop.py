import cv2
import numpy as np
from pathlib import Path

CASCADE_PATH = Path(__file__).resolve().parent / "haarcascade_frontalface_default.xml"

def analyze_faces_in_video(video_path: Path, sample_fps: float = 2.0) -> dict:
    """
    Samples frames from video clip to detect face positions and layout mode.
    Uses OpenCV Haar Cascade for ultra-fast, robust face detection without external dependencies.
    Returns:
        {
            "mode": "single" | "split" | "center",
            "primary_x": float,  # Normalized 0.0 to 1.0
            "secondary_x": float | None,
            "face_count": int
        }
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return {"mode": "center", "primary_x": 0.5, "secondary_x": None, "face_count": 0}

    try:
        video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_interval = max(1, int(video_fps / sample_fps))

        face_cascade = cv2.CascadeClassifier(str(CASCADE_PATH))
        face_x_coords = []
        
        frame_idx = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_interval == 0:
                h, w = frame.shape[:2]
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                # Small scale for instant detection
                small = cv2.resize(gray, (0, 0), fx=0.5, fy=0.5)
                faces = face_cascade.detectMultiScale(small, scaleFactor=1.1, minNeighbors=4, minSize=(30, 30))

                if len(faces) > 0:
                    frame_faces = []
                    for (fx, fy, fw, fh) in faces:
                        # fx, fw are on 0.5 scaled image
                        orig_center_x = (fx * 2 + fw) / float(w)
                        frame_faces.append(orig_center_x)
                    face_x_coords.append(frame_faces)

            frame_idx += 1
    finally:
        cap.release()

    if not face_x_coords:
        return {"mode": "center", "primary_x": 0.5, "secondary_x": None, "face_count": 0}

    # Aggregate face positions
    all_faces = [x for frame in face_x_coords for x in frame]
    if not all_faces:
        return {"mode": "center", "primary_x": 0.5, "secondary_x": None, "face_count": 0}

    # Check for split screen (two clusters of faces: e.g. Left < 0.45 and Right > 0.55)
    left_cluster = [x for x in all_faces if x < 0.45]
    right_cluster = [x for x in all_faces if x > 0.55]

    total_detections = len(all_faces)
    if len(left_cluster) > total_detections * 0.25 and len(right_cluster) > total_detections * 0.25:
        # Split-screen podcast layout detected!
        return {
            "mode": "split",
            "primary_x": float(np.median(left_cluster)),
            "secondary_x": float(np.median(right_cluster)),
            "face_count": 2
        }

    # Single dominant speaker
    primary_x = float(np.median(all_faces))
    return {
        "mode": "single",
        "primary_x": primary_x,
        "secondary_x": None,
        "face_count": 1
    }

def build_reframing_filter(
    analysis: dict,
    ass_subtitle_path: Path,
    style: str = "smart"
) -> str:
    """
    Constructs the high-speed FFmpeg video filter chain to produce vertical 1080x1920 video.
    Supports:
      - 'smart': Face-centered 9:16 crop
      - 'split': Top/bottom split-screen if 2 podcast speakers are found
      - 'blur': Blurred 9:16 background with centered original video
      - 'center': Direct 9:16 center crop
    """
    ass_escaped = str(ass_subtitle_path.name).replace("\\", "/").replace(":", "\\:")

    if style == "blur":
        # Dual-layer blurred canvas
        return (
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5[bg]; "
            f"[0:v]scale=1080:-2[fg]; "
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2,ass='{ass_escaped}'"
        )

    mode = analysis.get("mode", "single")

    # Podcast split screen is only used if explicitly selected as 'split'
    if style == "split":
        x1_norm = analysis.get("primary_x", 0.25)
        x2_norm = analysis.get("secondary_x", 0.75) if analysis.get("secondary_x") is not None else 0.75
        return (
            f"[0:v]split=2[sp1][sp2]; "
            f"[sp1]crop=w='min(in_w, in_h*1.0)':h='in_h':x='max(0, min(max(0, in_w-in_h), in_w*{x1_norm} - in_h/2))':y=0,scale=1080:960[top]; "
            f"[sp2]crop=w='min(in_w, in_h*1.0)':h='in_h':x='max(0, min(max(0, in_w-in_h), in_w*{x2_norm} - in_h/2))':y=0,scale=1080:960[bot]; "
            f"[top][bot]vstack=inputs=2,ass='{ass_escaped}'"
        )

    # Default / Smart mode: Focus on dynamic single face framing (no split screen)
    if style == "smart" or mode == "single":
        norm_x = analysis.get("primary_x", 0.5)
        return (
            f"crop=w='in_h*(9/16)':h='in_h':x='max(0, min(in_w - in_h*(9/16), in_w*{norm_x} - (in_h*(9/16))/2))':y=0,"
            f"scale=1080:1920,ass='{ass_escaped}'"
        )

    # Standard center crop fallback
    return f"scale=-2:1920,crop=1080:1920:(in_w-1080)/2:0,ass='{ass_escaped}'"
