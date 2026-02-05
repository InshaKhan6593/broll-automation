import os
import sys
import subprocess
import shutil
import platform
from pathlib import Path

def bundle_backend():
    print("Starting Python Backend Bundling...")

    project_root = Path(__file__).parent.parent
    backend_main = project_root / "backend" / "main.py"
    output_dir = project_root / "desktop" / "backend-dist"

    # Remove old builds
    if output_dir.exists():
        shutil.rmtree(output_dir)

    # PyInstaller path separator: ';' on Windows, ':' on macOS/Linux
    sep = ';' if platform.system() == 'Windows' else ':'

    # PyInstaller Command
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onedir",
        "--console",
        f"--distpath={output_dir.parent}",
        f"--workpath={project_root / 'temp' / 'pyinstaller_work'}",
        f"--name=backend-engine",
        # Include necessary data files (';' on Windows, ':' on macOS/Linux)
        f"--add-data={project_root / 'prompts'}{sep}prompts",
        f"--add-data={project_root / 'src'}{sep}src",
        # Collect all submodules for complex packages
        "--collect-submodules=chromadb",
        "--collect-submodules=langchain",
        "--collect-submodules=langchain_core",
        "--collect-submodules=langchain_community",
        "--collect-submodules=langchain_text_splitters",
        "--collect-submodules=langgraph",
        "--collect-submodules=ollama",
        "--collect-submodules=groq",
        "--collect-submodules=openai",
        "--collect-submodules=pydantic",
        "--collect-submodules=pydantic_core",
        "--collect-submodules=uvicorn",
        "--collect-submodules=starlette",
        "--collect-submodules=fastapi",
        "--collect-submodules=httpx",
        "--collect-submodules=httpcore",
        "--collect-submodules=anyio",
        # Hidden imports PyInstaller commonly misses
        "--hidden-import=chromadb.telemetry.product.posthog",
        "--hidden-import=chromadb.api.segment",
        "--hidden-import=chromadb.db.impl",
        "--hidden-import=chromadb.db.impl.sqlite",
        "--hidden-import=chromadb.segment.impl",
        "--hidden-import=chromadb.segment.impl.manager",
        "--hidden-import=chromadb.segment.impl.metadata",
        "--hidden-import=chromadb.segment.impl.vector",
        "--hidden-import=chromadb.migrations",
        "--hidden-import=chromadb.utils.embedding_functions",
        "--hidden-import=langchain",
        "--hidden-import=langgraph",
        "--hidden-import=ollama",
        "--hidden-import=groq",
        "--hidden-import=dotenv",
        "--hidden-import=imageio_ffmpeg",
        "--hidden-import=imageio_ffmpeg.binaries",
        "--hidden-import=multipart",
        "--hidden-import=python_multipart",
        "--hidden-import=sse_starlette",
        "--hidden-import=uvicorn.logging",
        "--hidden-import=uvicorn.loops",
        "--hidden-import=uvicorn.loops.auto",
        "--hidden-import=uvicorn.protocols",
        "--hidden-import=uvicorn.protocols.http",
        "--hidden-import=uvicorn.protocols.http.auto",
        "--hidden-import=uvicorn.protocols.websockets",
        "--hidden-import=uvicorn.protocols.websockets.auto",
        "--hidden-import=uvicorn.lifespan",
        "--hidden-import=uvicorn.lifespan.on",
        "--hidden-import=PIL",
        "--hidden-import=PIL.Image",
        # Collect data files for packages that need them
        "--collect-data=chromadb",
        "--collect-data=imageio_ffmpeg",
        str(backend_main)
    ]

    print(f"Running PyInstaller...")
    subprocess.run(cmd, check=True)

    # Rename for Electron to find it easily
    engine_dir = project_root / "desktop" / "backend-engine"
    if engine_dir.exists():
        print(f"Moving {engine_dir} to {output_dir}...")
        try:
            if output_dir.exists():
                shutil.rmtree(output_dir)
            shutil.move(str(engine_dir), str(output_dir))
            print("Move successful.")
        except Exception as e:
            print(f"Failed to move directory: {e}")

    print(f"Done. Python Backend bundled to {output_dir}")

if __name__ == "__main__":
    bundle_backend()
