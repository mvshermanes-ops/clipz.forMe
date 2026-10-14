import array
import glob
import math
import os
import re
import secrets
import subprocess
import tempfile
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import imageio_ffmpeg
import yt_dlp
from flask import Flask, jsonify, render_template, request, send_from_directory

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024

YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be"}
TWITCH_HOSTS = {"twitch.tv", "www.twitch.tv", "m.twitch.tv", "clips.twitch.tv"}
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
CLIP_ROOT = Path(tempfile.gettempdir()) / "clipz-jobs"
CLIP_ROOT.mkdir(parents=True, exist_ok=True)
MAX_SOURCE_SECONDS = 30 * 60
MAX_SOURCE_BYTES = 500 * 1024 * 1024
JOBS = {}
JOBS_LOCK = threading.Lock()


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
        if parsed.path == "/watch" and parse_qs(parsed.query).get("v"):
            return "YouTube"
        if re.match(r"^/(shorts|live|embed)/[^/]+", parsed.path):
            return "YouTube"
    if host in TWITCH_HOSTS:
        path = parsed.path.strip("/")
        if host == "clips.twitch.tv":
            return "Twitch" if path else None
        if re.match(r"^(videos/\d+|[^/]+/clip/[^/]+)$", path):
            return "Twitch"
    return None


def ffmpeg_run(args, timeout=240):
    command = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y"] + list(args)
    return subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)


def get_download_options(job_dir):
    return {
        "format": "best[height<=720][ext=mp4]/best[height<=720]/best",
        "outtmpl": str(job_dir / "source.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 2,
        "fragment_retries": 2,
        "socket_timeout": 20,
        "max_filesize": MAX_SOURCE_BYTES,
        "ffmpeg_location": FFMPEG,
        "merge_output_format": "mp4",
        "overwrites": True,
    }


def audio_energy(source_path):
    result = ffmpeg_run([
        "-i", str(source_path), "-vn", "-ac", "1", "-ar", "8000",
        "-f", "s16le", "pipe:1"
    ], timeout=180)
    if result.returncode != 0 or not result.stdout:
        raise RuntimeError("We couldn't analyse the audio track in this video.")
    samples = array.array("h")
    samples.frombytes(result.stdout[:len(result.stdout) - (len(result.stdout) % 2)])
    energy = []
    for start in range(0, len(samples), 8000):
        chunk = samples[start:start + 8000]
        if not chunk:
            break
        square_mean = sum(sample * sample for sample in chunk) / len(chunk)
        energy.append(math.sqrt(square_mean))
    if len(energy) < 2:
        raise RuntimeError("This video doesn't contain enough audio to find candidate moments.")
    return energy


def choose_moments(energy, duration, clip_length, count):
    usable = min(int(duration), len(energy))
    length = min(clip_length, max(5, usable - 1))
    if usable <= length:
        return [0]
    stride = max(1, min(3, length // 8))
    candidates = []
    for start in range(0, usable - length + 1, stride):
        window = energy[start:start + length]
        if window:
            mean = sum(window) / len(window)
            peak = max(window)
            candidates.append((mean + peak * 0.12, start))
    candidates.sort(reverse=True)
    chosen = []
    for score, start in candidates:
        if all(abs(start - existing) >= max(8, int(length * 0.8)) for existing in chosen):
            chosen.append(start)
        if len(chosen) >= count:
            break
    return sorted(chosen or [0])


def format_time(seconds):
    seconds = max(0, int(seconds))
    if seconds < 3600:
        return f"{seconds // 60:02d}:{seconds % 60:02d}"
    return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"


def set_job(job_id, **changes):
    with JOBS_LOCK:
        if job_id in JOBS:
            JOBS[job_id].update(changes)


def process_clip_job(job_id, video_url, platform, count, clip_length):
    job_dir = CLIP_ROOT / job_id
    try:
        set_job(job_id, status="processing", message="Reading video details…")
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "noplaylist": True,
                               "socket_timeout": 20}) as ydl:
            info = ydl.extract_info(video_url, download=False)
        duration = int(info.get("duration") or 0)
        title = info.get("title") or "Your video"
        if duration <= 0:
            raise RuntimeError("We couldn't read this video's duration. Try a direct public video or VOD link.")
        if duration > MAX_SOURCE_SECONDS:
            raise RuntimeError("This free prototype supports videos up to 30 minutes. Try a shorter video or clip.")
        if duration < 10:
            raise RuntimeError("This video is too short to create useful clips.")

        set_job(job_id, message="Downloading the source video…", title=title)
        with yt_dlp.YoutubeDL(get_download_options(job_dir)) as ydl:
            ydl.download([video_url])
        source_candidates = [
            Path(path) for path in glob.glob(str(job_dir / "source.*"))
            if Path(path).suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}
            and not path.endswith((".part", ".ytdl"))
        ]
        if not source_candidates:
            raise RuntimeError("The source video could not be downloaded. It may be private, restricted, or unavailable.")
        source_path = max(source_candidates, key=lambda p: p.stat().st_size)
        if source_path.stat().st_size > MAX_SOURCE_BYTES:
            raise RuntimeError("This source is too large for the free prototype (500 MB maximum).")

        set_job(job_id, message="Analysing audio and finding high-energy moments…")
        energy = audio_energy(source_path)
        starts = choose_moments(energy, duration, clip_length, count)
        actual_length = min(clip_length, max(5, duration - 1))
        clips = []
        for index, start in enumerate(starts, start=1):
            set_job(job_id, message=f"Rendering clip {index} of {len(starts)}…")
            filename = f"clip-{index:02d}.mp4"
            output_path = job_dir / filename
            result = ffmpeg_run([
                "-ss", str(start), "-i", str(source_path), "-t", str(actual_length),
                "-map", "0:v:0", "-map", "0:a:0?",
                "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "25",
                "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
                str(output_path)
            ], timeout=240)
            if result.returncode != 0 or not output_path.exists() or output_path.stat().st_size == 0:
                details = result.stderr.decode("utf-8", "ignore")[-500:]
                raise RuntimeError("Clip rendering failed. " + (details or "Please try a different video."))
            clips.append({
                "name": filename, "url": f"/clips/{job_id}/{filename}",
                "preview_url": f"/preview/{job_id}/{filename}",
                "start_seconds": start, "start": format_time(start),
                "end": format_time(min(duration, start + actual_length)),
                "duration": actual_length,
                "size_mb": round(output_path.stat().st_size / (1024 * 1024), 1),
            })
        set_job(job_id, status="done", message=f"Created {len(clips)} clip(s). Moments were ranked by audio energy; captions and semantic AI selection are not enabled yet.", clips=clips, title=title, platform=platform)
    except yt_dlp.utils.DownloadError as exc:
        message = str(exc)
        if "Sign in" in message or "login" in message.lower() or "private" in message.lower():
            friendly = "This video appears to require sign-in or is private. Try a public video or VOD."
        else:
            friendly = "Couldn't access that video from the free server. It may be restricted or the platform may have changed its delivery. Try another public link."
        set_job(job_id, status="error", error=friendly, message=friendly)
    except subprocess.TimeoutExpired:
        friendly = "Processing took too long on the free server. Try a shorter video or fewer clips."
        set_job(job_id, status="error", error=friendly, message=friendly)
    except RuntimeError as exc:
        set_job(job_id, status="error", error=str(exc), message=str(exc))
    except Exception:
        app.logger.exception("Clip creation failed")
        friendly = "Something went wrong while creating clips. Try a different public video."
        set_job(job_id, status="error", error=friendly, message=friendly)
    finally:
        try:
            for path in job_dir.glob("source.*"):
                if path.is_file():
                    path.unlink()
        except OSError:
            pass


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
        return jsonify(ok=False, error="Enter a valid YouTube video/Short or Twitch clip/VOD URL."), 400
    return jsonify(ok=True, platform=platform, url=video_url.strip(),
                   message="Link looks valid. Choose your clip settings and create clips.")


