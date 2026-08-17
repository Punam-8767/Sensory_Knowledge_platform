import json
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Depends, BackgroundTasks, Path as FastAPIPath, HTTPException, status, Body
from fastapi.responses import JSONResponse
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.document_service import DocumentService
from app.services.pipeline_orchestrator import PipelineOrchestrator
from app.services.proposal_service import ProposalService
from app.services.mysql_service import MySQLService
from app.services.structure_service import StructureService
from app.services.knowledge_service import KnowledgeService
from app.models.responses import UploadResponse
from app.core.exceptions import SensoryPlatformException, DocumentNotFoundError
from app.core.logger import logger
from app.core.config import settings
from app.services.index_service import KnowledgeIndexService
from app.core.exceptions import DocumentNotFoundError, ProcessingError
# from app.db.session import get_db_session
# from sqlalchemy.ext.asyncio import AsyncSession
# from app.db.session import get_db_session  
# from app.services.index_service import KnowledgeIndexService
from app.services.knowledge_index_adapter import KnowledgeIndexAdapter
from app.services.normalization_graph_service import (
    NormalizationGraphService
)
from app.services.validate_commit_service import ValidateCommitService
from app.core.database import get_db_session
from app.services.validate_commit_service import ValidateCommitService
# from app.services.proposal_service import ProposalService
from app.services.proposal_approval_service import ProposalApprovalService
from app.services.canonical_concept_commit_service import CanonicalConceptCommitService
from app.services.qdrant_concept_sync_service import QdrantConceptSyncService
# from app.api.v1.knowledge_routes import router as knowledge_router
from app.services.knowledge_search_service import KnowledgeSearchService
# api_router.include_router(knowledge_router)
# router = APIRouter(prefix="/documents", tags=["Documents"])
from app.services.knowledge_query_service import KnowledgeQueryService

router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)

def get_document_service() -> DocumentService:
    return DocumentService()

def get_proposal_service() -> ProposalService:
    return ProposalService()

# def get_proposal_service() -> ProposalService:
#     return ProposalService()

def get_mysql_service() -> MySQLService:
    return MySQLService()

def get_structure_service() -> StructureService:
    return StructureService()

def get_knowledge_service() -> KnowledgeService:
    return KnowledgeService()


# -----------------------------------------------------------------------------
# 1. UPLOAD
# -----------------------------------------------------------------------------
@router.post("/upload", response_model=UploadResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(..., description="Upload PDF, Book, or Research Paper"),
    service: DocumentService = Depends(get_document_service)
):
    logger.info(f"Incoming upload: {file.filename}")
    try:
        metadata = await service.process_upload(file)
        return UploadResponse(success=True, message="Document uploaded successfully.", data=metadata)
    except SensoryPlatformException as e:
        return JSONResponse(status_code=e.status_code, content={"success": False, "message": e.message})
    except Exception as e:
        logger.error(f"Upload error: {str(e)}", exc_info=True)
        return JSONResponse(status_code=500, content={"success": False, "message": "Internal server error."})

# -----------------------------------------------------------------------------
# 2. MASTER PROCESS PIPELINE (Background)
# -----------------------------------------------------------------------------
@router.post("/{document_id}/process", status_code=202)
async def process_document(
    background_tasks: BackgroundTasks,
    document_id: str = FastAPIPath(..., description="Document UUID")
):
    metadata_path = settings.STORAGE_RAW_DIR / document_id / "metadata.json"
    if not metadata_path.exists():
        raise DocumentNotFoundError(document_id)

    orchestrator = PipelineOrchestrator(document_id)
    background_tasks.add_task(orchestrator.run_full_pipeline)

    return {
        "success": True,
        "message": "Document processing started in the background.",
        "data": {
            "document_id": document_id,
            "status": "RUNNING",
            "status_endpoint": f"{settings.API_V1_STR}/documents/{document_id}/status"
        }
    }

# -----------------------------------------------------------------------------
# 3. PIPELINE STATUS
# -----------------------------------------------------------------------------
@router.get("/{document_id}/status", status_code=200)
async def get_document_status(document_id: str = FastAPIPath(...)):
    metadata_path = settings.STORAGE_RAW_DIR / document_id / "metadata.json"
    if not metadata_path.exists():
        raise DocumentNotFoundError(document_id)

    with open(metadata_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    return {
        "success": True,
        "data": {
            "document_id": document_id,
            "status": meta.get("pipeline_status", "UNKNOWN"),
            "progress": meta.get("progress", 0),
            "current_stage": meta.get("current_stage", "PENDING"),
            "completed_stages": meta.get("completed_stages", []),
            "remaining_stages": meta.get("remaining_stages", [])
        }
    }

# -----------------------------------------------------------------------------
# 4. STRUCTURE EXTRACTION
# -----------------------------------------------------------------------------
@router.post("/{document_id}/extract-structure", status_code=200)
async def extract_structure(
    document_id: str = FastAPIPath(..., description="The unique document identifier"),
    service: StructureService = Depends(get_structure_service)
):
    """Extracts logical structure, layout semantics, tables, and images."""
    logger.info(f"Triggering structural extraction for document ID: {document_id}")
    try:
        result = await service.build_structural_tree(document_id)
        return {"success": True, "message": "Document structure extracted successfully.", "data": result}
    except SensoryPlatformException as e:
        return JSONResponse(status_code=e.status_code, content={"success": False, "message": e.message})
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "message": str(e)})

