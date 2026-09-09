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

documents = load_runbooks(Path("runbooks"))
chunks = split_runbooks(documents)

documents = load_runbooks(Path("runbooks"))
chunks = split_runbooks(documents)

sample_chunks = chunks[:3]

embedding_model = get_embedding_model()
vectors = embedding_model.embed_documents(
    [chunk.page_content for chunk in sample_chunks]
)

print("Chunks embedded:", len(vectors))

for i, vector in enumerate(vectors):
    print(
        f"Chunk {i}:",
        sample_chunks[i].metadata.get("runbook_id"),
        sample_chunks[i].metadata.get("section"),
        len(vector),
    )
