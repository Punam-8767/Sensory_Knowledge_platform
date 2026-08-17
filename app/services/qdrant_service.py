# import uuid
# from typing import List, Dict, Any
# from openai import AsyncOpenAI
# from qdrant_client import AsyncQdrantClient
# from qdrant_client.http import models

# from app.core.config import settings
# from app.core.logger import logger

# class QdrantIndexService:
#     def __init__(self):
#         self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
#         # Assumes Qdrant is running locally or via URL in settings
#         self.qdrant_client = AsyncQdrantClient(url=getattr(settings, "QDRANT_URL", "http://localhost:6333"))
#         self.collection_name = "sensory_knowledge_index"
#         self.embedding_model = "text-embedding-3-small"

#     async def _ensure_collection(self):
#         """Ensures the Qdrant collection exists."""
#         exists = await self.qdrant_client.collection_exists(self.collection_name)
#         if not exists:
#             await self.qdrant_client.create_collection(
#                 collection_name=self.collection_name,
#                 vectors_config=models.VectorParams(size=1536, distance=models.Distance.COSINE),
#             )

#     async def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
#         if not texts: return []
#         resp = await self.openai_client.embeddings.create(input=texts, model=self.embedding_model)
#         return [data.embedding for data in resp.data]

#     async def index_semantic_objects(self, document_id: str, nodes: List[Dict[str, Any]]):
#         """
#         Idempotent vector insertion: Deletes old vectors for this document, 
#         generates embeddings for semantic node objects, and upserts them.
#         """
#         await self._ensure_collection()

#         # Idempotency: Clear existing vectors for this document
#         await self.qdrant_client.delete(
#             collection_name=self.collection_name,
#             points_selector=models.Filter(
#                 must=[models.FieldCondition(key="document_id", match=models.MatchValue(value=document_id))]
#             )
#         )

#         texts_to_embed = []
#         payloads = []
#         point_ids = []

#         for node in nodes:
#             # Construct a rich Semantic Knowledge Object string for the embedding
#             semantic_text = (
#                 f"Concept: {node['canonical_name']}. "
#                 f"Category: {node.get('category', 'Entity')}. "
#                 f"Definition: {node.get('definition', '')}. "
#                 f"Context: {node.get('hierarchy_context', 'General')}."
#             )
            
#             # If sub-nodes/attributes exist, append them to the semantic search string
#             if node.get("attributes"):
#                 attrs = [f"{a['attribute_name']}: {a['attribute_value']}" for a in node["attributes"]]
#                 semantic_text += f" Attributes: {', '.join(attrs)}."

#             texts_to_embed.append(semantic_text)
            
#             # The payload allows post-retrieval filtering and graph lookup
#             payloads.append({
#                 "document_id": document_id,
#                 "knowledge_type": "node",
#                 "node_id": node["id"],
#                 "canonical_name": node["canonical_name"],
#                 "category": node.get("category"),
#                 "source_page": node.get("source_page"),
#                 "hierarchy_context": node.get("hierarchy_context"),
#                 "content": semantic_text
#             })
#             point_ids.append(str(uuid.uuid4()))

#         # Batch embed and upsert
#         if texts_to_embed:
#             logger.info(f"Generating embeddings for {len(texts_to_embed)} semantic objects...")
#             embeddings = await self._get_embeddings(texts_to_embed)
            
#             points = [
#                 models.PointStruct(id=pid, vector=emb, payload=pay)
#                 for pid, emb, pay in zip(point_ids, embeddings, payloads)
#             ]
            
#             await self.qdrant_client.upsert(
#                 collection_name=self.collection_name,
#                 points=points
#             )
#             logger.info(f"Successfully indexed {len(points)} vectors in Qdrant for {document_id}.")





import uuid
from typing import List, Dict, Any, Set
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

from app.core.config import settings
from app.core.logger import logger

class QdrantIndexService:
    def __init__(self):
        # Fallback to defaults only if settings are genuinely missing
        self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.qdrant_client = AsyncQdrantClient(url=getattr(settings, "QDRANT_URL", "http://localhost:6333"))
        self.collection_name = getattr(settings, "QDRANT_COLLECTION", "sensory_knowledge_index")
        self.embedding_model = getattr(settings, "EMBEDDING_MODEL", "text-embedding-3-small")
        self.embedding_dim = getattr(settings, "EMBEDDING_DIM", 1536)
        
        self.namespace = uuid.NAMESPACE_DNS
        self.batch_size = 100 

    async def _ensure_collection(self):
        if not await self.qdrant_client.collection_exists(self.collection_name):
            await self.qdrant_client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(size=self.embedding_dim, distance=models.Distance.COSINE),
            )

    async def _get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        all_embeddings = []
        for i in range(0, len(texts), self.batch_size):
            batch_texts = texts[i:i + self.batch_size]
            resp = await self.openai_client.embeddings.create(input=batch_texts, model=self.embedding_model)
            all_embeddings.extend([data.embedding for data in resp.data])
        return all_embeddings

    async def reconcile_document_vectors(self, document_id: str, new_point_ids: Set[str]):
        """Deletes stale vectors that belong to this document but are no longer in the payload."""
        try:
            scroll_res = await self.qdrant_client.scroll(
                collection_name=self.collection_name,
                scroll_filter=models.Filter(
                    must=[models.FieldCondition(key="document_id", match=models.MatchValue(value=document_id))]
                ),
                limit=10000,
                with_payload=False,
                with_vectors=False
            )
            existing_ids = {point.id for point in scroll_res[0]}
            stale_ids = existing_ids - new_point_ids
            
            if stale_ids:
                await self.qdrant_client.delete(
                    collection_name=self.collection_name,
                    points_selector=models.PointIdsList(points=list(stale_ids))
                )
                logger.info(f"Reconciled Qdrant: Deleted {len(stale_ids)} stale semantic objects for {document_id}.")
        except Exception as e:
            logger.warning(f"Failed to reconcile stale Qdrant points for {document_id}. Proceeding with upsert. Error: {str(e)}")

    async def index_semantic_objects(self, semantic_payloads: List[Dict[str, Any]]):
        """Generates embeddings for knowledge objects and upserts idempotently."""
        await self._ensure_collection()

        texts_to_embed = []
        points_data = []
        new_point_ids = set()

        for item in semantic_payloads:
            semantic_text = item.get("semantic_text", "")
            if not semantic_text: continue
            
            # Deterministic UUID5 identity: document_id + knowledge_type + db_id
            unique_string = f"{item['document_id']}_{item['knowledge_type']}_{item['db_id']}"
            point_id = str(uuid.uuid5(self.namespace, unique_string))
            
            texts_to_embed.append(semantic_text)
            new_point_ids.add(point_id)
            
            payload = {k: v for k, v in item.items() if k != "semantic_text" and v is not None}
            payload["content"] = semantic_text
            points_data.append({"id": point_id, "payload": payload})

        if not texts_to_embed:
            return

        # Handle Stale Points Reconciliation
        await self.reconcile_document_vectors(semantic_payloads[0]["document_id"], new_point_ids)

        logger.info(f"Generating {len(texts_to_embed)} semantic embeddings for Qdrant...")
        all_embeddings = await self._get_embeddings_batch(texts_to_embed)
        
        qdrant_points = [
            models.PointStruct(id=p["id"], vector=emb, payload=p["payload"])
            for p, emb in zip(points_data, all_embeddings)
        ]
        
        for i in range(0, len(qdrant_points), self.batch_size):
            await self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=qdrant_points[i:i + self.batch_size]
            )
        logger.info(f"Successfully upserted {len(qdrant_points)} semantic objects into Qdrant.")