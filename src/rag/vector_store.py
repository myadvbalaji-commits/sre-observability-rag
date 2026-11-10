import logging
from typing import List, Dict, Any, Optional
import numpy as np

from src.config import settings
from src.rag.document_loader import Document
from src.rag.embeddings import EmbeddingService
from src.telemetry.tracer import trace_span

logger = logging.getLogger("sre_rag.vector_store")

class SREVectorStore:
    def __init__(self, persist_directory: Optional[str] = None):
        self.persist_directory = persist_directory or settings.chroma_persist_directory
        self.collection_name = settings.chroma_collection_name
        self.embedding_service = EmbeddingService()
        self.documents: Dict[str, Document] = {}
        self.embeddings: Dict[str, List[float]] = {}
        self._init_chroma()

    def _init_chroma(self):
        try:
            import chromadb
            self.chroma_client = chromadb.PersistentClient(path=self.persist_directory)
            self.collection = self.chroma_client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": "SRE Incident Postmortems and Runbooks"}
            )
            self.use_chroma = True
            logger.info(f"Initialized ChromaDB at {self.persist_directory}")
        except Exception as e:
            logger.warning(f"ChromaDB persistence initialization fallback to in-memory: {e}")
            self.use_chroma = False

    def add_documents(self, docs: List[Document]):
        with trace_span("vector_store.add_documents", {"doc.count": len(docs)}):
            if not docs:
                return

            ids = [d.doc_id for d in docs]
            texts = [d.content for d in docs]
            metas = [{k: str(v) for k, v in d.metadata.items()} for d in docs]
            embeddings = self.embedding_service.embed_documents(texts)

            for d, emb in zip(docs, embeddings):
                self.documents[d.doc_id] = d
                self.embeddings[d.doc_id] = emb

            if self.use_chroma:
                try:
                    self.collection.upsert(
                        ids=ids,
                        documents=texts,
                        metadatas=metas,
                        embeddings=embeddings
                    )
                except Exception as ex:
                    logger.warning(f"Chroma upsert failed ({ex}), retained in in-memory index.")

    def search(self, query: str, top_k: int = 3, filter_doc_type: Optional[str] = None) -> List[Dict[str, Any]]:
        with trace_span("vector_store.search", {"query": query, "top_k": top_k, "filter": str(filter_doc_type)}):
            query_emb = self.embedding_service.embed_query(query)
            
            # If Chroma is active, query Chroma
            if self.use_chroma:
                try:
                    where_clause = {"doc_type": filter_doc_type} if filter_doc_type else None
                    results = self.collection.query(
                        query_embeddings=[query_emb],
                        n_results=min(top_k, max(1, self.collection.count())),
                        where=where_clause
                    )
                    hits = []
                    if results and "ids" in results and results["ids"]:
                        for i, doc_id in enumerate(results["ids"][0]):
                            distance = results["distances"][0][i] if "distances" in results and results["distances"] else 0.0
                            similarity = 1.0 / (1.0 + distance)
                            meta = results["metadatas"][0][i] if results.get("metadatas") else {}
                            content = results["documents"][0][i] if results.get("documents") else ""
                            hits.append({
                                "doc_id": doc_id,
                                "similarity_score": round(float(similarity), 4),
                                "metadata": meta,
                                "content": content
                            })
                        return hits
                except Exception as ex:
                    logger.warning(f"Chroma query failed ({ex}). Falling back to cosine similarity.")

            # In-memory cosine similarity fallback
            scores = []
            q_arr = np.array(query_emb, dtype=np.float32)
            q_norm = np.linalg.norm(q_arr) or 1.0

            for doc_id, emb in self.embeddings.items():
                doc = self.documents.get(doc_id)
                if not doc:
                    continue
                if filter_doc_type and doc.metadata.get("doc_type") != filter_doc_type:
                    continue
                
                d_arr = np.array(emb, dtype=np.float32)
                d_norm = np.linalg.norm(d_arr) or 1.0
                cosine_sim = float(np.dot(q_arr, d_arr) / (q_norm * d_norm))
                scores.append((doc_id, cosine_sim, doc))

            scores.sort(key=lambda x: x[1], reverse=True)
            return [
                {
                    "doc_id": doc_id,
                    "similarity_score": round(float(sim), 4),
                    "metadata": doc.metadata,
                    "content": doc.content
                }
                for doc_id, sim, doc in scores[:top_k]
            ]
