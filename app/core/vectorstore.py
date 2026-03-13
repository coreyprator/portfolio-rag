"""ChromaDB vector store with explicit OpenAI embedding generation and GCS backup/restore."""

import logging
import os
import tarfile
import tempfile

import chromadb
import openai

from app.core.config import settings

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBED_BATCH_SIZE = 100
PERSIST_DIR = "/app/chroma_data"
BACKUP_BUCKET = "portfolio-rag-backups-57478301787"
BACKUP_BLOB = "chromadb-backup/chroma_persist.tar.gz"


def _gcs_client():
    """Lazy import and create GCS client."""
    from google.cloud import storage
    return storage.Client()


def backup_to_gcs():
    """Tar the ChromaDB persist directory and upload to GCS."""
    if not os.path.isdir(PERSIST_DIR):
        logger.warning(f"Persist dir {PERSIST_DIR} not found, skipping backup")
        return False
    try:
        client = _gcs_client()
        bucket = client.bucket(BACKUP_BUCKET)
        blob = bucket.blob(BACKUP_BLOB)
        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            with tarfile.open(tmp_path, "w:gz") as tar:
                tar.add(PERSIST_DIR, arcname=os.path.basename(PERSIST_DIR))
            blob.upload_from_filename(tmp_path)
            logger.info(f"ChromaDB backed up to gs://{BACKUP_BUCKET}/{BACKUP_BLOB}")
            return True
        finally:
            os.unlink(tmp_path)
    except Exception as e:
        logger.error(f"GCS backup failed: {e}")
        return False


def restore_from_gcs() -> bool:
    """Download and restore ChromaDB backup from GCS. Returns True if restored."""
    try:
        client = _gcs_client()
        bucket = client.bucket(BACKUP_BUCKET)
        blob = bucket.blob(BACKUP_BLOB)
        if not blob.exists():
            logger.info("No GCS backup found — starting fresh")
            return False
        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            blob.download_to_filename(tmp_path)
            parent = os.path.dirname(PERSIST_DIR)
            os.makedirs(parent, exist_ok=True)
            with tarfile.open(tmp_path, "r:gz") as tar:
                tar.extractall(path=parent)
            logger.info(f"ChromaDB restored from GCS backup to {PERSIST_DIR}")
            return True
        finally:
            os.unlink(tmp_path)
    except Exception as e:
        logger.error(f"GCS restore FAILED: {e}", exc_info=True)
        return False


class VectorStore:
    def __init__(self):
        self._client = None
        self._openai = None

    def initialize(self, restored_from_gcs: bool = False):
        """Initialize ChromaDB persistent client and OpenAI client."""
        os.makedirs(PERSIST_DIR, exist_ok=True)
        self._client = chromadb.PersistentClient(path=PERSIST_DIR)
        if settings.OPENAI_API_KEY:
            self._openai = openai.OpenAI(api_key=settings.OPENAI_API_KEY.strip())
            logger.info(f"ChromaDB initialized (persist={PERSIST_DIR}). OpenAI embeddings: {EMBEDDING_MODEL}")
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

    def query(self, query_text: str, collection: str = None, max_results: int = 5,
              where: dict = None) -> list[dict]:
        """Query one or all collections using semantic search."""
        if collection:
            return self._query_collection(query_text, collection, max_results, where=where)

        all_results = []
        for coll_name in ["portfolio", "etymology", "jazz_theory", "dcc"]:
            all_results.extend(self._query_collection(query_text, coll_name, max_results))
        all_results.sort(key=lambda x: x["distance"])
        return all_results[:max_results]

    def _query_collection(self, query_text: str, coll_name: str, max_results: int,
                          where: dict = None) -> list[dict]:
        try:
            coll = self.get_or_create_collection(coll_name)
            count = coll.count()
            if count == 0:
                return []
            query_embedding = self.embed_texts([query_text])[0]
            n = min(max_results, count)
            kwargs = {"query_embeddings": [query_embedding], "n_results": n}
            if where:
                kwargs["where"] = where
            results = coll.query(**kwargs)
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

    def query_by_metadata(self, collection: str, where: dict,
                          limit: int = 50) -> list[dict]:
        """Retrieve documents by metadata filter (no embedding query needed)."""
        try:
            coll = self.get_or_create_collection(collection)
            results = coll.get(where=where, limit=limit, include=["documents", "metadatas"])
        except Exception as e:
            logger.error(f"Metadata query error on {collection}: {e}")
            return []

        formatted = []
        docs = results.get("documents", [])
        metadatas = results.get("metadatas", [])
        for doc, meta in zip(docs, metadatas):
            formatted.append({
                "text": doc,
                "metadata": meta,
                "collection": collection,
            })
        return formatted

    def collection_counts(self) -> dict:
        counts = {}
        for name in ["portfolio", "etymology", "code", "jazz_theory", "dcc", "metapm"]:
            try:
                coll = self.get_or_create_collection(name)
                counts[name] = coll.count()
            except Exception:
                counts[name] = 0
        return counts


vector_store = VectorStore()
