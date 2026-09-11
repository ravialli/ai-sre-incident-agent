from pathlib import Path

from langchain_text_splitters import MarkdownHeaderTextSplitter
from langchain_core.documents import Document

from app.rag.runbook_loader import load_runbooks
from app.rag.embeddings import get_embedding_model

headers_to_split_on = [
    ("#", "title"),
    ("##", "section"),
    ("###", "subsection"),
]

splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=headers_to_split_on,
    strip_headers=False,
)

def split_runbooks(documents: list[Document]) -> list[Document]:
    chunks: list[Document] = []

    for document in documents:
        section_chunks = splitter.split_text(document.page_content)

        for chunk in section_chunks:
            chunk.metadata = {
                **document.metadata,
                **chunk.metadata,
            }

            chunks.append(chunk)

    return chunks
