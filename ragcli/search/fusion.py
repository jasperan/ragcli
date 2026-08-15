"""Reciprocal Rank Fusion for hybrid search.

The hybrid engine fuses three retrieval signals -- vector similarity, BM25
full-text, and knowledge-graph traversal -- with Reciprocal Rank Fusion (RRF).
It also applies per-chunk quality scores (from the feedback loop) as a
re-ranking multiplier, so retrieval self-improves as users give feedback.
"""

from collections import defaultdict
from typing import List, Dict, Any, Optional, Set, Tuple, Collection

from ..core.embedding import generate_embedding
from ..database.vector_ops import search_similar
from .bm25 import BM25Search
from ..knowledge.graph_search import GraphSearch
from ..utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_WEIGHTS = {"bm25": 1.0, "vector": 1.0, "graph": 0.8}


def _in_binds(values: Collection[str]) -> Tuple[str, Dict[str, str]]:
    """Build an Oracle IN-clause with bind params for a list of values.

    Returns ``(in_clause, bind_params)``, e.g. ``(":id_0, :id_1", {"id_0": ...})``.
    """
    bind_names = [f":id_{i}" for i in range(len(values))]
    bind_params = {f"id_{i}": v for i, v in enumerate(values)}
    return ", ".join(bind_names), bind_params


