"""
Image Caption Service

Provides:
- Caption generation using GPT-4o Vision
- Caching by filename (skip if already captioned)
- Batch processing for multiple images
"""

import os
import json
import base64
from pathlib import Path
from typing import List, Dict, Optional
import ollama
from ollama import Client
from dotenv import load_dotenv

from backend.services.logging import logger

load_dotenv()

from src.paths import IMAGE_INDEX_PATH, PROMPTS_DIR
VISION_PROMPT_PATH = PROMPTS_DIR / "vision_agent_prompt.md"


def load_image_index() -> List[Dict]:
    """Load existing image index."""
    if IMAGE_INDEX_PATH.exists():
        with open(IMAGE_INDEX_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_image_index(index: List[Dict]):
    """Save image index."""
    with open(IMAGE_INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)


def get_cached_caption(filename: str, index: List[Dict]) -> Optional[Dict]:
    """Check if caption exists for filename."""
    for item in index:
        if item.get("filename") == filename:
            return item
    return None


def load_vision_prompt() -> str:
    """Load the vision agent prompt."""
    if VISION_PROMPT_PATH.exists():
        with open(VISION_PROMPT_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return "Describe this image in detail for semantic search matching."


def encode_image(image_path: Path) -> str:
    """Encode image to base64."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def generate_caption_ollama(image_path: Path, system_prompt: str, ollama_key: str = None) -> Optional[Dict]:
    """Generate caption using Ollama Cloud (Qwen3-VL)."""
    api_key = ollama_key or os.getenv("OLLAMA_API_KEY")
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    client = Client(
        host=host,
        headers={'Authorization': f'Bearer {api_key}'}
    )
    
    try:
        # Ollama client can take the path directly or base64
        response = client.chat(
            model="qwen3-vl:235b-instruct-cloud",
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
        
        result = json.loads(response.message.content)
        return {
            "filename": image_path.name,
            "description": result.get("description", "")
        }
        
    except ollama.ResponseError as e:
        msg = f"Caption Model Error (Ollama): {e.error}"
        logger.error(msg)
        raise Exception(msg)
    except Exception as e:
        msg = f"Failed to caption {image_path.name}: {e}"
        logger.error(msg)
        raise Exception(msg)


def process_images(image_paths: List[Path], ollama_key: str = None) -> List[Dict]:
    """
    Process multiple images with caption caching.
    
    Returns list of captions (both cached and newly generated).
    """
    logger.set_step("Image Captioning")
    
    # Load existing index
    index = load_image_index()
    logger.info(f"Loaded {len(index)} existing captions from cache")
    
    # Load vision prompt
    system_prompt = load_vision_prompt()
    
    results = []
    new_captions = 0
    cached_captions = 0
    
    for image_path in image_paths:
        filename = image_path.name
        
        # Check cache
        cached = get_cached_caption(filename, index)
        
        if cached:
            logger.info(f"[cached] {filename}")
            results.append(cached)
            cached_captions += 1
        else:
            logger.info(f">> Captioning: {filename}...")
            caption = generate_caption_ollama(image_path, system_prompt, ollama_key=ollama_key)
            
            if caption:
                results.append(caption)
                index.append(caption)
                new_captions += 1
                logger.success(f"  Caption generated for {filename}")
            else:
                logger.warning(f"  Failed to caption {filename}")
    
    # Save updated index
    if new_captions > 0:
        save_image_index(index)
        logger.info(f"Saved {new_captions} new captions to index")
    
    logger.success(f"Captioning complete: {cached_captions} cached, {new_captions} new")
    
    return results
