# Clipz.me

A dark, creator-focused web prototype for turning long videos and streams into short clips.

## Current build

- Responsive creator dashboard
- Flask backend and health endpoint
- YouTube video, Shorts, and Twitch clip/VOD URL validation
- Render deployment configuration

**Honest status:** this initial build validates links only. It does not yet download, analyze, cut, caption, or export video. Those capabilities require a separate video-processing pipeline and will be added in later milestones.

## Run locally

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

## Deploy to Render

Create a new **Web Service**, connect this repository, and use the settings in `render.yaml`. The health check is `/health`.

## Next milestones

1. Add safe, temporary job records and progress UI.
2. Implement video ingestion for sources and rights-approved files.
3. Build highlight detection and clip rendering.
4. Add synced captions, context-aware emoji styling, previews, and exports.
