import json
import uuid
import aiomysql
from typing import Dict, Any
from app.core.config import settings
from app.core.logger import logger
from app.core.exceptions import DocumentNotFoundError, ProcessingError

class MySQLService:
    def __init__(self):
        self.processed_dir = settings.STORAGE_PROCESSED_DIR
        self.raw_dir = settings.STORAGE_RAW_DIR

    async def _get_connection(self):
        try:
            return await aiomysql.connect(
                host=settings.MYSQL_HOST,
                port=settings.MYSQL_PORT,
                user=settings.MYSQL_USER,
                password=settings.MYSQL_PASSWORD,
                db=settings.MYSQL_DB,
                autocommit=False
            )
        except Exception as e:
            logger.error(f"Failed to connect to MySQL: {str(e)}")
            raise ProcessingError("Database connection failed. Is MySQL running?")

    async def commit_schema_to_db(self, document_id: str) -> Dict[str, Any]:
        doc_dir = self.processed_dir / document_id
        payload_path = doc_dir / "mysql_payload.json"
        metadata_path = self.raw_dir / document_id / "metadata.json"

        if not payload_path.exists():
            raise DocumentNotFoundError(f"MySQL payload not found for {document_id}.")

        try:
            with open(payload_path, "r", encoding="utf-8") as f:
                payload = json.load(f)

            tables = payload.get("tables", {})
            proposals = tables.get("concept_proposals", [])
            terms = tables.get("concept_terms", [])
            relationships = tables.get("concept_relationships", [])

            logger.info(f"Starting MySQL Commit: {len(proposals)} proposals, {len(relationships)} edges.")

            conn = await self._get_connection()
            async with conn.cursor() as cursor:
                try:
                    # 1. Insert Pending Proposals (Section 8.1)
                    if proposals:
                        prop_sql = """
                            INSERT IGNORE INTO concept_proposals 
                            (proposal_uid, proposed_type, proposed_name, proposed_name_normalized, 
                             proposed_definition, proposed_data, proposed_terms, proposed_relationships, 
                             status, created_by) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending', 'document_pipeline')
                        """
                        prop_values = [
                            (
                                p["proposal_uid"], 
                                p["proposed_type"], 
                                p["proposed_name"], 
                                p["proposed_name_normalized"], 
                                p["proposed_definition"], 
                                json.dumps(p["proposed_data"]), 
                                json.dumps(p["proposed_terms"]), 
                                json.dumps(p["proposed_relationships"])
                            ) 
                            for p in proposals
                        ]
                        await cursor.executemany(prop_sql, prop_values)

                    # 2. Insert Concept Terms (Using term_type ENUM)
                    if terms:
                        term_sql = """
                            INSERT IGNORE INTO concept_terms (concept_uid, term, term_type, status) 
                            VALUES (%s, %s, %s, 'approved')
                        """
                        term_values = [
                            (t["concept_uid"], t["term"], t["term_type"]) 
                            for t in terms
                        ]
                        await cursor.executemany(term_sql, term_values)

                    # 3. Insert Live Relationships (Using integer relationship_type_id)
                    if relationships:
                        rel_sql = """
                            INSERT IGNORE INTO concept_relationships 
                            (source_concept_uid, target_concept_uid, relationship_type_id, status, created_by) 
                            VALUES (%s, %s, %s, 'approved', 'document_pipeline')
                        """
                        rel_values = [
                            (r["source_concept_uid"], r["target_concept_uid"], r["relationship_type_id"]) 
                            for r in relationships
                        ]
                        await cursor.executemany(rel_sql, rel_values)

                    await conn.commit()
                    logger.info(f"Successfully committed payload to database for {document_id}")

                except Exception as db_error:
                    await conn.rollback()
                    logger.error(f"Database transaction failed. Rolled back. Error: {str(db_error)}")
                    raise db_error
                finally:
                    conn.close()

            # Update Pipeline State
            if metadata_path.exists():
                with open(metadata_path, "r+", encoding="utf-8") as f:
                    meta_data = json.load(f)
                    meta_data["pipeline_status"] = "COMMITTED_TO_DB"
                    meta_data["next_step"] = "PIPELINE_COMPLETE"
                    f.seek(0)
                    json.dump(meta_data, f, indent=2)
                    f.truncate()

            return {
                "document_id": document_id,
                "pipeline_status": "COMMITTED_TO_DB",
                "inserted_stats": {
                    "proposals": len(proposals),
                    "terms": len(terms),
                    "relationships": len(relationships)
                }
            }

        except Exception as e:
            logger.error(f"MySQL commit failed for {document_id}: {str(e)}", exc_info=True)
            raise ProcessingError(f"Database commit failed: {str(e)}")