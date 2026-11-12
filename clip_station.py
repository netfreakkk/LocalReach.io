import os
import sys
import re
import time
import shutil
import argparse
from datetime import datetime
from pathlib import Path

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

def run_pipeline(
    video_source: str,
    style: str = "smart",
    model: str = "gemini-3.8-flash",
    highlight_color: str = "&H0000FFFF&",
    force_local: bool = False
):
    print("=" * 65)
    print("🎬 SCALEREACH.AI LOCAL CLONE — SHORT-FORM GENERATION ENGINE")
    print(f"Hardware Acceleration (RTX 4050 NVENC): {'ACTIVE' if HAS_NVENC else 'CPU FALLBACK'}")
    print(f"Reframing Style: {style.upper()} | Subtitle Color: {highlight_color}")
    print(f"AI Engine: {'100% LOCAL (Zero API Key)' if force_local or not GEMINI_API_KEY else 'Gemini Flash'}")
    print("=" * 65)

    run_id = f"batch_{int(time.time())}"
    work_dir = TEMP_DIR / run_id
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Step 1: Ingestion
        print("\n[Step 1/5] Ingesting source media...")
        master_mp4, proxy_mp4, meta = download_video(video_source, work_dir)
        print(f"  [✓] Source: '{meta['title']}' ({meta['duration']}s)")

        # Date-organized export folder: exports/YYYY-MM-DD/HH-MM-SS_{clean_title}
        date_str = datetime.now().strftime("%Y-%m-%d")
        time_str = datetime.now().strftime("%H-%M-%S")
        safe_title = re.sub(r'[^a-zA-Z0-9_\- ]', '', meta.get("title", "Video"))[:35].strip().replace(" ", "_")
        folder_name = f"{time_str}_{safe_title}" if safe_title else f"{time_str}_{run_id}"
        export_dir = EXPORTS_DIR / date_str / folder_name
        export_dir.mkdir(parents=True, exist_ok=True)

        # Step 2: Virality Analysis (Gemini Flash or 100% Local AI)
        print("\n[Step 2/5] Running Viral Hook & Retention Analysis...")
        analysis = analyze_video_moments(
            proxy_mp4,
            model_name=model,
            video_title=meta['title'],
            force_local=force_local
        )
        print(f"  [✓] Found {len(analysis.clips)} viral hooks! Theme: {analysis.dominant_theme}")
        for c in analysis.clips:
            print(f"      • Clip #{c.clip_number} [Score {c.viral_score}/100]: '{c.on_screen_hook}' ({c.start_seconds:.1f}s - {c.end_seconds:.1f}s)")

        # Step 3 & 4: Compositor & Smart Reframing
        print("\n[Step 3/5] Slicing, Reframing & Rendering 9:16 Vertical Videos...")
        rendered_files = []
        for c in analysis.clips:
            out_file = render_vertical_clip(
                master_video_path=master_mp4,
                clip=c,
                output_dir=export_dir,
                reframing_style=style,
                highlight_color=highlight_color
            )
            rendered_files.append(out_file)

        # Step 5: Post Pack Metadata Generation
        print("\n[Step 4/5] Generating Algorithm-Hijack Metadata & POST_PACK.md...")
        post_pack = write_post_pack(
            analysis,
            export_dir,
            video_source,
            video_title=meta['title'],
            job_id=run_id,
            relative_export_dir=f"/exports/{date_str}/{folder_name}"
        )
        print(f"  [✓] Saved post pack to: {post_pack}")

        print("\n" + "=" * 65)
        print("🎉 SUCCESS! All clips and metadata are packaged and ready.")
        print(f"📁 Output Folder: {export_dir}")
        print("=" * 65)

    finally:
        print("\n[*] Cleaning up temporary render proxy and intermediate files...")
        shutil.rmtree(work_dir, ignore_errors=True)

def main():
    parser = argparse.ArgumentParser(description="ScaleReach.ai Local Clone — Video Generation Engine")
    parser.add_argument("source", help="YouTube URL or local video file path")
    parser.add_argument(
        "--style",
        choices=["smart", "split", "blur", "center"],
        default="smart",
        help="Reframing layout: smart (face tracking), split (podcast dual-speaker), blur (blurred canvas), center (direct crop)"
    )
    parser.add_argument(
        "--model",
        default="gemini-3.8-flash",
        help="Gemini model version (default: gemini-3.8-flash)"
    )
    parser.add_argument(
        "--color",
        default="&H0000FFFF&",
        help="ASS hex color for active subtitle word (default yellow: &H0000FFFF&, neon green: &H002EFC2E&)"
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Force 100% offline local AI analysis (Zero API key needed)"
    )

    args = parser.parse_args()
    run_pipeline(
        video_source=args.source,
        style=args.style,
        model=args.model,
        highlight_color=args.color,
        force_local=args.local
    )

if __name__ == "__main__":
    main()