@app.post("/api/create-clips")
def create_clips():
    payload = request.get_json(silent=True) or {}
    video_url = (payload.get("url") or "").strip()
    platform = classify_video_url(video_url)
    if not platform:
        return jsonify(ok=False, error="Enter a valid public YouTube or Twitch video URL."), 400
    try:
        count = max(1, min(int(payload.get("count", 3)), 5))
        clip_length = max(10, min(int(payload.get("clip_length", 30)), 60))
    except (TypeError, ValueError):
        return jsonify(ok=False, error="Clip count and length must be numbers."), 400

    with JOBS_LOCK:
        active = any(job.get("status") == "processing" for job in JOBS.values())
        if active:
            return jsonify(ok=False, error="A clip job is already running on this free instance. Wait for it to finish, then try again."), 429
        job_id = secrets.token_urlsafe(10).replace("-", "").replace("_", "")
        JOBS[job_id] = {"status": "processing", "message": "Starting clip job…", "clips": []}
    (CLIP_ROOT / job_id).mkdir(parents=True, exist_ok=False)
    worker = threading.Thread(target=process_clip_job, args=(job_id, video_url, platform, count, clip_length), daemon=True)
    worker.start()
    return jsonify(ok=True, job_id=job_id, status="processing", message="Clip job started."), 202


@app.get("/api/jobs/<job_id>")
def get_job(job_id):
    if not re.fullmatch(r"[A-Za-z0-9]{8,32}", job_id):
        return jsonify(ok=False, error="Invalid job ID."), 404
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return jsonify(ok=False, error="This job is no longer available. Start a new clip job."), 404
        return jsonify(ok=True, job_id=job_id, **job)


@app.get("/clips/<job_id>/<path:filename>")
def download_clip(job_id, filename):
    if not re.fullmatch(r"[A-Za-z0-9]{8,32}", job_id) or not re.fullmatch(r"clip-\d{2}\.mp4", filename):
        return jsonify(ok=False, error="Invalid clip link."), 404
    directory = CLIP_ROOT / job_id
    if not (directory / filename).is_file():
        return jsonify(ok=False, error="This clip is no longer available. Create it again to download."), 404
    return send_from_directory(directory, filename, as_attachment=True, download_name=filename)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))


@app.get("/preview/<job_id>/<path:filename>")
def preview_clip(job_id, filename):
    if not re.fullmatch(r"[A-Za-z0-9]{8,32}", job_id) or not re.fullmatch(r"clip-\d{2}\.mp4", filename):
        return jsonify(ok=False, error="Invalid clip link."), 404
    directory = CLIP_ROOT / job_id
    if not (directory / filename).is_file():
        return jsonify(ok=False, error="This clip is no longer available. Create it again to preview."), 404
    return send_from_directory(directory, filename, as_attachment=False, mimetype="video/mp4")
