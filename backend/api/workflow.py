"""
Workflow Orchestration Service

Handles the full video editing pipeline:
1. Caption images (with caching)
2. Reset ChromaDB and create embeddings
3. Transcribe video
4. Create semantic segments
5. Run Director-Critic workflow
6. Render final video
"""

import os
import json
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from backend.services.logging import logger
from backend.services.caption import process_images

from src.paths import (
    CHROMA_DB_PATH,
    IMAGE_INDEX_PATH,
    TRANSCRIPT_PATH,
    SEGMENTS_PATH,
    EDL_PATH,
    OUTPUTS_DIR
)


class WorkflowState:
    """Track workflow execution state."""

    def __init__(self):
        self.status = "idle"  # idle, running, completed, failed, cancelled
        self.current_step = ""
        self.progress = 0
        self.error = None
        self.output_video = None
        self.started_at = None
        self.completed_at = None
        self.cancel_requested = False

    def to_dict(self):
        return {
            "status": self.status,
            "current_step": self.current_step,
            "progress": self.progress,
            "error": self.error,
            "output_video": self.output_video,
            "started_at": self.started_at,
            "completed_at": self.completed_at
        }


# Global workflow state
workflow_state = WorkflowState()


def _force_delete_dir(dir_path: Path):
    """Delete a directory file-by-file as fallback when shutil.rmtree fails."""
    for root, dirs, files in os.walk(str(dir_path), topdown=False):
        for name in files:
            file_path = Path(root) / name
            try:
                file_path.unlink()
            except PermissionError:
                # Mark writable then delete
                import stat
                file_path.chmod(stat.S_IWRITE)
                file_path.unlink()
        for name in dirs:
            try:
                (Path(root) / name).rmdir()
            except Exception:
                pass
    try:
        dir_path.rmdir()
    except Exception:
        pass


def reset_chroma_db():
    """Reset ChromaDB by deleting the collection via API (avoids Windows file locks)."""
    logger.set_step("Reset Vector Database")

    import chromadb
    from src.rag import COLLECTION_NAME

    # 1. Release RAG instance so it doesn't hold stale references
    try:
        from src.agents import reset_rag
        reset_rag()
    except Exception:
        pass

    # 2. Delete collection via ChromaDB API (no file locks!)
    try:
        client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
        try:
            client.delete_collection(COLLECTION_NAME)
            logger.success("ChromaDB collection cleared")
        except Exception:
            # Collection doesn't exist or already empty - that's fine
            logger.info("ChromaDB collection already empty")
        return
    except Exception as e:
        # If ChromaDB client itself fails (corruption), fall back to directory deletion
        logger.warning(f"ChromaDB API reset failed ({e}), trying file deletion...")
        import gc
        gc.collect()
        gc.collect()

        if CHROMA_DB_PATH.exists():
            import time
            for attempt in range(5):
                try:
                    shutil.rmtree(CHROMA_DB_PATH)
                    logger.success("ChromaDB directory deleted")
                    return
                except (PermissionError, OSError):
                    time.sleep(1.0 * (attempt + 1))

            # Last resort: file-by-file
            _force_delete_dir(CHROMA_DB_PATH)

        logger.info("ChromaDB reset complete (fallback)")


def create_embeddings_for_images(captions: List[dict], openai_key: str = None):
    """Create embeddings in ChromaDB directly from the provided captions list.

    Does NOT overwrite image_index.json - that file is the persistent caption cache
    managed by the caption service.
    """
    logger.set_step("Create Embeddings")

    import chromadb
    from chromadb.utils import embedding_functions
    from src.rag import COLLECTION_NAME

    logger.info(f"Creating embeddings for {len(captions)} images")

    if openai_key:
        os.environ["OPENAI_API_KEY"] = openai_key

    api_key = openai_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise Exception("OPENAI_API_KEY not found, needed for embeddings")

    # Create ChromaDB client and collection
    client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
    ef = embedding_functions.OpenAIEmbeddingFunction(
        api_key=api_key,
        model_name="text-embedding-3-small"
    )
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef
    )

    # Build batch data from captions
    ids = []
    documents = []
    metadatas = []

    for cap in captions:
        filename = cap.get("filename", "")
        description = cap.get("description", "")
        if not filename or not description:
            continue
        ids.append(filename)
        documents.append(description)
        metadatas.append({
            "filename": filename,
            "description": description[:1000]
        })

    if not ids:
        logger.warning("No valid captions to embed")
        return

    # Add in batches
    batch_size = 100
    for i in range(0, len(ids), batch_size):
        collection.add(
            ids=ids[i:i+batch_size],
            documents=documents[i:i+batch_size],
            metadatas=metadatas[i:i+batch_size]
        )

    logger.success(f"Created embeddings for {len(ids)} images")


def transcribe_video(video_path: Path, groq_key: str = None):
    """Run transcription on the video."""
    logger.set_step("Transcribe Video")
    
    logger.info(f"Transcribing: {video_path.name}")
    
    try:
        if groq_key:
            os.environ["GROQ_API_KEY"] = groq_key
            
        from src.transcribe import main as transcribe_main
        transcribe_main(video_path)
        
        logger.success("Transcription complete")
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise


def create_segments(ollama_key: str = None):
    """Create semantic segments from transcript."""
    logger.set_step("Create Segments")
    
    logger.info("Running semantic segmentation...")
    
    try:
        if ollama_key:
            os.environ["OLLAMA_API_KEY"] = ollama_key
            
        from src.create_segments import create_segments as run_create_segments
        run_create_segments()
        logger.success("Segments created successfully")
    except Exception as e:
        logger.error(f"Segment creation failed: {e}")
        raise


