"""ChromaDB vector store with explicit OpenAI embedding generation."""

import logging

import chromadb
import openai

from app.core.config import settings

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBED_BATCH_SIZE = 100


class VectorStore:
    def __init__(self):
        self._client = None
        self._openai = None

    def initialize(self):
        """Initialize ChromaDB client and OpenAI client."""
        self._client = chromadb.Client()
        if settings.OPENAI_API_KEY:
            self._openai = openai.OpenAI(api_key=settings.OPENAI_API_KEY.strip())
            logger.info(f"ChromaDB initialized. OpenAI embeddings: {EMBEDDING_MODEL}")
        else:
            logger.warning("OPENAI_API_KEY not set. Embedding generation disabled.")

    def get_or_create_collection(self, name: str):
        if self._client is None:
            self.initialize()
        return self._client.get_or_create_collection(
            name=name, metadata={"hnsw:space": "cosine"}
        )

    def delete_collection(self, name: str):
        if self._client is None:
            return
        try:
            self._client.delete_collection(name)
        except Exception:
            pass

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts using OpenAI API."""
        if not self._openai:
            raise RuntimeError("OpenAI client not initialized (OPENAI_API_KEY missing)")
        all_embeddings = []
        for i in range(0, len(texts), EMBED_BATCH_SIZE):
            batch = texts[i : i + EMBED_BATCH_SIZE]
            response = self._openai.embeddings.create(input=batch, model=EMBEDDING_MODEL)
            all_embeddings.extend([e.embedding for e in response.data])
        return all_embeddings

    def upsert(self, collection_name: str, ids: list[str], documents: list[str],
               metadatas: list[dict]) -> int:
        """Embed documents and upsert into a collection. Returns chunk count."""
        collection = self.get_or_create_collection(collection_name)
        embeddings = self.embed_texts(documents)
        batch_size = 500
        for start in range(0, len(ids), batch_size):
            end = start + batch_size
            collection.upsert(
                ids=ids[start:end],
                documents=documents[start:end],
                metadatas=metadatas[start:end],
                embeddings=embeddings[start:end],
            )
        return len(ids)

    def query(self, query_text: str, collection: str = None, max_results: int = 5) -> list[dict]:
        """Query one or all collections using semantic search."""
        if collection:
            return self._query_collection(query_text, collection, max_results)

        all_results = []
        for coll_name in ["portfolio", "etymology"]:
            all_results.extend(self._query_collection(query_text, coll_name, max_results))
        all_results.sort(key=lambda x: x["distance"])
        return all_results[:max_results]

    def _query_collection(self, query_text: str, coll_name: str, max_results: int) -> list[dict]:
        try:
            coll = self.get_or_create_collection(coll_name)
            count = coll.count()
            if count == 0:
                return []
            query_embedding = self.embed_texts([query_text])[0]
            n = min(max_results, count)
            results = coll.query(query_embeddings=[query_embedding], n_results=n)
        except Exception as e:
            logger.error(f"Query error on collection {coll_name}: {e}")
            return []

        formatted = []
        docs = results.get("documents", [[]])[0]
        distances = results.get("distances", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        for doc, dist, meta in zip(docs, distances, metadatas):
            formatted.append({
                "text": doc,
                "distance": dist,
                "score": round(max(0.0, 1.0 - dist), 4),
                "metadata": meta,
                "collection": coll_name,
            })
        return formatted

    def collection_counts(self) -> dict:
        counts = {}
        for name in ["portfolio", "etymology"]:
            try:
                coll = self.get_or_create_collection(name)
                counts[name] = coll.count()
            except Exception:
                counts[name] = 0
        return counts


vector_store = VectorStore()
