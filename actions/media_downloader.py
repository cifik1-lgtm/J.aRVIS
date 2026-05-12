import os
from pathlib import Path

try:
    import yt_dlp
    HAS_YTDLP = True
except ImportError:
    HAS_YTDLP = False

def media_downloader(parameters: dict, player=None) -> str:
    if not HAS_YTDLP:
        return "yt-dlp is not installed. Run: python -m pip install yt-dlp"
        
    url = parameters.get("url", "")
    format_type = parameters.get("format", "video") # video or audio
    save_path = parameters.get("save_path", "")
    
    if not url:
        return "No URL provided."
        
    if not save_path:
        save_path = str(Path.home() / "Downloads" / "JarvisMedia")
        
    Path(save_path).mkdir(parents=True, exist_ok=True)
    
    ydl_opts = {
        'outtmpl': os.path.join(save_path, '%(title)s.%(ext)s'),
        'quiet': False,
        'no_warnings': True
    }
    
    try:
        import imageio_ffmpeg
        ydl_opts['ffmpeg_location'] = imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        pass
    
    if format_type == "audio":
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
    else:
        ydl_opts.update({
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4'
        })
        
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return f"Successfully downloaded {format_type} to: {save_path}"
    except Exception as e:
        return f"Download failed: {str(e)}"
