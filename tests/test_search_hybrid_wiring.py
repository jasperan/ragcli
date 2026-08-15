"""End-to-end tests for hybrid search wiring and feedback-aware re-ranking.

These verify that the real query path (``similarity_search.search_chunks``)
honors the configured strategy, routes through the RRF fusion engine, applies
the query router, loads feedback quality scores, and degrades gracefully when
individual signals fail -- while the classic ``vector_only`` path is unchanged.
"""

from contextlib import ExitStack, contextmanager
from unittest.mock import MagicMock, patch

from ragcli.search.fusion import HybridSearch
from ragcli.search.router import QueryRouter
from ragcli.knowledge.graph_search import GraphSearch
from ragcli.core.similarity_search import search_chunks


def _config(**overrides):
    cfg = {
        "ollama": {"embedding_model": "nomic-embed-text", "endpoint": "http://localhost:11434", "timeout": 30},
        "vector_index": {},
        "search": {
            "strategy": "hybrid",
            "rrf_k": 60,
            "weights": {"bm25": 1.0, "vector": 1.0, "graph": 0.8},
            "use_router": True,
        },
        "knowledge_graph": {"max_hops": 2},
        "feedback": {"enabled": True, "quality_boost_range": 0.15},
    }
    for key, value in overrides.items():
        cfg[key] = value
    return cfg


def _vector_chunk(cid, rank=0):
    return {
        "chunk_id": cid,
        "document_id": "doc-1",
        "text": f"vector text {cid}",
        "chunk_number": rank + 1,
        "similarity_score": 0.9 - rank * 0.05,
    }


@contextmanager
def _patched_hybrid(conn=None, config=None, patch_quality=True):
    """Yield (hybrid, mocks) with every external boundary patched to inert defaults.

    Tests override individual ``mocks[name].return_value`` / ``side_effect``
    entries (names: embedding, vector, bm25, graph, and quality unless
    ``patch_quality=False``).
    """
    hybrid = HybridSearch(conn or MagicMock(), config or _config())
    with ExitStack() as stack:
        mocks = {
            "embedding": stack.enter_context(
                patch("ragcli.search.fusion.generate_embedding", return_value=[0.1] * 768)
            ),
            "vector": stack.enter_context(patch("ragcli.search.fusion.search_similar", return_value=[])),
            "bm25": stack.enter_context(patch.object(hybrid.bm25, "search", return_value=[])),
            "graph": stack.enter_context(
                patch.object(hybrid.graph_search, "subgraph_for_query", return_value={"chunk_ids": []})
            ),
        }
        if patch_quality:
            mocks["quality"] = stack.enter_context(patch.object(hybrid, "_load_quality_scores", return_value={}))
        yield hybrid, mocks


def _conn_with_cursor(rows=None, side_effect=None):
    """Return a connection whose cursor yields ``rows`` (or replays ``side_effect``)."""
    conn = MagicMock()
    cursor = MagicMock()
    if side_effect is not None:
        cursor.fetchall.side_effect = side_effect
    else:
        cursor.fetchall.return_value = rows
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn, cursor


def _mock_hybrid(results=None, signal_counts=None):
    """A HybridSearch-class mock whose search() returns fused results."""
    mock_hybrid = MagicMock()
    mock_hybrid.search.return_value = {
        "results": results or [],
        "query_embedding": [0.1] * 768,
        "signal_counts": signal_counts or {"vector": 0, "bm25": 0, "graph": 0},
    }
    return mock_hybrid


