"""
Agent Definitions for Video Editing System

Director: Search Agent - queries RAG and passes candidates to Critic
Critic: Selector + Guide - picks best image OR requests query refinement
Both use GLM 4.7 via Ollama
"""

import os
import json
from typing import TypedDict, List, Optional, Dict, Any
from pathlib import Path
import ollama
from ollama import chat as ollama_chat_sdk
from ollama import Client
from dotenv import load_dotenv
from src.rag import ImageRAG


load_dotenv()

# --- Configuration ---
from src.paths import PROMPTS_DIR, IMAGE_INDEX_PATH
EDITOR_PROMPT_PATH = PROMPTS_DIR / "editor_agent_prompt.md"

# Models Configuration - Cloud Models
DIRECTOR_MODEL = "mistral-large-3:675b-cloud"
CRITIC_MODEL = "gemma3:27b-cloud"

# Initialize Ollama Client
try:
    ollama_host = os.environ.get('OLLAMA_HOST', 'http://localhost:11434')
    ollama_client = Client(
        host=ollama_host,
        headers={'Authorization': 'Bearer ' + os.environ.get('OLLAMA_API_KEY', '')}
    )
except AttributeError:
    # Fallback if Client isn't directly available in the imported module shorthand, 
    # but usually we import Client from ollama. 
    # Let's adjust imports in the next block.
    pass

# Global RAG Instance (Lazy Load)
_rag_instance = None


def get_rag():
    global _rag_instance
    if _rag_instance is None:
        print("  [System] Initializing RAG Vector Store...")
        _rag_instance = ImageRAG(reset_db=False)
    return _rag_instance


def reset_rag():
    """Force reset of the global RAG instance to release file locks."""
    global _rag_instance
    if _rag_instance:
        print("  [System] Clearing global RAG instance...")
        # Try to explicitly close if method exists (cleaner cleanup)
        # Note: Chroma 0.4+ PersistentClient usually works via GC, but we'll destroy the ref.
        try:
            if hasattr(_rag_instance, 'client'):
                 del _rag_instance.client
        except:
            pass
        _rag_instance = None


# --- State Definition ---
class AgentState(TypedDict):
    # Input
    transcript_segment: Dict[str, Any]
    
    # Search State
    current_query: str                    # Current RAG search query
    all_candidates: List[Dict[str, Any]]  # All candidates from RAG for Critic
    
    # Decision State
    selected_image: Optional[str]         # Final selected image
    reasoning: Optional[str]              # Selection reasoning
    
    # Refinement State
    critic_verdict: Optional[str]         # SELECT, REFINE, or SKIP
    suggested_query: Optional[str]        # Critic's query suggestion (if REFINE)
    refinement_count: int                 # Track refinement rounds
    accumulated_candidates: List[Dict[str, Any]] # Track all unique candidates across rounds
    
    # Tracking
    used_images: List[str]                # Previously used images (de-duplication)
    ranked_candidates: List[Dict[str, Any]] # Top 3 candidates for Global Resolution


# --- Helper Functions ---
def load_prompt(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()




def clean_json_response(text: str) -> str:
    """Clean markdown-wrapped JSON responses."""
    text = text.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1:]
        if text.endswith("```"):
            text = text[:-3].strip()
    return text


def ollama_chat(system_prompt: str, user_message: str) -> dict:
    """
    Chat completion using Ollama SDK (for Critic - Gemma 3).
    Returns parsed JSON response.
    """
    # Initialize client locally to ensure env var is picked up or use global if preferred
    # Using the module level client would be better if we imported it correctly.
    # But since we need to change imports, let's just instantiate here or use a global.
    
    host = os.environ.get('OLLAMA_HOST', 'http://localhost:11434')
    client = Client(
        host=host,
        headers={'Authorization': 'Bearer ' + os.environ.get('OLLAMA_API_KEY', '')}
    )

    try:
        response = client.chat(
            model=CRITIC_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            stream=False, # JSON mode usually non-streaming, but let's check options.
                          # format='json' is supported.
            format="json",
        )
        
        content = response.message.content
        
        # Handle empty response
        if not content or not content.strip():
            raise ValueError("Empty response from Ollama")
        
        # Clean markdown wrapper if present
        content = clean_json_response(content)
        
        return json.loads(content)
    except json.JSONDecodeError as e:
        print(f"  [JSON Error] Failed to parse Ollama response: {e}")
        print(f"  [Raw content] {content[:200] if content else 'EMPTY'}...")
        raise
    except ollama.ResponseError as e:
        msg = f"Critic Model Error (Ollama): {e.error}"
        print(f"  [Error] {msg}")
        raise Exception(msg)
    except Exception as e:
        print(f"  [Ollama Error] {e}")
        raise



