
import os
import json
import base64
import time
from pathlib import Path
from ollama import Client
from dotenv import load_dotenv

# Load Environment Variables
load_dotenv()

# Configuration
IMAGE_DIR = Path("Images") 
PROMPT_PATH = Path("prompts/vision_agent_prompt.md")
OUTPUT_FILE = Path("image_index.json")

def get_model_client():
    api_key = os.getenv("OLLAMA_API_KEY")
    client = Client(
        host='https://ollama.com',
        headers={'Authorization': f'Bearer {api_key}'}
    )
    return "qwen3-vl:235b-instruct-cloud", client

def load_system_prompt():
    """Loads the Vision Agent system prompt."""
    if not PROMPT_PATH.exists():
        raise FileNotFoundError(f"Prompt file not found: {PROMPT_PATH}")
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()

def analyze_image_dynamic(client, model_id, image_path, system_prompt):
    """Sends image to AI for analysis."""
    # Add delay to avoid rate limits in parallel execution
    time.sleep(1)
    
    try:
        response = client.chat(
            model=model_id,
            messages=[
                {
                    "role": "user",
                    "content": f"{system_prompt}\nAnalyze this image and provide the JSON output with a 'description' field.",
                    "images": [str(image_path)]
                }
            ],
            options={"temperature": 0.2},
            format="json"
        )
        return json.loads(response.message.content)
    except Exception as e:
        print(f"Error analyzing {image_path}: {e}")
        return None

def main():
    print("--- Starting Image Indexing Agent (Groq Powered) ---")
    
    # Check for API Key
    if not os.getenv("GROQ_API_KEY"):
        print("ERROR: GROQ_API_KEY not found in .env file.")
        print("Please add your key to the .env file and run again.")
        return

    model_id, client = get_model_client()
    system_prompt = load_system_prompt()
    
    # Gather Images
    valid_extensions = {".jpg", ".jpeg", ".png"}
    if not IMAGE_DIR.exists():
         print(f"ERROR: Image directory not found: {IMAGE_DIR}")
         return
         
    image_files = [f for f in IMAGE_DIR.iterdir() if f.suffix.lower() in valid_extensions]
    
    print(f"Found {len(image_files)} images in {IMAGE_DIR}")
    print(f"Using Model: {model_id}")
    
    index_data = []
    
    # Process Images (Parallel - 3 Workers)
    import concurrent.futures
    print("--- Starting Parallel Indexing (3 Workers) ---")
    
    # Use existing index_data if you wanted to append, but here we likely start fresh or just accum
    # If we want to be safe, restart list
    index_data = [] 

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_to_img = {
            executor.submit(analyze_image_dynamic, client, model_id, img_path, system_prompt): img_path 
            for img_path in image_files
        }
        
        for future in concurrent.futures.as_completed(future_to_img):
            img_path = future_to_img[future]
            try:
                analysis = future.result()
                if analysis:
                    combined = {
                        "filename": img_path.name,
                        "description": analysis.get("description", ""), 
                    }
                    index_data.append(combined)
                    print(f"[Done] {img_path.name}")
                    
                    # Incremental Save (Main thread is safe here as as_completed yields sequentially)
                    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                        json.dump(index_data, f, indent=2)
                else:
                    print(f"[Failed] {img_path.name}")
            except Exception as exc:
                print(f"[Error] {img_path.name}: {exc}")

    print(f"--- Indexing Complete. Saved to {OUTPUT_FILE} ---")

if __name__ == "__main__":
    main()