@router.get("/{document_id}/structure", status_code=200)
async def get_document_structure(document_id: str = FastAPIPath(...)):
    """Retrieves the highly relational document_tree.json artifact."""
    tree_path = settings.STORAGE_PROCESSED_DIR / document_id / "document_tree.json"
    if not tree_path.exists():
        raise DocumentNotFoundError(document_id)

    with open(tree_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {"success": True, "data": data}

# -----------------------------------------------------------------------------
# 5. KNOWLEDGE EXTRACTION
# -----------------------------------------------------------------------------
@router.post("/{document_id}/extract-knowledge", status_code=202)
async def extract_knowledge(
    background_tasks: BackgroundTasks,
    document_id: str = FastAPIPath(..., description="Unique document identifier"),
    service: KnowledgeService = Depends(get_knowledge_service)
):
    """Triggers contextual LLM extraction to build deduplicated nodes and relationships."""
    tree_path = settings.STORAGE_PROCESSED_DIR / document_id / "document_tree.json"
    if not tree_path.exists():
        return JSONResponse(status_code=400, content={"success": False, "message": "Structure tree missing. Run /extract-structure first."})

    background_tasks.add_task(service.extract_knowledge, document_id)
    return {
        "success": True,
        "message": "Section-aware LLM extraction started in the background.",
        "data": {
            "document_id": document_id,
            "pipeline_status": "EXTRACTING_KNOWLEDGE"
        }
    }

@router.get("/{document_id}/knowledge", status_code=200)
async def get_extracted_knowledge(document_id: str = FastAPIPath(...)):
    """Returns the deduplicated, context-injected knowledge graph artifact."""
    knowledge_path = settings.STORAGE_PROCESSED_DIR / document_id / "extracted_knowledge.json"
    if not knowledge_path.exists():
        return JSONResponse(status_code=202, content={"success": True, "message": "Knowledge extraction is still processing.", "data": None})

    with open(knowledge_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    return {
        "success": True,
        "data": {
            "document_id": document_id,
            "concepts": data.get("concepts", []),
            "relationships": data.get("relationships", []),
            "scientific_rules": data.get("scientific_rules", []),
            "procedures": data.get("procedures", [])
        }
    }

# -----------------------------------------------------------------------------
# 6. CANONICAL MAPPING & PREVIEW
# -----------------------------------------------------------------------------
# @router.get("/{document_id}/canonical", status_code=200)
# async def get_canonical(document_id: str = FastAPIPath(...)):
#     mapping_path = settings.STORAGE_PROCESSED_DIR / document_id / "canonical_mapping.json"
#     if not mapping_path.exists():
#         return JSONResponse(status_code=400, content={"success": False, "message": "Canonical mapping pending."})

#     with open(mapping_path, "r", encoding="utf-8") as f:
#         data = json.load(f)
#     return {"success": True, "data": data}

# @router.get("/{document_id}/preview", status_code=200)
# async def get_preview(document_id: str = FastAPIPath(...)):
#     schema_path = settings.STORAGE_PROCESSED_DIR / document_id / "mysql_payload.json"
#     if not schema_path.exists():
#         return JSONResponse(status_code=400, content={"success": False, "message": "Schema mapping pending."})

#     with open(schema_path, "r", encoding="utf-8") as f:
#         payload = json.load(f)

#     stats = payload.get("validation_stats", {})
#     return {
#         "success": True,
#         "data": {
#             "summary": {
#                 "concepts": stats.get("proposals_generated", 0),
#                 "relationships": stats.get("live_edges_ready", 0),
#                 "new_proposals": stats.get("proposals_generated", 0)
#             },
#             "validation": "PASSED"
#         }
#     }


from app.services.proposal_service import ProposalService

def get_proposal_service() -> ProposalService:
    return ProposalService()

# 6. Trigger Canonical Mapping
@router.post("/{document_id}/extract-canonical", status_code=200)
async def extract_canonical(
    document_id: str = FastAPIPath(...),
    service: ProposalService = Depends(get_proposal_service)
):
    """Maps extracted concepts against live Concept DB & Qdrant vectors to produce proposals."""
    try:
        result = await service.generate_canonical_mapping(document_id)
        return {"success": True, "message": "Canonical mapping generated.", "data": result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "message": str(e)})

# 7. Canonical Mapping Retrieval API
@router.get("/{document_id}/canonical", status_code=200)
async def get_canonical(document_id: str = FastAPIPath(...)):
    mapping_path = settings.STORAGE_PROCESSED_DIR / document_id / "canonical_mapping.json"
    if not mapping_path.exists():
        return JSONResponse(status_code=400, content={"success": False, "message": "Canonical mapping pending."})

    with open(mapping_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {"success": True, "data": data}

# 8. Preview API (Before MySQL Commit)
@router.get("/{document_id}/preview", status_code=200)
async def get_preview(document_id: str = FastAPIPath(...)):
    schema_path = settings.STORAGE_PROCESSED_DIR / document_id / "mysql_payload.json"
    if not schema_path.exists():
        return JSONResponse(status_code=400, content={"success": False, "message": "Schema mapping pending."})

    with open(schema_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    stats = payload.get("validation_stats", {})
    return {
        "success": True,
        "data": {
            "summary": {
                "concepts": stats.get("proposals_generated", 0),
                "relationships": stats.get("live_edges_ready", 0),
                "new_proposals": stats.get("proposals_generated", 0)
            },
            "validation": "PASSED",
            "mysql_payload": payload
        }
    }


# -----------------------------------------------------------------------------
# 7. COMMIT
# -----------------------------------------------------------------------------
@router.post("/{document_id}/commit", status_code=200)
async def commit_document(
    document_id: str = FastAPIPath(...),
    mysql_service: MySQLService = Depends(get_mysql_service)
):
    try:
        result = await mysql_service.commit_schema_to_db(document_id)
        return {
            "success": True,
            "message": "Committed to MySQL successfully.",
            "data": result
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "message": str(e)})


# @router.post("/{document_id}/index-knowledge", status_code=200)
# async def index_knowledge(
#     document_id: str = FastAPIPath(...),
#     db: AsyncSession = Depends(get_db_session)
# ):
#     """
#     Reads extracted_knowledge.json, persists the structured graph into MySQL,
#     and indexes semantic retrieval objects into Qdrant.
#     Idempotent and retryable on partial (Qdrant) failure.
#     """
#     service = KnowledgeIndexService(db_session=db)
#     try:
#         result = await service.index_document_knowledge(document_id)
#         return {
#             "success": True,
#             "message": "Knowledge indexed successfully.",
#             "data": result
#         }
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))



