import os
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse

import logging

try:
    import chromadb
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

router = APIRouter()

# Standalone ChromaDB setup (lazy initialized so server startup is instantaneous)
chroma_client = None
memory_collection = None

def get_memory_collection():
    global chroma_client, memory_collection
    if not CHROMA_AVAILABLE:
        return None
    if memory_collection is not None:
        return memory_collection
    try:
        from chromadb.utils import embedding_functions
        DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/vector_store'))
        os.makedirs(DATA_DIR, exist_ok=True)
        chroma_client = chromadb.PersistentClient(path=DATA_DIR)
        emb_fn = embedding_functions.DefaultEmbeddingFunction()
        memory_collection = chroma_client.get_or_create_collection(name="andromeda_memory", embedding_function=emb_fn)
        return memory_collection
    except Exception as e:
        logging.warning(f"Failed to initialize Chroma memory collection: {e}")
        return None

@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """Ingests a document into the standalone Andromeda ChromaDB."""
    if not CHROMA_AVAILABLE:
        return JSONResponse(status_code=500, content={"error": "ChromaDB is not installed."})
        
    try:
        content = await file.read()
        text_content = content.decode('utf-8', errors='ignore')
        
        # Simple chunking logic
        chunk_size = 1000
        overlap = 200
        
        chunks = []
        start = 0
        while start < len(text_content):
            end = start + chunk_size
            chunks.append(text_content[start:end])
            start += chunk_size - overlap
            
        coll = get_memory_collection()
        if chunks and coll:
            docs = chunks
            ids = [f"{file.filename}_chunk_{i}" for i in range(len(chunks))]
            metadatas = [{"filename": file.filename}] * len(chunks)
            
            coll.upsert(documents=docs, ids=ids, metadatas=metadatas)
            
        return JSONResponse(status_code=200, content={
            "message": f"Successfully ingested {file.filename}",
            "chunks_processed": len(chunks)
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.get("/search")
async def search_memory(query: str):
    """Searches the memory ChromaDB."""
    if not CHROMA_AVAILABLE:
        return JSONResponse(status_code=500, content={"error": "ChromaDB is not installed."})
        
    try:
        results = memory_collection.query(query_texts=[query], n_results=3)
        return {"results": results}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
