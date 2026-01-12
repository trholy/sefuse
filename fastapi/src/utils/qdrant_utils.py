import os
import time
import logging
from typing import List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

logger = logging.getLogger(__name__)

VECTOR_DB_HOST = os.getenv('VECTOR_DB_HOST', 'qdrant')
QDRANT_PORT = os.environ.get('QDRANT_PORT', 6333)


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

    def _init_qdrant(
            self,
            max_retries: int = 10,
            wait: int = 3
    ) -> QdrantClient:

        for attempt in range(max_retries):
            try:
                client = QdrantClient(host=self.host, port=self.port)
                client.get_collections()  # test connection
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
        if self.collection_name not in existing_collections:
            client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=768, distance=Distance.COSINE)
            )
            logger.info(f"Created collection {self.collection_name}")
        else:
            logger.info(f"Collection {self.collection_name} already exists")

        return client

    def insert_projects(
            self,
            embeddings: List[List[float]],
            metadata_list: List[Dict[str, Any]],
            ids: List[str]
    ) -> None:
        points = [
            PointStruct(
                id=str(id_),
                vector=embedding,
                payload=metadata
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

    def search(self, query_vector: List[float], limit: int = 20):
        return self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=limit
        ).points