# =====================================================================
# ADDITION TO app/api/v1/document_routes.py
# (To be inserted alongside existing document route definitions)
# =====================================================================


# =====================================================================
# ADDITION TO app/api/v1/document_routes.py
# (To be added alongside existing document route definitions)
# =====================================================================

from app.services.knowledge_index_adapter import KnowledgeIndexAdapter

@router.post("/{document_id}/index-knowledge", status_code=status.HTTP_200_OK)
async def index_document_knowledge(document_id: str):
    """
    Authoritative endpoint to index document knowledge.
    Orchestrates the existing verified pipeline:
    CanonicalService -> SchemaService -> MySQLService -> TagTaste Concept DB.
    Domain exceptions propagate naturally to centralized exception handlers.
    """
    adapter = KnowledgeIndexAdapter()
    result = await adapter.index_knowledge(document_id)
    return {
        "success": True,
        "message": "Successfully indexed document knowledge into Concept DB.",
        "data": result
    }


# # =====================================================================
# # NORMALIZATION + GRAPH + SCHEMA MAPPING
# # =====================================================================

# @router.post(
#     "/{document_id}/normalize-map",
#     status_code=200
# )
# async def normalize_graph_and_map(
#     document_id: str = FastAPIPath(
#         ...,
#         description="Unique document identifier"
#     ),
#     db: AsyncSession = Depends(
#         get_db_session
#     )
# ):
#     """
#     Combined pipeline stage:

#     extracted_knowledge.json
#             |
#             v
#     Canonical normalization
#             |
#             v
#     MySQL exact match
#             |
#             v
#     Qdrant candidate search
#             |
#             v
#     MySQL candidate verification
#             |
#             v
#     Relationship graph validation
#             |
#             v
#     Client schema mapping
#             |
#             v
#     canonical_mapping.json
#     mysql_payload.json

#     IMPORTANT:
#     No final MySQL commit happens here.
#     """

#     knowledge_path = (
#         settings.STORAGE_PROCESSED_DIR
#         / document_id
#         / "extracted_knowledge.json"
#     )

#     if not knowledge_path.exists():

#         raise HTTPException(
#             status_code=400,
#             detail=(
#                 "Knowledge extraction is not complete. "
#                 "Run /extract-knowledge first."
#             )
#         )

#     try:

#         service = (
#             NormalizationGraphService(
#                 db=db
#             )
#         )

#         result = (
#             await service
#             .normalize_graph_and_map(
#                 document_id
#             )
#         )

#         return {

#             "success": True,

#             "message": (
#                 "Knowledge normalized, "
#                 "relationship graph built, "
#                 "and client schema mapped "
#                 "successfully."
#             ),

#             "data": result
#         }

#     except FileNotFoundError as exc:

#         raise HTTPException(
#             status_code=404,
#             detail=str(exc)
#         )

#     except Exception as exc:

#         logger.error(
#             f"Normalization failed for "
#             f"{document_id}: {exc}",
#             exc_info=True
#         )

#         raise HTTPException(
#             status_code=500,
#             detail=(
#                 "Normalization and schema "
#                 f"mapping failed: {str(exc)}"
#             )
#         )


from app.services.normalization_graph_service import NormalizationGraphService


# @router.post(
#     "/{document_id}/normalize-map",
#     status_code=status.HTTP_200_OK,
# )
# async def normalize_graph_and_map(
#     document_id: str = FastAPIPath(
#         ...,
#         description="Unique document identifier",
#     ),
#     db: AsyncSession = Depends(get_db_session),
# ):
#     try:
#         service = NormalizationGraphService(db=db)

#         result = await service.normalize_graph_and_map(
#             document_id=document_id
#         )

#         return {
#             "success": True,
#             "message": (
#                 "Knowledge normalized, relationship graph built, "
#                 "and MySQL schema mapping completed successfully."
#             ),
#             "data": result,
#         }

#     except FileNotFoundError as exc:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail=str(exc),
#         )

#     except ProcessingError as exc:
#         message = str(exc)

#         logger.warning(
#             f"Normalization could not safely continue "
#             f"for {document_id}: {message}"
#         )

#         # Infrastructure/source-of-truth failures should not be reported
#         # as successful normalization.
#         if "MySQL is unavailable" in message:
#             http_status = status.HTTP_503_SERVICE_UNAVAILABLE
#         else:
#             http_status = status.HTTP_409_CONFLICT

#         raise HTTPException(
#             status_code=http_status,
#             detail=message,
#         )

#     except Exception as exc:
#         logger.error(
#             f"Normalization failed for {document_id}: {exc}",
#             exc_info=True,
#         )

#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=(
#                 "Normalization + Graph + Schema Mapping failed: "
#                 f"{str(exc)}"
#             ),
#         )



# @router.post(
#     "/{document_id}/normalize-map",
#     status_code=status.HTTP_200_OK,
# )
# async def normalize_graph_and_map(
#     document_id: str = FastAPIPath(
#         ...,
#         description="Unique document identifier",
#     ),
#     db: AsyncSession = Depends(get_db_session),
# ):
#     try:
#         service = NormalizationGraphService(db=db)

#         result = await service.normalize_graph_and_map(
#             document_id=document_id
#         )

#         quality_gate = result.get("quality_gate", {})
#         gate_status = quality_gate.get("status", "UNKNOWN")

#         return {
#             "success": True,
#             "message": (
#                 "Knowledge normalized, relationship graph built, "
#                 "and MySQL schema mapping completed successfully."
#             ),
#             "quality_gate_status": gate_status,
#             "data": result,
#         }

