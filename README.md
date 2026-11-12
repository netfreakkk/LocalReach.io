# ⚡ ScaleReach.ai Local Studio (AI Shorts & Reels Engine)

A local-first, GPU-accelerated video repurposing engine powered by **Google Gemini Multimodal AI**, **OpenCV Haar Cascade Face Tracking**, **Faster-Whisper**, and **NVIDIA RTX NVENC**.

Feed it any YouTube URL or local long-form video, and it automatically extracts narrative-complete vertical 9:16 Shorts/Reels with:
- **🎯 Dynamic Face Tracking & Smart Reframing:** Automatically centers active speakers using ultra-fast local OpenCV Haar Cascade detection (200+ FPS) or dual-speaker podcast split-screen.
- **✨ Animated Karaoke Subtitles:** Hormozi-style word-by-word active highlighting with pop-scale animation and translucent dark glassmorphism top hook pill.
- **🌐 Strict Latin / Hinglish Transliteration:** Automatically translates Hindi/Urdu/multilingual speech into clean English with phonetic Roman Hinglish—preventing broken unicode scripts.
- **✂️ Natural Speech Boundary Snapping:** Eliminates dead air and trailing awkward silence by dynamically cutting at natural phrase boundaries and applying soft audio fade-outs.
- **🔥 YouTube Hotspot & Chapter Detection:** Extracts audience retention peaks directly from YouTube's "Most Replayed" heatmaps and chapter markers.
- **📁 Date-Organized Export Management:** Automatically groups rendered clips into clean chronological date folders (`exports/YYYY-MM-DD/HH-MM-SS_<Title>/`) with one-click download buttons.
- **🚀 Algorithm Hijack Post Pack:** Generates copy-paste ready YouTube Shorts titles, Instagram/Facebook SEO search paragraphs, and YouTube Studio keyword tags in `POST_PACK.md`.

---

## 🛠️ Tech Stack & Architecture

- **Multimodal AI:** Gemini 3.1 Flash-Lite / 3.8 Flash / 2.5 Flash (Watches 360p proxy stream for visual/vocal energy peaks & retention scoring)
- **Face Tracking & Reframer:** OpenCV Haar Cascade (Offline, 100% local, zero external dependency failures)
- **Word-Level Subtitles:** `faster-whisper` (INT8 quantized, millisecond-accurate word timestamps)
- **Compositor & Encoder:** FFmpeg with **NVIDIA NVENC (`h264_nvenc`)** for rendering 1080x1920 clips in seconds
- **Web Studio Dashboard:** FastAPI + Tailwind CSS dark-mode UI with live dual-progress metrics

---

## 🚀 Quick Start

### 1. Configure Your Gemini API Key
Create a `.env` file in the project root (see `.env.example`):
```env
GEMINI_API_KEY=your_gemini_api_key_here
```
*(You can get a free API key at [Google AI Studio](https://aistudio.google.com/))*

> **Note:** If no API key is provided, the engine seamlessly falls back to 100% offline local transcription and heuristic virality scoring.

---

### 2. Method A: Web Studio Dashboard (Recommended)

Start the local web server:
```powershell
.venv\Scripts\python.exe server.py
```
*(Or double-click `start.bat`)*

Then open your browser at **`http://localhost:8000`**.

You can:
1. Paste any YouTube URL or drop a local video file.
2. Choose your clip target: **Auto (All Video Hotspots)**, **3 Clips**, **5 Clips**, **8 Clips**, **10 Clips**, or **12 Clips**.
3. Select your framing layout (**Face Track**, **Podcast Split**, **Blurred Canvas**, or **Direct Center**).
4. Choose your subtitle color (Hormozi Yellow, Emerald Green, Electric Cyan, Crimson Alert).
5. Click **Generate Viral Clips**.
6. Watch live progress and preview/download rendered clips with 1-click SEO copy buttons.

---

### 3. Method B: Command Line (CLI)

Run directly on any YouTube video:
```powershell
.venv\Scripts\python.exe clip_station.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

#### Optional CLI Flags:
- `--style`: `smart` (default face-tracking), `split` (top/bottom podcast layout), `blur` (blurred 9:16 background), `center` (direct crop).
- `--color`: Subtitle highlight color in ASS hex (e.g. `&H0000FFFF&` for Yellow).
- `--local`: Force 100% local AI execution (zero external API calls).

---

## 📂 Project Structure

```text
├── core/
│   ├── analyzer.py          # Gemini multimodal video analyzer & hotspot integration
│   ├── compositor.py        # NVENC video cutting, audio fading, and subtitle muxing
│   ├── config.py            # Environment, path resolution, and hardware detection
│   ├── haarcascade_frontalface_default.xml # OpenCV local face detection model
│   ├── hotspots.py          # YouTube heatmap and chapter extraction
│   ├── ingest.py            # Video download, 360p proxy creation, and permanent disk cache
│   ├── local_analyzer.py    # 100% offline Whisper-based hook analysis fallback
│   ├── post_pack.py         # SEO metadata, titles, and hashtags generator
│   ├── schema.py            # Pydantic data models for structured viral analysis
│   ├── smart_crop.py        # OpenCV face centering and vertical reframing filters
│   └── subtitles.py         # Word timestamp extraction, Latin sanitizer, and ASS script generator
├── static/
│   └── index.html           # Tailwind CSS dark-mode web studio dashboard
├── clip_station.py          # CLI runner
├── server.py                # FastAPI web server and background job coordinator
├── start.bat                # Windows 1-click launcher
├── .env.example             # Template for API keys
└── .gitignore               # Excludes secrets, virtual environment, and heavy media
```

---

## 🔒 Security & Privacy

- All video downloads and rendered clips stay on your local machine under `downloads/` and `exports/`.
- Your `.env` API key is strictly ignored by Git and never committed or shared.
- Runs 100% locally with offline fallback support.
