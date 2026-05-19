"""
========================================================================
  ʏᴜᴋɪ ʏᴛ ᴀᴘɪ - ᴀᴅᴠᴀɴᴄᴇᴅ ᴍᴇᴅɪᴀ ꜱᴛʀᴇᴀᴍɪɴɢ ᴇɴɢɪɴᴇ
========================================================================
  © 2026 ᴋᴀɪᴛᴏ | ʜᴇʟʟꜰɪʀᴇᴅᴇᴠꜱ. ᴀʟʟ ʀɪɢʜᴛꜱ ʀᴇꜱᴇʀᴠᴇᴅ.
  
  ᴡᴀʀɴɪɴɢ: ᴅᴏ ɴᴏᴛ ᴇᴅɪᴛ, ᴍᴏᴅɪꜰʏ, ᴏʀ ʀᴇᴍᴏᴠᴇ ᴛʜɪꜱ ʜᴇᴀᴅᴇʀ.
  ᴛʜɪꜱ ᴄᴏᴅᴇʙᴀꜱᴇ ɪꜱ ᴘʀᴏᴛᴇᴄᴛᴇᴅ ʙʏ ᴀɴ ᴀᴄᴛɪᴠᴇ ᴀɴᴛɪ-ᴛᴀᴍᴘᴇʀ ᴍᴇᴄʜᴀɴɪꜱᴍ. 
  ʀᴇᴍᴏᴠɪɴɢ ᴛʜɪꜱ ᴄᴏᴘʏʀɪɢʜᴛ ɴᴏᴛɪᴄᴇ ᴡɪʟʟ ᴛʀɪɢɢᴇʀ ᴀ ꜱʏꜱᴛᴇᴍ-ʟᴇᴠᴇʟ 
  ꜰᴀᴛᴀʟ ᴇʀʀᴏʀ ᴀɴᴅ ᴘᴇʀᴍᴀɴᴇɴᴛʟʏ ᴘʀᴇᴠᴇɴᴛ ᴛʜᴇ ᴀᴘɪ ꜰʀᴏᴍ ʀᴜɴɴɪɴɢ.
========================================================================
"""

import sys

if __doc__ is None or "© 2026 ᴋᴀɪᴛᴏ | ʜᴇʟʟꜰɪʀᴇᴅᴇᴠꜱ. ᴀʟʟ ʀɪɢʜᴛꜱ ʀᴇꜱᴇʀᴠᴇᴅ." not in __doc__:
    print("\n[!] ꜰᴀᴛᴀʟ ᴇʀʀᴏʀ: ᴄᴏᴘʏʀɪɢʜᴛ ᴛᴀᴍᴘᴇʀɪɴɢ ᴅᴇᴛᴇᴄᴛᴇᴅ.")
    print("[!] ᴛʜᴇ ʜᴇʟʟꜰɪʀᴇᴅᴇᴠꜱ ᴄᴏᴘʏʀɪɢʜᴛ ʜᴇᴀᴅᴇʀ ʜᴀꜱ ʙᴇᴇɴ ᴍᴏᴅɪꜰɪᴇᴅ ᴏʀ ʀᴇᴍᴏᴠᴇᴅ.")
    print("[!] ᴀᴘɪ ᴇxᴇᴄᴜᴛɪᴏɴ ʙʟᴏᴄᴋᴇᴅ. ꜱʏꜱᴛᴇᴍ ᴇxɪᴛɪɴɢ...\n")
    sys.exit(1)

import os
import re
import time
import uuid
import shutil
import asyncio
from fastapi import FastAPI, BackgroundTasks, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from YUKIYTAPI.database.stats import init_db, add_download, get_stats

app = FastAPI(title="YUKI YT API")

BASE_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR    = os.path.join(BASE_DIR, "YUKIYTAPI", "saved")
COOKIES_FILE = os.path.join(BASE_DIR, "cookies.txt")
os.makedirs(CACHE_DIR, exist_ok=True)

init_db()

TOKENS     = {}
START_TIME = time.time()

# ─────────────────────────────────────────
# DETECT NODE.JS AVAILABILITY
# ─────────────────────────────────────────
NODE_AVAILABLE = shutil.which("node") is not None


