import os
import sys
import re
import json
import time
import shutil
import threading
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, BackgroundTasks, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Ensure utf-8 output on Windows console
if sys.stdout:
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from core.config import BASE_DIR, EXPORTS_DIR, TEMP_DIR, GEMINI_API_KEY, HAS_NVENC
from core.ingest import download_video
from core.analyzer import analyze_video_moments
from core.compositor import render_vertical_clip
from core.post_pack import write_post_pack

app = FastAPI(title="ScaleReach.ai Local Clone")

# Serve exported videos statically
app.mount("/exports", StaticFiles(directory=str(EXPORTS_DIR)), name="exports")

# In-memory job state tracker with dual progress metrics
jobs = {}

class GenerationRequest(BaseModel):
    url: str
    style: str = "smart" # "smart", "split", "blur", "center"
    highlight_color: str = "&H0000FFFF&" # Yellow
    model_name: str = "gemini-3.1-flash-lite"
    gemini_api_key: str = ""
    force_local: bool = False
    clip_count: int = 5 # 0 = Auto (All Hotspots), 3, 5, 8, 10, 12

def process_video_pipeline(
    job_id: str,
    source_input: str, # YouTube URL or local file path
    style: str,
    highlight_color: str,
    model_name: str,
    gemini_api_key: str,
    force_local: bool,
    clip_count: int = 5
):
    job = jobs[job_id]
    work_dir = TEMP_DIR / job_id
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        # ==========================================
        # STEP 1: INGESTION (0% - 25% Overall)
        # ==========================================
        job["current_step"] = 1
        job["step_name"] = "Step 1/5: Ingestion & Analysis Proxy"
        job["overall_progress"] = 5
        job["secondary_progress"] = 10
        job["secondary_message"] = "Preparing video ingestion..."

        def ingest_progress(pct: float, msg: str):
            job["secondary_progress"] = round(pct, 1)
            job["secondary_message"] = msg
            job["overall_progress"] = round(5 + (pct / 100.0) * 20, 1)

        master_mp4, proxy_mp4, meta = download_video(source_input, work_dir, progress_callback=ingest_progress)
        job["video_title"] = meta["title"]
        job["overall_progress"] = 25
        job["secondary_progress"] = 100
        job["secondary_message"] = f"Ingestion complete: '{meta['title']}' ({meta['duration']}s)"

        # Date-organized export structure: exports/YYYY-MM-DD/HH-MM-SS_{clean_title}
        date_str = datetime.now().strftime("%Y-%m-%d")
        time_str = datetime.now().strftime("%H-%M-%S")
        safe_title = re.sub(r'[^a-zA-Z0-9_\- ]', '', meta.get("title", "Video"))[:35].strip().replace(" ", "_")
        folder_name = f"{time_str}_{safe_title}" if safe_title else f"{time_str}_{job_id}"
        export_dir = EXPORTS_DIR / date_str / folder_name
        export_dir.mkdir(parents=True, exist_ok=True)
        rel_url = f"/exports/{date_str}/{folder_name}"
        job["export_dir"] = rel_url
        job["export_path"] = str(export_dir)
        job["date_folder"] = date_str

        # ==========================================
        # STEP 2: AI HOOK & RETENTION ANALYSIS (25% - 50% Overall)
        # ==========================================
        job["current_step"] = 2
        job["step_name"] = "Step 2/5: AI Viral Hook Detection"
        job["overall_progress"] = 30
        job["secondary_progress"] = 20
        api_key = gemini_api_key.strip() or GEMINI_API_KEY
        is_local = force_local or not api_key

        if is_local:
            job["secondary_message"] = "Transcribing with Faster-Whisper on CPU & scoring viral hooks..."
        else:
            job["secondary_message"] = "Uploading proxy to Gemini 3.8 Flash for audiovisual energy analysis..."

        # Determine target clips count (intelligent auto-scaling if 0/auto)
        if clip_count <= 0:
            from core.hotspots import extract_youtube_heatmap_hotspots, extract_chapter_hotspots
            heat = extract_youtube_heatmap_hotspots(meta) if meta else []
            ch = extract_chapter_hotspots(meta) if meta else []
            available_hotspots = max(len(heat), len(ch))
            
            vid_dur = meta.get("duration", 0) if meta else 0
            if available_hotspots >= 10:
                target_clips = min(15, available_hotspots)
            elif available_hotspots >= 5:
                target_clips = available_hotspots
            elif vid_dur >= 3600: # >1 hr
                target_clips = 10
            elif vid_dur >= 1800: # >30 min
                target_clips = 8
            elif vid_dur >= 600:  # >10 min
                target_clips = 6
            else:
                target_clips = 5
        else:
            target_clips = clip_count

        job["secondary_progress"] = 50
        analysis = analyze_video_moments(
            proxy_mp4,
            api_key=api_key,
            model_name=model_name,
            video_title=meta["title"],
            force_local=force_local,
            metadata=meta,
            target_clips=target_clips
        )
        job["total_clips"] = len(analysis.clips)
        job["overall_progress"] = 50
        job["secondary_progress"] = 100
        job["secondary_message"] = f"Found {len(analysis.clips)} viral hooks! (Theme: {analysis.dominant_theme})"

        # ==========================================
        # STEP 3 & 4: RENDERING (50% - 90% Overall)
        # ==========================================
        job["current_step"] = 3
        job["step_name"] = "Step 3/5: Face Reframing & RTX NVENC Rendering"
        total_clips = len(analysis.clips)

        for idx, c in enumerate(analysis.clips):
            clip_num = idx + 1
            base_overall = 50 + int((idx / total_clips) * 40)
            
            def clip_render_progress(sub_pct: float, sub_msg: str):
                job["secondary_progress"] = round(sub_pct, 1)
                job["secondary_message"] = f"Clip #{clip_num}/{total_clips} — {sub_msg}"
                job["overall_progress"] = round(base_overall + (sub_pct / 100.0) * (40 / total_clips), 1)

            render_vertical_clip(
                master_video_path=master_mp4,
                clip=c,
                output_dir=export_dir,
                reframing_style=style,
                highlight_color=highlight_color,
                progress_callback=clip_render_progress
            )

        # ==========================================
        # STEP 5: POST PACK & PACKAGING (90% - 100% Overall)
        # ==========================================
        job["current_step"] = 5
        job["step_name"] = "Step 5/5: Generating SEO & Algorithm Post Pack"
        job["overall_progress"] = 92
        job["secondary_progress"] = 50
        job["secondary_message"] = "Formatting YouTube Shorts tags and Instagram Explore context..."
        
        write_post_pack(analysis, export_dir, source_input, video_title=meta["title"], job_id=job_id, relative_export_dir=rel_url)

        job["status"] = "completed"
        job["overall_progress"] = 100
        job["secondary_progress"] = 100
        job["step_name"] = f"✓ Completed! {len(analysis.clips)} Viral Clips Ready"
        job["secondary_message"] = f"All {len(analysis.clips)} clips rendered and organized in exports/{date_str}/{folder_name}!"
        job["export_dir"] = rel_url
        
        meta_file = export_dir / "metadata.json"
        if meta_file.exists():
            job["results"] = json.loads(meta_file.read_text(encoding="utf-8"))

    except Exception as e:
        job["status"] = "failed"
        job["step_name"] = "Failed"
        job["secondary_message"] = str(e)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

