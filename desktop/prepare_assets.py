import os
import shutil
from pathlib import Path

def prepare_assets():
    print("🧹 Preparing Desktop Assets...")
    
    project_root = Path(__file__).parent.parent
    desktop_dir = project_root / "desktop"
    
    # 1. Prepare Renderer (Frontend)
    frontend_dist = project_root / "frontend" / "dist"
    target_renderer = desktop_dir / "renderer"
    
    if target_renderer.exists():
        shutil.rmtree(target_renderer)
    
    if frontend_dist.exists():
        print(f"Copying frontend from {frontend_dist}...")
        shutil.copytree(frontend_dist, target_renderer)
    else:
        print("❌ Error: frontend/dist not found! Run 'npm run build' in frontend folder first.")
        return

    # 2. Prepare Prompts (Ensure they are in the desktop folder for local referencing)
    prompts_src = project_root / "prompts"
    prompts_dest = desktop_dir / "prompts"
    
    if prompts_dest.exists():
        shutil.rmtree(prompts_dest)
    
    print(f"Copying prompts from {prompts_src}...")
    shutil.copytree(prompts_src, prompts_dest)

    print("✅ Assets prepared successfully in /desktop folder.")

if __name__ == "__main__":
    prepare_assets()
