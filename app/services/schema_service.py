# import json
# import uuid
# from typing import Dict, Any
# from app.core.config import settings
# from app.core.logger import logger
# from app.core.exceptions import DocumentNotFoundError, ProcessingError

# class SchemaService:
#     def __init__(self):
#         self.processed_dir = settings.STORAGE_PROCESSED_DIR
#         self.raw_dir = settings.STORAGE_RAW_DIR

#     async def build_mysql_payload(self, document_id: str) -> Dict[str, Any]:
#         """
#         Maps extracted knowledge and canonical mappings into strict MySQL table structures.
#         Validates relationships and generates the final SQL-ready payload.
#         """
#         doc_dir = self.processed_dir / document_id
#         knowledge_path = doc_dir / "extracted_knowledge.json"
#         mapping_path = doc_dir / "canonical_mapping.json"
#         metadata_path = self.raw_dir / document_id / "metadata.json"

#         if not knowledge_path.exists() or not mapping_path.exists():
#             raise DocumentNotFoundError(
#                 f"Prerequisite artifacts missing for {document_id}. Run extraction and normalization steps first."
#             )

#         try:
#             with open(knowledge_path, "r", encoding="utf-8") as f:
#                 knowledge = json.load(f)
#             with open(mapping_path, "r", encoding="utf-8") as f:
#                 mapping = json.load(f)

#             logger.info(f"Starting Schema Mapping & Validation for {document_id}")

#             # 1. Build Concept Lookup (Name -> UID)
#             concept_lookup = {}
#             db_concepts = []
#             db_concept_terms = []
            
#             for map_entry in mapping.get("mappings", []):
#                 name = map_entry["extracted_name"]
#                 uid = map_entry["canonical_uid"]
#                 status = map_entry["status"] # PROPOSAL or MAPPED_EXISTING
#                 category = map_entry.get("category", "General")
                
#                 # Populate lookup for relationship mapping
#                 concept_lookup[name.lower()] = uid
                
#                 # Only prepare SQL INSERTS for NEW proposals (existing ones are already in the DB)
#                 if status == "PROPOSAL":
#                     db_concepts.append({
#                         "uid": uid,
#                         "type_key": category,
#                         "status": "PENDING_REVIEW",
#                         "source_document_id": document_id
#                     })
                    
#                     db_concept_terms.append({
#                         "concept_uid": uid,
#                         "term": name,
#                         "is_canonical": True,
#                         "definition": map_entry.get("definition", "")
#                     })

#             # 2. Map Relationships & Validate Graph Integrity
#             db_relationships = []
#             missing_nodes = 0

#             for rel in knowledge.get("relationships", []):
#                 source_name = rel.get("source_concept", "").lower()
#                 target_name = rel.get("target_concept", "").lower()
#                 rel_type = rel.get("relationship_type", "")

#                 source_uid = concept_lookup.get(source_name)
#                 target_uid = concept_lookup.get(target_name)

#                 # Validation: Ensure both nodes exist before creating a MySQL relationship edge
#                 if source_uid and target_uid:
#                     db_relationships.append({
#                         "relationship_id": f"rel_{uuid.uuid4().hex[:8]}",
#                         "source_concept_uid": source_uid,
#                         "target_concept_uid": target_uid,
#                         "relationship_type": rel_type,
#                         "source_document_id": document_id
#                     })
#                 else:
#                     missing_nodes += 1

#             # 3. Compile the Final Payload tailored to the Client's MySQL Schema
#             mysql_payload = {
#                 "document_id": document_id,
#                 "validation_stats": {
#                     "valid_proposals": len(db_concepts),
#                     "valid_relationships": len(db_relationships),
#                     "dropped_invalid_relationships": missing_nodes
#                 },
#                 "tables": {
#                     "concepts": db_concepts,
#                     "concept_terms": db_concept_terms,
#                     "concept_relationships": db_relationships,
#                     "scientific_rules": knowledge.get("scientific_rules", []),
#                     "procedures": knowledge.get("procedures", [])
#                 }
#             }

