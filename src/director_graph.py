"""
Director Graph - Unified Visual Editor Workflow

Flow:
1. Editor Node (Search + Evaluate)
2. Conditional Check:
   - SELECT -> END
   - SKIP -> END
   - REFINE -> Increment -> Loop back to Editor
"""

import json
from pathlib import Path
from langgraph.graph import StateGraph, END
from src.agents import (
    AgentState, 
    editor_node, 
    increment_node,
    get_rag
)

# --- Paths ---
from src.paths import SEGMENTS_PATH, EDL_PATH
SEMANTIC_SEGMENTS_PATH = SEGMENTS_PATH
OUTPUT_EDL_PATH = EDL_PATH


# --- Conditional Edge Logic ---
def should_continue(state: AgentState):
    """Determine next step based on Editor's verdict."""
    verdict = state.get("critic_verdict", "SKIP")
    
    if verdict == "REFINE":
        return "refine"
    
    # SELECT or SKIP -> End
    return "end"


# --- Graph Construction ---
def create_workflow():
    """Build the LangGraph workflow for Unified Visual Editor."""
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("editor", editor_node)
    workflow.add_node("increment_refinement", increment_node)
    
    # Set entry point
    workflow.set_entry_point("editor")
    
    # Editor → Conditional
    workflow.add_conditional_edges(
        "editor",
        should_continue,
        {
            "end": END,
            "refine": "increment_refinement"
        }
    )
    
    # Increment → Editor (loop back)
    workflow.add_edge("increment_refinement", "editor")
    
    return workflow.compile()


def resolve_conflicts(segment_results):
    """
    Global Optimization: Resolve image conflicts by prioritizing higher relevance scores.
    Two-Pass Strategy to prevent greedy consumption of best images.
    """
    print("\n" + "=" * 60)
    print("  PHASE 2: GLOBAL OPTIMIZATION (Resolving Conflicts)")
    print("=" * 60)
    
    final_edits = []
    used_images = set()
    
    # 1. Collect all valid bids: {image_filename: [(segment_index, score, reasoning, segment_data)]}
    image_bids = {}
    
    for res in segment_results:
        idx = res['index']
        candidates = res['candidates'] # List of {filename, score, reasoning} (assuming score is present)
        
        if not candidates:
            continue
            
        # We only care about the top choice initially, but we keep backups
        top = candidates[0] 
        img = top['filename']
        
        # Parse score (handle string/float)
        try:
            score = float(top.get('score', 0))
        except:
            score = 0
            
        if img not in image_bids:
            image_bids[img] = []
        
        image_bids[img].append({
            'seg_index': idx,
            'score': score,
            'reasoning': top.get('reasoning', ''),
            'segment_data': res['segment_data'],
            'candidates': candidates # Keep full list for fallback
        })

    # 2. Iterate segments to assign best available images
    # We sort all segments by their "need" (score of their top pick) to prioritize stronger matches?
    # Or we iterate images and give to highest bidder?
    # Better: Iterate Images and assign to highest bidder. 
    # But if a segment loses, it needs to bid on its next choice.
    
    # Let's use a simpler approach: 
    # Sort all Bids by Score (Global Priority Queue). 
    # Attempt to fulfill highest score bids first.
    
    all_bids = []
    for img, bids in image_bids.items():
        for bid in bids:
            all_bids.append({
                'image': img,
                'score': bid['score'],
                'seg_index': bid['seg_index'],
                'bid_data': bid
            })
            
    # Sort by Score Descending
    all_bids.sort(key=lambda x: x['score'], reverse=True)
    
    assigned_segments = set()
    
    for bid in all_bids:
        seg_idx = bid['seg_index']
        img = bid['image']
        
        if seg_idx in assigned_segments:
            continue # This segment already got its best available match
            
        if img in used_images:
            # Conflict! This image was taken by a higher scoring bid.
            # We need to check this segment's next candidates.
            # (In this simplified view, we just try to find next available from its list)
            
            candidates = bid['bid_data']['candidates']
            found_fallback = False
            
            for cand in candidates[1:]: # Skip the first one we just lost
                alt_img = cand['filename']
                if alt_img not in used_images:
                    # Found a valid backup!
                    print(f"  [Resolve] Segment {seg_idx} lost '{img}' but found backup '{alt_img}'.")
                    final_edits.append({
                        "start_time": bid['bid_data']['segment_data']['start'],
                        "end_time": bid['bid_data']['segment_data']['end'],
                        "image": alt_img,
                        "reasoning": f"(Fallback) {cand.get('reasoning', '')}",
                        "text_context": bid['bid_data']['segment_data']['text']
                    })
                    used_images.add(alt_img)
                    assigned_segments.add(seg_idx)
                    found_fallback = True
                    break
            
            if not found_fallback:
                 print(f"  [Resolve] Segment {seg_idx} lost '{img}' and found NO valid backups. SKIPPED.")
            
            continue

        # No Conflict
        print(f"  [Assign] Segment {seg_idx} wins '{img}' (Score: {bid['score']})")
        final_edits.append({
            "start_time": bid['bid_data']['segment_data']['start'],
            "end_time": bid['bid_data']['segment_data']['end'],
            "image": img,
            "reasoning": bid['bid_data']['reasoning'],
            "text_context": bid['bid_data']['segment_data']['text']
        })
        used_images.add(img)
        assigned_segments.add(seg_idx)

    # Sort edits by time
    final_edits.sort(key=lambda x: x['start_time'])
    return final_edits