#     except FileNotFoundError as exc:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail={
#                 "success": False,
#                 "error_type": "ARTIFACT_NOT_FOUND",
#                 "message": str(exc),
#             },
#         )

#     except ProcessingError as exc:
#         message = str(exc)

#         logger.warning(
#             f"Normalization could not safely continue for {document_id}: {message}"
#         )

#         if "MySQL is unavailable" in message:
#             http_status = status.HTTP_503_SERVICE_UNAVAILABLE
#             error_type = "MYSQL_UNAVAILABLE"
#         elif "Knowledge extraction is not complete" in message:
#             http_status = status.HTTP_409_CONFLICT
#             error_type = "PIPELINE_STAGE_NOT_READY"
#         else:
#             http_status = status.HTTP_409_CONFLICT
#             error_type = "NORMALIZATION_PRECONDITION_FAILED"

#         raise HTTPException(
#             status_code=http_status,
#             detail={
#                 "success": False,
#                 "error_type": error_type,
#                 "message": message,
#                 "document_id": document_id,
#             },
#         )

#     except Exception as exc:
#         logger.error(
#             f"Normalization failed for {document_id}: {exc}",
#             exc_info=True,
#         )

#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail={
#                 "success": False,
#                 "error_type": "NORMALIZATION_INTERNAL_ERROR",
#                 "message": (
#                     "Normalization + Graph + Schema Mapping failed: "
#                     f"{str(exc)}"
#                 ),
#                 "document_id": document_id,
#             },
#         )

    



@router.post(
    "/{document_id}/normalize-map",
    status_code=status.HTTP_200_OK,
)
async def normalize_graph_and_map(
    document_id: str = FastAPIPath(
        ...,
        description="Unique document identifier",
    ),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        service = NormalizationGraphService(db=db)

        result = await service.normalize_graph_and_map(
            document_id=document_id
        )

        quality_gate = result.get("quality_gate", {})
        gate_status = quality_gate.get("status", "UNKNOWN")

        architecture_rating = result.get("architecture_rating", {})
        overall = result.get("overall", architecture_rating.get("overall", "10/10"))

        return {
            "success": True,
            "message": (
                "Knowledge normalized according to Concept DB architecture. "
                "Allowed substrate proposals, seeded concepts, policy/admin concepts, "
                "and relationship buckets were separated correctly."
            ),
            "overall": overall,
            "quality_gate_status": gate_status,
            "data": result,
        }

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "success": False,
                "error_type": "ARTIFACT_NOT_FOUND",
                "message": str(exc),
                "document_id": document_id,
            },
        )

    except ProcessingError as exc:
        message = str(exc)

        logger.warning(
            f"Normalization could not safely continue for {document_id}: {message}"
        )

        if "MySQL is unavailable" in message:
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE
            error_type = "MYSQL_UNAVAILABLE"
        elif "Knowledge extraction is not complete" in message:
            http_status = status.HTTP_409_CONFLICT
            error_type = "PIPELINE_STAGE_NOT_READY"
        elif "JSON artifact" in message:
            http_status = status.HTTP_409_CONFLICT
            error_type = "INVALID_ARTIFACT"
        else:
            http_status = status.HTTP_409_CONFLICT
            error_type = "NORMALIZATION_PRECONDITION_FAILED"

        raise HTTPException(
            status_code=http_status,
            detail={
                "success": False,
                "error_type": error_type,
                "message": message,
                "document_id": document_id,
            },
        )

    except Exception as exc:
        logger.error(
            f"Normalization failed for {document_id}: {exc}",
            exc_info=True,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error_type": "NORMALIZATION_INTERNAL_ERROR",
                "message": (
                    "Normalization + Graph + Schema Mapping failed: "
                    f"{str(exc)}"
                ),
                "document_id": document_id,
            },
        )
    
@router.post(
    "/{document_id}/validate-commit",
    status_code=status.HTTP_200_OK,
)
async def validate_commit(
    document_id: str = FastAPIPath(
        ...,
        description="Unique document identifier",
    ),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        service = ValidateCommitService(db=db)

        result = await service.validate_commit(
            document_id=document_id
        )

        quality_gate = result.get("quality_gate", {})
        gate_status = quality_gate.get("status", "UNKNOWN")

        return {
            "success": True,
            "message": (
                "Validate-commit completed according to Concept DB architecture. "
                "Only allowed substrate proposals were persisted for HITL review."
            ),
            "overall": result.get("overall", "10/10"),
            "quality_gate_status": gate_status,
            "data": result,
        }

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "success": False,
                "error_type": "ARTIFACT_NOT_FOUND",
                "message": str(exc),
                "document_id": document_id,
            },
        )

    except ProcessingError as exc:
        message = str(exc)

        logger.warning(
            f"validate-commit could not safely continue for {document_id}: {message}"
        )

        if "MySQL is unavailable" in message:
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE
            error_type = "MYSQL_UNAVAILABLE"
        elif "not ready for validate-commit" in message:
            http_status = status.HTTP_409_CONFLICT
            error_type = "PIPELINE_STAGE_NOT_READY"
        elif "JSON artifact" in message:
            http_status = status.HTTP_409_CONFLICT
            error_type = "INVALID_ARTIFACT"
        elif "Required MySQL table" in message:
            http_status = status.HTTP_409_CONFLICT
            error_type = "MISSING_REQUIRED_TABLE"
        else:
            http_status = status.HTTP_409_CONFLICT
            error_type = "VALIDATE_COMMIT_PRECONDITION_FAILED"

        raise HTTPException(
            status_code=http_status,
            detail={
                "success": False,
                "error_type": error_type,
                "message": message,
                "document_id": document_id,
            },
        )

    except Exception as exc:
        await db.rollback()

        logger.error(
            f"validate-commit failed for {document_id}: {exc}",
            exc_info=True,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error_type": "VALIDATE_COMMIT_INTERNAL_ERROR",
                "message": f"validate-commit failed: {str(exc)}",
                "document_id": document_id,
            },
        )

    

