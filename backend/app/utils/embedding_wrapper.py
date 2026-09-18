# app/utils/embedding_wrapper.py
from langchain_core.embeddings import Embeddings
from app.utils.embeddings import EmbeddingSingleton
import numpy as np


class LCEmbeddingWrapper(Embeddings):
    """
    LangChain wrapper for the embedding singleton (offline mode).
    """

    def __init__(self):
        self.model = EmbeddingSingleton.get_instance()
        print("✅ LCEmbeddingWrapper initialized (offline mode)")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of documents."""
        return [self.model.embed_query(text).tolist() for text in texts]

    def embed_query(self, text: str) -> list[float]:
        """Embed a query."""
        embedding = self.model.embed_query(text)
        if isinstance(embedding, np.ndarray):
            return embedding.tolist()
        return embedding