# ─────────────────────────────────────────
# URL / VIDEO ID PARSER  ← BUG FIXED HERE
# Handles: full URLs, short URLs, shorts, raw IDs
# ─────────────────────────────────────────
def extract_video_id(url_or_id: str) -> str:
    url_or_id = url_or_id.strip()

    # youtu.be/VIDEO_ID
    m = re.search(r'youtu\.be/([a-zA-Z0-9_-]{11})', url_or_id)
    if m:
        return m.group(1)

    # youtube.com/watch?v=VIDEO_ID
    m = re.search(r'[?&]v=([a-zA-Z0-9_-]{11})', url_or_id)
    if m:
        return m.group(1)

    # youtube.com/shorts/VIDEO_ID
    m = re.search(r'/shorts/([a-zA-Z0-9_-]{11})', url_or_id)
    if m:
        return m.group(1)

    # youtube.com/embed/VIDEO_ID
    m = re.search(r'/embed/([a-zA-Z0-9_-]{11})', url_or_id)
    if m:
        return m.group(1)

    # Raw 11-char video ID
    if re.match(r'^[a-zA-Z0-9_-]{11}$', url_or_id):
        return url_or_id

    # Fallback — return as-is and let yt-dlp handle it
    return url_or_id


# ─────────────────────────────────────────
# BUILD YT-DLP COMMAND  ← NODE FIX HERE
# Tries multiple player clients so it works
# even without Node.js installed
# ─────────────────────────────────────────
def build_ytdlp_cmd(video_id: str, outtmpl: str, media_type: str) -> list:
    cookies_args = ["--cookies", COOKIES_FILE] if os.path.exists(COOKIES_FILE) else []

    # Player clients to try — no Node.js needed for these
    # tv_embedded + mweb = most reliable in restricted envs
    player_clients = "tv_embedded,web,mweb,android"

    base = [
        "yt-dlp",
        *cookies_args,
        "--extractor-args", f"youtube:player_client={player_clients}",
        "--no-check-certificates",
        "--no-playlist",
        "-o", outtmpl,
        "--quiet",
        "--no-warnings",
    ]

    # Add node args only if node is available
    if NODE_AVAILABLE:
        base += ["--js-runtimes", "node"]

    if media_type == "audio":
        base += [
            "-f", "bestaudio/best",
        ]
    else:
        base += [
            "-f", "bestaudio/best",
        ]

    base.append(video_id)
    return base


# ─────────────────────────────────────────
# BACKGROUND: temp → cache (after response)
# ─────────────────────────────────────────
def _move_to_cache(tmp_path: str, cache_path: str) -> None:
    try:
        if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
            os.replace(tmp_path, cache_path)
    except Exception:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


# ─────────────────────────────────────────
# HOME
# ─────────────────────────────────────────
@app.get("/")
async def home(request: Request):
    uptime = round(time.time() - START_TIME, 2)
    return JSONResponse({
        "status":       "Running ✅",
        "owner":        "YUKIMUSIC",
        "uptime":       f"{uptime}s",
        "node_js":      "available ✅" if NODE_AVAILABLE else "not found ⚠️ (using fallback clients)",
        "cookies":      "loaded ✅" if os.path.exists(COOKIES_FILE) else "missing ⚠️",
        "message":      "Welcome to YUKI API",
    })


# ─────────────────────────────────────────
# STATS
# ─────────────────────────────────────────
@app.get("/stats")
async def api_stats():
    total_dl, cache_mb = get_stats()
    return JSONResponse({
        "status":               "success",
        "total_song_downloads": total_dl,
        "total_cache_size_mb":  cache_mb,
        "active_tokens":        len(TOKENS),
        "node_available":       NODE_AVAILABLE,
    })


# ─────────────────────────────────────────
# TOKEN GENERATE  ← URL PARSING FIXED
# ─────────────────────────────────────────
@app.get("/download")
async def generate_token(request: Request, url: str, type: str = "audio"):
    if type not in ("audio", "video"):
        raise HTTPException(status_code=400, detail="type must be 'audio' or 'video'")

    video_id   = extract_video_id(url)   # ← FIXED: handles raw IDs + all URL formats
    yuki_token = f"YUKIMusic{uuid.uuid4().hex[:16]}YukiBots"

    TOKENS[yuki_token] = {
        "video_id": video_id,
        "type":     type,
        "expires":  time.time() + 120,   # 2 min window (was 60s — too tight)
    }

    return JSONResponse({
        "status":         "success",
        "video_id":       video_id,
        "download_token": yuki_token,
        "expires_in":     "120 seconds",
        "usage":          f"/stream/{video_id}?token=<token>&type={type}",
    })


