import yt_dlp
import os
import imageio_ffmpeg

def download_media(url: str, out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()

    ydl_opts = {
        "outtmpl": f"{out_dir}/%(id)s.%(ext)s",
        "format": "best[filesize<50M]/best",
        "quiet": True,
        "noplaylist": True,
        "ffmpeg_location": ffmpeg_path,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filepath = ydl.prepare_filename(info)
        return filepath
