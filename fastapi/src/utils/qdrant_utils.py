import hashlib
import logging
import os
import re
import time
from collections import Counter
from collections.abc import Mapping
from typing import Any, Dict, List

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    Fusion,
    FusionQuery,
    Modifier,
    PointStruct,
    Prefetch,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

logger = logging.getLogger(__name__)

VECTOR_DB_HOST = os.getenv('VECTOR_DB_HOST', 'qdrant')
QDRANT_PORT = int(os.environ.get('QDRANT_PORT', '6333'))
DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"
PREFETCH_LIMIT_MULTIPLIER = 3


class QdrantManager:
    """Manages a Qdrant collection configured for hybrid (dense + sparse) search.

    On initialisation the collection is created or migrated to the named-vector
    schema required for RRF fusion queries. Dense vectors use cosine distance (768 dims);
    sparse vectors use IDF-weighted BM25-style indices.

    Args:
        host (str, default=VECTOR_DB_HOST): Qdrant server hostname.
        port (int, default=QDRANT_PORT): Qdrant gRPC/HTTP port (typically 6333).
        collection_name (str, default="fundings"): Name of the Qdrant collection.

    Example:
        manager = QdrantManager(collection_name="fundings_german")
        manager.insert_projects(embeddings, metadata_list, ids)
        results = manager.search(query_vector, query_text="solar energy", limit=10)
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
        return isinstance(vectors_config, Mapping) and DENSE_VECTOR_NAME in vectors_config

    @staticmethod
    def _sparse_vectors_include_sparse(sparse_vectors_config: Any) -> bool:
        return (
            isinstance(sparse_vectors_config, Mapping)
            and SPARSE_VECTOR_NAME in sparse_vectors_config
        )

    @staticmethod
    def _hybrid_collection_config() -> dict[str, Any]:
        return {
            "vectors_config": {
                DENSE_VECTOR_NAME: VectorParams(
                    size=768,
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

        Retries the initial connection with linear back-off. If the collection
        does not exist it is created; if it exists but lacks named dense or
        sparse vector configs it is migrated (recreated or updated).

        Args:
            max_retries (int, default=10): Number of connection attempts before raising.
            wait (int, default=3): Seconds between retry attempts.

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
            return client

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

        return client

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Split text into lowercase word tokens using word-boundary regex.

        Args:
            text (str): Raw input text.

        Returns:
            list[str]: Lowercased tokens.
        """
        return re.findall(r"\b\w+\b", text.lower())

    @staticmethod
    def _token_to_index(token: str) -> int:
        """Map a token to a stable integer index via its MD5 hash prefix.

        Args:
            token (str): Single lowercase word token.

        Returns:
            int: Deterministic 32-bit integer derived from the first 8 hex
                digits of the token's MD5 hash.
        """
        digest = hashlib.md5(token.encode("utf-8")).hexdigest()
        return int(digest[:8], 16)

    @classmethod
    def _build_sparse_vector(cls, text: str) -> SparseVector:
        """Build a sparse vector from term-frequency counts of the input text.

        Tokenises the text, counts occurrences, maps each token to a stable
        integer index via ``_token_to_index``, and returns a ``SparseVector``
        suitable for BM25-style retrieval in Qdrant.

        Args:
            text (str): Raw text to vectorise.

        Returns:
            SparseVector: Sparse vector with hashed token indices and
                term-frequency values. Empty when the text yields no tokens.
        """
        token_counts = Counter(cls._tokenize(text))
        if not token_counts:
            return SparseVector(indices=[], values=[])
        indexed_tokens = sorted(
            (cls._token_to_index(token), float(count))
            for token, count in token_counts.items()
        )
        indices = [index for index, _ in indexed_tokens]
        values = [value for _, value in indexed_tokens]
        return SparseVector(indices=indices, values=values)

    def insert_projects(
            self,
            embeddings: List[List[float]],
            metadata_list: List[Dict[str, Any]],
            ids: List[str]
    ) -> None:
        """Upsert a batch of points (dense + sparse vectors) into the collection.

        Sparse vectors are built from the `description` field in each metadata dict.
        All three lists must have the same length.

        Args:
            embeddings (List[List[float]]): Dense embedding vectors (one per point).
            metadata_list (List[Dict[str, Any]]): Payload dicts stored alongside each point.
            ids (List[str]): String IDs for each point (typically the project UUID).
        """
        points = [
            PointStruct(
                id=str(id_),
                vector=self._build_point_vector(embedding, metadata),
                payload=metadata,
            )
            for embedding, metadata, id_ in zip(embeddings, metadata_list, ids)
        ]
        self.client.upsert(collection_name=self.collection_name, points=points)
        logger.info(f"Inserted {len(points)} points into {self.collection_name}")

    def delete_projects(self, ids: List[str]) -> None:
        """Remove points by ID from the collection. No-op for an empty list.

        Args:
            ids (List[str]): Point IDs to delete.
        """
        if not ids:
            return

        self.client.delete(
            collection_name=self.collection_name,
            points_selector=ids
        )

        logger.info(
            f"Deleted {len(ids)} points from {self.collection_name}"
        )

    def search(
        self,
        query_vector: List[float],
        query_text: str = "",
        limit: int = 20,
        semantic_weight: float = 0.7,
    ) -> list[Any]:
        """Run a hybrid search using RRF fusion of dense and sparse results.

        `semantic_weight` controls the ratio of dense vs. sparse prefetch limits:
        - 1.0 → pure dense (cosine) search.
        - 0.0 → pure sparse (keyword) search.
        - 0.0 < w < 1.0 → RRF fusion with proportional prefetch limits.

        Args:
            query_vector (List[float]): Dense embedding of the search query.
            query_text (str, default=""): Raw query text for sparse vector construction.
            limit (int, default=20): Maximum number of results to return.
            semantic_weight (float, default=0.7): Weight between 0.0 (keyword) and
                1.0 (semantic). Values outside [0, 1] are clamped.

        Returns:
            list: Qdrant `ScoredPoint` objects with `.id`, `.score`, and `.payload`.
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
        dense_limit = max(1, round(total_prefetch * semantic_weight))
        sparse_limit = max(1, round(total_prefetch * (1.0 - semantic_weight)))

        response = self.client.query_points(
            collection_name=self.collection_name,
            prefetch=[
                Prefetch(query=query_vector, using=DENSE_VECTOR_NAME, limit=dense_limit),
                Prefetch(query=sparse_query, using=SPARSE_VECTOR_NAME, limit=sparse_limit),
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            limit=limit,
        )
        return response.points

    @staticmethod
    def _build_point_vector(embedding: list[float], metadata: Dict[str, Any]) -> dict[str, Any]:
        """Combine a dense embedding and a metadata-derived sparse vector into a named-vector dict.

        The sparse vector is built from the ``description`` field of the
        metadata payload.

        Args:
            embedding (list[float]): Pre-computed dense embedding vector.
            metadata (Dict[str, Any]): Point payload; its ``description``
                field is used to generate the sparse vector.

        Returns:
            dict[str, Any]: Mapping of vector names (``dense``, ``sparse``)
                to their respective vector values.
        """
        return {
            DENSE_VECTOR_NAME: embedding,
            SPARSE_VECTOR_NAME: QdrantManager._build_sparse_vector(
                str(metadata.get("description", ""))
            ),
        }
