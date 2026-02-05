
import os
import json
import subprocess
from pathlib import Path
import groq
from groq import Groq
from dotenv import load_dotenv
import imageio_ffmpeg as ffmpeg

# Load Environment Variables
load_dotenv()

# Configuration
from src.paths import UPLOADS_VIDEO_DIR, TEMP_DIR, TRANSCRIPT_PATH
VIDEO_FILE = UPLOADS_VIDEO_DIR / "Bob_clean.mov"
AUDIO_FILE = TEMP_DIR / "extracted_audio.mp3"
TRANSCRIPT_FILE = TRANSCRIPT_PATH


def extract_audio(video_path, audio_path):
    """Extracts mp3 audio from video using FFmpeg."""
    print(f"Extracting audio from {video_path}...")
    
    # Ensure temp dir exists
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    
    ffmpeg_exe = ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg_exe,
        "-y", # Overwrite
        "-i", str(video_path),
        "-q:a", "0", # Best variable bit rate
        "-map", "a", 
        str(audio_path)
    ]
    
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"Audio saved to {audio_path}")

def transcribe_audio(client, audio_path):
    """Translate audio to English using Groq Whisper."""
    print("Translating to English with Whisper (Groq API)...")

    with open(audio_path, "rb") as audio_file:
        transcript = client.audio.translations.create(
            model="whisper-large-v3",
            file=audio_file,
            response_format="verbose_json"
        )

    return transcript

def main(video_path_arg=None):
    print("--- Starting Transcription Agent (Groq Powered) ---")
    
    # Determine Video Path
    if video_path_arg:
        target_video = Path(video_path_arg)
    else:
        # Default fallback (or Could raise error)
        target_video = VIDEO_FILE

    if not target_video.exists():
        print(f"ERROR: Video file not found: {target_video}")
        return

    # Check for API Key
    if not os.getenv("GROQ_API_KEY"):
        print("ERROR: GROQ_API_KEY not found in .env file.")
        return

    client = Groq()
    
    # 1. Extract Audio
    try:
        extract_audio(target_video, AUDIO_FILE)
    except Exception as e:
        print(f"FFmpeg Error: {e}")
        return

    # 2. Transcribe (Direct to English)
    try:
        raw_result = transcribe_audio(client, AUDIO_FILE)
        print(f"DEBUG: raw_result type: {type(raw_result)}")
        
        clean_segments = process_transcript(raw_result)
        print(f"DEBUG: Processed {len(clean_segments)} segments.")
        
        # 3. Save
        for seg in clean_segments:
            seg['text_en'] = seg['text']

        data = {
            "source_video": str(target_video),
            "transcript": clean_segments
        }
        
        with open(TRANSCRIPT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            
        print(f"--- Transcription Complete. Saved to {TRANSCRIPT_FILE} ---")
        
    except groq.RateLimitError as e:
        msg = f"Groq API Rate Limit Reached: {e}"
        print(f"ERROR: {msg}")
        raise Exception(msg)  # Raise to stop workflow
    except groq.APIConnectionError as e:
        msg = f"Groq API Connection Failed: {e}"
        print(f"ERROR: {msg}")
        raise Exception(msg)
    except groq.APIError as e:
        msg = f"Groq API Error: {e}"
        print(f"ERROR: {msg}")
        raise Exception(msg)
    except Exception as e:
        print(f"Transcription Error: {e}")
        raise

def process_transcript(raw_transcript):
    """Clean up the transcript output."""
    segments = []
    
    # Access segments (handle dict vs object)
    if isinstance(raw_transcript, dict):
        raw_segments = raw_transcript.get('segments', [])
    else:
        raw_segments = getattr(raw_transcript, 'segments', [])

    for seg in raw_segments:
        # Access fields (handle dict vs object)
        if isinstance(seg, dict):
            s_id = seg.get('id')
            s_start = seg.get('start')
            s_end = seg.get('end')
            s_text = seg.get('text', '').strip()
        else:
            s_id = getattr(seg, 'id', None)
            s_start = getattr(seg, 'start', 0.0)
            s_end = getattr(seg, 'end', 0.0)
            s_text = getattr(seg, 'text', '').strip()
            
        segments.append({
            "id": s_id,
            "start": s_start,
            "end": s_end,
            "text": s_text
        })
    return segments

if __name__ == "__main__":
    main()