# --- Unified Editor Node (Search + Evaluate) ---
def editor_node(state: AgentState):
    """
    The Unified Editor Agent.
    1. Determines search query (Initial or Refined)
    2. Searches RAG
    3. Accumulates candidates across rounds
    4. Evaluates candidates (Select, Refine, or Skip)
    """
    segment = state['transcript_segment']
    segment_text = segment.get('text', '')
    context = segment.get('context', '') # Narrative Context
    refinement_count = state.get('refinement_count', 0)
    accumulated = state.get('accumulated_candidates', [])
    
    # --- 1. Determine Search Query ---
    if refinement_count == 0:
        # Initial Search: Combine Text + Context
        search_query = f"{segment_text} context: {context}"
        print(f"  [Editor] Initial Query: '{search_query[:60]}...'")
    else:
        # Refined Search: Use Suggestion + Context
        suggested = state.get('suggested_query')
        if suggested:
            search_query = f"{suggested} context: {context}"
            print(f"  [Editor] Refined Query: '{search_query[:60]}...'")
        else:
            # Fallback if no suggestion
            search_query = f"{segment_text} {context}"
            print(f"  [Editor] Fallback Query: '{search_query[:60]}...'")
            
    # --- 2. Search RAG ---
    rag = get_rag()
    new_candidates = rag.query(search_query, k=5) # Fetch top 5 per round
    
    # --- 3. Accumulate & Deduplicate ---
    current_filenames = {c['filename'] for c in accumulated}
    
    for cand in new_candidates:
        if cand['filename'] not in current_filenames:
            accumulated.append(cand)
            current_filenames.add(cand['filename'])
            
    # Sort accumulated by score (descending)
    accumulated.sort(key=lambda x: x['rag_score'], reverse=True)
    
    # Filter used images
    used_list = state.get("used_images", [])
    valid_candidates = [c for c in accumulated if c['filename'] not in used_list]
    
    print(f"  [Editor] Candidates (New: {len(new_candidates)}, Total Valid: {len(valid_candidates)})")
    
    if not valid_candidates:
         print("  [Editor] No valid candidates found.")
         return {
             "critic_verdict": "SKIP",
             "selected_image": None,
             "reasoning": "No candidates found after search.",
             "accumulated_candidates": accumulated,
             "current_query": search_query
         }

    # --- 4. Evaluate (LLM) ---
    # Prepare prompt with top 10 valid candidates
    top_candidates = valid_candidates[:10]
    candidates_str = json.dumps([
        {
            "id": i,
            "filename": c['filename'],
            "description": c['description'][:200],
            "score": f"{c['rag_score']:.2f}"
        }
        for i, c in enumerate(top_candidates)
    ], indent=2)
    
    system_prompt = load_prompt(PROMPTS_DIR / "editor_agent_prompt.md")
    
    user_message = f"""
TRANSCRIPT SEGMENT: "{segment_text}"
NARRATIVE CONTEXT: "{context}"

CANDIDATE IMAGES (Ranked by Relevance):
{candidates_str}

Refinement Round: {refinement_count + 1} / 3

YOUR TASK:
1. SELECT the best image if it matches well.
2. REFINE if all images are poor matches (suggest better query).
3. SKIP if this segment is impossible to visualize nicely.

Respond in JSON.
"""

    try:
        # Use Critic Model (Gemma 3 or similar strong model)
        result = ollama_chat(system_prompt, user_message)
        
        verdict = result.get("verdict", "REFINE").upper()
        selected = result.get("selected_image")
        reasoning = result.get("reasoning", "")
        suggested_query = result.get("suggested_query", "")
        
        # Force decision on final round
        if refinement_count >= 2 and verdict == "REFINE":
            print("  [Editor] Max rounds reached. Determining fallback...")
            # If the LLM still wants to REFINE after 3 rounds, it means nothing is good.
            # We should default to SKIP to avoid forced insertions, as per user request.
            verdict = "SKIP"
            reasoning = f"Max rounds reached without a confident match. Skipping to avoid forced insertion. {reasoning}"
            selected = None
                
        print(f"  [Editor] Verdict: {verdict}")
        if verdict == "SELECT":
            print(f"  [Editor] Selected: {selected}")
        elif verdict == "REFINE":
             print(f"  [Editor] Suggestion: {suggested_query}")
             
        return {
            "critic_verdict": verdict,
            "selected_image": selected,
            "reasoning": reasoning,
            "suggested_query": suggested_query,
            "accumulated_candidates": accumulated,
            "current_query": search_query,
            "ranked_candidates": top_candidates[:3] # Return top 3 for Global Resolution
        }

    except Exception as e:
        print(f"  [Editor Error] {e}")
        return {
            "critic_verdict": "SKIP",
            "reasoning": f"Error: {e}"
        }

def increment_node(state: AgentState):
    """Increments refinement counter."""
    return {"refinement_count": state.get('refinement_count', 0) + 1}