class TestHybridSearchFusion:

    def test_fuses_multiple_signals_with_rrf(self):
        """Vector + BM25 hits for the same chunk should outrank single-signal hits."""
        with _patched_hybrid() as (hybrid, m):
            m["vector"].return_value = [_vector_chunk("c1", 0)]
            m["bm25"].return_value = [
                {"chunk_id": "c2", "document_id": "doc-1", "text": "bm25 text", "chunk_number": 2},
                {"chunk_id": "c1", "document_id": "doc-1", "text": "vector text c1", "chunk_number": 1},
            ]
            m["graph"].return_value = {"chunk_ids": ["c3"]}

            result = hybrid.search("test query", top_k=5, signals={"vector", "bm25", "graph"})

            assert m["vector"].called
            assert m["bm25"].called
            assert m["graph"].called
            # c1 appears in vector (rank 0) + bm25 (rank 1) -> highest fused score
            assert result["results"][0]["chunk_id"] == "c1"
            assert result["signal_counts"] == {"vector": 1, "bm25": 2, "graph": 1}
            # All results carry a fusion_score
            assert all("fusion_score" in r for r in result["results"])

    def test_preserves_per_chunk_embeddings(self):
        """include_embeddings should still get chunk vectors after fusion."""
        vec_chunk = _vector_chunk("c1", 0)
        vec_chunk["embedding"] = [0.42] * 768
        with _patched_hybrid() as (hybrid, m):
            m["vector"].return_value = [vec_chunk]
            result = hybrid.search("q", top_k=5)
            assert result["results"][0]["embedding"] == [0.42] * 768

    def test_graph_only_chunks_are_enriched_with_text(self):
        """Chunks found only via the graph signal should still carry text."""
        conn, cursor = _conn_with_cursor([("g1", "doc-9", "Graph-discovered chunk text", 3)])
        with _patched_hybrid(conn=conn) as (hybrid, m):
            m["graph"].return_value = {"chunk_ids": ["g1"]}
            result = hybrid.search("q", top_k=5)
            assert "FROM CHUNKS" in cursor.execute.call_args[0][0].upper()
            assert result["results"][0]["chunk_id"] == "g1"
            assert result["results"][0]["text"] == "Graph-discovered chunk text"
            assert result["results"][0]["document_id"] == "doc-9"

    def test_quality_scores_loaded_from_db_when_not_provided(self):
        """Feedback quality scores should be loaded from CHUNK_QUALITY automatically."""
        conn, cursor = _conn_with_cursor([("c1", 0.9)])
        with _patched_hybrid(conn=conn, patch_quality=False) as (hybrid, m):
            m["vector"].return_value = [_vector_chunk("c1", 0)]
            result = hybrid.search("q", top_k=5)
            # CHUNK_QUALITY query executed
            assert "CHUNK_QUALITY" in cursor.execute.call_args[0][0]
            assert result["results"][0]["chunk_id"] == "c1"

    def test_quality_boost_changes_ranking(self):
        """A low-quality chunk should be penalized relative to a neutral one."""
        with _patched_hybrid() as (hybrid, m):
            m["vector"].return_value = [_vector_chunk("good", 0), _vector_chunk("bad", 1)]
            # Precompute quality scores: "good" boosted, "bad" penalized
            quality = {"good": 1.0, "bad": 0.0}
            result = hybrid.search("q", top_k=5, quality_scores=quality)
            ranked = [r["chunk_id"] for r in result["results"]]
            assert ranked.index("good") < ranked.index("bad")

    def test_failed_graph_signal_does_not_kill_search(self):
        """A graph crash should be isolated -- vector + BM25 still fuse."""
        with _patched_hybrid() as (hybrid, m):
            m["vector"].return_value = [_vector_chunk("c1", 0)]
            m["graph"].side_effect = RuntimeError("graph down")
            result = hybrid.search("q", top_k=5)
            assert result["results"][0]["chunk_id"] == "c1"
            assert result["signal_counts"]["graph"] == 0

    def test_failed_bm25_signal_is_isolated(self):
        with _patched_hybrid() as (hybrid, m):
            m["vector"].return_value = [_vector_chunk("c1", 0)]
            m["bm25"].side_effect = RuntimeError("no text index")
            result = hybrid.search("q", top_k=5)
            assert result["results"][0]["chunk_id"] == "c1"
            assert result["signal_counts"]["bm25"] == 0

    def test_bm25_only_strategy(self):
        """bm25_only strategy should not run vector or graph signals."""
        config = _config()
        config["search"]["strategy"] = "bm25_only"
        with _patched_hybrid(config=config) as (hybrid, m):
            m["vector"].return_value = [_vector_chunk("c1", 0)]
            m["bm25"].return_value = [
                {"chunk_id": "c2", "document_id": "doc-1", "text": "bm25", "chunk_number": 1}
            ]
            m["graph"].return_value = {"chunk_ids": ["c3"]}
            result = hybrid.search("q", top_k=5)
            assert not m["vector"].called
            assert m["bm25"].called
            assert not m["graph"].called
            assert result["results"][0]["chunk_id"] == "c2"

    def test_strategy_is_authoritative_over_router(self):
        """bm25_only strategy must win even if the router suggests other signals."""
        config = _config()
        config["search"]["strategy"] = "bm25_only"
        with _patched_hybrid(config=config) as (hybrid, m):
            m["vector"].return_value = [_vector_chunk("c1", 0)]
            m["bm25"].return_value = [
                {"chunk_id": "c2", "document_id": "doc-1", "text": "bm25", "chunk_number": 1}
            ]
            m["graph"].return_value = {"chunk_ids": ["c3"]}
            # Router would say "vector only" for a long query, but bm25_only wins
            result = hybrid.search("q", top_k=5, signals={"vector"})
            assert not m["vector"].called
            assert m["bm25"].called
            assert not m["graph"].called
            assert result["results"][0]["chunk_id"] == "c2"