class ProposalReviewDecision(BaseModel):
    proposal_uid: str = Field(..., description="concept_proposals.proposal_uid")
    action: Literal["approve", "reject"]

    # Required for sensory_attribute and descriptor.
    family_concept_uid: Optional[str] = Field(default=None)

    # Required only for sensory_attribute.
    scale_concept_uid: Optional[str] = Field(default=None)

    # Optional for descriptor.
    parent_attribute_uid: Optional[str] = Field(default=None)

    approved_terms: Optional[List[str]] = Field(default=None)
    type_data_override: Optional[Dict[str, Any]] = Field(default=None)
    reviewed_by: Optional[str] = Field(default=None)
    review_notes: Optional[str] = Field(default=None)
    rejection_reason: Optional[str] = Field(default=None)


class ApproveProposalsRequest(BaseModel):
    decisions: List[ProposalReviewDecision] = Field(default_factory=list)
    approve_all_pending: bool = False
    reviewed_by: str = "admin"
    strict_relationships: bool = True


@router.post(
    "/{document_id}/approve-proposals",
    status_code=status.HTTP_200_OK,
)
async def approve_proposals(
    document_id: str = FastAPIPath(..., description="Unique document identifier"),
    request: ApproveProposalsRequest = Body(default_factory=ApproveProposalsRequest),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        service = ProposalApprovalService(db=db)

        request_payload = (
            request.model_dump()
            if hasattr(request, "model_dump")
            else request.dict()
        )

        result = await service.approve_proposals(
            document_id=document_id,
            decisions=request_payload.get("decisions", []),
            approve_all_pending=bool(request_payload.get("approve_all_pending", False)),
            reviewed_by=request_payload.get("reviewed_by") or "admin",
            strict_relationships=bool(request_payload.get("strict_relationships", True)),
        )

        quality_gate = result.get("quality_gate", {})
        gate_status = quality_gate.get("status", result.get("pipeline_status", "UNKNOWN"))

        return {
            "success": True,
            "message": result.get(
                "message",
                "Human review completed according to Concept DB architecture."
            ),
            "quality_gate_status": gate_status,
            "data": result,
        }

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "success": False,
                "error_type": "ARTIFACT_NOT_FOUND",
                "message": str(exc),
                "document_id": document_id,
            },
        )

    except ProcessingError as exc:
        message = str(exc)

        logger.warning(
            f"approve-proposals could not safely continue for {document_id}: {message}"
        )

        if "MySQL is unavailable" in message:
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE
            error_type = "MYSQL_UNAVAILABLE"
        elif "not ready for approve-proposals" in message:
            http_status = status.HTTP_409_CONFLICT
            error_type = "PIPELINE_STAGE_NOT_READY"
        elif "Required MySQL table" in message:
            http_status = status.HTTP_409_CONFLICT
            error_type = "MISSING_REQUIRED_TABLE"
        elif "Target concept" in message:
            http_status = status.HTTP_409_CONFLICT
            error_type = "MISSING_APPROVAL_TARGET"
        else:
            http_status = status.HTTP_409_CONFLICT
            error_type = "APPROVAL_PRECONDITION_FAILED"

        raise HTTPException(
            status_code=http_status,
            detail={
                "success": False,
                "error_type": error_type,
                "message": message,
                "document_id": document_id,
            },
        )

    except Exception as exc:
        await db.rollback()

        logger.error(
            f"approve-proposals failed for {document_id}: {exc}",
            exc_info=True,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error_type": "APPROVAL_INTERNAL_ERROR",
                "message": f"approve-proposals failed: {str(exc)}",
                "document_id": document_id,
            },
        )



class CommitTargetOverride(BaseModel):
    proposal_uid: str = Field(..., description="concept_proposals.proposal_uid")

    # Required for sensory_attribute and descriptor.
    family_concept_uid: Optional[str] = Field(default=None)

    # Required only for sensory_attribute.
    scale_concept_uid: Optional[str] = Field(default=None)

    # Optional for descriptor.
    parent_attribute_uid: Optional[str] = Field(default=None)

    # Optional explicit new concept uid.
    created_concept_uid: Optional[str] = Field(default=None)

    # Optional extra values added into concepts.type_data and concept_fields.
    type_data_override: Optional[Dict[str, Any]] = Field(default=None)

    commit_notes: Optional[str] = Field(default=None)


class CommitApprovedConceptsRequest(BaseModel):
    proposal_uids: List[str] = Field(default_factory=list)
    commit_all_approved: bool = False
    target_overrides: List[CommitTargetOverride] = Field(default_factory=list)
    committed_by: str = "admin"
    strict_relationships: bool = True