def run_director_critic(ollama_key: str = None):
    """Run the Director-Critic workflow."""
    logger.set_step("Image Selection")
    
    logger.info("Running Director-Critic workflow...")
    
    try:
        if ollama_key:
            os.environ["OLLAMA_API_KEY"] = ollama_key
            
        from src.director_graph import main as run_director_graph
        run_director_graph()
        logger.success("Image selection complete")
    except Exception as e:
        logger.error(f"Director-Critic workflow failed: {e}")
        raise


def render_video(video_path: Path, images_dir: Path) -> Path:
    """Render the final video with FFmpeg."""
    logger.set_step("Render Video")
    
    logger.info("Rendering video with image overlays...")
    
    # Generate output filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"output_{timestamp}.mp4"
    output_path = OUTPUTS_DIR / output_filename
    
    try:
        # Update render module paths and run
        from src.render_video import render_with_ffmpeg
        import src.render_video as render_module
        
        # Save original paths
        original_video = render_module.VIDEO_PATH
        original_images = render_module.IMAGES_DIR
        original_output = render_module.OUTPUT_PATH
        
        # Set new paths
        render_module.VIDEO_PATH = video_path
        render_module.IMAGES_DIR = images_dir
        render_module.OUTPUT_PATH = output_path
        
        render_with_ffmpeg()
        
        # Restore originals
        render_module.VIDEO_PATH = original_video
        render_module.IMAGES_DIR = original_images
        render_module.OUTPUT_PATH = original_output
        
        if output_path.exists():
            logger.success(f"Video rendered: {output_filename}")
            return output_path
        else:
            raise Exception("Output video not created")
            
    except Exception as e:
        logger.error(f"Video rendering failed: {e}")
        raise


class WorkflowCancelled(Exception):
    """Raised when user cancels the workflow."""
    pass


def _check_cancelled():
    """Check if cancel was requested and raise if so."""
    if workflow_state.cancel_requested:
        raise WorkflowCancelled("Workflow cancelled by user")


def run_workflow(
    video_path: Path,
    image_paths: List[Path],
    images_dir: Path,
    api_keys: dict = None
) -> Optional[Path]:
    """
    Run the complete video editing workflow.
    """
    global workflow_state

    # Initialize keys
    keys = api_keys or {}
    groq_key = keys.get("groq_api_key")
    ollama_key = keys.get("ollama_api_key")
    openai_key = keys.get("openai_api_key")
    ollama_host = keys.get("ollama_host")

    # Set host environment variable if provided
    if ollama_host:
        os.environ["OLLAMA_HOST"] = ollama_host

    # Initialize state
    workflow_state.status = "running"
    workflow_state.cancel_requested = False
    workflow_state.started_at = datetime.now().isoformat()
    workflow_state.error = None
    workflow_state.output_video = None

    # Clear logs
    logger.clear()
    logger.info("=" * 50)
    logger.info("STARTING WORKFLOW")
    logger.info("=" * 50)
    logger.info(f"Video: {video_path.name}")
    logger.info(f"Images: {len(image_paths)} files")

    try:
        # Step 1: Caption images
        workflow_state.current_step = "Captioning"
        workflow_state.progress = 10
        captions = process_images(image_paths, ollama_key=ollama_key)

        if not captions:
            raise Exception("No captions generated")

        _check_cancelled()

        # Step 2: Embeddings
        workflow_state.current_step = "Embeddings"
        workflow_state.progress = 25
        reset_chroma_db()
        create_embeddings_for_images(captions, openai_key=openai_key)

        _check_cancelled()

        # Step 3: Transcription
        workflow_state.current_step = "Transcription"
        workflow_state.progress = 40
        transcribe_video(video_path, groq_key=groq_key)

        _check_cancelled()

        # Step 4: Segmentation
        workflow_state.current_step = "Segmentation"
        workflow_state.progress = 55
        create_segments(ollama_key=ollama_key)

        _check_cancelled()

        # Step 5: Selection
        workflow_state.current_step = "Selection"
        workflow_state.progress = 70
        run_director_critic(ollama_key=ollama_key)

        _check_cancelled()

        # Step 6: Rendering
        workflow_state.current_step = "Rendering"
        workflow_state.progress = 85
        output_path = render_video(video_path, images_dir)

        # Complete
        workflow_state.status = "completed"
        workflow_state.progress = 100
        workflow_state.current_step = "Complete"
        workflow_state.output_video = output_path.name
        workflow_state.completed_at = datetime.now().isoformat()

        logger.info("=" * 50)
        logger.success("WORKFLOW COMPLETE")
        logger.info("=" * 50)

        return output_path

    except WorkflowCancelled:
        workflow_state.status = "cancelled"
        workflow_state.completed_at = datetime.now().isoformat()
        logger.warning("WORKFLOW CANCELLED BY USER")
        return None

    except Exception as e:
        workflow_state.status = "failed"
        error_msg = str(e)
        workflow_state.error = error_msg
        workflow_state.completed_at = datetime.now().isoformat()

        logger.error("-" * 50)
        logger.error(f"WORKFLOW CRITICAL FAILURE: {error_msg}")
        logger.error("-" * 50)

        import traceback
        traceback.print_exc()

        return None


def get_workflow_status() -> dict:
    """Get current workflow status."""
    return workflow_state.to_dict()
