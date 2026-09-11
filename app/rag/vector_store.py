from langchain_chroma import Chroma
from pathlib import Path
from typing import Any

from app.config.settings import settings
from app.rag.embeddings import get_embedding_model
from app.rag.runbook_loader import load_runbooks
from app.rag.runbook_splitter import split_runbooks
from langchain_core.documents import Document
import hashlib


def build_chunk_id(chunk: Document) -> str:
    identity = "|".join([
        chunk.metadata.get("runbook_id", ""),
        chunk.metadata.get("title", ""),
        chunk.metadata.get("section", ""),
        chunk.metadata.get("subsection", ""),
        chunk.page_content,
    ])

    return hashlib.sha256(identity.encode("utf-8")).hexdigest()

def sanitize_chroma_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in metadata.items()
        if value is not None
        and value != []
    }

def get_runbook_vector_store() -> Chroma:
    embedding_model = get_embedding_model()

    return Chroma(
        collection_name=settings.rag_collection_name,
        embedding_function=embedding_model,
        persist_directory=settings.rag_persist_directory,
    )
    
    
def index_runbooks(runbooks_dir: Path) -> int:
    documents = load_runbooks(runbooks_dir)

    chunks = split_runbooks(documents)

    ids = [build_chunk_id(chunk) for chunk in chunks]
    
    chroma_chunks = [
        Document(
            page_content=chunk.page_content,
            metadata=sanitize_chroma_metadata(chunk.metadata),
        )
        for chunk in chunks
    ]


    vector_store = get_runbook_vector_store()

    vector_store.add_documents(documents=chroma_chunks, ids=ids)

    return len(chunks)