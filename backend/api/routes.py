"""
API Routes for Video Editor

Endpoints:
- POST /upload/video - Upload source video
- POST /upload/images - Upload multiple images
- GET /images - List uploaded images with caption status
- POST /workflow/start - Start the workflow
- GET /workflow/status - Get workflow status
- GET /workflow/logs - Get workflow logs (SSE stream)
- GET /output/video - Get output video info
"""

import os
import json
import asyncio
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel

from backend.services.logging import logger
from backend.api.workflow import run_workflow, get_workflow_status, workflow_state

router = APIRouter()

from src.paths import (
    UPLOADS_VIDEO_DIR as VIDEO_DIR,
    UPLOADS_IMAGES_DIR as IMAGES_DIR,
    OUTPUTS_DIR,
    IMAGE_INDEX_PATH,
    TRANSCRIPT_PATH,
    SEGMENTS_PATH,
    EDL_PATH,
    CHROMA_DB_PATH,
)


# --- Models ---

class UploadResponse(BaseModel):
    filename: str
    size: int
    path: str


class ImageInfo(BaseModel):
    filename: str
    has_caption: bool
    caption_preview: str = ""


class WorkflowStartRequest(BaseModel):
    groq_api_key: Optional[str] = None
    ollama_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    ollama_host: Optional[str] = None


class WorkflowResponse(BaseModel):
    status: str
    message: str


# --- Upload Endpoints ---

@router.post("/upload/video", response_model=UploadResponse)
async def upload_video(file: UploadFile = File(...)):
    """Upload source video file."""
    
    # Clear existing videos
    for existing in VIDEO_DIR.iterdir():
        existing.unlink()
    
    # Save new video
    file_path = VIDEO_DIR / file.filename
    
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    return UploadResponse(
        filename=file.filename,
        size=len(content),
        path=f"/uploads/video/{file.filename}"
    )


@router.post("/upload/images")
async def upload_images(files: List[UploadFile] = File(...)):
    """Upload multiple image files."""
    
    results = []
    
    for file in files:
        # Only accept images
        if not file.content_type or not file.content_type.startswith("image/"):
            continue
        
        file_path = IMAGES_DIR / file.filename
        
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        results.append(UploadResponse(
            filename=file.filename,
            size=len(content),
            path=f"/uploads/images/{file.filename}"
        ))
    
    return {"uploaded": len(results), "files": results}


@router.delete("/upload/images/{filename}")
async def delete_image(filename: str):
    """Delete an uploaded image."""
    file_path = IMAGES_DIR / filename
    
    if file_path.exists():
        file_path.unlink()
        return {"deleted": filename}
    
    raise HTTPException(status_code=404, detail="Image not found")


@router.delete("/upload/images")
async def clear_images():
    """Clear all uploaded images."""
    count = 0
    for file in IMAGES_DIR.iterdir():
        file.unlink()
        count += 1
    
    return {"deleted": count}


# --- Image Info ---

@router.get("/images")
async def list_images():
    """List uploaded images with caption status."""
    
    # Load existing captions
    captions = {}
    if IMAGE_INDEX_PATH.exists():
        with open(IMAGE_INDEX_PATH, "r", encoding="utf-8") as f:
            for item in json.load(f):
                captions[item["filename"]] = item.get("description", "")
    
    # List uploaded images
    images = []
    for file_path in IMAGES_DIR.iterdir():
        if file_path.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]:
            filename = file_path.name
            has_caption = filename in captions
            caption_preview = captions.get(filename, "")[:100] if has_caption else ""
            
            images.append({
                "filename": filename,
                "has_caption": has_caption,
                "caption_preview": caption_preview,
                "path": f"/uploads/images/{filename}"
            })
    
    return {
        "count": len(images),
        "cached_captions": len([i for i in images if i["has_caption"]]),
        "images": images
    }


# --- Workflow ---

@router.post("/workflow/start")
async def start_workflow(
    request: WorkflowStartRequest, 
    background_tasks: BackgroundTasks
):
    """Start the video editing workflow."""
    
    # Check if already running
    if workflow_state.status == "running":
        raise HTTPException(status_code=400, detail="Workflow already running")
    
    # Get video
    videos = list(VIDEO_DIR.iterdir())
    if not videos:
        raise HTTPException(status_code=400, detail="No video uploaded")
    
    video_path = videos[0]
    
    # Get images
    image_paths = [
        p for p in IMAGES_DIR.iterdir() 
        if p.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]
    ]
    
    if not image_paths:
        raise HTTPException(status_code=400, detail="No images uploaded")
    
    # Run workflow in background
    background_tasks.add_task(
        run_workflow, 
        video_path, 
        image_paths,
        IMAGES_DIR,
        api_keys=request.dict()
    )
    
    return {"status": "started", "message": "Workflow started in background"}