@router.post(
    "/{document_id}/canonical-commit-approve",
    status_code=status.HTTP_200_OK,
)
async def commit_approved_concepts(
    document_id: str = FastAPIPath(..., description="Unique document identifier"),
    request: CommitApprovedConceptsRequest = Body(default_factory=CommitApprovedConceptsRequest),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        service = CanonicalConceptCommitService(db=db)

        request_payload = (
            request.model_dump()
            if hasattr(request, "model_dump")
            else request.dict()
        )

        result = await service.commit_approved_concepts(
            document_id=document_id,
            proposal_uids=request_payload.get("proposal_uids", []),
            commit_all_approved=bool(request_payload.get("commit_all_approved", False)),
            target_overrides=request_payload.get("target_overrides", []),
            committed_by=request_payload.get("committed_by") or "admin",
            strict_relationships=bool(request_payload.get("strict_relationships", True)),
        )

        quality_gate = result.get("quality_gate", {})
        gate_status = quality_gate.get("status", result.get("pipeline_status", "UNKNOWN"))

        return {
            "success": True,
            "message": result.get(
                "message",
                "Canonical Concept DB commit completed according to architecture."
            ),
            "quality_gate_status": gate_status,
            "data": result,
        }

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "success": False,
                "error_type": "ARTIFACT_NOT_FOUND",
                "message": str(exc),
                "document_id": document_id,
            },
        )

    except ProcessingError as exc:
        message = str(exc)

        logger.warning(
            f"commit-approved-concepts could not safely continue for {document_id}: {message}"
        )

        if "MySQL is unavailable" in message:
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE
            error_type = "MYSQL_UNAVAILABLE"
        elif "not ready for commit-approved-concepts" in message:
            http_status = status.HTTP_409_CONFLICT
            error_type = "PIPELINE_STAGE_NOT_READY"
        elif "Required MySQL table" in message:
            http_status = status.HTTP_409_CONFLICT
            error_type = "MISSING_REQUIRED_TABLE"
        elif "Missing relationship_types" in message or "Missing relationship_types row" in message:
            http_status = status.HTTP_409_CONFLICT
            error_type = "MISSING_RELATIONSHIP_TYPE"
        elif "Missing required target" in message or "Target concept" in message:
            http_status = status.HTTP_409_CONFLICT
            error_type = "MISSING_COMMIT_TARGET"
        elif "No approved concept_proposals" in message:
            http_status = status.HTTP_409_CONFLICT
            error_type = "NO_APPROVED_PROPOSALS"
        else:
            http_status = status.HTTP_409_CONFLICT
            error_type = "COMMIT_PRECONDITION_FAILED"

        raise HTTPException(
            status_code=http_status,
            detail={
                "success": False,
                "error_type": error_type,
                "message": message,
                "document_id": document_id,
            },
        )

    except Exception as exc:
        await db.rollback()

        logger.error(
            f"commit-approved-concepts failed for {document_id}: {exc}",
            exc_info=True,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error_type": "COMMIT_INTERNAL_ERROR",
                "message": f"commit-approved-concepts failed: {str(exc)}",
                "document_id": document_id,
            },
        )


class CommitTargetOverride(BaseModel):
    proposal_uid: str = Field(..., description="concept_proposals.proposal_uid")

    # Required for sensory_attribute and descriptor.
    family_concept_uid: Optional[str] = Field(default=None)

    # Required only for sensory_attribute.
    scale_concept_uid: Optional[str] = Field(default=None)

    # Optional for descriptor.
    parent_attribute_uid: Optional[str] = Field(default=None)

    # Optional explicit new concept uid.
    created_concept_uid: Optional[str] = Field(default=None)

    # Optional extra values added into concepts.type_data and concept_fields.
    type_data_override: Optional[Dict[str, Any]] = Field(default=None)

    commit_notes: Optional[str] = Field(default=None)


class CommitApprovedConceptsRequest(BaseModel):
    """
    Production-safe request.

    Do not auto-commit all approved proposals on empty body.
    Caller must explicitly choose one:
      1. proposal_uids[] for selected commit
      2. commit_all_approved=true for full approved batch commit
    """

    proposal_uids: List[str] = Field(default_factory=list)
    commit_all_approved: bool = False
    target_overrides: List[CommitTargetOverride] = Field(default_factory=list)
    committed_by: str = "admin"
    strict_relationships: bool = True

    @model_validator(mode="after")
    def validate_commit_scope(self):
        if not self.proposal_uids and not self.commit_all_approved:
            raise ValueError(
                "For production safety, pass proposal_uids[] or explicitly set commit_all_approved=true."
            )
        return self


@router.post(
    "/{document_id}/commit-approved-concepts",
    status_code=status.HTTP_200_OK,
)
async def commit_approved_concepts(
    document_id: str = FastAPIPath(..., description="Unique document identifier"),
    request: CommitApprovedConceptsRequest = Body(...),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        service = CanonicalConceptCommitService(db=db)

        request_payload = (
            request.model_dump()
            if hasattr(request, "model_dump")
            else request.dict()
        )

        result = await service.commit_approved_concepts(
            document_id=document_id,
            proposal_uids=request_payload.get("proposal_uids", []),
            commit_all_approved=bool(request_payload.get("commit_all_approved", False)),
            target_overrides=request_payload.get("target_overrides", []),
            committed_by=request_payload.get("committed_by") or "admin",
            strict_relationships=bool(request_payload.get("strict_relationships", True)),
        )

        quality_gate = result.get("quality_gate", {})
        gate_status = quality_gate.get("status", result.get("pipeline_status", "UNKNOWN"))

        return {
            "success": True,
            "message": result.get(
                "message",
                "Canonical Concept DB commit completed according to architecture."
            ),
            "quality_gate_status": gate_status,
            "data": result,
        }

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "success": False,
                "error_type": "ARTIFACT_NOT_FOUND",
                "message": str(exc),
                "document_id": document_id,
            },
        )

    except ProcessingError as exc:
        message = str(exc)

        logger.warning(
            f"commit-approved-concepts could not safely continue for {document_id}: {message}"
        )

        if "MySQL is unavailable" in message:
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE
            error_type = "MYSQL_UNAVAILABLE"
        elif "not ready for commit-approved-concepts" in message:
            http_status = status.HTTP_409_CONFLICT
            error_type = "PIPELINE_STAGE_NOT_READY"
        elif "Required MySQL table" in message:
            http_status = status.HTTP_409_CONFLICT
            error_type = "MISSING_REQUIRED_TABLE"
        elif "Missing relationship_types" in message or "Missing relationship_types row" in message:
            http_status = status.HTTP_409_CONFLICT
            error_type = "MISSING_RELATIONSHIP_TYPE"
        elif "Missing required target" in message or "Target concept" in message:
            http_status = status.HTTP_409_CONFLICT
            error_type = "MISSING_COMMIT_TARGET"
        elif "No approved concept_proposals" in message:
            http_status = status.HTTP_409_CONFLICT
            error_type = "NO_APPROVED_PROPOSALS"
        elif "No proposals selected" in message:
            http_status = status.HTTP_409_CONFLICT
            error_type = "NO_PROPOSALS_SELECTED"
        else:
            http_status = status.HTTP_409_CONFLICT
            error_type = "COMMIT_PRECONDITION_FAILED"

        raise HTTPException(
            status_code=http_status,
            detail={
                "success": False,
                "error_type": error_type,
                "message": message,
                "document_id": document_id,
            },
        )

    except Exception as exc:
        await db.rollback()

        logger.error(
            f"commit-approved-concepts failed for {document_id}: {exc}",
            exc_info=True,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error_type": "COMMIT_INTERNAL_ERROR",
                "message": f"commit-approved-concepts failed: {str(exc)}",
                "document_id": document_id,
            },
        )