@app.post("/api/generate")
def start_generation(req: GenerationRequest, background_tasks: BackgroundTasks):
    job_id = f"batch_{int(time.time())}"
    jobs[job_id] = {
        "job_id": job_id,
        "status": "processing",
        "current_step": 1,
        "total_steps": 5,
        "step_name": "Initializing generation...",
        "overall_progress": 5,
        "secondary_progress": 10,
        "secondary_message": "Setting up environment...",
        "video_title": "",
        "created_at": time.time(),
        "results": None
    }
    background_tasks.add_task(
        process_video_pipeline,
        job_id,
        req.url,
        req.style,
        req.highlight_color,
        req.model_name,
        req.gemini_api_key,
        req.force_local,
        req.clip_count
    )
    return {"job_id": job_id, "status": "queued"}

@app.post("/api/upload-and-generate")
async def upload_and_generate(
    background_tasks: BackgroundTasks,
    video_file: UploadFile = File(...),
    style: str = Form("smart"),
    highlight_color: str = Form("&H0000FFFF&"),
    model_name: str = Form("gemini-3.1-flash-lite"),
    gemini_api_key: str = Form(""),
    force_local: bool = Form(False),
    clip_count: int = Form(5)
):
    job_id = f"batch_{int(time.time())}"
    upload_dir = TEMP_DIR / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    file_ext = Path(video_file.filename).suffix or ".mp4"
    saved_file = upload_dir / f"{job_id}{file_ext}"

    # Stream file to disk
    with open(saved_file, "wb") as buffer:
        shutil.copyfileobj(video_file.file, buffer)

    jobs[job_id] = {
        "job_id": job_id,
        "status": "processing",
        "current_step": 1,
        "total_steps": 5,
        "step_name": "Step 1/5: Upload Complete — Processing...",
        "overall_progress": 10,
        "secondary_progress": 100,
        "secondary_message": f"Saved uploaded file: {video_file.filename}",
        "video_title": Path(video_file.filename).stem,
        "created_at": time.time(),
        "results": None
    }

    background_tasks.add_task(
        process_video_pipeline,
        job_id,
        str(saved_file),
        style,
        highlight_color,
        model_name,
        gemini_api_key,
        force_local,
        clip_count
    )
    return {"job_id": job_id, "status": "queued"}

