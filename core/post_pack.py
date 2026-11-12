import json
from pathlib import Path
from .schema import VideoAnalysisResult

def write_post_pack(
    analysis: VideoAnalysisResult,
    export_dir: Path,
    source_url: str,
    video_title: str = "",
    job_id: str = "",
    relative_export_dir: str = ""
) -> Path:
    """
    Generates a master POST_PACK.md and metadata.json file containing
    copy-paste ready copy and algorithm-hijacking search blocks for all clips.
    """
    export_dir.mkdir(parents=True, exist_ok=True)
    post_pack_md = export_dir / "POST_PACK.md"
    metadata_json = export_dir / "metadata.json"

    md_lines = [
        "# 🚀 VIRAL SOCIAL MEDIA POST PACK",
        f"- **Source Title:** {video_title or 'Input Video'}",
        f"- **Source URL:** {source_url}",
        f"- **Core Premise:** {analysis.video_summary}",
        f"- **Dominant Genre:** {analysis.dominant_theme}\n",
        "---\n"
    ]

    clips_data = []

    for c in analysis.clips:
        clip_filename = f"clip_{c.clip_number}_score{c.viral_score}.mp4"
        all_hashtags = " ".join(c.niche_hashtags + c.algo_hijack_hashtags)
        yt_tags_csv = ", ".join(c.yt_studio_tags)

        md_lines.append(f"## 🎬 Clip #{c.clip_number} — Viral Score: {c.viral_score}/100")
        md_lines.append(f"- **Rendered File:** `{clip_filename}`")
        md_lines.append(f"- **Timestamp:** `{c.start_seconds:.1f}s` to `{c.end_seconds:.1f}s` (Duration: {c.end_seconds - c.start_seconds:.1f}s)")
        md_lines.append(f"- **Top Hook Banner:** `{c.on_screen_hook}`")
        md_lines.append(f"- **Hook Rationale:** {c.hook_rationale}\n")

        md_lines.append("### 1. YouTube Shorts Title (Copy-Paste)")
        md_lines.append(f"```text\n{c.yt_shorts_title}\n```\n")

        md_lines.append("### 2. Instagram & Facebook Reels Caption (Algorithm-Optimized)")
        ig_caption = (
            f"{c.ig_caption_hook}\n\n"
            f"Save this for later & share with someone who needs to see this! 👇\n.\n.\n"
            f"[Search Context]: {c.ig_seo_keyword_paragraph}\n.\n.\n"
            f"{all_hashtags}"
        )
        md_lines.append(f"```text\n{ig_caption}\n```\n")

        md_lines.append("### 3. YouTube Studio Search Tags (Comma-Separated)")
        md_lines.append(f"```text\n{yt_tags_csv}\n```\n")
        md_lines.append("---\n")

        clips_data.append({
            "clip_number": c.clip_number,
            "filename": clip_filename,
            "viral_score": c.viral_score,
            "start_seconds": c.start_seconds,
            "end_seconds": c.end_seconds,
            "hook_banner": c.on_screen_hook,
            "yt_shorts_title": c.yt_shorts_title,
            "ig_caption": ig_caption,
            "yt_studio_tags": c.yt_studio_tags,
            "hashtags": c.niche_hashtags + c.algo_hijack_hashtags
        })

    post_pack_md.write_text("\n".join(md_lines), encoding="utf-8")
    
    with open(metadata_json, "w", encoding="utf-8") as f:
        json.dump({
            "job_id": job_id,
            "export_dir": relative_export_dir,
            "source_url": source_url,
            "title": video_title,
            "summary": analysis.video_summary,
            "theme": analysis.dominant_theme,
            "clips": clips_data
        }, f, indent=2, ensure_ascii=False)

    return post_pack_md
