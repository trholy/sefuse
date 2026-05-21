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
QDRANT_PORT = os.environ.get('QDRANT_PORT', 6333)
DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"
PREFETCH_LIMIT_MULTIPLIER = 3


class QdrantManager:
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
        return re.findall(r"\b\w+\b", text.lower())

    @staticmethod
    def _token_to_index(token: str) -> int:
        digest = hashlib.md5(token.encode("utf-8")).hexdigest()
        return int(digest[:8], 16)

    @classmethod
    def _build_sparse_vector(cls, text: str) -> SparseVector:
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
        return {
            DENSE_VECTOR_NAME: embedding,
            SPARSE_VECTOR_NAME: QdrantManager._build_sparse_vector(
                str(metadata.get("description", ""))
            ),
        }
