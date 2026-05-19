"""
========================================================================
  ʏᴜᴋɪ ʏᴛ ᴀᴘɪ - ᴀᴅᴠᴀɴᴄᴇᴅ ᴍᴇᴅɪᴀ ꜱᴛʀᴇᴀᴍɪɴɢ ᴇɴɢɪɴᴇ
========================================================================
"""

import os
import re
import time
import uuid
import shutil
import asyncio
import glob

from fastapi import FastAPI, BackgroundTasks, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI(title="YUKI YT API")

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Auto-detect project root
# Works in:
# /app/main.py
# /app/YUKIYTAPI/main.py
# Docker / Coolify / local setups

if os.path.basename(BASE_DIR).lower() == "yukiytapi":
    PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
else:
    PROJECT_ROOT = BASE_DIR

# Cache directory
CACHE_DIR = os.path.join(PROJECT_ROOT, "saved")

# Cookies file
COOKIES_FILE = os.path.join(PROJECT_ROOT, "cookies.txt")

# Create cache dir if missing
os.makedirs(CACHE_DIR, exist_ok=True)

# Runtime storage
TOKENS = {}
START_TIME = time.time()

# Detect Node.js
NODE_AVAILABLE = shutil.which("node") is not None

# Debug logs
print(f"[YUKI] BASE_DIR      => {BASE_DIR}")
print(f"[YUKI] PROJECT_ROOT  => {PROJECT_ROOT}")
print(f"[YUKI] CACHE_DIR     => {CACHE_DIR}")
print(f"[YUKI] COOKIES_FILE  => {COOKIES_FILE}")
print(f"[YUKI] Cookies Found => {os.path.exists(COOKIES_FILE)}")
print(f"[YUKI] Node.js       => {NODE_AVAILABLE}")

def extract_video_id(url_or_id: str) -> str:
    url_or_id = url_or_id.strip()

    patterns = [
        r"youtu\.be\/([a-zA-Z0-9_-]{11})",
        r"[?&]v=([a-zA-Z0-9_-]{11})",
        r"\/shorts\/([a-zA-Z0-9_-]{11})",
        r"\/embed\/([a-zA-Z0-9_-]{11})",
    ]

    for pattern in patterns:
        m = re.search(pattern, url_or_id)
        if m:
            return m.group(1)

    if re.match(r"^[a-zA-Z0-9_-]{11}$", url_or_id):
        return url_or_id

    raise HTTPException(status_code=400, detail="Invalid YouTube URL or Video ID")


# ─────────────────────────────────────────
# BUILD YT-DLP COMMAND
# ─────────────────────────────────────────

def build_ytdlp_cmd(video_id: str, outtmpl: str, media_type: str):

    cookies_args = (
        ["--cookies", COOKIES_FILE]
        if os.path.exists(COOKIES_FILE)
        else []
    )

    player_clients = "android,mweb,tv_embedded,web"

    cmd = [
        "yt-dlp",

        *cookies_args,

        "--extractor-args",
        f"youtube:player_client={player_clients}",

        "--no-playlist",
        "--no-warnings",
        "--quiet",

        "-o",
        outtmpl,
    ]

    if NODE_AVAILABLE:
        cmd += ["--js-runtimes", "node"]

    if media_type == "audio":

        cmd += [
            "-f",
            "bestaudio/best",

            "--extract-audio",
            "--audio-format",
            "mp3",

            "--audio-quality",
            "0",
        ]

    else:

        cmd += [
            "-f",
            "bestvideo+bestaudio/best",
            "--merge-output-format",
            "mp4",
        ]

    cmd.append(f"https://youtu.be/{video_id}")

    return cmd


# ─────────────────────────────────────────
# MOVE TO CACHE
# ─────────────────────────────────────────

def move_to_cache(tmp_file, final_file):
    try:
        if os.path.exists(tmp_file):
            os.replace(tmp_file, final_file)
    except Exception:
        pass


# ─────────────────────────────────────────
# HOME
# ─────────────────────────────────────────

@app.get("/")
async def home():

    uptime = round(time.time() - START_TIME, 2)

    return {
        "status": "running",
        "uptime": uptime,
        "node": NODE_AVAILABLE,
        "cookies": os.path.exists(COOKIES_FILE),
    }