def find_export_by_job_id(job_id: str):
    if not EXPORTS_DIR.exists():
        return None, None
    # 1. Direct match (legacy flat layout e.g. exports/batch_xxx)
    old_path = EXPORTS_DIR / job_id
    if old_path.exists() and (old_path / "metadata.json").exists():
        return old_path, f"/exports/{job_id}"
    
    # 2. Date-nested layout (e.g. exports/YYYY-MM-DD/HH-MM-SS_title)
    for meta_file in EXPORTS_DIR.glob("*/*/metadata.json"):
        try:
            data = json.loads(meta_file.read_text(encoding="utf-8"))
            if data.get("job_id") == job_id or job_id in meta_file.parent.name:
                rel = meta_file.parent.relative_to(EXPORTS_DIR).as_posix()
                return meta_file.parent, f"/exports/{rel}"
        except Exception:
            continue
    return None, None

@app.get("/api/status/{job_id}")
def get_status(job_id: str):
    if job_id not in jobs:
        folder, rel_url = find_export_by_job_id(job_id)
        if folder:
            meta_file = folder / "metadata.json"
            data = json.loads(meta_file.read_text(encoding="utf-8"))
            return {
                "job_id": job_id,
                "status": "completed",
                "current_step": 5,
                "total_steps": 5,
                "step_name": "✓ Completed",
                "overall_progress": 100,
                "secondary_progress": 100,
                "secondary_message": f"Loaded from {folder.relative_to(EXPORTS_DIR).as_posix()}",
                "video_title": data.get("title", ""),
                "export_dir": rel_url,
                "results": data
            }
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]

@app.get("/api/history")
def get_history():
    history = []
    if EXPORTS_DIR.exists():
        meta_files = list(EXPORTS_DIR.glob("*/metadata.json")) + list(EXPORTS_DIR.glob("*/*/metadata.json"))
        meta_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        for meta_file in meta_files:
            try:
                data = json.loads(meta_file.read_text(encoding="utf-8"))
                folder = meta_file.parent
                rel_path = folder.relative_to(EXPORTS_DIR).as_posix()
                date_label = folder.parent.name if folder.parent != EXPORTS_DIR else "Legacy"
                history.append({
                    "job_id": data.get("job_id", folder.name),
                    "export_dir": f"/exports/{rel_path}",
                    "date": date_label,
                    "folder_name": folder.name,
                    "title": data.get("title", "Video"),
                    "clip_count": len(data.get("clips", [])),
                    "summary": data.get("summary", "")
                })
            except Exception:
                continue
    return history

@app.get("/", response_class=HTMLResponse)
def index():
    html_path = BASE_DIR / "static" / "index.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    return "<h1>ScaleReach.ai Clone Server Running</h1>"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