def main():
    print("=" * 60)
    print("  VISUAL EDITOR GRAPH - Context-Aware Search & Select")
    print("=" * 60)
    
    # 1. Load Semantic Segments
    if not SEMANTIC_SEGMENTS_PATH.exists():
        print(f"Error: {SEMANTIC_SEGMENTS_PATH} not found.")
        print("Run: python -m src.create_segments")
        return

    with open(SEMANTIC_SEGMENTS_PATH, "r", encoding="utf-8") as f:
        segments = json.load(f)

    print(f"Loaded {len(segments)} semantic segments.\n")
    
    # 2. Initialize RAG
    print("[System] Initializing RAG/ChromaDB...")
    rag = get_rag()
    
    # 3. Initialize Graph
    app = create_workflow()
    
    # 4. PHASE 1: Assessment (Collect Candidates)
    segment_results = []
    
    for i, seg in enumerate(segments):
        start_t = seg.get('start_time', 0)
        end_t = seg.get('end_time', 0)
        text_content = seg.get('text', '')
        context = seg.get('context', '')
        
        print(f"\n{'-' * 60}")
        print(f"SEGMENT {i}: {text_content[:60]}...")
        if context:
            print(f"Context: {context[:60]}...")
        print(f"{'-' * 60}")
        
        # Build initial state
        initial_state = {
            "transcript_segment": {
                "id": i,
                "start": start_t,
                "end": end_t,
                "text": text_content,
                "context": context
            },
            "current_query": "",
            "all_candidates": [],
            "accumulated_candidates": [],
            "selected_image": None,
            "reasoning": "",
            "critic_verdict": None,
            "suggested_query": None,
            "refinement_count": 0,
            "used_images": [] # Pass empty list so it doesn't filter prematurely
        }
        
        try:
            # Run the graph
            final_state = app.invoke(initial_state)
            
            verdict = final_state.get("critic_verdict")
            ranked = final_state.get("ranked_candidates", [])
            
            # Use 'selected_image' as primary if ranked is empty (backward compatibility)
            selected_img = final_state.get("selected_image")
            
            candidates_payload = []
            
            if verdict == "SELECT":
                # If ranked list exists, use it. Else create from selected.
                if ranked:
                    # Reformatted for resolver
                    for r in ranked:
                         candidates_payload.append({
                             "filename": r['filename'],
                             "score": r.get('score', r.get('rag_score', 0)), # Handle both
                             "reasoning": final_state.get("reasoning", "") # Shared reasoning
                         })
                elif selected_img:
                    candidates_payload.append({
                        "filename": selected_img,
                        "score": 100, # Assume high confidence if single select
                        "reasoning": final_state.get("reasoning", "")
                    })
            
            if candidates_payload:
                print(f"  [OK] Candidates found: {len(candidates_payload)}")
                segment_results.append({
                    "index": i,
                    "segment_data": initial_state["transcript_segment"],
                    "candidates": candidates_payload
                })
            else:
                print(f"  [SKIP] No candidates")
                
        except Exception as e:
            print(f"  [Error] Failed to process segment {i}: {e}")
            import traceback
            traceback.print_exc()

    # 5. PHASE 2: Global Resolution
    final_edits = resolve_conflicts(segment_results)

    # 6. Save EDL
    with open(OUTPUT_EDL_PATH, "w", encoding="utf-8") as f:
        json.dump(final_edits, f, indent=2)
    
    print("\n" + "=" * 60)
    print(f"  COMPLETE: {len(final_edits)} image edits saved to {OUTPUT_EDL_PATH}")
    print("=" * 60)
