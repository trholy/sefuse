import hashlib
import logging
import os
import re
import time
from collections import Counter
from collections.abc import Mapping
from types import SimpleNamespace
from typing import Any, Dict, List

import snowballstemmer
from stop_words import get_stop_words
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchAny,
    Modifier,
    PointStruct,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

logger = logging.getLogger(__name__)

VECTOR_DB_HOST = os.getenv('VECTOR_DB_HOST', 'qdrant')
QDRANT_PORT = int(os.environ.get('QDRANT_PORT', '6333'))
DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"
PREFETCH_LIMIT_MULTIPLIER = 5

STOPWORDS = frozenset(get_stop_words("de") + get_stop_words("en"))

_german_stemmer = snowballstemmer.stemmer("german")

BM25_K1 = float(os.getenv("BM25_K1", "1.2"))

_FUGEN_ELEMENTS = ("s", "es", "n", "en", "er", "e", "ns", "ens")
_MIN_COMPOUND_LENGTH = 10
_MIN_PART_LENGTH = 4

PAYLOAD_INDEX_FIELDS = (
    "project_uuid",
    "funding_type_keys",
    "funding_area_keys",
    "funding_location_keys",
    "eligible_applicants_keys",
)


def _bm25_saturate(tf: float, k1: float = BM25_K1) -> float:
    """Apply BM25 term-frequency saturation to a raw count.

    Sublinear weighting ensures that doubling the term count does not double
    its contribution — diminishing returns kick in quickly.

    Args:
        tf (float): Raw term frequency.
        k1 (float, default=BM25_K1): Saturation parameter. Lower values
            saturate faster; ``1.2`` is the standard BM25 default.

    Returns:
        float: Saturated term weight in the range ``(0, k1 + 1)``.
    """
    return (tf * (k1 + 1)) / (tf + k1)


def _split_compound(word: str) -> list[str]:
    """Split a German compound word into two parts at a fugen element.

    Tries every candidate split position and fugen element (``s``, ``es``,
    ``n``, ``en``, ``er``, ``e``, ``ns``, ``ens``). The most balanced split
    (closest to a 50/50 length ratio) wins. Words shorter than
    ``_MIN_COMPOUND_LENGTH`` or those without a valid split return an empty
    list.

    Args:
        word (str): Lowercased token to attempt splitting.

    Returns:
        list[str]: Two-element list ``[left, right]`` on success, or ``[]``
            if no valid split is found.
    """
    if len(word) < _MIN_COMPOUND_LENGTH:
        return []
    best = None
    best_balance = 0.0
    for i in range(_MIN_PART_LENGTH, len(word) - _MIN_PART_LENGTH + 1):
        for fugen in _FUGEN_ELEMENTS:
            end = i + len(fugen)
            if end > len(word) - _MIN_PART_LENGTH:
                continue
            if word[i:end] == fugen:
                left = word[:i]
                right = word[end:]
                balance = min(len(left), len(right)) / max(len(left), len(right))
                if balance > best_balance:
                    best_balance = balance
                    best = (left, right)
    return list(best) if best else []


