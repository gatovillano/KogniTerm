def run(source_dir, dest_dir, copy=True, extensions=None):
    from pathlib import Path
    import shutil
    from datetime import datetime
    
    if extensions is None:
        extensions = [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"]
    
    source_dir = Path(source_dir).expanduser()
    dest_dir = Path(dest_dir).expanduser()
    
    if not source_dir.exists():
        return f"Error: directorio fuente no existe: {source_dir}"
    
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    moved_count = 0
    for ext in extensions:
        for img_path in source_dir.rglob(f"*{ext}"):
            if img_path.is_file():
                mtime = datetime.fromtimestamp(img_path.stat().st_mtime)
                year_folder = mtime.strftime("%Y")
                month_folder = mtime.strftime("%m")
                day_folder = mtime.strftime("%d")
                
                target_subdir = dest_dir / year_folder / month_folder / day_folder
                target_subdir.mkdir(parents=True, exist_ok=True)
                
                target_path = target_subdir / img_path.name
                
                if copy:
                    shutil.copy2(img_path, target_path)
                else:
                    shutil.move(str(img_path), str(target_path))
                
                moved_count += 1
    
    return f"Organizacion completada: {moved_count} archivos procesados."

def main():
    import sys
    source = sys.argv[1] if len(sys.argv) > 1 else "/home/gato/Pictures"
    dest = sys.argv[2] if len(sys.argv) > 2 else "/tmp/photo_native"
    copy = sys.argv[3].lower() == "true" if len(sys.argv) > 3 else True
    print(run(source, dest, copy))

if __name__ == "__main__":
    main()