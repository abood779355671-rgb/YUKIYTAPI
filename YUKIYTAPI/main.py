import os
import time
import uuid
import asyncio
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
import yt_dlp

from YUKIYTAPI.database.stats import init_db, add_download, get_stats

app = FastAPI(title="YUKI YT API")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "YUKIYTAPI", "saved")
COOKIES_FILE = os.path.join(BASE_DIR, "cookies.txt") # <-- Tera cookies.txt ka path
os.makedirs(CACHE_DIR, exist_ok=True)

init_db()

TOKENS = {}
START_TIME = time.time()

@app.get("/")
async def home(request: Request):
    uptime = round(time.time() - START_TIME, 2)
    return JSONResponse({
        "status": "Running...",
        "owner": "YUKIMUSIC",
        "uptime": f"{uptime}s",
        "message": "Welcome to YUKI API"
    })

@app.get("/stats")
async def api_stats(request: Request):
    total_dl, cache_mb = get_stats()
    return JSONResponse({
        "status": "success",
        "total_song_downloads": total_dl,
        "total_cache_size_mb": cache_mb,
        "active_tokens": len(TOKENS)
    })

@app.get("/download")
async def generate_token(request: Request, url: str, type: str = "audio"):
    video_id = url.split('v=')[-1].split('&')[0] if 'v=' in url else url
    
    random_str = str(uuid.uuid4().hex)[:16]
    yuki_token = f"YUKIMusic{random_str}YukiBots"
    
    TOKENS[yuki_token] = {
        "video_id": video_id,
        "type": type,
        "expires": time.time() + 60
    }
    
    return JSONResponse({
        "status": "success",
        "video_id": video_id,
        "download_token": yuki_token,
        "usage": "Use token parameter in /stream endpoint"
    })

@app.get("/stream/{video_id}")
async def stream_music(request: Request, video_id: str, type: str = "audio", token: str = None):
    if not token or token not in TOKENS:
        raise HTTPException(status_code=401, detail="Invalid Token Access Denied")
        
    token_data = TOKENS[token]
    if time.time() > token_data["expires"] or token_data["video_id"] != video_id:
        raise HTTPException(status_code=401, detail="Token Expired")
        
    del TOKENS[token]

    ext = "mp3" if type == "audio" else "mp4"
    file_path = os.path.join(CACHE_DIR, f"{video_id}.{ext}")

    if not os.path.exists(file_path):
        ydl_opts = {
            'format': 'bestaudio/best' if type == "audio" else 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': file_path,
            'quiet': True,
            # 🔥 YT-DLP SYNTAX FIX: Changed list to dictionary format below
            'js_runtimes': {'node': {}},
            'cookiefile': COOKIES_FILE # <-- Cookies file yahan load ho rahi hai
        }
        if type == "audio":
            ydl_opts.update({
                'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]
            })
            
        try:
            await asyncio.to_thread(lambda: yt_dlp.YoutubeDL(ydl_opts).download([video_id]))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    add_download()
    return FileResponse(file_path, media_type="audio/mpeg" if type == "audio" else "video/mp4")
    