class TestSearchChunksStrategy:

    def _mock_client(self, conn):
        client = MagicMock()
        client.get_connection.return_value = conn
        return client

    def test_hybrid_strategy_routes_through_fusion(self):
        """search_chunks with hybrid strategy should use HybridSearch and report signals."""
        conn = MagicMock()
        client = self._mock_client(conn)
        config = _config()

        with patch("ragcli.core.similarity_search.OracleClient", return_value=client), \
             patch("ragcli.core.similarity_search.generate_embedding", return_value=[0.1] * 768), \
             patch("ragcli.core.similarity_search.HybridSearch") as mock_hybrid_cls:

            mock_hybrid = _mock_hybrid([_vector_chunk("c1", 0)], {"vector": 1, "bm25": 1, "graph": 0})
            mock_hybrid_cls.return_value = mock_hybrid

            result = search_chunks("test query", 5, 0.5, None, config)

            mock_hybrid_cls.assert_called_once()
            assert result["results"][0]["chunk_id"] == "c1"
            assert result["metrics"]["strategy"] == "hybrid"
            assert result["metrics"]["signal_counts"] == {"vector": 1, "bm25": 1, "graph": 0}
            conn.close.assert_called_once()

    def test_router_passed_to_hybrid_search(self):
        """The query router output should reach HybridSearch as signals."""
        conn = MagicMock()
        client = self._mock_client(conn)
        config = _config()

        with patch("ragcli.core.similarity_search.OracleClient", return_value=client), \
             patch("ragcli.core.similarity_search.generate_embedding", return_value=[0.1] * 768), \
             patch("ragcli.core.similarity_search.HybridSearch") as mock_hybrid_cls:

            mock_hybrid = _mock_hybrid()
            mock_hybrid_cls.return_value = mock_hybrid

            # A short technical query should route BM25 + vector per QueryRouter
            search_chunks("ORA-12154 error", 5, 0.5, None, config)
            signals = mock_hybrid.search.call_args.kwargs["signals"]
            assert "bm25" in signals
            assert "vector" in signals

    def test_router_disabled_passes_none(self):
        """With use_router=False, HybridSearch should get signals=None (full default set)."""
        conn = MagicMock()
        client = self._mock_client(conn)
        config = _config()
        config["search"]["use_router"] = False

        with patch("ragcli.core.similarity_search.OracleClient", return_value=client), \
             patch("ragcli.core.similarity_search.generate_embedding", return_value=[0.1] * 768), \
             patch("ragcli.core.similarity_search.HybridSearch") as mock_hybrid_cls:

            mock_hybrid = _mock_hybrid()
            mock_hybrid_cls.return_value = mock_hybrid

            search_chunks("a long natural language question", 5, 0.5, None, config)
            assert mock_hybrid.search.call_args.kwargs["signals"] is None

    def test_vector_only_strategy_uses_classic_path(self):
        """vector_only should keep the classic search_similar behavior."""
        conn = MagicMock()
        client = self._mock_client(conn)
        config = _config(search={"strategy": "vector_only", "use_router": True})

        with patch("ragcli.core.similarity_search.OracleClient", return_value=client), \
             patch("ragcli.core.similarity_search.generate_embedding", return_value=[0.1] * 768), \
             patch("ragcli.core.similarity_search.search_similar", return_value=[_vector_chunk("c1", 0)]) as mock_vec, \
             patch("ragcli.core.similarity_search.HybridSearch") as mock_hybrid_cls:

            result = search_chunks("test", 5, 0.5, None, config)

            mock_vec.assert_called_once()
            mock_hybrid_cls.assert_not_called()
            assert result["metrics"]["strategy"] == "vector_only"
            assert result["results"][0]["chunk_id"] == "c1"

    def test_reuses_caller_connection(self):
        """When a conn is provided, the caller owns it (no close)."""
        conn = MagicMock()
        config = _config()

        with patch("ragcli.core.similarity_search.generate_embedding", return_value=[0.1] * 768), \
             patch("ragcli.core.similarity_search.HybridSearch") as mock_hybrid_cls:

            mock_hybrid = _mock_hybrid()
            mock_hybrid_cls.return_value = mock_hybrid

            search_chunks("q", 5, 0.5, None, config, conn=conn)
            mock_hybrid_cls.assert_called_once_with(conn, config)
            conn.close.assert_not_called()


