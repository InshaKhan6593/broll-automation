"""
FastAPI Backend for Video Editor Application

Provides:
- File upload endpoints
- Workflow execution
- Real-time log streaming
- Video output serving
"""

import os
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.api.routes import router

from src.paths import (
    UPLOADS_DIR,
    OUTPUTS_DIR,
    DATA_ROOT
)

app = FastAPI(
    title="Video Editor API",
    description="AI-powered video editing with image overlay",
    version="1.0.0"
)

# CORS for Desktop app - Allow all origins in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api")

# Serve files from portable paths
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")
app.mount("/outputs", StaticFiles(directory=str(OUTPUTS_DIR)), name="outputs")


@app.get("/")
async def root():
    return {"message": "Video Editor API", "status": "running"}


if __name__ == "__main__":
    import uvicorn
    # Disable reload for bundled app
    is_frozen = getattr(sys, 'frozen', False)
    if is_frozen:
        # In frozen mode, pass app object directly (string import doesn't work)
        uvicorn.run(app, host="127.0.0.1", port=8000)
    else:
        uvicorn.run(
            "backend.main:app",
            host="127.0.0.1",
            port=8000,
            reload=True,
            reload_dirs=[str(PROJECT_ROOT / "backend"), str(PROJECT_ROOT / "src")],
        )