#             # 4. Save the SQL-Ready Artifact
#             payload_path = doc_dir / "mysql_payload.json"
#             with open(payload_path, "w", encoding="utf-8") as f:
#                 json.dump(mysql_payload, f, indent=4)

#             # 5. Update Pipeline State
#             if metadata_path.exists():
#                 with open(metadata_path, "r+", encoding="utf-8") as f:
#                     meta_data = json.load(f)
#                     meta_data["pipeline_status"] = "SCHEMA_MAPPED"
#                     meta_data["next_step"] = f"{settings.API_V1_STR}/documents/{document_id}/schema"
#                     f.seek(0)
#                     json.dump(meta_data, f, indent=2)
#                     f.truncate()

#             logger.info(f"Schema Mapping complete. {len(db_concepts)} concepts and {len(db_relationships)} relationships ready for MySQL.")
            
#             return {
#                 "document_id": document_id,
#                 "pipeline_status": "SCHEMA_MAPPED",
#                 "validation_stats": mysql_payload["validation_stats"],
#                 "mysql_artifact_path": str(payload_path.relative_to(settings.BASE_DIR)),
#                 "next_step": f"{settings.API_V1_STR}/documents/{document_id}/schema"
#             }

#         except Exception as e:
#             logger.error(f"Schema Mapping failed for {document_id}: {str(e)}", exc_info=True)
#             raise ProcessingError(f"Schema Mapping failed: {str(e)}")


import json
import uuid
from typing import Dict, Any
from app.core.config import settings
from app.core.logger import logger
from app.core.exceptions import DocumentNotFoundError, ProcessingError

# Map string relationships to the exact Concept DB 'rt' IDs (Section 4)
RELATIONSHIP_MAP = {
    "is_child_of": 2,
    "causes": 3,
    "measured_by": 4,
    "described_by": 5,
    "influences": 6,
    "related_to": 9,
    "part_of": 12,
    "categorized_as": 15,
    "applies_to": 16,
    "co_occurs_with": 19,
    "is_example_of": 21,
    "triggered_by": 22,
    "renders_as": 23,
    "benchmarked_by": 29,
    "pulls_from": 30,
    "uses_sql": 31
}

