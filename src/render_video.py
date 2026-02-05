import json
import subprocess
import os
from pathlib import Path
from src.paths import EDL_PATH, OUTPUTS_DIR

# --- Configuration (Defaults) ---
VIDEO_PATH = Path("Fabi_clean.mov")
IMAGES_DIR = Path("Images") 
OUTPUT_PATH = OUTPUTS_DIR / "output.mp4"

# FFmpeg Path
try:
    import imageio_ffmpeg as ffmpeg_lib
    FFMPEG_EXE = ffmpeg_lib.get_ffmpeg_exe()
except ImportError:
    FFMPEG_EXE = "ffmpeg"

def has_audio(video_path):
    """Check if the video has an audio stream using ffmpeg."""
    try:
        # Use ffmpeg itself to probe (ffprobe path is unreliable with imageio_ffmpeg)
        cmd = [
            FFMPEG_EXE, "-i", str(video_path),
            "-hide_banner", "-f", "null", "-"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        # FFmpeg prints stream info to stderr
        return "Audio:" in result.stderr
    except Exception:
        return False  # Default to False - safer than crashing with -map 0:a

def render_with_ffmpeg():
    print("--- Starting Video Renderer (FFmpeg Optimized) ---")

    if not VIDEO_PATH.exists():
        print(f"Error: Video file not found at {VIDEO_PATH}")
        return

    if not EDL_PATH.exists():
        print("Error: EDL file not found.")
        return

    # 1. Load Edits
    with open(EDL_PATH, "r", encoding="utf-8") as f:
        edits = json.load(f)

    if not edits:
        print("No edits found in EDL. Copying original video...")
        try:
            subprocess.run([
                FFMPEG_EXE, "-y", "-i", str(VIDEO_PATH), "-c", "copy", str(OUTPUT_PATH)
            ], check=True, capture_output=True, text=True)
            print("Done.")
        except Exception as e:
            print(f"Error: {e}")
        return

    # 2. Build FFmpeg Command - use explicit counter for input indices
    inputs = ["-i", str(VIDEO_PATH)]
    filter_complex_parts = []
    last_stream_name = "0:v"
    input_counter = 1  # next input index (0 = video)
    overlay_count = 0

    for i, edit in enumerate(edits):
        image_filename = edit["image"]
        image_path = IMAGES_DIR / image_filename

        if not image_path.exists():
            print(f"Warning: Image {image_filename} not found. Skipping.")
            continue

        inputs.extend(["-i", str(image_path)])
        image_input_index = input_counter
        input_counter += 1
        overlay_count += 1

        start_t = edit["start_time"]
        end_t = edit["end_time"]

        scaled = f"s{overlay_count}"
        padded = f"p{overlay_count}"
        next_stream = f"v{overlay_count}"

        # Chain Filters
        filter_complex_parts.append(f"[{image_input_index}:v]scale=1920:1080:force_original_aspect_ratio=decrease[{scaled}]")
        filter_complex_parts.append(f"[{scaled}]pad=1920:1080:(1920-iw)/2:(1080-ih)/2:black[{padded}]")
        filter_complex_parts.append(f"[{last_stream_name}][{padded}] overlay=(W-w)/2:(H-h)/2:enable='between(t,{start_t},{end_t})' [{next_stream}]")
        last_stream_name = next_stream

    if not filter_complex_parts:
        print("No valid overlays. Copying original video...")
        subprocess.run([
            FFMPEG_EXE, "-y", "-i", str(VIDEO_PATH), "-c", "copy", str(OUTPUT_PATH)
        ], check=True, capture_output=True, text=True)
        return

    # Rename last stream to 'outv'
    filter_complex_parts[-1] = filter_complex_parts[-1].rsplit("[", 1)[0] + "[outv]"
    last_stream_name = "outv"

    filter_complex_str = ";".join(filter_complex_parts)

    cmd = [FFMPEG_EXE, "-y"] + inputs + ["-filter_complex", filter_complex_str]
    cmd += ["-map", f"[{last_stream_name}]"]
    # Use 0:a? (optional) so FFmpeg doesn't crash if video has no audio
    cmd += ["-map", "0:a?"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18"]
    cmd += ["-c:a", "copy"]
    cmd.append(str(OUTPUT_PATH))

    print(f"Executing FFmpeg with {overlay_count} overlays ({input_counter - 1} images)...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            stderr_msg = result.stderr[-2000:] if result.stderr else "No stderr captured"
            error_msg = f"FFmpeg failed (exit code {result.returncode}):\n{stderr_msg}"
            print(error_msg)
            raise Exception(error_msg)
        print(f"Success: {OUTPUT_PATH}")
    except Exception as e:
        if "FFmpeg failed" not in str(e):
            print(f"FFmpeg Error: {e}")
        raise

if __name__ == "__main__":
    render_with_ffmpeg()