class QdrantManager:
    """Manages a Qdrant collection configured for hybrid (dense + sparse) search.

    On initialisation the collection is created or migrated to the named-vector
    schema required for hybrid search. Dense vectors use cosine distance (1024 dims);
    sparse vectors use IDF-weighted BM25-style indices with German stemming and
    compound splitting. Hybrid fusion uses score-aware Convex Combination instead
    of rank-based RRF.

    Args:
        host (str, default=VECTOR_DB_HOST): Qdrant server hostname.
        port (int, default=QDRANT_PORT): Qdrant gRPC/HTTP port (typically 6333).
        collection_name (str, default="fundings"): Name of the Qdrant collection.
    """

    def __init__(
            self,
            host: str = VECTOR_DB_HOST,
            port: int = QDRANT_PORT,
            collection_name: str = "fundings"
    ):
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.client = self._init_qdrant()

    @staticmethod
    def _vectors_include_dense(vectors_config: Any) -> bool:
        """Check whether the collection already has a named dense vector config.

        Args:
            vectors_config (Any): ``config.params.vectors`` from
                ``client.get_collection()``.

        Returns:
            bool: True if a ``"dense"`` key exists in the mapping.
        """
        return isinstance(vectors_config, Mapping) and DENSE_VECTOR_NAME in vectors_config

    @staticmethod
    def _sparse_vectors_include_sparse(sparse_vectors_config: Any) -> bool:
        """Check whether the collection already has a named sparse vector config.

        Args:
            sparse_vectors_config (Any): ``config.params.sparse_vectors`` from
                ``client.get_collection()``.

        Returns:
            bool: True if a ``"sparse"`` key exists in the mapping.
        """
        return (
            isinstance(sparse_vectors_config, Mapping)
            and SPARSE_VECTOR_NAME in sparse_vectors_config
        )

    @staticmethod
    def _hybrid_collection_config() -> dict[str, Any]:
        """Return the canonical vector/sparse-vector config for a hybrid collection.

        Returns:
            dict[str, Any]: Dict with ``vectors_config`` (1024-dim cosine) and
                ``sparse_vectors_config`` (IDF-modified sparse).
        """
        return {
            "vectors_config": {
                DENSE_VECTOR_NAME: VectorParams(
                    size=1024,
                    distance=Distance.COSINE,
                )
            },
            "sparse_vectors_config": {
                SPARSE_VECTOR_NAME: SparseVectorParams(
                    modifier=Modifier.IDF,
                )
            },
        }

    def _init_qdrant(
            self,
            max_retries: int = 10,
            wait: int = 3
    ) -> QdrantClient:
        """Connect to Qdrant and ensure the collection has the hybrid-search schema.

        If the collection does not exist it is created. If it exists but lacks
        named dense or sparse vector configs it is migrated (recreated or
        updated). Payload keyword indexes are created for frequently filtered
        fields after the collection is ready.

        Args:
            max_retries (int, default=10): Connection attempts before raising.
            wait (int, default=3): Seconds between retries.

        Returns:
            QdrantClient: Connected client instance.

        Raises:
            RuntimeError: If Qdrant is unreachable after all retries.
        """
        for attempt in range(max_retries):
            try:
                client = QdrantClient(host=self.host, port=self.port)
                client.get_collections()
                logger.info("Connected to Qdrant")
                break
            except Exception as e:
                logger.warning(
                    f"Qdrant not ready,"
                    f" retrying in {wait}s... ({attempt+1}/{max_retries})"
                )
                time.sleep(wait)
        else:
            raise RuntimeError("Cannot connect to Qdrant")

        existing_collections = [c.name for c in client.get_collections().collections]
        config = self._hybrid_collection_config()

        if self.collection_name not in existing_collections:
            client.create_collection(
                collection_name=self.collection_name,
                vectors_config=config["vectors_config"],
                sparse_vectors_config=config["sparse_vectors_config"],
            )
            logger.info("Created hybrid collection %s", self.collection_name)
        else:
            collection_info = client.get_collection(self.collection_name)
            vectors_config = collection_info.config.params.vectors
            sparse_vectors_config = collection_info.config.params.sparse_vectors

            has_dense_named_vector = self._vectors_include_dense(vectors_config)
            has_sparse_named_vector = self._sparse_vectors_include_sparse(
                sparse_vectors_config
            )

            if not has_dense_named_vector:
                logger.warning(
                    "Collection %s is not configured for named dense vectors. "
                    "Recreating collection for hybrid search.",
                    self.collection_name,
                )
                client.recreate_collection(
                    collection_name=self.collection_name,
                    vectors_config=config["vectors_config"],
                    sparse_vectors_config=config["sparse_vectors_config"],
                )
            elif not has_sparse_named_vector:
                logger.info(
                    "Collection %s missing sparse vector config. Updating collection.",
                    self.collection_name,
                )
                if config["sparse_vectors_config"]:
                    client.update_collection(
                        collection_name=self.collection_name,
                        sparse_vectors_config=config["sparse_vectors_config"],
                    )
            else:
                logger.info("Collection %s already configured for hybrid search", self.collection_name)

        self._ensure_payload_indexes(client)
        return client

    def _ensure_payload_indexes(self, client: QdrantClient) -> None:
        """Create keyword payload indexes for frequently filtered fields.

        Indexes accelerate ``FilterSelector`` and ``FieldCondition`` queries
        used by ``delete_projects`` and server-side taxonomy filtering. Silently
        skips fields whose indexes already exist.

        Args:
            client (QdrantClient): Connected Qdrant client.
        """
        for field in PAYLOAD_INDEX_FIELDS:
            try:
                client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field,
                    field_schema="keyword",
                )
            except Exception:
                logger.debug("Payload index for '%s' already exists or failed", field)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Tokenize, stem, and expand text for sparse vector construction.

        Pipeline: lowercase → regex word extraction → stopword removal →
        German Snowball stemming → compound splitting (with stemming of parts).
        Compound parts are appended alongside the original stem so that both
        the full compound and its constituents contribute to the sparse vector.

        Args:
            text (str): Input text (typically a chunk with contextual header).

        Returns:
            list[str]: Stemmed and expanded tokens (may contain duplicates for
                term-frequency counting).
        """
        raw_tokens = [t for t in re.findall(r"\b\w+\b", text.lower()) if t not in STOPWORDS]
        stemmed = _german_stemmer.stemWords(raw_tokens)
        expanded = []
        for token, stem in zip(raw_tokens, stemmed):
            expanded.append(stem)
            parts = _split_compound(token)
            if parts:
                expanded.extend(_german_stemmer.stemWords(parts))
        return expanded

    @staticmethod
    def _token_to_index(token: str) -> int:
        """Map a token string to a stable 32-bit integer index via MD5 hashing.

        Args:
            token (str): Stemmed token.

        Returns:
            int: Deterministic index derived from the first 8 hex digits of
                the MD5 digest.
        """
        digest = hashlib.md5(token.encode("utf-8")).hexdigest()
        return int(digest[:8], 16)

    @classmethod
    def _build_sparse_vector(cls, text: str) -> SparseVector:
        """Build a BM25-saturated sparse vector from text.

        Tokenizes the text via ``_tokenize`` (stemming + compound splitting),
        counts term frequencies, applies BM25 saturation to each count, and
        maps tokens to stable integer indices via ``_token_to_index``.

        Hash collisions (two distinct tokens mapping to the same 32-bit index)
        are resolved by summing their BM25 values, producing a valid sparse
        vector rather than a duplicate-index error.

        Args:
            text (str): Input text to vectorize.

        Returns:
            SparseVector: Sparse vector with unique sorted indices and BM25-saturated
                values, or an empty vector when no tokens survive filtering.
        """
        token_counts = Counter(cls._tokenize(text))
        if not token_counts:
            return SparseVector(indices=[], values=[])
        merged: dict[int, float] = {}
        for token, count in token_counts.items():
            idx = cls._token_to_index(token)
            merged[idx] = merged.get(idx, 0.0) + _bm25_saturate(float(count))
        indexed_tokens = sorted(merged.items())
        indices = [index for index, _ in indexed_tokens]
        values = [value for _, value in indexed_tokens]
        return SparseVector(indices=indices, values=values)

    def insert_projects(
            self,
            embeddings: List[List[float]],
            metadata_list: List[Dict[str, Any]],
            ids: List[str],
            chunk_texts: List[str],
    ) -> None:
        """Upsert project chunks into the Qdrant collection with dense and sparse vectors.

        Each chunk is stored as an independent ``PointStruct`` whose vector dict
        contains both a dense embedding and a BM25-saturated sparse vector built
        from the enriched chunk text.

        Args:
            embeddings (List[List[float]]): Dense embedding vectors, one per chunk.
            metadata_list (List[Dict[str, Any]]): Payload dicts for each chunk.
            ids (List[str]): Deterministic UUID5 point IDs.
            chunk_texts (List[str]): Enriched chunk texts used for sparse vector
                construction (includes contextual header, without embedding prefix).
        """
        points = [
            PointStruct(
                id=str(id_),
                vector=self._build_point_vector(embedding, chunk_text),
                payload=metadata,
            )
            for embedding, metadata, id_, chunk_text in zip(
                embeddings, metadata_list, ids, chunk_texts
            )
        ]
        self.client.upsert(collection_name=self.collection_name, points=points)
        logger.info(f"Inserted {len(points)} points into {self.collection_name}")

    def delete_projects(self, project_uuids: List[str]) -> None:
        """Delete all Qdrant points belonging to the given project UUIDs.

        Performs two deletions: a ``FilterSelector`` on the ``project_uuid``
        payload field (for chunked points) and a direct point-ID deletion
        (for legacy pre-migration points). No-op for an empty list.

        Args:
            project_uuids (List[str]): Project UUIDs whose points should be
                removed from the collection.
        """
        if not project_uuids:
            return

        self.client.delete(
            collection_name=self.collection_name,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="project_uuid",
                            match=MatchAny(any=project_uuids),
                        )
                    ]
                )
            ),
        )

        self.client.delete(
            collection_name=self.collection_name,
            points_selector=project_uuids,
        )

        logger.info(
            f"Deleted points for {len(project_uuids)} projects from {self.collection_name}"
        )

    def search(
        self,
        query_vector: List[float],
        query_text: str = "",
        limit: int = 20,
        semantic_weight: float = 0.7,
    ) -> list[Any]:
        """Run hybrid search using Convex Combination (CC) fusion.

        Dispatches to one of three modes based on ``semantic_weight``:

        - ``1.0``: pure dense (cosine) search.
        - ``0.0``: pure sparse (BM25 keyword) search.
        - ``0.0 < w < 1.0``: CC fusion — dense and sparse results are fetched
          independently, min-max normalized per source, and combined as
          ``score = w * d_norm + (1-w) * s_norm``.

        Prefetch limits are scaled by ``PREFETCH_LIMIT_MULTIPLIER`` and weighted
        by ``semantic_weight``, with a floor of ``limit`` per branch.

        Args:
            query_vector (List[float]): Dense embedding of the search query.
            query_text (str, default=""): Raw query text for sparse vector
                construction.
            limit (int, default=20): Maximum number of results to return.
            semantic_weight (float, default=0.7): Blend weight — ``0.0`` is
                pure keyword, ``1.0`` is pure semantic. Clamped to ``[0, 1]``.

        Returns:
            list[Any]: Scored points (``ScoredPoint`` or ``SimpleNamespace``
                with ``.id``, ``.score``, ``.payload``), sorted by descending
                fused score.
        """
        query_text = str(query_text)
        semantic_weight = max(0.0, min(1.0, semantic_weight))

        if semantic_weight >= 1.0:
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                using=DENSE_VECTOR_NAME,
                limit=limit,
            )
            return response.points

        sparse_query = self._build_sparse_vector(query_text)

        if semantic_weight <= 0.0:
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=sparse_query,
                using=SPARSE_VECTOR_NAME,
                limit=limit,
            )
            return response.points

        total_prefetch = max(limit, limit * PREFETCH_LIMIT_MULTIPLIER)
        dense_limit = max(limit, round(total_prefetch * semantic_weight))
        sparse_limit = max(limit, round(total_prefetch * (1.0 - semantic_weight)))

        dense_response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            using=DENSE_VECTOR_NAME,
            limit=dense_limit,
        )
        sparse_response = self.client.query_points(
            collection_name=self.collection_name,
            query=sparse_query,
            using=SPARSE_VECTOR_NAME,
            limit=sparse_limit,
        )

        return self._fuse_convex_combination(
            dense_response.points,
            sparse_response.points,
            semantic_weight,
            limit,
        )

    @staticmethod
    def _fuse_convex_combination(
        dense_points: list,
        sparse_points: list,
        semantic_weight: float,
        limit: int,
    ) -> list:
        """Fuse dense and sparse results via score-aware Convex Combination.

        Each source's scores are min-max normalized independently, then combined
        as ``score = w * d_norm + (1-w) * s_norm``. Points appearing in only one
        source receive ``0.0`` for the missing component. Single-point result
        sets normalize to ``1.0``.

        Args:
            dense_points (list): Scored points from the dense (cosine) query.
            sparse_points (list): Scored points from the sparse (BM25) query.
            semantic_weight (float): Weight for the dense component.
            limit (int): Maximum number of fused results to return.

        Returns:
            list: ``SimpleNamespace`` objects with ``.id``, ``.score``, and
                ``.payload``, sorted by descending fused score, truncated to
                ``limit``.
        """
        dense_scores = {str(p.id): p.score for p in dense_points}
        sparse_scores = {str(p.id): p.score for p in sparse_points}

        point_map: dict[str, Any] = {}
        for p in dense_points:
            point_map[str(p.id)] = p
        for p in sparse_points:
            if str(p.id) not in point_map:
                point_map[str(p.id)] = p

        d_min = min(dense_scores.values()) if dense_scores else 0.0
        d_max = max(dense_scores.values()) if dense_scores else 0.0
        s_min = min(sparse_scores.values()) if sparse_scores else 0.0
        s_max = max(sparse_scores.values()) if sparse_scores else 0.0
        d_range = d_max - d_min
        s_range = s_max - s_min

        fused = []
        for pid, point in point_map.items():
            if pid in dense_scores:
                d_norm = (dense_scores[pid] - d_min) / d_range if d_range > 0 else 1.0
            else:
                d_norm = 0.0
            if pid in sparse_scores:
                s_norm = (sparse_scores[pid] - s_min) / s_range if s_range > 0 else 1.0
            else:
                s_norm = 0.0
            score = semantic_weight * d_norm + (1.0 - semantic_weight) * s_norm
            fused.append(SimpleNamespace(id=point.id, score=score, payload=point.payload))

        fused.sort(key=lambda p: p.score, reverse=True)
        return fused[:limit]

    @staticmethod
    def _build_point_vector(embedding: list[float], chunk_text: str) -> dict[str, Any]:
        """Combine a dense embedding and a chunk-text-derived sparse vector.

        Args:
            embedding (list[float]): Pre-computed dense embedding vector.
            chunk_text (str): Enriched chunk text used for sparse vector
                construction (includes contextual header).

        Returns:
            dict[str, Any]: Named-vector dict with ``"dense"`` and ``"sparse"``
                keys, ready for ``PointStruct.vector``.
        """
        return {
            DENSE_VECTOR_NAME: embedding,
            SPARSE_VECTOR_NAME: QdrantManager._build_sparse_vector(chunk_text),
        }
