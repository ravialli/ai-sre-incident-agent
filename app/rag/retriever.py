
from langchain_core.documents import Document

from app.rag.vector_store import get_runbook_vector_store

def retrieve_runbooks(query: str, k: int = 6) -> list[Document]:
    
    vector_store = get_runbook_vector_store()
    
    candidate_k = max(k * 6, 20)

    candidates = vector_store.similarity_search(query, k=candidate_k)

    return _diversify_by_runbook(documents=candidates, k=k, max_per_runbook=2)

def _diversify_by_runbook(documents: list[Document], k: int, max_per_runbook: int = 2) -> list[Document]:
    selected: list[Document] = []
    counts: dict[str, int] = {}

    for document in documents:
        runbook_id = (document.metadata.get("runbook_id") or document.metadata.get("source") or document.metadata.get("filename") or "unknown")

        count = counts.get(runbook_id, 0)

        if count >= max_per_runbook:
            continue

        selected.append(document)
        counts[runbook_id] = count + 1

        if len(selected) >= k:
            break

    return selected
