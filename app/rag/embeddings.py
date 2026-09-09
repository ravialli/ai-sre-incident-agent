from langchain.embeddings import init_embeddings
from langchain_core.embeddings import Embeddings

from app.config.settings import settings

def get_embedding_model() -> Embeddings:

    return init_embeddings(
        model=settings.embedding_model,
        provider=settings.embedding_provider,
    )