@router.get("/workflow/status")
async def workflow_status():
    """Get current workflow status."""
    return get_workflow_status()


@router.get("/workflow/logs")
async def workflow_logs_stream():
    """Stream workflow logs via Server-Sent Events."""
    
    async def event_generator():
        queue = logger.subscribe()
        
        try:
            # First send all existing logs
            for log in logger.get_logs():
                yield f"data: {json.dumps({'type': 'log', 'data': log})}\n\n"
            
            # Then stream new logs
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield f": keepalive\n\n"
                    
        except asyncio.CancelledError:
            pass
        finally:
            logger.unsubscribe(queue)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.delete("/upload/video")
async def clear_video():
    """Clear uploaded video."""
    count = 0
    for file in VIDEO_DIR.iterdir():
        file.unlink()
        count += 1
    return {"deleted": count}


# --- Workflow ---

@router.post("/workflow/cancel")
async def cancel_workflow():
    """Cancel a running workflow. Stops cleanly between steps."""
    if workflow_state.status != "running":
        return {"status": "not_running", "message": "No workflow is running"}

    workflow_state.cancel_requested = True
    return {"status": "cancelling", "message": "Cancel requested. Workflow will stop after current step."}


@router.post("/workflow/reset")
async def reset_workflow():
    """Reset workflow state and clean up generated data.

    Keeps: image_index.json (caption cache), uploaded images.
    Deletes: transcript, segments, EDL, output videos, ChromaDB, uploaded video.
    """
    global workflow_state

    # Don't reset while workflow is running - use /workflow/cancel first
    if workflow_state.status == "running":
        raise HTTPException(status_code=400, detail="Workflow is running. Stop it first.")
    workflow_state.status = "idle"
    workflow_state.current_step = ""
    workflow_state.progress = 0
    workflow_state.error = None
    workflow_state.output_video = None
    workflow_state.started_at = None
    workflow_state.completed_at = None

    # Clear logs
    logger.clear()

    # Delete workflow data files (keep image_index.json!)
    for data_file in [TRANSCRIPT_PATH, SEGMENTS_PATH, EDL_PATH]:
        if data_file.exists():
            data_file.unlink()

    # Delete output videos (retry for Windows file locks from browser)
    if OUTPUTS_DIR.exists():
        import time
        for f in OUTPUTS_DIR.iterdir():
            for attempt in range(5):
                try:
                    f.unlink()
                    break
                except PermissionError:
                    time.sleep(0.3 * (attempt + 1))

    # Delete uploaded video
    if VIDEO_DIR.exists():
        for f in VIDEO_DIR.iterdir():
            try:
                f.unlink()
            except PermissionError:
                pass

    # Silently clear ChromaDB collection (no workflow log noise)
    try:
        import chromadb
        from src.rag import COLLECTION_NAME
        from src.agents import reset_rag
        reset_rag()
        client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
    except Exception:
        pass

    return {"status": "reset", "message": "Project reset. Captions and images preserved."}


@router.get("/workflow/logs/all")
async def get_all_logs():
    """Get all workflow logs (non-streaming)."""
    return {"logs": logger.get_logs()}


# --- Output ---

@router.get("/output/video")
async def get_output_video():
    """Get information about the output video."""
    
    status = get_workflow_status()
    
    if status["status"] != "completed" or not status["output_video"]:
        return {"available": False, "status": status["status"]}
    
    output_path = OUTPUTS_DIR / status["output_video"]
    
    if not output_path.exists():
        return {"available": False, "error": "Output file not found"}
    
    return {
        "available": True,
        "filename": status["output_video"],
        "path": f"/outputs/{status['output_video']}",
        "size": output_path.stat().st_size
    }


@router.get("/output/download/{filename}")
async def download_output(filename: str):
    """Download the output video."""
    
    file_path = OUTPUTS_DIR / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        file_path,
        media_type="video/mp4",
        filename=filename
    )
