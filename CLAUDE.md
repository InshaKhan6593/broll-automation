# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Humanitarian Video Editor** - An AI-powered documentary video editor that automatically selects and overlays B-roll images on video timelines based on transcript content. Designed for El Seibo Mission's work in the Dominican Republic (Bateyes/Haitian sugarcane workers' settlements).

## Commands

### Development
```bash
# Backend (FastAPI on localhost:8000)
pip install -r requirements.txt
python -m backend.main

# Frontend (Vite dev server)
cd frontend && npm install && npm run dev

# Frontend production build
cd frontend && npm run build
```

### Desktop App (Electron)
```bash
cd desktop
npm install
npm run start          # Dev mode
npm run pack           # Package test
npm run dist           # Build NSIS installer
python bundle_backend.py  # Create PyInstaller backend binary
```

## Architecture

### Three-Layer Structure
1. **Frontend** (`/frontend`) - React 19 + Vite, communicates via REST API + SSE logs
2. **Backend** (`/backend`) - FastAPI server, orchestrates workflow pipeline
3. **Core Processing** (`/src`) - Python modules for AI/video processing

### Processing Pipeline (Sequential)
```
1. Caption Images (index_images.py) → Qwen3-VL via Ollama → image_index.json
2. Create Embeddings (rag.py) → OpenAI text-embedding-3-small → ChromaDB
3. Transcribe Video (transcribe.py) → Groq Whisper → video_transcript.json
4. Semantic Segmentation (create_segments.py) → Mistral Large 3 → semantic_segments.json
5. Image Selection (director_graph.py) → LangGraph Editor Agent → edit_decision_list.json
6. Render Video (render_video.py) → FFmpeg composition → outputs/video_timestamp.mp4
```

### LangGraph Agent Architecture (`/src/director_graph.py`, `/src/agents.py`)
- **Editor Agent**: Searches RAG for candidate images, evaluates with LLM, returns SELECT/REFINE/SKIP
- **Refinement Loop**: Up to 3 rounds per segment with query refinement
- **Conflict Resolution**: Greedy matching to prevent image reuse

### Key API Endpoints (`/backend/api/routes.py`)
- `POST /upload/video`, `POST /upload/images` - File uploads
- `POST /workflow/start` - Trigger full pipeline
- `GET /workflow/status` - Poll workflow state
- `GET /workflow/logs` - SSE stream for real-time logs

### Path Management (`/src/paths.py`)
- Dev mode: Uses project directory
- Bundled mode: Uses `%APPDATA%/HumanitarianEditor`
- Auto-creates: `uploads/`, `chroma_db/`, `temp/`, `outputs/`

## Environment Variables (`.env`)
```
OLLAMA_API_KEY=<key>
OLLAMA_HOST=https://ollama.com
OPENAI_API_KEY=<key>
GROQ_API_KEY=<key>
```

## System Prompts (`/prompts/`)
- `editor_agent_prompt.md` - Image selection logic with humanitarian context
- `segment_consolidator_prompt.md` - Merges Whisper fragments into narrative chunks
- `vision_agent_prompt.md` - Image captioning guidance

## Data Files
- `image_index.json` - Image descriptions from vision model
- `video_transcript.json` - Raw Whisper output
- `semantic_segments.json` - Consolidated narrative segments
- `edit_decision_list.json` - Final image-to-timeline assignments
