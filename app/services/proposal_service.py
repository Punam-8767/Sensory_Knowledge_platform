import json
import asyncio
from typing import Dict, Any, List, Optional, Tuple, Set
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.exceptions import DocumentNotFoundError, ProcessingError, StorageError
from app.core.logger import logger


class ProposalService:
    def __init__(self, mysql_service=None, qdrant_service=None):
        self.raw_dir = settings.STORAGE_RAW_DIR
        self.processed_dir = settings.STORAGE_PROCESSED_DIR
        
        self.mysql_service = mysql_service
        self.qdrant_service = qdrant_service
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        # MDM Similarity Thresholds
        self.EXACT_MATCH_THRESHOLD = 0.95
        self.MERGE_REVIEW_THRESHOLD = 0.85

        # Enterprise Ontology Edge Validation Matrix (Source -> Edge -> Target)
        self.valid_edges = {
            "is_child_of": {"source": ["sensory_scale", "family", "sensory_attribute"], "target": ["axis", "family"]},
            "measured_by": {"source": ["sensory_attribute"], "target": ["sensory_scale"]},
            "described_by": {"source": ["sensory_attribute"], "target": ["descriptor"]},
            "categorized_as": {"source": ["sensory_attribute", "descriptor"], "target": ["family"]},
            "uses_sql": {"source": ["intent_group"], "target": ["sql_query_pattern"]},
            "composes_from": {"source": ["analysis_recipe"], "target": ["recipe_step"]},
            "gated_by": {"source": ["answer_shape_template"], "target": ["alignment_gate"]},
            "related_to": {"source": ["ANY"], "target": ["ANY"]}  # Generic fallback
        }

    ###########################################################################
    # STAGE 1: METADATA FILTERING
    ###########################################################################

    def _is_metadata_leakage(self, name: str) -> bool:
        """Filters authors, publishers, ISBNs, and copyright artifacts."""
        norm = "".join(c for c in name.lower() if c.isalnum())
        stop_words = {"press", "isbn", "copyright", "edition", "publisher", "inc", "ltd", "author"}
        known_authors = {"mortenmeilgaard", "gailvanceciville", "bthomascarr", "meilgaard", "civille", "carr"}
        return any(bad in norm for bad in stop_words) or norm in known_authors

    ###########################################################################
    # STAGE 2: INTERNAL SEMANTIC DEDUPLICATION (EMBEDDINGS)
    ###########################################################################

    async def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Batch fetches OpenAI embeddings for semantic clustering."""
        if not texts: return []
        resp = await self.client.embeddings.create(input=texts, model="text-embedding-3-small")
        return [data.embedding for data in resp.data]

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        return sum(a * b for a, b in zip(vec1, vec2))

    async def _semantic_internal_deduplication(self, raw_concepts: List[Dict]) -> List[Dict]:
        """
        Uses vector embeddings to cluster and merge duplicate concepts 
        within the document BEFORE hitting the DB (e.g., 'overall liking' == 'overall acceptance').
        """
        clean_concepts = [c for c in raw_concepts if not self._is_metadata_leakage(c.get("canonical_name", ""))]
        if not clean_concepts: return []

        names = [c["canonical_name"] for c in clean_concepts]
        embeddings = await self._get_embeddings(names)

        deduped = []
        for i, c in enumerate(clean_concepts):
            c["vector"] = embeddings[i]
            matched = False
            
            for existing in deduped:
                sim = self._cosine_similarity(c["vector"], existing["vector"])
                
                # Merge if semantically identical (>0.92) and same ontology
                if sim > 0.92 and existing.get("type_key") == c.get("type_key"):
                    existing["concept_terms"].extend(c.get("concept_terms", []))
                    existing["concept_terms"] = list({t["term"]: t for t in existing["concept_terms"]}.values()) # Dedupe terms
                    matched = True
                    break
            
            if not matched:
                deduped.append(c)

        # Cleanup internal vectors
        for d in deduped: d.pop("vector", None)
        return deduped

    ###########################################################################
    # STAGE 3: BATCH CONCEPT DB LOOKUP (NO N+1)
    ###########################################################################

    async def _batch_db_resolution(self, concepts: List[Dict]) -> Dict[str, Dict]:
        """
        Performs massive batch lookups against MySQL and Qdrant.
        Returns a mapping of local canonical_name -> Resolution Result.
        """
        resolution_map = {}
        names_to_search = [c["canonical_name"] for c in concepts]

        # 1. Batch SQL Lookup (Exact Match)
        sql_matches = {}
        if self.mysql_service:
            sql_results = await self.mysql_service.find_concepts_batch(names_to_search)
            for res in sql_results:
                sql_matches[res["searched_term"]] = res

        # 2. Batch Qdrant Lookup (Semantic Search) for those missing in SQL
        missing_names = [n for n in names_to_search if n not in sql_matches]
        vector_matches = {}
        if self.qdrant_service and missing_names:
            vector_results = await self.qdrant_service.search_batch(missing_names, score_threshold=self.MERGE_REVIEW_THRESHOLD)
            for req_term, res in vector_results.items():
                vector_matches[req_term] = res

        # 3. Compile Results
        for c in concepts:
            name = c["canonical_name"]
            if name in sql_matches:
                resolution_map[name] = {"match_type": "exact", "uid": sql_matches[name]["concept_uid"], "score": 1.0}
            elif name in vector_matches:
                resolution_map[name] = {"match_type": "fuzzy", "uid": vector_matches[name]["concept_uid"], "score": vector_matches[name]["score"]}
            else:
                resolution_map[name] = {"match_type": "none", "uid": None, "score": 0.0}

        return resolution_map

    ###########################################################################
    # STAGE 4: ONTOLOGY & EDGE VALIDATION
    ###########################################################################

    def _validate_ontology_edges(self, relationships: List[Dict], concept_types: Dict[str, str]) -> List[Dict]:
        """Strips out invalid relationships (e.g., descriptor -> uses_sql -> recipe)."""
        valid_edges = []
        for r in relationships:
            src_type = concept_types.get(r["source_concept"])
            tgt_type = concept_types.get(r["target_concept"])
            rel_type = r["relationship_type"]

            if not src_type or not tgt_type:
                continue

            rules = self.valid_edges.get(rel_type)
            if not rules:
                continue # Unrecognized relationship

            src_valid = "ANY" in rules["source"] or src_type in rules["source"]
            tgt_valid = "ANY" in rules["target"] or tgt_type in rules["target"]

            if src_valid and tgt_valid:
                valid_edges.append(r)
            else:
                logger.warning(f"Ontology Violation Dropped: {src_type} -> {rel_type} -> {tgt_type}")

        return valid_edges

    ###########################################################################
    # MASTER MDM ORCHESTRATOR
    ###########################################################################

    async def generate_canonical_mapping(self, document_id: str) -> Dict[str, Any]:
        processed_base = self.processed_dir / document_id
        knowledge_path = processed_base / "extracted_knowledge.json"

        if not knowledge_path.exists():
            raise DocumentNotFoundError(f"Knowledge artifact for {document_id} not found.")

        try:
            logger.info(f"Starting Enterprise MDM Canonical Mapping for {document_id}")
            
            with open(knowledge_path, "r", encoding="utf-8") as f:
                extracted_knowledge = json.load(f)

            raw_concepts = extracted_knowledge.get("concepts", [])
            raw_relationships = extracted_knowledge.get("relationships", [])

            # 1. Cleaning & Semantic Clustering
            clean_concepts = await self._semantic_internal_deduplication(raw_concepts)
            
            # 2. Batch Database & Vector Resolution
            resolution_map = await self._batch_db_resolution(clean_concepts)

            mapped_concepts = []
            staging_proposals = []
            
            # Map canonical names to their DB UID or a temporary staging reference
            concept_ref_map = {} 
            concept_type_map = {} # Needed for ontology validation

            for i, concept in enumerate(clean_concepts):
                canonical = concept["canonical_name"]
                type_key = concept.get("type_key", "descriptor")
                concept_type_map[canonical] = type_key
                
                res = resolution_map.get(canonical, {})
                score = res["score"]
                matched_uid = res["uid"]

                # Confidence Fusion: (LLM Conf * 0.3) + (DB Score * 0.7)
                llm_conf = concept.get("ai_confidence", 0.8)
                fused_confidence = round((llm_conf * 0.3) + (score * 0.7), 4)

                if score >= self.EXACT_MATCH_THRESHOLD:
                    # REUSE EXISTING
                    concept_ref_map[canonical] = matched_uid
                    mapped_concepts.append({
                        "canonical_name": canonical,
                        "concept_uid": matched_uid,
                        "status": "APPROVED_DB_MATCH",
                        "confidence": fused_confidence
                    })

                elif score >= self.MERGE_REVIEW_THRESHOLD:
                    # MERGE PROPOSAL (Fuzzy match requires human verification to merge)
                    staging_ref = f"merge_cand_{i}"
                    concept_ref_map[canonical] = staging_ref
                    
                    staging_proposals.append({
                        "staging_ref": staging_ref,
                        "proposal_type": "merge_update",
                        "target_concept_uid": matched_uid, # Link to the concept it might merge with
                        "proposed_name": canonical,
                        "proposed_data": concept.get("type_data", {}),
                        "fusion_confidence": fused_confidence,
                        "status": "pending_merge_review"
                    })

                else:
                    # NEW PROPOSAL (Completely novel concept)
                    staging_ref = f"new_cand_{i}"
                    concept_ref_map[canonical] = staging_ref
                    
                    staging_proposals.append({
                        "staging_ref": staging_ref,
                        "proposal_type": "new_concept",
                        "proposed_type": type_key,
                        "proposed_name": canonical,
                        "proposed_terms": concept.get("concept_terms", []),
                        "proposed_data": concept.get("type_data", {}),
                        "fusion_confidence": fused_confidence,
                        "status": "pending_new_review"
                    })

            # 3. Ontology & Edge Validation
            validated_relationships = self._validate_ontology_edges(raw_relationships, concept_type_map)

            resolved_edges = []
            for rel in validated_relationships:
                src_ref = concept_ref_map.get(rel["source_concept"])
                tgt_ref = concept_ref_map.get(rel["target_concept"])

                if src_ref and tgt_ref and src_ref != tgt_ref:
                    resolved_edges.append({
                        "source_ref": src_ref,     # Will be swapped for real UIDs during MySQL Transaction
                        "target_ref": tgt_ref,
                        "relationship_type": rel["relationship_type"]
                    })

            # 4. Construct Transactional Staging Payload
            staging_payload = {
                "document_id": document_id,
                "validation_stats": {
                    "existing_reused": len([c for c in mapped_concepts if c["status"] == "APPROVED_DB_MATCH"]),
                    "merge_proposals": len([p for p in staging_proposals if p["proposal_type"] == "merge_update"]),
                    "new_proposals": len([p for p in staging_proposals if p["proposal_type"] == "new_concept"]),
                    "valid_edges": len(resolved_edges)
                },
                "proposals": staging_proposals,
                "relationships": resolved_edges
            }

            # 5. Persist to MySQL Staging DB (NO FILE SYSTEM ARTIFACTS FOR CORE PAYLOADS)
            if self.mysql_service:
                await self.mysql_service.save_staging_payload(document_id, staging_payload)

            logger.info(f"MDM Mapping complete for {document_id}. Awaiting Dashboard Validation.")
            
            # Return lightweight summary for the frontend
            return staging_payload["validation_stats"]

        except Exception as e:
            logger.error(f"Canonical mapping failed for {document_id}: {str(e)}", exc_info=True)
            raise StorageError(f"Canonical mapping failed: {str(e)}")