# ─────────────────────────────────────────
# STREAM  (download → serve → cache in bg)
# ─────────────────────────────────────────
@app.get("/stream/{video_id}")
async def stream_music(
    request:          Request,
    video_id:         str,
    background_tasks: BackgroundTasks,
    type:             str = "audio",
    token:            str = None,
    x_download_token: str = Header(None),
):
    # ── Auth ──────────────────────────────────────────────────────────────────
    actual_token = token or x_download_token
    if not actual_token or actual_token not in TOKENS:
        raise HTTPException(status_code=401, detail="Invalid or missing token")

    token_data = TOKENS[actual_token]

    if time.time() > token_data["expires"]:
        TOKENS.pop(actual_token, None)
        raise HTTPException(status_code=401, detail="Token expired — request a new one from /download")

    if token_data["video_id"] != video_id:
        raise HTTPException(status_code=401, detail="Token video_id mismatch")

    del TOKENS[actual_token]

    # ── Cache hit → serve instantly ───────────────────────────────────────────
    ext        = "m4a" if type == "audio" else "mp4"
    cache_path = os.path.join(CACHE_DIR, f"{video_id}.{ext}")

    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
        add_download()
        return FileResponse(
            cache_path,
            media_type="audio/mp4" if type == "audio" else "video/mp4",
            filename=f"{video_id}.{ext}",
        )

    # ── Also check for opus cache (audio may have downloaded as opus) ─────────
    if type == "audio":
        opus_cache = os.path.join(CACHE_DIR, f"{video_id}.opus")
        if os.path.exists(opus_cache) and os.path.getsize(opus_cache) > 0:
            add_download()
            return FileResponse(opus_cache, media_type="audio/ogg", filename=f"{video_id}.opus")

    # ── Cache miss → yt-dlp download ──────────────────────────────────────────
    outtmpl = os.path.join(CACHE_DIR, f"{video_id}.tmp.%(ext)s")
    cmd     = build_ytdlp_cmd(video_id, outtmpl, type)

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()

        if process.returncode != 0:
            err_msg = stderr.decode(errors="replace")[:500]
            raise HTTPException(
                status_code=500,
                detail=f"yt-dlp failed: {err_msg}",
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")

    # ── Find downloaded file ───────────────────────────────────────────────────
    actual_tmp = None
    for fname in os.listdir(CACHE_DIR):
        if fname.startswith(f"{video_id}.tmp.") and not fname.endswith(".tmp"):
            actual_tmp = os.path.join(CACHE_DIR, fname)
            break

    if not actual_tmp or not os.path.exists(actual_tmp):
        raise HTTPException(status_code=500, detail="Download failed — output file not found")

    if os.path.getsize(actual_tmp) == 0:
        os.remove(actual_tmp)
        raise HTTPException(status_code=500, detail="Download failed — empty file")

    actual_ext  = actual_tmp.rsplit(".", 1)[-1]
    final_cache = os.path.join(CACHE_DIR, f"{video_id}.{actual_ext}")

    add_download()

    background_tasks.add_task(_move_to_cache, actual_tmp, final_cache)

    media_type = "audio/mp4" if type == "audio" else "video/mp4"
    if actual_ext == "opus":
        media_type = "audio/ogg"
    elif actual_ext == "webm":
        media_type = "video/webm"

    return FileResponse(
        actual_tmp,
        media_type=media_type,
        filename=f"{video_id}.{actual_ext}",
    )


# ─────────────────────────────────────────
# CACHE CLEAR (admin use)
# ─────────────────────────────────────────
@app.delete("/cache/{video_id}")
async def clear_cache(video_id: str):
    deleted = []
    for fname in os.listdir(CACHE_DIR):
        if fname.startswith(video_id):
            os.remove(os.path.join(CACHE_DIR, fname))
            deleted.append(fname)
    if not deleted:
        raise HTTPException(status_code=404, detail="No cache found for this video_id")
    return JSONResponse({"status": "deleted", "files": deleted})
  