class TestGraphSearchSchemaFixes:

    def test_find_entities_by_embedding_uses_entity_name_column(self):
        """The embedding query must select the real entity_name column."""
        conn, cursor = _conn_with_cursor([("e1", "Python", "TECHNOLOGY", 0.1)])
        gs = GraphSearch(conn, {"knowledge_graph": {"max_hops": 2}})
        results = gs.find_entities_by_embedding([0.1, 0.2, 0.3], top_k=5)

        sql = cursor.execute.call_args[0][0]
        assert "entity_name" in sql
        assert "name" not in sql.replace("entity_name", "")
        assert results[0]["name"] == "Python"

    def test_expand_entity_uses_real_relationship_columns(self):
        """_expand_entity must query source_id/target_id/rel_type (real schema)."""
        conn, cursor = _conn_with_cursor([
            ("e2", "LangChain", "TECHNOLOGY", "USES"),
            ("e3", "Oracle", "TECHNOLOGY", "DEPENDS_ON"),
        ])
        gs = GraphSearch(conn, {"knowledge_graph": {"max_hops": 2}})
        related = gs._expand_entity("e1", max_hops=1)

        sql = cursor.execute.call_args[0][0]
        assert "r.source_id" in sql
        assert "r.target_id" in sql
        assert "r.rel_type" in sql
        assert "source_entity_id" not in sql
        assert "relationship_type" not in sql
        assert related[0]["entity_id"] == "e2"
        assert related[0]["relationship"] == "USES"

    def test_expand_entity_dedups_cycles_across_hops(self):
        """A relationship discovered in an earlier hop must not be re-emitted."""
        conn, cursor = _conn_with_cursor(side_effect=[
            # Hop 1 discovers e2; hop 2 (e2 -> e1 cycle back, e2 -> e3 new)
            [("e2", "LangChain", "TECHNOLOGY", "USES")],
            [("e1", "Python", "TECHNOLOGY", "USES"), ("e3", "Oracle", "TECHNOLOGY", "DEPENDS_ON")],
        ])
        gs = GraphSearch(conn, {"knowledge_graph": {"max_hops": 2}})
        related = gs._expand_entity("e1", max_hops=2)

        ids = [r["entity_id"] for r in related]
        assert ids == ["e2", "e3"]  # e1 cycle back is suppressed
        assert len(ids) == len(set(ids))

    def test_lexical_fallback_finds_entities_without_embeddings(self):
        """find_entities_by_name should surface entities when no vectors exist."""
        conn, cursor = _conn_with_cursor([("e1", "Oracle Database", "TECHNOLOGY", 3)])
        gs = GraphSearch(conn, {"knowledge_graph": {"max_hops": 2}})
        results = gs.find_entities_by_name("oracle database tuning", top_k=5)

        sql = cursor.execute.call_args[0][0]
        assert "entity_name" in sql
        assert "LIKE" in sql
        assert results[0]["entity_id"] == "e1"
        assert results[0]["name"] == "Oracle Database"

    def test_subgraph_uses_lexical_fallback_when_embeddings_empty(self):
        """subgraph_for_query should fall back to name search when embedding search is empty."""
        conn = MagicMock()
        gs = GraphSearch(conn, {"knowledge_graph": {"max_hops": 2}})

        with patch.object(gs, "find_entities_by_embedding", return_value=[]), \
             patch.object(gs, "find_entities_by_name", return_value=[
                 {"entity_id": "e1", "name": "Oracle", "entity_type": "TECHNOLOGY"}
             ]) as mock_name, \
             patch.object(gs, "get_chunks_for_entities", return_value=["chunk1"]):

            result = gs.subgraph_for_query([0.1] * 768, top_k=5, query="oracle database")

            mock_name.assert_called_once_with("oracle database", top_k=5)
            assert result["used_lexical_fallback"] is True
            assert result["chunk_ids"] == ["chunk1"]
            assert result["seed_count"] == 1


