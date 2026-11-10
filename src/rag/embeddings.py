import hashlib
import logging
from typing import List
import numpy as np

from src.config import settings
from src.telemetry.tracer import trace_span

logger = logging.getLogger("sre_rag.embeddings")

class EmbeddingService:
    def __init__(self):
        self.api_key = settings.gemini_api_key
        self.model = settings.gemini_embedding_model
        self._init_google_genai()

    def _init_google_genai(self):
        if self.api_key and self.api_key != "your_gemini_api_key_here":
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.has_genai = True
                logger.info(f"Initialized Google Gemini embedding client with model {self.model}")
            except Exception as e:
                logger.warning(f"Failed to initialize Google GenAI embeddings: {e}")
                self.has_genai = False
        else:
            self.has_genai = False
            logger.info("No Gemini API key supplied; using deterministic local embedding fallback.")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        with trace_span("rag.embeddings.batch", {"batch.size": len(texts), "model": self.model}):
            if self.has_genai:
                try:
                    import google.generativeai as genai
                    results = []
                    for text in texts:
                        res = genai.embed_content(
                            model=self.model,
                            content=text,
                            task_type="retrieval_document"
                        )
                        results.append(res["embedding"])
                    return results
                except Exception as ex:
                    logger.warning(f"Google GenAI embedding call failed ({ex}). Falling back to local vectors.")
            
            return [self._local_fallback_embed(t) for t in texts]

    def embed_query(self, query: str) -> List[float]:
        with trace_span("rag.embeddings.query", {"query.length": len(query), "model": self.model}):
            if self.has_genai:
                try:
                    import google.generativeai as genai
                    res = genai.embed_content(
                        model=self.model,
                        content=query,
                        task_type="retrieval_query"
                    )
                    return res["embedding"]
                except Exception as ex:
                    logger.warning(f"Google GenAI query embedding failed ({ex}). Falling back.")
            return self._local_fallback_embed(query)

    @staticmethod
    def _local_fallback_embed(text: str, dim: int = 768) -> List[float]:
        """Deterministic 768-dim pseudo-semantic vector embedding for testing & zero-dependency local runs."""
        words = text.lower().split()
        vec = np.zeros(dim, dtype=np.float32)
        for w in words:
            h = int(hashlib.md5(w.encode("utf-8")).hexdigest(), 16)
            idx = h % dim
            sign = 1.0 if (h // dim) % 2 == 0 else -1.0
            vec[idx] += sign
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec.tolist()
