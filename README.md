# Clipz.me

A dark, creator-focused web prototype for turning public YouTube and Twitch videos into short-form clips.

## Current working features

- Responsive creator dashboard
- Flask backend and Render health endpoint
- YouTube and Twitch URL support through yt-dlp
- Download a public source video (up to 30 minutes / 500 MB)
- Rank candidate moments using audio loudness/energy
- Render 9:16 portrait MP4 clips (10–60 seconds, up to five clips)
- Download generated clips while the Render instance is alive

## Important limitations

This is a **working MVP, not full semantic AI clipping yet**. Automatic selection currently ranks high-energy audio windows; loud audio can mean music or noise rather than a funny moment. Semantic/funny-moment detection, synced subtitles, context-aware emojis, accounts, and persistent clip storage are not implemented yet.

The free Render instance has limited CPU, RAM, request time, and temporary storage. Processing can take a few minutes. Generated clips are temporary and may disappear when the service restarts or sleeps. Public links only; private, sign-in-required, DRM-protected, or unavailable videos will not work.

Only process videos you own or have permission to download and edit, and follow the source platform's terms.

## Run locally (Windows PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

## Deploy to Render

Connect this repository as a Python Web Service. Use:

- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app --bind 0.0.0.0:$PORT --timeout 600`
- Health check: `/health`

## Next milestones

1. Transcription and synced captions
2. Semantic highlight ranking (speech cues/context, not audio volume alone)
3. Context-aware emoji styling
4. Persistent job queue and clip storage for reliable processing
