
from langchain_core.documents import Document

from app.rag.vector_store import get_runbook_vector_store

def retrieve_runbooks(query: str, k: int = 5) -> list[Document]:
    
    vector_store = get_runbook_vector_store()
    
    print("Collection count:", vector_store._collection.count())

    result = vector_store.similarity_search(query, k=k)

    print("Results returned:", len(result))
    
    return result