class HybridSearch:
    """Fuse vector + BM25 + graph signals using Reciprocal Rank Fusion."""

    def __init__(self, conn, config: dict):
        self.conn = conn
        self.config = config
        search_config = config.get("search", {})
        self.k = search_config.get("rrf_k", 60)
        self.weights = search_config.get("weights", DEFAULT_WEIGHTS)
        self.strategy = search_config.get("strategy", "hybrid")
        self.bm25 = BM25Search(conn)
        self.graph_search = GraphSearch(conn, config)

    def search(
        self,
        query: str,
        top_k: int = 10,
        document_ids: Optional[List[str]] = None,
        quality_scores: Optional[Dict[str, float]] = None,
        signals: Optional[Set[str]] = None,
        min_similarity: float = 0.0,
        query_embedding: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """Run hybrid search and fuse results with RRF.

        Args:
            query: The user query.
            top_k: Number of fused results to return.
            document_ids: Optional filter to specific documents.
            quality_scores: Precomputed {chunk_id: quality_score}. When None
                and feedback is enabled, scores are loaded from CHUNK_QUALITY
                for the candidate chunk ids.
            signals: Optional subset of {"vector", "bm25", "graph"} to run.
                When None, all signals allowed by the configured strategy run.
            min_similarity: Minimum vector similarity for the vector signal.
            query_embedding: Precomputed query embedding (avoids a duplicate
                embedding call when the caller already generated one).

        Returns:
            Dict with "results" (ranked chunks with fusion_score),
            "query_embedding", and "signal_counts".
        """
        if query_embedding is None:
            query_embedding = generate_embedding(
                query, self.config["ollama"]["embedding_model"], self.config
            )

        fetch_k = top_k * 3

        # The configured strategy defines the allowed signal space; the query
        # router (if provided) may only narrow it, never widen it. If the
        # router suggests no valid signals, fall back to the strategy default.
        allowed_signals = self._default_signals()
        if signals is None:
            signals = allowed_signals
        else:
            narrowed = signals & allowed_signals
            signals = narrowed if narrowed else allowed_signals

        # Each signal is fetched independently and isolated by its own try/except:
        # a failure in one (e.g. a missing Oracle Text index for BM25) never
        # kills the others.
        fetchers = {
            "vector": lambda: search_similar(
                self.conn, query_embedding, fetch_k, min_similarity, document_ids
            ),
            "bm25": lambda: self.bm25.search(query, fetch_k, document_ids) or [],
            "graph": lambda: self.graph_search.subgraph_for_query(
                query_embedding, top_k=fetch_k, query=query
            ).get("chunk_ids", []) or [],
        }
        signal_results: Dict[str, Any] = {}
        for name in signals:
            try:
                signal_results[name] = fetchers[name]()
            except Exception as e:
                logger.warning("%s search failed, skipping signal: %s", name, e)

        vector_results = signal_results.get("vector", [])
        bm25_results = signal_results.get("bm25", [])
        graph_chunk_ids = signal_results.get("graph", [])

        scores = defaultdict(float)
        chunk_data: Dict[str, Dict[str, Any]] = {}

        for rank, chunk in enumerate(vector_results):
            cid = chunk["chunk_id"]
            scores[cid] += self.weights.get("vector", 1.0) / (self.k + rank + 1)
            chunk_data[cid] = chunk

        for rank, chunk in enumerate(bm25_results):
            cid = chunk["chunk_id"]
            scores[cid] += self.weights.get("bm25", 1.0) / (self.k + rank + 1)
            if cid not in chunk_data:
                chunk_data[cid] = chunk

        for rank, cid in enumerate(graph_chunk_ids):
            scores[cid] += self.weights.get("graph", 0.8) / (self.k + rank + 1)

        # Enrich graph-only chunks with their text so fused results never
        # surface empty context to the prompt.
        graph_only = [cid for cid in graph_chunk_ids if cid not in chunk_data]
        if graph_only:
            chunk_data.update(self._fetch_chunk_texts(graph_only))

        if quality_scores is None:
            quality_scores = self._load_quality_scores(set(scores.keys()))

        if quality_scores:
            boost_range = self.config.get("feedback", {}).get("quality_boost_range", 0.15)
            for cid in scores:
                q = quality_scores.get(cid, 0.5)
                scores[cid] *= (1.0 - boost_range + 2 * boost_range * q)

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        results = []
        for cid, score in ranked:
            data = chunk_data.get(cid, {})
            result = {
                "chunk_id": cid,
                "document_id": data.get("document_id", ""),
                "text": data.get("text", ""),
                "chunk_number": data.get("chunk_number", 0),
                "similarity_score": data.get("similarity_score", 0.0),
                "fusion_score": score,
            }
            # Preserve per-chunk embeddings for include_embeddings / heatmap
            if "embedding" in data:
                result["embedding"] = data["embedding"]
            results.append(result)

        return {
            "results": results,
            "query_embedding": query_embedding,
            "signal_counts": {
                "vector": len(vector_results),
                "bm25": len(bm25_results),
                "graph": len(graph_chunk_ids),
            },
        }

    def _default_signals(self) -> Set[str]:
        """Signals implied by the configured strategy."""
        if self.strategy == "bm25_only":
            return {"bm25"}
        if self.strategy == "vector_only":
            return {"vector"}
        return {"vector", "bm25", "graph"}

    def _load_quality_scores(self, chunk_ids: Set[str]) -> Dict[str, float]:
        """Load CHUNK_QUALITY scores for candidate chunks (feedback loop)."""
        if not chunk_ids or not self.config.get("feedback", {}).get("enabled", True):
            return {}

        in_clause, bind_params = _in_binds(chunk_ids)
        sql = (
            "SELECT chunk_id, quality_score FROM CHUNK_QUALITY "
            f"WHERE chunk_id IN ({in_clause})"
        )
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(sql, bind_params)
                rows = cursor.fetchall()
        except Exception as e:
            logger.debug("Quality score load skipped: %s", e)
            return {}

        result = {cid: 0.5 for cid in chunk_ids}
        for row in rows:
            result[row[0]] = row[1]
        return result

    def _fetch_chunk_texts(self, chunk_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Fetch text/metadata for chunks that only the graph signal found."""
        if not chunk_ids:
            return {}

        in_clause, bind_params = _in_binds(chunk_ids)
        sql = (
            "SELECT chunk_id, document_id, chunk_text, chunk_number "
            f"FROM CHUNKS WHERE chunk_id IN ({in_clause})"
        )
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(sql, bind_params)
                rows = cursor.fetchall()
        except Exception as e:
            logger.debug("Graph-only chunk enrichment skipped: %s", e)
            return {}

        result: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            text = row[2]
            if hasattr(text, "read"):  # Oracle CLOB
                text = text.read()
            result[row[0]] = {
                "chunk_id": row[0],
                "document_id": row[1],
                "text": str(text) if text else "",
                "chunk_number": row[3],
                "similarity_score": 0.0,
            }
        return result
