import os
import shutil
from pathlib import Path

def file_organizer(parameters: dict, player=None) -> str:
    target_dir = parameters.get("directory", str(Path.home() / "Downloads"))
    target_path = Path(target_dir)
    
    if not target_path.exists() or not target_path.is_dir():
        return f"Directory does not exist: {target_dir}"
        
    CATEGORIES = {
        "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp"],
        "Documents": [".pdf", ".doc", ".docx", ".txt", ".xlsx", ".csv", ".pptx", ".md"],
        "Audio": [".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg"],
        "Video": [".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv"],
        "Archives": [".zip", ".rar", ".7z", ".tar", ".gz"],
        "Installers": [".exe", ".msi", ".apk"],
        "Code": [".py", ".js", ".html", ".css", ".json", ".cpp", ".java", ".go"]
    }
    
    moved_count = 0
    results = []
    
    for item in target_path.iterdir():
        if item.is_file():
            ext = item.suffix.lower()
            placed = False
            for category, exts in CATEGORIES.items():
                if ext in exts:
                    dest_dir = target_path / category
                    dest_dir.mkdir(exist_ok=True)
                    
                    try:
                        dest_file = dest_dir / item.name
                        counter = 1
                        while dest_file.exists():
                            dest_file = dest_dir / f"{item.stem}_{counter}{item.suffix}"
                            counter += 1
                            
                        shutil.move(str(item), str(dest_file))
                        moved_count += 1
                        placed = True
                        break
                    except Exception as e:
                        results.append(f"Failed to move {item.name}: {e}")
            
            if not placed and parameters.get("move_others", False):
                dest_dir = target_path / "Others"
                dest_dir.mkdir(exist_ok=True)
                try:
                    dest_file = dest_dir / item.name
                    counter = 1
                    while dest_file.exists():
                        dest_file = dest_dir / f"{item.stem}_{counter}{item.suffix}"
                        counter += 1
                    shutil.move(str(item), str(dest_file))
                    moved_count += 1
                except:
                    pass
                    
    if player:
        player.write_log(f"📂 Organized {moved_count} files in {target_dir}")
        
    msg = f"Successfully organized {moved_count} files into subfolders in {target_dir}."
    if results:
        msg += f"\nErrors: {len(results)}"
    return msg