# ─────────────────────────────────────────
# DOWNLOAD TOKEN
# ─────────────────────────────────────────

@app.get("/download")
async def generate_token(
    request: Request,
    url: str,
    type: str = "audio"
):

    if type not in ["audio", "video"]:
        raise HTTPException(status_code=400, detail="Invalid type")

    video_id = extract_video_id(url)

    token = f"YUKI{uuid.uuid4().hex[:16]}"

    TOKENS[token] = {
        "video_id": video_id,
        "type": type,
        "expires": time.time() + 300,
    }

    return {
        "status": "success",
        "video_id": video_id,
        "token": token,
        "expires_in": "300s",
        "stream": f"/stream/{video_id}?token={token}&type={type}"
    }


# ─────────────────────────────────────────
# STREAM
# ─────────────────────────────────────────

@app.get("/stream/{video_id}")
async def stream_media(
    video_id: str,
    background_tasks: BackgroundTasks,
    type: str = "audio",
    token: str = None,
    x_download_token: str = Header(None),
):

    actual_token = token or x_download_token

    if not actual_token:
        raise HTTPException(status_code=401, detail="Token missing")

    if actual_token not in TOKENS:
        raise HTTPException(status_code=401, detail="Invalid token")

    token_data = TOKENS[actual_token]

    if time.time() > token_data["expires"]:
        TOKENS.pop(actual_token, None)
        raise HTTPException(status_code=401, detail="Token expired")

    if token_data["video_id"] != video_id:
        raise HTTPException(status_code=401, detail="Video mismatch")

    del TOKENS[actual_token]

    # ─────────────────────────────
    # CACHE CHECK
    # ─────────────────────────────

    ext = "mp3" if type == "audio" else "mp4"

    cache_file = os.path.join(CACHE_DIR, f"{video_id}.{ext}")

    if os.path.exists(cache_file):

        media_type = (
            "audio/mpeg"
            if type == "audio"
            else "video/mp4"
        )

        return FileResponse(
            cache_file,
            media_type=media_type,
            filename=f"{video_id}.{ext}"
        )

    # ─────────────────────────────
    # DOWNLOAD
    # ─────────────────────────────

    outtmpl = os.path.join(
        CACHE_DIR,
        f"{video_id}.tmp.%(ext)s"
    )

    cmd = build_ytdlp_cmd(video_id, outtmpl, type)

    try:

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:

            err = stderr.decode(errors="replace")

            raise HTTPException(
                status_code=500,
                detail=f"yt-dlp failed: {err[:500]}"
            )

    except HTTPException:
        raise

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    # ─────────────────────────────
    # FIND OUTPUT FILE
    # ─────────────────────────────

    matches = glob.glob(
        os.path.join(
            CACHE_DIR,
            f"{video_id}.tmp.*"
        )
    )

    if not matches:
        raise HTTPException(
            status_code=500,
            detail="Output file not found"
        )

    actual_file = matches[0]

    if os.path.getsize(actual_file) == 0:
        os.remove(actual_file)

        raise HTTPException(
            status_code=500,
            detail="Downloaded file empty"
        )

    actual_ext = actual_file.rsplit(".", 1)[-1]

    final_cache = os.path.join(
        CACHE_DIR,
        f"{video_id}.{actual_ext}"
    )

    background_tasks.add_task(
        move_to_cache,
        actual_file,
        final_cache
    )

    media_type = (
        "audio/mpeg"
        if type == "audio"
        else "video/mp4"
    )

    return FileResponse(
        actual_file,
        media_type=media_type,
        filename=f"{video_id}.{actual_ext}"
    )


# ─────────────────────────────────────────
# CLEAR CACHE
# ─────────────────────────────────────────

@app.delete("/cache/{video_id}")
async def clear_cache(video_id: str):

    deleted = []

    for file in os.listdir(CACHE_DIR):

        if file.startswith(video_id):

            os.remove(os.path.join(CACHE_DIR, file))
            deleted.append(file)

    return {
        "deleted": deleted
    }


# ─────────────────────────────────────────
# START
# ─────────────────────────────────────────

# uvicorn main:app --host 0.0.0.0 --port 8000
