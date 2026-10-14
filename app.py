import os
import re
from urllib.parse import urlparse

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be"}
TWITCH_HOSTS = {"twitch.tv", "www.twitch.tv", "m.twitch.tv", "clips.twitch.tv", "www.twitch.tv"}

def classify_video_url(value):
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip()
    if not re.match(r"^https?://", candidate, re.I):
        candidate = "https://" + candidate
    try:
        parsed = urlparse(candidate)
    except ValueError:
        return None
    host = (parsed.hostname or "").lower()
    if host in YOUTUBE_HOSTS:
        if host.endswith("youtu.be"):
            return "YouTube" if parsed.path.strip("/") else None
        if parsed.path == "/watch" and parsed.query:
            from urllib.parse import parse_qs
            return "YouTube" if parse_qs(parsed.query).get("v") else None
        if re.match(r"^/(shorts|live|embed)/[^/]+", parsed.path):
            return "YouTube"
    if host in TWITCH_HOSTS:
        path = parsed.path.strip("/")
        if host == "clips.twitch.tv":
            return "Twitch" if path else None
        if re.match(r"^(videos/\d+|[^/]+/clip/[^/]+)$", path):
            return "Twitch"
    return None

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/health")
def health():
    return jsonify(status="ok", app="Clipz.me")

@app.post("/api/validate")
def validate():
    payload = request.get_json(silent=True) or {}
    video_url = payload.get("url", "")
    platform = classify_video_url(video_url)
    if not platform:
        return jsonify(ok=False, error="Enter a valid YouTube video/Short or Twitch video/clip URL."), 400
    return jsonify(ok=True, platform=platform, url=video_url.strip(),
                   message="Link verified. Automatic highlight processing is the next build stage.")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
