#!/usr/bin/env python3
import os
import sys
from PIL import Image

def generate_icons(source_path, target_dir):
    os.makedirs(target_dir, exist_ok=True)
    img = Image.open(source_path).convert("RGBA")
    
    # Save master_icon.png
    master_path = os.path.join(target_dir, "master_icon.png")
    img.save(master_path, "PNG")
    print(f"✔ Created {master_path}")
    
    # List of PNG sizes to generate: (filename, size)
    png_sizes = [
        ("32x32.png", (32, 32)),
        ("128x128.png", (128, 128)),
        ("128x128@2x.png", (256, 256)),
        ("icon.png", (512, 512)),
        ("Square30x30Logo.png", (30, 30)),
        ("Square44x44Logo.png", (44, 44)),
        ("Square71x71Logo.png", (71, 71)),
        ("Square89x89Logo.png", (89, 89)),
        ("Square107x107Logo.png", (107, 107)),
        ("Square142x142Logo.png", (142, 142)),
        ("Square150x150Logo.png", (150, 150)),
        ("Square284x284Logo.png", (284, 284)),
        ("Square310x310Logo.png", (310, 310)),
        ("StoreLogo.png", (50, 50)),
    ]
    
    for filename, (w, h) in png_sizes:
        resized = img.resize((w, h), Image.Resampling.LANCZOS)
        out_path = os.path.join(target_dir, filename)
        resized.save(out_path, "PNG")
        print(f"✔ Created {out_path} ({w}x{h})")
        
    # Generate icon.ico
    ico_path = os.path.join(target_dir, "icon.ico")
    ico_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(ico_path, format="ICO", sizes=ico_sizes)
    print(f"✔ Created {ico_path} (ICO)")
    
    # Generate icon.icns (if supported by Pillow)
    icns_path = os.path.join(target_dir, "icon.icns")
    try:
        icns_sizes = [(16, 16), (32, 32), (64, 64), (128, 128), (256, 256), (512, 512), (1024, 1024)]
        img.save(icns_path, format="ICNS", sizes=icns_sizes)
        print(f"✔ Created {icns_path} (ICNS)")
    except Exception as e:
        print(f"⚠ Pillow ICNS save warning: {e}. Trying fallback copy or fallback generation...")
        # Fallback if ICNS format lacks sizes:
        try:
            img.save(icns_path, format="ICNS")
            print(f"✔ Created {icns_path} (ICNS fallback)")
        except Exception as e2:
            print(f"❌ Failed to save ICNS: {e2}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: generate_tauri_icons.py <source_image> <target_icons_dir>")
        sys.exit(1)
    generate_icons(sys.argv[1], sys.argv[2])
