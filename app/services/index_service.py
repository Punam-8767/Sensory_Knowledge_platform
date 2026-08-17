import json
import hashlib
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.mysql import insert

from app.core.config import settings
from app.core.exceptions import DocumentNotFoundError, ProcessingError
from app.core.logger import logger

from app.models.knowledge import KnowledgeExtractionPayload
from app.models.knowledge_db import (
    KnowledgeNode, NodeAttribute, NodeProvenance, 
    KnowledgeEdge, ScientificRuleModel, ProcedureModel
)
from app.services.qdrant_service import QdrantIndexService

class KnowledgeIndexService:
    def __init__(self, db_session: AsyncSession):
        self.processed_dir = settings.STORAGE_PROCESSED_DIR
        self.raw_dir = settings.STORAGE_RAW_DIR
        self.db = db_session
        self.qdrant_service = QdrantIndexService()

    def _normalize_key(self, name: str) -> str:
        key = "".join(c for c in name.lower() if c.isalnum())
        if key.endswith('s') and not key.endswith('ss') and len(key) > 3:
            key = key[:-1]
        return key

    def _generate_id(self, *args) -> str:
        key = "_".join(str(a).strip().lower() for a in args)
        return hashlib.md5(key.encode()).hexdigest()

    async def _update_status(self, document_id: str, global_status: str, stage_key: str, stage_value: str):
        metadata_path = self.raw_dir / document_id / "metadata.json"
        if metadata_path.exists():
            with open(metadata_path, "r+", encoding="utf-8") as mf:
                meta = json.load(mf)
                meta["pipeline_status"] = global_status
                meta[stage_key] = stage_value
                mf.seek(0)
                json.dump(meta, mf, indent=2)
                mf.truncate()

    async def index_document_knowledge(self, document_id: str) -> dict:
        processed_base = self.processed_dir / document_id
        knowledge_path = processed_base / "extracted_knowledge.json"

        if not knowledge_path.exists():
            raise DocumentNotFoundError(f"Extracted knowledge artifact not found for {document_id}.")

        try:
            with open(knowledge_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
                
            # Cross-document contamination check
            if raw_data.get("document_id") != document_id:
                raise ValueError("document_id in JSON payload does not match API path parameter.")
                
            payload = KnowledgeExtractionPayload.model_validate(raw_data)
        except Exception as e:
            raise ProcessingError(f"Extracted knowledge validation failed: {str(e)}")

        await self._update_status(document_id, "INDEXING", "stage_indexing", "running")
        logger.info(f"Starting Knowledge Persistence for {document_id}")

        qdrant_payloads = []
        node_id_map = {}

        # =========================================================
        # TRANSACTION BLOCK: MySQL Structured Graph + Provenance
        # =========================================================
        try:
            async with self.db.begin(): 
                # A. Nodes, Attributes, and Provenance
                for c in payload.concepts:
                    canonical = c.canonical_name.strip()
                    norm_key = self._normalize_key(canonical)
                    if not norm_key: continue

                    node_id = self._generate_id("node", norm_key)
                    node_id_map[norm_key] = node_id

                    await self.db.merge(KnowledgeNode(
                        id=node_id, canonical_name=canonical, category=c.category,
                        definition=c.definition, synonyms=c.synonyms, keywords=c.keywords
                    ))

                    attr_strings = []
                    for attr in c.attributes:
                        attr_id = self._generate_id(node_id, "attr", self._normalize_key(attr.name))
                        await self.db.merge(NodeAttribute(
                            id=attr_id, node_id=node_id, name=attr.name, value=attr.value
                        ))
                        attr_strings.append(f"{attr.name}: {attr.value}")

                    prov_id = self._generate_id(node_id, document_id, str(c.source_page), str(c.element_id))
                    await self.db.merge(NodeProvenance(
                        id=prov_id, node_id=node_id, document_id=document_id,
                        source_page=c.source_page, hierarchy_context=c.hierarchy_context,
                        element_id=c.element_id, section_path=c.section_path
                    ))

                    # Qdrant Semantic Payload (Embed Concept + Definition + Attributes)
                    semantic_text = f"Concept: {canonical}. Category: {c.category or 'Entity'}. Definition: {c.definition or ''}"
                    if attr_strings: semantic_text += f" Attributes: {', '.join(attr_strings)}."
                    if c.hierarchy_context: semantic_text += f" Context: {c.hierarchy_context}."

                    qdrant_payloads.append({
                        "document_id": document_id, "knowledge_type": "node", "db_id": node_id,
                        "canonical_name": canonical, "category": c.category, "source_page": c.source_page,
                        "hierarchy_context": c.hierarchy_context, "semantic_text": semantic_text
                    })

                # B. Relationships / Edges (MySQL Only for now)
                valid_edges = 0
                for r in payload.relationships:
                    src_key = self._normalize_key(r.source_concept)
                    tgt_key = self._normalize_key(r.target_concept)
                    src_id = node_id_map.get(src_key)
                    tgt_id = node_id_map.get(tgt_key)

                    if src_id and tgt_id and src_id != tgt_id:
                        edge_id = self._generate_id(document_id, "edge", src_id, r.relationship_type, tgt_id)
                        await self.db.merge(KnowledgeEdge(
                            id=edge_id, document_id=document_id,
                            source_node_id=src_id, target_node_id=tgt_id,
                            relationship_type=r.relationship_type,
                            source_section=r.source_section, source_page=r.source_page
                        ))
                        valid_edges += 1

                # C. Rules & Procedures
                for rule in payload.scientific_rules:
                    rule_id = self._generate_id(document_id, "rule", self._normalize_key(rule.rule_statement))
                    await self.db.merge(ScientificRuleModel(
                        id=rule_id, document_id=document_id, rule_statement=rule.rule_statement, 
                        context=rule.context, source_page=rule.source_page
                    ))
                    qdrant_payloads.append({
                        "document_id": document_id, "knowledge_type": "scientific_rule", "db_id": rule_id,
                        "source_page": rule.source_page, "semantic_text": f"Scientific Rule: {rule.rule_statement}. Context: {rule.context or ''}"
                    })

                for proc in payload.procedures:
                    proc_id = self._generate_id(document_id, "proc", self._normalize_key(proc.procedure_name))
                    await self.db.merge(ProcedureModel(
                        id=proc_id, document_id=document_id, procedure_name=proc.procedure_name, 
                        steps=proc.steps, source_page=proc.source_page
                    ))
                    qdrant_payloads.append({
                        "document_id": document_id, "knowledge_type": "procedure", "db_id": proc_id,
                        "source_page": proc.source_page, "semantic_text": f"Procedure: {proc.procedure_name}. Steps: {', '.join(proc.steps)}."
                    })

            await self._update_status(document_id, "MYSQL_INDEXED", "stage_mysql", "completed")
            logger.info(f"MySQL transaction committed: {len(payload.concepts)} nodes, {valid_edges} edges.")

        except Exception as e:
            # SQLAlchemy async context manager auto-rollbacks
            await self._update_status(document_id, "MYSQL_INDEX_FAILED", "stage_mysql", "failed")
            logger.error(f"MySQL Indexing failed for {document_id}: {str(e)}")
            raise ProcessingError(f"MySQL indexing failed: {str(e)}")

        # =========================================================
        # QDRANT BLOCK: Semantic Sync
        # =========================================================
        try:
            await self.qdrant_service.index_semantic_objects(qdrant_payloads)
            await self._update_status(document_id, "KNOWLEDGE_INDEXED", "stage_qdrant", "completed")
            
            return {
                "document_id": document_id,
                "nodes_indexed": len(payload.concepts),
                "relationships_indexed": valid_edges,
                "rules_indexed": len(payload.scientific_rules),
                "procedures_indexed": len(payload.procedures),
                "vectors_upserted": len(qdrant_payloads),
                "pipeline_status": "KNOWLEDGE_INDEXED"
            }

        except Exception as e:
            await self._update_status(document_id, "MYSQL_INDEXED_QDRANT_FAILED", "stage_qdrant", "failed")
            logger.error(f"Qdrant indexing failed for {document_id}: {str(e)}")
            # Raise gracefully: MySQL succeeded, but Qdrant failed. State is correctly reflected.
            raise ProcessingError("MySQL succeeded, but Qdrant semantic indexing failed. Safe to retry.")



            