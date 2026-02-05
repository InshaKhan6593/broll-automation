
import json
import os
from pathlib import Path
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

TRANSCRIPT_PATH = Path("video_transcript.json")
# Using 70B for high-level reasoning on "what is important"
MODEL = "llama-3.3-70b-versatile" 

SYSTEM_PROMPT = """
You are a Senior Documentary Film Editor with a keen eye for visual storytelling.
Your task is to analyze a transcript and select **Edit Points** (segments) where inserting B-Roll or photographic evidence would significantly enhance the narrative.

# THE PHILOSOPHY: CONTEXT > KEYWORDS
- **BAD SELECTION (Keyword Matching)**: The speaker says "I met a doctor." -> DO NOT SELECT. This is trivial.
- **GOOD SELECTION (Narrative Context)**: The speaker says "The doctors were exhausted, working late into the night to treat the overflow of patients." -> SELECT. This describes a *scene* and an *emotion* that we can visualize.

# SELECTION CRITERIA
1.  **Visual Evidence**: Does the speaker make a claim about a condition (poverty, dirt, crowds, joy) that an image would "prove" or reinforce?
2.  **Action & Interaction**: Look for moments describing *doing* something (treating patients, playing games, building houses).
3.  **Emotional Beats**: If the speaker reflects on how "hard" or "beautiful" something was, we need an image that captures that vibe.
4.  **Volume**: Do not arbitrarily limit yourself. If 15 segments need images to tell the story, select 15. We would rather have too many options than too few.

# INPUT
You will receive a numbered list of transcript segments.

# OUTPUT
Return a JSON object with a list of `selected_segment_ids`.
Example:
{
  "selected_segment_ids": [0, 3, 4, 5, 8, 9, 12, 14, 18, 22] 
}
"""

def select_segments():
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    
    if not TRANSCRIPT_PATH.exists():
        print("Transcript not found.")
        return []

    with open(TRANSCRIPT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        segments = data.get("transcript", [])
        
    # Format transcript for LLM
    transcript_text = ""
    for i, seg in enumerate(segments):
        # Use English translation if available, else original
        text_content = seg.get("text_en", seg["text"])
        transcript_text += f"[{i}] ({seg['start']:.1f}s): {text_content}\n"
        
    print(f"--- Selector Agent: Analyzing {len(segments)} segments ---")
    
    try:
        completion = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Here is the transcript:\n\n{transcript_text}\n\nSelect the key segments."}
            ],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        
        result = json.loads(completion.choices[0].message.content)
        selected_ids = result.get("selected_segment_ids", [])
        
        print(f"--- Selector Agent: Picked {len(selected_ids)} segments for illustration ---")
        return selected_ids
        
    except Exception as e:
        print(f"Selector Error: {e}")
        # Fallback: Pick every 5th segment? No, better to return empty and fail safe.
        return []

if __name__ == "__main__":
    ids = select_segments()
    print("Selected IDs:", ids)
