import os
import sys
from pathlib import Path

# --- Base Detection ---
def get_app_root():
    """Returns the root of the application source/binary."""
    if getattr(sys, 'frozen', False):
        # Bundled EXE (PyInstaller)
        return Path(sys._MEIPASS)
    # Running from source
    return Path(__file__).parent.parent

def get_data_root():
    """Returns the writable data storage directory."""
    if getattr(sys, 'frozen', False):
        # Store data in %APPDATA% on Windows when bundled
        data_dir = Path(os.environ.get('APPDATA')) / "HumanitarianEditor"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir
    # In development, keep data in the project root
    return get_app_root()

# --- Common Paths ---
APP_ROOT = get_app_root()
DATA_ROOT = get_data_root()

# Storage Directories
UPLOADS_DIR = DATA_ROOT / "uploads"
UPLOADS_VIDEO_DIR = UPLOADS_DIR / "video"
UPLOADS_IMAGES_DIR = UPLOADS_DIR / "images"

CHROMA_DB_PATH = DATA_ROOT / "chroma_db"
TEMP_DIR = DATA_ROOT / "temp"
OUTPUTS_DIR = DATA_ROOT / "outputs"

# Config / Data Files
IMAGE_INDEX_PATH = DATA_ROOT / "image_index.json"
TRANSCRIPT_PATH = DATA_ROOT / "video_transcript.json"
SEGMENTS_PATH = DATA_ROOT / "semantic_segments.json"
EDL_PATH = DATA_ROOT / "edit_decision_list.json"

# Resource Paths (Usually read-only in App Bundle)
PROMPTS_DIR = APP_ROOT / "prompts"

# Ensure dirs exist
for d in [UPLOADS_VIDEO_DIR, UPLOADS_IMAGES_DIR, CHROMA_DB_PATH, TEMP_DIR, OUTPUTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)
