
import json
import os
import shutil
import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from src.paths import IMAGE_INDEX_PATH, CHROMA_DB_PATH
COLLECTION_NAME = "image_library"


class ImageRAG:
    def __init__(self, reset_db=False):
        # Optional Reset for Dev/Refactoring
        if reset_db and CHROMA_DB_PATH.exists():
             try:
                 shutil.rmtree(CHROMA_DB_PATH)
                 print("  [RAG] Wiped existing ChromaDB for fresh start.")
             except Exception as e:
                 print(f"  [RAG Warning] Could not wipe DB: {e}")

        # Initialize Chrome Client (Persistent)
        self.client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
        
        # Use OpenAI Embedding Function
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
             raise ValueError("OPENAI_API_KEY not found needed for Chroma Embeddings.")
             
        self.ef = embedding_functions.OpenAIEmbeddingFunction(
                api_key=api_key,
                model_name="text-embedding-3-small"
        )
        
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self.ef
        )
        
        # Hydrate if empty or just returned from reset
        if self.collection.count() == 0:
            print("ChromaDB collection empty. Hydrating from index...")
            self.hydrate_index()
        else:
            print(f"Connected to ChromaDB. Count: {self.collection.count()}")

    def hydrate_index(self):
        """Loads images from JSON and adds to Chroma."""
        if not IMAGE_INDEX_PATH.exists():
            raise FileNotFoundError(f"Index not found: {IMAGE_INDEX_PATH}")
            
        with open(IMAGE_INDEX_PATH, "r", encoding="utf-8") as f:
            images = json.load(f)
            
        ids = []
        documents = []
        metadatas = []
        
        for img in images:
            img_id = img["filename"]
            # Content to embed: Description ONLY (that's all we have now)
            text_content = img.get("description", "")
            
            ids.append(img_id)
            documents.append(text_content)
            
            # Store full metadata for retrieval
            clean_meta = {
                "filename": img["filename"],
                "description": text_content[:1000] 
            }
            metadatas.append(clean_meta)
            
        # Add in batches
        if not ids:
             print("Warning: No IDs found to hydrate.")
             return

        batch_size = 100
        for i in range(0, len(ids), batch_size):
            try:
                self.collection.add(
                    ids=ids[i:i+batch_size],
                    documents=documents[i:i+batch_size],
                    metadatas=metadatas[i:i+batch_size]
                )
            except Exception as e:
                msg = f"Vector DB Error (OpenAI/Chroma): {e}"
                print(f"ERROR: {msg}")
                if "rate_limit" in str(e).lower():
                    msg = "OpenAI API Rate Limit Reached during Embedding. Please wait and try again."
                raise Exception(msg)
        print(f"Hydrated {len(ids)} images into ChromaDB.")

    def query(self, query_text: str, k: int = 5):
        """Finds top-k images."""
        results = self.collection.query(
            query_texts=[query_text],
            n_results=k
        )
        
        # Chroma returns lists of lists (for multiple queries)
        # Parse into clean dicts
        out = []
        if not results['ids']:
            return []
            
        for i in range(len(results['ids'][0])):
            desc = results['metadatas'][0][i]['description']
            dist = results['distances'][0][i] if results['distances'] else 1.0
            
            item = {
                "filename": results['ids'][0][i],
                "description": desc,
                "rag_score": 1.0 - dist # Invert distance to score
            }
            out.append(item)
            
        return out
