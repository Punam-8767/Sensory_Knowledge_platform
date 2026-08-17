import json
from typing import Dict, Any, List
from pathlib import Path
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import ScoredPoint

from app.core.config import settings
from app.core.logger import logger
from app.core.exceptions import DocumentNotFoundError, ProcessingError

class CanonicalService:
    def __init__(self):
        self.processed_dir = settings.STORAGE_PROCESSED_DIR
        self.raw_dir = settings.STORAGE_RAW_DIR
        self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        
        # Initialize Async Qdrant Client
        self.qdrant = AsyncQdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        self.collection_name = "concepts"
        self.similarity_threshold = 0.88  # High threshold for scientific exactness

    async def _get_embedding(self, text: str) -> List[float]:
        """Generates an embedding vector using OpenAI's text-embedding-3-small."""
        response = await self.openai_client.embeddings.create(
            input=text,
            model="text-embedding-3-small"
        )
        return response.data[0].embedding

    async def normalize_concepts(self, document_id: str) -> Dict[str, Any]:
        """
        Reads extracted knowledge, vectorizes concepts, and maps them against Qdrant.
        Flags matches as EXISTING and unmatched as PROPOSALS.
        """
        doc_dir = self.processed_dir / document_id
        knowledge_path = doc_dir / "extracted_knowledge.json"
        metadata_path = self.raw_dir / document_id / "metadata.json"

        if not knowledge_path.exists():
            raise DocumentNotFoundError(f"Knowledge payload not found for {document_id}. Run extract-knowledge first.")

        try:
            with open(knowledge_path, "r", encoding="utf-8") as f:
                extracted_data = json.load(f)

            concepts = extracted_data.get("concepts", [])
            logger.info(f"Starting Canonical Normalization for {len(concepts)} concepts in {document_id}")

            normalized_results = []
            new_proposals = 0
            mapped_existing = 0

            # Ensure collection exists (mock check for first-time runs)
            if not await self.qdrant.collection_exists(self.collection_name):
                logger.warning(f"Qdrant collection '{self.collection_name}' not found. All concepts will be PROPOSALS.")

            for concept in concepts:
                canonical_name = concept.get("canonical_name", "")
                definition = concept.get("definition", "")
                
                # We embed the name + definition for rich semantic search
                search_text = f"{canonical_name}: {definition}"
                vector = await self._get_embedding(search_text)

                matched_uid = None
                
                # Perform Vector Search if the collection is active
                if await self.qdrant.collection_exists(self.collection_name):
                    search_result: List[ScoredPoint] = await self.qdrant.search(
                        collection_name=self.collection_name,
                        query_vector=vector,
                        limit=1
                    )
                    
                    if search_result and search_result[0].score >= self.similarity_threshold:
                        matched_uid = search_result[0].payload.get("concept_uid")

                if matched_uid:
                    mapped_existing += 1
                    status = "MAPPED_EXISTING"
                else:
                    new_proposals += 1
                    status = "PROPOSAL"
                    # In a real system, you'd generate a temporary proposal UID here
                    matched_uid = f"prop_{canonical_name.lower().replace(' ', '_')}"

                normalized_results.append({
                    "extracted_name": canonical_name,
                    "definition": definition,
                    "category": concept.get("category"),
                    "status": status,
                    "canonical_uid": matched_uid
                })

            # Save the mapping
            mapping_payload = {
                "document_id": document_id,
                "total_processed": len(concepts),
                "mapped_existing": mapped_existing,
                "new_proposals": new_proposals,
                "mappings": normalized_results
            }

            mapping_path = doc_dir / "canonical_mapping.json"
            with open(mapping_path, "w", encoding="utf-8") as f:
                json.dump(mapping_payload, f, indent=4)

            # Update Pipeline State
            if metadata_path.exists():
                with open(metadata_path, "r+", encoding="utf-8") as f:
                    meta_data = json.load(f)
                    meta_data["pipeline_status"] = "NORMALIZED"
                    meta_data["next_step"] = f"{settings.API_V1_STR}/documents/{document_id}/normalize"
                    f.seek(0)
                    json.dump(meta_data, f, indent=2)
                    f.truncate()

            logger.info(f"Normalization complete: {mapped_existing} mapped, {new_proposals} proposals.")
            
            return mapping_payload

        except Exception as e:
            logger.error(f"Canonical Normalization failed for {document_id}: {str(e)}", exc_info=True)
            raise ProcessingError(f"Normalization failed: {str(e)}")