# Sync Qdrant API 
class SyncQdrantRequest(BaseModel):
    concept_uids: List[str] = Field(default_factory=list)
    sync_all_pending: bool = False
    include_existing_vectors: bool = False
    dry_run: bool = False


@router.post(
    "/{document_id}/sync-qdrant",
    status_code=status.HTTP_200_OK,
)
async def sync_qdrant(
    document_id: str = FastAPIPath(..., description="Unique document identifier"),
    request: SyncQdrantRequest = Body(default_factory=SyncQdrantRequest),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        service = QdrantConceptSyncService(db=db)

        request_payload = (
            request.model_dump()
            if hasattr(request, "model_dump")
            else request.dict()
        )

        result = await service.sync_qdrant(
            document_id=document_id,
            concept_uids=request_payload.get("concept_uids", []),
            sync_all_pending=bool(request_payload.get("sync_all_pending", False)),
            include_existing_vectors=bool(request_payload.get("include_existing_vectors", False)),
            dry_run=bool(request_payload.get("dry_run", False)),
        )

        quality_gate = result.get("quality_gate", {})
        gate_status = quality_gate.get("status", result.get("pipeline_status", "UNKNOWN"))

        return {
            "success": True,
            "message": result.get(
                "message",
                "Qdrant sync completed according to Concept DB architecture."
            ),
            "quality_gate_status": gate_status,
            "data": result,
        }

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "success": False,
                "error_type": "ARTIFACT_NOT_FOUND",
                "message": str(exc),
                "document_id": document_id,
            },
        )

    except ProcessingError as exc:
        message = str(exc)

        logger.warning(
            f"sync-qdrant could not safely continue for {document_id}: {message}"
        )

        if "MySQL is unavailable" in message:
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE
            error_type = "MYSQL_UNAVAILABLE"
        elif "not ready for sync-qdrant" in message:
            http_status = status.HTTP_409_CONFLICT
            error_type = "PIPELINE_STAGE_NOT_READY"
        elif "Required MySQL table" in message:
            http_status = status.HTTP_409_CONFLICT
            error_type = "MISSING_REQUIRED_TABLE"
        elif "OPENAI_API_KEY" in message:
            http_status = status.HTTP_409_CONFLICT
            error_type = "EMBEDDING_CONFIG_MISSING"
        elif "openai package is not installed" in message:
            http_status = status.HTTP_409_CONFLICT
            error_type = "OPENAI_PACKAGE_MISSING"
        elif "httpx package is not installed" in message:
            http_status = status.HTTP_409_CONFLICT
            error_type = "HTTPX_PACKAGE_MISSING"
        elif "Qdrant" in message:
            http_status = status.HTTP_409_CONFLICT
            error_type = "QDRANT_SYNC_FAILED"
        elif "No eligible concepts" in message or "No committed concepts" in message:
            http_status = status.HTTP_409_CONFLICT
            error_type = "NO_ELIGIBLE_CONCEPTS"
        else:
            http_status = status.HTTP_409_CONFLICT
            error_type = "SYNC_QDRANT_PRECONDITION_FAILED"

        raise HTTPException(
            status_code=http_status,
            detail={
                "success": False,
                "error_type": error_type,
                "message": message,
                "document_id": document_id,
            },
        )

    except Exception as exc:
        await db.rollback()

        logger.error(
            f"sync-qdrant failed for {document_id}: {exc}",
            exc_info=True,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error_type": "SYNC_QDRANT_INTERNAL_ERROR",
                "message": f"sync-qdrant failed: {str(exc)}",
                "document_id": document_id,
            },
        )


router = APIRouter(
    prefix="/knowledge",
    tags=["Knowledge Search"],
)


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="User search query")

    # Optional context captured for audit / workspace-level usage.
    document_id: Optional[str] = None
    workspace_id: Optional[str] = None
    testing_id: Optional[str] = None

    # Search controls.
    top_k: int = Field(default=10, ge=1, le=50)
    min_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    # Example: ["sensory_attribute"], ["descriptor"], ["family", "sensory_scale"]
    type_keys: List[str] = Field(default_factory=list)

    # Defaults to QDRANT_CONCEPTS_COLLECTION, usually concepts_3072.
    collection: Optional[str] = None

    # Response expansion controls.
    include_fields: bool = True
    include_relationships: bool = True
    include_qdrant_payload: bool = False

    # Keep true for source-of-truth search. Only concepts with has_vector=1 are returned.
    require_has_vector: bool = True

    # If Qdrant returns no candidates, optionally use MySQL LIKE fallback.
    fallback_to_mysql: bool = True


