import logging
from typing import Dict, Any

from app.services.canonical_service import CanonicalService
from app.services.schema_service import SchemaService
from app.services.mysql_service import MySQLService

logger = logging.getLogger(__name__)

class KnowledgeIndexAdapter:
    """
    Authoritative adapter orchestrating the existing pipeline:

    extracted_knowledge.json
        -> CanonicalService
        -> canonical_mapping.json
        -> SchemaService
        -> mysql_payload.json
        -> MySQLService
        -> existing TagTaste Concept DB

    The adapter does not introduce a new persistence model, vector store,
    transaction boundary, or cross-service rollback mechanism.
    """
    def __init__(
        self,
        canonical_service: CanonicalService = None,
        schema_service: SchemaService = None,
        mysql_service: MySQLService = None
    ):
        self.canonical_service = (
            canonical_service if canonical_service is not None
            else CanonicalService()
        )
        self.schema_service = (
            schema_service if schema_service is not None
            else SchemaService()
        )
        self.mysql_service = (
            mysql_service if mysql_service is not None
            else MySQLService()
        )

    async def index_knowledge(self, document_id: str) -> Dict[str, Any]:
        """
        Sequentially executes the verified existing pipeline services.
        Underlying exceptions propagate naturally without modification.
        """
        logger.info(f"Starting authoritative knowledge indexing for document: {document_id}")

        # Execute active CanonicalService normalization (produces canonical_mapping.json)
        canonical_result = await self.canonical_service.normalize_concepts(document_id)

        # Execute SchemaService payload compilation (produces mysql_payload.json and updates metadata)
        schema_result = await self.schema_service.build_mysql_payload(document_id)

        # Execute MySQLService live database commit (raw SQL transaction via aiomysql)
        db_result = await self.mysql_service.commit_schema_to_db(document_id)

        logger.info(f"Successfully completed knowledge indexing for document: {document_id}")
        return {
            "success": True,
            "document_id": document_id,
            "canonical_result": canonical_result,
            "schema_result": schema_result,
            "db_result": db_result
        }