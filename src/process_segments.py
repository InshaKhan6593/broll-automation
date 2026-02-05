
import json
import os
from pathlib import Path
from groq import Groq
from dotenv import load_dotenv

# Load Environment Variables
load_dotenv()

TRANSCRIPT_FILE = Path("video_transcript.json")
OUTPUT_FILE = Path("semantic_segments.json")
GROQ_MODEL = "llama-3.3-70b-versatile"

def get_groq_client():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not found in environment")
    return Groq(api_key=api_key)

def process_semantic_segments():
    """
    Reads raw transcript IDs and uses Groq to reconstruct flow 
    and segment by semantic context.
    """
    print("--- Starting Semantic Segmentation (Groq) ---")
    
    if not TRANSCRIPT_FILE.exists():
        print(f"Error: {TRANSCRIPT_FILE} not found.")
        return

    with open(TRANSCRIPT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        raw_segments = data.get("transcript", [])

    print(f"Loaded {len(raw_segments)} raw fragments.")

    # Prepare Context for LLM
    # We pass a simplified list to save tokens but keep IDs
    context_text = ""
    for seg in raw_segments:
        # Format: [ID] (Start-End) Text
        # Note: We rely on ID to map back times later
        context_text += f"[{seg['id']}] ({seg['start']:.1f}-{seg['end']:.1f}) {seg['text']}\n"

    system_prompt = """
    You are an expert Video Editor and Linguist.
    You will receive a raw, fragmented video transcript (timestamped).
    The text is a MIX of English and Haitian Creole/French.
    
    YOUR GOAL: 
    Reconstruct the flow of speech into coherent "Visual Segments".
    
    INSTRUCTIONS:
    1. READ the fragments. Reconstruct sentences.
    2. TRANSLATE any non-English speech into clear English.
    3. GROUP fragments into Segments.
       - A Segment = A complete thought, sentence, or visual idea.
       - A Segment should typically be 5-15 seconds long (not too short, not too long).
    4. OUTPUT JSON format exactly.
    
    JSON STRUCTURE:
    {
      "segments": [
        {
          "start_id": <int>,
          "end_id": <int>,
          "text": "<Full reconstructed English text for this segment>",
          "visual_intent": "<Brief description of what visual imagery fits this text>",
          "explanation": "<Why you grouped these IDs>"
        },
        ...
      ]
    }
    
    CRITICAL: 
    - Cover ALL IDs from start to finish. Do not skip.
    - "start_id" and "end_id" define the range of raw fragments included.
    - If the input text is gibberish/phonetic Creole, infer the meaning from context.
    """

    client = get_groq_client()
    
    try:
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context_text}
            ],
            response_format={"type": "json_object"}
        )
        
        result_json = json.loads(completion.choices[0].message.content)
        segments_out = result_json.get("segments", [])
        
        # Post-process to add exact start/end times from IDs
        final_segments = []
        id_map = {s['id']: s for s in raw_segments}
        
        for p_seg in segments_out:
            s_id = p_seg.get("start_id")
            e_id = p_seg.get("end_id")
            
            if s_id is not None and e_id is not None:
                # Get timing from raw map
                # Safety: check if ID exists
                start_node = id_map.get(s_id)
                end_node = id_map.get(e_id)
                
                if start_node and end_node:
                    p_seg['start_time'] = start_node['start']
                    p_seg['end_time'] = end_node['end']
                    final_segments.append(p_seg)
                else:
                    print(f"Warning: Invalid IDs in response: {s_id}-{e_id}")

        # Save
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(final_segments, f, indent=2)
            
        print(f"--- Segmentation Complete. Created {len(final_segments)} visual segments. Saved to {OUTPUT_FILE} ---")

    except Exception as e:
        print(f"Groq Error: {e}")

if __name__ == "__main__":
    process_semantic_segments()