class TestAskQueryThroughHybridPath:
    """End-to-end: ask_query -> similarity_search.search_chunks -> HybridSearch.

    Unlike the classic battle-hardening tests (which mock _search_chunks_internal),
    this exercises the real hybrid search path with only the DB/LLM boundaries
    mocked, proving the wiring works through the production call chain.
    """

    def test_ask_query_runs_hybrid_search_and_reports_signals(self):
        from ragcli.core.rag_engine import ask_query

        # --- Database boundary -------------------------------------------------
        conn, cursor = _conn_with_cursor(side_effect=[
            # Vector search returns one chunk; CHUNK_QUALITY query returns one row
            [("chunk-1", "doc-1", "Retrieval chunk text about Oracle AI.", 1, 0.12, [0.1] * 768)],
            [("chunk-1", 0.9)],
        ])
        cursor.fetchone.side_effect = [None]
        client = MagicMock()
        client.get_connection.return_value = conn

        config = {
            "rag": {"top_k": 5, "min_similarity_score": 0.5},
            "ollama": {
                "chat_model": "gemma3", "embedding_model": "nomic-embed-text",
                "endpoint": "http://localhost:11434", "timeout": 30,
            },
            "vector_index": {"dimension": 768},
            "search": {"strategy": "hybrid", "rrf_k": 60, "use_router": True},
            "knowledge_graph": {"max_hops": 2},
            "feedback": {"enabled": True, "quality_boost_range": 0.15},
            "memory": {"max_recent_turns": 5, "summarize_every": 5},
        }

        with patch("ragcli.core.rag_engine.OracleClient", return_value=client), \
             patch("ragcli.core.similarity_search.generate_embedding", return_value=[0.1] * 768), \
             patch("ragcli.core.similarity_search.HybridSearch") as mock_hybrid_cls, \
             patch("ragcli.core.rag_engine.generate_response", return_value="Fused answer."), \
             patch("ragcli.core.rag_engine.log_query", return_value="q-1") as mock_log:

            mock_hybrid = MagicMock()
            mock_hybrid.search.return_value = {
                "results": [{
                    "chunk_id": "chunk-1", "document_id": "doc-1",
                    "text": "Retrieval chunk text about Oracle AI.",
                    "chunk_number": 1, "similarity_score": 0.88, "fusion_score": 0.05,
                }],
                "query_embedding": [0.1] * 768,
                "signal_counts": {"vector": 1, "bm25": 2, "graph": 1},
            }
            mock_hybrid_cls.return_value = mock_hybrid

            result = ask_query("How does Oracle AI work?", config=config)

            # The hybrid engine was constructed with the caller's connection
            mock_hybrid_cls.assert_called_once_with(conn, config)
            assert result["response"] == "Fused answer."
            assert result["results"][0]["chunk_id"] == "chunk-1"
            # Signal provenance surfaces in metrics end to end
            assert result["metrics"]["signal_counts"] == {"vector": 1, "bm25": 2, "graph": 1}
            # The query (with rewritten context) was logged
            mock_log.assert_called_once()
