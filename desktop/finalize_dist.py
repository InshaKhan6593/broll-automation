import shutil
import os
from pathlib import Path

def finalize_dist():
    print("🧹 Finalizing Distribution Folder...")
    desktop_dir = Path("c:/Users/Insha Khan/jodel-processor-v2/desktop")
    dist_path = desktop_dir / "dist"
    test_dist = desktop_dir / "dist_test"
    
    if dist_path.exists():
        print(f"Removing old dist: {dist_path}")
        shutil.rmtree(dist_path)
    
    if test_dist.exists():
        print(f"Renaming {test_dist} to {dist_path}...")
        test_dist.rename(dist_path)
        print("✅ Finalization complete.")
    else:
        print("❌ Error: dist_test not found!")

if __name__ == "__main__":
    finalize_dist()
