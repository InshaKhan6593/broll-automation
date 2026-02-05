"""
Segment Creation Module

Reads raw Whisper transcript and uses GLM 4.7 (via Ollama) to create
meaningful visual segments using the segment_consolidator_prompt.
"""

import json
from pathlib import Path
import ollama
from ollama import Client
from dotenv import load_dotenv
import os

load_dotenv()

# --- Configuration ---
from src.paths import TRANSCRIPT_PATH, SEGMENTS_PATH, PROMPTS_DIR
TRANSCRIPT_FILE = TRANSCRIPT_PATH
SEGMENTS_FILE = SEGMENTS_PATH
PROMPT_FILE = PROMPTS_DIR / "segment_consolidator_prompt.md"
OUTPUT_FILE = SEGMENTS_PATH


# Model Configuration
MODEL_NAME = "mistral-large-3:675b-cloud"


def load_prompt() -> str:
    """Load the segment consolidator system prompt."""
    if not PROMPT_FILE.exists():
        raise FileNotFoundError(f"Prompt file not found: {PROMPT_FILE}")
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        return f.read()


def load_transcript() -> list:
    """Load raw transcript segments from Whisper output."""
    if not TRANSCRIPT_FILE.exists():
        raise FileNotFoundError(f"Transcript file not found: {TRANSCRIPT_FILE}")
    with open(TRANSCRIPT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("transcript", [])


def format_transcript_for_llm(raw_segments: list) -> str:
    """Format raw segments into a string for the LLM."""
    lines = []
    for seg in raw_segments:
        # Format: [ID] (Start-End) Text
        lines.append(f"[{seg['id']}] ({seg['start']:.1f}-{seg['end']:.1f}) {seg['text']}")
    return "\n".join(lines)


def clean_json_response(response_text: str) -> str:
    """
    Clean LLM response that might be wrapped in markdown code blocks.
    Handles: ```json ... ```, ``` ... ```, or plain JSON
    Also removes any text before the first opening brace or bracket.
    """
    text = response_text.strip()
    
    # Remove markdown code blocks if present
    if "```" in text:
        # Find start of code block
        start_marker = text.find("```")
        # Find newline after start marker (to skip ```json)
        first_newline = text.find("\n", start_marker)
        if first_newline != -1:
            # Check if there is a closing block
            end_marker = text.rfind("```")
            if end_marker > first_newline:
                text = text[first_newline + 1:end_marker].strip()
    
    # Fallback/Safety: Find first [ or { and last ] or }
    first_brace = text.find("[")
    first_curly = text.find("{")
    
    start_index = -1
    if first_brace != -1 and first_curly != -1:
        start_index = min(first_brace, first_curly)
    elif first_brace != -1:
        start_index = first_brace
    elif first_curly != -1:
        start_index = first_curly
        
    if start_index != -1:
        text = text[start_index:]
        
    # Find last closing
    last_brace = text.rfind("]")
    last_curly = text.rfind("}")
    
    end_index = -1
    if last_brace != -1 and last_curly != -1:
        end_index = max(last_brace, last_curly)
    elif last_brace != -1:
        end_index = last_brace
    elif last_curly != -1:
        end_index = last_curly
        
    if end_index != -1:
        text = text[:end_index+1]
            
    return text


def parse_llm_response(response_text: str, raw_segments: list) -> list:
    """
    Parse LLM JSON response. The prompt asks for start/end timestamps directly.
    """
    # Clean markdown wrapper if present
    cleaned_text = clean_json_response(response_text)
    
    # Calculate max duration from raw segments
    max_duration = 0.0
    if raw_segments:
        max_duration = raw_segments[-1].get('end', 0.0)
    
    try:
        result = json.loads(cleaned_text)
        segments_out = result.get("segments", [])
    except json.JSONDecodeError as e:
        print(f"Error parsing LLM response: {e}")
        print(f"Raw response: {response_text[:500]}...")
        return []

    final_segments = []
    for seg in segments_out:
        start = seg.get("start")
        end = seg.get("end")
        text = seg.get("text", "")
        context = seg.get("context", "")

        if start is None or end is None:
            print(f"Warning: Segment missing start or end: {seg}")
            continue

        if not text.strip():
            print(f"Warning: Segment has empty text, skipping")
            continue
            
        # Clamp timestamps to valid range
        start_float = float(start)
        end_float = float(end)
        
        if start_float > max_duration:
             print(f"Warning: Segment start {start_float} exceeds max duration {max_duration}. Skipping.")
             continue
             
        if end_float > max_duration:
             print(f"Warning: Segment end {end_float} exceeds max duration. Clamping to {max_duration}.")
             end_float = max_duration
             
        if start_float >= end_float:
             print(f"Warning: Invalid segment duration ({start_float}-{end_float}). Skipping.")
             continue

        final_segments.append({
            "start_time": start_float,
            "end_time": end_float,
            "text": text.strip(),
            "context": context.strip()
        })

    return final_segments



def create_segments():
    """Main function to create semantic segments from raw transcript."""
    print("--- Starting Segment Creation (Mistral Large) ---")

    # 1. Load inputs
    system_prompt = load_prompt()
    raw_segments = load_transcript()
    print(f"Loaded {len(raw_segments)} raw transcript fragments.")

    # 2. Format transcript for LLM
    transcript_text = format_transcript_for_llm(raw_segments)

    # 3. Call Mistral Large via Ollama Cloud
    print(f"Calling {MODEL_NAME} for semantic segmentation...")
    
    client = Client(
        host='https://ollama.com',
        headers={'Authorization': 'Bearer ' + os.environ.get('OLLAMA_API_KEY', '')}
    )

    try:
        response = client.chat(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": transcript_text}
            ],
            format="json",
        )
        
        response_text = response.message.content
        print(f"Received response ({len(response_text)} chars)")

    except ollama.ResponseError as e:
        msg = f"Ollama Cloud API Error: {e.error}"
        print(f"ERROR: {msg}")
        raise Exception(msg)
    except Exception as e:
        msg = f"Segmentation Error (Ollama): {e}"
        print(f"ERROR: {msg}")
        raise Exception(msg)

    # 4. Parse and validate response
    final_segments = parse_llm_response(response_text, raw_segments)

    if not final_segments:
        print("Error: No valid segments created.")
        return

    # 5. Save output
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_segments, f, indent=2)

    print(f"--- Segment Creation Complete. Created {len(final_segments)} visual segments. ---")
    print(f"Output saved to: {OUTPUT_FILE}")



if __name__ == "__main__":
    create_segments()