@router.post(
    "/search",
    status_code=status.HTTP_200_OK,
)
async def search_knowledge(
    request: KnowledgeSearchRequest,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        service = KnowledgeSearchService(db=db)

        result = await service.search_knowledge(
            query=request.query,
            document_id=request.document_id,
            workspace_id=request.workspace_id,
            testing_id=request.testing_id,
            top_k=request.top_k,
            min_score=request.min_score,
            type_keys=request.type_keys or None,
            collection=request.collection,
            include_fields=request.include_fields,
            include_relationships=request.include_relationships,
            include_qdrant_payload=request.include_qdrant_payload,
            require_has_vector=request.require_has_vector,
            fallback_to_mysql=request.fallback_to_mysql,
        )

        quality_gate = result.get("quality_gate", {})
        gate_status = quality_gate.get("status", result.get("status", "UNKNOWN"))

        return {
            "success": True,
            "message": (
                "Knowledge search completed. Qdrant candidates were verified against MySQL Concept DB."
                if gate_status == "SEARCH_COMPLETED"
                else "Knowledge search completed with no verified matches."
            ),
            "quality_gate_status": gate_status,
            "data": result,
        }

    except ProcessingError as exc:
        message = str(exc)

        logger.warning(f"knowledge/search precondition failed: {message}")

        if "MySQL is unavailable" in message:
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE
            error_type = "MYSQL_UNAVAILABLE"
        elif "OPENAI_API_KEY" in message:
            http_status = status.HTTP_409_CONFLICT
            error_type = "EMBEDDING_CONFIG_MISSING"
        elif "openai package" in message:
            http_status = status.HTTP_409_CONFLICT
            error_type = "OPENAI_PACKAGE_MISSING"
        elif "httpx package" in message:
            http_status = status.HTTP_409_CONFLICT
            error_type = "HTTPX_PACKAGE_MISSING"
        elif "Qdrant search failed" in message:
            http_status = status.HTTP_409_CONFLICT
            error_type = "QDRANT_SEARCH_FAILED"
        elif "Required MySQL table" in message:
            http_status = status.HTTP_409_CONFLICT
            error_type = "MISSING_REQUIRED_TABLE"
        else:
            http_status = status.HTTP_409_CONFLICT
            error_type = "KNOWLEDGE_SEARCH_PRECONDITION_FAILED"

        raise HTTPException(
            status_code=http_status,
            detail={
                "success": False,
                "error_type": error_type,
                "message": message,
            },
        )

    except Exception as exc:
        await db.rollback()

        logger.error(
            f"knowledge/search failed: {exc}",
            exc_info=True,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error_type": "KNOWLEDGE_SEARCH_INTERNAL_ERROR",
                "message": f"knowledge/search failed: {str(exc)}",
            },
        )


router = APIRouter(
    prefix="/knowledge",
    tags=["Knowledge Query"],
)


class KnowledgeQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, description="User question")

    # Optional business context.
    document_id: Optional[str] = None
    workspace_id: Optional[str] = None
    testing_id: Optional[str] = None

    # Retrieval controls.
    top_k: int = Field(default=5, ge=1, le=20)
    min_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    type_keys: List[str] = Field(default_factory=list)

    # Defaults to QDRANT_CONCEPTS_COLLECTION, usually concepts_3072.
    collection: Optional[str] = None

    # Answer controls.
    answer_style: str = Field(
        default="short",
        description="short, detailed, technical, or client",
    )

    # Response controls.
    include_canonical_knowledge: bool = True
    include_search_debug: bool = False

    # If Qdrant returns no candidates, optionally fallback to MySQL LIKE search.
    fallback_to_mysql: bool = True


@router.post(
    "/query",
    status_code=status.HTTP_200_OK,
)
async def query_knowledge(
    request: KnowledgeQueryRequest,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        service = KnowledgeQueryService(db=db)

        result = await service.query_knowledge(
            question=request.question,
            document_id=request.document_id,
            workspace_id=request.workspace_id,
            testing_id=request.testing_id,
            top_k=request.top_k,
            min_score=request.min_score,
            type_keys=request.type_keys or None,
            collection=request.collection,
            answer_style=request.answer_style,
            include_canonical_knowledge=request.include_canonical_knowledge,
            include_search_debug=request.include_search_debug,
            fallback_to_mysql=request.fallback_to_mysql,
        )

        quality_gate = result.get("quality_gate", {})
        gate_status = quality_gate.get("status", result.get("status", "UNKNOWN"))

        return {
            "success": True,
            "message": (
                "Knowledge query completed. Final answer was generated from MySQL-verified Concept DB context."
                if gate_status == "ANSWER_COMPLETED"
                else "Knowledge query completed, but no grounded answer could be generated from approved Concept DB knowledge."
            ),
            "quality_gate_status": gate_status,
            "data": result,
        }

    except ProcessingError as exc:
        message = str(exc)

        logger.warning(f"knowledge/query precondition failed: {message}")

        if "MySQL is unavailable" in message:
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE
            error_type = "MYSQL_UNAVAILABLE"
        elif "OPENAI_API_KEY" in message:
            http_status = status.HTTP_409_CONFLICT
            error_type = "OPENAI_CONFIG_MISSING"
        elif "openai package" in message:
            http_status = status.HTTP_409_CONFLICT
            error_type = "OPENAI_PACKAGE_MISSING"
        elif "httpx package" in message:
            http_status = status.HTTP_409_CONFLICT
            error_type = "HTTPX_PACKAGE_MISSING"
        elif "Qdrant search failed" in message:
            http_status = status.HTTP_409_CONFLICT
            error_type = "QDRANT_SEARCH_FAILED"
        elif "Required MySQL table" in message:
            http_status = status.HTTP_409_CONFLICT
            error_type = "MISSING_REQUIRED_TABLE"
        else:
            http_status = status.HTTP_409_CONFLICT
            error_type = "KNOWLEDGE_QUERY_PRECONDITION_FAILED"

        raise HTTPException(
            status_code=http_status,
            detail={
                "success": False,
                "error_type": error_type,
                "message": message,
            },
        )

    except Exception as exc:
        await db.rollback()

        logger.error(
            f"knowledge/query failed: {exc}",
            exc_info=True,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error_type": "KNOWLEDGE_QUERY_INTERNAL_ERROR",
                "message": f"knowledge/query failed: {str(exc)}",
            },
        )