class SchemaService:
    def __init__(self):
        self.processed_dir = settings.STORAGE_PROCESSED_DIR
        self.raw_dir = settings.STORAGE_RAW_DIR

    async def build_mysql_payload(self, document_id: str) -> Dict[str, Any]:
        doc_dir = self.processed_dir / document_id
        knowledge_path = doc_dir / "extracted_knowledge.json"
        mapping_path = doc_dir / "canonical_mapping.json"
        metadata_path = self.raw_dir / document_id / "metadata.json"

        if not knowledge_path.exists() or not mapping_path.exists():
            raise DocumentNotFoundError("Prerequisite artifacts missing. Run extraction and normalization first.")

        try:
            with open(knowledge_path, "r", encoding="utf-8") as f:
                knowledge = json.load(f)
            with open(mapping_path, "r", encoding="utf-8") as f:
                mapping = json.load(f)

            logger.info(f"Starting Schema Mapping & Validation for {document_id}")

            # Lookup dictionaries
            llm_concepts = {c["canonical_name"].lower(): c for c in knowledge.get("concepts", [])}
            concept_registry = {}  # name -> {uid, status}
            
            db_concept_proposals = {}
            db_relationships = []
            db_new_synonyms = []

            # 1. Process Mappings into Proposals vs. Existing
            for map_entry in mapping.get("mappings", []):
                name = map_entry["extracted_name"]
                name_lower = name.lower()
                uid = map_entry["canonical_uid"]
                status = map_entry["status"]
                category = map_entry.get("category", "General")
                
                concept_registry[name_lower] = {"uid": uid, "status": status}
                llm_data = llm_concepts.get(name_lower, {})

                if status == "PROPOSAL":
                    # Build ENUM-compliant terms array (canonical + synonyms)
                    terms_list = [{"term": name, "term_type": "canonical"}]
                    for syn in llm_data.get("synonyms", []):
                        terms_list.append({"term": syn, "term_type": "synonym"})

                    # Package exactly as Section 8.1 requires
                    db_concept_proposals[uid] = {
                        "proposal_uid": uid, # e.g., 'prop_sweetness'
                        "proposed_type": category,
                        "proposed_name": name,
                        "proposed_name_normalized": name_lower,
                        "proposed_definition": map_entry.get("definition", ""),
                        "proposed_data": llm_data,
                        "proposed_terms": terms_list,
                        "proposed_relationships": [] # Will populate in Step 2
                    }
                else:
                    # If existing, we can push newly discovered synonyms directly to concept_terms
                    for syn in llm_data.get("synonyms", []):
                        db_new_synonyms.append({
                            "concept_uid": uid,
                            "term": syn,
                            "term_type": "synonym"
                        })

            # 2. Process Relationships (Using Integer RT IDs)
            dropped_edges = 0
            for rel in knowledge.get("relationships", []):
                source_name = rel.get("source_concept", "").lower()
                target_name = rel.get("target_concept", "").lower()
                rel_string = rel.get("relationship_type", "")
                
                # Convert string to DB Integer (rt)
                rt_id = RELATIONSHIP_MAP.get(rel_string, 9) # Default to 9 (related_to) if unknown

                source = concept_registry.get(source_name)
                target = concept_registry.get(target_name)

                if not source or not target:
                    dropped_edges += 1
                    continue

                rel_payload = {
                    "source_concept_uid": source["uid"],
                    "target_concept_uid": target["uid"],
                    "relationship_type_id": rt_id
                }

                # If BOTH are existing, it goes straight to the live DB edges
                if source["status"] == "MAPPED_EXISTING" and target["status"] == "MAPPED_EXISTING":
                    db_relationships.append(rel_payload)
                
                # If EITHER is a proposal, the relationship stays inside the proposal's JSON waiting room
                elif source["status"] == "PROPOSAL":
                    db_concept_proposals[source["uid"]]["proposed_relationships"].append(rel_payload)
                elif target["status"] == "PROPOSAL":
                    db_concept_proposals[target["uid"]]["proposed_relationships"].append(rel_payload)

            mysql_payload = {
                "document_id": document_id,
                "validation_stats": {
                    "proposals_generated": len(db_concept_proposals),
                    "live_edges_ready": len(db_relationships),
                    "new_synonyms": len(db_new_synonyms),
                    "dropped_invalid_edges": dropped_edges
                },
                "tables": {
                    "concept_proposals": list(db_concept_proposals.values()),
                    "concept_relationships": db_relationships,
                    "concept_terms": db_new_synonyms
                }
            }

            payload_path = doc_dir / "mysql_payload.json"
            with open(payload_path, "w", encoding="utf-8") as f:
                json.dump(mysql_payload, f, indent=4)

            if metadata_path.exists():
                with open(metadata_path, "r+", encoding="utf-8") as f:
                    meta_data = json.load(f)
                    meta_data["pipeline_status"] = "SCHEMA_MAPPED"
                    meta_data["next_step"] = f"{settings.API_V1_STR}/documents/{document_id}/schema"
                    f.seek(0)
                    json.dump(meta_data, f, indent=2)
                    f.truncate()

            logger.info(f"Schema mapping complete. {len(db_concept_proposals)} proposals ready.")
            
            return {
                "document_id": document_id,
                "pipeline_status": "SCHEMA_MAPPED",
                "validation_stats": mysql_payload["validation_stats"],
                "mysql_artifact_path": str(payload_path.relative_to(settings.BASE_DIR))
            }

        except Exception as e:
            logger.error(f"Schema Mapping failed: {str(e)}", exc_info=True)
            raise ProcessingError(f"Schema Mapping failed: {str(e)}")